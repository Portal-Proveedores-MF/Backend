from app.config import settings
from app.domain.models import InvoiceExtraction, Entity  
from google.cloud import documentai

class DocAIInvoiceExtractor:
    def __init__(self):
        self.project_id   = settings.GOOGLE_CLOUD_PROJECT
        self.location     = settings.GOOGLE_CLOUD_REGION
        self.processor_id = settings.DOCAI_PROCESSOR_ID

        if not self.project_id or not self.processor_id:
            raise ValueError("Faltan GOOGLE_CLOUD_PROJECT o DOCAI_PROCESSOR_ID")

        self.client = documentai.DocumentProcessorServiceClient()

    def extract_invoice(self, local_pdf_path: str) -> InvoiceExtraction:
        # Nombre del procesador
        name = self.client.processor_path(self.project_id, self.location, self.processor_id)

        # Lee bytes del PDF local
        with open(local_pdf_path, "rb") as f:
            content = f.read()

        # Usa RawDocument (PDF en bytes)
        request = documentai.ProcessRequest(
            name=name,
            raw_document=documentai.RawDocument(content=content, mime_type="application/pdf"),
        )
        result = self.client.process_document(request=request)
        doc = result.document

        # Extrae entidades (ajusta a tu modelo si es distinto)
        ents = []
        for e in getattr(doc, "entities", []):
            ents.append(
                Entity(
                    type=e.type_, 
                    text=e.mention_text or "",
                    confidence=float(e.confidence or 0.0),
                )
            )

        return InvoiceExtraction(schema_version="1.0", entities=ents)
