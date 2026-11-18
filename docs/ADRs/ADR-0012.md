# ADR-0012: Asset Storage Architecture

- Project: MovieAIProducer
- ADR ID: ADR-0012
- Title: Asset Storage Architecture
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Decision Owners: Product Owner, Technical Architect, Infrastructure Owner
- Related ADRs: ADR-0001, ADR-0004, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011

---

1. Context

MovieAIProducer membutuhkan sistem penyimpanan yang mampu mengelola seluruh aset produksi film sepanjang siklus hidup project.

Jenis asset mencakup:

- Original reference images.
- Character reference images.
- Environment reference images.
- Concept art.
- Storyboards.
- Animatics.
- Generated images.
- Generated video clips.
- Voice recordings.
- Dialogue audio.
- Music and sound effects.
- Rendered scenes.
- Final film exports.
- Thumbnails and previews.
- QC evidence.
- Production documents.
- Metadata and provenance records.

Asset dapat berukuran besar, memiliki banyak versi, dan digunakan oleh berbagai tahapan produksi.

Sistem tidak boleh memperlakukan asset sebagai file biasa tanpa identitas, kepemilikan, riwayat, dan relasi produksi.

2. Problem Statement

Tanpa Asset Storage Architecture yang terstruktur, sistem berisiko mengalami:

- File hilang atau tertimpa.
- Duplikasi asset yang tidak terkendali.
- Referensi file rusak.
- Kebocoran asset privat.
- Ketidakjelasan versi final.
- Sulitnya melacak asal-usul media.
- Kesalahan penghapusan asset yang masih digunakan.
- Pemborosan storage.
- Sulitnya pemulihan setelah kegagalan.
- Ketidaksesuaian antara metadata database dan file fisik.

3. Decision

MovieAIProducer menggunakan Hybrid Asset Storage Architecture.

Arsitektur terdiri dari tiga lapisan utama:

1. Relational Database untuk metadata, ownership, lifecycle, dan relasi asset.
2. Object Storage untuk file media dan binary artifacts.
3. Asset Management Domain untuk mengelola identitas, versi, akses, provenance, dan lifecycle.

Database menjadi sumber kebenaran metadata transaksional.

Object storage menjadi tempat penyimpanan binary content.

Asset Management Domain menjadi satu-satunya jalur resmi untuk mengelola asset aplikasi.

Filesystem lokal dapat digunakan untuk development atau deployment kecil, tetapi harus berada di balik storage abstraction yang sama.

4. Architectural Principles

4.1 Metadata and Binary Separation

Metadata asset tidak disimpan sebagai binary file di database.

Database menyimpan informasi seperti:

- Asset ID.
- Project ID.
- File name.
- MIME type.
- File size.
- Checksum.
- Storage key.
- Asset type.
- Version.
- Status.
- Provenance.
- Ownership.
- Access policy.

Binary file disimpan di object storage.

4.2 Storage Provider Independence

Domain aplikasi tidak boleh bergantung langsung pada satu vendor storage.

Gunakan storage port/interface yang mendukung implementasi adapter.

Contoh kandidat:

- Local filesystem.
- S3-compatible object storage.
- Managed cloud object storage.

Pemilihan provider aktual harus mempertimbangkan biaya, region, kapasitas, keamanan, dan deployment architecture.

4.3 Immutable Original Assets

Original uploaded assets tidak boleh ditimpa secara diam-diam.

Setiap perubahan yang menghasilkan konten baru harus membuat versi atau asset baru.

4.4 Explicit Asset Lifecycle

Setiap asset mempunyai lifecycle yang dapat ditelusuri.

4.5 Secure by Default

Asset privat tidak boleh dapat diakses secara publik tanpa policy yang eksplisit.

4.6 Traceable Provenance

Setiap asset produksi harus dapat ditelusuri ke sumber, job, prompt, model, dan konteks MPB yang relevan.

5. Storage Architecture

5.1 Asset Management Domain

Bertanggung jawab terhadap:

- Asset registration.
- Asset metadata.
- Asset ownership.
- Version management.
- Asset relationships.
- Upload lifecycle.
- Download authorization.
- Provenance.
- Retention.
- Deletion.
- Storage reconciliation.

5.2 Storage Abstraction

Interface konseptual:

- "put_object"
- "get_object"
- "head_object"
- "delete_object"
- "copy_object"
- "generate_upload_url"
- "generate_download_url"
- "verify_object"
- "list_objects" (restricted administrative use)

Storage adapter menerjemahkan interface tersebut ke provider tertentu.

Domain tidak boleh menyimpan ketergantungan pada SDK vendor secara langsung.

5.3 Object Storage

Digunakan untuk:

- Original media.
- Generated media.
- Intermediate renders.
- Preview files.
- Thumbnails.
- Audio.
- QC evidence.
- Export packages.

5.4 Relational Metadata Store

Menyimpan:

- Asset identity.
- Asset versions.
- Project ownership.
- Storage location reference.
- Relationships.
- Checksums.
- Provenance.
- Lifecycle state.
- Access metadata.

Database fisik mengikuti ADR-0006.

6. Asset Classification

Asset harus memiliki klasifikasi yang konsisten.

Category| Examples
REFERENCE| Reference image, moodboard
CHARACTER| Character portraits, identity sheets
ENVIRONMENT| Location and set references
DESIGN| Concept art, production design
STORYBOARD| Storyboard frames
ANIMATIC| Animatic sequences
IMAGE| Generated and edited images
VIDEO| Generated scenes and shots
AUDIO| Voice, dialogue, music, SFX
RENDER| Intermediate and final renders
DOCUMENT| Scripts, production documents
QC_EVIDENCE| QC screenshots and evidence
DELIVERY| Final exports and delivery packages

Asset type dan MIME type merupakan dua hal berbeda.

Ekstensi file tidak boleh menjadi satu-satunya dasar untuk menentukan jenis konten.

7. Asset Identity and Versioning

Setiap asset mempunyai:

- Stable asset ID.
- Project ID.
- Asset category.
- Asset type.
- Version identifier.
- Created timestamp.
- Created by.
- Source reference.
- Lifecycle state.

7.1 Version Rules

- Original upload menjadi versi sumber.
- Editing menghasilkan versi baru.
- Regeneration menghasilkan asset baru.
- Final approval mengikat keputusan pada versi tertentu.
- Versi lama tetap dapat ditelusuri sesuai retention policy.
- Version number tidak boleh digunakan sebagai pengganti asset identity.

7.2 Immutable Asset Records

Perubahan metadata yang diperbolehkan harus tercatat.

Konten binary yang sudah diregistrasikan tidak boleh diganti diam-diam dengan binary berbeda menggunakan identitas dan checksum yang sama.

Jika konten berubah, sistem membuat versi atau asset baru.

8. Storage Key Strategy

Storage key harus:

- Unik.
- Tidak mudah ditebak.
- Tidak mengandung informasi sensitif.
- Stabil selama lifecycle asset.
- Terpisah dari nama file pengguna.
- Tidak mengandalkan URL publik sebagai identitas asset.

Contoh struktur konseptual:

"projects/{project_id}/assets/{asset_id}/versions/{version_id}/content"

Contoh tersebut adalah logical key layout, bukan ketentuan bahwa project ID atau asset ID harus diekspos kepada publik.

Original filename disimpan dalam metadata terpisah.

9. Upload Architecture

Upload flow:

1. User meminta upload.
2. Authorization memeriksa project scope.
3. Sistem membuat upload session.
4. Sistem menentukan storage target.
5. Client mengunggah file melalui mekanisme yang aman.
6. Sistem memverifikasi upload completion.
7. Sistem memeriksa ukuran dan checksum.
8. Sistem memvalidasi MIME type dan file signature.
9. Sistem menjalankan malware scanning jika tersedia.
10. Sistem mengekstrak metadata.
11. Asset diregistrasikan.
12. Asset memasuki status AVAILABLE setelah seluruh validasi wajib selesai.

Asset yang belum selesai diverifikasi tidak boleh dipakai oleh production workflow.

9.1 Upload Constraints

Policy dapat membatasi:

- Maximum file size.
- Maximum duration.
- Allowed MIME types.
- Allowed codecs.
- Project storage quota.
- User upload rate.
- Concurrent uploads.

Batas aktual harus dapat dikonfigurasi berdasarkan deployment dan kebutuhan produksi.

9.2 Interrupted Upload

Upload yang terputus harus dapat:

- Dilanjutkan jika storage provider mendukungnya.
- Dibatalkan.
- Dibersihkan setelah masa berlaku.
- Diverifikasi sebelum menjadi asset aktif.

10. Download and Access Architecture

Download flow:

1. Client meminta asset.
2. Authorization memeriksa actor.
3. Project membership diverifikasi.
4. Asset status diperiksa.
5. Access policy dievaluasi.
6. Sistem menghasilkan akses terbatas.
7. Download dicatat sesuai audit policy.

10.1 Signed URLs

Signed URL dapat digunakan untuk mengakses asset privat.

Ketentuan:

- Expiration time terbatas.
- Scope asset spesifik.
- Method dibatasi.
- Tidak boleh dibagikan sebagai permanent URL.
- Tidak boleh dicatat lengkap dalam log.
- Tidak boleh menggantikan authorization check.

Signed URL bukan pengganti access control.

10.2 Private by Default

Public access hanya diperbolehkan melalui keputusan policy yang eksplisit.

Asset project tidak boleh menjadi public hanya karena proses preview atau streaming.

11. Asset Lifecycle

Status konseptual:

- UPLOAD_PENDING.
- UPLOADING.
- VERIFYING.
- PROCESSING.
- AVAILABLE.
- QUARANTINED.
- ARCHIVED.
- DELETE_PENDING.
- DELETED.
- FAILED.

Transisi status harus tervalidasi.

Contoh:

"UPLOAD_PENDING → UPLOADING → VERIFYING → PROCESSING → AVAILABLE"

Jika validasi gagal:

"VERIFYING → QUARANTINED"

Jika pemrosesan gagal:

"PROCESSING → FAILED"

Asset yang gagal tidak boleh digunakan oleh workflow seolah-olah tersedia.

12. Asset Provenance

Asset produksi harus menyimpan relasi yang relevan:

- Project ID.
- Scene ID.
- Shot ID.
- MPB snapshot ID.
- Entity revision IDs.
- Prompt ID and version.
- Prompt compiler version.
- Provider ID.
- Model ID and version.
- Generation job ID.
- Parent asset IDs.
- Source asset IDs.
- QC run IDs.
- Approval references.

Provenance harus membedakan:

- Uploaded source.
- Generated output.
- Edited derivative.
- Transcoded copy.
- Preview.
- Final approved deliverable.

Asset tidak boleh dianggap final hanya karena file berhasil dibuat.

13. Asset Relationships

Sistem harus mendukung hubungan antarasset.

Contoh:

- Derived from.
- Generated from.
- Reference for.
- Thumbnail of.
- Preview of.
- Rendered from.
- Replaces.
- Approved version of.
- Evidence for.
- Included in delivery.

Relasi harus memiliki tipe yang jelas.

Penghapusan parent asset tidak boleh otomatis menghapus seluruh turunannya tanpa dependency analysis.

14. Media Processing Pipeline

Media processing harus dijalankan melalui asynchronous jobs.

Contoh pipeline:

1. Upload verification.
2. Metadata extraction.
3. Media probing.
4. Thumbnail generation.
5. Preview generation.
6. Audio waveform generation.
7. Video proxy generation.
8. Optional transcoding.
9. QC validation.
10. Asset availability update.

Pemrosesan media harus menggunakan worker terisolasi dengan batas CPU, memory, runtime, dan file size.

Jangan menjalankan media processing berat secara langsung pada API request thread.

15. Storage Integrity

Setiap asset harus mempunyai integrity metadata.

Minimum:

- File size.
- Checksum algorithm.
- Checksum value.
- Storage key.
- Upload timestamp.
- Verification status.

Gunakan checksum cryptographic seperti SHA-256 untuk verifikasi integritas.

Sistem harus dapat melakukan reconciliation antara:

- Database metadata.
- Object storage objects.
- Expected checksum.
- Asset lifecycle state.

Reconciliation mendeteksi:

- Missing object.
- Orphaned object.
- Incorrect checksum.
- Incomplete upload.
- Stale deletion.
- Metadata mismatch.

Perbaikan harus dilakukan melalui proses yang aman dan tercatat.

16. Deduplication

Deduplication dapat dipertimbangkan berdasarkan checksum.

Namun, deduplication tidak boleh merusak:

- Project isolation.
- Access control.
- Asset ownership.
- Retention policy.
- Provenance.
- Independent deletion requirements.

Jika binary content dibagikan secara internal, metadata kepemilikan dan hak akses tetap harus terpisah.

Deduplication tidak menjadi prioritas MVP jika kompleksitasnya melebihi manfaat yang terukur.

17. Retention and Deletion

Asset deletion harus mengikuti lifecycle policy.

17.1 Soft Deletion

Penghapusan awal dapat menggunakan status DELETE_PENDING atau logical deletion.

17.2 Dependency Check

Sebelum binary dihapus, sistem harus memeriksa:

- Asset masih dipakai scene atau shot.
- Asset merupakan referensi MPB.
- Asset terkait QC evidence.
- Asset menjadi source untuk derivative.
- Asset masuk final delivery.
- Asset tunduk pada retention requirement.

17.3 Physical Deletion

Physical deletion dilakukan setelah:

- Authorization.
- Dependency validation.
- Retention checks.
- Applicable legal holds.
- Deletion approval jika diperlukan.

Penghapusan harus tercatat.

17.4 Recovery Window

Jika sesuai policy, sediakan periode pemulihan sebelum physical deletion.

Nilainya ditentukan berdasarkan biaya storage, kebutuhan operasional, dan persyaratan retensi.

18. Storage Quota and Cost Governance

Sistem harus dapat memonitor:

- Total project storage.
- Storage per asset category.
- Upload volume.
- Download volume.
- Processing storage.
- Preview and proxy storage.
- Storage growth.
- Estimated storage cost.

Quota dapat ditetapkan berdasarkan:

- User.
- Project.
- Organization.
- Subscription tier.
- Deployment policy.

Quota enforcement harus dilakukan server-side.

19. Security Requirements

Minimum controls:

- Encryption in transit.
- Encryption at rest.
- Private bucket/container by default.
- Least-privilege storage credentials.
- Project-level authorization.
- File signature validation.
- MIME validation.
- Malware scanning where available.
- Upload size limits.
- Restricted media processing.
- Signed URL expiration.
- Secret management.
- Audit logging.
- Cross-project access testing.
- Secure deletion.
- Backup and recovery.

Media files harus diperlakukan sebagai untrusted input.

File extension dan client-supplied MIME type tidak cukup untuk menyatakan file aman.

20. Backup and Recovery

Storage recovery harus mengikuti ADR-0006 dan ADR-0019.

Prinsip:

- Metadata backup dan binary backup harus terkoordinasi.
- Database restore harus mempertahankan referensi asset.
- Object storage versioning dapat digunakan jika tersedia.
- Critical delivery assets harus memiliki recovery priority.
- Backup integrity harus diverifikasi.
- Restore harus diuji berkala.
- Retention harus terdokumentasi.

Backup yang belum pernah diuji restore tidak boleh dianggap sebagai recovery yang terbukti.

21. API Design

Endpoint konseptual:

Asset Registration and Upload

- "POST /api/v1/projects/{project_id}/assets/uploads"
- "POST /api/v1/assets/uploads/{upload_id}/complete"
- "POST /api/v1/assets"
- "GET /api/v1/assets/{asset_id}"

Asset Retrieval

- "GET /api/v1/assets/{asset_id}/download"
- "GET /api/v1/assets/{asset_id}/versions"
- "GET /api/v1/assets/{asset_id}/provenance"

Asset Management

- "POST /api/v1/assets/{asset_id}/archive"
- "POST /api/v1/assets/{asset_id}/restore"
- "DELETE /api/v1/assets/{asset_id}"

Asset Processing

- "POST /api/v1/assets/{asset_id}/process"
- "GET /api/v1/assets/{asset_id}/processing-status"

Endpoint merupakan rancangan konseptual dan harus diselaraskan dengan API_SPEC.md.

22. Observability

Metrics:

- Upload success rate.
- Upload failure rate.
- Upload duration.
- Download latency.
- Asset processing duration.
- Storage consumption.
- Storage growth.
- Missing object count.
- Checksum mismatch count.
- Quarantined asset count.
- Orphaned object count.
- Deletion backlog.
- Storage cost estimate.

Log harus memiliki correlation ID dan asset reference yang aman.

Jangan mencatat signed URL lengkap atau credential storage.

23. MVP Scope

Prioritas MVP:

1. Asset metadata model.
2. Storage abstraction interface.
3. Local filesystem adapter atau object storage adapter sesuai hasil repository audit.
4. Secure upload flow.
5. File validation.
6. Checksum verification.
7. Private asset access.
8. Asset versioning.
9. Project ownership.
10. Asset provenance.
11. Basic thumbnail and metadata processing.
12. Soft deletion.
13. Storage integrity checks.
14. Basic quota monitoring.

Advanced deduplication, multi-region replication, automated tiering, dan advanced lifecycle optimization dapat dikembangkan kemudian.

24. Implementation Sequence

Phase 1: Domain Foundation

- Define asset identity.
- Define asset categories.
- Define lifecycle.
- Define metadata contracts.
- Define provenance relationships.

Phase 2: Storage Abstraction

- Define storage interface.
- Implement selected adapter.
- Implement upload and download.
- Implement integrity verification.

Phase 3: Security

- Integrate ADR-0011 authorization.
- Implement private access.
- Implement signed URL policy if supported.
- Validate file types and signatures.
- Add upload restrictions.

Phase 4: Processing

- Integrate asynchronous jobs.
- Implement metadata extraction.
- Generate thumbnails and previews.
- Isolate media workers.
- Implement processing status.

Phase 5: Versioning and Lifecycle

- Implement asset versions.
- Implement relationships.
- Implement provenance.
- Implement archival and deletion workflow.

Phase 6: Governance

- Implement quota monitoring.
- Implement storage reconciliation.
- Implement backup integration.
- Implement operational dashboards.

25. Testing Requirements

Unit Tests

- Asset identity.
- Lifecycle transitions.
- Version creation.
- Checksum calculation.
- Storage key generation.
- Access policy.
- Provenance validation.

Integration Tests

- Upload and registration.
- Download authorization.
- Storage adapter operations.
- Metadata extraction.
- Asset processing jobs.
- Soft deletion and restoration.
- Reconciliation.

Security Tests

- Cross-project access.
- Unauthorized download.
- Expired signed URL.
- MIME spoofing.
- Malicious upload.
- Oversized file.
- Path traversal.
- Storage credential exposure.
- Unauthorized deletion.

Reliability Tests

- Interrupted upload.
- Storage provider timeout.
- Partial upload.
- Missing object.
- Checksum mismatch.
- Worker crash.
- Database/storage inconsistency.
- Recovery from backup.

End-to-End Test

1. User creates project.
2. User uploads reference image.
3. System verifies file.
4. Asset is registered.
5. Asset is linked to MPB.
6. Production workflow uses asset.
7. Generated output is registered with provenance.
8. QC validates generated output.
9. User approves the final asset.
10. Asset remains retrievable with correct access control.

26. Risks and Mitigations

Risk| Mitigation
Database and storage inconsistency| Reconciliation and recoverable workflows
Large media processing load| Asynchronous isolated workers
Asset leakage| Private storage and authorization
Broken asset references| Stable asset IDs and integrity checks
Storage cost growth| Quota, lifecycle and usage monitoring
Duplicate content| Optional checksum deduplication
Accidental deletion| Soft deletion and dependency checks
Provider lock-in| Storage adapter abstraction
Untrusted uploads| File validation and scanning
Lost provenance| Immutable asset history and relationships

27. Consequences

Positive

- Asset ownership becomes explicit.
- Large media files are handled independently of database metadata.
- Asset history becomes traceable.
- Storage provider changes become manageable.
- Security and project isolation are enforceable.
- Production and QC can reliably reference assets.
- Recovery and retention become structured.

Trade-offs

- Additional storage abstraction complexity.
- Metadata and binary consistency must be managed.
- Storage and processing costs can grow significantly.
- Versioning increases storage consumption.
- Reconciliation and lifecycle jobs require monitoring.

28. Decision Validation Checklist

- [ ] Metadata and binary storage are separated.
- [ ] Storage provider abstraction is defined.
- [ ] Asset identity is stable.
- [ ] Asset versions are traceable.
- [ ] Original assets are protected against silent overwrite.
- [ ] Upload validation is implemented.
- [ ] Private access is enforced.
- [ ] Project authorization is enforced.
- [ ] Provenance is preserved.
- [ ] Asset lifecycle is explicit.
- [ ] Dependency-aware deletion exists.
- [ ] Integrity verification is available.
- [ ] Backup and recovery are coordinated.
- [ ] Media processing is asynchronous.
- [ ] Storage usage is observable.

29. Review and Acceptance Conditions

This ADR can move from Proposed to Accepted when:

1. Asset domain boundaries are agreed.
2. Metadata and binary storage responsibilities are clear.
3. Storage adapter contract is approved.
4. Storage provider selection is supported by deployment requirements.
5. Lifecycle and deletion policies are defined.
6. Security is reconciled with ADR-0011.
7. Data ownership is reconciled with ADR-0006.
8. Async processing is reconciled with ADR-0007.
9. Backup and recovery are reconciled with ADR-0019.
10. Repository discovery confirms implementation feasibility.

Review this ADR if:

- Storage volume changes substantially.
- Multi-region delivery becomes necessary.
- A new media processing architecture is introduced.
- Legal retention requirements change.
- Storage provider migration becomes necessary.

---

Final Principle:

Every production asset must have a stable identity, an authorized owner, a traceable origin, a controlled lifecycle, and a verifiable storage location.

A file existing in storage does not automatically make it a valid, approved, or production-ready asset.
