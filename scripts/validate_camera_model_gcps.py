#!/usr/bin/env python3
"""
Camera model validation using 16 GCPs (4 box corners × 4 oblique images).

Forward-projects known GPS box corners through the pinhole camera model
and compares to manually-labeled pixel positions.

Phase 1: Sweep DFOV to find optimal diagonal field of view.
Phase 2: Per-image analysis with permutation consistency and per-frame du/dv.
Phase 3: Joint least-squares fit of DFOV + yaw_bias + pitch_bias + XY offset.

Data: Bushes box count area, San Lorenzo, Argentina (Nov 2025).
All 4 images at -45° pitch from 4 cardinal directions.

Usage:
    python scripts/validate_camera_model_gcps.py
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.thermal import rotation_from_ypr, hv_from_dfov, intrinsics_from_fov

try:
    from pyproj import Transformer
except ImportError:
    sys.exit("pyproj required: conda install -c conda-forge pyproj")

try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ── Data ──────────────────────────────────────────────────────────────

CAMERAS = [
    {"frame": "0076", "lat": -42.0852775, "lon": -63.8664954,
     "alt_msl": 59.2, "alt_agl": 35.4, "yaw": -88.4, "pitch": -45.0, "roll": 0.0},
    {"frame": "0116", "lat": -42.0857238, "lon": -63.8670125,
     "alt_msl": 56.0, "alt_agl": 32.2, "yaw": 1.4, "pitch": -45.0, "roll": 0.0},
    {"frame": "0158", "lat": -42.0853613, "lon": -63.8675492,
     "alt_msl": 58.5, "alt_agl": 34.7, "yaw": 89.5, "pitch": -45.0, "roll": 0.0},
    {"frame": "0197", "lat": -42.0849066, "lon": -63.8670938,
     "alt_msl": 59.4, "alt_agl": 35.6, "yaw": -179.3, "pitch": -45.0, "roll": 0.0},
]

CORNERS_WGS84 = {
    "NW": (-42.085258, -63.867123),
    "NE": (-42.085273, -63.866958),
    "SE": (-42.085392, -63.866972),
    "SW": (-42.085381, -63.867161),
}

# Labeled corner pixels per image (raw CSV order, not yet matched to corner names)
CORNER_PIXELS = {
    "0076": [(618, 411), (685, 132), (128, 395), (250, 84)],
    "0116": [(654, 43), (619, 348), (68, 303), (261, 11)],
    "0158": [(237, 200), (643, 583), (691, 224), (66, 525)],
    "0197": [(184, 411), (606, 457), (733, 146), (279, 116)],
}

IMG_W, IMG_H = 1280, 1024
CORNER_NAMES = ["NW", "NE", "SE", "SW"]


# ── Precompute UTM coordinates ────────────────────────────────────────

def precompute_utm():
    """Convert all WGS84 coordinates to UTM once."""
    t = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)

    corners_utm = {}
    for name, (lat, lon) in CORNERS_WGS84.items():
        e, n = t.transform(lon, lat)
        corners_utm[name] = (e, n)

    cameras_utm = []
    for cam in CAMERAS:
        Ce, Cn = t.transform(cam["lon"], cam["lat"])
        cameras_utm.append({
            **cam,
            "Ce": Ce,
            "Cn": Cn,
            "z_ground": cam["alt_msl"] - cam["alt_agl"],
        })

    return corners_utm, cameras_utm


# ── Forward projection ────────────────────────────────────────────────

def project_corners(cam_utm, corners_utm, fx, fy, cx, cy,
                    yaw_bias=0.0, pitch_bias=0.0, dx=0.0, dy=0.0):
    """Project all 4 corners for one camera with optional bias parameters.

    Args:
        cam_utm: camera dict with Ce, Cn, alt_msl, z_ground, yaw, pitch, roll
        corners_utm: dict mapping corner name → (easting, northing)
        fx, fy, cx, cy: camera intrinsics
        yaw_bias: additive yaw correction (degrees)
        pitch_bias: additive pitch correction (degrees)
        dx, dy: camera position offset in UTM (easting, northing)
    """
    Ce = cam_utm["Ce"] + dx
    Cn = cam_utm["Cn"] + dy
    Cz = cam_utm["alt_msl"]
    z_ground = cam_utm["z_ground"]

    R = rotation_from_ypr(
        cam_utm["yaw"] + yaw_bias,
        cam_utm["pitch"] + pitch_bias,
        cam_utm["roll"],
    )

    projected = {}
    for name in CORNER_NAMES:
        ce, cn = corners_utm[name]
        Vc = R.T @ np.array([ce - Ce, cn - Cn, z_ground - Cz])
        xc, yc, zc = Vc

        if zc <= 0:
            projected[name] = None
        else:
            projected[name] = (fx * xc / zc + cx, fy * yc / zc + cy)

    return projected


def best_assignment(projected, observed_pixels):
    """Find optimal corner→pixel assignment by exhaustive permutation search.

    Returns:
        (total_error, mapping, per_gcp_errors, best_permutation_tuple)
    """
    proj_list = [projected[name] for name in CORNER_NAMES]

    if any(p is None for p in proj_list):
        return (float("inf"), None, None, None)

    best_total = float("inf")
    best_perm = None
    best_errors = None

    for perm in itertools.permutations(range(4)):
        errors = []
        for i, pi in enumerate(perm):
            pu, pv = proj_list[i]
            ou, ov = observed_pixels[pi]
            errors.append(math.sqrt((pu - ou) ** 2 + (pv - ov) ** 2))
        total = sum(errors)
        if total < best_total:
            best_total = total
            best_perm = perm
            best_errors = errors

    mapping = {CORNER_NAMES[i]: int(best_perm[i]) for i in range(4)}
    return (best_total, mapping, best_errors, tuple(best_perm))


def residuals_for_params(cameras_utm, corners_utm, corner_pixels,
                         dfov, yaw_bias=0.0, pitch_bias=0.0, dx=0.0, dy=0.0):
    """Compute all per-GCP residual vectors (du, dv) for given parameters.

    Returns list of (frame, corner_name, du, dv, error) tuples and
    list of best permutation tuples per image.
    """
    hfov, vfov = hv_from_dfov(dfov, IMG_W, IMG_H)
    fx, fy, cx, cy = intrinsics_from_fov(hfov, vfov, IMG_W, IMG_H)

    residuals = []
    perms = []

    for cam in cameras_utm:
        projected = project_corners(cam, corners_utm, fx, fy, cx, cy,
                                    yaw_bias, pitch_bias, dx, dy)
        observed = corner_pixels[cam["frame"]]
        _, mapping, _, perm = best_assignment(projected, observed)
        perms.append(perm)

        if mapping is None:
            continue

        for name in CORNER_NAMES:
            pu, pv = projected[name]
            ou, ov = observed[mapping[name]]
            du = pu - ou
            dv = pv - ov
            err = math.sqrt(du * du + dv * dv)
            residuals.append((cam["frame"], name, du, dv, err))

    return residuals, perms


def total_error_for_params(params, cameras_utm, corners_utm, corner_pixels):
    """Objective function for scipy.optimize: total reprojection error."""
    dfov, yaw_bias, pitch_bias, dx, dy = params
    if dfov < 20 or dfov > 80:
        return 1e6

    residuals, _ = residuals_for_params(
        cameras_utm, corners_utm, corner_pixels,
        dfov, yaw_bias, pitch_bias, dx, dy,
    )
    return sum(r[4] for r in residuals)


# ── Ground error via local Jacobian ──────────────────────────────────

def ground_error_jacobian(cam_utm, corner_utm, fx, fy, cx, cy,
                          yaw_bias=0.0, pitch_bias=0.0, dx=0.0, dy=0.0):
    """Compute local Jacobian d(pixel)/d(ground) at a GCP.

    Returns the 2x2 Jacobian J where [du, dv] = J @ [de, dn],
    and the singular values (pixels per meter in principal directions).
    """
    Ce = cam_utm["Ce"] + dx
    Cn = cam_utm["Cn"] + dy
    Cz = cam_utm["alt_msl"]
    z_ground = cam_utm["z_ground"]

    R = rotation_from_ypr(
        cam_utm["yaw"] + yaw_bias,
        cam_utm["pitch"] + pitch_bias,
        cam_utm["roll"],
    )

    ce, cn = corner_utm
    d = np.array([ce - Ce, cn - Cn, z_ground - Cz])

    # Numerically compute Jacobian: pixel change per meter in E and N
    eps = 0.01  # 1 cm perturbation
    J = np.zeros((2, 2))
    for axis in range(2):
        d_plus = d.copy()
        d_plus[axis] += eps
        Vc_p = R.T @ d_plus
        if Vc_p[2] <= 0:
            return None, None
        u_p = fx * Vc_p[0] / Vc_p[2] + cx
        v_p = fy * Vc_p[1] / Vc_p[2] + cy

        d_minus = d.copy()
        d_minus[axis] -= eps
        Vc_m = R.T @ d_minus
        if Vc_m[2] <= 0:
            return None, None
        u_m = fx * Vc_m[0] / Vc_m[2] + cx
        v_m = fy * Vc_m[1] / Vc_m[2] + cy

        J[0, axis] = (u_p - u_m) / (2 * eps)
        J[1, axis] = (v_p - v_m) / (2 * eps)

    # Singular values: pixels per meter in principal directions
    sv = np.linalg.svd(J, compute_uv=False)
    return J, sv


# ── Main ──────────────────────────────────────────────────────────────

def main():
    corners_utm, cameras_utm = precompute_utm()

    print("=" * 72)
    print("Camera Model GCP Validation — DJI H30T Thermal")
    print("=" * 72)
    print(f"Images: {len(CAMERAS)} oblique frames at -45° pitch")
    print(f"GCPs:   4 box corners x 4 images = 16 total")
    print(f"Image:  {IMG_W}x{IMG_H}")
    print()

    # ── Phase 1: DFOV sweep ──────────────────────────────────────────
    print("Phase 1: DFOV-Only Sweep (35-50 deg, 0.1 deg steps)")
    print("-" * 52)

    dfov_values = np.arange(35.0, 50.05, 0.1)
    sweep_errors = []
    for dfov in dfov_values:
        residuals, _ = residuals_for_params(
            cameras_utm, corners_utm, CORNER_PIXELS, dfov)
        mean_err = np.mean([r[4] for r in residuals]) if residuals else float("inf")
        sweep_errors.append(mean_err)

    sweep_errors = np.array(sweep_errors)
    best_idx = np.argmin(sweep_errors)
    best_dfov_sweep = float(dfov_values[best_idx])
    best_err_sweep = float(sweep_errors[best_idx])

    # DFOV uncertainty: range where error < min + 1 px
    within_1px = dfov_values[sweep_errors < best_err_sweep + 1.0]
    dfov_lo = float(within_1px[0]) if len(within_1px) else best_dfov_sweep
    dfov_hi = float(within_1px[-1]) if len(within_1px) else best_dfov_sweep

    print(f"Optimal DFOV: {best_dfov_sweep:.1f} deg  "
          f"(+/- 1px range: {dfov_lo:.1f} - {dfov_hi:.1f} deg)")
    print(f"Mean reprojection error: {best_err_sweep:.1f} px")
    print()
    print("Error curve near minimum:")
    print(f"  {'DFOV':>6s}  {'Mean Err (px)':>13s}")
    for i in range(max(0, best_idx - 8), min(len(dfov_values), best_idx + 9)):
        marker = " <--" if i == best_idx else ""
        print(f"  {dfov_values[i]:6.1f}  {sweep_errors[i]:13.1f}{marker}")

    # ── Phase 2: Per-image analysis at sweep-optimal DFOV ────────────
    print()
    print(f"Phase 2: Per-Image Analysis at DFOV = {best_dfov_sweep:.1f} deg")
    print("-" * 52)

    hfov, vfov = hv_from_dfov(best_dfov_sweep, IMG_W, IMG_H)
    fx, fy, cx, cy = intrinsics_from_fov(hfov, vfov, IMG_W, IMG_H)
    print(f"HFOV={hfov:.2f}  VFOV={vfov:.2f}  fx={fx:.1f}  fy={fy:.1f}")
    print()

    residuals_p2, perms_p2 = residuals_for_params(
        cameras_utm, corners_utm, CORNER_PIXELS, best_dfov_sweep)

    results = {
        "dfov_sweep": {
            "optimal_dfov_deg": round(best_dfov_sweep, 2),
            "dfov_range_1px": [round(dfov_lo, 2), round(dfov_hi, 2)],
            "mean_error_px": round(best_err_sweep, 2),
        },
        "per_image": [],
        "all_gcps": [],
    }

    # Group residuals by frame
    frame_residuals = {}
    for frame_name, corner, du, dv, err in residuals_p2:
        frame_residuals.setdefault(frame_name, []).append((corner, du, dv, err))

    perm_tuples = []
    for idx, cam in enumerate(cameras_utm):
        fr = cam["frame"]
        fr_res = frame_residuals.get(fr, [])
        perm_tuples.append(perms_p2[idx])

        errs = [r[3] for r in fr_res]
        dus = [r[1] for r in fr_res]
        dvs = [r[2] for r in fr_res]

        # Recompute projected/observed for display
        projected = project_corners(cam, corners_utm, fx, fy, cx, cy)
        observed = CORNER_PIXELS[fr]
        _, mapping, _, _ = best_assignment(projected, observed)

        img_result = {
            "frame": fr,
            "yaw": cam["yaw"],
            "alt_agl": cam["alt_agl"],
            "z_ground": round(cam["z_ground"], 1),
            "mean_error_px": round(np.mean(errs), 1) if errs else None,
            "max_error_px": round(max(errs), 1) if errs else None,
            "du_mean_px": round(np.mean(dus), 1) if dus else None,
            "dv_mean_px": round(np.mean(dvs), 1) if dvs else None,
            "permutation": list(perms_p2[idx]) if perms_p2[idx] else None,
            "corner_mapping": mapping,
            "corners": [],
        }

        print(f"Frame {fr}  yaw={cam['yaw']:+.1f}  AGL={cam['alt_agl']}m  "
              f"z_gnd={cam['z_ground']:.1f}m")

        if mapping:
            for corner, du, dv, err in fr_res:
                pu, pv = projected[corner]
                pi = mapping[corner]
                ou, ov = observed[pi]
                img_result["corners"].append({
                    "corner": corner,
                    "predicted_px": [round(pu, 1), round(pv, 1)],
                    "observed_px": [ou, ov],
                    "du": round(du, 1), "dv": round(dv, 1),
                    "error_px": round(err, 1),
                })
                results["all_gcps"].append({
                    "frame": fr, "corner": corner,
                    "du": round(du, 1), "dv": round(dv, 1),
                    "error_px": round(err, 1),
                })
                print(f"  {corner}: pred=({pu:7.1f},{pv:7.1f})  "
                      f"obs=({ou:4d},{ov:4d})  "
                      f"du={du:+6.1f} dv={dv:+6.1f}  err={err:5.1f}")

            print(f"  -> mean={np.mean(errs):.1f}  max={max(errs):.1f}  "
                  f"du_mean={np.mean(dus):+.1f}  dv_mean={np.mean(dvs):+.1f}")
        else:
            print("  (projection failed)")

        results["per_image"].append(img_result)
        print()

    # ── Permutation consistency ──────────────────────────────────────
    print("Permutation consistency:")
    all_same = len(set(p for p in perm_tuples if p)) == 1
    for idx, cam in enumerate(cameras_utm):
        print(f"  {cam['frame']}: {perm_tuples[idx]}")
    if all_same:
        print("  -> CONSISTENT (same assignment across all images)")
    else:
        print("  -> INCONSISTENT (assignment varies by viewing angle)")
    print()

    results["permutation_consistency"] = {
        "consistent": all_same,
        "per_frame": {cameras_utm[i]["frame"]: list(perm_tuples[i])
                      for i in range(len(cameras_utm)) if perm_tuples[i]},
    }

    # ── Global du/dv summary ─────────────────────────────────────────
    all_du = np.array([r[2] for r in residuals_p2])
    all_dv = np.array([r[3] for r in residuals_p2])
    all_err = np.array([r[4] for r in residuals_p2])

    print("Global residuals (predicted - observed):")
    print(f"  du: mean={np.mean(all_du):+.1f}  std={np.std(all_du):.1f}")
    print(f"  dv: mean={np.mean(all_dv):+.1f}  std={np.std(all_dv):.1f}")
    print(f"  err: mean={np.mean(all_err):.1f}  median={np.median(all_err):.1f}  "
          f"max={np.max(all_err):.1f}  rms={np.sqrt(np.mean(all_err**2)):.1f}")
    print()

    results["summary_dfov_only"] = {
        "n_gcps": int(len(all_err)),
        "mean_error_px": round(float(np.mean(all_err)), 2),
        "median_error_px": round(float(np.median(all_err)), 2),
        "max_error_px": round(float(np.max(all_err)), 2),
        "rms_error_px": round(float(np.sqrt(np.mean(all_err ** 2))), 2),
        "du_mean_px": round(float(np.mean(all_du)), 2),
        "du_std_px": round(float(np.std(all_du)), 2),
        "dv_mean_px": round(float(np.mean(all_dv)), 2),
        "dv_std_px": round(float(np.std(all_dv)), 2),
    }

    # ── Anisotropic ground error ─────────────────────────────────────
    print("Anisotropic ground error (via local Jacobian):")
    ground_errors = []
    for cam in cameras_utm:
        for name in CORNER_NAMES:
            J, sv = ground_error_jacobian(
                cam, corners_utm[name], fx, fy, cx, cy)
            if sv is not None and sv[1] > 0:
                # sv = pixels per meter; invert for meters per pixel
                m_per_px_fine = 1.0 / sv[0]    # best-resolved direction
                m_per_px_coarse = 1.0 / sv[1]  # worst-resolved direction
                ground_errors.append({
                    "frame": cam["frame"], "corner": name,
                    "px_per_m_max": round(float(sv[0]), 1),
                    "px_per_m_min": round(float(sv[1]), 1),
                    "m_per_px_fine": round(m_per_px_fine, 4),
                    "m_per_px_coarse": round(m_per_px_coarse, 4),
                    "anisotropy": round(float(sv[0] / sv[1]), 2),
                })

    if ground_errors:
        aniso_vals = [g["anisotropy"] for g in ground_errors]
        fine_vals = [g["m_per_px_fine"] for g in ground_errors]
        coarse_vals = [g["m_per_px_coarse"] for g in ground_errors]
        print(f"  Resolution (fine dir):   {np.mean(fine_vals)*100:.2f} cm/px  "
              f"(range {np.min(fine_vals)*100:.2f}-{np.max(fine_vals)*100:.2f})")
        print(f"  Resolution (coarse dir): {np.mean(coarse_vals)*100:.2f} cm/px  "
              f"(range {np.min(coarse_vals)*100:.2f}-{np.max(coarse_vals)*100:.2f})")
        print(f"  Anisotropy ratio:        {np.mean(aniso_vals):.2f}  "
              f"(range {np.min(aniso_vals):.2f}-{np.max(aniso_vals):.2f})")

        # Compute ground error using per-GCP Jacobian
        ground_m_errors = []
        for r in residuals_p2:
            frame, corner, du, dv, err_px = r
            # Find matching Jacobian
            cam = next(c for c in cameras_utm if c["frame"] == frame)
            J, sv = ground_error_jacobian(
                cam, corners_utm[corner], fx, fy, cx, cy)
            if J is not None:
                # Invert Jacobian to get ground offset from pixel offset
                try:
                    J_inv = np.linalg.inv(J)
                    de, dn = J_inv @ np.array([du, dv])
                    ground_m_errors.append(math.sqrt(de * de + dn * dn))
                except np.linalg.LinAlgError:
                    pass

        if ground_m_errors:
            ge = np.array(ground_m_errors)
            print(f"  Ground error (Jacobian): mean={np.mean(ge):.2f}m  "
                  f"max={np.max(ge):.2f}m  rms={np.sqrt(np.mean(ge**2)):.2f}m")
            results["ground_error_jacobian"] = {
                "mean_m": round(float(np.mean(ge)), 3),
                "max_m": round(float(np.max(ge)), 3),
                "rms_m": round(float(np.sqrt(np.mean(ge ** 2))), 3),
            }
    print()

    results["anisotropy"] = {
        "mean_ratio": round(float(np.mean(aniso_vals)), 3) if ground_errors else None,
        "mean_fine_cm_per_px": round(float(np.mean(fine_vals)) * 100, 3) if ground_errors else None,
        "mean_coarse_cm_per_px": round(float(np.mean(coarse_vals)) * 100, 3) if ground_errors else None,
    }

    # ── Phase 3: Joint least-squares optimization ────────────────────
    print("Phase 3: Joint Optimization (DFOV + yaw_bias + pitch_bias + dE + dN)")
    print("-" * 52)

    if not SCIPY_AVAILABLE:
        print("  scipy not available; skipping optimization.")
        print("  Install via: pip install scipy")
        results["joint_fit"] = {"status": "skipped", "reason": "scipy not installed"}
    else:
        # Initial guess: sweep-optimal DFOV, zero biases
        x0 = np.array([best_dfov_sweep, 0.0, 0.0, 0.0, 0.0])

        res = minimize(
            total_error_for_params,
            x0,
            args=(cameras_utm, corners_utm, CORNER_PIXELS),
            method="Nelder-Mead",
            options={"xatol": 0.01, "fatol": 0.1, "maxiter": 5000},
        )

        opt_dfov, opt_yaw_b, opt_pitch_b, opt_dx, opt_dy = res.x
        opt_residuals, opt_perms = residuals_for_params(
            cameras_utm, corners_utm, CORNER_PIXELS,
            opt_dfov, opt_yaw_b, opt_pitch_b, opt_dx, opt_dy,
        )
        opt_errors = np.array([r[4] for r in opt_residuals])
        opt_du = np.array([r[2] for r in opt_residuals])
        opt_dv = np.array([r[3] for r in opt_residuals])

        print(f"  Converged: {res.success}  (iterations: {res.nit})")
        print()
        print(f"  Fitted parameters:")
        print(f"    DFOV:       {opt_dfov:.2f} deg  (was {best_dfov_sweep:.1f})")
        print(f"    yaw_bias:   {opt_yaw_b:+.3f} deg")
        print(f"    pitch_bias: {opt_pitch_b:+.3f} deg")
        print(f"    dE (east):  {opt_dx:+.3f} m")
        print(f"    dN (north): {opt_dy:+.3f} m")
        print()
        print(f"  Residuals after fit:")
        print(f"    mean={np.mean(opt_errors):.1f}  median={np.median(opt_errors):.1f}  "
              f"max={np.max(opt_errors):.1f}  rms={np.sqrt(np.mean(opt_errors**2)):.1f} px")
        print(f"    du: mean={np.mean(opt_du):+.1f}  std={np.std(opt_du):.1f}")
        print(f"    dv: mean={np.mean(opt_dv):+.1f}  std={np.std(opt_dv):.1f}")
        print()

        # Per-image breakdown after joint fit
        opt_hfov, opt_vfov = hv_from_dfov(opt_dfov, IMG_W, IMG_H)
        opt_fx, opt_fy, opt_cx, opt_cy = intrinsics_from_fov(
            opt_hfov, opt_vfov, IMG_W, IMG_H)

        print(f"  Per-image errors after joint fit:")
        opt_frame_res = {}
        for frame, corner, du, dv, err in opt_residuals:
            opt_frame_res.setdefault(frame, []).append(err)
        for cam in cameras_utm:
            fr_errs = opt_frame_res.get(cam["frame"], [])
            if fr_errs:
                print(f"    {cam['frame']}: mean={np.mean(fr_errs):.1f}  "
                      f"max={max(fr_errs):.1f}")
        print()

        # Permutation consistency after fit
        print(f"  Permutation consistency after fit:")
        opt_perm_same = len(set(p for p in opt_perms if p)) == 1
        for idx, cam in enumerate(cameras_utm):
            print(f"    {cam['frame']}: {opt_perms[idx]}")
        print(f"    -> {'CONSISTENT' if opt_perm_same else 'INCONSISTENT'}")
        print()

        # Compute ground error with joint-fit Jacobian
        opt_ground_m = []
        for r in opt_residuals:
            frame, corner, du, dv, _ = r
            cam = next(c for c in cameras_utm if c["frame"] == frame)
            J, sv = ground_error_jacobian(
                cam, corners_utm[corner], opt_fx, opt_fy, opt_cx, opt_cy,
                opt_yaw_b, opt_pitch_b, opt_dx, opt_dy)
            if J is not None:
                try:
                    de, dn = np.linalg.inv(J) @ np.array([du, dv])
                    opt_ground_m.append(math.sqrt(de * de + dn * dn))
                except np.linalg.LinAlgError:
                    pass

        if opt_ground_m:
            og = np.array(opt_ground_m)
            print(f"  Ground error after fit: mean={np.mean(og):.2f}m  "
                  f"rms={np.sqrt(np.mean(og**2)):.2f}m")

        # Improvement summary
        improvement = (1 - np.mean(opt_errors) / np.mean(all_err)) * 100
        print()
        print(f"  Improvement: {np.mean(all_err):.1f} -> {np.mean(opt_errors):.1f} px  "
              f"({improvement:+.1f}%)")

        results["joint_fit"] = {
            "converged": bool(res.success),
            "iterations": int(res.nit),
            "dfov_deg": round(float(opt_dfov), 3),
            "yaw_bias_deg": round(float(opt_yaw_b), 4),
            "pitch_bias_deg": round(float(opt_pitch_b), 4),
            "dx_east_m": round(float(opt_dx), 4),
            "dy_north_m": round(float(opt_dy), 4),
            "mean_error_px": round(float(np.mean(opt_errors)), 2),
            "median_error_px": round(float(np.median(opt_errors)), 2),
            "max_error_px": round(float(np.max(opt_errors)), 2),
            "rms_error_px": round(float(np.sqrt(np.mean(opt_errors ** 2))), 2),
            "du_mean_px": round(float(np.mean(opt_du)), 2),
            "du_std_px": round(float(np.std(opt_du)), 2),
            "dv_mean_px": round(float(np.mean(opt_dv)), 2),
            "dv_std_px": round(float(np.std(opt_dv)), 2),
            "ground_error_m": round(float(np.mean(og)), 3) if opt_ground_m else None,
            "improvement_pct": round(improvement, 1),
            "permutation_consistent": opt_perm_same,
        }

    # ── Overall assessment ───────────────────────────────────────────
    print()
    print("=" * 72)
    print("Assessment")
    print("=" * 72)

    # Use joint-fit error if available, else sweep-only
    if "joint_fit" in results and results["joint_fit"].get("mean_error_px"):
        final_err = results["joint_fit"]["mean_error_px"]
        err_source = "joint fit"
    else:
        final_err = float(np.mean(all_err))
        err_source = "DFOV-only sweep"

    best_image_err = min(r["mean_error_px"]
                         for r in results["per_image"] if r["mean_error_px"])

    if final_err < 30:
        verdict = "GOOD"
        note = ("Camera model validated. Direct ray-casting georeferencing "
                "is viable without GCPs.")
    elif final_err < 80:
        verdict = "MODERATE"
        note = (f"Camera model geometry correct (best image: {best_image_err:.0f}px "
                f"from {err_source}). Useful for coarse georeferencing. "
                "Homography preferred for precision.")
    else:
        verdict = "POOR"
        note = ("Camera model accuracy insufficient for georeferencing. "
                "Investigate altitude errors, radial distortion, or timing.")

    results["assessment"] = {"verdict": verdict, "note": note, "source": err_source}
    print(f"Verdict: {verdict}")
    print(f"  {note}")
    print()

    # Compare with old DFOV=41.0
    res_41, _ = residuals_for_params(cameras_utm, corners_utm, CORNER_PIXELS, 41.0)
    err_at_41_mean = float(np.mean([r[4] for r in res_41])) if res_41 else float("inf")
    print(f"Reference: DFOV=41.0 (undocumented): {err_at_41_mean:.1f} px")
    print(f"           DFOV={best_dfov_sweep:.1f} (sweep):     {best_err_sweep:.1f} px")
    if SCIPY_AVAILABLE:
        print(f"           Joint fit:               {np.mean(opt_errors):.1f} px")
    results["dfov_sweep"]["error_at_41_deg"] = round(err_at_41_mean, 2)

    # ── Save ─────────────────────────────────────────────────────────
    out_path = Path("data/interim/camera_model_gcp_validation.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
