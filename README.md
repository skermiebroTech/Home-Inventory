# HomeStock

A self-hosted home inventory system for Unraid. It records what you own, where
it is, what it cost, and when it needs service.

## Status

**The foundation is in place.** The database schema, the API contract, and the
Docker stack are done. The route handlers are stubs that answer `501`, and
Phase 2a replaces them.

The server has no GPU, so every AI model runs on the CPU. See the AI section
in [CLAUDE.md](CLAUDE.md) for what that changes.

| Phase | Work | State |
|---|---|---|
| 0 | Repository setup and scaffolding | Done |
| 1 | Models, schemas, migrations, stub routers, Docker stack | Done |
| 2a | Backend business logic | Not started |
| 2b | React web frontend | Not started |
| 2c | React Native mobile application | Not started |
| 3 | Integration, CI, and release polish | Not started |

## Planned features

- AI image recognition. Photograph an item and get a filled-in form.
- Receipt scanning with OCR and structured parsing.
- Barcode lookup against free product databases.
- A location tree: rooms, then zones, then containers.
- QR and NFC labels for items and locations.
- Warranty, maintenance, and lending tracking.
- Insurance reports, CSV export, and full ZIP backups.
- An offline-first mobile application for iOS and Android.

## Documents

- [docs/architecture.md](docs/architecture.md) — the full specification.
- [CLAUDE.md](CLAUDE.md) — coding conventions and open decisions.
- [.env.example](.env.example) — every configurable environment variable.

## Next step

Run the phase 1 prompt from [docs/architecture.md](docs/architecture.md).
