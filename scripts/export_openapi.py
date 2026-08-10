"""Script to export OpenAPI schema artifact from FastAPI application."""

import json
from pathlib import Path
from src.main import app

def export_openapi():
    docs_dir = Path(__file__).parents[1] / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    schema = app.openapi()
    target = docs_dir / "openapi.json"
    
    with open(target, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    print(f"Exported OpenAPI schema to {target}")

if __name__ == "__main__":
    export_openapi()
