
from pathlib import Path
from zipfile import ZipFile
import pandas as pd

project_dir = Path(__file__).resolve().parent.parent
catalog_path = project_dir / "data" / "catalog" / "ks_las_files.zip"
raw_dir = project_dir / "data" / "raw"
processed_dir = project_dir / "data" / "processed"

processed_dir.mkdir(parents=True, exist_ok=True)

# Leer el catalogo original
with ZipFile(catalog_path) as archive:
    with archive.open("ks_las_files.txt") as file:
        catalog = pd.read_csv(file, dtype=str)

# Identificar los archivos LAS disponibles localmente
downloaded_ids = {
    file.stem for file in raw_dir.glob("*.las")
}

# Extraer el identificador del archivo desde su URL
catalog["file_id"] = (
    catalog["URL"]
    .str.extract(r"/([^/]+)\.las$", expand=False)
)

# Conservar solo los registros de archivos descargados
matched = catalog[
    catalog["file_id"].isin(downloaded_ids)
].copy()

# Un registro por pozo
wells = matched.drop_duplicates(subset=["KGS_ID"]).copy()

wells = wells[
    [
        "KGS_ID",
        "API",
        "Lease",
        "Operator",
        "Latitude",
        "Longitude",
        "Location",
        "Elevation",
        "Elev_Ref",
    ]
].copy()

wells.columns = [
    "kgs_id",
    "api",
    "lease",
    "operator",
    "latitude",
    "longitude",
    "location",
    "elevation",
    "elevation_reference",
]

# Normalizar campos descriptivos de texto.
# Eliminar espacios iniciales/finales y espacios repetidos.
text_columns = [
    "lease",
    "operator",
    "location",
    "elevation_reference",
]

for column in text_columns:
    wells[column] = (
        wells[column]
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

# Generar CSV procesado
output_path = processed_dir / "wells.csv"
wells.to_csv(output_path, index=False)

print("PROJECT 07 - WELLS TABLE")
print("--------------------------------")
print(f"Archivos LAS locales: {len(downloaded_ids)}")
print(f"Archivos encontrados en catalogo: {matched['file_id'].nunique()}")
print(f"Pozos unicos: {len(wells)}")
print(f"Archivo generado: {output_path.name}")

print("\nPRIMEROS 5 POZOS")
print("--------------------------------")
print(
    wells[["kgs_id", "lease", "api"]]
    .head()
    .to_string(index=False)
)
