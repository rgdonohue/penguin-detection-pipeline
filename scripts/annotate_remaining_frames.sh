#!/bin/bash
# Helper script to annotate remaining ground truth frames using INTERACTIVE tool

THERMAL_DIR="data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5"
PDF_PATH="verification_images/Penguin Count - 7 Photos.pdf"

echo "================================================"
echo "Ground Truth Annotation Helper (Interactive)"
echo "================================================"
echo ""
echo "This uses the INTERACTIVE marking tool - just click on penguins!"
echo "The PDF will open alongside for reference."
echo ""
echo "Controls:"
echo "  - LEFT CLICK: Mark penguin location"
echo "  - RIGHT CLICK: Remove last point (undo)"
echo "  - ENTER or CLOSE WINDOW: Save and continue"
echo ""

# Check dependencies
python3 -c "import matplotlib, PIL" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Missing dependencies. Installing matplotlib and Pillow..."
    python3 -m pip install matplotlib Pillow
fi

# Frame 0354 - 23 penguins
echo "Frame 0354 (23 penguins expected)"
echo "---------------------------------"
echo "Starting interactive annotation tool..."
python3 scripts/mark_penguins.py \
  --image "$THERMAL_DIR/DJI_20241106194535_0354_T.JPG" \
  --pdf "$PDF_PATH" \
  --output verification_images/frame_0354_locations.csv

echo ""
read -p "Press Enter to continue to frame 0357..."

# Frame 0357 - 20 penguins
echo "Frame 0357 (20 penguins expected)"
echo "---------------------------------"
echo "Starting interactive annotation tool..."
python3 scripts/mark_penguins.py \
  --image "$THERMAL_DIR/DJI_20241106194546_0357_T.JPG" \
  --pdf "$PDF_PATH" \
  --output verification_images/frame_0357_locations.csv

echo ""
read -p "Press Enter to continue to frame 0358..."

# Frame 0358 - 15 penguins
echo "Frame 0358 (15 penguins expected)"
echo "---------------------------------"
echo "Starting interactive annotation tool..."
python3 scripts/mark_penguins.py \
  --image "$THERMAL_DIR/DJI_20241106194549_0358_T.JPG" \
  --pdf "$PDF_PATH" \
  --output verification_images/frame_0358_locations.csv

echo ""
read -p "Press Enter to continue to frame 0359..."

# Frame 0359 - 13 penguins
echo "Frame 0359 (13 penguins expected)"
echo "---------------------------------"
echo "Starting interactive annotation tool..."
python3 scripts/mark_penguins.py \
  --image "$THERMAL_DIR/DJI_20241106194553_0359_T.JPG" \
  --pdf "$PDF_PATH" \
  --output verification_images/frame_0359_locations.csv

echo ""
echo "================================================"
echo "Annotation Complete!"
echo "================================================"
echo ""
echo "Summary:"
ls -la verification_images/frame_035*_locations.csv
echo ""
echo "Total annotations:"
wc -l verification_images/frame_*_locations.csv | grep -v total | awk '{sum+=$1-1} END {print sum " penguins annotated"}'
echo ""
echo "Next step: Run validation on all frames"
echo "Use: ./scripts/validate_all_frames.sh"