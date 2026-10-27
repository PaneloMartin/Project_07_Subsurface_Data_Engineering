
from pathlib import Path
import pandas as pd
import lasio

project_dir = Path(__file__).resolve().parent.parent
raw_dir = project_dir / "data" / "raw"
processed_dir = project_dir / "data" / "processed"

processed_dir.mkdir(parents=True, exist_ok=True)

output_path = processed_dir / "measurements.csv"

total_rows = 0

with output_path.open("w", encoding="utf-8", newline="") as output:
    first_batch = True

    for file in sorted(raw_dir.glob("*.las")):
        las = lasio.read(file)

        # Una columna por curva, una fila por profundidad
        data = las.df()

        # Incorporar la profundidad como columna
        data = data.reset_index()

        # Convertir columnas de curvas en filas
        long_data = data.melt(
            id_vars=[data.columns[0]],
            var_name="mnemonic",
            value_name="value"
        )

        long_data = long_data.rename(
            columns={data.columns[0]: "depth"}
        )

        long_data.insert(0, "file_id", file.stem)

        # Mantener las mediciones faltantes como valores nulos
        long_data.to_csv(
            output,
            index=False,
            header=first_batch
        )

        first_batch = False
        total_rows += len(long_data)

        print(
            f"{file.name}: {len(long_data):,} mediciones"
        )

print("\nPROJECT 07 - MEASUREMENTS TABLE")
print("--------------------------------")
print(f"Total de registros: {total_rows:,}")
print(f"Archivo generado: {output_path.name}")
