# Deploy do VibePonto na Hetzner

Este roteiro publica o sistema em `https://vibeponto.com.br`, mantém banco, Redis,
RabbitMQ e painel do MinIO fora da internet e usa Caddy para emitir e renovar o
certificado HTTPS automaticamente.

## 1. Criar o servidor

Antes de clicar em **Create & Buy now**:

1. Use **Ubuntu 24.04 LTS**.
2. Para a pilha completa, escolha uma máquina com **8 GB de RAM**. Uma máquina de
   4 GB serve apenas para piloto com pouco tráfego e `API_WORKERS=1`.
3. Escolha a localização considerando latência e onde os dados podem ser
   armazenados. Ashburn tende a ter menor latência para o Brasil; as localizações
   europeias mantêm os dados do servidor na União Europeia.
4. Mantenha IPv4. IPv6 é opcional.
5. Adicione uma chave SSH. No PowerShell local:

   ```powershell
   ssh-keygen -t ed25519 -C "vibeponto-prod" -f "$env:USERPROFILE\.ssh\vibeponto_prod"
   Get-Content "$env:USERPROFILE\.ssh\vibeponto_prod.pub" | Set-Clipboard
   ```

   Cole a chave pública em **SSH keys > Add SSH key**. Nunca envie ou copie o
   arquivo sem a extensão `.pub`.
6. Crie e aplique um firewall com estas regras de entrada:

   | Protocolo | Porta | Origem |
   |---|---:|---|
   | TCP | 22 | seu IP público `/32` |
   | TCP | 80 | qualquer IPv4 e IPv6 |
   | TCP | 443 | qualquer IPv4 e IPv6 |
7. Ative **Backups**.
8. Use o nome `vibeponto-prod-01` e crie o servidor.

As portas 3000, 8000, 5432, 6379, 5672, 9000, 9001 e 15672 não devem ser
liberadas no firewall.

## 2. Primeiro acesso e usuário administrativo

Substitua `IP_DO_SERVIDOR` pelo IPv4 mostrado na Hetzner:

```powershell
ssh -i "$env:USERPROFILE\.ssh\vibeponto_prod" root@IP_DO_SERVIDOR
```

No servidor:

```bash
apt update
apt upgrade -y
apt install -y ca-certificates curl git openssl nano
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
```

Abra outro PowerShell e confirme o acesso antes de desabilitar o login de root:

```powershell
ssh -i "$env:USERPROFILE\.ssh\vibeponto_prod" deploy@IP_DO_SERVIDOR
```

Somente depois do teste, ainda como root:

```bash
cat >/etc/ssh/sshd_config.d/99-vibeponto.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
EOF
sshd -t
systemctl reload ssh
```

## 3. Instalar Docker pelo repositório oficial

Execute como o usuário `deploy`:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
exit
```

Conecte novamente como `deploy` e valide:

```bash
docker version
docker compose version
```

## 4. Baixar o projeto

```bash
sudo mkdir -p /opt/vibeponto
sudo chown deploy:deploy /opt/vibeponto
git clone https://github.com/maximussjrp/vibeponto.git /opt/vibeponto
cd /opt/vibeponto
```

O deploy deve usar uma revisão que já contenha `deploy/Caddyfile` e a configuração
do serviço `caddy` em `docker-compose.prod.yml`.

## 5. Configurar os segredos

```bash
cd /opt/vibeponto
cp .env.production.example .env.production
chmod 600 .env.production
```

Gere um valor diferente para cada senha/chave:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Edite o arquivo:

```bash
nano .env.production
```

Substitua todos os valores `replace-with-...`. Confirme principalmente:

```dotenv
ENVIRONMENT=production
DEBUG=false
APP_PUBLIC_URL=https://vibeponto.com.br
CORS_ORIGINS=["https://vibeponto.com.br","https://www.vibeponto.com.br"]
NEXT_PUBLIC_API_URL=https://vibeponto.com.br/api/v1
SITE_DOMAIN=vibeponto.com.br
STORAGE_DOMAIN=storage.vibeponto.com.br
STORAGE_PUBLIC_ENDPOINT=https://storage.vibeponto.com.br
ACME_EMAIL=seu-email-operacional@exemplo.com
API_WORKERS=2
CELERY_WORKER_CONCURRENCY=2
```

Use somente caracteres hexadecimais nas senhas geradas acima. Isso evita que
caracteres reservados quebrem as URLs internas do banco, Redis e RabbitMQ.
Em uma máquina de 4 GB, use `API_WORKERS=1` e `CELERY_WORKER_CONCURRENCY=1`.

O exemplo mantém `EMAIL_PROVIDER=disabled`. Antes de liberar recuperação de senha
para usuários, configure `smtp`, `sendgrid` ou `ses` e preencha as credenciais
correspondentes no mesmo arquivo. O sistema continua respondendo de forma genérica
quando o envio estiver indisponível, sem revelar se um e-mail está cadastrado.

Valide sem iniciar os serviços:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
```

## 6. Apontar o domínio no Registro.br

No painel do domínio, abra **DNS > Editar zona** e crie três registros `A`:

| Nome | Tipo | Destino |
|---|---|---|
| `@` (ou vazio) | A | `IP_DO_SERVIDOR` |
| `www` | A | `IP_DO_SERVIDOR` |
| `storage` | A | `IP_DO_SERVIDOR` |

Não use o redirecionamento web do Registro.br. O domínio precisa apontar por DNS
diretamente para a VPS. Se houver registros `AAAA` antigos, remova-os por enquanto;
adicione IPv6 somente depois de testar a conectividade IPv6 do servidor.

Confira a propagação no computador local:

```powershell
Resolve-DnsName vibeponto.com.br
Resolve-DnsName www.vibeponto.com.br
Resolve-DnsName storage.vibeponto.com.br
```

Os três nomes devem retornar o IPv4 da Hetzner.

## 7. Subir a produção

Depois que o DNS estiver apontando para o servidor:

```bash
cd /opt/vibeponto
docker compose --env-file .env.production -f docker-compose.prod.yml build --pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

O serviço `migrate` deve terminar com código 0. Os demais devem ficar em execução
ou saudáveis. Acompanhe os logs iniciais:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 api frontend caddy
```

O Caddy obtém e renova o certificado automaticamente quando o DNS aponta para a
VPS e as portas 80/443 estão abertas.

## 8. Validar e criar a primeira empresa

No computador local:

```powershell
curl.exe -I https://vibeponto.com.br
curl.exe https://vibeponto.com.br/health
curl.exe https://vibeponto.com.br/ready
```

Depois acesse:

- `https://vibeponto.com.br/registro` para criar a primeira empresa e o usuário
  administrador;
- `https://vibeponto.com.br/login` para entrar.

Não execute `seed_demo_data.py` em produção.

## 9. Backup e manutenção

O backup automático da Hetzner guarda sete cópias diárias do disco. Mantenha também
um `pg_dump` criptografado fora desta VPS; um backup no mesmo servidor não protege
contra perda da máquina ou da conta.

Backup manual do PostgreSQL:

```bash
cd /opt/vibeponto
mkdir -p backups
set -a
. ./.env.production
set +a
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "backups/postgres-$(date +%F-%H%M).sql.gz"
```

Atualização da aplicação:

```bash
cd /opt/vibeponto
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml build --pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --remove-orphans
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Ver logs e uso de disco:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200
df -h
docker system df
```

Nunca use `docker system prune --volumes`: os dados persistentes do PostgreSQL,
MinIO, Redis, RabbitMQ e os certificados do Caddy ficam em volumes Docker.
