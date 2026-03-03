#!/bin/bash

VENV_DIR="venv"

# Check if the virtual environment exists by looking for the activate script
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment. Please ensure 'python3-venv' or 'python3' is installed."
        exit 1
    fi

    echo "[INFO] Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    echo "[INFO] Upgrading pip..."
    python3 -m pip install --upgrade pip

    echo "[INFO] Installing requirements..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install requirements."
        exit 1
    fi
    echo "[INFO] Setup complete!"
else
    echo "[INFO] Activating existing virtual environment..."
    source "$VENV_DIR/bin/activate"
fi

echo "[INFO] Starting NIR Tracker Server..."
python3 server.py
