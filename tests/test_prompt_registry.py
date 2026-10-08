from pathlib import Path

from services.prompt_registry import PromptRegistry


def test_registry_seeds_active_builtin_versions(tmp_path: Path):
    registry = PromptRegistry(f"sqlite:///{(tmp_path / 'prompts.db').as_posix()}")
    active = registry.active_versions()
    assert active == {
        "routing": "1.0.0",
        "consultation_answer": "1.0.0",
        "workflow_extraction": "1.0.0",
    }
    routing = registry.get_active("routing", include_content=False)
    assert routing["content_sha256"]
    assert "content" not in routing


def test_registry_seed_is_idempotent(tmp_path: Path):
    database_url = f"sqlite:///{(tmp_path / 'prompts.db').as_posix()}"
    first = PromptRegistry(database_url)
    second = PromptRegistry(database_url)
    assert len(first.list_versions()) == 3
    assert len(second.list_versions()) == 3
