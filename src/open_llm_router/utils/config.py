import json
from pathlib import Path
from typing import Dict, Any
from .logger import proxy_logger


class BackendConfig:
    def __init__(self):
        self._config = None

    def load_backends(self) -> Dict[str, Any]:
        """Load backend configurations from conf/backends.json or conf/backends.example.json"""
        if self._config is not None:
            return self._config

        # Use absolute paths from the project root
        project_root = Path(__file__).parent.parent.parent.parent
        backends_file = project_root / "conf/backends.json"
        example_file = project_root / "conf/backends.example.json"

        config_source = None
        if backends_file.exists():
            config_source = backends_file
            proxy_logger.info(f"Loading backend config from {backends_file}")
        elif example_file.exists():
            config_source = example_file
            proxy_logger.info(f"Loading backend config from {example_file} (fallback)")
        else:
            proxy_logger.warning(
                "No backend config files found, using hardcoded fallback"
            )
            config = self._get_fallback_config()
            self._config = config
            return config

        try:
            with open(config_source, "r") as f:
                config = json.load(f)
                proxy_logger.debug(f"Loaded config with keys: {list(config.keys())}")
        except Exception as e:
            proxy_logger.error(f"Failed to load config from {config_source}: {e}")
            config = self._get_fallback_config()

        # Convert new format to legacy format for compatibility
        if "providers" in config:
            config = self._convert_to_legacy_format(config)

        self._config = config
        return config

    def _get_fallback_config(self) -> Dict[str, Any]:
        """Return hardcoded fallback configuration"""
        return {
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

    def _convert_to_legacy_format(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert new provider format to legacy backend format for compatibility"""
        proxy_logger.debug("Converting provider format to legacy backend format")

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

        proxy_logger.info(
            f"Converted {len(config['providers'])} providers to legacy format"
        )
        return legacy_config

    def reload(self):
        """Reload configuration from file"""
        self._config = None
        return self.load_backends()

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return self.load_backends()


# Global config instance
backend_config = BackendConfig()
