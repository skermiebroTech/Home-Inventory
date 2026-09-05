# HomeStock

A self-hosted home inventory system for Unraid. It records what you own, where
it is, what it cost, and when it needs service.

Photograph an item and a local AI model fills the form. Photograph a receipt
and the server reads it. Print a QR label for a box. Nothing leaves your
server.

![The dashboard](docs/screenshots/dashboard.png)

One item holds its photographs, the parts fitted to it, the service history,
and a log of every change. The coloured squares are test photographs.

![One item](docs/screenshots/item.png)

| | |
|---|---|
| ![The item list](docs/screenshots/items.png) | ![The cables](docs/screenshots/cables.png) |
| ![The spares shelf](docs/screenshots/spares.png) | ![The labels](docs/screenshots/labels.png) |

The phone carries the same data and reads it with no signal.

| | |
|---|---|
| <img src="docs/screenshots/phone-cables.png" width="260" alt="The cables on a phone"> | <img src="docs/screenshots/phone-spares.png" width="260" alt="The spares on a phone"> |

## What it does

- **AI recognition.** Photograph an item, from as many sides as you like. The
  server reads any text it finds first, so a picture of the rating plate gives
  the exact model and the serial number. A model on your own server then names
  the item and guesses the category and the value.
- **Recognition on the phone.** The phone can hold the model itself. It reads
  the photograph with no server and no network, which suits an old server
  with no GPU. One download in the More tab, and it can be deleted again.
- **Receipt reading.** Photograph a receipt. Tesseract reads the text, a model
  turns it into fields, and you link the lines to items.
- **Barcodes.** Scan a product code. HomeStock asks Open Food Facts and
  UPCitemdb, then fills the form.
- **A location tree.** Rooms hold zones. Zones hold containers.
- **QR and NFC labels.** A label opens the record when a phone reads it.
- **Warranty, service, and lending.** Dates that matter, and who has your drill.
- **Reports.** A CSV, a full ZIP backup, and an insurance PDF with photographs.
- **An offline-first phone application.** Every read works with no signal.
  Writes queue and sync later.

## Quick start with Docker Compose

```bash
git clone https://github.com/YOUR_USERNAME/home-inventory.git
cd home-inventory
cp .env.example .env

# Generate a signing key and put it in .env
openssl rand -hex 32

docker compose -f docker/docker-compose.yml up -d
```

Open `http://localhost:7850`. The first visit shows the setup wizard: it makes
the owner account and the first rooms.

The AI features need a model. Pull one once:

```bash
docker compose -f docker/docker-compose.yml --profile setup up ollama-init
```

That downloads `moondream` for images and `llama3.2:3b` for receipt text. Both
are small, because this stack expects a CPU and no GPU.

Already run Ollama on your server? Set `HS_OLLAMA_URL` in `.env` and start
only two services:

```bash
docker compose -f docker/docker-compose.yml up -d app postgres
```

## Install on Unraid

[docs/deploy-unraid.md](docs/deploy-unraid.md) holds the whole sequence for
the Unraid terminal: the directories, the database container, the image build
from this repository, and the check that it works. Follow that file if you
want to copy and paste.

The Docker tab does the same job with the template:

1. Open the **Docker** tab, then **Add Container**.
2. Paste the template URL, or copy [unraid/home-inventory.xml](unraid/home-inventory.xml)
   to `/boot/config/plugins/dockerMan/templates-user/`.
3. Set **Secret Key**. Generate one with `openssl rand -hex 32`.
4. Point **Uploads**, **Backups**, and **Config** at a share, for example
   `/mnt/user/appdata/home-inventory/`.
5. Apply. Unraid pulls the image, and the migrations run on the first start.

HomeStock needs a PostgreSQL 16 server. Run the one from
`docker/docker-compose.yml`, or point `HS_DATABASE_URL` at a server that you
already run.

An update works the same way: Unraid shows "update ready", you click apply,
the new container starts, and Alembic brings the schema forward. The data
stays in the mapped shares.

## Environment variables

Every setting reads the `HS_` prefixed name first. If that name is not set, it
falls back to the bare name, because the Unraid template uses bare names.
[.env.example](.env.example) holds the full list with comments.

| Variable | Default | What it does |
|---|---|---|
| `HS_SECRET_KEY` | *(must change)* | Signs the tokens. |
| `HS_PORT` | `7850` | The port of the web interface. |
| `HS_DATABASE_URL` | `postgresql+asyncpg://homestock:homestock@postgres:5432/homestock` | The database. |
| `HS_UPLOAD_DIR` | `/data/uploads` | Photographs and receipts. |
| `HS_BACKUP_DIR` | `/data/backups` | The archives. |
| `HS_CONFIG_DIR` | `/data/config` | The backup schedule state. |
| `HS_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | The life of an access token. |
| `HS_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | The life of a refresh token. |
| `HS_RATE_LIMIT_AUTH` | `20/minute` | The limit on the sign in routes. |
| `HS_AI_ENABLED` | `true` | Turns every AI route on or off. |
| `HS_OLLAMA_URL` | `http://ollama:11434` | Where Ollama listens. |
| `HS_OLLAMA_VISION_MODEL` | `moondream` | Reads a photograph. |
| `HS_OLLAMA_TEXT_MODEL` | `llama3.2:3b` | Reads receipt text. |
| `HS_AI_INLINE_TIMEOUT` | `8` | Seconds to wait before a scan becomes a job. |
| `HS_IMAGE_MAX_DIMENSION` | `2000` | The longest side of a stored original. |
| `HS_THUMBNAIL_SIZES` | `200,600` | The thumbnail widths, in pixels. |
| `HS_STRIP_EXIF_GPS` | `true` | Removes the position from every upload. |
| `HS_TESSERACT_CMD` | `/usr/bin/tesseract` | Reads the text on a photograph. |
| `HS_BACKUP_ENABLED` | `false` | Turns the scheduled backup on. |
| `HS_BACKUP_CRON` | `0 3 * * *` | When it runs. |
| `HS_BACKUP_RETENTION` | `7` | How many archives to keep. |
| `HS_RCLONE_REMOTE` | *(empty)* | Copies each archive off the server. |
| `HS_CORS_ORIGINS` | `*` | Which origins may call the API. |

## Backup and restore

**From the web interface.** Settings holds the schedule, a Run now button, and
a restore. Export holds a CSV, the full ZIP, and the insurance PDF.

**On a schedule.** Turn the backup on in Settings. The container writes a ZIP
to `/data/backups` at the cron time, keeps the newest few, and copies each one
to your rclone remote when you name one. `rclone` is not in the image; install
it beside the container, or leave the field empty.

**By hand, with the server stopped.**

```bash
set -a; . ./.env; set +a
./scripts/backup.sh -o /mnt/user/backups
./scripts/restore.sh /mnt/user/backups/homestock-backup-20260905-030000.zip
```

Every archive holds `database.sql`, `uploads/`, `inventory-report.csv`, and
`metadata.json`. The restore reads the schema version in `metadata.json` and
refuses an archive that a newer version wrote.

## The phone application

The application is Expo. It works with no signal: every screen reads a local
SQLite copy, and a change waits in a queue until the phone reaches the server.

```bash
cd mobile
npm install
npx expo start          # then open it in Expo Go
```

For a build that carries the camera, NFC, and the notifications:

```bash
npm install -g eas-cli
eas login
eas build --profile development --platform ios     # or android
```

`eas.json` holds three profiles: `development` for a debug build, `preview`
for an APK or a simulator build, and `production` for the store.

Expo Go has no NFC module. NFC needs a development build. Everything else runs
in Expo Go.

On the sign in screen, type the address of your server, for example
`http://192.168.1.20:7850`.

## For contributors

```
backend/    FastAPI, SQLAlchemy 2.0, Alembic. Async everywhere.
frontend/   React, TypeScript, Vite, TanStack Query, Zustand, Tailwind.
mobile/     Expo Router, expo-sqlite, expo-camera.
docker/     The multi-stage image and the Compose stack.
docs/       architecture.md and the generated openapi.yaml.
scripts/    The standalone backup and restore, and the OpenAPI dump.
unraid/     The Community Applications template.
```

Every response uses one envelope: `{"data": ..., "error": null}`. On a failure
`data` is null and `error` carries a stable code. The contract lives in
[docs/openapi.yaml](docs/openapi.yaml), and the two clients read it.

The server has no GPU, so a vision call takes tens of seconds. An AI route
answers 200 with the result when the model was quick, and 202 with a job when
it was not. Both replies use the same shape, so a client needs one code path.

Run the checks:

```bash
cd backend && pip install -r requirements-dev.txt && pytest && ruff check app tests
cd frontend && npm ci && npm run typecheck && npm run build
cd mobile && npm ci && npm run typecheck
```

The test suite needs PostgreSQL, because the models use a UUID primary key,
JSONB, and a generated `tsvector` column. Point `HS_TEST_DATABASE_URL` at a
server, or let the suite start its own through `pgserver`.

After any route change, write the contract again:

```bash
python scripts/dump_openapi.py
```

## Licence

This repository has no licence file yet. Choose one before you publish it,
because without a licence nobody else may use the code.
