from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth, initialize_app

initialize_app()
security = HTTPBearer(auto_error=True)

async def require_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials  # Swagger pondrá "Bearer <token>" y FastAPI extrae el token
        decoded = auth.verify_id_token(token)
        return {"uid": decoded["uid"], "email": decoded.get("email")}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
