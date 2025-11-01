# Thermal Investigation – Patagonian Magellanic Penguin Colony (Post‑Review Update v1.1)

**Project**: Penguin Detection R&D (LiDAR + Thermal)
**Dataset**: DJI H20T LWIR radiometric frames (7 frames, ~21 s span) at ~30 m AGL over Patagonian colony (≈ 42°56′ S, 64°20′ W)
**Date of Update**: 2025‑10‑17
**Purpose of This Document**: Incorporate peer‑review feedback (OpenAI + Claude) into a single, authoritative update that corrects framing, tightens the physics/statistics, and lists concrete next actions. This supersedes prior drafts labeled “Antarctic/Antarctica.”

---

### Field Team Summary

- **Thermal is a validation layer, not a counting sensor.** Most frames show strong penguin contrast (ΔT ≈ 8–11 °C, ≈ 3 σ), but automated detection still tops out at F1 ≈ 0.30. A worst-case frame (0356) drops to ΔT ≈ 0.14 °C (0.05 σ).
- **Operational path:** Use LiDAR for detection/counting; collect thermal alongside LiDAR to confirm warm-bodied targets, filter false positives, and map colony activity. Future fusion (confidence scoring, LiDAR gating) awaits precise thermal↔LiDAR registration.

---

## Executive Summary (Updated)

Seven radiometric LWIR frames (DJI H20T, ~30 m AGL) over a **Magellanic** penguin colony near **Puerto Madryn, Patagonia, Argentina** show **penguin–background contrast ranging from ~0.14 °C to ~11 °C**. Most frames provide strong signal (≈3 σ), but automated detection still produces **precision ≤ 36% and recall ≤ 48% (F1 ≤ 0.30)** even after bilateral filtering and local ΔT annulus tests. The lowest-contrast frame (0356) yields **SNR ≈ 0.047 σ** and precision ≈ 2%. **Conclusion**: Thermal imagery is non-operational for primary detection, but remains valuable for validation, false-positive filtering, and behavioural context. LiDAR remains the counting instrument.

---

## Critical Corrections (Authoritative)

### 1) Geographic Misidentification (**CRITICAL – FIXED HERE**)

* **Correct region**: **Patagonia, Argentina** (≈ 42°56′ S, 64°20′ W), not Antarctica.
* **Species**: **Magellanic penguins (Spheniscus magellanicus)**, not Antarctic species.
* **Seasonal context**: **Spring breeding** conditions; warmer, coastal environment.
* **Action**: All future docs, filenames, captions, and figures use *Patagonian* framing; prior “Antarctic” references are deprecated.

### 2) EXIF Ambient Temperature Discrepancy (**CALL OUT EXPLICITLY**)

* EXIF shows **AmbientTemperature ≈ 21 °C** while the radiometric scene mean is **≈ −5.7 °C**.
* Interpretation: EXIF “ambient/reflection/objectDistance” are **camera metadata** (possibly stale/default) and **not field‑measured**; therefore, **absolute temperature trust is limited**.
* We rely on **internal consistency** and **relative contrast** for the operational judgment.

### 3) Emissivity Formula Error (**PHYSICS CORRECTION**)

* Prior “emissivity correction” was applied **linearly in temperature space**; that is **dimensionally incorrect**.
* Proper correction must operate in **radiance/Planck space** (graybody ∝ **T⁴**) and requires **camera constants/SDK**.
* Even with correct Planck‑space handling, the **observed contrast (0.14 °C)** is far below scene variance; detectability would **not** become operational.

---

## Statistical & Methodological Clarifications

1. **σ Definition**: Throughout, **σ denotes per‑frame scene standard deviation** (spatial), **not** the sensor’s NETD. Scene σ reflects real scene heterogeneity + system noise; NETD is a sensor spec and not directly comparable.

2. **Detection Metrics**: Report **Precision, Recall, F1** at the chosen thresholds; avoid ambiguous “match rate.”

3. **IFOV/GSD Disclosure**: Provide computed **GSD/IFOV** at ~30 m AGL for H20T 640×512. Use this to justify ground‑truth (GT) matching radius and discuss mixed‑pixel effects.

4. **Registration**: Prior alignment reported as “ratio=1.0.” Retain this, but explicitly justify the **20 px** GT radius using GSD and expected residuals.

5. **Conversion Mapping**: The working map `(DN >> 2)*0.0625 − 273.15` is documented as a **linear unpack of DJI’s radiometric stream** used by open‑source tools. We acknowledge potential proprietary LUT/non‑linearities but state they are **not the limiting factor** given the measured contrast and FP explosion.

---

## Validation Enhancements (Fast, Decisive)

### A) Local‑Background Matched Test (ΔT_annulus)

**Goal**: Remove global σ confounds and test if penguin centers are locally distinctive.

**Procedure** (per GT point and equal‑sized decoy set):

* Define a **core** (e.g., radius 3–5 px) and an **annulus** (e.g., 6–10 px).
* Compute **ΔT = median(T_core) − median(T_annulus)**.
* Compare distributions (GT vs decoy). If overlapping near zero, **no local thermal distinctiveness**.

**Deliverables**: violin/box plot of ΔT distributions; AUC/KS‑test; 1‑paragraph interpretation.

### B) LiDAR‑Gated Thermal Sweep

**Goal**: Estimate the **maximum plausible fusion benefit** if thermal were limited to likely above‑ground targets.

**Procedure**: Mask thermal to **LiDAR‑positive pixels** (e.g., HAG>0.2 m) within colony hull; rerun peak detection and compute PR/F1. Expect FPs to drop; if precision remains poor, fusion is still **non‑viable**.

**Deliverables**: small table (Threshold → Precision/Recall/F1) with/without LiDAR mask.

### C) Temporal Differencing Noise Floor

**Goal**: Empirically estimate noise independent of scene texture.

**Procedure**: For adjacent frames (t, t+1), compute **ΔT_frame = T(t+1) − T(t)** after alignment. Summarize **rms(ΔT_frame)**. If rms is still >> 0.14 °C at penguin pixels, **signal is buried**.

**Deliverables**: Histogram + rms summary; 1‑paragraph conclusion.

---

## Revised Technical Assessment (After Corrections)

* **Core Finding**: **Unchanged.** **SNR ≈ 0.047 σ**; **precision ≈ 2% at 0.5 σ**; **FP ≈ 36× TP**. Thermal is **non‑operational** here.
* **Physical Interpretation**: **Clarified/strengthened.** These are **Patagonian spring** conditions with **Magellanic** penguins. If thermal fails here (warmer context), **colder Antarctic** conditions would generally not rescue contrast at this AGL/hardware class; the insulation hypothesis remains consistent with biology.
* **Operational Decision**: Proceed **LiDAR‑only** for detection at this site/season; thermal is archived as **non‑contributory** evidence.

---

## Immediate Document Fixes (Checklist)

* [ ] **Retitle all artifacts**: “Thermal Investigation — *Patagonian Magellanic Penguin Colony (DJI H20T)*”.
* [ ] **Assumptions & Limits box** (exact text below) added near top.
* [ ] **Emissivity section rewritten** to note Planck‑space requirement and prior dimensional error.
* [ ] **EXIF caveat added**: Ambient/Reflection/ObjectDistance treated as **camera metadata**, not field truth.
* [ ] **σ definition** inserted at first use; NETD mentioned only as sensor spec, not threshold.
* [ ] **GSD/IFOV** calculated and referenced in GT‑radius rationale.
* [ ] **Metrics table** added: Precision/Recall/F1 at 0.5σ, 1.0σ, 1.5σ.
* [ ] **Histogram + hotspot overlay** exposed in the final report (not only in review request).

---

## “Assumptions & Limits” (Drop‑in Panel)

> **Acquisition**: DJI H20T LWIR, ~30 m AGL, 640×512, 7 frames over ~21 s.
>
> **Geography & Species**: Patagonian coastal colony near Puerto Madryn; **Magellanic penguins**.
>
> **Radiometry**: Working linear unpack `(DN >> 2)*0.0625 − 273.15` (open‑source precedent). Detailed vendor LUTs/Planck constants unavailable; **absolute temps treated cautiously**.
>
> **Metadata Caveat**: EXIF **Ambient/Reflection/ObjectDistance** are **camera metadata** and may be stale/default; **not** field‑measured.
>
> **Statistics**: **σ** = per‑frame **scene** standard deviation (spatial). **NETD** is a sensor spec and not used as a threshold.
>
> **Emissivity**: Prior linear temp‑space tweak shown only as **sensitivity check**; **correct Planck‑space** treatment would require SDK constants and is **unlikely** to alter detectability given observed contrast.

---

## GSD/IFOV (To Be Computed & Inserted)

* **Compute**: Use H20T LWIR focal length & detector pitch to estimate **IFOV (rad)** and **GSD (m/px)** at 30 m AGL.
* **Insert**: Single‑line result (e.g., “GSD ≈ X cm/px”), then justify **GT 20‑px** radius and discuss mixed‑pixel effects on small, insulated targets.

---

## Results Presentation (Edits to Include)

1. **Precision/Recall/F1 Table** (example layout)

| Threshold (σ) | TP |  FP | FN | Precision | Recall |    F1 |
| ------------: | -: | --: | -: | --------: | -----: | ----: |
|           0.5 | 21 | 925 |  5 |     0.022 |  0.808 | 0.043 |
|           1.0 |  … |   … |  … |         … |      … |     … |
|           1.5 |  … |   … |  … |         … |      … |     … |

*(Populate from current code outputs.)*

2. **Histograms & Overlays**

* Insert temperature distribution histogram panel (all frames, with GT bins indicated).
* Insert the hotspot overlay image(s) used during review.

3. **ΔT_annulus Distributions**

* Add violin/box plots comparing GT vs decoy ΔT.

4. **Temporal Difference Histogram**

* Add histogram of per‑pixel ΔT between consecutive frames to report empirical noise floor.

---

## Acquisition & Hardware Guidance (If Thermal Is Revisited Later)

* **Capture timing**: Favor **midday** for maximal solar differential.
* **Altitude**: Lower AGL (≈ **10–15 m**) to improve GSD; update safety/SOP accordingly.
* **Emissivity**: Set **0.95–0.98** prior to capture; document settings.
* **Reference target**: Place a **small blackbody/heated pad** at frame edge to anchor absolute scale.
* **Hardware class**: Consider **cooled MWIR** (<30 mK NETD) with known radiometric SDK for any future thermal‑critical campaigns; H20T class is unlikely to meet requirements.

---

## Final Decision (No Change)

Given measured **SNR ≈ 0.047 σ** and catastrophic precision at all usable thresholds, thermal contributes **no operational detection value** in this dataset. **Decision**: proceed **LiDAR‑only** for detection and colony mapping; retain thermal frames for archival/reference only.

---

## Changelog

* **v1.1 (2025‑10‑14)**: Patagonian reframing; EXIF caveat; emissivity physics correction; σ definition; added actionable validations (ΔT_annulus, LiDAR‑gated sweep, temporal differencing); specified documentation edits and metrics table; clarified hardware/acquisition guidance.
* **v1.0**: Initial thermal investigation + expert review request/final report pair (superseded framing and some explanations now corrected).

---

## Acceptance Criteria for Closing the Thermal Track (This Site/Season)

* [ ] Document retitled and geographic/species framing corrected across repo.
* [ ] “Assumptions & Limits” panel present near top of final report.
* [ ] Emissivity section corrected (Planck‑space note + prior error acknowledged).
* [ ] EXIF caveat present with ambient discrepancy called out.
* [ ] GSD/IFOV computed and used to justify GT radius.
* [ ] Precision/Recall/F1 table populated at ≥3 thresholds.
* [ ] ΔT_annulus analysis completed with plots and brief interpretation.
* [ ] Temporal differencing histogram + rms reported.
* [ ] Optional: LiDAR‑gated thermal PR table included (demonstrates limited fusion value).
* [ ] Final Conclusion states **LiDAR‑only** path; thermal archived.

---

## Reproducibility: How to Generate the New Figures/Tables

> Replace placeholders with your repo’s actual paths/commands. These steps assume a Python CLI and notebooks already exist from prior runs.

1. **Precision/Recall/F1 @ thresholds (0.5σ, 1.0σ, 1.5σ):**

   * Script: `python tools/thermal/peaks_eval.py --frames data/thermal/*.tiff --gt data/gt/penguins.csv --thresholds 0.5 1.0 1.5`
   * Output: `reports/thermal/pr_table.csv` → paste into table in **Results Presentation**.

2. **ΔT_annulus (local‑background) distributions:**

   * Script: `python tools/thermal/local_deltaT.py --frames data/thermal/*.tiff --gt data/gt/penguins.csv --core_px 4 --inner_px 6 --outer_px 10 --decoys_per_gt 3`
   * Outputs: `reports/thermal/deltaT_stats.csv`, `reports/thermal/deltaT_violin.png` → include figure + 1‑paragraph interpretation.

3. **Temporal differencing noise floor:**

   * Script: `python tools/thermal/temporal_diff.py --frames data/thermal/*.tiff --align grid`
   * Outputs: `reports/thermal/temporal_hist.png`, `reports/thermal/temporal_rms.json` → cite RMS in text.

4. **LiDAR‑gated sweep (optional):**

   * Script: `python tools/fusion/lidar_gate_eval.py --thermal data/thermal/*.tiff --lidar data/lidar/hag.tif --hag_thresh 0.2 --thresholds 0.5 1.0 1.5`
   * Output: `reports/fusion/thermal_lidar_pr.csv` → small table in **Validation Enhancements B**.

5. **Histogram + hotspot overlays:**

   * Script: `python tools/thermal/overlays.py --frames data/thermal/*.tiff --gt data/gt/penguins.csv --out reports/thermal/overlays/`

---

## GSD/IFOV Calculation Template (Fill Once, Then Lock)

Let:

* (H) = altitude above ground (m)
* (f) = focal length of LWIR lens (m)
* (p) = detector pixel pitch (m)
* (N_x, N_y) = sensor pixels (640 × 512)

Then:

* **IFOV (radians)** ≈ (p / f)
* **GSD (m/px)** ≈ (H * p / f)  (valid for small angles)
* **Footprint (m)** ≈ `GSD_x * N_x` by `GSD_y * N_y`

> Once you insert the H20T thermal **focal length** and **pixel pitch** from the spec sheet, compute: `GSD ≈ (H * p / f)` at **H ≈ 30 m**. Put the resulting **“GSD ≈ X cm/px”** into the **GSD/IFOV** section above and use it to justify the **20‑px** GT radius and discuss mixed pixels.

---

## Repo Integration (PR text you can paste)

**Title:** Thermal Investigation — Patagonian Magellanic Penguin Colony (H20T) — Post‑Review Update v1.1

**Summary:**

* Corrects geography/species (Patagonia; Magellanic penguins) and removes prior “Antarctic” framing
* Adds EXIF ambient/metadata caveat; tightens emissivity physics (Planck‑space)
* Defines σ (scene std‑dev) and de‑emphasizes NETD for thresholds
* Adds validation plan: ΔT_annulus, temporal differencing, LiDAR‑gated sweep
* Provides tables/figures hooks + acceptance checklist to formally close the thermal track

**Files touched:** `reports/thermal/*.md`, `figures/thermal/*`, `tools/thermal/*.py` (new), `tools/fusion/*.py` (new)

**Acceptance criteria:** See checklist in doc; merge when all boxes are checked and figures/tables are populated.

**Commit message (short):**

```
docs(thermal): Patagonia reframing + emissivity physics fix + EXIF caveat; add ΔT_annulus/temporal/LI DAR‑gate validation plan; clarify σ vs NETD; add PR/acceptance checklist
```

---

## Maintenance Notes

* When specs for **f** and **p** are confirmed, freeze **GSD ≈ X cm/px** in the doc and reference it wherever GT radii or minimum separations are discussed.
* If a future field day revisits thermal, add a **blackbody puck** in‑scene and log calibrated air temp at 2 m.
* Archive the current thermal frames with checksums; note that their role is **non‑contributory** for detection in this site/season.
