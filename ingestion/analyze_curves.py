
from pathlib import Path
from collections import Counter
import lasio

project_dir = Path(__file__).resolve().parent.parent
raw_dir = project_dir / "data" / "raw"

curve_counts = Counter()
curve_units = {}

for file in sorted(raw_dir.glob("*.las")):
    las = lasio.read(file)

    for curve in las.curves:
        mnemonic = curve.mnemonic.upper().strip()
        unit = curve.unit.strip()

        curve_counts[mnemonic] += 1
        curve_units.setdefault(mnemonic, set()).add(unit)

print("PROJECT 07 - CURVE ANALYSIS")
print("--------------------------------")

print(f"Tipos de curvas diferentes: {len(curve_counts)}")

print("\nCURVAS MAS FRECUENTES")
print("--------------------------------")

for mnemonic, count in curve_counts.most_common(20):
    units = ", ".join(sorted(curve_units[mnemonic]))
    print(f"{mnemonic:12} | {count:2} archivos | unidades: {units}")


print("\nCURVAS CON MULTIPLES UNIDADES")
print("--------------------------------")

for mnemonic, units in sorted(curve_units.items()):
    if len(units) > 1:
        print(f"{mnemonic:12} | {', '.join(sorted(units))}")


print("\nINVESTIGACION DE DCAL")
print("--------------------------------")

for file in sorted(raw_dir.glob("*.las")):
    las = lasio.read(file)

    for curve in las.curves:
        if curve.mnemonic.upper().strip() == "DCAL":
            print(f"Archivo: {file.name}")
            print(f"Unidad: {curve.unit}")
            print(f"Descripcion: {curve.descr}")
            print("--------------------------------")
