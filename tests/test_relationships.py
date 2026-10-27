
from pathlib import Path
import pandas as pd

project_dir = Path(__file__).resolve().parent.parent
processed_dir = project_dir / "data" / "processed"

wells = pd.read_csv(
    processed_dir / "wells.csv",
    dtype={"kgs_id": str}
)

logs = pd.read_csv(
    processed_dir / "log_files.csv",
    dtype={"kgs_id": str, "file_id": str}
)

curves = pd.read_csv(
    processed_dir / "curves.csv",
    dtype={"file_id": str}
)

measurements = pd.read_csv(
    processed_dir / "measurements.csv",
    dtype={"file_id": str}
)

print("PROJECT 07 - RELATIONSHIP TESTS")
print("--------------------------------")

# Cada archivo debe pertenecer a un pozo existente
orphan_logs = ~logs["kgs_id"].isin(wells["kgs_id"])

# Cada curva debe pertenecer a un archivo existente
orphan_curves = ~curves["file_id"].isin(logs["file_id"])

# Cada medicion debe pertenecer a una curva existente
curve_keys = pd.MultiIndex.from_frame(
    curves[["file_id", "mnemonic"]]
)

measurement_keys = pd.MultiIndex.from_frame(
    measurements[["file_id", "mnemonic"]]
)

orphan_measurements = ~measurement_keys.isin(curve_keys)

results = {
    "Archivos sin pozo": int(orphan_logs.sum()),
    "Curvas sin archivo": int(orphan_curves.sum()),
    "Mediciones sin curva": int(orphan_measurements.sum()),
}

for test, errors in results.items():
    status = "PASS" if errors == 0 else "FAIL"
    print(f"{status} | {test}: {errors:,}")

if any(results.values()):
    raise SystemExit("Fallaron las pruebas de integridad")

print("\nTodas las relaciones verificadas.")
