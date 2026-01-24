"""Script de seed para dados iniciais de desenvolvimento."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, init_db
from app.core.security import hash_password
from app.models import (
    BeneficioCarteira,
    BeneficioTipo,
    Equipe,
    Escala,
    EscalaRegime,
    MarcacaoEvento,
    MarcacaoPonto,
    MarcacaoStatus,
    MarcacaoTipo,
    Perimetro,
    Tenant,
    Usuario,
    UserRole,
    UserStatus,
)


async def seed_database():
    """Popula o banco com dados de desenvolvimento."""
    
    print("🌱 Iniciando seed do banco de dados...")
    
    # Inicializar banco
    await init_db()
    
    async with async_session_maker() as db:
        # Verificar se já tem dados
        result = await db.execute(select(Tenant))
        if result.scalar_one_or_none():
            print("⚠️  Banco já possui dados. Pulando seed.")
            return
        
        # ================================================================
        # TENANT
        # ================================================================
        print("📦 Criando tenant...")
        
        tenant = Tenant(
            id=uuid4(),
            nome="Vibe Coding Ltda",
            cnpj="12.345.678/0001-90",
            email="contato@vibecoding.com.br",
            telefone="(11) 99999-9999",
            endereco={
                "logradouro": "Av. Paulista",
                "numero": "1000",
                "complemento": "Sala 1001",
                "bairro": "Bela Vista",
                "cidade": "São Paulo",
                "estado": "SP",
                "cep": "01310-100",
            },
            config={
                "timezone": "America/Sao_Paulo",
                "marcacao_foto_obrigatoria": True,
                "marcacao_geo_obrigatoria": True,
                "tolerancia_atraso_min": 10,
            },
        )
        db.add(tenant)
        
        # ================================================================
        # EQUIPES
        # ================================================================
        print("👥 Criando equipes...")
        
        equipe_dev = Equipe(
            id=uuid4(),
            tenant_id=tenant.id,
            nome="Desenvolvimento",
            descricao="Time de desenvolvimento de software",
        )
        db.add(equipe_dev)
        
        equipe_ops = Equipe(
            id=uuid4(),
            tenant_id=tenant.id,
            nome="Operações",
            descricao="Time de operações e suporte",
        )
        db.add(equipe_ops)
        
        # ================================================================
        # USUÁRIOS
        # ================================================================
        print("👤 Criando usuários...")
        
        # Admin
        admin = Usuario(
            id=uuid4(),
            tenant_id=tenant.id,
            nome="Administrador",
            email="admin@vibecoding.com.br",
            cpf="111.111.111-11",
            telefone="(11) 99999-0001",
            matricula="ADM001",
            password_hash=hash_password("Admin@123"),
            papel=UserRole.ADMIN_DP,
            status=UserStatus.ACTIVE,
        )
        db.add(admin)
        
        # Gestor
        gestor = Usuario(
            id=uuid4(),
            tenant_id=tenant.id,
            nome="João Silva",
            email="joao@vibecoding.com.br",
            cpf="222.222.222-22",
            telefone="(11) 99999-0002",
            matricula="GES001",
            password_hash=hash_password("Gestor@123"),
            papel=UserRole.GESTOR,
            status=UserStatus.ACTIVE,
            equipe_id=equipe_dev.id,
        )
        db.add(gestor)
        
        # Atualizar líder da equipe
        equipe_dev.lider_id = gestor.id
        
        # Colaboradores
        colaboradores = []
        for i, nome in enumerate(["Maria Santos", "Pedro Costa", "Ana Oliveira"], start=1):
            colab = Usuario(
                id=uuid4(),
                tenant_id=tenant.id,
                nome=nome,
                email=f"{nome.split()[0].lower()}@vibecoding.com.br",
                cpf=f"{i+2}{i+2}{i+2}.{i+2}{i+2}{i+2}.{i+2}{i+2}{i+2}-{i+2}{i+2}",
                telefone=f"(11) 99999-000{i+2}",
                matricula=f"COL00{i}",
                password_hash=hash_password("Colab@123"),
                papel=UserRole.COLABORADOR,
                status=UserStatus.ACTIVE,
                equipe_id=equipe_dev.id,
            )
            db.add(colab)
            colaboradores.append(colab)
        
        # ================================================================
        # PERÍMETRO
        # ================================================================
        print("📍 Criando perímetro...")
        
        perimetro = Perimetro(
            id=uuid4(),
            tenant_id=tenant.id,
            nome="Escritório Sede",
            descricao="Perímetro do escritório na Av. Paulista",
            equipe_id=equipe_dev.id,
            centro_lat=Decimal("-23.561414"),
            centro_lng=Decimal("-46.656589"),
            raio_metros=200,
            tolerancia_metros=50,
            tolerancia_minutos=5,
        )
        db.add(perimetro)
        
        # ================================================================
        # ESCALA
        # ================================================================
        print("📅 Criando escala...")
        
        escala = Escala(
            id=uuid4(),
            tenant_id=tenant.id,
            nome="Horário Comercial",
            equipe_id=equipe_dev.id,
            regime=EscalaRegime.FIXO,
            janelas={
                "seg": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "ter": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "qua": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "qui": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "sex": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
            },
            tolerancia_entrada_min=10,
            tolerancia_saida_min=10,
        )
        db.add(escala)
        
        # ================================================================
        # MARCAÇÕES DE EXEMPLO
        # ================================================================
        print("⏱️  Criando marcações de exemplo...")
        
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for colab in colaboradores:
            for dias_atras in range(5):
                data = hoje - timedelta(days=dias_atras)
                
                # Pular fins de semana
                if data.weekday() >= 5:
                    continue
                
                # Entrada
                entrada = MarcacaoPonto(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    usuario_id=colab.id,
                    perimetro_id=perimetro.id,
                    tipo=MarcacaoTipo.FACIAL,
                    evento=MarcacaoEvento.ENTRADA,
                    timestamp_local=data.replace(hour=8, minute=5),
                    timestamp_servidor=data.replace(hour=8, minute=5),
                    latitude=Decimal("-23.561414"),
                    longitude=Decimal("-46.656589"),
                    accuracy_metros=10,
                    modo="online",
                    status=MarcacaoStatus.PROCESSADO,
                )
                db.add(entrada)
                
                # Saída para almoço
                pausa_inicio = MarcacaoPonto(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    usuario_id=colab.id,
                    perimetro_id=perimetro.id,
                    tipo=MarcacaoTipo.FACIAL,
                    evento=MarcacaoEvento.PAUSA_INICIO,
                    timestamp_local=data.replace(hour=12, minute=0),
                    timestamp_servidor=data.replace(hour=12, minute=0),
                    latitude=Decimal("-23.561414"),
                    longitude=Decimal("-46.656589"),
                    accuracy_metros=10,
                    modo="online",
                    status=MarcacaoStatus.PROCESSADO,
                )
                db.add(pausa_inicio)
                
                # Retorno do almoço
                pausa_fim = MarcacaoPonto(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    usuario_id=colab.id,
                    perimetro_id=perimetro.id,
                    tipo=MarcacaoTipo.FACIAL,
                    evento=MarcacaoEvento.PAUSA_FIM,
                    timestamp_local=data.replace(hour=13, minute=0),
                    timestamp_servidor=data.replace(hour=13, minute=0),
                    latitude=Decimal("-23.561414"),
                    longitude=Decimal("-46.656589"),
                    accuracy_metros=10,
                    modo="online",
                    status=MarcacaoStatus.PROCESSADO,
                )
                db.add(pausa_fim)
                
                # Saída
                saida = MarcacaoPonto(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    usuario_id=colab.id,
                    perimetro_id=perimetro.id,
                    tipo=MarcacaoTipo.FACIAL,
                    evento=MarcacaoEvento.SAIDA,
                    timestamp_local=data.replace(hour=17, minute=10),
                    timestamp_servidor=data.replace(hour=17, minute=10),
                    latitude=Decimal("-23.561414"),
                    longitude=Decimal("-46.656589"),
                    accuracy_metros=10,
                    modo="online",
                    status=MarcacaoStatus.PROCESSADO,
                )
                db.add(saida)
        
        # ================================================================
        # CARTEIRAS DE BENEFÍCIO
        # ================================================================
        print("💳 Criando carteiras de benefício...")
        
        for colab in colaboradores:
            # VA
            carteira_va = BeneficioCarteira(
                id=uuid4(),
                tenant_id=tenant.id,
                usuario_id=colab.id,
                tipo=BeneficioTipo.VA,
                nome="Vale Alimentação",
                saldo=Decimal("800.00"),
                politica={
                    "limite_diario": 200,
                    "categorias_permitidas": ["supermercado", "alimentacao"],
                },
            )
            db.add(carteira_va)
            
            # VR
            carteira_vr = BeneficioCarteira(
                id=uuid4(),
                tenant_id=tenant.id,
                usuario_id=colab.id,
                tipo=BeneficioTipo.VR,
                nome="Vale Refeição",
                saldo=Decimal("600.00"),
                politica={
                    "limite_diario": 50,
                    "categorias_permitidas": ["restaurante", "lanchonete"],
                },
            )
            db.add(carteira_vr)
        
        # ================================================================
        # COMMIT
        # ================================================================
        await db.commit()
        
        print("✅ Seed concluído com sucesso!")
        print("")
        print("📋 Credenciais de acesso:")
        print("   Admin:       admin@vibecoding.com.br / Admin@123")
        print("   Gestor:      joao@vibecoding.com.br / Gestor@123")
        print("   Colaborador: maria@vibecoding.com.br / Colab@123")


if __name__ == "__main__":
    asyncio.run(seed_database())
