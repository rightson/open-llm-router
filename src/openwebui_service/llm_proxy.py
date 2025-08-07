from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
import uuid

app = FastAPI()

# API KEY configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxxx")
GROK_API_KEY = os.getenv("GROK_API_KEY", "gsk-xxxx")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "sk-ant-xxx")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIza...")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load backend configurations
def load_backends() -> Dict[str, Any]:
    """Load backend configurations from conf/backends.json or conf/backends.example.json"""
    backends_file = Path("conf/backends.json")
    example_file = Path("conf/backends.example.json")

    if backends_file.exists():
        with open(backends_file, "r") as f:
            config = json.load(f)
    elif example_file.exists():
        with open(example_file, "r") as f:
            config = json.load(f)
    else:
        # Fallback to hardcoded configuration
        config = {
            "providers": {
                "openai": {
                    "name": "OpenAI",
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "endpoints": {"chat_completions": "/chat/completions"},
                    "models": ["gpt-4", "gpt-3.5-turbo"],
                    "model_prefixes": ["gpt-"],
                },
                "grok": {
                    "name": "Groq",
                    "base_url": "https://api.grok.com/openai/v1",
                    "api_key_env": "GROK_API_KEY",
                    "endpoints": {"chat_completions": "/chat/completions"},
                    "models": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
                    "model_prefixes": ["llama", "mixtral"],
                },
            },
            "model_aliases": {},
            "default_models": {"chat": "gpt-3.5-turbo"},
        }

    # Convert new format to legacy format for compatibility
    if "providers" in config:
        legacy_config = {
            "backends": {},
            "model_aliases": config.get("model_aliases", {}),
            "default_models": config.get("default_models", {"chat": "gpt-3.5-turbo"}),
        }

        for provider_name, provider_config in config["providers"].items():
            # Convert to legacy backend format
            base_url = provider_config["base_url"]
            chat_endpoint = provider_config.get("endpoints", {}).get(
                "chat_completions", "/chat/completions"
            )
            full_url = base_url + chat_endpoint

            legacy_config["backends"][provider_name] = {
                "name": provider_config["name"],
                "base_url": full_url,
                "api_key_env": provider_config["api_key_env"],
                "headers_template": {"Authorization": "Bearer {api_key}"},
                "models": provider_config.get("models", []),
                "model_prefixes": provider_config.get("model_prefixes", []),
            }

        return legacy_config

    return config


# Load backends configuration at startup
BACKENDS_CONFIG = load_backends()


def get_backend_for_model(model: str) -> str:
    """Determine which backend to use for a given model"""
    # Check model aliases first
    model_aliases = BACKENDS_CONFIG.get("model_aliases", {})
    if model in model_aliases:
        model = model_aliases[model]

    # Check each backend's models
    backends = BACKENDS_CONFIG.get("backends", {})
    for backend_name, backend_config in backends.items():
        models = backend_config.get("models", [])
        if model in models:
            return backend_name

    # Fallback to prefix-based matching for backward compatibility
    for backend_name, backend_config in backends.items():
        model_prefixes = backend_config.get("model_prefixes", [])
        for prefix in model_prefixes:
            if model.startswith(prefix):
                return backend_name

    raise HTTPException(400, f"Unknown model: {model}")


def get_api_key_for_backend(backend_name: str, backend_config: Dict[str, Any]) -> str:
    """Get API key for a backend"""
    api_key_env = backend_config.get("api_key_env")
    if not api_key_env:
        raise HTTPException(
            500, f"No API key environment variable configured for {backend_name}"
        )

    api_key = os.getenv(api_key_env)
    if not api_key:
        # Fallback to legacy environment variables
        legacy_keys = {
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "GROK_API_KEY": GROK_API_KEY,
            "CLAUDE_API_KEY": CLAUDE_API_KEY,
            "GEMINI_API_KEY": GEMINI_API_KEY,
        }
        api_key = legacy_keys.get(api_key_env, f"default-{backend_name}-key")

    return api_key


def convert_openai_to_anthropic_messages(messages):
    """Convert OpenAI messages format to Anthropic format"""
    anthropic_msgs = []

    for i, m in enumerate(messages):
        logger.debug(
            f"Processing message {i}: role={m.get('role')}, has_content={bool(m.get('content'))}"
        )

        # Skip messages without content
        if not m.get("content"):
            logger.debug(f"Skipping message {i} - no content")
            continue

        role = m["role"]

        # Only allow user and assistant roles for Anthropic
        if role not in ("user", "assistant"):
            logger.debug(f"Skipping message {i} - invalid role: {role}")
            continue

        anthropic_msgs.append({"role": role, "content": m["content"]})

    return anthropic_msgs


async def handle_claude_request(body, backend, stream):
    """Handle Claude-specific request processing"""
    logger.info(f"Processing Claude model: {body.get('model')}")

    try:
        # Convert OpenAI messages to Anthropic format
        messages = body.get("messages", [])
        anthropic_msgs = convert_openai_to_anthropic_messages(messages)

        logger.info(
            f"Converted {len(messages)} messages to {len(anthropic_msgs)} Anthropic messages"
        )

        # Build Claude-specific payload
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": body.get("max_tokens", 4096),
            "temperature": body.get("temperature", 1.0),
            "messages": anthropic_msgs,
        }

        logger.debug(f"Claude payload: {json.dumps(payload, indent=2)}")

        # Generate response ID for OpenAI compatibility
        openai_resp_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        logger.info(f"Generated response ID: {openai_resp_id}")

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(
                    backend["base_url"],
                    json=payload,
                    headers=backend["headers"],
                    timeout=120,
                )

                if stream:
                    logger.info("Starting Claude streaming response")
                    return StreamingResponse(
                        claude_stream_response(
                            response, body.get("model"), openai_resp_id
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
                    logger.info("Creating Claude non-streaming response")
                    if response.status_code != 200:
                        error_detail = await get_error_detail(response)
                        raise HTTPException(
                            status_code=response.status_code, detail=error_detail
                        )

                    resp_json = response.json()
                    logger.debug(
                        f"Claude response JSON: {json.dumps(resp_json, indent=2)}"
                    )

                    # Convert Claude response to OpenAI format
                    openai_resp = await convert_claude_to_openai_response(
                        resp_json, body.get("model"), openai_resp_id
                    )

                    logger.info("Claude non-streaming response created successfully")
                    return JSONResponse(content=openai_resp)

            except httpx.TimeoutException:
                logger.error(f"Timeout requesting Claude for model {body.get('model')}")
                raise HTTPException(status_code=504, detail="Request timeout to Claude")
            except httpx.RequestError as e:
                logger.error(f"Request error to Claude: {str(e)}")
                raise HTTPException(
                    status_code=502, detail=f"Claude request failed: {str(e)}"
                )

    except Exception as e:
        logger.error(f"Unexpected error in Claude processing: {str(e)}", exc_info=True)
        error_response = {"error": f"Claude model processing failed: {str(e)}"}
        return JSONResponse(
            content=error_response,
            status_code=500,
        )


def choose_backend(model: str):
    """Choose the appropriate backend for the given model"""
    backend_name = get_backend_for_model(model)
    backends = BACKENDS_CONFIG.get("backends", {})

    if backend_name not in backends:
        raise HTTPException(400, f"Backend {backend_name} not found in configuration")

    backend_config = backends[backend_name]
    api_key = get_api_key_for_backend(backend_name, backend_config)

    # Build headers from template
    headers_template = backend_config.get(
        "headers_template", {"Authorization": "Bearer {api_key}"}
    )
    headers = {}
    for key, value in headers_template.items():
        if isinstance(value, str) and "{api_key}" in value:
            headers[key] = value.format(api_key=api_key)
        else:
            headers[key] = value

    return {
        "base_url": backend_config["base_url"],
        "api_key": api_key,
        "headers": headers,
        "backend_name": backend_name,
        "config": backend_config,
    }


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request, authorization: str = Header(None)):
    """Proxy chat completions requests to appropriate backend with full OpenAI compatibility"""
    try:
        # Parse request body
        body = await request.json()
        model = body.get("model", "gpt-3.5-turbo")
        stream = body.get("stream", False)

        logger.info(f"Proxying request for model: {model}, stream: {stream}")

        # Validate required fields
        if not body.get("messages"):
            raise HTTPException(
                status_code=400, detail="Missing required field: messages"
            )

        # Choose appropriate backend
        backend = choose_backend(model)

        # Handle Claude-specific processing
        if backend["backend_name"] == "claude":
            return await handle_claude_request(body, backend, stream)

        # Make request to backend (for non-Claude backends)
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(
                    backend["base_url"],
                    json=body,
                    headers=backend["headers"],
                    timeout=120,
                )

                # Handle different response types
                if stream:
                    # Check if the backend response is actually streaming
                    if response.headers.get("content-type", "").startswith(
                        "text/event-stream"
                    ):
                        return StreamingResponse(
                            stream_response(response),
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
                        logger.warning(
                            f"Expected streaming response but got {response.headers.get('content-type')}"
                        )
                        response_data = response.json()
                        formatted_response = format_openai_response(
                            response_data, model, backend["backend_name"]
                        )
                        return JSONResponse(content=formatted_response)
                else:
                    # Handle non-streaming response
                    if response.status_code != 200:
                        error_detail = await get_error_detail(response)
                        raise HTTPException(
                            status_code=response.status_code, detail=error_detail
                        )

                    response_data = response.json()

                    # Ensure OpenAI-compatible response format
                    formatted_response = format_openai_response(
                        response_data, model, backend["backend_name"]
                    )

                    return JSONResponse(content=formatted_response)

            except httpx.TimeoutException:
                logger.error(
                    f"Timeout requesting {backend['backend_name']} for model {model}"
                )
                raise HTTPException(
                    status_code=504,
                    detail=f"Request timeout to {backend['backend_name']}",
                )
            except httpx.RequestError as e:
                logger.error(f"Request error to {backend['backend_name']}: {str(e)}")
                raise HTTPException(
                    status_code=502, detail=f"Backend request failed: {str(e)}"
                )

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Unexpected error in proxy_chat_completions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def list_models():
    """List all available models"""
    all_models = []
    backends = BACKENDS_CONFIG.get("backends", {})

    for backend_name, backend_config in backends.items():
        models = backend_config.get("models", [])
        for model in models:
            all_models.append(
                {
                    "id": model,
                    "object": "model",
                    "created": 1677610602,
                    "owned_by": backend_config.get("name", backend_name),
                    "backend": backend_name,
                }
            )

    # Add model aliases
    model_aliases = BACKENDS_CONFIG.get("model_aliases", {})
    for alias, target in model_aliases.items():
        # Find the backend for the target model
        try:
            backend = get_backend_for_model(target)
            backend_config = backends.get(backend, {})
            all_models.append(
                {
                    "id": alias,
                    "object": "model",
                    "created": 1677610602,
                    "owned_by": backend_config.get("name", backend),
                    "backend": backend,
                    "alias_for": target,
                }
            )
        except Exception:
            continue

    return {"object": "list", "data": all_models}


@app.post("/admin/reload-backends")
def reload_backends():
    """Reload backend configurations from file (admin endpoint)"""
    global BACKENDS_CONFIG
    try:
        BACKENDS_CONFIG = load_backends()
        return {
            "status": "success",
            "message": "Backend configuration reloaded",
            "backends_count": len(BACKENDS_CONFIG.get("backends", {})),
            "models_count": sum(
                len(b.get("models", []))
                for b in BACKENDS_CONFIG.get("backends", {}).values()
            ),
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to reload backends: {str(e)}"}


@app.get("/admin/config")
def get_config():
    """Get current backend configuration (admin endpoint)"""
    return BACKENDS_CONFIG


async def claude_stream_response(
    response: httpx.Response, model: str, openai_resp_id: str
) -> AsyncGenerator[str, None]:
    """Stream Claude response and convert to OpenAI format"""
    try:
        text_accum = ""
        created_time = int(time.time())
        event_count = 0

        logger.debug("Processing Claude stream events")

        # Parse the response body as streaming JSON
        response_body = await response.aread()
        response_lines = response_body.decode().strip().split("\n")

        for event_line in response_lines:
            if not event_line.strip():
                continue

            try:
                event_count += 1
                # Parse each line as JSON (Claude sends individual JSON objects per line)
                chunk = json.loads(event_line)
                logger.debug(f"Claude event {event_count}: type={chunk.get('type')}")

                if chunk["type"] == "content_block_delta":
                    delta_text = chunk["delta"].get("text", "")
                    if not delta_text:
                        logger.debug(f"Claude event {event_count}: no delta text")
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

                    logger.debug(f"Yielding Claude event {event_count}")
                    yield f"data: {json.dumps(stream_payload, ensure_ascii=False)}\n\n"

                elif chunk["type"] == "message_stop":
                    logger.info(
                        f"Claude streaming completed - processed {event_count} events"
                    )
                    yield "data: [DONE]\n\n"
                    return

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Invalid JSON in Claude stream chunk: {event_line[:100]} - {e}"
                )
                continue

        logger.debug(f"Claude stream completed - processed {event_count} events")
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Exception in Claude event generator: {str(e)}", exc_info=True)
        error_payload = {"error": f"Claude stream processing failed: {str(e)}"}
        yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


async def convert_claude_to_openai_response(resp_json, model, openai_resp_id):
    """Convert Claude non-streaming response to OpenAI format"""
    answer = ""

    try:
        # Extract answer from Claude response structure
        if (
            "content" in resp_json
            and isinstance(resp_json["content"], list)
            and resp_json["content"]
        ):
            # Modern Claude API format with content blocks
            for block in resp_json["content"]:
                if block.get("type") == "text":
                    answer += block.get("text", "")
            logger.debug(f"Extracted answer from content blocks: {len(answer)} chars")

        elif "completion" in resp_json:
            # Legacy Claude API format
            answer = resp_json["completion"]
            logger.debug(f"Extracted answer from completion: {len(answer)} chars")

        else:
            logger.error("Error extracting answer from Claude response")
            answer = ""

    except Exception as e:
        logger.error(f"Error extracting answer from Claude response: {e}")
        answer = ""

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
                "finish_reason": "stop",
            }
        ],
        "usage": resp_json.get("usage", {}),
    }

    logger.info("Claude non-streaming response created successfully")
    return openai_resp


async def stream_response(response: httpx.Response) -> AsyncGenerator[str, None]:
    """Stream response from backend while maintaining OpenAI format"""
    try:
        chunk_count = 0
        async for chunk in response.aiter_text():
            if chunk:
                chunk_count += 1
                logger.debug(f"Processing chunk {chunk_count}")

                # Parse the SSE chunk
                lines = chunk.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("data: "):
                        data_part = line[6:]  # Remove 'data: ' prefix

                        if data_part == "[DONE]":
                            logger.debug("Stream completed - sending [DONE]")
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
                            logger.warning(
                                f"Invalid JSON in stream chunk: {data_part[:100]} - {e}"
                            )
                            continue
                    elif line and not line.startswith("data:"):
                        logger.debug(f"Non-data line in stream: {line}")

        logger.debug(f"Stream completed - processed {chunk_count} chunks")
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Exception in stream_response: {str(e)}")
        # Send error in SSE format
        error_payload = {
            "error": {
                "message": f"Stream processing error: {str(e)}",
                "type": "stream_error",
            }
        }
        yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


async def get_error_detail(response: httpx.Response) -> str:
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
    response_data: Dict[str, Any], model: str, backend_name: str
) -> Dict[str, Any]:
    """Format response to ensure OpenAI compatibility"""
    # If already in correct format, return as-is
    if all(
        key in response_data for key in ["id", "object", "created", "model", "choices"]
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
        "system_fingerprint": f"{backend_name}-proxy",
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
                "message": {"role": "assistant", "content": response_data["content"]},
                "finish_reason": "stop",
            }
        ]

    return formatted_response


@app.get("/admin/backends")
def list_backends():
    """List all configured backends (admin endpoint)"""
    backends = BACKENDS_CONFIG.get("backends", {})
    backend_list = []

    for backend_name, backend_config in backends.items():
        backend_list.append(
            {
                "name": backend_name,
                "display_name": backend_config.get("name", backend_name),
                "base_url": backend_config.get("base_url"),
                "model_count": len(backend_config.get("models", [])),
                "models": backend_config.get("models", []),
                "model_prefixes": backend_config.get("model_prefixes", []),
            }
        )

    return {
        "backends": backend_list,
        "total_backends": len(backend_list),
        "model_aliases": BACKENDS_CONFIG.get("model_aliases", {}),
        "default_models": BACKENDS_CONFIG.get("default_models", {}),
    }
