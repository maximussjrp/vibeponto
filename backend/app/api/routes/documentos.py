"""Router de documentos e assinaturas."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentUser,
    RequireAdmin,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import (
    Assinatura,
    AssinaturaMetodo,
    AssinaturaStatus,
    Documento,
    DocumentoTipo,
    Usuario,
    UserRole,
)
from app.schemas import (
    AssinaturaRead,
    AssinaturaRequest,
    AssinaturaVerify,
    DocumentoCreate,
    DocumentoRead,
    DocumentoUpdate,
    DocumentoUpload,
    DocumentoWithAssinaturas,
    LoteDocumentosCreate,
    LoteDocumentosStatus,
    PaginatedResponse,
    SuccessResponse,
)
from app.services import get_storage_service


router = APIRouter(prefix="/documentos", tags=["Documentos"])


@router.get("", response_model=PaginatedResponse[DocumentoRead])
async def listar_documentos(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    tipo: Optional[DocumentoTipo] = None,
    usuario_id: Optional[UUID] = None,
    periodo_referencia: Optional[str] = None,
    assinatura_status: Optional[AssinaturaStatus] = None,
):
    """
    Listar documentos.
    
    - Colaborador vê apenas seus documentos
    - Gestor/Admin vê todos do tenant
    """
    query = select(Documento).where(Documento.tenant_id == tenant.tenant_id)
    count_query = select(func.count(Documento.id)).where(
        Documento.tenant_id == tenant.tenant_id
    )
    
    # Filtro por permissão
    if not current_user.has_role(UserRole.ADMIN_DP, UserRole.GESTOR):
        query = query.where(Documento.usuario_id == current_user.id)
        count_query = count_query.where(Documento.usuario_id == current_user.id)
    
    # Filtros específicos
    if tipo:
        query = query.where(Documento.tipo == tipo)
        count_query = count_query.where(Documento.tipo == tipo)
    
    if usuario_id:
        query = query.where(Documento.usuario_id == usuario_id)
        count_query = count_query.where(Documento.usuario_id == usuario_id)
    
    if periodo_referencia:
        query = query.where(Documento.periodo_referencia == periodo_referencia)
        count_query = count_query.where(Documento.periodo_referencia == periodo_referencia)
    
    if assinatura_status:
        query = query.where(Documento.assinatura_status == assinatura_status)
        count_query = count_query.where(Documento.assinatura_status == assinatura_status)
    
    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Paginação
    query = query.order_by(Documento.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    documentos = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[DocumentoRead.model_validate(d) for d in documentos],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=DocumentoRead, status_code=status.HTTP_201_CREATED)
async def criar_documento(
    data: DocumentoCreate,
    upload: DocumentoUpload,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar documento com upload de arquivo."""
    
    # Verificar usuário existe
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == data.usuario_id,
            Usuario.tenant_id == tenant.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário não encontrado",
        )
    
    # Upload do arquivo
    storage = get_storage_service()
    upload_result = await storage.upload_base64(
        tenant_id=tenant.tenant_id,
        folder="documentos",
        filename=upload.arquivo_nome,
        base64_content=upload.arquivo_base64,
        content_type=upload.arquivo_mime,
    )
    
    # Criar documento
    documento = Documento(
        tenant_id=tenant.tenant_id,
        usuario_id=data.usuario_id,
        tipo=data.tipo,
        titulo=data.titulo,
        descricao=data.descricao,
        periodo_referencia=data.periodo_referencia,
        arquivo_url=upload_result["url"],
        arquivo_nome=upload.arquivo_nome,
        arquivo_tamanho=upload_result["size"],
        arquivo_hash=upload_result["hash"],
        arquivo_mime=upload.arquivo_mime,
        requer_assinatura=data.requer_assinatura,
        extra_data=data.metadata,
    )
    
    db.add(documento)
    await db.commit()
    await db.refresh(documento)
    
    return DocumentoRead.model_validate(documento)


@router.get("/{documento_id}", response_model=DocumentoWithAssinaturas)
async def get_documento(
    documento_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter documento com assinaturas."""
    
    result = await db.execute(
        select(Documento)
        .options(selectinload(Documento.assinaturas))
        .where(
            Documento.id == documento_id,
            Documento.tenant_id == tenant.tenant_id,
        )
    )
    documento = result.scalar_one_or_none()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado",
        )
    
    # Verificar permissão
    if not current_user.is_gestor() and documento.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    response = DocumentoWithAssinaturas.model_validate(documento)
    response.assinaturas = [AssinaturaRead.model_validate(a) for a in documento.assinaturas]
    
    return response


@router.get("/{documento_id}/download")
async def download_documento(
    documento_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gerar URL de download do documento."""
    
    result = await db.execute(
        select(Documento).where(
            Documento.id == documento_id,
            Documento.tenant_id == tenant.tenant_id,
        )
    )
    documento = result.scalar_one_or_none()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado",
        )
    
    # Verificar permissão
    if not current_user.is_gestor() and documento.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Gerar URL pré-assinada
    storage = get_storage_service()
    
    url = await storage.get_presigned_url(
        key=documento.arquivo_url,
        expires_in=3600,
        download_filename=documento.arquivo_nome,
    )
    
    return {"download_url": url, "expires_in": 3600}


# ============================================================================
# ASSINATURAS
# ============================================================================

@router.post("/{documento_id}/assinar", response_model=AssinaturaRead)
async def assinar_documento(
    documento_id: UUID,
    data: AssinaturaRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """Assinar documento."""
    
    result = await db.execute(
        select(Documento).with_for_update().where(
            Documento.id == documento_id,
            Documento.tenant_id == tenant.tenant_id,
        )
    )
    documento = result.scalar_one_or_none()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado",
        )
    
    # Even administrators cannot sign for a different recipient.
    if documento.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o destinatário pode assinar")
    if data.metodo != AssinaturaMetodo.ESIGN:
        raise HTTPException(status_code=400, detail="Método de assinatura não implementado")

    # Verificar se requer assinatura
    if not documento.requer_assinatura:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este documento não requer assinatura",
        )
    
    # Verificar se já assinou
    result = await db.execute(
        select(Assinatura).where(
            Assinatura.documento_id == documento_id,
            Assinatura.usuario_id == current_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documento já assinado por este usuário",
        )
    
    # Criar assinatura
    import hashlib
    
    # Gerar hash combinado (documento + usuário + timestamp)
    signature_data = f"{documento.arquivo_hash}|{current_user.id}|{datetime.utcnow().isoformat()}"
    assinatura_hash = hashlib.sha256(signature_data.encode()).hexdigest()
    
    assinatura = Assinatura(
        documento_id=documento_id,
        usuario_id=current_user.id,
        metodo=data.metodo,
        status=AssinaturaStatus.ASSINADO,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent", "")[:500],
        geoloc=data.geoloc,
        documento_hash=documento.arquivo_hash,
        assinatura_data=assinatura_hash,
        assinado_em=datetime.utcnow(),
    )
    
    db.add(assinatura)
    
    # Atualizar status do documento
    await db.execute(
        update(Documento)
        .where(Documento.id == documento_id)
        .values(assinatura_status=AssinaturaStatus.ASSINADO)
    )
    
    await db.commit()
    await db.refresh(assinatura)
    
    return AssinaturaRead.model_validate(assinatura)


@router.get("/{documento_id}/assinaturas/{assinatura_id}/verificar", response_model=AssinaturaVerify)
async def verificar_assinatura(
    documento_id: UUID,
    assinatura_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verificar validade de uma assinatura."""
    
    result = await db.execute(
        select(Assinatura)
        .join(Documento)
        .where(
            Assinatura.id == assinatura_id,
            Assinatura.documento_id == documento_id,
            Documento.tenant_id == tenant.tenant_id,
        )
    )
    assinatura = result.scalar_one_or_none()
    
    if not assinatura:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assinatura não encontrada",
        )
    
    # Buscar documento e usuário
    result = await db.execute(
        select(Documento).where(Documento.id == documento_id)
    )
    documento = result.scalar_one()
    if not current_user.is_gestor() and documento.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = await db.execute(
        select(Usuario).where(Usuario.id == assinatura.usuario_id)
    )
    usuario = result.scalar_one()
    
    # Verificar integridade
    valida = (
        assinatura.status == AssinaturaStatus.ASSINADO and
        assinatura.documento_hash == documento.arquivo_hash
    )
    
    return AssinaturaVerify(
        valida=valida,
        documento_hash=documento.arquivo_hash,
        assinatura_hash=assinatura.assinatura_data or "",
        assinado_em=assinatura.assinado_em,
        usuario_nome=usuario.nome,
    )


# ============================================================================
# LOTE DE DOCUMENTOS
# ============================================================================

@router.post("/lote", response_model=LoteDocumentosStatus, status_code=status.HTTP_202_ACCEPTED)
async def criar_lote_documentos(
    data: LoteDocumentosCreate,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Criar lote de documentos para múltiplos usuários.
    
    Processa em background e retorna ID do lote para acompanhamento.
    """
    from uuid import uuid4
    
    lote_id = uuid4()
    
    # TODO: Criar job de processamento em background
    # Por enquanto, retorna status placeholder
    
    return LoteDocumentosStatus(
        lote_id=lote_id,
        total=len(data.usuarios_ids),
        processados=0,
        sucesso=0,
        falha=0,
        status="pendente",
    )


@router.get("/lote/{lote_id}", response_model=LoteDocumentosStatus)
async def get_lote_status(
    lote_id: UUID,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
):
    """Consultar status de processamento de lote."""
    
    # TODO: Buscar status real do lote
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Lote não encontrado",
    )
