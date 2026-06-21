# Frontend — static dashboard

Deployable static bundle for the Water System Risk & Funding Priority Index,
hosted on Cloudflare Pages (`water-risk.example.com`). It no longer bundles
any data file: all data is fetched from the FastAPI backend
(`water-api.example.com`), with server-side filtering, sorting and
pagination.

Deployable files (output directory = `web/`):

- `index.html`
- `styles.css`
- `config.js` — sets `window.APP_CONFIG.apiBase`
- `app.js`
- `vendor/leaflet/*`
- `data/ohio_map.json`, `data/ohio_counties.geojson` — static map assets (well under 25 MiB)

## Configure the API base URL

Edit [`config.js`](config.js):

```js
window.APP_CONFIG = { apiBase: "http://localhost:8000" };          // dev
window.APP_CONFIG = { apiBase: "https://water-api.example.com" }; // prod
```

## Run locally

Start the backend (see [`../docs/deploy.md`](../docs/deploy.md)), then serve the
static files:

```powershell
python -m http.server 8080 -d web
```

Open `http://localhost:8080`.
