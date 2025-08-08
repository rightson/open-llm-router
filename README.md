# Open LLM Router - Self-Hosted AI Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Self-hosted LLM routing with OpenAI-compatible API for multiple providers. Purpose-built for Open-WebUI with message format conversion and unified model access.

## Why This vs Open-WebUI's Native Configuration?

- **Format Conversion**: Auto-converts OpenAI messages to Claude/Gemini formats
- **Model Aliasing**: Smart routing (e.g., `claude-sonnet-4` → `claude-sonnet-4-20250514`)
- **Streaming Compatibility**: Converts provider streaming to OpenAI SSE format
- **Cost Savings**: Direct API calls without markup fees (vs OpenRouter.ai)
- **Privacy**: All requests stay on your infrastructure

## Supported Models

**OpenAI**: `gpt-4o`, `gpt-4.1`, `o3`
**Groq**: `grok-4`, `grok-3`
**Claude**: `claude-opus-4.1`, `claude-sonnet-4` (with format conversion)
**Gemini**: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`

## Quick Start

```bash
# Setup environment
cp .env.example .env
# Edit .env with your API keys and database credentials

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

**Backend Configuration**:
```bash
# Initialize backends config
./manage.sh init backends
# Edit conf/backends.json for custom providers/models
```

## Usage with Open-WebUI

1. Configure Open-WebUI connection:
   - Base URL: `http://localhost:8086/v1`
   - Use any configured API key
2. Claude models work transparently with automatic format conversion
3. All models appear as OpenAI-compatible in the interface

## API Endpoints

- `POST /v1/chat/completions` - OpenAI-compatible chat (includes Claude with conversion)
- `GET /v1/models` - List available models
- `POST /admin/reload-backends` - Reload configuration

## Management Commands

```bash
# Database
./manage.sh init -x          # Initialize database
./manage.sh init backends    # Setup backend config

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
- Intelligent model routing with aliases
- OpenAI-compatible streaming for all providers
- Enhanced logging with request timing and status codes
- Template-based database initialization

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.