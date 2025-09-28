# LiteLLM Configuration Compatibility

Open LLM Router now supports LiteLLM's `config.yml` format in addition to its native `backends.json` format. This provides seamless migration paths for users of both systems.

## Configuration File Priority

The router checks for configuration files in this order:

1. `conf/config.yml` (LiteLLM format)
2. `conf/config.yaml` (LiteLLM format)
3. `conf/backends.json` (native format)
4. `conf/backends.example.json` (fallback)

## LiteLLM Format Support

### Example config.yml

```yaml
# LiteLLM-compatible configuration for Open LLM Router
model_list:
  # OpenAI models
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      api_base: https://api.openai.com/v1

  # Groq models (X.AI Grok)
  - model_name: grok-4
    litellm_params:
      model: groq/grok-4-latest
      api_key: os.environ/GROK_API_KEY
      api_base: https://api.x.ai/v1

  # Anthropic Claude models
  - model_name: claude-sonnet-4
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/CLAUDE_API_KEY
      api_base: https://api.anthropic.com/v1

  # Google Gemini models
  - model_name: gemini-2.5
    litellm_params:
      model: vertex_ai/gemini-2.5-pro
      api_key: os.environ/GEMINI_API_KEY
      api_base: https://generativelanguage.googleapis.com/v1beta

# Optional sections (supported)
litellm_settings:
  drop_params: true
  set_verbose: false
  json_logs: true
  request_timeout: 600

general_settings:
  master_key: sk-1234
  default_models:
    chat: gpt-4o
    completion: gpt-4o
    embedding: text-embedding-ada-002

router_settings:
  routing_strategy: simple-shuffle
```

## Provider Mapping

The compatibility layer automatically maps LiteLLM providers to Open LLM Router backends:

| LiteLLM Format | Provider | Open LLM Router Backend |
|---|---|---|
| `openai/model-name` | OpenAI | openai |
| `azure/model-name` | Azure OpenAI | openai |
| `anthropic/claude-*` | Anthropic | claude |
| `bedrock/anthropic.claude-*` | AWS Bedrock | claude |
| `vertex_ai/gemini-*` | Google Vertex AI | gemini |
| `gemini/model-name` | Google Gemini | gemini |
| `groq/model-name` | X.AI Grok | grok |

## Model Alias Support

LiteLLM model aliases are automatically converted:

```yaml
model_list:
  - model_name: gpt-4.1        # User-facing name
    litellm_params:
      model: gpt-4.1           # Actual model name

  - model_name: claude-sonnet  # User-facing alias
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514  # Full model path
```

This creates model aliases mapping `claude-sonnet` → `claude-sonnet-4-20250514`.

## Environment Variable Formats

Both formats are supported for API keys:

```yaml
# LiteLLM format
api_key: os.environ/OPENAI_API_KEY

# Alternative format
api_key: ${OPENAI_API_KEY}

# Direct value (not recommended)
api_key: sk-actual-key-here
```

## Migration Guide

### From LiteLLM to Open LLM Router

1. Copy your existing `config.yml` to `conf/config.yml`
2. Ensure environment variables are set
3. Restart the router - no code changes needed

### From Open LLM Router to LiteLLM Format

Convert your `backends.json` to `config.yml`:

**Before (backends.json):**
```json
{
  "providers": {
    "openai": {
      "name": "OpenAI",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "models": ["gpt-4o", "gpt-4.1"]
    }
  }
}
```

**After (config.yml):**
```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: gpt-4.1
    litellm_params:
      model: gpt-4.1
      api_key: os.environ/OPENAI_API_KEY
```

## Supported LiteLLM Features

✅ **Fully Supported:**
- `model_list` configuration
- `litellm_params` (model, api_key, api_base)
- Environment variable references (`os.environ/VAR`)
- Provider-specific model formats
- Model aliases through different `model_name`
- Basic `general_settings`

⚠️ **Partially Supported:**
- `litellm_settings` (logged but not all options used)
- `router_settings` (logged but routing uses internal logic)

❌ **Not Supported:**
- Advanced LiteLLM features (callbacks, middleware, etc.)
- LiteLLM-specific model parameters
- Complex routing strategies
- Authentication beyond API keys

## Backward Compatibility

All existing Open LLM Router functionality remains unchanged:
- Native `backends.json` format still works
- All API endpoints remain the same
- Model routing logic is preserved
- Provider-specific features maintained

## Testing

The compatibility layer includes comprehensive tests:

```bash
# Test with LiteLLM config
cp conf/config.example.yml conf/config.yml
python -m pytest tests/test_llm_router.py -v

# Test with native config
rm conf/config.yml  # Falls back to backends.json
python -m pytest tests/test_llm_router.py -v
```

## Dependencies

The LiteLLM compatibility requires PyYAML:

```bash
pip install pyyaml>=6.0
```

This is automatically installed via `requirements.txt`.

## Troubleshooting

**Config not loading:**
- Check file exists in `conf/` directory
- Verify YAML syntax is valid
- Check logs for parsing errors

**Models not routing correctly:**
- Verify provider prefixes match supported formats
- Check environment variables are set
- Review model name mappings in logs

**API key errors:**
- Ensure environment variables are properly set
- Check `os.environ/` format in config
- Verify API key names match your environment

## Examples

See `conf/config.example.yml` for a complete working example with all supported providers and models.