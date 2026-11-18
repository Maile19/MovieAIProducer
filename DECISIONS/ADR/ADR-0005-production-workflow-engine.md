# ADR-0005: Production Workflow Engine

- Project: MovieAIProducer
- ADR ID: ADR-0005
- Title: Production Workflow Engine
- Status: Proposed
- Date: 2026-11-19
- Decision Owners: Project Architecture
- Decision Scope: Production lifecycle orchestration and execution management
- Version: 1.0

---

1. Context

MovieAIProducer coordinates a multi-stage AI-assisted filmmaking process.

The production lifecycle includes 16 major stages:

1. Creative Brief & Film Strategy.
2. Visual Concept & Style Bible.
3. Story Architecture & Screenplay.
4. Script Breakdown & Production Feasibility.
5. Character Casting & Character Bible.
6. Extras, Crowd & Creature Design.
7. Production Design & Environment Bible.
8. Wardrobe, Makeup & Prosthetics Bible.
9. Storyboard, Animatic & Previsualization.
10. Director's Scene Direction.
11. Cinematography & Camera Engineering.
12. Lighting & Atmospheric Engineering.
13. Performance, Dialogue & Voice Direction.
14. Motion, Physics & Continuity Engineering.
15. AI Production Orchestration.
16. Scene Execution, Editorial & Final QC.

These stages have dependencies, approval requirements, production tasks, and potentially long-running AI generation operations.

Some stages are sequential, while others may execute in parallel.

For example:

- Character and environment development may overlap after story requirements are sufficiently stable.
- Wardrobe development depends on character identity and production context.
- Cinematography and lighting specifications may be developed collaboratively.
- Multiple independent scenes may enter production concurrently.
- Final quality control depends on completed outputs and validation results.

A simple linear workflow cannot represent these relationships reliably.

The platform requires a workflow engine that can coordinate dependencies, control execution, preserve progress, and recover from failures.

2. Problem Statement

How should MovieAIProducer coordinate complex production workflows while preserving consistency and execution reliability?

The system must support:

1. Configurable production stages.
2. Dependency-aware execution.
3. Scene and shot task orchestration.
4. Parallel execution where safe.
5. Human approval gates.
6. AI agent task assignment.
7. Long-running generation jobs.
8. Retry and recovery.
9. Pause, resume, and cancellation.
10. Production progress tracking.
11. Dependency invalidation after approved changes.
12. Traceable execution history.
13. Multiple production projects.
14. Controlled workflow evolution.

The workflow engine must distinguish production stage completion from individual task completion and from generated asset approval.

3. Decision

Adopt a persistent, dependency-aware Production Workflow Engine using explicit state machines, task orchestration, and event-driven coordination.

The engine will manage the production lifecycle as a structured graph of stages, tasks, approvals, and dependencies.

It will support:

- Project-level workflows.
- Stage-level workflows.
- Scene-level workflows.
- Shot-level workflows.
- Task-level execution.
- Human and AI task ownership.
- Synchronous and asynchronous operations.
- Parallel task execution.
- Approval gates.
- Persistent state.
- Recovery and retry.
- Audit history.
- Progress aggregation.

The engine must remain independent of individual AI providers and generation tools.

Provider-specific execution is delegated to the Provider Adapter System.

See ADR-0003: Provider Adapter System.

4. Architecture Options Considered

Option A: Linear Sequential Pipeline

Every production stage executes in a fixed order.

Advantages:

- Simple implementation.
- Easy progress tracking.
- Predictable execution.

Disadvantages:

- Cannot efficiently represent parallel work.
- Difficult to handle conditional dependencies.
- Poor flexibility for different production types.
- Difficult recovery from partial failure.
- Rework can unnecessarily restart later stages.

Assessment: Rejected as the primary architecture.

A linear sequence may still be used for workflows that genuinely require strict ordering.

Option B: Event-Driven Workflow Without Persistent Orchestration

Components communicate through events and independently react to changes.

Advantages:

- Loose coupling.
- Flexible event handling.
- Natural support for asynchronous operations.

Disadvantages:

- Difficult global state management.
- Complex recovery and debugging.
- Harder to determine overall production status.
- Event ordering and duplicate delivery require careful handling.
- Difficult human approval coordination.

Assessment: Rejected as the sole orchestration strategy.

Event-driven communication remains useful within the selected architecture.

Option C: Persistent State Machine and Dependency-Aware Workflow Graph

A persistent workflow engine manages explicit execution states and dependency relationships.

Advantages:

- Reliable progress tracking.
- Explicit execution rules.
- Supports parallel tasks.
- Better failure recovery.
- Human approval integration.
- Auditable state transitions.
- Adaptable production workflows.

Disadvantages:

- More complex initial design.
- Requires persistent execution history.
- Dependency and state transitions must be carefully validated.

Assessment: Selected.

5. Workflow Hierarchy

The system will use a hierarchical workflow structure.

5.1 Project Workflow

Represents the complete production lifecycle of a film project.

Responsibilities:

- Overall production status.
- Workflow configuration.
- Stage dependencies.
- Project-level approval.
- Production progress.
- Final delivery status.

5.2 Stage Workflow

Represents one of the 16 major production stages.

Responsibilities:

- Stage objectives.
- Required inputs.
- Expected outputs.
- Completion criteria.
- Approval requirements.
- Stage dependencies.
- Stage-level progress.

5.3 Scene Workflow

Represents the production lifecycle of an individual scene.

Responsibilities:

- Scene requirements.
- Required production assets.
- Scene-specific tasks.
- Continuity checks.
- Scene approvals.
- Execution status.

5.4 Shot Workflow

Represents the production process of an individual shot.

Responsibilities:

- Shot specifications.
- Prompt compilation.
- Provider execution.
- Output validation.
- Asset selection.
- Shot approval.

5.5 Task Execution

Represents an individual actionable unit of work.

Examples:

- Generate character reference.
- Validate scene continuity.
- Compile video prompt.
- Submit video generation.
- Review generated shot.
- Approve lighting specifications.

Tasks may be assigned to:

- Human users.
- AI agents.
- Internal services.
- External provider integrations.

6. Workflow Graph

The production workflow must support a directed dependency graph.

Each node represents a stage, task, or production operation.

Each edge represents a dependency.

Supported dependency types:

- FINISH_TO_START.
- START_TO_START.
- FINISH_TO_FINISH.
- EXPLICIT_APPROVAL.
- CONDITIONAL_DEPENDENCY.
- DATA_DEPENDENCY.

The MVP may implement a smaller subset initially, provided unsupported dependency types are not presented as operational features.

Dependency Rules

- A task cannot execute before mandatory dependencies are satisfied.
- Conditional dependencies must have explicit evaluation rules.
- Approval dependencies require a valid approval record.
- Circular dependencies must be rejected.
- Failed prerequisites must prevent dependent execution when required.
- Optional dependencies must be explicitly marked.
- Dependency changes must be audited.

The workflow engine must distinguish blocking dependencies from informational relationships.

7. Production Workflow State Machine

7.1 Project States

Recommended canonical states:

1. DRAFT
2. READY
3. IN_PROGRESS
4. PAUSED
5. BLOCKED
6. REVIEW
7. COMPLETED
8. CANCELLED
9. ARCHIVED

7.2 Stage States

1. NOT_STARTED
2. READY
3. IN_PROGRESS
4. WAITING_APPROVAL
5. BLOCKED
6. FAILED
7. COMPLETED
8. SKIPPED
9. CANCELLED

7.3 Task States

1. CREATED
2. READY
3. QUEUED
4. RUNNING
5. WAITING_EXTERNAL
6. WAITING_APPROVAL
7. RETRY_PENDING
8. BLOCKED
9. SUCCEEDED
10. FAILED
11. CANCELLED
12. EXPIRED

7.4 State Transition Rules

Every state transition must be validated.

Rules:

- Invalid transitions must be rejected.
- Every transition must record its origin.
- Human approval transitions must identify the responsible user.
- Automated transitions must identify the responsible agent or service.
- Terminal states must not be reopened without an explicit recovery or new execution operation.
- Repeated event delivery must not create duplicate state changes.
- State changes must be persisted before dependent operations are triggered.

The state machine must be implemented centrally rather than duplicated across API handlers and frontend components.

8. Sixteen Production Stage Definitions

Stage 01: Creative Brief & Film Strategy

Inputs:

- User creative requirements.
- Production objectives.
- Target audience.
- Constraints.

Outputs:

- Approved creative brief.
- Project production scope.
- Initial success criteria.

Gate:

- Creative brief approval.

Stage 02: Visual Concept & Style Bible

Inputs:

- Approved creative brief.

Outputs:

- Visual direction.
- Style references.
- Color and atmosphere specifications.
- Visual consistency rules.

Gate:

- Visual direction approval.

Stage 03: Story Architecture & Screenplay

Inputs:

- Approved creative brief.
- Visual and narrative constraints.

Outputs:

- Story structure.
- Character arcs.
- Screenplay.
- Scene sequence.
- Dialogue.

Gate:

- Story and screenplay approval.

Stage 04: Script Breakdown & Production Feasibility

Inputs:

- Approved screenplay.

Outputs:

- Scene breakdown.
- Production requirements.
- Estimated complexity.
- Required assets.
- Production feasibility assessment.

Gate:

- Production scope approval.

Stage 05: Character Casting & Character Bible

Inputs:

- Approved screenplay.
- Character requirements.

Outputs:

- Character profiles.
- Character appearance.
- Personality and behavior.
- Voice identity.
- Reference assets.

Gate:

- Character approval.

Stage 06: Extras, Crowd & Creature Design

Inputs:

- Scene breakdown.
- Approved character specifications.

Outputs:

- Extras and crowd specifications.
- Creature designs.
- Crowd behavior.
- Supporting character references.

Gate:

- Required supporting-entity approval.

Stage 07: Production Design & Environment Bible

Inputs:

- Approved scenes.
- Character and location requirements.

Outputs:

- Environment specifications.
- Prop specifications.
- Location references.
- Spatial continuity rules.

Gate:

- Production design approval.

Stage 08: Wardrobe, Makeup & Prosthetics Bible

Inputs:

- Character Bible.
- Environment and scene context.

Outputs:

- Costume specifications.
- Makeup references.
- Hair specifications.
- Prosthetic requirements.
- Appearance continuity rules.

Gate:

- Appearance approval.

Stage 09: Storyboard, Animatic & Previsualization

Inputs:

- Approved screenplay.
- Character and environment references.

Outputs:

- Storyboards.
- Shot sequences.
- Animatic references.
- Timing and visual planning.

Gate:

- Previsualization approval.

Stage 10: Director's Scene Direction

Inputs:

- Approved scenes and previsualization.

Outputs:

- Scene objectives.
- Performance direction.
- Emotional progression.
- Blocking and staging instructions.

Gate:

- Directorial approval.

Stage 11: Cinematography & Camera Engineering

Inputs:

- Scene direction.
- Storyboard.
- Visual style.

Outputs:

- Shot framing.
- Camera positions.
- Lens intent.
- Camera movement.
- Composition instructions.

Gate:

- Cinematography approval.

Stage 12: Lighting & Atmospheric Engineering

Inputs:

- Scene specifications.
- Environment.
- Cinematography.

Outputs:

- Lighting plans.
- Light direction.
- Color temperature.
- Atmosphere.
- Lighting continuity requirements.

Gate:

- Lighting approval.

Stage 13: Performance, Dialogue & Voice Direction

Inputs:

- Approved screenplay.
- Character and scene specifications.

Outputs:

- Acting direction.
- Dialogue performance.
- Voice requirements.
- Audio cues.
- Lip-sync requirements where needed.

Gate:

- Performance and audio approval.

Stage 14: Motion, Physics & Continuity Engineering

Inputs:

- Approved scene and shot specifications.
- Character and environment states.

Outputs:

- Motion instructions.
- Physical interaction constraints.
- Movement timing.
- Continuity requirements.
- Validation rules.

Gate:

- Motion and continuity approval.

Stage 15: AI Production Orchestration

Inputs:

- Approved production specifications.
- Provider capability registry.
- Generation requirements.

Outputs:

- Execution plans.
- Provider and model selections.
- Compiled prompts.
- Generation jobs.
- Asset references.

Gate:

- Production execution authorization.

Stage 16: Scene Execution, Editorial & Final QC

Inputs:

- Approved production execution plan.
- Generated and imported assets.

Outputs:

- Selected production shots.
- Edited scenes.
- Audio and visual assembly.
- QC reports.
- Final deliverables.

Gate:

- Final quality and delivery approval.

The 16 stages define the production framework. They do not require every project to use identical tasks, durations, or approval gates.

9. Workflow Configuration

The workflow engine must support configurable production templates.

A template may define:

- Stage sequence.
- Stage dependencies.
- Required deliverables.
- Optional stages.
- Approval gates.
- Task templates.
- Quality requirements.
- Execution constraints.

Different production types may use different workflow templates.

Examples:

- Short film.
- Feature film.
- Commercial.
- Music video.
- Social media film.
- Experimental film.

The initial implementation should prioritize one complete reference workflow before supporting every production type.

A project must retain the workflow template version used when its execution was created.

10. Human Approval Gates

Human approval is required at explicitly configured decision points.

Approval records should contain:

- Approval ID.
- Project ID.
- Stage ID.
- Task or deliverable reference.
- Revision reference.
- Approver identity.
- Approval decision.
- Comments.
- Timestamp.

Supported decisions:

- APPROVED.
- REJECTED.
- NEEDS_REVISION.
- DEFERRED.

Rules:

- Approval must reference an exact revision.
- A new revision invalidates an approval only according to configured dependency rules.
- AI agents cannot impersonate human approval.
- Rejection must preserve review history.
- Critical production gates must block downstream execution until resolved.

11. Task Assignment and Agent Orchestration

The engine must support multiple execution actors.

Human Tasks

Examples:

- Review screenplay.
- Approve character design.
- Select final video output.
- Resolve continuity conflicts.

AI Agent Tasks

Examples:

- Analyze screenplay.
- Generate scene breakdown.
- Review character consistency.
- Compile provider prompts.
- Evaluate output quality.

System Tasks

Examples:

- Validate data.
- Generate production snapshots.
- Calculate task dependencies.
- Record usage.
- Publish workflow events.

External Provider Tasks

Examples:

- Submit image generation.
- Submit video generation.
- Generate dialogue audio.
- Retrieve generated output.

Task assignments must include:

- Responsible actor.
- Required permissions.
- Input references.
- Expected output.
- Execution constraints.
- Timeout.
- Retry policy.
- Acceptance criteria.

An agent completing a task does not automatically mean the associated production deliverable is approved.

12. Parallel Execution

The workflow engine may execute independent tasks in parallel.

Examples:

- Character reference generation for different characters.
- Independent environment concept development.
- Independent scene analysis.
- Separate shot generation jobs.
- Independent asset validation.

Parallel execution must respect shared dependencies.

Rules:

- Dependencies must be satisfied first.
- Shared canonical data must not be concurrently overwritten.
- Task concurrency must be configurable.
- Provider rate limits must be respected.
- Project resource limits must be enforced.
- Results must be associated with the correct task and production snapshot.

Parallel execution must not compromise narrative or visual continuity.

13. Long-Running Operations

AI generation and media processing may take substantial time.

The workflow engine must not hold HTTP requests open while waiting for long-running operations.

Instead:

1. Create a task.
2. Validate its prerequisites.
3. Persist the task.
4. Submit it to the execution queue.
5. Execute through an appropriate worker or provider adapter.
6. Record status changes.
7. Retrieve results.
8. Validate outputs.
9. Publish completion events.
10. Update workflow progress.

Long-running jobs must be recoverable after application or worker restarts.

See ADR-0007: Async Job Processing.

14. Pause, Resume, and Cancellation

The engine must support project and task control.

Pause

Pausing a project prevents new eligible work from being scheduled.

Already running external provider jobs may continue unless cancellation is explicitly supported and requested.

Resume

Resuming re-evaluates dependencies and schedules eligible tasks.

Cancellation

Cancellation must distinguish:

- Cancel requested.
- Cancellation confirmed.
- Cancellation unsupported.
- Provider operation already completed.

The system must not report an external job as cancelled without confirmation.

Recovery

Recovery must restore persisted workflow state and identify:

- Tasks interrupted by process failure.
- Jobs with uncertain provider status.
- Expired leases.
- Missing output references.
- Incomplete state transitions.

15. Failure and Retry Management

Failures must be classified by severity and retryability.

Examples:

- Validation failure.
- Missing prerequisite.
- Provider failure.
- Timeout.
- Permission failure.
- Output rejection.
- Human rejection.
- Infrastructure failure.

Rules:

- Retry only eligible operations.
- Preserve failed execution history.
- Do not overwrite previous successful outputs.
- Respect provider idempotency requirements.
- Prevent unlimited retry loops.
- Escalate persistent failures for review.
- Re-evaluate dependent tasks after recovery.

A failed task must not automatically mark the entire project as failed unless its failure blocks required production completion.

16. Rework and Dependency Invalidation

Production specifications may change after downstream work has started.

The workflow engine must support controlled rework.

Example:

If a character's approved appearance changes:

1. Create a new character revision.
2. Analyze dependent scenes and shots.
3. Identify affected prompts and assets.
4. Mark dependent work for review.
5. Recompile prompts where required.
6. Regenerate affected outputs when authorized.
7. Revalidate continuity.
8. Preserve previous production history.

The system must not indiscriminately restart every stage.

Rework scope must be determined from explicit dependency relationships.

The Master Production Bible remains authoritative for approved production specifications.

See ADR-0004: Master Production Bible.

17. Progress Tracking

Progress must be calculated from persisted workflow state.

The platform should expose:

- Project progress.
- Stage progress.
- Scene progress.
- Shot progress.
- Task progress.
- Approval completion.
- Blocked task count.
- Failed task count.
- Active generation jobs.
- Estimated remaining work, when sufficient data exists.

Progress must not be calculated solely by counting completed stages.

Tasks may have different weights and importance.

The initial implementation may use transparent task-weighted progress.

Estimated completion time must be labeled as an estimate, not a guaranteed deadline.

18. Workflow Events

The engine should publish normalized domain or application events.

Examples:

- project_workflow_created
- project_workflow_started
- stage_started
- stage_blocked
- stage_completed
- task_created
- task_queued
- task_started
- task_waiting_approval
- task_succeeded
- task_failed
- approval_requested
- approval_granted
- approval_rejected
- workflow_paused
- workflow_resumed
- workflow_cancel_requested
- workflow_completed
- dependency_invalidated

Event requirements:

- Stable event identity.
- Event type.
- Schema version.
- Aggregate identity.
- Timestamp.
- Correlation ID.
- Causation ID.
- Actor identity.
- Relevant revision references.

Consumers must handle duplicate delivery safely.

Events are records of meaningful changes, not a substitute for authoritative workflow state.

19. Persistence and Consistency

Workflow state must be persisted.

Required logical records include:

- Workflow definition.
- Workflow instance.
- Workflow version.
- Stage instance.
- Task instance.
- Dependency.
- Execution attempt.
- Approval.
- State transition.
- Workflow event.
- Execution result.
- Production snapshot reference.

Critical state transitions must be transactional.

Queue submission must not create a state where a task appears queued but has been permanently lost.

A transactional outbox or equivalent reliable publication mechanism should be considered when event publication is separated from database transactions.

20. Workflow Security

The engine must enforce:

- Project ownership.
- Role-based task permissions.
- Approval permissions.
- Agent authorization.
- Restricted execution actions.
- Audit logging.
- Protected provider credentials.
- Input and output validation.

AI agents may only execute actions permitted by their assigned role and task scope.

A task ID alone must never grant access to project data.

21. Consequences

Positive Consequences

- Reliable production orchestration.
- Clear execution states.
- Better progress visibility.
- Support for parallel production work.
- Controlled human approvals.
- Recoverable long-running tasks.
- More precise rework handling.
- Traceable production history.
- Provider-independent workflow execution.

Negative Consequences

- More complex state management.
- Persistent execution history increases storage requirements.
- Dependency graphs require careful validation.
- Workflow versioning requires migration strategy.
- Concurrency and recovery need thorough testing.
- Event handling introduces additional consistency concerns.

Accepted Trade-offs

The platform prioritizes durable and auditable workflow execution over a simplistic linear pipeline.

The MVP should implement a minimal but reliable workflow engine rather than adopting a complex distributed orchestration platform prematurely.

22. Implementation Requirements

Implementation must follow this sequence:

1. Inspect the existing repository and identify current workflow logic.
2. Map current production stages and task responsibilities.
3. Define workflow and task domain models.
4. Define canonical state machines.
5. Implement transition validation.
6. Implement persistent workflow instances.
7. Implement dependency graph validation.
8. Implement task scheduling.
9. Implement human approval gates.
10. Implement asynchronous task execution.
11. Integrate Provider Adapter System.
12. Implement pause and resume.
13. Implement failure recovery.
14. Implement workflow event recording.
15. Implement progress aggregation.
16. Integrate MPB revision references.
17. Implement dependency invalidation and rework.
18. Add authorization and audit controls.
19. Add automated state and integration tests.
20. Validate one complete film production workflow.

Do not implement all 16 stages as fully automated workflows at once.

Start with one vertical workflow that proves:

- Stage transitions.
- Task dependencies.
- Human approval.
- AI execution.
- Asynchronous generation.
- Output validation.
- Recovery.
- MPB provenance.

Select implementation technology only after repository and operational requirements are audited.

23. Validation Criteria

- [ ] Project, stage, scene, shot, and task workflows are represented.
- [ ] Workflow definitions are versioned.
- [ ] Workflow instances persist across process restarts.
- [ ] State transitions are validated.
- [ ] Circular dependencies are rejected.
- [ ] Required dependencies block premature execution.
- [ ] Parallel execution respects dependency constraints.
- [ ] Human approvals reference exact revisions.
- [ ] AI task completion is distinct from human approval.
- [ ] Long-running operations execute asynchronously.
- [ ] Task execution history is preserved.
- [ ] Retry policies prevent uncontrolled execution loops.
- [ ] Pause and resume behavior is deterministic.
- [ ] Cancellation reports actual external execution status.
- [ ] Interrupted jobs can be recovered.
- [ ] Rework invalidates only affected dependencies.
- [ ] Progress reflects persisted execution state.
- [ ] Workflow events are traceable and versioned.
- [ ] Authorization is enforced at execution boundaries.
- [ ] At least one end-to-end production workflow passes integration testing.

Documentation alone does not satisfy implementation validation.

24. Review Conditions

Review this ADR when:

- Production workflow complexity materially increases.
- A dedicated workflow orchestration service becomes necessary.
- Parallel execution requirements change.
- Distributed execution becomes operationally necessary.
- Workflow definitions require major compatibility changes.
- Recovery requirements exceed current capabilities.
- Project-specific workflows introduce new dependency patterns.

Any material change to the selected architecture requires a superseding ADR.

25. Related Documents

- BRD.md
- PRD.md
- ARCHITECTURE.md
- AI_PIPELINE.md
- DATA_MODEL.md
- AGENTS.md
- API_SPEC.md
- SECURITY.md
- ERROR_HANDLING.md
- TEST_STRATEGY.md
- OBSERVABILITY.md
- BACKUP_RECOVERY.md
- ADR-0001: Architecture Style
- ADR-0002: Application Structure
- ADR-0003: Provider Adapter System
- ADR-0004: Master Production Bible
- ADR-0006: Data Storage Strategy
- ADR-0007: Async Job Processing
- ADR-0009: Continuity Engine
- ADR-0010: Quality Control Engine

26. Final Decision Summary

MovieAIProducer adopts a Persistent, Dependency-Aware Production Workflow Engine based on explicit state machines and task orchestration.

The engine coordinates all production levels, supports parallel execution where safe, enforces approval gates, and preserves recoverable execution history.

The 16 production stages define the overall production framework, while configurable workflow definitions determine the actual tasks and dependencies for each project.

All production execution must remain traceable to the approved Master Production Bible revision and associated production snapshot.

Decision status: Proposed.
