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

## Quick Start

1. **Setup environment:**
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your database and API credentials

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install open-webui

# Optional: Install package in development mode
pip install -e .

# Install PM2 for process management
npm install -g pm2
```

2. **Initialize database:**
```bash
# Generate and execute SQL initialization
./manage.sh init -x
```

3. **Start services:**
```bash
# Start all services with PM2
./manage.sh start

# OR start services individually:
./manage.sh start open-webui    # Start Open-WebUI only
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

# Start individual services
./manage.sh start open-webui    # Open-WebUI only
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
OPENWEBUI_PORT=5487
LLM_PROXY_PORT=8000

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
- **OpenAI**: GPT-4, GPT-3.5-turbo, GPT-4-turbo, GPT-4o
- **Groq**: Llama 3.1 70B/8B, Mixtral 8x7B, Gemma 7B
- **Claude**: Claude 3.5 Sonnet/Haiku, Claude 3 Opus/Sonnet/Haiku (via local proxy)
- **Gemini**: Gemini Pro/Pro Vision, Gemini 1.5 Pro/Flash (via local proxy)

### Backend Configuration

**Initialize backend configuration:**
```bash
# Copy default backends to customizable file
./manage.sh init backends
```

**Customize backends in `conf/backends.json`:**
```json
{
  "backends": {
    "openai": {
      "name": "OpenAI",
      "base_url": "https://api.openai.com/v1/chat/completions",
      "api_key_env": "OPENAI_API_KEY",
      "headers_template": {
        "Authorization": "Bearer {api_key}"
      },
      "models": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
      "model_prefixes": ["gpt-"]
    },
    "custom_backend": {
      "name": "Custom LLM",
      "base_url": "https://api.custom.com/v1/chat/completions",
      "api_key_env": "CUSTOM_API_KEY",
      "headers_template": {
        "Authorization": "Bearer {api_key}",
        "X-Custom-Header": "custom-value"
      },
      "models": ["custom-model-1", "custom-model-2"],
      "model_prefixes": ["custom-"]
    }
  },
  "model_aliases": {
    "gpt": "gpt-3.5-turbo",
    "fast": "gpt-3.5-turbo"
  },
  "default_models": {
    "chat": "gpt-3.5-turbo"
  }
}
```

### API Endpoints
- `GET /` - Health check
- `GET /v1/models` - List all available models (OpenAI compatible)
- `POST /v1/chat/completions` - Chat completions (OpenAI compatible)
- `POST /admin/reload-backends` - Reload backend configuration
- `GET /admin/config` - Get current configuration
- `GET /admin/backends` - List all configured backends

### Usage Examples
```bash
# Test the proxy
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# List available models
curl http://localhost:8000/v1/models

# Use model alias
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Reload backends after editing conf/backends.json
curl -X POST http://localhost:8000/admin/reload-backends

# List configured backends
curl http://localhost:8000/admin/backends
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

**Virtual environment missing:**
```bash
❌ Virtual environment not found.
```
Solution: Create venv and install Open-WebUI:
```bash
python3 -m venv venv
source venv/bin/activate
pip install open-webui
```

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
   - Set LLM proxy URL: `http://localhost:8000`
   - Add your API keys to `.env`
   - Start both services: `./manage.sh start`

2. **In Open-WebUI web interface:**
   - Go to Settings → Connections
   - Add custom OpenAI API connection
   - Set Base URL to: `http://localhost:8000/v1`
   - Use any of your configured API keys
   - Select models: GPT-4, Llama, Claude, Gemini

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
