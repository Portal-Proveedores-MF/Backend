from dataclasses import dataclass, field
from typing import List, Optional
from pydantic import BaseModel

@dataclass
class Entity:
    type: str
    text: str
    confidence: float

@dataclass
class InvoiceExtraction:
    entities: List[Entity] = field(default_factory=list)
    schema_version: str = "1.0"

class GcsEventData(BaseModel):
    bucket: str
    name: str
    generation: Optional[str] = None

class GcsEvent(BaseModel):
    data: GcsEventData

# ---- DTOs usados por tu router ----
class InvoiceDTO(BaseModel):
    id: Optional[str] = None
    supplierId: Optional[str] = None
    name: Optional[str] = None
    filePath: Optional[str] = None
    status: Optional[str] = None
    engine: Optional[str] = None

    # totales
    currency: Optional[str] = None
    total: Optional[str] = None
    totalTax: Optional[str] = None
    netAmount: Optional[str] = None

    # nuevos metadatos visibles en la tabla
    issueDate: Optional[str] = None
    dueDate: Optional[str] = None
    supplierName: Optional[str] = None
    supplierAddress: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
