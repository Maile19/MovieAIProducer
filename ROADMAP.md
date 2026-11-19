# Product & Engineering Roadmap - MovieAIProducer

> Operational development roadmap aligning core software engineering milestones with the **16 Hollywood Operational Production Stages**.

---

## 1. Roadmap Architecture & Development Strategy

The MovieAIProducer engineering roadmap coordinates the incremental delivery of our virtual film production platform. To ensure production fidelity, the technical milestones directly map to the 16 Hollywood Operational Stages defined in the studio pipeline.

Development follows strict **Test-Driven Development (TDD)** and Clean Architecture protocols:
1. **Incremental Delivery:** Every milestone produces testable, verifiable software components.
2. **Quality Gates:** Advancing between phases requires 100% test passage on architecture boundaries, domain models, and regression suites.
3. **Traceability:** Every technical feature maps to a registered task in `TASKS.md` and an Architecture Decision Record (ADR).

---

## 2. Engineering Milestones vs. 16 Operational Stages

```
[Phase 0: Discovery] ──> [Phase 1: Foundation] ──> [Phase 2: Project Management]
      (COMPLETED)               (COMPLETED)                   (IN PROGRESS)
                                                                   │
[Phase 5: Visual Direction] <── [Phase 4: Production Bible] <──────┘
        │
        └──> [Phase 6: Storyboard] ──> [Phase 7: Prompt Engine] ──> [Phase 8: QC & Delivery]
```

| Milestone | Operational Stage | Target Discipline | Core Deliverables & Technical Scope | Status |
| :--- | :--- | :--- | :--- | :--- |
| **R0** | Stage 00 | System Discovery | Repository discovery, dependency risk audit, gap analysis against `ARCHITECTURE.md`. | **COMPLETED** |
| **R1** | Stage 00 | System Foundation | FastAPI bootstrap, Clean Architecture layer boundaries, Async SQLAlchemy 2.0 + SQLite database engine, Alembic migrations baseline, health endpoints. | **COMPLETED** |
| **R2** | Stage 01 | Creative Brief & Film Strategy | Project CRUD, Creative Brief domain entity, aspect ratio config, project dashboard services. | In Progress |
| **R3** | Stage 02–04 | Story Architecture & Screenplay | 4-act narrative curve generator, 50-scene structural breakdown, dialogue calibration (5.0s pacing), script breakdown. | Planned |
| **R4** | Stage 05–08 | Master Production Bible (MPB) | Character DNA seeds, dynamic state progression (`#State 01-05`), environment bibles (`#Env 01-05`), hero props (`#Prop 01-05`), extras sheets (`#Extras 01-08`). | Planned |
| **R5** | Stage 10–14 | Cinematography & Visual Direction | Style catalog (`#Style 01-18`), camera matrix (`#Cam 01-34`), optical lenses (`#Lens 01-06`), lighting (`#Light 01-14`), acting (`#Act 01-24`), motion parallax (`#Speed 01-05`, `#FG/#BG`). | Planned |
| **R6** | Stage 09 | Previsualization & Storyboarding | Rapid keyframe generation, camera blocking validator, temporal animatics assembly, 180-degree rule checker. | Planned |
| **R7** | Stage 15 | AI Engine & Prompt Compilation | MPB token resolution, prompt compiler, provider adapter interface, Runway Gen-3 & Kling adapters, async job dispatcher. | Planned |
| **R8** | Stage 15 | Audio & Dialogue Synthesis | ElevenLabs voice cloning integration, dialogue audio synthesis, audio bridge calibration (J-cuts and L-cuts). | Planned |
| **R9** | Stage 16 | Continuity & Quality Control | Automated visual drift detection, facial embedding cosine scoring, lighting jump detector, QC scorecard reporting. | Planned |
| **R10**| Stage 16 | Final Editorial & Delivery | Timeline assembly, EDL / XML export for Premiere & DaVinci Resolve, C2PA provenance manifest signing, final 4K package export. | Planned |

---

## 3. Phase-by-Phase Technical Breakdown

### Phase 0: Repository Discovery (Completed)
- **Scope:** Tasks 001 through 003.
- **Outcomes:** Full repository audit, dependency manifests inspected, architectural gap analysis resolved.

### Phase 1: Core Foundation & Persistence (Completed)
- **Scope:** Tasks 004 through 006.
- **Outcomes:**
  - `TASK-004`: Application Bootstrap. Configured FastAPI entry point, structured logging via `structlog`, and environment settings with `pydantic-settings`.
  - `TASK-005`: Clean Architecture Foundation. Established strict domain, application, and infrastructure layer boundaries enforced by unit tests (`tests/architecture/test_layer_boundaries.py`).
  - `TASK-006`: Database Foundation. Implemented asynchronous SQLAlchemy 2.0 with `aiosqlite`, Unit of Work pattern, generic Repository contracts, and Alembic migrations (`migrations/versions/0001_initial_database_foundation.py`).
  - 50 automated tests passing with 100% verification rate.

### Phase 2: Project Management & Creative Brief (Current Priority)
- **Scope:** Tasks 007 through 010.
- **Objectives:**
  - Implement filesystem asset storage abstractions with checksum validation (`TASK-007`).
  - Implement Project entity CRUD with lifecycle states (`TASK-008`).
  - Implement Creative Brief management with genre, emotion, and aspect ratio models (`TASK-009`).
  - Build project dashboard aggregators providing stage progress and resource health (`TASK-010`).

### Phase 3: Story Architecture & Screenplay Engine
- **Scope:** Tasks 011 through 013.
- **Objectives:**
  - Construct 4-act narrative curve generator mapping 50 scenes (`TASK-011`).
  - Implement screenplay parser with slugline and dialogue tokenization (`TASK-012`).
  - Build scene breakdown service analyzing location, time, character presence, and 5-second pacing (`TASK-013`).

### Phase 4: Master Production Bible & DNA Locking
- **Scope:** Tasks 014 through 017.
- **Objectives:**
  - Build Master Production Bible schema with immutable revision snapshots (`TASK-014`).
  - Implement Character Bible with DNA seeds, voice traits, and `#State 01-05` progression (`TASK-015`).
  - Implement Environment Bible (`#Env 01-05`) and hero prop manifests (`#Prop 01-05`) (`TASK-016`).
  - Implement wardrobe state tracking and damage continuity (`TASK-017`).

### Phase 5: Cinematography & Visual Direction Systems
- **Scope:** Tasks 018 through 021.
- **Objectives:**
  - Implement visual style catalog engine supporting `#Style 01-18` (`TASK-018`).
  - Implement cinematography engine supporting `#Cam 01-34`, `#Lens 01-06`, and `#Comp 01-08` (`TASK-019`).
  - Implement photometric lighting engine supporting `#Light 01-14` with Kelvin ratings (`TASK-020`).
  - Implement performance and motion dynamics engines (`#Act 01-24`, `#Speed 01-05`) (`TASK-021`).

### Phase 6: Previs & Storyboarding Module
- **Scope:** Tasks 022 through 024.
- **Objectives:**
  - Implement keyframe generator for scene previs (`TASK-022`).
  - Build shot blocking and 180-degree axis validator (`TASK-023`).
  - Build animatic timeline generator with temporal pacing checks (`TASK-024`).

### Phase 7: Prompt Engine & Provider Adapters
- **Scope:** Tasks 025 through 028.
- **Objectives:**
  - Define structured prompt schemas and data contracts (`TASK-025`).
  - Build prompt compiler resolving MPB tokens into target syntax (`TASK-026`).
  - Implement provider adapter interfaces for Runway Gen-3 and Kling (`TASK-027`).
  - Implement prompt versioning and seed reproducibility tracking (`TASK-028`).

### Phase 8+: Continuity, QC & Delivery
- **Scope:** Tasks 029 through 035.
- **Objectives:**
  - Build automated continuity scoring engine (facial embeddings, color histograms, lighting continuity).
  - Implement final timeline assembly and editorial export (EDL / XML / MP4).

---

## 4. Operational Protocol: Plan → Execute → Monitor

Every development cycle on this roadmap follows an explicit execution loop:

```
┌────────────────────────────────────────────────────────┐
│                   Development Loop                     │
├────────────────────┬───────────────────┬───────────────┤
│ 1. PLAN            │ 2. EXECUTE        │ 3. MONITOR    │
│ - Author/Audit ADR │ - Author TDD Tests│ - Run Pytest  │
│ - Define Contracts │ - Implement Code  │ - Layer Audit │
│ - Update TASKS.md  │ - Apply Migration │ - Verify DoD  │
└────────────────────┴───────────────────┴───────────────┘
```

- **PLAN:** Confirm task tickets, inspect existing architecture, define domain contracts, and author necessary ADR documents.
- **EXECUTE:** Follow strict Test-Driven Development. Author failing unit/integration tests, implement clean domain/application logic, and run migrations.
- **MONITOR:** Run automated regression suites (`uv run pytest`), verify layer boundary integrity, validate documentation sync, and update task status.
