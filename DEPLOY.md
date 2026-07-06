# Deploying Transom for a demo

The app ships as **one service**: FastAPI serves both the API and the
production frontend build (`frontend/dist`) from the same origin, so a
deployment is a single container with four environment variables.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | GPT-4o Vision + embeddings + RAG answering |
| `MISTRAL_API_KEY` | yes | Blueprint OCR |
| `PINECONE_API_KEY` | yes | Warranty vector search |
| `LOGFIRE_TOKEN` | no | Observability — runs with export disabled if absent |

The SQLite database and uploaded photos live under `/data` in the
container (`DATABASE_PATH`, `UPLOADS_DIR` — already set in the
Dockerfile). Mount a volume there if you want data to survive
redeploys; for a demo, ephemeral is usually fine since the dashboard is
session-scoped anyway. The schema is created automatically on first
boot.

**Sizing:** the PII model + reranker need ~2–4 GB RAM. Free tiers
(512 MB) will OOM — pick a plan with at least 2 GB, ideally 4 GB.

## Option 1 — Railway (easiest persistent link)

1. Push the repo to GitHub (double-check `.env` is not committed — it's
   gitignored).
2. https://railway.app → New Project → **Deploy from GitHub repo**.
   Railway detects the `Dockerfile` automatically.
3. In the service's **Variables** tab, add the env vars above.
4. In **Settings → Networking**, click **Generate Domain**.
5. (Optional) **Settings → Volumes**: mount a volume at `/data`.

Share the generated `*.up.railway.app` URL with the interviewer.

## Option 2 — Fly.io

```bash
fly launch --no-deploy        # accept the detected Dockerfile
fly volumes create data --size 1
# add to fly.toml:  [mounts]  source = "data"  destination = "/data"
fly secrets set OPENAI_API_KEY=... MISTRAL_API_KEY=... PINECONE_API_KEY=...
fly scale memory 4096
fly deploy
```

## Option 3 — Any Docker host (VPS, EC2, ...)

```bash
docker compose up -d --build     # reads keys from ./.env
```

Then reverse-proxy port 8000 (Caddy/nginx) for HTTPS, or for a quick
public URL without a proxy:

```bash
cloudflared tunnel --url http://localhost:8000
```

## Try the production image locally first

```bash
docker compose up --build
open http://localhost:8000
```

## Notes for a public demo link

- The link exposes YOUR OpenAI/Mistral API keys' spending — each upload
  costs a few cents. Fine for an interviewer; don't post the URL
  publicly, and consider setting spend limits on the provider dashboards.
- The warranty chat answers from the Pinecone index ingested for
  property #1 (`property_1_warranty` namespace) — that data is in
  Pinecone, not the container, so it works on a fresh deployment.
- A demo reset: the trash button in the top bar wipes ingested data;
  the dashboard is session-scoped on top of that (each page load starts
  empty until documents are uploaded).
