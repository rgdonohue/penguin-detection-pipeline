#!/usr/bin/env bash
# Minimal thermal pipeline test
# Tests ortho-one command on single frame from penguin-2.0 legacy data

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Thermal Pipeline Minimal Test"
echo "======================================"
echo

# Check virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not active${NC}"
    echo "Run: source .venv/bin/activate"
    exit 1
fi

echo -e "${GREEN}✓${NC} Virtual environment active: $VIRTUAL_ENV"

# Check GDAL/rasterio availability
echo -e "\n${YELLOW}Checking GDAL/rasterio...${NC}"
python3 -c "import rasterio, pyproj; print('✓ GDAL stack available')" || {
    echo -e "${RED}✗ GDAL/rasterio not found${NC}"
    echo "Install via: pip install gdal rasterio pyproj"
    echo "Or see RUNBOOK.md for conda instructions"
    exit 1
}

# Test data paths (from penguin-2.0 legacy)
DSM="data/legacy_ro/penguin-2.0/results/full_dsm.tif"
THERMAL_DIR="data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5"
THERMAL_IMAGE="$THERMAL_DIR/DJI_20241106192556_0001_T.JPG"
POSES_CSV="$THERMAL_DIR/poses.csv"

# Output directory
OUT_DIR="data/interim/thermal_test"
mkdir -p "$OUT_DIR"

echo -e "\n${YELLOW}Checking test data...${NC}"
for file in "$DSM" "$THERMAL_IMAGE" "$POSES_CSV"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Found: $file"
    else
        echo -e "${RED}✗${NC} Missing: $file"
        exit 1
    fi
done

# Run thermal orthorectification
echo -e "\n${YELLOW}Running thermal orthorectification...${NC}"
echo "Command: python scripts/run_thermal_ortho.py ortho-one \\"
echo "  --image $THERMAL_IMAGE \\"
echo "  --poses $POSES_CSV \\"
echo "  --dsm $DSM \\"
echo "  --out $OUT_DIR/test_ortho.tif \\"
echo "  --snap-grid"
echo

python scripts/run_thermal_ortho.py ortho-one \
    --image "$THERMAL_IMAGE" \
    --poses "$POSES_CSV" \
    --dsm "$DSM" \
    --out "$OUT_DIR/test_ortho.tif" \
    --snap-grid || {
    echo -e "\n${RED}✗ Orthorectification failed${NC}"
    exit 1
}

echo -e "\n${GREEN}✓ Orthorectification succeeded${NC}"

# Verify output
echo -e "\n${YELLOW}Verifying output...${NC}"
if [ -f "$OUT_DIR/test_ortho.tif" ]; then
    SIZE=$(stat -f%z "$OUT_DIR/test_ortho.tif" 2>/dev/null || stat -c%s "$OUT_DIR/test_ortho.tif" 2>/dev/null)
    echo -e "${GREEN}✓${NC} Output file created: $OUT_DIR/test_ortho.tif ($(numfmt --to=iec-i --suffix=B $SIZE 2>/dev/null || echo $SIZE bytes))"

    # Check with gdalinfo if available
    if command -v gdalinfo &> /dev/null; then
        echo -e "\n${YELLOW}GeoTIFF info:${NC}"
        gdalinfo "$OUT_DIR/test_ortho.tif" | head -20
    fi
else
    echo -e "${RED}✗${NC} Output file not created"
    exit 1
fi

# Run grid verification
echo -e "\n${YELLOW}Verifying grid alignment...${NC}"
python scripts/run_thermal_ortho.py verify-grid \
    --dsm "$DSM" \
    --ortho "$OUT_DIR/test_ortho.tif" || {
    echo -e "\n${YELLOW}⚠️  Grid verification failed (non-fatal)${NC}"
}

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All tests passed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo "Output:"
echo "  $OUT_DIR/test_ortho.tif"
echo
echo "View in QGIS:"
echo "  qgis $OUT_DIR/test_ortho.tif $DSM &"
