"""Where uploaded files (photos, PDFs, voice notes) are kept: local disk or Cloud Storage."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("invalid key")
        return path

    async def put(self, key: str, data: bytes, mime_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return key

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        if not path.exists():
            return None
        return await asyncio.to_thread(path.read_bytes)

    async def delete_prefix(self, prefix: str) -> None:
        path = self._path(prefix)
        if path.is_dir():
            await asyncio.to_thread(shutil.rmtree, path, True)
        elif path.exists():
            path.unlink()


class GcsBlobStore:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage

        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket)

    async def put(self, key: str, data: bytes, mime_type: str) -> str:
        blob = self.bucket.blob(key)
        await asyncio.to_thread(blob.upload_from_string, data, content_type=mime_type)
        return key

    async def get(self, key: str) -> bytes | None:
        blob = self.bucket.blob(key)
        exists = await asyncio.to_thread(blob.exists)
        if not exists:
            return None
        return await asyncio.to_thread(blob.download_as_bytes)

    async def delete_prefix(self, prefix: str) -> None:
        blobs = await asyncio.to_thread(lambda: list(self.client.list_blobs(self.bucket, prefix=prefix)))
        for blob in blobs:
            await asyncio.to_thread(blob.delete)
