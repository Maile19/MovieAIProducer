# CDA-0004: Canonical Event & Integration Contract Registry

- Project: MovieAIProducer
- Document ID: CDA-0004
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Classification: Architecture Governance
- Depends on: CDA-0002, CDA-0003, ADR-0001, ADR-0005, ADR-0007, ADR-0013

---

1. Purpose

Dokumen ini menetapkan standar resmi untuk komunikasi dan integrasi antardomain MovieAIProducer.

Tujuannya:

1. Menentukan kepemilikan setiap event.
2. Menetapkan format event yang konsisten.
3. Memisahkan domain event, command, query, audit record, dan telemetry.
4. Menjamin integritas komunikasi antarmodul.
5. Mencegah duplikasi event dan pemrosesan berulang.
6. Mendukung pemulihan ketika proses integrasi gagal.
7. Memastikan setiap perubahan dapat dilacak ke sumbernya.
8. Menyiapkan arsitektur untuk pengembangan skala besar tanpa mewajibkan microservices sejak awal.

2. Architectural Decision

MovieAIProducer menggunakan Domain-Owned Event Contract Architecture.

Prinsip utama:

- Setiap domain bertanggung jawab atas event yang diterbitkannya.
- Event merepresentasikan fakta bahwa sesuatu telah terjadi.
- Command meminta domain melakukan suatu tindakan.
- Query meminta informasi tanpa mengubah state.
- Event bukan pengganti database atau authoritative domain state.
- Konsumen tidak boleh mengambil alih kepemilikan state domain lain.
- Setiap kontrak harus memiliki versi dan dokumentasi.
- Pengiriman event harus dapat dipulihkan dan diproses secara idempotent.

Pada MVP, komunikasi dapat menggunakan kontrak internal dalam satu aplikasi modular monolith. Message broker bukan persyaratan awal.

3. Communication Model

Lima jenis komunikasi harus dibedakan.

3.1 Domain Event

Fakta yang sudah terjadi.

Contoh:

- "project.created"
- "mpb.revision.approved"
- "workflow.started"
- "job.failed"
- "asset.registered"
- "qc.completed"

Event tidak meminta penerima melakukan sesuatu secara langsung. Konsumen memutuskan apakah fakta tersebut relevan dengan tanggung jawabnya.

3.2 Command

Instruksi untuk melakukan tindakan.

Contoh:

- "CreateProject"
- "ApproveMPBRevision"
- "StartWorkflow"
- "SubmitGenerationRequest"
- "RegisterAsset"
- "StartQC"

Command harus memiliki target domain yang jelas dan melewati pemeriksaan otorisasi.

3.3 Query

Permintaan data tanpa perubahan state.

Contoh:

- "GetProject"
- "GetMPBSnapshot"
- "GetWorkflowStatus"
- "GetAssetMetadata"
- "GetQCReport"

Query harus membaca data dari pemilik domain atau melalui read model yang dikelola secara eksplisit.

3.4 Audit Record

Catatan aktivitas yang diperlukan untuk akuntabilitas dan investigasi.

Contoh:

- Pengguna menyetujui revisi MPB.
- AI agent mengajukan perubahan.
- Administrator mengubah konfigurasi.
- Pengguna mengunduh aset privat.

Audit record bukan pengganti domain event.

3.5 Telemetry

Data untuk observability dan operasional.

Contoh:

- Durasi generation.
- Jumlah retry.
- Provider latency.
- Worker utilization.
- Token usage.
- Queue depth.

Telemetry tidak boleh menjadi sumber kebenaran untuk status transaksi.

4. Event Naming Convention

Gunakan format:

"<domain>.<aggregate>.<past-tense-action>"

Contoh:

- "project.project.created"
- "mpb.revision.approved"
- "workflow.execution.started"
- "job.execution.failed"
- "asset.asset.registered"
- "qc.run.completed"

Ketentuan:

1. Gunakan huruf kecil.
2. Gunakan titik sebagai pemisah.
3. Gunakan nama yang menjelaskan fakta yang sudah terjadi.
4. Hindari nama generik seperti "updated", jika konteksnya tidak jelas.
5. Jangan memasukkan nama pengguna atau data sensitif dalam nama event.
6. Jangan menggunakan nama event untuk menyatakan perintah.
7. Jangan mengubah arti event lama ketika melakukan upgrade versi.

Nama di atas adalah contoh kontrak konseptual. Nama final wajib didaftarkan dalam registry.

5. Canonical Event Envelope

Setiap event harus mengikuti struktur konseptual berikut:

```json
{
  "event_id": "evt_unique_id",
  "event_type": "mpb.revision.approved",
  "event_version": 1,
  "occurred_at": "2026-11-19T10:00:00Z",
  "published_at": "2026-11-19T10:00:02Z",
  "producer": {
    "domain": "mpb_management",
    "module_version": "1.0.0"
  },
  "tenant_id": "tenant_id",
  "project_id": "project_id",
  "aggregate": {
    "type": "mpb_revision",
    "id": "revision_id",
    "version": 4
  },
  "actor": {
    "type": "human",
    "id": "actor_id"
  },
  "correlation_id": "correlation_id",
  "causation_id": "causation_id",
  "trace_id": "trace_id",
  "schema_ref": "events/mpb/revision-approved/v1",
  "data": {
    "mpb_id": "mpb_id",
    "revision_id": "revision_id",
    "approval_id": "approval_id"
  },
  "metadata": {
    "environment": "production",
    "source": "mpb_management"
  }
}
```

Ketentuan:

- "event_id" harus unik.
- "event_type" harus terdaftar.
- "event_version" wajib.
- "occurred_at" adalah waktu fakta terjadi.
- "published_at" adalah waktu publikasi jika tersedia.
- "producer" mengidentifikasi domain penerbit.
- "tenant_id" dan "project_id" digunakan jika relevan.
- "aggregate.version" mendukung deteksi perubahan dan urutan.
- "correlation_id" menghubungkan satu rangkaian proses.
- "causation_id" mengidentifikasi penyebab langsung.
- "trace_id" menghubungkan telemetry.
- "data" hanya berisi informasi yang diperlukan konsumen.
- "metadata" tidak boleh menjadi tempat menyimpan data bisnis tanpa skema.

Field opsional hanya boleh dihilangkan jika memang tidak relevan. Format final harus disesuaikan dengan model data dan kebijakan privasi.

6. Domain Event Ownership Registry

Setiap domain hanya menerbitkan event atas fakta yang berada dalam kewenangannya.

Domain| Contoh event| Pemilik
D-001 Identity & Access| "identity.user.authenticated"| Identity
D-002 Project Management| "project.project.created"| Project
D-003 Creative Development| "creative.brief.approved"| Creative
D-004 Story Architecture| "story.structure.approved"| Story
D-005 Character Management| "character.profile.approved"| Character
D-006 Production Design| "production_design.environment.approved"| Production Design
D-007 MPB Management| "mpb.revision.approved"| MPB
D-008 Cinematography| "cinematography.plan.approved"| Cinematography
D-009 Lighting| "lighting.plan.approved"| Lighting
D-010 Performance & Audio| "performance.take.approved"| Performance
D-011 Motion Engineering| "motion.profile.validated"| Motion
D-012 Storyboard & Previs| "previs.sequence.completed"| Previs
D-013 Scene & Shot Management| "scene.shot.created"| Scene & Shot
D-014 Workflow Engine| "workflow.execution.started"| Workflow
D-015 Job Processing| "job.execution.failed"| Job
D-016 AI Orchestration| "ai.generation.requested"| AI Orchestration
D-017 Provider Integration| "provider.operation.completed"| Provider
D-018 Prompt Compilation| "prompt.compilation.completed"| Prompt
D-019 Asset Management| "asset.asset.registered"| Asset
D-020 Continuity Engine| "continuity.validation.completed"| Continuity
D-021 Quality Control| "qc.run.completed"| QC
D-022 Editorial| "editorial.timeline.updated"| Editorial
D-023 Delivery| "delivery.package.published"| Delivery
D-024 Notifications| "notification.delivery.failed"| Notifications
D-025 Observability| "observability.alert.triggered"| Observability
D-026 Audit Governance| "audit.record.created"| Audit
D-027 Administration| "administration.configuration.changed"| Administration

Registry harus menyimpan nama event, pemilik, versi, skema, klasifikasi data, konsumen, dan status kontrak.

7. Canonical Event Catalog

Daftar berikut merupakan baseline awal. Setiap event harus memiliki definisi payload dan kondisi penerbitan sebelum dinyatakan aktif.

7.1 Project

- "project.project.created"
- "project.project.updated"
- "project.project.archived"
- "project.project.cancelled"

7.2 Creative Development

- "creative.brief.created"
- "creative.brief.updated"
- "creative.brief.approved"
- "creative.brief.rejected"

7.3 Story Architecture

- "story.structure.created"
- "story.structure.revised"
- "story.structure.approved"
- "story.screenplay.completed"

7.4 Character Management

- "character.profile.created"
- "character.profile.updated"
- "character.profile.approved"
- "character.state.registered"

7.5 Production Design

- "production_design.environment.created"
- "production_design.environment.approved"
- "production_design.prop.registered"
- "production_design.wardrobe.approved"

7.6 MPB Management

- "mpb.revision.created"
- "mpb.revision.submitted"
- "mpb.revision.approved"
- "mpb.revision.rejected"
- "mpb.change_request.created"
- "mpb.change_request.approved"
- "mpb.change_request.rejected"
- "mpb.snapshot.created"

7.7 Workflow Engine

- "workflow.execution.created"
- "workflow.execution.started"
- "workflow.execution.paused"
- "workflow.execution.resumed"
- "workflow.execution.blocked"
- "workflow.execution.completed"
- "workflow.execution.failed"
- "workflow.execution.cancelled"
- "workflow.task.started"
- "workflow.task.completed"
- "workflow.task.failed"
- "workflow.task.approval_requested"

7.8 Job Processing

- "job.execution.queued"
- "job.execution.started"
- "job.execution.retry_scheduled"
- "job.execution.completed"
- "job.execution.failed"
- "job.execution.cancellation_requested"
- "job.execution.cancelled"
- "job.execution.dead_lettered"

7.9 AI Orchestration

- "ai.generation.requested"
- "ai.generation.started"
- "ai.generation.completed"
- "ai.generation.failed"
- "ai.generation.cancelled"
- "ai.generation.result_received"

7.10 Provider Integration

- "provider.operation.submitted"
- "provider.operation.started"
- "provider.operation.completed"
- "provider.operation.failed"
- "provider.operation.cancellation_requested"
- "provider.operation.cancelled"
- "provider.webhook.received"

7.11 Prompt Compilation

- "prompt.compilation.requested"
- "prompt.compilation.completed"
- "prompt.compilation.failed"
- "prompt.validation.completed"
- "prompt.approval.requested"

7.12 Asset Management

- "asset.upload.requested"
- "asset.asset.uploaded"
- "asset.asset.registered"
- "asset.asset.validated"
- "asset.asset.approved"
- "asset.asset.rejected"
- "asset.asset.archived"
- "asset.asset.deleted"

7.13 Continuity Engine

- "continuity.validation.requested"
- "continuity.validation.completed"
- "continuity.violation.detected"
- "continuity.violation.resolved"
- "continuity.override.approved"

7.14 Quality Control

- "qc.run.requested"
- "qc.run.started"
- "qc.run.completed"
- "qc.run.failed"
- "qc.finding.detected"
- "qc.approval.requested"
- "qc.approval.granted"
- "qc.approval.rejected"

7.15 Editorial

- "editorial.timeline.created"
- "editorial.timeline.updated"
- "editorial.sequence.approved"
- "editorial.export.completed"

7.16 Delivery

- "delivery.package.created"
- "delivery.package.validated"
- "delivery.package.approved"
- "delivery.package.published"
- "delivery.package.failed"

7.17 Notifications

- "notification.delivery.requested"
- "notification.delivery.completed"
- "notification.delivery.failed"

7.18 Identity, Audit & Administration

- "identity.user.authenticated"
- "identity.session.revoked"
- "audit.record.created"
- "administration.configuration.changed"
- "administration.policy.updated"

Event katalog ini bukan instruksi untuk menerbitkan semua event pada MVP. Implementasi mengikuti kebutuhan vertical slice dan kontrak yang telah diverifikasi.

8. Critical Integration Contracts

8.1 Workflow ↔ Job Processing

Workflow Engine memiliki state workflow dan workflow task.

Job Processing memiliki state eksekusi teknis.

Alur:

1. Workflow Task meminta eksekusi.
2. Job Processing membuat job.
3. Job diproses oleh worker.
4. Job menghasilkan event hasil eksekusi.
5. Workflow menerima hasil dan mengevaluasi transisi task.
6. Workflow memperbarui state berdasarkan kebijakan domain.

Ketentuan:

- Job selesai tidak otomatis berarti task disetujui.
- Job gagal tidak otomatis berarti seluruh workflow gagal.
- Retry teknis tidak boleh diam-diam menggandakan workflow task.
- Cancellation request bukan bukti bahwa provider atau worker sudah berhenti.

8.2 AI Orchestration ↔ Provider Integration

AI Orchestration bertanggung jawab atas generation request.

Provider Integration bertanggung jawab atas operasi eksternal.

Alur:

1. AI Orchestration membuat generation request.
2. Provider capability diverifikasi.
3. Provider adapter mengirim permintaan.
4. Provider operation ID disimpan.
5. Hasil atau status diterima melalui polling atau webhook jika tersedia.
6. Provider menerbitkan hasil operasi.
7. AI Orchestration mengevaluasi dan memproses hasil.

Provider tidak boleh mengubah MPB secara langsung.

8.3 Generation Result ↔ Asset Management

Generation result tidak otomatis menjadi approved asset.

Alur:

1. Hasil generation diterima.
2. Binary media disimpan melalui storage abstraction.
3. Asset Management memvalidasi file.
4. Metadata, provenance, checksum, dan relasi disimpan.
5. Asset masuk lifecycle yang sesuai.
6. QC atau human review dilakukan sesuai kebijakan.
7. Asset hanya digunakan dalam produksi jika status dan izin penggunaannya memenuhi persyaratan.

8.4 Continuity ↔ QC

Continuity Engine menyediakan hasil validasi continuity.

QC Engine mengonsumsi hasil tersebut sebagai salah satu sumber pemeriksaan.

Ketentuan:

- Continuity Engine tetap menjadi pemilik hasil validasi continuity.
- QC Engine tetap menjadi pemilik QC run dan QC findings.
- QC tidak boleh menulis ulang state continuity.
- Hasil AI harus memiliki confidence dan evidence yang sesuai.
- Finding yang belum terverifikasi manusia tidak boleh diperlakukan sebagai kepastian mutlak.

8.5 QC ↔ Approval ↔ Delivery

QC menyelesaikan pemeriksaan dan menerbitkan hasil.

Approval policy menentukan siapa yang boleh menyetujui.

Delivery hanya mempublikasikan paket yang memenuhi seluruh persyaratan.

Ketentuan:

- QC pass bukan otomatis approval.
- Approval harus dapat diaudit.
- Delivery tidak boleh mengabaikan blocker.
- Perubahan pada aset yang sudah disetujui dapat memerlukan QC dan approval ulang.

9. Reliability & Delivery Guarantees

9.1 Transactional Outbox

Untuk perubahan state yang memerlukan publikasi event yang andal, gunakan transactional outbox atau mekanisme ekuivalen.

Dalam satu transaksi database:

1. Domain memperbarui state.
2. Domain menambahkan outbox record.
3. Transaksi disimpan secara atomik.
4. Publisher mengambil outbox record.
5. Event dikirim kepada konsumen.
6. Outbox record ditandai berhasil dipublikasikan.

Jangan mengandalkan dua operasi database dan pengiriman jaringan terpisah tanpa mekanisme rekonsiliasi.

9.2 Delivery Semantics

Baseline adalah at-least-once delivery.

Konsekuensinya:

- Event dapat diterima lebih dari satu kali.
- Konsumen wajib idempotent.
- Konsumen wajib mendeteksi event duplikat.
- Exactly-once tidak boleh diasumsikan.

9.3 Idempotency

Gunakan "event_id" atau consumer-specific idempotency key.

Konsumen menyimpan bukti pemrosesan yang berhasil.

Event duplikat tidak boleh mengulang side effect yang sudah berhasil.

9.4 Ordering

Urutan event dijaga berdasarkan aggregate ketika dibutuhkan.

Gunakan aggregate ID dan aggregate version untuk mendeteksi:

- Event tertinggal.
- Event duplikat.
- Event tidak berurutan.
- Perubahan yang terlewat.

Jangan menjanjikan global ordering untuk seluruh event sistem.

9.5 Retry & Dead Letter

Kegagalan sementara dapat di-retry menggunakan kebijakan terkontrol dengan exponential backoff dan jitter.

Kegagalan permanen atau batas retry yang tercapai harus diarahkan ke dead-letter handling.

Dead-letter record harus menyimpan:

- Event ID.
- Consumer.
- Error classification.
- Attempt count.
- Timestamp.
- Correlation ID.
- Recovery status.

Reprocessing harus melalui prosedur terkontrol dan idempotent.

9.6 Replay & Reconciliation

Replay harus mempertimbangkan:

- Consumer version.
- Event schema version.
- Efek samping eksternal.
- Duplikasi.
- State saat ini.
- Retention policy.

Event replay tidak boleh secara otomatis mengulangi pembayaran, publikasi, atau tindakan eksternal tanpa idempotency dan pemeriksaan otorisasi.

10. Schema Evolution & Versioning

Setiap event contract memiliki versi sendiri.

Aturan:

1. Perubahan yang kompatibel dapat mempertahankan versi mayor kontrak.
2. Perubahan yang memutus kompatibilitas memerlukan versi baru.
3. Field baru sebaiknya opsional sampai seluruh konsumen siap.
4. Field lama tidak boleh dihapus tanpa migration plan.
5. Perubahan semantik dianggap breaking change meskipun struktur JSON tetap sama.
6. Consumer harus menolak atau menangani versi yang tidak didukung dengan aman.
7. Kontrak lama memiliki kebijakan deprecation dan masa transisi.

Event schema harus dapat divalidasi otomatis melalui contract test.

11. Event Contract Registry

Setiap event harus terdaftar dengan metadata minimum:

Field| Deskripsi
Event type| Nama event unik
Version| Versi kontrak
Owner domain| Pemilik fakta
Schema reference| Lokasi skema
Description| Tujuan event
Producer| Modul penerbit
Consumers| Modul penerima
Data classification| Klasifikasi data
Delivery policy| Aturan pengiriman
Idempotency policy| Aturan duplikasi
Ordering policy| Aturan urutan
Retention| Kebijakan penyimpanan
Status| Draft, proposed, active, deprecated

Status kontrak:

- Draft
- Proposed
- Accepted
- Active
- Deprecated
- Retired

Perubahan kontrak harus melalui review pemilik domain dan pengujian kompatibilitas.

12. Security & Data Governance

Event harus mengikuti prinsip least data necessary.

Persyaratan:

- Tenant scope harus diverifikasi.
- Project scope harus diverifikasi jika relevan.
- Konsumen hanya boleh menerima event yang diizinkan.
- Jangan memasukkan API key, password, token, atau secret.
- Jangan memasukkan binary media ke dalam event envelope.
- Gunakan asset reference dan akses terkontrol.
- Minimalkan PII.
- Terapkan retention sesuai klasifikasi data.
- Event sensitif harus memiliki aturan akses dan audit.
- Jangan menganggap event ID sebagai otorisasi akses.

Event yang membawa data privat harus dilindungi sesuai security policy dan authorization model.

13. Correlation, Causation & Provenance

Setiap rangkaian proses yang saling terkait harus dapat ditelusuri.

Gunakan:

- "correlation_id" untuk rangkaian proses.
- "causation_id" untuk pemicu langsung.
- "trace_id" untuk observability.
- "aggregate.version" untuk versi perubahan.
- "actor" untuk identitas pelaku jika tersedia.
- "project_id" untuk ruang lingkup proyek.
- Referensi MPB snapshot untuk proses generation yang bergantung pada spesifikasi produksi.

Untuk AI generation, provenance perlu menghubungkan:

- Generation request.
- MPB snapshot.
- Prompt IR.
- Compiled prompt.
- Compiler version.
- Provider.
- Model.
- Provider operation ID.
- Asset hasil.
- QC run dan approval jika ada.

Informasi tersebut tidak harus seluruhnya berada dalam satu event. Gunakan referensi antarentitas.

14. Modular Monolith Implementation

Pada tahap awal:

- Domain menerbitkan event melalui internal event contract.
- Event handler terdaftar secara eksplisit.
- Database transaction menjaga konsistensi state dan outbox.
- Konsumen memproses event secara idempotent.
- Tidak diperlukan message broker hanya untuk memenuhi pola event-driven.
- Jangan membuat komunikasi antarmodul melalui import database model milik domain lain.

Struktur logis yang diusulkan:

application/
  contracts/
    events/
    commands/
    queries/

infrastructure/
  messaging/
    event_publisher/
    event_dispatcher/
    outbox/
    inbox/
    retry/
    dead_letter/

domains/
  project/
  mpb/
  workflow/
  jobs/
  ai_orchestration/
  providers/
  prompts/
  assets/
  continuity/
  quality_control/
  delivery/

Struktur ini adalah usulan logis, bukan instruksi membuat folder sebelum repository diaudit.

Ketika kebutuhan skala meningkat, internal event transport dapat diganti atau diperluas dengan message broker tanpa mengubah domain contract secara sembarangan.

Teknologi broker belum diputuskan.

15. Failure Handling

Failure| Penanganan
Publisher crash| Outbox diproses ulang
Consumer crash| Delivery ulang
Duplicate event| Idempotency check
Out-of-order event| Aggregate version check
Invalid schema| Reject dan quarantine
Temporary database failure| Controlled retry
Permanent consumer failure| Dead-letter
External side effect duplicated| External idempotency key
Tenant mismatch| Reject dan security audit
Unsupported event version| Safe rejection atau compatibility handler
Lost notification| Reconciliation dan retry

Kegagalan komunikasi tidak boleh mengakibatkan state domain berubah tanpa kontrol.

16. Testing Requirements

Unit Tests

- Event envelope validation.
- Event naming validation.
- Schema validation.
- Event version validation.
- Idempotency handler.
- Aggregate version handling.
- Authorization checks.

Integration Tests

- Domain transaction dan outbox.
- Outbox publisher.
- Consumer delivery.
- Workflow dan Job integration.
- AI Orchestration dan Provider integration.
- Provider result dan Asset registration.
- Continuity dan QC integration.
- QC, approval dan Delivery integration.

Contract Tests

- Producer contract.
- Consumer compatibility.
- Backward compatibility.
- Breaking change detection.
- Unknown event version handling.

Failure Tests

- Publisher crash.
- Consumer crash.
- Duplicate delivery.
- Event delay.
- Out-of-order delivery.
- Database outage.
- Dead-letter recovery.
- Replay safety.

Security Tests

- Tenant isolation.
- Project isolation.
- Unauthorized consumer.
- Secret leakage.
- PII leakage.
- Unauthorized replay.

17. MVP Implementation Scope

MVP tidak perlu mengaktifkan seluruh katalog.

Prioritas vertical slice:

1. Project creation.
2. MPB revision creation and approval.
3. Workflow execution.
4. Job dispatch and completion.
5. AI generation request.
6. Provider operation result.
7. Asset registration.
8. Continuity validation.
9. QC completion.
10. Human approval.
11. Delivery readiness.

Implementasikan hanya event yang benar-benar diperlukan untuk menyelesaikan satu alur produksi end-to-end.

18. Implementation Sequence

Phase 1: Contract Foundation

- Tetapkan event envelope.
- Tetapkan naming convention.
- Buat event registry.
- Buat schema validation.
- Tetapkan domain ownership.

Phase 2: Reliability Foundation

- Implementasikan outbox.
- Implementasikan consumer idempotency.
- Implementasikan retry.
- Implementasikan dead-letter handling.
- Implementasikan correlation IDs.

Phase 3: Vertical Integration

- Workflow ↔ Job.
- AI ↔ Provider.
- Generation ↔ Asset.
- Continuity ↔ QC.
- QC ↔ Approval ↔ Delivery.

Phase 4: Governance & Scale

- Contract compatibility checks.
- Replay controls.
- Event reconciliation.
- Monitoring.
- Broker evaluation berdasarkan metrik aktual.

19. Acceptance Criteria

CDA-0004 dapat dinyatakan siap diimplementasikan apabila:

- [ ] Setiap event memiliki pemilik domain.
- [ ] Event naming convention konsisten.
- [ ] Event envelope tervalidasi.
- [ ] Command, query, event, audit, dan telemetry terpisah.
- [ ] Event contract memiliki versioning.
- [ ] State domain tetap authoritative.
- [ ] Outbox atau mekanisme ekuivalen tersedia untuk transaksi kritis.
- [ ] Konsumen idempotent.
- [ ] Ordering ditangani sesuai kebutuhan aggregate.
- [ ] Retry dan dead-letter tersedia.
- [ ] Replay memiliki kontrol keamanan.
- [ ] Correlation dan provenance dapat ditelusuri.
- [ ] Tenant isolation diuji.
- [ ] Integrasi kritis memiliki contract test.
- [ ] Tidak ada asumsi bahwa message broker atau microservices wajib pada MVP.

20. Risks

ID| Risiko| Mitigasi
CDA4-R01| Event ownership tumpang tindih| Domain ownership registry
CDA4-R02| Duplicate processing| Idempotency
CDA4-R03| Event kehilangan sinkronisasi| Outbox dan reconciliation
CDA4-R04| Schema breaking changes| Versioning dan contract tests
CDA4-R05| Cross-tenant data leakage| Tenant authorization
CDA4-R06| Replay mengulang side effect| Controlled replay
CDA4-R07| Event menjadi sumber state palsu| Domain tetap authoritative
CDA4-R08| Event terlalu banyak| MVP vertical slice
CDA4-R09| Audit tercampur telemetry| Pisahkan governance
CDA4-R10| Premature broker adoption| Modular monolith terlebih dahulu

21. Cross-Document Dependencies

Dokumen ini harus direkonsiliasi dengan:

- ADR-0001: Architecture Style.
- ADR-0005: Production Workflow Engine.
- ADR-0007: Async Job Processing.
- ADR-0013: Observability Stack.
- ADR-0014: Deployment Strategy.
- DATA_MODEL.md.
- API_SPEC.md.
- ERROR_HANDLING.md.
- OBSERVABILITY.md.
- SECURITY.md.
- CDA-0002: Domain Ownership.
- CDA-0003: Lifecycle & State Transition Matrix.

Jika ditemukan konflik, jangan mengubah kontrak secara sepihak. Catat konflik, identifikasi pemilik domain, dan lakukan keputusan arsitektur yang diperlukan.

22. Governance & Final Status

Status: PROPOSED

Dokumen ini merupakan baseline kontrak integrasi yang diusulkan.

Dokumen belum dianggap sebagai implementasi aktual dan belum membuktikan bahwa event registry, outbox, inbox, atau consumer telah tersedia di repository.

Sebelum status menjadi Accepted:

1. Audit repository.
2. Periksa model data aktual.
3. Cocokkan lifecycle.
4. Cocokkan API dan error contracts.
5. Verifikasi kebutuhan transaksi.
6. Review keamanan.
7. Buat contract tests.
8. Selesaikan konflik antardokumen.

Final Decision Principle:

Domain owns its state. Events communicate facts. Commands request actions. Queries retrieve information. Audit records preserve accountability. Telemetry measures system behavior.

Kelima hal tersebut tidak boleh dicampuradukkan.

---

End of CDA-0004
