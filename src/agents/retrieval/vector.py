"""Minimal Semantic Vector Retrieval Integration using ChromaDB."""

import os
from typing import Any
import chromadb
from chromadb.config import Settings

import os
from typing import Any
import chromadb
from chromadb.config import Settings

# Lazy initialization of chroma client to avoid overhead if not used
_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma")
        if not os.path.exists(persist_dir):
            os.makedirs(persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=persist_dir, settings=Settings(anonymized_telemetry=False))
    return _chroma_client

def index_evidence(tenant_id: str, patient_id: str, items: list[Any]) -> None:
    """Index narrative note evidence into Chroma for semantic search."""
    if not items:
        return
        
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="clinical_notes")
    
    docs = []
    ids = []
    metadatas = []
    
    for item in items:
        # Resolve whether this is a dict or an object
        if isinstance(item, dict):
            fact_type = item.get("fact_type", "")
            ev_id = item.get("evidence_id")
            norm_val = item.get("normalized_value")
            citations = item.get("citations", [])
        else:
            fact_type = getattr(item, "fact_type", "")
            ev_id = getattr(item, "evidence_id", None)
            norm_val = getattr(item, "normalized_value", None)
            citations = getattr(item, "citations", [])

        # Only index unstructured narrative notes
        if fact_type not in {"clinical_note", "note", "narrative"}:
            if not isinstance(norm_val, dict) or "statement" not in norm_val:
                continue
                
        if not ev_id:
            continue
            
        if not norm_val or not isinstance(norm_val, dict):
            continue
            
        text = norm_val.get("statement", "")
        if not text:
            continue
            
        # Get provenance
        source_doc_id = "unknown"
        page_num = 1
        chunk_id = ""
        source_type = "unknown"

        if citations and len(citations) > 0:
            first_cit = citations[0]
            if isinstance(first_cit, dict):
                source_doc_id = first_cit.get("document_id", "unknown")
                page_num = first_cit.get("page_number", 1)
                chunk_id = first_cit.get("block_id", "")
                source_type = first_cit.get("source_type", "unknown")
            else:
                source_doc_id = getattr(first_cit, "document_id", "unknown")
                page_num = getattr(first_cit, "page_number", 1)
                chunk_id = getattr(first_cit, "block_id", "")
                source_type = getattr(first_cit, "source_type", "unknown")
            
        docs.append(text)
        ids.append(str(ev_id))
        metadatas.append({
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "evidence_id": str(ev_id),
            "source_document_id": str(source_doc_id),
            "source_type": str(source_type),
            "page_number": int(page_num) if page_num else 1,
            "chunk_id": str(chunk_id or "")
        })
        
    if docs:
        collection.upsert(documents=docs, ids=ids, metadatas=metadatas)

def clear_patient_evidence(tenant_id: str, patient_id: str) -> None:
    """Explicitly delete Chroma vectors matching BOTH the tenant_id and patient_id."""
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(name="clinical_notes")
        collection.delete(
            where={
                "$and": [
                    {"tenant_id": tenant_id},
                    {"patient_id": patient_id}
                ]
            }
        )
    except Exception:
        pass

class SemanticRetriever:
    """Retrieves semantic candidates from Chroma DB enforcing tenant and patient scope."""
    
    def retrieve(self, tenant_id: str, patient_id: str, query: str, k: int = 5) -> dict[str, float]:
        """
        Search Chroma for semantically similar notes.
        Returns a dict mapping evidence_id to a similarity score (0.0 to 1.0).
        """
        if not query.strip():
            return {}
            
        try:
            client = get_chroma_client()
            collection = client.get_or_create_collection(name="clinical_notes")
            
            if collection.count() == 0:
                return {}
                
            # Perform vector search scoped to BOTH tenant and patient
            results = collection.query(
                query_texts=[query],
                n_results=k,
                where={
                    "$and": [
                        {"tenant_id": tenant_id},
                        {"patient_id": patient_id}
                    ]
                }
            )
            
            scores = {}
            if results and results.get("ids") and len(results["ids"]) > 0 and results["ids"][0]:
                # Chroma uses L2 distance by default (unless configured otherwise).
                distances = results.get("distances", [[0] * len(results["ids"][0])])[0]
                ids = results["ids"][0]
                
                for doc_id, dist in zip(ids, distances):
                    # Convert L2 distance to score [0, 1]
                    sim = 1.0 / (1.0 + float(dist))
                    scores[doc_id] = sim
                    
            return scores
        except Exception:
            # Fail closed on scope/connection errors, return empty candidates (don't crash the pipeline)
            return {}
