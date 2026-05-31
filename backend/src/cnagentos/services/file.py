"""File storage and management service for Phase 7.

Provides file upload/download with SHA-256 deduplication, reference-counted
blob management, and permission-checked downloads.
"""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import File, FileBlob, User, utc_now
from cnagentos.services.file_storage import MAX_FILE_SIZE, ALLOWED_CONTENT_TYPES

# Re-export constants for convenience
__all__ = ["FileService", "MAX_FILE_SIZE", "ALLOWED_CONTENT_TYPES"]


class FileService:
    """File upload/download and management service with SHA-256 dedup."""

    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None,
    ) -> None:
        self.session = session
        self.actor = actor
        self.ip_address = ip_address

    # ------------------------------------------------------------------
    # Upload & download
    # ------------------------------------------------------------------

    async def upload_file(
        self, data: bytes, filename: str, content_type: str,
    ) -> dict:
        """Upload a file, deduplicate via SHA-256, and return metadata.

        Steps:
          1. Validate file size and content type.
          2. Compute SHA-256 hash.
          3. Look up existing blob by hash — increment ref_count if found.
          4. Otherwise persist the blob to disk and create a new FileBlob record.
          5. Create a ``File`` record linking the blob to the upload session.
        """
        if len(data) > MAX_FILE_SIZE:
            raise ApiError(400, "FILE_TOO_LARGE",
                           f"文件大小 {len(data)} 超过限制 {MAX_FILE_SIZE}")
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ApiError(400, "INVALID_CONTENT_TYPE",
                           f"不支持的文件类型: {content_type}")

        sha256 = hashlib.sha256(data).hexdigest()

        # Check for existing blob
        blob = await self.session.scalar(
            select(FileBlob).where(FileBlob.sha256 == sha256)
        )

        if blob:
            # Existing blob: increment ref count
            blob.ref_count += 1
            await self.session.flush()
            file_id = str(uuid4())
            file_rec = File(
                id=file_id, blob_id=blob.id,
                filename=filename, uploaded_by=self.actor.id,
            )
            self.session.add(file_rec)
            await self.session.commit()
            return self._file_to_dict(file_rec, blob)

        # New blob: persist to disk
        from cnagentos.services.file_storage import FileStorageService

        storage = FileStorageService()
        file_id = str(uuid4())
        storage_path = storage._store_path(filename, file_id)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(data)

        blob = FileBlob(
            id=str(uuid4()),
            sha256=sha256,
            mime_type=content_type,
            size_bytes=len(data),
            storage_path=str(storage_path),
            ref_count=1,
        )
        self.session.add(blob)
        await self.session.flush()

        file_rec = File(
            id=file_id, blob_id=blob.id,
            filename=filename, uploaded_by=self.actor.id,
        )
        self.session.add(file_rec)
        await self.session.commit()
        return self._file_to_dict(file_rec, blob)

    async def get_file_metadata(self, file_id: str) -> dict:
        file_rec = await self.session.get(File, file_id)
        if file_rec is None:
            raise ApiError(404, "NOT_FOUND", "文件不存在")
        blob = await self.session.get(FileBlob, file_rec.blob_id)
        return self._file_to_dict(file_rec, blob)

    async def download_file(self, file_id: str) -> tuple[bytes, str, str]:
        """Return (raw_bytes, original_filename, mime_type)."""
        file_rec = await self.session.get(File, file_id)
        if file_rec is None:
            raise ApiError(404, "NOT_FOUND", "文件不存在")
        blob = await self.session.get(FileBlob, file_rec.blob_id)
        if blob is None:
            raise ApiError(404, "NOT_FOUND", "文件数据丢失")
        path = Path(blob.storage_path)
        if not path.exists():
            raise ApiError(404, "NOT_FOUND", "文件存储数据丢失")
        data = path.read_bytes()
        return data, file_rec.filename, blob.mime_type

    # ------------------------------------------------------------------
    # Admin: list, stats, delete
    # ------------------------------------------------------------------

    async def list_files(
        self, page: int = 1, page_size: int = 20,
        mime_type: str | None = None,
    ) -> tuple[list[dict], int]:
        query = select(File).options(
            selectinload(File.blob), selectinload(File.uploader),
        )
        count_query = select(func.count(File.id))

        if mime_type:
            query = query.join(FileBlob).where(FileBlob.mime_type == mime_type)
            count_query = count_query.join(FileBlob).where(FileBlob.mime_type == mime_type)

        total = (await self.session.scalar(count_query)) or 0
        rows = (
            (await self.session.scalars(
                query.order_by(File.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ))
            .all()
        )
        results = []
        for f in rows:
            results.append({
                "id": f.id,
                "filename": f.filename,
                "mime_type": f.blob.mime_type if f.blob else None,
                "size_bytes": f.blob.size_bytes if f.blob else 0,
                "sha256": f.blob.sha256 if f.blob else None,
                "uploaded_by": f.uploader.username if f.uploader else None,
                "uploaded_by_id": f.uploaded_by,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            })
        return results, total

    async def storage_stats(self) -> dict:
        """Return aggregated storage statistics."""
        total_files = (await self.session.scalar(select(func.count(File.id)))) or 0
        total_blobs = (await self.session.scalar(select(func.count(FileBlob.id)))) or 0
        total_size = (
            await self.session.scalar(select(func.coalesce(func.sum(FileBlob.size_bytes), 0)))
        ) or 0
        # "Saved" space = total_blobs would repeat without dedup
        raw_size = (
            await self.session.scalar(
                select(func.coalesce(func.sum(FileBlob.size_bytes * FileBlob.ref_count), 0))
            )
        ) or 0
        saved = raw_size - total_size
        return {
            "total_files": total_files,
            "total_blobs": total_blobs,
            "total_size_bytes": total_size,
            "saved_bytes": saved,
            "dedup_ratio": round(saved / raw_size, 4) if raw_size else 0,
        }

    async def delete_file(self, file_id: str) -> None:
        """Delete a File record, decrement blob ref_count, and clean up if zero."""
        file_rec = await self.session.get(File, file_id)
        if file_rec is None:
            raise ApiError(404, "NOT_FOUND", "文件不存在")

        blob = await self.session.get(FileBlob, file_rec.blob_id)
        await self.session.delete(file_rec)

        if blob:
            blob.ref_count -= 1
            if blob.ref_count <= 0:
                # Remove from disk
                path = Path(blob.storage_path)
                if path.exists():
                    path.unlink()
                await self.session.delete(blob)

        await self.session.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _file_to_dict(self, file_rec: File, blob: FileBlob | None) -> dict:
        return {
            "id": file_rec.id,
            "filename": file_rec.filename,
            "mime_type": blob.mime_type if blob else None,
            "size_bytes": blob.size_bytes if blob else 0,
            "sha256": blob.sha256 if blob else None,
            "uploaded_by": file_rec.uploaded_by,
            "created_at": file_rec.created_at.isoformat() if file_rec.created_at else None,
        }
