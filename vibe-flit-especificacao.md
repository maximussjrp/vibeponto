# Vibe Coding — Especificação Completa de Sistema de RH/DP (Tipo Flit)

Objetivo: Documentar minuciosamente um sistema complexo de gestão de ponto eletrônico, documentos trabalhistas com assinatura digital e benefícios flexíveis, com diferenciais de Vibe Coding (performance, segurança, IA antifraude, UX e integrações), pronto para implementação por equipes de produto/engenharia.

---

## 1. Proposta de Valor e Diferenciais (Vibe Coding)
- Auditoria antifraude com IA + liveness: detecção de fotos impressas/telas, face mismatch, replay, mascaramento, blur, e variações de luz.
- Geofencing avançado: múltiplos perímetros por pessoa/equipe, tolerância por janela temporal, exceções e auditoria de desvios.
- Offline-first com sincronização confiável: filas persistentes, reconciliação conflituosa, marcações assinadas no dispositivo (chaves por usuário).
- Segurança por padrão: criptografia em repouso e em trânsito; storage segregado; segregação multi-tenant; RBAC granular; MFA; logs imutáveis.
- Compliance: Portaria 671/MTE (AEJ/Espelho), LGPD (base legal, DPO), evidências de auditoria; suporte ICP-Brasil opcional.
- Integrações robustas: folha/ERP/eSocial via conectores, webhooks assíncronos, reprocessamento idempotente.
- UX consistente: modais bem definidos, estados, acessibilidade; aplicativos mobile/kiosk/web coesos.
- Observabilidade: métricas, tracing (OpenTelemetry), dashboards de SLA, relatórios de conformidade.

---

## 2. Arquitetura de Alto Nível
- Frontends: Web (Gestor/Admin/Colaborador), Mobile (Colaborador), Kiosk/Tablet (Flit Multi), Web Kiosk (Flit Web).
- Backends (serviços):
  - Auth & RBAC
  - Usuários & Times
  - Ponto (marcação, espelho, AEJ, escalas)
  - AuditorIA (detecção antifraude)
  - Geofence & Dispositivos
  - Documentos & Assinaturas (Youk-like)
  - Benefícios (carteiras/cartões/recargas) (Beneflit-like)
  - Integrações (folha/ERP/eSocial/WhatsApp)
  - Notificações & Webhooks
  - Relatórios & Compliance
- Infra: API Gateway, Service Mesh, Filas (Kafka/Rabbit), Storage (S3/Blob), DBs (PostgreSQL/Redis/Elastic), CDN, Secrets, Observabilidade.
- Multi-tenant: isolamento por `tenant_id`, chaves e storage segregados.

---

## 3. Modelo de Dados (Principais Entidades)
- `Tenant`: id, nome, CNPJ, contatos, config, chaves.
- `Usuario`: id, nome, email, telefone, cpf, matrícula, papel, status, equipe, foto base (template biométrico), credenciais.
- `Equipe`: id, nome, líderes, membros, perímetros padrão.
- `MarcacaoPonto`: id, usuario_id, tipo (foto/facial/qr/matricula/whatsapp/web), device_id, timestamp_local, timestamp_servidor, timezone, geoloc, perimetro_id, modo (online/offline), comprovante_id, flags (suspeita, auditoria).
- `Comprovante`: id, marcacao_id, hash, assinatura (local), status.
- `Perimetro`: id, usuario_id/equipe_id, nome, geojson/polígono, tolerâncias.
- `Dispositivo`: id, tipo (mobile/web/kiosk), plataforma, versao, token, ultimo_seen, status.
- `Escala`: id, usuario_id/equipe_id, regime (fixo/flex/12x36), janelas, pausas remuneradas, regras HE/Banco.
- `Auditoria`: id, marcacao_id, score, motivos, imagens analisadas, liveness, decisão (aprovada/reprovada/revisão).
- `Documento`: id, tipo (holerite/recibo/13º/férias/informe), periodo, usuario_id, arquivo, status assinatura.
- `Assinatura`: id, documento_id, usuario_id, método (e-sign/icp), status, trilha de evidências.
- `BeneficioCarteira`: id, usuario_id, tipo (VA/VR/auxilio/etc.), saldo, política.
- `Cartao`: id, usuario_id, emissor, número mascarado, status.
- `Recarga`: id, carteira_id, valor, taxa, status, lote.
- `IntegracaoFolha`: id, provedor, config, mapeamentos.
- `Webhook`: id, evento, url, segredo, tentativas, status, ultima_entrega.
- `Notificacao`: id, canal (email/push/sms/whatsapp), mensagem, destino, status.

---

## 4. Autenticação, Autorização e Segurança
- OIDC/OAuth2, JWT com escopos por papel; Refresh Tokens; MFA (TOTP/SMS/Push).
- RBAC: papéis (`admin_dp`, `gestor`, `colaborador`, `auditor`, `financeiro`).
- Segurança: TLS, HSTS, CSP, rate limiting, detecção anômala de login, device attestation.
- LGPD: bases legais, consentimento granular, DSR (acesso/exclusão/portabilidade), retenção configurável.

---

## 5. APIs e Rotas (REST) — Detalhadas

### 5.1 Auth & RBAC
- POST `/auth/login` — credenciais → tokens
  - body: `{ email, password, deviceInfo }`
  - 200: `{ access_token, refresh_token, user, scopes }`
  - 401/429
- POST `/auth/refresh` — troca refresh por novo access
- POST `/auth/logout` — invalida tokens ativos
- GET `/auth/me` — dados do usuário/logins
- GET `/rbac/roles` — lista papéis e permissões
- POST `/rbac/assign` — atribui papel a usuário

### 5.2 Usuários & Times
- GET `/users` (filtros: equipe, status)
- POST `/users` — criação (suporta import CSV)
- GET `/users/{id}` — perfil
- PATCH `/users/{id}` — atualização
- DELETE `/users/{id}` — desativação
- POST `/users/{id}/photo` — base biométrica
- GET `/teams` | POST `/teams` | PATCH `/teams/{id}` | DELETE `/teams/{id}`
- POST `/teams/{id}/members` — adicionar/remover

### 5.3 Ponto (Marcação, Espelho, AEJ)
- POST `/ponto/marcacoes`
  - body: `{ usuario_id, tipo, device_id, timestamp_local, geoloc?, foto_base64?, qr_data?, matricula?, modo, evidencias: { liveness?: {frames}, deviceIntegrity?: {...}} }`
  - 201: `{ id, status: "pendente|processado|suspeita", comprovante_id }`
  - Valida: perímetro, duplicidade de janela, ordem (entrada/pausa/retorno/saída), offline queue.
- GET `/ponto/marcacoes`
  - filtros: usuario, equipe, periodo, status, suspeita.
- GET `/ponto/marcacoes/{id}` — detalhes + auditoria
- POST `/ponto/marcacoes/{id}/corrigir`
  - body: `{ motivo, novo_horario, anexos[] }` → fluxo de aprovação.
- GET `/ponto/espelho`
  - query: `{ usuario_id, periodo }` → PDF/HTML + JSON.
- GET `/ponto/aej`
  - query: `{ periodo }` → arquivo conforme Portaria 671.
- POST `/ponto/escalas` | PATCH `/ponto/escalas/{id}` | GET `/ponto/escalas`
- GET `/ponto/comprovantes/{id}` — download.

### 5.4 AuditorIA (Antifraude)
- POST `/auditoria/analise`
  - body: `{ marcacao_id, imagem, deviceInfo, geoloc }`
  - 200: `{ score, motivos[], liveness: {passed, hints}, decisao: "aprovada|reprovada|revisao" }`
- GET `/auditoria/marcacoes/{id}` — resultado da auditoria
- POST `/auditoria/marcacoes/{id}/revisao` — revisão humana
- GET `/auditoria/estatisticas` — métricas (por período/tenant)

### 5.5 Geofence & Dispositivos
- POST `/geofence/perimetros` — cria polígono (GeoJSON), tolerâncias
- GET `/geofence/perimetros` | PATCH `/geofence/perimetros/{id}` | DELETE
- POST `/devices/register` — registra kiosk/mobile (attestation + token)
- GET `/devices` — inventário; saúde (versões, último check-in)

### 5.6 Documentos & Assinaturas (Youk)
- POST `/documentos` — upload (tipo/periodo/usuario)
- GET `/documentos` — filtros por tipo/periodo/status
- GET `/documentos/{id}` — metadados + arquivo
- POST `/documentos/{id}/assinar`
  - body: `{ metodo: "esign|icp", motivo?, local?, evidencias? }`
  - 200: `{ assinatura_id, status }`
- GET `/assinaturas/{id}` — trilha de evidências (IP, device, timestamp, hash)
- POST `/documentos/lotes` — envio massivo (holerites/recibos)

### 5.7 Benefícios (Carteiras/Cartões/Recargas)
- POST `/beneficios/carteiras` — cria carteira por usuário
- GET `/beneficios/carteiras` | GET `/beneficios/carteiras/{id}`
- POST `/beneficios/recargas` — recarga (lote), opções de taxas
- GET `/beneficios/recargas/{id}` — status
- POST `/beneficios/cartoes` — emissão; GET `/beneficios/cartoes`
- GET `/beneficios/transacoes` — extratos; exportação
- POST `/beneficios/politicas` — regras de uso (categorias, limites, janelas)

### 5.8 Integrações
- Folha/ERP/eSocial:
  - GET `/integracoes/folha/providers`
  - POST `/integracoes/folha/config` (credenciais/mapeamentos)
  - POST `/integracoes/folha/export` — exporta horas/absenças/espelhos
- WhatsApp (API oficial):
  - POST `/integracoes/whatsapp/sessions`
  - POST `/integracoes/whatsapp/send` (templates)
  - POST `/integracoes/whatsapp/webhook` — recepção de mídia/localização/confirm.
- Webhooks:
  - POST `/webhooks` — registra; GET `/webhooks`
  - Eventos: `ponto.marcado`, `ponto.suspeita`, `documento.assinado`, `beneficio.recarga.concluida`, `integracao.folha.exportado`.

### 5.9 Notificações
- POST `/notificacoes` — cria notificação
- GET `/notificacoes` — status/filtros
- Canais: Email, Push, SMS, WhatsApp.

### 5.10 Relatórios & Compliance
- GET `/relatorios/ponto`
- GET `/relatorios/auditoria`
- GET `/relatorios/documentos`
- GET `/compliance/lgpd/dsr` — solicitações
- GET `/compliance/portaria671/indicadores`

---

## 6. UI — Modais, Telas e Fluxos

### 6.1 Colaborador — App Mobile
- Modal: Registro de Ponto (selfie)
  - Estados: preparação → câmera → liveness (instruções: piscar/virar rosto) → confirmação → envio.
  - Erros: face não detectada, liveness falhou, fora do perímetro, offline (entra fila), duplicidade de janela.
- Modal: Compartilhar Localização (permite/nega)
- Modal: Correção de Marcação
  - Campos: seleção da marcação, novo horário, motivo, anexos; envia para aprovação.
- Tela: Espelho de Ponto (visualização e download)
- Tela: Documentos (holerites, recibos) com Modal de Assinatura (e-sign)
- Tela: Benefícios (carteiras/saldos/transações)

### 6.2 Kiosk/Tablet (Flit Multi)
- Modal: Escolher método (QR/matrícula/foto)
- Tela: Captura Facial com Liveness simplificado
- Modal: Resultado (sucesso/suspeita)
- Tela: Modo offline com contador de itens em fila

### 6.3 Web (Flit Web) — Colaborador/Grupal
- Modal: Marcação em grupo (seleção de colaboradores, captura sequencial)
- Modal: Importação via lista (para grupos fixos)

### 6.4 Gestor/Admin — Painel Web
- Tela: Dashboard (KPIs: faltas, HE, suspeitas, perímetros violados)
- Modal: Aprovação de Correções (lista, detalhes, evidências)
- Modal: Configuração de Perímetros (mapa, polígonos, tolerâncias)
- Modal: Upload de Documentos (lote; mapeamento de período)
- Modal: Assinatura em massa (com delegação/ordem de assinatura)
- Modal: Configurações de Benefícios (políticas, recargas, lotes)
- Modal: Integrações (folha/ERP/WhatsApp; testes de conexão)
- Modal: Webhooks (URLs, segredo, teste de entrega)
- Modal: Dispositivos (registro, revogação, health check)
- Tela: AuditorIA (fila de revisões; modal de decisão com evidências e histórico)
- Tela: Relatórios (filtros avançados; exportar CSV/PDF)

---

## 7. Fluxos Críticos
- Registro via WhatsApp: sessão → solicitação de localização → selfie → validação → confirmação → comprovante.
- Offline Sync: marcação assinada localmente → fila persistente → backoff exponencial → reconciliação → conflito (gera tarefa para gestor).
- Correção de Marcação: colaborador solicita → gestor revisa → aprova/reprova → atualiza espelho/aej.
- Assinatura de Holerite: upload → notifica colaborador → assina (e-sign/icp) → trilha de evidências → disponibiliza.
- Recarga Benefícios: lote → valida regras → chama emissor → atualiza saldos → notifica.
- Export Folha: seleciona período → gera bundle (JSON/CSV/PDF) → entrega → webhook de sucesso/falha.

---

## 8. Regras de Negócio (exemplos)
- Janela de marcação: bloqueio de duplicidade (ex.: duas entradas consecutivas).
- HE/Banco: cálculo segundo escala e políticas; aprovações necessárias.
- Perímetros: até 5 por colaborador; tolerância de raio; exceções com justificativa.
- AuditorIA: score mínimo para auto-aprovação; abaixo disso → revisão; thresholds por tenant.
- LGPD: retenção documentos (ex.: 5 anos), registros de consentimento, minimização de dados em exportações.

---

## 9. Erros e Códigos
- 400 (validação), 401 (auth), 403 (permissão), 404 (não encontrado), 409 (conflito), 422 (semântica), 429 (rate), 500/503 (infra).
- Payload de erro padrão: `{ code, message, details?, correlation_id }`

---

## 10. Integrações (Detalhes)
- Folha/ERP: conectores (ex.: TOTVS, Senior, Ahgora, Secullum, Domínio); mapeamentos de campos; retries; DLQ.
- WhatsApp: provedor oficial; templates; callbacks; rate limits.
- Benefícios: emissores (cartões), reconciliação de transações; antifraude de uso fora de categoria.

---

## 11. Observabilidade e Compliance
- Logs imutáveis com trilha (quem/onde/quando), especialmente para alterações de ponto e assinatura.
- Métricas: latência, sucesso, fila offline, taxa de suspeitas, tempo de revisão.
- Tracing distribuído; dashboards de conformidade (Portaria 671) e LGPD (DSR status).

---

## 12. Segurança Técnica
- Criptografia: AES-256 em repouso, TLS1.2+ em trânsito.
- Segredos: KMS/KeyVault; rotação periódica; escopo por tenant.
- Device attestation: verificação de integridade; versões mínimas (iOS 14+/Android 10+).
- Proteção de mídia sensível: expiração de URLs, redactions em logs.

---

## 13. Escalabilidade e Deploy
- Containers (K8s), auto-scaling, rollouts canários; CDN para assets.
- Filas para análises de IA e processamento de lotes.
- Sharding por tenant de alto volume.

---

## 14. Roadmap (MVP → Plus)
- MVP (12 semanas):
  - Ponto: marcação mobile/web, perímetros, espelho, AEJ; AuditorIA básico; correções; integrações folha (1-2 provedores); WhatsApp; documentos (holerite e e-sign); notificações; relatórios iniciais.
- Plus: ICP-Brasil, liveness avançado, Benefícios completos, conectores adicionais, dashboards compliance, SSO/IdP corporativo.

---

## 15. Anexos (Esquemas Simplificados)
- Exemplos de payloads:
  - Marcação: `{ usuario_id, tipo: "facial", timestamp_local: "2026-01-22T08:15:00-03:00", geoloc: { lat, lng, accuracy }, evidencias: { liveness: { passed: true, frames_hash }, deviceIntegrity: { rooted: false } } }`
  - AuditorIA: `{ marcacao_id, score: 0.87, motivos: ["face_mismatch_low"], decisao: "revisao" }`
  - Documento assinatura: `{ documento_id, metodo: "esign", evidencias: { ip, user_agent, geoloc? }, hash }`
  - Recarga: `{ carteira_id, valor: 150.00, lote_ref, regras: { categorias_permitidas: ["alimentacao"], limite_diario: 50 } }`

---

Notas finais: Esta especificação é uma base para implementação. Detalhes de provedores, mapeamentos e requisitos legais específicos (ex.: formatos AEJ/Espelho, ICP-Brasil) devem ser validados com assessoria jurídica e documentação oficial de cada integração.

---

## 16. Armazenamento e Bancos de Dados

### 16.1 Visão Geral de Stack
- Core relacional: PostgreSQL (ACID, robusto, extensões). Multi-tenant por `tenant_id` e partições por período.
- Geoespacial: PostGIS (geometrias, índices espaciais para perímetros e geolocalização de marcações).
- Time-series: TimescaleDB (extensão do PostgreSQL) OU partições nativas por mês para `MarcacaoPonto`.
- Busca/Logs: OpenSearch/Elasticsearch (indexação de auditorias, trilhas e consultas textuais/analíticas).
- Cache/Sessões/Filas leves: Redis (rate limit, locks distribuídos, cache de RBAC, filas simples).
- Mensageria: RabbitMQ (local e simples) ou Kafka (alto throughput; usar em produção). Para desenvolvimento local, RabbitMQ é recomendado.
- Blobs: S3 compatível (MinIO) para armazenar mídia sensível (selfies, comprovantes, PDFs) com URLs temporárias.

### 16.2 Mapeamento por Serviço
- Auth & RBAC: PostgreSQL (tabelas de usuários/papéis/permissões), Redis (tokens/blacklist/nonce), OpenSearch (logs de acesso).
- Ponto: PostgreSQL/TimescaleDB (marcações, escalas, espelhos, AEJ); PostGIS (perímetros e validações espaciais).
- AuditorIA: Metadados em PostgreSQL; resultados/razões indexados em OpenSearch; mídia em MinIO.
- Documentos & Assinaturas: PostgreSQL (metadados) + MinIO (arquivos); OpenSearch para trilha de evidências.
- Benefícios: PostgreSQL (carteiras/cartões/recargas), Redis (saldos cache), OpenSearch (transações para buscas).
- Integrações/Notificações/Webhooks: PostgreSQL (config/entregas), RabbitMQ (filas), OpenSearch (logs de entrega).

### 16.3 Estratégia de Particionamento e Retenção
- `MarcacaoPonto`: partições por mês e por `tenant_id` (particionamento por range/Lista). Ex.: `ponto_marcacoes_{tenant}_{YYYYMM}`.
- Índices por colunas de consulta frequente: `(usuario_id, timestamp_servidor)`, `status`, `suspeita`, `equipe_id`.
- Espaço geográfico: coluna `geom POINT` com SRID apropriado (ex.: 4326), índice espacial `GIST`.
- Retenção:
  - Marcações: manter completas pelo período legal (consultar Portaria 671 e práticas internas; p.ex. 5 anos).
  - Trilhas de auditoria: 24-36 meses online; arquivar em S3 (MinIO) em CSV/Parquet.
  - Logs de acesso: 12 meses; anonimizar campos sensíveis.

### 16.4 Índices e Constraints (Exemplos)
- Unicidade: impedir duplicidade de eventos (ex.: duas entradas consecutivas sem saída) via regra de negócio + constraint parcial conforme contexto.
- Exemplo de índices (PostgreSQL):
  - `CREATE INDEX ix_marcacoes_usuario_ts ON marcacoes (usuario_id, timestamp_servidor DESC);`
  - `CREATE INDEX ix_marcacoes_status ON marcacoes (status);`
  - `CREATE INDEX ix_marcacoes_suspeita ON marcacoes (suspeita);`
  - `CREATE INDEX ix_marcacoes_geom ON marcacoes USING GIST (geom);`
- JSONB (metadados): usar índices GIN em campos com consultas frequentes (ex.: `evidencias`): `CREATE INDEX ix_marcacoes_evidencias_gin ON marcacoes USING GIN (evidencias);`

### 16.5 Armazenamento Offline (Dispositivo)
- Mobile: SQLite (armazenamento local de marcações em fila, comprovantes e metadados mínimos), criptografado (ex.: SQLCipher quando possível).
- Assinatura local: chave privada do usuário (provisionada pelo app; protegida no keystore/Keychain); hash do evento + metadados.
- Estratégia de sincronização: filas persistentes; backoff exponencial; reconciliação e detecção de conflitos com geração de tarefa para gestor.

### 16.6 Governança de Dados (LGPD)
- Minimização: armazenar o mínimo necessário em índices de busca; ofuscar/hashear identificadores onde possível.
- Pseudonimização: separar tabelas sensíveis (biometria) em storage isolado; acesso apenas por serviços autorizados.
- Direitos do titular: endpoints para extração, exclusão e portabilidade; trilhas auditáveis das ações.

---

## 17. Ambiente Local de Testes (Windows)

### 17.1 Requisitos
- Docker Desktop com WSL2 habilitado
- `git`, `make` (opcional), e Powershell

### 17.2 Docker Compose (stack leve)
Arquivo `docker-compose.yml` (pode ser gerado ao lado deste documento): PostgreSQL + PostGIS, Redis, MinIO, RabbitMQ.

```yaml
version: "3.9"
services:
  postgres:
    image: postgis/postgis:15-3.4
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: vibe
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio:/data
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
volumes:
  pgdata:
  minio:
```

### 17.3 Comandos (Powershell)
```powershell
# Subir stack
docker compose up -d

# Acessar Postgres
docker exec -it $(docker ps -qf "ancestor=postgis/postgis:15-3.4") psql -U dev -d vibe

# Criar extensão PostGIS/Timescale (no psql)
-- dentro do psql
CREATE EXTENSION IF NOT EXISTS postgis;
-- opcional:
-- CREATE EXTENSION IF NOT EXISTS timescaledb;

# Acessar MinIO console (http://localhost:9001) com minio/minio123
# Acessar RabbitMQ console (http://localhost:15672) guest/guest
```

### 17.4 Stack completo (opcional)
- Adicionar OpenSearch (pesado) para buscas/auditoria; útil em testes integrados.
- Kafka/Zookeeper para alto throughput (substitui RabbitMQ em cenários avançados).

### 17.5 Alternativas de Banco Local
- SQLite: ideal para testes rápidos e unitários; substituir PostgreSQL no repositório via drivers/ORM (ex.: SQLAlchemy) e executar migrações simplificadas.
- Local PostgreSQL sem Docker: instalar via instalador oficial e criar DB/usuário.

---

## 18. Migrations, Fixtures e Testes

### 18.1 ORM e Migrations
- ORM sugerido: SQLAlchemy/Prisma/TypeORM (conforme stack de linguagem).
- Migrations: Alembic (Python) com versionamento; scripts para criar extensões (PostGIS/Timescale) por ambiente.

### 18.2 Testes Automatizados
- Unitários: isolam domínios (ponto, auditoria, documentos, benefícios); usar SQLite/in-memory quando aplicável.
- Integração: Testcontainers (Postgres/Redis/MinIO/RabbitMQ) para subir serviços efêmeros por suíte.
- Fixures/Seeds: gerar usuários/equipes/perímetros e lote de marcações (incluindo casos suspeitos) para validar auditoria/relatórios.
- Mock/Simulação: WhatsApp API, emissores de cartão; usar servidores de mock com contratos.

### 18.3 Dados de Exemplo
- Gerar marcações com distribuição realista (entrada/pausa/retorno/saída, atrasos, HE), com `geom` variando dentro/fora de perímetro.
- Criar documentos (holerites) e assinaturas com evidências simuladas.
- Simular recargas e transações de benefícios com regras de uso.

---

## 19. Performance Tuning (Inicial)
- Pooling de conexões (PgBouncer em produção; tuning local via parâmetros).
- Índices cobrindo filtros críticos; análise com `EXPLAIN ANALYZE` para rotas mais usadas.
- Partições e vacuum autogerenciado em tabelas de alto volume (marcações).
- Redis para cachear agregações de dashboard (KPIs) por janelas.

---

## 20. Backup/Restore e Governança Local
- PostgreSQL: `pg_dump` para backup; restores frequentes em ambiente de QA.
- MinIO: versionamento de objetos e ciclo de vida (expiração) configurável.
- RabbitMQ: export de definições; não usar para armazenamento de long-term.
- Anonimização: rotinas para mascarar dados pessoais em dumps usados em testes.

