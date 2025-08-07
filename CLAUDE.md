# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install open-webui

# Optional: Install package in development mode
pip install -e .

# Copy environment configuration
cp .env.example .env
# Edit .env with your database and API credentials
```

### Database Management
```bash
# Generate SQL initialization file
./manage.sh init

# Generate and execute SQL initialization
./manage.sh init -x

# Initialize backend configuration (recommended for new setups)
./manage.sh init backends

# Check service and database status
./manage.sh status
```

### Service Management
```bash
# Start all services with PM2
./manage.sh start

# Start individual services
./manage.sh start open-webui    # Open-WebUI only
./manage.sh start llm-proxy     # LLM Proxy only

# Stop all services
./manage.sh stop
```

### Testing
```bash
# Run all tests
pytest tests/test_llm_proxy.py -v

# Run specific test categories
pytest tests/test_llm_proxy.py::TestLLMProxy -v          # Unit tests
pytest tests/test_llm_proxy.py::TestLLMProxyIntegration -v  # Integration tests (requires API keys)

# Run tests with coverage
pip install pytest-cov
pytest tests/test_llm_proxy.py --cov=src.openwebui_service.llm_proxy --cov-report=html
```

### Code Quality
```bash
# Format code with Black
black src/ tests/

# Type checking with MyPy
mypy src/

# Lint with Flake8
flake8 src/ tests/
```

## Architecture Overview

### Core Components

**LLM Proxy (`src/openwebui_service/llm_proxy.py`)**
- FastAPI application providing unified API to multiple AI providers
- Supports OpenAI, Groq, Claude, and Gemini models
- Routes requests based on model names and prefixes
- Configurable backends via `conf/backends.json`
- OpenAI-compatible API endpoints

**Database Initializer (`src/openwebui_service/pg_init.py`)**
- PostgreSQL database setup utility using SQL templates
- Environment variable substitution for secure configuration
- Creates databases, users, and permissions for Open-WebUI

**Management Script (`manage.sh`)**
- Bash script for service lifecycle management
- PM2 process management integration
- Database initialization and status checking
- Multi-platform PostgreSQL detection

### Configuration System

**Backend Configuration (`conf/backends.json`)**
- Defines AI provider endpoints and authentication
- Model mappings and aliases
- Headers template for API requests
- Extensible for custom providers

**Environment Variables (`.env`)**
- Database connection settings
- API keys for AI providers
- Service ports and configuration

### Key Patterns

**Model Routing Logic**
- Model aliases resolve first (e.g., "gpt" → "gpt-3.5-turbo")
- Exact model name matching against backend configurations
- Fallback to prefix-based matching for backward compatibility
- Error handling for unknown models

**Template System**
- SQL templates with variable substitution
- Environment-driven configuration
- Secure password and credential handling

**Multi-Service Architecture**
- Open-WebUI as primary web interface
- LLM Proxy as backend API gateway
- PostgreSQL database for data persistence
- PM2 for production process management

## Important Notes

- The LLM proxy expects backend configurations in `conf/backends.json` (falls back to `conf/backends.example.json`)
- All services require proper environment configuration via `.env` file
- Testing includes both unit tests and integration tests requiring real API keys
- The system supports multiple PostgreSQL installations (Homebrew, system, Postgres.app)
- PM2 is required for production service management