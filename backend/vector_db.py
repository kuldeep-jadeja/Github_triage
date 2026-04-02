"""
Vector database operations using Chroma with multilingual embeddings.
Handles: embed+store, similarity search, upsert lifecycle, bootstrap.
"""

import logging
from typing import List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger(__name__)

# Module-level singletons — loaded once at startup
_embedder: Optional[SentenceTransformer] = None
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


def get_embedder() -> SentenceTransformer:
    """Get or create the embedding model singleton."""
    global _embedder
    if _embedder is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def get_collection() -> chromadb.Collection:
    """Get or create the Chroma collection singleton."""
    global _client, _collection
    if _collection is None:
        logger.info(f"Initializing Chroma at: {settings.chroma_path}")
        _client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _client.get_or_create_collection(
            name="github_issues",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def verify_embedder() -> bool:
    """Verify the embedding model loads and produces valid embeddings."""
    try:
        embedder = get_embedder()
        test_embedding = embedder.encode("test")
        expected_dim = embedder.get_sentence_embedding_dimension()
        if len(test_embedding) != expected_dim:
            logger.error(
                f"Embedding dimension mismatch: got {len(test_embedding)}, expected {expected_dim}"
            )
            return False
        logger.info(f"Embedding model verified: {expected_dim}-dim vectors")
        return True
    except Exception as e:
        logger.error(f"Embedding model verification failed: {e}")
        return False


def embed_and_store_issue(issue: dict) -> None:
    """
    Store or update an issue in the vector DB.
    Uses upsert so re-storing an existing issue updates it.
    """
    collection = get_collection()
    embedder = get_embedder()

    text = f"{issue.get('title', '')}\n{issue.get('body', '')[:2000]}"
    embedding = embedder.encode(text).tolist()

    collection.upsert(
        ids=[str(issue["number"])],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{
            "number": issue["number"],
            "state": issue.get("state", "open"),
            "labels": ",".join(issue.get("labels", [])),
            "created_at": issue.get("created_at", ""),
            "url": issue.get("html_url", ""),
            "title": issue.get("title", ""),
        }],
    )
    logger.debug(f"Stored issue #{issue['number']} in vector DB")


def search_similar(title: str, body: str, top_k: int = 5) -> List[dict]:
    """
    Find similar past issues using cosine similarity.
    Returns list of dicts with number, score, url, state, labels, snippet.
    """
    collection = get_collection()
    embedder = get_embedder()

    if collection.count() == 0:
        logger.info("Vector DB is empty, no similar issues to find")
        return []

    query_text = f"{title}\n{body[:2000]}"
    query_embedding = embedder.encode(query_text).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    similar = []
    for i in range(len(results["ids"][0])):
        score = 1 - results["distances"][0][i]
        metadata = results["metadatas"][0][i]
        similar.append({
            "number": metadata.get("number", 0),
            "score": round(score, 3),
            "url": metadata.get("url", ""),
            "state": metadata.get("state", "unknown"),
            "labels": metadata.get("labels", ""),
            "snippet": results["documents"][0][i][:200] if results["documents"][0][i] else "",
        })

    return similar


def get_collection_size() -> int:
    """Get the number of issues in the vector DB."""
    collection = get_collection()
    return collection.count()
