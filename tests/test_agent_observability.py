from api.agent_observability import AgentTraceStore


def test_trace_store_records_success_without_message_content():
    store = AgentTraceStore(max_traces=10)
    trace_id = store.start("conversation-1", input_chars=12)
    store.finish(trace_id, output_chars=24, output_chunks=3)

    trace = store.recent(1)[0]
    assert trace["status"] == "success"
    assert trace["input_chars"] == 12
    assert trace["output_chars"] == 24
    assert trace["output_chunks"] == 3
    assert "message" not in trace
    assert "content" not in trace


def test_trace_records_active_prompt_versions():
    store = AgentTraceStore(max_traces=10)
    trace_id = store.start(
        "conversation-versioned",
        input_chars=3,
        prompt_versions={"routing": "1.0.0"},
    )
    store.finish(trace_id, output_chars=4, output_chunks=1)
    assert store.get(trace_id)["prompt_versions"] == {"routing": "1.0.0"}


def test_trace_store_summary_includes_success_rate_and_latency():
    store = AgentTraceStore(max_traces=10)
    successful = store.start("conversation-1", input_chars=5)
    failed = store.start("conversation-2", input_chars=7)
    store.finish(successful, output_chars=10, output_chunks=2)
    store.finish(failed, output_chars=0, output_chunks=0, error=RuntimeError("failed"))

    summary = store.summary()
    assert summary["total_requests"] == 2
    assert summary["successful_requests"] == 1
    assert summary["failed_requests"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["average_latency_ms"] is not None


def test_trace_store_is_bounded():
    store = AgentTraceStore(max_traces=2)
    for index in range(3):
        trace_id = store.start(f"conversation-{index}", input_chars=index)
        store.finish(trace_id, output_chars=index, output_chunks=1)

    assert len(store.recent(10)) == 2


def test_trace_detail_and_analytics_expose_only_execution_metadata():
    store = AgentTraceStore(max_traces=10)
    successful = store.start("conversation-1", input_chars=5)
    failed = store.start("conversation-2", input_chars=7)
    store.finish(successful, output_chars=10, output_chunks=2)
    store.finish(failed, output_chars=0, output_chunks=0, error=ValueError("secret text"))

    detail = store.get(failed)
    analytics = store.analytics()
    assert detail["error_type"] == "ValueError"
    assert "secret text" not in str(detail)
    assert analytics["status_distribution"] == {"success": 1, "error": 1}
    assert analytics["error_distribution"] == {"ValueError": 1}
    assert len(analytics["trend"]) == 2
