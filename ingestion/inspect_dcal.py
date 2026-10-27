
from pathlib import Path
import lasio
import pandas as pd

project_dir = Path(__file__).resolve().parent.parent
raw_dir = project_dir / "data" / "raw"

filenames = [
    "1044249719.las",
    "1054310728.las",
]

for filename in filenames:
    las = lasio.read(raw_dir / filename)
    df = las.df()

    values = df["DCAL"].dropna()

    print(f"\nARCHIVO: {filename}")
    print("--------------------------------")
    print(f"Valores validos: {len(values):,}")
    print(f"Minimo: {values.min():.2f}")
    print(f"Maximo: {values.max():.2f}")
    print(f"Mediana: {values.median():.2f}")

    print("\nPrimeros 10 valores validos:")
    print(values.head(10).to_string())


print("\nANALISIS DE VALORES EXTREMOS")
print("--------------------------------")

for filename in filenames:
    las = lasio.read(raw_dir / filename)
    values = las.df()["DCAL"].dropna()

    print(f"\nArchivo: {filename}")
    print(f"Valores mayores a 20: {(values > 20).sum():,}")
    print(f"Valores iguales a 0: {(values == 0).sum():,}")
    print(f"Percentil 95: {values.quantile(0.95):.2f}")
    print(f"Percentil 99: {values.quantile(0.99):.2f}")
