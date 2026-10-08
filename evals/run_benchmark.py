"""Run reproducible Agent/RAG/workflow benchmarks against configured services."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_community.callbacks.manager import get_openai_callback

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.task_classification.task_classifier import TaskClassifier
from agents.workflow_agent import WorkflowAgent
from api.chat_handler import ProcessUserInput_stream
from config.model_provider import create_chat_model, get_model_provider
from services.knowledge_service import KnowledgeService
from services.workflow_engine import WorkflowEngine

DATASET_DIR = PROJECT_ROOT / "evals" / "datasets"
RESULT_DIR = PROJECT_ROOT / "evals" / "results"


def load_cases(name: str) -> list[dict[str, Any]]:
    return json.loads((DATASET_DIR / name).read_text(encoding="utf-8"))


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * ratio) - 1)]


def timing_summary(values: list[float]) -> dict[str, float]:
    return {
        "average_ms": round(statistics.fmean(values), 2) if values else 0.0,
        "p95_ms": round(percentile(values, 0.95), 2),
    }


def usage_dict(callback) -> dict[str, int]:
    return {
        "prompt_tokens": int(callback.prompt_tokens),
        "completion_tokens": int(callback.completion_tokens),
        "total_tokens": int(callback.total_tokens),
    }


def add_usage(total: dict[str, int], item: dict[str, int]) -> None:
    for key in total:
        total[key] += item[key]


async def evaluate_routing() -> dict[str, Any]:
    cases = load_cases("routing.json")
    classifier = TaskClassifier(create_chat_model(temperature=0))
    details = []
    latencies = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for case in cases:
        started = time.perf_counter()
        with get_openai_callback() as callback:
            decision = await classifier.classify(case["input"])
        elapsed = (time.perf_counter() - started) * 1000
        tokens = usage_dict(callback)
        if classifier.last_usage["total_tokens"]:
            tokens = {
                key: tokens[key] + classifier.last_usage[key]
                for key in tokens
            }
        add_usage(usage, tokens)
        actual = decision.intent.value
        details.append({
            **case,
            "actual": actual,
            "correct": actual == case["expected"],
            "confidence": decision.confidence,
            "latency_ms": round(elapsed, 2),
            "tokens": tokens,
        })
        latencies.append(elapsed)

    correct = sum(item["correct"] for item in details)
    return {
        "sample_size": len(cases),
        "correct": correct,
        "accuracy": round(correct / len(cases), 4),
        "latency": timing_summary(latencies),
        "tokens": {**usage, "average_per_case": round(usage["total_tokens"] / len(cases), 2)},
        "details": details,
    }


def document_source(document: dict[str, Any]) -> str | None:
    for keyword in document.get("keywords", []):
        if isinstance(keyword, str) and keyword.startswith("source:"):
            return keyword.removeprefix("source:")
    return None


async def evaluate_rag() -> dict[str, Any]:
    cases = load_cases("rag.json")
    service = KnowledgeService(os.getenv("DATABASE_URL", "sqlite:///data/smart_appointment.db"))
    await service.initialize()
    details = []
    latencies = []

    for case in cases:
        started = time.perf_counter()
        documents = await service.search(case["query"], top_k=5)
        elapsed = (time.perf_counter() - started) * 1000
        sources = [source for doc in documents if (source := document_source(doc))]
        relevant_ranks = [
            index for index, source in enumerate(sources, start=1)
            if source in case["expected_sources"]
        ]
        first_rank = min(relevant_ranks) if relevant_ranks else None
        details.append({
            **case,
            "retrieved_sources": sources,
            "first_relevant_rank": first_rank,
            "hit_at_5": first_rank is not None,
            "reciprocal_rank": round(1 / first_rank, 4) if first_rank else 0.0,
            "latency_ms": round(elapsed, 2),
        })
        latencies.append(elapsed)

    hits = sum(item["hit_at_5"] for item in details)
    return {
        "sample_size": len(cases),
        "hits_at_5": hits,
        "hit_rate_at_5": round(hits / len(cases), 4),
        "mrr": round(statistics.fmean(item["reciprocal_rank"] for item in details), 4),
        "latency": timing_summary(latencies),
        "details": details,
    }


def fields_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if isinstance(expected_value, (int, float)):
            try:
                if float(actual_value) != float(expected_value):
                    return False
            except (TypeError, ValueError):
                return False
        elif str(expected_value).lower() not in str(actual_value).lower():
            return False
    return True


async def evaluate_workflows(run_id: str) -> dict[str, Any]:
    cases = load_cases("workflow.json")
    db_file = (RESULT_DIR / f"workflow-{run_id}.db").resolve()
    engine = WorkflowEngine(f"sqlite:///{db_file.as_posix()}")
    details = []
    latencies = []
    tool_calls = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        for case in cases:
            agent = WorkflowAgent(session_id=f"benchmark-{case['id']}", workflow_engine=engine)
            turn_details = []
            draft = None
            for text in case["turns"]:
                started = time.perf_counter()
                with get_openai_callback() as callback:
                    draft = await agent.create_draft(text)
                elapsed = (time.perf_counter() - started) * 1000
                tokens = usage_dict(callback)
                add_usage(usage, tokens)
                latencies.append(elapsed)
                turn_details.append({"input": text, "latency_ms": round(elapsed, 2), "tokens": tokens})

            persisted = engine.get(draft.workflow_id) if draft and draft.workflow_id else None
            type_ok = bool(draft and draft.workflow_type.value == case["expected_type"])
            status_ok = bool(draft and draft.status.value == case["expected_status"])
            fields_ok = bool(draft and fields_match(draft.fields, case["expected_fields"]))
            persistence_ok = bool(persisted and persisted["status"] == case["expected_status"])
            case_tool_calls = agent.tool_registry.audit_records()
            tool_calls.extend(case_tool_calls)
            details.append({
                **case,
                "actual_type": draft.workflow_type.value if draft else None,
                "actual_status": draft.status.value if draft else None,
                "actual_fields": draft.fields if draft else {},
                "workflow_id": draft.workflow_id if draft else None,
                "type_ok": type_ok,
                "status_ok": status_ok,
                "fields_ok": fields_ok,
                "persistence_ok": persistence_ok,
                "success": type_ok and status_ok and fields_ok and persistence_ok,
                "turn_details": turn_details,
                "tool_calls": case_tool_calls,
            })
    finally:
        engine.close()

    success_count = sum(item["success"] for item in details)
    successful_tool_calls = sum(item["success"] for item in tool_calls)
    return {
        "sample_size": len(cases),
        "successful": success_count,
        "task_completion_rate": round(success_count / len(cases), 4),
        "persistence_success_rate": round(sum(item["persistence_ok"] for item in details) / len(cases), 4),
        "tool_calls": len(tool_calls),
        "successful_tool_calls": successful_tool_calls,
        "tool_call_success_rate": round(successful_tool_calls / len(tool_calls), 4) if tool_calls else None,
        "latency_per_turn": timing_summary(latencies),
        "tokens": {**usage, "average_per_turn": round(usage["total_tokens"] / len(latencies), 2)},
        "details": details,
        "database": str(db_file),
    }


def has_repeated_agent_output(output: str) -> bool:
    """Detect the repeated handoff pattern that caused the original UI loop."""
    segments = [part.strip() for part in re.split(r"(?=\[(?:THOUGHT|REPLY)\])", output) if part.strip()]
    return any(segments.count(segment) >= 3 for segment in set(segments))


async def evaluate_e2e(run_id: str) -> dict[str, Any]:
    cases = load_cases("e2e.json")
    details = []
    latencies = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for case in cases:
        chunks: list[str] = []

        async def consume() -> None:
            async for chunk in ProcessUserInput_stream(
                case["input"], conversation_id=f"benchmark-e2e-{run_id}-{case['id']}"
            ):
                chunks.append(chunk)
                if sum(map(len, chunks)) > 12000:
                    raise RuntimeError("output_limit_exceeded")

        started = time.perf_counter()
        timed_out = False
        error = None
        with get_openai_callback() as callback:
            try:
                await asyncio.wait_for(consume(), timeout=30)
            except asyncio.TimeoutError:
                timed_out = True
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        elapsed = (time.perf_counter() - started) * 1000
        output = "".join(chunks)
        repeated = has_repeated_agent_output(output)
        loop_incident = timed_out or repeated or error == "RuntimeError: output_limit_exceeded"
        tokens = usage_dict(callback)
        add_usage(usage, tokens)
        latencies.append(elapsed)
        details.append({
            **case,
            "completed": not timed_out and error is None,
            "loop_incident": loop_incident,
            "timed_out": timed_out,
            "repeated_output": repeated,
            "error": error,
            "output_chars": len(output),
            "latency_ms": round(elapsed, 2),
            "tokens": tokens,
            "output": output,
        })

    incidents = sum(item["loop_incident"] for item in details)
    completed = sum(item["completed"] for item in details)
    return {
        "sample_size": len(cases),
        "completed": completed,
        "completion_rate": round(completed / len(cases), 4),
        "loop_incidents": incidents,
        "loop_incident_rate": round(incidents / len(cases), 4),
        "latency": timing_summary(latencies),
        "tokens": {**usage, "average_per_case": round(usage["total_tokens"] / len(cases), 2)},
        "details": details,
    }


def markdown_report(result: dict[str, Any]) -> str:
    route = result["routing"]
    rag = result["rag"]
    workflow = result["workflow"]
    e2e = result["e2e"]
    failures = [
        *(f"路由 {x['id']}: 期望 {x['expected']}，实际 {x['actual']}" for x in route["details"] if not x["correct"]),
        *(f"RAG {x['id']}: Top-5 未命中，召回 {', '.join(x['retrieved_sources']) or '空'}" for x in rag["details"] if not x["hit_at_5"]),
        *(f"流程 {x['id']}: 类型={x['actual_type']}，状态={x['actual_status']}，字段={x['actual_fields']}" for x in workflow["details"] if not x["success"]),
        *(f"端到端 {x['id']}: timeout={x['timed_out']}，重复输出={x['repeated_output']}，错误={x['error']}" for x in e2e["details"] if x["loop_incident"] or not x["completed"]),
    ]
    failure_text = "\n".join(f"- {item}" for item in failures) or "- 无"
    return f"""# 企业 Multi-Agent 项目基准测试报告

- 测试时间：{result['meta']['tested_at']}
- Chat Provider / Model：{result['meta']['chat_provider']} / {result['meta']['chat_model']}
- Embedding Provider / Model：{result['meta']['embedding_provider']} / {result['meta']['embedding_model']}
- 数据集版本：固定测试集 v1（结果目录保留逐条明细）

## 核心结果

| 指标 | 实测结果 | 样本数 | 延迟 |
|---|---:|---:|---:|
| Agent 路由准确率 | {route['accuracy'] * 100:.1f}% | {route['sample_size']} | 平均 {route['latency']['average_ms']:.0f} ms / P95 {route['latency']['p95_ms']:.0f} ms |
| RAG Hit Rate@5 | {rag['hit_rate_at_5'] * 100:.1f}% | {rag['sample_size']} | 平均 {rag['latency']['average_ms']:.0f} ms / P95 {rag['latency']['p95_ms']:.0f} ms |
| RAG MRR | {rag['mrr']:.3f} | {rag['sample_size']} | 同上 |
| Workflow 多轮任务完成率 | {workflow['task_completion_rate'] * 100:.1f}% | {workflow['sample_size']} | 每轮平均 {workflow['latency_per_turn']['average_ms']:.0f} ms / P95 {workflow['latency_per_turn']['p95_ms']:.0f} ms |
| Workflow 持久化成功率 | {workflow['persistence_success_rate'] * 100:.1f}% | {workflow['sample_size']} | — |
| 端到端完成率 | {e2e['completion_rate'] * 100:.1f}% | {e2e['sample_size']} | 平均 {e2e['latency']['average_ms']:.0f} ms / P95 {e2e['latency']['p95_ms']:.0f} ms |
| 循环异常率 | {e2e['loop_incident_rate'] * 100:.1f}% | {e2e['sample_size']} | 超时/重复输出/超长输出判定 |

## Token 使用

- 路由：共 {route['tokens']['total_tokens']} Token，平均 {route['tokens']['average_per_case']:.1f} Token/请求。
- Workflow：共 {workflow['tokens']['total_tokens']} Token，平均 {workflow['tokens']['average_per_turn']:.1f} Token/轮。
- 端到端：共 {e2e['tokens']['total_tokens']} Token，平均 {e2e['tokens']['average_per_case']:.1f} Token/请求。
- Embedding Provider 的响应未通过 LangChain Chat 回调暴露 Token，因此 RAG Token 不计入。

## 失败案例

{failure_text}

## 简历使用边界

- 以上数字只描述本次固定测试集，不外推到生产流量。
- 当前尚未实现通用 Tool Registry/MCP 执行闭环，因此不写“工具调用成功率”。
- 如需写“从 A 提升到 B”，必须引用同一测试集、同一模型配置下保存的前后两份时间戳报告；不得跨数据集比较。
"""


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-routing", action="store_true")
    parser.add_argument("--skip-rag", action="store_true")
    parser.add_argument("--skip-workflow", action="store_true")
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument(
        "--routing-provider",
        choices=("deepseek", "jev", "jev_hybrid"),
        help="Override ROUTING_PROVIDER for this benchmark run.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    if args.routing_provider:
        os.environ["ROUTING_PROVIDER"] = args.routing_provider
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    result: dict[str, Any] = {
        "meta": {
            "tested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "chat_provider": get_model_provider(),
            "chat_model": os.getenv("LLM_MODEL", "unknown"),
            "routing_provider": os.getenv("ROUTING_PROVIDER", "deepseek"),
            "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "unknown"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "unknown"),
        }
    }

    if not args.skip_routing:
        print("[1/4] evaluating routing...", flush=True)
        result["routing"] = await evaluate_routing()
    if not args.skip_rag:
        print("[2/4] evaluating RAG...", flush=True)
        result["rag"] = await evaluate_rag()
    if not args.skip_workflow:
        print("[3/4] evaluating workflows...", flush=True)
        result["workflow"] = await evaluate_workflows(run_id)
    if not args.skip_e2e:
        print("[4/4] evaluating end-to-end loop safety...", flush=True)
        result["e2e"] = await evaluate_e2e(run_id)

    json_text = json.dumps(result, ensure_ascii=False, indent=2)
    timestamped_json = RESULT_DIR / f"benchmark-{run_id}.json"
    timestamped_json.write_text(json_text, encoding="utf-8")

    if all(section in result for section in ("routing", "rag", "workflow", "e2e")):
        (RESULT_DIR / "latest.json").write_text(json_text, encoding="utf-8")
        report = markdown_report(result)
        timestamped_md = RESULT_DIR / f"benchmark-{run_id}.md"
        timestamped_md.write_text(report, encoding="utf-8")
        (RESULT_DIR / "latest.md").write_text(report, encoding="utf-8")

    print(f"result_json={timestamped_json}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
