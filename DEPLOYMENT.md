# Deploying TripSync AI

This gets you a live, shareable link — the backend (API + data service)
on Render, the frontend on Vercel, both with generous free tiers.

**Before you start:** I built and reviewed the Dockerfiles/configs below
but couldn't actually run `docker build` to verify them (no Docker
available in the environment I built this in). Run this first, locally:

```bash
docker compose build
docker compose up
```

Visit `http://localhost:8080` — if the trip planner works end-to-end
there, everything below will work the same way on Render/Vercel. If
something fails to build, it's almost certainly a missing dependency in
one of the two `Dockerfile`s — check the error against
`requirements.txt` and add whatever's missing.

---

## 1. Push to GitHub

Both Render and Vercel deploy from a GitHub repo, not a zip upload.

```bash
cd travel-planner
git init
git add .
git commit -m "Initial commit"
gh repo create tripsync-ai --public --source=. --push
# or: create a repo on github.com, then git remote add origin <url> && git push
```

## 2. Deploy the data service (Render)

1. Go to [render.com](https://render.com), sign up (free, GitHub login works)
2. **New +** → **Web Service** → connect your `tripsync-ai` repo
3. Settings:
   - **Name**: `tripsync-data-service`
   - **Runtime**: Docker
   - **Dockerfile Path**: `data_service/Dockerfile`
   - **Docker Build Context Directory**: `.` (repo root — the Dockerfile copies from root)
   - **Instance Type**: Free
4. **Create Web Service**. Wait for the build (~2-3 min). Render gives
   you a URL like `https://tripsync-data-service.onrender.com` — copy it.

## 3. Deploy Redis (optional but recommended)

1. Render dashboard → **New +** → **Key Value** (Render's managed Redis)
2. Free tier is fine for a demo. Copy the **Internal Redis URL** it gives you.
3. Skip this and the app still works — falls back to in-memory caching
   automatically (see `cache/factory.py`).

## 4. Deploy the main API (Render)

1. **New +** → **Web Service** → same repo
2. Settings:
   - **Name**: `tripsync-api`
   - **Runtime**: Docker
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Build Context Directory**: `.`
   - **Instance Type**: Free
3. **Environment** tab, add:
   ```
   OWN_FLIGHT_SERVICE_URL=https://tripsync-data-service.onrender.com
   OWN_HOTEL_SERVICE_URL=https://tripsync-data-service.onrender.com
   OWN_ACTIVITY_SERVICE_URL=https://tripsync-data-service.onrender.com
   REDIS_URL=<internal redis URL from step 3, if you set it up>
   CORS_ALLOWED_ORIGINS=*
   ```
   (You'll come back and tighten `CORS_ALLOWED_ORIGINS` in step 6, once
   you know your actual Vercel URL — can't set it yet, chicken-and-egg.)
4. **Create Web Service**. Copy the resulting URL, e.g.
   `https://tripsync-api.onrender.com`.

**Free tier note**: Render's free web services spin down after 15 min
of inactivity and take ~30-60s to wake up on the next request. Fine for
a portfolio demo people click occasionally; mention it if a reviewer
hits a slow first load.

## 5. Deploy the frontend (Vercel)

1. Go to [vercel.com](https://vercel.com), sign up (GitHub login works)
2. **Add New** → **Project** → import your `tripsync-ai` repo
3. Settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite (auto-detected)
4. **Environment Variables**, add:
   ```
   VITE_API_BASE_URL=https://tripsync-api.onrender.com
   ```
   (the URL from step 4 — no trailing slash)
5. **Deploy**. Vercel gives you a URL like `https://tripsync-ai.vercel.app`.

## 6. Close the loop — tighten CORS

Now that you have the Vercel URL, go back to Render → `tripsync-api` →
**Environment**, update:
```
CORS_ALLOWED_ORIGINS=https://tripsync-ai.vercel.app
```
Save — Render redeploys automatically. This is what `cors_allowed_origins`
in `config.py` reads (see `api/main.py`).

## 7. Verify

Visit your Vercel URL, submit a trip request, confirm the SSE stream
shows agent progress live and the final itinerary renders. Check the
`data_source` values (visible if you inspect network requests / add a
debug log) to confirm it's hitting `own_service`, not falling back to
mock the whole time — if the data service URL is wrong, everything
still "works" via mock fallback, which can silently hide a
misconfiguration.

---

## Alternative: Railway instead of Render

Railway works almost identically (Docker-native, generous free tier,
same env var pattern) if you'd rather use that — the steps are the same
shape, just a different dashboard.

## Alternative: Netlify instead of Vercel

Same idea — root directory `frontend`, build command `npm run build`,
publish directory `dist`, same `VITE_API_BASE_URL` env var.
