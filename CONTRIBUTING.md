# Development & Contribution Guidelines - MovieAIProducer

> Operational standards, Clean Architecture rules, Test-Driven Development (TDD) protocols, and git workflows for human and autonomous AI contributors.

---

## 1. Engineering Principles

MovieAIProducer coordinates complex cinematic AI generation through strict software engineering practices. All contributors—human developers and autonomous AI agents alike—must adhere to these core principles:

1. **Clean Architecture Isolation:** Domain logic represents cinematic production rules and must remain 100% isolated from databases, HTTP frameworks, and third-party AI provider SDKs.
2. **Test-Driven Development (TDD):** Automated tests are authored before or alongside implementation code. Code without test coverage is not merged.
3. **Traceability:** Every modification must trace to a ticket in `TASKS.md` and adhere to an Architecture Decision Record (ADR).
4. **Plan → Execute → Monitor:** Development proceeds through structured planning, disciplined execution, and automated verification.

---

## 2. Development Setup

MovieAIProducer uses [`uv`](https://github.com/astral-sh/uv) for fast, deterministic virtual environments and dependency locking.

### Prerequisites

- Linux or macOS (Ubuntu 22.04+ recommended)
- Python `>=3.12, <3.15`
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git

### Initializing the Workspace

```bash
# 1. Clone the repository
git clone https://github.com/your-org/MovieAIProducer.git
cd MovieAIProducer

# 2. Synchronize virtual environment and dependencies
uv sync

# 3. Create local environment configuration
cp .env.example .env

# 4. Apply database migrations
uv run alembic upgrade head

# 5. Verify local test suite
uv run pytest

# 6. Start the development server
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 3. Clean Architecture Boundary Rules

The codebase is organized into three concentric architectural rings:

```
┌────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                  │
│       (FastAPI, SQLAlchemy, SQLite, Alembic,           │
│        Runway Adapter, Kling Adapter, S3 Storage)      │
│   ┌────────────────────────────────────────────────┐   │
│   │               Application Layer                │   │
│   │         (Pipelines, Prompt Compilation,        │   │
│   │          Continuity Services, Use Cases)       │   │
│   │   ┌────────────────────────────────────────┐   │   │
│   │   │              Domain Layer              │   │   │
│   │   │     (Project, Scene, Shot, DNA Tokens, │   │   │
│   │   │      Master Production Bible, Entities)│   │   │
│   │   └────────────────────────────────────────┘   │   │
│   └────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

### Dependency Inversion Rules

- **Domain Layer (`backend/app/domain/`):**
  - Contains enterprise business entities, value objects, and repository interfaces.
  - **Constraint:** Must only import from the Python Standard Library and internal domain models.
  - **Forbidden:** Never import FastAPI, SQLAlchemy, Pydantic (outside domain schemas), HTTP libraries, or third-party AI SDKs.
- **Application Layer (`backend/app/application/`):**
  - Contains use cases, pipeline coordinators, and service orchestrators.
  - **Constraint:** Depends only on the Domain Layer. Interacts with persistence and providers exclusively via abstract domain interfaces.
  - **Forbidden:** Never import concrete database models, SQLAlchemy sessions, or provider SDKs.
- **Infrastructure Layer (`backend/app/infrastructure/`):**
  - Contains database engines, Alembic migrations, concrete repositories, and external AI provider adapters.
  - **Constraint:** Implements domain interfaces and depends inward.

### Automated Layer Enforcement

We run automated architecture tests to prevent dependency leakage:
```bash
uv run pytest tests/architecture/test_layer_boundaries.py
```
Any pull request introducing illegal outer-layer imports into domain modules will fail CI.

---

## 4. Test-Driven Development (TDD) Protocol

Every feature or bug fix follows a strict TDD lifecycle:

```
[Write Failing Test] ──> [Verify Test Fails (Red)] ──> [Implement Code (Green)] ──> [Refactor & Clean]
```

1. **Step 1: Author the Test:** Write unit tests asserting expected behaviors, edge cases, and error conditions in `tests/`.
2. **Step 2: Confirm Failure:** Run `uv run pytest path/to/test_file.py` and verify the test fails with the expected error.
3. **Step 3: Implement Minimal Solution:** Write the cleanest, most direct code in `backend/app/` to satisfy the test assertions.
4. **Step 4: Verify Passage:** Confirm all tests pass (`uv run pytest`).
5. **Step 5: Refactor:** Optimize structure, clean up variable names, and verify layer boundary compliance without breaking tests.

---

## 5. Code Style & Linting Standards

We enforce code consistency and formatting using `ruff`:

```bash
# Check for linting violations
uv run ruff check .

# Automatically fix fixable violations
uv run ruff check --fix .

# Verify code formatting
uv run ruff format --check .

# Automatically apply formatting
uv run ruff format .
```

### Style Directives

- **Line Length:** 88 characters.
- **Type Annotations:** Full type annotations required for all function arguments and return types.
- **Docstrings:** Clear, concise docstrings explaining *why* a function exists, its parameters, and any raised exceptions.
- **Logging:** Use `structlog` for structured JSON logging. Avoid `print()` statements in production code.

---

## 6. Database Migration Workflow

All relational schema alterations must be managed through Alembic.

```bash
# 1. Update SQLAlchemy models in backend/app/infrastructure/database/models/
# 2. Generate migration script
uv run alembic revision --autogenerate -m "descriptive_migration_name"

# 3. Review the generated script in migrations/versions/ for safety and accuracy
# 4. Test upgrading to the new revision
uv run alembic upgrade head

# 5. Test downgrading back (verify rollback capability)
uv run alembic downgrade -1

# 6. Re-apply to head and run migration tests
uv run alembic upgrade head
uv run pytest tests/infrastructure/test_database_migrations.py
```

---

## 7. Git Workflow & Conventional Commits

### Branching Strategy

- `main`: Protected production branch. All code must pass CI before merging.
- Feature branches: `feat/<task-id>-<short-description>` (e.g., `feat/task-007-asset-storage`).
- Bug fix branches: `fix/<issue-id>-<short-description>` (e.g., `fix/scene-timeout-handler`).
- Documentation/audit: `patch/<topic>` (e.g., `patch/audit-md-pipeline`).

### Conventional Commits Format

Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short imperative description>

[optional body explaining motivation and architectural context]

[optional footer referencing task or issue: Closes TASK-007]
```

Allowed types:
- `feat`: A new feature or pipeline capability.
- `fix`: A bug fix or defect correction.
- `refactor`: Code restructuring without behavioral change.
- `test`: Adding or updating automated tests.
- `docs`: Documentation updates or additions.
- `chore`: Tooling, dependency updates, or configuration adjustments.

*Example:*
```
feat(database): establish async database foundation

Implement async SQLAlchemy 2.0 engine, Unit of Work pattern,
and Alembic migration baseline for SQLite storage.

Closes TASK-006
```

---

## 8. Autonomous AI Agent Collaboration Guidelines

Autonomous agents operating via the **Antigravity CLI (`agy`)** swarm runtime must adhere to strict operational boundaries:

1. **Kanban & Task Assignment:** Never author code or modify files without an assigned ticket in `TASKS.md`.
2. **Subagent Sandboxing:** Authors and coders must operate in isolated working copies (`workspace: "share"` or `workspace: "branch"`) to prevent write collisions.
3. **No Monolithic Generations:** Implement features incrementally. Do not generate massive, untestable files in a single turn.
4. **Humanizer Voice Standard:** All written documentation, pull request summaries, and script voiceovers must comply with `/home/ubuntu/.hermes/skills/creative/humanizer/SKILL.md`. Avoid AI clichés ("testament to", "delve into", "pivotal", "seamless"), robotic enumerations, and marketing fluff.

---

## 9. Definition of Done (DoD)

A pull request is ready for merge only when all items are verified:

- [ ] All 50+ unit and integration tests pass (`uv run pytest`).
- [ ] Architecture layer boundary tests pass (`uv run pytest tests/architecture/test_layer_boundaries.py`).
- [ ] Linting and formatting pass with zero warnings (`uv run ruff check .` and `uv run ruff format --check .`).
- [ ] Database migrations apply cleanly and roll back successfully.
- [ ] Documentation (`README.md`, `ARCHITECTURE.md`, `API_SPEC.md`, `TASKS.md`, `CHANGELOG.md`) is updated to reflect all changes.
- [ ] No secrets, private credentials, or temporary debug files are committed.
