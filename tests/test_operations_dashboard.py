from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routes import router


def test_operations_dashboard_renders_observability_entry_points():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/ops")
    assert response.status_code == 200
    assert "Agent 运营与调试后台" in response.text
    assert "/api/observability/traces" in response.text
    assert "/api/knowledge/index/status" in response.text
    assert "/api/versions/prompts" in response.text
    assert 'href="/"' in response.text
    assert "返回 FlowPilot" in response.text
