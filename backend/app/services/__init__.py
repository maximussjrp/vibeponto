"""Services package."""

from app.services.auditoria import AuditorIAService, processar_auditoria_background
from app.services.geo import GeoService, geo_service, GeoPoint, GeoValidationResult
from app.services.lgpd import LGPDService, lgpd_service
from app.services.pdf import PDFService, pdf_service
from app.services.storage import StorageService, get_storage_service
from app.services.facial_recognition import (
    facial_service,
    get_facial_service,
    FaceDetectionResult,
    FaceComparisonResult,
    FacialProvider,
)

__all__ = [
    "AuditorIAService",
    "processar_auditoria_background",
    "GeoService",
    "geo_service",
    "GeoPoint",
    "GeoValidationResult",
    "LGPDService",
    "lgpd_service",
    "PDFService",
    "pdf_service",
    "StorageService",
    "get_storage_service",
    "facial_service",
    "get_facial_service",
    "FaceDetectionResult",
    "FaceComparisonResult",
    "FacialProvider",
]
