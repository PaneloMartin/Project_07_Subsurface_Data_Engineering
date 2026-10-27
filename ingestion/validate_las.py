
from pathlib import Path
import lasio

project_dir = Path(__file__).resolve().parent.parent
raw_dir = project_dir / "data" / "raw"

files = sorted(raw_dir.glob("*.las"))

valid = 0
failed = 0

print("PROJECT 07 - LAS VALIDATION")
print("--------------------------------")
print(f"Archivos encontrados: {len(files)}")

for file in files:
    try:
        las = lasio.read(file)

        rows = len(las.index)
        curves = len(las.curves)

        if rows == 0 or curves < 2:
            raise ValueError("Sin mediciones o curvas suficientes")

        print(f"OK    {file.name} | {rows:,} filas | {curves} curvas")
        valid += 1

    except Exception as error:
        print(f"ERROR {file.name} | {error}")
        failed += 1

print("\nRESUMEN")
print("--------------------------------")
print(f"Validos: {valid}")
print(f"Con errores: {failed}")
