# 📊 VibePonto - Sistema de Ponto Eletrônico

Sistema completo de ponto eletrônico com benefícios flexíveis, desenvolvido para conformidade com a Portaria 671/MTE e LGPD.

## 🏗️ Arquitetura do Sistema

```
Bateponto/
├── backend/                 # API FastAPI (Python 3.11+)
├── frontend/               # Aplicação Next.js 14 (React)
├── mobile/                 # App Flutter (em desenvolvimento)
├── scripts/                # Scripts de manutenção
├── docker-compose.yml      # Orquestração de containers
└── README.md               # Este arquivo
```

---

## 🚀 Quick Start

### Pré-requisitos
- Docker e Docker Compose
- Node.js 18+ (para desenvolvimento local)
- Python 3.11+ (para desenvolvimento local)

### Executar com Docker

```bash
# Clonar e iniciar
docker-compose up -d

# Verificar status
docker-compose ps

# Acessar
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Credenciais de Teste
```
Email: maximussjrp@hotmail.com
Senha: Admin@123
Papel: admin_dp (Administrador)
```

---

## 📁 Estrutura do Backend

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py              # Dependências (auth, tenant, db)
│   │   └── routes/              # Rotas da API
│   │       ├── auth.py          # Autenticação (login, refresh, MFA)
│   │       ├── beneficios.py    # Benefícios (VA/VR/VT, cartões)
│   │       ├── dashboard.py     # Dashboard e métricas
│   │       ├── documentos.py    # Upload e assinatura de docs
│   │       ├── equipes.py       # CRUD de equipes
│   │       ├── escalas.py       # Escalas de trabalho
│   │       ├── espelho.py       # Espelho de ponto
│   │       ├── geo.py           # Geolocalização e perímetros
│   │       ├── ponto.py         # Marcações de ponto
│   │       ├── tenant.py        # Empresa e configurações
│   │       └── usuarios.py      # CRUD de usuários
│   ├── core/
│   │   ├── config.py            # Configurações (Settings)
│   │   ├── database.py          # Conexão PostgreSQL async
│   │   └── security.py          # JWT, bcrypt, tokens
│   ├── models/
│   │   └── models.py            # SQLAlchemy models
│   ├── schemas/
│   │   ├── auth.py              # Schemas de autenticação
│   │   ├── base.py              # Schemas base
│   │   ├── geo.py               # Schemas de geolocalização
│   │   └── ponto.py             # Schemas de marcação
│   ├── services/
│   │   ├── assinatura_digital.py  # Assinatura ICP-Brasil
│   │   ├── auditoria.py         # Serviço de auditoria
│   │   ├── exportacao_aej.py    # Exportação AEJ/AFD
│   │   ├── facial_recognition.py # Reconhecimento facial
│   │   ├── geo.py               # Cálculos geográficos
│   │   ├── lgpd.py              # Conformidade LGPD
│   │   ├── pdf.py               # Geração de PDFs
│   │   └── storage.py           # MinIO/S3 storage
│   ├── tasks/                   # Tarefas assíncronas (Celery)
│   ├── main.py                  # Aplicação FastAPI
│   └── worker.py                # Worker Celery
├── tests/
│   ├── conftest.py              # Fixtures de teste
│   └── test_api.py              # Testes de API
├── scripts/
│   ├── seed_admin.py            # Criar usuário admin
│   ├── seed_demo_data.py        # Dados de demonstração
│   └── test_flow.py             # Testar fluxo completo
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

### Rotas da API

| Rota | Método | Descrição |
|------|--------|-----------|
| `/api/v1/auth/login` | POST | Login com email/senha |
| `/api/v1/auth/refresh` | POST | Renovar access token |
| `/api/v1/auth/me` | GET | Dados do usuário logado |
| `/api/v1/usuarios` | GET/POST | CRUD usuários |
| `/api/v1/equipes` | GET/POST | CRUD equipes |
| `/api/v1/escalas` | GET/POST | CRUD escalas |
| `/api/v1/ponto/registrar` | POST | Registrar marcação |
| `/api/v1/ponto/marcacoes` | GET | Listar marcações |
| `/api/v1/espelho` | GET | Espelho de ponto |
| `/api/v1/geo/perimetros` | GET/POST | CRUD perímetros |
| `/api/v1/tenant` | GET/PATCH | Dados da empresa |
| `/api/v1/configuracoes/*` | GET/PATCH | Configurações |
| `/api/v1/dashboard/stats` | GET | Estatísticas |

---

## 📁 Estrutura do Frontend

```
frontend/
├── public/
│   ├── manifest.json            # PWA manifest
│   └── sw.js                    # Service Worker
├── src/
│   ├── app/
│   │   ├── (dashboard)/
│   │   │   └── dashboard/
│   │   │       ├── auditoria/   # Logs de auditoria
│   │   │       ├── beneficios/  # Gestão de benefícios
│   │   │       ├── configuracoes/ # Preferências
│   │   │       ├── documentos/  # Upload de docs
│   │   │       ├── empresa/     # Dados da empresa
│   │   │       ├── equipes/     # CRUD equipes
│   │   │       ├── escalas/     # Escalas de trabalho
│   │   │       ├── espelho/     # Espelho de ponto
│   │   │       ├── exportacao/  # Exportação AEJ/AFD
│   │   │       ├── locais/      # Locais de trabalho
│   │   │       ├── perimetros/  # Desenho de perímetros
│   │   │       ├── perfil/      # Perfil do usuário
│   │   │       ├── ponto/       # Histórico de ponto
│   │   │       ├── registrar-ponto/ # Registro de ponto
│   │   │       ├── usuarios/    # CRUD colaboradores
│   │   │       ├── layout.tsx   # Layout do dashboard
│   │   │       └── page.tsx     # Dashboard principal
│   │   ├── esqueci-senha/       # Recuperação de senha
│   │   ├── login/               # Tela de login
│   │   ├── offline/             # Página offline (PWA)
│   │   ├── redefinir-senha/     # Redefinir senha
│   │   ├── registro/            # Cadastro de empresa
│   │   ├── globals.css          # Estilos globais
│   │   ├── layout.tsx           # Layout raiz
│   │   └── providers.tsx        # Context providers
│   ├── components/
│   │   ├── ui/                  # Componentes shadcn/ui
│   │   │   ├── alert-dialog.tsx
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── switch.tsx
│   │   │   ├── table.tsx
│   │   │   └── ...
│   │   └── AssinaturaDigital.tsx # Assinatura ICP-Brasil
│   ├── hooks/
│   │   ├── useAuth.ts           # Hook de autenticação
│   │   └── useOfflineSync.ts    # Hook PWA/offline
│   ├── lib/
│   │   ├── api.ts               # Cliente Axios
│   │   ├── permissions.ts       # Sistema de permissões
│   │   └── utils.ts             # Utilitários
│   ├── services/
│   │   ├── auth.ts              # Serviço de auth
│   │   ├── empresa.ts           # Serviço de empresa
│   │   ├── equipes.ts           # Serviço de equipes
│   │   ├── index.ts             # Exports
│   │   ├── ponto.ts             # Serviço de ponto
│   │   └── usuarios.ts          # Serviço de usuários
│   └── __tests__/               # Testes (Vitest)
├── Dockerfile
├── next.config.js
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vitest.config.ts
```

### Sistema de Permissões

| Papel | Acesso |
|-------|--------|
| `admin_dp` | Acesso total a todos os módulos |
| `gestor` | Gerencia equipe, aprova pontos, relatórios |
| `auditor` | Visualização e auditoria |
| `financeiro` | Benefícios e relatórios financeiros |
| `colaborador` | Apenas seu próprio ponto e espelho |

### Módulos Disponíveis
- dashboard
- registrar_ponto
- colaboradores
- equipes
- escalas
- locais
- perimetros
- ponto
- espelho
- exportacao
- auditoria
- documentos
- beneficios
- empresa
- configuracoes

---

## 🗄️ Banco de Dados

### Principais Tabelas

| Tabela | Descrição |
|--------|-----------|
| `tenants` | Empresas (multi-tenant) |
| `usuarios` | Usuários do sistema |
| `equipes` | Equipes/departamentos |
| `escalas` | Escalas de trabalho |
| `perimetros` | Perímetros geográficos |
| `marcacoes_ponto` | Registros de ponto |
| `documentos` | Arquivos e contratos |
| `carteiras_beneficio` | Saldos VA/VR/VT |
| `transacoes` | Movimentações de benefícios |
| `audit_logs` | Logs de auditoria |

### Enums Importantes (lowercase)
- `tipo`: manual, facial, nfc, qrcode, foto, app, web
- `evento`: entrada, saida, intervalo_inicio, intervalo_fim
- `status`: pendente, aprovado, rejeitado, ajustado

---

## 🐳 Containers Docker

| Container | Porta | Descrição |
|-----------|-------|-----------|
| vibeponto-api | 8000 | API FastAPI |
| vibeponto-frontend | 3000 | Next.js |
| vibeponto-postgres | 5432 | PostgreSQL + PostGIS |
| vibeponto-redis | 6379 | Cache e filas |
| vibeponto-minio | 9000/9001 | Object storage |

### Comandos Úteis

```bash
# Ver logs
docker logs vibeponto-api -f
docker logs vibeponto-frontend -f

# Acessar container
docker exec -it vibeponto-api bash
docker exec -it vibeponto-postgres psql -U vibeponto -d vibeponto

# Reiniciar serviço
docker restart vibeponto-api
docker restart vibeponto-frontend

# Copiar arquivo para container
docker cp arquivo.py vibeponto-api:/app/arquivo.py
```

---

## 🧪 Testes

### Backend (pytest)
```bash
cd backend
pytest -v
pytest tests/test_api.py -v
```

### Frontend (vitest)
```bash
cd frontend
npm test
npm run test:watch
```

---

## 📋 Funcionalidades Principais

### ✅ Implementado
- [x] Login/Logout com JWT
- [x] Refresh Token automático
- [x] Multi-tenant (isolamento por empresa)
- [x] CRUD de Usuários
- [x] CRUD de Equipes
- [x] CRUD de Escalas
- [x] Registro de Ponto (foto, geolocalização)
- [x] Espelho de Ponto
- [x] Dashboard com métricas
- [x] Sistema de Permissões
- [x] Auditoria de ações
- [x] Configurações da empresa
- [x] PWA / Modo Offline
- [x] Exportação AEJ (Portaria 671)
- [x] Interface de Assinatura Digital
- [x] Desenho de Perímetros no mapa

### 🔜 Roadmap
- [ ] Reconhecimento Facial (treinamento de modelo)
- [ ] App Mobile (Flutter)
- [ ] Benefícios Flexíveis completo
- [ ] Integração com folha de pagamento
- [ ] Notificações push
- [ ] Relatórios avançados

---

## 🔒 Segurança

- Senhas com bcrypt (12 rounds)
- JWT com expiração curta (30 min)
- Refresh tokens rotativos
- CORS configurado
- Rate limiting
- Audit logs
- Conformidade LGPD

---

## 📞 Suporte

- Documentação API: http://localhost:8000/docs
- Código fonte: Este repositório
- Problemas: Abrir issue no GitHub

---

## 📝 Licença

Proprietário - Todos os direitos reservados
