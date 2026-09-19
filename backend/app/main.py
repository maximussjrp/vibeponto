"""Aplicacao FastAPI principal."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
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
from app.core.observability import (
    HTTP_REQUESTS_IN_PROGRESS,
    REQUEST_ID_HEADER,
    configure_logging,
    configure_opentelemetry,
    get_route_template,
    metrics_content_type,
    metrics_payload,
    observe_http_request,
    observe_readiness_check,
    reset_request_id,
    sanitize_request_id,
    set_request_id,
)
from app.core.redis import get_redis

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager para a aplicacao."""
    await init_db()
    yield


app = FastAPI(
    title="VibePonto API",
    description="""
    Sistema de Ponto Eletronico com Beneficios Flexiveis.

    Desenvolvido para conformidade com a Portaria 671/MTE e LGPD.

    ## Funcionalidades

    - **Ponto Eletronico**: Marcacoes com foto, facial, QR Code, geolocalizacao
    - **AuditorIA**: Deteccao automatica de fraudes com IA
    - **Espelho de Ponto**: Visualizacao e assinatura digital
    - **AEJ**: Exportacao conforme Portaria 671
    - **Documentos**: Upload, assinatura digital (e-Sign e ICP-Brasil)
    - **Beneficios**: Carteiras VA/VR/VT, cartoes, recargas
    - **Multi-tenant**: Isolamento completo por empresa
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
configure_opentelemetry(app=app, engine=engine)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = set_request_id(request_id)
    method = request.method.upper()
    start = time.perf_counter()
    status_code = 500
    recorded_exception = False
    HTTP_REQUESTS_IN_PROGRESS.labels(method).inc()

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    except Exception:
        recorded_exception = True
        route = get_route_template(request)
        duration_seconds = time.perf_counter() - start
        observe_http_request(method, route, status_code, duration_seconds)
        logger.exception(
            "Unhandled request error",
            extra={
                "http_method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration_seconds * 1000, 2),
            },
        )
        raise
    finally:
        duration_seconds = time.perf_counter() - start
        route = get_route_template(request)
        HTTP_REQUESTS_IN_PROGRESS.labels(method).dec()
        if not recorded_exception:
            observe_http_request(method, route, status_code, duration_seconds)
            logger.info(
                "HTTP request completed",
                extra={
                    "http_method": method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
        reset_request_id(token)


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

    start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    observe_readiness_check("database", checks["database"], time.perf_counter() - start)

    start = time.perf_counter()
    try:
        redis = await get_redis()
        await redis.client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    observe_readiness_check("redis", checks["redis"], time.perf_counter() - start)

    if all(status == "ok" for status in checks.values()):
        return {"status": "ready", "version": settings.app_version, "checks": checks}

    raise HTTPException(
        status_code=503,
        detail={"status": "unready", "version": settings.app_version, "checks": checks},
    )


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint. Protect externally via private network/reverse proxy."""
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    return Response(content=metrics_payload(), media_type=metrics_content_type())


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "VibePonto API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }
