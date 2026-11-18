# API Specification - MovieAIProducer

## 1. Vision
The MovieAIProducer API provides a secure, versioned, and modular RESTful contract bridging the Frontend, Domain Services, and Infrastructure (AI Providers). It enforces strict resource ownership and validation to ensure production-grade reliability.

## 2. API Standards
- **Version:** `/api/v1`
- **Format:** JSON-only (snake_case).
- **Standards:** RESTful design, standard HTTP status codes (2xx, 4xx, 5xx), and standard Response Envelopes for success/error states.
- **Security:** Token-based auth, RBAC (Role-Based Access Control) for all endpoints.

## 3. Core Modules
- **Auth:** Login/Logout/Refresh.
- **Projects:** Management, Creative Brief, Overview.
- **Story/Screenplay:** Acts, Sequences, Scenes, Dialogue.
- **Master Production Bible (MPB):** Character/World/Direction/Style libraries.
- **Storyboard/Shot:** Visual sequencing and cinematography planning.
- **Prompt/Production:** Compilation, Provider Orchestration, Job Tracking.
- **QC/Continuity:** Validation rules, scoring, and findings.
- **Assets:** Metadata for images/videos/audio.

## 4. Key Request Contracts (Examples)
- **POST /api/v1/projects:** Initializes a new production project.
- **POST /api/v1/shots/{id}/generate:** Submits an AI generation job (asynchronous).
- **POST /api/v1/shots/{id}/qc/run:** Initiates quality assessment for a generated asset.

## 5. Security Protocols
- **Credential Protection:** API Keys/Secrets are NEVER returned in API responses.
- **Idempotency:** Critical operations (Production Jobs) require `Idempotency-Key` headers to prevent duplicate executions.
- **Validation:** Pydantic-based schema validation for all incoming requests.

## 6. Implementation Guidelines
- **Modularity:** API routes must map to domain modules defined in `ARCHITECTURE.md`.
- **Traceability:** Every operation must be correlated with a `request_id`.
- **Async Handling:** Long-running tasks must return `202 Accepted` and provide a Job ID for status polling.
- **Documentation:** All endpoints must be documented via OpenAPI (Swagger).
