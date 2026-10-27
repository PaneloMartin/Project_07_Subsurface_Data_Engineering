
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import urlparse
import pandas as pd

project_dir = Path(__file__).resolve().parent.parent
catalog_path = project_dir / "data" / "catalog" / "ks_las_files.zip"
raw_dir = project_dir / "data" / "raw"
processed_dir = project_dir / "data" / "processed"

processed_dir.mkdir(parents=True, exist_ok=True)

# Leer el catalogo del KGS
with ZipFile(catalog_path) as archive:
    with archive.open("ks_las_files.txt") as file:
        catalog = pd.read_csv(file, dtype=str)

# Extraer file_id desde la URL
catalog["file_id"] = (
    catalog["URL"].str.extract(r"/([^/]+)\.las$", expand=False)
)

# Identificar archivos descargados
local_files = {
    file.stem: file
    for file in raw_dir.glob("*.las")
}

# Seleccionar los archivos presentes localmente
logs = catalog[
    catalog["file_id"].isin(local_files)
].copy()

# Conservar un registro por archivo
logs = logs.drop_duplicates(subset=["file_id"])

# Incorporar el tamaño real de cada archivo
logs["file_size_bytes"] = logs["file_id"].map(
    lambda file_id: local_files[file_id].stat().st_size
)

# Construir URL de descarga actual
logs["download_url"] = logs["URL"].str.replace(
    "https://www.kgs.ku.edu/b_1/",
    "https://kgsimages.blob.core.windows.net/web/web_1/",
    regex=False,
)

logs = logs[
    [
        "file_id",
        "KGS_ID",
        "URL",
        "download_url",
        "Depth_start",
        "Depth_stop",
        "file_size_bytes",
    ]
].copy()

logs.columns = [
    "file_id",
    "kgs_id",
    "catalog_url",
    "download_url",
    "depth_start",
    "depth_stop",
    "file_size_bytes",
]

output_path = processed_dir / "log_files.csv"
logs.to_csv(output_path, index=False)

print("PROJECT 07 - LOG FILES TABLE")
print("--------------------------------")
print(f"Archivos registrados: {len(logs)}")
print(f"Pozos relacionados: {logs['kgs_id'].nunique()}")
print(f"Archivo generado: {output_path.name}")

print("\nPRIMEROS 5 ARCHIVOS")
print("--------------------------------")
print(
    logs[
        ["file_id", "kgs_id", "depth_start", "depth_stop"]
    ].head().to_string(index=False)
)
