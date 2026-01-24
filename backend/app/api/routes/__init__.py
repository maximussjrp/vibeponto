"""API routes package."""

from app.api.routes.auth import router as auth_router
from app.api.routes.beneficios import router as beneficios_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.documentos import router as documentos_router
from app.api.routes.equipes import router as equipes_router
from app.api.routes.escalas import router as escalas_router
from app.api.routes.espelho import router as espelho_router
from app.api.routes.geo import router as geo_router
from app.api.routes.ponto import router as ponto_router
from app.api.routes.tenant import router as tenant_router
from app.api.routes.usuarios import router as usuarios_router

__all__ = [
    "auth_router",
    "beneficios_router",
    "dashboard_router",
    "documentos_router",
    "equipes_router",
    "escalas_router",
    "espelho_router",
    "geo_router",
    "ponto_router",
    "tenant_router",
    "usuarios_router",
]
