from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    GOOGLE_CLOUD_PROJECT: str
    GOOGLE_CLOUD_REGION: str = "us"
    DOCAI_PROCESSOR_ID: str
    GCS_BUCKET: str
    APP_ENV: str = "dev"
    FIRESTORE_COLL: str = "invoices"

    # ---- Aliases convenientes para el resto del código ----
    @property
    def project_id(self) -> str:
        return self.GOOGLE_CLOUD_PROJECT

    @property
    def processor_id(self) -> str:
        return self.DOCAI_PROCESSOR_ID

    @property
    def firestore_collection(self) -> str:
        return self.FIRESTORE_COLL

    @property
    def app_env(self) -> str:
        return self.APP_ENV

settings = Settings()
