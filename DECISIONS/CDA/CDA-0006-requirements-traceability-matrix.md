# CDA-0006: Requirements Traceability Matrix (RTM)

- Project: MovieAIProducer
- Document ID: CDA-0006
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Classification: Architecture & Product Governance
- Depends on: BRD.md, PRD.md, TASKS.md, TEST_STRATEGY.md, CHANGELOG.md, ADR-0001 through ADR-0015, CDA-0001 through CDA-0005

---

1. Purpose

Dokumen ini menetapkan sistem keterlacakan kebutuhan MovieAIProducer dari tujuan bisnis sampai bukti implementasi dan rilis.

Tujuan:

1. Memastikan setiap kebutuhan bisnis diterjemahkan menjadi kebutuhan produk.
2. Memastikan setiap requirement memiliki identifier unik.
3. Menghubungkan requirement dengan domain dan keputusan arsitektur.
4. Menghubungkan requirement dengan API, data model, dan workflow.
5. Menghubungkan requirement dengan implementation task.
6. Menghubungkan requirement dengan test case.
7. Memastikan setiap fitur memiliki acceptance criteria.
8. Mengidentifikasi requirement yang belum diimplementasikan.
9. Mencegah fitur diklaim selesai tanpa bukti.
10. Mengelola perubahan requirement secara terkendali.

2. Architectural Decision

MovieAIProducer menggunakan Bidirectional Requirements Traceability Architecture.

Setiap requirement harus dapat ditelusuri:

Forward Traceability

Business Objective → Product Requirement → User Story → Domain → ADR → Data Contract → API → Task → Test → Release Evidence.

Backward Traceability

Release Evidence → Test → Implementation → Task → API/Data Contract → ADR → Requirement → Business Objective.

Tidak boleh ada requirement penting yang hanya tercantum dalam dokumen tanpa jalur implementasi dan validasi.

Tidak boleh ada fitur produksi yang tidak memiliki alasan bisnis atau produk yang dapat ditelusuri.

3. Traceability Principles

3.1 Unique Identity

Setiap requirement harus memiliki ID stabil.

Format:

"<CATEGORY>-<DOMAIN>-<NUMBER>"

Contoh:

- "BR-PROD-001"
- "FR-MPB-001"
- "FR-AI-001"
- "NFR-SEC-001"
- "NFR-PERF-001"
- "OPS-DEP-001"

ID tidak boleh digunakan kembali setelah requirement dihapus atau digantikan.

3.2 One Requirement, One Meaning

Setiap requirement harus menjelaskan satu kebutuhan yang dapat dipahami dan diuji.

Requirement yang terlalu luas harus dipecah.

3.3 Testable Requirements

Setiap requirement harus memiliki acceptance criteria yang dapat diverifikasi.

Kata-kata seperti "cepat", "bagus", "profesional", dan "mudah" harus diterjemahkan menjadi kriteria yang dapat dinilai.

3.4 Bidirectional Links

Setiap hubungan antarartefak harus menggunakan identifier yang dapat ditelusuri.

Jangan hanya mengandalkan nama file atau judul dokumen.

3.5 Evidence-Based Completion

Status completed tidak boleh diberikan hanya karena kode sudah ditulis.

Harus tersedia bukti yang sesuai, seperti:

- Test result.
- Code review.
- API verification.
- Integration test.
- Security test.
- Deployment evidence.
- Human approval jika diwajibkan.

4. Requirement Categories

Prefix| Kategori| Deskripsi
BR| Business Requirement| Tujuan dan kebutuhan bisnis
PR| Product Requirement| Kemampuan produk
FR| Functional Requirement| Perilaku sistem
NFR| Non-Functional Requirement| Kualitas dan batasan sistem
UX| User Experience| Interaksi dan pengalaman pengguna
SEC| Security Requirement| Keamanan
DATA| Data Requirement| Integritas dan pengelolaan data
AI| AI Requirement| Orchestration, generation, dan AI governance
OPS| Operational Requirement| Deployment dan operasi
QC| Quality Requirement| Validasi hasil produksi
INT| Integration Requirement| Integrasi antardomain dan provider
COMP| Compliance Requirement| Kewajiban hukum dan kebijakan yang berlaku

5. Traceability Hierarchy

Level 1: Business Objective

Menjelaskan mengapa MovieAIProducer dibangun.

Contoh:

- BO-001: Mempercepat proses produksi film berbantuan AI.
- BO-002: Menjaga konsistensi kreatif dan visual.
- BO-003: Mengurangi pekerjaan produksi berulang.
- BO-004: Menghasilkan workflow produksi yang dapat direproduksi.
- BO-005: Menyediakan sistem produksi yang dapat dikembangkan dan dipelihara.

Level 2: Business Requirement

Menjelaskan hasil bisnis yang harus dicapai.

Contoh:

- BR-PROD-001: Sistem harus mendukung alur produksi dari creative brief hingga final delivery.
- BR-CONT-001: Sistem harus menjaga konsistensi karakter dan lingkungan antarscene.
- BR-AI-001: Sistem harus mendukung penggunaan beberapa provider AI melalui integrasi yang terkontrol.

Level 3: Product Requirement

Menjelaskan kemampuan yang dibutuhkan pengguna.

Contoh:

- PR-MPB-001: Pengguna dapat mengelola Master Production Bible.
- PR-SCENE-001: Pengguna dapat mengelola scene dan shot.
- PR-AI-001: Pengguna dapat membuat generation request.
- PR-QC-001: Pengguna dapat memeriksa kualitas hasil produksi.

Level 4: Functional Requirement

Menjelaskan perilaku sistem secara spesifik.

Contoh:

- FR-MPB-001: Sistem harus membuat revisi MPB baru.
- FR-MPB-002: Sistem harus menyimpan riwayat revisi.
- FR-MPB-003: Sistem harus menyediakan approval gate.
- FR-AI-001: Sistem harus memvalidasi capability model sebelum generation.
- FR-ASSET-001: Sistem harus menyimpan metadata dan provenance hasil generation.

Level 5: Implementation & Verification

Menghubungkan requirement dengan:

- Domain owner.
- ADR.
- Data model.
- API contract.
- Event contract.
- Error contract.
- Implementation task.
- Automated test.
- Human review.
- Release evidence.

6. Canonical Requirement Registry

Setiap requirement harus memiliki metadata berikut:

Field| Keterangan
Requirement ID| Identifier unik
Title| Nama requirement
Description| Penjelasan
Category| Jenis requirement
Business objective| Tujuan bisnis terkait
Priority| Prioritas
Domain owner| Pemilik
Source document| Sumber kebutuhan
ADR reference| Keputusan arsitektur
Data reference| Model atau entitas terkait
API reference| Endpoint atau contract
Event reference| Event terkait
Task reference| Implementation task
Test reference| Test case
Acceptance criteria| Kriteria penerimaan
Status| Lifecycle
Evidence| Bukti penyelesaian

7. Canonical Traceability Matrix

Matriks berikut adalah baseline kebutuhan tingkat tinggi. Ini belum merupakan daftar requirement lengkap dari seluruh BRD dan PRD.

Requirement ID| Requirement| Domain| Architecture Reference| Verification
BR-PROD-001| End-to-end production workflow| Workflow| ADR-0005| Workflow integration test
FR-PROJ-001| Project creation and management| Project| CDA-0002| Project API test
FR-MPB-001| MPB revision management| MPB| ADR-0004| Revision test
FR-MPB-002| MPB approval workflow| MPB| ADR-0004, ADR-0011| Authorization test
FR-MPB-003| Immutable production snapshots| MPB| ADR-0004| Snapshot integrity test
FR-STORY-001| Story and screenplay management| Story| CDA-0002| Story domain test
FR-CHAR-001| Character identity and state management| Character| ADR-0009| Continuity test
FR-SCENE-001| Scene and shot management| Scene & Shot| CDA-0002| Scene API test
FR-WF-001| Workflow state management| Workflow| ADR-0005| State transition test
FR-JOB-001| Persistent asynchronous jobs| Jobs| ADR-0007| Job recovery test
FR-AI-001| AI generation orchestration| AI| ADR-0003| Orchestration test
FR-PROV-001| Provider adapter integration| Provider| ADR-0003| Provider contract test
FR-PROMPT-001| Structured prompt compilation| Prompt| ADR-0008| Compiler test
FR-ASSET-001| Asset registration and versioning| Asset| ADR-0012| Asset lifecycle test
FR-CONT-001| Continuity validation| Continuity| ADR-0009| Continuity test
FR-QC-001| Multi-layer quality control| QC| ADR-0010| QC test
FR-EDITOR-001| Editorial timeline management| Editorial| CDA-0002| Editorial test
FR-DELIVERY-001| Final delivery validation| Delivery| ADR-0014| Delivery integration test
NFR-SEC-001| Tenant isolation| Identity| ADR-0011| Security isolation test
NFR-OBS-001| Correlation-based observability| Observability| ADR-0013| Trace propagation test
NFR-REL-001| Reliable event processing| Integration| CDA-0004| Outbox and idempotency test
NFR-ERR-001| Canonical error handling| Cross-domain| CDA-0005| Error contract test
NFR-REC-001| Backup and recovery| Operations| BACKUP_RECOVERY.md| Recovery drill
NFR-DEP-001| Reproducible deployment| Operations| ADR-0014| Deployment verification

Setiap baris harus dipecah menjadi requirement spesifik saat BRD dan PRD diekstraksi secara lengkap.

8. Domain-to-Requirement Mapping

Domain| Requirement Scope| Owner
D-001 Identity & Access| Authentication, authorization, tenant isolation| Identity
D-002 Project Management| Project lifecycle| Project
D-003 Creative Development| Creative brief and direction| Creative
D-004 Story Architecture| Story and screenplay| Story
D-005 Character Management| Character identity and states| Character
D-006 Production Design| Environment and props| Production Design
D-007 MPB Management| Production specification authority| MPB
D-008 Cinematography| Camera and lens configuration| Cinematography
D-009 Lighting| Lighting specification| Lighting
D-010 Performance & Audio| Acting, dialogue and sound| Performance
D-011 Motion Engineering| Motion and physical behavior| Motion
D-012 Storyboard & Previs| Previsualization| Previs
D-013 Scene & Shot Management| Scene and shot structure| Scene & Shot
D-014 Workflow Engine| Production workflow| Workflow
D-015 Job Processing| Technical job execution| Jobs
D-016 AI Orchestration| AI task coordination| AI
D-017 Provider Integration| External AI providers| Provider
D-018 Prompt Compilation| Canonical prompt IR and compilation| Prompt
D-019 Asset Management| Media asset lifecycle| Asset
D-020 Continuity Engine| Production continuity| Continuity
D-021 Quality Control| Production quality validation| QC
D-022 Editorial| Editing and timeline| Editorial
D-023 Delivery| Final package and publication| Delivery
D-024 Notifications| User notifications| Notifications
D-025 Observability| Logs, metrics and traces| Observability
D-026 Audit Governance| Accountability and audit records| Audit
D-027 Administration| Configuration and policy| Administration

Setiap domain harus memiliki requirement owner yang jelas, tetapi requirement lintas domain dapat memiliki beberapa dependency.

9. ADR Traceability

ADR harus dihubungkan dengan requirement yang menjadi alasan keputusan tersebut.

ADR| Decision| Requirement Relationship
ADR-0001| Modular Monolith + Clean Architecture| Maintainability, modularity, scalability
ADR-0002| Domain-oriented structure| Domain ownership
ADR-0003| Provider adapter system| Multi-provider integration
ADR-0004| Master Production Bible| Creative and production authority
ADR-0005| Production workflow engine| End-to-end workflow
ADR-0006| Data storage strategy| Data integrity and persistence
ADR-0007| Async job processing| Long-running execution
ADR-0008| Prompt compilation engine| Provider-aware prompt generation
ADR-0009| Continuity engine| Character and scene consistency
ADR-0010| QC engine| Production quality
ADR-0011| Authentication and authorization| Security and access control
ADR-0012| Asset storage architecture| Media asset management
ADR-0013| Observability stack| Monitoring and diagnostics
ADR-0014| Deployment strategy| Reproducible release
ADR-0015| Frontend architecture| Usable production workspace

ADR reference alone tidak membuktikan requirement telah diimplementasikan.

10. API, Data, Event & Error Traceability

Setiap functional requirement yang membutuhkan interaksi sistem harus memiliki kontrak yang sesuai.

10.1 Data

Requirement harus dihubungkan dengan:

- Entity.
- Aggregate.
- Primary ownership.
- Relationship.
- Constraints.
- Lifecycle.
- Migration.
- Retention.

10.2 API

Requirement harus dihubungkan dengan:

- API operation.
- Request schema.
- Response schema.
- Authentication.
- Authorization.
- Error responses.
- Idempotency jika relevan.

10.3 Event

Requirement yang memerlukan komunikasi antardomain harus mengacu pada CDA-0004.

10.4 Error

Requirement yang memerlukan failure handling harus mengacu pada CDA-0005.

Tidak semua requirement membutuhkan API atau event. Tandai "Not Applicable" beserta alasannya jika memang tidak relevan.

11. Task Traceability

Setiap implementation task harus merujuk minimal:

- Requirement ID.
- Domain owner.
- Scope.
- Dependencies.
- Acceptance criteria.
- Test reference.
- Documentation reference.

Task tanpa requirement dapat diterima untuk pekerjaan maintenance atau technical debt, tetapi harus memiliki justification dan owner.

Task tidak boleh dianggap selesai hanya karena branch atau commit sudah dibuat.

12. Test Traceability

Setiap requirement yang dapat diuji harus memiliki test reference.

Kategori pengujian:

1. Unit test.
2. Integration test.
3. Contract test.
4. End-to-end test.
5. Security test.
6. Performance test.
7. Resilience test.
8. Accessibility test.
9. AI quality evaluation.
10. Human acceptance test.

AI quality requirement tidak boleh hanya dinilai dengan unit test deterministik.

Gunakan evaluation dataset, rubric, threshold yang disetujui, human review, dan provenance sesuai kebutuhan.

Test result harus menyimpan:

- Requirement ID.
- Test ID.
- Test version.
- Environment.
- Commit atau artifact reference.
- Execution timestamp.
- Result.
- Evidence.
- Failure details jika ada.

13. Requirement Lifecycle

Status requirement:

- Proposed
- Under Review
- Accepted
- Planned
- In Progress
- Implemented
- Verified
- Released
- Deprecated
- Rejected

Definisi:

Proposed: Kebutuhan baru diajukan.

Under Review: Sedang dianalisis.

Accepted: Kebutuhan disetujui.

Planned: Masuk backlog implementasi.

In Progress: Pengerjaan berlangsung.

Implemented: Implementasi tersedia tetapi belum seluruhnya diverifikasi.

Verified: Acceptance criteria lulus berdasarkan bukti.

Released: Tersedia pada release yang ditentukan.

Deprecated: Tidak lagi direkomendasikan.

Rejected: Tidak diterima dengan alasan yang tercatat.

Penting:

- Implemented tidak sama dengan Verified.
- Verified tidak sama dengan Released.
- Draft documentation tidak sama dengan implementation.
- Test pass tidak otomatis membuktikan seluruh acceptance criteria terpenuhi.

14. Priority & Risk

Prioritas requirement:

- P0: Critical. Tanpa ini sistem tidak dapat memenuhi fungsi utama atau memiliki risiko keamanan/integritas yang tidak dapat diterima.
- P1: High. Dibutuhkan untuk MVP atau workflow utama.
- P2: Medium. Meningkatkan kapabilitas dan efisiensi.
- P3: Low. Enhancement atau kebutuhan lanjutan.

Setiap requirement juga harus memiliki:

- Business impact.
- Technical risk.
- Security impact.
- Dependency impact.
- Cost impact.
- Delivery estimate jika tersedia.

Jangan menggunakan priority sebagai pengganti severity atau risk.

15. Change Impact Analysis

Setiap perubahan requirement harus melalui impact analysis.

Periksa:

1. Business objective.
2. Related requirements.
3. Domain ownership.
4. ADR.
5. Data model.
6. API contracts.
7. Event contracts.
8. Error contracts.
9. Workflow dependencies.
10. Security and authorization.
11. Test coverage.
12. Documentation.
13. Deployment and migration.
14. Existing production data.

Perubahan pada MPB, prompt compilation, provider capability, continuity, atau QC dapat berdampak pada banyak scene dan asset.

Dampak harus dinilai sebelum perubahan disetujui.

Requirement yang sudah released tidak boleh diubah secara diam-diam tanpa change record dan evaluasi compatibility.

16. Traceability Coverage Metrics

Metrik minimum:

Requirement Coverage

Persentase requirement yang memiliki owner dan acceptance criteria.

Architecture Coverage

Persentase requirement yang memiliki ADR atau alasan eksplisit bahwa ADR tidak diperlukan.

Implementation Coverage

Persentase requirement accepted yang memiliki implementation task.

Test Coverage

Persentase requirement yang memiliki test reference.

Verification Coverage

Persentase requirement yang memiliki bukti acceptance test berhasil.

Release Coverage

Persentase requirement yang telah diverifikasi dan dipetakan ke release.

Formula:

"Coverage = (Requirements with valid trace / Applicable requirements) × 100%"

Setiap metrik harus menyertakan denominator dan daftar pengecualian.

Target 100% dapat ditetapkan untuk requirement P0 dan P1 sebelum release, tetapi target keseluruhan harus disesuaikan dengan fase produk dan risiko.

Jangan menyembunyikan requirement yang belum terpetakan dengan mengeluarkannya dari denominator tanpa alasan.

17. Traceability Governance

Tanggung jawab:

Role| Responsibility
Product Owner| Business dan product requirement
Product Analyst| Requirement definition
Architect| Architecture mapping
Domain Owner| Domain contracts dan implementation scope
Tech Lead| Task dan implementation traceability
QA Lead| Test coverage dan verification
Security Owner| Security requirement validation
DevOps/Operations| Deployment dan release evidence
Release Owner| Final release traceability

Satu orang dapat menjalankan beberapa peran pada MVP, tetapi tanggung jawabnya tetap harus jelas.

18. Tooling & Repository Strategy

Repository harus menyediakan satu sumber resmi untuk requirement registry.

Pilihan implementasi awal:

- Markdown registry untuk MVP.
- YAML atau JSON untuk metadata terstruktur.
- Automated validation script untuk identifier dan broken references.
- Test report untuk verification evidence.
- Release manifest untuk requirement yang disertakan dalam release.

Contoh struktur logis:

docs/
  requirements/
    README.md
    business/
    product/
    functional/
    non-functional/
    security/
    integration/
    registry/
      requirements.yaml
      traceability.yaml
  architecture/
    adr/
    cda/
  testing/
  releases/

scripts/
  validate_requirement_ids.py
  validate_traceability.py

Struktur tersebut merupakan proposal. Jangan membuat atau memindahkan file sebelum repository discovery.

19. Automated Validation

Automated validator sebaiknya memeriksa:

- Duplicate requirement ID.
- Invalid requirement status.
- Missing owner.
- Missing acceptance criteria.
- Broken document references.
- Broken ADR references.
- Broken task references.
- Broken test references.
- Missing evidence for Verified status.
- Missing release reference for Released status.
- Deprecated requirement yang masih digunakan tanpa justifikasi.

Validator harus menghasilkan laporan yang dapat dibaca manusia dan CI.

Kegagalan validasi requirement kritis harus dapat memblokir release sesuai release policy.

20. MVP Implementation Sequence

Phase 1: Requirement Inventory

- Ekstrak requirement dari BRD.
- Ekstrak requirement dari PRD.
- Identifikasi duplikasi.
- Identifikasi konflik.
- Berikan ID unik.

Phase 2: Architecture Mapping

- Hubungkan requirement dengan domain.
- Hubungkan requirement dengan ADR.
- Hubungkan requirement dengan data dan API.
- Hubungkan requirement dengan event dan error contract.

Phase 3: Execution Mapping

- Hubungkan requirement dengan TASKS.md.
- Tetapkan dependency.
- Tetapkan acceptance criteria.
- Tentukan test strategy.

Phase 4: Verification Mapping

- Hubungkan test case.
- Simpan test evidence.
- Verifikasi hasil.
- Hubungkan ke release.

Phase 5: Automation

- Bangun requirement registry.
- Tambahkan validator.
- Integrasikan dengan CI.
- Buat traceability report.

21. Acceptance Criteria

- [ ] Semua requirement memiliki ID unik.
- [ ] Semua requirement memiliki sumber.
- [ ] Semua requirement memiliki kategori.
- [ ] Semua requirement accepted memiliki owner.
- [ ] Requirement penting memiliki acceptance criteria.
- [ ] Business objective terhubung ke product requirement.
- [ ] Product requirement terhubung ke functional requirement.
- [ ] Functional requirement terhubung ke domain.
- [ ] Architecture dependency dapat ditelusuri.
- [ ] Implementation task dapat ditelusuri.
- [ ] Test case dapat ditelusuri.
- [ ] Verified requirement memiliki evidence.
- [ ] Released requirement memiliki release reference.
- [ ] Broken references dapat dideteksi otomatis.
- [ ] Change impact dapat dianalisis.
- [ ] Coverage metrics memiliki denominator yang jelas.
- [ ] Requirement yang belum terpenuhi dapat dilaporkan.

22. Risks

ID| Risiko| Mitigasi
CDA6-R01| Requirement hilang| Canonical registry
CDA6-R02| Duplicate requirement| Unique ID validation
CDA6-R03| Requirement tidak dapat diuji| Acceptance criteria
CDA6-R04| Dokumentasi tidak sesuai implementasi| Repository audit
CDA6-R05| Test tidak mewakili requirement| Bidirectional mapping
CDA6-R06| Perubahan tidak diketahui dampaknya| Impact analysis
CDA6-R07| Klaim selesai tanpa bukti| Evidence-based status
CDA6-R08| Requirement tidak terhubung ke release| Release manifest
CDA6-R09| Traceability menjadi pekerjaan manual berlebihan| Automated validation
CDA6-R10| Coverage metrics menyesatkan| Transparent denominator

23. Cross-Document Dependencies

Wajib direkonsiliasi dengan:

- BRD.md
- PRD.md
- ARCHITECTURE.md
- TASKS.md
- DATA_MODEL.md
- API_SPEC.md
- PROVIDER_MATRIX.md
- SECURITY.md
- ERROR_HANDLING.md
- TEST_STRATEGY.md
- DEPLOYMENT.md
- OBSERVABILITY.md
- BACKUP_RECOVERY.md
- CHANGELOG.md
- ADR-0001 sampai ADR-0015
- CDA-0001 sampai CDA-0005

Jika ditemukan requirement yang tidak memiliki pemilik, konflik, atau acceptance criteria, masukkan ke issue register. Jangan menganggapnya selesai.

24. Governance & Final Status

Status: PROPOSED

Dokumen ini menetapkan baseline traceability untuk MovieAIProducer.

Belum berarti requirement telah diekstrak secara lengkap, seluruh hubungan sudah tervalidasi, atau validator telah dibuat.

Sebelum Accepted:

1. Audit repository.
2. Ekstrak requirement aktual dari BRD dan PRD.
3. Cocokkan dengan TASKS.
4. Cocokkan dengan ADR dan CDA.
5. Periksa API dan data contracts.
6. Tetapkan test references.
7. Validasi evidence.
8. Buat laporan traceability.
9. Selesaikan orphan requirements dan broken links.

Final Decision Principle:

No requirement without an owner.
No critical requirement without acceptance criteria.
No implementation claim without evidence.
No release claim without verification.

---

End of CDA-0006
