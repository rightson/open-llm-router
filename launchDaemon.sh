#!/bin/bash
# Launch daemon wrapper for Open LLM Router service
# This script sources environment variables and manages the service

# Service label for launchd
SERVICE_LABEL="com.github.rightson.open-llm-router"
PLIST_PATH="/Library/LaunchDaemons/${SERVICE_LABEL}.plist"

# Change to the script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Parse command
COMMAND="${1:-start}"

case "$COMMAND" in
    "status")
        echo "🔍 Checking daemon status..."
        echo ""

        # Check if service is installed
        if [ -f "$PLIST_PATH" ]; then
            echo "✅ Service installed: $PLIST_PATH"
        else
            echo "❌ Service not installed"
            echo "   Run: sudo ./manage.sh service install"
            exit 1
        fi

        # Check if service is loaded (try both with and without sudo)
        # First try without sudo (for user-level services)
        LAUNCHD_STATUS=$(launchctl list 2>/dev/null | grep "$SERVICE_LABEL" || true)

        # If not found and we're not root, try with sudo for system-level services
        if [ -z "$LAUNCHD_STATUS" ] && [ "$(id -u)" -ne 0 ]; then
            # Try to check system-level launchd without password if possible
            LAUNCHD_STATUS=$(sudo -n launchctl list 2>/dev/null | grep "$SERVICE_LABEL" || true)

            if [ -z "$LAUNCHD_STATUS" ] && [ $? -eq 1 ]; then
                echo "⚠️  Cannot check system daemon status (requires sudo)"
                echo "   Run: sudo $0 status"
                echo ""
            fi
        elif [ -z "$LAUNCHD_STATUS" ] && [ "$(id -u)" -eq 0 ]; then
            # Running as root, check system services
            LAUNCHD_STATUS=$(launchctl list 2>/dev/null | grep "$SERVICE_LABEL" || true)
        fi

        if [ -n "$LAUNCHD_STATUS" ]; then
            echo "✅ Service loaded in launchd"

            # Get PID if running
            PID=$(echo "$LAUNCHD_STATUS" | awk '{print $1}')
            if [ "$PID" != "-" ] && [ -n "$PID" ]; then
                echo "✅ Service running (PID: $PID)"

                # Get more details about the process
                PROCESS_INFO=$(ps -p "$PID" -o comm= 2>/dev/null || echo "")
                if [ -n "$PROCESS_INFO" ]; then
                    echo "   Process: $PROCESS_INFO"
                fi
            else
                echo "⚠️  Service loaded but not running"
                echo "   Try: sudo ./manage.sh service start"
            fi
        else
            if [ -z "$LAUNCHD_STATUS" ]; then
                echo "❌ Service not loaded in launchd"
                echo "   Try: sudo ./manage.sh service start"
            fi
        fi

        # Show log file status
        LOG_DIR="${OPEN_LLM_ROUTER_LOG_DIR:-${SCRIPT_DIR}/logs}"
        LOG_PATH="${LOG_DIR}/open-llm-router.log"
        ERROR_LOG_PATH="${LOG_DIR}/open-llm-router.error.log"

        echo ""
        echo "📋 Log files:"
        if [ -f "$LOG_PATH" ]; then
            LOG_SIZE=$(du -h "$LOG_PATH" | awk '{print $1}')
            LOG_LINES=$(wc -l < "$LOG_PATH" | tr -d ' ')
            echo "   Standard: $LOG_PATH ($LOG_SIZE, $LOG_LINES lines)"
        else
            echo "   Standard: $LOG_PATH (not found)"
        fi

        if [ -f "$ERROR_LOG_PATH" ]; then
            ERROR_SIZE=$(du -h "$ERROR_LOG_PATH" | awk '{print $1}')
            ERROR_LINES=$(wc -l < "$ERROR_LOG_PATH" | tr -d ' ')
            echo "   Error: $ERROR_LOG_PATH ($ERROR_SIZE, $ERROR_LINES lines)"
        else
            echo "   Error: $ERROR_LOG_PATH (not found)"
        fi

        # Show recent log entries
        echo ""
        echo "📝 Recent log entries (last 5 lines):"
        if [ -f "$LOG_PATH" ]; then
            tail -5 "$LOG_PATH" | sed 's/^/   /'
        else
            echo "   (no log file)"
        fi
        ;;

    "reload")
        echo "🔄 Reloading daemon..."

        # Check if running with sudo
        if [ "$(id -u)" -ne 0 ]; then
            echo "❌ This command requires root privileges. Please run with sudo:"
            echo "  sudo $0 reload"
            exit 1
        fi

        # Check if service is installed
        if [ ! -f "$PLIST_PATH" ]; then
            echo "❌ Service not installed"
            echo "   Run: sudo ./manage.sh service install"
            exit 1
        fi

        # Unload and reload the service
        echo "  -> Unloading service..."
        launchctl unload "$PLIST_PATH" 2>/dev/null || true

        echo "  -> Loading service..."
        launchctl load "$PLIST_PATH"

        echo "✅ Service reloaded successfully"

        # Show status after reload
        sleep 1
        "$0" status
        ;;

    "start")
        # Source environment variables if .env exists
        if [ -f .env ]; then
            source .env
        fi

        # Start the open-webui service
        exec ./manage.sh start open-webui
        ;;

    *)
        echo "Usage: $0 {start|status|reload}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the open-webui service (default, used by launchd)"
        echo "  status  - Show daemon status and recent logs"
        echo "  reload  - Reload the daemon (requires sudo)"
        echo ""
        echo "Examples:"
        echo "  $0 status"
        echo "  sudo $0 reload"
        exit 1
        ;;
esac