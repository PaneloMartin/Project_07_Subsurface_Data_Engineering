
from pathlib import Path

# Ubicacion de nuestro proyecto
project_dir = Path(__file__).resolve().parent.parent

# Carpeta donde guardamos los archivos originales
raw_dir = project_dir / "data" / "raw"

# Buscar todos los archivos con extension .las
las_files = list(raw_dir.glob("*.las"))

print("PROJECT 07 - LAS FILE INSPECTION")
print("--------------------------------")

print(f"Directorio: {raw_dir}")
print(f"Archivos LAS encontrados: {len(las_files)}")

for file in las_files:
    print(f"\nArchivo: {file.name}")
    print(f"Tamaño: {file.stat().st_size:,} bytes")

    with file.open("r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline().strip()

    print(f"Primera linea: {first_line}")
