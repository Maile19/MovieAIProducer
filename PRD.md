# Product Requirements Document (PRD) - MovieAIProducer

> Technical product specifications, functional architecture, data contracts, and quality acceptance criteria for MovieAIProducer.

---

## 1. Product Vision & Philosophy

MovieAIProducer is an intelligent virtual film production environment that transforms creative ideas into structured, continuous, and quality-controlled cinematic workflows. It replaces unstructured text-to-video prompting with an automated virtual film studio governed by the **Master Production Bible (MPB)** and the **12-Step Cinematic Pipeline**.

### 1.1 Core Principles

1. **Story Before Visuals:** Visual assets derive from narrative beats, character motivations, and dramatic structure, never from arbitrary style exploration.
2. **Consistency Before Volume:** Generating one continuous 50-scene narrative with zero character or lighting drift is prioritized over generating hundreds of disconnected clips.
3. **Specifications Before Execution:** All camera, lighting, acting, and environment parameters must be compiled into deterministic schemas before dispatching provider inference calls.
4. **Provider-Independent Data Contracts:** Production specifications exist in an abstract domain layer, decoupled from the syntax of external AI generation platforms.
5. **Human-in-the-Loop Governance:** Autonomous agents prepare options and compile parameters, while the human director retains approval authority at designated creative gates.
6. **Automated Quality Verification:** Every generated frame and shot is audited against objective continuity and optical criteria prior to timeline assembly.

---

## 2. Operating Modes & User Journeys

MovieAIProducer adapts its agent autonomy based on director preference:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Operational Execution Modes                       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Director Mode   │      │   Hybrid Mode    │      │  Autopilot Mode  │
│  (100% Approval) │      │ (Default Studio) │      │  (Batch Render)  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

| Operational Mode | Agent Autonomy | Human Intervention Points | Primary Use Case |
| :--- | :--- | :--- | :--- |
| **Director Mode** | Low: AI acts strictly as an assistant, drafting candidate options for every matrix selection. | Human must approve every step (Genre, Style, Scene list, Character DNA, Shot list, Render). | High-stakes auteur filmmaking and masterclass cinematography projects. |
| **Hybrid Mode (Default)** | Balanced: AI automates routine breakdowns, prompt compilation, and retry loops. | Human confirms creative gates: Creative Brief, Character DNA lock, Script approval, and Final QC. | Standard indie film production, episodic series development, and commercial pilots. |
| **Autopilot Mode** | High: Autonomous execution of pre-approved bibles through rendering, QC auditing, and packaging. | Human is only alerted if a scene fails QC score thresholds three consecutive times. | High-throughput content syndication, concept testing, and rapid previsualization. |

---

## 3. Application Architecture & Studio Workspaces

MovieAIProducer organizes film production into six dedicated studio workspaces:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     MovieAIProducer Studio Suite                       │
├───────────────────┬────────────────────┬───────────────────────────────┤
│ 1. Creative Studio│ 2. World Studio    │ 3. Cinematography Studio      │
│ (Story, Screenplay│ (Character DNA,    │ (Optics, Lighting, Acting,   │
│  & Scene Lists)   │  Environments)     │  Composition & Motion)        │
├───────────────────┼────────────────────┼───────────────────────────────┤
│ 4. Previs Studio  │ 5. Engine Studio   │ 6. Continuity & QC Studio     │
│ (Storyboards,     │ (Prompt Compilation│ (Frame Drift Audit, 180° Rule,│
│  Animatics)       │  & Provider Dispatch) Color Grade Verification)     │
└───────────────────┴────────────────────┴───────────────────────────────┘
```

### 3.1 Studio 1: Creative & Story Studio
- **Scope:** Steps 1, 3, and 7 of the cinematic pipeline.
- **Capabilities:**
  - Ingests project loglines and generates a 4-act dramatic curve (Setup, Rising Action, Descent, Climax).
  - Decomposes narrative into exactly 50 scenes, each calibrated to a 5.0-second temporal pacing window.
  - Generates scene sluglines (`INT/EXT`, `LOCATION`, `TIME OF DAY`), dramatic objectives, and dialogue blocks.
  - Implements audio cut planning (J-cut audio anticipation and L-cut dialogue overhang).

### 3.2 Studio 2: Character & World Studio
- **Scope:** Steps 4, 5, and 6 of the cinematic pipeline.
- **Capabilities:**
  - Generates immutable Character DNA profiles (synthetic facial seeds, eye color, bone structure, voice timbre).
  - Tracks Character State Evolution across five stages:
    * `#State 01`: Pristine / Baseline
    * `#State 02`: Fatigued / Strained
    * `#State 03`: Battle-Damaged / Wounded
    * `#State 04`: Disheveled / Exhausted
    * `#State 05`: Climax / Transcendent
  - Compiles Environment Bibles (`#Env 01-05`), hero props (`#Prop 01-05`), and extras clusters (`#Extras 01-08`).

### 3.3 Studio 3: Cinematography & Visual Studio
- **Scope:** Steps 2, 8, 9, 10, and 11 of the cinematic pipeline.
- **Capabilities:**
  - Visual Style Selection: Manages catalog of 18 visual aesthetics (`#Style 01` Michael Bay through `#Style 18` Vintage Film).
  - Optical Physics Engine: Assigns lens characteristics (`#Lens 01-06`), depth of field, and bokeh geometries.
  - Camera & Composition Matrix: Assigns 34 camera angles (`#Cam 01-34`) and 8 composition geometries (`#Comp 01-08`).
  - Lighting Matrix: Manages 14 photometric setups (`#Light 01-14`), Kelvin color temperatures, and key-to-fill ratios.
  - Acting & Emotion Matrix: Assigns 24 psychological performance cues (`#Act 01-24`).
  - Motion Dynamics: Configures velocity profiles (`#Speed 01-05`) and multi-layer foreground/background parallax.

### 3.4 Studio 4: Storyboard & Previsualization Studio
- **Scope:** Operational Stage 09.
- **Capabilities:**
  - Generates visual keyframes for all 50 scenes using rapid text-to-image inference.
  - Assembles temporal animatics with rough scratch audio to evaluate narrative pacing before video generation.
  - Evaluates spatial camera blocking and visualizes the 180-degree line of action.

### 3.5 Studio 5: Prompt Compilation & Provider Studio
- **Scope:** Step 12 and Operational Stage 15.
- **Capabilities:**
  - Translates Master Production Bible entities into platform-native prompt syntax.
  - Supports provider adapters:
    * **Runway Gen-3 Alpha:** Text-to-Video and Image-to-Video camera control prompts.
    * **Kling 1.5:** Motion brush and high-dynamic-range video generation.
    * **Google Veo:** Photorealistic physics-compliant cinematic clips.
    * **Midjourney v6 / Flux:** Ultra-high-resolution keyframe character anchors.
    * **ElevenLabs:** Character voice cloning and dialogue audio synthesis.
  - Manages asynchronous job dispatching, exponential backoff retries, and quota limits.

### 3.6 Studio 6: Continuity & Quality Assurance Studio
- **Scope:** Operational Stage 16.
- **Capabilities:**
  - Computes automated continuity scorecards evaluating facial similarity, wardrobe condition, and lighting balance.
  - Flags continuity defects:
    * *Spatial Inversion:* Crossing the 180-degree line of action.
    * *Character Drift:* Cosine similarity between character facial embeddings `< 0.90`.
    * *Photometric Mismatch:* Sudden Kelvin jumps between sequential shots within the same scene.
  - Triggers automated regeneration workflows for scenes failing quality thresholds.

---

## 4. Master Production Bible (MPB) State Machine

Every scene and production entity transitions through an explicit state machine:

```
[Draft] ──> [Planned] ──> [Ready] ──> [Generating] ──> [QC_Evaluating] ──> [Approved] ──> [Locked]
                                            │                 │
                                            └── [Failed] <────┘ (Score < 85%)
                                                    │
                                                    └──> [Re-queued]
```

### State Definitions & Transition Criteria

| State | Prerequisites to Enter | Permissions & Mutation Rules |
| :--- | :--- | :--- |
| **`Draft`** | Project initialization. | Unrestricted edits to narrative parameters. |
| **`Planned`** | Story beat and scene slugline confirmed. | Scene parameters locked; visual direction can be edited. |
| **`Ready`** | All 11 pre-production steps completed and validated. | MPB variables become read-only; prompt compiled. |
| **`Generating`** | Provider job dispatched to generation API. | Entity locked against all modifications. |
| **`QC_Evaluating`**| Rendered video binary returned by provider. | Automated scoring algorithms analyze video frames. |
| **`Approved`** | Continuity Score `>= 85%` and human review passed. | Video asset linked to timeline. |
| **`Locked`** | Final film assembly approved by Showrunner. | Permanent immutable snapshot; cannot be altered. |
| **`Failed`** | Provider timeout, inference error, or QC `< 85%`. | Job tagged with failure reason; moved to retry queue. |

---

## 5. Non-Functional Requirements

### 5.1 Performance & Latency
- **Prompt Compilation:** The prompt compiler service must resolve and compile an MPB scene prompt in `<= 200ms`.
- **System Health Checks:** The `/health` endpoint must return database and engine status in `<= 50ms`.
- **Concurrent Job Dispatching:** The background task supervisor must manage at least 10 parallel video generation jobs without database lock contention.

### 5.2 Reliability & Fault Tolerance
- **Provider Resilience:** Generation requests encountering HTTP 429 (Rate Limit) or 503 (Provider Unavailable) must retry with exponential backoff (initial delay: 2.0s, backoff factor: 2.0, max attempts: 4).
- **Circuit Breaker:** If a provider fails 5 consecutive generation requests within a 3-minute window, the provider is temporarily paused, and jobs route to an alternate configured provider.
- **Transaction Atomicity:** All multi-entity database mutations must execute within ACID transaction blocks managed by the Unit of Work.

### 5.3 Security & Secret Isolation
- **Credential Storage:** AI provider API keys (Runway, Kling, OpenAI, ElevenLabs) must never be stored in plain text in the database. Keys must be sourced via environment variables (`.env`) or secure secret managers.
- **Scrubbing:** Generated prompts and logs must automatically scrub internal secrets, authorization headers, and personal identifying information before saving.

---

## 6. Acceptance Criteria

A production release of MovieAIProducer satisfies this PRD when:
1. All 12 steps of the cinematic pipeline can be configured, validated, and stored in the database.
2. The 50-scene structural breakdown successfully generates across 4 acts with 5.0-second scene pacing.
3. DNA tokens for characters, environments, and props remain immutable across all 50 scenes once locked.
4. Generative video prompts compile deterministically with correct matrix codes (`#Style`, `#Light`, `#Act`, `#Lens`, `#Comp`, `#Speed`).
5. Background worker jobs complete asynchronously with full error tracking and status reporting.
6. The test suite passes with 100% success on all architecture boundary, domain invariant, and database tests.
