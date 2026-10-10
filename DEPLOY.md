# Deploy: Render (API + PostgreSQL) and Vercel (frontend)

```
Browser ──> Vercel (React)  ──/api/*──>  Render (FastAPI)  ──>  Render PostgreSQL
```

The browser only talks to Vercel. Vercel forwards `/api/*` to Render, so no CORS
setup is needed and the Dify key never leaves the backend.

## 1. Backend + database on Render

1. Render dashboard → **New → Blueprint** → pick this repo (branch `main`).
2. Render reads `render.yaml` and creates:
   - `everest-textile-db`: free PostgreSQL
   - `everest-textile-api`: the FastAPI service, with `DATABASE_URL` and a random
     `JWT_SECRET` filled in automatically
3. Leave `CORS_ORIGINS` and `DIFY_API_KEY` empty for now and click **Apply**.
4. When the service is live, open `https://<your-service>.onrender.com/api/health`.
   It should show `"status": "ok"` and `"dialect": "postgresql"`.

On first start the API creates all tables and loads the demo data (demo logins in
`README.md`). Later restarts keep existing data; demo data is only loaded into an
empty database. To start empty instead, set `SEED_IF_EMPTY=false`.

**Note the service URL.** If Render gave it a suffix (for example
`everest-textile-api-ab12.onrender.com`), update the `/api` rewrite in
`frontend/vercel.json` to match and push.

## 2. Frontend on Vercel

1. Vercel → **Add New → Project** → import this repo.
2. **Root Directory: `frontend`** (framework Vite is detected).
3. Deploy. `frontend/vercel.json` sends `/api/*` to Render and serves
   `index.html` for app routes such as `/login` and `/app/...`.
4. Open the site, log in as `owner@everest.test` / `owner123`.

## 3. AI assistant (when ready)

On Render → `everest-textile-api` → **Environment**: set `DIFY_API_KEY` (and
`DIFY_BASE_URL` if not using Dify Cloud), then **Save, rebuild and deploy**. Until
then the chat bubble answers with a "not configured" message.

## Free-plan notes

- The Render free web service sleeps after ~15 minutes idle; the first request
  then takes 30–60 s. Open `/api/health` a minute before a demo.
- Render's free PostgreSQL has a time limit (see Render's pricing page); export
  data you want to keep before it expires.
