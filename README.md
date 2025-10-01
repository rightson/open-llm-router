# Open LLM Router - LiteLLM-Compatible Router + Open-WebUI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Two main strengths:**
1. **Lightweight LiteLLM-compatible router** - Drop in your existing LiteLLM config, minimal code
2. **Open-WebUI with PostgreSQL** - Complete setup with database initialization and PM2 management

Self-hosted LLM routing that's easy to run and maintain.

## When to Use This

**✅ Good Fit:**
- Need LiteLLM-compatible routing without the full LiteLLM stack
- Want Open-WebUI with PostgreSQL pre-configured
- Simple setups with minimal maintenance overhead
- On-premises deployments with strict data control requirements
- Quick deployment with existing LiteLLM configs

**❌ Consider Alternatives:**
- **Advanced Features**: Use [LiteLLM](https://litellm.ai) directly (100+ providers, load balancing, caching, observability)
- **Zero Setup**: Use [OpenRouter.ai](https://openrouter.ai) (400+ models, automatic failover, no hosting)
- **Single Provider**: Use Open-WebUI's native configuration

## Features

**Router:**
- **LiteLLM Config Compatible**: Use existing LiteLLM `config.yml` files directly
- **Minimal Code**: Lightweight implementation, easy to understand and maintain
- **Auto Format Conversion**: OpenAI ↔ Claude/Gemini message formats
- **Streaming Support**: Unified OpenAI-compatible SSE streaming
- **Hot Reload**: Update config without restarting services

**Infrastructure:**
- **PostgreSQL Setup**: Pre-configured database initialization for Open-WebUI
- **PM2 Management**: Simple service orchestration
- **Environment-based Secrets**: API keys in `.env`, referenced in config

## Supported Providers

Works with any LiteLLM-supported provider. Common examples:
- **OpenAI**: `gpt-4o`, `gpt-4.1`, `o3-mini`
- **Anthropic**: `claude-opus-4`, `claude-sonnet-4`
- **Google**: `gemini-2.0-flash`, `gemini-1.5-pro`
- **xAI**: `grok-2`, `grok-beta`
- **Many more**: See [LiteLLM providers](https://docs.litellm.ai/docs/providers)

## Quick Start

```bash
# Setup environment
cp .env.example .env
# Edit .env with your API keys and database credentials

# Configure router
cp conf/config.example.yml conf/config.yml
# Edit conf/config.yml to match your providers/models

# Initialize database and start services
./manage.sh init -x
./manage.sh start
```

**Requirements**: Python 3.11+, PostgreSQL, PM2

## Configuration

**1. Environment Variables (.env)**:
```env
# API Keys (referenced by config.yml)
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key
GEMINI_API_KEY=your_gemini_key

# Database & Ports
DATABASE_URL=postgresql://user:pass@localhost:5432/openwebui_db
LLM_ROUTER_PORT=8086
OPENWEBUI_PORT=8087
```

**2. LiteLLM Config (conf/config.yml)**:
```yaml
model_list:
  - model_name: gpt-4.1
    litellm_params:
      model: gpt-4.1
      api_key: os.environ/OPENAI_API_KEY

  - model_name: claude-sonnet-4
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/CLAUDE_API_KEY
```

**That's it!** Standard LiteLLM format - the router handles the rest automatically.

See `LITELLM_COMPATIBILITY.md` for advanced features and migration notes.

## Usage with Open-WebUI

1. Configure Open-WebUI connection:
   - Base URL: `http://localhost:8086/v1`
   - Use any configured API key
2. Claude models work transparently with automatic format conversion
3. All models appear as OpenAI-compatible in the interface

## API Endpoints

- `POST /v1/chat/completions` - OpenAI-compatible chat (includes Claude with conversion)
- `GET /v1/models` - List available models
- `POST /admin/reload-backends` - Reload `conf/config.yml` without restart

## Management Commands

```bash
# Database
./manage.sh init -x          # Initialize database
# Services
./manage.sh start           # Start all services (PM2)
./manage.sh start llm-router # Start router only
./manage.sh stop           # Stop all services
./manage.sh status         # Check status

# PM2 Management
pm2 logs                   # View logs
pm2 restart all           # Restart services
```

## Testing

```bash
# Install and run tests
pip install pytest pytest-asyncio
pytest tests/test_llm_router.py -v

# Test the router
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{"model": "claude-sonnet-4", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Architecture

**Minimal codebase** - easy to understand and maintain:

```
src/open_llm_router/
├── llm_router.py              # Main FastAPI app (~300 lines)
├── providers/                # Provider implementations
│   ├── claude.py            # Anthropic format conversion
│   ├── gemini.py            # Google Gemini integration
│   └── openai.py            # OpenAI/compatible providers
└── utils/
    ├── model_router.py      # LiteLLM config → backend routing
    └── logger.py            # Request logging
```

**Design Philosophy**:
- LiteLLM config compatibility without the full stack
- Automatic format conversion (OpenAI ↔ provider-specific)
- Simple streaming aggregation
- Hot-reloadable configuration

## Limitations

This is a **lightweight alternative**, not a full LiteLLM replacement:
- **No Advanced Features**: Missing caching, load balancing, fallbacks, observability
- **Basic Routing**: Single provider per model, no intelligent selection
- **Self-Hosted**: You manage infrastructure and updates
- **Limited Scale**: Best for small teams, not enterprise deployments

For production needs, consider [LiteLLM](https://litellm.ai) or [OpenRouter.ai](https://openrouter.ai).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
