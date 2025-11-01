#!/bin/bash
# Complete thermal detection pipeline workflow

echo "================================================"
echo "Penguin Thermal Detection Pipeline"
echo "Target: ~1533 penguins"
echo "================================================"
echo ""

# Step 1: Check ground truth status
echo "Step 1: Checking ground truth status..."
echo "---------------------------------"
missing_frames=""
for frame in 0354 0357 0358 0359; do
    if [ ! -f "verification_images/frame_${frame}_locations.csv" ]; then
        missing_frames="$missing_frames $frame"
    fi
done

if [ -n "$missing_frames" ]; then
    echo "⚠️  Missing ground truth for frames:$missing_frames"
    echo "Run: ./scripts/annotate_remaining_frames.sh"
    exit 1
else
    echo "✅ All ground truth files present"
fi
echo ""

# Step 2: Validate all frames
echo "Step 2: Validating thermal extraction..."
echo "---------------------------------"
read -p "Run validation? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./scripts/validate_all_frames.sh
fi
echo ""

# Step 3: Run parameter optimization
echo "Step 3: Parameter optimization..."
echo "---------------------------------"
read -p "Run optimization? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python scripts/optimize_thermal_detection.py \
        --ground-truth-dir verification_images/ \
        --thermal-dir data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/ \
        --output data/interim/optimization_results.json \
        --csv-output data/interim/optimization_summary.csv \
        --verbose

    echo ""
    echo "Optimization results:"
    if [ -f "data/interim/optimization_summary.csv" ]; then
        cat data/interim/optimization_summary.csv | column -t -s,
    fi
fi
echo ""

# Step 4: Test batch on subset
echo "Step 4: Test batch processing on subset..."
echo "---------------------------------"
read -p "Run test batch (100 frames)? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python scripts/run_thermal_detection_batch.py \
        --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
        --params data/interim/optimal_thermal_params.json \
        --output data/processed/thermal_test/ \
        --limit 100 \
        --verbose

    if [ -f "data/processed/thermal_test/detection_summary.json" ]; then
        echo ""
        echo "Test batch results:"
        python -c "import json; d=json.load(open('data/processed/thermal_test/detection_summary.json')); print(f'  Total detections: {d[\"total_detections\"]}'); print(f'  Average per frame: {d[\"average_per_frame\"]:.1f}')"
    fi
fi
echo ""

# Step 5: Full batch processing
echo "Step 5: Full batch processing (~1533 frames)..."
echo "---------------------------------"
echo "⚠️  This will take 2-4 hours"
read -p "Run FULL batch? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Determine parallel workers
    CORES=$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)
    WORKERS=$((CORES / 2))  # Use half the cores
    echo "Using $WORKERS parallel workers..."

    python scripts/run_thermal_detection_batch.py \
        --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
        --params data/interim/optimal_thermal_params.json \
        --output data/processed/thermal_detections/ \
        --parallel $WORKERS \
        --checkpoint-every 100 \
        --verbose

    # Show final results
    if [ -f "data/processed/thermal_detections/detection_summary.json" ]; then
        echo ""
        echo "================================================"
        echo "FINAL RESULTS"
        echo "================================================"
        python -c "
import json
d = json.load(open('data/processed/thermal_detections/detection_summary.json'))
target = 1533
diff = d['total_detections'] - target
pct = (diff / target) * 100
print(f'Total detections: {d[\"total_detections\"]}')
print(f'Target: {target}')
print(f'Difference: {diff:+d} ({pct:+.1f}%)')
print(f'Average per frame: {d[\"average_per_frame\"]:.1f}')
print(f'Processing time: {d[\"processing_time_seconds\"]/60:.1f} minutes')
if abs(pct) <= 20:
    print('✅ Within 20% of target!')
else:
    print(f'⚠️  {abs(pct):.1f}% off target')
"
    fi
fi

echo ""
echo "================================================"
echo "Pipeline Complete!"
echo "================================================"
echo ""
echo "Generated outputs:"
echo "  - data/interim/optimization_results.json (parameter sweep)"
echo "  - data/interim/optimal_thermal_params.json (best parameters)"
echo "  - data/processed/thermal_detections/all_detections.csv (all detections)"
echo "  - data/processed/thermal_detections/frame_counts.csv (per-frame counts)"
echo "  - data/processed/thermal_detections/detection_summary.json (statistics)"
echo ""
echo "Next steps:"
echo "  1. Generate visualization graphics"
echo "  2. Run LiDAR detection for comparison"
echo "  3. Perform fusion analysis"
echo "  4. Create client report"