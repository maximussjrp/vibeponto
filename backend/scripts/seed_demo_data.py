"""
Script para popular o banco de dados com dados de demonstração realistas
Para executar: python -m scripts.seed_demo_data
"""
import asyncio
import uuid
from datetime import datetime, date, time, timedelta
import random
from passlib.context import CryptContext

# Configuração do bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tenant principal (usar o existente do max)
TENANT_ID = "e4dd1ab2-76e9-43bb-b34d-469862099f82"  # Será atualizado depois

# Colaboradores fictícios realistas
COLABORADORES = [
    {"nome": "Maria Silva Santos", "email": "maria.santos@vibeponto.com", "cpf": "12345678901", "papel": "gestor", "equipe": "Administrativo"},
    {"nome": "João Pedro Oliveira", "email": "joao.oliveira@vibeponto.com", "cpf": "23456789012", "papel": "colaborador", "equipe": "Desenvolvimento"},
    {"nome": "Ana Carolina Lima", "email": "ana.lima@vibeponto.com", "cpf": "34567890123", "papel": "colaborador", "equipe": "Desenvolvimento"},
    {"nome": "Carlos Eduardo Souza", "email": "carlos.souza@vibeponto.com", "cpf": "45678901234", "papel": "colaborador", "equipe": "Suporte"},
    {"nome": "Fernanda Rodrigues", "email": "fernanda.rodrigues@vibeponto.com", "cpf": "56789012345", "papel": "colaborador", "equipe": "Comercial"},
    {"nome": "Ricardo Almeida Costa", "email": "ricardo.costa@vibeponto.com", "cpf": "67890123456", "papel": "gestor", "equipe": "Comercial"},
    {"nome": "Juliana Pereira Nunes", "email": "juliana.nunes@vibeponto.com", "cpf": "78901234567", "papel": "colaborador", "equipe": "RH"},
    {"nome": "Bruno Henrique Dias", "email": "bruno.dias@vibeponto.com", "cpf": "89012345678", "papel": "colaborador", "equipe": "Desenvolvimento"},
    {"nome": "Patrícia Mendes Ferreira", "email": "patricia.ferreira@vibeponto.com", "cpf": "90123456789", "papel": "auditor", "equipe": "RH"},
    {"nome": "Lucas Gabriel Martins", "email": "lucas.martins@vibeponto.com", "cpf": "01234567890", "papel": "colaborador", "equipe": "Suporte"},
    {"nome": "Camila Rocha Barbosa", "email": "camila.barbosa@vibeponto.com", "cpf": "11223344556", "papel": "colaborador", "equipe": "Administrativo"},
    {"nome": "Thiago Fernandes Lopes", "email": "thiago.lopes@vibeponto.com", "cpf": "22334455667", "papel": "financeiro", "equipe": "Financeiro"},
]

EQUIPES = ["Administrativo", "Desenvolvimento", "Suporte", "Comercial", "RH", "Financeiro"]

# SQL para inserir dados
INSERT_EQUIPE = """
INSERT INTO equipes (id, tenant_id, nome, descricao, cor, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
ON CONFLICT DO NOTHING;
"""

INSERT_USUARIO = """
INSERT INTO usuarios (id, tenant_id, nome, email, cpf, matricula, password_hash, papel, status, equipe_id, created_at, updated_at, mfa_enabled)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, NOW(), NOW(), false)
ON CONFLICT DO NOTHING;
"""

INSERT_MARCACAO = """
INSERT INTO marcacoes_ponto (id, tenant_id, usuario_id, data_hora, evento, tipo, latitude, longitude, foto_url, validado, observacao, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
ON CONFLICT DO NOTHING;
"""

def gerar_matricula(index: int) -> str:
    return f"VBP{2024}{index:04d}"

def gerar_senha_hash() -> str:
    return pwd_context.hash("Senha@123")

def gerar_cor_equipe(index: int) -> str:
    cores = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]
    return cores[index % len(cores)]

async def main():
    import asyncpg
    
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="vibeponto",
        password="vibeponto_dev_123",
        database="vibeponto"
    )
    
    try:
        # Buscar tenant do max
        tenant_row = await conn.fetchrow(
            "SELECT id FROM tenants WHERE id = (SELECT tenant_id FROM usuarios WHERE email = 'maximussjrp@hotmail.com')"
        )
        tenant_id = str(tenant_row['id']) if tenant_row else None
        
        if not tenant_id:
            print("❌ Tenant não encontrado!")
            return
        
        print(f"✅ Usando tenant: {tenant_id}")
        
        # 1. Criar equipes
        print("\n📁 Criando equipes...")
        equipe_ids = {}
        for i, equipe_nome in enumerate(EQUIPES):
            equipe_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO equipes (id, tenant_id, nome, descricao, cor, created_at, updated_at)
                VALUES ($1, $2::uuid, $3, $4, $5, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """, equipe_id, tenant_id, equipe_nome, f"Equipe de {equipe_nome}", gerar_cor_equipe(i))
            equipe_ids[equipe_nome] = equipe_id
            print(f"  ✓ Equipe: {equipe_nome}")
        
        # Buscar equipes existentes
        equipes_db = await conn.fetch("SELECT id, nome FROM equipes WHERE tenant_id = $1::uuid", tenant_id)
        for eq in equipes_db:
            equipe_ids[eq['nome']] = str(eq['id'])
        
        # 2. Criar colaboradores
        print("\n👥 Criando colaboradores...")
        usuario_ids = []
        senha_hash = gerar_senha_hash()
        
        for i, colab in enumerate(COLABORADORES):
            usuario_id = str(uuid.uuid4())
            equipe_id = equipe_ids.get(colab['equipe'])
            matricula = gerar_matricula(i + 1)
            
            try:
                await conn.execute("""
                    INSERT INTO usuarios (id, tenant_id, nome, email, cpf, matricula, password_hash, papel, status, equipe_id, created_at, updated_at, mfa_enabled)
                    VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8, 'active', $9::uuid, NOW(), NOW(), false)
                    ON CONFLICT (tenant_id, email) DO NOTHING
                """, usuario_id, tenant_id, colab['nome'], colab['email'], colab['cpf'], matricula, senha_hash, colab['papel'], equipe_id)
                usuario_ids.append(usuario_id)
                print(f"  ✓ {colab['nome']} ({colab['papel']}) - {colab['equipe']}")
            except Exception as e:
                print(f"  ⚠ Erro ao criar {colab['nome']}: {e}")
        
        # Buscar todos os usuários para gerar marcações
        usuarios_db = await conn.fetch("""
            SELECT id, nome FROM usuarios 
            WHERE tenant_id = $1::uuid AND papel != 'admin_dp'
        """, tenant_id)
        
        # 3. Gerar marcações de ponto para os últimos 30 dias
        print("\n⏰ Gerando marcações de ponto (últimos 30 dias)...")
        
        hoje = date.today()
        marcacoes_count = 0
        
        for usuario in usuarios_db:
            usuario_id = str(usuario['id'])
            usuario_nome = usuario['nome']
            
            # Gerar marcações para cada dia útil dos últimos 30 dias
            for dias_atras in range(30, -1, -1):
                dia = hoje - timedelta(days=dias_atras)
                
                # Pular fins de semana
                if dia.weekday() >= 5:  # Sábado e Domingo
                    continue
                
                # Simular algumas faltas (5% de chance)
                if random.random() < 0.05:
                    continue
                
                # Horários base com pequenas variações
                hora_entrada = time(8, random.randint(0, 15), random.randint(0, 59))
                hora_pausa_inicio = time(12, random.randint(0, 10), random.randint(0, 59))
                hora_pausa_fim = time(13, random.randint(0, 15), random.randint(0, 59))
                hora_saida = time(17, random.randint(0, 30), random.randint(0, 59))
                
                # Alguns atrasos (10% de chance)
                if random.random() < 0.10:
                    hora_entrada = time(8, random.randint(30, 59), random.randint(0, 59))
                
                # Algumas horas extras (15% de chance)
                if random.random() < 0.15:
                    hora_saida = time(random.randint(18, 20), random.randint(0, 59), random.randint(0, 59))
                
                eventos = [
                    ("ENTRADA", hora_entrada),
                    ("PAUSA_INICIO", hora_pausa_inicio),
                    ("PAUSA_FIM", hora_pausa_fim),
                    ("SAIDA", hora_saida),
                ]
                
                for evento, hora in eventos:
                    data_hora = datetime.combine(dia, hora)
                    marcacao_id = str(uuid.uuid4())
                    
                    # Coordenadas de São José do Rio Preto com pequena variação
                    lat = -20.8197 + random.uniform(-0.01, 0.01)
                    lng = -49.3794 + random.uniform(-0.01, 0.01)
                    
                    tipo = random.choice(["WEB", "FACIAL", "FOTO"])
                    validado = random.random() > 0.1  # 90% validados
                    
                    try:
                        await conn.execute("""
                            INSERT INTO marcacoes_ponto (id, tenant_id, usuario_id, data_hora, evento, tipo, latitude, longitude, foto_url, validado, observacao, created_at, updated_at)
                            VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                        """, marcacao_id, tenant_id, usuario_id, data_hora, evento, tipo, lat, lng, None, validado, None)
                        marcacoes_count += 1
                    except Exception as e:
                        pass  # Ignorar duplicatas
            
            print(f"  ✓ Marcações geradas para: {usuario_nome}")
        
        print(f"\n✅ Total de marcações criadas: {marcacoes_count}")
        
        # 4. Resumo final
        print("\n" + "="*50)
        print("📊 RESUMO DOS DADOS CRIADOS")
        print("="*50)
        
        counts = await conn.fetch("""
            SELECT 'Equipes' as tabela, COUNT(*)::int as total FROM equipes WHERE tenant_id = $1::uuid
            UNION ALL
            SELECT 'Usuários', COUNT(*)::int FROM usuarios WHERE tenant_id = $1::uuid
            UNION ALL
            SELECT 'Marcações', COUNT(*)::int FROM marcacoes_ponto WHERE tenant_id = $1::uuid
        """, tenant_id)
        
        for row in counts:
            print(f"  {row['tabela']}: {row['total']}")
        
        print("\n🔐 Senha padrão para todos os colaboradores: Senha@123")
        print("✅ Dados de demonstração criados com sucesso!")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
