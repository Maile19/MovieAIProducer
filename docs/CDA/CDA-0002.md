# CDA-0002: CANONICAL GLOSSARY & DOMAIN OWNERSHIP MATRIX

- Project: MovieAIProducer
- Document ID: CDA-0002
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Category: Architecture Governance
- Related Documents: ARCHITECTURE.md, DATA_MODEL.md, API_SPEC.md, AI_PIPELINE.md, AGENTS.md
- Related ADRs: ADR-0001 through ADR-0015

---

PART A: CANONICAL GLOSSARY

1. Governance Rules

1. Setiap konsep utama memiliki satu istilah kanonis.
2. Istilah kanonis digunakan dalam dokumentasi, API, database, event, dan source code.
3. Sinonim tidak boleh digunakan sebagai nama entity yang berbeda.
4. Istilah domain tidak boleh berubah hanya karena perbedaan UI wording.
5. Perubahan istilah harus melalui dokumentasi dan migration review.
6. Istilah yang belum memiliki definisi harus dianggap provisional.
7. Istilah teknis harus dibedakan dari istilah bisnis.

2. Product and Production Terminology

Canonical Term| Definition| Avoid Confusion With
Project| Kontainer utama seluruh pekerjaan film| Production
Production| Aktivitas dan proses pembuatan film| Project
Production Brief| Ringkasan kebutuhan produksi| Creative Brief
Creative Brief| Arahan kreatif awal proyek| Production Brief
Master Production Bible (MPB)| Sistem referensi otoritatif untuk spesifikasi produksi yang disetujui| Single document
Production Stage| Tahap besar dalam workflow produksi| Workflow Task
Workflow| Struktur dan status proses kerja| Job
Scene| Unit naratif dalam cerita| Shot
Shot| Unit pengambilan gambar atau visualisasi produksi| Scene
Sequence| Kelompok scene yang memiliki hubungan naratif atau editorial| Workflow
Storyboard| Representasi visual rencana scene atau shot| Final video
Animatic| Representasi temporal storyboard dengan timing dan media pendukung| Final edit
Previsualization (Previs)| Simulasi visual awal sebelum produksi final| Final render
Asset| Media atau resource digital yang dikelola sistem| File
Production Artifact| Hasil atau dokumen yang dihasilkan dalam proses produksi| Asset
Final Delivery| Paket hasil produksi yang disiapkan untuk distribusi| Internal preview

3. MPB Terminology

Canonical Term| Definition
Bible| Kumpulan spesifikasi terstruktur untuk suatu domain produksi
Bible Entry| Satu record spesifikasi di dalam Bible
Canonical Reference| Referensi stabil terhadap entity atau revision
Revision| Versi perubahan suatu entity
Snapshot| Rekaman immutable dari konteks produksi pada waktu tertentu
Approval| Keputusan resmi atas suatu perubahan atau hasil
Change Request| Permintaan perubahan terhadap spesifikasi yang telah ada
Impact Analysis| Analisis dampak perubahan terhadap resource terkait
Approved Specification| Spesifikasi yang telah melewati approval policy
Production Context| Kumpulan informasi yang dibutuhkan untuk menjalankan produksi tertentu

MPB bukan satu tabel besar dan bukan sekadar dokumen Markdown.

MPB mengoordinasikan referensi dan revision dari domain yang tetap memiliki data masing-masing.

4. Character Terminology

Canonical Term| Definition
Character| Identitas tokoh dalam cerita
Character DNA| Identitas visual, karakteristik, dan atribut dasar tokoh
Character State| Kondisi tokoh pada titik tertentu dalam cerita
Character Profile| Informasi terstruktur mengenai tokoh
Character Reference Asset| Media referensi visual tokoh
Character Performance| Ekspresi, gesture, dan perilaku tokoh dalam adegan
Figurant / Extra| Individu latar yang bukan karakter utama
Crowd| Kelompok figurant yang dikelola sebagai kesatuan visual atau produksi

Character identity tidak boleh dicampur dengan temporary character state.

5. Cinematography Terminology

Canonical Term| Definition
Camera Configuration| Konfigurasi kamera yang digunakan dalam perencanaan shot
Camera Movement| Pergerakan kamera
Lens Specification| Spesifikasi atau intent lensa
Composition| Penataan elemen visual dalam frame
Framing| Batas dan cakupan visual dalam frame
Lighting Setup| Rencana pengaturan cahaya
Atmosphere| Kondisi visual dan atmosferik lingkungan
Shot Direction| Arahan pengambilan atau pembentukan shot

Camera intent bukan jaminan bahwa model AI akan mereproduksi karakteristik optik secara presisi.

6. AI and Provider Terminology

Canonical Term| Definition
AI Provider| Organisasi atau layanan penyedia AI
Provider Adapter| Implementasi penghubung antara kontrak internal dan API provider
Model| Model AI tertentu dari provider
Model Version| Versi model yang digunakan
Capability| Kemampuan yang didukung model
Capability Evidence| Bukti yang mendukung status kemampuan
Prompt IR| Representasi prompt terstruktur yang independen dari provider
Prompt Compilation| Proses mengubah Prompt IR menjadi format yang didukung target model
Generation Request| Permintaan pembuatan konten
Generation Job| Pekerjaan asynchronous untuk menjalankan generation request
Generation Result| Hasil dari proses generation
Provider Operation| Operasi yang sedang atau telah diproses oleh provider
Model Router| Komponen pemilihan model berdasarkan capability dan policy

Provider dan model adalah entitas berbeda.

Nama provider tidak cukup untuk menyimpulkan kemampuan seluruh modelnya.

7. Workflow and Job Terminology

Canonical Term| Definition
Workflow Definition| Template atau definisi proses
Workflow Instance| Pelaksanaan workflow untuk resource tertentu
Workflow Task| Unit pekerjaan di dalam workflow
Task Dependency| Hubungan prasyarat antar-task
Job| Unit eksekusi asynchronous
Job Attempt| Satu percobaan menjalankan job
Job Lease| Kepemilikan sementara job oleh worker
Worker| Proses yang menjalankan job
Queue| Mekanisme distribusi job
Retry| Percobaan ulang yang diizinkan
Cancellation Request| Permintaan pembatalan
Cancellation Confirmation| Konfirmasi bahwa operasi berhasil dibatalkan
Reconciliation| Proses menyelaraskan kondisi antar-sistem

Workflow Task tidak sama dengan Job.

Workflow Task merepresentasikan kebutuhan pekerjaan produksi. Job merepresentasikan eksekusi teknis.

8. Continuity and QC Terminology

Canonical Term| Definition
Continuity| Konsistensi antarbagian produksi
Continuity State| Kondisi yang harus dipertahankan
Continuity Rule| Aturan pemeriksaan konsistensi
Continuity Finding| Temuan dari pemeriksaan continuity
QC Run| Satu proses evaluasi kualitas
QC Finding| Temuan kualitas
QC Severity| Tingkat dampak masalah
QC Confidence| Tingkat keyakinan terhadap hasil pemeriksaan
QC Score| Nilai berdasarkan rubric
QC Blocker| Temuan yang mencegah approval
QC Approval| Keputusan resmi atas hasil evaluasi

Severity, confidence, dan score adalah tiga konsep terpisah.

9. Asset Terminology

Canonical Term| Definition
Asset ID| Identitas stabil asset
Asset Version| Versi binary atau metadata asset
Asset Metadata| Informasi terstruktur mengenai asset
Storage Key| Lokasi internal object dalam storage
Checksum| Nilai verifikasi integritas binary
Asset Provenance| Riwayat asal-usul dan proses asset
Asset Relationship| Hubungan asset dengan entity lain
Preview| Representasi ringan untuk pemeriksaan
Derivative| File turunan dari asset asli
Original Asset| Binary sumber yang dipertahankan sesuai retention policy

Asset identity tidak boleh bergantung pada filename atau URL sementara.

10. Identity and Security Terminology

Canonical Term| Definition
User| Identitas manusia
Agent Identity| Identitas AI agent
Service Identity| Identitas aplikasi atau service
Provider Identity| Identitas eksternal provider
Tenant| Batas isolasi organisasi atau customer
Project Scope| Batas akses dalam suatu project
Role| Kumpulan permission
Permission| Hak melakukan operasi tertentu
Policy| Aturan evaluasi akses
Audit Event| Rekaman tindakan yang penting secara governance
Telemetry| Data operasional untuk observability

Agent Identity dan User Identity tidak boleh dipertukarkan.

---

PART B: DOMAIN OWNERSHIP MATRIX

11. Ownership Principles

Setiap domain harus memiliki:

- Satu authoritative owner.
- Defined data ownership.
- Defined business rules.
- Defined application operations.
- Defined API boundary.
- Defined event responsibility.
- Defined test ownership.

Satu domain dapat menggunakan layanan domain lain, tetapi tidak boleh mengambil alih kepemilikan datanya.

12. Canonical Domain Registry

Domain ID| Domain| Primary Responsibility
D-001| Identity & Access| User identity, authentication, authorization
D-002| Project Management| Project lifecycle and ownership
D-003| Creative Development| Creative brief and creative decisions
D-004| Story Architecture| Story, sequence, screenplay, narrative
D-005| Character Management| Character identity and state
D-006| Production Design| Environment, props, wardrobe, makeup
D-007| MPB Management| Approved production specifications and snapshots
D-008| Cinematography| Camera, lens, framing, composition
D-009| Lighting| Lighting and atmosphere specifications
D-010| Performance & Audio| Acting, dialogue, voice, sound intent
D-011| Motion Engineering| Movement, action, physics and temporal constraints
D-012| Storyboard & Previs| Visual planning and previsualization
D-013| Scene & Shot Management| Scene and shot production structure
D-014| Workflow Engine| Production workflow state and dependencies
D-015| Job Processing| Asynchronous execution lifecycle
D-016| AI Orchestration| AI request coordination
D-017| Provider Integration| Provider adapters and capability registry
D-018| Prompt Compilation| Prompt IR and provider-specific compilation
D-019| Asset Management| Asset identity, version, access and provenance
D-020| Continuity Engine| Production consistency validation
D-021| Quality Control| Quality evaluation and approval
D-022| Editorial| Editing plans and editorial relationships
D-023| Delivery| Final package and delivery lifecycle
D-024| Notifications| User-facing notification delivery
D-025| Observability| Operational telemetry
D-026| Audit Governance| Authoritative audit records
D-027| Administration| Platform configuration and operational administration

Domain boundaries are logical boundaries. They do not automatically imply separate microservices.

13. Domain Data Ownership

Domain| Owns| Does Not Own
Identity & Access| Users, identities, roles, policies| Project content
Project Management| Project metadata and lifecycle| Story content
Creative Development| Creative brief and decisions| Approved MPB snapshots
Story Architecture| Story and screenplay entities| Character asset binaries
Character Management| Character identity and state| Asset storage
Production Design| Environment, props, wardrobe specs| Storage binary
MPB Management| Snapshot records, references, approval coordination| All underlying domain records
Cinematography| Camera and composition specs| Scene ownership
Lighting| Lighting specifications| Media binaries
Performance & Audio| Performance and audio specifications| Voice provider credentials
Motion Engineering| Motion and physics specifications| Video generation execution
Storyboard & Previs| Storyboard and previs records| Final delivery package
Scene & Shot Management| Scene and shot records| Workflow engine state
Workflow Engine| Workflow instances, task state, dependencies| Technical job execution
Job Processing| Jobs, attempts, leases, execution results| Production approval
AI Orchestration| Generation request coordination| Provider implementation details
Provider Integration| Provider/model/capability registry| Project creative decisions
Prompt Compilation| Prompt IR and compiled prompt versions| MPB authority
Asset Management| Asset metadata, versions, relationships| Binary storage infrastructure
Continuity Engine| Continuity rules, runs, findings| MPB approved specifications
Quality Control| QC runs, findings, scores, approvals| Original production assets
Editorial| Editorial structure and edit decisions| Asset binary storage
Delivery| Delivery packages and delivery status| Source production specifications
Notifications| Notification records and delivery status| Business decisions
Observability| Logs, metrics and traces| Authoritative audit history
Audit Governance| Audit records and integrity controls| General telemetry
Administration| Platform-level configuration| Unrestricted access to private user data

14. Domain Interaction Rules

14.1 Direct Ownership

Only the owning domain may perform authoritative writes to its data.

Other domains must use:

- Defined application interfaces.
- Internal domain contracts.
- Approved commands.
- Published events where appropriate.

14.2 Cross-Domain Read

Cross-domain reads should use explicit query interfaces or approved read models.

Avoid arbitrary access to another domain's internal tables.

14.3 Cross-Domain Write

A domain must not directly mutate another domain's records.

Instead, request an operation from the owning domain.

14.4 Shared Database

A modular monolith may initially use one relational database.

However:

- Table ownership remains explicit.
- Domain repositories own writes.
- Cross-domain queries are controlled.
- Schema changes require review.
- Database sharing does not imply domain ownership sharing.

14.5 Cross-Domain Transactions

Use local transactions within the owning domain where possible.

For multi-domain processes, prefer explicit workflow coordination, reliable events, and reconciliation rather than assuming a single distributed transaction.

---

PART C: CRITICAL OWNERSHIP BOUNDARIES

15. MPB vs Domain Modules

MPB is the authority for approved production context.

It does not become the owner of all story, character, environment, or cinematography tables.

Domain modules own their entities and revisions.

MPB maintains canonical references, approval coordination, and immutable snapshots.

16. Workflow Engine vs Job Processing

Workflow Engine:

- Production stage.
- Workflow instance.
- Workflow task.
- Task dependencies.
- Approval gates.
- Rework transitions.

Job Processing:

- Job execution.
- Worker assignment.
- Attempt lifecycle.
- Lease.
- Retry.
- Provider execution tracking.
- Technical result handling.

A workflow task may create or reference jobs.

A job cannot independently approve a workflow task.

17. AI Orchestration vs Provider Integration

AI Orchestration:

- Coordinates generation requests.
- Resolves production context.
- Selects eligible capability.
- Coordinates prompt compilation.
- Initiates jobs.

Provider Integration:

- Implements provider adapters.
- Maintains provider/model registry.
- Tracks verified capabilities.
- Normalizes provider responses.
- Handles provider-specific errors.

Neither domain owns approved creative decisions.

18. Prompt Compilation vs AI Orchestration

Prompt Compilation:

- Prompt IR.
- Constraint validation.
- Context compilation.
- Provider-specific translation.
- Compiled prompt provenance.

AI Orchestration:

- Determines when compilation is required.
- Supplies request context.
- Coordinates execution.
- Records generation lifecycle.

Prompt compilation does not execute provider jobs.

19. Continuity vs QC

Continuity:

- Character and environment state.
- Timeline consistency.
- Spatial consistency.
- Prop and wardrobe consistency.
- Continuity rules and findings.

QC:

- Visual quality.
- Directorial quality.
- Technical quality.
- Production quality.
- Rubric and approval decisions.

QC may consume continuity findings but does not own continuity rules.

20. Asset Management vs Object Storage

Asset Management owns:

- Asset identity.
- Metadata.
- Versioning.
- Permissions.
- Provenance.
- Relationships.
- Lifecycle.

Storage infrastructure owns binary persistence and retrieval.

Storage provider implementation must remain behind an abstraction.

21. Observability vs Audit Governance

Observability records operational behavior.

Audit Governance records authoritative business and security actions.

Telemetry retention and sampling must never silently remove required audit records.

---

PART D: CROSS-DOMAIN CONTRACT RULES

22. Contract Requirements

Every domain interaction should define:

- Contract identifier.
- Producer domain.
- Consumer domain.
- Operation or event.
- Input schema.
- Output schema.
- Authorization requirements.
- Idempotency requirements.
- Error behavior.
- Versioning policy.
- Observability fields.

23. Canonical Identifier Conventions

Proposed identifiers:

Entity| Identifier
Project| project_id
User| user_id
Character| character_id
Scene| scene_id
Shot| shot_id
Asset| asset_id
Workflow| workflow_id
Workflow Task| workflow_task_id
Job| job_id
Generation Request| generation_request_id
QC Run| qc_run_id
Continuity Run| continuity_run_id
MPB Snapshot| mpb_snapshot_id
Revision| revision_id
Approval| approval_id
Provider| provider_id
Model| model_id

Identifiers should be stable, unique, and opaque where appropriate.

Do not use sequential identifiers as public authorization secrets.

24. Event Ownership

An event is published by the domain that owns the underlying state transition.

Examples:

- "project.created" → Project Management.
- "character.updated" → Character Management.
- "mpb.snapshot.created" → MPB Management.
- "workflow.task.started" → Workflow Engine.
- "job.started" → Job Processing.
- "generation.completed" → AI Orchestration or its designated result owner, according to the final contract.
- "asset.registered" → Asset Management.
- "continuity.run.completed" → Continuity Engine.
- "qc.run.completed" → Quality Control.
- "delivery.completed" → Delivery.

Event names and payload schemas require a separate canonical event registry before implementation.

25. Authorization Boundaries

Every domain must enforce authorization at its application boundary.

Rules:

- Project membership must be checked.
- Tenant isolation must be enforced.
- Agent permissions must be scoped.
- Service identities must have least privilege.
- Sensitive operations require explicit policies.
- Human approval must be attributable to an authorized identity.
- Frontend visibility does not constitute authorization.

26. Revision and Provenance Rules

Every production output that depends on approved specifications should record its source context.

Minimum provenance where applicable:

- project_id.
- scene_id.
- shot_id.
- mpb_snapshot_id.
- source revision identifiers.
- prompt version.
- compiler version.
- provider_id.
- model_id.
- model version.
- generation job ID.
- source asset IDs.
- QC run ID.

Not every entity needs every field. Provenance must be relevant to the operation.

---

PART E: IMPLEMENTATION GOVERNANCE

27. Domain Module Readiness

A domain module is implementation-ready when it has:

- Defined ownership.
- Defined entities.
- Defined invariants.
- Defined application operations.
- Defined authorization rules.
- Defined contracts.
- Defined errors.
- Defined events where needed.
- Defined tests.
- Defined acceptance criteria.

28. Change Management

A change to canonical terminology or ownership requires:

1. Identify affected documents.
2. Identify affected domains.
3. Review API and event contracts.
4. Review database migration impact.
5. Review frontend terminology.
6. Review AI agent instructions.
7. Update glossary.
8. Update ADR if architecture changes.
9. Update tests.
10. Record the decision.

29. Audit Acceptance Checklist

- [ ] Canonical glossary established.
- [ ] Domain registry established.
- [ ] Each domain has one authoritative owner.
- [ ] MPB ownership boundary is explicit.
- [ ] Workflow and job boundaries are explicit.
- [ ] AI orchestration and provider boundaries are explicit.
- [ ] Prompt compilation boundary is explicit.
- [ ] Continuity and QC boundaries are explicit.
- [ ] Asset and storage boundaries are explicit.
- [ ] Observability and audit boundaries are explicit.
- [ ] Identifier conventions are defined.
- [ ] Cross-domain contracts are required.
- [ ] Authorization boundaries are defined.
- [ ] Provenance requirements are defined.

30. Final Governance Principle

Every important business concept must have one canonical definition.

Every authoritative record must have one owning domain.

Every cross-domain operation must use an explicit contract.

Every AI-generated production result must retain its provenance.

No domain may silently override another domain's authority.

---

Status: Proposed.

This document establishes the terminology and logical ownership baseline. It does not authorize creation of all proposed modules, tables, services, or API endpoints before repository discovery and implementation planning.
