#!/bin/bash

echo "Updated system and installing system package dependencies"
sudo apt-get update
sudo apt-get install -y \
    python3 \
    wget \
    unzip \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    xvfb

echo "Setting up python virtual environment"
uv venv
source .venv/bin/activate

echo "Installing python dependencies"
uv pip install -r requirements.txt

echo "Installing Chrome for Testing and drivers via SeleniumBase"
sbase get chrome
sbase get chromedriver latest
sbase get uc_driver latest

# Symlink Chrome for Testing into venv bin so UC mode can find it on PATH
CHROME_BIN=$(find .venv/lib -path "*/drivers/chrome-linux64/chrome" -type f 2>/dev/null | head -1)
if [ -n "$CHROME_BIN" ]; then
    ln -sf "$(pwd)/$CHROME_BIN" .venv/bin/google-chrome
    echo "Symlinked Chrome for Testing to .venv/bin/google-chrome"
fi

mkdir -p logs

echo "Setup completed successfully!"