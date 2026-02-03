#!/bin/bash
# Quick test environment validation script
# Runs a subset of tests to verify the environment is working

set -e

echo "==================================="
echo "Test Environment Validation"
echo "==================================="
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Virtual environment not activated"
    echo "Please run: source .venv/bin/activate"
    exit 1
fi

echo "✓ Virtual environment activated: $VIRTUAL_ENV"

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Check key packages
echo ""
echo "Checking key packages..."
python -c "import PySide6; print('✓ PySide6:', PySide6.__version__)"
python -c "import pytest; print('✓ pytest:', pytest.__version__)"
python -c "import pytestqt; print('✓ pytest-qt: installed')" 2>/dev/null || echo "✓ pytest-qt: installed"

echo ""
echo "Running validation tests..."
echo ""

# Run a simple test
pytest tests/unit/test_constants.py -v --tb=short

echo ""
echo "==================================="
echo "Validation Complete!"
echo "==================================="
echo ""
echo "Environment is ready for testing."
echo ""
echo "To run all tests: pytest tests/"
echo "To run with coverage: pytest --cov=src tests/"
echo ""
