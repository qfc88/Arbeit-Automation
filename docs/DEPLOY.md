# Deploy — home server + VPS reverse proxy + ZeroTier admin

Target hardware:
- **Home server**: Ryzen 5700X (8C/16T) + 16 GB RAM + RTX 2060 12 GB. Runs Postgres + scraper + (Pha 3) API + frontend + ML.
- **VPS**: 1–2 vCPU / 1–2 GB RAM, public IP, a domain with Let's Encrypt. Only role: TLS terminator and tunnel endpoint.
- **Admin laptop**: ZeroTier client.

The VPS never sees plaintext admin traffic. Admins reach the home server directly over ZeroTier. End users reach the public portal only through the VPS → WireGuard tunnel → home nginx.

## Topology

```
Internet
   │ 443
   ▼
┌──────────────┐
│ VPS          │  nginx TLS, rate-limit, /admin → 404
│ 10.8.0.1     │  WireGuard listen :51820/udp
└──────┬───────┘
       │  WireGuard (home dials out, keepalive holds NAT open)
       ▼
┌──────────────┐                     ┌─────────────────┐
│ Home server  │  nginx (Docker)     │ Admin laptop     │
│ 10.8.0.2     │  ─ Host jobs.*      │ ZeroTier client  │
│ zt0 10.147.* │  ─ Host admin.home  │ ◄── direct ─────┘
│ Docker compose (postgres, scraper, adminer, monitor, …) │
└──────────────┘
```

Port matrix:

| Surface         | Listener                 | Reachable from              | Allowed paths                     |
|-----------------|--------------------------|-----------------------------|-----------------------------------|
| Public          | VPS :443                 | Internet                    | `/`, `/api/*` (admin → 404)      |
| VPS → home      | wg0 10.8.0.2 :80         | 10.8.0.1 only               | Public paths only                 |
| Admin           | zt0 10.147.x.x :80       | ZeroTier members only       | `/adminer`, `/monitor`, `/admin` |
| Docker services | 127.0.0.1:{5432,8000,…}  | localhost only              | via nginx                         |

## One-time setup

### 1. VPS

```bash
# SSH in as root.
apt update && apt install -y nginx wireguard ufw fail2ban certbot python3-certbot-nginx

# WireGuard keys
cd /etc/wireguard
umask 077
wg genkey | tee vps.key | wg pubkey > vps.pub
# Save vps.pub somewhere; you need it on the home box.

# Copy the template in, fill in keys + home peer pubkey
cp /path/to/repo/deploy/wireguard/vps-wg0.conf.example wg0.conf
vim wg0.conf

systemctl enable --now wg-quick@wg0

# Firewall
bash /path/to/repo/deploy/ufw-vps.sh

# nginx
cp /path/to/repo/deploy/nginx/vps-jobs.conf /etc/nginx/sites-available/jobs.conf
ln -s /etc/nginx/sites-available/jobs.conf /etc/nginx/sites-enabled/
# Replace server_name + cert paths with your domain first.

certbot --nginx -d jobs.yourdomain
nginx -t && systemctl reload nginx
```

### 2. Home server

```bash
# Docker + NVIDIA runtime
apt install -y docker.io docker-compose-v2 wireguard ufw
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt update && apt install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# WireGuard (home dials VPS)
cd /etc/wireguard
umask 077
wg genkey | tee home.key | wg pubkey > home.pub
cp /path/to/repo/deploy/wireguard/home-wg0.conf.example wg0.conf
vim wg0.conf     # paste keys + VPS endpoint + pubkey
systemctl enable --now wg-quick@wg0

# ZeroTier
curl -s https://install.zerotier.com | bash
zerotier-cli join <network-id>
# Approve device + tag role=server in my.zerotier.com
# Paste deploy/zerotier/flow-rules.txt into the network's Flow Rules page.

# Firewall
bash /path/to/repo/deploy/ufw-home.sh

# Secrets
cd /path/to/repo
cp .env.docker.example .env.docker
vim .env.docker                          # fill DB_PASSWORD + TWOCAPTCHA_API_KEY

# Admin htpasswd
htpasswd -c deploy/nginx/htpasswd admin

# TLS for admin surface (optional but recommended — use Let's Encrypt with
# DNS-01 or a self-signed cert; nginx only listens on LAN interfaces so
# public Let's Encrypt HTTP-01 will not work).
mkdir -p deploy/nginx/certs

# Bring up the stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 3. Admin laptop

```bash
# Install ZeroTier client, join the same network, get approved.
# Add to /etc/hosts:
echo "10.147.x.x admin.home" >> /etc/hosts   # real ZT IP of the home server
```

## Verification

From a machine **not on ZeroTier**, outside your LAN:

```bash
curl -I https://jobs.yourdomain/                 # 200 (job portal)
curl -I https://jobs.yourdomain/admin            # 404
curl -I https://jobs.yourdomain/adminer          # 404
```

From the admin laptop (on ZeroTier):

```bash
curl -I http://admin.home/adminer/               # 401 (basic-auth challenge)
curl -u admin:*** http://admin.home/adminer/     # 200
```

From the home server:

```bash
docker compose ps                                # all healthy
docker compose exec job-scraper nvidia-smi       # GPU reachable (Pha 3)
ss -ltnp | grep -E '5432|8000|8080|9000'         # bound to 127.0.0.1 only
wg show                                          # handshake fresh (<3 min)
ufw status verbose                               # deny by default
```

## Resource sizing on the home box

Budget when Pha 3 is fully deployed:

| Service         | CPU      | RAM    | GPU VRAM |
|-----------------|----------|--------|----------|
| postgres        | 2 cores  | 2 GB   | —        |
| scraper (×6)    | 6 cores  | 5 GB   | —        |
| api (FastAPI)   | 1 core   | 1 GB   | —        |
| frontend (Next) | 1 core   | 1 GB   | —        |
| ml-inference    | 1 core   | 2 GB   | 2–6 GB   |
| nginx + adminer | <1 core  | 256 MB | —        |
| **Total**       | ~11 / 16 | ~11 / 16 GB | 2–6 / 12 GB |

Leaves ~5 threads / 5 GB RAM as burst headroom for the scraper's concurrency=6 profile and for ML training spikes.

## Threat model — what this setup does *not* do

- ZeroTier is a layer-2 mesh, not a zero-trust identity plane. Admin paths stay behind htpasswd (and later JWT) so a stolen ZT membership alone is not enough.
- The VPS is a proxy, not a WAF. If DDoS is a concern, put Cloudflare / bunny.net in front.
- WireGuard keys are as important as SSH keys. Losing `home.key` = someone else can impersonate the home peer. Rotate if the home disk ever leaves your control.
- Backups: run `pg_dump` on a schedule to an off-box target (rsync.net, Backblaze B2, etc.). Not configured by this repo.
