import csv
import io
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader

from .models import InputAttachment

ALLOWED_TYPES = {
    "application/pdf",
    "text/csv",
    "image/png",
    "image/jpeg",
}
MAX_FILE_BYTES = 10 * 1024 * 1024


async def normalize_upload(upload: UploadFile, target_dir: Path) -> InputAttachment:
    content = await upload.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"{upload.filename} exceeds the 10 MB upload limit.")
    if upload.content_type not in ALLOWED_TYPES:
        raise ValueError(f"{upload.filename} has an unsupported content type.")

    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.filename or "upload").name
    (target_dir / safe_name).write_bytes(content)

    if upload.content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(content))
        text = " ".join((page.extract_text() or "") for page in reader.pages[:10])
        summary = f"PDF with {len(reader.pages)} pages. Extract: {text[:1200]}"
    elif upload.content_type == "text/csv":
        decoded = content.decode("utf-8", errors="replace")
        rows = list(csv.reader(io.StringIO(decoded)))[:8]
        summary = "CSV preview: " + " | ".join(", ".join(row[:8]) for row in rows)
    else:
        summary = (
            f"{upload.content_type} image ({len(content):,} bytes) supplied as "
            "multimodal context for the research plan."
        )

    return InputAttachment(
        name=safe_name,
        content_type=upload.content_type,
        bytes=len(content),
        summary=summary,
    )
