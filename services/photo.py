import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional


class PhotoService:
    def __init__(self, upload_dir: str = "static/uploads/photos"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "/static/uploads/photos"

    def save_photo(self, file_content: bytes, extension: str = "jpg") -> str:
        filename = f"{uuid.uuid4()}.{extension}"
        file_path = self.upload_dir / filename
        file_path.write_bytes(file_content)
        return filename

    def get_photo_url(self, filename: str) -> Optional[str]:
        if not filename:
            return None
        return f"{self.base_url}/{filename}"

    def delete_photo(self, filename: str) -> bool:
        if not filename:
            return False
        file_path = self.upload_dir / filename
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def validate_photo(
        self, file_content: bytes, max_size_mb: float = 5.0
    ) -> tuple[bool, Optional[str]]:
        if not file_content:
            return False, "No photo provided"

        max_size_bytes = max_size_mb * 1024 * 1024
        if len(file_content) > max_size_bytes:
            return False, f"Photo size exceeds {max_size_mb}MB limit"

        if len(file_content) < 100:
            return False, "Photo is too small or corrupted"

        return True, None


photo_service = PhotoService()
