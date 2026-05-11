import math
import numpy as np
import matplotlib.pyplot as plt
import pickle

def swap_coords(points: np.ndarray) -> np.ndarray:
    return points[:, [1, 0]]

def translate_to_origin(points: np.ndarray) -> np.ndarray:
    return points - points[0]

def rotate_to_horizontal(points: np.ndarray) -> np.ndarray:
    # Get original starting point
    start = points[0]

    end = points[-1]
    
    # Calculate angle to horizontal
    angle = math.atan2(end[1], end[0])
    
    # Rotation matrix
    c, s = np.cos(-angle), np.sin(-angle)
    rotation_matrix = np.array([[c, -s], [s, c]])
    
    # Apply rotation to all points
    return np.dot(points, rotation_matrix.T) 

def scale_x_0_to_1(points: np.ndarray) -> np.ndarray:
    # Requires the set of points to start at origin (0, 0)
    
    start = points[0]
    end = points[-1]
    
    i = 0
    for p in points:
        # xp : xend = ratio : 1
        # yp : xp = m : ratio
        
        ratio = p[0] / end[0]
        if p[0] != 0:
            p = [ratio, ratio * p[1] / p[0]]
            
        points[i] = p
        i += 1;
    
    return points

def prepare_points_for_dtw(points: np.ndarray) -> np.ndarray:
    return scale_x_0_to_1(rotate_to_horizontal(translate_to_origin(points)))

def dtw_cost(points_a: np.ndarray, points_b: np.ndarray) -> float:
    n, m = len(points_a), len(points_b)
    cost_matrix = np.full((n + 1, m + 1), np.inf, dtype=float)
    cost_matrix[0, 0] = 0.0
    
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            distance = np.linalg.norm(points_a[i - 1] - points_b[j - 1])
            cost_matrix[i, j] = distance + min(
                cost_matrix[i - 1, j],    # Insertion
                cost_matrix[i, j - 1],    # deletion
                cost_matrix[i - 1, j - 1] # match
            )
    
    return float(cost_matrix[n, m])

def find_top3_costs(points: np.ndarray, coastal_data: list) -> list:
    scores = [];
    
    for coast in coastal_data:
        pts = coast.get("pts")
        if pts is None:
            continue
        
        cost = dtw_cost(points, pts)
        
        feat = coast["feat_idx"]
        section = coast["section_idx"]
        
        result = {
            "feat_id": feat,
            "section_id": section,
            "name": f"Costa {feat} - Sezione {section}",
            "score": float(cost),
            "pts": pts
        }
        scores.append(result)
    
    scores.sort(key=lambda x: x["score"])
    return scores[:3]

def plot_top3_matches(top3: list):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    
    for ax, item in zip(axes, top3):
        pts = item["pts"]
        ax.plot(pts[:, 0], pts[:, 1], color="blue")
        ax.axhline(0, color="gray", linestyle="--", linewidth=0.7)
        ax.set_title(f"{item['name']}\nscore {item['score']:.6f}")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x normalizzato")
    
    axes[0].set_ylabel("y normalizzato")
    plt.tight_layout()
    plt.show()

def plot_top3_with_target(target_pts: np.ndarray, top3: list):
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(target_pts[:, 0], target_pts[:, 1], label="Path utente", color="black", linewidth=2)
    
    for item in top3:
        pts = item["pts"]
        ax.plot(pts[:, 0], pts[:, 1], label=f"{item['name']} ({item['score']:.4f})")
    
    ax.set_aspect("equal", adjustable="box")
    ax.legend()
    ax.set_title("Top 3 coste più simili")
    plt.show()

# ======================== LOAD PROCESSED DATA ========================
#
# Data structure:
# {
#     'feat_idx':    int,           # Original feature ID
#     'section_idx': int,           # Section number within feature
#     'start_coord': (lon, lat),    # Original WGS84 start point
#     'end_coord':   (lon, lat),    # Original WGS84 end point
#     'pts':         np.ndarray,    # Normalized points [[0,1] × [-y,y], ...]
# }

data_path = "../geopandas/normalized_sections/n_s_1.pkl"

print("Loading costal data...")

with open(data_path, 'rb') as f:
  costal_data = pickle.load(f)

print("Costal data loaded!")

# ========= PREPARING COMPARISON EXAMPLE LINE FOR DTW =========
example_line_path = "example_line_Y-X.bin"

print("Loading example data...")

with open(example_line_path, 'rb') as f:
    # comp_line = swap_coords(pickle.load(f))
    comp_line = pickle.load(f)
    
print("Example data loaded!")

prepared_line = prepare_points_for_dtw(comp_line)

# ==================== PLOT AND SHOW DATA ====================
_, (ax1, ax2) = plt.subplots(1, 2) # 1 row, 2 columns

# Transpose to get (x_coords, y_coords)
yc, xc = comp_line.T
yc = (1 - yc)
ax1.plot(xc, yc)
ax1.set_title('comp_line')
ax1.axis("equal")

# Transpose to get (x_coords, y_coords)
xp, yp = prepared_line.T
ax2.plot(xp, yp)
ax2.set_title('prepared_line')
ax2.axis("equal")

plt.show()

# ================ DYNAMIC TIME WARPING (DTW) ================
# Risultato: 3 coste che assomigliano di più al path selezionato dall'utente
print("Finding the 3 most similar coasts...")
top3 = find_top3_costs(prepared_line, costal_data)

print("The 3 most similar coasts:")

for coast in top3:
    print(f"Feat ID: {coast["feat_id"]}")
    print(f"Section ID: {coast["section_id"]}")
    print(f"Name: {coast["name"]}")
    print(f"Score: {coast["score"]:.6f}")
    
    coast_data = next(
    (item for item in costal_data 
        if item['feat_idx'] == coast["feat_id"] and item['section_idx'] == coast["section_id"]),
        None
    )
    
    print(f"Coords: {coast_data.get("start_coord")}, {coast_data.get("end_coord")}\n")

plot_top3_with_target(prepared_line, top3)