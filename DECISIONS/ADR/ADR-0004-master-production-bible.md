# ADR-0004: Master Production Bible

- Project: MovieAIProducer
- ADR ID: ADR-0004
- Title: Master Production Bible as the Single Source of Truth
- Status: Proposed
- Date: 2026-11-19
- Decision Owners: Project Architecture
- Decision Scope: Canonical creative and production data governance
- Version: 1.0

---

1. Context

MovieAIProducer coordinates a complete AI-assisted filmmaking workflow.

A single film project may contain hundreds of interconnected production specifications:

- Creative brief.
- Genre and emotional direction.
- Story structure.
- Screenplay and dialogue.
- Character identity and behavior.
- Character appearance and state.
- Environment and location specifications.
- Props and production design.
- Wardrobe, makeup, and prosthetics.
- Storyboard and shot specifications.
- Camera and lens direction.
- Lighting design.
- Acting and performance direction.
- Motion and physical behavior.
- Audio and voice direction.
- Generated media assets.
- Scene continuity.
- Quality-control results.
- Editorial and final delivery requirements.

These specifications influence one another.

For example, changing a character's wardrobe may affect multiple scenes, reference images, generated videos, and continuity validation.

Without a canonical source of truth, individual AI agents and production stages may produce conflicting versions of the same creative information.

The platform therefore requires a centralized production specification system with controlled revisions, traceability, and approval workflows.

2. Problem Statement

How should MovieAIProducer maintain consistency across all creative and production decisions?

The architecture must ensure:

1. One authoritative source for approved production specifications.
2. Structured relationships between production entities.
3. Controlled changes and revision history.
4. Traceability from creative decisions to generated outputs.
5. Consistency across scenes and shots.
6. Protection against unauthorized AI modifications.
7. Reproducible production execution.
8. Controlled propagation of approved changes.
9. Support for human review and approval.
10. Recovery from invalid or conflicting production changes.

The system must distinguish approved creative intent from generated outputs, temporary suggestions, and experimental variations.

3. Decision

Adopt the Master Production Bible (MPB) as the canonical Single Source of Truth for approved creative and production specifications.

All production stages must consume the relevant approved MPB data through controlled application interfaces.

AI agents, workflows, and provider adapters must not independently redefine canonical production specifications.

The MPB must support:

- Structured production entities.
- Versioned specifications.
- Revision history.
- Approval states.
- Dependency tracking.
- Change impact analysis.
- Scene and shot references.
- Asset provenance.
- Immutable historical snapshots.
- Controlled change propagation.
- Audit records.

The MPB is a logical domain capability, not necessarily one physical document or database table.

It may be implemented using multiple relational entities, structured documents, and references to media assets.

4. Core Principles

4.1 Single Source of Truth

Each canonical production specification must have one authoritative owner.

Examples:

- Character identity is owned by the Character domain.
- Environment specifications are owned by Production Design.
- Camera specifications are owned by Cinematography.
- Lighting specifications are owned by Lighting.
- Approved scene requirements are governed by the production workflow and MPB.

The MPB provides the canonical project-wide production view and resolves how these specifications are referenced together.

Single Source of Truth does not mean every data type must be stored in one table or one file.

4.2 Approved Data Is Authoritative

Only approved production data is authoritative for execution.

Drafts, suggestions, generated variations, and experimental outputs must be clearly distinguished from approved specifications.

4.3 AI Is Not an Autonomous Authority

AI agents may:

- Suggest changes.
- Identify inconsistencies.
- Generate alternatives.
- Analyze production constraints.
- Propose continuity corrections.
- Recommend improvements.

AI agents may not silently overwrite approved canonical data.

Changes to approved specifications require the configured approval process.

4.4 Traceability

Every important production output must be traceable to the specifications and revisions used to create it.

4.5 Reproducibility

The platform must preserve sufficient information to understand and reproduce a generation attempt, subject to provider availability and model version constraints.

4.6 Controlled Evolution

Production specifications may evolve, but changes must be versioned, reviewed, and auditable.

5. MPB Logical Structure

The MPB is composed of interconnected production domains.

5.1 Project Foundation

Contains:

- Project identity.
- Project title.
- Production objectives.
- Genre.
- Target audience.
- Language.
- Aspect ratio.
- Intended duration.
- Visual and emotional direction.
- Production constraints.
- Delivery requirements.

5.2 Story Bible

Contains:

- Premise.
- Logline.
- Synopsis.
- Themes.
- Narrative structure.
- Story arcs.
- Screenplay references.
- Scene sequence.
- Story logic.
- Narrative constraints.

5.3 Character Bible

Contains:

- Character identity.
- Character description.
- Personality.
- Behavioral traits.
- Physical appearance.
- Voice identity.
- Costume references.
- Character relationships.
- Character development.
- Character states.
- Reference assets.

Character identity must remain distinct from temporary scene-specific appearance or emotional state.

5.4 Environment Bible

Contains:

- Location identity.
- Environment descriptions.
- Geography and spatial layout.
- Architectural characteristics.
- Materials and textures.
- Weather.
- Time of day.
- Environmental conditions.
- Lighting references.
- Continuity constraints.

5.5 Prop and Production Design Bible

Contains:

- Prop identity.
- Physical characteristics.
- Scale.
- Material.
- Color.
- Ownership or assigned character.
- Scene usage.
- Initial and final state.
- Reference images.

5.6 Wardrobe and Appearance Bible

Contains:

- Costume identity.
- Clothing specifications.
- Material and color.
- Makeup.
- Hair.
- Prosthetics.
- Character assignment.
- Scene-specific variation.
- Continuity requirements.

5.7 Cinematography Bible

Contains:

- Camera configuration.
- Lens intent.
- Framing.
- Composition.
- Camera position.
- Movement.
- Focus behavior.
- Shot size.
- Aspect ratio constraints.
- Cinematography references.

Camera and lens descriptions represent production intent. Actual optical behavior depends on the selected generation or rendering system.

5.8 Lighting Bible

Contains:

- Lighting style.
- Key light direction.
- Fill light.
- Backlight.
- Practical lights.
- Color temperature.
- Contrast.
- Atmosphere.
- Time-of-day behavior.
- Scene lighting continuity.

5.9 Performance and Audio Bible

Contains:

- Acting direction.
- Emotional intent.
- Physical behavior.
- Dialogue.
- Voice characteristics.
- Accent and language.
- Audio cues.
- Music direction.
- Sound effects.
- Lip-sync requirements.

5.10 Motion Bible

Contains:

- Character movement.
- Object movement.
- Environmental movement.
- Physical interaction.
- Motion timing.
- Speed and acceleration intent.
- Gravity and collision constraints.
- Motion continuity.
- Camera-motion relationships.

Motion requirements must be defined according to scene needs. Every scene does not require the same number of motion layers.

5.11 Scene and Shot Bible

Contains:

- Scene identity.
- Scene order.
- Narrative purpose.
- Location.
- Characters present.
- Scene state.
- Shot list.
- Camera instructions.
- Lighting requirements.
- Performance instructions.
- Motion instructions.
- Dialogue and audio.
- Required assets.
- Continuity dependencies.
- Execution constraints.

5.12 Quality and Delivery Bible

Contains:

- Quality requirements.
- Validation rules.
- Approval criteria.
- Technical output requirements.
- Editorial constraints.
- Delivery formats.
- Acceptance status.

6. Authority and Data Ownership

The MPB coordinates canonical references while domain modules remain responsible for their own business data.

Domain| Canonical ownership
Creative Brief| Project creative objectives
Story| Narrative and screenplay
Character| Character identity and states
Production Design| Environments and props
Wardrobe| Costume and appearance
Cinematography| Camera and lens specifications
Lighting| Lighting specifications
Audio| Voice, dialogue, and sound requirements
Motion| Physical and movement constraints
Production Workflow| Execution and approval states
Continuity| Cross-scene consistency findings
Quality Control| Validation and acceptance results
Asset Management| Media files and asset metadata

The MPB references and assembles these canonical specifications into a consistent production context.

A domain module must not allow another module to bypass its approved write interface.

7. Versioning Strategy

The MPB must support project-level and entity-level versioning.

7.1 Project Revision

Each meaningful approved project change creates a new project revision.

Example:

- MPB v1.0
- MPB v1.1
- MPB v1.2
- MPB v2.0

Version numbering is a governance convention, not a substitute for database revision identifiers.

7.2 Entity Revision

Important entities may have independent revisions.

Examples:

- Character A revision 3.
- Environment B revision 2.
- Scene 12 revision 5.
- Shot 12B revision 2.

7.3 Revision Metadata

Each revision should record:

- Revision ID.
- Project ID.
- Entity ID.
- Previous revision.
- Change description.
- Changed fields.
- Author or responsible agent.
- Change source.
- Timestamp.
- Approval status.
- Approval identity.
- Related change request.

7.4 Immutable Approved Revisions

An approved revision must not be edited in place.

A correction creates a new revision.

Historical revisions must remain available according to retention policy.

8. Approval Lifecycle

The canonical specification lifecycle is:

1. DRAFT
2. IN_REVIEW
3. APPROVED
4. SUPERSEDED
5. ARCHIVED

Additional rejection or cancellation states may be introduced where needed.

Rules:

- Draft specifications may be edited by authorized actors.
- In-review specifications require explicit review decisions.
- Approved specifications become authoritative.
- Superseded specifications remain available for historical traceability.
- Archived specifications are retained according to project policy.
- Approval must identify the responsible actor.
- Approval must record the exact revision being approved.

AI-generated suggestions must never automatically become approved merely because generation completed successfully.

9. Change Management

Every meaningful modification to an approved specification must follow a controlled change process.

9.1 Change Request

A change request should contain:

- Change request ID.
- Target entity.
- Current revision.
- Proposed revision.
- Reason for change.
- Change origin.
- Affected scenes.
- Affected shots.
- Affected assets.
- Continuity risks.
- Production impact.
- Approval requirements.

9.2 Change Sources

Changes may originate from:

- Human user.
- Creative director.
- Production manager.
- Authorized AI agent.
- Quality-control recommendation.
- Continuity analysis.
- External asset import.
- Production workflow.

The origin must be recorded.

9.3 Change Impact Analysis

Before approval, the system should identify dependent production elements.

Example:

Changing a character's hair style may affect:

- Character reference images.
- Wardrobe and appearance specifications.
- Scene reference packages.
- Generated video assets.
- Continuity validation.
- Future scene prompts.

9.4 Controlled Propagation

An approved change does not automatically regenerate every dependent asset.

The system must classify affected items:

- Information-only update.
- Revalidation required.
- Prompt recompilation required.
- Asset regeneration recommended.
- Asset regeneration required.
- Human review required.

Critical dependencies must block production approval until resolved.

10. Scene and Shot Context Resolution

Every production execution must resolve the appropriate MPB context.

A scene or shot context may include:

1. Project-level specifications.
2. Story and screenplay revisions.
3. Relevant character revisions.
4. Relevant environment revisions.
5. Relevant prop revisions.
6. Wardrobe and appearance revisions.
7. Cinematography specifications.
8. Lighting specifications.
9. Performance and audio requirements.
10. Motion requirements.
11. Scene-specific overrides.
12. Approved continuity constraints.

The resolved context must be deterministic for a given set of revision references.

The system must not silently select arbitrary latest revisions when a production job requires specific approved versions.

11. Overrides and Exceptions

Scene-specific requirements may override general production defaults only through explicit rules.

Each override must contain:

- Target specification.
- Overridden field.
- Original value.
- New value.
- Reason.
- Scope.
- Approval status.
- Applicable scene or shot.
- Effective revision.

Rules:

- Overrides must be scoped.
- Overrides must not modify global canonical values.
- Critical conflicts must be flagged.
- Unapproved overrides cannot drive production execution.
- Expired or superseded overrides must not remain active accidentally.

12. AI Agent Rules

AI agents must interact with MPB through authorized application interfaces.

Read Access

Agents may read the approved context necessary for their assigned tasks.

Access must respect project permissions and data minimization.

Proposal Access

Agents may submit:

- New draft entities.
- Proposed revisions.
- Continuity findings.
- Alternative creative options.
- Production recommendations.

Write Access

Direct modification of approved specifications is prohibited.

Approved changes must pass the configured change-management and approval process.

Agent Traceability

Every AI-originated proposal should record:

- Agent identity.
- Model and provider.
- Task or workflow ID.
- Input revision references.
- Output revision reference.
- Prompt or instruction reference.
- Timestamp.
- Validation results.

AI output must remain distinguishable from human-approved decisions.

13. Generated Asset Provenance

Every generated or imported asset must preserve its production provenance.

Recommended metadata:

- Asset ID.
- Project ID.
- Scene ID.
- Shot ID.
- Asset type.
- Asset source.
- MPB revision reference.
- Entity revision references.
- Canonical prompt reference.
- Compiled prompt reference.
- Provider ID.
- Model ID.
- Adapter version.
- Generation job ID.
- Generation parameters.
- Creation timestamp.
- Validation status.
- Approval status.
- Parent asset reference, if derived from another asset.

An asset may be technically valid but still fail production requirements.

Asset approval must therefore remain separate from generation success.

14. Continuity Integration

The MPB provides the canonical specifications used by the Continuity Engine.

Continuity validation should evaluate:

- Character appearance.
- Character position and state.
- Costume consistency.
- Prop state.
- Environment layout.
- Time and weather.
- Lighting continuity.
- Scene transitions.
- Dialogue and performance continuity.
- Motion and spatial relationships.

The Continuity Engine may identify conflicts and recommend changes.

It must not silently rewrite canonical specifications.

See ADR-0009: Continuity Engine.

15. Data Integrity and Concurrency

The MPB implementation must protect against conflicting modifications.

Requirements:

- Revision-based concurrency control.
- Optimistic locking where appropriate.
- Transactional approval operations.
- Unique revision identifiers.
- Referential integrity.
- Audit records.
- Validated state transitions.
- Idempotent change submission where necessary.

If two users or agents propose changes based on the same revision, the system must detect the conflict.

It must not silently overwrite one proposal with another.

Conflict resolution must preserve both histories.

16. Snapshot and Recovery Strategy

Production execution must use a reproducible snapshot of its approved specifications.

A production snapshot should record:

- Project revision.
- Scene and shot revisions.
- Relevant entity revisions.
- Approved overrides.
- Prompt compiler version.
- Provider and model references.
- Production configuration.
- Snapshot timestamp.

A snapshot is immutable after creation.

If canonical specifications change during execution, the running job must continue using its original snapshot unless an explicit restart or migration decision is approved.

The system must support restoration of previously approved revisions subject to project permissions and audit policy.

17. Consequences

Positive Consequences

- Consistent production specifications.
- Better character and environment continuity.
- Controlled creative changes.
- Reproducible generation context.
- Clear human and AI responsibility.
- Improved auditability.
- Reduced accidental production drift.
- Better integration between production stages.

Negative Consequences

- More complex data relationships.
- Revision and approval infrastructure required.
- Additional storage for historical data.
- Change impact analysis requires dependency tracking.
- More governance effort for production teams.
- Context resolution must be carefully designed.

Accepted Trade-offs

The platform prioritizes production consistency and traceability over unrestricted automatic modification.

Creative flexibility remains available through draft revisions and explicit scene-specific overrides.

18. Implementation Requirements

Implementation must follow this sequence:

1. Inspect the existing repository and current data model.
2. Identify existing project, scene, shot, character, and asset entities.
3. Define canonical ownership for each domain.
4. Define MPB project and entity revision contracts.
5. Implement approval lifecycle.
6. Implement revision history.
7. Implement change request handling.
8. Implement dependency and impact tracking.
9. Implement scene and shot context resolution.
10. Implement immutable production snapshots.
11. Integrate AI agent proposal interfaces.
12. Integrate continuity validation.
13. Integrate generated asset provenance.
14. Add audit and concurrency tests.
15. Validate an end-to-end scene production workflow.

Do not introduce one enormous JSON document as the only source of truth.

Do not duplicate domain-owned information without a clear synchronization strategy.

Do not build all revision and dependency mechanisms before validating the actual repository and MVP requirements.

19. Validation Criteria

- [ ] MPB is the canonical production specification system.
- [ ] Domain ownership is explicitly documented.
- [ ] Approved and draft data are distinguishable.
- [ ] Project and entity revisions are supported.
- [ ] Approved revisions cannot be modified in place.
- [ ] Approval records identify the exact approved revision.
- [ ] AI agents cannot silently overwrite approved specifications.
- [ ] Change requests preserve their origin and rationale.
- [ ] Change impact analysis identifies dependent production elements.
- [ ] Scene and shot context resolution is deterministic.
- [ ] Scene-specific overrides are scoped and auditable.
- [ ] Production snapshots preserve exact revision references.
- [ ] Generated assets retain production provenance.
- [ ] Continuity findings do not automatically mutate canonical data.
- [ ] Concurrent modifications are detected.
- [ ] Historical revisions can be retrieved.
- [ ] A complete scene execution can be traced to its MPB snapshot.
- [ ] Automated tests verify approval, revision, and concurrency rules.

Documentation alone does not satisfy implementation validation.

20. Review Conditions

Review this ADR when:

- Domain ownership changes.
- A new production specification category is introduced.
- Revision or approval policies materially change.
- Collaborative editing introduces new concurrency requirements.
- External production systems become authoritative sources.
- Snapshot size or retrieval performance becomes a significant issue.
- A major change affects production provenance.

Material changes to this decision require a superseding ADR.

21. Related Documents

- BRD.md
- PRD.md
- ARCHITECTURE.md
- AI_PIPELINE.md
- DATA_MODEL.md
- AGENTS.md
- PROMPTS.md
- API_SPEC.md
- SECURITY.md
- ERROR_HANDLING.md
- TEST_STRATEGY.md
- BACKUP_RECOVERY.md
- ADR-0001: Architecture Style
- ADR-0002: Application Structure
- ADR-0003: Provider Adapter System
- ADR-0005: Production Workflow Engine
- ADR-0006: Data Storage Strategy
- ADR-0008: Prompt Compilation Engine
- ADR-0009: Continuity Engine
- ADR-0010: Quality Control Engine
- ADR-0012: Asset Storage

22. Final Decision Summary

MovieAIProducer adopts the Master Production Bible as the Single Source of Truth for approved creative and production specifications.

The MPB will coordinate domain-owned data through versioned references, explicit approvals, immutable production snapshots, and controlled change propagation.

AI agents may propose creative and technical changes, but approved production specifications remain under explicit governance.

Every important production output must be traceable to the exact production context used during its execution.

Decision status: Proposed.

This ADR establishes the canonical production data governance strategy. It does not claim that MPB revisioning, approval workflows, or snapshot mechanisms have already been implemented or tested in the repository.
