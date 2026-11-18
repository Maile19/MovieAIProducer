# ADR-0001: Architecture Style

- Project: MovieAIProducer
- ADR ID: ADR-0001
- Title: Architecture Style
- Status: Proposed
- Date: 2026-11-19
- Decision Owners: Project Architecture
- Decision Scope: Overall application architecture
- Version: 1.1

---

1. Context

MovieAIProducer is a professional AI-powered film production platform designed to manage the complete filmmaking workflow, from creative development to final production and quality control.

The platform coordinates multiple complex domains, including:

- Creative brief and film strategy.
- Story architecture and screenplay.
- Character and environment development.
- Production design and continuity.
- Storyboard and previsualization.
- Cinematography and lighting.
- Performance, dialogue, and audio.
- AI provider orchestration.
- Scene execution and production tracking.
- Editorial planning and final quality control.

The platform must support multiple AI providers, asynchronous generation jobs, complex production assets, structured creative data, and long-running workflows.

The architecture must therefore provide:

1. Clear separation of business responsibilities.
2. Maintainable and testable modules.
3. Independent evolution of production domains.
4. Provider-independent AI integration.
5. Reliable data consistency and workflow execution.
6. A migration path toward distributed services when justified.
7. A practical implementation strategy for the MVP.

The initial architecture must avoid unnecessary operational complexity while preserving the ability to scale.

2. Problem Statement

Which architecture style should be adopted for MovieAIProducer?

The selected architecture must balance:

- Development speed.
- Architectural clarity.
- Long-term maintainability.
- Testing and reliability.
- Deployment simplicity.
- Scalability.
- Operational cost.
- Future extensibility.

Premature microservices could introduce distributed-system complexity before the product requires it.

A traditional monolith without enforced boundaries could create tightly coupled modules and make future changes increasingly expensive.

The architecture decision must address both risks.

3. Decision

Adopt a Modular Monolith combined with Clean Architecture for the MVP and initial production releases.

The application will be deployed as one primary application system while its internal business domains remain modular and independently testable.

The architecture will enforce:

- Domain-oriented modules.
- Explicit module ownership.
- Separation of business logic from infrastructure.
- Dependency inversion.
- Provider-independent integration contracts.
- Controlled inter-module communication.
- Independent testing of domain logic.
- Clear boundaries for future service extraction.

The architecture is not a commitment to remain monolithic forever. It establishes a controlled evolution path based on measurable requirements.

4. Architecture Principles

4.1 Modular Monolith

The application runs as a cohesive deployment unit initially, but its internal modules have explicit responsibilities.

Each module owns its business rules and exposes controlled interfaces to other modules.

Modules must not directly manipulate another module's internal implementation.

4.2 Clean Architecture

Each domain module follows the dependency direction:

Domain → Application → Infrastructure / Presentation

The dependency rule is:

- Domain contains business entities, rules, and domain contracts.
- Application contains use cases and orchestration.
- Infrastructure implements persistence, external APIs, queues, and technical integrations.
- Presentation exposes HTTP APIs and user-facing interfaces.

Dependencies must point inward toward business rules.

Domain logic must not depend on FastAPI, React, database vendors, AI provider SDKs, or deployment infrastructure.

4.3 Separation of Concerns

Each component must have one clearly defined responsibility.

Business rules, workflow coordination, external integrations, persistence, and user interface logic must remain separated.

4.4 Explicit Contracts

Modules communicate through documented interfaces, application services, or domain events.

Direct access to another module's private repositories, tables, or internal services is prohibited unless explicitly approved through an architecture decision.

4.5 Provider Independence

AI provider integrations must be isolated behind provider adapters and normalized contracts.

The application must not make its core business logic dependent on one vendor's SDK or response format.

See ADR-0003: Provider Adapter System.

4.6 Testability

Domain and application logic must be testable without requiring:

- Live AI provider calls.
- Production databases.
- External network access.
- A running frontend.
- Production deployment infrastructure.

Infrastructure integrations require separate integration and contract tests.

5. Architecture Options Considered

Option A: Traditional Monolith

All application components are developed in one codebase with limited or informal internal boundaries.

Advantages:

- Simple initial deployment.
- Low operational overhead.
- Fast initial development.

Disadvantages:

- High risk of tight coupling.
- Unclear module ownership.
- Difficult independent testing.
- Increasing regression risk as features grow.
- Difficult future extraction of business domains.

Assessment: Not selected because MovieAIProducer has multiple complex production domains requiring strict internal boundaries.

Option B: Microservices

Each major business domain operates as an independently deployed service.

Advantages:

- Independent deployment.
- Independent scaling.
- Clear service ownership.
- Technology flexibility.

Disadvantages:

- Distributed data consistency.
- Network failure handling.
- Service discovery and communication complexity.
- More complicated observability.
- Increased infrastructure and operational cost.
- Slower initial development.

Assessment: Not selected for the MVP because the current operational requirements do not yet justify distributed deployment.

Option C: Modular Monolith + Clean Architecture

One primary application deployment with independently structured business modules and enforced dependency boundaries.

Advantages:

- Simpler deployment than microservices.
- Strong internal separation.
- Clear domain ownership.
- Easier integration testing.
- Lower operational overhead.
- Future extraction path for selected modules.

Disadvantages:

- Requires architectural discipline.
- Module boundaries must be actively enforced.
- Shared deployment can couple release schedules.
- Scaling individual modules independently is limited.

Assessment: Selected as the best balance between initial delivery and long-term maintainability.

6. Logical Architecture

The system is organized into the following logical layers.

6.1 Presentation Layer

Responsibilities:

- Web application.
- HTTP API endpoints.
- Request validation.
- Authentication entry points.
- Response serialization.
- User interaction.

Presentation components must not contain core business rules.

6.2 Application Layer

Responsibilities:

- Use cases.
- Workflow orchestration.
- Transaction boundaries.
- Application-level validation.
- Authorization coordination.
- Command and query handling.
- Domain service coordination.

The application layer coordinates domain behavior but does not own infrastructure implementation details.

6.3 Domain Layer

Responsibilities:

- Business entities.
- Value objects.
- Domain services.
- Business rules.
- Domain events.
- Invariants.
- Domain-level contracts.

This layer is the core of the application and must remain independent of technical frameworks.

6.4 Infrastructure Layer

Responsibilities:

- Database implementations.
- Repository implementations.
- External AI providers.
- File and object storage.
- Queue and background processing.
- External service clients.
- Logging and monitoring integrations.

Infrastructure implements contracts defined by the inner layers.

7. Domain Module Boundaries

The initial logical domain boundaries are:

Module| Primary responsibility
Creative Brief| Project objectives and creative requirements
Story| Narrative architecture and screenplay
Character| Character identity, behavior, and states
Production Design| Environment, props, wardrobe, and visual assets
Previsualization| Storyboard, animatic, and scene planning
Direction| Scene intent, acting, and directorial instructions
Cinematography| Camera, lens, framing, and movement
Lighting| Lighting design and atmosphere
Audio| Dialogue, voice, music, and sound design
Master Production Bible| Canonical production specifications
Continuity| Cross-scene consistency and state tracking
AI Orchestration| Provider routing and generation coordination
Production Workflow| Production stages, tasks, and execution states
Quality Control| Validation, scoring, and approval
Asset Management| Generated files and production references
Identity & Access| Users, authentication, and permissions

These are logical boundaries, not a requirement to create one deployment or database per module.

The exact implementation boundaries must be validated against the actual repository before development.

8. Module Communication Rules

Modules may communicate through:

1. Public application interfaces.
2. Explicit domain contracts.
3. Domain events.
4. Approved query interfaces.

Rules:

- No uncontrolled circular dependencies.
- No direct access to another module's private implementation.
- No importing internal infrastructure classes across module boundaries.
- No hidden cross-module database writes.
- Cross-module operations must have explicit ownership.
- Domain events must be versioned when their contracts evolve.
- Event consumers must handle duplicate delivery safely when asynchronous messaging is used.

Synchronous calls are preferred for operations requiring immediate results and transactional coordination.

Asynchronous events and jobs are preferred for long-running generation, notifications, and background processing.

9. Data Ownership and Consistency

Each domain module owns its business data and rules.

For the MVP, modules may share one relational database, provided that:

- Data ownership remains explicit.
- Repository access is controlled.
- Database changes are managed through migrations.
- Cross-module writes are coordinated through application services.
- Referential integrity is enforced where appropriate.
- Critical operations use transactions.
- Long-running workflows do not hold database transactions open.

The Master Production Bible acts as the canonical source of truth for approved creative and production specifications.

Generated assets, execution history, and provider responses must not silently overwrite approved production specifications.

See:

- ADR-0004: Master Production Bible.
- ADR-0006: Data Storage Strategy.
- ADR-0012: Asset Storage.

10. Scalability Strategy

Scalability will be introduced progressively.

Phase 1: Modular Application

- One primary application deployment.
- Domain-oriented modules.
- Relational database.
- Basic background job processing.
- Centralized logging.
- Provider adapters.

Phase 2: Workload Separation

When required:

- Separate background workers from web processes.
- Introduce dedicated queues.
- Isolate high-volume asset processing.
- Add caching where measurements justify it.
- Optimize database access and indexing.

Phase 3: Selective Service Extraction

A module may become an independent service when it has measurable operational or organizational reasons.

Potential candidates include:

- AI generation orchestration.
- Video processing and rendering.
- Asset processing.
- High-volume asynchronous workers.
- Continuity and QC processing.

Extraction must preserve domain contracts and data ownership.

Microservices Migration Criteria

Service extraction requires at least one demonstrated need:

1. Independent scaling is materially necessary.
2. A module requires a different deployment or availability profile.
3. Resource-intensive processing affects unrelated application workloads.
4. Independent release cycles provide measurable value.
5. A clear service boundary and ownership model already exist.
6. Operational capability exists to manage distributed services.

Microservices must not be introduced merely to make the architecture appear more advanced.

11. Security and Reliability Requirements

The architecture must support:

- Authentication and authorization at application boundaries.
- Role- and permission-based access control.
- Secure provider credential storage.
- Input validation.
- Audit logging for sensitive operations.
- Explicit ownership checks for production assets.
- Idempotency for critical asynchronous operations.
- Transactional consistency for critical business changes.
- Controlled retry policies.
- Timeouts and failure isolation for external providers.

Security and reliability controls must be implemented at the appropriate boundaries, not assumed to exist because the architecture is modular.

See:

- SECURITY.md
- ERROR_HANDLING.md
- ADR-0011: Authentication & Authorization.

12. Consequences

Positive Consequences

- Clear business domain separation.
- Better maintainability.
- Reduced coupling.
- Easier automated testing.
- Simpler initial deployment.
- Lower initial infrastructure complexity.
- More controlled provider integration.
- Defined path for future service extraction.

Negative Consequences

- More initial architectural design work.
- Requires consistent module boundary enforcement.
- Shared deployment can create release coupling.
- Shared database requires strict ownership discipline.
- Individual module scaling is limited until workloads are separated.

Accepted Trade-offs

The project prioritizes internal modularity and operational simplicity over independent service deployment during the MVP.

This trade-off will be reviewed using real production metrics.

13. Risks and Mitigations

Risk| Mitigation
Modules become tightly coupled| Enforce dependency rules and architecture tests
Shared database creates hidden dependencies| Explicit data ownership and repository boundaries
Business logic leaks into API handlers| Keep use cases and domain rules in inner layers
Provider SDK lock-in| Use provider-independent contracts and adapters
Long-running jobs block requests| Move generation into asynchronous workers
Monolith becomes difficult to scale| Measure workloads and separate bottlenecks
Overengineering slows MVP| Implement only required abstractions
Future service extraction becomes expensive| Maintain stable module contracts and ownership

14. Implementation Requirements

Before implementation:

1. Inspect the existing repository and identify its actual technology stack.
2. Map existing code to the proposed domain boundaries.
3. Identify duplicated business logic and dependency violations.
4. Establish module ownership.
5. Define dependency rules.
6. Create architecture tests.
7. Implement one vertical production workflow as a reference.
8. Validate the approach before expanding to all domains.

Do not generate the entire proposed folder structure blindly.

Do not migrate technologies or rewrite existing modules without a repository audit and an explicit migration plan.

The implementation must follow the approved TASKS.md and ROADMAP.md.

15. Validation Criteria

ADR-0001 can be considered implemented when the following criteria are demonstrated:

- [ ] Domain, Application, Infrastructure, and Presentation responsibilities are separated.
- [ ] Core domain logic does not depend on external frameworks.
- [ ] Module boundaries and ownership are documented.
- [ ] Circular dependencies are prevented or detected.
- [ ] Cross-module access uses approved contracts.
- [ ] Database access is controlled through approved persistence interfaces.
- [ ] Provider SDKs are isolated from business logic.
- [ ] Domain and application tests run without live external services.
- [ ] Architecture rules are enforced through automated checks where practical.
- [ ] At least one complete vertical production workflow passes integration tests.
- [ ] Deployment and background execution responsibilities are documented.
- [ ] Repository implementation matches the approved architecture or has documented exceptions.

A proposed architecture is not considered implemented merely because its documentation exists.

16. Review Conditions

This ADR must be reviewed when:

- The MVP architecture is implemented.
- The system reaches production workloads that expose scaling constraints.
- A major domain requires independent deployment.
- Database ownership boundaries change.
- The team adopts a distributed service architecture.
- New technical constraints invalidate the original assumptions.

Any change to this decision must be documented in a superseding ADR.

17. Related Documents

- BRD.md
- PRD.md
- ARCHITECTURE.md
- TASKS.md
- AI_PIPELINE.md
- DATA_MODEL.md
- API_SPEC.md
- PROVIDER_MATRIX.md
- SECURITY.md
- ERROR_HANDLING.md
- TEST_STRATEGY.md
- DEPLOYMENT.md
- ADR-0002: Application Structure
- ADR-0003: Provider Adapter System
- ADR-0004: Master Production Bible
- ADR-0006: Data Storage Strategy
- ADR-0007: Async Job Processing

18. Final Decision Summary

MovieAIProducer adopts Modular Monolith + Clean Architecture as its initial architecture strategy.

The platform will maintain strict domain boundaries, explicit contracts, provider independence, and testable business logic while retaining a simple deployment model for the MVP.

Future distributed architecture decisions must be justified by measurable product, workload, reliability, or organizational requirements.

Decision status: Proposed.
