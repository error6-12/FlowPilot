from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import knowledge


class FakeKnowledgeService:
    def get_index_status(self):
        return {
            "version": 4,
            "document_count": 57,
            "dimension": 2048,
            "last_operation": "upsert",
        }


def test_index_status_endpoint_exposes_safe_operational_metadata(monkeypatch):
    async def fake_service():
        return FakeKnowledgeService()

    monkeypatch.setattr(knowledge, "get_knowledge_service", fake_service)
    app = FastAPI()
    app.include_router(knowledge.router)
    response = TestClient(app).get("/api/knowledge/index/status")

    assert response.status_code == 200
    assert response.json()["data"]["version"] == 4
    assert response.json()["data"]["document_count"] == 57
