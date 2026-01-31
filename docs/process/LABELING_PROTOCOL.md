# LiDAR Detection Labeling Protocol

## Purpose

Classify LiDAR detection candidates as true penguins or false positives to estimate pipeline precision. Labels feed into `scripts/estimate_precision.py` for site-level precision and adjusted count estimates.

## Label Categories

| Label | Code | Criteria |
|-------|------|----------|
| True Positive | `TP` | HAG pattern consistent with penguin body shape; rounded blob, HAG ~0.2-0.5m, area consistent with single or adjacent penguins |
| False Positive — Rock | `FP_rock` | Angular or irregular shape; HAG may be in range but pattern is jagged or asymmetric; no biological appearance |
| False Positive — Vegetation | `FP_vegetation` | Elongated or diffuse shape; may show linear patterns; HAG may be higher or more variable than penguin |
| False Positive — Empty Burrow | `FP_burrow_empty` | Annular/ring pattern in HAG suggesting burrow entrance without visible penguin; surrounding context shows burrow structures |
| Uncertain | `uncertain` | Ambiguous pattern that cannot be confidently classified; may be partial penguin, overlapping features, or edge artifact |

## Labeling Procedure

1. Open the label sample CSV (`label_sample.csv`) in a spreadsheet editor.
2. For each row, examine:
   - The HAG crop image (if available in the `crops/` directory)
   - The `hag_mean`, `hag_max`, `area_m2`, `circularity`, `solidity` features
   - The detection's position relative to neighboring detections
3. Assign a label from the table above in the `label` column.
4. Add brief notes in the `notes` column if the classification is borderline.
5. Save the CSV.

## Decision Rules

- **HAG 0.25-0.45m + circularity > 0.4 + solidity > 0.8 + compact shape**: likely `TP`
- **HAG in range but shape is jagged/angular**: likely `FP_rock`
- **HAG > 0.5m or elongated**: likely `FP_vegetation`
- **Ring/annular pattern, low central HAG**: likely `FP_burrow_empty`
- **Ambiguous or multiple interpretations**: `uncertain`

## Output Format

The labeled CSV must contain at minimum:
- `id`: Detection ID (from pipeline output)
- `label`: One of `TP`, `FP_rock`, `FP_vegetation`, `FP_burrow_empty`, `uncertain`
- `notes`: Optional free-text

## Quality Assurance

- Each site sample should be labeled by at least one reviewer.
- Inter-rater agreement can be checked by having a second reviewer label a subset.
- `uncertain` labels are excluded from precision calculation (conservative).
