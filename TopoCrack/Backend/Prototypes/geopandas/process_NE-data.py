import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import LineString, box
from shapely.ops import substring, linemerge

# ----------- Dividere in sezioni di uguale lunghezza -----------
def split_line_equal_sections(line: LineString, n_sections: int) -> list:
  # Divide una LineString in 'n_sections' parti di uguale lunghezza.
  # Preserva le coordinate originali (in CRS corrente) di start e end
  # di ogni sezione come attributi.
  if line.geom_type == 'MultiLineString':
    line = linemerge(line)
    # Se 'lineimage' no  riesce ad unire (linee non connesse),
    # processa ogni parte separatamente
    if line.geom_type == 'MultiLineString':
      sections = []
      for part in line.geoms:
        sections.extend(split_line_equal_sections(part, n_sections))
      return sections
  
  total_length = line.length
  section_length = total_length / n_sections
  
  sections = []
  for i in range(n_sections):
    start_dist = i * section_length
    end_dist = (i + 1) * section_length
    seg = substring(line, start_dist, end_dist)
    sections.append({
      'geometry':     seg,
      'section_idx':  i,
      'start_coord':  seg.coords[0], # (x, y) in metri UTM
      'end_coord':    seg.coords[-1],  # (x, y) in metri UTM
      'length_m':     seg.length,
    })
  return sections

def explode_to_sections(gdf: gpd.GeoDataFrame, n_sections: int) -> gpd.GeoDataFrame:
  records = []
  for feat_idx, row in gdf.iterrows():
    segs = split_line_equal_sections(row.geometry, n_sections)
    for seg in segs:
      rec = {'feat_idx': feat_idx, **seg}
      records.append(rec)
  return gpd.GeoDataFrame(records, crs=gdf.crs).reset_index(drop=True)


# ----------- Convertire ogni sezione in punti, ruotare e scalare -----------
def section_to_normalized_points(line: LineString, n_points: int = 100) -> np.ndarray:
  # Dato un segmento di costa (LineString in metri):
  #   1. Campiona n_points punti equidistanti
  #   2. Trasla: start → origine (0, 0)
  #   3. Ruota: end → asse x positivo  →  start.y = end.y = 0
  #   4. Scala: end.x → 1             →  x ∈ [0, 1]

  # Returns:
  #     pts (n_points, 2): array normalizzato
  # 1. Campionamento
  distances = np.linspace(0, line.length, n_points)
  pts = np.array([[line.interpolate(d).x, line.interpolate(d).y]
                  for d in distances])
  
  # 2. Traslazione
  pts = pts - pts[0]
  
  # 3. Rotazione - allinea il vettore start->end con l'asse x
  angle = np.arctan2(pts[-1, 1], pts[-1, 0])
  c, s  = np.cos(-angle), np.sin(-angle)
  R     = np.array([[c, -s], [s, c]])
  pts   = (R @ pts.T).T
  
  # Forza y=0 esatto per start e end (per compensare possibili errori numerici floating point)
  pts[0,  1] = 0.0
  pts[-1, 1] = 0.0
  
  # 4. Scalatura - divide per la lunghezza della corda (distanza start-end)
  chord = pts[-1, 0]
  if chord < 1e-10:
    raise ValueError("Sezione degenere: start e end coincidono dopo rotazione")
  pts = pts / chord # x in [0,1], y in unità relative alla corda
  
  return pts

def normalize_all_sections(sections_gdf: gpd.GeoDataFrame, n_points: int = 100) -> list:
  results = []
  for _, row in sections_gdf.iterrows():
    try:
      pts = section_to_normalized_points(row.geometry, n_points)
    except ValueError as e:
      print(f"  Sezione ({row.feat_idx}, {row.section_idx}) saltata: {e}")
      pts = None
    results.append({
      'feat_idx':    row.feat_idx,
      'section_idx': row.section_idx,
      'start_coord': row.start_coord,  # coordinate originali UTM preservate
      'end_coord':   row.end_coord,
      'pts':         pts,
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


# Carica da cache (scaricato con download_and_cache_NE-data.py)
coast = gpd.read_file("./ne_data/ne_10m_coastline/ne_10m_coastline.shp")

# Ritaglia esattamente alla bounding box (lon_min, lat_min, lon_max, lat_max)
bbox_italia = (5.93, 34.76, 18.99, 47.10)
coast_ita = coast.clip(box(*bbox_italia)).reset_index(drop=True)
print(f"{len(coast_ita)} segmenti di costa nell'area")

# Riproietta in metri (UTM 32N, ideale per l'Italia)
coast_m = coast_ita.to_crs(epsg=32632)

# Plot
# coast_m.plot()
# plt.show()


# ------------ Suddivisione e normalizzazione ------------
sections_gdf = explode_to_sections(coast_m, n_sections=3)
normalized = normalize_all_sections(sections_gdf, n_points=50)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# --- Sinistra: costa originale ---
coast_m.plot(ax=axes[0], color='steelblue', lw=0.8)
axes[0].set_title("Costa originale (UTM 32N)")
axes[0].set_aspect('equal')


colors = [color_for_section(item['feat_idx'], item['section_idx']) for item in normalized]

# --- Destra: sezioni normalizzate sovrapposte ---
for item, color in zip(normalized, colors):
    if item['pts'] is not None:
        pts = item['pts']
        axes[1].plot(pts[:, 0], pts[:, 1], alpha=0.4, lw=0.8, color=color)

axes[1].axhline(0, color='red', lw=1, ls='--', label='y = 0 (start / end)')
axes[1].scatter([0, 1], [0, 0], color='red', zorder=5)
axes[1].set_xlim(-5, 5)
axes[1].set_xlabel("x normalizzato  [0 = start, 1 = end]")
axes[1].set_ylabel("y  (deviazione laterale relativa)")
axes[1].set_title("Sezioni normalizzate")
axes[1].legend()

plt.tight_layout()
plt.show()

# sections_gdf = explode_to_sections(coast_m, n_sections=20)
