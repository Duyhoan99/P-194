from unittest import mock

import pytest

from src.agents.contracts import DocumentCitation, EvidenceItem
from src.agents.evidence import ScopedEvidence, retrieve_evidence
from src.agents.retrieval.vector import SemanticRetriever, index_evidence


class MockCollection:
    def __init__(self):
        self.docs = []
        self.ids = []
        self.metadatas = []

    def get_or_create_collection(self, name):
        return self

    def upsert(self, documents, ids, metadatas):
        self.docs.extend(documents)
        self.ids.extend(ids)
        self.metadatas.extend(metadatas)

    def count(self):
        return len(self.ids)

    def query(self, query_texts, n_results, where):
        # Very simple mock logic for tests
        tenant_id = None
        patient_id = None

        if "$and" in where:
            for cond in where["$and"]:
                if "tenant_id" in cond:
                    tenant_id = cond["tenant_id"]
                if "patient_id" in cond:
                    patient_id = cond["patient_id"]

        results = {"ids": [[]], "distances": [[]]}

        for idx, (i, meta, doc) in enumerate(zip(self.ids, self.metadatas, self.docs)):
            if tenant_id and meta.get("tenant_id") != tenant_id:
                continue
            if patient_id and meta.get("patient_id") != patient_id:
                continue

            # If query is "Bệnh nhân có vấn đề tuân thủ điều trị không?" and doc has "misses evening doses"
            if "tuân thủ" in query_texts[0].lower() and "misses" in doc:
                results["ids"][0].append(i)
                results["distances"][0].append(0.5)
            # If query is exact
            elif query_texts[0] == doc:
                results["ids"][0].append(i)
                results["distances"][0].append(0.0)

        return results

    def get(self, ids):
        idx = self.ids.index(ids[0])
        return {"metadatas": [self.metadatas[idx]]}

mock_client = MockCollection()

def setup_chroma():
    # Setup test collection
    mock_client.docs = []
    mock_client.ids = []
    mock_client.metadatas = []

    # Patient 1 data
    cit1 = DocumentCitation(
        citation_id="cit1", source_type="pdf", document_id="doc1", document_name="test.pdf",
        page_number=1, block_id="b1", snippet="Patient frequently misses evening doses.",
        source_checksum="abc", extraction_version="1"
    )
    e1 = EvidenceItem(
        evidence_id="e1", fact_type="clinical_note",
        normalized_value={"statement": "Patient frequently misses evening doses."},
        source_value="", source_time=None, verification_status="verified", citations=[cit1]
    )

    # Patient 2 data
    cit2 = DocumentCitation(
        citation_id="cit2", source_type="pdf", document_id="doc2", document_name="test2.pdf",
        page_number=2, block_id="b2", snippet="Patient has hypertension.",
        source_checksum="def", extraction_version="1"
    )
    e2 = EvidenceItem(
        evidence_id="e2", fact_type="clinical_note",
        normalized_value={"statement": "Patient has hypertension."},
        source_value="", source_time=None, verification_status="verified", citations=[cit2]
    )

    index_evidence("t1", "p1", [e1])
    index_evidence("t1", "p2", [e2])

    return (e1, e2)

@pytest.fixture(autouse=True)
def mock_chroma_client():
    with mock.patch("src.agents.retrieval.vector.get_chroma_client", return_value=mock_client):
        yield

@pytest.fixture
def mock_chroma():
    return setup_chroma()

@pytest.fixture
def e1(mock_chroma):
    return mock_chroma[0]

@pytest.fixture
def e2(mock_chroma):
    return mock_chroma[1]
def test_semantic_paraphrase(e1, e2):
    packet = [ScopedEvidence(item=e1, origin="note", patient_id="p1", tenant_id="t1")]

    # Query without keyword match
    results = retrieve_evidence(packet, route="hybrid", question="Bệnh nhân có vấn đề tuân thủ điều trị không?")
    assert len(results) == 1
    assert results[0].item.evidence_id == "e1"

def test_cross_patient_isolation(e1, e2):
    # Try to query p1 but looking for hypertension
    retriever = SemanticRetriever()
    scores = retriever.retrieve("t1", "p1", "Patient has hypertension.", k=5)
    # p1 does not have hypertension in their index
    assert "e2" not in scores

def test_cross_tenant_isolation(e1, e2):
    retriever = SemanticRetriever()
    scores = retriever.retrieve("t2", "p1", "Patient frequently misses evening doses.", k=5)
    # Different tenant should return nothing
    assert "e1" not in scores

def test_provenance_preservation(e1, e2):
    data = mock_client.get(ids=["e1"])
    metadata = data["metadatas"][0]

    assert metadata["evidence_id"] == "e1"
    assert metadata["source_document_id"] == "doc1"
    assert metadata["page_number"] == 1
    assert metadata["tenant_id"] == "t1"
    assert metadata["patient_id"] == "p1"

def test_vector_unavailable(e1, e2):
    packet = [ScopedEvidence(item=e1, origin="note", patient_id="p1", tenant_id="t1")]

    # Mocking get_chroma_client to raise Exception inside retrieve
    with mock.patch("src.agents.retrieval.vector.get_chroma_client", side_effect=Exception("Chroma is down")):
        # Should not crash, just return the item based on base score
        results = retrieve_evidence(packet, route="hybrid", question="Patient misses doses?")
        assert len(results) == 1

def test_structured_fallback():
    # If Chroma is down, structured data still works
    e_med = EvidenceItem(
        evidence_id="e_med", fact_type="medication",
        normalized_value={"statement": "Metformin 1000mg"},
        source_value="", source_time=None, verification_status="verified", citations=[]
    )
    packet = [ScopedEvidence(item=e_med, origin="structured", patient_id="p1", tenant_id="t1")]

    with mock.patch("src.agents.retrieval.vector.get_chroma_client", side_effect=Exception("Chroma is down")):
        results = retrieve_evidence(packet, route="hybrid", question="Thuốc Metformin hiện tại là gì?")
        assert len(results) == 1
        assert results[0].item.evidence_id == "e_med"

if __name__ == "__main__":
    e1, e2 = setup_chroma()
    test_semantic_paraphrase(e1, e2)
    test_cross_patient_isolation(e1, e2)
    test_cross_tenant_isolation(e1, e2)
    test_provenance_preservation(e1, e2)
    test_vector_unavailable(e1, e2)
    test_structured_fallback()
    print("All Phase 2 tests passed!")
