import math
import numpy as np
import matplotlib.pyplot as plt
import pickle

def swap_coords(points: np.ndarray) -> np.ndarray:
    for p in points:
        p = [p[1], p[0]]
        
    return points

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
    
    for p in points:
        # xp : xend = ratio : 1
        # yp : xp = m : ratio
        
        ratio = p[0]/end[0]
        if p[0] != 0:
            p = [ratio, ratio*p[1]/p[0]]
    
    return points

def prepare_points_for_dtw(points: np.ndarray) -> np.ndarray:
    return scale_x_0_to_1(rotate_to_horizontal(translate_to_origin(points)))

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
    comp_line = swap_coords(pickle.load(f))

print("Example data loaded!")

prepared_line = prepare_points_for_dtw(comp_line)

# ==================== PLOT AND SHOW DATA ====================
_, (ax1, ax2) = plt.subplots(1, 2) # 1 row, 2 columns

# Transpose to get (x_coords, y_coords)
xc, yc = comp_line.T
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
