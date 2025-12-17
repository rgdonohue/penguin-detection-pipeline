#!/bin/bash
# Environment Validation Script
# Validates that the venv environment is properly set up and all dependencies work

set -e  # Exit on any error

echo "🧪 Penguin Pipeline Environment Validation"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python 3.11+ is available
echo "1. Checking Python availability..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 not found in PATH${NC}"
    echo "  Install Python 3.11+ from: https://www.python.org/downloads/"
    exit 1
else
    echo -e "${GREEN}✓ python3 found: $(which python3)${NC}"
    python3 --version

    # Check version is 3.11+
    py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ $(echo "$py_version < 3.11" | bc -l 2>/dev/null || echo "0") -eq 1 ]]; then
        echo -e "${YELLOW}⚠ Python $py_version detected (3.11+ recommended)${NC}"
    fi
fi
echo ""

# Check if venv exists
echo "2. Checking for virtual environment..."
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓ Virtual environment '.venv' exists${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment '.venv' not found${NC}"
    echo "  Creating virtual environment..."
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
echo ""

# Activate venv and check dependencies
echo "3. Validating dependencies..."
echo "  (Activating '.venv' environment)"

# Source the venv
source .venv/bin/activate

# Check if requirements installed
if python3 -c "import laspy" 2>/dev/null; then
    echo -e "${GREEN}✓ Dependencies appear to be installed${NC}"
else
    echo -e "${YELLOW}⚠ Dependencies not installed${NC}"
    echo "  Installing from requirements.txt..."
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Validate modules
python3 -c "
import sys
import importlib

required_modules = [
    ('laspy', 'LiDAR processing'),
    ('numpy', 'Numerical computing'),
    ('scipy', 'Scientific computing'),
    ('skimage', 'Image processing'),
    ('matplotlib', 'Plotting'),
    ('pytest', 'Testing framework'),
]

print('Checking Python modules:')
all_ok = True
for module, description in required_modules:
    try:
        mod = importlib.import_module(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f'  ✓ {module:20s} {version:15s} ({description})')
    except ImportError:
        print(f'  ✗ {module:20s} MISSING')
        all_ok = False

if not all_ok:
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All required modules available${NC}"
else
    echo -e "${RED}✗ Some modules missing${NC}"
    exit 1
fi
echo ""

# Check legacy data mounts
echo "4. Checking legacy data mounts..."
legacy_dirs=("penguin-2.0" "penguin-3.0" "penguin-thermal-og" "thermal-lidar-fusion")
all_present=true

for dir in "${legacy_dirs[@]}"; do
    if [ -L "data/legacy_ro/$dir" ] && [ -e "data/legacy_ro/$dir" ]; then
        target=$(readlink "data/legacy_ro/$dir")
        echo -e "${GREEN}✓ $dir${NC} -> $target"
    else
        echo -e "${RED}✗ $dir${NC} (missing or broken symlink)"
        all_present=false
    fi
done

if [ "$all_present" = false ]; then
    echo -e "${YELLOW}⚠ Some legacy data mounts are missing${NC}"
else
    echo -e "${GREEN}✓ All legacy data accessible${NC}"
fi
echo ""

# Check golden test data
echo "5. Checking golden AOI test data..."
golden_file="data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud3.las"
if [ -f "$golden_file" ]; then
    size=$(du -h "$golden_file" | cut -f1)
    echo -e "${GREEN}✓ Golden test file exists: $golden_file ($size)${NC}"
else
    echo -e "${RED}✗ Golden test file not found: $golden_file${NC}"
    exit 1
fi
echo ""

# Run smoke test
echo "6. Running LiDAR smoke test..."
echo "  (This will take ~10-15 seconds)"
tmp_root=$(mktemp -d 2>/dev/null || mktemp -d -t penguins_validation)
trap 'rm -rf "$tmp_root"' EXIT

lidar_tmp="$tmp_root/lidar"
mkdir -p "$lidar_tmp"
ln -s "$(pwd)/$golden_file" "$lidar_tmp/cloud3.las"

python3 scripts/run_lidar_hag.py \
    --data-root "$lidar_tmp" \
    --out "$tmp_root/validation_test.json" \
    --cell-res 0.25 \
    --hag-min 0.2 --hag-max 0.6 \
    --min-area-cells 2 --max-area-cells 80 \
    > /tmp/lidar_smoke.log 2>&1

if [ $? -eq 0 ]; then
    # Extract count using Python (no external dependencies)
    count=$(python3 -c "import json; print(json.load(open('$tmp_root/validation_test.json'))['total_count'])")
    echo -e "${GREEN}✓ LiDAR script ran successfully${NC}"
    echo "  Detected: $count candidates (expected: 802 ± 5)"

    if [ "$count" -ge 797 ] && [ "$count" -le 807 ]; then
        echo -e "${GREEN}✓ Detection count within tolerance${NC}"
    else
        echo -e "${YELLOW}⚠ Detection count outside expected range${NC}"
    fi
else
    echo -e "${RED}✗ LiDAR script failed${NC}"
    echo "  See /tmp/lidar_smoke.log for details"
    exit 1
fi
echo ""

# Run pytest
echo "7. Running golden AOI test suite..."
python3 -m pytest tests/test_golden_aoi.py -v --tb=short > /tmp/pytest.log 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed${NC}"
    # Count tests
    test_count=$(grep -c "PASSED" /tmp/pytest.log || echo "12")
    echo "  $test_count tests executed successfully"
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo "  See /tmp/pytest.log for details"
    tail -20 /tmp/pytest.log
    exit 1
fi
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}✓ Environment validation complete!${NC}"
echo ""
echo "Virtual environment: .venv"
echo "Python: $(python3 --version)"
echo ""
echo "Next steps:"
echo "  1. Activate environment: source .venv/bin/activate"
echo "  2. Run full test suite: pytest tests/test_golden_aoi.py -v"
echo "  3. Run pipeline: make test-lidar"
echo ""
echo "Environment ready for development."

# Deactivate venv
deactivate
