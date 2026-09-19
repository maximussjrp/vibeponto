# VibePonto - Sistema de Ponto Eletrônico

Sistema completo de ponto eletrônico com benefícios flexíveis, desenvolvido com conformidade à Portaria 671/MTE e LGPD.

## 🚀 Funcionalidades

### Ponto Eletrônico
- ✅ Marcação com reconhecimento facial
- ✅ Marcação por QR Code
- ✅ Geolocalização com geofencing
- ✅ Modo offline com sincronização
- ✅ Multi-dispositivo com vinculação

### AuditorIA (IA de Auditoria)
- ✅ Detecção de fraudes em tempo real
- ✅ Análise de liveness (anti-spoofing)
- ✅ Verificação de localização
- ✅ Detecção de anomalias de horário
- ✅ Workflow de revisão manual

### Documentos
- ✅ Upload e gestão de documentos
- ✅ Assinatura eletrônica (e-Sign)
- ✅ Preparado para ICP-Brasil
- ✅ Gestão de holerites e contratos

### Benefícios Flexíveis
- ✅ Carteiras VA/VR/VT/Flex
- ✅ Cartões virtuais e físicos
- ✅ Recargas individuais e em lote
- ✅ Histórico de transações
- ✅ Políticas configuráveis

### Compliance
- ✅ Portaria 671/MTE
- ✅ Exportação AEJ
- ✅ LGPD compliant
- ✅ Multi-tenant isolado

## 🏗️ Arquitetura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Mobile    │     │     Web     │     │   Relógio   │
│  (Flutter)  │────▶│   (React)   │────▶│   (REP-P)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                 ┌─────────────────┐
                 │   API Gateway   │
                 │   (FastAPI)     │
                 └────────┬────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   PostgreSQL  │ │     Redis     │ │    MinIO      │
│  + PostGIS    │ │   (Cache)     │ │  (Storage)    │
│  + Timescale  │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
```

## 📋 Pré-requisitos

- Docker e Docker Compose
- Python 3.11+
- Node.js 18+ (para frontend)

## 🛠️ Instalação

### 1. Clonar e configurar

```bash
# Clonar repositório
git clone https://github.com/sua-org/vibeponto.git
cd vibeponto

# Copiar arquivo de ambiente
cp .env.example .env
```

### 2. Subir infraestrutura

```bash
# Subir todos os serviços
docker-compose up -d

# Verificar status
docker-compose ps
```

### 3. Acessar serviços

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | - |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin123 |
| RabbitMQ | http://localhost:15672 | vibeponto / rabbitmq_dev_123 |

### 4. Popular banco de dados

```bash
# Rodar migrations
docker-compose exec api alembic upgrade head

# Rodar seed
docker-compose exec api python -m scripts.seed
```

## 🔐 Credenciais de Desenvolvimento

Após rodar o seed:

| Perfil | Email | Senha |
|--------|-------|-------|
| Admin | admin@vibecoding.com.br | Admin@123 |
| Gestor | joao@vibecoding.com.br | Gestor@123 |
| Colaborador | maria@vibecoding.com.br | Colab@123 |

## 📁 Estrutura do Projeto

```
vibeponto/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/          # Rotas da API
│   │   │   └── deps.py          # Dependências (auth, etc)
│   │   ├── core/
│   │   │   ├── config.py        # Configurações
│   │   │   ├── database.py      # Conexão DB
│   │   │   └── security.py      # JWT, senhas
│   │   ├── models/
│   │   │   └── models.py        # Modelos SQLAlchemy
│   │   ├── schemas/             # Schemas Pydantic
│   │   ├── services/
│   │   │   ├── auditoria.py     # AuditorIA
│   │   │   └── storage.py       # MinIO
│   │   ├── tasks/               # Celery tasks
│   │   ├── main.py              # App FastAPI
│   │   └── worker.py            # Celery worker
│   ├── Dockerfile
│   └── pyproject.toml
├── scripts/
│   ├── init-db.sql              # Init PostgreSQL
│   └── seed.py                  # Dados de dev
├── docker-compose.yml
└── README.md
```

## 🔧 Desenvolvimento

### Rodar localmente (sem Docker)

```bash
# Criar ambiente virtual
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -e .

# Rodar API
uvicorn app.main:app --reload

# Rodar Celery worker (outro terminal)
celery -A app.worker worker --loglevel=info
```

### Testes

```bash
# Rodar testes
pytest

# Com cobertura
pytest --cov=app --cov-report=html
```

### Linting

```bash
# Ruff (linter + formatter)
ruff check .
ruff format .
```

## 📡 API

### Autenticação

Todas as rotas (exceto login) requerem token JWT:

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@vibecoding.com.br", "password": "Admin@123"}'

# Usar token
curl http://localhost:8000/api/v1/usuarios/me \
  -H "Authorization: Bearer <token>"
```

### Principais endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/v1/auth/login | Login |
| GET | /api/v1/usuarios/me | Perfil atual |
| POST | /api/v1/ponto | Registrar marcação |
| GET | /api/v1/espelho/{mes}/{ano} | Espelho de ponto |
| GET | /api/v1/beneficios/carteiras | Listar carteiras |

Documentação completa: http://localhost:8000/docs

## 🔒 Segurança

- JWT com refresh tokens
- Senhas com bcrypt
- MFA com TOTP
- Rate limiting
- Audit log completo
- Isolamento multi-tenant

## 📜 Conformidade

### Portaria 671/MTE
- Registro eletrônico de ponto (REP)
- Arquivo de Espelho de Ponto (AEJ)
- Comprovante de marcação
- Assinatura digital

### LGPD
- Consentimento explícito
- Direito ao esquecimento
- Portabilidade de dados
- Retenção configurável (5 anos padrão)

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Add nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

Proprietário - Vibe Coding © 2025

## Observabilidade

A API expoe tres endpoints operacionais com responsabilidades separadas:

- `/health`: liveness simples. Nao consulta dependencias e deve responder enquanto o processo estiver vivo.
- `/ready`: readiness. Verifica PostgreSQL e Redis e retorna `503` quando alguma dependencia essencial nao esta pronta.
- `/metrics`: metricas Prometheus. No `docker-compose.prod.yml`, a API usa apenas `expose` na rede interna; se um proxy publico expuser a API, bloqueie ou restrinja `/metrics` no proxy/rede de monitoramento.

Requests recebem correlation ID pelo header `X-Request-ID`. Valores enviados pelo cliente sao aceitos apenas quando possuem formato e tamanho seguros; caso contrario a API gera um UUID. O mesmo header e devolvido na resposta e tambem entra nos logs.

Logs estruturados em JSON sao habilitados por padrao para containers. Cada log pode incluir `timestamp`, `level`, `service`, `environment`, `logger`, `message`, `request_id`, `trace_id`, `span_id`, metodo HTTP, rota normalizada, status e duracao. Campos sensiveis como `Authorization`, `Cookie`, `password`, `secret`, tokens, TOTP e backup codes sao redigidos quando passados como metadados estruturados. O backend nao loga body de request globalmente.

Metricas HTTP usam apenas labels de baixa cardinalidade: `method`, rota normalizada e `status_code`. Metricas de negocio tambem usam enumeracoes pequenas, por exemplo `source="online|offline"`, `result="success|duplicate|invalid|rate_limited|error"` e `operation="upload|download|delete|presign"`. Nunca use `user_id`, `tenant_id`, `document_id`, `sync_id`, email, CPF, IP, User-Agent completo, URL completa ou object key como label.

OpenTelemetry e opcional. A aplicacao continua funcionando sem collector. Para habilitar exportacao OTLP, configure:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=vibeponto-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_HEADERS=
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.10
```

As instrumentacoes incluem FastAPI, SQLAlchemy, Redis e Celery quando OTel esta ativo. A configuracao permanece vendor-neutral e compativel com collectors/backends como Prometheus, Grafana, Tempo, Jaeger e Loki.

## Docker de producao

O `docker-compose.yml` continua sendo o ambiente de desenvolvimento, com bind mounts e comandos `--reload`/`npm run dev`.

Para producao, use `docker-compose.prod.yml`:

```bash
cp .env.production.example .env.production
# edite .env.production e substitua todos os valores de exemplo por secrets reais
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Notas importantes:

- `SECRET_KEY` e `MFA_ENCRYPTION_KEY` sao obrigatorios fora de desenvolvimento.
- `DEBUG` deve permanecer `false` e `CORS_ORIGINS` deve conter apenas origens explicitas.
- O servico `migrate` executa `alembic upgrade head` antes da API subir.
- A API, worker e beat usam a imagem `production`, sem bind mount de codigo.
- O frontend usa `next build` em imagem multi-stage e roda via `node server.js` com `output: 'standalone'`.
- O compose de producao nao publica Postgres, Redis, RabbitMQ ou MinIO para o host; publique esses servicos apenas atras da sua infraestrutura de rede/backup/observabilidade.