# Phase 2: AI/YOLO Detection Investigation Plan

*Status: DEFERRED - Focus on physics-first fusion pipeline*
*Created: 2025-11-01*
*Review After: Fusion baseline complete + metrics available*

## Executive Summary

This document outlines the Phase 2 plan for investigating AI-based object detection (YOLO or similar) for penguin detection. This is **explicitly deferred** until after the physics-first LiDAR + thermal fusion pipeline is complete, validated, and metrics are available to justify additional complexity.

## Prerequisite Gates (Must Complete First)

### 1. Fusion Pipeline Completion ✓
- [ ] Thermal orthorectification stable with RMSE ≤ 2px
- [ ] VRT/COG mosaic generation automated
- [ ] LiDAR candidates → thermal stats join operational
- [ ] Fusion labels (LiDAR-only / Thermal-only / Both) validated

### 2. Ground Truth Collection ✓
- [ ] ≥500 verified penguin instances across multiple conditions
- [ ] ≥2,000 instances preferred for robust training
- [ ] Variation across: colony density, sun angle, snow/rock backgrounds, sensor settings
- [ ] Negative samples (rocks, shadows) explicitly labeled

### 3. Baseline Metrics Established ✓
- [ ] LiDAR-only precision/recall measured
- [ ] Thermal-only precision/recall measured
- [ ] Fusion (LiDAR + thermal) precision/recall measured
- [ ] False positive rate by category (rocks, shadows, vegetation)
- [ ] Processing time per km² benchmarked

## Decision Criteria for Phase 2 Activation

Investigate AI detection **only if ALL conditions met**:

1. **Performance Gap Exists**
   - Fusion pipeline shows systematic misses that appear visually detectable
   - Target precision (>0.95) or recall (>0.90) not achieved with physics-based approach
   - Specific failure modes identified (e.g., partially occluded penguins, edge cases)

2. **ROI Justification**
   - Expected accuracy improvement ≥10% over fusion baseline
   - Human review time reduction ≥50% for same accuracy
   - Cost of development < value of improved detection rate

3. **Data Readiness**
   - Stable, aligned orthorectified imagery (thermal + optional RGB)
   - Consistent georegistration between LiDAR and imagery (≤0.5m error)
   - Sufficient labeled instances across environmental conditions

## Proposed Approach: Weak Supervision Strategy

### Phase 2A: Pseudo-Label Pretraining
```python
# Conceptual workflow
1. Use LiDAR detections as initial pseudo-labels
2. Extract thermal patches at detection locations (e.g., 64x64 px)
3. Pretrain lightweight classifier (ResNet18 or EfficientNet-B0)
4. Human-audit stratified sample (~10%) to identify bias
5. Retrain with corrected labels
```

### Phase 2B: Detection Head Development
- **Architecture**: YOLOv8-nano or YOLOv5s (small, fast variants)
- **Input**: Orthorectified thermal tiles (512x512 or 1024x1024)
- **Classes**: Single class (penguin) initially
- **Training**:
  - Transfer learning from COCO or similar
  - Augmentation: rotation, brightness, thermal noise simulation
  - Validation: k-fold cross-validation across different flight sessions

### Phase 2C: Ensemble Integration
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   LiDAR     │────▶│    Fusion    │────▶│   Ensemble  │
│  HAG Blobs  │     │    Logic     │     │   Voting    │
└─────────────┘     └──────────────┘     └─────────────┘
                           ▲                      ▲
┌─────────────┐           │                      │
│   Thermal   │───────────┘                      │
│ Statistics  │                                   │
└─────────────┘                                   │
                                                  │
┌─────────────┐                                   │
│    YOLO     │───────────────────────────────────┘
│  Detections │
└─────────────┘
```

## Implementation Checklist (When Activated)

### Data Preparation
- [ ] Export LiDAR detections as COCO/YOLO format annotations
- [ ] Create train/val/test splits (60/20/20) stratified by scene
- [ ] Generate negative samples (hard negatives from false positives)
- [ ] Implement data loader with proper normalization for thermal

### Model Development
- [ ] Baseline: Train binary classifier on patches
- [ ] Detection: Train YOLO on full tiles
- [ ] Benchmark inference speed (target: <100ms per tile on GPU)
- [ ] Implement confidence calibration

### Validation & Testing
- [ ] Cross-validate across different environmental conditions
- [ ] Test on held-out flight sessions
- [ ] Compare with fusion baseline using same test set
- [ ] Analyze failure modes and edge cases

### Production Integration
- [ ] Dockerize inference pipeline
- [ ] Add model versioning and weights management
- [ ] Implement fallback to physics-based detection
- [ ] Create monitoring for model drift

## Resource Requirements

### Compute
- Training: 1x GPU (RTX 3090 or better) for 24-48 hours
- Inference: GPU preferred but CPU viable for YOLOv8-nano

### Human Time
- Data labeling audit: 40-80 hours
- Model development: 80-120 hours
- Integration & testing: 40-60 hours
- **Total: ~200-260 hours** (1-1.5 months with one engineer)

### Costs
- GPU compute: ~$500-1000 (cloud) or use existing hardware
- Labeling tools: $0 (use CVAT or Label Studio open source)
- Human time: Primary cost driver

## Risk Mitigation

1. **Overfitting Risk**: Use extensive augmentation, small model architectures
2. **Label Noise**: Manual audit of high-confidence disagreements between models
3. **Distribution Shift**: Retain physics-based fusion as fallback
4. **Complexity Creep**: Time-box to 6 weeks; if no clear win, abandon

## Success Metrics

**GO Decision Requires:**
- Precision ≥0.97 (vs fusion baseline)
- Recall ≥0.93 (vs fusion baseline)
- Inference <100ms per 1024x1024 tile
- False positive rate <2% on known hard negatives

**NO-GO if:**
- Improvement <5% over fusion baseline
- Requires extensive manual labeling (>200 hours)
- Inference too slow for operational use
- Model not generalizing across sessions

## Key Insight

> "The goal is NOT to use AI. The goal is accurate, auditable penguin counts. AI is only a tool if simpler methods fail."

## Review Schedule

1. **After fusion pipeline complete**: Assess baseline metrics
2. **At 3-month mark**: Review if gaps justify Phase 2 activation
3. **At 6-month mark**: Final go/no-go on AI investigation

---

*Remember: Every hour spent on AI development is an hour not spent improving the deterministic pipeline. Choose wisely.*