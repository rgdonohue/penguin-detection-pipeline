#!/bin/bash
# Validate all 7 ground truth frames

THERMAL_DIR="data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5"
OUTPUT_DIR="data/interim/thermal_validation"

echo "================================================"
echo "Validating All Ground Truth Frames"
echo "================================================"
echo ""

mkdir -p "$OUTPUT_DIR"

# Array of frame numbers and their corresponding thermal image timestamps
declare -a frames=("0353:20241106194532" "0354:20241106194535" "0355:20241106194539"
                   "0356:20241106194542" "0357:20241106194546" "0358:20241106194549"
                   "0359:20241106194553")

total_validated=0
failed_frames=""

for frame_info in "${frames[@]}"; do
    IFS=':' read -r frame_id timestamp <<< "$frame_info"

    echo "Validating frame $frame_id..."
    echo "---------------------------------"

    csv_file="verification_images/frame_${frame_id}_locations.csv"
    thermal_image="${THERMAL_DIR}/DJI_${timestamp}_${frame_id}_T.JPG"

    if [ ! -f "$csv_file" ]; then
        echo "⚠️  Missing CSV: $csv_file"
        failed_frames="$failed_frames $frame_id"
        echo ""
        continue
    fi

    if [ ! -f "$thermal_image" ]; then
        echo "⚠️  Missing thermal image: $thermal_image"
        failed_frames="$failed_frames $frame_id"
        echo ""
        continue
    fi

    # Run validation
    python scripts/validate_thermal_extraction.py \
        --thermal-image "$thermal_image" \
        --ground-truth "$csv_file" \
        --output "$OUTPUT_DIR/"

    if [ $? -eq 0 ]; then
        echo "✅ Frame $frame_id validated successfully"
        ((total_validated++))
    else
        echo "❌ Frame $frame_id validation failed"
        failed_frames="$failed_frames $frame_id"
    fi
    echo ""
done

echo "================================================"
echo "Validation Summary"
echo "================================================"
echo "Validated: $total_validated / 7 frames"

if [ -n "$failed_frames" ]; then
    echo "Failed frames:$failed_frames"
else
    echo "✅ All frames validated successfully!"
fi

echo ""
echo "Output files in: $OUTPUT_DIR/"
ls -la "$OUTPUT_DIR"/*.txt 2>/dev/null | tail -7

echo ""
echo "Next step: Run parameter optimization"
echo "python scripts/optimize_thermal_detection.py \\"
echo "  --ground-truth-dir verification_images/ \\"
echo "  --thermal-dir $THERMAL_DIR/ \\"
echo "  --output data/interim/optimization_results.json \\"
echo "  --csv-output data/interim/optimization_summary.csv \\"
echo "  --verbose"