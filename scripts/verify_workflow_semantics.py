"""Live smoke test for contextual Workflow Agent extraction."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.workflow_agent import WorkflowAgent
from services.workflow_engine import WorkflowEngine


async def main() -> None:
    agent = WorkflowAgent(session_id="workflow-semantic-smoke-test")
    first = await agent.create_draft("帮我预订A301会议室")
    second = await agent.create_draft("开始时间，两点，结束时间，四点")
    confirmed = await agent.create_draft("对的")
    print(f"first_type={first.workflow_type.value}")
    print(f"first_missing={','.join(first.missing_fields)}")
    print(f"second_status={second.status.value}")
    print(f"resource={second.fields.get('resource')}")
    print(f"start_time={second.fields.get('start_time')}")
    print(f"end_time={second.fields.get('end_time')}")
    print(f"assumptions={';'.join(second.assumptions)}")
    print(f"confirmed_status={confirmed.status.value}")
    print(f"workflow_id={confirmed.workflow_id}")
    verifier = WorkflowEngine()
    try:
        stored = verifier.get(confirmed.workflow_id)
        print(f"persisted_status={stored['status'] if stored else 'missing'}")
        print(f"audit_actions={','.join(log['action'] for log in stored['audit_logs']) if stored else ''}")
    finally:
        verifier.close()


if __name__ == "__main__":
    asyncio.run(main())
