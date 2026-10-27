
from pathlib import Path
from zipfile import ZipFile
import pandas as pd

# 1. Localizar el proyecto y el catalogo
project_dir = Path(__file__).resolve().parent.parent
zip_path = project_dir / "data" / "catalog" / "ks_las_files.zip"

# 2. Abrir el ZIP sin descomprimirlo
with ZipFile(zip_path) as archive:
    with archive.open("ks_las_files.txt") as file:
        df = pd.read_csv(file, dtype=str)

# 3. Mostrar informacion general
print("PROJECT 07 - KGS LAS CATALOG")
print("--------------------------------")

print(f"Registros del catalogo: {len(df):,}")
print(f"Pozos KGS unicos: {df['KGS_ID'].nunique():,}")
print(f"URLs unicas: {df['URL'].nunique():,}")

# 4. Mostrar los campos disponibles
print("\nCOLUMNAS DEL CATALOGO")
print("--------------------------------")
print(df.columns.tolist())

# 5. Mostrar los primeros cinco registros
print("\nPRIMEROS 5 REGISTROS")
print("--------------------------------")

print(
    df[["KGS_ID", "Lease", "Operator", "API", "URL"]]
    .head(5)
    .to_string(index=False)
)


# 6. Seleccionar diez pozos diferentes con API y URL
candidates = df.dropna(subset=["KGS_ID", "API", "URL"]).copy()

candidates = candidates[
    candidates["API"].str.strip().ne("")
    & candidates["URL"].str.startswith("https://", na=False)
]

# Evitar seleccionar dos archivos del mismo pozo
selected = candidates.drop_duplicates(subset=["KGS_ID"]).head(10)

print("\nPRIMEROS 10 POZOS SELECCIONADOS")
print("--------------------------------")

print(
    selected[["KGS_ID", "Lease", "API", "Depth_start", "Depth_stop"]]
    .to_string(index=False)
)

print(f"\nTotal de pozos seleccionados: {len(selected)}")
