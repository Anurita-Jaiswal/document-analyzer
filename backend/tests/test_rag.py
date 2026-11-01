import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.workers.processor import process_document_job
from backend.app.models import ProcessingJob
from backend.app.db.session import SessionLocal

client = TestClient(app)

def upload_and_process_test_file(headers, filename: str, content: str):
    file_payload = io.BytesIO(content.encode("utf-8"))
    upload_res = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": (filename, file_payload, "text/plain")}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    db = SessionLocal()
    job = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id).first()
    db.close()

    assert job is not None
    process_document_job(job.id, doc_id)
    return doc_id

def test_rag_evaluation_and_grounding():
    # 1. Login
    login_res = client.post("/api/v1/auth/demo-login")
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Ingest Document A (Quarterly Security Report)
    doc_a_id = upload_and_process_test_file(
        headers,
        "security_audit_2026.txt",
        (
            "DocuMind Security Audit 2026.\n"
            "Section 1: Zero-Trust Access Architecture.\n"
            "The organization completed end-to-end TLS 1.3 encryption across all internal microservices.\n"
            "Multi-factor authentication adoption reached 99.4% in Q3.\n"
            "The primary vulnerability identified was legacy session token expiration on stale devices.\n"
            "Recommended Mitigation: Enforce 24-hour mandatory token invalidation for privileged accounts."
        )
    )

    # Ingest Document B (Infrastructure Expansion Report)
    doc_b_id = upload_and_process_test_file(
        headers,
        "infra_expansion_2026.txt",
        (
            "DocuMind Cloud Infrastructure Plan.\n"
            "Section 1: Database and Compute Scaling.\n"
            "The platform deployed ChromaDB and PostgreSQL clusters across the North America region.\n"
            "Target retrieval latency is established below 120 milliseconds under a concurrent load of 500 requests.\n"
            "Annual hardware budget was approved at $320,000."
        )
    )

    # Create Chat Session
    sess_res = client.post("/api/v1/chat/sessions", headers=headers, json={"title": "RAG Evaluation Benchmark"})
    session_id = sess_res.json()["id"]

    # Test Case 1: Direct Evidence Retrieval & Page Provenance
    qa_res_1 = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers,
        json={
            "question": "What is the targeted retrieval latency under concurrent load?",
            "document_ids": [doc_b_id]
        }
    )
    assert qa_res_1.status_code == 200
    res_1 = qa_res_1.json()
    assert res_1["grounding_status"] == "supported"
    assert "120" in res_1["content"]
    assert len(res_1["citations"]) > 0
    assert res_1["citations"][0]["document_id"] == doc_b_id

    # Test Case 2: Cross-Document Comparative Query
    qa_res_2 = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers,
        json={
            "question": "What are the key security vulnerabilities and the annual hardware budget?",
            "document_ids": [doc_a_id, doc_b_id]
        }
    )
    assert qa_res_2.status_code == 200
    res_2 = qa_res_2.json()
    assert res_2["grounding_status"] == "supported"
    assert len(res_2["citations"]) >= 1

    # Test Case 3: Missing / Out-of-Scope Question (Hallucination Prevention)
    qa_res_3 = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers,
        json={
            "question": "Who is the chief medical officer and what surgical procedures were performed?",
            "document_ids": [doc_a_id]
        }
    )
    assert qa_res_3.status_code == 200
    res_3 = qa_res_3.json()
    assert res_3["grounding_status"] == "insufficient_evidence"
    assert "not contain sufficient information" in res_3["content"].lower()
