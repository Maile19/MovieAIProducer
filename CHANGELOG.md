# Changelog - MovieAIProducer

> Release history and change management log for the MovieAIProducer platform.

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Change Categories

- **Added:** New user-facing or architectural features.
- **Changed:** Modifications to existing functionality or data structures.
- **Deprecated:** Features slated for removal in future releases.
- **Removed:** Removed features or deleted deprecated APIs.
- **Fixed:** Bug fixes and defect remediations.
- **Security:** Vulnerability patches and credential handling updates.
- **Database:** Schema migrations, index alterations, and data integrity modifications.
- **Infrastructure:** CI/CD pipeline, build tooling, deployment manifests, and runtime dependencies.

---

## [Unreleased]

### Planned (Phase 1 Foundation & Phase 2 Project Management)
- **Asset Storage (`TASK-007`):** Abstract storage repository supporting local filesystem and S3-compatible object storage with SHA-256 checksum verification.
- **Project Entity CRUD (`TASK-008`):** Project aggregate root, lifecycle state transitions (`Draft`, `Active`, `Archived`), and repository persistence.
- **Creative Brief (`TASK-009`):** Creative brief domain models for Genre, Emotion, and Aspect Ratio (16:9 / 9:16).
- **Project Dashboard (`TASK-010`):** Service aggregating production stage progress and resource health metrics.

---

## [0.1.0] - 2026-11-19

### Overview
Initial foundation release establishing Clean Architecture boundaries, asynchronous database persistence, FastAPI application bootstrap, and 50 automated verification tests. Completes Phase 0 (Repository Discovery) and Tasks 001 through 006 of Phase 1 (Foundation).

### Added
- **FastAPI Application Bootstrap (`TASK-004`):** Entry point in `backend/app/main.py` configured with structured JSON logging (`structlog`), CORS middleware, and environment validation via `pydantic-settings`.
- **System Health Endpoints (`TASK-004`):** Production health check at `/health` providing application status, database connectivity verification, latency metrics, and version telemetry.
- **Clean Architecture Foundation (`TASK-005`):** Structural isolation separating `backend/app/domain`, `backend/app/application`, and `backend/app/infrastructure`. Domain models are completely isolated from outer framework dependencies.
- **Automated Layer Boundary Tests (`TASK-005`):** Unit test suite in `tests/architecture/test_layer_boundaries.py` enforcing dependency inversion and preventing illegal imports into the domain layer.
- **Asynchronous Database Engine (`TASK-006`):** SQLAlchemy 2.0 async engine configured with `aiosqlite` for high-throughput, non-blocking SQLite database transactions.
- **Unit of Work & Repository Pattern (`TASK-006`):** Transactional Unit of Work implementation (`backend/app/infrastructure/database/unit_of_work.py`) and generic repository contracts managing session lifecycle and ACID consistency.
- **Automated Verification Suite:** 50 automated tests across architecture boundaries, domain primitives, database repositories, migrations, and API health endpoints (`uv run pytest` passing with 100% success).

### Database
- **Initial Foundation Migration (`TASK-006`):** Created migration `migrations/versions/0001_initial_database_foundation.py` establishing foundational metadata schema and Alembic revision tracking.
- **Alembic Configuration (`TASK-006`):** Integrated `alembic.ini` and asynchronous migration runner in `migrations/env.py`.

### Infrastructure
- **Deterministic Package Management (`TASK-002`):** Migrated repository dependencies to `uv` (`pyproject.toml` and `uv.lock`), supporting Python `>=3.12, <3.15`.
- **Code Quality Tooling:** Configured `ruff` for linting and code formatting with an 88-character line limit.
- **Test Configuration:** Configured `pytest` with `anyio` async test plugins and pythonpath resolution.

### Governance
- **Repository Discovery & Audit (`TASK-001`, `TASK-002`, `TASK-003`):** Completed architectural gap analysis, mapped existing modules, and authoritatively resolved Clean Architecture requirements.

---

## Release Traceability Matrix

| Version | Release Date | Git Commit SHA | Primary Tasks | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **0.1.0** | 2026-11-19 | `cad786c` | TASK-001 through TASK-006 | 50 passing tests via `uv run pytest`; clean migration status. |

---

## Release Quality Gates

A release is approved for tagging and deployment only when all following gates pass:
1. **Automated Test Suite:** Zero test failures across unit, integration, and architecture test suites (`uv run pytest`).
2. **Layer Boundary Verification:** Zero domain layer boundary violations (`tests/architecture/test_layer_boundaries.py`).
3. **Database Migration Verification:** Schema migrations apply cleanly from empty state and support reversible rollbacks (`uv run pytest tests/infrastructure/test_database_migrations.py`).
4. **Code Quality Inspection:** Zero unresolved errors from `uv run ruff check .` and formatting verification with `uv run ruff format --check .`.
5. **Documentation Alignment:** `ROADMAP.md`, `TASKS.md`, and `CHANGELOG.md` are synchronized with actual codebase capabilities.
