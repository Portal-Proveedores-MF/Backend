--------------------------------------------------------------------------
--------------------------------------------------------------------------
## Pruebas locales 

1. Credenciales de aplicación

gcloud auth login --update-adc
gcloud auth application-default set-quota-project neo-portal-proveedores-477002

gcloud auth application-default print-access-token #para verificar que muestre el token

2. Instalar deps y levantar FastAPI

cd backend

py -3.11 -m venv .venv311
.venv311\Scripts\activate

//pip install fastapi uvicorn[standard] google-cloud-storage google-cloud-documentai google-cloud-firestore

pip install -r requirements.txt

pip install python-dotenv pydantic-settings
pip install firebase-admin

uvicorn app.main:app --reload --port 8080

Para ver el swagger
http://127.0.0.1:8080/docs

Para subir un archivo al bucket (desde esta carpeta)
gsutil cp .\sample.pdf gs://neo-portal-proveedores-pdfs/sample.pdf


3. Sube un PDF de prueba a tu bucket (el que ya creaste):

gsutil cp .\sample.pdf gs://neo-portal-proveedores-pdfs/pruebas/sample.pdf


4. Simula el evento de Eventarc (POST al endpoint local):

{
  "data": {
    "bucket": "neo-portal-proveedores-pdfs",
    "name": "sample2.pdf",
    "generation": "12345"
  }
}

Deberías ver en respuesta 
{
  "ok": true,
  "doc_id": "neo-portal-proveedores-pdfs:sample2.pdf:12345",
  "skipped": false
}
y un documento nuevo en Firestore → colección invoices.

Para ver el token de firebase (para pruebas locales)
--------------------------------------------------------------------------
--------------------------------------------------------------------------
## Para desplegar

gcloud artifacts repositories create $REPO `
  --repository-format=docker `
  --location=$REGION `
  --description="Repo para imágenes del backend" 


$IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:$(Get-Date -Format 'yyyyMMdd-HHmmss')"
gcloud builds submit --tag $IMAGE

gcloud run deploy $SERVICE `
  --image $IMAGE `
  --region $REGION `
  --service-account $SA_EMAIL `
  --allow-unauthenticated `
  --memory 512Mi --cpu 1 --concurrency 80 `
  --port 8080 `
  --set-env-vars "GCS_BUCKET=$GCS_BUCKET,DOC_PROCESSOR_NAME=$DOC_PROCESSOR_NAME"


gcloud run services logs read neo-backend --region southamerica-east1 --limit 200
# Backend
