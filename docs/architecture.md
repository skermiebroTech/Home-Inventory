# Home Inventory System — Architecture & Build Guide

## Project Overview

A self-hosted home inventory system running on Unraid via Docker. Designed for simplicity, with AI image recognition, receipt scanning, a cross-platform mobile app, and easy backup/export. Installable and updatable through the Unraid Community Applications Docker page.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | **Python / FastAPI** | Fast to build, strong AI/ML library ecosystem, async, auto-generated OpenAPI docs |
| Database | **PostgreSQL 16** | Robust, JSON fields for flexible metadata, full-text search built in |
| Migrations | **Alembic** | Auto-migration on container startup, version-tracked schema changes |
| File Storage | **Local filesystem** (mapped Unraid volume) | Simple, fast, no object-store overhead, easy to backup with standard tools |
| Web Frontend | **React + TypeScript + Vite** | Fast dev cycle, huge ecosystem, serves as admin/desktop interface |
| Mobile App | **React Native + Expo** | Cross-platform iOS + Android from one codebase, Expo handles builds and OTA updates |
| AI — Image Recognition | **Ollama (LLaVA / Llama 3.2 Vision)** | Runs locally on your Unraid box, no cloud API costs, private |
| AI — Receipt OCR | **Tesseract + vision model fallback** | Tesseract for text extraction, vision model for structured parsing of vendor/date/items |
| Reverse Proxy | **Unraid's built-in Nginx or Swag** | HTTPS termination, already running on your server |
| Barcode Lookup | **Open Food Facts API + UPCitemdb** | Free product databases, auto-fill item details from barcode scan |

---

## Container Architecture

```
┌─────────────────────────────────────────────────┐
│  Unraid Docker                                  │
│                                                 │
│  ┌──────────────────────┐  ┌──────────────────┐ │
│  │  home-inventory      │  │  ollama          │ │
│  │  (API + Web UI)      │  │  (AI inference)  │ │
│  │  Port: 7850          │──│  Port: 11434     │ │
│  │                      │  │                  │ │
│  │  FastAPI backend     │  │  LLaVA model     │ │
│  │  React frontend      │  │                  │ │
│  │  (served as static)  │  │                  │ │
│  └──────────┬───────────┘  └──────────────────┘ │
│             │                                   │
│  ┌──────────┴───────────┐                       │
│  │  PostgreSQL 16       │                       │
│  │  Port: 5432 internal │                       │
│  └──────────────────────┘                       │
│                                                 │
│  Volumes:                                       │
│  /mnt/user/appdata/home-inventory/db            │
│  /mnt/user/appdata/home-inventory/uploads       │
│  /mnt/user/appdata/home-inventory/backups       │
│  /mnt/user/appdata/home-inventory/config        │
└─────────────────────────────────────────────────┘
```

**Single `docker-compose.yml`** defines all three services. The main container bundles the API and pre-built React frontend. Ollama runs as a sidecar — if the user already has Ollama on Unraid, the app can point to the existing instance instead.

---

## Database Schema (Core Tables)

```
users
  id, email, name, password_hash, role, created_at

locations
  id, user_id, parent_id (nullable, self-ref), name, type (room/zone/container), 
  description, photo_path, sort_order

items
  id, user_id, location_id, name, description, category, subcategory,
  brand, model, serial_number, barcode, purchase_price, current_value,
  purchase_date, purchase_location, warranty_expires, condition,
  quantity, notes, is_lent, lent_to, lent_date, created_at, updated_at

item_photos
  id, item_id, file_path, thumbnail_path, is_primary, ai_description, created_at

receipts
  id, user_id, file_path, thumbnail_path, vendor, purchase_date, total_amount,
  currency, ocr_raw_text, ocr_parsed_json, created_at

receipt_items (links receipts to inventory items)
  id, receipt_id, item_id, line_text, line_amount

tags
  id, name, color

item_tags
  item_id, tag_id

maintenance_logs
  id, item_id, description, date_performed, next_due_date, cost, notes

custom_fields
  id, item_id, field_name, field_value

nfc_tags
  id, item_id OR location_id, nfc_uid, label
```

---

## API Routes

```
Auth
  POST   /api/auth/register
  POST   /api/auth/login
  POST   /api/auth/refresh
  GET    /api/auth/me

Items
  GET    /api/items                    (list, filter, search, paginate)
  POST   /api/items                    (create)
  GET    /api/items/:id
  PUT    /api/items/:id
  DELETE /api/items/:id
  POST   /api/items/:id/photos         (upload photos)
  DELETE /api/items/:id/photos/:photoId
  POST   /api/items/bulk               (bulk create from AI scan)
  GET    /api/items/search?q=          (fuzzy full-text search)

Locations
  GET    /api/locations                (tree structure)
  POST   /api/locations
  PUT    /api/locations/:id
  DELETE /api/locations/:id

Receipts
  POST   /api/receipts/upload          (upload + trigger OCR)
  GET    /api/receipts
  GET    /api/receipts/:id
  PUT    /api/receipts/:id             (edit parsed data)
  POST   /api/receipts/:id/link/:itemId

AI
  POST   /api/ai/recognize             (photo → item suggestions)
  POST   /api/ai/receipt-parse          (receipt image → structured data)
  POST   /api/ai/bulk-scan             (multi-item photo → item list)
  GET    /api/ai/status                (model loaded, GPU available, etc.)

Tags
  GET    /api/tags
  POST   /api/tags
  PUT    /api/tags/:id
  DELETE /api/tags/:id

Maintenance
  GET    /api/items/:id/maintenance
  POST   /api/items/:id/maintenance
  PUT    /api/maintenance/:id
  GET    /api/maintenance/upcoming      (next 30 days)

Lending
  POST   /api/items/:id/lend
  POST   /api/items/:id/return
  GET    /api/items/lent                (all currently lent items)

NFC
  POST   /api/nfc/register
  GET    /api/nfc/:uid                  (lookup by NFC tag UID)

Labels
  GET    /api/items/:id/qr              (generate QR code PNG)
  GET    /api/locations/:id/qr

Export / Backup
  GET    /api/export/full               (ZIP: db dump + all images + metadata JSON)
  GET    /api/export/csv                (items as CSV)
  GET    /api/export/insurance-report   (PDF report with photos and values)
  POST   /api/backup/schedule           (configure auto-backup to Unraid share or rclone target)
  GET    /api/backup/status

Sync (for mobile offline-first)
  GET    /api/sync/changes?since=       (delta sync endpoint)
  POST   /api/sync/push                 (upload offline changes)

Health
  GET    /api/health                    (for Unraid Docker status check)
```

---

## Mobile App Architecture (React Native + Expo)

```
Features:
- Camera integration for item photos and receipt capture
- Barcode scanner (expo-barcode-scanner)
- NFC read/write (react-native-nfc-manager)
- Offline-first with local SQLite (expo-sqlite)
- Background sync when connectivity returns
- Push notifications for warranty expiry, maintenance due, lending reminders
- Quick-add: snap photo → AI suggests name/category → confirm → saved
- Receipt scan: snap receipt → OCR → parsed items → link to inventory

Sync strategy:
- Each record has a `version` counter and `updated_at` timestamp
- On sync, client sends its last sync timestamp
- Server returns all changes since that timestamp
- Conflicts resolved by last-write-wins with server as authority
- Photos queued for upload over WiFi to avoid mobile data drain
```

---

## AI Pipeline

```
Image Recognition Flow:
1. User snaps photo on phone or web
2. Photo uploaded to /api/ai/recognize
3. Backend sends image to Ollama (LLaVA) with prompt:
   "Identify all objects in this image. For each, provide:
    name, likely brand, category, estimated value AUD.
    Return as JSON array."
4. Backend parses response, returns suggested items
5. User confirms/edits, items created in database

Receipt OCR Flow:
1. User photographs receipt
2. Image sent to /api/receipts/upload
3. Backend runs Tesseract for raw text extraction
4. Raw text + image sent to Ollama vision model with prompt:
   "Parse this receipt. Extract: store name, date, each line item
    (name, quantity, unit price, total), subtotal, tax, grand total.
    Return as JSON."
5. Parsed data shown to user for confirmation
6. User links line items to existing or new inventory items

Bulk Scan Flow:
1. User takes photo of shelf/drawer/area
2. Sent to /api/ai/bulk-scan
3. Vision model identifies multiple items
4. Returns list of suggested items with bounding regions
5. User reviews list, confirms or removes, all created at once
```

---

## Unraid Integration

### Docker Template XML (for Community Applications)

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>HomeInventory</Name>
  <Repository>ghcr.io/YOUR_USERNAME/home-inventory:latest</Repository>
  <Registry>https://ghcr.io/YOUR_USERNAME/home-inventory</Registry>
  <Branch>
    <Tag>latest</Tag>
    <TagDescription>Latest stable release</TagDescription>
  </Branch>
  <Branch>
    <Tag>beta</Tag>
    <TagDescription>Beta release with newest features</TagDescription>
  </Branch>
  <Network>bridge</Network>
  <Privileged>false</Privileged>
  <Support>https://github.com/YOUR_USERNAME/home-inventory/issues</Support>
  <Overview>
    Self-hosted home inventory system with AI image recognition, receipt scanning,
    mobile app sync, QR/NFC labels, warranty tracking, and insurance reports.
  </Overview>
  <Category>HomeAutomation: Tools:</Category>
  <WebUI>http://[IP]:[PORT:7850]</WebUI>
  <Icon>https://raw.githubusercontent.com/YOUR_USERNAME/home-inventory/main/icon.png</Icon>
  <ExtraParams>--restart=unless-stopped</ExtraParams>

  <Config Name="Web UI Port" Target="7850" Default="7850" Mode="tcp"
    Type="Port" Display="always" Required="true">7850</Config>

  <Config Name="Database" Target="/data/db" Default="/mnt/user/appdata/home-inventory/db"
    Mode="rw" Type="Path" Display="always" Required="true">/mnt/user/appdata/home-inventory/db</Config>

  <Config Name="Uploads" Target="/data/uploads" Default="/mnt/user/appdata/home-inventory/uploads"
    Mode="rw" Type="Path" Display="always" Required="true">/mnt/user/appdata/home-inventory/uploads</Config>

  <Config Name="Backups" Target="/data/backups" Default="/mnt/user/appdata/home-inventory/backups"
    Mode="rw" Type="Path" Display="always" Required="true">/mnt/user/appdata/home-inventory/backups</Config>

  <Config Name="Config" Target="/data/config" Default="/mnt/user/appdata/home-inventory/config"
    Mode="rw" Type="Path" Display="always" Required="true">/mnt/user/appdata/home-inventory/config</Config>

  <Config Name="Ollama URL" Target="OLLAMA_URL" Default="http://host.docker.internal:11434"
    Type="Variable" Display="always" Required="false">http://host.docker.internal:11434</Config>

  <Config Name="Secret Key" Target="SECRET_KEY" Default="CHANGE_ME_TO_RANDOM_STRING"
    Type="Variable" Display="always" Required="true">CHANGE_ME_TO_RANDOM_STRING</Config>

  <Config Name="PUID" Target="PUID" Default="99" Type="Variable" Display="advanced">99</Config>
  <Config Name="PGID" Target="PGID" Default="100" Type="Variable" Display="advanced">100</Config>
  <Config Name="TZ" Target="TZ" Default="Australia/Brisbane" Type="Variable" Display="always">Australia/Brisbane</Config>
</Container>
```

### Update path
- Push tagged images to GHCR: `v1.0.0`, `v1.1.0`, `latest`
- Unraid CA checks the image digest periodically
- User sees "update available" on Docker tab, clicks Apply
- New container starts, Alembic runs migrations automatically
- Data safe in mapped volumes, nothing lost

---

## Backup System

```
Manual:
  GET /api/export/full → downloads a ZIP containing:
    - database.sql (pg_dump)
    - uploads/ (all photos and receipt images)
    - metadata.json (schema version, item count, export date)
    - inventory-report.csv

Scheduled:
  - Configurable via web UI settings page
  - Cron job inside container runs at user-set interval
  - Writes ZIP to /data/backups/ (mapped to Unraid share)
  - Optional: push to rclone target (Backblaze B2, S3, Google Drive, etc.)
  - Retention policy: keep last N backups, delete older

Restore:
  POST /api/backup/restore (upload ZIP)
  - Validates schema version compatibility
  - Restores database and uploads
  - Runs any needed migrations
```

---

## Recommended AI Model for Claude Code

**Use Opus** — it's the default model Claude Code uses for the main agent. For a project this size and complexity (multi-service Docker app, full API, React frontend, React Native mobile app, AI integration), Opus handles the architectural decisions and large file generation best.

If you want to use Claude Code's sub-agent feature (`/compact` or background tasks), those already default to Sonnet for speed, which is fine for smaller focused tasks.

---

## Parallel Claude Code Sessions

**Yes — this project benefits from parallel sessions, but only after phase 1.**

The constraint is that the backend API contract must exist before the frontend and mobile app can be built against it. So:

### Phase 1 — Sequential (one session)
Generate the project skeleton, database schema, API routes, OpenAPI spec, Docker setup, and Alembic migrations. This is the shared foundation everything else depends on.

### Phase 2 — Parallel (three sessions simultaneously)

Open three terminal tabs, `cd` into the same repo, and run Claude Code in each:

| Terminal | Focus | Prompt suffix |
|---|---|---|
| Tab 1 | Backend API implementation | "Implement all API route handlers, database models, and the AI/OCR pipeline. Do not modify files in /frontend or /mobile." |
| Tab 2 | React web frontend | "Build the React web frontend against the OpenAPI spec in /docs/openapi.yaml. Do not modify files in /backend or /mobile." |
| Tab 3 | React Native mobile app | "Build the React Native Expo mobile app against the OpenAPI spec in /docs/openapi.yaml. Do not modify files in /backend or /frontend." |

Each session works in its own directory subtree so there are no file conflicts. They all code against the same API contract from phase 1.

### Phase 3 — Sequential (one session)
Integration testing, Docker compose wiring, Unraid template, CI/CD pipeline, final polish.

---

## Claude Code Prompt — Phase 1 (Foundation)

Copy everything below the line into Claude Code as your first prompt. It will generate the project skeleton and shared contracts.

---

```
I'm building a self-hosted home inventory system called "HomeStock". Here is the full architecture spec — follow it exactly.

PROJECT STRUCTURE:
homestock/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              (FastAPI app, startup, CORS, static mount)
│   │   ├── config.py            (settings from env vars)
│   │   ├── database.py          (async SQLAlchemy engine + session)
│   │   ├── models/              (SQLAlchemy ORM models)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── item.py
│   │   │   ├── location.py
│   │   │   ├── receipt.py
│   │   │   ├── tag.py
│   │   │   ├── maintenance.py
│   │   │   ├── nfc.py
│   │   │   └── custom_field.py
│   │   ├── schemas/             (Pydantic request/response schemas)
│   │   │   └── (mirrors models/)
│   │   ├── routers/             (FastAPI route handlers)
│   │   │   ├── auth.py
│   │   │   ├── items.py
│   │   │   ├── locations.py
│   │   │   ├── receipts.py
│   │   │   ├── ai.py
│   │   │   ├── tags.py
│   │   │   ├── maintenance.py
│   │   │   ├── lending.py
│   │   │   ├── nfc.py
│   │   │   ├── labels.py
│   │   │   ├── export.py
│   │   │   ├── backup.py
│   │   │   ├── sync.py
│   │   │   └── health.py
│   │   ├── services/            (business logic)
│   │   │   ├── ai_service.py    (Ollama integration)
│   │   │   ├── ocr_service.py   (Tesseract + vision model receipt parsing)
│   │   │   ├── barcode_service.py (OpenFoodFacts/UPCitemdb lookup)
│   │   │   ├── backup_service.py
│   │   │   ├── export_service.py
│   │   │   └── sync_service.py
│   │   └── utils/
│   │       ├── auth.py          (JWT, password hashing)
│   │       ├── qr.py            (QR code generation)
│   │       └── thumbnails.py    (image resize on upload)
│   ├── alembic/                 (migrations)
│   ├── alembic.ini
│   ├── requirements.txt
│   └── entrypoint.sh            (run migrations then start uvicorn)
├── frontend/                    (React + TypeScript + Vite)
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── mobile/                      (React Native + Expo)
│   ├── app/
│   ├── package.json
│   └── app.json
├── docker/
│   ├── Dockerfile               (multi-stage: build frontend, copy into Python image)
│   ├── Dockerfile.dev           (hot-reload dev setup)
│   └── docker-compose.yml       (app + postgres + ollama)
├── unraid/
│   └── home-inventory.xml       (Unraid CA template)
├── docs/
│   ├── openapi.yaml             (generated from FastAPI, committed for mobile/frontend reference)
│   └── README.md
├── scripts/
│   ├── backup.sh
│   └── restore.sh
├── CLAUDE.md                    (project conventions for Claude Code)
├── .env.example
├── .gitignore
└── README.md

PHASE 1 TASKS — do all of these now:

1. Create the full directory structure above with placeholder files.

2. Write CLAUDE.md with these conventions:
   - Python: use ruff for linting, async everywhere, type hints required
   - All API responses use consistent envelope: {"data": ..., "error": null}
   - File uploads go to /data/uploads/{items|receipts|locations}/{id}/
   - Thumbnails auto-generated at 200px and 600px widths on upload
   - Database: use UUID primary keys, all tables have created_at and updated_at
   - Auth: JWT with access + refresh tokens, bcrypt password hashing
   - Environment variables prefixed with HS_ (e.g. HS_SECRET_KEY, HS_OLLAMA_URL)
   - Frontend: functional components only, TanStack Query for data fetching, Zustand for state
   - Mobile: Expo Router for navigation, expo-sqlite for offline cache

3. Implement all SQLAlchemy models matching the database schema in the architecture doc. Include:
   - users, locations (self-referential parent_id for tree), items, item_photos, receipts, receipt_items, tags, item_tags, maintenance_logs, custom_fields, nfc_tags
   - All relationships and cascading deletes
   - Full-text search index on items (name, description, brand, model, notes)

4. Write all Pydantic schemas (create, update, response) for every model.

5. Create the initial Alembic migration from the models.

6. Write the FastAPI main.py with:
   - CORS configured for local network access
   - Static file serving for the built frontend
   - Startup event that runs Alembic migrations
   - Health check endpoint at /api/health
   - OpenAPI docs at /api/docs

7. Write stub routers for every route group (auth, items, locations, receipts, ai, tags, maintenance, lending, nfc, labels, export, backup, sync, health). Each route should have the correct method, path, request/response schemas, and a "not implemented" placeholder body.

8. Write docker-compose.yml with three services:
   - app: builds from Dockerfile, ports 7850:7850, volumes for db/uploads/backups/config, env vars from .env
   - postgres: postgres:16-alpine, data volume, internal only
   - ollama: ollama/ollama:latest, port 11434 internal, model volume
   Include a healthcheck on the app service hitting /api/health.

9. Write the multi-stage Dockerfile:
   - Stage 1: node:20-alpine, build the React frontend
   - Stage 2: python:3.12-slim, install requirements, copy backend + built frontend, entrypoint.sh

10. Write entrypoint.sh: run alembic upgrade head, then exec uvicorn.

11. Write the Unraid CA template XML from the architecture doc.

12. Write .env.example with all configurable vars and sensible defaults for Unraid.

13. Generate the OpenAPI spec to docs/openapi.yaml by adding a script that starts the app and dumps the spec.

Do NOT implement the actual business logic in the route handlers yet — that's phase 2. Focus on getting the full skeleton compilable, the database migratable, the Docker stack bootable, and the API contract locked down.
```

---

## Claude Code Prompt — Phase 2a (Backend Implementation)

```
Continue building HomeStock. The project skeleton, models, schemas, and stub routers are in place.

Implement ALL backend route handlers with full business logic. Work only in /backend — do not touch /frontend or /mobile.

Priority order:
1. Auth (register, login, refresh, JWT middleware)
2. Locations (CRUD, tree structure queries, move location)
3. Items (CRUD, search with PostgreSQL full-text, filtering, pagination, photo upload with auto-thumbnailing)
4. Tags (CRUD, assign/remove from items)
5. AI service (Ollama integration — recognize items from photo, bulk scan, configurable model name via env var, graceful fallback if Ollama unavailable)
6. Receipts (upload, OCR with Tesseract, structured parsing via Ollama vision, link to items)
7. Barcode service (scan barcode → lookup OpenFoodFacts API → return product info → optional auto-create item)
8. Labels (QR code generation as PNG for items and locations)
9. NFC (register tag UID to item or location, lookup by UID)
10. Maintenance (CRUD, upcoming maintenance query)
11. Lending (lend item, return item, list all lent)
12. Export (full ZIP backup, CSV export, insurance PDF report with ReportLab)
13. Backup (scheduled backup via APScheduler, configurable interval, rclone push support)
14. Sync (delta sync endpoint — return all changes since timestamp, accept pushed changes with conflict resolution)
15. Health (return service status, DB connection, Ollama reachability, disk usage)

For the AI service, use this Ollama prompt for image recognition:
"You are a home inventory assistant. Analyze this image and identify every distinct item visible. For each item return a JSON array of objects with: name, brand (if visible, else null), category, subcategory, estimated_value_aud (number), condition (new/good/fair/poor). Be specific — say 'DeWalt DCD771 cordless drill' not just 'drill'."

For receipt OCR, the prompt should be:
"Parse this receipt image. Return JSON with: store_name, date (YYYY-MM-DD), items (array of {name, quantity, unit_price, total}), subtotal, tax, grand_total, currency. If any field is unreadable, use null."

Write tests for auth, items CRUD, and the sync endpoint using pytest + httpx.
```

## Claude Code Prompt — Phase 2b (Web Frontend)

```
Continue building HomeStock. The project skeleton and OpenAPI spec are in place at /docs/openapi.yaml.

Build the React web frontend in /frontend. Do not touch /backend or /mobile.

Tech: React 18, TypeScript, Vite, TanStack Query, Zustand, React Router, Tailwind CSS.

Pages to build:
1. Login / Register
2. Dashboard — overview cards (total items, total value, items by room, recent additions, upcoming maintenance, lent items count)
3. Items — searchable/filterable grid or list view with thumbnails, click to expand details
4. Item Detail — full info, photo gallery, linked receipts, maintenance log, edit inline
5. Add Item — form with camera/upload for photo, barcode scanner button (calls API), AI recognize button
6. Locations — tree view (rooms → zones → containers), click to see items in that location, drag to move
7. Receipts — upload page, shows OCR results for confirmation, link items
8. Tags — manage tags, filter items by tag
9. Maintenance — upcoming maintenance calendar/list view
10. Lending — who has what, return button
11. Labels — print QR codes for items or locations (generate and display, browser print)
12. Settings — backup controls (manual download, schedule, rclone config), user profile, Ollama status
13. Export — download CSV, full backup ZIP, generate insurance report PDF

Design direction:
- Clean, minimal UI. Think Notion meets a utility app — functional over decorative.
- Light and dark mode via Tailwind's dark: classes, toggle in header.
- Mobile-responsive — this doubles as the tablet/phone-in-browser experience.
- Snappy interactions — optimistic updates with TanStack Query mutations.
- Photo uploads show instant preview before saving.
- Search bar in the header, always accessible, with fuzzy matching and category filters.
- Use Lucide icons, no heavy icon libraries.

API client: generate a typed fetch wrapper from the OpenAPI spec using openapi-typescript-codegen or write a thin typed client manually. All API calls go through TanStack Query hooks.
```

## Claude Code Prompt — Phase 2c (Mobile App)

```
Continue building HomeStock. The project skeleton and OpenAPI spec are in place at /docs/openapi.yaml.

Build the React Native mobile app in /mobile using Expo (SDK 52+, Expo Router). Do not touch /backend or /frontend.

Core requirements:
- Offline-first: local SQLite database (expo-sqlite) mirrors server state
- Background sync when online (expo-background-fetch or on app foreground)
- Camera integration (expo-camera) for item photos and receipt capture
- Barcode scanner (expo-barcode-scanner or expo-camera barcode scanning)
- NFC read/write (react-native-nfc-manager) for tag registration and lookup
- Push notifications (expo-notifications) for warranty expiry, maintenance due, lending reminders

Screens (Expo Router file-based routing):
1. (auth)/login — server URL input + email/password, stores JWT in SecureStore
2. (tabs)/home — dashboard with stats cards, recent items, quick actions
3. (tabs)/items — searchable list with thumbnails, pull-to-refresh, infinite scroll
4. (tabs)/scan — camera view with three modes: Photo (single item AI), Barcode, Receipt
5. (tabs)/more — locations tree, tags, maintenance, lending, settings
6. items/[id] — item detail, photo gallery (swipeable), edit, maintenance log
7. items/add — add form, pre-filled if coming from AI scan or barcode lookup
8. receipts/[id] — receipt viewer with parsed data, link items

Quick-add flow (the money feature):
1. User taps the scan tab, points camera at an item
2. Snaps photo → sent to /api/ai/recognize
3. AI returns suggested name, category, brand, value
4. User sees pre-filled form, adjusts if needed, picks location from dropdown
5. Taps save → item created with photo attached
6. Whole flow takes under 10 seconds for a single item

Sync strategy:
- On app open: GET /api/sync/changes?since={last_sync_timestamp}
- Apply server changes to local SQLite
- Push any locally queued creates/edits/deletes via POST /api/sync/push
- Photos queued separately, uploaded over WiFi only (configurable)
- Conflict resolution: server wins, but show user a "conflict resolved" toast if their edit was overwritten

Offline behavior:
- All reads work offline from SQLite
- Creates and edits queued with a "pending sync" badge
- Photo thumbnails cached locally, full-res fetched on demand
- Barcode lookup requires connectivity (show offline message)
- AI recognition requires connectivity (show offline message)

Design: match the web UI's clean/minimal aesthetic. Use React Native Paper or Tamagui for consistent components. Support iOS and Android.

Configure app.json for Expo EAS builds. Include build profiles for development, preview, and production.
```

---

## Claude Code Prompt — Phase 3 (Integration & Polish)

```
HomeStock backend, frontend, and mobile app are built. Now wire everything together and polish for release.

Tasks:
1. Verify docker-compose.yml works end-to-end: app + postgres + ollama all start, migrations run, frontend loads, API responds, AI recognition works.

2. Write a GitHub Actions CI pipeline (.github/workflows/):
   - On push to main: lint (ruff), test (pytest), build Docker image, push to GHCR with :latest and :vX.Y.Z tags
   - On PR: lint + test only

3. Write scripts/backup.sh and scripts/restore.sh that work standalone (outside Docker) for manual Unraid backup scenarios.

4. Create a first-run setup wizard in the frontend:
   - Detect if no users exist → show registration
   - Prompt to set up first location (e.g. "Home" with rooms)
   - Check Ollama connectivity, offer to skip AI features if unavailable
   - Generate SECRET_KEY if still set to default

5. Write a comprehensive README.md with:
   - One-command Docker Compose quickstart
   - Unraid CA installation instructions
   - Screenshots (placeholder paths)
   - Environment variable reference
   - Backup and restore guide
   - Mobile app build instructions
   - Architecture overview for contributors

6. Validate the Unraid CA template XML works by checking it against the Unraid template schema.

7. Add rate limiting on auth endpoints (slowapi).

8. Add image compression on upload (Pillow — strip EXIF GPS data for privacy, resize originals to max 2000px, generate 200px and 600px thumbnails).

9. Test the full quick-add flow: mobile camera → AI recognize → pre-filled form → save → syncs to web UI.

10. Test the receipt flow: mobile camera → upload → OCR → parsed data → link items → visible on web.
```
