# 🚀 Guia de Deploy - VibePonto

Este guia cobre o deploy do VibePonto em ambiente de produção.

---

## 📋 Checklist Pré-Deploy

### Segurança
- [ ] Alterar `SECRET_KEY` para valor único e forte (32+ caracteres)
- [ ] Alterar senhas do banco de dados
- [ ] Configurar HTTPS/SSL
- [ ] Configurar CORS para domínio de produção
- [ ] Habilitar rate limiting
- [ ] Remover `DEBUG=True`

### Infraestrutura
- [ ] Servidor com mínimo 2 vCPU, 4GB RAM
- [ ] PostgreSQL 15+ com PostGIS
- [ ] Redis 7+
- [ ] Armazenamento S3/MinIO para arquivos
- [ ] Domínio configurado (DNS A/CNAME)

---

## 🏗️ Opções de Deploy

### Opção 1: VPS com Docker Compose (Recomendado para início)

#### Servidores Recomendados
- **DigitalOcean**: Droplet $24/mês (2 vCPU, 4GB)
- **Hetzner**: CX21 €6.90/mês (2 vCPU, 4GB)
- **Vultr**: $24/mês (2 vCPU, 4GB)
- **Linode**: Linode 4GB $24/mês

#### Passo a Passo

```bash
# 1. Conectar no servidor
ssh root@seu-servidor.com

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin

# 3. Clonar repositório
git clone https://seu-repo.git /opt/vibeponto
cd /opt/vibeponto

# 4. Criar arquivo .env de produção
cp .env.example .env
nano .env
```

#### Configurar .env de Produção

```env
# Ambiente
ENVIRONMENT=production
DEBUG=false

# Banco de Dados
POSTGRES_USER=vibeponto_prod
POSTGRES_PASSWORD=SuaSenhaForte123!@#
POSTGRES_DB=vibeponto_prod
DATABASE_URL=postgresql+asyncpg://vibeponto_prod:SuaSenhaForte123!@#@postgres:5432/vibeponto_prod

# Segurança
SECRET_KEY=sua-chave-secreta-muito-forte-com-pelo-menos-32-caracteres
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS (seu domínio)
CORS_ORIGINS=https://ponto.suaempresa.com.br

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO/S3
MINIO_ROOT_USER=minio_prod
MINIO_ROOT_PASSWORD=SuaSenhaMinio123!
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=vibeponto-prod

# Email (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-app-password

# Sentry (opcional)
SENTRY_DSN=https://xxx@sentry.io/xxx

# Frontend
NEXT_PUBLIC_API_URL=https://api.ponto.suaempresa.com.br/api/v1
```

#### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  api:
    build: ./backend
    container_name: vibeponto-api
    restart: always
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - postgres
      - redis
    networks:
      - vibeponto-network

  frontend:
    build: ./frontend
    container_name: vibeponto-frontend
    restart: always
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
    depends_on:
      - api
    networks:
      - vibeponto-network

  postgres:
    image: postgis/postgis:15-3.3
    container_name: vibeponto-postgres
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    networks:
      - vibeponto-network

  redis:
    image: redis:7-alpine
    container_name: vibeponto-redis
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - vibeponto-network

  minio:
    image: minio/minio:latest
    container_name: vibeponto-minio
    restart: always
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    environment:
      - MINIO_ROOT_USER=${MINIO_ROOT_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
    networks:
      - vibeponto-network

  nginx:
    image: nginx:alpine
    container_name: vibeponto-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - certbot_data:/var/www/certbot
    depends_on:
      - api
      - frontend
    networks:
      - vibeponto-network

volumes:
  postgres_data:
  redis_data:
  minio_data:
  certbot_data:

networks:
  vibeponto-network:
    driver: bridge
```

#### Nginx Config (nginx/nginx.conf)

```nginx
events {
    worker_connections 1024;
}

http {
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    upstream api {
        server api:8000;
    }

    upstream frontend {
        server frontend:3000;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name ponto.suaempresa.com.br api.ponto.suaempresa.com.br;
        return 301 https://$server_name$request_uri;
    }

    # API Server
    server {
        listen 443 ssl http2;
        server_name api.ponto.suaempresa.com.br;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        location / {
            limit_req zone=api burst=20 nodelay;
            
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /api/v1/auth/login {
            limit_req zone=login burst=5 nodelay;
            
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    # Frontend Server
    server {
        listen 443 ssl http2;
        server_name ponto.suaempresa.com.br;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

#### Iniciar Produção

```bash
# 5. Criar diretórios
mkdir -p nginx/ssl

# 6. Obter certificado SSL (Let's Encrypt)
apt install certbot
certbot certonly --standalone -d ponto.suaempresa.com.br -d api.ponto.suaempresa.com.br
cp /etc/letsencrypt/live/ponto.suaempresa.com.br/*.pem nginx/ssl/

# 7. Iniciar containers
docker compose -f docker-compose.prod.yml up -d

# 8. Verificar logs
docker logs vibeponto-api -f

# 9. Criar admin inicial
docker exec -it vibeponto-api python scripts/seed_admin.py
```

---

### Opção 2: Cloud Gerenciado (AWS/GCP/Azure)

#### AWS (Elastic Container Service)

```
Arquitetura:
- ECS Fargate (API + Frontend)
- RDS PostgreSQL
- ElastiCache Redis
- S3 para arquivos
- CloudFront CDN
- ACM para SSL
- Route 53 DNS
```

Custo estimado: $100-200/mês (mínimo)

#### Google Cloud (Cloud Run)

```
Arquitetura:
- Cloud Run (API + Frontend)
- Cloud SQL PostgreSQL
- Memorystore Redis
- Cloud Storage
- Cloud CDN
- Cloud Armor (WAF)
```

Custo estimado: $80-150/mês (mínimo)

---

### Opção 3: Plataformas PaaS

#### Railway.app (Mais simples)
1. Conectar repositório GitHub
2. Configurar variáveis de ambiente
3. Deploy automático

Custo: $20-50/mês

#### Render.com
Similar ao Railway, com bom tier gratuito para testes.

---

## 🔄 CI/CD com GitHub Actions

### .github/workflows/deploy.yml

```yaml
name: Deploy Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          
      - name: Run tests
        run: |
          cd backend
          pytest -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to server
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /opt/vibeponto
            git pull origin main
            docker compose -f docker-compose.prod.yml build
            docker compose -f docker-compose.prod.yml up -d
```

---

## 📊 Monitoramento

### Logs
```bash
# Ver logs em tempo real
docker logs vibeponto-api -f --tail 100

# Logs do nginx
docker logs vibeponto-nginx -f
```

### Métricas (Opcional)

Adicionar Prometheus + Grafana:

```yaml
# Adicionar ao docker-compose.prod.yml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3001:3000"
```

---

## 🔐 Backup

### Script de Backup (backup.sh)

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/opt/backups

# Backup PostgreSQL
docker exec vibeponto-postgres pg_dump -U vibeponto_prod vibeponto_prod > $BACKUP_DIR/db_$DATE.sql
gzip $BACKUP_DIR/db_$DATE.sql

# Backup MinIO
docker exec vibeponto-minio mc mirror /data $BACKUP_DIR/minio_$DATE

# Limpar backups antigos (manter 7 dias)
find $BACKUP_DIR -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Cron para backup diário
```bash
crontab -e
# Adicionar:
0 2 * * * /opt/vibeponto/backup.sh >> /var/log/backup.log 2>&1
```

---

## 🆘 Troubleshooting

### API não inicia
```bash
# Ver logs detalhados
docker logs vibeponto-api --tail 100

# Verificar conexão com banco
docker exec -it vibeponto-api python -c "from app.core.database import engine; print('OK')"
```

### Erro de conexão banco
```bash
# Verificar se postgres está rodando
docker exec -it vibeponto-postgres pg_isready

# Verificar conexão
docker exec -it vibeponto-postgres psql -U vibeponto_prod -c "SELECT 1"
```

### Frontend não carrega
```bash
# Verificar build
docker logs vibeponto-frontend

# Rebuild
docker compose build frontend --no-cache
docker compose up -d frontend
```

### SSL/Certificado expirado
```bash
# Renovar Let's Encrypt
certbot renew
docker restart vibeponto-nginx
```

---

## 📝 Manutenção

### Atualizar sistema
```bash
cd /opt/vibeponto
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### Limpar recursos Docker
```bash
docker system prune -a --volumes
```

### Verificar uso de disco
```bash
df -h
docker system df
```

---

## 💰 Custos Estimados

| Componente | Opção Econômica | Produção |
|------------|-----------------|----------|
| VPS | $24/mês | $48/mês |
| PostgreSQL Gerenciado | - | $25/mês |
| Redis Gerenciado | - | $15/mês |
| S3/Storage | $5/mês | $10/mês |
| Domínio | $15/ano | $15/ano |
| SSL | Grátis (Let's Encrypt) | Grátis |
| **Total** | **~$30/mês** | **~$100/mês** |

---

## 📞 Suporte

Em caso de problemas:
1. Verificar logs: `docker logs vibeponto-api -f`
2. Verificar status: `docker compose ps`
3. Consultar documentação API: `/docs`
4. Abrir issue no repositório
