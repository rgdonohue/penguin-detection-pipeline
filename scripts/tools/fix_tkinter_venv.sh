#!/bin/bash
# Fix venv to use Python with tkinter support

echo "Fixing venv to support tkinter..."

# Deactivate if active
deactivate 2>/dev/null || true

# Backup old venv
if [ -d .venv ]; then
    echo "Backing up existing .venv to .venv.backup..."
    rm -rf .venv.backup 2>/dev/null
    mv .venv .venv.backup
fi

# Create new venv with system Python (which has tkinter)
echo "Creating new venv with tkinter-enabled Python..."
/usr/bin/python3 -m venv .venv

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
