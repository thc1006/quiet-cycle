"""Build with the provisioned PEP 517 backend; no isolation or dependency download."""
from pathlib import Path
import os


def main() -> None:
    from setuptools.build_meta import build_sdist, build_wheel
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    output = root / "dist"
    output.mkdir(exist_ok=True)
    print(build_wheel(str(output)))
    print(build_sdist(str(output)))

if __name__ == "__main__":
    main()
