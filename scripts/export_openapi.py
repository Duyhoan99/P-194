"""Script to export OpenAPI schema artifact from FastAPI application."""

import json
import sys
from importlib import import_module
from pathlib import Path


def export_openapi():
    repo_root = Path(__file__).parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    app = import_module("src.main").app
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(exist_ok=True)

    schema = app.openapi()
    target = docs_dir / "openapi.json"

    with open(target, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"Exported OpenAPI schema to {target}")

if __name__ == "__main__":
    export_openapi()
