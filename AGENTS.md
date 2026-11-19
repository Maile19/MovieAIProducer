# Agent Orchestration Architecture - MovieAIProducer

> Operational multi-agent architecture and swarm governance powered by the **Antigravity CLI (`agy`)** runtime.

MovieAIProducer utilizes an autonomous multi-agent orchestration architecture to produce 50-scene cinematic films. The orchestrator runtime is strictly powered by **Antigravity CLI (`agy`)**, replacing legacy single-agent scripts with a distributed, role-isolated agent swarm coordinated over an event-driven message board.

---

## 1. Orchestration Engine: Antigravity CLI (`agy`)

Antigravity CLI (`agy`) acts as the primary runtime coordinator. It manages process lifecycles, execution boundaries, contextual memory, and inter-agent message routing.

```
                    ┌────────────────────────────────────────┐
                    │       Antigravity CLI (`agy`)          │
                    │         Runtime Orchestrator           │
                    └──────────────────┬─────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │        Swarm Shared Message Board           │
                │     (Event-Driven, Reactive Wakeup)         │
                └──────┬───────────────┬───────────────┬──────┘
                       │               │               │
        ┌──────────────┴──────┐ ┌──────┴──────┐ ┌──────┴──────────────┐
        │     Coordinator     │ │   Worker 1  │ │   Worker 2          │
        │    (Showrunner)     │ │ (Core/Gov)  │ │ (Architecture/CDA)  │
        └─────────────────────┘ └─────────────┘ └─────────────────────┘
```

### 1.1 Core Principles of the `agy` Runtime

1. **Reactive Wakeup (Zero Polling Loops):** Agents never poll message boards or sleep in busy loops. The `agy` messaging bus delivers incoming events directly to agent contexts, waking them only when addressed by name (`@worker-name`) or broadcast (`@all`).
2. **Context Sandboxing:** Subagents run in isolated execution contexts. They share no hidden state, in-memory pointers, or ambient session variables.
3. **Workspace Isolation:** When authoring code or parallelizing builds, workers run in dedicated branches or git worktrees (`workspace: "share"` or `workspace: "branch"`), preventing write collisions.
4. **Deterministic Token Economy:** Agents remain asleep until an event explicitly calls upon them, preserving context windows and token budgets.

---

## 2. Production Swarm Roster

Film production requires distinct specialized disciplines. MovieAIProducer divides responsibilities across specialized agents governed by the `agy` runtime.

| Agent Name | Production Discipline | Primary Responsibilities | Deliverables |
| :--- | :--- | :--- | :--- |
| **`coordinator`** | Showrunner & Lead Producer | Project lifecycle, step sequencing, user approval gating, worker dispatching, and swarm status tracking. | Master Production Plan, stage transitions, final approval logs. |
| **`script-architect`** | Screenwriter & Story Editor | 4-act narrative arc, 50-scene structural breakdown, scene sluglines, dialogue, and 5-second pacing calibration. | Screenplay markdown, scene lists, voiceover scripts. |
| **`character-curator`** | Casting & Wardrobe Director | Character DNA generation, visual seeds, voice traits, and dynamic state evolution (`#State 01-05`). | Character Bibles, wardrobe registries, costume damage charts. |
| **`world-builder`** | Production Designer | Environment bibles (`#Env 01-05`), hero props (`#Prop 01-05`), and cultural crowd sheets (`#Extras 01-08`). | Environment registries, prop DNA manifests, set layouts. |
| **`visual-director`** | Cinematographer & Lighting Lead | Camera angles (`#Cam 01-34`), optical lenses (`#Lens 01-06`), framing geometry (`#Comp 01-08`), and lighting (`#Light 01-14`). | Shot lists, camera setups, lighting breakdown sheets. |
| **`prompt-compiler`** | AI Prompt Engineer | Translates Master Production Bible (MPB) specs into platform-optimized prompt syntax for AI generation backends. | Compiled generation prompts, negative prompt matrices, seed configs. |
| **`provider-dispatcher`** | Systems & Pipeline Engineer | Manages external generation jobs (Kling, Runway, Veo, ElevenLabs), handling async retries and rate limits. | Job execution logs, raw asset binaries, render manifests. |
| **`continuity-qc`** | Script Supervisor & QA Auditor | Enforces the 180-degree rule, spatial orientation, color palette fidelity, character visual drift, and audio J/L-cuts. | QC scorecards, defect reports, continuity flags. |
| **`swarm-monitor`** | Runtime Watchdog | Monitors the swarm message board on a scheduled timer, detects deadlocks or stalled agents, and wakes responsible workers. | Swarm health telemetry, heartbeat logs. |

---

## 3. Communication Protocols & Board Governance

All agents interact through the `agy` shared message board.

### 3.1 Message Board Directives

- **Targeted Addressing (`@agent-name`):** Messages must explicitly address the target agent. Untargeted messages do not wake sleeping agents.
- **Broadcast Protocol (`@all`):** Reserved exclusively for system-level announcements, architectural migrations, or emergency production stops.
- **Result-Driven Posting:** Agents post concrete outcomes, diff summaries, or structured errors. Vague status posts such as "Working on it" or "Acknowledged" are prohibited.
- **Completion Marker (`[done]`):** Final deliverables posted to the coordinator must start with `[done]` (for example: `@coordinator [done] Scene 04 prompt compilation complete`).

### 3.2 Swarm Primitives

Workers interact with the board using the following primitives:

```python
# Read incoming messages after the last seen sequence ID
board = read_board(since=last_seq_id)

# Post structured deliverable to the message bus
post_message(text="@continuity-qc Ready for inspection on Scene 12 shot list.")

# Sleep immediately until woken by an explicit mention
swarm_wait(since=last_seq_id, mentions_only=True)
```

---

## 4. Multi-Agent Production Workflows

MovieAIProducer executes the 12-Step Cinematic Pipeline across five structured agent phases:

```
[Phase 1: Creative Ideation] ──> [Phase 2: Master Production Bible] ──> [Phase 3: Visual Engineering]
          │                                                                      │
          └──────────────────────────┐                                           │
                                     ▼                                           ▼
                       [Phase 5: QC & Delivery] <── [Phase 4: Provider Generation]
```

### Phase 1: Creative Brief & Narrative Blueprint (Steps 1–3)
- **Agents:** `coordinator`, `script-architect`.
- **Workflow:** The coordinator ingests the creative brief (Genre, Emotion, Aspect Ratio). `script-architect` drafts the 50-scene blueprint across 4 acts.
- **Gate:** Human director reviews and confirms narrative arc before proceeding.

### Phase 2: Master Production Bible & Asset DNA (Steps 4–6)
- **Agents:** `character-curator`, `world-builder`.
- **Workflow:** Character DNA tokens, voice seeds, and `#State 01-05` progressions are locked. Environments (`#Env 01-05`) and hero props (`#Prop 01-05`) are compiled into the MPB.
- **Gate:** DNA Locking Invariant: Once approved, character and world variables become immutable.

### Phase 3: Technical Directing & Cinematography (Steps 7–11)
- **Agents:** `visual-director`, `script-architect`.
- **Workflow:** `script-architect` calibrates 5-second dialogue beats and audio transitions (J/L-cuts). `visual-director` assigns camera setups (`#Cam 01-34`), lens profiles (`#Lens 01-06`), lighting keys (`#Light 01-14`), and motion speeds (`#Speed 01-05`).
- **Gate:** Cinematography feasibility check; spatial continuity verification.

### Phase 4: Prompt Compilation & Provider Generation (Step 12)
- **Agents:** `prompt-compiler`, `provider-dispatcher`.
- **Workflow:** `prompt-compiler` resolves MPB tokens into target provider schemas (e.g., Runway Gen-3 text-to-video, Kling image-to-video, ElevenLabs voice cloning). `provider-dispatcher` dispatches async generation jobs with retry budgets.
- **Gate:** Generation completion without HTTP or model inference errors.

### Phase 5: QC Auditing & Editorial Delivery (Step 12 Post-Processing)
- **Agents:** `continuity-qc`, `coordinator`.
- **Workflow:** `continuity-qc` inspects rendered video frames for character drift, lighting consistency, 180-degree rule adherence, and audio alignment. Passing shots are marked `Approved` and `Locked`.
- **Gate:** QC score exceeds 95% threshold; human final sign-off.

---

## 5. Quality Gates & Governance Rules

Every agent operating within the MovieAIProducer ecosystem must adhere to five mandatory quality gates:

### 1. Kanban-First Protocol
No agent generates code or assets without an assigned task ticket in `TASKS.md` or a Kanban issue tracking ID. Work commences only on tasks in the `In Progress` state.

### 2. Test-Driven Development (TDD)
Software engineering tasks require tests to be authored before implementation code. The agent must verify failure, implement the solution, and verify test passage using `uv run pytest`.

### 3. Compliance & Architectural Review
Any proposed change affecting system interfaces, databases, or workflow pipelines must reference or author an Architecture Decision Record (ADR) in `docs/ADRs/` or `DECISIONS/ADR/` prior to landing.

### 4. Humanizer Standard
All generated documentation, commentary, dialogue, and scripts must comply with the Humanizer writing standards (`/home/ubuntu/.hermes/skills/creative/humanizer/SKILL.md`). Fluff phrases, hollow marketing clichés ("pivotal", "testament to", "seamless"), robotic enumerations, and AI boilerplate are strictly forbidden.

### 5. Architectural Clean Boundary
Agents must respect Clean Architecture layer boundaries:
- Domain layer models must never import from application, infrastructure, or presentation modules.
- Changes violating layer boundaries fail continuous integration (`tests/architecture/test_layer_boundaries.py`).

---

## 6. Antigravity Tooling & Customizations

Agents have access to a suite of native Antigravity tools and skills to execute their work:

- **`codebase-memory-mcp`:** Structural code discovery via knowledge graph queries (`search_graph`, `trace_path`, `check_index_coverage`). Used before any refactor or architectural audit.
- **`run_workflow`:** Python workflow orchestration engine for complex parallel execution pipelines.
- **`manage_task` & `run_command`:** Async task supervision and deterministic shell execution in isolated Linux sessions.
- **`read_file`, `write_file`, `edit_file`:** Safe, atomic file operations with precise boundary inspection.
