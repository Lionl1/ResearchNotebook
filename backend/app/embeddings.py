from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

from .config import EMBEDDINGS_DEVICE, EMBEDDINGS_MODEL


def _maybe_prefix(texts: List[str], model: str, is_query: bool) -> List[str]:
    lowered = model.lower()
    if "e5" not in lowered:
        return texts
    prefix = "query" if is_query else "passage"
    return [f"{prefix}: {text}" for text in texts]


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDINGS_MODEL, device=EMBEDDINGS_DEVICE)


def _encode(texts: List[str], is_query: bool) -> List[List[float]]:
    if not texts:
        return []
    model = _get_model()
    prepared = _maybe_prefix(texts, EMBEDDINGS_MODEL, is_query=is_query)
    vectors = model.encode(
        prepared,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


async def embed_texts(texts: List[str]) -> List[List[float]]:
    return _encode(texts, is_query=False)


async def embed_query(text: str) -> List[float]:
    vectors = _encode([text], is_query=True)
    return vectors[0] if vectors else []
