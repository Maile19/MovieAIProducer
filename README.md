# MovieAIProducer

> Hollywood-Grade Cinematic AI Film Production Platform powered by the 12-Step Cinematic Framework and the Master Production Bible (MPB).

MovieAIProducer coordinates long-form generative AI cinema. Unlike simple prompt wrappers that generate disconnected video clips, MovieAIProducer operates as an end-to-end virtual film studio. It maintains narrative continuity, optical physics, character state evolution, and production design across a 50-scene (4-act) screenplay.

---

## Key Features

| Capability                        | Technical Implementation                                                                                                                                      | Production Value                                                                                     |
| :-------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------- |
| **12-Step Cinematic Pipeline**    | Sequential workflow enforcing genre, style, 4-act story blueprint, character DNA, camera optics, lighting, acting, and motion dynamics.                       | Eliminates haphazard prompting; guarantees complete pre-production coverage before video generation. |
| **Master Production Bible (MPB)** | Central domain registry managing immutable identifiers for characters, environments, wardrobe, and props.                                                     | Absolute visual continuity across 50 scenes with zero character or asset drift.                      |
| **Provider-Agnostic Engine**      | Decoupled adapter layer isolating domain logic from external inference APIs (Kling, Runway Gen-3, Google Veo, Midjourney, ElevenLabs).                        | Hot-swap generation providers without altering story specifications or prompt architectures.         |
| **Optical & Cinematic Matrices**  | 34 camera angles (`#Cam 01-34`), 6 lens physics profiles (`#Lens 01-06`), 8 composition geometries (`#Comp 01-08`), and 14 lighting designs (`#Light 01-14`). | Studio-grade cinematography with strict adherence to the 180-degree rule and focal length physics.   |
| **Character State Evolution**     | 5 discrete character condition states (`#State 01-05`) tracking costume damage, fatigue, and emotional progression.                                           | Visual storytelling where character appearance evolves logically with plot developments.             |
| **Continuity & Quality Control**  | Automated rule engine evaluating frame bridging, spatial orientation, audio synchronization (J/L-cuts), and color palettes.                                   | Catches artifacts, lighting mismatches, and geometry errors prior to editorial assembly.             |

---

## System Architecture

MovieAIProducer follows Clean Architecture principles, ensuring that creative and domain rules remain completely independent of external frameworks, databases, and AI provider SDKs.

```text
MovieAIProducer/
├── backend/
│   └── app/
│       ├── domain/             # Enterprise business rules & entities
│       │   ├── entities/       # Project, Scene, Shot, Character, DNA, MPB
│       │   └── interfaces/     # Repository & provider abstract contracts
│       ├── application/        # Use cases & workflow orchestration
│       │   ├── pipelines/      # 12-step cinematic pipeline coordinators
│       │   └── services/       # Prompt compilation, continuity checkers
│       ├── infrastructure/     # External implementations & concrete adapters
│       │   ├── database/       # Async SQLAlchemy 2.0, SQLite engine, UoW
│       │   ├── providers/      # Kling, Runway, Google Veo, ElevenLabs adapters
│       │   └── storage/        # Local filesystem & S3 asset managers
│       ├── api/                # FastAPI routing & HTTP controllers
│       └── core/               # App configuration, logging, settings
├── migrations/                 # Alembic database migration scripts
├── tests/                      # Unit, integration, and architecture test suites
│   ├── domain/                 # Domain logic & entity invariant tests
│   ├── application/            # Pipeline & use case execution tests
│   ├── infrastructure/         # DB engine, repository, and migration tests
│   └── architecture/           # Dependency rule & layer boundary enforcement
├── docs/                       # Architecture Decision Records (ADRs) & CDAs
├── DECISIONS/                  # Canonical decision registries & audit artifacts
└── pyproject.toml              # Python dependency manifest (uv-managed)
```

### Architectural Highlights

- **Dependency Inversion:** Outer layers (API, Infrastructure) depend inward on the Domain layer. Domain models import nothing from FastAPI, SQLAlchemy, or third-party AI SDKs.
- **Async Database Core:** High-performance async persistence powered by SQLAlchemy 2.0, `aiosqlite`, and Alembic schema migrations.
- **Unit of Work & Repository Pattern:** Clean transaction boundaries for multi-entity production updates.
- **Strict Layer Enforcement:** Automated test suites (`tests/architecture/test_layer_boundaries.py`) verify that domain components remain untainted by outer dependencies.

---

## Quickstart

MovieAIProducer uses [`uv`](https://github.com/astral-sh/uv) for fast, deterministic Python environment and dependency management.

### Prerequisites

- Linux or macOS (Ubuntu 22.04+ recommended)
- Python `>=3.12, <3.15`
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Installation & Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/MovieAIProducer.git
   cd MovieAIProducer
   ```

2. **Sync virtual environment and dependencies:**

   ```bash
   uv sync
   ```

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env to set application settings and provider credentials
   ```

4. **Apply database migrations:**

   ```bash
   uv run alembic upgrade head
   ```

5. **Start the FastAPI backend server:**

   ```bash
   uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Verify server status:**
   - Swagger Interactive Documentation: `http://localhost:8000/docs`
   - Redoc Specification: `http://localhost:8000/redoc`
   - Health Check: `http://localhost:8000/health`

---

## Development & Testing

All development workflows are executed through `uv`.

### Running Tests

Run the complete test suite:

```bash
uv run pytest
```

Run test categories selectively:

```bash
# Architecture & layer boundary tests
uv run pytest tests/architecture/

# Domain logic & entity invariants
uv run pytest tests/domain/

# Database engine & migrations
uv run pytest tests/infrastructure/test_database_migrations.py

# Health endpoints
uv run pytest tests/test_health.py
```

### Code Formatting & Linting

We enforce strict formatting and static code quality using `ruff`:

```bash
# Check for lint violations
uv run ruff check .

# Automatically apply safe fixes
uv run ruff check --fix .

# Verify formatting
uv run ruff format --check .

# Auto-format codebase
uv run ruff format .
```

### Database Migrations

When altering models in `backend/app/infrastructure/database/models/`:

```bash
# Generate a new migration revision
uv run alembic revision --autogenerate -m "add_scene_and_shot_entities"

# Apply pending migrations
uv run alembic upgrade head

# Downgrade one revision (for rollback testing)
uv run alembic downgrade -1
```

---

## Cinematic 12-Step Pipeline

Every production initiated in MovieAIProducer traverses 12 immutable gates:

```text
[1. Genre & Aspect] ──> [2. Visual Style] ──> [3. 4-Act Blueprint] ──> [4. Character DNA]
                                                                               │
[8. Optics & Geometry] <── [7. Dialogue & Audio] <── [6. Environment] <── [5. Extras Sheet]
        │
        └──> [9. Cinematic Lighting] ──> [10. Acting Matrix] ──> [11. Motion Layers] ──> [12. Studio Execution]
```

1. **Genre & Ratio:** Narrative tone, sub-genre, emotional valence, and aspect ratio (16:9 cinema or 9:16 vertical).
2. **Visual Style:** Master aesthetic catalog selection (`#Style 01` Michael Bay through `#Style 18` Vintage Film).
3. **Story Blueprint:** 50-scene structural breakdown mapped across a standard 4-act dramatic curve.
4. **Character DNA:** Visual seed locking, voice characteristics, and dynamic state progression (`#State 01-05`).
5. **Extras Sheet:** Secondary character ensembles and cultural crowd matching (5 to 8 groups).
6. **Environment & Props:** World design bibles, atmospheric keys (`#Env 01-05`), and hero props (`#Prop 01-05`).
7. **Dialogue & Audio:** Voiceover calibration, 5-second scene timing, and J-cut/L-cut sound bridges.
8. **Cinematography:** Camera setups (`#Cam 01-34`), lens focal lengths (`#Lens 01-06`), and composition framing (`#Comp 01-08`).
9. **Lighting Matrix:** Key, fill, rim, and atmospheric lighting styles (`#Light 01-14`).
10. **Acting & Performance:** Micro-expression cues, emotional intensity, and physical gestures (`#Act 01-24`).
11. **Motion Dynamics:** Foreground/background parallax separation (`#FG/#BG`) and motion velocity profiles (`#Speed 01-05`).
12. **Studio Execution:** Prompt compilation, provider API dispatch, quality control scoring, and timeline export.

---

## Agent Orchestration

MovieAIProducer leverages **Antigravity CLI (`agy`)** as its primary multi-agent orchestration runtime. Independent specialized subagents handle architectural design, prompt compilation, provider execution, and continuous quality audits.

See [AGENTS.md](AGENTS.md) for complete details on swarm topologies, message bus communication, subagent sandboxing, and quality gate governance.

---

## Governance & Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - High-level system design and technology choices.
- [AI_PIPELINE.md](AI_PIPELINE.md) - Full 12-step creative pipeline and 16 operational stages.
- [AGENTS.md](AGENTS.md) - Antigravity CLI orchestration protocols and agent roster.
- [PROMPTS.md](PROMPTS.md) - Hollywood prompt engineering catalog, templates, and matrix codes.
- [BRD.md](BRD.md) - Business requirements, success metrics, and operational goals.
- [PRD.md](PRD.md) - Product specifications, user journeys, and feature definitions.
- [ROADMAP.md](ROADMAP.md) - Stage-by-stage engineering plan and milestones.
- [TASKS.md](TASKS.md) - Actionable engineering checklist and implementation tracking.
- [CHANGELOG.md](CHANGELOG.md) - Historical release logs and semantic version tracking.
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines, code standards, and PR workflows.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
