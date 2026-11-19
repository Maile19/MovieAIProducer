# REST API Specification - MovieAIProducer

- **Project:** MovieAIProducer
- **Document ID:** SPEC-0001
- **Domain:** HTTP Presentation Layer & Service Contracts
- **Version:** 2.0.0
- **Status:** Approved Specification
- **Canonical References:** ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0011, CDA-0004, CDA-0005
- **Base URL (Local):** `http://127.0.0.1:8000`
- **Base URL (Production):** `https://producer.apologets.com`

---

## 1. API Architecture & Standards

The MovieAIProducer API provides a deterministic, versioned RESTful interface for the Hollywood 12-Step Cinematic Pipeline. It is engineered with FastAPI and enforces strict validation via Pydantic schemas.

### Core Protocol Standards
1. **Explicit Implementation Transparency:** All endpoints are strictly marked as either **`[IMPLEMENTED]`** (verified against current codebase) or **`[PLANNED]`** (scheduled roadmap item).
2. **Standard Correlation Headers:** Every request and response carries the `X-Request-ID` header (UUIDv4) for distributed tracing across logs, database transactions, and background workers.
3. **Idempotency Keys:** Mutating production jobs accept an `Idempotency-Key` header to prevent duplicate GPU invocations and billing redundancy.
4. **Standard Error Envelope (RFC 7807 Aligned):** All 4xx and 5xx responses return a uniform JSON error payload.

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "The requested scene does not exist.",
    "request_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "details": [
      {
        "field": "scene_id",
        "issue": "UUID 3fa85f64-5717-4562-b3fc-2c963f66afa6 not found in project"
      }
    ]
  }
}
```

---

## 2. API Endpoint Matrix Summary

| Method | Path | Status | Domain Module | Description |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/health` | **`[IMPLEMENTED]`** | Core System | Liveness probe returning service operational status |
| **GET** | `/ready` | **`[IMPLEMENTED]`** | Core System | Readiness probe verifying SQLite connectivity and CAS storage |
| **POST** | `/api/v1/auth/login` | **`[PLANNED]`** | Auth & Identity | Authenticate with credentials and receive JWT bearer tokens |
| **POST** | `/api/v1/auth/refresh` | **`[PLANNED]`** | Auth & Identity | Rotate expired access token using valid refresh token |
| **GET** | `/api/v1/auth/me` | **`[PLANNED]`** | Auth & Identity | Get authenticated user profile and RBAC permissions |
| **GET** | `/api/v1/projects` | **`[PLANNED]`** | Project Management | List all film projects with pagination |
| **POST** | `/api/v1/projects` | **`[PLANNED]`** | Project Management | Initialize new cinematic film project |
| **GET** | `/api/v1/projects/{id}` | **`[PLANNED]`** | Project Management | Retrieve project summary, aspect ratio, and active stage |
| **GET** | `/api/v1/projects/{id}/bible` | **`[PLANNED]`** | Master Production Bible | Retrieve active MPB and locked DNA variables |
| **PUT** | `/api/v1/projects/{id}/bible` | **`[PLANNED]`** | Master Production Bible | Update MPB creative variables (#Style, #Light, #Env) |
| **POST** | `/api/v1/projects/{id}/bible/lock` | **`[PLANNED]`** | Master Production Bible | Lock MPB version, making DNA immutable for generation |
| **GET** | `/api/v1/projects/{id}/scenes` | **`[PLANNED]`** | Story & Screenplay | Retrieve 50-scene blueprint organized by 4 Acts |
| **POST** | `/api/v1/projects/{id}/scenes` | **`[PLANNED]`** | Story & Screenplay | Batch generate or create 50 scenes |
| **GET** | `/api/v1/scenes/{id}` | **`[PLANNED]`** | Story & Screenplay | Retrieve scene narrative goal, slugline, and dialogue |
| **POST** | `/api/v1/scenes/{id}/calibrate-dialogue`| **`[PLANNED]`** | Story & Screenplay | Calibrate dialogue lines to 5s limit and J/L cuts |
| **GET** | `/api/v1/projects/{id}/characters` | **`[PLANNED]`** | Character & Voice DNA | List registered characters and face embeddings |
| **POST** | `/api/v1/characters/{id}/states` | **`[PLANNED]`** | Character & Voice DNA | Register character evolution state (#State 01-05) |
| **POST** | `/api/v1/characters/{id}/voice-dna` | **`[PLANNED]`** | Character & Voice DNA | Register reference WAV audio for GPT-SoVITS cloning |
| **GET** | `/api/v1/scenes/{id}/shots` | **`[PLANNED]`** | Cinematography Matrix | List shots for a specific scene |
| **POST** | `/api/v1/scenes/{id}/shots` | **`[PLANNED]`** | Cinematography Matrix | Add shot with #Cam, #Lens, #Comp, #Light, #Act codes |
| **POST** | `/api/v1/shots/{id}/compile-prompt` | **`[PLANNED]`** | Prompt Compilation | Transpile DNA & camera matrices into engine prompt |
| **POST** | `/api/v1/shots/{id}/generate` | **`[PLANNED]`** | AI Production Engine | Submit video generation job to ComfyUI/Kling/Veo |
| **POST** | `/api/v1/shots/{id}/generate-voice` | **`[PLANNED]`** | AI Production Engine | Submit dialogue TTS job to GPT-SoVITS/ElevenLabs |
| **GET** | `/api/v1/jobs/{id}` | **`[PLANNED]`** | AI Production Engine | Poll asynchronous job progress and status |
| **POST** | `/api/v1/jobs/{id}/cancel` | **`[PLANNED]`** | AI Production Engine | Abort running generation job |
| **POST** | `/api/v1/shots/{id}/qc/run` | **`[PLANNED]`** | Quality Control Engine | Execute automated CLIP, aesthetic, and SNR checks |
| **GET** | `/api/v1/shots/{id}/qc/report` | **`[PLANNED]`** | Quality Control Engine | Retrieve automated QC scorecard and defect log |
| **POST** | `/api/v1/shots/{id}/approve` | **`[PLANNED]`** | Quality Control Engine | Showrunner sign-off locking shot into master cut |
| **POST** | `/api/v1/assets/upload` | **`[PLANNED]`** | Asset Storage (CAS) | Upload reference image/audio to content-addressed store |
| **GET** | `/api/v1/assets/{id}` | **`[PLANNED]`** | Asset Storage (CAS) | Retrieve asset metadata and SHA-256 checksum |
| **GET** | `/api/v1/assets/{id}/stream` | **`[PLANNED]`** | Asset Storage (CAS) | HTTP range video streaming for dailies player |
| **WS** | `/api/v1/ws/projects/{id}/events` | **`[PLANNED]`** | Real-Time Events | WebSocket feed for job progress and live QC alerts |

---

## 3. Implemented Endpoints Specification `[IMPLEMENTED]`

### 3.1 Liveness Probe
- **Endpoint:** `GET /health`
- **Status:** **`[IMPLEMENTED]`**
- **File Reference:** `backend/app/api/health.py`
- **Authentication:** None (Public)
- **Response Headers:** `X-Request-ID: <uuid4>`

#### Response (200 OK):
```json
{
  "status": "alive"
}
```

---

### 3.2 Readiness Probe
- **Endpoint:** `GET /ready`
- **Status:** **`[IMPLEMENTED]`**
- **File Reference:** `backend/app/api/health.py`
- **Authentication:** None (Public)
- **Logic:** Performs `SELECT 1` on the active SQLAlchemy engine and verifies that `settings.asset_storage_path` exists as a valid directory.

#### Response (200 OK - Healthy):
```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "asset_storage": true
  }
}
```

#### Response (503 Service Unavailable - Degraded):
```json
{
  "status": "not_ready",
  "checks": {
    "database": false,
    "asset_storage": true
  }
}
```

---

## 4. Planned Core Endpoints Specification `[PLANNED]`

### 4.1 Project Creation
- **Endpoint:** `POST /api/v1/projects`
- **Status:** **`[PLANNED]`**
- **Authentication:** Bearer Token (Role: Showrunner)

#### Request Body:
```json
{
  "title": "Chronicles of Nusantara 2099",
  "slug": "chronicles-of-nusantara-2099",
  "genre": "Sci-Fi Cyberpunk",
  "sub_genre": "Neo-Noir Investigation",
  "aspect_ratio": "16:9",
  "target_style_code": "#Style 08",
  "operational_stage": 1
}
```

#### Response (201 Created):
```json
{
  "data": {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "title": "Chronicles of Nusantara 2099",
    "slug": "chronicles-of-nusantara-2099",
    "status": "PLANNING",
    "aspect_ratio": "16:9",
    "operational_stage": 1,
    "created_at": "2026-11-19T09:00:00Z",
    "updated_at": "2026-11-19T09:00:00Z"
  }
}
```

---

### 4.2 Master Production Bible (MPB) Locking
- **Endpoint:** `POST /api/v1/projects/{project_id}/bible/lock`
- **Status:** **`[PLANNED]`**
- **Authentication:** Bearer Token (Role: Showrunner)
- **Purpose:** Freezes all creative parameters from Steps 1–6 into an immutable baseline.

#### Request Body:
```json
{
  "approval_notes": "Character DNA and #Style 08 locked. Approved by Showrunner for 50-scene generation.",
  "confirm_dna_freeze": true
}
```

#### Response (200 OK):
```json
{
  "data": {
    "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "bible_version": 1,
    "is_locked": true,
    "locked_at": "2026-11-19T09:15:00Z",
    "locked_by_user_id": "usr_9921bdfa",
    "locked_parameters": {
      "style_code": "#Style 08",
      "characters_locked": 3,
      "environments_locked": 5,
      "props_locked": 4
    }
  }
}
```

---

### 4.3 Dialogue Pacing Calibration
- **Endpoint:** `POST /api/v1/scenes/{scene_id}/calibrate-dialogue`
- **Status:** **`[PLANNED]`**
- **Authentication:** Bearer Token (Role: Director / Writer)
- **Purpose:** Automatically validates dialogue length against the 5.0-second generative limit and calculates J/L audio transitions.

#### Request Body:
```json
{
  "target_language": "id-ID",
  "max_seconds_per_chunk": 5.0
}
```

#### Response (200 OK):
```json
{
  "data": {
    "scene_id": "4b87e221-a1b9-4a02-a192-3d9284fae101",
    "total_calibrated_chunks": 4,
    "chunks": [
      {
        "line_number": 1,
        "character_name": "Arya",
        "raw_text": "Kita tidak punya waktu lagi untuk berdebat di sini, sistem distrik sedang runtuh.",
        "syllable_count": 28,
        "estimated_duration_seconds": 4.6,
        "transition_type": "J_CUT",
        "audio_lead_seconds": 1.2,
        "passes_5s_limit": true
      }
    ]
  }
}
```

---

### 4.4 Shot Video Generation Dispatch
- **Endpoint:** `POST /api/v1/shots/{shot_id}/generate`
- **Status:** **`[PLANNED]`**
- **Authentication:** Bearer Token (Role: Cinematographer / Director)
- **Headers:** `Idempotency-Key: <unique-client-token>`

#### Request Body:
```json
{
  "provider_target": "comfyui_local",
  "engine_model": "wan2.1_t2v_14b",
  "resolution": "1920x1080",
  "duration_seconds": 5.0,
  "seed": 8492019482,
  "cfg_scale": 7.0,
  "motion_speed": "#Speed 03",
  "apply_ip_adapter_face": true
}
```

#### Response (202 Accepted):
```json
{
  "data": {
    "job_id": "job_3a8f9c11-0982-42fe-bcae-8df92018ea1b",
    "shot_id": "shot_77b912ca-1029-4d81-9bfe-3d849204812a",
    "status": "QUEUED",
    "provider": "comfyui_local",
    "estimated_latency_seconds": 45,
    "queue_position": 1,
    "created_at": "2026-11-19T09:20:00Z"
  }
}
```

---

### 4.5 Asynchronous Job Polling
- **Endpoint:** `GET /api/v1/jobs/{job_id}`
- **Status:** **`[PLANNED]`**
- **Authentication:** Bearer Token

#### Response (200 OK - In Progress):
```json
{
  "data": {
    "job_id": "job_3a8f9c11-0982-42fe-bcae-8df92018ea1b",
    "shot_id": "shot_77b912ca-1029-4d81-9bfe-3d849204812a",
    "status": "PROCESSING",
    "progress_percent": 68.5,
    "current_node": "KSampler_Wan2.1",
    "elapsed_time_seconds": 31,
    "completed_at": null,
    "result_asset_key": null
  }
}
```

#### Response (200 OK - Completed):
```json
{
  "data": {
    "job_id": "job_3a8f9c11-0982-42fe-bcae-8df92018ea1b",
    "shot_id": "shot_77b912ca-1029-4d81-9bfe-3d849204812a",
    "status": "COMPLETED",
    "progress_percent": 100.0,
    "elapsed_time_seconds": 42,
    "completed_at": "2026-11-19T09:20:42Z",
    "result_asset_key": "cas/8f/3e/8f3e2b9c7a10298374fbead74892018a.mp4",
    "qc_report_id": "qc_9872134a-99aa-41bc-9023-fa18274901ba"
  }
}
```

---

### 4.6 Automated Quality Control Report
- **Endpoint:** `GET /api/v1/shots/{shot_id}/qc/report`
- **Status:** **`[PLANNED]`**
- **Authentication:** Bearer Token

#### Response (200 OK):
```json
{
  "data": {
    "shot_id": "shot_77b912ca-1029-4d81-9bfe-3d849204812a",
    "overall_score": 0.89,
    "passed": true,
    "metrics": {
      "face_similarity_insightface": 0.88,
      "clip_text_video_score": 0.84,
      "aesthetic_predictor_score": 8.7,
      "temporal_jitter_variance": 0.08,
      "audio_snr_db": 34.2,
      "lip_sync_confidence": 0.91
    },
    "critical_defects": [],
    "warnings": [
      "Minor contrast spike in frame 48 due to simulated lightning strike (#Light 11)"
    ]
  }
}
```

---

## 5. Security & Rate Limiting Specifications

1. **Token Authentication:** All `/api/v1/*` routes (except health probes) require an `Authorization: Bearer <JWT>` header signed with RS256.
2. **Rate Limits:**
   - Public health endpoints: `60 requests/minute`.
   - General API endpoints: `300 requests/minute`.
   - Generation endpoints (`/generate`, `/generate-voice`): `10 requests/minute` per project.
3. **CORS & Allowed Hosts:** Enforced via `TrustedHostMiddleware` and Starlette `CORSMiddleware`, restricting browser origins to `localhost`, `127.0.0.1`, and `https://producer.apologets.com`.
