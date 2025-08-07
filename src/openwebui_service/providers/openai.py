import time
from typing import Dict, Any
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from .base import BaseProvider
from ..utils.logger import proxy_logger


class OpenAIProvider(BaseProvider):
    async def handle_request(self, body: Dict[str, Any], stream: bool = False):
        """Handle OpenAI and OpenAI-compatible provider requests"""
        model = body.get("model")
        proxy_logger.info(f"Processing {self.backend_name} model: {model}")
        start_time = time.time()

        # Log the upstream request
        url = self.backend["base_url"]
        proxy_logger.log_request(self.backend_name, model, url, stream)

        # Make request to backend (for OpenAI-compatible backends)
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(
                    url,
                    json=body,
                    headers=self.backend["headers"],
                    timeout=120,
                )

                # Log the upstream response
                proxy_logger.time_and_log_response(
                    self.backend_name, model, response, start_time
                )

                # Handle different response types
                if stream:
                    # Check if the backend response is actually streaming
                    if response.headers.get("content-type", "").startswith(
                        "text/event-stream"
                    ):
                        return StreamingResponse(
                            self.stream_response(response),
                            media_type="text/event-stream",
                            headers={
                                "Cache-Control": "no-cache",
                                "Connection": "keep-alive",
                                "Access-Control-Allow-Origin": "*",
                                "Access-Control-Allow-Headers": "*",
                            },
                        )
                    else:
                        # Backend didn't return a stream, treat as non-streaming
                        proxy_logger.warning(
                            f"Expected streaming response but got {response.headers.get('content-type')}"
                        )
                        response_data = response.json()
                        formatted_response = self.format_openai_response(
                            response_data, model
                        )
                        return JSONResponse(content=formatted_response)
                else:
                    # Handle non-streaming response
                    if response.status_code != 200:
                        error_detail = await self.get_error_detail(response)
                        raise HTTPException(
                            status_code=response.status_code, detail=error_detail
                        )

                    response_data = response.json()

                    # Ensure OpenAI-compatible response format
                    formatted_response = self.format_openai_response(
                        response_data, model
                    )

                    return JSONResponse(content=formatted_response)

            except httpx.TimeoutException:
                proxy_logger.error(
                    f"Timeout requesting {self.backend_name} for model {model}"
                )
                raise HTTPException(
                    status_code=504,
                    detail=f"Request timeout to {self.backend_name}",
                )
            except httpx.RequestError as e:
                proxy_logger.error(f"Request error to {self.backend_name}: {str(e)}")
                raise HTTPException(
                    status_code=502, detail=f"Backend request failed: {str(e)}"
                )
