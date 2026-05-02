from fastapi import APIRouter

from app.api.v1.contact import router as contact_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.knowledge_bases import router as knowledge_bases_router
from app.api.v1.query import router as query_router
from app.api.v1.retrieval import router as retrieval_router
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(contact_router, prefix=settings.api_v1_prefix)
api_router.include_router(knowledge_bases_router, prefix=settings.api_v1_prefix)
api_router.include_router(documents_router, prefix=settings.api_v1_prefix)
api_router.include_router(jobs_router, prefix=settings.api_v1_prefix)
api_router.include_router(retrieval_router, prefix=settings.api_v1_prefix)
api_router.include_router(query_router, prefix=settings.api_v1_prefix)
