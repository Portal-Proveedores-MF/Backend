from typing import Protocol, Optional, Dict, Any
from dataclasses import dataclass
from app.domain.models import InvoiceExtraction, Entity
from google.cloud import firestore

# Puertos
class StoragePort(Protocol):
    def download_to_tmp(self, bucket: str, name: str) -> str: ...

class DocAIPort(Protocol):
    def extract_invoice(self, local_pdf_path: str) -> InvoiceExtraction: ...

class RepositoryPort(Protocol):
    def invoice_exists(self, supplier_id: str, invoice_id: str) -> bool: ...
    def save_invoice(self, supplier_id: str, invoice_id: str, payload: dict) -> None: ...
    def add_event(self, invoice_id: str, event: dict) -> None: ...
    # NUEVO
    def get_user_snapshot(self, uid: str) -> Optional[Dict[str, Any]]: ...

@dataclass
class ProcessInvoiceUseCase:
    storage: StoragePort
    extractor: DocAIPort
    repository: RepositoryPort

    def _find(self, entities: list[Entity], etype: str) -> Optional[str]:
        for e in entities:
            if e.type == etype:
                return e.text
        return None

    def _normalize(
        self,
        extraction: InvoiceExtraction,
        bucket: str,
        name: str,
        generation: Optional[str],
        uploader_uid: Optional[str] = None,
        uploader_email: Optional[str] = None,
        supplier_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        es = extraction.entities

        supplier_id      = self._find(es, "supplier_tax_id") or "unknown"
        invoice_id       = self._find(es, "invoice_id") or f"{name}"
        total            = self._find(es, "total_amount")
        total_tax        = self._find(es, "total_tax_amount")
        net_amount       = self._find(es, "net_amount")
        currency         = self._find(es, "currency")               # "SOLES", "PEN", etc.
        issue_date       = self._find(es, "invoice_date")           # fecha de emisión
        due_date         = self._find(es, "due_date")               # vencimiento (si viene)
        supplier_name    = self._find(es, "supplier_name")
        supplier_address = self._find(es, "supplier_address")

        normalized = {
            "supplierId": supplier_id,
            "invoiceId": invoice_id,
            "filePath": f"gs://{bucket}/{name}",
            "name": name,
            "generation": generation,
            "engine": "docai",
            "schemaVersion": extraction.schema_version,

            "currency": currency,
            "total": total,
            "totalTax": total_tax,
            "netAmount": net_amount,
            "issueDate": issue_date,       
            "dueDate": due_date,
            "supplierName": supplier_name,  
            "supplierAddress": supplier_address, 

            "supplierUid": uploader_uid,
            "supplierSnapshot": supplier_snapshot or {},
            "createdBy": {"uid": uploader_uid, "email": uploader_email},
            "status": "parsed",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,

            "raw": {"entities": [e.__dict__ for e in es]},
        }
        return supplier_id, invoice_id, normalized

    def run(
        self,
        bucket: str,
        name: str,
        generation: Optional[str] = None,
        uploader_uid: Optional[str] = None,
        uploader_email: Optional[str] = None,
    ) -> dict:
        local_path  = self.storage.download_to_tmp(bucket, name)
        extraction  = self.extractor.extract_invoice(local_path)

        snap = None
        if uploader_uid:
            snap = self.repository.get_user_snapshot(uploader_uid)  # {supplierProfile:{...}, email,...}

        supplier_id, invoice_id, payload = self._normalize(
            extraction, bucket, name, generation,
            uploader_uid=uploader_uid,
            uploader_email=uploader_email,
            supplier_snapshot=(snap or {}).get("supplierProfile", {})
        )

        unique_id = f"{bucket}:{name}:{generation or 'nog'}"
        if self.repository.invoice_exists(supplier_id, invoice_id):
            self.repository.add_event(invoice_id, {
                "action": "SKIPPED_DUPLICATE",
                "note": unique_id,
                "at": firestore.SERVER_TIMESTAMP
            })
            return {"ok": True, "doc_id": f"{supplier_id}/{invoice_id}", "skipped": True}

        self.repository.save_invoice(supplier_id, invoice_id, payload)
        self.repository.add_event(invoice_id, {
            "action": "EXTRACTED",
            "note": unique_id,
            "at": firestore.SERVER_TIMESTAMP
        })
        return {"ok": True, "doc_id": f"{supplier_id}/{invoice_id}", "skipped": False}
