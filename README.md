# QR Code Generator API

A FastAPI service where users register, authenticate, generate styled QR codes from web URLs, download them as PNG files, and manage their own generation history.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
$env:QR_API_SECRET = "a-long-random-value"
uvicorn app.main:app --reload
```

For convenience, this project also supports the shorter command from the
repository root:

```powershell
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to use the interactive API documentation.

## API flow

1. `POST /auth/register` with `{ "email", "password" }` (passwords require at least 10 characters).
2. In Swagger (`/docs`), click **Authorize**, enter the registered email as **username** and its password, then click **Authorize**. Swagger obtains and applies the OAuth2 token automatically.
3. `POST /qrcodes` with a payload such as:

```json
{
  "url": "https://example.com",
  "foreground": "#112233",
  "background": "#FFFFFF",
  "size": 10,
  "border": 4,
  "error_correction": "M"
}
```

4. Use `GET /qrcodes` to view history, `GET /qrcodes/{id}/download` for PNG output, and `DELETE /qrcodes/{id}` to remove an item.

Generated files are rendered on demand from the stored, validated QR configuration, so the service does not need to retain image files. SQLite data lives at `data/qr_api.db` by default; mount or persist that directory when deploying.

## Deployment notes

Set `ENVIRONMENT=production`, provide a unique `QR_API_SECRET`, store `QR_DATABASE_PATH` on persistent storage, and configure `QR_CORS_ORIGINS` for your client origins. A production process can be started with:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or build the included container image and attach persistent storage for SQLite:

```powershell
docker build -t qr-code-api .
docker run --rm -p 8000:8000 -e QR_API_SECRET="a-long-random-value" -v "${PWD}/data:/data" qr-code-api
```

## Deploy: Render API + Vercel frontend

The browser application is in `frontend/`. It is a static HTML/CSS/JavaScript
site that calls the API URL in `frontend/config.js`.

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint**, connect the repository, and deploy
   `render.yaml`. It creates a free Docker web service for demonstrations.
   After deployment, copy the public `https://…onrender.com` API URL. Set
   `QR_CORS_ORIGINS` in the Render service after the Vercel URL is known (see
   step 4). Its SQLite data resets whenever the free service restarts or sleeps.
3. Replace the local value in `frontend/config.js` with the Render API URL and
   push the change. Do not include a trailing slash.
4. In Vercel, import the same GitHub repository. Set the **Root Directory** to
   `frontend`, select **Other** for the framework preset, and leave build and
   output settings empty. Deploy. Copy the production Vercel URL.
5. In Render → service → Environment, set `QR_CORS_ORIGINS` to that Vercel URL
   (for example `https://quickqr.vercel.app`) and redeploy the API.

For local browser testing, leave `frontend/config.js` pointed at
`http://127.0.0.1:8000` and serve the folder with any static server. The API
must have `QR_CORS_ORIGINS=http://127.0.0.1:<frontend-port>` when the frontend
uses a different local port.
