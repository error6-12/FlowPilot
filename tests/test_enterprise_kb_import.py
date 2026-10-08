from pathlib import Path

from scripts.import_enterprise_kb import extract_keywords, load_chunks, split_markdown


def test_markdown_splitter_keeps_headings():
    text = "# 制度\n\n总则。\n\n## 申请流程\n\n第一步。\n\n第二步。"
    chunks = split_markdown(text, max_chars=40)

    assert chunks
    assert any("申请流程" in chunk for chunk in chunks)


def test_extract_keywords_supports_chinese_delimiters():
    text = "# 文档\n\n## 关键词\n请假、年假,审批，HR"

    assert extract_keywords(text) == ["请假", "年假", "审批", "HR"]


def test_load_chunks_adds_source_metadata(tmp_path: Path):
    policy_dir = tmp_path / "hr_policy"
    policy_dir.mkdir()
    (policy_dir / "leave.md").write_text(
        "# 请假制度\n\n员工需要提前申请。\n\n## 关键词\n请假、审批",
        encoding="utf-8",
    )

    chunks = load_chunks(tmp_path)

    assert chunks[0].category == "enterprise/hr_policy"
    assert "来源文件：hr_policy/leave.md" in chunks[0].content
    assert "kb:enterprise-agent-kb" in chunks[0].keywords


def test_bundled_kb_contains_meeting_room_weekly_snapshot():
    chunks = load_chunks()
    snapshot_chunks = [
        chunk
        for chunk in chunks
        if chunk.source_file == "admin_service/meeting_room_weekly_snapshot.md"
    ]

    assert snapshot_chunks
    combined = "\n".join(chunk.content for chunk in snapshot_chunks)
    assert "演示基准时间：2026-10-06 14:30" in combined
    assert "当前空闲：A302、A305、B501、B503、C802" in combined
    assert "模拟运营数据" in combined
