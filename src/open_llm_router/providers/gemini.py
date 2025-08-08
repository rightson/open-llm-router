import json
import time
import uuid
from typing import Dict, Any, AsyncGenerator, List
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from .base import BaseProvider
from ..utils.logger import proxy_logger


class GeminiProvider(BaseProvider):
    def __init__(self, backend: Dict[str, Any], backends_config: Dict[str, Any]):
        super().__init__(backend)
        self.backends_config = backends_config

    def convert_openai_to_gemini_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert OpenAI messages format to Gemini format"""
        gemini_contents = []

        for i, m in enumerate(messages):
            proxy_logger.debug(
                f"Processing message {i}: role={m.get('role')}, has_content={bool(m.get('content'))}"
            )

            # Skip messages without content
            if not m.get("content"):
                proxy_logger.debug(f"Skipping message {i} - no content")
                continue

            role = m["role"]
            content = m["content"]

            # Convert role to Gemini format (user stays user, assistant becomes model)
            gemini_role = "user" if role == "user" else "model"

            # Skip system messages as Gemini doesn't support them in the same way
            if role == "system":
                proxy_logger.debug(
                    f"Skipping message {i} - system role not supported in Gemini"
                )
                continue

            # Create Gemini content format (no role needed for request)
            gemini_content = {"parts": [{"text": content}]}

            gemini_contents.append(gemini_content)

        return gemini_contents

    async def handle_request(self, body: Dict[str, Any], stream: bool = False):
        """Handle Gemini-specific request processing"""
        model = body.get("model")
        proxy_logger.info(f"Processing Gemini model: {model}")
        start_time = time.time()

        try:
            # Convert OpenAI messages to Gemini format
            messages = body.get("messages", [])
            gemini_contents = self.convert_openai_to_gemini_messages(messages)

            proxy_logger.info(
                f"Converted {len(messages)} messages to {len(gemini_contents)} Gemini contents"
            )

            # Build Gemini-specific payload
            payload = {"contents": gemini_contents}

            # Add optional parameters
            if "temperature" in body:
                payload["generationConfig"] = {"temperature": body["temperature"]}

            # Add max_tokens if specified
            if "max_tokens" in body:
                if "generationConfig" not in payload:
                    payload["generationConfig"] = {}
                payload["generationConfig"]["maxOutputTokens"] = body["max_tokens"]

            # Streaming is handled differently for Gemini
            if stream:
                # For streaming, we need to use the streamGenerateContent endpoint
                # This will be handled in the URL construction below
                pass

            proxy_logger.debug(f"Gemini payload: {json.dumps(payload, indent=2)}")

            # Get model name from the request
            model_name = body.get("model", "gemini-pro")

            # Build Gemini-specific headers and URL
            api_key = self.backend["api_key"]
            gemini_headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": api_key,
            }

            # Construct the full URL with model name and endpoint type
            # For Gemini, we need the original base_url from providers config, not the processed backend URL
            original_config = self.backends_config.get("providers", {}).get(
                "gemini", {}
            )
            gemini_base_url = original_config.get(
                "base_url", "https://generativelanguage.googleapis.com/v1beta"
            )
            if stream:
                # Use streaming endpoint
                gemini_url = (
                    f"{gemini_base_url}/models/{model_name}:streamGenerateContent"
                )
            else:
                # Use regular endpoint
                gemini_url = f"{gemini_base_url}/models/{model_name}:generateContent"

            proxy_logger.info(f"Gemini URL: {gemini_url}")

            # Generate response ID for OpenAI compatibility
            openai_resp_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
            proxy_logger.info(f"Generated response ID: {openai_resp_id}")

            # Log the upstream request
            proxy_logger.log_request("gemini", model, gemini_url, stream)

            async with httpx.AsyncClient(timeout=120) as client:
                try:
                    response = await client.post(
                        gemini_url,
                        json=payload,
                        headers=gemini_headers,
                        timeout=120,
                    )

                    # Log the upstream response
                    proxy_logger.time_and_log_response(
                        "gemini", model, response, start_time
                    )

                    if stream:
                        proxy_logger.info("Starting Gemini streaming response")
                        return StreamingResponse(
                            self.gemini_stream_response(
                                response, model, openai_resp_id
                            ),
                            media_type="text/event-stream",
                            headers={
                                "Cache-Control": "no-cache",
                                "Connection": "keep-alive",
                                "Access-Control-Allow-Origin": "*",
                                "Access-Control-Allow-Headers": "*",
                            },
                        )
                    else:
                        proxy_logger.info("Creating Gemini non-streaming response")
                        if response.status_code != 200:
                            error_detail = await self.get_error_detail(response)
                            raise HTTPException(
                                status_code=response.status_code, detail=error_detail
                            )

                        resp_json = response.json()
                        proxy_logger.debug(
                            f"Gemini response JSON: {json.dumps(resp_json, indent=2)}"
                        )

                        # Convert Gemini response to OpenAI format
                        openai_resp = await self.convert_gemini_to_openai_response(
                            resp_json, model, openai_resp_id
                        )

                        proxy_logger.info(
                            "Gemini non-streaming response created successfully"
                        )
                        return JSONResponse(content=openai_resp)

                except httpx.TimeoutException:
                    proxy_logger.error(f"Timeout requesting Gemini for model {model}")
                    raise HTTPException(
                        status_code=504, detail="Request timeout to Gemini"
                    )
                except httpx.RequestError as e:
                    proxy_logger.error(f"Request error to Gemini: {str(e)}")
                    raise HTTPException(
                        status_code=502, detail=f"Gemini request failed: {str(e)}"
                    )

        except Exception as e:
            proxy_logger.error(
                f"Unexpected error in Gemini processing: {str(e)}", exc_info=True
            )
            error_response = {"error": f"Gemini model processing failed: {str(e)}"}
            return JSONResponse(
                content=error_response,
                status_code=500,
            )

    async def convert_gemini_to_openai_response(
        self, resp_json: Dict[str, Any], model: str, openai_resp_id: str
    ) -> Dict[str, Any]:
        """Convert Gemini non-streaming response to OpenAI format"""
        answer = ""

        try:
            # Extract answer from Gemini API response structure
            if (
                "candidates" in resp_json
                and isinstance(resp_json["candidates"], list)
                and resp_json["candidates"]
            ):
                # Gemini API format with candidates
                candidate = resp_json["candidates"][0]  # Use first candidate
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if part.get("text"):
                            answer += part["text"]
                    proxy_logger.debug(
                        f"Extracted answer from Gemini parts: {len(answer)} chars"
                    )
            else:
                proxy_logger.error("Error extracting answer from Gemini response")
                answer = ""

        except Exception as e:
            proxy_logger.error(f"Error extracting answer from Gemini response: {e}")
            answer = ""

        # Convert Gemini finish_reason to OpenAI finish_reason
        finish_reason = "stop"  # Default
        try:
            if (
                "candidates" in resp_json
                and resp_json["candidates"]
                and "finishReason" in resp_json["candidates"][0]
            ):
                gemini_finish = resp_json["candidates"][0]["finishReason"]
                # Map Gemini finish reasons to OpenAI format
                finish_reason_map = {
                    "STOP": "stop",
                    "MAX_TOKENS": "length",
                    "SAFETY": "content_filter",
                    "RECITATION": "content_filter",
                    "OTHER": "stop",
                }
                finish_reason = finish_reason_map.get(gemini_finish, "stop")
        except Exception as e:
            proxy_logger.warning(
                f"Could not extract finish reason from Gemini response: {e}"
            )

        # Build usage information from Gemini response
        usage_info = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            if "usageMetadata" in resp_json:
                usage_metadata = resp_json["usageMetadata"]
                usage_info = {
                    "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                    "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                    "total_tokens": usage_metadata.get("totalTokenCount", 0),
                }
        except Exception as e:
            proxy_logger.warning(
                f"Could not extract usage info from Gemini response: {e}"
            )

        # Build OpenAI-compatible response
        openai_resp = {
            "id": openai_resp_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage_info,
        }

        proxy_logger.info("Gemini non-streaming response created successfully")
        return openai_resp

    async def gemini_stream_response(
        self, response, model: str, openai_resp_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Streams Gemini API array responses as OpenAI-compatible SSE stream.

        Gemini's :streamGenerateContent returns an array of JSON objects:
        [ {...}, {...}, ... ]
        This function parses that stream robustly and yields OpenAI API style chunks.
        """
        buffer = ""
        started = False
        ended = False
        created_time = int(time.time())
        text_accum = ""

        brace_level = 0
        obj_buffer = ""
        inside_obj = False

        try:
            async for chunk in response.aiter_text():
                if not chunk.strip():
                    continue
                buffer += chunk

                # Remove array opening bracket (if present in the first chunk)
                if not started:
                    buffer = buffer.lstrip()
                    if buffer.startswith("["):
                        buffer = buffer[1:]
                        started = True

                i = 0
                while i < len(buffer):
                    c = buffer[i]
                    if not inside_obj:
                        if c == "{":
                            inside_obj = True
                            brace_level = 1
                            obj_buffer = "{"
                        i += 1
                        continue
                    else:
                        obj_buffer += c
                        if c == "{":
                            brace_level += 1
                        elif c == "}":
                            brace_level -= 1
                            if brace_level == 0:
                                # Complete JSON object found
                                try:
                                    event_data = json.loads(obj_buffer)
                                    # ---- Begin OpenAI chunk conversion logic ----
                                    # This part is critical: convert Gemini response object to OpenAI SSE chunk(s)
                                    if "candidates" in event_data:
                                        candidates = event_data["candidates"]
                                        if candidates and len(candidates) > 0:
                                            candidate = candidates[0]
                                            # Output delta chunk
                                            if (
                                                "content" in candidate
                                                and "parts" in candidate["content"]
                                            ):
                                                parts = candidate["content"]["parts"]
                                                delta_text = ""
                                                for part in parts:
                                                    if "text" in part:
                                                        full_text = part["text"]
                                                        if full_text.startswith(
                                                            text_accum
                                                        ):
                                                            delta_text = full_text[
                                                                len(text_accum) :
                                                            ]
                                                            text_accum = full_text
                                                        else:
                                                            delta_text = full_text
                                                            text_accum += delta_text
                                                if delta_text:
                                                    stream_payload = {
                                                        "id": openai_resp_id,
                                                        "object": "chat.completion.chunk",
                                                        "created": created_time,
                                                        "model": model,
                                                        "choices": [
                                                            {
                                                                "index": 0,
                                                                "delta": {
                                                                    "content": delta_text
                                                                },
                                                                "finish_reason": None,
                                                            }
                                                        ],
                                                    }
                                                    yield f"data: {json.dumps(stream_payload, ensure_ascii=False)}\n\n"

                                            # Output finish reason
                                            if "finishReason" in candidate:
                                                gemini_finish = candidate[
                                                    "finishReason"
                                                ]
                                                finish_reason_map = {
                                                    "STOP": "stop",
                                                    "MAX_TOKENS": "length",
                                                    "SAFETY": "content_filter",
                                                    "RECITATION": "content_filter",
                                                    "OTHER": "stop",
                                                }
                                                finish_reason = finish_reason_map.get(
                                                    gemini_finish, "stop"
                                                )
                                                # Send final chunk with finish_reason
                                                final_payload = {
                                                    "id": openai_resp_id,
                                                    "object": "chat.completion.chunk",
                                                    "created": created_time,
                                                    "model": model,
                                                    "choices": [
                                                        {
                                                            "index": 0,
                                                            "delta": {},
                                                            "finish_reason": finish_reason,
                                                        }
                                                    ],
                                                }
                                                yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
                                                yield "data: [DONE]\n\n"
                                                ended = True
                                                return
                                    # ---- End OpenAI chunk conversion logic ----
                                except Exception as e:
                                    # Ignore parse errors, continue
                                    pass
                                inside_obj = False
                                obj_buffer = ""
                        i += 1

                # Trim processed buffer (keep only unparsed part)
                if not inside_obj:
                    buffer = buffer[i:]
                else:
                    buffer = buffer[i - len(obj_buffer) :]

                # If end of array, stop
                if buffer.strip().startswith("]"):
                    break

            if not ended:
                yield "data: [DONE]\n\n"
        except Exception as e:
            # Log and yield an error as OpenAI format
            import traceback

            proxy_logger.error("Error in gemini_stream_response:", str(e))
            proxy_logger.error(traceback.format_exc())
            error_payload = {"error": f"Gemini stream processing failed: {str(e)}"}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
