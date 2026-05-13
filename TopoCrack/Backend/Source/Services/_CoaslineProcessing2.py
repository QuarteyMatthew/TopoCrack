import io
from time import sleep
import zipfile, geopandas as gpd, numpy as np, logging, requests
from pathlib import Path
from geopandas import GeoDataFrame
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

def DownloadCoastline(resolution: str = "50m", cacheDir: str = "../Cache") -> GeoDataFrame:
    cachePath = Path(cacheDir)
    coastlineDir = f"ne_{resolution}_coastline"
    coastlinePath = cachePath / coastlineDir
    dotShapePath = coastlinePath / "ne_10m_coastline.shp"
    dotShapeXPath = coastlinePath / "ne_10m_coastline.shx"
    
    if not (coastlinePath.exists() and dotShapePath.exists() and dotShapeXPath.exists()):
        if not cachePath.exists():
            logger.debug("Cache directory not found, creating it at '%s'...", cachePath)
            cachePath.mkdir(parents=True, exist_ok=True)
        
        logger.info("Coastal data not found in cache. Starting download (resolution=%s)...", resolution)
        downloadURL = f"https://naturalearth.s3.amazonaws.com/{resolution}_physical/{coastlineDir}.zip"
        logger.debug("Download URL: %s", downloadURL)
        
        req = requests.get(downloadURL)
        req.raise_for_status()
        logger.info("Download complete (%.1f MB). Extracting archive...", len(req.content) / 1_000_000)
        
        with zipfile.ZipFile(io.BytesIO(req.content)) as zipFile:
            zipFile.extractall(coastlinePath)
            
        # Rimozione dei file non necessari: logghiamo quanti ne eliminiamo
        # così è facile accorgersi se il formato del pacchetto cambia in futuro.
        removedCount = 0
        suffices = [".cpg", ".dbf", ".prj", ".html", ".txt"]
        for neFile in coastlinePath.iterdir():
            if not neFile.is_file():
                continue
            if neFile.suffix.lower() in suffices:
                neFile.unlink()
                removedCount += 1
        logger.debug("Removed %d unnecessary files from the archive.", removedCount)
    else:
        # I file sono già stati scaricati
        logger.info("Coastal data found in cache, skipping download.")
    
    shapeFile = next(coastlinePath.glob("*.shp"))
    logger.debug("Reading shapefile: '%s'", shapeFile)
    coastlines = gpd.read_file(shapeFile)
    logger.info("Shapefile loaded: %d coastline features.", len(coastlines))
    
    return coastlines

def SampleCoast(geoData: GeoDataFrame, nPoints: int) -> list:
  coasts = []
  
  
  return coasts

print("Getting coastlines...")
gdf = DownloadCoastline(resolution="50m")
# print(gdf.columns)      # List all columns
# print(gdf.info())       # Detailed info
# print(gdf.crs)          # Coordinate reference system
# print(gdf.geometry.type)  # Geometry types
# print(gdf.head())       # First few rows

# ========= PLOT ONE COAST AT A TIME =========

_, ax = plt.subplots(figsize=(12, 8))

for idx, row in gdf.iterrows():
  # costline = row['geometry']
  
  color = np.random.rand(3,)
  
  # Plot the line
  gpd.GeoDataFrame([row], geometry='geometry', crs=gdf.crs).plot(ax=ax, color=color)

plt.show()