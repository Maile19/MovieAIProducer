# ADR-0015: Frontend Architecture

- Project: MovieAIProducer
- ADR ID: ADR-0015
- Title: Frontend Architecture
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Decision Owners: Product Owner, Technical Architect, Frontend Lead
- Related ADRs: ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0013, ADR-0014

---

1. Context

MovieAIProducer merupakan platform produksi film berbasis AI dengan workflow kompleks yang mencakup:

- Creative development.
- Screenplay and story architecture.
- Character and environment management.
- Production Bible.
- Storyboard and previsualization.
- Scene and shot planning.
- AI generation orchestration.
- Asset management.
- Continuity validation.
- Quality control.
- Editorial planning.
- Final delivery.

Frontend bukan sekadar kumpulan halaman CRUD. Frontend merupakan production workspace tempat pengguna merencanakan, mengendalikan, memantau, dan mengevaluasi keseluruhan proses produksi.

Sistem harus mampu menampilkan informasi kompleks tanpa membuat pengguna kehilangan konteks proyek.

2. Problem Statement

Tanpa frontend architecture yang jelas, risiko meliputi:

- Komponen saling bergantung.
- Business logic tersebar di UI.
- State management tidak konsisten.
- Data antarhalaman tidak sinkron.
- UI menjadi sulit dikembangkan.
- Workflow produksi tidak memiliki navigasi yang jelas.
- Perubahan MPB tidak tercermin secara konsisten.
- Job AI dan proses asynchronous sulit dipantau.
- Asset dan versi produksi sulit ditelusuri.
- Layout tidak efektif pada layar berbeda.
- Accessibility dan usability terabaikan.

3. Decision

MovieAIProducer menggunakan:

Domain-Oriented Modular Frontend Architecture with Feature-Based Composition.

Prinsip:

1. Feature-oriented modularity.
2. Clear component boundaries.
3. Separation of presentation and application logic.
4. Typed API contracts.
5. Explicit state ownership.
6. Reusable design system.
7. Server-state and client-state separation.
8. Permission-aware rendering.
9. Responsive layout with desktop-landscape priority.
10. Accessibility and usability by design.

Frontend tidak boleh menjadi tempat utama implementasi business rules.

Business rules tetap berada pada backend domain/application layer.

4. Frontend Architecture Principles

4.1 Domain-Oriented Modules

Setiap modul frontend merepresentasikan kemampuan bisnis yang jelas.

Contoh:

- Projects.
- Creative Brief.
- Story.
- Characters.
- Production Bible.
- Environments.
- Storyboards.
- Scenes.
- Shots.
- Production Workflow.
- AI Generation.
- Assets.
- Continuity.
- Quality Control.
- Editorial.
- Delivery.
- Administration.

Modul dapat berkembang secara independen selama mengikuti shared contracts dan design system.

4.2 Separation of Concerns

Pisahkan:

- Presentation.
- UI interaction.
- Application orchestration.
- API communication.
- State management.
- Domain-specific frontend logic.

Komponen visual tidak boleh langsung menjalankan business logic kompleks.

4.3 Reusable UI

Komponen reusable digunakan untuk pola UI yang konsisten.

Namun, jangan membuat abstraction terlalu dini untuk komponen yang hanya memiliki satu penggunaan dan belum memiliki pola stabil.

4.4 Typed Contracts

API request, response, errors, dan event payload harus menggunakan kontrak yang terdefinisi.

TypeScript dapat digunakan jika sesuai dengan stack yang ditemukan saat repository audit.

4.5 Backend Authority

Frontend boleh melakukan validasi awal untuk pengalaman pengguna.

Namun, backend tetap menjadi otoritas untuk:

- Authorization.
- Data integrity.
- MPB approval.
- Workflow transitions.
- QC approval.
- Provider capability enforcement.
- Production state changes.

5. Proposed Technology Direction

Teknologi kandidat:

- React.
- TypeScript.
- Modern build tooling.
- Component-based UI.
- CSS utility framework atau design-system styling.
- Typed API client.
- Server-state management.
- Client-state management sesuai kebutuhan.
- Automated frontend testing.

Pilihan library spesifik belum final.

Keputusan harus mempertimbangkan:

- Repository yang tersedia.
- Existing framework.
- Dependency compatibility.
- Developer experience.
- Performance.
- Maintenance cost.
- Deployment architecture.

Jangan mengganti stack yang sudah berjalan sebelum melakukan audit.

6. Logical Frontend Structure

Struktur konseptual:

frontend/
├── app/
│   ├── routing/
│   ├── providers/
│   ├── layouts/
│   └── bootstrap/
│
├── modules/
│   ├── projects/
│   ├── creative-brief/
│   ├── story/
│   ├── characters/
│   ├── production-bible/
│   ├── environments/
│   ├── storyboards/
│   ├── scenes/
│   ├── shots/
│   ├── workflow/
│   ├── ai-generation/
│   ├── assets/
│   ├── continuity/
│   ├── quality-control/
│   ├── editorial/
│   ├── delivery/
│   └── administration/
│
├── shared/
│   ├── ui/
│   ├── hooks/
│   ├── utilities/
│   ├── types/
│   ├── api/
│   ├── permissions/
│   └── design-system/
│
├── services/
│   ├── api-client/
│   ├── authentication/
│   ├── realtime/
│   └── telemetry/
│
└── tests/
    ├── integration/
    └── e2e/

Struktur tersebut merupakan logical proposal, bukan instruksi untuk langsung membuat seluruh folder.

Implementasi mengikuti repository discovery.

7. Application Shell

Application Shell menjadi kerangka utama pengalaman pengguna.

Komponen utama:

- Global navigation.
- Project selector.
- Project context.
- Workflow navigation.
- Main workspace.
- Contextual inspector.
- Notification center.
- User and account menu.
- Global command/search interface.
- System status indicators.

Application Shell harus mempertahankan project context ketika pengguna berpindah antarfitur.

8. Layout Strategy

8.1 Desktop Landscape First

Desktop landscape menjadi target utama untuk production workspace.

Prioritas:

- Workspace yang luas.
- Multi-panel layout.
- Scene and shot timelines.
- Preview and inspector panels.
- Asset browser.
- Workflow status.
- Contextual production information.

8.2 Responsive Behavior

Tablet:

- Adaptive panel layout.
- Collapsible navigation.
- Simplified multi-panel views.

Mobile:

- Focused single-task workflows.
- Simplified navigation.
- Read-only monitoring untuk fitur yang kompleks jika diperlukan.
- Avoid forcing dense desktop interfaces into narrow screens.

Mobile tidak harus memiliki seluruh kemampuan desktop pada MVP.

8.3 Workspace Layout Modes

Komponen workspace dapat memiliki layout:

- Standard.
- Split View.
- Full Canvas.
- Timeline View.
- Review View.
- Asset Browser View.

Layout preference dapat disimpan per pengguna jika kebutuhan sudah terbukti.

9. Design System

Design system menjadi fondasi visual dan interaksi.

9.1 Design Tokens

Mencakup:

- Color.
- Typography.
- Spacing.
- Sizing.
- Radius.
- Borders.
- Shadows.
- Motion.
- Layering.
- Focus states.

9.2 Component Categories

Foundation

- Colors.
- Typography.
- Icons.
- Spacing.
- Responsive rules.

Basic Components

- Button.
- Input.
- Select.
- Checkbox.
- Radio.
- Dialog.
- Tooltip.
- Badge.
- Tabs.

Data Components

- Table.
- List.
- Tree.
- Timeline.
- Status indicator.
- Progress.
- Filter.
- Search.

Production Components

- Scene card.
- Shot card.
- Character reference.
- Asset thumbnail.
- Storyboard panel.
- Video preview.
- Continuity indicator.
- QC finding panel.
- Generation job monitor.

9.3 Component Governance

Komponen reusable harus memiliki:

- Defined purpose.
- Typed properties.
- Consistent behavior.
- Accessibility requirements.
- Usage documentation.
- Tests where appropriate.

Hindari duplikasi komponen yang memiliki fungsi dan perilaku sama.

10. Routing Architecture

Routing harus mengikuti domain dan workflow.

Contoh konseptual:

/projects
/projects/:projectId/overview
/projects/:projectId/brief
/projects/:projectId/story
/projects/:projectId/characters
/projects/:projectId/production-bible
/projects/:projectId/storyboards
/projects/:projectId/scenes
/projects/:projectId/shots
/projects/:projectId/workflow
/projects/:projectId/generation
/projects/:projectId/assets
/projects/:projectId/continuity
/projects/:projectId/quality-control
/projects/:projectId/editorial
/projects/:projectId/delivery

Ketentuan:

- Route harus memiliki authorization checks.
- Project context harus divalidasi.
- Invalid resource IDs harus ditangani.
- Deep links harus berfungsi.
- Navigation state tidak boleh menjadi sumber kebenaran data.
- Route structure dapat berubah setelah API dan product requirements diaudit.

11. State Management Strategy

Pisahkan state berdasarkan kepemilikan dan siklus hidupnya.

11.1 Server State

Data yang dimiliki backend:

- Projects.
- MPB.
- Scenes.
- Shots.
- Assets.
- Workflow.
- Jobs.
- QC results.

Server state harus memiliki strategi:

- Fetching.
- Caching.
- Invalidation.
- Refetching.
- Optimistic updates bila aman.
- Error recovery.

11.2 Client State

Data lokal UI:

- Open panels.
- Active tabs.
- Selected timeline range.
- Temporary filters.
- Modal state.
- Local workspace preferences.

11.3 Form State

Form harus mendukung:

- Validation.
- Dirty state.
- Save status.
- Unsaved change warnings.
- Conflict handling.
- Draft recovery jika dibutuhkan.

11.4 Workflow State

Workflow status berasal dari backend.

Frontend tidak boleh menganggap perubahan lokal sebagai transisi workflow yang sudah berhasil sebelum server mengonfirmasi.

12. Master Production Bible Integration

MPB merupakan Single Source of Truth.

Frontend harus membedakan:

- Draft.
- Proposed change.
- Pending approval.
- Approved revision.
- Rejected change.
- Superseded revision.

UI harus menampilkan:

- Current revision.
- Approval status.
- Change history.
- Revision provenance.
- Impact analysis.
- Related scenes and shots.

AI-generated suggestions harus ditampilkan sebagai proposal.

Frontend tidak boleh mengubah approved MPB secara diamdiam.

13. AI Generation Interface

AI Generation Workspace harus menyediakan:

- Prompt preview.
- Provider and model selection.
- Capability information.
- Input references.
- MPB context.
- Generation settings.
- Estimated cost when available.
- Job status.
- Result preview.
- Error information.
- Retry controls.
- Human review and approval.

Frontend tidak boleh menjanjikan kemampuan model yang belum diverifikasi.

Generation job harus memiliki identitas dan status yang dapat ditelusuri.

14. Asset Management Interface

Asset Browser harus mendukung:

- Search.
- Filtering.
- Sorting.
- Pagination or virtualization.
- Preview.
- Version history.
- Metadata.
- Provenance.
- Permissions.
- Approval status.
- Usage references.

Asset thumbnail tidak boleh dianggap sebagai bukti bahwa binary asset masih tersedia.

Download dan preview harus mengikuti authorization backend.

15. Timeline and Canvas Architecture

Timeline dan canvas merupakan bagian penting production workspace.

Komponen yang mungkin dibutuhkan:

- Scene timeline.
- Shot timeline.
- Storyboard sequence.
- Audio track representation.
- Asset placement.
- Duration and timing.
- Continuity markers.
- QC markers.
- Production status overlays.

Untuk data besar:

- Virtualization.
- Lazy loading.
- Incremental rendering.
- Efficient state updates.
- Media thumbnail optimization.

Rendering performance harus diukur berdasarkan dataset realistis.

16. Realtime and Async Updates

Frontend dapat menerima updates melalui polling, Server-Sent Events, atau WebSocket sesuai kebutuhan backend.

Contoh events:

- Workflow task updated.
- Job queued.
- Job started.
- Job progress updated.
- Job completed.
- Job failed.
- Asset processed.
- QC completed.
- Approval requested.

Realtime updates harus memiliki:

- Event identity.
- Project scope.
- Resource identity.
- Timestamp.
- Version or sequence information jika tersedia.

Frontend harus mampu menangani reconnect, duplicate events, dan missed updates.

Server tetap menjadi authoritative state source.

17. Error and Loading Experience

Semua modul harus memiliki pola yang konsisten untuk:

- Initial loading.
- Background refresh.
- Empty states.
- Validation errors.
- API failures.
- Permission denied.
- Resource not found.
- Conflict.
- Rate limiting.
- Provider errors.
- Network interruption.

Error message harus menjelaskan:

1. Apa yang gagal.
2. Dampaknya.
3. Apakah data aman.
4. Apa tindakan berikutnya.

Jangan menampilkan raw stack traces atau secret.

18. Accessibility

Frontend harus mempertimbangkan:

- Keyboard navigation.
- Visible focus indicators.
- Semantic structure.
- Screen reader labels.
- Color contrast.
- Accessible dialogs.
- Form error announcements.
- Reduced motion preferences.

Komponen interaktif harus memiliki perilaku keyboard yang konsisten.

Accessibility diuji sebagai bagian dari quality process.

19. Performance Strategy

Prioritas optimasi:

- Route-based code splitting.
- Lazy loading.
- Image optimization.
- Video preview optimization.
- Virtualized large lists.
- Debounced search.
- Efficient caching.
- Avoid unnecessary re-renders.
- Background processing for expensive operations.
- Bundle size monitoring.

Frontend tidak boleh mengunduh seluruh media produksi sekaligus.

Performance budgets ditetapkan berdasarkan pengukuran nyata dan target perangkat.

20. Security and Authorization

Frontend security controls:

- Secure session handling.
- Permission-aware UI.
- Safe rendering.
- Input validation.
- Protected routes.
- Secure file preview.
- No secret exposure.
- Safe external navigation.
- CSP-compatible implementation where supported.

Frontend authorization hanya membantu pengalaman pengguna.

Backend tetap wajib memeriksa setiap request.

Jangan menyimpan provider API keys dalam browser.

21. Testing Strategy

Unit Tests

- Component behavior.
- Utility functions.
- Form validation.
- State transitions.
- Permission rendering.

Integration Tests

- API integration.
- Routing.
- State synchronization.
- MPB revision display.
- Job status updates.
- Asset access.
- Workflow interaction.

End-to-End Tests

- Create project.
- Complete creative brief.
- Review production specifications.
- Create scene and shot.
- Submit generation job.
- Monitor job status.
- Review asset.
- Run continuity validation.
- Run QC.
- Complete approval workflow.

Visual and Accessibility Tests

- Responsive layout.
- Desktop landscape workspace.
- Tablet behavior.
- Mobile behavior.
- Keyboard navigation.
- Color contrast.
- Visual regression where useful.

22. MVP Scope

Prioritas awal:

1. Application Shell.
2. Authentication interface.
3. Project navigation.
4. Project overview.
5. Creative Brief interface.
6. Story and scene interface.
7. MPB viewer and editor with revision awareness.
8. Character and environment management.
9. Basic shot and storyboard workspace.
10. AI generation job monitor.
11. Asset browser.
12. Workflow status.
13. Basic QC review.
14. Responsive foundations.
15. Design system foundations.

Advanced timeline editing, multi-user collaborative canvas, dan complex real-time editing dapat ditunda sampai kebutuhan terbukti.

23. Implementation Sequence

Phase 1: Frontend Discovery

- Inspect existing framework.
- Inspect routing.
- Inspect components.
- Inspect API integration.
- Inspect state management.
- Inspect styling system.
- Identify technical debt.

Phase 2: Foundation

- Establish application shell.
- Define route conventions.
- Establish design tokens.
- Establish API client.
- Establish error handling.
- Establish authentication integration.

Phase 3: Core Modules

- Project.
- Creative Brief.
- Story.
- Character.
- Production Bible.

Phase 4: Production Workspace

- Scene.
- Shot.
- Storyboard.
- Asset browser.
- Workflow monitor.

Phase 5: AI and QC

- Generation interface.
- Job monitor.
- Continuity review.
- QC interface.
- Approval workflow.

Phase 6: Optimization

- Performance profiling.
- Accessibility audit.
- Responsive refinement.
- Visual regression.
- Usability validation.

24. Risks and Mitigations

Risk| Mitigation
Overly coupled components| Domain-oriented modules
Duplicated business logic| Backend domain authority
State inconsistency| Explicit state ownership
Large media payloads| Lazy loading and virtualization
UI permission bypass assumptions| Backend authorization
MPB revision confusion| Revision-aware UI
Realtime event loss| Reconciliation with server state
Premature abstraction| Evidence-based component reuse
Responsive layout degradation| Device-specific testing
Performance regression| Measured performance budgets

25. Consequences

Positive

- Clear frontend boundaries.
- Consistent UI.
- Better maintainability.
- Easier domain module development.
- Predictable state ownership.
- Better production workflow visibility.
- Improved testability.
- Responsive experience.

Trade-offs

- Initial architecture and design-system effort.
- Need for frontend governance.
- Typed API contracts require coordination.
- Complex workspace components need dedicated performance testing.

26. Decision Validation Checklist

- [ ] Domain-oriented frontend modules are defined.
- [ ] Application Shell responsibilities are clear.
- [ ] Presentation and application logic are separated.
- [ ] Backend remains business-rule authority.
- [ ] Server and client state are separated.
- [ ] API contracts are typed.
- [ ] MPB revision awareness is included.
- [ ] AI job lifecycle is represented.
- [ ] Asset access respects permissions.
- [ ] Desktop landscape experience is prioritized.
- [ ] Responsive behavior is defined.
- [ ] Accessibility requirements are included.
- [ ] Performance strategy is documented.
- [ ] Testing strategy covers core workflows.
- [ ] Frontend structure is reconciled with repository reality.

27. Review and Acceptance Conditions

This ADR can move from Proposed to Accepted when:

1. Existing frontend repository has been audited.
2. Framework and build tooling are confirmed.
3. Frontend module boundaries are approved.
4. API contracts are sufficiently defined.
5. State management strategy is selected.
6. Design system foundation is approved.
7. Responsive and accessibility requirements are reviewed.
8. MPB and workflow integration are validated.
9. MVP frontend scope is agreed.
10. Implementation feasibility is confirmed.

Review this ADR if:

- Frontend framework changes.
- The platform adopts a separate desktop application.
- Collaborative real-time editing becomes a core requirement.
- Rendering requirements exceed the current architecture.
- Major changes occur in backend API boundaries.

---

Final Principle:

The frontend is the production control room of MovieAIProducer.

It must make complex production workflows understandable, traceable, and controllable without duplicating backend authority or hiding important production decisions.
