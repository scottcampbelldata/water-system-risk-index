# Portfolio Web App

This folder is the deployable static portfolio app for the Water System Risk & Funding Priority Index.

Deploy these files as a static site:

- `index.html`
- `styles.css`
- `app.js`
- `data/app_data.json`

Regenerate app data after running the pipeline:

```powershell
python src/export_web_app_data.py
```

Run locally:

```powershell
python -m http.server 8080 -d web
```

Then open `http://localhost:8080`.
