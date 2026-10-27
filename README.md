# Meridian Call Guide

A small call-side guide for Meridian Growth Partners, built for the DeepThought FDE task. It covers all eight cold-call stages and saves the call outcome and stage history.

## Stack
- Frontend: React + Vite (deploy to Vercel)
- Backend: FastAPI + Supabase Python client (deploy to Render)
- Database: Supabase PostgreSQL
- LLM: Gemini API called from the backend to draft a factual two-sentence summary after a call closes. The API key stays server-side.

## Local setup

### 1. Supabase
1. Create a Supabase project.
2. Open **SQL Editor** and run `supabase/schema.sql` in full.
3. In Project Settings / API, copy the Project URL and `service_role` key. Keep the service-role key private.

### 2. Backend
Open CMD in the `backend` folder. Activate your Python 3.11 virtual environment if you already created one in the project root.

```cmd
python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env` with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, and `FRONTEND_ORIGIN=http://localhost:5173`.

Run:
```cmd
uvicorn main:app --reload --port 8000
```
Check `http://127.0.0.1:8000/health`.

### 3. Frontend
Open a second CMD window in `frontend`:
```cmd
npm.cmd install
copy .env.example .env
npm.cmd run dev
```
Open the local URL printed by Vite (normally `http://localhost:5173`).

## Deploy

### Render
- Create a **Web Service** from the public GitHub repository.
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/health`
- Environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `FRONTEND_ORIGIN` (the deployed Vercel URL).

### Vercel
- Import the same GitHub repository.
- Root Directory: `frontend`
- Framework preset: Vite
- Environment variable: `VITE_API_BASE_URL` = the deployed Render base URL, with no trailing slash.

After Vercel deployment, set Render's `FRONTEND_ORIGIN` to the Vercel URL and redeploy Render if needed.

## API endpoints
- `GET /health` — health check
- `GET /stages` — eight stages
- `POST /calls` — start a call
- `POST /calls/{call_id}/stage-results` — save a stage result
- `POST /calls/{call_id}/close` — close call and optionally generate AI summary
- `GET /calls` — list past calls
- `GET /calls/{call_id}` — retrieve call and stage history

## Notes
- Stage phrases in the interface are representative examples inspired by the task's 100-call dataset; they are not claimed as exact frequency rankings.
- The prospect's stage-5 wording is stored separately and passed through to the final call record.
- Do not commit `.env` files or expose the Supabase service-role key in the frontend.
- The app is an MVP; verify the full flow with test records before submitting.
