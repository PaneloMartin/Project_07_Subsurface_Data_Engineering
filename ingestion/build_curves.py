
from pathlib import Path
import pandas as pd
import lasio

project_dir = Path(__file__).resolve().parent.parent
raw_dir = project_dir / "data" / "raw"
processed_dir = project_dir / "data" / "processed"

processed_dir.mkdir(parents=True, exist_ok=True)

records = []

for file in sorted(raw_dir.glob("*.las")):
    las = lasio.read(file)

    for position, curve in enumerate(las.curves):
        mnemonic = curve.mnemonic.upper().strip()
        original_unit = curve.unit.strip()

        quality_status = "OK"

        if not original_unit:
            quality_status = "UNIT_MISSING"

        elif mnemonic == "DCAL" and original_unit.upper() == "GAPI":
            quality_status = "UNIT_SUSPECT"

        records.append({
            "file_id": file.stem,
            "curve_position": position,
            "mnemonic": mnemonic,
            "original_unit": original_unit,
            "description": curve.descr,
            "quality_status": quality_status,
        })

df = pd.DataFrame(records)

output_path = processed_dir / "curves.csv"
df.to_csv(output_path, index=False)

print("PROJECT 07 - CURVES TABLE")
print("--------------------------------")
print(f"Archivos procesados: {df['file_id'].nunique()}")
print(f"Curvas registradas: {len(df)}")
print(f"Archivo generado: {output_path.name}")

print("\nESTADOS DE CALIDAD")
print("--------------------------------")
print(df["quality_status"].value_counts().to_string())
