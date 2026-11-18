# ADR-0002: Application Structure

Project: MovieAIProducer
ADR ID: ADR-0002
Status: Proposed
Date: 2026-11-18
Decision Owner: Project Architecture

1. Context

MovieAIProducer memiliki banyak domain produksi film yang saling berhubungan.

Struktur aplikasi harus mendukung:

- Domain separation.
- Clean Architecture.
- Independent testing.
- Reusable components.
- Provider independence.
- Background processing.
- Future scalability.
- Maintainable codebase.

Struktur folder tidak boleh hanya mengikuti jenis file. Struktur harus mencerminkan tanggung jawab bisnis dan batas domain.

2. Problem Statement

Tanpa struktur aplikasi yang konsisten, risiko yang dapat muncul:

1. Business logic tersebar di API routes.
2. Database queries bercampur dengan business logic.
3. Provider SDK digunakan langsung oleh domain.
4. Modul saling mengakses internal implementation.
5. Circular dependencies.
6. Duplicate business rules.
7. Testing menjadi sulit.
8. Perubahan satu fitur merusak fitur lain.

Diperlukan standar application structure yang konsisten.

3. Decision Drivers

Prioritas:

- Clear module ownership.
- Separation of concerns.
- Dependency control.
- Testability.
- Maintainability.
- Developer productivity.
- AI coding agent compatibility.
- Incremental implementation.

4. Options Considered

Option A: Layer-Based Structure Only

Contoh:

src/
├── controllers/
├── services/
├── repositories/
├── models/
└── utilities/

Advantages:

- Mudah dipahami.
- Cepat dibuat.
- Cocok untuk aplikasi kecil.

Disadvantages:

- Domain tersebar di banyak folder.
- Ownership tidak jelas.
- Modul mudah saling bergantung.

Option B: Feature-Based Structure

Contoh:

src/
├── projects/
├── screenplay/
├── characters/
├── prompts/
└── production/

Advantages:

- Domain lebih mudah ditemukan.
- Feature ownership lebih jelas.
- Cocok untuk pengembangan modular.

Disadvantages:

- Layer boundaries dapat tidak konsisten.
- Infrastruktur dan business logic dapat bercampur.

Option C: Domain Modules + Clean Architecture

Setiap domain memiliki pemisahan tanggung jawab internal.

Advantages:

- Domain ownership jelas.
- Dependency lebih terkendali.
- Testing lebih mudah.
- Mendukung pertumbuhan sistem.

Disadvantages:

- Struktur awal lebih kompleks.
- Membutuhkan standar konsisten.
- Memerlukan aturan komunikasi antar-modul.

5. Proposed Decision

Menggunakan Domain-Oriented Modular Structure dengan Clean Architecture boundaries.

Struktur final harus disesuaikan dengan repository discovery dan stack yang benar-benar digunakan.

6. Proposed Logical Structure

movieai-producer/
│
├── apps/
│   ├── api/
│   ├── web/
│   └── worker/
│
├── packages/
│   ├── shared-contracts/
│   ├── shared-types/
│   └── shared-utils/
│
├── backend/
│   └── src/
│       ├── domain/
│       │   ├── projects/
│       │   ├── creative_brief/
│       │   ├── story/
│       │   ├── screenplay/
│       │   ├── production_bible/
│       │   ├── characters/
│       │   ├── environments/
│       │   ├── props/
│       │   ├── wardrobe/
│       │   ├── storyboard/
│       │   ├── cinematography/
│       │   ├── prompts/
│       │   ├── production/
│       │   ├── continuity/
│       │   ├── quality_control/
│       │   └── editorial/
│       │
│       ├── application/
│       │   ├── projects/
│       │   ├── screenplay/
│       │   ├── production/
│       │   ├── prompts/
│       │   ├── continuity/
│       │   └── quality_control/
│       │
│       ├── infrastructure/
│       │   ├── database/
│       │   ├── providers/
│       │   ├── storage/
│       │   ├── queue/
│       │   ├── observability/
│       │   └── security/
│       │
│       ├── presentation/
│       │   └── api/
│       │
│       └── bootstrap/
│
├── frontend/
│   └── src/
│       ├── app/
│       ├── features/
│       ├── components/
│       ├── layouts/
│       ├── hooks/
│       ├── services/
│       ├── state/
│       └── types/
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   └── fixtures/
│
├── docs/
├── scripts/
├── infrastructure/
├── .github/
│   └── workflows/
│
├── AGENTS.md
├── README.md
├── CONTRIBUTING.md
└── CHANGELOG.md

Đây là logical proposal. Tidak boleh membuat seluruh struktur tersebut secara otomatis sebelum audit repository.

7. Domain Module Internal Structure

Setiap domain module dapat menggunakan struktur:

projects/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── events.py
│   └── exceptions.py
│
├── application/
│   ├── commands.py
│   ├── queries.py
│   ├── use_cases.py
│   └── ports.py
│
├── infrastructure/
│   └── repositories/
│
└── tests/

Struktur dan ekstensi file mengikuti bahasa pemrograman aktual.

Jangan membuat file kosong hanya untuk memenuhi template.

8. Dependency Rules

Aturan dependency:

Presentation
     |
     v
Application
     |
     v
Domain

Infrastructure
     |
     v
Application Ports

Ketentuan:

1. Domain tidak bergantung pada framework.
2. Domain tidak bergantung pada database SDK.
3. Application layer mengatur use cases.
4. Infrastructure mengimplementasikan interfaces.
5. Presentation tidak menyimpan business rules.
6. Provider SDK hanya digunakan melalui provider adapters.
7. Shared packages tidak boleh menjadi tempat menumpuk business logic.

Dependency harus mengarah ke abstraction yang stabil.

9. Module Ownership

Module| Responsibility
Projects| Project lifecycle
Creative Brief| Creative requirements
Story| Story architecture
Screenplay| Script and dialogue
Production Bible| MPB source of truth
Characters| Character DNA and states
Environments| Location and environment states
Props| Prop identity and continuity
Wardrobe| Costume and appearance
Storyboard| Visual scene planning
Cinematography| Camera and lens direction
Prompts| Prompt specification and compilation
Production| Generation orchestration
Continuity| Cross-scene consistency
Quality Control| Quality evaluation
Editorial| Editing and delivery

Setiap domain memiliki owner yang bertanggung jawab atas business rules dan kontraknya.

10. Cross-Module Communication

Modul tidak boleh mengakses internal implementation modul lain secara bebas.

Gunakan:

- Public application interfaces.
- Explicit commands and queries.
- Domain events jika sesuai.
- Shared contracts yang stabil.
- Transaction boundaries yang jelas.

Hindari:

- Direct access ke private repositories modul lain.
- Circular imports.
- Shared mutable state.
- Database table access tanpa ownership rules.

11. Shared Code Policy

Shared code hanya digunakan apabila benar-benar memiliki makna lintas domain.

Contoh:

- UUID utilities.
- Time utilities.
- Common error contracts.
- Shared API types.
- Trace context.
- Common validation primitives.

Jangan menempatkan semua fungsi ke dalam "common", "helpers", atau "utils".

Business rules harus tetap berada di domain pemiliknya.

12. Frontend Structure

Frontend menggunakan feature-oriented architecture.

Prinsip:

- Feature components terisolasi.
- Shared UI components terpusat.
- API communication melalui service layer.
- State management memiliki ownership jelas.
- Business logic penting tidak hanya berada di UI.
- Error, loading, empty, dan success states harus konsisten.

Production workspace menggunakan landscape-oriented interface sesuai "UI_UX.md".

13. Worker Structure

Background worker harus menjadi execution boundary tersendiri.

Tanggung jawab:

- Process production jobs.
- Execute provider tasks.
- Process assets.
- Run continuity checks.
- Run QC tasks.
- Handle retries.
- Report job lifecycle.

Worker menggunakan application use cases dan infrastructure adapters yang sama dengan API.

Jangan menduplikasi business logic antara API dan worker.

14. Configuration Management

Konfigurasi dipisahkan berdasarkan environment:

- Development.
- Testing.
- Staging.
- Production.

Aturan:

- Tidak ada hardcoded secrets.
- Gunakan validated configuration.
- Tetapkan safe defaults.
- Fail fast jika required configuration tidak tersedia.
- Jangan menyimpan environment-specific values di domain layer.

15. Testing Structure

Tests harus mengikuti domain dan application boundaries.

Minimum:

- Domain unit tests.
- Application use-case tests.
- Infrastructure integration tests.
- Provider contract tests.
- API tests.
- Frontend tests.
- End-to-end workflow tests.

Setiap modul harus memiliki test ownership yang jelas.

16. Risks & Mitigation

Risk| Mitigation
Too many small modules| Domain boundary review
Excessive abstraction| Require practical justification
Circular dependencies| Automated dependency checks
Shared package sprawl| Ownership policy
Inconsistent module structure| Architecture conventions
Premature monorepo complexity| Repository discovery first

17. Implementation Requirements

Sebelum menerapkan struktur:

1. Audit repository.
2. Identifikasi existing folder structure.
3. Identifikasi entry points.
4. Identifikasi existing domain modules.
5. Identifikasi import dependencies.
6. Periksa build dan deployment workflow.
7. Susun target structure.
8. Buat migration plan.
9. Refactor secara bertahap.
10. Jalankan regression tests.

Tidak boleh melakukan rewrite besar tanpa alasan teknis dan migration strategy.

18. Validation Criteria

Keputusan ini dapat diterima apabila:

- Setiap domain memiliki ownership.
- Dependency direction konsisten.
- Domain dapat diuji secara independen.
- Provider SDK tidak bocor ke domain.
- Cross-module contracts jelas.
- Tidak ada circular dependencies.
- API dan worker tidak menduplikasi business logic.
- Struktur mendukung incremental development.

19. Consequences

Positive

- Struktur lebih mudah dipahami.
- Perubahan lebih terisolasi.
- Testing lebih terarah.
- AI coding agents lebih mudah menemukan konteks.
- Pengembangan paralel lebih aman.

Negative

- Memerlukan disiplin boundaries.
- Ada overhead awal dalam perancangan.
- Cross-module operations membutuhkan contract design.

20. Related Documents

- "ARCHITECTURE.md"
- "TASKS.md"
- "DATA_MODEL.md"
- "API_SPEC.md"
- "AGENTS.md"
- "CONTRIBUTING.md"
- "TEST_STRATEGY.md"
- "DEPLOYMENT.md"

21. Final Principle

Struktur aplikasi harus mengikuti domain dan tanggung jawab, bukan sekadar jenis file.

Organize by business capability. Enforce architectural boundaries. Keep implementation replaceable.

---

ADR Status: Proposed
Acceptance Condition: Repository discovery, dependency analysis, dan architecture review selesai.
