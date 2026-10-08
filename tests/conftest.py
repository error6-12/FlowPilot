"""Pytest policy: keep the default suite deterministic and free of API calls."""

from pathlib import Path

import pytest


LEGACY_INTEGRATION_FILES = {
    "test_appointment_agent.py",
    "test_consultant_agent.py",
    "test_task_classification_agent.py",
    "test_user_behavior_agent.py",
}


def pytest_collection_modifyitems(items):
    integration = pytest.mark.integration
    for item in items:
        if Path(str(item.fspath)).name in LEGACY_INTEGRATION_FILES:
            item.add_marker(integration)
