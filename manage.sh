#!/bin/bash
# Management script for Open-WebUI PostgreSQL service

set -e

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "❌ .env file not found. Copy .env.example to .env first."
    echo "Run: cp .env.example .env"
    exit 1
fi

# Check required variables
required_vars=("OPENWEBUI_DB_USER" "OPENWEBUI_DB_PASSWORD" "OPENWEBUI_DB_NAME" "DATABASE_URL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Missing required environment variable: $var"
        exit 1
    fi
done

# Find psql
PSQL_PATH=""
psql_paths=(
    "/usr/bin/psql"
    "/usr/local/bin/psql"
    "/opt/homebrew/bin/psql"
    "/opt/homebrew/Cellar/postgresql@16/*/bin/psql"
    "/opt/homebrew/Cellar/postgresql@15/*/bin/psql"
    "/opt/homebrew/Cellar/postgresql@14/*/bin/psql"
    "/Applications/Postgres.app/Contents/Versions/*/bin/psql"
)

for path in "${psql_paths[@]}"; do
    if [[ "$path" == *"*"* ]]; then
        # Handle glob patterns
        found_path=$(ls $path 2>/dev/null | head -n1 || true)
        if [ -n "$found_path" ]; then
            PSQL_PATH="$found_path"
            break
        fi
    else
        if [ -x "$path" ]; then
            PSQL_PATH="$path"
            break
        fi
    fi
done

if [ -z "$PSQL_PATH" ]; then
    echo "❌ psql not found. Please install PostgreSQL."
    exit 1
fi

# Functions
generate_sql() {
    echo "🗄️  Generating SQL from template..."
    # Ensure run directory exists
    mkdir -p run
    python3 -m src.openwebui_service.pg_init -e .env -o run/init_openwebui_db.sql
    echo "✅ SQL file generated: run/init_openwebui_db.sql"
}

init_database() {
    generate_sql

    echo "📊 Executing database initialization..."

    # Try to run psql
    if "$PSQL_PATH" -d postgres -f run/init_openwebui_db.sql; then
        echo "✅ Database initialized successfully!"
    else
        echo "❌ Failed to execute SQL. Try running manually:"
        echo "  $PSQL_PATH -d postgres -f run/init_openwebui_db.sql"
        exit 1
    fi
}

check_dependencies() {
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "❌ Virtual environment not found. Create it first:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        exit 1
    fi

    # Check if PM2 is installed
    if ! command -v pm2 >/dev/null 2>&1; then
        echo "❌ PM2 not found. Install it first:"
        echo "  npm install -g pm2"
        exit 1
    fi
}

start_open_webui() {
    local extra_args="$@"
    echo "🚀 Starting Open-WebUI..."
    check_dependencies

    if [ ! -x "venv/bin/open-webui" ]; then
        echo "❌ open-webui not found in virtual environment. Install it first:"
        echo "  source venv/bin/activate"
        echo "  pip install open-webui"
        exit 1
    fi

    echo "📊 Using database: $(echo $DATABASE_URL | cut -d'@' -f2 2>/dev/null || echo 'configured database')"

    # Start Open-WebUI with extra arguments
    if [ -n "$extra_args" ]; then
        echo "📋 Extra arguments: $extra_args"
        exec venv/bin/open-webui serve --port ${OPENWEBUI_PORT:-8087} --host ${OPENWEBUI_HOST:-localhost} $extra_args
    else
        exec venv/bin/open-webui serve --port ${OPENWEBUI_PORT:-8087} --host ${OPENWEBUI_HOST:-localhost}
    fi
}

start_llm_proxy() {
    local extra_args="$@"
    echo "🚀 Starting LLM Proxy..."
    check_dependencies

    if [ ! -f "src/openwebui_service/llm_proxy.py" ]; then
        echo "❌ src/openwebui_service/llm_proxy.py not found"
        exit 1
    fi

    # Check required API keys
    if [ -z "$OPENAI_API_KEY" ] && [ -z "$GROK_API_KEY" ] && [ -z "$CLAUDE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
        echo "⚠️  Warning: No API keys configured. Add at least one API key to .env"
    fi

    echo "📊 Starting proxy on port ${LLM_PROXY_PORT:-8086}"

    # Start LLM Proxy with uvicorn and extra arguments
    if [ -n "$extra_args" ]; then
        echo "📋 Extra arguments: $extra_args"
        exec venv/bin/python -m uvicorn src.openwebui_service.llm_proxy:app --host ${LLM_PROXY_HOST:-localhost} --port ${LLM_PROXY_PORT:-8086} $extra_args
    else
        exec venv/bin/python -m uvicorn src.openwebui_service.llm_proxy:app --host ${LLM_PROXY_HOST:-localhost} --port ${LLM_PROXY_PORT:-8086}
    fi
}

start_all_services() {
    echo "🚀 Starting all services with PM2..."
    check_dependencies

    # Stop existing PM2 processes
    pm2 delete open-webui llm-proxy 2>/dev/null || true

    # Start Open-WebUI with PM2
    if [ ! -x "venv/bin/open-webui" ]; then
        echo "❌ open-webui not found in virtual environment. Install it first:"
        echo "  source venv/bin/activate"
        echo "  pip install open-webui"
        exit 1
    fi

    echo "📊 Using database: $(echo $DATABASE_URL | cut -d'@' -f2 2>/dev/null || echo 'configured database')"

    # Ensure run directory exists
    mkdir -p run

    # Create PM2 ecosystem file
    cat > run/ecosystem.config.js << EOF
module.exports = {
  apps: [
    {
      name: 'open-webui',
      script: './venv/bin/open-webui',
      args: 'serve --port ${OPENWEBUI_PORT:-5487}',
      env: {
        DATABASE_URL: '${DATABASE_URL}',
        OPENAI_API_KEY: '${OPENAI_API_KEY:-}',
        NODE_ENV: 'production'
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '1G'
    },
    {
      name: 'llm-proxy',
      script: './venv/bin/python',
      args: '-m uvicorn src.openwebui_service.llm_proxy:app --host ${LLM_PROXY_HOST:-localhost} --port ${LLM_PROXY_PORT:-8086}',
      env: {
        OPENAI_API_KEY: '${OPENAI_API_KEY:-}',
        GROK_API_KEY: '${GROK_API_KEY:-}',
        CLAUDE_API_KEY: '${CLAUDE_API_KEY:-}',
        GEMINI_API_KEY: '${GEMINI_API_KEY:-}',
        NODE_ENV: 'production'
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '500M'
    }
  ]
};
EOF

    # Start services
    pm2 start run/ecosystem.config.js
    pm2 save

    echo "✅ Services started with PM2:"
    pm2 status
    echo ""
    echo "📊 Access points:"
    echo "  Open-WebUI: http://localhost:${OPENWEBUI_PORT:-5487}"
    echo "  LLM Proxy:  http://localhost:${LLM_PROXY_PORT:-8086}"
    echo ""
    echo "PM2 commands:"
    echo "  pm2 status          # Check status"
    echo "  pm2 logs            # View logs"
    echo "  pm2 restart all     # Restart services"
    echo "  pm2 stop all        # Stop services"
    echo "  pm2 delete all      # Delete services"
}

stop_services() {
    echo "🛑 Stopping services..."
    pm2 delete open-webui llm-proxy 2>/dev/null || true
    echo "✅ All services stopped"
}

check_status() {
    echo "📊 Checking Open-WebUI service status..."

    # Check environment
    echo "✅ Environment configuration: OK"

    # Check database connection
    if [ -n "$DATABASE_URL" ]; then
        if "$PSQL_PATH" "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
            echo "✅ Database connection: OK"
        else
            echo "❌ Database connection: FAILED"
        fi
    else
        echo "❌ DATABASE_URL not configured"
    fi

    # Check Open-WebUI installation
    if [ -x "venv/bin/open-webui" ]; then
        version=$(venv/bin/open-webui --version 2>/dev/null || echo "unknown")
        echo "✅ Open-WebUI: $version"
    else
        echo "❌ Open-WebUI: NOT INSTALLED"
    fi
}

init_models() {
    echo "🔧 Initializing models configuration..."

    if [ ! -f "conf/models.example.json" ]; then
        echo "❌ conf/models.example.json not found"
        exit 1
    fi

    if [ -f "conf/models.json" ]; then
        echo "⚠️  conf/models.json already exists. Backup created as conf/models.json.bak"
        cp conf/models.json conf/models.json.bak
    fi

    cp conf/models.example.json conf/models.json
    echo "✅ Copied conf/models.example.json to conf/models.json"
    echo "📝 Edit conf/models.json to customize your model configurations"
}

init_backends() {
    echo "🔧 Initializing backends configuration..."

    if [ ! -f "conf/backends.example.json" ]; then
        echo "❌ conf/backends.example.json not found"
        exit 1
    fi

    if [ -f "conf/backends.json" ]; then
        echo "⚠️  conf/backends.json already exists. Backup created as conf/backends.json.bak"
        cp conf/backends.json conf/backends.json.bak
    fi

    cp conf/backends.example.json conf/backends.json
    echo "✅ Copied conf/backends.example.json to conf/backends.json"
    echo "📝 Edit conf/backends.json to customize your backend and model configurations"

    # Also migrate models.json if it exists
    if [ -f "conf/models.json" ]; then
        echo "⚠️  Found existing conf/models.json - consider migrating to conf/backends.json format"
        echo "📋 Backup created as conf/models.json.bak.$(date +%s)"
        cp conf/models.json "conf/models.json.bak.$(date +%s)"
    fi
}

# Main command handling
case "${1:-}" in
    "init")
        if [ "${2:-}" = "models" ]; then
            init_models
        elif [ "${2:-}" = "backends" ]; then
            init_backends
        elif [ "${2:-}" = "--execute" ] || [ "${2:-}" = "-x" ]; then
            init_database
        else
            generate_sql
            echo "To execute manually:"
            echo "  $PSQL_PATH -d postgres -f run/init_openwebui_db.sql"
        fi
        ;;
    "start")
        case "${2:-}" in
            "open-webui")
                shift 2  # Remove 'start' and 'open-webui'
                start_open_webui "$@"
                ;;
            "llm-proxy")
                shift 2  # Remove 'start' and 'llm-proxy'
                start_llm_proxy "$@"
                ;;
            "")
                start_all_services
                ;;
            *)
                echo "Usage: $0 start [open-webui|llm-proxy] [extra-options...]"
                echo ""
                echo "  start                      Start all services with PM2"
                echo "  start open-webui [opts]    Start Open-WebUI only with extra options"
                echo "  start llm-proxy [opts]     Start LLM Proxy only with extra options"
                echo ""
                echo "Examples:"
                echo "  $0 start llm-proxy --reload --log-level debug"
                echo "  $0 start open-webui --dev"
                exit 1
                ;;
        esac
        ;;
    "stop")
        stop_services
        ;;
    "status")
        check_status
        ;;
    *)
        echo "Usage: $0 {init|start|stop|status}"
        echo ""
        echo "Commands:"
        echo "  init                       Generate SQL file from template"
        echo "  init -x                    Generate and execute SQL file"
        echo "  init models                Initialize models.json from example (legacy)"
        echo "  init backends              Initialize backends.json from example"
        echo "  start                      Start all services with PM2"
        echo "  start open-webui [opts]    Start Open-WebUI only with extra options"
        echo "  start llm-proxy [opts]     Start LLM Proxy only with extra options"
        echo "  stop                       Stop all PM2 services"
        echo "  status                     Check service status"
        echo ""
        echo "Examples:"
        echo "  $0 start llm-proxy --reload --log-level debug"
        echo "  $0 start open-webui --dev"
        exit 1
        ;;
esac
