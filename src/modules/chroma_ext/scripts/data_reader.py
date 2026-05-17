from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import docx2txt

from service.logger import LoggerConfigurator


@dataclass
class DocumentChunk:
    """A single document chunk ready for indexing into ChromaDB."""

    id: str
    text: str
    metadata: dict[str, Any]


def _read_docx(path: Path) -> str:
    """Read a .docx file into a unicode string."""
    text = docx2txt.process(str(path)) or ""
    return text.strip()


def _split_into_chunks(
    text: str,
    chunk_size: int = 1024,
    chunk_overlap: int = 256,
) -> List[str]:
    """Split text into overlapping chunks of fixed character size."""
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        chunks.append(chunk)

        if end >= length:
            break

        start = end - chunk_overlap

    return chunks


def _calc_signature(text: str) -> str:
    """Compute MD5 hash of the file content for change detection."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _build_topic_prefix(full_text: str, max_tokens: int = 256) -> str:
    """Build a topic context prefix from the first max_tokens words of the document."""
    if not full_text:
        return ""

    tokens = full_text.split()
    topic_tokens = tokens[:max_tokens]
    prefix = " ".join(topic_tokens)
    return prefix


def load_docx_with_metadata(
    logger: LoggerConfigurator,
    root_dir: str | Path,
    chunk_size: int = 750,
    chunk_overlap: int = 250,
    topic_tokens: int = 120,
) -> List[DocumentChunk]:
    """Walk root_dir, read all .docx files, and return a list of chunks with metadata.

    Chunk ID format: "<rel_path>::chunk:<idx>", e.g. "contracts/doc.docx::chunk:0"

    Each chunk is prefixed with the document's opening topic context (first topic_tokens words)
    so that every chunk carries document-level context.

    Args:
        logger: Logger instance.
        root_dir: Root directory containing .docx files organized into topic subfolders.
        chunk_size: Character size of each chunk.
        chunk_overlap: Overlap between consecutive chunks in characters.
        topic_tokens: Number of words to use as the topic prefix from the document start.

    Returns:
        List of DocumentChunk objects ready for ChromaDB ingestion.
    """
    root = Path(root_dir)
    chunks: List[DocumentChunk] = []

    logger.debug("Loading docx with metadata...")
    for path in root.rglob("*.docx"):
        full_text = _read_docx(path)
        if not full_text:
            continue

        rel_path = path.relative_to(root)
        rel_path_str = str(rel_path).replace(os.sep, "/")
        file_signature = _calc_signature(full_text)

        # Topic is derived from the first-level subfolder name
        topic = rel_path.parts[0] if len(rel_path.parts) > 1 else "general"

        topic_prefix = _build_topic_prefix(full_text, max_tokens=topic_tokens)

        text_chunks = _split_into_chunks(
            text=full_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        num_chunks = len(text_chunks)

        for idx, base_chunk_text in enumerate(text_chunks):
            doc_id = f"{rel_path_str}::chunk:{idx}"

            if topic_prefix:
                chunk_text = (
                    "# Document title context: \n\n"
                    + topic_prefix
                    + "\n\n"
                    + "## Document excerpt: \n\n"
                    + base_chunk_text
                    + "\n\n"
                )
            else:
                chunk_text = base_chunk_text

            metadata: dict[str, Any] = {
                "source": str(path),
                "rel_path": rel_path_str,
                "topic": topic,
                "filename": path.name,
                "extension": path.suffix,
                "chunk_index": idx,
                "num_chunks": num_chunks,
                "file_signature": file_signature,
                "topic_prefix_tokens": topic_tokens,
            }

            chunks.append(
                DocumentChunk(
                    id=doc_id,
                    text=chunk_text,
                    metadata=metadata,
                )
            )

    return chunks
