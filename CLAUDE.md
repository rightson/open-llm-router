# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Open LLM Router** - a self-hosted OpenRouter.ai alternative that provides:
- Multi-provider LLM routing (OpenAI, Groq, Claude, Gemini) with OpenAI-compatible API
- Complete PostgreSQL database setup for Open-WebUI
- PM2-based process management for production deployments
- Template-based database initialization

## Essential Commands

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
./manage.sh start llm-router     # LLM Router only

# Stop all services
./manage.sh stop
```

### Testing
```bash
# Run all tests
pytest tests/test_llm_router.py -v

# Run specific test categories
pytest tests/test_llm_router.py::TestLLMRouter -v          # Unit tests
pytest tests/test_llm_router.py::TestLLMRouterIntegration -v  # Integration tests (requires API keys)

# Run tests with coverage
pip install pytest-cov
pytest tests/test_llm_router.py --cov=src.open_llm_router.llm_router --cov-report=html
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

**Open LLM Router (`src/open_llm_router/llm_router.py`)**
- FastAPI application providing unified API to multiple AI providers (self-hosted OpenRouter.ai alternative)
- Supports OpenAI, Groq, Claude, and Gemini models with full OpenAI compatibility
- Modular architecture with provider-specific handlers
- OpenAI-compatible API endpoints with streaming support
- Enhanced logging with upstream provider request/response timing and status codes

**Utility Modules (`src/open_llm_router/utils/`)**
- **Logger (`utils/logger.py`)**: Enhanced logging with upstream API provider tracking, request/response timing, and status codes
- **Config (`utils/config.py`)**: Backend configuration loading with support for both new and legacy formats
- **Model Router (`utils/model_router.py`)**: Model-to-backend routing, API key management, and backend selection

**Provider Modules (`src/open_llm_router/providers/`)**
- **Base Provider (`providers/base.py`)**: Common functionality for error handling, response formatting, and streaming
- **Claude Provider (`providers/claude.py`)**: Anthropic API integration with message format conversion and streaming support
- **Gemini Provider (`providers/gemini.py`)**: Google Gemini API integration with specialized streaming parser
- **OpenAI Provider (`providers/openai.py`)**: Handles OpenAI and OpenAI-compatible providers (Groq, etc.)

**Database Initializer (`src/open_llm_router/pg_init.py`)**
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
- LLM Router as backend API gateway
- PostgreSQL database for data persistence
- PM2 for production process management

**Modular Provider Architecture**
- **Provider Selection**: Automatic provider instantiation based on model routing
- **Request Handling**: Provider-specific request processing with enhanced logging
- **Response Formatting**: Consistent OpenAI-compatible response formatting across all providers
- **Error Handling**: Comprehensive error handling with provider-specific error processing
- **Streaming Support**: Provider-specific streaming implementations with OpenAI SSE format conversion

**Enhanced Logging System**
- **Request Logging**: Logs outgoing requests with provider, model, URL, and streaming status
  - Format: `→ CLAUDE: claude-sonnet-4 (streaming) -> https://api.anthropic.com/v1/messages`
- **Response Logging**: Logs responses with timing, status codes, and success indicators
  - Format: `← CLAUDE: ✓ 200 in 1234ms for claude-sonnet-4`
- **Debug Information**: Model alias resolution, backend selection, and API key status
- **Error Tracking**: Detailed error logging with request context and provider information

**Provider-Specific Features**
- **Claude Provider**: Message format conversion, role filtering, Anthropic API streaming event parsing
- **Gemini Provider**: Specialized JSON array streaming parser, usage metadata extraction
- **OpenAI Provider**: Direct OpenAI API compatibility with fallback response formatting
- **Base Provider**: Shared error handling, response formatting, and streaming utilities

## Important Notes

- **Modular Architecture**: The LLM router is now organized into focused modules for better maintainability
- **Enhanced Logging**: INFO logger displays upstream provider, timing, and status codes for all requests
- **Backward Compatibility**: All existing functionality and APIs remain unchanged
- **Configuration**: Backend configurations in `conf/backends.json` (falls back to `conf/backends.example.json`)
- **Testing**: All existing tests pass without modification (19/19 passed)
- **Environment**: All services require proper environment configuration via `.env` file
- **Dependencies**: PostgreSQL and PM2 required for production deployment

## File Structure

```
src/open_llm_router/
├── llm_router.py              # Main FastAPI application
├── pg_init.py                # Database initialization
├── utils/                    # Utility modules
│   ├── __init__.py
│   ├── logger.py             # Enhanced logging with provider tracking
│   ├── config.py             # Backend configuration management
│   └── model_router.py       # Model routing and backend selection
└── providers/                # Provider-specific implementations
    ├── __init__.py
    ├── base.py               # Base provider with common functionality
    ├── claude.py             # Anthropic Claude API integration
    ├── gemini.py             # Google Gemini API integration
    └── openai.py             # OpenAI and compatible providers
```

## Supported Models

The router currently supports the following models across 4 providers:

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