#!/usr/bin/env bash
# Fix venv to use Python with tkinter support

echo "Fixing venv to support tkinter..."

PYTHON_BIN="${PYTHON_BIN:-python3.12}"

# Deactivate if active
deactivate 2>/dev/null || true

# Backup old venv
if [ -d .venv ]; then
    echo "Backing up existing .venv to .venv.backup..."
    rm -rf .venv.backup 2>/dev/null
    mv .venv .venv.backup
fi

# Create new venv with a Python that has tkinter support
echo "Creating new venv with tkinter-enabled Python (${PYTHON_BIN})..."
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "✗ ${PYTHON_BIN} not found. Install Python 3.12.x or set PYTHON_BIN to a tkinter-enabled interpreter."
    exit 1
fi
"${PYTHON_BIN}" -m venv .venv

# Activate and install deps
echo "Installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Test tkinter
echo ""
echo "Testing tkinter..."
python3 -c "import tkinter; print('✅ Tkinter is available')"
python3 -c "import matplotlib, PIL; print('✅ Matplotlib and Pillow ready')"

echo ""
echo "✅ venv fixed! Now run:"
echo "  source .venv/bin/activate"
echo "  ./scripts/annotate_remaining_frames.sh"
