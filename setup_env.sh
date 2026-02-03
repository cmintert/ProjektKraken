#!/bin/bash
# Setup script for ProjektKraken test environment
# This script creates a virtual environment and installs all dependencies

set -e  # Exit on any error

echo "==================================="
echo "ProjektKraken Test Environment Setup"
echo "==================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    echo "✓ Virtual environment already exists at .venv"
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing virtual environment..."
        rm -rf .venv
    else
        echo "Using existing virtual environment"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip -q

# Install requirements
echo "Installing dependencies from requirements.txt..."
echo "(This may take several minutes...)"
pip install -r requirements.txt

echo ""
echo "==================================="
echo "Installation Complete!"
echo "==================================="
echo ""
echo "To activate the environment, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To run tests:"
echo "  pytest tests/unit/          # Run unit tests"
echo "  pytest tests/integration/   # Run integration tests"
echo "  pytest --cov=src            # Run with coverage"
echo ""
echo "To deactivate the environment:"
echo "  deactivate"
echo ""
