import os
from typing import Dict, Any
from fastapi import HTTPException
from .logger import proxy_logger


class ModelRouter:
    def __init__(self, backends_config: Dict[str, Any]):
        self.backends_config = backends_config

    def get_backend_for_model(self, model: str) -> str:
        """Determine which backend to use for a given model"""
        # Check model aliases first
        model_aliases = self.backends_config.get("model_aliases", {})
        if model in model_aliases:
            original_model = model
            model = model_aliases[model]
            proxy_logger.debug(f"Model alias resolved: {original_model} -> {model}")

        # Check each backend's models
        backends = self.backends_config.get("backends", {})
        for backend_name, backend_config in backends.items():
            models = backend_config.get("models", [])
            if model in models:
                proxy_logger.debug(f"Model {model} found in {backend_name} backend")
                return backend_name

        # Fallback to prefix-based matching for backward compatibility
        for backend_name, backend_config in backends.items():
            model_prefixes = backend_config.get("model_prefixes", [])
            for prefix in model_prefixes:
                if model.startswith(prefix):
                    proxy_logger.debug(
                        f"Model {model} matched prefix {prefix} for {backend_name}"
                    )
                    return backend_name

        proxy_logger.error(f"Unknown model requested: {model}")
        raise HTTPException(400, f"Unknown model: {model}")

    def get_api_key_for_backend(
        self, backend_name: str, backend_config: Dict[str, Any]
    ) -> str:
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
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "sk-xxxx"),
                "GROK_API_KEY": os.getenv("GROK_API_KEY", "gsk-xxxx"),
                "CLAUDE_API_KEY": os.getenv("CLAUDE_API_KEY", "sk-ant-xxx"),
                "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "AIza..."),
            }
            api_key = legacy_keys.get(api_key_env, f"default-{backend_name}-key")

        # Log API key status without exposing the key
        has_valid_key = api_key and not any(
            api_key.startswith(default)
            for default in ["sk-xxxx", "gsk-xxxx", "sk-ant-xxx", "AIza..."]
        )
        proxy_logger.debug(f"{api_key_env} loaded: {'Yes' if has_valid_key else 'No'}")

        return api_key

    def choose_backend(self, model: str) -> Dict[str, Any]:
        """Choose the appropriate backend for the given model"""
        backend_name = self.get_backend_for_model(model)
        backends = self.backends_config.get("backends", {})

        if backend_name not in backends:
            raise HTTPException(
                400, f"Backend {backend_name} not found in configuration"
            )

        backend_config = backends[backend_name]
        api_key = self.get_api_key_for_backend(backend_name, backend_config)

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
