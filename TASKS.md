# Engineering Task Checklist - MovieAIProducer

> Actionable engineering checklist and implementation tracking for MovieAIProducer, aligned with the **16 Hollywood Operational Stages**.

---

## Task Status Summary

| Phase        | Milestone               | Operational Stage | Total Tasks | Completed | In Progress | Planned |
| :----------- | :---------------------- | :---------------- | :---------- | :-------- | :---------- | :------ |
| **Phase 0**  | R0: Discovery           | Stage 00          | 3           | 3         | 0           | 0       |
| **Phase 1**  | R1: Foundation          | Stage 00          | 4           | 3         | 1           | 0       |
| **Phase 2**  | R2: Project Mgmt        | Stage 01          | 3           | 0         | 0           | 3       |
| **Phase 3**  | R3: Story & Screenplay  | Stage 02–04       | 3           | 0         | 0           | 3       |
| **Phase 4**  | R4: Production Bible    | Stage 05–08       | 4           | 0         | 0           | 4       |
| **Phase 5**  | R5: Visual Direction    | Stage 10–14       | 4           | 0         | 0           | 4       |
| **Phase 6**  | R6: Previs & Storyboard | Stage 09          | 3           | 0         | 0           | 3       |
| **Phase 7**  | R7: Prompt Engine       | Stage 15          | 4           | 0         | 0           | 4       |
| **Phase 8**  | R8: AI Orchestration    | Stage 15          | 3           | 0         | 0           | 3       |
| **Phase 9**  | R9: Audio & Voice       | Stage 13          | 2           | 0         | 0           | 2       |
| **Phase 10** | R10: Continuity & QC    | Stage 16          | 3           | 0         | 0           | 3       |
| **Phase 11** | R11: Delivery & Export  | Stage 16          | 2           | 0         | 0           | 2       |
| **Total**    |                         |                   | **38**      | **6**     | **1**       | **31**  |

---

## Detailed Task Breakdown

### PHASE 0: REPOSITORY DISCOVERY & AUDIT (P0) — COMPLETED

- [x] **TASK-001: Comprehensive Repository Discovery & Structure Mapping**
  - _Scope:_ Map repository layout, dependencies, and configuration. Identify legacy code and missing components.
  - _Evidence:_ Commit `f4ade69`. Directory mapped, `pyproject.toml` evaluated.
- [x] **TASK-002: Dependency & Security Risk Audit**
  - _Scope:_ Audit package manifests for runtime risks, CVEs, and outdated constraints.
  - _Evidence:_ Configured modern `uv` dependency management in `pyproject.toml` (Python 3.12+, FastAPI, SQLAlchemy 2.0).
- [x] **TASK-003: Architectural Gap Analysis**
  - _Scope:_ Compare existing codebase against `ARCHITECTURE.md` and formulate Clean Architecture remediation.
  - _Evidence:_ Completed gap audit; established baseline for domain/application/infrastructure layer segregation.

---

### PHASE 1: APPLICATION FOUNDATION & PERSISTENCE (P0) — IN PROGRESS

- [x] **TASK-004: FastAPI Application Bootstrap & Logging**
  - _Scope:_ Implement entry point (`backend/app/main.py`), settings management via `pydantic-settings`, and structured logging via `structlog`.
  - _Evidence:_ Commit `40f2718`. Health check endpoints verified at `/health`.
- [x] **TASK-005: Clean Architecture Foundation & Layer Boundary Enforcement**
  - _Scope:_ Establish strict boundary rules between Domain, Application, and Infrastructure layers. Author automated boundary compliance tests.
  - _Evidence:_ Commit `ff19c0e`. Automated layer tests passing in `tests/architecture/test_layer_boundaries.py`.
- [x] **TASK-006: Asynchronous Database Foundation & Migration Baseline**
  - _Scope:_ Implement async SQLAlchemy 2.0 engine, Unit of Work pattern, generic Repository contracts, and Alembic migrations.
  - _Evidence:_ Commit `cad786c`. Migration `0001_initial_database_foundation.py` applied. Verified with 50 passing tests via `uv run pytest`.
- [ ] **TASK-007: Project Asset Storage Abstraction**
  - _Scope:_ Implement abstract asset storage repository supporting local filesystem and S3-compatible object storage with SHA-256 checksums.
  - _Acceptance Criteria:_ File upload/retrieval contracts pass unit tests; binary files stored with deterministic hash keys.
  - _Verification:_ `uv run pytest tests/infrastructure/test_storage.py`

---

### PHASE 2: PROJECT MANAGEMENT & CREATIVE BRIEF (P0) — PLANNED

_Alignment: Hollywood Operational Stage 01 (Creative Brief & Film Strategy)_

- [ ] **TASK-008: Project Entity Domain & CRUD Operations**
  - _Scope:_ Implement Project aggregate root, lifecycle state transitions (`Draft`, `Active`, `Archived`), and repository persistence.
  - _Verification:_ `uv run pytest tests/domain/test_project.py`
- [ ] **TASK-009: Creative Brief Domain Model & Validation**
  - _Scope:_ Implement Creative Brief models for Genre, Sub-Genre, Emotional Arc, and Aspect Ratio (16:9 / 9:16).
  - _Verification:_ `uv run pytest tests/domain/test_creative_brief.py`
- [ ] **TASK-010: Project Studio Dashboard Services**
  - _Scope:_ Implement read-model aggregator providing real-time production statistics and completion percentages.
  - _Verification:_ `uv run pytest tests/application/test_dashboard_service.py`

---

### PHASE 3: STORY ARCHITECTURE & SCREENPLAY ENGINE (P0) — PLANNED

_Alignment: Hollywood Operational Stages 02–04 (Story Architecture & Script Breakdown)_

- [ ] **TASK-011: 4-Act Story Curve Generator**
  - _Scope:_ Build narrative generator dividing project into 4 standard acts with inciting incidents, midpoints, and climaxes.
  - _Verification:_ `uv run pytest tests/domain/test_story_arc.py`
- [ ] **TASK-012: 50-Scene Structural Breakdown Engine**
  - _Scope:_ Decompose screenplay into exactly 50 scenes, each strictly calibrated to 5.0-second durations.
  - _Verification:_ `uv run pytest tests/application/test_scene_breakdown.py`
- [ ] **TASK-013: Dialogue Calibration & Audio Transition Planner**
  - _Scope:_ Implement word-per-minute pacing validator (max 14 words per 5s cut) and plan J/L audio cut bridges.
  - _Verification:_ `uv run pytest tests/application/test_audio_timing.py`

---

### PHASE 4: MASTER PRODUCTION BIBLE (MPB) & DNA LOCKING (P0) — PLANNED

_Alignment: Hollywood Operational Stages 05–08 (Character, World & Production Design)_

- [ ] **TASK-014: Master Production Bible Schema & Versioning**
  - _Scope:_ Implement MPB domain aggregate managing immutable versioned snapshots of production specs.
  - _Verification:_ `uv run pytest tests/domain/test_production_bible.py`
- [ ] **TASK-015: Character DNA & State Evolution Engine**
  - _Scope:_ Implement character entity with visual DNA seeds, voice profiles, and `#State 01-05` damage/fatigue transitions.
  - _Verification:_ `uv run pytest tests/domain/test_character_dna.py`
- [ ] **TASK-016: Environment Bible & Hero Prop Registry**
  - _Scope:_ Build catalog models for environments (`#Env 01-05`) and hero props (`#Prop 01-05`).
  - _Verification:_ `uv run pytest tests/domain/test_environment_prop.py`
- [ ] **TASK-017: Extras & Crowd Demographics Manager**
  - _Scope:_ Implement background crowd cluster registry (`#Extras 01-08`) with cultural and period consistency checks.
  - _Verification:_ `uv run pytest tests/domain/test_extras.py`

---

### PHASE 5: CINEMATOGRAPHY & VISUAL DIRECTION (P1) — PLANNED

_Alignment: Hollywood Operational Stages 10–14 (Cinematography, Lighting & Direction)_

- [ ] **TASK-018: Visual Style Catalog Engine**
  - _Scope:_ Implement style directives for `#Style 01` through `#Style 18`, including color palettes and sensor emulation.
  - _Verification:_ `uv run pytest tests/domain/test_style_catalog.py`
- [ ] **TASK-019: Cinematography & Optical Physics Engine**
  - _Scope:_ Implement models for `#Cam 01-34`, `#Lens 01-06`, and `#Comp 01-08` with spatial 180-degree action line tracking.
  - _Verification:_ `uv run pytest tests/domain/test_cinematography.py`
- [ ] **TASK-020: Cinematic Lighting & Photometry Engine**
  - _Scope:_ Implement lighting matrix `#Light 01-14` specifying Kelvin temperatures, key/fill ratios, and volumetric haze.
  - _Verification:_ `uv run pytest tests/domain/test_lighting.py`
- [ ] **TASK-021: Performance & Motion Dynamics Engine**
  - _Scope:_ Implement acting performance codes (`#Act 01-24`), motion speeds (`#Speed 01-05`), and foreground/background layering (`#FG/#BG`).
  - _Verification:_ `uv run pytest tests/domain/test_performance_motion.py`

---

### PHASE 6: PREVISUALIZATION & STORYBOARDING (P1) — PLANNED

_Alignment: Hollywood Operational Stage 09 (Storyboard, Animatic & Previs)_

- [ ] **TASK-022: Scene Keyframe Generation Service**
  - _Scope:_ Generate visual anchor keyframes for all 50 scenes via fast text-to-image inference.
  - _Verification:_ `uv run pytest tests/application/test_keyframe_service.py`
- [ ] **TASK-023: Camera Blocking & 180-Degree Spatial Validator**
  - _Scope:_ Algorithmic verification ensuring camera vectors do not cross the axis of action between sequential shots.
  - _Verification:_ `uv run pytest tests/application/test_spatial_validator.py`
- [ ] **TASK-024: Temporal Animatic Assembler**
  - _Scope:_ Assemble 50-scene keyframes into a rough cut video with temporary scratch audio.
  - _Verification:_ `uv run pytest tests/application/test_animatic_service.py`

---

### PHASE 7: PROMPT ENGINE & PROVIDER ADAPTERS (P0) — PLANNED

_Alignment: Hollywood Operational Stage 15 (AI Production Orchestration)_

- [ ] **TASK-025: Structured Prompt Schema & Validation Contracts**
  - _Scope:_ Define Pydantic models for structured prompt compiler inputs and target provider schemas.
  - _Verification:_ `uv run pytest tests/domain/test_prompt_schema.py`
- [ ] **TASK-026: MPB Prompt Compiler Engine**
  - _Scope:_ Build compiler resolving MPB variables into deterministic prompts with negative prompt injection.
  - _Verification:_ `uv run pytest tests/application/test_prompt_compiler.py`
- [ ] **TASK-027: Video Provider Adapter Implementations (Runway & Kling)**
  - _Scope:_ Implement concrete provider adapters with async HTTP dispatching, rate-limiting, and error mapping.
  - _Verification:_ `uv run pytest tests/infrastructure/test_provider_adapters.py`
- [ ] **TASK-028: Prompt Versioning & Reproducibility Registry**
  - _Scope:_ Store generation seed configurations, compiler versions, and prompt snapshots for auditing.
  - _Verification:_ `uv run pytest tests/domain/test_prompt_versioning.py`

---

### PHASE 8: AI PRODUCTION ORCHESTRATION & DISPATCH (P1) — PLANNED

_Alignment: Hollywood Operational Stage 15 (AI Production Orchestration)_

- [ ] **TASK-029: Async Generation Job Queue & Task Manager**
  - _Scope:_ Implement persistent job queue managing generation lifecycle (`Planned` -> `Generating` -> `Completed`).
  - _Verification:_ `uv run pytest tests/infrastructure/test_job_queue.py`
- [ ] **TASK-030: Provider Failover & Circuit Breaker Engine**
  - _Scope:_ Implement automated retry logic, exponential backoff, and fallback routing across providers.
  - _Verification:_ `uv run pytest tests/infrastructure/test_circuit_breaker.py`
- [ ] **TASK-031: Asset Ingestion & Checksum Validator**
  - _Scope:_ Download rendered video binaries, compute SHA-256 hashes, and catalog assets into storage.
  - _Verification:_ `uv run pytest tests/infrastructure/test_asset_ingestion.py`

---

### PHASE 9: AUDIO DIRECTION & DIALOGUE SYNTHESIS (P1) — PLANNED

_Alignment: Hollywood Operational Stage 13 (Performance, Dialogue & Voice Direction)_

- [ ] **TASK-032: ElevenLabs Voice Cloning & TTS Adapter**
  - _Scope:_ Implement ElevenLabs adapter linking Voice DNA profiles to dialogue generation jobs.
  - _Verification:_ `uv run pytest tests/infrastructure/test_tts_adapter.py`
- [ ] **TASK-033: Audio Transition & Cut Bridge Synthesizer**
  - _Scope:_ Assemble J-cut / L-cut sound waveforms aligning dialogue over scene boundary transitions.
  - _Verification:_ `uv run pytest tests/application/test_audio_mixer.py`

---

### PHASE 10: CONTINUITY & QUALITY CONTROL (P1) — PLANNED

_Alignment: Hollywood Operational Stage 16 (Scene Execution, Editorial & Final QC)_

- [ ] **TASK-034: Automated Character Drift & Face Embedding Scorer**
  - _Scope:_ Extract keyframes and compute facial embedding cosine similarity against Character DNA reference.
  - _Verification:_ `uv run pytest tests/application/test_face_scorer.py`
- [ ] **TASK-035: Lighting & Color Grade Histogram Evaluator**
  - _Scope:_ Measure luminance and color histogram variances across sequential scene cuts.
  - _Verification:_ `uv run pytest tests/application/test_color_evaluator.py`
- [ ] **TASK-036: Automated QC Scorecard & Defect Reporting**
  - _Scope:_ Calculate overall scene QC score; flag scenes scoring under 85% for automated regeneration.
  - _Verification:_ `uv run pytest tests/application/test_qc_scorecard.py`

---

### PHASE 11: FINAL EDITORIAL & DELIVERY (P1) — PLANNED

_Alignment: Hollywood Operational Stage 16 (Editorial & Final Delivery)_

- [ ] **TASK-037: Timeline Exporter (EDL / FCPXML / DaVinci Resolve)**
  - _Scope:_ Export calibrated 50-scene cut lists with embedded timecode and audio transition markers.
  - _Verification:_ `uv run pytest tests/application/test_timeline_exporter.py`
- [ ] **TASK-038: C2PA Provenance Manifest Signer**
  - _Scope:_ Inject standardized cryptographic content provenance metadata into final MP4 deliverables.
  - _Verification:_ `uv run pytest tests/infrastructure/test_c2pa_signer.py`
