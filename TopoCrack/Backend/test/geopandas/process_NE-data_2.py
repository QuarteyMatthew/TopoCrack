"""
Coastline Processing with Geodetic Division and Normalization

This script:
1. Loads coastline data (WGS84 lat/lon format)
2. Divides it into fixed-length geodetic sections (accounting for Earth's curvature)
3. Normalizes each section to [0,1] x [-y, y] coordinate space for consistent analysis
4. Visualizes the original coastline, normalized sections, and re-positioned sections
"""

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import LineString
from shapely.ops import linemerge
from pyproj import CRS, Geod
from functools import lru_cache
from pyproj import Transformer

# Initialize Geod calculator using WGS84 ellipsoid (realistic Earth model)
geod = Geod(ellps="WGS84")

# ======================== SUDDIVISIONE GEODETICA ========================
# These functions divide coastlines into equal-length sections, accounting for
# Earth's curvature (geodetic distances, not simple Euclidean)

def geodetic_length(line: LineString) -> float:
    """
    Calculate the true geodetic (curved surface) length of a line on Earth.
    Uses WGS84 ellipsoid; result in meters.
    """
    return abs(geod.geometry_length(line))

def interpolate_geodetic(coords: list, distance_m: float) -> tuple:
    """
    Find a point at exactly 'distance_m' meters from the line's start.
    Walks along line segments using geodetic distances (curved Earth).
    
    Args:
        coords: List of (lon, lat) tuples forming the line
        distance_m: Target distance in meters from start
    
    Returns:
        (longitude, latitude) of the point at the target distance
    """
    accumulated = 0.0  # Distance traveled so far
    
    # Walk through each line segment
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        
        # Calculate geodetic distance and initial bearing for this segment
        az12, _, seg_len = geod.inv(lon1, lat1, lon2, lat2)
        
        # Check if target distance falls within this segment
        if accumulated + seg_len >= distance_m:
            # Calculate how far along this segment to go
            remaining = distance_m - accumulated
            # Find the exact point at that distance
            lon_new, lat_new, _ = geod.fwd(lon1, lat1, az12, remaining)
            return (lon_new, lat_new)
        
        accumulated += seg_len
    
    # If we've exhausted the line, return the endpoint
    return coords[-1]

# =================================================================================================================
# TODO: aggiungere un parametro che controlla la lunghezza minima delle sezioni al posto che calcolaro staticamente
# =================================================================================================================
def split_line_geodetic(line: LineString, section_length_m: float) -> list:
    if line is None or line.is_empty:
        return []

    if line.geom_type == 'MultiLineString':
        line = linemerge(line)
        if line.geom_type == 'MultiLineString':
            sections = []
            for part in line.geoms:
                sections.extend(split_line_geodetic(part, section_length_m))
            return sections

    total_length = geodetic_length(line)
    coords = list(line.coords)

    # Discard sections shorter than 1/10 of section_length_m
    min_length_m = section_length_m / 10
    if total_length < min_length_m:
        return []

    # Pre-calculate cumulative vertex distances
    vertex_dists = [0.0]
    for i in range(len(coords) - 1):
        _, _, seg_len = geod.inv(*coords[i], *coords[i + 1])
        vertex_dists.append(vertex_dists[-1] + seg_len)

    # Short-but-valid coastline: split in half to capture both sides
    # (e.g. small islands that are shorter than section_length_m but still meaningful)
    if total_length < section_length_m:
        mid_dist = total_length / 2
        mid_pt   = interpolate_geodetic(coords, mid_dist)

        # First half: from start to midpoint
        inner_first = [coords[0]]
        for vd, coord in zip(vertex_dists, coords):
            if 0 < vd < mid_dist:
                inner_first.append(coord)
        inner_first.append(mid_pt)

        # Second half: from midpoint to end
        inner_second = [mid_pt]
        for vd, coord in zip(vertex_dists, coords):
            if mid_dist < vd < total_length:
                inner_second.append(coord)
        inner_second.append(coords[-1])

        return [
            {
                'geometry':    LineString(inner_first),
                'section_idx': 0,
                'start_coord': coords[0],
                'end_coord':   mid_pt,
                'length_m':    mid_dist,
            },
            {
                'geometry':    LineString(inner_second),
                'section_idx': 1,
                'start_coord': mid_pt,
                'end_coord':   coords[-1],
                'length_m':    total_length - mid_dist,
            },
        ]

    n_full_sections = int(total_length // section_length_m)
    sections = []

    for i in range(n_full_sections):
        start_dist = i * section_length_m
        end_dist   = start_dist + section_length_m

        start_pt = interpolate_geodetic(coords, start_dist)
        end_pt   = interpolate_geodetic(coords, end_dist)

        inner = [start_pt]
        for vd, coord in zip(vertex_dists, coords):
            if start_dist < vd < end_dist:
                inner.append(coord)
        inner.append(end_pt)

        sections.append({
            'geometry':    LineString(inner),
            'section_idx': i,
            'start_coord': start_pt,
            'end_coord':   end_pt,
            'length_m':    section_length_m,
        })

    # Handle the remainder after the last full section
    remainder_start = n_full_sections * section_length_m
    remainder_length = total_length - remainder_start

    if remainder_length >= min_length_m:
        start_pt = interpolate_geodetic(coords, remainder_start)
        end_pt   = coords[-1]

        inner = [start_pt]
        for vd, coord in zip(vertex_dists, coords):
            if remainder_start < vd < total_length:
                inner.append(coord)
        inner.append(end_pt)

        sections.append({
            'geometry':    LineString(inner),
            'section_idx': n_full_sections,
            'start_coord': start_pt,
            'end_coord':   end_pt,
            'length_m':    remainder_length,
        })

    return sections

def explode_to_sections(gdf: gpd.GeoDataFrame, section_length_m: float) -> gpd.GeoDataFrame:
    """
    Process all coastline features: split each into sections and return as GeoDataFrame.
    
    Args:
        gdf: Input GeoDataFrame with LineString geometries (WGS84)
        section_length_m: Target section length in meters
    
    Returns:
        GeoDataFrame with one row per section (original geometry is replaced with sections)
    """
    records = []
    
    # Process each feature (coastline) in the input data
    for feat_idx, row in gdf.iterrows():
        segs = split_line_geodetic(row.geometry, section_length_m)
        
        # Add each section as a new record, preserving the feature index
        for seg in segs:
            records.append({'feat_idx': feat_idx, **seg})
    
    # Print processing summary
    print(f"  → {len(records)} sezioni create da tutte le feature (incluse le coste corte)")
    
    # Create GeoDataFrame from sections, maintaining original CRS
    return gpd.GeoDataFrame(records, crs=gdf.crs).reset_index(drop=True)


# ======================== NORMALIZZAZIONE ========================
# These functions normalize sections to a canonical [0,1] × [-y,y] coordinate system.
# This allows consistent analysis of coastline shapes regardless of their size/position.

@lru_cache
def utm_crs_for_lon(lon: float) -> CRS:
    """
    Get UTM (Universal Transverse Mercator) CRS for a given longitude.
    UTM uses meters instead of degrees, making distance calculations more accurate.
    
    Args:
        lon: Longitude (degrees, -180 to 180)
    
    Returns:
        CRS object for the appropriate UTM zone
    """
    # UTM divides Earth into 60 zones, each 6 degrees wide
    # Zone 1 is centered at lon=-177, Zone 30 at lon=-3, Zone 31 at lon=3, etc.
    zone = int((lon + 180) / 6) + 1
    # EPSG code: 32600 + zone for Northern hemisphere (32700 + zone for Southern)
    return CRS.from_epsg(32600 + zone)

def section_to_normalized_points(line: LineString, n_points: int = 100) -> np.ndarray:
    """
    Transform a coastline section into normalized coordinates [0,1] × [-y,y].
    
    Process:
    1. Project to local UTM (meters instead of degrees)
    2. Sample n_points evenly along the line
    3. Translate: start point → (0, 0)
    4. Rotate: end point → positive x-axis (y=0)
    5. Scale: end point.x → 1 (normalize chord length)
    
    Result: consistent shape representation independent of original size/orientation.
    
    Args:
        line: Shapely LineString in WGS84 (lon, lat)
        n_points: Number of points to sample (default 100)
    
    Returns:
        numpy array of shape (n_points, 2) with normalized (x, y) coordinates
    """
    # Find the center longitude of this section
    lon_center = np.mean([c[0] for c in line.coords])
    
    # Project to local UTM: lon/lat degrees → meters
    # Use a temporary GeoDataFrame to leverage geopandas projection
    utm_gdf = gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326")
    utm_gdf = utm_gdf.to_crs(utm_crs_for_lon(lon_center))
    line_m = utm_gdf.geometry.iloc[0]

    # Sample n_points evenly along the line
    distances = np.linspace(0, line_m.length, n_points)
    pts = np.array([[line_m.interpolate(d).x, line_m.interpolate(d).y]
                    for d in distances])

    # Step 1: Translate so start point is at origin
    pts -= pts[0]

    # Step 2 & 3: Rotate so that end point lies on positive x-axis
    # Calculate rotation angle to align end point to x-axis
    angle = np.arctan2(pts[-1, 1], pts[-1, 0])
    c, s = np.cos(-angle), np.sin(-angle)
    # Apply rotation matrix: [[cos, -sin], [sin, cos]]
    rotation_matrix = np.array([[c, -s], [s, c]])
    pts = (rotation_matrix @ pts.T).T

    # Enforce y=0 at start and end (numerical cleanup)
    pts[0,  1] = 0.0
    pts[-1, 1] = 0.0

    # Step 4: Scale so that x ranges from 0 to 1
    chord = pts[-1, 0]  # Distance from start to end along x-axis
    if chord < 1e-10:
        raise ValueError("Sezione degenere: start e end coincidono")

    return pts / chord

def normalize_all_sections(sections_gdf: gpd.GeoDataFrame, n_points: int = 100) -> list:
    """
    Normalize all sections to their canonical coordinate system.
    Skips degenerate sections (where start and end coincide).
    
    Args:
        sections_gdf: GeoDataFrame with section geometries
        n_points: Number of sample points per section
    
    Returns:
        List of dicts with normalized point arrays and metadata
    """
    results = []
    
    for _, row in sections_gdf.iterrows():
        try:
            # Normalize this section to [0,1] × [-y,y] space
            pts = section_to_normalized_points(row.geometry, n_points)
        except ValueError as e:
            # Skip degenerate sections
            print(f"  Sezione ({row.feat_idx}, {row.section_idx}) saltata: {e}")
            pts = None
        
        results.append({
            'feat_idx':    row.feat_idx,      # Original feature ID
            'section_idx': row.section_idx,   # Section number within feature
            'start_coord': row.start_coord,   # Original WGS84 start (for visualization)
            'end_coord':   row.end_coord,     # Original WGS84 end (for visualization)
            'pts':         pts,               # Normalized points or None if failed
        })
    
    return results

def color_for_section(feat_idx, section_idx, cmap='hsv'):
    """
    Generate a deterministic but visually distinct color for each section.
    Adjacent sections always have different colors (using hash mixing).
    
    Args:
        feat_idx: Feature index (which coastline)
        section_idx: Section index within that feature
        cmap: Colormap name (default 'hsv' gives good color spread)
    
    Returns:
        RGBA color tuple from matplotlib colormap
    """
    # Mix two indices using XOR and multiplication by large primes
    # This ensures nearby indices map to very different hash values
    # 2654435761 and 2246822519 are large primes commonly used in hashing
    h = (feat_idx * 2654435761 ^ section_idx * 2246822519) & 0xFFFFFFFF
    
    # Convert 32-bit hash to [0, 1] range for colormap
    value = h / 0xFFFFFFFF
    
    return plt.colormaps[cmap](value)


# ======================== MAIN ========================
# Load and process coastline data

# Load Natural Earth coastline data (already in WGS84, EPSG:4326)
coast = gpd.read_file("./ne_data/ne_50m_coastline/ne_50m_coastline.shp")

# Configuration: divide coastlines into 50 km sections
SECTION_LENGTH_M = 500_000  # 500 km geodetic distance

# Step 1: Split all coastlines into geodetic sections
print("Dividing coastlines into sections...")
sections_gdf = explode_to_sections(coast, section_length_m=SECTION_LENGTH_M)

# Step 2: Normalize each section to canonical [0,1] coordinate space
print("Normalizing sections...")
normalized = normalize_all_sections(sections_gdf, n_points=20)

# ======================== VISUALIZATION ========================

# Step 3: Generate deterministic colors for each section
colors = [color_for_section(item['feat_idx'], item['section_idx']) for item in normalized]

print("Creating visualization...")
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# --- Plot 1: Original coastlines (WGS84 coordinates) ---
coast.plot(ax=axes[0], color='steelblue', lw=0.5)
axes[0].set_title("Costa originale (WGS84)")
axes[0].set_aspect('equal')

# --- Plot 2: Sections reprojected back to WGS84 ---
# Fix: invert the normalization in UTM space (meters), then convert to WGS84.
# Doing it in lon/lat space (as before) causes severe distortion near the poles
# because degrees of longitude shrink dramatically at high latitudes.
coast.plot(ax=axes[1], color='lightgray', lw=0.4, zorder=1)

for item, color in zip(normalized, colors):
    if item['pts'] is None:
        continue

    start_lonlat = item['start_coord']
    end_lonlat   = item['end_coord']

    # Use the same UTM zone that was used during normalization
    lon_center = (start_lonlat[0] + end_lonlat[0]) / 2
    utm_crs = utm_crs_for_lon(lon_center)

    to_utm  = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    to_wgs  = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

    # Convert start and end to UTM (meters) — same space the normalization used
    start_utm = np.array(to_utm.transform(start_lonlat[0], start_lonlat[1]))
    end_utm   = np.array(to_utm.transform(end_lonlat[0],   end_lonlat[1]))

    chord_vec = end_utm - start_utm
    chord_len = np.linalg.norm(chord_vec)
    angle     = np.arctan2(chord_vec[1], chord_vec[0])

    c, s  = np.cos(angle), np.sin(angle)
    R_inv = np.array([[c, -s], [s, c]])

    # 1. Scale by UTM chord length  2. Rotate back  3. Translate to UTM start
    pts_utm = (R_inv @ (item['pts'] * chord_len).T).T + start_utm

    # Convert UTM coordinates back to WGS84 lon/lat
    lons, lats = to_wgs.transform(pts_utm[:, 0], pts_utm[:, 1])

    axes[1].plot(lons, lats, lw=1.0, alpha=0.6, color=color, rasterized=True)

axes[1].set_title("Sezioni riposizionate (WGS84)")
axes[1].set_aspect('equal')
axes[1].set_xlabel("Longitudine")
axes[1].set_ylabel("Latitudine")

plt.tight_layout()
plt.show()