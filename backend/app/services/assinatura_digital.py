"""
Serviço de Assinatura Digital ICP-Brasil
Suporta assinatura de documentos com certificados A1/A3
"""

import base64
import hashlib
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID, ExtensionOID
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CertificadoInfo(BaseModel):
    """Informações do certificado digital"""
    titular: str
    cpf: Optional[str] = None
    cnpj: Optional[str] = None
    email: Optional[str] = None
    emissor: str
    validade_inicio: datetime
    validade_fim: datetime
    numero_serie: str
    tipo: str  # A1, A3, etc
    cadeia_confianca: List[str] = []
    is_valido: bool = True
    motivo_invalido: Optional[str] = None


class AssinaturaDigital(BaseModel):
    """Dados de uma assinatura digital"""
    id: UUID
    documento_id: UUID
    usuario_id: UUID
    certificado_info: CertificadoInfo
    hash_documento: str
    assinatura_base64: str
    timestamp: datetime
    lta_timestamp: Optional[str] = None  # Long Term Archival
    politica_assinatura: str = "AD-RB"  # AD-RB, AD-RT, AD-RV, AD-RC, AD-RA


class AssinaturaRequest(BaseModel):
    """Request para assinar documento"""
    documento_id: UUID
    certificado_base64: str  # Certificado PFX/P12 em base64
    senha_certificado: str
    politica: str = "AD-RB"


class VerificacaoResult(BaseModel):
    """Resultado da verificação de assinatura"""
    valido: bool
    mensagem: str
    detalhes: Dict[str, Any] = {}
    certificado_info: Optional[CertificadoInfo] = None
    timestamp_verificacao: datetime


class AssinaturaDigitalService:
    """Serviço de assinatura digital ICP-Brasil"""
    
    # OIDs ICP-Brasil
    OID_CPF = "2.16.76.1.3.1"
    OID_CNPJ = "2.16.76.1.3.3"
    OID_PESSOA_FISICA = "2.16.76.1.3.1"
    OID_PESSOA_JURIDICA = "2.16.76.1.3.4"
    
    # Políticas de assinatura
    POLITICAS = {
        "AD-RB": "Assinatura Digital com Referência Básica",
        "AD-RT": "Assinatura Digital com Referência de Tempo",
        "AD-RV": "Assinatura Digital com Referências para Validação",
        "AD-RC": "Assinatura Digital com Referências Completas",
        "AD-RA": "Assinatura Digital com Referências para Arquivamento",
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def extrair_info_certificado(
        self, 
        certificado_pem: bytes
    ) -> CertificadoInfo:
        """Extrai informações do certificado X.509"""
        try:
            cert = x509.load_pem_x509_certificate(certificado_pem)
            
            # Extrair dados do subject
            subject = cert.subject
            titular = self._get_attribute(subject, NameOID.COMMON_NAME)
            email = self._get_attribute(subject, NameOID.EMAIL_ADDRESS)
            
            # Extrair CPF/CNPJ das extensões ICP-Brasil
            cpf = None
            cnpj = None
            
            try:
                san = cert.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                for name in san.value:
                    if hasattr(name, 'value'):
                        value = str(name.value)
                        # CPF está nos primeiros 11 dígitos após identificador
                        if self.OID_CPF in value:
                            cpf = self._extrair_cpf(value)
                        elif self.OID_CNPJ in value:
                            cnpj = self._extrair_cnpj(value)
            except x509.ExtensionNotFound:
                pass
            
            # Emissor
            issuer = cert.issuer
            emissor = self._get_attribute(issuer, NameOID.COMMON_NAME)
            
            # Determinar tipo (A1, A3, etc)
            tipo = self._determinar_tipo_certificado(cert)
            
            # Validar
            is_valido = True
            motivo_invalido = None
            
            now = datetime.now(timezone.utc)
            if cert.not_valid_before_utc > now:
                is_valido = False
                motivo_invalido = "Certificado ainda não é válido"
            elif cert.not_valid_after_utc < now:
                is_valido = False
                motivo_invalido = "Certificado expirado"
            
            return CertificadoInfo(
                titular=titular or "Desconhecido",
                cpf=cpf,
                cnpj=cnpj,
                email=email,
                emissor=emissor or "Desconhecido",
                validade_inicio=cert.not_valid_before_utc,
                validade_fim=cert.not_valid_after_utc,
                numero_serie=str(cert.serial_number),
                tipo=tipo,
                is_valido=is_valido,
                motivo_invalido=motivo_invalido,
            )
            
        except Exception as e:
            logger.error(f"Erro ao extrair info do certificado: {e}")
            raise ValueError(f"Certificado inválido: {str(e)}")
    
    def _get_attribute(self, name: x509.Name, oid) -> Optional[str]:
        """Extrai atributo do Name"""
        try:
            attrs = name.get_attributes_for_oid(oid)
            if attrs:
                return attrs[0].value
        except:
            pass
        return None
    
    def _extrair_cpf(self, value: str) -> Optional[str]:
        """Extrai CPF do valor OtherName"""
        import re
        # CPF tem 11 dígitos
        match = re.search(r'\d{11}', value)
        return match.group(0) if match else None
    
    def _extrair_cnpj(self, value: str) -> Optional[str]:
        """Extrai CNPJ do valor OtherName"""
        import re
        # CNPJ tem 14 dígitos
        match = re.search(r'\d{14}', value)
        return match.group(0) if match else None
    
    def _determinar_tipo_certificado(self, cert: x509.Certificate) -> str:
        """Determina se é A1, A3, etc baseado nas políticas"""
        try:
            policies = cert.extensions.get_extension_for_oid(
                ExtensionOID.CERTIFICATE_POLICIES
            )
            for policy in policies.value:
                oid = policy.policy_identifier.dotted_string
                if "2.16.76.1.2.1" in oid:
                    return "A1"
                elif "2.16.76.1.2.3" in oid:
                    return "A3"
                elif "2.16.76.1.2.2" in oid:
                    return "A2"
                elif "2.16.76.1.2.4" in oid:
                    return "A4"
        except:
            pass
        return "Desconhecido"
    
    async def carregar_certificado_pfx(
        self, 
        pfx_data: bytes, 
        senha: str
    ) -> tuple:
        """Carrega certificado PFX/P12"""
        from cryptography.hazmat.primitives.serialization import pkcs12
        
        try:
            private_key, certificate, chain = pkcs12.load_key_and_certificates(
                pfx_data, 
                senha.encode()
            )
            
            if not certificate:
                raise ValueError("Certificado não encontrado no arquivo PFX")
            
            if not private_key:
                raise ValueError("Chave privada não encontrada no arquivo PFX")
            
            return private_key, certificate, chain or []
            
        except Exception as e:
            logger.error(f"Erro ao carregar PFX: {e}")
            raise ValueError(f"Erro ao carregar certificado: {str(e)}")
    
    async def calcular_hash_documento(
        self, 
        conteudo: bytes, 
        algoritmo: str = "SHA-256"
    ) -> str:
        """Calcula hash do documento"""
        if algoritmo == "SHA-256":
            h = hashlib.sha256(conteudo)
        elif algoritmo == "SHA-512":
            h = hashlib.sha512(conteudo)
        else:
            raise ValueError(f"Algoritmo não suportado: {algoritmo}")
        
        return h.hexdigest()
    
    async def assinar_documento(
        self,
        documento_bytes: bytes,
        private_key,
        politica: str = "AD-RB"
    ) -> bytes:
        """Assina documento com chave privada"""
        
        # Calcular hash
        documento_hash = hashlib.sha256(documento_bytes).digest()
        
        # Assinar
        if isinstance(private_key, rsa.RSAPrivateKey):
            assinatura = private_key.sign(
                documento_hash,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        else:
            # Para outros tipos de chave (EC, etc)
            from cryptography.hazmat.primitives.asymmetric import ec
            if isinstance(private_key, ec.EllipticCurvePrivateKey):
                assinatura = private_key.sign(
                    documento_hash,
                    ec.ECDSA(hashes.SHA256())
                )
            else:
                raise ValueError("Tipo de chave não suportado")
        
        return assinatura
    
    async def verificar_assinatura(
        self,
        documento_bytes: bytes,
        assinatura: bytes,
        certificado: x509.Certificate
    ) -> VerificacaoResult:
        """Verifica assinatura digital"""
        try:
            public_key = certificado.public_key()
            documento_hash = hashlib.sha256(documento_bytes).digest()
            
            if isinstance(public_key, rsa.RSAPublicKey):
                public_key.verify(
                    assinatura,
                    documento_hash,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            else:
                from cryptography.hazmat.primitives.asymmetric import ec
                if isinstance(public_key, ec.EllipticCurvePublicKey):
                    public_key.verify(
                        assinatura,
                        documento_hash,
                        ec.ECDSA(hashes.SHA256())
                    )
            
            # Extrair info do certificado
            cert_pem = certificado.public_bytes(serialization.Encoding.PEM)
            cert_info = await self.extrair_info_certificado(cert_pem)
            
            return VerificacaoResult(
                valido=True,
                mensagem="Assinatura válida",
                detalhes={
                    "algoritmo": "RSA-SHA256",
                    "hash_documento": hashlib.sha256(documento_bytes).hexdigest(),
                },
                certificado_info=cert_info,
                timestamp_verificacao=datetime.now(timezone.utc),
            )
            
        except Exception as e:
            logger.error(f"Erro na verificação: {e}")
            return VerificacaoResult(
                valido=False,
                mensagem=f"Assinatura inválida: {str(e)}",
                timestamp_verificacao=datetime.now(timezone.utc),
            )
    
    async def criar_envelope_assinado(
        self,
        documento_id: UUID,
        usuario_id: UUID,
        documento_bytes: bytes,
        certificado_base64: str,
        senha: str,
        politica: str = "AD-RB"
    ) -> Dict[str, Any]:
        """Cria envelope com documento assinado"""
        
        # Decodificar certificado
        pfx_data = base64.b64decode(certificado_base64)
        
        # Carregar chaves
        private_key, certificate, chain = await self.carregar_certificado_pfx(
            pfx_data, senha
        )
        
        # Extrair info
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
        cert_info = await self.extrair_info_certificado(cert_pem)
        
        if not cert_info.is_valido:
            raise ValueError(f"Certificado inválido: {cert_info.motivo_invalido}")
        
        # Calcular hash
        doc_hash = await self.calcular_hash_documento(documento_bytes)
        
        # Assinar
        assinatura = await self.assinar_documento(
            documento_bytes, private_key, politica
        )
        
        # Criar envelope
        envelope = {
            "versao": "1.0",
            "politica": politica,
            "documento": {
                "id": str(documento_id),
                "hash": doc_hash,
                "algoritmo_hash": "SHA-256",
            },
            "assinatura": {
                "valor": base64.b64encode(assinatura).decode(),
                "algoritmo": "RSA-SHA256",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "certificado": {
                "titular": cert_info.titular,
                "cpf": cert_info.cpf,
                "cnpj": cert_info.cnpj,
                "emissor": cert_info.emissor,
                "numero_serie": cert_info.numero_serie,
                "validade": {
                    "inicio": cert_info.validade_inicio.isoformat(),
                    "fim": cert_info.validade_fim.isoformat(),
                },
                "tipo": cert_info.tipo,
                "pem": cert_pem.decode(),
            },
            "assinante": {
                "usuario_id": str(usuario_id),
            }
        }
        
        return envelope
    
    async def validar_cadeia_certificacao(
        self,
        certificado: x509.Certificate,
        cadeia: List[x509.Certificate]
    ) -> bool:
        """Valida cadeia de certificação ICP-Brasil"""
        # Em produção, verificar contra CRLs e OCSP
        # e validar até a raiz ICP-Brasil
        
        # Por enquanto, validação básica
        now = datetime.now(timezone.utc)
        
        # Verificar validade do certificado
        if certificado.not_valid_before_utc > now:
            return False
        if certificado.not_valid_after_utc < now:
            return False
        
        # Verificar cadeia
        for cert in cadeia:
            if cert.not_valid_before_utc > now:
                return False
            if cert.not_valid_after_utc < now:
                return False
        
        return True


# Funções auxiliares para uso nas rotas

async def assinar_espelho_ponto(
    db: AsyncSession,
    usuario_id: UUID,
    periodo_inicio: datetime,
    periodo_fim: datetime,
    certificado_base64: str,
    senha: str
) -> Dict[str, Any]:
    """Assina espelho de ponto com certificado digital"""
    from app.models import MarcacaoPonto, Usuario
    
    # Buscar marcações do período
    result = await db.execute(
        select(MarcacaoPonto)
        .where(MarcacaoPonto.usuario_id == usuario_id)
        .where(MarcacaoPonto.data_hora >= periodo_inicio)
        .where(MarcacaoPonto.data_hora <= periodo_fim)
        .order_by(MarcacaoPonto.data_hora)
    )
    marcacoes = result.scalars().all()
    
    # Gerar documento para assinatura
    doc_data = {
        "tipo": "ESPELHO_PONTO",
        "usuario_id": str(usuario_id),
        "periodo": {
            "inicio": periodo_inicio.isoformat(),
            "fim": periodo_fim.isoformat(),
        },
        "marcacoes": [
            {
                "id": str(m.id),
                "data_hora": m.data_hora.isoformat(),
                "tipo": m.tipo,
                "evento": m.evento,
            }
            for m in marcacoes
        ],
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }
    
    documento_bytes = json.dumps(doc_data, ensure_ascii=False).encode('utf-8')
    
    # Criar serviço e assinar
    service = AssinaturaDigitalService(db)
    envelope = await service.criar_envelope_assinado(
        documento_id=usuario_id,  # Usar como ID do documento
        usuario_id=usuario_id,
        documento_bytes=documento_bytes,
        certificado_base64=certificado_base64,
        senha=senha,
        politica="AD-RB"
    )
    
    # Adicionar dados do espelho ao envelope
    envelope["espelho_ponto"] = doc_data
    
    return envelope
