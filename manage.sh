#!/bin/bash
# Management script for Open-WebUI PostgreSQL service

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
    "/opt/homebrew/Cellar/postgresql@17/*/bin/psql"
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
    python3 -m src.open_llm_router.pg_init -e .env -o run/init_openwebui_db.sql
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
        echo "📦 PM2 not found. Installing pm2"
        npm install -g pm2
        echo "✅ pm2 installed"
    fi
}

check_dependencies_llm_router() {
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "📦 Virtual environment not found. Creating it..."
        python3 -m venv venv
        echo "✅ Virtual environment created"

        echo "📦 Installing requirements..."
        venv/bin/pip3 install -r requirements.txt
        echo "✅ Requirements installed"
    fi

    # Check if uvicorn is available
    if [ ! -x "venv/bin/uvicorn" ]; then
        echo "📦 uvicorn not found. Installing requirements..."
        venv/bin/pip3 install -r requirements.txt
        echo "✅ Requirements installed"
    fi
}

check_dependencies_open_webui() {
    # Check Python version (open-webui requires Python 3.11+)
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    required_version="3.11"

    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        echo "❌ open-webui requires Python 3.11+, but found Python $python_version"
        echo "Please install Python 3.11+ and ensure 'python3' points to it"
        exit 1
    fi

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "📦 Virtual environment not found. Creating it..."
        python3 -m venv venv
        echo "✅ Virtual environment created"

        echo "📦 Installing requirements..."
        venv/bin/pip3 install -r requirements.txt
        echo "✅ Requirements installed"
    fi

    # Check if open-webui is available
    if [ ! -x "venv/bin/open-webui" ]; then
        echo "📦 open-webui not found. Installing requirements..."
        venv/bin/pip3 install -r requirements.txt
        echo "✅ Requirements installed"
    fi
}

start_open_webui() {
    local extra_args="$@"
    echo "🚀 Starting Open-WebUI..."
    check_dependencies_open_webui

    echo "📊 Using database: $(echo $DATABASE_URL | cut -d'@' -f2 2>/dev/null || echo 'configured database')"
    export DATABASE_URL=$DATABASE_URL

    # Start Open-WebUI with extra arguments
    if [ -n "$extra_args" ]; then
        echo "📋 Extra arguments: $extra_args"
        exec venv/bin/open-webui serve --port ${OPENWEBUI_PORT:-8087} --host ${OPENWEBUI_HOST:-localhost} $extra_args
    else
        exec venv/bin/open-webui serve --port ${OPENWEBUI_PORT:-8087} --host ${OPENWEBUI_HOST:-localhost}
    fi
}

start_llm_router() {
    local extra_args="$@"
    echo "🚀 Starting LLM Router..."
    check_dependencies_llm_router

    if [ ! -f "src/open_llm_router/llm_router.py" ]; then
        echo "❌ src/open_llm_router/llm_router.py not found"
        exit 1
    fi

    # Check required API keys
    if [ -z "$OPENAI_API_KEY" ] && [ -z "$GROK_API_KEY" ] && [ -z "$CLAUDE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
        echo "⚠️  Warning: No API keys configured. Add at least one API key to .env"
    fi

    echo "📊 Starting router on port ${LLM_ROUTER_PORT:-8086}"

    # Start LLM Router with uvicorn and extra arguments
    if [ -n "$extra_args" ]; then
        echo "📋 Extra arguments: $extra_args"
        exec venv/bin/python -m uvicorn src.open_llm_router.llm_router:app --host ${LLM_ROUTER_HOST:-localhost} --port ${LLM_ROUTER_PORT:-8086} $extra_args
    else
        exec venv/bin/python -m uvicorn src.open_llm_router.llm_router:app --host ${LLM_ROUTER_HOST:-localhost} --port ${LLM_ROUTER_PORT:-8086}
    fi
}

start_all_services() {
    echo "🚀 Starting all services with PM2..."
    check_dependencies

    # Stop existing PM2 processes
    pm2 delete open-webui llm-router 2>/dev/null || true

    # Start Open-WebUI and LLM Router with PM2

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
      args: 'serve --port ${OPENWEBUI_PORT:-8087}',
      interpreter: './venv/bin/python',
      env: {
        DATABASE_URL: '${DATABASE_URL}',
        OPENAI_API_KEY: '${OPENAI_API_KEY:-}',
        NODE_ENV: 'production'
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '2G'
    },
    {
      name: 'llm-router',
      script: './venv/bin/python',
      args: '-m uvicorn src.open_llm_router.llm_router:app --host ${LLM_ROUTER_HOST:-localhost} --port ${LLM_ROUTER_PORT:-8086}',
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
    echo "  Open-WebUI: http://localhost:${OPENWEBUI_PORT:-8087}"
    echo "  LLM Router: http://localhost:${LLM_ROUTER_PORT:-8086}"
    echo ""
    echo "PM2 commands:"
    echo "  pm2 status          # Check status"
    echo "  pm2 logs            # View logs"
    echo "  pm2 restart all     # Restart services"
    echo "  pm2 stop all        # Stop services"
    echo "  pm2 delete all      # Delete services"
}

start_ollama() {
    echo "🚀 Starting Ollama server..."

    # Check if ollama is installed
    if ! command -v ollama >/dev/null 2>&1; then
        echo "❌ ollama not found. Please install Ollama first:"
        echo "  https://ollama.ai/download"
        exit 1
    fi

    # Export all OLLAMA_* environment variables from .env
    echo "📋 Loading OLLAMA_* environment variables from .env..."
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue

        # Only export variables that start with OLLAMA_
        if [[ "$key" =~ ^OLLAMA_ ]]; then
            # Remove any surrounding quotes from value
            value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
            export "$key=$value"
            echo "  ✓ $key"
        fi
    done < .env

    echo "🔄 Starting ollama serve..."
    exec ollama serve
}

check_ollama_installed() {
    if ! command -v ollama >/dev/null 2>&1; then
        echo "❌ ollama not found. Please install Ollama first:"
        echo "  https://ollama.ai/download"
        return 1
    fi
    return 0
}

stop_services() {
    echo "🛑 Stopping services..."
    pm2 delete open-webui llm-router ollama 2>/dev/null || true
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

scan_ollama_models() {
    echo "🔍 Scanning Ollama models..."

    # Check if ollama is installed
    if ! command -v ollama >/dev/null 2>&1; then
        echo "⚠️  Ollama not found. Skipping Ollama scan."
        echo "   Install from https://ollama.ai/download"
        return 1
    fi

    # Get OLLAMA_HOST from environment or use default
    local ollama_host="${OLLAMA_HOST:-http://localhost:11434}"

    # Try to list models via API
    local response=$(curl -s "${ollama_host}/api/tags" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$response" ]; then
        echo "⚠️  Could not connect to Ollama at ${ollama_host}"
        echo "   Make sure Ollama is running: ./manage.sh start ollama"
        return 1
    fi

    # Extract model names using Python (more reliable than jq which might not be installed)
    local models=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    for model in models:
        print(model.get('name', ''))
except:
    pass
" 2>/dev/null)

    if [ -z "$models" ]; then
        echo "⚠️  No Ollama models found"
        return 1
    fi

    echo "✅ Found Ollama models:"
    echo "$models" | while read -r model; do
        [ -n "$model" ] && echo "   - $model"
    done

    echo "$models"
    return 0
}

scan_lmstudio_models() {
    echo "🔍 Scanning LM Studio models..."

    # Get LM Studio host from environment or use default
    local lmstudio_host="${LMSTUDIO_HOST:-http://localhost:1234}"

    # Try to list models via OpenAI-compatible API
    local response=$(curl -s "${lmstudio_host}/v1/models" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$response" ]; then
        echo "⚠️  Could not connect to LM Studio at ${lmstudio_host}"
        echo "   Make sure LM Studio is running with the server started"
        return 1
    fi

    # Extract model IDs using Python
    local models=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('data', [])
    for model in models:
        print(model.get('id', ''))
except:
    pass
" 2>/dev/null)

    if [ -z "$models" ]; then
        echo "⚠️  No LM Studio models found"
        return 1
    fi

    echo "✅ Found LM Studio models:"
    echo "$models" | while read -r model; do
        [ -n "$model" ] && echo "   - $model"
    done

    echo "$models"
    return 0
}

update_config_with_models() {
    local service="$1"
    shift
    local models=("$@")

    if [ ${#models[@]} -eq 0 ]; then
        echo "⚠️  No models to add"
        return 1
    fi

    local config_file="conf/config.yml"

    if [ ! -f "$config_file" ]; then
        echo "❌ $config_file not found. Creating from example..."
        if [ -f "conf/config.example.yml" ]; then
            cp conf/config.example.yml "$config_file"
        else
            echo "❌ conf/config.example.yml not found"
            return 1
        fi
    fi

    # Backup config file with timestamp
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="${config_file}.${timestamp}.bak"
    cp "$config_file" "$backup_file"
    echo "📦 Backup created: $backup_file"

    # Use Python to update the YAML file
    python3 << EOF
import yaml
import sys
from pathlib import Path

config_file = "$config_file"
service = "$service"
models = [m.strip() for m in """${models[*]}""".split() if m.strip()]

try:
    # Load existing config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f) or {}

    # Ensure model_list exists
    if 'model_list' not in config:
        config['model_list'] = []

    # Determine API parameters based on service
    if service == "ollama":
        api_base = "${OLLAMA_HOST:-http://localhost:11434}"
        model_prefix = "ollama/"
    elif service == "lmstudio":
        api_base = "${LMSTUDIO_HOST:-http://localhost:1234}"
        model_prefix = "openai/"
    else:
        print(f"❌ Unknown service: {service}")
        sys.exit(1)

    # Track existing model names
    existing_models = {m.get('model_name', ''): i for i, m in enumerate(config['model_list'])}

    # Add or update models
    added_count = 0
    updated_count = 0

    for model in models:
        if not model:
            continue

        # Clean model name for display
        model_display_name = model.replace(':', '-').replace('/', '-')

        model_entry = {
            'model_name': model_display_name,
            'litellm_params': {
                'model': f"{model_prefix}{model}",
                'api_base': api_base
            }
        }

        # Add custom_llm_provider for Ollama
        if service == "ollama":
            model_entry['litellm_params']['custom_llm_provider'] = 'ollama'

        # Check if model already exists
        if model_display_name in existing_models:
            # Update existing entry
            idx = existing_models[model_display_name]
            config['model_list'][idx] = model_entry
            updated_count += 1
        else:
            # Add new entry
            config['model_list'].append(model_entry)
            added_count += 1

    # Write updated config
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"✅ Config updated: {added_count} models added, {updated_count} models updated")

except Exception as e:
    print(f"❌ Error updating config: {e}")
    sys.exit(1)
EOF

    if [ $? -eq 0 ]; then
        echo "✅ Successfully updated $config_file"
        return 0
    else
        echo "❌ Failed to update config"
        return 1
    fi
}

scan_models() {
    local service="${1:-all}"
    local update_config="${2:-false}"

    echo "🔍 Scanning for available models..."
    echo ""

    local ollama_models=()
    local lmstudio_models=()

    # Scan Ollama if requested
    if [ "$service" = "all" ] || [ "$service" = "ollama" ]; then
        local ollama_output=$(scan_ollama_models)
        local ollama_status=$?

        if [ $ollama_status -eq 0 ]; then
            # Read models into array
            while IFS= read -r line; do
                [ -n "$line" ] && ollama_models+=("$line")
            done <<< "$(echo "$ollama_output" | grep -v "^🔍\|^✅\|^⚠️\|^   -")"
        fi
        echo ""
    fi

    # Scan LM Studio if requested
    if [ "$service" = "all" ] || [ "$service" = "lmstudio" ]; then
        local lmstudio_output=$(scan_lmstudio_models)
        local lmstudio_status=$?

        if [ $lmstudio_status -eq 0 ]; then
            # Read models into array
            while IFS= read -r line; do
                [ -n "$line" ] && lmstudio_models+=("$line")
            done <<< "$(echo "$lmstudio_output" | grep -v "^🔍\|^✅\|^⚠️\|^   -")"
        fi
        echo ""
    fi

    # Update config if requested
    if [ "$update_config" = "true" ] || [ "$update_config" = "--update" ] || [ "$update_config" = "-u" ]; then
        if [ ${#ollama_models[@]} -gt 0 ]; then
            echo "📝 Updating config.yml with Ollama models..."
            update_config_with_models "ollama" "${ollama_models[@]}"
            echo ""
        fi

        if [ ${#lmstudio_models[@]} -gt 0 ]; then
            echo "📝 Updating config.yml with LM Studio models..."
            update_config_with_models "lmstudio" "${lmstudio_models[@]}"
            echo ""
        fi
    else
        echo "💡 To update conf/config.yml with these models, run:"
        echo "   $0 scan-models $service --update"
    fi
}

# --- Service Management ---
SERVICE_LABEL="com.github.rightson.open-llm-router"
PLIST_NAME="${SERVICE_LABEL}.plist"
SOURCE_PLIST_TEMPLATE="${SCRIPT_DIR}/launchDaemon/${PLIST_NAME}.template"
SOURCE_PLIST_PATH="${SCRIPT_DIR}/launchDaemon/${PLIST_NAME}"
DEST_PLIST_PATH="/Library/LaunchDaemons/${PLIST_NAME}"
LOG_DIR="${OPEN_LLM_ROUTER_LOG_DIR:-${SCRIPT_DIR}/logs}"
LOG_PATH="${LOG_DIR}/open-llm-router.log"
ERROR_LOG_PATH="${LOG_DIR}/open-llm-router.error.log"

manage_service() {
    sub_command="$1"

    # Check for sudo access for commands that need it
    if [[ "$sub_command" == "install" || "$sub_command" == "uninstall" || "$sub_command" == "start" || "$sub_command" == "stop" ]]; then
        if [ "$(id -u)" -ne 0 ]; then
            echo "❌ This command requires root privileges. Please run with sudo:"
            echo "  sudo $0 service $sub_command"
            exit 1
        fi
    fi

    case "$sub_command" in
        "install")
            echo "🛠️  Installing service..."

            # Check if template exists
            if [ ! -f "$SOURCE_PLIST_TEMPLATE" ]; then
                echo "❌ Source plist template not found at: $SOURCE_PLIST_TEMPLATE"
                exit 1
            fi

            # Create logs directory if it doesn't exist
            mkdir -p "${LOG_DIR}"

            # Get current user
            CURRENT_USER="${SUDO_USER:-$(whoami)}"

            # Generate plist from template with actual paths
            echo "  -> Generating plist with absolute paths..."
            sed -e "s|{{WORKING_DIR}}|${SCRIPT_DIR}|g" \
                -e "s|{{USER}}|${CURRENT_USER}|g" \
                -e "s|{{LOG_PATH}}|${LOG_PATH}|g" \
                -e "s|{{ERROR_LOG_PATH}}|${ERROR_LOG_PATH}|g" \
                "$SOURCE_PLIST_TEMPLATE" > "$SOURCE_PLIST_PATH"

            echo "  -> Copying plist to $DEST_PLIST_PATH"
            cp "$SOURCE_PLIST_PATH" "$DEST_PLIST_PATH"

            echo "  -> Setting ownership to root:wheel"
            chown root:wheel "$DEST_PLIST_PATH"

            echo "  -> Loading service with launchctl..."
            launchctl load "$DEST_PLIST_PATH"

            echo "✅ Service installed and started successfully."
            echo "   To check logs, run: $0 service logs"
            ;;
        "uninstall")
            echo "🗑️  Uninstalling service..."
            if [ -f "$DEST_PLIST_PATH" ]; then
                echo "  -> Unloading service with launchctl..."
                launchctl unload "$DEST_PLIST_PATH" 2>/dev/null || true

                echo "  -> Removing plist file: $DEST_PLIST_PATH"
                rm "$DEST_PLIST_PATH"
                echo "✅ Service uninstalled."
            else
                echo "⚠️  Service not found at $DEST_PLIST_PATH. Nothing to do."
            fi
            ;;
        "start")
            echo "🚀 Starting service..."
            if [ ! -f "$DEST_PLIST_PATH" ]; then
                echo "❌ Service not installed. Run 'sudo $0 service install' first."
                exit 1
            fi
            launchctl load "$DEST_PLIST_PATH"
            echo "✅ Service started."
            ;;
        "stop")
            echo "🛑 Stopping service..."
            if [ ! -f "$DEST_PLIST_PATH" ]; then
                echo "❌ Service not installed."
                exit 1
            fi
            launchctl unload "$DEST_PLIST_PATH"
            echo "✅ Service stopped."
            ;;
        "logs")
            echo "📋 Tailing logs... (Press Ctrl+C to exit)"
            echo "--- Standard Log: $LOG_PATH ---"
            tail -f "$LOG_PATH"
            ;;
        "logs:error")
            echo "📋 Tailing error logs... (Press Ctrl+C to exit)"
            echo "--- Error Log: $ERROR_LOG_PATH ---"
            tail -f "$ERROR_LOG_PATH"
            ;;
        *)
            echo "Usage: $0 service {install|uninstall|start|stop|logs|logs:error}"
            exit 1
            ;;
    esac
}

# Main command handling
case "${1:-}" in
    "init")
        if [ "${2:-}" = "models" ]; then
            init_models
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
            "llm-router")
                shift 2  # Remove 'start' and 'llm-router'
                start_llm_router "$@"
                ;;
            "ollama")
                start_ollama
                ;;
            "")
                start_all_services
                ;;
            *)
                echo "Usage: $0 start [open-webui|llm-router|ollama] [extra-options...]"
                echo ""
                echo "  start                      Start Open-WebUI and LLM Router with PM2"
                echo "  start open-webui [opts]    Start Open-WebUI only with extra options"
                echo "  start llm-router [opts]    Start LLM Router only with extra options"
                echo "  start ollama               Start Ollama server only (no PM2)"
                echo ""
                echo "Examples:"
                echo "  $0 start llm-router --reload --log-level debug"
                echo "  $0 start ollama"
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
    "service")
        manage_service "${2:-}"
        ;;
    "scan-models")
        scan_models "${2:-all}" "${3:-false}"
        ;;
    *)
        echo "Usage: $0 {init|start|stop|status|scan-models|service}"
        echo ""
        echo "Commands:"
        echo "  init                       Generate SQL file from template"
        echo "  init -x                    Generate and execute SQL file"
        echo "  init models                Initialize models.json from example (legacy)"
        echo "  start                      Start Open-WebUI and LLM Router with PM2"
        echo "  start open-webui [opts]    Start Open-WebUI only with extra options"
        echo "  start llm-router [opts]    Start LLM Router only with extra options"
        echo "  start ollama               Start Ollama server only (no PM2)"
        echo "  stop                       Stop all PM2 services"
        echo "  status                     Check service status"
        echo "  scan-models [service] [-u] Scan available models from Ollama/LM Studio"
        echo "                             service: all (default), ollama, or lmstudio"
        echo "                             -u, --update: Update conf/config.yml"
        echo "  service <cmd>              Manage the launchd service"
        echo "                             (install, uninstall, start, stop, logs)"
        echo ""
        echo "Examples:"
        echo "  $0 start                   # Start Open-WebUI and LLM Router with PM2"
        echo "  $0 start llm-router --reload --log-level debug"
        echo "  $0 start ollama            # Start ollama directly (no PM2)"
        echo "  $0 scan-models             # Scan all available models"
        echo "  $0 scan-models ollama -u   # Scan Ollama and update config.yml"
        echo "  $0 scan-models lmstudio -u # Scan LM Studio and update config.yml"
        echo "  sudo $0 service install"
        exit 1
        ;;
esac
