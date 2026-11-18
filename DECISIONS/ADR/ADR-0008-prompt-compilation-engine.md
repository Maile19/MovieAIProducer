# ADR-0008: Prompt Compilation Engine

Project: MovieAIProducer
ADR ID: ADR-0008
Title: Prompt Compilation Engine
Version: 1.0
Status: Proposed
Date: 2026-11-19
Decision Owners: Product Architect / AI Technical Lead

---

1. Context

MovieAIProducer bukan sekadar prompt generator. Sistem harus menerjemahkan creative intent dan production specifications menjadi instruksi yang dapat dieksekusi oleh berbagai AI providers.

Prompt production dapat melibatkan:

- Creative brief.
- Story architecture.
- Screenplay.
- Character DNA.
- Character state.
- Environment Bible.
- Prop DNA.
- Wardrobe and makeup.
- Scene direction.
- Camera and lens configuration.
- Composition.
- Lighting.
- Acting and emotional performance.
- Motion and physics.
- Dialogue and voice.
- Audio direction.
- Continuity constraints.
- Model-specific capabilities.

Setiap AI provider memiliki format input, batas token, parameter, kemampuan, dan interpretasi prompt yang berbeda.

Karena itu, sistem membutuhkan compiler yang mengubah satu canonical production specification menjadi prompt yang sesuai dengan target model tanpa kehilangan creative intent.

2. Problem Statement

Tanpa prompt compilation architecture yang konsisten, sistem berisiko mengalami:

- Prompt saling bertentangan.
- Karakter berubah antar-scene.
- Environment tidak konsisten.
- Camera instruction bertabrakan.
- Motion terlalu kompleks.
- Prompt melebihi batas provider.
- Model menerima instruksi yang tidak didukung.
- Revisi MPB tidak tercermin dalam prompt.
- Prompt generation sulit direproduksi.
- Sulit membandingkan hasil antar-provider.
- Prompt kehilangan detail penting ketika diterjemahkan.

Diperlukan sistem yang mampu menghasilkan prompt secara deterministik, terstruktur, tervalidasi, dan provider-aware.

3. Decision Drivers

1. Creative fidelity.
2. Production consistency.
3. MPB alignment.
4. Provider compatibility.
5. Prompt reproducibility.
6. Capability awareness.
7. Validation and conflict detection.
8. Maintainability.
9. Cost and token efficiency.
10. Version control.

4. Options Considered

Option A: Direct Prompt Templates

Setiap fitur memiliki template prompt sendiri dan langsung mengirimkannya ke provider.

Advantages:

- Mudah dimulai.
- Implementasi awal sederhana.
- Cocok untuk prototipe.

Disadvantages:

- Template mudah terduplikasi.
- Sulit menjaga konsistensi antar-scene.
- Sulit menyesuaikan provider.
- Conflict resolution tidak terpusat.
- Sulit melakukan versioning.

Decision: Rejected as the complete architecture.

Option B: Single Universal Prompt

Seluruh production information digabungkan menjadi satu prompt universal.

Advantages:

- Satu sumber prompt.
- Mudah dipahami secara konseptual.

Disadvantages:

- Prompt menjadi sangat panjang.
- Informasi tidak relevan ikut dikirim.
- Tidak memperhitungkan model capability.
- Sulit mengontrol prioritas instruksi.
- Tidak ideal untuk berbagai generation tasks.

Decision: Rejected.

Option C: Structured Prompt Compilation Engine

Production specifications disusun menjadi canonical intermediate representation, divalidasi, kemudian dikompilasi menjadi provider-specific prompts.

Advantages:

- Pemisahan creative intent dari provider syntax.
- Mendukung reusable components.
- Memungkinkan conflict detection.
- Mendukung provider-specific optimization.
- Prompt dapat direproduksi dan diaudit.
- Mendukung versioning.

Disadvantages:

- Memerlukan compiler architecture.
- Perlu definisi intermediate representation.
- Membutuhkan capability registry dan testing.

Decision: Accepted.

5. Architecture Decision

MovieAIProducer menggunakan Structured, Provider-Aware Prompt Compilation Architecture.

Prompt compilation terdiri atas:

1. Context Resolver.
2. Production Specification Loader.
3. Prompt Component Registry.
4. Canonical Prompt Intermediate Representation.
5. Constraint Validator.
6. Conflict Detector.
7. Prompt Optimizer.
8. Provider Capability Resolver.
9. Provider Prompt Compiler.
10. Prompt Validation Engine.
11. Prompt Version Registry.
12. Prompt Provenance Recorder.

Canonical creative intent harus tetap terpisah dari provider-specific prompt syntax.

Provider adapter tidak boleh menjadi satu-satunya tempat penyimpanan creative logic.

6. Logical Architecture

       Master Production Bible
                  |
                  v
          Context Resolver
                  |
                  v
       Production Specification
                  |
                  v
       Prompt Component Registry
                  |
                  v
      Canonical Prompt IR Builder
                  |
                  v
         Constraint Validator
                  |
                  v
          Conflict Detector
                  |
                  v
           Prompt Optimizer
                  |
                  v
      Provider Capability Resolver
                  |
                  v
        Provider Prompt Compiler
                  |
                  v
          Prompt Validation
                  |
                  v
        Compiled Prompt Package
                  |
                  v
          AI Orchestration
                  |
                  v
             Provider

Compiler harus dapat menghasilkan preview sebelum prompt dikirim untuk generation.

7. Canonical Prompt Intermediate Representation

7.1 Purpose

Canonical Prompt IR adalah representasi terstruktur dari creative intent dan production instructions.

IR bukan sekadar gabungan string.

IR harus memungkinkan sistem memahami:

- Apa yang harus dibuat.
- Siapa atau apa yang menjadi subjek.
- Di mana adegan berlangsung.
- Apa yang sedang terjadi.
- Bagaimana kamera diarahkan.
- Bagaimana pencahayaan dibangun.
- Bagaimana karakter bergerak.
- Bagaimana audio digunakan.
- Apa yang harus dipertahankan.
- Apa yang dilarang berubah.

7.2 Logical Structure

Contoh struktur konseptual:

{
  "schema_version": "1.0",
  "project_id": "project_reference",
  "scene_id": "scene_reference",
  "shot_id": "shot_reference",
  "context": {
    "mpb_snapshot_id": "snapshot_reference",
    "scene_revision": 1,
    "shot_revision": 1
  },
  "creative_intent": {},
  "subject": {},
  "environment": {},
  "action": {},
  "performance": {},
  "cinematography": {},
  "lighting": {},
  "motion": {},
  "audio": {},
  "continuity": {},
  "constraints": {},
  "output_requirements": {}
}

Struktur ini merupakan logical contract, bukan final database schema.

7.3 IR Rules

- Field penting memiliki schema validation.
- Setiap component memiliki version.
- Source references dapat ditelusuri.
- Explicit user instructions dipertahankan.
- Missing values tidak boleh diisi dengan asumsi yang tidak terverifikasi.
- Unsupported instructions harus ditandai.
- Provider syntax tidak boleh mencemari canonical representation.

8. Prompt Component Registry

Prompt dibangun dari komponen yang dapat digunakan ulang.

Komponen utama:

Component| Responsibility
Creative Intent| Tujuan dan emosi scene
Story Context| Narrative context
Character DNA| Identitas visual karakter
Character State| Kondisi karakter pada shot
Environment DNA| Identitas lokasi
Prop DNA| Identitas dan kondisi properti
Wardrobe DNA| Kostum dan penampilan
Scene Action| Aksi utama
Acting Direction| Ekspresi dan performa
Camera Direction| Kamera dan framing
Lens Intent| Karakteristik visual lensa
Composition| Posisi dan susunan frame
Lighting| Cahaya dan atmosfer
Motion| Gerakan karakter dan objek
Physics| Interaksi fisik
Dialogue| Dialog dan lip-sync
Audio| Suara dan ambience
Continuity| Ketentuan antar-shot
Negative Constraints| Hal yang harus dihindari
Output Requirements| Format dan durasi hasil

Komponen harus memiliki:

- Component ID.
- Component version.
- Schema.
- Required fields.
- Optional fields.
- Source reference.
- Validation rules.
- Priority.
- Compatibility metadata.

9. Production Context Resolution

Compiler harus menerima context yang tepat sebelum membangun prompt.

Context resolution mencakup:

1. Project.
2. Approved MPB snapshot.
3. Story and screenplay context.
4. Scene specification.
5. Shot specification.
6. Character state.
7. Environment state.
8. Prop state.
9. Wardrobe state.
10. Previous and related shot continuity.
11. Production constraints.
12. Target provider and model.

Context resolver harus mengikuti ownership domain.

Compiler tidak boleh membaca tabel internal module lain secara langsung tanpa application contract.

Snapshot Consistency

Semua specification yang relevan harus berasal dari snapshot atau revision references yang konsisten.

Jika reference tidak tersedia, compiler harus mengembalikan validation error atau meminta explicit resolution.

10. Instruction Priority and Conflict Resolution

Instruksi dapat berasal dari berbagai sumber.

Priority hierarchy yang diusulkan:

1. Platform safety and technical constraints.
2. Explicit approved production constraints.
3. Approved MPB specifications.
4. Approved scene and shot direction.
5. Approved continuity requirements.
6. Task-specific creative instructions.
7. Provider optimization hints.

Hierarchy tersebut tidak berarti setiap instruksi pada level lebih tinggi selalu menang tanpa evaluasi.

Jika terdapat konflik antar-approved specifications, compiler harus menghasilkan conflict report.

Conflict Types

- Character identity conflict.
- Character appearance conflict.
- Environment conflict.
- Wardrobe conflict.
- Prop state conflict.
- Camera conflict.
- Lighting conflict.
- Motion conflict.
- Duration conflict.
- Aspect ratio conflict.
- Audio conflict.
- Continuity conflict.
- Provider capability conflict.

Compiler tidak boleh diam-diam menghapus salah satu instruksi penting.

11. Prompt Compilation Stages

Stage 1: Input Resolution

Memuat seluruh approved specifications yang relevan.

Stage 2: Normalization

Mengubah data ke canonical structure.

Stage 3: Validation

Memeriksa field wajib, schema version, dan referential integrity.

Stage 4: Conflict Detection

Mengidentifikasi instruksi yang bertentangan.

Stage 5: Capability Resolution

Mengidentifikasi kemampuan model target.

Stage 6: Optimization

Mengurangi redundansi tanpa menghilangkan creative intent.

Stage 7: Provider Compilation

Menerjemahkan canonical IR menjadi provider-specific prompt.

Stage 8: Final Validation

Memeriksa batas provider, parameter, unsupported features, dan output requirements.

Stage 9: Packaging

Membentuk final generation request.

Stage 10: Provenance Recording

Merekam seluruh sumber dan versi yang digunakan.

12. Provider Capability Awareness

Compiler harus mengetahui kapabilitas target model.

Contoh capability dimensions:

- Text-to-image.
- Image-to-image.
- Text-to-video.
- Image-to-video.
- Video-to-video.
- Reference image support.
- Character reference support.
- Multi-shot generation.
- Native audio generation.
- Dialogue and speech.
- Lip-sync.
- Camera movement controls.
- Motion controls.
- Duration limits.
- Resolution limits.
- Aspect ratio support.
- Negative prompt support.
- Seed support.
- Input image limits.
- Video reference limits.

Capability registry harus membedakan:

- VERIFIED: kemampuan telah diuji atau didukung dokumentasi resmi yang relevan.
- PARTIALLY_VERIFIED: sebagian kemampuan telah dikonfirmasi.
- UNVERIFIED: belum dikonfirmasi.
- UNSUPPORTED: tidak didukung.
- DEPRECATED: tidak lagi direkomendasikan.

Kemampuan model dapat berubah berdasarkan versi.

Capability record harus memiliki source, verification date, model version, dan evidence.

Jangan menganggap seluruh model dalam satu provider memiliki kemampuan identik.

13. Provider-Specific Compilation

Setiap provider memiliki compiler adapter.

Contoh logical interfaces:

class PromptCompilerPort:
    def compile(self, canonical_ir, capabilities):
        ...

    def validate(self, compiled_prompt, capabilities):
        ...

Contoh implementasi adapter:

ProviderPromptCompiler
├── TextImageCompiler
├── TextVideoCompiler
├── ImageVideoCompiler
├── AudioCompiler
└── MediaAnalysisCompiler

Struktur tersebut bersifat konseptual.

Compiler adapter bertugas:

- Mengubah format instruksi.
- Memetakan parameter.
- Memilih supported features.
- Menyesuaikan batas panjang prompt.
- Menandai unsupported requirements.
- Mempertahankan intent dan constraints.
- Menghasilkan normalized compilation report.

Provider-specific compiler tidak boleh mengubah approved MPB data.

14. Prompt Optimization

Optimization bertujuan meningkatkan keterbacaan dan efisiensi prompt tanpa mengorbankan detail produksi.

Optimization techniques:

- Deduplication.
- Context pruning.
- Instruction grouping.
- Priority ordering.
- Token budgeting.
- Redundancy reduction.
- Model-specific formatting.
- Reference consolidation.

Optimization Rules

- Jangan menghapus character identity constraints.
- Jangan menghilangkan critical continuity constraints.
- Jangan mengubah aksi utama.
- Jangan mengubah makna dialog.
- Jangan mengubah camera intention tanpa authorization.
- Jangan mengubah approved creative decisions.
- Jangan menyamarkan unsupported features.
- Jangan mengklaim prompt optimization menjamin output yang identik dengan spesifikasi.

Setiap optimization harus dapat ditelusuri.

15. Prompt Length and Token Budget

Compiler harus memperhitungkan batas input model.

Token budgeting mempertimbangkan:

- System instructions.
- User instructions.
- Production context.
- Reference metadata.
- Canonical prompt components.
- Provider-specific parameters.
- Reserved output tokens jika berlaku.

Prioritas context pruning:

1. Preserve safety and required technical constraints.
2. Preserve approved identity and continuity.
3. Preserve primary action and creative intent.
4. Preserve essential cinematography.
5. Preserve essential lighting and performance.
6. Remove redundant descriptions.
7. Remove nonessential context.

Jika prompt tetap melebihi batas, compiler harus menghasilkan actionable validation error atau meminta perubahan eksplisit.

16. Prompt Versioning

Setiap compiled prompt harus memiliki version reference.

Minimal menyimpan:

- Prompt ID.
- Prompt version.
- Compiler version.
- IR schema version.
- Component versions.
- Provider compiler version.
- Target provider.
- Target model.
- Model version jika tersedia.
- MPB snapshot ID.
- Source revision references.
- Compilation timestamp.
- Validation report.
- Optimization report.
- Prompt hash.

Perubahan compiler tidak boleh mengubah historical prompt records.

Prompt regeneration harus dapat menggunakan versi specification dan compiler yang sesuai selama dependency masih tersedia.

17. Prompt Provenance

Setiap prompt harus menjelaskan asal instruksinya.

Provenance record minimal mencakup:

- Source entity.
- Source revision.
- Component ID.
- Transformation performed.
- Optimization applied.
- Provider mapping.
- Validation result.

Tujuan provenance:

- Audit.
- Debugging.
- Reproduction.
- Quality analysis.
- Provider comparison.
- Prompt regression testing.

Prompt yang dikirim tanpa provenance tidak boleh dianggap production-grade execution record.

18. Prompt Preview and Human Approval

User harus dapat melihat hasil kompilasi sebelum menjalankan generation.

Preview menampilkan:

- Canonical production intent.
- Final compiled prompt.
- Provider and model.
- Supported capabilities.
- Unsupported features.
- Warnings.
- Conflict report.
- Estimated token usage jika tersedia.
- Referenced assets.
- MPB snapshot reference.

Untuk perubahan critical, sistem dapat mewajibkan approval sebelum execution.

AI-generated prompt suggestions tidak otomatis mengubah approved production specifications.

19. Prompt Testing Strategy

Testing harus mencakup:

Unit Tests

- Component validation.
- Normalization.
- Conflict detection.
- Provider mapping.
- Token budget.
- Optimization rules.
- Prompt hashing.

Integration Tests

- MPB context resolution.
- Scene and shot compilation.
- Provider adapter compatibility.
- Job creation.
- Provenance persistence.

Regression Tests

Gunakan canonical fixture set untuk mendeteksi perubahan output yang tidak diharapkan.

Provider Tests

Uji kemampuan berdasarkan provider dan model version.

Quality Tests

Evaluasi:

- Instruction completeness.
- Continuity preservation.
- Prompt clarity.
- Contradiction rate.
- Unsupported instruction rate.
- Redundancy.
- Token efficiency.

Prompt quality score tidak boleh dianggap sebagai bukti bahwa hasil video pasti sesuai.

20. Failure Handling

Error categories:

- MISSING_CONTEXT.
- INVALID_SCHEMA.
- REVISION_CONFLICT.
- UNSUPPORTED_CAPABILITY.
- PROMPT_TOO_LONG.
- PROVIDER_COMPILATION_FAILED.
- INVALID_PARAMETER_MAPPING.
- REFERENCE_ASSET_UNAVAILABLE.
- VERSION_INCOMPATIBLE.
- VALIDATION_FAILED.

Setiap error harus menyertakan:

- Error code.
- Human-readable message.
- Affected component.
- Relevant source reference.
- Recovery suggestion.

Critical errors harus menghentikan generation submission.

Warnings dapat diteruskan hanya jika policy mengizinkan dan user mengetahui konsekuensinya.

21. Security Requirements

- Prompt tidak boleh mengandung credentials.
- External content diperlakukan sebagai untrusted input.
- Prompt injection harus diisolasi dari trusted production instructions.
- Project data harus mengikuti authorization.
- Asset references harus diverifikasi.
- Prompt logs harus memiliki redaction policy.
- Provider request payload harus mengikuti data-sharing policy.
- Prompt preview tidak boleh membocorkan project lain.
- Compiler tidak boleh mengeksekusi arbitrary instructions dari prompt content.

22. MVP Implementation Scope

MVP harus membuktikan satu vertical slice:

1. Resolve approved MPB snapshot.
2. Load scene and shot specifications.
3. Build canonical prompt IR.
4. Validate required fields.
5. Detect basic conflicts.
6. Resolve target model capabilities.
7. Compile provider-specific prompt.
8. Show prompt preview.
9. Record prompt version and provenance.
10. Submit through AI orchestration.
11. Associate generation result with prompt record.

Tidak perlu mengimplementasikan seluruh kategori media sekaligus.

Mulai dari satu generation modality dan satu provider yang benar-benar memiliki akses integration yang terverifikasi.

23. Implementation Sequence

Phase 1: Repository Discovery

- Audit existing prompt templates.
- Audit provider adapters.
- Audit MPB data contracts.
- Audit generation request structures.
- Audit prompt versioning.
- Audit model capability registry.

Phase 2: Canonical Contract

- Define IR schema.
- Define component contracts.
- Define provenance contract.
- Define validation errors.
- Define versioning rules.

Phase 3: Compiler Core

- Implement context resolver.
- Implement component registry.
- Implement IR builder.
- Implement validator.
- Implement conflict detector.

Phase 4: Provider Compilation

- Implement capability resolver.
- Implement provider compiler.
- Implement parameter mapping.
- Implement prompt optimization.
- Implement token budgeting.

Phase 5: Governance

- Implement prompt preview.
- Implement approval gates.
- Implement version persistence.
- Implement provenance recording.
- Implement audit history.

Phase 6: Quality and Integration

- Add regression fixtures.
- Add integration tests.
- Validate provider compatibility.
- Test failure scenarios.
- Connect with AI orchestration.
- Connect with asynchronous job processing.

24. Consequences

Positive

- Creative intent terpisah dari provider syntax.
- Prompt lebih konsisten.
- MPB context dapat direproduksi.
- Provider-specific behavior lebih terkontrol.
- Prompt dapat diaudit.
- Capability mismatch dapat dideteksi sebelum generation.
- Perubahan compiler dapat diuji secara terstruktur.

Negative

- Membutuhkan canonical schema.
- Compiler harus dipelihara mengikuti perubahan perubahan provider.
- Versioning dan provenance menambah penyimpanan.
- Capability verification membutuhkan proses berkelanjutan.

Accepted Trade-offs

Kompleksitas compiler diterima untuk menjaga konsistensi produksi lintas-provider dan mencegah prompt menjadi kumpulan template yang tidak terkontrol.

25. Validation Checklist

- [ ] Canonical Prompt IR tersedia.
- [ ] Component registry tersedia.
- [ ] MPB snapshot context dapat di-resolve.
- [ ] Scene and shot context dapat dikompilasi.
- [ ] Schema validation berjalan.
- [ ] Conflict detection berjalan.
- [ ] Provider capability registry tersedia.
- [ ] Capability status memiliki evidence.
- [ ] Provider-specific compiler tersedia.
- [ ] Unsupported requirements ditandai.
- [ ] Token budget validation berjalan.
- [ ] Optimization tidak menghilangkan critical constraints.
- [ ] Prompt preview tersedia.
- [ ] Prompt versioning tersedia.
- [ ] Provenance tercatat.
- [ ] Regression tests berjalan.
- [ ] Prompt injection protection diuji.
- [ ] Generation job terhubung dengan prompt record.
- [ ] Historical prompt dapat ditelusuri.

26. Review Conditions

ADR ini perlu ditinjau ulang apabila:

- Provider memperkenalkan format prompt baru.
- Model capabilities berubah signifikan.
- Canonical IR tidak lagi mampu merepresentasikan kebutuhan produksi.
- Multi-modal prompt requirements berkembang.
- Prompt compiler membutuhkan distributed processing.
- Evaluasi menunjukkan kehilangan creative intent akibat optimasi.

27. Related Documents

- "BRD.md"
- "PRD.md"
- "ARCHITECTURE.md"
- "AI_PIPELINE.md"
- "DATA_MODEL.md"
- "AGENTS.md"
- "PROMPTS.md"
- "API_SPEC.md"
- "PROVIDER_MATRIX.md"
- "ERROR_HANDLING.md"
- "TEST_STRATEGY.md"
- "OBSERVABILITY.md"
- "DECISIONS/ADR/README.md"

Related ADRs:

- ADR-0001: Architecture Style.
- ADR-0002: Application Structure.
- ADR-0003: Provider Adapter System.
- ADR-0004: Master Production Bible.
- ADR-0005: Production Workflow Engine.
- ADR-0006: Data Storage Strategy.
- ADR-0007: Async Job Processing.
- ADR-0009: Continuity Engine.

---

Final Decision: Proposed.

MovieAIProducer adopts a Structured, Provider-Aware Prompt Compilation Engine using canonical production intent, validated intermediate representation, capability-aware compilation, versioning, and complete provenance tracking.

Implementation must preserve approved MPB specifications and must never claim unsupported provider capabilities.
