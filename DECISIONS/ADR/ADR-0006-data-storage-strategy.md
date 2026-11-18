# ADR-0006: Data Storage Strategy

Project: MovieAIProducer
ADR ID: ADR-0006
Title: Data Storage Strategy
Version: 1.0
Status: Proposed
Date: 2026-11-19
Decision Owners: Project Architecture

---

1. Context

MovieAIProducer mengelola beberapa kategori data dengan karakteristik berbeda:

1. Data bisnis: user, project, membership, permissions, dan konfigurasi.
2. Data kreatif: story, screenplay, characters, environments, props, wardrobe, dan production specifications.
3. Master Production Bible (MPB): approved specifications, revisions, snapshots, dan change history.
4. Production workflow: stages, scenes, shots, tasks, dependencies, executions, dan approvals.
5. AI orchestration: prompts, provider configurations, model capabilities, requests, responses, dan usage records.
6. Media assets: image, video, audio, storyboard, animatic, dan hasil rendering.
7. Audit history: perubahan data, approval, user actions, dan system events.
8. Operational data: background jobs, temporary files, cache, dan execution logs.

Semua data tersebut tidak memiliki kebutuhan penyimpanan yang sama.

Penyimpanan seluruh data dalam satu media dapat menimbulkan masalah performa, skalabilitas, konsistensi, backup, dan biaya operasional.

Arsitektur perlu memisahkan transactional data dari binary media assets tanpa menghilangkan integritas hubungan antar-data.

2. Problem Statement

Sistem membutuhkan strategi penyimpanan yang:

- Menjamin konsistensi data bisnis dan production workflow.
- Mempertahankan histori revisi MPB.
- Mendukung immutable production snapshots.
- Menyimpan file media berukuran besar secara efisien.
- Menjamin hubungan antara asset, scene, shot, project, dan generation job.
- Mendukung asynchronous processing.
- Memungkinkan backup dan recovery yang dapat diuji.
- Mendukung pengembangan dari MVP menuju production scale.
- Menghindari ketergantungan pada satu vendor storage.
- Menjamin isolasi dan keamanan data setiap project.

3. Decision Drivers

Prioritas keputusan:

1. Data integrity.
2. Reliability and recoverability.
3. MPB revision consistency.
4. Asset scalability.
5. Security and access control.
6. Maintainability.
7. Provider independence.
8. Operational simplicity.
9. Cost efficiency.
10. Performance under increasing workload.

4. Options Considered

Option A: All-in-Database Storage

Semua data, termasuk binary image, video, dan audio, disimpan dalam database.

Advantages:

- Satu sistem penyimpanan.
- Transaksi database dapat mencakup metadata dan binary data.
- Backup dapat dilakukan melalui mekanisme database.

Disadvantages:

- Database membengkak dengan cepat.
- Backup dan restore menjadi lebih berat.
- Media delivery kurang efisien.
- Beban database meningkat.
- Kurang ideal untuk media berukuran besar.

Decision: Rejected as the primary storage strategy.

Option B: Filesystem/Object Storage Only

Semua data disimpan sebagai file atau object, termasuk data bisnis dan workflow.

Advantages:

- Struktur file sederhana.
- Media storage fleksibel.
- Infrastruktur awal dapat terlihat lebih ringan.

Disadvantages:

- Referential integrity lebih sulit.
- Transaksi lintas-data tidak tersedia secara native.
- Query relasional kompleks.
- Concurrency dan consistency membutuhkan implementasi tambahan.
- Audit dan revision management lebih sulit.

Decision: Rejected as the primary storage strategy.

Option C: Hybrid Storage Architecture

Memisahkan transactional database, binary asset storage, asynchronous job processing, dan optional caching.

Advantages:

- Data ownership lebih jelas.
- Relational integrity dapat dipertahankan.
- Media storage dapat berkembang secara independen.
- Mendukung asynchronous production workflow.
- Memudahkan backup dan recovery berdasarkan kategori data.
- Dapat menggunakan provider storage yang berbeda.

Disadvantages:

- Memerlukan koordinasi metadata dan binary assets.
- Backup membutuhkan prosedur lintas-komponen.
- Operasional lebih kompleks daripada satu database.

Decision: Accepted as the proposed architecture.

5. Architecture Decision

MovieAIProducer menggunakan Hybrid Storage Architecture.

Komponen utamanya:

1. Relational Database: authoritative source of truth untuk transactional data.
2. Object Storage / Filesystem: penyimpanan binary assets.
3. Job Queue: koordinasi pekerjaan asynchronous.
4. Cache: optimasi performa yang bersifat optional.
5. Audit and Event Records: histori perubahan dan aktivitas sistem.

Database menjadi sumber kebenaran untuk metadata, relasi, status, dan referensi asset.

Object storage menjadi sumber kebenaran untuk isi binary file.

Cache dan queue tidak boleh menggantikan authoritative database state.

6. Logical Storage Architecture

                 MovieAIProducer
                        |
                        v
                 Application Layer
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
     Relational     Asset Storage   Job Queue
      Database       Adapter         Adapter
          |             |             |
          v             v             v
    Business Data    Media Files   Async Tasks
    MPB Revisions    Generated     Retry State
    Workflow State   Assets        Job Dispatch
    Audit Records    Source Files
          |
          v
    Optional Cache
    Derived Data
    Temporary Results

Storage access harus melalui application ports dan infrastructure adapters.

Domain layer tidak boleh bergantung langsung pada vendor database atau object storage.

7. Relational Database Strategy

7.1 Database Responsibilities

Relational database menyimpan:

- Users and identities.
- Projects and memberships.
- Roles and permissions.
- Creative briefs.
- Story and screenplay structures.
- Character and environment records.
- Production specifications.
- MPB revisions.
- MPB snapshots.
- Scene and shot definitions.
- Workflow stages and tasks.
- Job metadata.
- Asset metadata.
- Provider and model registries.
- Approval records.
- Audit records.
- Billing and usage metadata, jika fitur billing diaktifkan.

7.2 Database Selection

Database final harus dipilih setelah repository discovery dan evaluasi kebutuhan operasional.

Proposed baseline:

Development / MVP

- SQLite dapat digunakan untuk local development atau MVP berskala kecil jika concurrency dan deployment model mendukungnya.
- Database access harus melalui abstraction yang tidak mengunci domain ke SQLite.

Production

- PostgreSQL menjadi kandidat utama untuk production.
- Validasi kebutuhan concurrency, connection management, deployment, backup, dan operational support sebelum keputusan final.

SQLite bukan otomatis pilihan production untuk seluruh deployment. PostgreSQL juga tidak boleh ditetapkan tanpa mempertimbangkan kondisi repository dan infrastruktur aktual.

7.3 Data Access Rules

- Domain layer tidak mengakses database secara langsung.
- Gunakan repository interfaces.
- Infrastructure layer mengimplementasikan repository.
- Transaction boundaries ditetapkan pada application use cases.
- Query kompleks harus memiliki ownership yang jelas.
- Hindari query database tersebar di seluruh application modules.

7.4 Schema Design

Gunakan relational modeling untuk entitas dan hubungan utama.

Ketentuan:

- Primary key harus stabil.
- Foreign key digunakan untuk menjaga referential integrity.
- Unique constraints digunakan untuk identitas yang tidak boleh duplikat.
- Check constraints digunakan untuk invariant yang dapat dijaga database.
- Index dibuat berdasarkan pola query yang terukur.
- Timestamp menggunakan format konsisten dan timezone-aware.
- Soft delete hanya digunakan jika ada kebutuhan bisnis dan kebijakan retention yang jelas.

Jangan menjadikan satu kolom JSON raksasa sebagai pengganti seluruh relational model.

JSON dapat digunakan untuk:

- Provider-specific metadata.
- Model capability details.
- Flexible generation settings.
- Versioned configuration.
- Optional attributes yang memang bervariasi.

Setiap JSON structure yang penting harus memiliki schema version, validation, dan compatibility policy.

8. MPB Revision Storage

MPB merupakan domain penting sehingga revision history tidak boleh bergantung pada overwrite data biasa.

8.1 Revision Model

Setiap perubahan terhadap approved production specification harus menghasilkan revision yang dapat ditelusuri.

Revision minimal mencatat:

- Entity ID.
- Project ID.
- Revision number.
- Previous revision reference.
- Change summary.
- Changed fields atau structured change records.
- Actor.
- Timestamp.
- Approval status.
- Approval identity.
- Related change request.

8.2 Immutable Snapshots

Production snapshot harus merepresentasikan kondisi MPB pada titik waktu tertentu.

Snapshot minimal menyimpan:

- Project reference.
- MPB revision references.
- Scene and shot revision references.
- Relevant production configuration.
- Provider/model configuration references.
- Snapshot creation timestamp.
- Snapshot version.
- Integrity hash atau equivalent verification metadata.

Snapshot yang telah digunakan untuk production job tidak boleh berubah secara diam-diam.

8.3 Historical Access

Sistem harus mendukung:

- Membaca revision lama.
- Membandingkan dua revision.
- Melihat perubahan yang disetujui.
- Mengetahui siapa yang membuat perubahan.
- Mengidentifikasi production job yang menggunakan revision tertentu.
- Memulihkan specification melalui controlled revision process.

Restoration tidak boleh menghapus histori perubahan yang sudah terjadi.

9. Asset Storage Strategy

9.1 Asset Categories

Asset storage menangani:

- Reference images.
- Character images.
- Environment images.
- Props and wardrobe references.
- Storyboards.
- Animatics.
- Generated images.
- Generated videos.
- Voice recordings.
- Music and sound effects.
- Rendered sequences.
- Final production exports.

9.2 Storage Responsibility

Database menyimpan metadata asset.

Object storage atau filesystem menyimpan binary content.

Contoh metadata:

- Asset ID.
- Project ID.
- Asset type.
- Original filename.
- Storage key.
- MIME type.
- File size.
- Checksum.
- Version.
- Created by.
- Created timestamp.
- Lifecycle status.
- Access classification.
- Related scene/shot.
- Generation job reference.

9.3 Storage Abstraction

Implementasikan interface konseptual:

class AssetStoragePort:
    def put(self, source, metadata):
        ...

    def get(self, storage_key):
        ...

    def delete(self, storage_key):
        ...

    def exists(self, storage_key):
        ...

    def get_metadata(self, storage_key):
        ...

Kode tersebut merupakan interface ilustratif, bukan implementasi final.

Application layer tidak boleh bergantung langsung pada filesystem path atau SDK vendor.

9.4 Storage Key

Gunakan generated storage key, bukan filename user sebagai lokasi penyimpanan utama.

Contoh struktur konseptual:

projects/{project_id}/assets/{asset_id}/versions/{version}

Ketentuan:

- Storage key harus unik.
- Nama file asli tetap disimpan sebagai metadata.
- Jangan mempercayai path dari user.
- Cegah path traversal.
- Hindari kebocoran informasi internal melalui URL.
- Gunakan checksum untuk integrity verification.

9.5 Access Control

Default asset access adalah private.

Akses diberikan melalui:

- Application authorization.
- Ownership and project membership checks.
- Short-lived signed URLs jika diperlukan.
- Explicit permission untuk download dan sharing.

Jangan membuat bucket atau direktori media menjadi public secara default.

9.6 Asset Lifecycle

Asset lifecycle minimal:

UPLOADING
    |
    v
PROCESSING
    |
    v
AVAILABLE
    |
    v
ARCHIVED
    |
    v
DELETION_PENDING
    |
    v
DELETED

Status harus dikelola melalui valid state transitions.

Asset yang gagal diunggah atau diproses harus memiliki cleanup policy.

Penghapusan metadata tidak boleh menyebabkan binary file tertinggal tanpa kontrol, dan penghapusan binary tidak boleh dilakukan sebelum referential checks selesai.

10. Transactional Integrity

Database transaction harus menjaga konsistensi perubahan data dalam satu database boundary.

Namun, database transaction tidak otomatis mencakup object storage atau external provider.

Untuk operasi lintas-komponen gunakan pola yang sesuai:

- Staged upload.
- Temporary storage key.
- Database state transition.
- Finalization step.
- Compensating action.
- Reconciliation job.

Contoh upload:

1. Buat asset record dengan status UPLOADING.
2. Upload binary ke temporary storage.
3. Validasi ukuran, MIME type, dan checksum.
4. Finalisasi storage object.
5. Update database menjadi AVAILABLE.
6. Jika gagal, jalankan cleanup atau reconciliation.

Operasi harus idempotent jika memungkinkan.

Jangan mengasumsikan database dan object storage dapat di-commit dalam satu atomic transaction.

11. Job Queue and Asynchronous Processing

Job queue digunakan untuk pekerjaan yang tidak cocok dijalankan secara synchronous, misalnya:

- AI image generation.
- AI video generation.
- Audio generation.
- Media analysis.
- Rendering.
- Transcoding.
- Asset validation.
- Thumbnail generation.
- Long-running production tasks.

Ketentuan:

- Job metadata tetap disimpan dalam database.
- Queue berfungsi untuk dispatch dan koordinasi.
- Queue bukan authoritative source of truth.
- Job harus memiliki unique ID.
- Job harus memiliki status dan retry policy.
- Worker harus mendukung idempotency.
- Failed job harus dapat diperiksa.
- Recovery tidak boleh bergantung pada pesan queue yang masih tersedia.

Gunakan transactional outbox atau pola reliability yang setara ketika perubahan database harus diikuti publikasi event secara konsisten.

Teknologi queue final diputuskan melalui ADR-0007.

12. Cache Strategy

Cache hanya digunakan jika terdapat kebutuhan performa yang terbukti.

Contoh kandidat:

- Frequently accessed project metadata.
- Provider capability registry.
- Derived dashboard statistics.
- Expensive read-only computations.
- Temporary session data jika sesuai.

Ketentuan:

- Cache bukan source of truth.
- Data harus dapat dibangun kembali.
- Cache invalidation harus dirancang.
- TTL digunakan jika sesuai.
- Hindari menyimpan data sensitif tanpa alasan dan kontrol yang jelas.
- Sistem harus tetap benar ketika cache kosong atau tidak tersedia.

Redis atau teknologi lain tidak diwajibkan pada MVP sebelum ada kebutuhan terukur.

13. Data Ownership and Module Boundaries

Setiap domain module memiliki ownership terhadap data yang dikelolanya.

Contoh:

Module| Data ownership
Identity| Users, identities, roles
Projects| Projects, memberships
Story| Story structures, screenplay
Characters| Character records and revisions
Production Design| Environments, props, wardrobe
MPB| Revision coordination and snapshots
Workflow| Stages, tasks, dependencies
AI Orchestration| Requests, routing, executions
Providers| Provider and model registry
Assets| Asset metadata and lifecycle
Quality Control| QC results and approvals
Audit| Audit records

Module lain tidak boleh mengubah data milik module tersebut secara langsung.

Cross-module interaction harus melalui application interfaces atau domain events yang sesuai.

Pada modular monolith, database dapat digunakan bersama secara fisik, tetapi ownership logis dan aturan akses tetap dipisahkan.

14. Data Classification and Security

Data minimal diklasifikasikan menjadi:

1. Public.
2. Internal.
3. Confidential.
4. Restricted.

Contoh:

- Public: informasi yang memang disetujui untuk publikasi.
- Internal: konfigurasi operasional umum.
- Confidential: project data, screenplay, dan media produksi.
- Restricted: credentials, tokens, secrets, dan informasi keamanan.

Security requirements:

- TLS untuk komunikasi jaringan.
- Encryption at rest sesuai kemampuan deployment.
- Secrets tidak disimpan dalam source code.
- Access control berdasarkan project membership dan role.
- Validasi upload dan file type.
- Batas ukuran upload.
- Malware scanning jika diperlukan berdasarkan risiko.
- Audit untuk akses dan perubahan penting.
- Isolasi data lintas project.
- Signed URL memiliki expiry.
- Backup harus dilindungi dengan access control dan encryption.

Data pribadi dan data produksi harus mengikuti retention dan deletion policy yang ditetapkan.

15. Indexing and Performance

Index ditentukan dari pola akses aktual.

Prioritas awal:

- Project ID.
- User ID.
- Asset ID.
- Scene ID.
- Shot ID.
- Workflow status.
- Job status.
- Revision number.
- Created timestamp.
- Foreign key columns yang sering digunakan.

Performance guidelines:

- Pagination untuk daftar besar.
- Hindari N+1 queries.
- Gunakan streaming untuk file besar.
- Hindari memuat seluruh media ke memory.
- Batasi concurrent database connections.
- Gunakan connection pooling jika database mendukung dan diperlukan.
- Monitor query latency.
- Evaluasi index melalui query plans.

Jangan menambahkan index tanpa mempertimbangkan biaya write dan storage.

16. Backup and Recovery

Backup mencakup:

- Relational database.
- Object storage.
- Configuration.
- Required encryption keys and recovery material.
- Audit history.
- Workflow recovery metadata.

Ketentuan:

- Database backup harus konsisten.
- Asset backup harus dapat dicocokkan dengan metadata.
- Backup memiliki retention policy.
- Backup harus dilindungi dari akses tidak sah.
- Recovery Point Objective (RPO) dan Recovery Time Objective (RTO) ditentukan berdasarkan kebutuhan bisnis.
- Restore test wajib dilakukan.
- Backup yang belum pernah diuji restore tidak boleh dianggap terverifikasi.

Detail operasional mengikuti "BACKUP_RECOVERY.md".

17. Local Development and Environment Strategy

Local development harus dapat dijalankan tanpa bergantung pada production infrastructure.

Gunakan konfigurasi environment untuk memilih adapter:

- Local filesystem adapter.
- Development database.
- Optional local queue.
- Optional local cache.

Production dapat menggunakan:

- PostgreSQL.
- S3-compatible object storage atau provider yang memenuhi kebutuhan.
- Dedicated queue infrastructure.
- Optional distributed cache.

Perbedaan environment tidak boleh mengubah domain logic.

Jangan meng-hardcode credential, storage endpoint, atau path environment tertentu ke dalam application code.

18. Migration Strategy

Database schema changes harus dikelola melalui migration system.

Ketentuan:

- Setiap migration memiliki identitas unik.
- Migration dapat ditelusuri dalam version control.
- Migration diuji pada environment terpisah.
- Destructive migration membutuhkan review khusus.
- Data migration harus memiliki validasi.
- Rollback atau forward-fix strategy harus ditentukan.
- Application version dan schema compatibility harus diperhatikan.

Hindari perubahan schema manual di production yang tidak tercatat.

19. Consequences

Positive Consequences

- Pemisahan metadata dan binary assets.
- Relational integrity lebih kuat.
- MPB revision lebih mudah ditelusuri.
- Production snapshot lebih dapat direproduksi.
- Media storage dapat berkembang independen.
- Provider storage dapat diganti melalui adapter.
- Backup dan recovery lebih terstruktur.

Negative Consequences

- Sistem memiliki beberapa komponen storage.
- Operasi lintas-komponen membutuhkan reconciliation.
- Backup dan restore lebih kompleks.
- Monitoring storage membutuhkan perhatian khusus.
- Developer harus memahami ownership dan lifecycle setiap data.

Accepted Trade-offs

Kompleksitas tambahan diterima karena sistem membutuhkan integritas production data dan kemampuan mengelola media dalam skala besar.

20. Implementation Sequence

Implementasi dilakukan bertahap.

Phase 1: Repository Discovery

- Periksa database yang sudah digunakan.
- Identifikasi ORM atau data access layer.
- Audit schema dan migration.
- Audit asset storage yang sudah ada.
- Periksa file upload dan download.
- Identifikasi queue dan cache yang sudah digunakan.
- Dokumentasikan deployment constraints.

Tidak boleh mengganti teknologi sebelum audit selesai.

Phase 2: Storage Contracts

- Definisikan repository interfaces.
- Definisikan AssetStoragePort.
- Definisikan transaction boundaries.
- Definisikan storage metadata contract.
- Definisikan error handling.
- Definisikan configuration abstraction.

Phase 3: Database Foundation

- Tetapkan schema conventions.
- Implementasikan migration workflow.
- Terapkan relational constraints.
- Implementasikan repository adapters.
- Buat database integrity tests.

Phase 4: Asset Storage

- Implementasikan storage adapter.
- Implementasikan upload lifecycle.
- Implementasikan checksum validation.
- Implementasikan private access.
- Implementasikan asset metadata.
- Implementasikan cleanup dan reconciliation.

Phase 5: MPB and Workflow Persistence

- Implementasikan revision records.
- Implementasikan immutable snapshots.
- Implementasikan workflow persistence.
- Implementasikan audit history.
- Implementasikan concurrency controls.

Phase 6: Reliability

- Implementasikan backup.
- Implementasikan restore procedure.
- Implementasikan storage health checks.
- Implementasikan recovery tests.
- Implementasikan reconciliation monitoring.

Phase 7: Optimization

- Evaluasi query performance.
- Evaluasi asset delivery.
- Evaluasi cache.
- Evaluasi queue infrastructure.
- Evaluasi storage cost.

21. Risks and Mitigations

Risk| Mitigation
Database bloat| Keep binary assets outside relational database
Orphaned files| Reconciliation and lifecycle management
Missing assets| Checksums and verified backup
Inconsistent metadata| Transactional state transitions
Lost queue messages| Persistent job records and recovery
Unauthorized asset access| Private storage and authorization
Broken migrations| Automated migration tests
Vendor lock-in| Storage ports and adapters
MPB history loss| Immutable revision and snapshot records
Concurrent updates| Optimistic locking or equivalent controls
Excessive infrastructure| Start with minimum viable components

22. Validation Checklist

ADR-0006 dapat dianggap terimplementasi setelah:

- [ ] Database technology dipilih berdasarkan repository audit.
- [ ] Database access memiliki abstraction yang jelas.
- [ ] Module data ownership terdokumentasi.
- [ ] Schema migration berjalan konsisten.
- [ ] Referential integrity diuji.
- [ ] MPB revisions dapat ditelusuri.
- [ ] Production snapshots immutable.
- [ ] Asset metadata terpisah dari binary content.
- [ ] Upload lifecycle diuji.
- [ ] Asset access private by default.
- [ ] Checksum verification berjalan.
- [ ] Orphan asset reconciliation tersedia.
- [ ] Queue tidak menjadi source of truth.
- [ ] Cache dapat dihilangkan tanpa merusak correctness.
- [ ] Backup database dan assets berjalan.
- [ ] Restore test berhasil.
- [ ] Project isolation diuji.
- [ ] Migration compatibility diuji.
- [ ] Monitoring storage tersedia.

23. Review Conditions

ADR ini harus ditinjau ulang apabila:

- Database concurrency melampaui kapasitas deployment saat ini.
- Asset storage membutuhkan distributed architecture.
- Volume video dan rendering meningkat signifikan.
- Multi-region storage menjadi kebutuhan.
- Retention atau compliance requirements berubah.
- Recovery objectives membutuhkan arsitektur baru.
- Database technology harus diganti.

24. Related Documents

- "ARCHITECTURE.md"
- "DATA_MODEL.md"
- "AI_PIPELINE.md"
- "API_SPEC.md"
- "SECURITY.md"
- "ERROR_HANDLING.md"
- "TEST_STRATEGY.md"
- "DEPLOYMENT.md"
- "OBSERVABILITY.md"
- "BACKUP_RECOVERY.md"
- "CONTRIBUTING.md"
- "DECISIONS/ADR/README.md"

Related ADRs:

- ADR-0001: Architecture Style.
- ADR-0002: Application Structure.
- ADR-0003: Provider Adapter System.
- ADR-0004: Master Production Bible.
- ADR-0005: Production Workflow Engine.
- ADR-0007: Async Job Processing.

---

Final Decision: Proposed.

MovieAIProducer adopts a Hybrid Storage Architecture: relational database for authoritative transactional data, object storage for binary media, persistent job records with asynchronous queue processing, and optional cache for measured performance needs.

Technology selection and production implementation remain subject to repository discovery and infrastructure validation.
