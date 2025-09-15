#!/bin/bash
# Launch daemon wrapper for Open LLM Router service
# This script sources environment variables and starts the service

# Change to the script's directory
cd "$(dirname "$0")"

# Source environment variables if .env exists
if [ -f .env ]; then
    source .env
fi

# Start the open-webui service
exec ./manage.sh start open-webui