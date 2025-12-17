#!/usr/bin/env python3
"""
San Lorenzo Penguin Count Analysis

Analyzes GPS waypoints from Argentina field data to calculate:
- Polygon areas for each counted zone
- Penguin densities (penguins/ha)
- Comparison with LiDAR/thermal detection targets

Ground truth counts from PDF:
- Caves: 908 penguins
- Plains: 453 penguins
- Road: 359 penguins
- Box Count Caves: 32 penguins
- Box Count Bushes: 55 penguins
"""

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

# Prefer PROJ via pyproj when available for accurate projections.
try:
    from pyproj import Transformer  # type: ignore

    _WGS84_TO_UTM20S = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)
except Exception:
    _WGS84_TO_UTM20S = None

# UTM Zone 20S parameters for Argentina (used by the fallback implementation)
UTM_ZONE = 20
UTM_SOUTH = True

@dataclass
class CountedArea:
    name: str
    penguin_count: int
    area_m2: Optional[float] = None
    area_ha: Optional[float] = None
    density_per_ha: Optional[float] = None
    boundary_points: Optional[List[Tuple[float, float]]] = None
    notes: str = ""

def wgs84_to_utm_series(lat: float, lon: float, zone: Optional[int] = None, south: Optional[bool] = None) -> Tuple[float, float]:
    """
    Convert WGS84 lat/lon to UTM easting/northing (WGS84 ellipsoid).

    Notes:
    - This is a local, series-expansion implementation (not PROJ). It's adequate for
      small-area measurements (e.g. polygon area in Argentina) but is not intended
      as a general-purpose geodesy library.
    - UTM is defined roughly for latitudes [-80, 84] degrees. Outside that range,
      use UPS instead.
    """
    # Validate UTM latitude range (standard UTM; UPS handles the poles)
    if not (-80.0 <= lat <= 84.0):
        raise ValueError(f"UTM is defined roughly for latitudes [-80, 84]. Got lat={lat}.")

    # Normalize longitude to [-180, 180) for consistent zone computation.
    lon_norm = ((lon + 180.0) % 360.0) - 180.0

    # Determine zone if not provided (1..60)
    if zone is None:
        zone = int((lon_norm + 180.0) // 6.0) + 1
    if not (1 <= zone <= 60):
        raise ValueError(f"UTM zone must be in [1, 60]. Got zone={zone}.")

    # Determine hemisphere if not provided
    is_south = (lat < 0.0) if south is None else bool(south)

    # Central meridian for zone: lon0 = -183 + 6*zone (degrees)
    central_meridian = -183.0 + 6.0 * zone

    # Scale factor
    k0 = 0.9996

    # WGS84 parameters
    a = 6378137.0  # equatorial radius
    f = 1 / 298.257223563  # flattening
    e2 = 2 * f - f * f  # eccentricity squared

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon_norm)
    lon0_rad = math.radians(central_meridian)

    # Calculate N (radius of curvature)
    N = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)

    # Calculate T, C, A, M
    T = math.tan(lat_rad) ** 2
    C = e2 / (1 - e2) * math.cos(lat_rad) ** 2
    A = (lon_rad - lon0_rad) * math.cos(lat_rad)

    # Calculate M (meridional arc)
    e4 = e2 * e2
    e6 = e4 * e2
    M = a * ((1 - e2/4 - 3*e4/64 - 5*e6/256) * lat_rad
             - (3*e2/8 + 3*e4/32 + 45*e6/1024) * math.sin(2*lat_rad)
             + (15*e4/256 + 45*e6/1024) * math.sin(4*lat_rad)
             - (35*e6/3072) * math.sin(6*lat_rad))

    # Calculate easting
    x = k0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58*e2/(1-e2))*A**5/120)
    easting = x + 500000  # False easting

    # Calculate northing
    y = k0 * (M + N * math.tan(lat_rad) * (A**2/2 + (5-T+9*C+4*C**2)*A**4/24
              + (61-58*T+T**2+600*C-330*e2/(1-e2))*A**6/720))

    # False northing for southern hemisphere
    northing = y + 10000000 if is_south else y

    return easting, northing


def wgs84_to_utm(lat: float, lon: float) -> Tuple[float, float]:
    """Convert WGS84 lat/lon to UTM Zone 20S (EPSG:32720)."""
    if _WGS84_TO_UTM20S is not None:
        easting, northing = _WGS84_TO_UTM20S.transform(lon, lat)
        return float(easting), float(northing)
    return wgs84_to_utm_series(lat, lon, zone=UTM_ZONE, south=UTM_SOUTH)


def polygon_area_utm(points: List[Tuple[float, float]]) -> float:
    """Calculate polygon area using shoelace formula on UTM coordinates."""
    if len(points) < 3:
        return 0.0

    # Convert to UTM meters
    utm_points = [wgs84_to_utm(lat, lon) for lat, lon in points]

    # Shoelace formula
    n = len(utm_points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += utm_points[i][0] * utm_points[j][1]
        area -= utm_points[j][0] * utm_points[i][1]

    return abs(area) / 2.0

def convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Compute convex hull of lat/lon points.

    Implementation detail:
    - We project to UTM (zone 20S for Argentina) first and run a 2D monotone-chain
      hull in meters. This avoids subtle mistakes in spherical coordinates and
      fixes issues in the previous hull implementation (inconsistent angle/cross math).
    """
    if len(points) < 3:
        return points

    # Project lat/lon to UTM so hull math is in meters.
    pts = []
    for lat, lon in points:
        x, y = wgs84_to_utm(lat, lon)
        pts.append((x, y, lat, lon))

    # Sort by x then y (monotone chain requirement)
    pts.sort(key=lambda p: (p[0], p[1]))

    def cross(o, a, b) -> float:
        # Cross product of OA x OB in 2D (x,y) space
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Build lower hull
    lower: List[Tuple[float, float, float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper: List[Tuple[float, float, float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Concatenate, removing duplicate endpoints
    hull = lower[:-1] + upper[:-1]
    return [(lat, lon) for _, _, lat, lon in hull]

def load_waypoints(csv_path: Path) -> dict:
    """Load waypoints from CSV file."""
    waypoints = {'caves': [], 'plains': [], 'road': []}

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            zone = row.get('zone', '').strip()
            if row['lat'] and row['lon']:
                lat = float(row['lat'])
                lon = float(row['lon'])
                if zone not in waypoints:
                    waypoints[zone] = []
                waypoints[zone].append((lat, lon))

    return waypoints

def analyze_san_lorenzo():
    """Main analysis function."""

    # Ground truth counts from field notes
    ground_truth = {
        'caves': CountedArea(
            name="High Density Caves",
            penguin_count=908,
            notes="Start/end waypoints + right edge points"
        ),
        'plains': CountedArea(
            name="The Plains",
            penguin_count=453,
            notes="Top and bottom edge waypoints available"
        ),
        'road': CountedArea(
            name="The Road",
            penguin_count=359,
            notes="Waypoints not documented in PDF"
        ),
        'box_caves': CountedArea(
            name="Box Count High Density Caves",
            penguin_count=32,
            area_m2=11539.75,  # From PDF: 124,212.85 ft² = 11,539.75 m²
            notes="2 walked out between thermal and LiDAR"
        ),
        'box_bushes': CountedArea(
            name="Box Count High Density Bushes",
            penguin_count=55,
            area_m2=37983.65,  # From PDF: 408,852.64 ft² = 37,983.65 m²
            notes="Rectangular area"
        ),
    }

    # Load waypoints
    csv_path = Path(__file__).parent.parent / "data/processed/san_lorenzo_waypoints.csv"
    if csv_path.exists():
        waypoints = load_waypoints(csv_path)
    else:
        # Use embedded waypoints
        waypoints = {
            'caves': [
                (-42.086263, -63.874072), (-42.086285, -63.874350),  # Start
                (-42.086656, -63.873951), (-42.087376, -63.873872),  # Right edge
                (-42.087740, -63.873728), (-42.088702, -63.873419),
                (-42.088878, -63.873310), (-42.089107, -63.873427),  # End
            ],
            'plains': [
                # Top edge
                (-42.084360, -63.867691), (-42.084418, -63.868053),
                (-42.084467, -63.868250), (-42.084534, -63.868537),
                (-42.084587, -63.868683), (-42.084671, -63.868935),
                (-42.084725, -63.869125), (-42.084772, -63.869388),
                (-42.084836, -63.869808), (-42.084864, -63.869953),
                (-42.084915, -63.870255), (-42.084953, -63.870431),
                (-42.085021, -63.870748),
                # Bottom edge (selected points for boundary)
                (-42.085187, -63.870152), (-42.085151, -63.869924),
                (-42.085090, -63.869588), (-42.085004, -63.869279),
                (-42.084942, -63.869132), (-42.084867, -63.868800),
                (-42.084776, -63.868289), (-42.084658, -63.867900),
                (-42.084520, -63.867496),
            ],
            'road': [],  # No waypoints documented
        }

    print("=" * 70)
    print("SAN LORENZO PENGUIN COUNT ANALYSIS")
    print("=" * 70)
    print()

    # Calculate areas from waypoints
    for zone_name, zone_data in ground_truth.items():
        if zone_name in waypoints and waypoints[zone_name]:
            points = waypoints[zone_name]
            hull = convex_hull(points)
            area_m2 = polygon_area_utm(hull)
            zone_data.area_m2 = area_m2
            zone_data.boundary_points = hull

        # Calculate derived values
        if zone_data.area_m2:
            zone_data.area_ha = zone_data.area_m2 / 10000
            zone_data.density_per_ha = zone_data.penguin_count / zone_data.area_ha

    # Print results
    print("COUNTED AREAS:")
    print("-" * 70)

    total_penguins = 0
    total_area_ha = 0

    for zone_name, zone_data in ground_truth.items():
        print(f"\n{zone_data.name}:")
        print(f"  Penguin count: {zone_data.penguin_count}")

        if zone_data.area_m2:
            print(f"  Area: {zone_data.area_m2:,.1f} m² ({zone_data.area_ha:.3f} ha)")
            print(f"  Density: {zone_data.density_per_ha:.1f} penguins/ha")
            total_area_ha += zone_data.area_ha
        else:
            print("  Area: Not computed (insufficient waypoints)")

        if zone_data.notes:
            print(f"  Notes: {zone_data.notes}")

        total_penguins += zone_data.penguin_count

    # Summary statistics
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTotal penguins (San Lorenzo): {total_penguins}")
    print(f"Total counted area: {total_area_ha:.2f} ha")
    if total_area_ha > 0:
        print(f"Average density: {total_penguins / total_area_ha:.1f} penguins/ha")

    # Compare to Caleta sites
    print()
    print("-" * 70)
    print("COMPARISON WITH CALETA SITES:")
    print("-" * 70)
    caleta = {
        'tiny_island': CountedArea("Tiny Island", 321, area_ha=0.7),
        'small_island': CountedArea("Small Island", 1557, area_ha=4.0),
        'box_1': CountedArea("Box Count 1", 8),
        'box_2': CountedArea("Box Count 2", 12),
    }

    for name, data in caleta.items():
        if data.area_ha:
            data.density_per_ha = data.penguin_count / data.area_ha
            print(f"{data.name}: {data.penguin_count} penguins, {data.area_ha} ha, "
                  f"{data.density_per_ha:.1f} penguins/ha")
        else:
            print(f"{data.name}: {data.penguin_count} penguins")

    # Grand total
    caleta_total = sum(d.penguin_count for d in caleta.values())
    grand_total = total_penguins + caleta_total

    print()
    print("=" * 70)
    print("GRAND TOTAL (ALL SITES)")
    print("=" * 70)
    print(f"\nSan Lorenzo: {total_penguins} penguins")
    print(f"Caleta: {caleta_total} penguins")
    print(f"TOTAL: {grand_total} penguins")

    # Detection pipeline targets
    print()
    print("-" * 70)
    print("DETECTION PIPELINE IMPLICATIONS:")
    print("-" * 70)
    print(f"\nLegacy target (Punta Tombo): 1,533 penguins")
    print(f"New Argentina total: {grand_total} penguins")
    print(f"Difference: +{grand_total - 1533} penguins ({(grand_total/1533 - 1)*100:.1f}% increase)")

    # Density-based detection thresholds
    print()
    print("Density ranges observed:")
    densities = []
    for zone in list(ground_truth.values()) + list(caleta.values()):
        if zone.density_per_ha:
            densities.append((zone.name, zone.density_per_ha))

    densities.sort(key=lambda x: x[1])
    for name, density in densities:
        print(f"  {name}: {density:.1f} penguins/ha")

    if densities:
        min_d = min(d for _, d in densities)
        max_d = max(d for _, d in densities)
        print(f"\nRange: {min_d:.1f} - {max_d:.1f} penguins/ha")

    # Output JSON for pipeline integration
    output = {
        'san_lorenzo': {
            zone: {
                'name': data.name,
                'penguin_count': data.penguin_count,
                'area_m2': data.area_m2,
                'area_ha': data.area_ha,
                'density_per_ha': data.density_per_ha,
                'notes': data.notes
            }
            for zone, data in ground_truth.items()
        },
        'caleta': {
            zone: {
                'name': data.name,
                'penguin_count': data.penguin_count,
                'area_ha': data.area_ha,
                'density_per_ha': data.density_per_ha
            }
            for zone, data in caleta.items()
        },
        'totals': {
            'san_lorenzo': total_penguins,
            'caleta': caleta_total,
            'grand_total': grand_total,
            'legacy_target': 1533
        }
    }

    output_path = Path(__file__).parent.parent / "data/processed/san_lorenzo_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nAnalysis saved to: {output_path}")

    return output

if __name__ == "__main__":
    analyze_san_lorenzo()
