# Open-WebUI + LLM Proxy Service Manager

A complete service management solution for running Open-WebUI with PostgreSQL database and multi-provider LLM proxy. Includes database initialization, service management, and configuration templates.

## Features

- **Database Management**: Automatic PostgreSQL database and user setup
- **Multi-Service Management**: Start/stop Open-WebUI and LLM Proxy independently or together
- **LLM Proxy**: Route requests to multiple AI providers (OpenAI, Groq, Claude, Gemini)
- **PM2 Integration**: Production-ready process management with auto-restart
- **Template System**: SQL templates with environment variable substitution
- **Multi-Platform**: Supports Homebrew PostgreSQL, system PostgreSQL, and Postgres.app
- **Comprehensive Testing**: Pytest suite for API verification
- **Idempotent Operations**: Safe to run multiple times

## Requirements

- **Python 3.11+** (required for Open-WebUI)
- **PostgreSQL** (for database)
- **PM2** (for production process management, optional for individual services)

## Quick Start

1. **Setup environment:**
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your database and API credentials

# Dependencies are automatically installed when starting services
# OR install manually:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Install package in development mode
pip install -e .

# Install PM2 for process management (only needed for ./manage.sh start)
npm install -g pm2
```

2. **Initialize database:**
```bash
# Generate and execute SQL initialization
./manage.sh init -x
```

3. **Start services:**
```bash
# Start all services with PM2 (requires PM2)
./manage.sh start

# OR start services individually (auto-installs dependencies):
./manage.sh start open-webui    # Start Open-WebUI only (requires Python 3.11+)
./manage.sh start llm-proxy     # Start LLM Proxy only
```

## Management Commands

### Database Commands
```bash
# Generate SQL file only
./manage.sh init

# Generate and execute SQL file
./manage.sh init -x

# Initialize backend configuration (recommended)
./manage.sh init backends

# Initialize models configuration (legacy)
./manage.sh init models
```

### Service Commands
```bash
# Start all services with PM2
./manage.sh start

# Start individual services (auto-installs dependencies)
./manage.sh start open-webui    # Open-WebUI only (requires Python 3.11+)
./manage.sh start llm-proxy     # LLM Proxy only

# Stop all services
./manage.sh stop

# Check service and database status
./manage.sh status
```

### PM2 Process Management
```bash
# View service status
pm2 status

# View logs
pm2 logs
pm2 logs open-webui    # Open-WebUI logs only
pm2 logs llm-proxy     # LLM Proxy logs only

# Restart services
pm2 restart all
pm2 restart open-webui
pm2 restart llm-proxy

# Stop services
pm2 stop all
pm2 delete all         # Remove from PM2
```

## Configuration

### Environment Variables (.env)

```env
# PostgreSQL configuration for Open-WebUI
OPENWEBUI_DB_USER=openwebui_user
OPENWEBUI_DB_PASSWORD=your_secure_password_here
OPENWEBUI_DB_NAME=openwebui_db

# Database connection settings
DB_HOST=localhost
DB_PORT=5432

# Service Ports
OPENWEBUI_PORT=8087
LLM_PROXY_PORT=8086

# Database URL for Open-WebUI (constructed from above variables)
DATABASE_URL=postgresql://${OPENWEBUI_DB_USER}:${OPENWEBUI_DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${OPENWEBUI_DB_NAME}

# LLM API Configuration
OPENAI_API_KEY=your_openai_api_key_here
GROK_API_KEY=your_grok_api_key_here
CLAUDE_API_KEY=your_claude_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Files Structure
```
├── manage.sh                       # Main management script
├── pyproject.toml                  # Python package configuration
├── requirements.txt                # Python dependencies
├── .env.example                   # Environment configuration template
├── src/                           # Source code (Python package)
│   └── openwebui_service/
│       ├── __init__.py            # Package initialization
│       ├── llm_proxy.py           # LLM proxy server
│       └── pg_init.py             # Database initialization utility
├── conf/                          # Configuration files
│   ├── backends.example.json     # Default backend configurations (for git)
│   ├── models.example.json       # Legacy model configurations (for git)
│   ├── backends.json            # LLM providers configuration
│   ├── backends.json             # Custom backend configurations (git ignored)
│   └── models.json               # Legacy model configurations (git ignored)
├── templates/                     # Template files
│   └── init_template.sql         # SQL template with variables
├── tests/                         # Test files
│   └── test_llm_proxy.py         # Pytest test suite
├── run/                           # Runtime generated files (git ignored)
│   ├── init_openwebui_db.sql     # Generated SQL file
│   └── ecosystem.config.js       # PM2 configuration (auto-generated)
└── venv/                          # Virtual environment (created by user)
```

## LLM Proxy Features

The LLM Proxy provides a unified API to multiple AI providers with expandable model configurations:

### Supported Providers
- **OpenAI**: GPT-4o, GPT-4.1, O3 (direct integration)
- **Groq**: Grok-4, Grok-3 (direct integration)
- **Claude**: Claude Opus 4.1, Claude Sonnet 4 (with full OpenAI compatibility and streaming support)
- **Gemini**: Gemini 2.5 Pro/Flash/Flash-Lite (via local proxy)

### Backend Configuration

**Initialize backend configuration:**
```bash
# Copy default backends to customizable file
./manage.sh init backends
```

**Customize backends in `conf/backends.json`:**
```json
{
  "providers": {
    "openai": {
      "name": "OpenAI",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "endpoints": {
        "chat_completions": "/chat/completions"
      },
      "models": ["gpt-4o", "gpt-4.1", "o3"],
      "model_prefixes": ["gpt-", "o"]
    },
    "claude": {
      "name": "Anthropic Claude",
      "base_url": "http://localhost:9000/v1",
      "api_key_env": "CLAUDE_API_KEY",
      "endpoints": {
        "chat_completions": "/chat/completions"
      },
      "models": ["claude-opus-4-1-20250805", "claude-sonnet-4-20250514"],
      "model_prefixes": ["claude-"]
    },
    "custom_backend": {
      "name": "Custom LLM",
      "base_url": "https://api.custom.com/v1",
      "api_key_env": "CUSTOM_API_KEY",
      "endpoints": {
        "chat_completions": "/chat/completions"
      },
      "models": ["custom-model-1", "custom-model-2"],
      "model_prefixes": ["custom-"]
    }
  },
  "model_aliases": {
    "gpt-4.1": "gpt-4.1",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "claude-opus-4.1": "claude-opus-4-1-20250805"
  },
  "default_models": {
    "chat": "gpt-4.1"
  }
}
```

### Claude Integration Features

The LLM Proxy includes full Claude integration with OpenAI API compatibility:

**Message Processing:**
- Automatic conversion from OpenAI message format to Anthropic format
- Filters out system messages and invalid roles for Claude compatibility
- Preserves conversation context and message content

**Streaming Support:**
- Real-time streaming responses from Claude models
- Converts Claude streaming events to OpenAI-compatible Server-Sent Events
- Proper handling of `content_block_delta` and `message_stop` events

**Response Compatibility:**
- Converts Claude response structure to OpenAI format
- Handles both modern content blocks and legacy completion formats
- Maintains usage statistics and response metadata

**Model Support:**
- `claude-opus-4-1-20250805` (Claude Opus 4.1)
- `claude-sonnet-4-20250514` (Claude Sonnet 4)
- Model aliases: `claude-opus-4.1`, `claude-sonnet-4`

### API Endpoints
- `GET /` - Health check
- `GET /v1/models` - List all available models (OpenAI compatible)
- `POST /v1/chat/completions` - Chat completions (OpenAI compatible, includes Claude)
- `POST /admin/reload-backends` - Reload backend configuration
- `GET /admin/config` - Get current configuration
- `GET /admin/backends` - List all configured backends

### Usage Examples
```bash
# Test the proxy
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# List available models
curl http://localhost:8086/v1/models

# Use Claude model with streaming
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-claude-api-key" \
  -d '{
    "model": "claude-sonnet-4",
    "messages": [{"role": "user", "content": "Explain quantum computing"}],
    "stream": true
  }'

# Use Claude model alias
curl -X POST http://localhost:8086/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-claude-api-key" \
  -d '{
    "model": "claude-opus-4.1",
    "messages": [{"role": "user", "content": "Write a Python function"}]
  }'

# Reload backends after editing conf/backends.json
curl -X POST http://localhost:8086/admin/reload-backends

# List configured backends
curl http://localhost:8086/admin/backends
```

## Database Setup Details

The initialization creates:
- **Database**: Creates the specified database if it doesn't exist
- **User**: Creates database user with secure password
- **Permissions**: Grants full access to database and schema
- **Extensions**: Installs `uuid-ossp` and `pg_trgm` for Open-WebUI features
- **Ownership**: Sets user as database owner for complete control

## Troubleshooting

### Common Issues

**Environment file missing:**
```bash
❌ .env file not found. Copy .env.example to .env first.
```
Solution: `cp .env.example .env` and edit with your credentials

**PostgreSQL not found:**
```bash
❌ psql not found. Please install PostgreSQL.
```
Solution: Install PostgreSQL via Homebrew: `brew install postgresql`

**Database connection failed:**
```bash
❌ Database connection: FAILED
```
Solution: Ensure PostgreSQL is running: `brew services start postgresql`

**Python version too old (for Open-WebUI):**
```bash
❌ open-webui requires Python 3.11+, but found Python 3.10
```
Solution: Install Python 3.11+ and ensure `python3` points to it

**Dependencies automatically handled:**
- Virtual environment is created automatically when starting services
- Requirements are installed automatically when needed
- Open-WebUI installation is handled automatically

### Manual Database Setup

If automatic initialization fails, run manually:
```bash
# Generate SQL file
./manage.sh init

# Execute manually (choose one):
psql -d postgres -f init_openwebui_db.sql
# OR for Homebrew PostgreSQL:
/opt/homebrew/bin/psql -d postgres -f init_openwebui_db.sql
```

## Advanced Usage

### Custom PostgreSQL Setup
The script automatically detects PostgreSQL installations:
- Homebrew PostgreSQL (`/opt/homebrew/bin/psql`)
- System PostgreSQL (`/usr/bin/psql`, `/usr/local/bin/psql`)
- Postgres.app (`/Applications/Postgres.app/...`)

## Testing

### Run Test Suite
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/test_llm_proxy.py -v

# Run specific test categories
pytest tests/test_llm_proxy.py::TestLLMProxy -v          # Unit tests
pytest tests/test_llm_proxy.py -k "integration" -v       # Integration tests (requires API keys)

# Run tests with coverage
pytest tests/test_llm_proxy.py --cov=llm_proxy --cov-report=html
```

### Test Categories
- **Unit Tests**: Provider configuration, model routing, error handling
- **Integration Tests**: Real API calls (requires valid API keys)
- **Configuration Tests**: backends.json validation

### Using with Open-WebUI

1. **Configure Open-WebUI to use the proxy:**
   - Set LLM proxy URL: `http://localhost:8086`
   - Add your API keys to `.env`
   - Start both services: `./manage.sh start`

2. **In Open-WebUI web interface:**
   - Go to Settings → Connections
   - Add custom OpenAI API connection
   - Set Base URL to: `http://localhost:8086/v1`
   - Use any of your configured API keys
   - Select models: GPT-4, Llama, Claude, Gemini

3. **Using Claude models:**
   - Claude models appear as regular OpenAI-compatible models in Open-WebUI
   - Available models: `claude-opus-4-1-20250805`, `claude-sonnet-4-20250514`
   - Model aliases: `claude-opus-4.1`, `claude-sonnet-4`
   - Full streaming support with real-time responses
   - Automatic message format conversion (no configuration needed)

### Environment Customization
You can override default settings in `.env`:
```env
# Use different host/port
DB_HOST=192.168.1.100
DB_PORT=5433
OPENWEBUI_PORT=8080

# Custom database names
OPENWEBUI_DB_NAME=my_openwebui
OPENWEBUI_DB_USER=my_user

# OpenAI API settings
OPENAI_API_KEY=sk-your-key
OPENAI_API_BASE_URL=https://api.openai.com/v1
```

## License

This service manager is provided as-is for setting up Open-WebUI with PostgreSQL databases.
