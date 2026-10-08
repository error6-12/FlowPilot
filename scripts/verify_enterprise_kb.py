"""Run a small live retrieval smoke test for the enterprise knowledge base."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.knowledge_service import KnowledgeService


async def main() -> None:
    service = KnowledgeService()
    await service.initialize()
    results = await service.search("普通员工在上海出差，住宿标准是多少？", top_k=3)
    print(f"active_docs={len(service.get_all_documents())}")
    for index, result in enumerate(results, start=1):
        source = next(
            (
                keyword.split(":", 1)[1]
                for keyword in result.get("keywords", [])
                if keyword.startswith("source:")
            ),
            "unknown",
        )
        print(
            f"rank={index} score={result['score']:.4f} "
            f"category={result['category']} source={source}"
        )


if __name__ == "__main__":
    asyncio.run(main())
