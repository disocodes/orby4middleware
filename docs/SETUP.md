# Setup and Upgrade Semantics

orby4middleware setup is intentionally idempotent. Re-running setup must not blindly recreate resources that already exist.

## Linux

```bash
./scripts/setup.sh
```

Preview decisions without changing anything:

```bash
./scripts/setup.sh --dry-run
```

Enable optional services:

```bash
./scripts/setup.sh --profile imaging
./scripts/setup.sh --profile fhir
./scripts/setup.sh --profile imaging --profile fhir
```

Reuse an externally managed resource:

```bash
./scripts/setup.sh --skip-service postgres
./scripts/setup.sh --profile imaging --skip-service orthanc
```

When skipping PostgreSQL, configure `ORBY_DATABASE_URL`/`.env` to point at the external database before starting the Orby service.

Apply changed Compose definitions intentionally:

```bash
./scripts/setup.sh --reconcile
```

## Windows PowerShell

```powershell
./scripts/setup.ps1
./scripts/setup.ps1 -DryRun
./scripts/setup.ps1 -Profile imaging
./scripts/setup.ps1 -SkipService postgres
./scripts/setup.ps1 -Reconcile
```

## Decision rules

Normal setup uses these rules:

| State | Action |
|---|---|
| `.env` already exists | keep it; never overwrite |
| service is already running | `SKIP` |
| service container exists but is stopped | `START` |
| service is missing | `CREATE` |
| service is listed with `--skip-service` | `SKIP` as externally managed |
| `--reconcile` is supplied | explicitly apply the current Compose definition |

The database startup path uses SQLAlchemy `create_all()`, which creates missing tables and does not drop/recreate existing tables.

## Errors are not suppressed

Idempotency does **not** mean ignoring failures.

The Linux helper uses strict shell error handling and prints the failing command/line. The PowerShell helper uses `$ErrorActionPreference = "Stop"` and returns a non-zero exit when a Docker operation fails.

A resource is skipped only because the desired state is already satisfied or because the operator explicitly marked it as externally managed.

## External services

Optional components can be supplied by existing infrastructure instead of Docker Compose. Examples include:

- PostgreSQL;
- Orthanc/PACS;
- HAPI FHIR or another FHIR server;
- an external integration engine such as Open Integration Engine/OpenHIM;
- an existing EMR/LIS HL7 endpoint.

Use `--skip-service` for Compose-managed names and configure the corresponding Orby connection/target settings to point to the external system.
