"""Small repository consistency checks; not a substitute for mypy or Ruff."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tomllib
import typing

from quietcycle import __all__ as public_names
import quietcycle
from quietcycle import models

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    count = 0
    for directory in ("src", "tests", "examples", "scripts"):
        for path in (ROOT / directory).rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))
            count += 1
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert metadata["project"]["version"] == quietcycle.__version__
    assert all(hasattr(quietcycle, name) for name in public_names)
    for name in public_names:
        item = getattr(quietcycle, name)
        if isinstance(item, type) and issubclass(item, models.Model):
            typing.get_type_hints(item, include_extras=True)
    from quietcycle import learning
    import inspect
    for name in learning.__all__:
        item = getattr(learning, name)
        if isinstance(item, type) or inspect.isfunction(item):
            typing.get_type_hints(item, include_extras=True)
    from quietcycle.api import create_app
    typing.get_type_hints(create_app)
    missing = []
    for path in [*ROOT.glob("*.md"), *(ROOT / "docs").glob("*.md")]:
        for target in re.findall(r"\]\(([^\s)]+)\)", path.read_text()):
            target = target.split("#", 1)[0]
            if target and "://" not in target and not target.startswith("mailto:"):
                if not (path.parent / target).exists():
                    missing.append((str(path.relative_to(ROOT)), target))
    assert not missing, missing
    assert not list((ROOT / "src").rglob("*.html"))
    assert not list((ROOT / "src").rglob("*.js"))
    print(json.dumps({"python_311_parse_files": count, "public_exports": len(public_names),
                      "learning_public_exports": len(learning.__all__),
                      "missing_markdown_targets": missing, "frontend": False}, indent=2))

if __name__ == "__main__":
    main()
