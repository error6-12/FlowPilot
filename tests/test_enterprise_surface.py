from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import LEGACY_APPOINTMENT_ENABLED, api_routers
from web.routes import router as web_router
from app import app as flowpilot_app


def test_enterprise_mode_does_not_register_legacy_business_apis():
    assert LEGACY_APPOINTMENT_ENABLED is False
    paths = {route.path for router in api_routers for route in router.routes}
    assert not any("technician" in path for path in paths)
    assert not any("appointment" in path for path in paths)


def test_homepage_uses_flowpilot_navigation_without_massage_links():
    html = Path("web/templates/index.html").read_text(encoding="utf-8")
    assert "FlowPilot" in html
    assert "Agent 运营后台" in html
    assert "技师状态" not in html
    assert "技师排班" not in html
    assert "预约成功" not in html
    assert "查看处理详情" in html
    assert "splitReplySources" in html
    assert "escapeHtml" in html
    assert "errors.join('')" in html
    assert "hydrateWorkflowCard" in html
    assert "该凭证来自 Workflow API 中已持久化的真实记录" in html


def test_legacy_technician_pages_return_404_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_LEGACY_APPOINTMENT", raising=False)
    app = FastAPI()
    app.include_router(web_router)
    client = TestClient(app)
    assert client.get("/technician").status_code == 404
    assert client.get("/technician_schedule").status_code == 404


def test_flowpilot_docs_has_home_back_button():
    response = TestClient(flowpilot_app).get("/docs")

    assert response.status_code == 200
    assert 'href="/"' in response.text
    assert "返回 FlowPilot" in response.text
