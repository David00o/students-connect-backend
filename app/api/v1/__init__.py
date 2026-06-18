from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router

# Future modules will be added here:
# from app.api.v1.routes.profile import router as profile_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
