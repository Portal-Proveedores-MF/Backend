from google.cloud import storage
from pathlib import Path
import tempfile

class GCSStorage:
    def __init__(self):
        self.client = storage.Client()
        # obtiene un directorio temporal que sí existe en Windows y Linux
        self.tmp_dir = Path(tempfile.gettempdir())

    def download_to_tmp(self, bucket: str, name: str) -> Path:
        """Descarga el archivo al directorio temporal compatible con cualquier SO"""
        bucket_obj = self.client.bucket(bucket)
        blob = bucket_obj.blob(name)
        tmp_path = self.tmp_dir / Path(name).name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(tmp_path))
        return tmp_path

    def gcs_uri(self, bucket: str, name: str) -> str:
        """Retorna la URI gs:// completa (si solo necesitas la ruta lógica)"""
        return f"gs://{bucket}/{name}"
