#!/usr/bin/env python3
"""
Blob Classifier Training — Penguin Detection Pipeline

Trains a lightweight logistic regression classifier on labeled blob features
to improve detection precision beyond single-threshold HAG filtering.

The classifier uses multiple features (HAG statistics, geometry, spectral)
to output:
- Probability score per detection
- Top 3 contributing features for interpretability

Usage:
    # Train from labeled samples
    python scripts/train_blob_classifier.py \
        --features data/processed/blob_features.parquet \
        --labels data/labels/caleta_tiny_labels.csv \
        --out models/blob_classifier.pkl \
        --verbose

    # Evaluate existing model
    python scripts/train_blob_classifier.py \
        --features data/processed/blob_features.parquet \
        --labels data/labels/caleta_tiny_labels.csv \
        --model models/blob_classifier.pkl \
        --evaluate-only \
        --verbose
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# Features used for classification (interpretable, non-redundant)
CLASSIFIER_FEATURES = [
    # HAG features (primary signal)
    "hag_mean",
    "hag_max",
    "hag_std",
    "hag_p95",
    "hag_range",

    # Geometry features
    "area_cells",
    "circularity",
    "solidity",
    "eccentricity",
    "aspect_ratio",

    # Spectral features (z-score normalized)
    "intensity_zscore",
    "greenness_zscore",

    # Merge indicator
    "likely_merged_score",
]


def load_features(features_path: Path):
    """Load blob features from Parquet file."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required for feature loading")

    return pd.read_parquet(features_path)


def load_labels(labels_path: Path):
    """Load labels from CSV file.

    Expected format:
    - detection_id: matches blob feature detection_id
    - label: 1 for true positive, 0 for false positive
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required for label loading")

    df = pd.read_csv(labels_path)

    # Validate required columns
    if "detection_id" not in df.columns:
        raise ValueError("Labels CSV must have 'detection_id' column")
    if "label" not in df.columns:
        raise ValueError("Labels CSV must have 'label' column")

    return df


def prepare_training_data(
    features_df,
    labels_df,
    feature_cols: List[str],
):
    """Join features and labels, prepare X and y matrices.

    Returns (X, y, feature_names, merged_df)
    """
    import pandas as pd

    # Join on detection_id
    merged = pd.merge(
        features_df,
        labels_df[["detection_id", "label"]],
        on="detection_id",
        how="inner",
    )

    if len(merged) == 0:
        raise ValueError("No matching detection_ids between features and labels")

    # Select features, handle missing
    available_features = [f for f in feature_cols if f in merged.columns]
    missing_features = [f for f in feature_cols if f not in merged.columns]

    if missing_features:
        print(f"WARNING: Missing features (will be filled with 0): {missing_features}", file=sys.stderr)

    # Create feature matrix
    X = merged[available_features].fillna(0).values
    y = merged["label"].values

    return X, y, available_features, merged


def train_classifier(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    regularization: float = 1.0,
    class_weight: str = "balanced",
):
    """Train logistic regression classifier.

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Label vector (n_samples,)
        feature_names: Names of features for interpretability
        regularization: Inverse regularization strength (C parameter)
        class_weight: "balanced" to handle imbalanced classes

    Returns:
        Trained classifier dict with model and metadata
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train logistic regression
    model = LogisticRegression(
        C=regularization,
        class_weight=class_weight,
        max_iter=1000,
        random_state=42,
    )
    model.fit(X_scaled, y)

    # Extract feature importance (absolute coefficient values)
    importances = np.abs(model.coef_[0])
    importance_ranking = np.argsort(importances)[::-1]

    return {
        "model": model,
        "scaler": scaler,
        "feature_names": feature_names,
        "coefficients": dict(zip(feature_names, model.coef_[0].tolist())),
        "intercept": float(model.intercept_[0]),
        "feature_importance": dict(zip(feature_names, importances.tolist())),
        "top_features": [feature_names[i] for i in importance_ranking[:5]],
    }


def evaluate_classifier(
    classifier: Dict,
    X: np.ndarray,
    y: np.ndarray,
    verbose: bool = False,
) -> Dict:
    """Evaluate classifier performance.

    Returns dict with metrics:
    - accuracy, precision, recall, f1
    - confusion matrix
    - classification report
    """
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        confusion_matrix,
        classification_report,
        roc_auc_score,
    )

    model = classifier["model"]
    scaler = classifier["scaler"]

    X_scaled = scaler.transform(X)
    y_pred = model.predict(X_scaled)
    y_prob = model.predict_proba(X_scaled)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "f1": float(f1_score(y, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, y_prob)) if len(np.unique(y)) > 1 else 0.0,
        "n_samples": len(y),
        "n_positive": int(np.sum(y)),
        "n_negative": int(np.sum(1 - y)),
    }

    cm = confusion_matrix(y, y_pred)
    metrics["confusion_matrix"] = cm.tolist()
    metrics["true_negatives"] = int(cm[0, 0])
    metrics["false_positives"] = int(cm[0, 1])
    metrics["false_negatives"] = int(cm[1, 0])
    metrics["true_positives"] = int(cm[1, 1])

    if verbose:
        print("\nClassification Report:")
        print(classification_report(y, y_pred, target_names=["FP", "TP"]))
        print(f"\nROC AUC: {metrics['roc_auc']:.3f}")
        print(f"Confusion Matrix:")
        print(f"  TN={metrics['true_negatives']}, FP={metrics['false_positives']}")
        print(f"  FN={metrics['false_negatives']}, TP={metrics['true_positives']}")

    return metrics


def cross_validate(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    n_folds: int = 5,
    verbose: bool = False,
) -> Dict:
    """Perform k-fold cross-validation.

    Returns dict with mean and std metrics across folds.
    """
    from sklearn.model_selection import StratifiedKFold

    kfold = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    fold_metrics = []
    for fold, (train_idx, test_idx) in enumerate(kfold.split(X, y)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        classifier = train_classifier(X_train, y_train, feature_names)
        metrics = evaluate_classifier(classifier, X_test, y_test, verbose=False)
        fold_metrics.append(metrics)

        if verbose:
            print(f"Fold {fold + 1}: F1={metrics['f1']:.3f}, Precision={metrics['precision']:.3f}, Recall={metrics['recall']:.3f}")

    # Aggregate metrics
    cv_results = {}
    for key in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
        values = [m[key] for m in fold_metrics]
        cv_results[f"{key}_mean"] = float(np.mean(values))
        cv_results[f"{key}_std"] = float(np.std(values))

    if verbose:
        print(f"\nCross-validation ({n_folds}-fold):")
        print(f"  F1: {cv_results['f1_mean']:.3f} ± {cv_results['f1_std']:.3f}")
        print(f"  Precision: {cv_results['precision_mean']:.3f} ± {cv_results['precision_std']:.3f}")
        print(f"  Recall: {cv_results['recall_mean']:.3f} ± {cv_results['recall_std']:.3f}")
        print(f"  ROC AUC: {cv_results['roc_auc_mean']:.3f} ± {cv_results['roc_auc_std']:.3f}")

    return cv_results


def predict_with_explanation(
    classifier: Dict,
    features_df,
    top_n: int = 3,
):
    """Predict probabilities and generate top feature explanations.

    Args:
        classifier: Trained classifier dict
        features_df: DataFrame with blob features
        top_n: Number of top contributing features to report

    Returns:
        DataFrame with probability and top_features columns added
    """
    import pandas as pd

    model = classifier["model"]
    scaler = classifier["scaler"]
    feature_names = classifier["feature_names"]
    coefficients = classifier["coefficients"]

    # Prepare features
    available_features = [f for f in feature_names if f in features_df.columns]
    X = features_df[available_features].fillna(0).values
    X_scaled = scaler.transform(X)

    # Predict probabilities
    probabilities = model.predict_proba(X_scaled)[:, 1]

    # Compute feature contributions for each sample
    contributions = X_scaled * model.coef_[0]

    top_features_list = []
    for i in range(len(features_df)):
        # Get top contributing features for this sample
        sample_contributions = contributions[i]
        top_indices = np.argsort(np.abs(sample_contributions))[::-1][:top_n]
        top_feature_names = [available_features[j] for j in top_indices]
        top_feature_values = [round(sample_contributions[j], 3) for j in top_indices]

        explanation = "; ".join([
            f"{name}={val:+.2f}"
            for name, val in zip(top_feature_names, top_feature_values)
        ])
        top_features_list.append(explanation)

    result = features_df.copy()
    result["probability"] = probabilities
    result["top_features"] = top_features_list

    return result


def save_classifier(classifier: Dict, out_path: Path) -> None:
    """Save trained classifier to pickle file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove non-picklable items and save
    save_data = {
        "model": classifier["model"],
        "scaler": classifier["scaler"],
        "feature_names": classifier["feature_names"],
        "coefficients": classifier["coefficients"],
        "intercept": classifier["intercept"],
        "feature_importance": classifier["feature_importance"],
        "top_features": classifier["top_features"],
    }

    with open(out_path, "wb") as f:
        pickle.dump(save_data, f)


def load_classifier(model_path: Path) -> Dict:
    """Load trained classifier from pickle file."""
    with open(model_path, "rb") as f:
        return pickle.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Train blob classifier for LiDAR penguin detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--features", required=True, help="Blob features Parquet file")
    parser.add_argument("--labels", required=True, help="Labels CSV file (detection_id, label)")
    parser.add_argument("--out", default="models/blob_classifier.pkl", help="Output model path")
    parser.add_argument("--model", default=None, help="Existing model to evaluate (skip training)")
    parser.add_argument("--evaluate-only", action="store_true", help="Only evaluate, don't save model")
    parser.add_argument("--cross-validate", action="store_true", help="Perform k-fold cross-validation")
    parser.add_argument("--n-folds", type=int, default=5, help="Number of CV folds")
    parser.add_argument("--regularization", type=float, default=1.0, help="Regularization strength (C)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Check dependencies
    try:
        import pandas as pd
        from sklearn.linear_model import LogisticRegression
    except ImportError as e:
        print(f"ERROR: Required dependencies not available: {e}", file=sys.stderr)
        print("Install with: pip install pandas scikit-learn", file=sys.stderr)
        sys.exit(1)

    features_path = Path(args.features)
    labels_path = Path(args.labels)
    out_path = Path(args.out)

    if not features_path.exists():
        print(f"ERROR: Features file not found: {features_path}", file=sys.stderr)
        sys.exit(1)
    if not labels_path.exists():
        print(f"ERROR: Labels file not found: {labels_path}", file=sys.stderr)
        sys.exit(1)

    # Load data
    if args.verbose:
        print(f"Loading features from {features_path}...")
    features_df = load_features(features_path)
    if args.verbose:
        print(f"  Loaded {len(features_df)} blob features")

    if args.verbose:
        print(f"Loading labels from {labels_path}...")
    labels_df = load_labels(labels_path)
    if args.verbose:
        print(f"  Loaded {len(labels_df)} labels")

    # Prepare training data
    X, y, feature_names, merged_df = prepare_training_data(
        features_df, labels_df, CLASSIFIER_FEATURES
    )
    if args.verbose:
        print(f"  Matched {len(merged_df)} samples")
        print(f"  Positive (TP): {np.sum(y)}, Negative (FP): {np.sum(1-y)}")
        print(f"  Features: {feature_names}")

    # Cross-validation if requested
    if args.cross_validate:
        if args.verbose:
            print(f"\nPerforming {args.n_folds}-fold cross-validation...")
        cv_results = cross_validate(X, y, feature_names, n_folds=args.n_folds, verbose=args.verbose)

    # Train or load model
    if args.model:
        if args.verbose:
            print(f"\nLoading existing model from {args.model}...")
        classifier = load_classifier(Path(args.model))
    else:
        if args.verbose:
            print("\nTraining classifier...")
        classifier = train_classifier(
            X, y, feature_names,
            regularization=args.regularization,
        )

        if args.verbose:
            print("\nFeature Importance (top 5):")
            for feat in classifier["top_features"]:
                coef = classifier["coefficients"][feat]
                imp = classifier["feature_importance"][feat]
                print(f"  {feat}: coef={coef:+.3f}, importance={imp:.3f}")

    # Evaluate
    if args.verbose:
        print("\nEvaluating on full dataset...")
    metrics = evaluate_classifier(classifier, X, y, verbose=args.verbose)

    # Save model
    if not args.evaluate_only and not args.model:
        if args.verbose:
            print(f"\nSaving model to {out_path}...")
        save_classifier(classifier, out_path)

    # Print summary
    summary = {
        "features_file": str(features_path),
        "labels_file": str(labels_path),
        "n_samples": metrics["n_samples"],
        "n_positive": metrics["n_positive"],
        "n_negative": metrics["n_negative"],
        "metrics": {
            "accuracy": round(metrics["accuracy"], 4),
            "precision": round(metrics["precision"], 4),
            "recall": round(metrics["recall"], 4),
            "f1": round(metrics["f1"], 4),
            "roc_auc": round(metrics["roc_auc"], 4),
        },
        "top_features": classifier["top_features"],
    }

    if not args.evaluate_only and not args.model:
        summary["model_path"] = str(out_path)

    if args.cross_validate:
        summary["cross_validation"] = {
            k: round(v, 4) for k, v in cv_results.items()
        }

    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
