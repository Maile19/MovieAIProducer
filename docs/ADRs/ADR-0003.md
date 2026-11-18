# ADR-0003: Provider Adapter System

- Project: MovieAIProducer
- ADR ID: ADR-0003
- Title: Provider Adapter System
- Status: Proposed
- Date: 2026-11-19
- Decision Owners: Project Architecture
- Decision Scope: External AI and media generation integrations
- Version: 1.0

---

1. Context

MovieAIProducer is designed to coordinate professional film production using multiple AI providers and media generation technologies.

The platform may integrate with providers for:

- Large Language Models (LLM).
- Image generation.
- Video generation.
- Voice synthesis.
- Speech recognition.
- Music and sound generation.
- Video editing and rendering.
- Media analysis.
- Asset storage and delivery.

Different providers expose different APIs, request formats, response structures, authentication mechanisms, generation limits, pricing models, and asynchronous execution patterns.

Some products provide public APIs, while others operate primarily through user-facing interfaces or assisted workflows.

The system must distinguish between actual API integrations and workflows that require external user interaction.

A direct integration with one provider must not become a dependency of the entire MovieAIProducer application.

2. Problem Statement

How should MovieAIProducer integrate multiple AI and media providers while maintaining:

1. Provider independence.
2. Consistent application contracts.
3. Capability-aware model selection.
4. Reliable asynchronous execution.
5. Normalized errors and status reporting.
6. Cost and usage tracking.
7. Secure credential management.
8. Provider-specific prompt optimization.
9. Controlled fallback behavior.
10. Long-term extensibility.

The platform must also prevent unsupported claims about provider capabilities or automatic integration.

3. Decision

Adopt a Provider Adapter Architecture using provider-independent ports, normalized contracts, and capability-based routing.

The application layer communicates with provider interfaces rather than calling vendor SDKs directly.

Each provider adapter translates the normalized application contract into the provider-specific request and translates the response into the platform's normalized result.

The architecture separates:

- Provider identity.
- Model identity.
- Provider capabilities.
- Integration method.
- Prompt compilation.
- Generation execution.
- Job lifecycle.
- Usage and cost tracking.
- Output validation.

The system must preserve the original canonical prompt and production specifications while allowing provider-specific prompt adaptation.

4. Architecture Options Considered

Option A: Direct SDK Calls Throughout the Application

Each business module calls provider SDKs directly.

Advantages:

- Fast initial implementation.
- Direct access to vendor features.

Disadvantages:

- Strong vendor coupling.
- Duplicate integration logic.
- Difficult provider replacement.
- Inconsistent error handling.
- Difficult testing and maintenance.

Assessment: Rejected.

Option B: Single Primary Provider Integration

The platform uses one provider for each generation category.

Advantages:

- Simple integration.
- Lower initial development effort.
- Fewer compatibility concerns.

Disadvantages:

- Vendor dependency.
- Limited model choice.
- Reduced resilience.
- Pricing and availability risks.
- Difficult expansion into specialized workflows.

Assessment: Rejected as the long-term architecture.

A single provider may still be selected for an individual MVP capability.

Option C: Provider Adapter Architecture

Each provider is integrated through a dedicated adapter implementing standardized application contracts.

Advantages:

- Provider independence.
- Consistent execution lifecycle.
- Easier testing.
- Capability-based routing.
- Controlled provider replacement.
- Better observability.
- Extensible integration ecosystem.

Disadvantages:

- Additional abstraction.
- Contract maintenance.
- Provider-specific features require explicit extension mechanisms.
- Capability information must be maintained.

Assessment: Selected.

5. Architectural Components

5.1 Provider Registry

The Provider Registry maintains provider and model metadata.

Responsibilities:

- Provider identification.
- Model identification.
- Supported generation categories.
- Supported capabilities.
- API availability.
- Integration status.
- Operational status.
- Known limitations.
- Pricing metadata.
- Version information.

The registry must distinguish between verified capabilities and unverified assumptions.

5.2 Capability Registry

The Capability Registry describes what a provider and model can actually do.

Examples:

Video generation

- Text-to-video.
- Image-to-video.
- Video extension.
- First-frame conditioning.
- Last-frame conditioning.
- Reference image support.
- Character reference support.
- Native audio generation.
- Aspect ratio options.
- Resolution options.
- Duration constraints.
- Frame-rate constraints.

Image generation

- Text-to-image.
- Image-to-image.
- Inpainting.
- Outpainting.
- Reference image support.
- Resolution and aspect ratio.
- Batch generation.

Voice and audio

- Text-to-speech.
- Speech-to-text.
- Voice cloning, when legally and technically supported.
- Language support.
- Speaker control.
- Emotion or delivery control.
- Audio format.

Capabilities must be associated with the exact provider and model version where possible.

A capability must not be assumed to exist merely because another model from the same provider supports it.

5.3 Provider Adapter

Each adapter implements the provider-independent interface.

Responsibilities:

- Authentication.
- Request translation.
- Provider API communication.
- Response translation.
- Provider error normalization.
- Job submission.
- Job status retrieval.
- Result retrieval.
- Usage metadata extraction.

Provider-specific SDKs must remain inside adapter implementations.

5.4 Model Router

The Model Router selects an eligible model based on:

- Requested capability.
- Provider integration status.
- Model availability.
- Output requirements.
- Quality requirements.
- Cost constraints.
- Latency constraints.
- Region restrictions.
- User configuration.
- Project configuration.
- Reliability history.

Routing must never select a model solely because it is inexpensive.

If no compatible model exists, the system must return an explicit capability or availability error.

5.5 Prompt Compiler

The Prompt Compiler transforms canonical production instructions into provider-compatible prompts.

It must preserve:

- Narrative intent.
- Character identity.
- Character state.
- Environment specifications.
- Camera direction.
- Lighting intent.
- Motion direction.
- Audio requirements.
- Continuity constraints.
- Negative constraints.
- Scene-specific requirements.

Provider-specific prompt transformations must not silently change the approved creative intent.

The original canonical prompt must remain recoverable.

See ADR-0008: Prompt Compilation Engine.

5.6 Generation Orchestrator

The Generation Orchestrator manages generation execution.

Responsibilities:

- Request validation.
- Model routing.
- Adapter invocation.
- Asynchronous job creation.
- Job tracking.
- Retry coordination.
- Result validation.
- Usage recording.
- Workflow event publication.

The orchestrator must not contain vendor-specific request formatting.

6. Integration Classification

Every provider integration must have an explicit integration level.

Level 1: Native API Integration

The platform communicates with an officially supported provider API.

Requirements:

- Documented API endpoint.
- Supported authentication.
- Request and response contracts.
- Job status handling where applicable.
- Error handling.
- Integration tests.

Only verified API capabilities may be marked as available.

Level 2: Assisted / Exportable Workflow

The platform generates provider-compatible prompts, reference packages, and production instructions.

The user performs the generation through the provider's external interface.

Requirements:

- Prompt export.
- Reference asset export.
- Configuration instructions.
- Manual result import or attachment.
- Clear indication that execution occurs externally.

This level must not be presented as automatic generation.

Level 3: Manual External Workflow

The platform provides production specifications and instructions for a user-operated external process.

The user manually performs the operation and records the result.

This level is useful for providers without a suitable public API.

Integration Status

Each provider integration must also have an operational status:

- Planned.
- Under Evaluation.
- Verified.
- Active.
- Degraded.
- Deprecated.
- Disabled.

Integration level and operational status are separate fields.

For example, a Native API integration may be verified but temporarily degraded.

7. Provider Categories

The architecture must support the following integration categories.

Category| Responsibility
LLM| Story development, analysis, planning, reasoning
Image| Concept art, character and environment references
Video| Scene and shot generation
Voice| Character voice and dialogue synthesis
Speech| Transcription and audio analysis
Music| Music and soundtrack generation
Sound Effects| Environmental and cinematic sound
Media Analysis| Image, video, and audio understanding
Rendering| Compositing, encoding, editing, and output
Storage| Asset persistence and delivery

Storage is a separate infrastructure capability and must not be treated as an AI generation provider.

Local rendering tools such as FFmpeg may implement rendering interfaces without being classified as external AI providers.

8. Normalized Contracts

The application layer must use normalized contracts.

8.1 Generation Request

A normalized generation request should contain:

- Request ID.
- Project ID.
- Production stage.
- Scene ID, when applicable.
- Shot ID, when applicable.
- Requested capability.
- Provider preference, if configured.
- Model preference, if configured.
- Canonical prompt reference.
- Compiled prompt reference.
- Input asset references.
- Output constraints.
- Generation parameters.
- Quality requirements.
- Cost constraints.
- Idempotency key.
- Trace and correlation identifiers.

The request must preserve provenance linking the generated output to the production specification.

8.2 Generation Response

A normalized response should contain:

- Request ID.
- Job ID.
- Provider ID.
- Model ID.
- Integration version.
- Execution status.
- Output asset references.
- Usage metadata.
- Estimated or actual cost, when available.
- Provider timestamps.
- Error details, when applicable.
- Trace identifiers.

Provider-specific metadata may be retained in a structured extension field.

It must not replace normalized fields.

8.3 Contract Versioning

All shared provider contracts must be versioned.

Breaking changes require explicit migration.

Adapters must declare the contract version they implement.

Old jobs must remain interpretable after provider adapter upgrades.

9. Asynchronous Job Lifecycle

Video, image, voice, and other generation operations may take longer than a normal HTTP request.

The architecture must support asynchronous jobs.

Canonical job states:

1. CREATED
2. VALIDATING
3. QUEUED
4. SUBMITTED
5. PROCESSING
6. SUCCEEDED
7. FAILED
8. CANCEL_REQUESTED
9. CANCELLED
10. EXPIRED

Additional internal states may be introduced when justified.

Rules:

- Job transitions must be validated.
- Duplicate submissions must be controlled through idempotency.
- Provider polling must respect rate limits.
- Webhooks must be authenticated and validated.
- Duplicate webhook delivery must be handled safely.
- Terminal job states must not be silently reopened.
- Job state changes must be recorded.
- Results must be validated before entering approved production workflows.

A provider that does not support asynchronous execution may be handled through an adapter-specific execution strategy.

See ADR-0007: Async Job Processing.

10. Prompt Translation Strategy

The system maintains three distinct representations:

A. Canonical Production Prompt

The authoritative creative instruction derived from the Master Production Bible and approved production requirements.

It must remain provider-independent.

B. Compiled Provider Prompt

The translated prompt optimized for a specific provider and model.

It may include:

- Provider-specific syntax.
- Supported parameter mappings.
- Model-specific constraints.
- Prompt compression.
- Structured input formatting.

C. Execution Metadata

Records:

- Compiler version.
- Provider adapter version.
- Model identifier.
- Compilation timestamp.
- Transformation warnings.
- Unsupported requirement warnings.
- Original prompt reference.

The compiler must not silently remove important production constraints.

If a provider cannot satisfy a critical requirement, the system must flag the limitation before execution.

11. Error Normalization

Provider errors must be translated into normalized application error categories.

Examples:

Error category| Meaning
AUTHENTICATION_FAILED| Invalid or expired credentials
PERMISSION_DENIED| Account lacks required access
RATE_LIMITED| Provider rate limit reached
QUOTA_EXCEEDED| Provider quota exhausted
INSUFFICIENT_CREDITS| Provider account lacks credits
INVALID_REQUEST| Provider rejected request parameters
UNSUPPORTED_CAPABILITY| Requested feature is unsupported
MODEL_UNAVAILABLE| Model unavailable
PROVIDER_UNAVAILABLE| Provider service unavailable
TIMEOUT| Operation exceeded allowed duration
CONTENT_REJECTED| Provider safety system rejected input
OUTPUT_INVALID| Generated result failed validation
UNKNOWN_PROVIDER_ERROR| Unclassified provider failure

The normalized error must retain:

- Internal error code.
- Provider error code.
- Safe diagnostic message.
- Retryability.
- Relevant request and job identifiers.
- Timestamp.
- Correlation ID.

Sensitive credentials and private request data must never appear in logs.

See ERROR_HANDLING.md.

12. Retry, Timeout, and Resilience

The architecture must provide controlled resilience mechanisms.

Retry Policy

Retries are allowed only when the operation is considered retryable.

Rules:

- Exponential backoff.
- Randomized jitter.
- Maximum retry attempts.
- Maximum total execution duration.
- Respect provider retry instructions.
- No automatic retry for invalid requests or permanent permission failures.
- No duplicate billing-producing submissions without idempotency safeguards.

Timeout Policy

Timeouts must be configurable by operation category.

Different limits may apply to:

- Text generation.
- Image generation.
- Video generation.
- Voice generation.
- Rendering.
- Result downloads.

Circuit Breaker

A circuit breaker may temporarily stop requests to a failing provider.

It must support:

- Failure thresholds.
- Open state.
- Half-open recovery checks.
- Closed state.
- Monitoring and audit records.

Fallback Policy

Fallback is permitted only when the alternative provider satisfies the required capabilities and production constraints.

Fallback must not silently change:

- Character identity.
- Aspect ratio.
- Scene duration.
- Required reference inputs.
- Critical visual constraints.
- Audio requirements.
- Continuity requirements.

If no acceptable fallback exists, the system must stop and request an explicit decision.

13. Cost and Usage Management

Each generation operation should record available usage information.

Tracked information:

- Provider.
- Model.
- Project.
- Scene and shot references.
- Request and job IDs.
- Input and output usage.
- Duration or generation units.
- Estimated cost.
- Actual cost, when provided.
- Currency.
- Billing metadata.
- Execution timestamp.

Rules:

- Estimated cost must be distinguished from actual cost.
- Missing provider cost data must not be fabricated.
- Usage records must be traceable to their generation jobs.
- Provider price changes must be versioned.
- Budget limits must be enforced before expensive operations where possible.

14. Security Requirements

Provider integration must support:

- Secure credential storage.
- Environment-based secret configuration.
- Credential encryption where applicable.
- Least-privilege access.
- Credential rotation.
- Provider-specific access controls.
- Redaction of secrets in logs.
- Request and webhook signature verification.
- Controlled outbound network access.
- Download URL validation.
- Protection against SSRF.
- File type and file size validation.

Credentials must never be committed to Git or embedded in frontend code.

Users must not be able to access credentials belonging to other users or projects.

15. Capability Verification and Provider Governance

The system must not assume that provider capabilities remain unchanged.

Each capability record should include:

- Provider.
- Model.
- Capability.
- Verification status.
- Verification source.
- Verification date.
- Last tested date.
- Known limitations.
- Applicable API version.
- Evidence or documentation reference.

Verification levels:

- UNVERIFIED.
- DOCUMENTED.
- TESTED.
- VERIFIED_IN_PRODUCTION.
- DEPRECATED.

A provider feature must not be advertised as production-ready when it is only documented but not tested.

Provider and model changes must be reviewed for:

- API compatibility.
- Output differences.
- Parameter changes.
- Cost changes.
- Performance changes.
- Safety behavior.
- Contract compatibility.

16. Testing Strategy

Unit Tests

Test:

- Request normalization.
- Response normalization.
- Capability matching.
- Model routing.
- Error mapping.
- Prompt translation.
- Retry decisions.
- Idempotency behavior.

Adapter Contract Tests

Every adapter must pass the common adapter contract test suite.

Tests must verify:

- Required interface implementation.
- Authentication behavior.
- Request translation.
- Response mapping.
- Error mapping.
- Job lifecycle handling.
- Timeout behavior.
- Usage extraction.

Integration Tests

Test against provider sandbox environments or controlled test accounts where available.

Tests must not require live production generation for every automated test run.

Failure Tests

Test:

- Provider timeout.
- Rate limiting.
- Invalid credentials.
- Malformed responses.
- Duplicate webhooks.
- Missing output files.
- Partial generation failure.
- Provider outage.
- Unsupported model capability.

Regression Tests

Existing provider adapters must be tested whenever shared contracts or routing logic change.

17. Data and Audit Requirements

The system must preserve generation provenance.

Every generated output should be traceable to:

- Project.
- Scene.
- Shot.
- Canonical production prompt.
- Compiled provider prompt.
- Provider.
- Model.
- Adapter version.
- Contract version.
- Generation parameters.
- Job history.
- Output validation.
- Usage record.

Generation history must be retained according to project retention and data governance policies.

The platform must distinguish:

- Generated output.
- Imported external output.
- User-edited output.
- Approved production asset.
- Rejected output.

18. Consequences

Positive Consequences

- Reduced vendor lock-in.
- Consistent application interfaces.
- Easier provider expansion.
- More reliable routing.
- Centralized usage tracking.
- Better failure handling.
- Provider-specific optimization without changing core business logic.
- Improved testability and auditability.

Negative Consequences

- More abstraction and implementation work.
- Provider contract maintenance.
- Capability registry maintenance.
- Additional compatibility testing.
- Some vendor-specific features may require explicit extension contracts.
- Normalization can hide provider-specific functionality if designed too narrowly.

Accepted Trade-offs

The platform prioritizes stable common contracts while preserving controlled access to provider-specific features.

The adapter architecture must not reduce every provider to the lowest common denominator.

19. Implementation Requirements

Implementation must follow this sequence:

1. Inspect existing repository and technology stack.
2. Identify current provider integrations.
3. Define provider-independent contracts.
4. Define provider and model registry.
5. Define capability metadata.
6. Implement adapter interface.
7. Implement one reference adapter.
8. Create adapter contract tests.
9. Implement capability-aware routing.
10. Implement normalized job lifecycle.
11. Implement prompt compilation integration.
12. Add usage and cost recording.
13. Add retry, timeout, and resilience controls.
14. Add provider integration health monitoring.
15. Validate with an end-to-end production workflow.

The first adapter must be selected based on verified API availability, actual project requirements, and implementation feasibility.

Do not implement every provider simultaneously.

Do not use browser automation or unofficial endpoints as if they were supported public APIs.

Do not claim that Google Flow, Veo, Kling, Runway, or another product is natively integrated until its actual supported API and integration have been verified.

20. Validation Criteria

- [ ] Provider integrations are isolated behind adapters.
- [ ] Application business logic does not directly call vendor SDKs.
- [ ] Provider and model identities are independently represented.
- [ ] Capability metadata is model-specific.
- [ ] Integration levels are explicitly recorded.
- [ ] Unverified capabilities cannot be advertised as verified.
- [ ] Normalized generation request and response contracts exist.
- [ ] Contract versioning is implemented.
- [ ] Job lifecycle transitions are validated.
- [ ] Idempotency protects critical generation submissions.
- [ ] Provider errors are normalized.
- [ ] Retry and timeout policies are configurable.
- [ ] Fallback selection respects required capabilities.
- [ ] Canonical prompts remain recoverable.
- [ ] Provider-specific prompt compilation is traceable.
- [ ] Usage and cost records are linked to generation jobs.
- [ ] Credentials are securely stored.
- [ ] Adapter contract tests pass.
- [ ] At least one real or sandbox provider integration passes end-to-end testing.
- [ ] Generated outputs preserve production provenance.

Documentation alone does not satisfy implementation validation.

21. Review Conditions

Review this ADR when:

- A new provider category is introduced.
- Provider API contracts change materially.
- Model routing requirements change.
- The system requires multi-region provider routing.
- Provider-specific capabilities cannot be represented safely.
- A provider must be isolated into an independent service.
- Cost or reliability metrics justify a different strategy.

A change that materially alters the decision requires a superseding ADR.

22. Related Documents

- BRD.md
- PRD.md
- ARCHITECTURE.md
- AI_PIPELINE.md
- DATA_MODEL.md
- API_SPEC.md
- PROVIDER_MATRIX.md
- SECURITY.md
- ERROR_HANDLING.md
- TEST_STRATEGY.md
- OBSERVABILITY.md
- ADR-0001: Architecture Style
- ADR-0004: Master Production Bible
- ADR-0007: Async Job Processing
- ADR-0008: Prompt Compilation Engine
- ADR-0012: Asset Storage
- ADR-0013: Observability Stack

23. Final Decision Summary

MovieAIProducer adopts a Provider Adapter Architecture with capability-based routing and normalized execution contracts.

The platform will maintain a provider-independent core while allowing specialized provider integrations through isolated adapters.

Native API, Assisted / Exportable, and Manual External workflows must remain explicitly distinguishable.

Canonical production intent and Master Production Bible specifications must remain authoritative throughout prompt compilation, generation, and output validation.

Decision status: Proposed.
