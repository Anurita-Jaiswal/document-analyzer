import io
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import init_db

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()

def test_cross_user_isolation():
    uid = uuid.uuid4().hex[:6]
    # Register User A
    user_a_res = client.post("/api/v1/auth/register", json={
        "email": f"user_a_{uid}@test.com",
        "password": "PasswordA123!",
        "full_name": "User Alpha"
    })
    assert user_a_res.status_code == 200
    token_a = user_a_res.json()["access_token"]

    # Register User B
    user_b_res = client.post("/api/v1/auth/register", json={
        "email": f"user_b_{uid}@test.com",
        "password": "PasswordB123!",
        "full_name": "User Beta"
    })
    assert user_b_res.status_code == 200
    token_b = user_b_res.json()["access_token"]

    # User A uploads a private document
    file_payload = io.BytesIO(b"Confidential Alpha Financials: Revenue $5M.")
    upload_res = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("alpha_secret.txt", file_payload, "text/plain")}
    )
    assert upload_res.status_code == 201
    doc_a_id = upload_res.json()["id"]

    # User B attempts to access User A's document -> Must be 404 (Not Found / Access Denied)
    forbidden_get = client.get(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden_get.status_code == 404

    # User B attempts to delete User A's document -> Must be 404
    forbidden_delete = client.delete(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden_delete.status_code == 404
