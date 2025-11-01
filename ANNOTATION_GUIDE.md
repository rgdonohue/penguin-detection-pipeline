# Ground Truth Annotation Guide

## ⚠️ **USE THE INTERACTIVE TOOL** - Not the CLI!

The **interactive marking tool** (`mark_penguins.py`) is MUCH faster and more accurate than manual transcription:
- **Click directly on penguins** in the thermal image
- **Right-click to undo** mistakes
- **PDF opens alongside** for reference
- **No manual coordinate entry** needed

## Quick Start

```bash
# Install dependencies if needed
pip install matplotlib Pillow

# Run the annotation helper (uses interactive tool)
./scripts/annotate_remaining_frames.sh
```

This will:
1. Open each thermal image with the interactive marker
2. Open the PDF reference alongside
3. Let you click on each penguin location
4. Save to CSV automatically

## Interactive Tool Controls

- **LEFT CLICK**: Mark penguin location
- **RIGHT CLICK**: Remove last point (undo)
- **ENTER or CLOSE**: Save and continue to next frame

## Manual Interactive Tool Usage

If you need to annotate a specific frame:

```bash
python scripts/mark_penguins.py \
  --image data/legacy_ro/.../DJI_20241106194535_0354_T.JPG \
  --pdf "verification_images/Penguin Count - 7 Photos.pdf" \
  --output verification_images/frame_0354_locations.csv
```

## Why NOT the CLI Tool?

The CLI tool (`mark_penguins_cli.py`) requires:
- Manual transcription of coordinates from another viewer
- Typing "x,y" for 70+ penguins
- Risk of typos and errors
- Much slower workflow

## Expected Counts

- Frame 0354: 23 penguins
- Frame 0357: 20 penguins
- Frame 0358: 15 penguins
- Frame 0359: 13 penguins

Total: 71 penguins to annotate

## After Annotation

Run validation:
```bash
./scripts/validate_all_frames.sh
```

Then proceed with optimization and batch processing.