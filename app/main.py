import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.domain.models import GcsEvent
from app.shared.logging import setup_logging
from app.usecases.process_invoice import ProcessInvoiceUseCase
from app.adapters.outbound.gcs_storage import GCSStorage
from app.adapters.outbound.docai_invoice import DocAIInvoiceExtractor
from app.adapters.outbound.firestore_repo import FirestoreRepo
from app.routers import invoices as invoices_router
from app.routers import storage as storage_router

setup_logging()
log = logging.getLogger("invoices")

app = FastAPI(title="Invoices Backend")
app.include_router(invoices_router.router)
app.include_router(storage_router.router)  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://neo-portal-proveedores-477002.web.app", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

usecase = ProcessInvoiceUseCase(
    storage=GCSStorage(),
    extractor=DocAIInvoiceExtractor(),
    repository=FirestoreRepo(),
)

@app.get("/health")
def health():
    return {"ok": True, "env": settings.APP_ENV}

@app.post("/")
async def handle_event(payload: GcsEvent):
    try:
        bucket = payload.data.bucket
        name = payload.data.name
        generation = payload.data.generation
        result = usecase.run(bucket=bucket, name=name, generation=generation)
        log.info("processed", extra={"bucket": bucket, "obj_name": name, "result": result})
        return result
    except Exception as e:
        log.error("error_processing", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/env-check")
def env_check():
    return {
        "project": settings.GOOGLE_CLOUD_PROJECT,
        "processor": settings.DOCAI_PROCESSOR_ID,
        "bucket": settings.GCS_BUCKET,
    }

@app.get("/healthz")
def healthz():
    return {"ok": True}