from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.versioning import router


def test_prompt_version_api_hides_content_by_default():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/versions/prompts")
    assert response.status_code == 200
    body = response.json()
    assert body["active_versions"]["routing"] == "1.0.0"
    assert all("content" not in item for item in body["versions"])


def test_unknown_active_prompt_returns_404():
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/api/versions/prompts/missing/active").status_code == 404
