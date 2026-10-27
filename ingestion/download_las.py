
from pathlib import Path
from zipfile import ZipFile
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import pandas as pd

# Directorios del proyecto
project_dir = Path(__file__).resolve().parent.parent
catalog_path = project_dir / "data" / "catalog" / "ks_las_files.zip"
raw_dir = project_dir / "data" / "raw"

raw_dir.mkdir(parents=True, exist_ok=True)

# Leer catalogo
with ZipFile(catalog_path) as archive:
    with archive.open("ks_las_files.txt") as file:
        df = pd.read_csv(file, dtype=str)

# Seleccionar diez pozos diferentes
candidates = df.dropna(subset=["KGS_ID", "API", "URL"]).copy()

candidates = candidates[
    candidates["API"].str.strip().ne("")
    & candidates["URL"].str.startswith("https://", na=False)
]

selected = candidates.drop_duplicates(subset=["KGS_ID"]).head(10)

print("PROJECT 07 - KGS LAS DOWNLOADER")
print("--------------------------------")

# Descargar archivos
for _, well in selected.iterrows():
    original_url = well["URL"]

    # Actualizar la direccion del KGS a Azure
    old_prefix = "https://www.kgs.ku.edu/b_1/"
    new_prefix = "https://kgsimages.blob.core.windows.net/web/web_1/"

    url = original_url.replace(old_prefix, new_prefix, 1)

    filename = Path(urlparse(url).path).name

    destination = raw_dir / filename

    print(f"\nPozo: {well['Lease']}")
    print(f"KGS ID: {well['KGS_ID']}")
    print(f"Archivo: {filename}")

    if destination.exists():
        print("Estado: YA EXISTE - omitido")
        continue

    try:
        request = Request(
            url,
            headers={"User-Agent": "Project07-Research/1.0"}
        )

        with urlopen(request, timeout=30) as response:
            content = response.read()

        # Comprobar que parece un archivo LAS
        if not content.lstrip().startswith(b"~"):
            raise ValueError("El contenido no parece ser un archivo LAS")

        destination.write_bytes(content)

        print(f"Estado: DESCARGADO ({len(content):,} bytes)")

    except Exception as error:
        print(f"Estado: ERROR - {error}")

print("\nProceso finalizado.")
