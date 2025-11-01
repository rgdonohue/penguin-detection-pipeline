#!/usr/bin/env python3
"""
Interactive penguin location marker for ground truth validation.

Opens thermal image and lets you click on penguin locations.
Saves coordinates to CSV for thermal extraction validation.

Usage:
    python scripts/mark_penguins.py \
        --image data/legacy_ro/.../DJI_20241106194542_0356_T.JPG \
        --output verification_images/frame_0356_locations.csv

    # Optional: also open PDF for reference
    python scripts/mark_penguins.py \
        --image data/legacy_ro/.../DJI_20241106194542_0356_T.JPG \
        --pdf verification_images/Penguin\ Count\ -\ 7\ Photos.pdf \
        --output verification_images/frame_0356_locations.csv

Instructions:
    1. Click on center of each penguin location
    2. Press ENTER when done (or close window)
    3. Coordinates saved to CSV

    Optional: Right-click to remove last point if you made a mistake
"""

import sys
import argparse
import subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('TkAgg')  # Interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from PIL import Image


class PenguinMarker:
    def __init__(self, image_path: Path, output_path: Path):
        self.image_path = image_path
        self.output_path = output_path
        self.points = []

        # Load image
        self.img = Image.open(image_path)
        self.img_array = np.array(self.img)

        # Setup figure
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        self.fig.canvas.manager.set_window_title(f'Mark Penguins: {image_path.name}')

        # Display image
        self.im = self.ax.imshow(self.img_array)
        self.ax.set_title(
            'Click on penguin centers | Right-click to undo | Press ENTER or close window when done',
            fontsize=12, fontweight='bold'
        )
        self.ax.set_xlabel(f'X (pixels, 0-{self.img.width-1})', fontsize=11)
        self.ax.set_ylabel(f'Y (pixels, 0-{self.img.height-1})', fontsize=11)

        # Add coordinate display in top-right
        self.coord_text = self.ax.text(
            0.98, 0.02, '', transform=self.ax.transAxes,
            fontsize=10, verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8)
        )

        # Add count display in top-left
        self.count_text = self.ax.text(
            0.02, 0.98, 'Penguins marked: 0', transform=self.ax.transAxes,
            fontsize=12, verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9),
            fontweight='bold'
        )

        # Store circle patches for each point
        self.circles = []

        # Connect event handlers
        self.cid_click = self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.cid_key = self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.cid_motion = self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.cid_close = self.fig.canvas.mpl_connect('close_event', self.on_close)

    def on_motion(self, event):
        """Update coordinate display as mouse moves."""
        if event.inaxes == self.ax:
            x, y = int(event.xdata), int(event.ydata)
            self.coord_text.set_text(f'Cursor: ({x}, {y})')
            self.fig.canvas.draw_idle()

    def on_click(self, event):
        """Handle mouse clicks."""
        if event.inaxes != self.ax:
            return

        x, y = int(event.xdata), int(event.ydata)

        if event.button == 1:  # Left click - add point
            self.points.append((x, y))

            # Draw circle at clicked location
            circle = Circle((x, y), radius=5, color='cyan', fill=False, linewidth=2)
            self.ax.add_patch(circle)

            # Draw center crosshair
            self.ax.plot(x, y, 'c+', markersize=10, markeredgewidth=2)

            self.circles.append(circle)

            print(f"✓ Marked penguin {len(self.points)}: ({x}, {y})")

        elif event.button == 3:  # Right click - remove last point
            if self.points:
                removed = self.points.pop()

                # Remove last circle
                if self.circles:
                    self.circles[-1].remove()
                    self.circles.pop()

                # Remove last crosshair (harder - just redraw everything)
                self.redraw_all_points()

                print(f"✗ Removed last point: {removed} (now {len(self.points)} penguins)")

        # Update count
        self.count_text.set_text(f'Penguins marked: {len(self.points)}')
        self.fig.canvas.draw()

    def redraw_all_points(self):
        """Redraw all points (used after undo)."""
        # Clear all circles
        for circle in self.circles:
            circle.remove()
        self.circles.clear()

        # Clear plot lines (crosshairs)
        for line in self.ax.lines[:]:
            line.remove()

        # Redraw all points
        for x, y in self.points:
            circle = Circle((x, y), radius=5, color='cyan', fill=False, linewidth=2)
            self.ax.add_patch(circle)
            self.ax.plot(x, y, 'c+', markersize=10, markeredgewidth=2)
            self.circles.append(circle)

    def on_key(self, event):
        """Handle keyboard events."""
        if event.key == 'enter':
            print("\n✅ ENTER pressed - saving and closing...")
            self.save_and_close()
        elif event.key == 'escape':
            print("\n❌ ESC pressed - closing without saving...")
            plt.close(self.fig)

    def on_close(self, event):
        """Handle window close event."""
        if self.points:
            print("\n💾 Window closed - saving points...")
            self.save_points()

    def save_and_close(self):
        """Save points and close window."""
        self.save_points()
        plt.close(self.fig)

    def save_points(self):
        """Save marked points to CSV."""
        if not self.points:
            print("⚠️  No points marked - nothing to save")
            return

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.output_path, 'w') as f:
            f.write('x,y,label\n')
            for x, y in self.points:
                f.write(f'{x},{y},penguin\n')

        print(f"\n✅ Saved {len(self.points)} penguin locations to:")
        print(f"   {self.output_path}")
        print(f"\nNext steps:")
        print(f"  1. Run validation script:")
        print(f"     python scripts/validate_thermal_extraction.py \\")
        print(f"         --thermal-image {self.image_path} \\")
        print(f"         --ground-truth {self.output_path} \\")
        print(f"         --output data/interim/thermal_validation/")

    def run(self):
        """Show interactive window and start event loop."""
        plt.tight_layout()
        plt.show()


def open_pdf_reference(pdf_path: Path):
    """Open PDF in separate window for reference (non-blocking)."""
    try:
        # macOS
        subprocess.Popen(['open', str(pdf_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        return True
    except:
        try:
            # Linux
            subprocess.Popen(['xdg-open', str(pdf_path)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            return True
        except:
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Interactive penguin location marker for ground truth validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Mark penguins on frame 0356
  python scripts/mark_penguins.py \\
      --image data/legacy_ro/penguin-2.0/.../DJI_20241106194542_0356_T.JPG \\
      --output verification_images/frame_0356_locations.csv

  # Also open PDF for reference
  python scripts/mark_penguins.py \\
      --image data/legacy_ro/.../DJI_20241106194542_0356_T.JPG \\
      --pdf verification_images/Penguin\\ Count\\ -\\ 7\\ Photos.pdf \\
      --output verification_images/frame_0356_locations.csv

Instructions:
  - LEFT CLICK on each penguin center
  - RIGHT CLICK to remove last point (undo)
  - ENTER to save and close
  - ESC to close without saving
  - Just close window to save automatically
        """
    )
    parser.add_argument(
        '--image',
        type=Path,
        required=True,
        help='Path to thermal JPEG image'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Path to save CSV with penguin locations'
    )
    parser.add_argument(
        '--pdf',
        type=Path,
        help='Optional: PDF with ground truth annotations (will open for reference)'
    )

    args = parser.parse_args()

    if not args.image.exists():
        print(f"❌ Error: Image not found: {args.image}")
        return 1

    print("=" * 70)
    print("Interactive Penguin Location Marker")
    print("=" * 70)
    print()
    print(f"📷 Image: {args.image.name}")
    print(f"💾 Output: {args.output}")

    if args.pdf and args.pdf.exists():
        print(f"📄 Reference PDF: {args.pdf.name}")
        print()
        print("Opening PDF for reference...")
        if open_pdf_reference(args.pdf):
            print("✅ PDF opened in separate window")
        else:
            print("⚠️  Could not auto-open PDF - please open manually")

    print()
    print("Instructions:")
    print("  • LEFT CLICK on each penguin center")
    print("  • RIGHT CLICK to undo last point")
    print("  • ENTER to save and close")
    print("  • ESC to close without saving")
    print("  • Or just close the window to save")
    print()
    print("Starting interactive marker...")
    print("=" * 70)
    print()

    marker = PenguinMarker(args.image, args.output)
    marker.run()

    return 0


if __name__ == '__main__':
    sys.exit(main())
