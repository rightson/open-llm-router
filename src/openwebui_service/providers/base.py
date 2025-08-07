import json
import time
import uuid
from typing import Dict, Any, AsyncGenerator
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from ..utils.logger import proxy_logger


class BaseProvider:
    def __init__(self, backend: Dict[str, Any]):
        self.backend = backend
        self.backend_name = backend["backend_name"]

    async def handle_request(self, body: Dict[str, Any], stream: bool = False):
        """Handle request - to be implemented by subclasses"""
        raise NotImplementedError

    async def get_error_detail(self, response: httpx.Response) -> str:
        """Extract error details from backend response"""
        try:
            error_data = response.json()
            if isinstance(error_data, dict) and "error" in error_data:
                error_info = error_data["error"]
                if isinstance(error_info, dict):
                    return error_info.get(
                        "message", f"Backend error: {response.status_code}"
                    )
                else:
                    return str(error_info)
            else:
                return f"Backend error: {response.status_code}"
        except Exception:
            return f"Backend error: {response.status_code} - {response.text[:200]}"

    def format_openai_response(
        self, response_data: Dict[str, Any], model: str
    ) -> Dict[str, Any]:
        """Format response to ensure OpenAI compatibility"""
        # If already in correct format, return as-is
        if all(
            key in response_data
            for key in ["id", "object", "created", "model", "choices"]
        ):
            return response_data

        # Generate OpenAI-compatible response
        formatted_response = {
            "id": response_data.get("id", f"chatcmpl-{uuid.uuid4().hex[:29]}"),
            "object": "chat.completion",
            "created": response_data.get("created", int(time.time())),
            "model": model,
            "choices": [],
            "usage": response_data.get(
                "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            ),
            "system_fingerprint": f"{self.backend_name}-proxy",
        }

        # Handle different response formats
        if "choices" in response_data:
            formatted_response["choices"] = response_data["choices"]
        elif "message" in response_data:
            # Single message format
            formatted_response["choices"] = [
                {
                    "index": 0,
                    "message": response_data["message"],
                    "finish_reason": response_data.get("finish_reason", "stop"),
                }
            ]
        elif "content" in response_data:
            # Direct content format
            formatted_response["choices"] = [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_data["content"],
                    },
                    "finish_reason": "stop",
                }
            ]

        return formatted_response

    async def stream_response(
        self, response: httpx.Response
    ) -> AsyncGenerator[str, None]:
        """Stream response from backend while maintaining OpenAI format"""
        try:
            chunk_count = 0
            async for chunk in response.aiter_text():
                if chunk:
                    chunk_count += 1
                    proxy_logger.debug(f"Processing chunk {chunk_count}")

                    # Parse the SSE chunk
                    lines = chunk.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if line.startswith("data: "):
                            data_part = line[6:]  # Remove 'data: ' prefix

                            if data_part == "[DONE]":
                                proxy_logger.debug("Stream completed - sending [DONE]")
                                yield "data: [DONE]\n\n"
                                return

                            try:
                                # Parse and re-serialize to ensure valid JSON
                                chunk_dict = json.loads(data_part)

                                # Create OpenAI-compatible streaming chunk
                                if "choices" in chunk_dict:
                                    # Already in correct format
                                    payload = chunk_dict
                                else:
                                    # Convert to OpenAI streaming format
                                    payload = {
                                        "id": chunk_dict.get(
                                            "id", f"chatcmpl-{uuid.uuid4().hex[:29]}"
                                        ),
                                        "object": "chat.completion.chunk",
                                        "created": chunk_dict.get(
                                            "created", int(time.time())
                                        ),
                                        "model": chunk_dict.get("model", "unknown"),
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": chunk_dict.get("delta", {}),
                                                "finish_reason": chunk_dict.get(
                                                    "finish_reason"
                                                ),
                                            }
                                        ],
                                    }

                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                            except json.JSONDecodeError as e:
                                proxy_logger.warning(
                                    f"Invalid JSON in stream chunk: {data_part[:100]} - {e}"
                                )
                                continue
                        elif line and not line.startswith("data:"):
                            proxy_logger.debug(f"Non-data line in stream: {line}")

            proxy_logger.debug(f"Stream completed - processed {chunk_count} chunks")
            yield "data: [DONE]\n\n"

        except Exception as e:
            proxy_logger.error(f"Exception in stream_response: {str(e)}")
            # Send error in SSE format
            error_payload = {
                "error": {
                    "message": f"Stream processing error: {str(e)}",
                    "type": "stream_error",
                }
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
