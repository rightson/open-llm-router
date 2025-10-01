# Open LLM Router - Lightweight Router for Open-WebUI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Simple, self-hosted LLM routing for Open-WebUI installations. Provides OpenAI-compatible API for 4 major providers with message format conversion.

## When to Use This

**✅ Good Fit:**
- Small teams running Open-WebUI locally
- Simple setups needing 4-5 providers (OpenAI, Groq, Claude, Gemini)
- On-premises deployments with strict data control requirements
- Minimal infrastructure and maintenance overhead preferred

**❌ Consider Alternatives:**
- **Production/Enterprise**: Use [OpenRouter.ai](https://openrouter.ai) (400+ models, automatic failover, enterprise features)
- **Complex Routing**: Use [LiteLLM](https://litellm.ai) (100+ providers, load balancing, advanced features)
- **Single Provider**: Use Open-WebUI's native configuration

## Features

- **Format Conversion**: Auto-converts OpenAI messages to Claude/Gemini formats
- **Model Aliasing**: Smart routing (e.g., `claude-sonnet-4` → `claude-sonnet-4-20250514`)
- **Streaming Compatibility**: Converts provider streaming to OpenAI SSE format
- **Direct API Access**: No markup fees, full control over API keys
- **Open-WebUI Integration**: Built-in PostgreSQL setup and PM2 management

## Supported Models (Limited Scope)

**4 Providers, ~10 Models:**
- **OpenAI**: `gpt-4o`, `gpt-4.1`, `o3`
- **Groq**: `grok-4`, `grok-3`
- **Claude**: `claude-opus-4.1`, `claude-sonnet-4` (with format conversion)
- **Gemini**: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`

*For access to 400+ models, use [OpenRouter.ai](https://openrouter.ai) instead.*

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

**Environment (.env)**:
```env
# Database
OPENWEBUI_DB_USER=openwebui_user
OPENWEBUI_DB_PASSWORD=your_password
OPENWEBUI_DB_NAME=openwebui_db
DATABASE_URL=postgresql://${OPENWEBUI_DB_USER}:${OPENWEBUI_DB_PASSWORD}@localhost:5432/${OPENWEBUI_DB_NAME}

# Ports
OPENWEBUI_PORT=8087
LLM_ROUTER_PORT=8086

# API Keys
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key
GEMINI_API_KEY=your_gemini_key
GROK_API_KEY=your_grok_key
```

**Router (conf/config.yml)**:
```bash
# Start from the LiteLLM-compatible template
cp conf/config.example.yml conf/config.yml
# List models and providers using LiteLLM's config.yml format
```

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

- Place the file at `conf/config.yml`; `conf/config.yaml` is also detected.
- The router converts LiteLLM's structure to its internal backend format automatically.
- See `LITELLM_COMPATIBILITY.md` for full format support and migration notes.

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

```
src/open_llm_router/
├── llm_router.py              # Main FastAPI app
├── providers/                # Provider-specific implementations
│   ├── claude.py            # Anthropic API with format conversion
│   ├── gemini.py            # Google Gemini API integration
│   └── openai.py            # OpenAI/compatible providers
└── utils/                   # Utilities
    ├── model_router.py      # Model routing and backend selection
    └── logger.py            # Enhanced logging with timing
```

**Key Features**:
- Provider-specific message format conversion
- Basic model routing with aliases
- OpenAI-compatible streaming for all providers
- Enhanced logging with request timing and status codes
- Template-based database initialization

## Limitations

- **Limited Scale**: 4 providers vs 400+ in OpenRouter.ai
- **No Failover**: Single provider per model, no automatic fallback
- **Basic Routing**: No intelligent load balancing or provider selection
- **Maintenance Overhead**: Self-hosted setup and updates required
- **Feature Gap**: Missing enterprise features (analytics, spend tracking, etc.)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
