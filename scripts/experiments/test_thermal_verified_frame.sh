#!/usr/bin/env bash
# Thermal Pipeline Validation - Verified Frame 0356
# Tests orthorectification on frame with 28 manually-verified penguins

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================================"
echo "Thermal Pipeline Validation - Ground Truth Frame"
echo "======================================================"
echo
echo -e "${BLUE}Frame: DJI_20241106194542_0356_T.JPG${NC}"
echo -e "${BLUE}Expected: 28 verified penguins${NC}"
echo -e "${BLUE}Timestamp: 19:45:42 (Nov 6, 2024)${NC}"
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

# Test data paths
DSM="data/legacy_ro/penguin-2.0/results/full_dsm.tif"
THERMAL_DIR="data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5"
THERMAL_IMAGE="$THERMAL_DIR/DJI_20241106194542_0356_T.JPG"
POSES_CSV="$THERMAL_DIR/poses.csv"

# Output directory
OUT_DIR="data/interim/thermal_validation"
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

# Get image dimensions for reference
echo -e "\n${YELLOW}Image information:${NC}"
if command -v exiftool &> /dev/null; then
    exiftool -ImageWidth -ImageHeight -XMP:GPSLatitude -XMP:GPSLongitude \
        "$THERMAL_IMAGE" | grep -E "(Width|Height|GPS)"
fi

# Run thermal orthorectification
echo -e "\n${YELLOW}Running thermal orthorectification...${NC}"
echo "Command: python scripts/run_thermal_ortho.py ortho-one \\"
echo "  --image $THERMAL_IMAGE \\"
echo "  --poses $POSES_CSV \\"
echo "  --dsm $DSM \\"
echo "  --out $OUT_DIR/frame_0356_ortho.tif \\"
echo "  --snap-grid"
echo

python scripts/run_thermal_ortho.py ortho-one \
    --image "$THERMAL_IMAGE" \
    --poses "$POSES_CSV" \
    --dsm "$DSM" \
    --out "$OUT_DIR/frame_0356_ortho.tif" \
    --snap-grid || {
    echo -e "\n${RED}✗ Orthorectification failed${NC}"
    exit 1
}

echo -e "\n${GREEN}✓ Orthorectification succeeded${NC}"

# Verify output
echo -e "\n${YELLOW}Verifying output...${NC}"
if [ -f "$OUT_DIR/frame_0356_ortho.tif" ]; then
    SIZE=$(stat -f%z "$OUT_DIR/frame_0356_ortho.tif" 2>/dev/null || stat -c%s "$OUT_DIR/frame_0356_ortho.tif" 2>/dev/null)
    echo -e "${GREEN}✓${NC} Output file created: $OUT_DIR/frame_0356_ortho.tif"
    echo "   Size: $(numfmt --to=iec-i --suffix=B $SIZE 2>/dev/null || echo $SIZE bytes)"

    # Check with gdalinfo if available
    if command -v gdalinfo &> /dev/null; then
        echo -e "\n${YELLOW}GeoTIFF info:${NC}"
        gdalinfo "$OUT_DIR/frame_0356_ortho.tif" | head -25

        echo -e "\n${YELLOW}Statistics (min/max/mean):${NC}"
        gdalinfo -stats "$OUT_DIR/frame_0356_ortho.tif" | grep -A 5 "Band 1"
    fi
else
    echo -e "${RED}✗${NC} Output file not created"
    exit 1
fi

# Run grid verification
echo -e "\n${YELLOW}Verifying grid alignment...${NC}"
python scripts/run_thermal_ortho.py verify-grid \
    --dsm "$DSM" \
    --ortho "$OUT_DIR/frame_0356_ortho.tif" || {
    echo -e "\n${YELLOW}⚠️  Grid verification failed (non-fatal)${NC}"
}

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Validation test complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "${BLUE}Expected Result:${NC}"
echo "  - 28 verified penguins should be visible as bright/warm spots"
echo "  - Image should cover the verified ground truth area"
echo "  - Thermal signatures should be preserved"
echo
echo "Output:"
echo "  $OUT_DIR/frame_0356_ortho.tif"
echo
echo "View in QGIS:"
echo "  qgis $OUT_DIR/frame_0356_ortho.tif $DSM &"
echo
echo "Compare with ground truth PDF:"
echo "  open verification_images/'Penguin Count - 7 Photos.pdf' &"
