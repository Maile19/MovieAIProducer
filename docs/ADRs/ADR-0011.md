# ADR-0011: Authentication & Authorization

- Project: MovieAIProducer
- ADR ID: ADR-0011
- Title: Authentication & Authorization
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Decision Owners: Security Architect, Technical Lead, Product Owner
- Related ADRs: ADR-0001, ADR-0002, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0010
- Reference Documents: SECURITY.md, API_SPEC.md, DATA_MODEL.md

---

1. Context

MovieAIProducer adalah platform produksi film berbasis kecerdasan buatan (AI) yang mengorkestrasi alur kerja kreatif tingkat profesional: dari brief kreatif, penulisan skenario, Master Production Bible (MPB), perancangan karakter dan dunia, storyboard, animatic, kompilasi prompt, eksekusi render AI multi-provider, kontinuitas, hingga Quality Control (QC).

Seluruh siklus ini melibatkan aset digital bernilai tinggi, kekayaan intelektual (IP) skenario, aset referensi visual/suara, serta kredensial provider AI pihak ketiga (OpenAI, Anthropic, Runway, Kling, ElevenLabs, dll.) yang memiliki implikasi biaya finansial nyata pada setiap eksekusi komputasi.

Selain itu, produksi film adalah kerja kolaboratif yang melibatkan beragam peran dengan tanggung jawab berbeda: Sutradara (Director), Produser (Producer), Editor, Operator AI, QC Reviewer, dan Eksekutif/Klien. Setiap peran membutuhkan tingkat akses dan wewenang yang spesifik.

Oleh karena itu, MovieAIProducer membutuhkan arsitektur Autentikasi (Authentication / AuthN) dan Otorisasi (Authorization / AuthZ) yang kokoh, modular, terisolasi per-project, aman secara default, serta mematuhi prinsip *Least Privilege* dan *Defense in Depth*.

---

2. Problem Statement

Tanpa arsitektur autentikasi dan otorisasi yang terdefinisi secara ketat, sistem menghadapi risiko kritis:

1. **Kebocoran Kekayaan Intelektual (IP):** Skenario, konsep cerita, dan aset visual pra-rilis dapat diakses oleh pihak yang tidak berhak.
2. **Penyalahgunaan API Key & Pemborosan Biaya AI:** Akses tanpa batas pada endpoint eksekusi AI generation dapat memicu pemborosan kuota API atau serangan pembengkakan tagihan (*financial exhaustion*).
3. **Modifikasi Tidak Sah pada Master Production Bible (MPB):** Snapshot MPB yang telah disetujui (Approved DNA) dapat diubah tanpa otorisasi sutradara, merusak konsistensi film secara keseluruhan.
4. **Ketiadaan Pemisahan Peran (Role Confusion):** Operator render atau reviewer dapat secara tidak sengaja mengubah skrip atau menyetujui rilis tanpa wewenang produser/sutradara.
5. **Kebocoran Data Lintas Project (Cross-Project Contamination / IDOR):** Pengguna pada satu project dapat membaca atau memodifikasi aset project lain akibat ketiadaan validasi *ownership boundary*.
6. **Kerentanan Sesi & Kredensial:** Penyimpanan token yang tidak aman (misalnya di `localStorage`) membuka celah pencurian sesi via Cross-Site Scripting (XSS) atau serangan Cross-Site Request Forgery (CSRF).
7. **Ketiadaan Jejak Audit (Audit Trail):** Perubahan kritis, approval, atau pemicuan pekerjaan tidak dapat dilacak secara akuntabel kepada individu tertentu.

---

3. Decision Drivers

Keputusan perancangan ini didorong oleh prinsip-prinsip utama:

1. **Defense in Depth & Secure by Default:** Keamanan berlapis di level gateway, session, middleware, domain service, database, dan file storage. Seluruh endpoint dan aset privat secara default.
2. **Least Privilege & Role-Based Access Control (RBAC):** Hak akses diberikan seminimal mungkin sesuai fungsi kerja pada tingkat project.
3. **Project Isolation & Strict Ownership Boundaries:** Isolasi ketat antar-project; ketiadaan akses lintas batas tanpa izin eksplisit.
4. **Protection of AI Provider Credentials:** API key provider pihak ketiga tidak boleh terekspos ke sisi klien/frontend dalam keadaan apa pun.
5. **Session Hygiene & Token Lifecycle:** Penggunaan standard industri terkini (Argon2id untuk hashing password, HttpOnly SameSite secure cookies untuk web client, dan JWT dengan rotasi refresh token untuk API/CLI).
6. **Separation of Concerns:** Pemisahan yang bersih antara modul AuthN (verifikasi identitas) dan AuthZ (verifikasi wewenang aksi).
7. **Auditability & Non-repudiation:** Pencatatan log keamanan yang lengkap untuk setiap aksi autentikasi, perubahan hak akses, dan approval produksi.
8. **Scalability & Extensibility:** Mendukung arsitektur modular monolith saat ini, dengan jalur evolusi yang mulus menuju SSO (OAuth2/OIDC) dan multi-tenancy di masa mendatang.

---

4. Options Considered

### Opsi 1: Simple Shared API Key / Single User Model
- **Deskripsi:** Menggunakan sistem kunci API global tunggal atau autentikasi berbasis file konfigurasi lokal.
- **Kelebihan:** Sangat cepat diimplementasikan untuk prototipe lokal awal.
- **Kelemahan:** Tidak mendukung kolaborasi tim, tidak memiliki pemisahan peran sutradara/produser/operator, rawan kebocoran, tidak memenuhi standar produksi profesional.
- **Hasil:** Ditolak.

### Opsi 2: Ketergantungan Penuh pada Managed Auth Provider Eksternal (Auth0 / Clerk / Firebase)
- **Deskripsi:** Menyerahkan seluruh manajemen identitas, sesi, dan otorisasi ke layanan SaaS eksternal.
- **Kelebihan:** Manajemen UI login dan MFA siap pakai.
- **Kelemahan:** Mengunci platform pada vendor tertentu (*vendor lock-in*), menyulitkan instalasi on-premise/self-hosted atau offline sandbox studio film, latensi jaringan tambahan pada setiap verifikasi token internal, dan biaya lisensi per-pengguna aktif.
- **Hasil:** Ditolak sebagai fondasi inti (namun arsitektur harus menyediakan adapter untuk integrasi OIDC di masa mendatang).

### Opsi 3: Modular Internal Auth Engine dengan Dual-Mode Session/JWT dan Project-Scoped RBAC (Dipilih)
- **Deskripsi:** Membangun core autentikasi internal di dalam domain MovieAIProducer menggunakan library kriptografi standar (Argon2id, Cryptography, PyJWT), mendukung session cookie (HttpOnly) untuk UI web dan Bearer Token untuk CLI/Service/Agent, dipadukan dengan Project-Scoped RBAC dan Permission Matrix granular.
- **Kelebihan:** Mandiri, tanpa dependensi vendor eksternal, berkinerja tinggi, mendukung deployment self-hosted/air-gapped, memfasilitasi integrasi agen AI/CLI, dan terintegrasi langsung dengan model domain project.
- **Kelemahan:** Membutuhkan implementasi penanganan rotasi token dan session security yang cermat.
- **Hasil:** Diterima.

---

5. Architecture Decision

MovieAIProducer menetapkan **Modular Internal Authentication & Project-Scoped RBAC Architecture**.

### 5.1 Komponen Inti Arsitektur

Arsitektur terdiri dari 6 komponen utama:

1. **Identity & Password Management Subsystem:**
   - Password disimpan menggunakan algoritma **Argon2id** (memory-hard, resistant to GPU/ASIC brute-force).
   - Validasi kompleksitas password (panjang minimum, entropi, pencegahan common passwords).
   - Verifikasi email dan alur reset password berbasis token kriptografis berbatas waktu (*time-bound cryptographically signed tokens*).

2. **Dual-Mode Session & Token Manager:**
   - **Web Browser Client:** Menggunakan sesi berbasis **HttpOnly, Secure, SameSite=Lax/Strict** cookie untuk mencegah serangan XSS mencuri kredensial.
   - **CLI, Automation & AI Agents:** Menggunakan **Bearer Access Token (JWT)** berumur pendek (15 menit) yang dipasangkan dengan **Refresh Token** berumur panjang (7-30 hari) dengan mekanisme *Single-Use Refresh Token Rotation* dan deteksi penggunaan kembali (*replay detection*).

3. **Project Membership & Context Resolver:**
   - Pengguna dapat menjadi anggota di banyak project dengan peran (*role*) yang berbeda di masing-masing project.
   - Setiap request yang berinteraksi dengan resource project wajib menyelesaikan *Project Context* dan memvalidasi keanggotaan aktif pengguna pada project tersebut.

4. **Granular Permission & RBAC Engine:**
   - Menyediakan 8 peran produksi standar film.
   - Memetakan setiap peran ke sekumpulan *atomic permissions* (contoh: `mpb.approve`, `scene.execute`, `qc.review`).
   - Melakukan evaluasi izin secara deklaratif pada level endpoint/route dan domain service.

5. **Secrets & Provider Credential Vault:**
   - Kredensial eksternal (API Key AI Provider, Storage S3 Secret) dienkripsi saat istirahat (*encrypted at rest*) menggunakan AES-256-GCM.
   - Kunci dekripsi master dikelola melalui *Environment Variable* / Key Management System yang terisolasi.
   - Kredensial provider tidak pernah dikirimkan ke frontend atau dicatat dalam log aplikasi.

6. **Security Audit Logger:**
   - Mencatat setiap peristiwa keamanan: login berhasil/gagal, logout, penggantian password, perubahan peran anggota project, approval dokumen penting, dan pembatalan hak akses.

---

6. Role-Based Access Control (RBAC) Matrix

### 6.1 Definisi Peran Produksi (Production Roles)

Peran ditentukan pada cakupan per-project:

| Peran | Deskripsi Tanggung Jawab |
|---|---|
| **OWNER** | Pemilik project, memiliki kontrol absolut atas administrasi, penagihan, penghapusan project, dan penugasan anggota. |
| **ADMIN** | Pengelola konfigurasi teknis, integrasi provider API, manajemen member, dan kuota. |
| **DIRECTOR** | Penentu visi kreatif film: persetujuan naskah, approval Master Production Bible (MPB), dan persetujuan akhir setiap scene/shot. |
| **PRODUCER** | Pengendali jadwal, anggaran, alur kerja produksi, pipeline staging, dan alokasi resource eksekusi. |
| **EDITOR** | Pengelola aset, urutan adegan, perakitan shot, timeline kasar/halus, dan ekspor produksi. |
| **OPERATOR** | Penanggung jawab teknis eksekusi pekerjaan AI: memicu kompilasi prompt, rendering shot, dan pemantauan job. |
| **REVIEWER** | Petugas peninjau kualitas dan kontinuitas: menjalankan QC, memberikan catatan revisi, dan validasi kepatuhan MPB. |
| **VIEWER** | Akses baca saja (*read-only*) untuk stakeholder eksternal, klien, atau peninjau tanpa hak eksekusi. |

### 6.2 Matriks Hak Akses (Permission Matrix)

| Kategori Permission | Nama Permission | OWNER | ADMIN | DIRECTOR | PRODUCER | EDITOR | OPERATOR | REVIEWER | VIEWER |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Project** | `project.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | `project.update` | ✓ | ✓ | - | ✓ | - | - | - | - |
| | `project.delete` | ✓ | - | - | - | - | - | - | - |
| | `project.members.manage`| ✓ | ✓ | - | - | - | - | - | - |
| **Secrets/Providers**| `provider.config.read` | ✓ | ✓ | - | - | - | - | - | - |
| | `provider.config.update`| ✓ | ✓ | - | - | - | - | - | - |
| **Screenplay/Story** | `story.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | `story.write` | ✓ | - | ✓ | - | - | - | - | - |
| | `story.approve` | ✓ | - | ✓ | ✓ | - | - | - | - |
| **Master Bible (MPB)**| `mpb.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | `mpb.draft` | ✓ | - | ✓ | - | - | - | - | - |
| | `mpb.approve` (DNA Lock)| ✓ | - | ✓ | - | - | - | - | - |
| **Shot & Direction** | `shot.plan` | ✓ | - | ✓ | ✓ | ✓ | - | - | - |
| | `shot.execute` (AI Run) | ✓ | - | - | ✓ | - | ✓ | - | - |
| | `job.cancel` | ✓ | ✓ | - | ✓ | - | ✓ | - | - |
| **Continuity & QC** | `qc.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | `qc.run` | ✓ | - | - | ✓ | - | ✓ | ✓ | - |
| | `qc.approve` | ✓ | - | ✓ | ✓ | - | - | ✓ | - |
| | `qc.override_blocker` | ✓ | - | ✓ | - | - | - | - | - |
| **Assets & Export** | `asset.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | `asset.manage` | ✓ | ✓ | - | ✓ | ✓ | - | - | - |
| | `asset.export_master` | ✓ | - | ✓ | ✓ | ✓ | - | - | - |

---

7. Data Model Autentikasi & Otorisasi

Berikut adalah skema relasional tabel inti untuk domain keamanan:

```
[User]
  id: UUID (PK)
  email: VARCHAR(255) (UNIQUE, indexed)
  password_hash: VARCHAR(255)
  full_name: VARCHAR(150)
  is_active: BOOLEAN (default: true)
  is_verified: BOOLEAN (default: false)
  is_superuser: BOOLEAN (default: false)
  mfa_enabled: BOOLEAN (default: false)
  mfa_secret_encrypted: VARCHAR(255) (nullable)
  created_at: TIMESTAMP WITH TIMEZONE
  updated_at: TIMESTAMP WITH TIMEZONE

[Session]
  id: UUID (PK)
  user_id: UUID (FK -> User.id, ON DELETE CASCADE)
  session_token_hash: VARCHAR(64) (UNIQUE, SHA-256)
  ip_address: VARCHAR(45)
  user_agent: TEXT
  expires_at: TIMESTAMP WITH TIMEZONE
  revoked_at: TIMESTAMP WITH TIMEZONE (nullable)
  created_at: TIMESTAMP WITH TIMEZONE

[RefreshToken]
  id: UUID (PK)
  user_id: UUID (FK -> User.id, ON DELETE CASCADE)
  token_hash: VARCHAR(64) (UNIQUE, SHA-256)
  token_family: UUID (indexed)
  is_revoked: BOOLEAN (default: false)
  expires_at: TIMESTAMP WITH TIMEZONE
  created_at: TIMESTAMP WITH TIMEZONE

[ProjectMember]
  id: UUID (PK)
  project_id: UUID (FK -> Project.id, ON DELETE CASCADE)
  user_id: UUID (FK -> User.id, ON DELETE CASCADE)
  role: VARCHAR(50) (OWNER, ADMIN, DIRECTOR, PRODUCER, EDITOR, OPERATOR, REVIEWER, VIEWER)
  created_at: TIMESTAMP WITH TIMEZONE
  updated_at: TIMESTAMP WITH TIMEZONE
  UNIQUE(project_id, user_id)

[ProjectInvitation]
  id: UUID (PK)
  project_id: UUID (FK -> Project.id, ON DELETE CASCADE)
  email: VARCHAR(255)
  role: VARCHAR(50)
  token_hash: VARCHAR(64) (UNIQUE)
  invited_by: UUID (FK -> User.id)
  expires_at: TIMESTAMP WITH TIMEZONE
  accepted_at: TIMESTAMP WITH TIMEZONE (nullable)
  created_at: TIMESTAMP WITH TIMEZONE

[AuditLog]
  id: UUID (PK)
  user_id: UUID (FK -> User.id, nullable)
  project_id: UUID (FK -> Project.id, nullable, indexed)
  event_type: VARCHAR(100) (indexed)
  action: VARCHAR(100)
  resource_type: VARCHAR(100)
  resource_id: VARCHAR(100) (nullable)
  details_json: JSON / TEXT
  ip_address: VARCHAR(45)
  user_agent: TEXT
  timestamp: TIMESTAMP WITH TIMEZONE (default: NOW(), indexed)
```

---

8. Token & Session Management Lifecycle

### 8.1 Strategi Password Hashing
- Algoritma: **Argon2id** (varian hybrid dari Argon2 yang tahan terhadap side-channel dan GPU cracking).
- Parameter Standar (OWASP Recommended):
  - Memory: 64 MB (65536 KiB)
  - Iterations (Time): 3
  - Parallelism: 4 threads
- Salt: Kriptografis acak 16-byte yang digenerate otomatis per password.

### 8.2 Web Session Strategy
- Klien web menerima session cookie:
  - `Name`: `__Host-movieai_session` (menggunakan prefix `__Host-` untuk memastikan origin dan HTTPS-only).
  - `HttpOnly`: True (mencegah akses JavaScript, memitigasi pencurian sesi via XSS).
  - `Secure`: True (hanya ditransmisikan melalui HTTPS).
  - `SameSite`: `Lax` (atau `Strict` untuk operasi mutasi), mencegah serangan CSRF lintas domain.
  - `Path`: `/`
- Durasi idle timeout: 2 jam; Durasi absolut timeout: 24 jam.

### 8.3 API / CLI / Agent Token Lifecycle
Untuk interaksi tanpa cookie (CLI developer, SDK Python, dan Background Agents):
1. **Access Token (JWT):**
   - Berisi claims standar: `sub` (User ID), `iat`, `exp`, `jti`.
   - Masa berlaku: **15 menit**.
   - Ditandatangani menggunakan algoritma asimetris (RS256/EdDSA) atau simetris yang aman (HS256 dengan secret minimum 256-bit).
2. **Refresh Token:**
   - String berentropi tinggi (kriptografis 256-bit acak), disimpan dalam database dalam bentuk hash SHA-256.
   - Masa berlaku: **14 hari**.
   - Setiap penggunaan refresh token menghasilkan pasangan Access Token baru dan Refresh Token baru (**Refresh Token Rotation**).
   - Jika refresh token yang sudah pernah digunakan dikirim kembali, sistem mendeteksi *Token Reuse Attack*, segera membatalkan seluruh silsilah keluarga token (*token family*), dan memaksa re-autentikasi pengguna.

---

9. Otorisasi & Project Isolation Enforcement

### 9.1 Mekanisme Evaluasi di FastAPI
Setiap endpoint API dilindungi melalui dependency injection bertingkat:

```python
# Contoh Alur Otorisasi FastAPI
@router.post("/projects/{project_id}/shots/{shot_id}/generate")
async def execute_shot_generation(
    project_id: UUID,
    shot_id: UUID,
    current_user: User = Depends(get_current_active_user),
    permission: None = Depends(require_project_permission("shot.execute"))
):
    # Logika eksekusi generation hanya berjalan jika:
    # 1. User terautentikasi dan aktif.
    # 2. User adalah anggota aktif dari project_id.
    # 3. Peran user memiliki permission "shot.execute".
    ...
```

### 9.2 Isolasi Database Lintas Project
1. **Mandatory Project Scope:** Setiap query yang mengakses resource turunan (Scene, Shot, Character, Asset, QC Report) WAJIB menyertakan klausul filter `WHERE project_id = :project_id` secara deterministik pada repository layer.
2. **Resource Ownership Verification:** Sebelum melakukan pembaruan atau penghapusan data, service layer wajib memastikan bahwa resource yang dituju memang berelasi dengan `project_id` dari konteks sesi pemanggil.
3. **No Cross-Project Foreign Keys:** Data kreatif dari satu project dilarang keras mereferensikan entitas project lain secara langsung tanpa proses import/duplikasi resmi.

---

10. Perlindungan Kredensial AI Provider & Secrets

Provider Adapter System (ADR-0003) membutuhkan API Key untuk berkomunikasi dengan model AI eksternal.

Aturan Perlindungan Kredensial:
1. **Penyimpanan di Level Environment / Encrypted Vault:**
   - Kunci API default sistem disimpan dalam environment variable host (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, dll.).
   - Jika project menggunakan kunci API khusus milik user/project (*Bring Your Own Key* - BYOK), nilai tersebut dienkripsi di database menggunakan **AES-256-GCM** dengan salt dan initialization vector (IV) unik.
2. **Kerahasiaan Mutlak pada API Contract:**
   - Serializer dan skema respons API dilarang keras mengembalikan nilai kunci asli. Response hanya boleh mengembalikan metadata (misal: `"provider": "openai"`, `"is_configured": true`, `"key_preview": "...ab12"`).
3. **Penyembunyian Log (Log Masking):**
   - Seluruh logging HTTP client, tracer observability, dan pesan error wajib menyaring (*redact*) header autentikasi (`Authorization: Bearer ***`) dan parameter rahasia.

---

11. Alur Kerja (Workflows)

### 11.1 Alur Autentikasi Pengguna
```
[User] -> (POST /api/v1/auth/login [email, password])
       -> [Auth Service]
            1. Query User by email
            2. Verifikasi Argon2id password hash
            3. Periksa status is_active dan is_verified
            4. Buat record Session & AuditLog (LOGIN_SUCCESS)
            5. Set HttpOnly Cookie / Return JWT + Refresh Token
```

### 11.2 Alur Evaluasi Otorisasi Request
```
[Request] -> [FastAPI Authentication Middleware]
          -> Memvalidasi Session Cookie / Bearer JWT -> Mengidentifikasi User
          -> [Project Context Resolver]
          -> Mengecek Membership User pada Target Project ID
          -> Mengekstrak Role User pada Project tersebut
          -> [Permission Guard]
          -> Memeriksa apakah Role memiliki izin yang diperlukan (misal: `mpb.approve`)
          -> Jika TIDAK: Return 403 Forbidden (AuditLog: PERMISSION_DENIED)
          -> Jika YA: Teruskan ke Domain Service / Business Logic
```

---

12. Rencana Implementasi Bertahap (Implementation Sequence)

### Fase 1: Core Identity & Local Auth (P0 - MVP)
- [x] Dokumen spesifikasi ADR-0011 dan penyelarasan dengan `SECURITY.md`.
- [ ] Implementasi tabel database `users`, `sessions`, `refresh_tokens`, `project_members`, dan `audit_logs` via Alembic migration.
- [ ] Service hashing password menggunakan `argon2-cffi`.
- [ ] Endpoint `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/me`.
- [ ] Middleware autentikasi dan FastAPI dependencies (`get_current_user`, `get_current_active_user`).
- [ ] Pengujian unit dan integrasi untuk login dan proteksi route.

### Fase 2: Project RBAC & Context Guards (P0 - MVP)
- [ ] Implementasi resolver project membership dan permission matrix.
- [ ] Dependency guard `require_project_permission(perm_name)`.
- [ ] Proteksi seluruh endpoint project yang ada (`/api/v1/projects/*`).
- [ ] Audit logging untuk seluruh aksi otorisasi dan penolakan akses.

### Fase 3: Hardening & Secret Encryption (P1)
- [ ] Modul enkripsi kredensial provider (AES-256-GCM) untuk BYOK.
- [ ] Rate limiting pada endpoint sensitif (login, reset password).
- [ ] Integrasi CSRF protection untuk session cookie.
- [ ] Dukungan rotasi token keluarga refresh token.

### Fase 4: Enterprise & Identity Federation (P2 - Post-MVP)
- [ ] Integrasi Single Sign-On (SSO) via OAuth2/OIDC (Google, GitHub, Studio IdP).
- [ ] Multi-Factor Authentication (MFA) berbasis TOTP.
- [ ] Dukungan Service Accounts untuk pipeline CI/CD eksternal.

---

13. Konsekuensi Keputusan (Consequences)

### Positif:
- **Kekayaan Intelektual Terlindungi:** Skenario, karakter, dan aset film aman di dalam batas project masing-masing.
- **Biaya Terkendali:** Eksekusi render AI hanya dapat dilakukan oleh peran yang berwenang (Producer/Operator).
- **Integritas Master Bible Terjamin:** DNA karakter dan styling visual tidak dapat dirusak oleh perubahan tanpa otorisasi Director.
- **Sesuai Standar Industri:** Menggunakan protokol keamanan standar modern (Argon2id, HttpOnly SameSite cookies, JWT rotation) tanpa mengorbankan portabilitas lokal.
- **Audit Trail yang Kuat:** Setiap tindakan penting tercatat dan dapat dipertanggungjawabkan.

### Negatif / Trade-offs:
- **Kompleksitas Tambahan pada Dependency Injection:** Setiap endpoint domain wajib menyertakan guard konteks project dan permission, menambah sedikit overhead penulisan kode.
- **Manajemen State Session:** Membutuhkan penanganan pembersihan session kadaluarsa (*session cleanup task*) secara berkala di latar belakang.

---

14. Kriteria Validasi & Penerimaan (Acceptance Criteria)

ADR ini dinyatakan diterima dan terimplementasi penuh jika:
1. Tidak ada endpoint sensitif di `/api/v1/*` yang dapat diakses tanpa autentikasi valid (kecuali endpoint publik `/auth/login`, `/auth/register`, dan `/health`).
2. Pengguna A tidak dapat membaca, mengubah, atau mengeksekusi aset milik Project B jika tidak terdaftar sebagai member aktif di Project B (bebas dari IDOR).
3. Hanya pengguna ber-role `DIRECTOR` dan `OWNER` yang diizinkan menyetujui Master Production Bible (`mpb.approve`).
4. Kunci rahasia AI provider tidak pernah bocor dalam respons JSON API maupun log aplikasi.
5. Uji penetrasi otomatis memvalidasi kekebalan terhadap session fixation, brute-force (dengan rate limiting), dan token replay.

---

15. Dokumen Terkait
- [SECURITY.md](file:///home/ubuntu/MovieAIProducer/SECURITY.md)
- [API_SPEC.md](file:///home/ubuntu/MovieAIProducer/API_SPEC.md)
- [DATA_MODEL.md](file:///home/ubuntu/MovieAIProducer/DATA_MODEL.md)
- [ADR-0001: Architecture Style](file:///home/ubuntu/MovieAIProducer/DECISIONS/ADR/ADR-0001-architecture-style.md)
- [ADR-0006: Data Storage Strategy](file:///home/ubuntu/MovieAIProducer/DECISIONS/ADR/ADR-0006-data-storage-strategy.md)
- [ADR-0010: Quality Control Engine](file:///home/ubuntu/MovieAIProducer/DECISIONS/ADR/ADR-0010-quality-control-engine.md)
