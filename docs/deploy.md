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
- Python 3.12+, Postgres 14+ installed.
- Any Linux VPS (provider-agnostic; reached over SSH). A host alias in your
  `~/.ssh/config` keeps the real hostname out of the repo.
- Repo checked out at `/home/deploy/water-system-risk-index` (adjust paths to the
  service account you run under).

### Install dependencies
```bash
cd /home/deploy/water-system-risk-index
python3 -m pip install -r requirements-api.txt
```
On a modern Debian/Ubuntu the system Python is "externally managed" (PEP 668), so
either install into a virtualenv or pass `--break-system-packages`. Only the
runtime deps in `requirements-api.txt` are needed to serve; `requirements-dev.txt`
(ruff/mypy/pytest/pip-audit/httpx) is for development and CI.

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

### Updating an existing deployment

To roll out new code + data to a box that is already running:
```bash
cd /home/deploy/water-system-risk-index
git fetch origin && git reset --hard origin/main   # match the canonical branch
python3 -m pip install -r requirements-api.txt      # only if runtime deps changed
python3 -m waterapi.cli init-db                     # idempotent; adds new tables/indexes
python3 -m waterapi.cli load                        # reseed from the refreshed app_data.json
sudo systemctl restart water-api                    # pick up the new code
curl -s http://127.0.0.1:8000/health                # expect {"status","version","database":"ok"}
```

**Schema-evolution gotcha.** `init-db` uses `CREATE TABLE IF NOT EXISTS`, so it
will *not* add new **columns** to a table that already exists. When the schema
gains a column on an existing table (e.g. the `min_lon/min_lat/max_lon/max_lat`
bounding-box columns added to `water_system_boundaries` and
`water_system_swap_areas` for viewport loading), add them explicitly before
reloading, then re-run `init-db` for the indexes:
```sql
ALTER TABLE water_system_boundaries ADD COLUMN IF NOT EXISTS min_lon double precision;
ALTER TABLE water_system_boundaries ADD COLUMN IF NOT EXISTS min_lat double precision;
ALTER TABLE water_system_boundaries ADD COLUMN IF NOT EXISTS max_lon double precision;
ALTER TABLE water_system_boundaries ADD COLUMN IF NOT EXISTS max_lat double precision;
-- repeat for water_system_swap_areas
```
`load` runs as a single transaction, so a failed reload rolls back and leaves the
live data intact.

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
