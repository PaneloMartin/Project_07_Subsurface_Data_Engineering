
from pathlib import Path
import lasio

# Localizar el archivo LAS
project_dir = Path(__file__).resolve().parent.parent
las_path = project_dir / "data" / "raw" / "1054310728.las"

print("PROJECT 07 - LAS DATA READER")
print("--------------------------------")

# Leer e interpretar el archivo LAS
las = lasio.read(las_path)

# Mostrar informacion general
print(f"Archivo: {las_path.name}")
print(f"Version LAS: {las.version.VERS.value}")
print(f"Pozo: {las.well.WELL.value}")

# Mostrar las curvas disponibles
print("\nCURVAS DISPONIBLES")
print("--------------------------------")

for curve in las.curves:
    print(
        f"{curve.mnemonic:10} "
        f"Unidad: {curve.unit:10} "
        f"Descripcion: {curve.descr}"
    )

# Mostrar cantidad de mediciones
print("\nRESUMEN")
print("--------------------------------")
print(f"Numero de curvas: {len(las.curves)}")
print(f"Numero de registros de profundidad: {len(las.index)}")
