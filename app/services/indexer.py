"""Materials indexer (feature 6.3, RAG ingestion).

Walks the presentations tree, extracts text from each material, chunks it, embeds the
chunks, and upserts them into the vector store. Triggered by the owner ``/reindex`` command
(and, later, the nightly precompute job).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.domain.lesson_map import LessonMap
from app.services.content_extraction import extract_text
from app.services.drive import DriveService
from app.services.drive_parser import file_id, file_name, is_folder, walk_materials
from app.services.vectorstore import ChunkRecord, Embedder, VectorStore

_log = get_logger("indexer")

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


def chunk_text(text: str, *, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character windows, trimmed to whitespace boundaries."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    step = max(size - overlap, 1)
    while start < len(cleaned):
        chunks.append(cleaned[start : start + size])
        start += step
    return chunks


class MaterialsIndexer:
    """Indexes course materials into the vector store."""

    def __init__(
        self,
        drive: DriveService,
        lesson_map: LessonMap,
        embedder: Embedder,
        store: VectorStore,
    ) -> None:
        self._drive = drive
        self._map = lesson_map
        self._embedder = embedder
        self._store = store

    async def reindex(self) -> int:
        """Rebuild the index from scratch. Returns the number of chunks indexed."""
        await self._store.clear()
        children = await self._drive.list_children(self._map.roots.presentations_folder)
        lesson_folders = [c for c in children if is_folder(c)]
        total = 0
        for folder in lesson_folders:
            lesson_key = file_name(folder)
            materials = await walk_materials(self._drive, file_id(folder))
            for material in materials:
                text = await extract_text(
                    self._drive,
                    {"id": material.drive_file_id, "name": material.name, "mimeType": ""},
                )
                chunks = chunk_text(text)
                if not chunks:
                    continue
                embeddings = await self._embedder.embed(chunks)
                for index, (chunk, embedding) in enumerate(
                    zip(chunks, embeddings, strict=False)
                ):
                    await self._store.upsert(
                        ChunkRecord(
                            chunk_id=f"{material.drive_file_id}:{index}",
                            drive_file_id=material.drive_file_id,
                            name=material.name,
                            view_url=material.view_url,
                            text=chunk,
                            lesson_key=lesson_key,
                        ),
                        embedding,
                    )
                    total += 1
        _log.info("reindex_complete", chunks=total)
        return total
