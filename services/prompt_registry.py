"""Persistent, read-first prompt registry for traceable Agent releases."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from db.base import SessionManager
from db.models import PromptVersion
from services.prompt_catalog import BUILTIN_PROMPTS


class PromptRegistry:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///data/smart_appointment.db")
        self.sessions = SessionManager(self.database_url)
        self.seed_builtins()

    def seed_builtins(self) -> None:
        with self.sessions.session_scope() as session:
            for name, (version, content, note) in BUILTIN_PROMPTS.items():
                exists = session.query(PromptVersion).filter_by(prompt_name=name, version=version).first()
                if exists:
                    continue
                active_exists = session.query(PromptVersion).filter_by(prompt_name=name, is_active=True).first()
                session.add(PromptVersion(
                    prompt_name=name,
                    version=version,
                    content=content,
                    change_note=note,
                    is_active=active_exists is None,
                ))

    @staticmethod
    def _to_dict(item: PromptVersion, include_content: bool = False) -> dict[str, Any]:
        result = {
            "name": item.prompt_name,
            "version": item.version,
            "change_note": item.change_note,
            "is_active": bool(item.is_active),
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "content_sha256": hashlib.sha256(item.content.encode("utf-8")).hexdigest(),
        }
        if include_content:
            result["content"] = item.content
        return result

    def get_active(self, name: str, include_content: bool = True) -> dict[str, Any]:
        with self.sessions.session_scope() as session:
            item = session.query(PromptVersion).filter_by(prompt_name=name, is_active=True).first()
            if item is None:
                raise KeyError(f"No active prompt: {name}")
            return self._to_dict(item, include_content=include_content)

    def active_content(self, name: str) -> str:
        return str(self.get_active(name, include_content=True)["content"])

    def active_versions(self) -> dict[str, str]:
        with self.sessions.session_scope() as session:
            items = session.query(PromptVersion).filter_by(is_active=True).all()
            return {item.prompt_name: item.version for item in items}

    def list_versions(self, name: str | None = None, include_content: bool = False) -> list[dict[str, Any]]:
        with self.sessions.session_scope() as session:
            query = session.query(PromptVersion)
            if name:
                query = query.filter_by(prompt_name=name)
            items = query.order_by(PromptVersion.prompt_name, PromptVersion.id.desc()).all()
            return [self._to_dict(item, include_content=include_content) for item in items]


prompt_registry = PromptRegistry()
