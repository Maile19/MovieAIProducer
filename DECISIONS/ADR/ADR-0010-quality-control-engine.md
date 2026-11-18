# ADR-0010: Quality Control Engine

- Project: MovieAIProducer
- ADR ID: ADR-0010
- Title: Quality Control Engine
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Decision Owners: Product Owner, Technical Architect, Production Director
- Related ADRs: ADR-0001, ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009

---

1. Context

MovieAIProducer membutuhkan sistem Quality Control (QC) yang dapat mengevaluasi kualitas hasil produksi film pada seluruh tahapan, mulai dari konsep kreatif hingga final delivery.

Kualitas film tidak dapat diukur hanya berdasarkan resolusi, frame rate, atau skor AI. Hasil produksi harus memenuhi standar naratif, visual, penyutradaraan, performa, kontinuitas, audio, dan spesifikasi teknis.

Sistem QC harus dapat menjawab:

1. Apakah hasil produksi sesuai dengan visi kreatif?
2. Apakah karakter dan lingkungan konsisten?
3. Apakah gerakan manusia terlihat alami?
4. Apakah kamera dan pencahayaan mendukung tujuan adegan?
5. Apakah dialog, ekspresi, dan audio tersinkronisasi?
6. Apakah hasil video memenuhi standar teknis?
7. Apakah terdapat kesalahan yang mengharuskan regenerasi?
8. Apakah hasil sudah layak disetujui dan diteruskan ke tahap berikutnya?

QC harus menggabungkan validasi deterministik, pemeriksaan berbasis aturan, analisis AI, dan penilaian manusia.

2. Problem Statement

Tanpa QC Engine yang terstruktur, sistem berisiko menghasilkan:

- Video dengan kualitas teknis baik tetapi gagal secara naratif.
- Perubahan identitas karakter antarscene.
- Gerakan tubuh, wajah, atau objek yang tidak realistis.
- Kamera yang tidak sesuai arahan sutradara.
- Pencahayaan dan warna yang tidak konsisten.
- Dialog yang tidak sinkron dengan gerakan bibir.
- Artefak visual, flicker, distorsi, dan frame rusak.
- Audio clipping, noise, atau ketidakseimbangan.
- Hasil yang dianggap selesai meskipun belum memenuhi standar produksi.

Skor agregat saja tidak cukup. Satu kegagalan kritis tidak boleh disembunyikan oleh nilai tinggi pada dimensi lain.

3. Decision

MovieAIProducer akan menggunakan Multi-Layer Quality Control Architecture.

Sistem menggabungkan empat metode pemeriksaan:

1. Deterministic Technical Validation.
2. Rule-Based Quality Validation.
3. AI-Assisted Perceptual and Creative Analysis.
4. Human Review and Approval.

QC Engine menjadi layanan domain tersendiri dan terintegrasi dengan Production Workflow Engine, Continuity Engine, Master Production Bible, Asset Management, dan Provider Adapter System.

QC bukan bagian dari Continuity Engine. Continuity merupakan salah satu dimensi pemeriksaan QC yang lebih luas.

4. Quality Standards

MovieAIProducer menetapkan empat standar kualitas utama.

4.1 Visual Excellence

Menilai kualitas visual hasil produksi:

- Visual clarity.
- Composition and framing.
- Character identity consistency.
- Environment consistency.
- Wardrobe and prop consistency.
- Lighting quality.
- Color consistency.
- Natural facial expressions.
- Natural body movement.
- Motion smoothness.
- Physical plausibility.
- Artifact detection.
- Flicker and distortion.
- Visual coherence across shots.

4.2 Directorial Excellence

Menilai keberhasilan penerjemahan visi sutradara:

- Story intention.
- Scene objectives.
- Emotional progression.
- Character performance.
- Acting direction.
- Camera intention.
- Shot selection.
- Scene pacing.
- Dialogue delivery.
- Blocking and staging.
- Dramatic readability.
- Genre consistency.
- Audience comprehension.

4.3 Technical Excellence

Menilai kualitas teknis:

- Resolution.
- Aspect ratio.
- Frame rate.
- Codec and container.
- Duration.
- Frame integrity.
- Audio sample rate.
- Audio channels.
- Loudness.
- Clipping.
- Synchronization.
- File integrity.
- Encoding quality.
- Playback compatibility.
- Delivery specification compliance.

4.4 Production Excellence

Menilai kesiapan produksi dan kelayakan hasil:

- Compliance with approved MPB.
- Continuity validation.
- Asset provenance.
- Production requirement completion.
- Approved revisions.
- Workflow completion.
- Rework status.
- Delivery readiness.
- Required human approvals.
- Traceability of production decisions.

Keempat standar tersebut menjadi kerangka utama seluruh rubric QC.

5. Quality Control Scope

QC harus tersedia pada enam tingkat.

Level| Scope| Contoh
Project| Keseluruhan film| Konsistensi visi dan kualitas
Stage| Tahap produksi| Kesiapan storyboard
Scene| Satu adegan| Narasi, emosi, kontinuitas
Shot| Satu shot| Kamera, gerakan, komposisi
Asset| Satu aset| Video, audio, gambar
Final Film| Film final| Master delivery validation

Sistem harus dapat menjalankan pemeriksaan pada satu level maupun secara hierarkis.

Hasil QC tingkat shot dapat diagregasi menjadi scene, stage, dan project, tetapi temuan kritis tidak boleh hilang akibat agregasi.

6. QC Architecture

Komponen utama:

6.1 QC Orchestrator

Mengelola siklus pemeriksaan:

- Menerima permintaan QC.
- Menentukan policy dan rubric.
- Mengidentifikasi objek yang diperiksa.
- Membuat QC run.
- Menjadwalkan validator.
- Mengumpulkan hasil.
- Menghitung skor.
- Mengidentifikasi blockers.
- Menentukan rekomendasi.
- Mengirim hasil ke workflow.

6.2 QC Policy Registry

Menyimpan aturan pemeriksaan berdasarkan:

- Project.
- Production stage.
- Asset type.
- Scene type.
- Shot type.
- Provider and model.
- Delivery target.
- Quality standard.

Policy harus memiliki versi dan riwayat perubahan.

6.3 Deterministic Validators

Melakukan pemeriksaan teknis yang dapat diukur secara objektif.

Contoh:

- File dapat dibaca.
- Codec sesuai.
- Resolusi sesuai.
- Frame rate sesuai.
- Durasi sesuai.
- Audio channel sesuai.
- File checksum valid.
- File tidak rusak.
- Tidak terdapat frame kosong yang tidak diperbolehkan.

Validator deterministik tidak boleh digantikan oleh penilaian AI jika pengujian teknis langsung tersedia.

6.4 Rule-Based Validators

Memeriksa kesesuaian dengan aturan produksi.

Contoh:

- Shot menggunakan aspect ratio yang ditentukan.
- Karakter menggunakan wardrobe yang disetujui.
- Scene memiliki seluruh shot wajib.
- Dialog tidak melebihi batas yang ditetapkan proyek.
- Adegan memenuhi persyaratan storyboard.
- Asset mempunyai referensi MPB yang valid.

6.5 AI Perceptual Analyzer

Menganalisis aspek yang sulit diukur menggunakan aturan deterministik.

Contoh:

- Naturalness of human motion.
- Facial expression coherence.
- Character visual similarity.
- Camera movement quality.
- Lighting consistency.
- Visual artifacts.
- Lip-sync quality.
- Emotional performance.
- Narrative readability.

Hasil AI harus menyertakan bukti, tingkat confidence, model yang digunakan, dan batasan analisis.

AI tidak boleh mengklaim kepastian objektif untuk penilaian perseptual yang bersifat probabilistik.

6.6 Human Review Interface

Memungkinkan reviewer:

- Menonton video atau shot.
- Melihat timeline temuan.
- Membandingkan dengan referensi.
- Meninjau bukti AI.
- Memberikan komentar.
- Menerima atau menolak rekomendasi.
- Menyetujui atau menolak hasil QC.
- Meminta revisi.
- Mencatat alasan keputusan.

AI tidak memiliki kewenangan menyetujui hasil produksi final atas nama manusia.

7. QC Evaluation Dimensions

Rubric QC minimal mencakup:

Narrative and Story

- Story coherence.
- Scene objective fulfillment.
- Narrative continuity.
- Dramatic progression.
- Pacing.
- Dialogue clarity.
- Scene readability.

Character and Acting

- Identity preservation.
- Facial consistency.
- Body proportions.
- Emotional authenticity.
- Natural expressions.
- Gesture coherence.
- Acting intention.
- Performance consistency.

Cinematography

- Shot composition.
- Camera angle.
- Camera movement.
- Lens intent.
- Framing.
- Focus.
- Depth of field.
- Visual storytelling.

Lighting and Color

- Exposure.
- Lighting direction.
- Shadow coherence.
- Color continuity.
- Highlight control.
- Skin tone rendering.
- Atmospheric consistency.

Motion and Physics

- Body mechanics.
- Object interaction.
- Weight and balance.
- Momentum.
- Collision plausibility.
- Motion smoothness.
- Temporal consistency.
- Unintended deformation.

Continuity

- Character state.
- Wardrobe.
- Props.
- Environment.
- Spatial relationships.
- Temporal relationships.
- Shot-to-shot consistency.

Continuity Engine menjadi sumber validasi kontinuitas yang terintegrasi dengan QC.

Audio

- Dialogue intelligibility.
- Lip-sync.
- Audio-video synchronization.
- Loudness.
- Clipping.
- Background noise.
- Ambience consistency.
- Music and SFX balance.

Technical Delivery

- Codec.
- Container.
- Resolution.
- Aspect ratio.
- Frame rate.
- Duration.
- Audio format.
- File integrity.
- Playback validation.
- Delivery target compliance.

Tidak semua dimensi wajib berlaku pada setiap asset. QC Policy menentukan dimensi yang relevan.

8. Scoring Architecture

QC menggunakan skor terstruktur, bukan satu angka tanpa penjelasan.

Setiap dimensi dapat memiliki:

- Raw score.
- Normalized score.
- Weight.
- Evidence references.
- Confidence.
- Severity.
- Evaluator type.
- Rubric version.

Skor agregat dapat dihitung menggunakan:

"Overall Score = Σ (Dimension Score × Dimension Weight)"

Bobot harus dikonfigurasi melalui rubric yang sesuai dengan jenis produksi dan target delivery.

Tidak ada threshold universal yang berlaku untuk seluruh film, scene, dan asset.

8.1 Critical Blocker Override

Kegagalan kritis harus mengalahkan skor agregat.

Contoh:

- File video tidak dapat diputar.
- Asset menggunakan karakter yang salah.
- Adegan melanggar keputusan kreatif yang telah disetujui.
- Audio utama tidak tersedia ketika diwajibkan.
- Hasil tidak memenuhi spesifikasi delivery wajib.
- Terdapat kerusakan visual atau teknis yang membuat hasil tidak layak digunakan.

Skor 95/100 tidak dapat menghasilkan status PASS jika masih terdapat critical blocker.

8.2 Severity Classification

- CRITICAL: Menghalangi kelanjutan atau delivery.
- HIGH: Memerlukan perbaikan sebelum approval.
- MEDIUM: Mengurangi kualitas dan perlu dievaluasi.
- LOW: Perbaikan minor.
- INFO: Catatan tanpa kewajiban perbaikan.

8.3 Confidence

Confidence merupakan tingkat keyakinan evaluator terhadap temuannya.

Confidence tidak sama dengan severity atau score.

Contoh: AI dapat mendeteksi kemungkinan lip-sync error dengan confidence 0.62. Temuan tersebut perlu diverifikasi manusia sebelum menjadi keputusan final jika bukti belum cukup.

9. QC Data Model

Entitas konseptual:

QCRun

Mencatat satu proses pemeriksaan:

- id.
- project_id.
- target_type.
- target_id.
- qc_policy_version.
- rubric_version.
- mpb_snapshot_id.
- status.
- started_at.
- completed_at.
- evaluator_summary.

QCResult

Menyimpan hasil pemeriksaan:

- id.
- qc_run_id.
- dimension.
- score.
- normalized_score.
- weight.
- confidence.
- status.

QCFinding

Menyimpan temuan:

- id.
- qc_run_id.
- target_type.
- target_id.
- dimension.
- severity.
- confidence.
- description.
- evidence_reference.
- timestamp_start.
- timestamp_end.
- recommended_action.
- review_status.

QCEvidence

Menyimpan referensi bukti:

- id.
- finding_id.
- evidence_type.
- asset_id.
- timestamp.
- frame_reference.
- source_reference.
- evaluator_metadata.

QCRecommendation

Menyimpan saran tindakan:

- id.
- finding_id.
- action_type.
- priority.
- suggested_changes.
- dependency_impact.
- status.

QCApproval

Menyimpan keputusan manusia:

- id.
- qc_run_id.
- reviewer_id.
- decision.
- reason.
- approved_at.
- policy_context.

QCRubricVersion

Menyimpan versi rubric:

- id.
- rubric_name.
- version.
- criteria.
- weights.
- thresholds.
- effective_at.
- created_by.

Struktur tersebut adalah model konseptual. Skema database fisik harus mengikuti keputusan implementasi ADR-0006 dan audit repository.

10. MPB and Production Provenance

Setiap QC run harus terhubung dengan konteks produksi yang tepat.

Minimal referensi:

- MPB snapshot.
- Relevant entity revisions.
- Scene and shot identifiers.
- Prompt version.
- Prompt compiler version.
- Provider.
- Model identifier and version.
- Generation job.
- Source assets.
- Generated asset.
- QC policy and rubric versions.

QC harus dapat menjawab:

- Hasil mana yang diperiksa?
- Berdasarkan spesifikasi versi berapa?
- Menggunakan model apa?
- Menggunakan prompt versi berapa?
- Temuan berasal dari validator apa?
- Siapa yang memberikan approval?
- Apakah hasil pernah direvisi?

Riwayat QC tidak boleh diubah diam-diam.

11. QC Workflow Integration

Integrasi dengan ADR-0005 dan ADR-0007.

Alur standar:

1. Production task menghasilkan asset.
2. Asset disimpan dan diverifikasi.
3. Workflow membuat QC job.
4. QC Orchestrator menjalankan validator.
5. AI analyzer melakukan analisis bila diperlukan.
6. Hasil pemeriksaan dikumpulkan.
7. Critical blocker diperiksa.
8. Reviewer menerima temuan yang memerlukan keputusan manusia.
9. Sistem menentukan status QC.
10. Workflow menerima hasil.
11. Asset dapat diteruskan, ditolak, atau diminta untuk rework.

11.1 QC States

- PENDING.
- QUEUED.
- RUNNING.
- AWAITING_REVIEW.
- PASSED.
- PASSED_WITH_NOTES.
- FAILED.
- BLOCKED.
- CANCEL_REQUESTED.
- CANCELLED.
- ERROR.

Status harus memiliki transisi yang tervalidasi.

11.2 Rework Handling

Jika QC gagal:

- Temuan disimpan.
- Rekomendasi dibuat.
- Workflow dapat membuat rework task.
- Revisi harus terhubung dengan temuan.
- Asset baru mendapat identitas dan provenance baru.
- QC dijalankan ulang.
- Hasil sebelumnya tetap tersedia.

Jika perubahan memengaruhi asset turunan, sistem harus mengevaluasi dependency dan menentukan apakah QC sebelumnya masih berlaku.

Perubahan tidak boleh menghapus riwayat approval secara otomatis.

12. Human Approval Policy

Human approval wajib untuk:

- Critical creative decisions.
- Final character identity acceptance.
- Major scene performance approval.
- Critical continuity overrides.
- Final film approval.
- Delivery master approval.
- Keputusan ketika bukti AI tidak cukup untuk penilaian yang dapat dipercaya.

Approval harus mencatat reviewer, keputusan, waktu, dan alasan.

AI dapat memberi rekomendasi, tetapi tidak dapat mengubah rekomendasi menjadi approval manusia.

13. Policy Configuration

QC harus dapat disesuaikan berdasarkan:

- Genre.
- Production type.
- Project requirements.
- Asset type.
- Scene complexity.
- Delivery platform.
- Resolution and frame rate targets.
- Provider capabilities.
- Quality tier.

Contoh: Film sinematik, film animasi, video pendek, dan iklan mungkin memerlukan rubric berbeda.

Threshold harus dapat dikalibrasi dan diberi versi. Perubahan rubric tidak boleh mengubah hasil QC historis.

14. Security and Governance

Ketentuan keamanan:

- RBAC untuk reviewer dan administrator.
- Private asset access.
- Signed URLs dengan masa berlaku terbatas bila diperlukan.
- Audit log untuk approval dan override.
- Validasi input dan metadata.
- Batas ukuran dan durasi asset.
- Isolasi proses media analysis.
- Proteksi terhadap file berbahaya.
- Rate limiting untuk endpoint analisis.
- Pembatasan akses terhadap evidence dan media.
- Retention policy untuk QC artifacts.
- Secret management untuk provider.
- Perlindungan data pengguna dan proyek.

QC tidak boleh memberikan akses publik terhadap asset privat hanya karena asset sedang dianalisis.

15. API Design

Contoh endpoint konseptual:

- "POST /api/v1/qc/runs"
- "GET /api/v1/qc/runs/{run_id}"
- "GET /api/v1/qc/runs/{run_id}/results"
- "GET /api/v1/qc/runs/{run_id}/findings"
- "POST /api/v1/qc/findings/{finding_id}/review"
- "POST /api/v1/qc/runs/{run_id}/approve"
- "POST /api/v1/qc/runs/{run_id}/rework"
- "GET /api/v1/qc/policies"
- "GET /api/v1/qc/rubrics"
- "GET /api/v1/qc/assets/{asset_id}/history"

Endpoint di atas merupakan rancangan awal dan belum menjadi kontrak API final. Detail request, response, authorization, dan error codes harus diselaraskan dengan API_SPEC.md.

16. Observability

QC Engine harus mencatat:

- QC run count.
- Pass/fail rate.
- Critical blocker rate.
- Average QC duration.
- AI analysis latency.
- Validator failure rate.
- Human review waiting time.
- Rework frequency.
- Cost per QC run.
- False-positive and false-negative review outcomes.
- Provider and model reliability.

Setiap QC run harus memiliki correlation ID dan traceable execution history.

17. MVP Scope

MVP tidak harus langsung mengimplementasikan semua jenis analisis AI.

Prioritas:

1. QC data model dan persistent QC runs.
2. Technical file validation.
3. Resolution, aspect ratio, frame rate, dan duration validation.
4. Audio format validation.
5. Rule-based MPB compliance.
6. Basic continuity findings integration.
7. QC finding and evidence storage.
8. Basic score and severity engine.
9. Human review and approval.
10. Workflow integration.
11. Rework task creation.
12. QC history and reporting.

AI perceptual analysis dapat diperkenalkan secara bertahap setelah jalur teknis dan review manusia terbukti stabil.

18. Implementation Sequence

Phase 1: Foundation

- Define QC domain contracts.
- Define policy and rubric versioning.
- Implement QC run lifecycle.
- Implement persistence.
- Implement authorization.

Phase 2: Deterministic Validation

- Implement media metadata extraction.
- Implement file integrity checks.
- Implement video validation.
- Implement audio validation.
- Implement delivery profile validation.

Phase 3: Findings and Scoring

- Implement finding registry.
- Implement evidence references.
- Implement severity classification.
- Implement score aggregation.
- Implement critical blocker override.

Phase 4: Human Review

- Implement reviewer interface.
- Implement review decisions.
- Implement approval audit trail.
- Implement override governance.

Phase 5: Workflow Integration

- Connect QC with production jobs.
- Connect QC with workflow states.
- Implement rework task generation.
- Implement dependency invalidation.
- Implement recovery and retry.

Phase 6: AI-Assisted Analysis

- Introduce provider-independent analysis contracts.
- Verify model capabilities.
- Implement selected perceptual analyzers.
- Store confidence and evidence.
- Evaluate false positives and false negatives.
- Add human review for uncertain results.

Phase 7: Reporting and Calibration

- Implement project-level QC dashboard.
- Calibrate rubrics.
- Measure review agreement.
- Monitor QC costs and performance.
- Refine policy versions.

19. Testing Requirements

Unit Tests

- Score aggregation.
- Severity classification.
- Critical blocker override.
- State transitions.
- Policy selection.
- Rubric versioning.
- Approval authorization.
- Finding lifecycle.

Integration Tests

- Asset to QC run.
- QC run to workflow.
- QC finding to rework task.
- MPB snapshot resolution.
- Evidence retrieval.
- Approval audit logging.

Media Validation Tests

- Valid and invalid video files.
- Corrupted media.
- Incorrect codec.
- Incorrect resolution.
- Incorrect frame rate.
- Incorrect aspect ratio.
- Missing audio.
- Audio clipping.
- Invalid duration.
- Unsupported formats.

AI Analysis Tests

- Confidence handling.
- Missing evidence.
- Analyzer timeout.
- Provider failure.
- Inconsistent analyzer outputs.
- False-positive review.
- Model version changes.

Security Tests

- Unauthorized approval.
- Cross-project asset access.
- Invalid evidence references.
- Malicious media uploads.
- Oversized media.
- Expired asset access.
- Audit log integrity.

End-to-End Tests

Generate one scene, store its asset, run QC, review findings, request rework, generate a revised asset, rerun QC, and approve the final result.

20. Risks and Mitigations

Risk| Mitigation
AI subjective assessment treated as fact| Store confidence, evidence, and evaluator type
High score hides critical defect| Critical blocker override
Excessive false positives| Human review and calibration
Different rubrics produce incomparable scores| Versioned rubrics and explicit context
QC delays production| Async execution and priority policies
Rework causes stale downstream assets| Dependency impact analysis
Expensive AI analysis| Selective analyzer execution and cost tracking
Historical results change unexpectedly| Immutable QC run records
Incorrect automatic approval| Explicit human approval gates

21. Consequences

Positive

- Quality decisions become traceable.
- Production defects can be identified systematically.
- Critical failures cannot be hidden by aggregate scores.
- Human and AI evaluation can work together.
- Rework becomes structured and measurable.
- Final delivery gains a consistent quality gate.
- QC policies can evolve without rewriting historical results.

Trade-offs

- Additional processing and storage costs.
- More complex workflow integration.
- Need for calibrated rubrics.
- Human review remains necessary.
- Perceptual AI analysis has inherent uncertainty.
- QC execution can increase production time.

22. Decision Validation Checklist

Before accepting this ADR, verify:

- [ ] QC is a separate domain capability.
- [ ] Four quality standards are represented.
- [ ] Six QC levels are supported.
- [ ] Deterministic and AI-assisted validation are separated.
- [ ] Rubrics and policies are versioned.
- [ ] Critical blocker override is implemented.
- [ ] Severity, confidence, and score are distinct.
- [ ] Findings retain evidence references.
- [ ] MPB snapshot provenance is preserved.
- [ ] Human approval is auditable.
- [ ] QC integrates with workflow and async jobs.
- [ ] Rework and dependency invalidation are traceable.
- [ ] Historical QC results remain immutable.
- [ ] MVP can be tested through one complete vertical workflow.

23. Review and Acceptance Conditions

This ADR can move from Proposed to Accepted when:

1. QC domain boundaries are agreed.
2. Scoring and blocker policy are approved.
3. Human approval responsibilities are defined.
4. Data ownership and persistence are reconciled with ADR-0006.
5. Workflow integration is reconciled with ADR-0005 and ADR-0007.
6. API contracts are reconciled with API_SPEC.md.
7. Security and observability requirements are reviewed.
8. Repository discovery confirms implementation feasibility.

Review this ADR if:

- The production quality model changes substantially.
- A new delivery standard requires different QC behavior.
- AI evaluation capabilities change significantly.
- QC becomes a separate distributed service.
- New regulatory or contractual requirements arise.

---

Final Principle:

Quality Control Engine must not merely assign scores to generated media. It must establish whether each production result satisfies its approved creative intent, continuity requirements, technical specifications, and delivery standards, with evidence and accountable approval.

A high score is not proof of quality. A passing result must be supported by valid checks, traceable evidence, and the required human decisions.