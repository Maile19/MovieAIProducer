# Data Model & Database Specification - MovieAIProducer

## 1. Purpose
This document defines the data structures for MovieAIProducer, ensuring the Master Production Bible (MPB) acts as the Single Source of Truth while maintaining traceability, versioning, and provider-independence.

## 2. Key Data Design Principles
- **Stable Identity:** All primary entities use UUIDs.
- **Relational Integrity:** Strict relational tables; JSON reserved for flexible configs.
- **Traceability:** Every asset and job is traceable to its MPB version, Prompt version, and Approval state.
- **Provider-Independence:** The production engine consumes structured data; platform-specific prompt syntax is compiled at the Infrastructure Layer.

## 3. Core Entity Domains
1. **Project:** Meta-info, settings, and versions.
2. **Story:** Screenplay, scenes, sequences, and dialogue.
3. **Character:** Identity, DNA, and Scene-specific states.
4. **World:** Environments, Props, Wardrobe, and Makeup.
5. **Direction:** Visual styles, Cameras, Lighting, and Motion matrices.
6. **Previsualization:** Storyboards, shots, and animatics.
7. **AI Orchestration:** Prompt templates, providers, models, and jobs.
8. **Asset Management:** Metadata for binary files (Image/Video/Audio).
9. **Continuity & QC:** Validation rules, findings, and scoring.
10. **Governance:** Approvals, Audit logs, and Exports.

## 4. Key Data Models (Schema Contracts)
- **Project:** {id, name, slug, status, aspect_ratio, settings}
- **Scene:** {id, sequence_id, scene_number, slugline, status, duration}
- **CharacterState:** {id, character_id, scene_id, costume_state, physical_condition}
- **Shot:** {id, scene_id, camera_setup_id, lighting_setup_id, motion_profile_id, duration}
- **ProductionJob:** {id, scene_id, shot_id, prompt_specification_id, status, attempt_count}
- **Asset:** {id, project_id, asset_type, storage_key, checksum, status}
- **QCReport:** {id, scene_id, production_job_id, overall_score, critical_failure}

## 5. Persistence & Storage Strategy
- **SQLite (MVP):** Standard persistent store for structured data.
- **FileSystem:** Holds binary assets (video/images). Database entries store metadata and stable storage keys.
- **Migrations:** All changes enforced via `Alembic` (or equivalent schema versioning).
- **Security:** Secrets/API Keys strictly managed via environment variables.

## 6. Implementation Protocols
- **Stability:** UUIDs must not change.
- **Versioning:** Approved versions are immutable; revisions branch from the last approved state.
- **Integrity:** Strict Foreign Key constraints; transactions for multi-entity updates.
- **Verification:** Implementers must audit existing schemas and run migration tests before deploying any new data model changes.
