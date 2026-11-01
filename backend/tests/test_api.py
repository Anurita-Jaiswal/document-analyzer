import os
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import init_db
from backend.app.workers.processor import process_document_job

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()

def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "ai_engine" in data

def test_auth_and_demo_login():
    res = client.post("/api/v1/auth/demo-login")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "researcher@documind.ai"
    token = data["access_token"]

    # Verify /me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "researcher@documind.ai"

def test_document_lifecycle_and_rag():
    # 1. Login
    login_res = client.post("/api/v1/auth/demo-login")
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload Document
    test_content = (
        "DocuMind Research Report 2026.\n"
        "Project Title: Enterprise Document Intelligence Assistant.\n"
        "Key Deliverable: Grounded RAG with source verification.\n"
        "Total Budget: $150,000 for development and cloud testing.\n"
        "Key Finding: Automatic citation cards improve student research efficiency by 45%.\n"
        "Critical Deadline: November 15, 2026."
    )
    file_payload = io.BytesIO(test_content.encode("utf-8"))
    upload_res = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("project_report.txt", file_payload, "text/plain")}
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["id"]
    assert doc_data["status"] == "queued"

    # Synchronously run processor for deterministic testing
    from backend.app.models import ProcessingJob
    from backend.app.db.session import SessionLocal
    db = SessionLocal()
    job = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id).first()
    db.close()
    
    assert job is not None
    process_document_job(job.id, doc_id)

    # 3. Check document status is ready
    get_res = client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "ready"
    assert get_res.json()["page_count"] >= 1

    # 4. Generate Document Summary
    summary_res = client.post(f"/api/v1/documents/{doc_id}/summary", headers=headers)
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["document_id"] == doc_id
    assert len(summary_data["key_points"]) > 0

    # 5. Extract Structured Fields
    extract_res = client.post(
        "/api/v1/extraction",
        headers=headers,
        json={"document_ids": [doc_id]}
    )
    assert extract_res.status_code == 200
    extract_data = extract_res.json()
    assert "extracted_data" in extract_data

    # 6. Chat Session & Grounded Question Answering
    session_res = client.post("/api/v1/chat/sessions", headers=headers, json={"title": "Test QA Session"})
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    # Ask grounded question
    msg_res = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers,
        json={
            "question": "What is the total budget allocated for the project?",
            "document_ids": [doc_id]
        }
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert msg_data["role"] == "assistant"
    assert msg_data["grounding_status"] in ["supported", "insufficient_evidence"]
    assert len(msg_data["citations"]) > 0
    assert msg_data["citations"][0]["document_id"] == doc_id
    assert msg_data["citations"][0]["page"] == 1
