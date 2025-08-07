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
- Supports OpenAI, Groq, Claude, and Gemini models with full OpenAI compatibility
- Complete `proxy_chat_completions` implementation with comprehensive error handling
- Routes requests based on model names and prefixes
- Configurable backends via `conf/backends.json`
- OpenAI-compatible API endpoints with streaming support
- Advanced response formatting ensuring OpenAI API compliance
- Robust timeout handling and network error management
- Comprehensive logging for debugging and monitoring
- **Claude Integration**: Full Claude API support with message format conversion and streaming

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
- Model aliases resolve first (e.g., "gpt-4.1" → "gpt-4.1", "claude-opus-4.1" → "claude-opus-4-1-20250805")
- Exact model name matching against backend configurations
- Fallback to prefix-based matching for backward compatibility
- Error handling for unknown models with proper HTTP status codes
- Support for 10+ models across 4 providers (OpenAI, Groq, Claude, Gemini)

**Template System**
- SQL templates with variable substitution
- Environment-driven configuration
- Secure password and credential handling

**Multi-Service Architecture**
- Open-WebUI as primary web interface
- LLM Proxy as backend API gateway
- PostgreSQL database for data persistence
- PM2 for production process management

**proxy_chat_completions Implementation**
- Full OpenAI-compatible `/v1/chat/completions` endpoint
- Supports both streaming and non-streaming responses
- Advanced response format normalization from various backend formats
- Comprehensive error handling: timeouts (120s), network errors, malformed requests
- Request validation with meaningful error messages
- Automatic API key management per provider
- Response formatting ensures OpenAI API compliance regardless of backend
- Logging integration for monitoring and debugging

**Claude-Specific Processing**
- **Message Format Conversion**: Automatically converts OpenAI messages to Anthropic format
- **Role Filtering**: Filters out system messages and invalid roles for Claude compatibility
- **Streaming Support**: Parses Claude streaming events (`content_block_delta`, `message_stop`) and converts to OpenAI SSE format
- **Response Conversion**: Converts Claude response structure (content blocks/completion) to OpenAI format
- **Error Handling**: Claude-specific error handling with proper HTTP status codes
- **API Compatibility**: Full Anthropic API integration with bedrock-2023-05-31 version

## Important Notes

- The LLM proxy expects backend configurations in `conf/backends.json` (falls back to `conf/backends.example.json`)
- Configuration supports both legacy format and new provider-based format with automatic conversion
- All services require proper environment configuration via `.env` file
- Testing includes both unit tests and integration tests requiring real API keys
- The system supports multiple PostgreSQL installations (Homebrew, system, Postgres.app)
- PM2 is required for production service management

## Supported Models

The proxy currently supports the following models across 4 providers:

**OpenAI Models:**
- `gpt-4o`, `gpt-4.1`, `o3`

**Groq Models:**
- `grok-4`, `grok-3`

**Claude Models:**
- `claude-opus-4-1-20250805`, `claude-sonnet-4-20250514`

**Gemini Models:**
- `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`

**Model Aliases (preserve major/minor versions, remove datecodes):**
- `gpt-4.1` → `gpt-4.1`
- `grok-4` → `grok-4` 
- `claude-sonnet-4` → `claude-sonnet-4-20250514`
- `claude-opus-4.1` → `claude-opus-4-1-20250805`
- `gemini-2.5` → `gemini-2.5-pro`