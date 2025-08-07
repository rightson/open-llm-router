from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
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

        # Make request to backend
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
                    return StreamingResponse(
                        stream_response(response), media_type="text/plain"
                    )
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

                    return formatted_response

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


async def stream_response(response: httpx.Response) -> AsyncGenerator[str, None]:
    """Stream response from backend while maintaining OpenAI format"""
    async for chunk in response.aiter_text():
        if chunk.strip():
            yield chunk


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
