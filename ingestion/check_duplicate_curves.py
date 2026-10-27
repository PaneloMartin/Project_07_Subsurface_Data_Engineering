
from pathlib import Path
import pandas as pd

project_dir = Path(__file__).resolve().parent.parent
curves_path = project_dir / "data" / "processed" / "curves.csv"

df = pd.read_csv(curves_path, dtype={"file_id": str})

duplicates = df[
    df.duplicated(
        subset=["file_id", "mnemonic"],
        keep=False
    )
].sort_values(["file_id", "mnemonic", "curve_position"])

print("PROJECT 07 - DUPLICATE CURVE CHECK")
print("--------------------------------")
print(f"Curvas registradas: {len(df)}")
print(f"Registros con nombres repetidos: {len(duplicates)}")

if duplicates.empty:
    print("No se encontraron nombres repetidos dentro de un mismo archivo.")
else:
    print("\nCURVAS DUPLICADAS")
    print("--------------------------------")
    print(
        duplicates[
            ["file_id", "curve_position", "mnemonic", "original_unit"]
        ].to_string(index=False)
    )
