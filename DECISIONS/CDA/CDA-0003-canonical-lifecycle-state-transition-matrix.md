# CDA-0003: CANONICAL LIFECYCLE & STATE TRANSITION MATRIX

- Project: MovieAIProducer
- Document ID: CDA-0003
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Category: Architecture Governance
- Related Documents: DATA_MODEL.md, API_SPEC.md, AI_PIPELINE.md, ERROR_HANDLING.md, TEST_STRATEGY.md
- Related ADRs: ADR-0004, ADR-0005, ADR-0007, ADR-0009, ADR-0010, ADR-0011, ADR-0012

---

PART A: STATE GOVERNANCE

1. Objectives

Menetapkan satu standar lifecycle untuk seluruh domain agar:

1. Status memiliki arti yang konsisten.
2. Transisi status dapat divalidasi.
3. Tidak ada perubahan status tanpa otorisasi.
4. Proses asynchronous dapat dipantau.
5. Kegagalan dapat dipulihkan.
6. Approval tidak disamakan dengan execution completion.
7. AI tidak dapat melewati human approval.
8. Seluruh perubahan penting dapat diaudit.

2. Core State Principles

2.1 State Ownership

Setiap entity memiliki satu domain yang berwenang mengubah authoritative state.

Domain lain tidak boleh mengubah status secara langsung.

2.2 Explicit Transitions

Setiap perubahan status harus mengikuti transition rules.

Tidak boleh melakukan arbitrary status assignment.

2.3 Terminal States

Terminal state adalah kondisi akhir untuk satu lifecycle instance.

Jika pekerjaan perlu dilanjutkan setelah terminal state, gunakan instance atau revision baru sesuai jenis entity.

2.4 Approval Is Separate

Execution completion tidak berarti approval.

Contoh:

- Job completed tidak berarti asset approved.
- Generation completed tidak berarti hasil layak produksi.
- QC completed tidak berarti QC passed.
- Workflow completed tidak berarti final delivery approved.

2.5 Cancellation Semantics

"cancellation_requested" berbeda dari "cancelled".

Permintaan pembatalan belum membuktikan bahwa operasi eksternal sudah berhenti.

2.6 State and Event Separation

State merupakan kondisi authoritative saat ini.

Event merupakan rekaman perubahan atau fakta yang terjadi.

Event tidak boleh dianggap sebagai pengganti authoritative state.

---

PART B: CANONICAL STATUS VOCABULARY

3. Standard Status Definitions

Status| Meaning
draft| Data masih dalam penyusunan
pending| Menunggu proses atau keputusan
queued| Menunggu giliran eksekusi
scheduled| Dijadwalkan untuk diproses
running| Sedang dijalankan
in_progress| Pekerjaan sedang berlangsung
paused| Dihentikan sementara secara terkontrol
blocked| Tidak dapat dilanjutkan karena prasyarat
awaiting_review| Menunggu pemeriksaan
awaiting_approval| Menunggu keputusan approval
approved| Telah disetujui oleh otoritas yang berwenang
rejected| Ditolak oleh otoritas yang berwenang
completed| Eksekusi atau aktivitas berhasil diselesaikan
failed| Eksekusi gagal
cancellation_requested| Pembatalan diminta
cancelled| Pembatalan telah dikonfirmasi
expired| Masa berlaku berakhir
archived| Dipindahkan ke status arsip
superseded| Digantikan revision atau entity yang lebih baru
deprecated| Tidak lagi direkomendasikan untuk penggunaan baru
disabled| Dinonaktifkan melalui kebijakan
deleted| Dihapus sesuai lifecycle dan retention policy

Status tersebut merupakan vocabulary lintas-domain, bukan daftar yang harus diterapkan ke setiap entity.

Setiap domain hanya menggunakan status yang relevan.

4. Important Semantic Distinctions

completed vs approved

- "completed": pekerjaan selesai dijalankan.
- "approved": hasil telah disetujui.

failed vs rejected

- "failed": proses teknis gagal.
- "rejected": keputusan review menolak hasil atau proposal.

blocked vs paused

- "blocked": terdapat kondisi yang mencegah kelanjutan.
- "paused": proses dihentikan sementara secara sengaja.

cancelled vs expired

- "cancelled": operasi dihentikan melalui proses pembatalan.
- "expired": masa berlaku atau batas waktu berakhir.

archived vs deleted

- "archived": data tetap tersedia sesuai kebijakan akses.
- "deleted": data menjalani penghapusan sesuai retention dan legal requirements.

---

PART C: ENTITY LIFECYCLE MATRICES

5. Project Lifecycle

Owner: Project Management Domain.

States

- draft
- active
- paused
- completed
- archived
- cancelled

Allowed Transitions

From| To| Condition
draft| active| Project setup valid
draft| cancelled| Authorized cancellation
active| paused| Authorized pause
paused| active| Resume permitted
active| completed| Project completion criteria met
completed| archived| Archive policy permits
paused| cancelled| Authorized cancellation
completed| cancelled| Not allowed by default

Project completion tidak otomatis berarti final film delivery berhasil.

6. Production Brief Lifecycle

Owner: Creative Development Domain.

States

- draft
- in_review
- approved
- rejected
- superseded

Allowed Transitions

From| To| Condition
draft| in_review| Validation passed
in_review| approved| Authorized approval
in_review| rejected| Authorized rejection
rejected| draft| Revision requested
approved| superseded| New approved revision replaces it

Approved brief tidak boleh diedit secara langsung.

Perubahan harus menghasilkan revision atau change request.

7. MPB Lifecycle

Owner: MPB Management Domain, dengan data ownership tetap pada domain terkait.

States

- draft
- pending_review
- approved
- superseded
- archived

Allowed Transitions

From| To| Condition
draft| pending_review| Required specifications complete
pending_review| approved| Approval policy satisfied
pending_review| draft| Revision required
approved| superseded| Replacement approved
superseded| archived| Retention policy permits

MPB Rules

1. Approved snapshot immutable.
2. Snapshot memiliki stable identity.
3. Change request tidak mengubah snapshot lama.
4. Snapshot baru harus memiliki provenance.
5. Production job menggunakan snapshot tertentu.
6. Rejection tidak menghapus historical revision.

8. Change Request Lifecycle

Owner: Domain yang memiliki entity target, dengan MPB Management mengoordinasikan perubahan production context.

States

- draft
- submitted
- impact_analysis
- pending_approval
- approved
- rejected
- applied
- cancelled

Allowed Transitions

From| To| Condition
draft| submitted| Required fields valid
submitted| impact_analysis| Request accepted for evaluation
impact_analysis| pending_approval| Impact report ready
impact_analysis| rejected| Request invalid or infeasible
pending_approval| approved| Authorized approval
pending_approval| rejected| Authorized rejection
approved| applied| Changes successfully committed
draft| cancelled| Request withdrawn
submitted| cancelled| Cancellation permitted

Approval tidak berarti perubahan sudah diterapkan.

"applied" hanya setelah authoritative owner berhasil menyimpan perubahan.

9. Workflow Lifecycle

Owner: Workflow Engine.

States

- draft
- ready
- running
- paused
- blocked
- completed
- failed
- cancellation_requested
- cancelled

Allowed Transitions

From| To| Condition
draft| ready| Definition and dependencies valid
ready| running| Start authorized
running| paused| Pause permitted
paused| running| Resume conditions satisfied
running| blocked| Dependency or approval blocker
blocked| ready| Blocker resolved
blocked| running| Safe resume policy permits
running| completed| Required tasks completed
running| failed| Unrecoverable workflow failure
ready| cancellation_requested| Cancellation requested
running| cancellation_requested| Cancellation requested
cancellation_requested| cancelled| Cancellation confirmed
paused| cancellation_requested| Cancellation requested

Workflow status harus dihitung berdasarkan workflow policy dan task state, bukan sekadar jumlah task yang selesai.

10. Workflow Task Lifecycle

Owner: Workflow Engine.

States

- pending
- ready
- running
- blocked
- awaiting_review
- awaiting_approval
- completed
- failed
- skipped
- cancellation_requested
- cancelled

Rules

- Task hanya dapat berjalan jika dependencies terpenuhi.
- Task yang menunggu approval tidak dianggap completed.
- Task gagal dapat di-retry jika policy mengizinkan.
- Skipped task harus memiliki reason.
- Task completed harus menyimpan completion evidence.
- Rework dapat mengembalikan task ke lifecycle baru atau revision yang dapat ditelusuri.

Task status tidak boleh dimutasi oleh Job Processing.

11. Job Lifecycle

Owner: Job Processing Domain.

States

- queued
- scheduled
- running
- retry_wait
- cancellation_requested
- succeeded
- failed
- cancelled
- expired
- dead_letter

Allowed Transitions

From| To| Condition
queued| running| Worker acquires valid lease
queued| cancelled| Cancellation confirmed
scheduled| queued| Schedule time reached
scheduled| cancelled| Cancellation confirmed
running| succeeded| Execution succeeded
running| retry_wait| Retry policy allows
retry_wait| queued| Retry time reached
running| failed| Retry unavailable or exhausted
running| cancellation_requested| Cancellation requested
cancellation_requested| cancelled| Cancellation confirmed
cancellation_requested| succeeded| Operation completed before cancellation
cancellation_requested| failed| Operation failed
queued| dead_letter| Policy-defined terminal dispatch failure

"dead_letter" merupakan terminal operational state yang membutuhkan inspection atau controlled reprocessing.

Job Rules

- Job identity must be stable.
- Each attempt has separate identity.
- Worker lease must expire safely.
- Duplicate execution must be controlled.
- Result persistence must be idempotent.
- Provider operation IDs must be recorded when available.
- Cancellation must distinguish requested and confirmed.

12. Generation Request Lifecycle

Owner: AI Orchestration Domain.

States

- draft
- validated
- submitted
- processing
- awaiting_review
- completed
- failed
- cancelled

Rules

- Request validation occurs before execution.
- Submission creates or associates an execution job.
- Processing status reflects orchestration state.
- Generation result is separate from asset approval.
- Completed request may still require QC or human review.
- Retry must preserve request provenance.

Generation Request and Job are separate entities with related but independent lifecycles.

13. Provider Operation Lifecycle

Owner: Provider Integration Domain or designated adapter operation manager.

States

- submitted
- accepted
- processing
- succeeded
- failed
- cancellation_requested
- cancelled
- unknown
- expired

Rules

- Provider response must be normalized.
- Provider operation ID is retained.
- Unknown state must not be interpreted as success.
- Webhook and polling updates must be idempotent.
- Provider timeout does not prove provider-side cancellation.
- Reconciliation must resolve uncertain operations when possible.

14. Asset Lifecycle

Owner: Asset Management Domain.

States

- registered
- processing
- available
- awaiting_review
- approved
- rejected
- quarantined
- archived
- deletion_pending
- deleted

Rules

- Asset registration does not imply processing success.
- Binary existence does not imply asset approval.
- Quarantined assets cannot be used in production without explicit policy.
- Approved assets must retain provenance.
- Deletion must respect legal hold and retention policy.
- Asset versions must remain distinguishable.

15. Continuity Run Lifecycle

Owner: Continuity Engine.

States

- queued
- running
- completed
- failed
- cancelled

Result Classification

- pass
- pass_with_warnings
- fail
- inconclusive

Rules

- Run lifecycle and result classification are separate.
- A completed run can have a failing result.
- Confidence must remain separate from severity.
- Human overrides require reason and identity.
- Historical findings must remain traceable.

16. QC Run Lifecycle

Owner: Quality Control Domain.

States

- queued
- running
- completed
- failed
- cancelled

Result Classification

- pass
- pass_with_warnings
- fail
- inconclusive

Approval States

- not_required
- awaiting_approval
- approved
- rejected

Rules

- QC execution status and quality result are independent.
- QC completion does not automatically imply approval.
- Critical blocker policy overrides numerical score.
- Human approval must be attributable.
- Rubric version must be recorded.

17. Approval Lifecycle

Owner: Domain that owns the approval policy and target entity.

States

- pending
- approved
- rejected
- withdrawn
- expired

Rules

- Approval requires authorized identity.
- Approval action records target revision.
- Approval must not silently apply unrelated revisions.
- Rejection requires reason according to policy.
- Withdrawal is permitted only before finalization where policy allows.
- Expiration follows explicit policy.

18. Delivery Lifecycle

Owner: Delivery Domain.

States

- draft
- preparing
- validating
- awaiting_approval
- ready
- delivering
- delivered
- failed
- cancelled
- archived

Rules

- Package preparation is separate from delivery.
- Technical validation must pass before ready.
- Approval requirements must be satisfied.
- Delivery confirmation must be based on destination evidence.
- A failed delivery must preserve package and attempt history.

---

PART D: TRANSITION GOVERNANCE

19. Transition Authorization

Every state transition must verify:

- Caller identity.
- Domain authority.
- Project scope.
- Required permission.
- Current state.
- Transition policy.
- Preconditions.
- Revision compatibility.

AI agents may request authorized transitions but cannot bypass approval policy.

20. Concurrency and Optimistic Locking

For mutable entities:

- Use revision number or equivalent version token.
- Detect stale updates.
- Reject conflicting writes.
- Return a structured conflict response.
- Require the caller to reload or reconcile.

Concurrent approval attempts must be handled deterministically.

21. Idempotency

Operations that may be retried must define idempotency behavior.

Examples:

- Submit generation request.
- Create job.
- Complete workflow task.
- Approve revision.
- Register asset.
- Process provider webhook.
- Create delivery attempt.

Duplicate requests must not create duplicate authoritative outcomes.

22. Timeouts and Expiration

Timeout policy must define:

- Start time.
- Deadline.
- Retry eligibility.
- Expiration action.
- Recovery action.
- Ownership of final state.

Timeout is not automatically equivalent to cancellation.

23. Rework and Revisions

Rework must preserve historical results.

A new revision or controlled task attempt should be created when an already completed production output requires modification.

Do not silently rewrite historical approved records.

24. Event and State Consistency

Every meaningful transition should generate an event or audit record according to the domain contract.

Required controls:

- Stable event identity.
- Aggregate identity.
- Previous and new state.
- Actor identity.
- Timestamp.
- Correlation ID.
- Relevant revision.
- Transition reason.

Transactional outbox or an equivalent reliability pattern should be considered where state changes and event publication must remain consistent.

---

PART E: CANONICAL STATE IMPLEMENTATION RULES

25. State Machine Requirements

Every implemented state machine must define:

1. Entity owner.
2. Initial state.
3. Allowed states.
4. Allowed transitions.
5. Preconditions.
6. Authorization.
7. Terminal states.
8. Retry behavior.
9. Cancellation behavior.
10. Timeout behavior.
11. Audit requirements.
12. Recovery behavior.

26. Prohibited Patterns

- Arbitrary string status assignment.
- Frontend-only state transitions.
- Treating timeout as confirmed cancellation.
- Treating job completion as approval.
- Treating QC completion as QC pass.
- Treating asset registration as asset availability.
- Reusing terminal job instances without a defined retry model.
- Mutating immutable approved snapshots.
- Deleting historical audit records.
- Updating another domain's authoritative state directly.

27. Testing Requirements

Unit Tests

- Valid transition.
- Invalid transition.
- Unauthorized transition.
- Terminal-state protection.
- Retry behavior.
- Cancellation behavior.
- Timeout behavior.

Concurrency Tests

- Duplicate requests.
- Concurrent approvals.
- Stale revision.
- Duplicate webhook.
- Worker lease expiration.

Integration Tests

- Workflow task creates job.
- Job completes and updates workflow through contract.
- Generation result registers asset.
- Continuity findings are consumed by QC.
- QC approval enables delivery.
- Failed provider operation is reconciled.

Recovery Tests

- Worker crash.
- Queue redelivery.
- Provider timeout.
- Database interruption.
- Event publication failure.
- Stuck cancellation.
- Dead-letter reprocessing.

28. Audit Acceptance Checklist

- [ ] Every lifecycle has an authoritative owner.
- [ ] Every entity has a defined initial state.
- [ ] Valid transitions are documented.
- [ ] Invalid transitions are rejected.
- [ ] Terminal states are explicit.
- [ ] Approval is separate from execution.
- [ ] Cancellation semantics are explicit.
- [ ] Retry and recovery are defined.
- [ ] Concurrency is controlled.
- [ ] Idempotency is defined.
- [ ] State changes are auditable.
- [ ] Events remain distinct from authoritative state.
- [ ] Cross-domain transitions use contracts.
- [ ] Tests cover state transitions and failure scenarios.

---

29. FINAL GOVERNANCE PRINCIPLE

Every lifecycle must have one authoritative owner.

Every transition must be valid, authorized, and traceable.

Every execution result must remain distinct from its approval decision.

Every failure must have an explicit recovery path.

No system component may silently invent or bypass a state transition.

---

Status: Proposed.

This matrix establishes the lifecycle baseline. Domain-specific implementation details, timeout values, retry limits, and approval policies must be finalized through domain specifications and repository discovery.
