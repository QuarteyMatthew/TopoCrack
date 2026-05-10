# Downloading and caching the Natural Earth coasts data

import geopandas as gpd
import requests, zipfile, io
from pathlib import Path

def download_coastline(resolution='50m', cache_dir='./ne_data'):
  # Risoluzioni: 10m (dettaglio), 50m (medio), 110m (basso)
  # Categorie possibili: cultural, physical, raster
  
  Path(cache_dir).mkdir(exist_ok=True)
  fname = f"ne_{resolution}_coastline"
  local_path = Path(cache_dir) / fname

  if not local_path.exists():
      url = f"https://naturalearth.s3.amazonaws.com/{resolution}_physical/{fname}.zip"
      r = requests.get(url)
      r.raise_for_status()
      with zipfile.ZipFile(io.BytesIO(r.content)) as z:
          z.extractall(local_path)

  shp = next(local_path.glob("*.shp"))
  return gpd.read_file(shp)

coast = download_coastline(resolution='10m')