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

On start the API creates all tables and the owner login (`OWNER_EMAIL` /
`OWNER_PASSWORD`). It does **not** load demo data unless you set
`SEED_IF_EMPTY=true` (then demo data loads only into a totally empty database;
demo logins in `README.md`). Restarts never touch existing data.

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

## 4. Resetting data on a deployed database (RESET_DATA)

`SEED_IF_EMPTY` only loads demo data into a **totally empty** database, so a
Render database that already holds old demo data + test junk (e.g. a supplier
payment of ₹20,13,22,110 showing a −₹20 crore loss) never gets refreshed. Use the
one-time **`RESET_DATA`** flag to fix it.

**It is destructive. Set it, deploy once, then remove it.** If left set, every
restart wipes again.

| Value   | Effect                                                                 |
| ------- | ---------------------------------------------------------------------- |
| `empty` | Delete all business data (orders, payments, machines, yarn, wages, …). **Keeps roles and the owner login** from `OWNER_EMAIL` / `OWNER_PASSWORD`. A clean mill for entering real data live. |
| `demo`  | Same wipe, then reload the clean October 2026 demo seed.               |
| (unset) | Normal startup. Nothing is wiped.                                      |

Steps on Render (`everest-textile-api` → **Environment**):

1. Make sure `OWNER_EMAIL` and `OWNER_PASSWORD` are set — after an `empty` reset
   that is the only login that still exists.
2. Add `RESET_DATA=empty` (or `demo`). **Save, rebuild and deploy.**
3. Watch the deploy **Logs** for a line like
   `RESET_DATA=empty: wiped N business rows across M tables …`.
4. **Remove the `RESET_DATA` variable** and deploy once more, so later restarts
   never wipe again.
5. Log in as the owner and confirm the dashboard shows real/zero figures.

Any value other than `empty` or `demo` is ignored (logged as such) and nothing is
wiped.
