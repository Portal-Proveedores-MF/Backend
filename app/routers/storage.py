from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from pathlib import Path
import re

from google.cloud import storage

from app.shared.auth import require_user
from app.adapters.outbound.firestore_repo import FirestoreRepo
from app.config import settings

router = APIRouter(prefix="/storage", tags=["storage"])
_repo = FirestoreRepo()
_storage = storage.Client()

def _parse_gs_uri(gs_uri: str):
    # gs://bucket/path/to/file.pdf -> (bucket, name)
    if not gs_uri or not gs_uri.startswith("gs://"):
        return None, None
    rest = gs_uri[5:]
    bucket, _, name = rest.partition("/")
    return bucket, name

def _sign_get(bucket: str, name: str, minutes: int = 10) -> str:
    blob = _storage.bucket(bucket).blob(name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=minutes),
        method="GET",
        response_disposition=f'inline; filename="{Path(name).name}"',
    )

def _sign_put(bucket: str, name: str, minutes: int = 10) -> str:
    blob = _storage.bucket(bucket).blob(name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=minutes),
        method="PUT",
        content_type="application/pdf",
    )

class UploadUrlBody(BaseModel):
    filename: str


@router.get("/view-url/{supplier_id}/{invoice_id}")
def signed_view_url(supplier_id: str, invoice_id: str, user=Depends(require_user)):
    doc_id = f"{supplier_id}/{invoice_id}"

    inv = _repo.get(doc_id)
    if not inv:
        raise HTTPException(404, "Not found")

    # dueño o admin
    if not _repo.is_admin(user["uid"]) and inv.get("supplierUid") != user["uid"]:
        raise HTTPException(403, "Forbidden")

    bucket, name = _parse_gs_uri(inv.get("filePath", ""))
    if not bucket or not name:
        raise HTTPException(400, "Invalid filePath")

    url = _sign_get(bucket, name, minutes=10)
    return {"url": url}


@router.post("/upload-url")
def get_upload_url(body: UploadUrlBody, user=Depends(require_user)):
    # Ruta destino controlada por el backend (evita colisiones)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", body.filename or "invoice.pdf")
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    name = f"uploads/{user['uid']}/{ts}-{safe}"
    bucket = settings.GCS_BUCKET

    url = _sign_put(bucket, name, minutes=10)
    return {"url": url, "bucket": bucket, "name": name}
