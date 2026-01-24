-- Script para popular banco de dados VibePonto com dados realistas
-- Tenant principal
\set tenant_id '20f38fb2-adf0-42e8-9ce6-1599152f7580'

-- Senha hash para 'Senha@123' (bcrypt)
\set senha_hash '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.mqjvjfXQPOLdOy'

-- 1. CRIAR EQUIPES
INSERT INTO equipes (id, tenant_id, nome, descricao, cor, created_at, updated_at) VALUES
('a1111111-1111-1111-1111-111111111111', :'tenant_id'::uuid, 'Administrativo', 'Equipe Administrativa', '#3B82F6', NOW(), NOW()),
('a2222222-2222-2222-2222-222222222222', :'tenant_id'::uuid, 'Desenvolvimento', 'Equipe de Desenvolvimento de Software', '#10B981', NOW(), NOW()),
('a3333333-3333-3333-3333-333333333333', :'tenant_id'::uuid, 'Suporte', 'Equipe de Suporte ao Cliente', '#F59E0B', NOW(), NOW()),
('a4444444-4444-4444-4444-444444444444', :'tenant_id'::uuid, 'Comercial', 'Equipe Comercial e Vendas', '#EF4444', NOW(), NOW()),
('a5555555-5555-5555-5555-555555555555', :'tenant_id'::uuid, 'RH', 'Recursos Humanos', '#8B5CF6', NOW(), NOW()),
('a6666666-6666-6666-6666-666666666666', :'tenant_id'::uuid, 'Financeiro', 'Departamento Financeiro', '#EC4899', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- 2. CRIAR COLABORADORES
INSERT INTO usuarios (id, tenant_id, nome, email, cpf, telefone, matricula, password_hash, papel, status, equipe_id, mfa_enabled, created_at, updated_at) VALUES
-- Gestores
('b1111111-1111-1111-1111-111111111111', :'tenant_id'::uuid, 'Maria Silva Santos', 'maria.santos@vibeponto.com', '12345678901', '17999001001', 'VBP20240001', :'senha_hash', 'gestor', 'active', 'a1111111-1111-1111-1111-111111111111', false, NOW(), NOW()),
('b2222222-2222-2222-2222-222222222222', :'tenant_id'::uuid, 'Ricardo Almeida Costa', 'ricardo.costa@vibeponto.com', '67890123456', '17999001002', 'VBP20240002', :'senha_hash', 'gestor', 'active', 'a4444444-4444-4444-4444-444444444444', false, NOW(), NOW()),

-- Colaboradores Desenvolvimento
('b3333333-3333-3333-3333-333333333333', :'tenant_id'::uuid, 'João Pedro Oliveira', 'joao.oliveira@vibeponto.com', '23456789012', '17999001003', 'VBP20240003', :'senha_hash', 'colaborador', 'active', 'a2222222-2222-2222-2222-222222222222', false, NOW(), NOW()),
('b4444444-4444-4444-4444-444444444444', :'tenant_id'::uuid, 'Ana Carolina Lima', 'ana.lima@vibeponto.com', '34567890123', '17999001004', 'VBP20240004', :'senha_hash', 'colaborador', 'active', 'a2222222-2222-2222-2222-222222222222', false, NOW(), NOW()),
('b5555555-5555-5555-5555-555555555555', :'tenant_id'::uuid, 'Bruno Henrique Dias', 'bruno.dias@vibeponto.com', '89012345678', '17999001005', 'VBP20240005', :'senha_hash', 'colaborador', 'active', 'a2222222-2222-2222-2222-222222222222', false, NOW(), NOW()),

-- Colaboradores Suporte
('b6666666-6666-6666-6666-666666666666', :'tenant_id'::uuid, 'Carlos Eduardo Souza', 'carlos.souza@vibeponto.com', '45678901234', '17999001006', 'VBP20240006', :'senha_hash', 'colaborador', 'active', 'a3333333-3333-3333-3333-333333333333', false, NOW(), NOW()),
('b7777777-7777-7777-7777-777777777777', :'tenant_id'::uuid, 'Lucas Gabriel Martins', 'lucas.martins@vibeponto.com', '01234567890', '17999001007', 'VBP20240007', :'senha_hash', 'colaborador', 'active', 'a3333333-3333-3333-3333-333333333333', false, NOW(), NOW()),

-- Colaboradores Comercial
('b8888888-8888-8888-8888-888888888888', :'tenant_id'::uuid, 'Fernanda Rodrigues', 'fernanda.rodrigues@vibeponto.com', '56789012345', '17999001008', 'VBP20240008', :'senha_hash', 'colaborador', 'active', 'a4444444-4444-4444-4444-444444444444', false, NOW(), NOW()),

-- Colaboradores RH
('b9999999-9999-9999-9999-999999999999', :'tenant_id'::uuid, 'Juliana Pereira Nunes', 'juliana.nunes@vibeponto.com', '78901234567', '17999001009', 'VBP20240009', :'senha_hash', 'colaborador', 'active', 'a5555555-5555-5555-5555-555555555555', false, NOW(), NOW()),
('baaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', :'tenant_id'::uuid, 'Patrícia Mendes Ferreira', 'patricia.ferreira@vibeponto.com', '90123456789', '17999001010', 'VBP20240010', :'senha_hash', 'auditor', 'active', 'a5555555-5555-5555-5555-555555555555', false, NOW(), NOW()),

-- Colaboradores Administrativo
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', :'tenant_id'::uuid, 'Camila Rocha Barbosa', 'camila.barbosa@vibeponto.com', '11223344556', '17999001011', 'VBP20240011', :'senha_hash', 'colaborador', 'active', 'a1111111-1111-1111-1111-111111111111', false, NOW(), NOW()),

-- Financeiro
('bcccccc-cccc-cccc-cccc-cccccccccccc', :'tenant_id'::uuid, 'Thiago Fernandes Lopes', 'thiago.lopes@vibeponto.com', '22334455667', '17999001012', 'VBP20240012', :'senha_hash', 'financeiro', 'active', 'a6666666-6666-6666-6666-666666666666', false, NOW(), NOW())
ON CONFLICT DO NOTHING;

-- 3. GERAR MARCAÇÕES DE PONTO PARA JANEIRO DE 2026
-- Criando função temporária para gerar marcações em massa
DO $$
DECLARE
    v_tenant_id uuid := '20f38fb2-adf0-42e8-9ce6-1599152f7580';
    v_usuario record;
    v_data date;
    v_hora_entrada time;
    v_hora_pausa_ini time;
    v_hora_pausa_fim time;
    v_hora_saida time;
    v_rand float;
    v_lat float;
    v_lng float;
    v_tipo text;
    v_validado boolean;
BEGIN
    -- Para cada usuário (exceto admin)
    FOR v_usuario IN 
        SELECT id, nome FROM usuarios 
        WHERE tenant_id = v_tenant_id AND papel != 'admin_dp'
    LOOP
        -- Para cada dia de janeiro de 2026 (dias 2 a 23)
        FOR v_data IN SELECT generate_series('2026-01-02'::date, '2026-01-23'::date, '1 day'::interval)::date
        LOOP
            -- Pular fins de semana
            IF EXTRACT(DOW FROM v_data) IN (0, 6) THEN
                CONTINUE;
            END IF;
            
            -- 5% de chance de falta
            v_rand := random();
            IF v_rand < 0.05 THEN
                CONTINUE;
            END IF;
            
            -- Gerar horários com variações
            v_rand := random();
            IF v_rand < 0.10 THEN
                -- 10% atraso
                v_hora_entrada := '08:30:00'::time + (random() * interval '30 minutes');
            ELSE
                v_hora_entrada := '08:00:00'::time + (random() * interval '15 minutes');
            END IF;
            
            v_hora_pausa_ini := '12:00:00'::time + (random() * interval '10 minutes');
            v_hora_pausa_fim := '13:00:00'::time + (random() * interval '15 minutes');
            
            v_rand := random();
            IF v_rand < 0.15 THEN
                -- 15% hora extra
                v_hora_saida := '18:00:00'::time + (random() * interval '2 hours');
            ELSE
                v_hora_saida := '17:00:00'::time + (random() * interval '30 minutes');
            END IF;
            
            -- Coordenadas de São José do Rio Preto
            v_lat := -20.8197 + (random() - 0.5) * 0.02;
            v_lng := -49.3794 + (random() - 0.5) * 0.02;
            
            -- Tipo aleatório
            v_rand := random();
            IF v_rand < 0.4 THEN
                v_tipo := 'WEB';
            ELSIF v_rand < 0.7 THEN
                v_tipo := 'FACIAL';
            ELSE
                v_tipo := 'FOTO';
            END IF;
            
            v_validado := random() > 0.1;
            
            -- Inserir ENTRADA
            INSERT INTO marcacoes_ponto (id, tenant_id, usuario_id, data_hora, evento, tipo, latitude, longitude, validado, created_at, updated_at)
            VALUES (gen_random_uuid(), v_tenant_id, v_usuario.id, v_data + v_hora_entrada, 'ENTRADA', v_tipo, v_lat, v_lng, v_validado, NOW(), NOW());
            
            -- Inserir PAUSA_INICIO
            INSERT INTO marcacoes_ponto (id, tenant_id, usuario_id, data_hora, evento, tipo, latitude, longitude, validado, created_at, updated_at)
            VALUES (gen_random_uuid(), v_tenant_id, v_usuario.id, v_data + v_hora_pausa_ini, 'PAUSA_INICIO', v_tipo, v_lat, v_lng, v_validado, NOW(), NOW());
            
            -- Inserir PAUSA_FIM
            INSERT INTO marcacoes_ponto (id, tenant_id, usuario_id, data_hora, evento, tipo, latitude, longitude, validado, created_at, updated_at)
            VALUES (gen_random_uuid(), v_tenant_id, v_usuario.id, v_data + v_hora_pausa_fim, 'PAUSA_FIM', v_tipo, v_lat, v_lng, v_validado, NOW(), NOW());
            
            -- Inserir SAIDA
            INSERT INTO marcacoes_ponto (id, tenant_id, usuario_id, data_hora, evento, tipo, latitude, longitude, validado, created_at, updated_at)
            VALUES (gen_random_uuid(), v_tenant_id, v_usuario.id, v_data + v_hora_saida, 'SAIDA', v_tipo, v_lat, v_lng, v_validado, NOW(), NOW());
            
        END LOOP;
        RAISE NOTICE 'Marcações geradas para: %', v_usuario.nome;
    END LOOP;
END $$;

-- 4. VERIFICAR RESULTADO
SELECT 'Equipes' as tabela, COUNT(*) as total FROM equipes WHERE tenant_id = '20f38fb2-adf0-42e8-9ce6-1599152f7580'
UNION ALL
SELECT 'Usuários', COUNT(*) FROM usuarios WHERE tenant_id = '20f38fb2-adf0-42e8-9ce6-1599152f7580'
UNION ALL
SELECT 'Marcações', COUNT(*) FROM marcacoes_ponto WHERE tenant_id = '20f38fb2-adf0-42e8-9ce6-1599152f7580';
