import json
from pathlib import Path

import pytest


@pytest.mark.anyio
async def test_every_manifest_pdf_can_be_opened_by_stable_document_id(client) -> None:
    data_root = Path(__file__).parents[2] / "data" / "demo_mvp_v1"
    manifest = json.loads((data_root / "dataset_manifest.json").read_text(encoding="utf-8"))

    for item in manifest["documents"]:
        response = await client.get(f"/api/v1/documents/{item['document_id']}/raw")
        assert response.status_code == 200, item["document_id"]
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == f'inline; filename="{Path(item["file"]).name}"'
        assert response.content.startswith(b"%PDF-")


@pytest.mark.anyio
async def test_unknown_document_id_does_not_fall_back_to_another_patient_file(client) -> None:
    response = await client.get("/api/v1/documents/DOC-PAT003-UNKNOWN-999/raw")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"
