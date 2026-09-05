# HomeStock — Project Conventions

A self-hosted home inventory system. It runs on Unraid through Docker.
The full specification is in [docs/architecture.md](docs/architecture.md).

## Repository layout

| Path | Contents | Owner phase |
|---|---|---|
| `backend/` | FastAPI application, SQLAlchemy models, Alembic migrations | 1, 2a |
| `frontend/` | React + TypeScript + Vite web interface | 2b |
| `mobile/` | React Native + Expo application | 2c |
| `docker/` | Dockerfile, Dockerfile.dev, docker-compose.yml | 1, 3 |
| `unraid/` | Unraid Community Applications template | 1, 3 |
| `docs/` | Architecture specification and the generated OpenAPI file | 1 |
| `scripts/` | Standalone backup and restore shell scripts | 3 |

During phase 2, three sessions can run at the same time. Each session must
change only its own directory. Do not change `docs/openapi.yaml` after phase 1
without telling the other sessions. That file is the shared contract.

## Python

- Target Python 3.12.
- Use `ruff` for linting and formatting.
- Write async code everywhere. Use `async def` for all route handlers and all
  database access.
- Type hints are required on every function signature.
- Use SQLAlchemy 2.0 style. Use `Mapped[]` and `mapped_column()`.

## API

- Every response uses the same envelope: `{"data": ..., "error": null}`.
- On failure the envelope becomes `{"data": null, "error": {...}}`.
- All routes live under the `/api` prefix.
- OpenAPI documentation is at `/api/docs`.

## Database

- Primary keys are UUIDs.
- Every table has `created_at` and `updated_at`.
- Every table that the mobile application syncs also has a `version` counter.
- Alembic runs on container start, before uvicorn starts.

## Authentication

- JWT with an access token and a refresh token.
- Hash passwords with bcrypt.

## File uploads

- Uploads go to `{HS_UPLOAD_DIR}/{items|receipts|locations}/{id}/`.
- Generate thumbnails at 200 px and 600 px width on upload.
- Resize the original to a maximum of 2000 px.
- Remove EXIF GPS data from every uploaded image.

## Environment variables

Read the `HS_` prefixed name first. If it is not set, fall back to the bare
name. Example: read `HS_SECRET_KEY`, then `SECRET_KEY`.

The fallback exists because the Unraid Community Applications template uses
bare names, and the architecture specification uses the `HS_` prefix. Both
must work. See [.env.example](.env.example) for the full list.

Put this behaviour in one place, in `backend/app/config.py`. Do not repeat the
fallback logic in other modules.

## Frontend

- Use functional components only.
- Use TanStack Query for data fetching.
- Use Zustand for client state.
- Use Tailwind CSS. Support light mode and dark mode with `dark:` classes.
- Use Lucide for icons.

## Mobile

- Use Expo Router for navigation.
- Use `expo-sqlite` for the offline cache.
- Store the JWT in `expo-secure-store`.
- All reads must work offline. Queue writes and sync them later.

## AI on a CPU

**This server has no GPU.** Every model runs on the CPU. That constraint
shapes three decisions. Do not undo them without measuring first.

1. **Small models are the default.** The vision model is `moondream` (1.8B),
   not `llava` (7B). A 7B vision model needs one to two minutes per image on
   a CPU. Set `HS_OLLAMA_VISION_MODEL` to change it.
2. **Receipt parsing uses a text model.** Tesseract reads the image on the
   CPU, then `HS_OLLAMA_TEXT_MODEL` structures the text. Do not send receipt
   images to the vision model. Text inference is several times faster.
3. **The AI routes return a job, not a result.** A request that runs longer
   than `HS_AI_INLINE_TIMEOUT` seconds returns 202 with a job id, and the
   client polls `GET /api/ai/jobs/{job_id}`. A synchronous 90 second request
   dies at the reverse proxy.

Keep `OLLAMA_KEEP_ALIVE` long. On a CPU, loading a model from disk costs more
time than the inference does.

## Resolved decisions

1. **The Unraid template maps no database path.** A Community Applications
   template installs one container, but PostgreSQL runs as its own service.
   A `/data/db` mapping would tell the user their database sits on that
   share when nothing writes there. The template asks for `HS_DATABASE_URL`
   instead, and the overview names the PostgreSQL 16 prerequisite.
   `docker-compose.yml` still holds the volume, so Compose stays one command.
2. **Ollama stays a service in `docker-compose.yml`.** A comment at the top
   of the file explains how to point at an existing instance. A fourth
   service, `ollama-init`, sits behind the `setup` profile and pulls the
   models.

## Two columns that the specification does not list

`version` and `deleted_at` sit on every table that the mobile application
mirrors. The sync contract needs both.

A hard delete cannot reach the mobile client, because a delta query returns
nothing for a row that no longer exists. Every query that returns user
content must therefore filter on `deleted_at IS NULL`.

## Working in parallel

Two sessions can write the same file and the last write wins. Before you
start a parallel session:

1. Commit first. An uncommitted overwrite cannot be recovered.
2. Keep each session inside its own directory, as the table above sets out.
3. Do not run `ruff --fix` or any repository wide rewrite while another
   session writes. It will edit files that the other session owns.
