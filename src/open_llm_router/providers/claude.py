import json
import time
import uuid
from typing import Dict, Any, AsyncGenerator, List
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from .base import BaseProvider
from ..utils.logger import proxy_logger


class ClaudeProvider(BaseProvider):
    def convert_openai_to_anthropic_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert OpenAI messages format to Anthropic format"""
        anthropic_msgs = []

        for i, m in enumerate(messages):
            proxy_logger.debug(
                f"Processing message {i}: role={m.get('role')}, has_content={bool(m.get('content'))}"
            )

            # Skip messages without content
            if not m.get("content"):
                proxy_logger.debug(f"Skipping message {i} - no content")
                continue

            role = m["role"]

            # Only allow user and assistant roles for Anthropic
            if role not in ("user", "assistant"):
                proxy_logger.debug(f"Skipping message {i} - invalid role: {role}")
                continue

            anthropic_msgs.append({"role": role, "content": m["content"]})

        return anthropic_msgs

    async def handle_request(self, body: Dict[str, Any], stream: bool = False):
        """Handle Claude-specific request processing"""
        model = body.get("model")
        proxy_logger.info(f"Processing Claude model: {model}")
        start_time = time.time()

        try:
            # Convert OpenAI messages to Anthropic format
            messages = body.get("messages", [])
            anthropic_msgs = self.convert_openai_to_anthropic_messages(messages)

            proxy_logger.info(
                f"Converted {len(messages)} messages to {len(anthropic_msgs)} Anthropic messages"
            )

            # Build Claude-specific payload (Anthropic API format)
            payload = {
                "model": model,
                "max_tokens": body.get("max_tokens", 1024),
                "messages": anthropic_msgs,
            }

            # Add optional parameters
            if "temperature" in body:
                payload["temperature"] = body["temperature"]
            if stream:
                payload["stream"] = True

            proxy_logger.debug(f"Claude payload: {json.dumps(payload, indent=2)}")

            # Build Anthropic-specific headers
            api_key = self.backend["api_key"]
            claude_headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }

            # Generate response ID for OpenAI compatibility
            openai_resp_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
            proxy_logger.info(f"Generated response ID: {openai_resp_id}")

            # Log the upstream request
            url = self.backend["base_url"]
            proxy_logger.log_request("claude", model, url, stream)

            async with httpx.AsyncClient(timeout=120) as client:
                try:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=claude_headers,
                        timeout=120,
                    )

                    # Log the upstream response
                    proxy_logger.time_and_log_response(
                        "claude", model, response, start_time
                    )

                    if stream:
                        proxy_logger.info("Starting Claude streaming response")
                        return StreamingResponse(
                            self.claude_stream_response(
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
                        proxy_logger.info("Creating Claude non-streaming response")
                        if response.status_code != 200:
                            error_detail = await self.get_error_detail(response)
                            raise HTTPException(
                                status_code=response.status_code, detail=error_detail
                            )

                        resp_json = response.json()
                        proxy_logger.debug(
                            f"Claude response JSON: {json.dumps(resp_json, indent=2)}"
                        )

                        # Convert Claude response to OpenAI format
                        openai_resp = await self.convert_claude_to_openai_response(
                            resp_json, model, openai_resp_id
                        )

                        proxy_logger.info(
                            "Claude non-streaming response created successfully"
                        )
                        return JSONResponse(content=openai_resp)

                except httpx.TimeoutException:
                    proxy_logger.error(f"Timeout requesting Claude for model {model}")
                    raise HTTPException(
                        status_code=504, detail="Request timeout to Claude"
                    )
                except httpx.RequestError as e:
                    proxy_logger.error(f"Request error to Claude: {str(e)}")
                    raise HTTPException(
                        status_code=502, detail=f"Claude request failed: {str(e)}"
                    )

        except Exception as e:
            proxy_logger.error(
                f"Unexpected error in Claude processing: {str(e)}", exc_info=True
            )
            error_response = {"error": f"Claude model processing failed: {str(e)}"}
            return JSONResponse(
                content=error_response,
                status_code=500,
            )

    async def claude_stream_response(
        self, response: httpx.Response, model: str, openai_resp_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream Claude response and convert to OpenAI format"""
        try:
            text_accum = ""
            created_time = int(time.time())
            event_count = 0

            proxy_logger.debug("Processing Anthropic Claude stream events")

            # Process the streaming response from Anthropic API
            async for chunk in response.aiter_text():
                if not chunk.strip():
                    continue

                # Anthropic API sends Server-Sent Events format
                lines = chunk.strip().split("\n")
                for line in lines:
                    if line.startswith("data: "):
                        data_part = line[6:]  # Remove 'data: ' prefix

                        if data_part == "[DONE]":
                            proxy_logger.info(
                                f"Claude streaming completed - processed {event_count} events"
                            )
                            yield "data: [DONE]\n\n"
                            return

                        try:
                            event_count += 1
                            event_data = json.loads(data_part)
                            proxy_logger.debug(
                                f"Claude event {event_count}: type={event_data.get('type')}"
                            )

                            if event_data.get("type") == "content_block_delta":
                                delta_text = event_data.get("delta", {}).get("text", "")
                                if not delta_text:
                                    proxy_logger.debug(
                                        f"Claude event {event_count}: no delta text"
                                    )
                                    continue

                                text_accum += delta_text
                                stream_payload = {
                                    "id": openai_resp_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": delta_text},
                                            "finish_reason": None,
                                        }
                                    ],
                                }

                                proxy_logger.debug(
                                    f"Yielding Claude event {event_count}"
                                )
                                yield f"data: {json.dumps(stream_payload, ensure_ascii=False)}\n\n"

                            elif event_data.get("type") == "message_stop":
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
                                            "finish_reason": "stop",
                                        }
                                    ],
                                }
                                yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"

                                proxy_logger.info(
                                    f"Claude streaming completed - processed {event_count} events"
                                )
                                yield "data: [DONE]\n\n"
                                return

                        except json.JSONDecodeError as e:
                            proxy_logger.warning(
                                f"Invalid JSON in Claude stream chunk: {data_part[:100]} - {e}"
                            )
                            continue

            proxy_logger.debug(
                f"Claude stream completed - processed {event_count} events"
            )
            yield "data: [DONE]\n\n"

        except Exception as e:
            proxy_logger.error(
                f"Exception in Claude event generator: {str(e)}", exc_info=True
            )
            error_payload = {"error": f"Claude stream processing failed: {str(e)}"}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    async def convert_claude_to_openai_response(
        self, resp_json: Dict[str, Any], model: str, openai_resp_id: str
    ) -> Dict[str, Any]:
        """Convert Claude non-streaming response to OpenAI format"""
        answer = ""

        try:
            # Extract answer from Anthropic API response structure
            if (
                "content" in resp_json
                and isinstance(resp_json["content"], list)
                and resp_json["content"]
            ):
                # Anthropic API format with content blocks
                for block in resp_json["content"]:
                    if block.get("type") == "text":
                        answer += block.get("text", "")
                proxy_logger.debug(
                    f"Extracted answer from content blocks: {len(answer)} chars"
                )

            elif "completion" in resp_json:
                # Legacy format fallback
                answer = resp_json["completion"]
                proxy_logger.debug(
                    f"Extracted answer from completion: {len(answer)} chars"
                )

            else:
                proxy_logger.error("Error extracting answer from Claude response")
                answer = ""

        except Exception as e:
            proxy_logger.error(f"Error extracting answer from Claude response: {e}")
            answer = ""

        # Convert Anthropic stop_reason to OpenAI finish_reason
        stop_reason = resp_json.get("stop_reason", "stop")
        finish_reason = "stop" if stop_reason == "end_turn" else stop_reason

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
            "usage": resp_json.get("usage", {}),
        }

        proxy_logger.info("Claude non-streaming response created successfully")
        return openai_resp
