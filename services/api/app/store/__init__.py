"""Store factory: memory for development, Firestore for deployment."""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import BlobStore, ConflictError, HouseholdRecord, Job, Store
from .blobs import GcsBlobStore, LocalBlobStore
from .memory import MemoryStore


@lru_cache
def get_store() -> Store:
    s = get_settings()
    if s.store == "firestore":
        from .firestore import FirestoreStore

        return FirestoreStore(project=s.project)
    return MemoryStore()


@lru_cache
def get_blobs() -> BlobStore:
    s = get_settings()
    if s.bucket:
        return GcsBlobStore(s.bucket)
    return LocalBlobStore(s.data_dir / "blobs")


__all__ = ["BlobStore", "ConflictError", "HouseholdRecord", "Job", "Store", "get_blobs", "get_store"]
