"""Import the bundled enterprise Markdown knowledge base into the configured database + FAISS.

The importer is idempotent: previously imported enterprise chunks are soft
deleted only after every new embedding has been generated successfully.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.model_provider import create_embedding_model
from config.database import DatabaseConfig
from db.models import Base, KnowledgeDocument


DEFAULT_SOURCE = PROJECT_ROOT / "knowledge_base" / "enterprise-agent-kb"
IMPORT_MARKER = "kb:enterprise-agent-kb"
LEGACY_CATEGORIES = {
    "营业时间",
    "服务项目",
    "技师信息",
    "门店地址",
    "服务介绍",
    "服务质量",
    "预约政策",
    "会员服务",
}


@dataclass(frozen=True)
class KnowledgeChunk:
    content: str
    category: str
    keywords: list[str]
    source_file: str


def split_markdown(text: str, max_chars: int = 1800, overlap_chars: int = 180) -> list[str]:
    """Split Markdown on headings/paragraphs while keeping useful context."""
    blocks = re.split(r"(?=^#{1,4}\s+)", text.strip(), flags=re.MULTILINE)
    units: list[str] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) <= max_chars:
            units.append(block)
            continue

        heading_match = re.match(r"^(#{1,4}\s+[^\n]+)", block)
        heading = heading_match.group(1) if heading_match else ""
        body = block[len(heading):].strip() if heading else block
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
        current = heading

        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip()
            if current and len(candidate) > max_chars:
                units.append(current.strip())
                tail = current[-overlap_chars:] if overlap_chars else ""
                current = f"{heading}\n\n{tail}\n\n{paragraph}".strip()
            else:
                current = candidate
        if current.strip():
            units.append(current.strip())

    # Markdown often contains many very small subsections. Pack adjacent units
    # into retrieval-sized chunks so headings survive without creating hundreds
    # of tiny, expensive embeddings.
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)

    return chunks


def extract_keywords(text: str) -> list[str]:
    match = re.search(r"^##\s*关键词\s*$([\s\S]*)", text, flags=re.MULTILINE)
    if not match:
        return []
    first_content_line = next(
        (line.strip() for line in match.group(1).splitlines() if line.strip()),
        "",
    )
    return [item.strip() for item in re.split(r"[、,，]", first_content_line) if item.strip()]


def load_chunks(source_dir: Path = DEFAULT_SOURCE) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for path in sorted(source_dir.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        relative = path.relative_to(source_dir).as_posix()
        department = relative.split("/", 1)[0]
        text = path.read_text(encoding="utf-8")
        document_keywords = extract_keywords(text)

        for index, section in enumerate(split_markdown(text), start=1):
            heading = re.search(r"^#{1,4}\s+(.+)$", section, flags=re.MULTILINE)
            section_title = heading.group(1).strip() if heading else path.stem
            metadata_header = (
                f"来源文件：{relative}\n"
                f"知识分区：{department}\n"
                f"章节：{section_title}\n\n"
            )
            chunks.append(
                KnowledgeChunk(
                    content=metadata_header + section,
                    category=f"enterprise/{department}",
                    keywords=[
                        IMPORT_MARKER,
                        f"source:{relative}",
                        f"section:{index}",
                        path.stem,
                        section_title,
                        *document_keywords,
                    ],
                    source_file=relative,
                )
            )
    return chunks


def import_chunks(chunks: list[KnowledgeChunk], replace_legacy: bool = True) -> dict:
    load_dotenv(PROJECT_ROOT / ".env")
    model = create_embedding_model()
    embeddings = model.embed_documents(
        [f"{chunk.content}\n关键词：{' '.join(chunk.keywords)}" for chunk in chunks]
    )
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding count does not match chunk count")

    import os

    database_url = DatabaseConfig().connection_string
    engine = create_engine(database_url, **DatabaseConfig(database_url).get_engine_kwargs())
    Base.metadata.create_all(engine)
    deactivated = 0

    with Session(engine) as session:
        active_documents = session.query(KnowledgeDocument).filter(
            KnowledgeDocument.is_active == 1
        ).all()
        for document in active_documents:
            keywords = document.keywords or []
            is_previous_import = IMPORT_MARKER in keywords
            is_legacy = replace_legacy and document.category in LEGACY_CATEGORIES
            if is_previous_import or is_legacy:
                document.is_active = 0
                deactivated += 1

        for chunk, embedding in zip(chunks, embeddings):
            session.add(
                KnowledgeDocument(
                    content=chunk.content,
                    category=chunk.category,
                    keywords=chunk.keywords,
                    embedding=embedding,
                )
            )
        session.commit()

    engine.dispose()
    return {
        "source_files": len({chunk.source_file for chunk in chunks}),
        "chunks_imported": len(chunks),
        "documents_deactivated": deactivated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import enterprise Markdown knowledge")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--keep-legacy", action="store_true")
    args = parser.parse_args()

    chunks = load_chunks(args.source)
    if not chunks:
        raise SystemExit("No Markdown chunks found")
    result = import_chunks(chunks, replace_legacy=not args.keep_legacy)
    print(
        "import_ok=True "
        f"source_files={result['source_files']} "
        f"chunks_imported={result['chunks_imported']} "
        f"documents_deactivated={result['documents_deactivated']}"
    )


if __name__ == "__main__":
    main()
