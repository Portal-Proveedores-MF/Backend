from typing import Any, Dict, List, Optional, Tuple
from google.cloud import firestore
from app.config import settings

def _parse_doc_id(doc_id: str) -> Tuple[str, str]:
    if "/" not in doc_id:
        raise ValueError("doc_id debe ser 'supplierId/invoiceId'")
    supplier_id, invoice_id = doc_id.split("/", 1)
    return supplier_id, invoice_id

class FirestoreRepo:
    def __init__(self):
        self.db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        self.suppliers_coll = getattr(settings, "FIRESTORE_SUPPLIERS_COLL", "suppliers")
        self.invoices_sub   = getattr(settings, "FIRESTORE_INVOICES_SUB", "invoices")
        self.events_sub     = getattr(settings, "FIRESTORE_EVENTS_SUB", "events")

    # ---------- USUARIOS ----------
    def get_user_snapshot(self, uid: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("users").document(uid).get()
        return doc.to_dict() if doc.exists else None

    def is_admin(self, uid: str) -> bool:
        data = self.get_user_snapshot(uid)
        return (data or {}).get("role") == "admin"

    # ---------- REFS ----------
    def _inv_ref(self, supplier_id: str, invoice_id: str):
        return (self.db.collection(self.suppliers_coll)
                    .document(supplier_id)
                    .collection(self.invoices_sub)
                    .document(invoice_id))

    def _events_ref(self, invoice_id: str):
        # eventos por invoiceId en colección raíz "invoices/{invoiceId}/events"
        return (self.db.collection("invoices")
                    .document(invoice_id)
                    .collection(self.events_sub))

    # ---------- CRUD ----------
    def invoice_exists(self, supplier_id: str, invoice_id: str) -> bool:
        return self._inv_ref(supplier_id, invoice_id).get().exists

    def save_invoice(self, supplier_id: str, invoice_id: str, data: Dict[str, Any]) -> None:
        self._inv_ref(supplier_id, invoice_id).set(data, merge=True)

    def get_invoice(self, supplier_id: str, invoice_id: str) -> Optional[Dict[str, Any]]:
        snap = self._inv_ref(supplier_id, invoice_id).get()
        return snap.to_dict() if snap.exists else None

    def list_invoices(
        self,
        supplier_uid: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        supplier_id: Optional[str] = None,  # RUC explícito (solo admin)
    ) -> List[Dict[str, Any]]:
        if supplier_id:
            # listado solo de ese RUC
            query = (self.db.collection(self.suppliers_coll)
                        .document(supplier_id)
                        .collection(self.invoices_sub))
        elif supplier_uid:
            # listado por UID (para no-admin)
            query = self.db.collection_group(self.invoices_sub).where("supplierUid", "==", supplier_uid)
        else:
            # admin global
            query = self.db.collection_group(self.invoices_sub)

        if status:
            query = query.where("status", "==", status)

        # Requiere índice (collectionGroup + order_by createdAt)
        docs = query.order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return [d.to_dict() | {"id": d.id, "supplierId": d.reference.parent.parent.id} for d in docs]

    # ---------- EVENTOS / ESTADO ----------
    def add_event(self, invoice_id: str, event: Dict[str, Any]) -> None:
        self._events_ref(invoice_id).add(event)

    def update_invoice_status(self, supplier_id: str, invoice_id: str, status: str, by_uid: Optional[str] = None):
        # Actualiza estado en la factura y registra evento
        self._inv_ref(supplier_id, invoice_id).update({
            "status": status,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        self.add_event(invoice_id, {
            "action": f"STATUS_{status.upper()}",
            "byUid": by_uid,
            "at": firestore.SERVER_TIMESTAMP
        })

    # ---------- Wrappers usados por el router ----------
    def list(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
        *,
        requester_uid: Optional[str] = None,
        supplier_id: Optional[str] = None
    ):
        suid = None
        # si NO es admin, forzamos filtro por su UID (ignora RUC)
        if requester_uid and not self.is_admin(requester_uid):
            suid = requester_uid
            supplier_id = None

        items = self.list_invoices(
            supplier_uid=suid,
            status=status,
            limit=limit,
            supplier_id=supplier_id
        )
        return items, None

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        supplier_id, invoice_id = _parse_doc_id(doc_id)
        return self.get_invoice(supplier_id, invoice_id)

    def update_status(self, doc_id: str, status: str, by_uid: Optional[str] = None):
        supplier_id, invoice_id = _parse_doc_id(doc_id)
        self.update_invoice_status(supplier_id, invoice_id, status, by_uid=by_uid)

    # ---------- Stats (usado por /invoices/stats/summary) ----------
    def stats(self) -> Dict[str, Any]:
        cg = self.db.collection_group(self.invoices_sub)
        statuses = ["parsed", "observed", "approved", "paid"]
        out: Dict[str, int] = {}
        for s in statuses:
            out[s] = len(list(cg.where("status", "==", s).limit(1000).stream()))
        out["total"] = len(list(cg.limit(1000).stream()))
        return out
