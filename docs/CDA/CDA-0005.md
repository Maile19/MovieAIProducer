# CDA-0005: Canonical Error & Failure Contract Registry

- Project: MovieAIProducer
- Document ID: CDA-0005
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Classification: Architecture Governance
- Depends on: CDA-0002, CDA-0003, CDA-0004, ADR-0001, ADR-0005, ADR-0007, ADR-0011, ADR-0013

---

1. Purpose

Dokumen ini menetapkan standar penanganan error dan failure di seluruh sistem MovieAIProducer.

Tujuan:

1. Menyatukan klasifikasi error antardomain.
2. Memisahkan business rejection dari technical failure.
3. Menentukan error contract untuk API dan internal communication.
4. Menetapkan kebijakan retry dan recovery.
5. Mencegah kegagalan berulang dan duplicate side effects.
6. Menjamin keamanan informasi error.
7. Memudahkan debugging, monitoring, dan incident response.
8. Menjamin bahwa kegagalan satu modul tidak merusak keseluruhan sistem.

2. Architectural Decision

MovieAIProducer menggunakan Centralized Error Taxonomy with Domain-Owned Failure Semantics.

Prinsip:

- Setiap domain memiliki kewenangan atas makna business error miliknya.
- Format error dan metadata teknis mengikuti kontrak bersama.
- Business error tidak boleh diperlakukan sebagai technical failure.
- Retry hanya dilakukan jika kegagalan dan operasi memenuhi syarat retry.
- Error internal tidak boleh mengekspos secret, stack trace, atau data privat.
- Semua kegagalan kritis harus dapat ditelusuri melalui correlation ID.
- Recovery harus mempertahankan integritas domain state.
- Error response bukan pengganti audit record.

Standar ini berlaku untuk API, workflow, jobs, AI orchestration, provider integration, asset processing, continuity, QC, editorial, dan delivery.

3. Error Classification

3.1 Validation Error

Permintaan tidak memenuhi format atau aturan validasi.

Contoh:

- Field wajib kosong.
- Format aspect ratio tidak valid.
- Prompt IR tidak memenuhi schema.
- Scene duration tidak sesuai aturan konfigurasi.

Penanganan:

- Jangan jalankan proses yang bergantung pada input tidak valid.
- Kembalikan detail field yang aman ditampilkan.
- Jangan retry otomatis tanpa perubahan input.

3.2 Authentication Error

Identitas pengguna atau service tidak dapat diverifikasi.

Contoh:

- Token tidak valid.
- Session expired.
- Signature tidak cocok.
- Service identity tidak dikenali.

Penanganan:

- Tolak akses.
- Jangan mengungkap alasan sensitif secara berlebihan.
- Catat aktivitas keamanan sesuai kebijakan audit.

3.3 Authorization Error

Identitas terverifikasi tetapi tidak memiliki izin melakukan tindakan.

Contoh:

- User mencoba mengakses proyek tenant lain.
- AI agent mencoba menyetujui MPB.
- Worker mencoba menghapus aset tanpa izin.

Penanganan:

- Tolak tindakan.
- Jangan retry.
- Catat security event jika relevan.

3.4 Business Rule Error

Operasi melanggar aturan bisnis atau lifecycle domain.

Contoh:

- MPB revision belum disetujui.
- Workflow belum memenuhi dependency.
- Asset belum lolos QC.
- Delivery diblokir oleh critical finding.

Penanganan:

- Pertahankan state yang valid.
- Berikan alasan yang dapat dipahami.
- Tidak melakukan retry teknis.

3.5 Conflict Error

Permintaan bertentangan dengan state terkini.

Contoh:

- Optimistic locking conflict.
- Revision sudah berubah.
- Dua pengguna mengedit entitas bersamaan.
- State transition tidak lagi valid.

Penanganan:

- Ambil state terbaru jika diizinkan.
- Tampilkan konflik kepada pemanggil.
- Retry hanya jika operasi aman dan menggunakan state terkini.

3.6 Resource Error

Resource yang dibutuhkan tidak tersedia atau tidak memenuhi kapasitas.

Contoh:

- Asset tidak ditemukan.
- Storage penuh.
- Worker tidak tersedia.
- Quota habis.

Penanganan:

- Bedakan resource tidak ditemukan, kapasitas penuh, dan resource sementara tidak tersedia.
- Retry hanya untuk kondisi sementara.
- Quota exhaustion tidak boleh di-retry tanpa perubahan entitlement atau quota.

3.7 Provider Error

Kegagalan layanan eksternal.

Contoh:

- Provider timeout.
- Provider rate limit.
- Model tidak tersedia.
- Provider menolak parameter.
- Provider mengembalikan hasil yang tidak valid.

Penanganan:

- Normalisasi provider-specific error.
- Simpan raw diagnostic secara aman.
- Jangan meneruskan secret atau response sensitif.
- Retry sesuai klasifikasi provider dan idempotency.

3.8 Technical Infrastructure Error

Kegagalan infrastruktur.

Contoh:

- Database connection failure.
- Object storage unavailable.
- Network failure.
- Queue unavailable.
- Worker process crash.

Penanganan:

- Retry terbatas untuk operasi yang aman.
- Terapkan timeout dan circuit breaker jika sesuai.
- Pertahankan state transaksi.
- Aktifkan recovery dan observability.

3.9 Internal Application Error

Kegagalan yang tidak diharapkan dalam kode aplikasi.

Contoh:

- Unhandled exception.
- Broken invariant.
- Unexpected null.
- Internal dependency failure.

Penanganan:

- Jangan tampilkan detail internal kepada pengguna.
- Catat stack trace di log yang terlindungi.
- Buat incident atau alert sesuai severity.
- Jangan melakukan retry tanpa analisis keamanan operasi.

3.10 Quality & Production Failure

Kegagalan yang terjadi saat validasi hasil produksi.

Contoh:

- Continuity violation.
- Lip-sync failure.
- Character identity mismatch.
- Rendering artifact.
- Audio clipping.
- QC critical blocker.

Penanganan:

- Catat finding beserta evidence.
- Pertahankan hasil pemeriksaan.
- Arahkan ke rework jika kebijakan mengharuskan.
- Jangan menyamakan hasil QC fail dengan technical exception.

4. Canonical Error Envelope

Semua error yang diekspos melalui API harus menggunakan struktur konsisten.

Contoh:

```json
{
  "error": {
    "code": "MPB_REVISION_NOT_APPROVED",
    "category": "business_rule",
    "message": "MPB revision must be approved before production.",
    "retryable": false,
    "severity": "medium",
    "correlation_id": "correlation_id",
    "occurred_at": "2026-11-19T10:00:00Z",
    "details": {
      "resource_type": "mpb_revision",
      "resource_id": "revision_id"
    },
    "field_errors": [],
    "documentation_ref": "errors/mpb/revision-not-approved"
  }
}
```

Ketentuan:

- "code" adalah kode stabil dan unik.
- "category" mengikuti taxonomy.
- "message" aman ditampilkan.
- "retryable" hanya petunjuk kebijakan, bukan izin retry tanpa pemeriksaan.
- "severity" menunjukkan dampak operasional.
- "correlation_id" membantu investigasi.
- "occurred_at" menggunakan timestamp standar.
- "details" hanya berisi informasi yang boleh diungkap.
- "field_errors" digunakan untuk validasi input.
- "documentation_ref" opsional.

Stack trace, credential, raw provider token, dan secret tidak boleh dimasukkan ke public error envelope.

5. Canonical Error Code Convention

Format:

"<DOMAIN>_<RESOURCE>_<FAILURE>"

Contoh:

- "PROJECT_NOT_FOUND"
- "MPB_REVISION_NOT_APPROVED"
- "WORKFLOW_DEPENDENCY_NOT_MET"
- "JOB_EXECUTION_TIMEOUT"
- "PROVIDER_RATE_LIMITED"
- "ASSET_VALIDATION_FAILED"
- "CONTINUITY_VIOLATION_DETECTED"
- "QC_CRITICAL_BLOCKER"
- "DELIVERY_REQUIREMENTS_NOT_MET"

Ketentuan:

1. Gunakan uppercase snake case.
2. Kode tidak berubah ketika message diterjemahkan.
3. Kode lama tidak boleh digunakan kembali untuk makna berbeda.
4. Breaking semantic changes memerlukan kode baru.
5. Setiap kode memiliki pemilik domain.
6. Setiap kode memiliki dokumentasi dan test.

6. Error Ownership Registry

Domain| Pemilik error
Identity & Access| Authentication dan authorization
Project Management| Project lifecycle dan ownership
Creative Development| Brief dan creative constraints
Story Architecture| Story structure dan screenplay
Character Management| Character identity dan profile
Production Design| Environment, props, wardrobe
MPB Management| Revision, approval, snapshot
Cinematography| Camera configuration
Lighting| Lighting constraints
Performance & Audio| Voice, dialogue, performance
Motion Engineering| Motion constraints
Storyboard & Previs| Previsualization validation
Scene & Shot Management| Scene/shot consistency
Workflow Engine| Workflow state dan dependency
Job Processing| Job execution dan recovery
AI Orchestration| Generation request
Provider Integration| Provider operation
Prompt Compilation| Prompt IR dan compilation
Asset Management| Asset metadata dan lifecycle
Continuity Engine| Continuity validation
Quality Control| QC run dan findings
Editorial| Timeline dan editorial constraints
Delivery| Packaging dan publication
Notifications| Notification delivery
Observability| Telemetry dan alert delivery
Audit Governance| Audit persistence dan integrity
Administration| Configuration dan policy

Domain owner bertanggung jawab atas kode dan semantik. Error formatter bersama hanya menangani representasi standar.

7. HTTP Status Mapping

Pemetaan awal untuk REST API:

HTTP| Penggunaan
400| Malformed request
401| Authentication required or invalid
403| Permission denied
404| Resource not found
409| State conflict
410| Resource permanently unavailable
413| Payload too large
415| Unsupported media type
422| Semantic validation or business rule rejection
429| Rate limit or quota restriction
500| Unexpected internal error
502| Invalid upstream response
503| Service temporarily unavailable
504| Upstream timeout

Ketentuan:

- Status HTTP tidak menggantikan error code.
- Mapping harus konsisten dengan API_SPEC.md.
- Jangan gunakan 500 untuk semua kegagalan.
- Jangan mengungkap keberadaan resource privat melalui perbedaan response yang tidak aman.
- Async job failure dikomunikasikan melalui job status dan result contract, bukan hanya HTTP response awal.

8. Retry Policy

Retry harus ditentukan berdasarkan kategori dan sifat operasi.

8.1 Retryable Candidates

- Temporary network failure.
- Transient database connectivity failure.
- Provider 429 dengan respect terhadap Retry-After.
- Provider 5xx sementara.
- Worker interruption.
- Temporary storage outage.

8.2 Non-Retryable Candidates

- Invalid input.
- Authentication failure.
- Authorization failure.
- Business rule rejection.
- Unsupported model capability.
- Permanently invalid provider parameter.
- Quota exhausted.
- User rejection.
- Invalid asset format.

8.3 Retry Requirements

Setiap retry policy harus menentukan:

- Maximum attempts.
- Backoff strategy.
- Jitter.
- Per-attempt timeout.
- Total execution deadline.
- Idempotency key.
- Retryable error categories.
- Recovery behavior.
- Dead-letter policy.

Jangan menetapkan angka retry universal untuk semua operasi. Nilainya harus ditentukan berdasarkan karakteristik provider, biaya, dan dampak operasi.

9. Timeout & Cancellation

Setiap operasi eksternal dan internal yang berpotensi berlangsung lama harus memiliki timeout policy.

Bedakan:

- Connection timeout.
- Request timeout.
- Execution timeout.
- Provider operation timeout.
- Overall workflow deadline.

Cancellation:

1. Catat cancellation request.
2. Kirim permintaan pembatalan ke komponen terkait.
3. Tunggu konfirmasi jika tersedia.
4. Perbarui state berdasarkan hasil sebenarnya.
5. Jika status tidak diketahui, jangan mengklaim operasi telah dibatalkan.

Cancellation request tidak sama dengan cancellation confirmed.

10. Circuit Breaker & Provider Resilience

Provider adapter dapat menerapkan circuit breaker berdasarkan bukti kegagalan operasional.

State:

- Closed.
- Open.
- Half-open.

Ketentuan:

- Jangan melakukan retry terus-menerus terhadap provider yang sedang tidak sehat.
- Fallback hanya jika capability alternatif kompatibel.
- Jangan mengubah creative intent atau parameter kritis secara diam-diam.
- Catat provider/model yang digunakan.
- Fallback harus dapat ditelusuri.
- Jangan mengirim ulang operasi non-idempotent tanpa pemeriksaan.

11. Error Handling Across Domains

11.1 Workflow ↔ Job

- Workflow Engine memiliki state workflow.
- Job Processing memiliki state job.
- Job failure dapat menyebabkan task gagal, menunggu retry, atau membutuhkan intervensi.
- Workflow tidak boleh mengubah job menjadi completed tanpa bukti hasil.

11.2 AI ↔ Provider

- AI Orchestration menormalisasi hasil generation.
- Provider Integration menormalisasi error eksternal.
- Raw provider diagnostics disimpan dengan akses terbatas.
- Provider error tidak boleh merusak generation request history.

11.3 Generation ↔ Asset

- File gagal disimpan tidak boleh dianggap asset terdaftar.
- Asset validation failure harus dicatat.
- Partial upload harus direkonsiliasi.
- File orphan harus memiliki prosedur cleanup.

11.4 Continuity ↔ QC

- Continuity violation merupakan domain finding.
- QC dapat menggunakan finding tersebut.
- QC tidak boleh mengubahnya menjadi technical exception.
- Confidence dan severity harus tetap terpisah.

11.5 QC ↔ Approval ↔ Delivery

- QC fail dapat memblokir approval sesuai policy.
- Approval rejection bukan system failure.
- Delivery failure tidak boleh mengubah hasil QC sebelumnya.
- Rework harus memicu pemeriksaan ulang pada hasil yang terdampak.

12. User-Facing Error Experience

Pesan kepada pengguna harus:

- Menjelaskan apa yang gagal.
- Menjelaskan apakah pengguna dapat memperbaikinya.
- Menyediakan tindakan berikutnya jika diketahui.
- Menghindari istilah internal yang tidak diperlukan.
- Tidak menyalahkan pengguna tanpa dasar.
- Tidak mengungkap data privat atau detail keamanan.

Contoh:

Internal Code| User Message
"MPB_REVISION_NOT_APPROVED"| Production cannot start because the MPB revision is not approved yet.
"PROVIDER_RATE_LIMITED"| The generation provider is temporarily busy. Please try again later.
"ASSET_VALIDATION_FAILED"| This media file could not pass validation.
"WORKFLOW_DEPENDENCY_NOT_MET"| A required production step has not been completed.
"QC_CRITICAL_BLOCKER"| This scene cannot proceed until the critical quality issue is resolved.

Pesan harus mendukung internasionalisasi.

13. Logging & Observability

Setiap error operasional yang relevan harus memiliki:

- Timestamp.
- Error code.
- Category.
- Severity.
- Correlation ID.
- Trace ID jika tersedia.
- Domain.
- Operation.
- Resource reference.
- Attempt count.
- Provider/model jika relevan.
- Duration.
- Recovery status.

Ketentuan:

- Stack trace hanya pada log internal dengan akses terlindungi.
- Secret dan token wajib disensor.
- PII diminimalkan.
- Audit record dipisahkan dari application log.
- Telemetry failure tidak boleh menghilangkan domain transaction.
- Error log tidak boleh menjadi satu-satunya bukti perubahan state.

14. Recovery & Reconciliation

Recovery harus mempertimbangkan kondisi aktual sistem.

Contoh:

- Job yang terhenti: periksa heartbeat dan lease.
- Outbox tertunda: publikasikan ulang.
- Provider operation tidak diketahui: query status jika API mendukung.
- Asset upload parsial: periksa checksum dan storage object.
- Workflow task tertinggal: rekonsiliasi dengan job.
- Notification gagal: retry tanpa mengulang transaksi bisnis.

Recovery action harus:

1. Memiliki otorisasi.
2. Memiliki correlation ID.
3. Memiliki idempotency protection.
4. Memiliki audit trail jika berdampak pada data bisnis.
5. Mempertahankan provenance.
6. Tidak melewati approval gate.

15. Error Registry

Setiap error harus memiliki:

Field| Deskripsi
Error code| Identifier stabil
Domain owner| Pemilik semantik
Category| Taxonomy
Description| Penjelasan
HTTP mapping| Jika API-facing
Retryable| Kebijakan awal
Severity| Dampak
User message| Pesan aman
Recovery procedure| Langkah pemulihan
Security classification| Sensitivitas
Test reference| Test yang memvalidasi
Status| Lifecycle kode

Status error code:

- Proposed
- Accepted
- Active
- Deprecated
- Retired

16. Testing Requirements

Unit Tests

- Error classification.
- Error code uniqueness.
- Error envelope validation.
- HTTP mapping.
- Retry eligibility.
- Secret redaction.
- User message localization.

Integration Tests

- API exception handling.
- Workflow/Job error propagation.
- Provider error normalization.
- Asset storage recovery.
- Outbox retry.
- Dead-letter handling.
- Cancellation behavior.

Resilience Tests

- Network timeout.
- Provider rate limit.
- Provider 5xx.
- Database outage.
- Worker crash.
- Storage outage.
- Duplicate execution.
- Circuit breaker transitions.

Security Tests

- Stack trace leakage.
- Secret leakage.
- PII leakage.
- Cross-tenant error leakage.
- Unauthorized recovery.
- Error enumeration attacks.

Production Quality Tests

- QC critical blocker.
- Continuity failure.
- Invalid asset.
- Rework dependency.
- Delivery validation failure.

17. MVP Implementation Scope

Prioritas implementasi:

1. Canonical error taxonomy.
2. Stable error codes.
3. API error envelope.
4. Domain exception mapping.
5. Retry classification.
6. Correlation ID propagation.
7. Secret redaction.
8. Job failure handling.
9. Provider error normalization.
10. Recovery logging.
11. Contract tests.

Advanced circuit breaker, automated reconciliation, dan sophisticated failure analytics dapat ditambahkan setelah kebutuhan operasional terukur.

18. Implementation Sequence

Phase 1: Foundation

- Buat error taxonomy.
- Buat error registry.
- Buat canonical error envelope.
- Implementasikan exception mapping.
- Integrasikan correlation ID.

Phase 2: Reliability

- Implementasikan retry policy.
- Implementasikan timeout.
- Implementasikan idempotency checks.
- Implementasikan dead-letter handling.
- Implementasikan cancellation semantics.

Phase 3: Domain Integration

- Workflow dan Job.
- AI dan Provider.
- Asset processing.
- Continuity dan QC.
- Approval dan Delivery.

Phase 4: Governance

- Error registry validation.
- Security testing.
- Recovery drills.
- Incident review.
- Deprecation governance.

19. Acceptance Criteria

- [ ] Semua domain menggunakan canonical error taxonomy.
- [ ] Error code stabil dan unik.
- [ ] Business rejection terpisah dari technical failure.
- [ ] API menggunakan error envelope konsisten.
- [ ] HTTP mapping konsisten dengan API_SPEC.
- [ ] Retry hanya dilakukan untuk operasi yang memenuhi syarat.
- [ ] Idempotency melindungi side effect.
- [ ] Timeout dan cancellation memiliki semantik jelas.
- [ ] Provider error dinormalisasi.
- [ ] Stack trace dan secret tidak bocor.
- [ ] Correlation ID dapat ditelusuri.
- [ ] Recovery memiliki kontrol otorisasi.
- [ ] Job dan workflow state tidak tercampur.
- [ ] QC finding tidak diperlakukan sebagai technical exception.
- [ ] Automated tests mencakup jalur kritis.

20. Risks

ID| Risiko| Mitigasi
CDA5-R01| Business error dianggap technical failure| Taxonomy
CDA5-R02| Infinite retry| Bounded retry
CDA5-R03| Duplicate external side effect| Idempotency
CDA5-R04| Secret leakage| Redaction
CDA5-R05| Error state tidak konsisten| Domain ownership
CDA5-R06| Cancellation palsu| Confirmation semantics
CDA5-R07| Recovery merusak provenance| Audited recovery
CDA5-R08| Provider error tidak seragam| Adapter normalization
CDA5-R09| Error message membocorkan resource privat| Security review
CDA5-R10| Error registry drift| Contract validation

21. Cross-Document Dependencies

Wajib direkonsiliasi dengan:

- BRD.md.
- PRD.md.
- ARCHITECTURE.md.
- API_SPEC.md.
- SECURITY.md.
- ERROR_HANDLING.md.
- OBSERVABILITY.md.
- TEST_STRATEGY.md.
- DEPLOYMENT.md.
- ADR-0005.
- ADR-0007.
- ADR-0011.
- ADR-0013.
- CDA-0002.
- CDA-0003.
- CDA-0004.

Jika ditemukan konflik, catat dan selesaikan melalui governance arsitektur. Jangan melakukan perubahan sepihak.

22. Governance & Final Status

Status: PROPOSED

Dokumen ini adalah baseline kontrak error dan failure yang diusulkan, bukan bukti implementasi.

Sebelum Accepted:

1. Audit repository.
2. Periksa error handling aktual.
3. Cocokkan HTTP response.
4. Cocokkan lifecycle dan retry semantics.
5. Review security.
6. Verifikasi provider error mapping.
7. Implementasikan contract tests.
8. Lakukan failure simulation.

Final Decision Principle:

An error must be classified, owned, observable, secure, and recoverable.

A business rejection is not a technical failure. A retry is not a recovery strategy by itself. A completed job is not an approved production result.

---

End of CDA-0005
