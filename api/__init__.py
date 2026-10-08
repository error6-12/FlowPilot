"""API router inventory for FlowPilot enterprise and optional legacy modes."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from .consultation import router as consultation_router
from .knowledge import router as knowledge_router
from .observability import router as observability_router
from .task import router as task_router
from .versioning import router as versioning_router
from .workflows import router as workflows_router


LEGACY_APPOINTMENT_ENABLED = os.getenv(
    "ENABLE_LEGACY_APPOINTMENT", "false"
).strip().lower() in {"1", "true", "yes", "on"}

api_routers = [
    consultation_router,
    task_router,
    knowledge_router,
    observability_router,
    workflows_router,
    versioning_router,
]

if LEGACY_APPOINTMENT_ENABLED:
    from .appointment import router as appointment_router
    from .technician import router as technician_router
    from .user_behavior_analysis import router as user_behavior_analysis_router
    from .user_behavior_analysis import router_underscore as user_behavior_analysis_underscore_router

    api_routers.extend([
        appointment_router,
        technician_router,
        user_behavior_analysis_router,
        user_behavior_analysis_underscore_router,
    ])


__all__ = ["api_routers", "LEGACY_APPOINTMENT_ENABLED"]
