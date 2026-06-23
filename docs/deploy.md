# Deployment - Water System Risk Index

Full-stack layout (mirrors the `grid` app):

- **Frontend** - static bundle in `web/`, hosted on **Cloudflare Pages** at
  `https://water-risk.example.com`.
- **Backend** - FastAPI + Postgres on the VPS at
  `https://water-api.example.com`, fronted by nginx + certbot TLS,
  supervised by systemd.

The browser pulls only what it displays (server-side filter / sort / paginate);
the 27 MB JSON is no longer shipped to clients.

---

## 1. Backend (VPS)

### Prerequisites
- Python 3.12, Postgres 14+ installed.
- Repo checked out at `/home/deploy/water-system-risk-index`.

### Install dependencies
```bash
cd /home/deploy/water-system-risk-index
python3 -m pip install -r requirements-api.txt
```

### Create the database and role
```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE water_app WITH LOGIN PASSWORD 'CHANGE_ME';
CREATE DATABASE water_risk OWNER water_app;
SQL
```

### Configure environment
```bash
cp .env.example .env
# edit .env: set PGPASSWORD (and PGHOST/PGUSER/PGDATABASE if different),
# WATER_API_PORT=8000, WATER_CORS_ORIGINS=https://water-risk.example.com
```
`.env` is gitignored - never commit real credentials.

### Create schema and seed data
```bash
# Idempotent: safe to re-run.
python3 -m waterapi.cli init-db

# Loads data/processed/app_data.json into Postgres (truncate + insert in one tx).
python3 -m waterapi.cli load
```

A data refresh is just: regenerate the seed, then reload:
```bash
python3 src/export_web_app_data.py   # rebuilds data/processed/app_data.json from processed CSVs
python3 -m waterapi.cli load
```

### Run as a service
```bash
sudo cp deploy/systemd/water-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now water-api
sudo systemctl status water-api
curl -s http://127.0.0.1:8000/health   # {"status":"ok","version":"0.1.0"}
```

### Reverse proxy + TLS
```bash
sudo cp deploy/nginx/water-api.example.com.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/water-api.example.com.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d water-api.example.com   # adds HTTPS + redirect
```

---

## 2. Frontend (Cloudflare Pages)

The frontend is fully static; the only config is the API base URL in
[`web/config.js`](../web/config.js).

- **Local dev** - leave `apiBase` as `http://localhost:8000`.
- **Production** - set it to `https://water-api.example.com` before/at deploy.

Cloudflare Pages settings:
- Build command: *(none - static)*
- Output directory: `web`

To inject the production API base without editing the committed file, add a Pages
build step, e.g.:
```bash
echo 'window.APP_CONFIG = { apiBase: "https://water-api.example.com" };' > web/config.js
```

No file in `web/` exceeds Cloudflare's 25 MiB per-file limit (largest is
`web/data/ohio_map.json`, ~1.8 MB).

---

## 3. Local development (Windows)

```powershell
python -m pip install -r requirements-api.txt
# Point .env at a local Postgres, then:
python -m waterapi.cli init-db
python -m waterapi.cli load
python -m waterapi.cli serve          # uvicorn on http://127.0.0.1:8000

# Serve the frontend from web/ (any static server), e.g.:
python -m http.server 5173 --directory web
# open http://localhost:5173
```
