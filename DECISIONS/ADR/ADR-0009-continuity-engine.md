# ADR-0009: Continuity Engine

Project: MovieAIProducer
ADR ID: ADR-0009
Title: Continuity Engine
Version: 1.0
Status: Proposed
Date: 2026-11-19
Decision Owners: Product Architect / Creative Technical Lead

---

1. Context

MovieAIProducer menghasilkan film melalui banyak scene dan shot yang dapat diproduksi secara terpisah, menggunakan model AI dan provider yang berbeda.

Setiap shot harus tetap menjadi bagian dari satu kesatuan dunia cerita.

Continuity mencakup:

- Character identity.
- Facial appearance.
- Body proportions.
- Hair and makeup.
- Wardrobe.
- Character age and physical condition.
- Character emotional state.
- Props and object positions.
- Environment identity.
- Environment layout.
- Lighting conditions.
- Time of day.
- Weather and atmosphere.
- Camera direction.
- Screen direction.
- Spatial relationships.
- Action progression.
- Dialogue and audio continuity.
- Scene-to-scene transitions.

AI generation dapat menghasilkan variasi visual yang tidak diinginkan, meskipun prompt dan reference images serupa.

Karena itu, continuity harus dikelola sebagai bagian dari production architecture, bukan sekadar instruksi tambahan dalam prompt.

2. Problem Statement

Tanpa Continuity Engine, sistem berisiko mengalami:

- Wajah karakter berubah antar-shot.
- Kostum tidak sesuai timeline cerita.
- Prop berpindah posisi.
- Karakter berpindah lokasi tanpa transisi.
- Luka atau kondisi fisik menghilang.
- Pencahayaan berubah tanpa alasan.
- Arah gerak tidak konsisten.
- Screen direction terbalik.
- Environment memiliki layout berbeda.
- Properti muncul atau menghilang.
- Kondisi cuaca tidak konsisten.
- Dialog dan reaksi tidak sinkron.
- AI-generated footage tidak cocok saat editorial assembly.

Diperlukan engine yang dapat melacak, memvalidasi, dan mengelola perubahan kondisi produksi sepanjang timeline cerita.

3. Decision Drivers

1. Character identity preservation.
2. Visual consistency.
3. Narrative consistency.
4. Temporal consistency.
5. Spatial consistency.
6. Production reproducibility.
7. Reference asset management.
8. Change impact analysis.
9. Provider independence.
10. Human creative control.

4. Options Considered

Option A: Prompt-Only Continuity

Continuity dijaga dengan memasukkan deskripsi karakter dan environment ke setiap prompt.

Advantages:

- Sederhana.
- Mudah diimplementasikan.
- Tidak membutuhkan domain engine tambahan.

Disadvantages:

- Tidak memiliki state tracking.
- Sulit mendeteksi perubahan.
- Sangat bergantung pada interpretasi model.
- Tidak menyediakan audit atau impact analysis.

Decision: Rejected as the complete continuity architecture.

Option B: Reference Asset-Only Continuity

Continuity dijaga menggunakan reference images dan reference videos.

Advantages:

- Memberikan referensi visual langsung.
- Berguna untuk character dan environment consistency.

Disadvantages:

- Tidak mencakup seluruh continuity rules.
- Tidak menjelaskan temporal state.
- Tidak memvalidasi narrative progression.
- Tidak semua provider mendukung reference assets dengan cara yang sama.

Decision: Rejected as the sole solution.

Option C: State-Based Continuity Engine

Continuity dikelola menggunakan canonical entity states, temporal and spatial records, reference assets, constraints, dan validation rules.

Advantages:

- Mendukung visual dan narrative continuity.
- Memungkinkan automated validation.
- Mendukung impact analysis.
- Terintegrasi dengan MPB dan prompt compiler.
- Dapat bekerja lintas-provider.

Disadvantages:

- Membutuhkan data model yang lebih kompleks.
- Perlu rule definitions.
- Automated visual verification tetap memiliki keterbatasan.

Decision: Accepted.

5. Architecture Decision

MovieAIProducer menggunakan State-Based, Timeline-Aware Continuity Engine.

Continuity Engine bertanggung jawab untuk:

1. Menyimpan canonical continuity states.
2. Menentukan state sebelum dan sesudah setiap shot.
3. Mengelola temporal and spatial relationships.
4. Mengelola visual reference assets.
5. Menjalankan continuity validation.
6. Mendeteksi perubahan yang tidak diharapkan.
7. Menghasilkan continuity context untuk prompt compiler.
8. Melakukan impact analysis saat production specifications berubah.
9. Menyediakan continuity reports.
10. Mendukung human review dan approval.

Continuity Engine tidak menggantikan MPB.

MPB tetap menjadi Single Source of Truth untuk approved production specifications.

Continuity Engine mengelola interpretasi, hubungan, dan validasi continuity berdasarkan data tersebut.

6. Logical Architecture

          Master Production Bible
                    |
                    v
             Continuity Context
                    |
          +---------+---------+
          |         |         |
          v         v         v
      Character  Environment  Prop
        State       State     State
          |         |         |
          +---------+---------+
                    |
                    v
             Timeline Resolver
                    |
                    v
             Spatial Resolver
                    |
                    v
            Continuity Rules
                    |
                    v
           Continuity Validator
                    |
          +---------+---------+
          |                   |
          v                   v
    Prompt Compiler       QC Engine
          |
          v
      AI Production
          |
          v
     Generated Results
          |
          v
    Continuity Evaluation
          |
          v
      Human Approval

7. Continuity Domains

7.1 Character Continuity

Character continuity menjaga identitas dan kondisi karakter.

Attributes:

- Character ID.
- Canonical identity.
- Facial characteristics.
- Body proportions.
- Skin and hair appearance.
- Age representation.
- Wardrobe.
- Makeup.
- Accessories.
- Physical condition.
- Emotional state.
- Character position.
- Character orientation.
- Character action state.

Identity attributes harus dipisahkan dari temporary character state.

Contoh:

Identity

- Facial structure.
- Eye characteristics.
- Hair identity.
- Body proportions.

Temporary State

- Wet hair.
- Facial expression.
- Injury.
- Dirt.
- Sweat.
- Blood.
- Emotional condition.
- Clothing damage.

Perubahan temporary state harus mengikuti timeline cerita.

7.2 Environment Continuity

Environment continuity menjaga konsistensi lokasi.

Attributes:

- Environment ID.
- Location identity.
- Spatial layout.
- Architectural features.
- Main objects.
- Background elements.
- Lighting setup.
- Weather.
- Atmosphere.
- Time of day.
- Environmental damage.
- Environmental changes.

Perubahan environment harus memiliki narrative atau production justification.

7.3 Prop Continuity

Setiap prop penting harus memiliki identity dan state.

Attributes:

- Prop ID.
- Prop type.
- Appearance.
- Material.
- Color.
- Size.
- Initial position.
- Current position.
- Holder.
- Condition.
- Damage state.
- Visibility.
- Last known state.

Prop state transitions harus dapat ditelusuri.

Contoh:

Gun on Table
      |
      v
Character Picks Up
      |
      v
Gun Held in Right Hand
      |
      v
Gun Placed on Floor

7.4 Wardrobe and Makeup Continuity

Mencakup:

- Clothing identity.
- Clothing layers.
- Colors and materials.
- Accessories.
- Footwear.
- Hair styling.
- Makeup.
- Prosthetics.
- Damage.
- Wetness.
- Dirt.
- Blood.
- Costume changes.

Wardrobe changes harus mengikuti costume timeline.

7.5 Performance Continuity

Menjaga kelanjutan performa karakter:

- Emotional progression.
- Body orientation.
- Gesture progression.
- Gaze direction.
- Action completion.
- Physical momentum.
- Dialogue reaction.
- Breathing and exertion state.

Performa tidak harus identik di setiap shot, tetapi harus sesuai dengan perkembangan aksi dan emosi.

7.6 Cinematographic Continuity

Mencakup:

- Screen direction.
- Camera axis.
- Shot size.
- Camera position.
- Camera movement.
- Subject eyeline.
- Composition.
- Lens intent.
- Lighting direction.
- Exposure and color treatment.

Continuity rules harus tetap memberi ruang untuk intentional creative decisions seperti jump cuts atau perubahan sudut yang disengaja.

8. Temporal Continuity Model

Continuity harus mengikuti urutan cerita dan waktu produksi.

Setiap scene dan shot memiliki:

- Narrative order.
- Timeline position.
- Start condition.
- End condition.
- Duration intent.
- Character states.
- Environment states.
- Prop states.
- Action transitions.
- Continuity dependencies.

Timeline tidak boleh diasumsikan selalu sama dengan urutan produksi.

Sistem harus membedakan:

1. Narrative order.
2. Production order.
3. Editorial order.

Ketiganya dapat berbeda.

State Transition

Setiap perubahan state harus memiliki:

- Previous state.
- New state.
- Triggering event.
- Source shot.
- Timeline position.
- Change reason.
- Approval status.

Perubahan yang tidak memiliki penjelasan harus ditandai untuk review.

9. Spatial Continuity Model

Spatial continuity mengelola hubungan posisi antar-subject dan object.

Contoh data:

- Character A berada di sebelah kiri meja.
- Character B berdiri di depan pintu.
- Prop X berada di tangan Character A.
- Camera berada di sisi tertentu dari action axis.

Spatial representation dapat menggunakan:

- Relative positions.
- Directional relationships.
- Scene coordinate systems.
- Bounding regions.
- Reference landmarks.
- Screen-space relationships.

Absolute 3D coordinates hanya diwajibkan jika production workflow memang membutuhkan dan memiliki data yang memadai.

Jangan mengarang koordinat fisik dari deskripsi visual yang tidak memiliki dasar.

10. Continuity Dependency Graph

Continuity relationships dapat dimodelkan sebagai graph.

Contoh:

Character DNA
     |
     v
Character State
     |
     v
Scene 01 Shot 01
     |
     v
Scene 01 Shot 02
     |
     v
Scene 02 Shot 01
     |
     +------> Wardrobe State
     |
     +------> Prop State
     |
     +------> Environment State
     |
     v
Continuity Validation

Dependency graph digunakan untuk mengetahui dampak perubahan specification.

Contoh:

Jika Character DNA berubah, sistem dapat mengidentifikasi seluruh scene dan shot yang menggunakan character tersebut.

Jika hanya temporary injury state berubah, impact dapat dibatasi pada bagian timeline yang relevan.

11. Reference Asset Strategy

Continuity Engine menggunakan visual references sebagai bukti pendukung.

Reference categories:

- Character master reference.
- Character expression references.
- Character wardrobe references.
- Environment master reference.
- Environment angle references.
- Prop reference.
- Lighting reference.
- Shot reference.
- Approved generation output.

Setiap reference asset harus memiliki:

- Asset ID.
- Reference category.
- Related entity.
- Revision.
- Approval status.
- Provenance.
- Source.
- Created timestamp.
- Quality status.

Reference images bukan pengganti structured continuity data.

Jika provider tidak mendukung reference images, compiler harus menandai keterbatasan tersebut.

12. Continuity Rules Engine

Rules dapat berasal dari:

1. Global project rules.
2. Character rules.
3. Environment rules.
4. Prop rules.
5. Wardrobe rules.
6. Scene rules.
7. Shot rules.
8. Timeline rules.
9. Cinematographic rules.

Rule attributes:

- Rule ID.
- Rule type.
- Scope.
- Severity.
- Condition.
- Expected state.
- Exception policy.
- Source reference.
- Version.
- Approval status.

Severity levels:

- CRITICAL.
- HIGH.
- MEDIUM.
- LOW.
- INFORMATIONAL.

Critical violations harus menghentikan approval sampai diselesaikan atau diberikan authorized exception.

13. Continuity Validation

Validation dilakukan pada beberapa level.

Level 1: Structural Validation

Memeriksa:

- Missing character references.
- Missing environment references.
- Missing prop states.
- Missing timeline information.
- Invalid state transitions.
- Broken revision references.

Level 2: Logical Validation

Memeriksa:

- Character location conflicts.
- Wardrobe timeline conflicts.
- Prop state conflicts.
- Impossible action transitions.
- Inconsistent environmental conditions.
- Dialogue and action ordering.

Level 3: Visual Validation

Menggunakan computer vision atau multimodal analysis untuk membantu mendeteksi:

- Character appearance drift.
- Clothing mismatch.
- Prop mismatch.
- Environment mismatch.
- Unexpected object appearance.
- Composition inconsistency.

Visual analysis menghasilkan evidence dan confidence, bukan kebenaran mutlak.

Level 4: Editorial Validation

Memeriksa:

- Shot-to-shot transition.
- Screen direction.
- Eyeline.
- Action continuity.
- Audio continuity.
- Narrative transition.

Level 5: Human Review

Critical continuity decisions harus dapat diverifikasi oleh manusia.

AI tidak boleh secara otomatis menyetujui perubahan creative specifications yang bersifat penting.

14. Continuity Severity and Scoring

Continuity findings memiliki severity dan confidence yang terpisah.

Severity menunjukkan dampak terhadap produksi.

Confidence menunjukkan tingkat keyakinan sistem terhadap hasil deteksi.

Contoh:

Finding| Severity| Confidence
Character face changed| Critical| 0.95
Prop slightly displaced| Medium| 0.82
Background light variation| Low| 0.67
Wardrobe color mismatch| High| 0.91

Angka tersebut hanya contoh.

Jangan menggunakan confidence sebagai pengganti severity.

Critical violation tidak boleh dianggap aman hanya karena skor keseluruhan tinggi.

15. Continuity Change Management

Setiap perubahan approved specification harus menjalani impact analysis.

Change workflow:

1. Change request dibuat.
2. Related entities diidentifikasi.
3. Affected scenes dan shots dihitung.
4. Dependency graph diperiksa.
5. Continuity impact report dibuat.
6. Human review dilakukan jika diperlukan.
7. Approved revision diterapkan.
8. Affected production jobs dievaluasi.
9. Required revalidation dijalankan.

Perubahan MPB tidak boleh otomatis mengubah historical production snapshots.

16. Prompt Compiler Integration

Continuity Engine menyediakan resolved context kepada Prompt Compilation Engine.

Context mencakup:

- Character identity.
- Current character state.
- Previous shot ending state.
- Current shot starting state.
- Environment state.
- Prop state.
- Wardrobe state.
- Spatial relationships.
- Cinematographic constraints.
- Approved exceptions.

Prompt compiler hanya menerima resolved, versioned context.

Continuity Engine tidak boleh mengirim seluruh historical data jika tidak relevan.

17. Production Workflow Integration

Continuity validation menjadi bagian dari workflow.

Contoh:

Shot Specification
       |
       v
Continuity Pre-Check
       |
       v
Prompt Compilation
       |
       v
AI Generation
       |
       v
Asset Registration
       |
       v
Continuity Post-Check
       |
       v
Human Review
       |
       v
Approved Shot

Pre-check mencegah generation dengan input yang tidak valid.

Post-check memeriksa hasil aktual.

Production Workflow Engine tetap bertanggung jawab atas job dependencies dan workflow state.

18. Continuity Overrides

Tidak semua perbedaan merupakan kesalahan.

Creative direction dapat dengan sengaja meminta:

- Wardrobe changes.
- Character transformation.
- Time jump.
- Scene transition.
- Lighting shift.
- Prop destruction.
- Camera axis crossing.
- Visual discontinuity.
- Dream sequences.

Override harus memiliki:

- Scope.
- Reason.
- Source.
- Approver.
- Valid timeline range.
- Related revision.

Override tidak boleh menjadi mekanisme untuk mengabaikan seluruh continuity validation.

19. API Contract

Logical endpoints:

GET  /api/v1/projects/{project_id}/continuity
GET  /api/v1/scenes/{scene_id}/continuity
GET  /api/v1/shots/{shot_id}/continuity
POST /api/v1/continuity/validate
GET  /api/v1/continuity/reports/{report_id}
POST /api/v1/continuity/change-requests
GET  /api/v1/continuity/impact-analysis/{change_id}
POST /api/v1/continuity/overrides

Semua endpoint harus memeriksa project authorization.

Request dan response mengikuti kontrak "API_SPEC.md".

20. Data and Audit Requirements

Continuity records harus menyimpan:

- Entity references.
- State versions.
- Timeline references.
- Source revisions.
- Validation reports.
- Reference assets.
- Approved overrides.
- Change history.
- Human review decisions.

Historical continuity records harus dapat ditelusuri.

Jangan menghapus evidence yang diperlukan untuk menjelaskan mengapa suatu shot pernah dinyatakan approved.

21. Security Requirements

- Continuity data mengikuti project isolation.
- Reference assets bersifat private.
- Visual analysis hanya menggunakan asset yang authorized.
- External model access mengikuti data-sharing policy.
- AI-generated state suggestions harus ditandai sebagai unapproved.
- Approval actions memiliki audit trail.
- Unauthorized state changes harus ditolak.
- Asset references harus diverifikasi.

22. MVP Implementation Scope

MVP harus membuktikan continuity pada satu vertical production workflow.

Minimum capabilities:

1. Character identity record.
2. Character state tracking.
3. Environment state tracking.
4. Basic prop tracking.
5. Scene and shot timeline.
6. Previous-shot and next-shot context.
7. Basic continuity rules.
8. Structural and logical validation.
9. Reference asset association.
10. Continuity report.
11. Human review.
12. Prompt compiler integration.

Computer vision-based continuity analysis dapat dimulai sebagai assisted validation.

Jangan menjadikan automated visual identity scoring sebagai syarat awal MVP.

23. Implementation Sequence

Phase 1: Repository Discovery

- Audit character data.
- Audit environment and prop data.
- Audit scene and shot structures.
- Audit MPB revisions.
- Audit reference assets.
- Audit QC and visual analysis components.

Phase 2: Domain Foundation

- Define continuity entities.
- Define character state.
- Define environment state.
- Define prop state.
- Define timeline model.
- Define state transition rules.

Phase 3: Continuity Context

- Implement context resolver.
- Implement temporal resolver.
- Implement spatial relationships.
- Implement reference association.
- Implement dependency graph.

Phase 4: Validation

- Implement structural rules.
- Implement logical rules.
- Implement severity classification.
- Implement continuity reports.
- Implement exception handling.

Phase 5: Production Integration

- Integrate with MPB.
- Integrate with Prompt Compiler.
- Integrate with Workflow Engine.
- Integrate with Asset Storage.
- Integrate with Quality Control.

Phase 6: Advanced Validation

- Add visual analysis.
- Add reference comparison.
- Add temporal analysis.
- Add editorial continuity checks.
- Evaluate detection quality.

24. Consequences

Positive

- Character and environment consistency lebih terstruktur.
- State changes dapat ditelusuri.
- Production continuity memiliki source of truth.
- Impact analysis membantu mengurangi rework.
- Prompt compiler menerima context yang relevan.
- Human review memiliki evidence yang lebih jelas.

Negative

- Membutuhkan state modeling.
- Reference assets memerlukan governance.
- Visual analysis memiliki keterbatasan.
- Continuity rules membutuhkan maintenance.
- Perubahan timeline dapat memerlukan revalidation.

Accepted Trade-offs

Continuity Engine menambah kompleksitas domain, tetapi diperlukan untuk menjaga konsistensi film yang terdiri atas banyak scene dan shot yang diproduksi secara terpisah.

25. Validation Checklist

- [ ] Character identity terpisah dari temporary state.
- [ ] Character state memiliki timeline.
- [ ] Environment state dapat ditelusuri.
- [ ] Prop state transitions tersedia.
- [ ] Wardrobe continuity dapat divalidasi.
- [ ] Spatial relationships dapat direpresentasikan.
- [ ] Narrative order terpisah dari production order.
- [ ] Continuity dependency graph tersedia.
- [ ] Reference assets memiliki provenance.
- [ ] Structural validation berjalan.
- [ ] Logical validation berjalan.
- [ ] Visual validation memiliki confidence metadata.
- [ ] Severity terpisah dari confidence.
- [ ] Approved exceptions memiliki audit trail.
- [ ] MPB revision integration berjalan.
- [ ] Prompt compiler integration berjalan.
- [ ] Workflow integration berjalan.
- [ ] Historical continuity dapat ditelusuri.
- [ ] Human review tersedia.
- [ ] Project isolation diuji.

26. Review Conditions

ADR ini perlu ditinjau ulang apabila:

- Multi-character scene complexity meningkat.
- Production menggunakan 3D scene reconstruction.
- Automated visual continuity menjadi kebutuhan utama.
- Temporal video analysis berkembang.
- Continuity graph menjadi terlalu kompleks.
- Multi-provider reference limitations berubah.
- Editorial integration membutuhkan data model baru.

27. Related Documents

- "BRD.md"
- "PRD.md"
- "ARCHITECTURE.md"
- "AI_PIPELINE.md"
- "DATA_MODEL.md"
- "PROMPTS.md"
- "API_SPEC.md"
- "PROVIDER_MATRIX.md"
- "ERROR_HANDLING.md"
- "TEST_STRATEGY.md"
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
- ADR-0007: Async Job Processing.
- ADR-0008: Prompt Compilation Engine.
- ADR-0010: Quality Control Engine.

---

Final Decision: Proposed.

MovieAIProducer adopts a State-Based, Timeline-Aware Continuity Engine that tracks character, environment, prop, wardrobe, performance, spatial, and cinematographic continuity across scenes and shots.

Continuity validation combines deterministic rules, visual analysis, and human review. Approved MPB specifications remain authoritative, and AI-generated continuity suggestions never silently modify them.
