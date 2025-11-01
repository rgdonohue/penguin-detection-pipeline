#!/usr/bin/env python3
"""
CLI penguin location marker for ground truth validation.

Simple text-based version - you provide coordinates from your image viewer.

Usage:
    python scripts/mark_penguins_cli.py \
        --output verification_images/frame_0356_locations.csv

Instructions:
    1. Open thermal image in Preview/GIMP/any viewer that shows coordinates
    2. For each penguin, note the x,y pixel coordinates
    3. Enter them when prompted (format: x,y)
    4. Press ENTER with no input when done
"""

import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="CLI penguin location marker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Instructions:
  1. Open the thermal image in an image viewer that shows pixel coordinates:
     - Preview (Tools → Show Inspector → General tab)
     - GIMP (Window → Dockable Dialogs → Pointer)
     - Any other image editor

  2. For each penguin in the PDF ground truth:
     - Note its x,y pixel coordinates in the thermal image
     - Enter them when prompted (format: x,y or x y)

  3. Press ENTER with no input when done

Example session:
  Penguin 1 - Enter x,y (or just ENTER to finish): 320,256
  ✓ Added: (320, 256)
  Penguin 2 - Enter x,y (or just ENTER to finish): 340 245
  ✓ Added: (340, 245)
  ...
  Penguin 28 - Enter x,y (or just ENTER to finish): [ENTER]
  ✅ Saved 27 penguin locations
        """
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Path to save CSV with penguin locations'
    )
    parser.add_argument(
        '--expected',
        type=int,
        help='Expected number of penguins (optional, for validation)'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=640,
        help='Image width in pixels (default: 640 for H20T)'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=512,
        help='Image height in pixels (default: 512 for H20T)'
    )
    parser.add_argument(
        '--image',
        type=Path,
        help='Optional: thermal image path to auto-detect dimensions'
    )
    parser.add_argument(
        '--append',
        action='store_true',
        help='Append to existing CSV instead of overwriting'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing CSV without confirmation'
    )

    args = parser.parse_args()

    # Auto-detect image dimensions if image provided
    width, height = args.width, args.height
    if args.image and args.image.exists():
        try:
            from PIL import Image
            with Image.open(args.image) as img:
                width, height = img.size
                print(f"ℹ️  Auto-detected image dimensions: {width}×{height}")
        except ImportError:
            print("⚠️  PIL not available, using manual dimensions")
        except Exception as e:
            print(f"⚠️  Could not read image dimensions: {e}")

    # Check if output file exists and handle accordingly
    if args.output.exists() and not args.append and not args.force:
        print(f"⚠️  Output file already exists: {args.output}")
        response = input("Overwrite? (y/n) or 'a' to append: ").strip().lower()
        if response == 'n':
            print("Aborted.")
            return 1
        elif response == 'a':
            args.append = True
            print("Will append to existing file.")
        elif response != 'y':
            print("Invalid response. Aborted.")
            return 1

    print("=" * 70)
    print("CLI Penguin Location Marker")
    print("=" * 70)
    print()
    print(f"💾 Output: {args.output}")
    if args.expected:
        print(f"🐧 Expected penguins: {args.expected}")
    print(f"📐 Image dimensions: {width}×{height}")
    print()
    print("Instructions:")
    print("  1. Open thermal image in viewer with coordinate display")
    print("  2. Enter penguin coordinates when prompted")
    print("  3. Format: 'x,y' or 'x y' (e.g., '320,256' or '320 256')")
    print("  4. Press ENTER with no input to finish")
    print()
    print("Tip: To open thermal image in Preview with coordinates:")
    print("  open data/legacy_ro/.../DJI_20241106194542_0356_T.JPG")
    print("  Then: Tools → Show Inspector → General tab (shows cursor position)")
    print()
    print("=" * 70)
    print()

    # Load existing locations if appending
    locations = []
    if args.append and args.output.exists():
        import csv
        with open(args.output, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                locations.append((int(row['x']), int(row['y'])))
        print(f"ℹ️  Loaded {len(locations)} existing locations from {args.output}")
        print()

    penguin_num = len(locations) + 1

    while True:
        if args.expected and penguin_num <= args.expected:
            prompt = f"Penguin {penguin_num} - Enter x,y (or just ENTER to finish): "
        elif args.expected and penguin_num > args.expected:
            prompt = f"Extra penguin {penguin_num} - Enter x,y (or just ENTER to finish): "
        else:
            prompt = f"Penguin {penguin_num} - Enter x,y (or just ENTER to finish): "

        user_input = input(prompt).strip()

        if not user_input:
            # Empty input - done
            break

        # Parse input (support both "x,y" and "x y" formats)
        try:
            if ',' in user_input:
                parts = user_input.split(',')
            else:
                parts = user_input.split()

            if len(parts) != 2:
                print(f"  ⚠️  Invalid format. Use 'x,y' or 'x y'. Try again.")
                continue

            x = int(parts[0].strip())
            y = int(parts[1].strip())

            # Basic validation with actual dimensions
            if not (0 <= x < width and 0 <= y < height):
                print(f"  ⚠️  Coordinates out of range (image is {width}×{height}). Try again.")
                continue

            locations.append((x, y))
            print(f"  ✓ Added: ({x}, {y}) - Total: {len(locations)}")
            penguin_num += 1

        except ValueError:
            print(f"  ⚠️  Could not parse coordinates. Use integers only. Try again.")
            continue

    print()
    print("=" * 70)

    if not locations:
        print("❌ No locations entered - nothing to save")
        return 1

    # Save to CSV
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, 'w') as f:
        f.write('x,y,label\n')
        for x, y in locations:
            f.write(f'{x},{y},penguin\n')

    print(f"✅ Saved {len(locations)} penguin locations to:")
    print(f"   {args.output}")
    print()

    if args.expected:
        if len(locations) < args.expected:
            print(f"⚠️  Warning: Expected {args.expected} penguins, got {len(locations)}")
            print(f"   You can run this script again with --append to add more")
        elif len(locations) > args.expected:
            print(f"ℹ️  Note: Got {len(locations)} locations (expected {args.expected})")

    print()
    print("Next step - Run validation:")
    print("  python scripts/validate_thermal_extraction.py \\")
    print("      --thermal-image data/legacy_ro/.../DJI_20241106194542_0356_T.JPG \\")
    print(f"      --ground-truth {args.output} \\")
    print("      --output data/interim/thermal_validation/")
    print()
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
