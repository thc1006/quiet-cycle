"""Create a reproducible source handoff archive. Does not publish anything."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'.git', '.pytest_cache', '.mypy_cache', '.ruff_cache', '__pycache__',
           '.venv', 'venv', 'build', '.coverage', '.DS_Store'}


def files(root: Path) -> list[Path]:
    result = []
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part in EXCLUDE or part.endswith('.egg-info') for part in relative.parts):
            continue
        if path.suffix in {'.pyc', '.pyo', '.zip'}:
            continue
        if path.is_symlink():
            raise ValueError('Repository archives do not include symlinks')
        if path.is_file():
            result.append(path)
    return sorted(result, key=lambda path: path.relative_to(root).as_posix())


def pack(root: Path, output: Path) -> int:
    selected = files(root)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in selected:
            info = zipfile.ZipInfo('quiet-cycle/' + path.relative_to(root).as_posix(), (2026, 9, 17, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return len(selected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    count = pack(ROOT, args.output)
    print(f'{count} files; sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
