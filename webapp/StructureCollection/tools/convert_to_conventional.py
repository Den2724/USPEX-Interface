from __future__ import annotations

from pathlib import Path
import sys

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def convert_all(src_dir: Path, dst_dir: Path) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    failures = 0

    for cif_path in sorted(src_dir.glob("*.cif")):
        try:
            structure = Structure.from_file(cif_path)
            analyzer = SpacegroupAnalyzer(structure, symprec=1e-3)
            conventional = analyzer.get_conventional_standard_structure()
            conventional.to(filename=dst_dir / cif_path.name)
        except Exception as exc:
            failures += 1
            print(f"Failed: {cif_path.name}: {exc}", file=sys.stderr)

    return failures


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1]
    destination = source / "conventional"
    failed = convert_all(source, destination)
    if failed:
        raise SystemExit(f"{failed} CIF files failed to convert.")
