#!/bin/bash

# Start script for Laser Marking System on Linux/macOS

echo "Starting Laser Marking System..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check if required packages are installed
echo "Checking dependencies..."
python3 main.py --check-deps
if [ $? -ne 0 ]; then
    echo
    echo "Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install required packages"
        exit 1
    fi
fi

# Setup environment
echo "Setting up environment..."
python3 main.py --setup-env

# Start the application
echo
echo "Starting Laser Marking System..."
python3 main.py