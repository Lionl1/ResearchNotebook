from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Tuple

import chromadb

from .config import CHROMA_DIR

logger = logging.getLogger(__name__)


def _sanitize_collection_name(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).lower()
    safe = safe.strip("_")
    if not safe:
        safe = "notebook"
    if len(safe) < 3:
        safe = f"{safe}_{hashlib.md5(name.encode('utf-8')).hexdigest()[:6]}"
    if len(safe) > 63:
        safe = safe[:50] + "_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:12]
    return safe


def _normalize_json(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {key: _normalize_json(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except Exception:
            return value
    return value


class ChromaVectorStore:
    def __init__(self, persist_dir: str) -> None:
        self._persist_dir = persist_dir
        self._client = chromadb.PersistentClient(path=persist_dir)

    def reset(self) -> None:
        self._client = chromadb.PersistentClient(path=self._persist_dir)

    def _collection_name(self, notebook_id: str) -> str:
        return f"nb_{_sanitize_collection_name(notebook_id)}"

    def _get_collection(self, notebook_id: str):
        name = self._collection_name(notebook_id)
        return self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

    def _delete_by_source_ids(self, collection, source_ids: List[str]) -> None:
        for source_id in source_ids:
            if not source_id:
                continue
            try:
                collection.delete(where={"source_id": source_id})
            except Exception as exc:
                logger.warning("Failed to delete vectors for source %s: %s", source_id, exc)

    def _existing_source_ids(self, notebook_id: str) -> List[str]:
        try:
            collection = self._client.get_collection(self._collection_name(notebook_id))
        except Exception:
            return []
        result = collection.get(include=["metadatas"])
        metadatas = _normalize_json(result.get("metadatas")) or []
        source_ids = {
            (meta or {}).get("source_id")
            for meta in metadatas
            if isinstance(meta, dict) and (meta or {}).get("source_id")
        }
        return sorted(source_ids)

    def upsert(
        self,
        notebook_id: str,
        embeddings: List[List[float]],
        metas: List[Dict[str, Any]],
        prune_missing: bool = False,
    ) -> None:
        collection = self._get_collection(notebook_id)
        source_ids = sorted(
            {
                str(meta.get("source_id"))
                for meta in metas
                if meta.get("source_id")
            }
        )
        if prune_missing:
            existing_ids = set(self._existing_source_ids(notebook_id))
            obsolete_ids = sorted(existing_ids - set(source_ids))
            self._delete_by_source_ids(collection, obsolete_ids)
        self._delete_by_source_ids(collection, source_ids)

        if not embeddings:
            return

        name = self._collection_name(notebook_id)
        ids = []
        for idx, meta in enumerate(metas):
            source_id = meta.get("source_id") or "source"
            chunk_index = meta.get("chunk_index", idx)
            ids.append(f"{name}_{source_id}_{chunk_index}")
        documents = [meta.get("text", "") for meta in metas]
        metadatas = []
        for meta in metas:
            meta_copy = dict(meta)
            meta_copy.pop("text", None)
            metadatas.append(meta_copy)
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "Upserted %d vectors for notebook %s across %d sources",
            len(embeddings),
            notebook_id,
            len(source_ids),
        )

    def replace(self, notebook_id: str, embeddings: List[List[float]], metas: List[Dict[str, Any]]) -> None:
        self.upsert(notebook_id, embeddings, metas, prune_missing=True)

    def export(self, notebook_id: str) -> Dict[str, Any] | None:
        try:
            collection = self._client.get_collection(self._collection_name(notebook_id))
        except Exception:
            return None
        result = collection.get(include=["embeddings", "documents", "metadatas"])
        ids = _normalize_json(result.get("ids")) or []
        embeddings = _normalize_json(result.get("embeddings")) or []
        documents = _normalize_json(result.get("documents")) or []
        metadatas = _normalize_json(result.get("metadatas")) or []
        if not ids or not embeddings:
            return None
        return {
            "ids": ids,
            "embeddings": embeddings,
            "documents": documents,
            "metadatas": metadatas,
        }

    def import_data(self, notebook_id: str, data: Dict[str, Any]) -> None:
        ids = data.get("ids") or []
        embeddings = data.get("embeddings") or []
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        if not ids or not embeddings:
            return
        self.delete(notebook_id)
        collection = self._get_collection(notebook_id)
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def has(self, notebook_id: str) -> bool:
        name = self._collection_name(notebook_id)
        try:
            self._client.get_collection(name)
            return True
        except Exception:
            return False

    def count(self, notebook_id: str) -> int:
        name = self._collection_name(notebook_id)
        try:
            collection = self._client.get_collection(name)
            return int(collection.count())
        except Exception:
            return 0

    def search(self, notebook_id: str, query: List[float], top_k: int) -> List[Tuple[float, Dict[str, Any]]]:
        if not query or top_k <= 0:
            return []
        try:
            collection = self._client.get_collection(self._collection_name(notebook_id))
        except Exception:
            return []

        result = collection.query(
            query_embeddings=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        output: List[Tuple[float, Dict[str, Any]]] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            meta = dict(meta or {})
            meta["text"] = doc or ""
            score = 1.0 - float(dist) if dist is not None else 0.0
            output.append((score, meta))
        return output

    def delete(self, notebook_id: str) -> None:
        name = self._collection_name(notebook_id)
        try:
            self._client.delete_collection(name)
        except Exception:
            return

    def delete_source(self, notebook_id: str, source_id: str) -> None:
        if not source_id:
            return
        try:
            collection = self._client.get_collection(self._collection_name(notebook_id))
        except Exception:
            return
        self._delete_by_source_ids(collection, [source_id])


VECTOR_STORE = ChromaVectorStore(CHROMA_DIR)
