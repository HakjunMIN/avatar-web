#!/bin/bash

action=$1

function check_python_installed() {
    command -v python >/dev/null 2>&1
}

function check_uv_installed() {
    command -v uv >/dev/null 2>&1
}

if [ "$action" == "configure" ]; then
    echo "Installing Linux platform required dependencies..."
    sudo apt-get update
    sudo apt-get install -y build-essential libssl-dev libasound2 wget

    if ! check_python_installed; then
        echo -e "\e[31mPython is not installed. Please install Python to proceed.\e[0m"
        exit 1
    fi

    if ! check_uv_installed; then
        echo "uv is not installed. Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source $HOME/.cargo/env || export PATH="$HOME/.cargo/bin:$PATH"
        
        if ! check_uv_installed; then
            echo -e "\e[31muv installation failed. Please install uv manually to proceed.\e[0m"
            echo "Visit https://docs.astral.sh/uv/getting-started/installation/ for installation instructions."
            exit 1
        fi
    fi

    echo "Installing requirements packages with uv..."
    if ! uv sync; then
        exit 1
    fi
elif [ "$action" == "run" ]; then

    # Load environment variables from .env file
    ENV_FILE=".env/.env.dev" 
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"

        # Ensure environment variables are available to the C++ binary
        export SPEECH_KEY=$SPEECH_RESOURCE_KEY
        export AZURE_OPENAI_API_KEY=$SPEECH_RESOURCE_KEY
        export SPEECH_REGION=$SERVICE_REGION
        export AZURE_OPENAI_ENDPOINT="https://${CUSTOM_SUBDOMAIN_NAME}.openai.azure.com/"
        echo "Environment variables loaded from $ENV_FILE"

    else
        echo "Environment file $ENV_FILE not found. You can create one to set environment variables or manually set secrets in environment variables."
    fi
    uv run python -m flask run -h 0.0.0.0 -p 5000
else
    echo -e "\e[31mInvalid action: $action\e[0m"
    echo "Usage: $0 configure or $0 run"
    exit 1
fi
