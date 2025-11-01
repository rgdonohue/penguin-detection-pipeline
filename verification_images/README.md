# Ground Truth Verification Data

This directory contains manually-verified penguin locations for validating thermal extraction.

## Source

`Penguin Count - 7 Photos.pdf` - Contains 7 thermal frames with manually-marked penguin locations (blue circles).

**Frames:**
- Frame 0353: 15 penguins (DJI_20241106194532_0353_T.JPG)
- Frame 0354: 23 penguins (DJI_20241106194535_0354_T.JPG)
- Frame 0355: 23 penguins (DJI_20241106194539_0355_T.JPG)
- **Frame 0356: 28 penguins** (DJI_20241106194542_0356_T.JPG) ⭐ **Highest density**
- Frame 0357: 20 penguins (DJI_20241106194546_0357_T.JPG)
- Frame 0358: 15 penguins (DJI_20241106194549_0358_T.JPG)
- Frame 0359: 13 penguins (DJI_20241106194553_0359_T.JPG)

**Total:** 137 verified penguins across 21 seconds of flight

## Ground Truth CSV Format

To validate thermal extraction, create CSV files with penguin pixel coordinates:

```csv
x,y,label
320,256,penguin
340,245,penguin
...
```

Where:
- `x`: Horizontal pixel coordinate (0-639)
- `y`: Vertical pixel coordinate (0-511)
- `label`: Object type (typically "penguin")

## Extraction Methods

### Method 1: Manual Annotation (Most Accurate)

Open the thermal image in an image viewer and manually record coordinates:

```bash
# Open thermal image
open data/legacy_ro/penguin-2.0/.../DJI_20241106194542_0356_T.JPG

# Or use GIMP/Photoshop to get pixel coordinates of each blue circle center
```

### Method 2: Semi-Automated (If PDF Coordinates Available)

If PDF contains vector data with circle locations:

```python
# Extract from PDF (requires PyPDF2 or similar)
import PyPDF2
# ... extract circle coordinates ...
# ... map to thermal image pixel space ...
```

### Method 3: Interactive Marker

Use `scripts/mark_ground_truth.py` (if created) to click on penguins interactively.

## Validation Usage

Once ground truth CSV is created:

```bash
python scripts/validate_thermal_extraction.py \
    --thermal-image data/legacy_ro/penguin-2.0/.../DJI_20241106194542_0356_T.JPG \
    --ground-truth verification_images/frame_0356_locations.csv \
    --output data/interim/thermal_validation/
```

This will:
1. Extract 16-bit thermal data from DJI EXIF
2. Overlay ground truth locations
3. Measure temperature at each penguin location
4. Calculate thermal contrast (penguin vs background)
5. Generate validation visualization

## Expected Results

**If extraction is correct:**
- Penguins should be WARMER than background (positive contrast)
- Typical penguin surface temperature: 25-30°C
- Background (ground/ice): 5-15°C
- Contrast: ~10-20°C

**Current results (prototype):**
- Image range: -13.77°C to 12.16°C
- Mean: -5.69°C
- Suggests ~15-20°C calibration offset needed

## TODO

- [ ] Extract penguin locations from PDF frame 0356 (28 locations)
- [ ] Create frame_0356_locations.csv
- [ ] Run validation script
- [ ] Measure thermal contrast
- [ ] Determine if calibration refinement is needed
- [ ] Repeat for frames 0353-0359 (137 total penguins)
