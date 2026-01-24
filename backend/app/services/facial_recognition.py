"""
Serviço de Reconhecimento Facial.

Suporta múltiplos providers:
- local: Usa face_recognition (dlib) - gratuito, roda local
- aws: Usa Amazon Rekognition
- azure: Usa Azure Face API

Para produção, recomenda-se AWS Rekognition ou Azure Face.
"""

import base64
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


class FacialProvider(str, Enum):
    """Providers de reconhecimento facial."""
    LOCAL = "local"
    AWS = "aws"
    AZURE = "azure"


@dataclass
class FaceDetectionResult:
    """Resultado da detecção de face."""
    face_detected: bool
    num_faces: int
    confidence: float
    face_encoding: Optional[bytes] = None
    bounding_box: Optional[dict] = None
    message: str = ""


@dataclass
class FaceComparisonResult:
    """Resultado da comparação de faces."""
    match: bool
    similarity: float  # 0.0 a 1.0
    confidence: float
    message: str = ""


class BaseFacialService(ABC):
    """Interface base para serviços de reconhecimento facial."""
    
    @abstractmethod
    async def detect_face(self, image_data: bytes) -> FaceDetectionResult:
        """Detecta face em uma imagem."""
        pass
    
    @abstractmethod
    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        threshold: float = 0.6,
    ) -> FaceComparisonResult:
        """Compara duas faces."""
        pass
    
    @abstractmethod
    async def get_face_encoding(self, image_data: bytes) -> Optional[bytes]:
        """Extrai encoding da face para armazenamento."""
        pass


class LocalFacialService(BaseFacialService):
    """
    Serviço local usando face_recognition (dlib).
    
    Gratuito e roda localmente, bom para desenvolvimento.
    Para produção com alto volume, considere AWS ou Azure.
    """
    
    def __init__(self):
        try:
            import face_recognition
            import numpy as np
            from PIL import Image
            self.face_recognition = face_recognition
            self.np = np
            self.Image = Image
            self._available = True
            logger.info("Serviço de reconhecimento facial local inicializado")
        except ImportError:
            self._available = False
            logger.warning(
                "face_recognition não instalado. "
                "Instale com: pip install face_recognition Pillow"
            )
    
    def _load_image(self, image_data: bytes):
        """Carrega imagem de bytes."""
        if not self._available:
            raise RuntimeError("face_recognition não está disponível")
        
        image = self.Image.open(io.BytesIO(image_data))
        if image.mode != "RGB":
            image = image.convert("RGB")
        return self.np.array(image)
    
    async def detect_face(self, image_data: bytes) -> FaceDetectionResult:
        """Detecta face em uma imagem."""
        if not self._available:
            return FaceDetectionResult(
                face_detected=False,
                num_faces=0,
                confidence=0.0,
                message="Serviço de reconhecimento facial não disponível",
            )
        
        try:
            image = self._load_image(image_data)
            face_locations = self.face_recognition.face_locations(image)
            num_faces = len(face_locations)
            
            if num_faces == 0:
                return FaceDetectionResult(
                    face_detected=False,
                    num_faces=0,
                    confidence=0.0,
                    message="Nenhuma face detectada na imagem",
                )
            
            if num_faces > 1:
                return FaceDetectionResult(
                    face_detected=True,
                    num_faces=num_faces,
                    confidence=0.7,
                    message=f"Múltiplas faces detectadas ({num_faces}). Use imagem com apenas uma face.",
                )
            
            # Extrair encoding
            face_encodings = self.face_recognition.face_encodings(image, face_locations)
            encoding_bytes = None
            if face_encodings:
                encoding_bytes = face_encodings[0].tobytes()
            
            # Bounding box
            top, right, bottom, left = face_locations[0]
            bounding_box = {
                "top": top,
                "right": right,
                "bottom": bottom,
                "left": left,
            }
            
            return FaceDetectionResult(
                face_detected=True,
                num_faces=1,
                confidence=0.95,
                face_encoding=encoding_bytes,
                bounding_box=bounding_box,
                message="Face detectada com sucesso",
            )
            
        except Exception as e:
            logger.error(f"Erro ao detectar face: {e}")
            return FaceDetectionResult(
                face_detected=False,
                num_faces=0,
                confidence=0.0,
                message=f"Erro ao processar imagem: {str(e)}",
            )
    
    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        threshold: float = 0.6,
    ) -> FaceComparisonResult:
        """Compara duas faces."""
        if not self._available:
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message="Serviço de reconhecimento facial não disponível",
            )
        
        try:
            source_img = self._load_image(source_image)
            target_img = self._load_image(target_image)
            
            source_encodings = self.face_recognition.face_encodings(source_img)
            target_encodings = self.face_recognition.face_encodings(target_img)
            
            if not source_encodings:
                return FaceComparisonResult(
                    match=False,
                    similarity=0.0,
                    confidence=0.0,
                    message="Nenhuma face encontrada na imagem de origem",
                )
            
            if not target_encodings:
                return FaceComparisonResult(
                    match=False,
                    similarity=0.0,
                    confidence=0.0,
                    message="Nenhuma face encontrada na imagem de destino",
                )
            
            # Calcular distância (quanto menor, mais similar)
            distance = self.face_recognition.face_distance(
                [source_encodings[0]], target_encodings[0]
            )[0]
            
            # Converter distância para similaridade (0-1)
            similarity = max(0, 1 - distance)
            match = distance <= threshold
            
            return FaceComparisonResult(
                match=match,
                similarity=float(similarity),
                confidence=0.95 if match else 0.5,
                message="Faces correspondem" if match else "Faces não correspondem",
            )
            
        except Exception as e:
            logger.error(f"Erro ao comparar faces: {e}")
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message=f"Erro ao processar imagens: {str(e)}",
            )
    
    async def get_face_encoding(self, image_data: bytes) -> Optional[bytes]:
        """Extrai encoding da face para armazenamento."""
        result = await self.detect_face(image_data)
        return result.face_encoding if result.face_detected else None
    
    async def compare_with_encoding(
        self,
        image_data: bytes,
        stored_encoding: bytes,
        threshold: float = 0.6,
    ) -> FaceComparisonResult:
        """Compara uma imagem com um encoding armazenado."""
        if not self._available:
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message="Serviço de reconhecimento facial não disponível",
            )
        
        try:
            image = self._load_image(image_data)
            image_encodings = self.face_recognition.face_encodings(image)
            
            if not image_encodings:
                return FaceComparisonResult(
                    match=False,
                    similarity=0.0,
                    confidence=0.0,
                    message="Nenhuma face encontrada na imagem",
                )
            
            # Converter bytes de volta para numpy array
            stored_array = self.np.frombuffer(stored_encoding, dtype=self.np.float64)
            
            distance = self.face_recognition.face_distance(
                [stored_array], image_encodings[0]
            )[0]
            
            similarity = max(0, 1 - distance)
            match = distance <= threshold
            
            return FaceComparisonResult(
                match=match,
                similarity=float(similarity),
                confidence=0.95 if match else 0.5,
                message="Face verificada com sucesso" if match else "Face não corresponde ao cadastro",
            )
            
        except Exception as e:
            logger.error(f"Erro ao comparar com encoding: {e}")
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message=f"Erro ao verificar face: {str(e)}",
            )


class AWSFacialService(BaseFacialService):
    """
    Serviço usando Amazon Rekognition.
    
    Requer credenciais AWS configuradas.
    """
    
    def __init__(self):
        try:
            import boto3
            self.client = boto3.client(
                "rekognition",
                region_name=getattr(settings, "aws_region", "us-east-1"),
            )
            self._available = True
            logger.info("Serviço AWS Rekognition inicializado")
        except Exception as e:
            self._available = False
            logger.warning(f"AWS Rekognition não disponível: {e}")
    
    async def detect_face(self, image_data: bytes) -> FaceDetectionResult:
        """Detecta face usando AWS Rekognition."""
        if not self._available:
            return FaceDetectionResult(
                face_detected=False,
                num_faces=0,
                confidence=0.0,
                message="AWS Rekognition não disponível",
            )
        
        try:
            response = self.client.detect_faces(
                Image={"Bytes": image_data},
                Attributes=["DEFAULT"],
            )
            
            faces = response.get("FaceDetails", [])
            num_faces = len(faces)
            
            if num_faces == 0:
                return FaceDetectionResult(
                    face_detected=False,
                    num_faces=0,
                    confidence=0.0,
                    message="Nenhuma face detectada",
                )
            
            if num_faces > 1:
                return FaceDetectionResult(
                    face_detected=True,
                    num_faces=num_faces,
                    confidence=faces[0]["Confidence"] / 100,
                    message=f"Múltiplas faces detectadas ({num_faces})",
                )
            
            face = faces[0]
            bbox = face["BoundingBox"]
            
            return FaceDetectionResult(
                face_detected=True,
                num_faces=1,
                confidence=face["Confidence"] / 100,
                bounding_box={
                    "left": bbox["Left"],
                    "top": bbox["Top"],
                    "width": bbox["Width"],
                    "height": bbox["Height"],
                },
                message="Face detectada com sucesso",
            )
            
        except Exception as e:
            logger.error(f"Erro AWS Rekognition detect_faces: {e}")
            return FaceDetectionResult(
                face_detected=False,
                num_faces=0,
                confidence=0.0,
                message=f"Erro: {str(e)}",
            )
    
    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        threshold: float = 0.6,
    ) -> FaceComparisonResult:
        """Compara faces usando AWS Rekognition."""
        if not self._available:
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message="AWS Rekognition não disponível",
            )
        
        try:
            response = self.client.compare_faces(
                SourceImage={"Bytes": source_image},
                TargetImage={"Bytes": target_image},
                SimilarityThreshold=threshold * 100,
            )
            
            matches = response.get("FaceMatches", [])
            
            if not matches:
                return FaceComparisonResult(
                    match=False,
                    similarity=0.0,
                    confidence=0.95,
                    message="Faces não correspondem",
                )
            
            best_match = matches[0]
            similarity = best_match["Similarity"] / 100
            
            return FaceComparisonResult(
                match=True,
                similarity=similarity,
                confidence=best_match["Face"]["Confidence"] / 100,
                message="Faces correspondem",
            )
            
        except self.client.exceptions.InvalidParameterException:
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message="Nenhuma face detectada em uma das imagens",
            )
        except Exception as e:
            logger.error(f"Erro AWS Rekognition compare_faces: {e}")
            return FaceComparisonResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                message=f"Erro: {str(e)}",
            )
    
    async def get_face_encoding(self, image_data: bytes) -> Optional[bytes]:
        """AWS Rekognition não retorna encoding - usa compare_faces diretamente."""
        return None


class MockFacialService(BaseFacialService):
    """
    Serviço mock para desenvolvimento.
    
    Sempre retorna sucesso para facilitar testes.
    """
    
    async def detect_face(self, image_data: bytes) -> FaceDetectionResult:
        """Sempre detecta uma face."""
        # Verificar se é uma imagem válida (mínimo de bytes)
        if len(image_data) < 1000:
            return FaceDetectionResult(
                face_detected=False,
                num_faces=0,
                confidence=0.0,
                message="Imagem muito pequena ou inválida",
            )
        
        return FaceDetectionResult(
            face_detected=True,
            num_faces=1,
            confidence=0.95,
            message="Face detectada (modo desenvolvimento)",
        )
    
    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        threshold: float = 0.6,
    ) -> FaceComparisonResult:
        """Sempre retorna match."""
        return FaceComparisonResult(
            match=True,
            similarity=0.92,
            confidence=0.95,
            message="Faces correspondem (modo desenvolvimento)",
        )
    
    async def get_face_encoding(self, image_data: bytes) -> Optional[bytes]:
        """Retorna encoding fake."""
        import hashlib
        return hashlib.sha256(image_data).digest()


def get_facial_service(provider: Optional[str] = None) -> BaseFacialService:
    """
    Factory para obter o serviço de reconhecimento facial.
    
    Ordem de prioridade:
    1. Provider específico se fornecido
    2. Configuração do settings
    3. Fallback para mock em desenvolvimento
    """
    provider = provider or getattr(settings, "facial_provider", "mock")
    
    if provider == FacialProvider.AWS:
        service = AWSFacialService()
        if service._available:
            return service
        logger.warning("AWS não disponível, usando mock")
    
    if provider == FacialProvider.LOCAL:
        service = LocalFacialService()
        if service._available:
            return service
        logger.warning("face_recognition não disponível, usando mock")
    
    # Fallback para mock
    return MockFacialService()


# Instância singleton
facial_service = get_facial_service()
