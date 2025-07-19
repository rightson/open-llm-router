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
    python3 pg_init.py -e .env -o init_openwebui_db.sql
    echo "✅ SQL file generated: init_openwebui_db.sql"
}

init_database() {
    generate_sql
    
    echo "📊 Executing database initialization..."
    
    # Try to run psql
    if "$PSQL_PATH" -d postgres -f init_openwebui_db.sql; then
        echo "✅ Database initialized successfully!"
    else
        echo "❌ Failed to execute SQL. Try running manually:"
        echo "  $PSQL_PATH -d postgres -f init_openwebui_db.sql"
        exit 1
    fi
}

start_service() {
    echo "🚀 Starting Open-WebUI..."
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "❌ Virtual environment not found. Create it first:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate" 
        echo "  pip install open-webui"
        exit 1
    fi
    
    if [ ! -x "venv/bin/open-webui" ]; then
        echo "❌ open-webui not found in virtual environment. Install it first:"
        echo "  source venv/bin/activate"
        echo "  pip install open-webui"
        exit 1
    fi
    
    echo "📊 Using database: $(echo $DATABASE_URL | cut -d'@' -f2 2>/dev/null || echo 'configured database')"
    
    # Start Open-WebUI
    exec venv/bin/open-webui serve
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

# Main command handling
case "${1:-}" in
    "init")
        if [ "${2:-}" = "--execute" ] || [ "${2:-}" = "-x" ]; then
            init_database
        else
            generate_sql
            echo "To execute manually:"
            echo "  $PSQL_PATH -d postgres -f init_openwebui_db.sql"
        fi
        ;;
    "start")
        start_service
        ;;
    "status")
        check_status
        ;;
    *)
        echo "Usage: $0 {init|start|status}"
        echo ""
        echo "Commands:"
        echo "  init          Generate SQL file from template"
        echo "  init -x       Generate and execute SQL file"
        echo "  start         Start Open-WebUI service"
        echo "  status        Check service status"
        exit 1
        ;;
esac