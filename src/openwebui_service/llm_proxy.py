from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import json
from pathlib import Path
from typing import Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    # Load .env from the project root (parent directory)
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

# Import our new modular components
from .utils.logger import proxy_logger
from .utils.config import backend_config
from .utils.model_router import ModelRouter
from .providers.claude import ClaudeProvider
from .providers.gemini import GeminiProvider
from .providers.openai import OpenAIProvider

app = FastAPI()

# Load backends configuration at startup
BACKENDS_CONFIG = backend_config.load_backends()

# Initialize model router with configuration
model_router = ModelRouter(BACKENDS_CONFIG)


# Export functions for backward compatibility with tests
def choose_backend(model: str):
    """Choose the appropriate backend for the given model (backward compatibility)"""
    return model_router.choose_backend(model)


def get_backend_for_model(model: str):
    """Determine which backend to use for a given model (backward compatibility)"""
    return model_router.get_backend_for_model(model)


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request, authorization: str = Header(None)):
    """Proxy chat completions requests to appropriate backend with full OpenAI compatibility"""
    try:
        # Parse request body
        body = await request.json()
        model = body.get("model", "gpt-3.5-turbo")
        stream = body.get("stream", False)

        proxy_logger.info(f"Proxying request for model: {model}, stream: {stream}")

        # Validate required fields
        if not body.get("messages"):
            raise HTTPException(
                status_code=400, detail="Missing required field: messages"
            )

        # Choose appropriate backend using the model router
        backend = model_router.choose_backend(model)
        backend_name = backend["backend_name"]

        # Create the appropriate provider instance and handle the request
        if backend_name == "claude":
            provider = ClaudeProvider(backend)
            return await provider.handle_request(body, stream)
        elif backend_name == "gemini":
            provider = GeminiProvider(backend, BACKENDS_CONFIG)
            return await provider.handle_request(body, stream)
        else:
            # Handle OpenAI-compatible providers (openai, grok, etc.)
            provider = OpenAIProvider(backend)
            return await provider.handle_request(body, stream)

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        proxy_logger.error(f"Unexpected error in proxy_chat_completions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def list_models():
    """List all available models"""
    all_models = []
    backends = BACKENDS_CONFIG.get("backends", {})

    for backend_name, backend_config_dict in backends.items():
        models = backend_config_dict.get("models", [])
        for model in models:
            all_models.append(
                {
                    "id": model,
                    "object": "model",
                    "created": 1677610602,
                    "owned_by": backend_config_dict.get("name", backend_name),
                    "backend": backend_name,
                }
            )

    # Add model aliases
    model_aliases = BACKENDS_CONFIG.get("model_aliases", {})
    for alias, target in model_aliases.items():
        # Find the backend for the target model
        try:
            backend = model_router.get_backend_for_model(target)
            backend_config_dict = backends.get(backend, {})
            all_models.append(
                {
                    "id": alias,
                    "object": "model",
                    "created": 1677610602,
                    "owned_by": backend_config_dict.get("name", backend),
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
    global BACKENDS_CONFIG, model_router
    try:
        BACKENDS_CONFIG = backend_config.reload()
        model_router = ModelRouter(BACKENDS_CONFIG)
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


@app.get("/admin/backends")
def list_backends():
    """List all configured backends (admin endpoint)"""
    backends = BACKENDS_CONFIG.get("backends", {})
    backend_list = []

    for backend_name, backend_config_dict in backends.items():
        backend_list.append(
            {
                "name": backend_name,
                "display_name": backend_config_dict.get("name", backend_name),
                "base_url": backend_config_dict.get("base_url"),
                "model_count": len(backend_config_dict.get("models", [])),
                "models": backend_config_dict.get("models", []),
                "model_prefixes": backend_config_dict.get("model_prefixes", []),
            }
        )

    return {
        "backends": backend_list,
        "total_backends": len(backend_list),
        "model_aliases": BACKENDS_CONFIG.get("model_aliases", {}),
        "default_models": BACKENDS_CONFIG.get("default_models", {}),
    }
