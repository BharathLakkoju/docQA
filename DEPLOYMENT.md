# Deployment (Phase 6)

Deployment configs are prepared but **not yet applied** — this repo has no GitHub remote and no
accounts were created on your behalf (Claude Code doesn't create accounts or log into third-party
services). Follow this once you're ready.

## 1. Push to GitHub

Render's Blueprint deploy and Vercel's Git integration both deploy from a GitHub repo.

```
gh repo create workflowgpt-cicd-copilot --private --source=. --remote=origin
git push -u origin master
```

(Use `--public` instead if you want it public — recommended eventually, since this is a portfolio
project, but keep it private until Phase 7's README/attribution pass is done.)

## 2. Backend — Render

Config lives in `render.yaml` (repo root) + `backend/Dockerfile`. The Dockerfile builds from the repo
root context (not `backend/`) because `backend/app.py` imports `agents/` and `retrieval/` as sibling
packages, and installs `actionlint` (a Go binary — see `agents/validators/actionlint_validator.py`)
alongside the Python deps.

1. Sign in at https://dashboard.render.com (free, no card required for the free web-service tier).
2. **New +** → **Blueprint** → connect the GitHub repo from step 1. Render reads `render.yaml`
   automatically.
3. Fill in the two secrets marked `sync: false` in `render.yaml` when prompted (or after, in the
   service's **Environment** tab):
   - `PINECONE_API_KEY` — from your Pinecone project (the one holding `workflowgpt-configs` /
     `workflowgpt-prose`, already populated in Phase 2).
   - `OPENROUTER_API_KEY` — from https://openrouter.ai (free account).
   - `CORS_ORIGINS` — leave blank for now; come back and set it to the Vercel URL from step 3 once
     that's live (comma-separated if you end up with both a production and preview URL you want to
     allow).
4. Deploy. First deploy will take a few minutes (Docker build + actionlint install + first fastembed
   model download on first request). Confirm `https://<your-service>.onrender.com/health` returns
   `{"status": "ok"}`.

Free-tier note: Render's free web services spin down after 15 minutes idle and take ~30-60s to wake on
the next request — expect a cold-start delay on the first query after inactivity. This is a known,
disclosed limitation of the zero-cost hosting tier, not a bug — worth a line in Phase 7's README.

## 3. Frontend — Vercel

No extra config needed beyond `frontend/`'s existing `package.json` — Next.js App Router deploys to
Vercel with zero-config.

1. Sign in at https://vercel.com (free, GitHub login works directly).
2. **Add New** → **Project** → import the same GitHub repo, set **Root Directory** to `frontend/`.
3. Add the environment variable in the project's **Settings → Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = the Render URL from step 2 (e.g. `https://workflowgpt-backend.onrender.com`)
4. Deploy. Confirm the chat page (`/`) and eval dashboard (`/eval`) both load and successfully hit the
   live backend (not `localhost`).

## 4. Close the loop

Go back to Render and set `CORS_ORIGINS` to the Vercel URL from step 3, then redeploy the backend (or
it'll block the frontend's requests with a CORS error). If you keep both a production and a preview
Vercel domain you want working, comma-separate them.

## 5. Verify live, not just localhost

Per `Instructions.md` Phase 6 step 3 — actually exercise the deployed version:

- [ ] A factual-lookup query returns a grounded answer with real citations.
- [ ] A fix-generation query (e.g. "write a GitHub Actions job that...") returns a validated snippet.
- [ ] The eval dashboard at `/eval` loads the real Phase 4 numbers (not a loading spinner forever —
      that usually means `CORS_ORIGINS` or `NEXT_PUBLIC_API_URL` is misconfigured).
- [ ] No secrets appear in browser dev tools (Network tab, page source) — only `NEXT_PUBLIC_API_URL`
      (a plain backend URL, not a secret) should be visible client-side.
