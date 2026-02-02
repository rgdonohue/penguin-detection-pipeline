# LiDAR Detection Labeling Protocol

## Purpose

Classify LiDAR detection candidates as true penguins or false positives to estimate pipeline precision. Labels feed into `scripts/estimate_precision.py` for site-level precision and adjusted count estimates.

## What You're Looking At

Each candidate is a blob detected in the LiDAR height-above-ground (HAG) grid. The pipeline accepted it because it fell within a height and size range — but those filters also accept rocks, vegetation, burrow rims, and other objects of similar size. Your job is to classify what each detection actually is, using visual evidence.

Each crop image shows two panels:
- **RGB** (left): Natural color rendered from the LiDAR point cloud. Use this as your primary visual evidence — color, texture, and shape are the most informative cues.
- **HAG** (right): Height above ground in greyscale (brighter = taller). Shows the 3D shape of the detection.

The cyan **×** marks the detection centroid in both panels.

## Label Categories

| Label | Code | What to look for |
|-------|------|------------------|
| True Positive | `TP` | Rounded, penguin-shaped blob in RGB. Typically dark (black/brown) body with lighter edges. Smooth, compact HAG profile ~0.2–0.5 m tall. |
| False Positive — Rock | `FP_rock` | Grey/brown, angular or irregular shape in RGB. HAG may be in range but profile is jagged, asymmetric, or hard-edged. No biological appearance. |
| False Positive — Vegetation | `FP_vegetation` | Green tones in RGB, or elongated/diffuse shape. May show linear patterns (grass clumps, bush edges). HAG often more variable than a penguin. |
| False Positive — Empty Burrow | `FP_burrow` | Ring or raised-rim pattern visible in HAG with low center. RGB may show a dark hole or shadow. No penguin body visible. |
| Uncertain | `uncertain` | Cannot confidently classify. Partial view, overlapping features, edge artifact, or genuinely ambiguous. |

## Labeling Procedure

1. Open the label sample CSV (`label_sample.csv`) in a spreadsheet editor.
2. For each row, examine:
   - The crop image in the `crops/` directory (RGB + HAG side-by-side)
   - Use **RGB appearance** as primary evidence: color and shape are the strongest discriminators
   - Use HAG as supporting evidence for height and 3D profile
   - Check the numeric features (`area_m2`, `hag_mean`, `intensity_mean`, `rgb_r/g/b_mean`) if the image is ambiguous
3. Assign a label from the table above in the `label` column.
4. Add brief notes in the `notes` column for borderline cases (e.g., "possible pair merged", "edge of crop", "shadow only").
5. Save the CSV. Do not reorder rows or modify columns other than `label` and `notes`.

## Guidance

- **Lead with the RGB image.** If it looks like a penguin (dark rounded body, correct scale), it probably is. If it looks like a rock or bush, it probably is.
- **Don't rely on numeric thresholds.** The pipeline already applied height and size filters. Repeating those thresholds here doesn't add information. Your value as a labeler is visual pattern recognition that the pipeline can't do.
- **Merged detections** (two penguins close together producing one blob) should be labeled `TP` with a note "merged pair" or similar. The blob still represents real penguins.
- **When genuinely uncertain, say so.** The precision estimator excludes `uncertain` labels. Marking something uncertain is better than guessing.

## Output Format

The labeled CSV must contain at minimum:
- `id`: Detection ID (do not modify)
- `label`: One of `TP`, `FP_rock`, `FP_vegetation`, `FP_burrow`, `uncertain`
- `notes`: Optional free-text

## Quality Assurance

- Each site sample should be labeled by at least one reviewer.
- `uncertain` labels are excluded from precision calculation (conservative).
- If a second reviewer labels a subset, inter-rater agreement on TP vs FP should exceed 80% for the sample to be considered reliable.
