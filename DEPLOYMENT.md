# Deployment (Phase 6) — LIVE

- **Backend**: https://workflowgpt-backend.onrender.com (Render, free Docker web service)
- **Frontend**: https://documentorqa.vercel.app (Vercel, custom alias on the `frontend` project —
  the project's default domain `frontend-bharathlakkojus-projects.vercel.app` also resolves to the
  same deployment)

Both verified live end-to-end (not just localhost): factual-lookup queries, fix-generation with
`actionlint` validation, and the eval dashboard all confirmed working against the real public URLs.

## How it was deployed

Config lives in `render.yaml` (repo root) + `backend/Dockerfile` for the backend (Docker build from
the repo root context, since `backend/app.py` imports `agents/` and `retrieval/` as sibling packages,
and installs the `actionlint` Go binary alongside Python deps). Deployed via Render's Blueprint flow
(dashboard → New+ → Blueprint → connect `BharathLakkoju/docQA`).

Frontend has no extra config beyond `frontend/package.json` — deployed via `vercel --prod` from
`frontend/`, with `NEXT_PUBLIC_API_URL` set to the Render URL via `vercel env add`.

## Issues hit during deployment, for next time

1. **Blank `OPENROUTER_API_KEY`** — first Render apply left it empty. `/health` and `/eval/*` (no
   external calls) worked fine, but `/query` 500'd with `openai.AuthenticationError: Missing
   Authentication header`. Pinecone retrieval had already succeeded by that point in the traceback, so
   the error was isolated to the LLM call specifically. Fix: set the real key in Render's Environment
   tab and let it redeploy.
2. **Vercel's "Aliased: ..." CLI output is not the stable production URL.** `vercel --prod` prints a
   transient per-deployment alias in its terminal output; the actual stable, project-name-based domain
   (`frontend-<org-slug>.vercel.app`) is separate and only visible via `vercel alias ls`. Wiring
   `CORS_ORIGINS` to the transient alias caused every CORS preflight to fail even after Render redeployed
   correctly — the fix was pointing `CORS_ORIGINS` at the real stable alias (or the custom domain).
3. **Switching Vercel accounts mid-session breaks the existing project link.** Running `vercel login` in
   a separate terminal to switch accounts invalidates `frontend/.vercel/project.json`'s link to the old
   account's project. Symptom looked like "deployment malfunctioned"; fix was `rm -rf .vercel && vercel
   link --yes` to relink under the new account, then re-add env vars (a fresh project has none) and
   redeploy.
4. **Vercel Deployment Protection (SSO wall) is on by default for some account/team configs.** It
   302-redirects every request — including the CORS preflight itself — to a Vercel login page, so the
   site is completely inaccessible to the public even though the deploy itself succeeded. This is a
   dashboard-only project setting (**Settings → Deployment Protection**, set Production to Disabled);
   there's no CLI flag for it. Had to be turned off by hand before the site was actually reachable.
5. **Render free-tier cold starts.** The service spins down after ~15 min idle; the very first request
   after a cold start can fail client-side as "Failed to fetch" (the frontend has no client-side retry)
   before the container finishes waking — a retry a few seconds later succeeds. This is expected
   free-tier behavior, not a bug, and is worth a line in Phase 7's README so it doesn't read as broken.

## Re-deploying

**Backend**: push to `master` — Render auto-deploys from the connected GitHub repo on every push (no
manual step needed) as long as the Render service's auto-deploy setting is on.

**Frontend**: `cd frontend && npx vercel --prod --yes` (requires `vercel whoami` to show the correct
account — re-run `vercel link --yes` first if the account was switched since the last deploy).

## Verify live, not just localhost (re-check after any redeploy)

- [ ] `curl https://workflowgpt-backend.onrender.com/health` → `{"status":"ok"}`
- [ ] A factual-lookup query on https://documentorqa.vercel.app returns a grounded answer with real
      citations.
- [ ] A fix-generation query (e.g. "write a GitHub Actions job that...") returns a validated snippet.
- [ ] `/eval` loads the real Phase 4 numbers (a loading spinner forever usually means `CORS_ORIGINS` or
      `NEXT_PUBLIC_API_URL` drifted out of sync — check `vercel alias ls` for the real frontend domain
      before assuming the backend is broken).
- [ ] No secrets appear in browser dev tools (Network tab, page source) — only `NEXT_PUBLIC_API_URL`
      (a plain backend URL, not a secret) should be visible client-side.
