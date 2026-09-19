"""Aplicação FastAPI principal."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import (
    auth_router,
    beneficios_router,
    dashboard_router,
    documentos_router,
    equipes_router,
    escalas_router,
    espelho_router,
    geo_router,
    ponto_router,
    tenant_router,
    usuarios_router,
)
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.redis import get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager para a aplicação."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="VibePonto API",
    description="""
    Sistema de Ponto Eletrônico com Benefícios Flexíveis.
    
    Desenvolvido para conformidade com a Portaria 671/MTE e LGPD.
    
    ## Funcionalidades
    
    - **Ponto Eletrônico**: Marcações com foto, facial, QR Code, geolocalização
    - **AuditorIA**: Detecção automática de fraudes com IA
    - **Espelho de Ponto**: Visualização e assinatura digital
    - **AEJ**: Exportação conforme Portaria 671
    - **Documentos**: Upload, assinatura digital (e-Sign e ICP-Brasil)
    - **Benefícios**: Carteiras VA/VR/VT, cartões, recargas
    - **Multi-tenant**: Isolamento completo por empresa
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(usuarios_router, prefix="/api/v1")
app.include_router(equipes_router, prefix="/api/v1")
app.include_router(ponto_router, prefix="/api/v1")
app.include_router(espelho_router, prefix="/api/v1")
app.include_router(geo_router, prefix="/api/v1")
app.include_router(escalas_router, prefix="/api/v1")
app.include_router(documentos_router, prefix="/api/v1")
app.include_router(beneficios_router, prefix="/api/v1")
app.include_router(tenant_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Liveness check endpoint."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for production dependency checks."""
    checks = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        redis = await get_redis()
        await redis.client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    if all(status == "ok" for status in checks.values()):
        return {"status": "ready", "version": settings.app_version, "checks": checks}

    raise HTTPException(
        status_code=503,
        detail={"status": "unready", "version": settings.app_version, "checks": checks},
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "VibePonto API",
        "docs": "/docs",
        "health": "/health",
    }
