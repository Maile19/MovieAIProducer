# ADR-0007: Async Job Processing

Project: MovieAIProducer
ADR ID: ADR-0007
Title: Async Job Processing
Version: 1.0
Status: Proposed
Date: 2026-11-19
Decision Owners: Product Architect / Technical Lead

---

1. Context

MovieAIProducer menjalankan pekerjaan yang membutuhkan waktu pemrosesan panjang dan tidak selalu selesai dalam satu HTTP request.

Contohnya:

- AI screenplay generation.
- Character image generation.
- Environment generation.
- Storyboard generation.
- AI video generation.
- Voice and audio generation.
- Media analysis.
- Video rendering.
- Audio mixing.
- Transcoding.
- Continuity validation.
- Quality control.
- Final export.

Sebagian provider AI menggunakan asynchronous API yang mengembalikan operation ID atau job ID. Sebagian lainnya memberikan hasil secara langsung.

Sistem harus mengakomodasi kedua pola tersebut melalui satu workflow yang konsisten.

2. Problem Statement

Tanpa job processing architecture yang terstruktur, sistem berisiko mengalami:

- HTTP request timeout.
- Duplikasi generation.
- Hilangnya status pekerjaan.
- Retry yang tidak terkendali.
- Resource exhaustion.
- Job macet tanpa recovery.
- Hasil generation tidak terhubung dengan MPB snapshot.
- Ketidaksesuaian status antara aplikasi dan provider.
- Kegagalan proses ketika worker restart.
- Sulitnya membatalkan atau menjadwalkan ulang pekerjaan.

Diperlukan sistem asynchronous processing yang durable, observable, idempotent, dan dapat dipulihkan.

3. Decision Drivers

1. Reliability.
2. Job durability.
3. Idempotency.
4. Failure recovery.
5. Concurrency control.
6. Provider compatibility.
7. Resource management.
8. Cost control.
9. Observability.
10. Operational simplicity.

4. Options Considered

Option A: Synchronous Processing

Semua pekerjaan diproses langsung dalam HTTP request.

Advantages:

- Implementasi sederhana.
- Tidak memerlukan worker terpisah.

Disadvantages:

- Tidak cocok untuk long-running jobs.
- Risiko timeout.
- Sulit mengelola retry dan recovery.
- Tidak mendukung orchestration kompleks dengan baik.

Decision: Rejected as the primary processing architecture.

Option B: In-Memory Background Tasks

Pekerjaan berjalan di background dalam proses aplikasi yang sama.

Advantages:

- Mudah dibuat untuk prototipe.
- Infrastruktur tambahan minimal.

Disadvantages:

- Job dapat hilang ketika proses restart.
- Scaling terbatas.
- Recovery sulit.
- Tidak ideal untuk production workload.

Decision: Rejected for durable production processing.

Option C: Persistent Job Records + Asynchronous Queue + Workers

Job disimpan secara durable, didispatch melalui queue, dan dijalankan oleh worker.

Advantages:

- Mendukung long-running jobs.
- Memiliki recovery mechanism.
- Dapat mengatur concurrency.
- Mendukung retry dan monitoring.
- Worker dapat diskalakan secara independen.

Disadvantages:

- Membutuhkan koordinasi beberapa komponen.
- Perlu idempotency dan reconciliation.
- Infrastruktur lebih kompleks.

Decision: Accepted.

5. Architecture Decision

MovieAIProducer menggunakan Persistent Asynchronous Job Processing Architecture.

Komponen utama:

1. Job Registry: menyimpan authoritative job state.
2. Job Dispatcher: mengirim pekerjaan ke queue.
3. Message Queue: mendistribusikan pekerjaan.
4. Worker Pool: mengeksekusi pekerjaan.
5. Execution Adapter: berinteraksi dengan provider atau internal services.
6. Result Processor: memvalidasi dan menyimpan hasil.
7. Retry Manager: mengelola retry.
8. Recovery Manager: memulihkan pekerjaan yang tertinggal.
9. Job Monitor: menyediakan status dan observability.

Database menjadi sumber kebenaran status pekerjaan.

Queue hanya menjadi mekanisme dispatch dan koordinasi.

6. Logical Architecture

              Application API
                    |
                    v
             Job Application
                    |
                    v
               Job Registry
                    |
                    v
             Job Dispatcher
                    |
                    v
              Message Queue
                    |
          +---------+---------+
          |         |         |
          v         v         v
       Worker 1  Worker 2  Worker N
          |         |         |
          v         v         v
      Execution Adapters / Provider APIs
                    |
                    v
              Result Processor
                    |
          +---------+---------+
          |                   |
          v                   v
       Database           Asset Storage
          |
          v
      Job Monitor

Setiap worker hanya boleh mengakses domain dan resource melalui kontrak yang ditentukan.

7. Job Domain Model

7.1 Job Entity

Setiap job minimal memiliki:

- Job ID.
- Project ID.
- Workflow ID, jika terkait workflow.
- Scene ID, jika terkait scene.
- Shot ID, jika terkait shot.
- Job type.
- Job status.
- Priority.
- Payload reference.
- Input reference.
- Output reference.
- MPB snapshot reference.
- Attempt count.
- Maximum attempts.
- Scheduled timestamp.
- Started timestamp.
- Completed timestamp.
- Error reference.
- Idempotency key.
- Created by.
- Created timestamp.
- Updated timestamp.

Payload sensitif atau berukuran besar tidak boleh otomatis disimpan sebagai pesan queue.

7.2 Job Types

Contoh kategori:

Category| Example
CREATIVE| Story and screenplay generation
IMAGE| Character and environment generation
VIDEO| Scene and shot generation
AUDIO| Voice, music, sound effects
ANALYSIS| Media and script analysis
RENDER| Composition and rendering
TRANSCODE| Video and audio conversion
CONTINUITY| Continuity validation
QC| Quality control
EXPORT| Final production export

Job type harus memiliki handler yang terdaftar secara eksplisit.

Jangan menggunakan dynamic execution dari arbitrary job payload.

8. Job State Machine

Status minimum:

- QUEUED
- DISPATCHED
- RUNNING
- WAITING_PROVIDER
- RETRY_WAIT
- SUCCEEDED
- FAILED
- CANCEL_REQUESTED
- CANCELLED
- TIMED_OUT
- BLOCKED

Logical transitions:

QUEUED
   |
   v
DISPATCHED
   |
   v
RUNNING
   |
   +------> WAITING_PROVIDER
   |              |
   |              v
   |            RUNNING
   |
   +------> SUCCEEDED
   |
   +------> RETRY_WAIT
   |              |
   |              v
   |            QUEUED
   |
   +------> FAILED
   |
   +------> CANCEL_REQUESTED
                  |
                  v
              CANCELLED

BLOCKED digunakan ketika dependency belum terpenuhi.

TIMED_OUT digunakan ketika execution melewati batas waktu yang ditentukan.

Semua state transitions harus divalidasi oleh domain rules.

Terminal states tidak boleh berubah secara sembarangan.

Reprocessing harus menghasilkan execution attempt atau job baru dengan hubungan historis yang jelas.

9. Idempotency Strategy

Job processing tidak boleh mengasumsikan bahwa sebuah pesan hanya akan diterima satu kali.

Queue delivery dapat bersifat at-least-once.

Karena itu:

- Setiap job memiliki stable ID.
- Setiap logical operation memiliki idempotency key.
- Worker memeriksa status dan claim job secara atomik.
- Duplicate messages tidak boleh menghasilkan duplicate side effects.
- Result persistence harus idempotent.
- Asset creation harus memiliki deduplication strategy.
- Provider idempotency key digunakan jika didukung provider.

Jika provider tidak mendukung idempotency, sistem harus mengakui adanya risiko duplicate generation dan menggunakan reconciliation sebelum mengulangi request yang statusnya tidak diketahui.

Exactly-once execution tidak boleh dijanjikan hanya karena menggunakan queue.

10. Worker Architecture

10.1 Worker Responsibilities

Worker bertugas:

1. Mengambil job.
2. Memvalidasi payload.
3. Memeriksa dependency.
4. Melakukan claim job.
5. Memastikan execution masih valid.
6. Memuat MPB snapshot yang relevan.
7. Menjalankan handler.
8. Melaporkan progress.
9. Menyimpan hasil.
10. Mengubah status.
11. Menghasilkan event.
12. Melakukan cleanup sesuai kebijakan.

10.2 Worker Isolation

Worker harus memiliki batas resource:

- CPU.
- Memory.
- Execution time.
- Network concurrency.
- Provider concurrency.
- Disk usage.
- Temporary storage.

Job rendering dan video processing dapat memerlukan worker pool terpisah dari pekerjaan ringan seperti metadata validation.

10.3 Worker Types

Logical worker groups:

- General Worker.
- AI Generation Worker.
- Media Processing Worker.
- Rendering Worker.
- Validation Worker.
- Export Worker.

Tidak semua worker group harus menjadi proses terpisah pada MVP.

Pemisahan dilakukan berdasarkan workload dan kebutuhan resource.

11. Priority and Scheduling

Sistem mendukung priority:

- CRITICAL
- HIGH
- NORMAL
- LOW
- BACKGROUND

Priority tidak boleh menyebabkan starvation permanen terhadap pekerjaan berprioritas rendah.

Scheduling dapat mempertimbangkan:

- Project priority.
- User entitlement.
- Provider capacity.
- Resource availability.
- Dependency readiness.
- Deadline.
- Cost limits.
- Fairness policy.

Prioritas tidak boleh melewati authorization, safety checks, atau production approval gates.

12. Concurrency Control

Concurrency harus dibatasi pada beberapa tingkat:

1. Global worker capacity.
2. Per-job-type capacity.
3. Per-provider capacity.
4. Per-model capacity.
5. Per-project capacity.
6. Per-user capacity.
7. Per-resource capacity.

Provider rate limits harus dihormati.

Sistem harus mendukung configurable concurrency limits.

Optimistic locking, atomic claims, atau mekanisme setara digunakan untuk mencegah dua worker mengeksekusi job yang sama secara bersamaan.

13. Retry Strategy

Retry hanya dilakukan untuk error yang dianggap recoverable.

Retryable Errors

Contoh:

- Temporary network failure.
- Provider rate limit.
- Temporary provider outage.
- Transient storage failure.
- Temporary service unavailability.

Non-Retryable Errors

Contoh:

- Invalid request.
- Unauthorized access.
- Unsupported capability.
- Invalid production specification.
- Policy rejection yang tidak dapat diperbaiki secara otomatis.
- Permanently missing input.

Retry Policy

- Configurable maximum attempts.
- Exponential backoff.
- Randomized jitter.
- Retry-after header support.
- Maximum delay.
- Error classification.
- Retry history.

Contoh konseptual:

Attempt 1: immediate
Attempt 2: 5 seconds
Attempt 3: 15 seconds
Attempt 4: 45 seconds
Attempt 5: 120 seconds

Angka tersebut hanya contoh, bukan konfigurasi final.

Jangan mengulang request berbiaya tinggi secara otomatis tanpa memeriksa apakah provider sudah menerima atau menyelesaikan request sebelumnya.

14. Timeout and Heartbeat

Setiap job harus memiliki timeout policy yang sesuai dengan jenis pekerjaan.

Ketentuan:

- Job execution timeout.
- Provider request timeout.
- Worker heartbeat.
- Visibility timeout atau lease.
- Stale job detection.
- Graceful shutdown.

Heartbeat digunakan untuk membedakan worker yang masih aktif dari worker yang berhenti merespons.

Lease expiration tidak boleh otomatis menghasilkan duplicate external generation tanpa reconciliation.

15. Provider Async Execution

Provider dapat menggunakan beberapa pola:

1. Synchronous response.
2. Asynchronous operation ID.
3. Polling.
4. Webhook callback.
5. Long-running streaming execution.

Provider adapter bertanggung jawab menerjemahkan pola tersebut ke normalized job lifecycle.

Untuk asynchronous provider:

- Simpan provider operation ID.
- Simpan provider request reference.
- Simpan submission timestamp.
- Simpan last polling timestamp.
- Simpan provider status.
- Simpan provider result reference.
- Simpan callback verification metadata jika webhook digunakan.

Webhook harus diverifikasi dan diproses secara idempotent.

Jangan mempercayai callback tanpa autentikasi atau signature verification yang sesuai.

16. Cancellation Strategy

Cancellation merupakan permintaan, bukan jaminan bahwa pekerjaan eksternal langsung berhenti.

Proses:

1. User meminta cancellation.
2. Job berubah menjadi CANCEL_REQUESTED.
3. Worker atau provider adapter menerima cancellation signal.
4. Jika provider mendukung cancellation, kirim permintaan.
5. Tunggu konfirmasi.
6. Update menjadi CANCELLED setelah cancellation terverifikasi.

Jika provider tidak mendukung cancellation:

- Tandai execution sebagai cancellation requested.
- Hentikan pekerjaan lokal jika aman.
- Abaikan atau karantina hasil yang datang kemudian sesuai kebijakan.
- Catat biaya dan status provider jika masih berjalan.

Jangan mengklaim job berhasil dibatalkan sebelum ada konfirmasi yang memadai.

17. Dependency and Workflow Integration

Job dapat memiliki dependency terhadap job lain.

Contoh:

Character Generation
        |
        v
Environment Generation
        |
        v
Storyboard Generation
        |
        v
Video Generation
        |
        v
Scene Validation
        |
        v
Final Rendering

Dependency harus ditentukan oleh Production Workflow Engine.

Job Processing Engine mengeksekusi job yang telah memenuhi dependency requirements.

Kegagalan upstream dapat memblokir downstream jobs.

Jika upstream output berubah, downstream jobs yang bergantung pada output tersebut harus dievaluasi untuk invalidation atau re-execution.

Jangan menganggap seluruh workflow harus berjalan secara serial. Independent jobs dapat berjalan paralel.

18. MPB Snapshot and Reproducibility

Setiap production job yang bergantung pada creative specifications harus merekam MPB snapshot reference.

Minimal mencatat:

- MPB snapshot ID.
- Relevant revision references.
- Prompt version.
- Model and provider version.
- Generation settings.
- Input asset references.
- Execution timestamp.
- Result references.

Job tidak boleh diam-diam membaca specification terbaru di tengah execution jika job tersebut sudah dikunci pada snapshot tertentu.

Perubahan MPB setelah job dibuat harus menghasilkan explicit revalidation atau new job decision.

19. Result Processing

Result processor bertanggung jawab untuk:

- Validasi response.
- Validasi media metadata.
- Checksum generation.
- Asset registration.
- Result association.
- Usage recording.
- Cost recording.
- Job completion.
- Event publication.

Hasil provider tidak otomatis menjadi approved production asset.

Asset harus melewati quality control dan approval yang sesuai.

Hasil gagal atau tidak lengkap harus memiliki status yang dapat ditelusuri.

20. Dead Letter and Failed Job Handling

Job yang gagal melewati retry policy dapat masuk ke dead-letter state atau dead-letter queue.

Ketentuan:

- Failure reason harus tercatat.
- Attempt history harus tersedia.
- Payload reference harus dapat diperiksa dengan aman.
- Sensitive data harus disensor.
- Manual retry harus memiliki authorization.
- Manual replay harus mempertimbangkan idempotency.
- Dead-letter processing harus memiliki audit trail.

Dead-letter queue bukan tempat membuang error tanpa tindak lanjut.

21. Job Events

Event examples:

- job.created
- job.queued
- job.dispatched
- job.started
- job.progress_updated
- job.waiting_provider
- job.retry_scheduled
- job.cancel_requested
- job.cancelled
- job.succeeded
- job.failed
- job.timed_out
- job.blocked

Event records harus memiliki:

- Event ID.
- Job ID.
- Event type.
- Timestamp.
- Correlation ID.
- Relevant metadata.
- Schema version.

Events merupakan catatan perubahan, bukan pengganti authoritative job state.

Gunakan transactional outbox atau mekanisme yang setara untuk menjaga konsistensi perubahan database dan publikasi event.

22. API Contract

Logical endpoints:

POST   /api/v1/jobs
GET    /api/v1/jobs/{job_id}
GET    /api/v1/jobs
POST   /api/v1/jobs/{job_id}/cancel
POST   /api/v1/jobs/{job_id}/retry
GET    /api/v1/jobs/{job_id}/events
GET    /api/v1/jobs/{job_id}/result

Ketentuan:

- Semua endpoint harus melewati authorization.
- Pagination digunakan untuk listing.
- Create job mendukung idempotency.
- Cancel mengembalikan status permintaan cancellation.
- Retry memvalidasi job state dan permission.
- Result endpoint hanya mengembalikan hasil yang boleh diakses.
- API tidak boleh mengekspos internal queue payload atau secrets.

Detail request dan response mengikuti "API_SPEC.md".

23. Security Requirements

- Job creation harus memeriksa project authorization.
- Worker harus memiliki least-privilege permissions.
- Queue harus dilindungi.
- Payload tidak boleh mengeksekusi arbitrary code.
- Provider credentials disimpan dalam secrets management.
- Webhook diverifikasi.
- Asset result tetap private.
- Sensitive fields disensor dalam logs.
- Job access harus mengikuti project isolation.
- Manual replay membutuhkan permission khusus.
- Rate limits diterapkan untuk mencegah job abuse.

24. Observability

Setiap job harus dapat ditelusuri melalui:

- Job ID.
- Correlation ID.
- Project ID.
- Workflow ID.
- Provider request ID.
- Worker ID.
- Attempt number.

Metrics:

- Queue depth.
- Queue wait time.
- Job execution duration.
- Success rate.
- Failure rate.
- Retry rate.
- Timeout rate.
- Cancellation rate.
- Worker utilization.
- Provider latency.
- Cost per job.
- Dead-letter count.

Dashboard harus membedakan queue delay, provider delay, worker execution time, dan result processing time.

Detail observability mengikuti "OBSERVABILITY.md".

25. MVP Implementation Scope

MVP tidak perlu langsung memiliki distributed worker infrastructure yang kompleks.

Minimum implementation:

1. Persistent job records.
2. Job state machine.
3. One reliable dispatcher.
4. One worker process.
5. At least one queue implementation or durable polling mechanism.
6. Idempotency protection.
7. Basic retry policy.
8. Timeout and stale job detection.
9. Basic progress reporting.
10. Result persistence.
11. Error history.
12. Manual retry with authorization.
13. Job monitoring endpoint.

Teknologi queue harus dipilih setelah repository audit.

Redis, RabbitMQ, Celery, Dramatiq, RQ, atau alternatif lainnya tidak boleh dianggap sudah dipilih melalui ADR ini.

26. Implementation Sequence

Phase 1: Repository Discovery

- Audit existing background tasks.
- Audit job persistence.
- Audit provider async operations.
- Audit database transaction model.
- Audit deployment process.
- Audit existing queue and worker infrastructure.

Phase 2: Domain Foundation

- Define Job entity.
- Define Job state machine.
- Define job types.
- Define idempotency rules.
- Define retry classifications.
- Define job ownership.

Phase 3: Persistence and Dispatch

- Implement job repository.
- Implement atomic job claims.
- Implement dispatcher.
- Implement durable dispatch mechanism.
- Implement event publication strategy.

Phase 4: Worker Execution

- Implement worker lifecycle.
- Implement job handler registry.
- Implement execution timeout.
- Implement heartbeat.
- Implement graceful shutdown.
- Implement resource limits.

Phase 5: Reliability

- Implement retries.
- Implement stale job recovery.
- Implement cancellation.
- Implement dead-letter handling.
- Implement reconciliation.
- Implement duplicate message protection.

Phase 6: Provider Integration

- Connect provider adapters.
- Support asynchronous provider operations.
- Support polling or webhooks.
- Persist provider operation references.
- Implement result processing.

Phase 7: Monitoring and Testing

- Implement job dashboard data.
- Add job metrics.
- Add structured logs.
- Test failure and recovery.
- Test concurrency.
- Test duplicate delivery.
- Test worker restart.

27. Consequences

Positive

- Long-running tasks tidak memblokir API.
- Job state dapat dipantau.
- Worker dapat diskalakan secara independen.
- Retry dan recovery lebih terstruktur.
- Provider asynchronous API dapat diintegrasikan.
- Production execution dapat ditelusuri.
- Job dapat dikaitkan dengan MPB snapshot.

Negative

- Infrastruktur lebih kompleks.
- Perlu menjaga consistency antara database dan queue.
- Worker membutuhkan resource monitoring.
- Retry dapat menimbulkan biaya tambahan.
- External provider cancellation tidak selalu tersedia.

Accepted Trade-offs

Durability dan reliability lebih diprioritaskan daripada kesederhanaan background task berbasis memory.

28. Validation Checklist

- [ ] Job records persistent.
- [ ] Job state transitions tervalidasi.
- [ ] Duplicate delivery tidak menghasilkan duplicate side effects.
- [ ] Job claim bersifat atomic.
- [ ] Retry policy berdasarkan error classification.
- [ ] Timeout dan heartbeat berjalan.
- [ ] Stale job recovery tersedia.
- [ ] Worker restart tidak menghilangkan job.
- [ ] Cancellation status akurat.
- [ ] Provider async operation dapat dipantau.
- [ ] Webhook memiliki verification.
- [ ] Result processing idempotent.
- [ ] MPB snapshot reference tercatat.
- [ ] Failed jobs dapat diperiksa.
- [ ] Manual retry memiliki audit trail.
- [ ] Queue metrics tersedia.
- [ ] Worker resource limits diterapkan.
- [ ] Project authorization diuji.
- [ ] Integration tests mencakup failure scenarios.

29. Review Conditions

ADR ini perlu ditinjau ulang apabila:

- Job volume meningkat secara signifikan.
- Multi-worker distributed execution diperlukan.
- Provider async workloads berkembang.
- Queue latency melampaui target.
- GPU rendering membutuhkan dedicated scheduling.
- Multi-region execution dibutuhkan.
- Job isolation memerlukan container-level execution.

30. Related Documents

- "ARCHITECTURE.md"
- "TASKS.md"
- "AI_PIPELINE.md"
- "DATA_MODEL.md"
- "API_SPEC.md"
- "ERROR_HANDLING.md"
- "TEST_STRATEGY.md"
- "DEPLOYMENT.md"
- "OBSERVABILITY.md"
- "BACKUP_RECOVERY.md"
- "DECISIONS/ADR/README.md"

Related ADRs:

- ADR-0001: Architecture Style.
- ADR-0002: Application Structure.
- ADR-0003: Provider Adapter System.
- ADR-0004: Master Production Bible.
- ADR-0005: Production Workflow Engine.
- ADR-0006: Data Storage Strategy.
- ADR-0008: Prompt Compilation Engine.

---

Final Decision: Proposed.

MovieAIProducer adopts Persistent Asynchronous Job Processing with database-backed job state, queue-based dispatch, isolated workers, idempotent execution, controlled retries, recovery, and provider-aware lifecycle management.

Specific queue technology and deployment topology remain subject to repository discovery and infrastructure validation.
