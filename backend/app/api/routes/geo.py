"""Router de geofencing e perímetros."""

from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import Perimetro, Usuario
from app.schemas import (
    PaginatedResponse,
    PerimetroCreateCircle,
    PerimetroCreatePolygon,
    PerimetroRead,
    PerimetroUpdate,
    PerimetroValidateRequest,
    PerimetroValidateResponse,
    SuccessResponse,
)


router = APIRouter(prefix="/geo", tags=["Geofencing"])


@router.get("/perimetros", response_model=PaginatedResponse[PerimetroRead])
async def listar_perimetros(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    ativo: Optional[bool] = None,
    usuario_id: Optional[UUID] = None,
    equipe_id: Optional[UUID] = None,
):
    """Listar perímetros."""
    
    query = select(Perimetro).where(Perimetro.tenant_id == tenant.tenant_id)
    count_query = select(func.count(Perimetro.id)).where(
        Perimetro.tenant_id == tenant.tenant_id
    )
    
    if ativo is not None:
        query = query.where(Perimetro.ativo == ativo)
        count_query = count_query.where(Perimetro.ativo == ativo)
    
    if usuario_id:
        query = query.where(Perimetro.usuario_id == usuario_id)
        count_query = count_query.where(Perimetro.usuario_id == usuario_id)
    
    if equipe_id:
        query = query.where(Perimetro.equipe_id == equipe_id)
        count_query = count_query.where(Perimetro.equipe_id == equipe_id)
    
    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Paginação
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Perimetro.nome)
    
    result = await db.execute(query)
    perimetros = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[PerimetroRead.model_validate(p) for p in perimetros],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/perimetros/circulo", response_model=PerimetroRead, status_code=status.HTTP_201_CREATED)
async def criar_perimetro_circular(
    data: PerimetroCreateCircle,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar perímetro circular (centro + raio)."""
    
    # Criar geometria de buffer a partir do ponto
    # Em produção, usar ST_Buffer do PostGIS
    from geoalchemy2 import WKTElement
    
    # Criar ponto WKT
    point_wkt = f"POINT({data.centro_lng} {data.centro_lat})"
    
    perimetro = Perimetro(
        tenant_id=tenant.tenant_id,
        nome=data.nome,
        descricao=data.descricao,
        usuario_id=data.usuario_id,
        equipe_id=data.equipe_id,
        centro_lat=data.centro_lat,
        centro_lng=data.centro_lng,
        raio_metros=data.raio_metros,
        tolerancia_metros=data.tolerancia_metros,
        tolerancia_minutos=data.tolerancia_minutos,
        # geom será preenchido via trigger ou função PostgreSQL
    )
    
    db.add(perimetro)
    await db.commit()
    await db.refresh(perimetro)
    
    return PerimetroRead.model_validate(perimetro)


@router.post("/perimetros/poligono", response_model=PerimetroRead, status_code=status.HTTP_201_CREATED)
async def criar_perimetro_poligonal(
    data: PerimetroCreatePolygon,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar perímetro poligonal."""
    
    if not data.polygon.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Polígono inválido. Mínimo 4 pontos e deve ser fechado.",
        )
    
    # Criar WKT do polígono
    coords_str = ", ".join(f"{lng} {lat}" for lng, lat in data.polygon.coordinates)
    polygon_wkt = f"POLYGON(({coords_str}))"
    
    from geoalchemy2 import WKTElement
    
    perimetro = Perimetro(
        tenant_id=tenant.tenant_id,
        nome=data.nome,
        descricao=data.descricao,
        usuario_id=data.usuario_id,
        equipe_id=data.equipe_id,
        geom=WKTElement(polygon_wkt, srid=4326),
        tolerancia_metros=data.tolerancia_metros,
        tolerancia_minutos=data.tolerancia_minutos,
    )
    
    db.add(perimetro)
    await db.commit()
    await db.refresh(perimetro)
    
    return PerimetroRead.model_validate(perimetro)


@router.get("/perimetros/{perimetro_id}", response_model=PerimetroRead)
async def get_perimetro(
    perimetro_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter perímetro por ID."""
    
    result = await db.execute(
        select(Perimetro).where(
            Perimetro.id == perimetro_id,
            Perimetro.tenant_id == tenant.tenant_id,
        )
    )
    perimetro = result.scalar_one_or_none()
    
    if not perimetro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perímetro não encontrado",
        )
    
    return PerimetroRead.model_validate(perimetro)


@router.patch("/perimetros/{perimetro_id}", response_model=PerimetroRead)
async def update_perimetro(
    perimetro_id: UUID,
    data: PerimetroUpdate,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar perímetro."""
    
    result = await db.execute(
        select(Perimetro).where(
            Perimetro.id == perimetro_id,
            Perimetro.tenant_id == tenant.tenant_id,
        )
    )
    perimetro = result.scalar_one_or_none()
    
    if not perimetro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perímetro não encontrado",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Perimetro)
            .where(Perimetro.id == perimetro_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(perimetro)
    
    return PerimetroRead.model_validate(perimetro)


@router.delete("/perimetros/{perimetro_id}", response_model=SuccessResponse)
async def delete_perimetro(
    perimetro_id: UUID,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Desativar perímetro."""
    
    result = await db.execute(
        select(Perimetro).where(
            Perimetro.id == perimetro_id,
            Perimetro.tenant_id == tenant.tenant_id,
        )
    )
    perimetro = result.scalar_one_or_none()
    
    if not perimetro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perímetro não encontrado",
        )
    
    await db.execute(
        update(Perimetro)
        .where(Perimetro.id == perimetro_id)
        .values(ativo=False)
    )
    await db.commit()
    
    return SuccessResponse(message="Perímetro desativado")


@router.post("/validar", response_model=PerimetroValidateResponse)
async def validar_posicao(
    data: PerimetroValidateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Validar se uma posição está dentro de um perímetro.
    
    - Se perimetro_id fornecido, valida contra esse perímetro
    - Senão, valida contra todos os perímetros ativos do usuário
    """
    from math import radians, sin, cos, sqrt, atan2
    
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calcular distância em metros usando fórmula de Haversine."""
        R = 6371000  # Raio da Terra em metros
        
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    # Buscar perímetros
    query = select(Perimetro).where(
        Perimetro.tenant_id == tenant.tenant_id,
        Perimetro.ativo == True,
    )
    
    if data.perimetro_id:
        query = query.where(Perimetro.id == data.perimetro_id)
    else:
        # Buscar equipe do usuário
        result = await db.execute(
            select(Usuario.equipe_id).where(Usuario.id == current_user.id)
        )
        equipe_id = result.scalar_one_or_none()
        
        query = query.where(
            (Perimetro.usuario_id == current_user.id) |
            (Perimetro.equipe_id == equipe_id)
        )
    
    result = await db.execute(query)
    perimetros = result.scalars().all()
    
    if not perimetros:
        return PerimetroValidateResponse(
            dentro=False,
            tolerancia_excedida=False,
        )
    
    # Validar contra cada perímetro (simplificado para círculos)
    for p in perimetros:
        if p.centro_lat and p.centro_lng and p.raio_metros:
            distancia = haversine_distance(
                data.latitude, data.longitude,
                p.centro_lat, p.centro_lng
            )
            
            raio_total = p.raio_metros + p.tolerancia_metros
            
            if distancia <= p.raio_metros:
                return PerimetroValidateResponse(
                    dentro=True,
                    perimetro_id=p.id,
                    perimetro_nome=p.nome,
                    distancia_metros=int(distancia),
                    tolerancia_excedida=False,
                )
            elif distancia <= raio_total:
                return PerimetroValidateResponse(
                    dentro=True,
                    perimetro_id=p.id,
                    perimetro_nome=p.nome,
                    distancia_metros=int(distancia),
                    tolerancia_excedida=True,
                )
    
    # Não está em nenhum perímetro
    # Calcular distância do mais próximo
    menor_distancia = float('inf')
    perimetro_proximo = None
    
    for p in perimetros:
        if p.centro_lat and p.centro_lng:
            distancia = haversine_distance(
                data.latitude, data.longitude,
                p.centro_lat, p.centro_lng
            )
            if distancia < menor_distancia:
                menor_distancia = distancia
                perimetro_proximo = p
    
    return PerimetroValidateResponse(
        dentro=False,
        perimetro_id=perimetro_proximo.id if perimetro_proximo else None,
        perimetro_nome=perimetro_proximo.nome if perimetro_proximo else None,
        distancia_metros=int(menor_distancia) if perimetro_proximo else None,
        tolerancia_excedida=False,
    )
