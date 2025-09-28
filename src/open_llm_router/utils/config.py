import json
import yaml
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from .logger import proxy_logger


class BackendConfig:
    def __init__(self):
        self._config = None

    def load_backends(self) -> Dict[str, Any]:
        """Load backend configurations from various formats (JSON, YAML, LiteLLM)"""
        if self._config is not None:
            return self._config

        # Use absolute paths from the project root
        project_root = Path(__file__).parent.parent.parent.parent

        # Check for configuration files in order of preference
        config_files = [
            project_root / "conf/config.yml",        # LiteLLM config.yml
            project_root / "conf/config.yaml",       # LiteLLM config.yaml
            project_root / "conf/backends.json",     # Current format
            project_root / "conf/backends.example.json"  # Fallback
        ]

        config_source = None
        config_format = None

        for config_file in config_files:
            if config_file.exists():
                config_source = config_file
                if config_file.suffix in ['.yml', '.yaml']:
                    config_format = 'yaml'
                else:
                    config_format = 'json'
                proxy_logger.info(f"Loading backend config from {config_file} (format: {config_format})")
                break

        if config_source is None:
            proxy_logger.warning(
                "No backend config files found, using hardcoded fallback"
            )
            config = self._get_fallback_config()
            self._config = config
            return config

        try:
            with open(config_source, "r") as f:
                if config_format == 'yaml':
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
                proxy_logger.debug(f"Loaded config with keys: {list(config.keys())}")
        except Exception as e:
            proxy_logger.error(f"Failed to load config from {config_source}: {e}")
            config = self._get_fallback_config()

        # Convert different formats to internal format
        if "model_list" in config:  # LiteLLM format
            config = self._convert_litellm_format(config)
        elif "providers" in config:  # Current Open LLM Router format
            config = self._convert_to_legacy_format(config)
        # If neither, assume legacy format and use as-is

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

    def _convert_litellm_format(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert LiteLLM config.yml format to Open LLM Router internal format"""
        proxy_logger.debug("Converting LiteLLM format to internal format")

        legacy_config = {
            "backends": {},
            "model_aliases": {},
            "default_models": config.get("general_settings", {}).get("default_models", {"chat": "gpt-3.5-turbo"}),
        }

        # Group models by provider to create backend entries
        providers_data = {}
        model_aliases = {}

        for model_entry in config.get("model_list", []):
            model_name = model_entry["model_name"]
            litellm_params = model_entry["litellm_params"]

            # Parse the model parameter to determine provider
            provider_info = self._parse_litellm_model(litellm_params)
            if not provider_info:
                proxy_logger.warning(f"Skipping model {model_name}: unsupported format")
                continue

            provider_name = provider_info["provider"]
            actual_model = provider_info["model"]
            api_base = provider_info["api_base"]
            api_key = provider_info["api_key"]

            # Create or update provider data
            if provider_name not in providers_data:
                providers_data[provider_name] = {
                    "name": provider_name.title(),
                    "base_url": api_base,
                    "api_key_env": self._extract_env_var(api_key),
                    "models": [],
                    "model_prefixes": []
                }

            # Add model to provider
            if actual_model not in providers_data[provider_name]["models"]:
                providers_data[provider_name]["models"].append(actual_model)

            # Create model alias if different from actual model
            if model_name != actual_model:
                model_aliases[model_name] = actual_model

        # Convert to legacy backend format
        for provider_name, provider_data in providers_data.items():
            legacy_config["backends"][provider_name] = {
                "name": provider_data["name"],
                "base_url": provider_data["base_url"],
                "api_key_env": provider_data["api_key_env"],
                "headers_template": {"Authorization": "Bearer {api_key}"},
                "models": provider_data["models"],
                "model_prefixes": self._infer_model_prefixes(provider_data["models"])
            }

        legacy_config["model_aliases"] = model_aliases

        proxy_logger.info(
            f"Converted {len(config.get('model_list', []))} models from LiteLLM format to {len(legacy_config['backends'])} backends"
        )
        return legacy_config

    def _parse_litellm_model(self, litellm_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse LiteLLM model parameters to extract provider and model info"""
        model_param = litellm_params.get("model", "")
        api_base = litellm_params.get("api_base", "")
        api_key = litellm_params.get("api_key", "")

        # Handle different LiteLLM model formats
        if "/" in model_param:
            provider_prefix, model_name = model_param.split("/", 1)

            if provider_prefix in ["openai", "azure"]:
                return {
                    "provider": "openai",
                    "model": model_name,
                    "api_base": api_base or "https://api.openai.com/v1",
                    "api_key": api_key or "os.environ/OPENAI_API_KEY"
                }
            elif provider_prefix in ["anthropic", "bedrock"] and "claude" in model_name:
                return {
                    "provider": "claude",
                    "model": model_name,
                    "api_base": api_base or "https://api.anthropic.com/v1",
                    "api_key": api_key or "os.environ/CLAUDE_API_KEY"
                }
            elif provider_prefix in ["vertex_ai", "gemini"]:
                return {
                    "provider": "gemini",
                    "model": model_name,
                    "api_base": api_base or "https://generativelanguage.googleapis.com/v1beta",
                    "api_key": api_key or "os.environ/GEMINI_API_KEY"
                }
            elif provider_prefix == "groq":
                return {
                    "provider": "grok",
                    "model": model_name,
                    "api_base": api_base or "https://api.x.ai/v1",
                    "api_key": api_key or "os.environ/GROK_API_KEY"
                }
        else:
            # Handle direct model names
            if model_param.startswith("gpt-") or model_param.startswith("o"):
                return {
                    "provider": "openai",
                    "model": model_param,
                    "api_base": api_base or "https://api.openai.com/v1",
                    "api_key": api_key or "os.environ/OPENAI_API_KEY"
                }
            elif model_param.startswith("claude-"):
                return {
                    "provider": "claude",
                    "model": model_param,
                    "api_base": api_base or "https://api.anthropic.com/v1",
                    "api_key": api_key or "os.environ/CLAUDE_API_KEY"
                }
            elif model_param.startswith("gemini-"):
                return {
                    "provider": "gemini",
                    "model": model_param,
                    "api_base": api_base or "https://generativelanguage.googleapis.com/v1beta",
                    "api_key": api_key or "os.environ/GEMINI_API_KEY"
                }
            elif model_param.startswith("grok-"):
                return {
                    "provider": "grok",
                    "model": model_param,
                    "api_base": api_base or "https://api.x.ai/v1",
                    "api_key": api_key or "os.environ/GROK_API_KEY"
                }

        return None

    def _extract_env_var(self, api_key_value: str) -> str:
        """Extract environment variable name from LiteLLM format"""
        if api_key_value.startswith("os.environ/"):
            return api_key_value.replace("os.environ/", "")
        elif api_key_value.startswith("${") and api_key_value.endswith("}"):
            return api_key_value[2:-1]
        else:
            # If it's a direct value, we should use a generic env var name
            # but this is not recommended for security
            return "API_KEY"

    def _infer_model_prefixes(self, models: List[str]) -> List[str]:
        """Infer model prefixes from model names"""
        prefixes = set()
        for model in models:
            # Extract prefix before first dash or number
            match = re.match(r'^([a-zA-Z]+[-]?[a-zA-Z]*)', model)
            if match:
                prefix = match.group(1)
                if not prefix.endswith('-'):
                    prefix += '-'
                prefixes.add(prefix)
        return list(prefixes)

    def reload(self):
        """Reload configuration from file"""
        self._config = None
        return self.load_backends()

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return self.load_backends()


# Global config instance
backend_config = BackendConfig()
