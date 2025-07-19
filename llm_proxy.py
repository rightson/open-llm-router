from fastapi import FastAPI, Request, Header, HTTPException
import httpx
import os
import json
from pathlib import Path
from typing import Dict, Any

app = FastAPI()

# API KEY configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxxx")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk-xxxx")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "sk-ant-xxx")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIza...")

# Load backend configurations
def load_backends() -> Dict[str, Any]:
    """Load backend configurations from backends.json or backends.example.json"""
    backends_file = Path("backends.json")
    example_file = Path("backends.example.json")
    
    if backends_file.exists():
        with open(backends_file, 'r') as f:
            return json.load(f)
    elif example_file.exists():
        with open(example_file, 'r') as f:
            return json.load(f)
    else:
        # Fallback to hardcoded configuration
        return {
            "backends": {
                "openai": {
                    "name": "OpenAI",
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "api_key_env": "OPENAI_API_KEY",
                    "headers_template": {"Authorization": "Bearer {api_key}"},
                    "models": ["gpt-4", "gpt-3.5-turbo"],
                    "model_prefixes": ["gpt-"]
                },
                "groq": {
                    "name": "Groq", 
                    "base_url": "https://api.groq.com/openai/v1/chat/completions",
                    "api_key_env": "GROQ_API_KEY",
                    "headers_template": {"Authorization": "Bearer {api_key}"},
                    "models": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
                    "model_prefixes": ["llama", "mixtral"]
                }
            },
            "model_aliases": {},
            "default_models": {"chat": "gpt-3.5-turbo"}
        }

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
        raise HTTPException(500, f"No API key environment variable configured for {backend_name}")
    
    api_key = os.getenv(api_key_env)
    if not api_key:
        # Fallback to legacy environment variables
        legacy_keys = {
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "GROQ_API_KEY": GROQ_API_KEY,
            "CLAUDE_API_KEY": CLAUDE_API_KEY,
            "GEMINI_API_KEY": GEMINI_API_KEY
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
    headers_template = backend_config.get("headers_template", {"Authorization": "Bearer {api_key}"})
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
        "backend_name": backend_name
    }

@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request,
                                 authorization: str = Header(None)):
    body = await request.json()
    model = body.get("model", "gpt-3.5-turbo")

    # 簡單的 auth, 可擴充為 JWT、OAuth 或其他
    if authorization not in [f"Bearer {OPENAI_API_KEY}", f"Bearer {GROQ_API_KEY}"]:
        pass # 可以加入自己的驗證邏輯

    backend = choose_backend(model)

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            backend["base_url"],
            json=body,
            headers=backend["headers"]
        )
        return response.json()

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
            all_models.append({
                "id": model,
                "object": "model",
                "created": 1677610602,
                "owned_by": backend_config.get("name", backend_name),
                "backend": backend_name
            })
    
    # Add model aliases
    model_aliases = BACKENDS_CONFIG.get("model_aliases", {})
    for alias, target in model_aliases.items():
        # Find the backend for the target model
        try:
            backend = get_backend_for_model(target)
            backend_config = backends.get(backend, {})
            all_models.append({
                "id": alias,
                "object": "model", 
                "created": 1677610602,
                "owned_by": backend_config.get("name", backend),
                "backend": backend,
                "alias_for": target
            })
        except:
            continue
    
    return {
        "object": "list",
        "data": all_models
    }

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
            "models_count": sum(len(b.get("models", [])) for b in BACKENDS_CONFIG.get("backends", {}).values())
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to reload backends: {str(e)}"
        }

@app.get("/admin/config")
def get_config():
    """Get current backend configuration (admin endpoint)"""
    return BACKENDS_CONFIG

@app.get("/admin/backends")
def list_backends():
    """List all configured backends (admin endpoint)"""
    backends = BACKENDS_CONFIG.get("backends", {})
    backend_list = []
    
    for backend_name, backend_config in backends.items():
        backend_list.append({
            "name": backend_name,
            "display_name": backend_config.get("name", backend_name),
            "base_url": backend_config.get("base_url"),
            "model_count": len(backend_config.get("models", [])),
            "models": backend_config.get("models", []),
            "model_prefixes": backend_config.get("model_prefixes", [])
        })
    
    return {
        "backends": backend_list,
        "total_backends": len(backend_list),
        "model_aliases": BACKENDS_CONFIG.get("model_aliases", {}),
        "default_models": BACKENDS_CONFIG.get("default_models", {})
    }