# System Architecture & Technical Design - MovieAIProducer

## 1. Architecture Vision
MovieAIProducer uses a modular monolith architecture (for MVP) to coordinate the 12-step cinematic workflow. The system enforces a strict separation between domain logic (the "Master Production Bible"), workflow orchestration, and external AI provider integration.

## 2. High-Level System Architecture
- **Application Layer:** Orchestrates the 12-Step pipeline and background generation jobs.
- **Domain Layer:** Owns the "Source of Truth" (Bible) and business invariants (Continuity, Quality rules).
- **Infrastructure Layer:** Handles database persistence (SQLite), filesystem asset storage, and Provider Adapters (Google Flow, Kling, Runway).

## 3. Technology Stack
- **Backend:** FastAPI (Python 3.11+)
- **Database:** SQLite (with SQLAlchemy)
- **Frontend:** Next.js (Tailwind CSS, Mobile-first)
- **Validation:** Pydantic
- **Workflow:** Explicit State Machine for Scene/Job tracking.

## 4. Repository Structure
- `backend/app/domain/`: Core entities (Character, Scene, DNA, Assets).
- `backend/app/application/`: Production logic & orchestrators.
- `backend/app/infrastructure/`: SQLite repositories and AI Provider Adapters.
- `frontend/`: Cinematic dashboard and production studio.

## 5. Provider Adapter Architecture
The Domain Layer is strictly isolated from external AI provider SDKs. All generation is routed through a standard `VideoProvider` interface, allowing hot-swapping or adding new AI models without modifying core cinematic logic.

## 6. Key Data Architecture
- **Stable Identifiers:** UUID-based for all entities (Scene, Asset, Job).
- **DNA Locking:** Immutable identifiers for character/environment DNA ensure consistency across all 50 scenes.
- **State Machine:** Enforces strict pipeline transitions: `Planned` -> `Ready` -> `Generating` -> `Approved` -> `Locked`.

## 7. Security & Privacy
- Credentials are managed via environment variables (never in code).
- DNA and asset metadata are stored locally to maintain user privacy and ownership.
