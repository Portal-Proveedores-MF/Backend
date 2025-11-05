from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from app.adapters.outbound.firestore_repo import FirestoreRepo
from app.adapters.outbound.gcs_storage import GCSStorage
from app.usecases.process_invoice import ProcessInvoiceUseCase
from app.adapters.outbound.docai_invoice import DocAIInvoiceExtractor
from app.shared.auth import require_user
from app.domain.models import InvoiceDTO, StatusUpdate

router = APIRouter(prefix="/invoices", tags=["invoices"])

repo = FirestoreRepo()
usecase = ProcessInvoiceUseCase(
    storage=GCSStorage(),
    extractor=DocAIInvoiceExtractor(),
    repository=repo
)

class FromUploadBody(BaseModel):
    bucket: str
    name: str
    generation: Optional[str] = None

@router.get("", response_model=list[InvoiceDTO])
def list_invoices(
    status: Optional[str] = Query(None),
    supplierId: Optional[str] = Query(None),   
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    user=Depends(require_user)
):
    # si viene supplierId y es admin, filtramos por RUC
    items, _ = repo.list(
        status=status,
        limit=limit,
        cursor=cursor,
        requester_uid=user["uid"],
        supplier_id=supplierId
    )
    return items


@router.post("/from-upload")
def create_from_upload(body: FromUploadBody, user=Depends(require_user)):
    """Crea/procesa una factura a partir de un PDF ya en GCS."""
    result = usecase.run(
        bucket=body.bucket,
        name=body.name,
        generation=body.generation,
        uploader_uid=user["uid"],
        uploader_email=user.get("email")
    )
    return result

@router.patch("/{supplierId}/{invoiceId}/status")
def change_status(supplierId: str, invoiceId: str, body: StatusUpdate, user=Depends(require_user)):
    doc_id = f"{supplierId}/{invoiceId}"
    if not repo.get(doc_id):
        raise HTTPException(404, "Not found")
    repo.update_status(doc_id, body.status, by_uid=user["uid"])
    return {"ok": True, "doc_id": doc_id, "status": body.status}

@router.post("/{supplierId}/{invoiceId}/reprocess")
def reprocess(supplierId: str, invoiceId: str, user=Depends(require_user)):
    doc_id = f"{supplierId}/{invoiceId}"
    inv = repo.get(doc_id)
    if not inv:
        raise HTTPException(404, "Not found")

    src = inv.get("source", {}) or {
        "bucket": (inv.get("filePath") or "").replace("gs://", "").split("/", 1)[0],
        "name": inv.get("name"),
        "generation": inv.get("generation"),
    }
    result = usecase.run(
        bucket=src.get("bucket"),
        name=src.get("name"),
        generation=src.get("generation"),
        uploader_uid=user["uid"],
        uploader_email=user.get("email")
    )
    return result
