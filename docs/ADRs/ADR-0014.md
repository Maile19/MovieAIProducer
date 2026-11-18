# ADR-0014: Deployment Strategy

- Project: MovieAIProducer
- ADR ID: ADR-0014
- Title: Deployment Strategy
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Decision Owners: Product Owner, Technical Architect, DevOps / Infrastructure Owner
- Related ADRs: ADR-0001, ADR-0002, ADR-0006, ADR-0007, ADR-0011, ADR-0012, ADR-0013

---

1. Context

MovieAIProducer membutuhkan deployment architecture yang mampu menjalankan:

- Web application.
- Backend API.
- Database.
- Background workers.
- Workflow orchestration.
- AI provider integrations.
- Media processing.
- Asset storage.
- QC Engine.
- Observability services.

Sistem harus dapat dikembangkan secara bertahap tanpa memaksakan kompleksitas infrastruktur yang belum diperlukan.

Deployment harus mendukung development, testing, staging, dan production dengan konfigurasi yang dapat dibedakan dan diaudit.

2. Problem Statement

Tanpa deployment strategy yang jelas, risiko yang muncul:

- Perbedaan konfigurasi antara development dan production.
- Deployment yang tidak konsisten.
- Secret tersimpan di repository.
- Database migration menyebabkan downtime atau kehilangan data.
- Worker menggunakan versi aplikasi berbeda dari API.
- Deployment gagal tanpa rollback yang aman.
- Media processing menghabiskan resource API.
- Storage dan database tidak konsisten setelah deployment.
- Sulit memulihkan layanan setelah kegagalan.
- Perubahan aplikasi tidak dapat ditelusuri ke commit dan build tertentu.

3. Decision

MovieAIProducer menggunakan Environment-Separated, Container-Ready Deployment Architecture.

Prinsip utama:

1. Environment separation.
2. Reproducible builds.
3. Immutable deployment artifacts.
4. Automated CI/CD.
5. Configuration and secret separation.
6. Database migration governance.
7. Background worker isolation.
8. Health-based deployment validation.
9. Rollback and recovery capability.
10. Infrastructure automation.

MVP dapat dimulai dengan modular monolith pada satu deployment environment.

Arsitektur harus siap memisahkan worker dan komponen pendukung ketika kebutuhan operasional meningkat.

Microservices dan Kubernetes bukan persyaratan awal.

4. Deployment Principles

4.1 Git as Source of Truth

Source code dan deployment configuration yang diperlukan harus dikelola melalui version control.

Deployment harus dapat ditelusuri ke:

- Repository.
- Commit SHA.
- Build identifier.
- Release version.
- Configuration version.
- Database migration version.

Perubahan manual pada production harus dibatasi dan dicatat.

4.2 Immutable Artifacts

Build artifact harus dihasilkan melalui pipeline dan tidak diedit secara manual setelah build selesai.

Setiap deployment harus menggunakan artifact yang dapat diidentifikasi secara unik.

4.3 Environment Separation

Development, testing, staging, dan production harus memiliki batas konfigurasi serta data yang jelas.

4.4 Fail Safely

Jika health check, migration, atau validasi deployment gagal, pipeline harus menghentikan promosi release.

4.5 Gradual Complexity

Infrastruktur ditingkatkan berdasarkan kebutuhan terukur, bukan sekadar asumsi skala.

5. Deployment Environments

5.1 Development

Digunakan untuk:

- Feature development.
- Local integration.
- Debugging.
- Unit tests.
- Early prototyping.

Karakteristik:

- Development credentials.
- Local database atau isolated development database.
- Local storage adapter bila sesuai.
- Mock provider untuk testing.
- Debug logging.

5.2 Testing / CI

Digunakan untuk:

- Automated tests.
- Integration tests.
- Security tests.
- Database migration tests.
- Build validation.
- Contract validation.

Environment harus bersifat disposable bila memungkinkan.

5.3 Staging

Digunakan untuk:

- Release candidate validation.
- End-to-end tests.
- Deployment verification.
- Provider integration testing.
- Performance checks.
- User acceptance testing.

Staging harus mendekati production dalam konfigurasi dan perilaku, tanpa mencampur data privat production.

5.4 Production

Digunakan untuk layanan pengguna.

Persyaratan:

- Secure configuration.
- Production database.
- Persistent asset storage.
- Monitoring and alerting.
- Backup and recovery.
- Controlled deployments.
- Restricted administration.
- Operational runbooks.

6. Logical Deployment Architecture

Komponen deployment:

6.1 Web Frontend

Bertanggung jawab terhadap UI dan komunikasi dengan backend.

Dapat disajikan melalui static hosting atau application server sesuai kebutuhan framework.

6.2 Backend API

Menangani:

- Authentication.
- Authorization.
- Project management.
- Production domain operations.
- Asset management.
- QC requests.
- Workflow commands.

6.3 Background Workers

Menjalankan:

- AI provider jobs.
- Media processing.
- Video validation.
- Thumbnail generation.
- QC analysis.
- Long-running production tasks.

Worker tidak boleh bergantung pada API process yang harus tetap hidup selama job berlangsung.

6.4 Database

Menyimpan:

- Transactional metadata.
- Project data.
- Workflow states.
- Job records.
- Asset metadata.
- QC records.
- User and permission records.

6.5 Object Storage

Menyimpan binary media dan production artifacts.

6.6 Queue / Job Dispatch

Menghubungkan job dispatcher dengan worker.

Teknologi queue mengikuti ADR-0007 dan hasil repository audit.

6.7 Observability

Mengumpulkan logs, metrics, traces, dan operational events sesuai ADR-0013.

7. Deployment Topology Evolution

Stage 1: MVP

Karakteristik:

- Modular monolith.
- One primary application deployment.
- Separate worker process where needed.
- One selected relational database.
- Filesystem or object storage adapter.
- Basic monitoring.
- Automated CI.

Tujuan: membuktikan satu vertical production workflow secara lengkap.

Stage 2: Production Hardening

Penambahan:

- Separate API and worker deployment.
- Dedicated persistent object storage.
- Reliable job queue.
- Database backup automation.
- Centralized observability.
- Deployment health gates.
- Resource limits.

Stage 3: Scale Optimization

Jika metrik menunjukkan kebutuhan:

- Independent worker pools.
- Separate media processing workers.
- Horizontal API scaling.
- Dedicated database resources.
- Cache.
- Advanced queue management.
- CDN for authorized media delivery.

Stage 4: Distributed Deployment

Hanya jika ada kebutuhan operasional yang terbukti:

- Independently deployed domain services.
- Multi-region architecture.
- Advanced orchestration.
- Kubernetes or equivalent platform.
- Service-to-service identity.
- Distributed resilience mechanisms.

Setiap perubahan tahap harus didukung oleh capacity planning dan operational evidence.

8. Containerization Strategy

Aplikasi harus container-ready.

Container image harus:

- Dibangun dari reproducible build process.
- Menggunakan pinned dependencies.
- Menjalankan proses non-root jika memungkinkan.
- Menggunakan minimal runtime image yang sesuai.
- Memiliki health check.
- Tidak menyimpan persistent data di container filesystem.
- Tidak mengandung secret.
- Memiliki image provenance.
- Dipindai untuk vulnerability.

Docker atau compatible OCI tooling dapat digunakan setelah kompatibilitas repository diverifikasi.

9. Configuration Management

Configuration harus dipisahkan dari source code.

Kategori konfigurasi:

- Application settings.
- Environment settings.
- Database connection.
- Queue configuration.
- Storage configuration.
- Provider settings.
- Authentication configuration.
- Observability configuration.
- Feature flags.
- Resource limits.

Configuration harus divalidasi saat startup.

Jika required configuration tidak tersedia, aplikasi harus gagal dengan error yang jelas.

Jangan menggunakan production secret sebagai fallback untuk development atau testing.

10. Secret Management

Secret mencakup:

- Database credentials.
- OAuth client secrets.
- JWT signing keys.
- Encryption keys.
- AI provider API keys.
- Storage credentials.
- Queue credentials.
- External service tokens.

Ketentuan:

- Tidak disimpan dalam Git.
- Tidak dimasukkan ke container image.
- Tidak ditampilkan dalam logs.
- Akses dibatasi berdasarkan environment.
- Rotasi harus didukung.
- Secret yang bocor harus dapat dicabut.
- Production secrets harus terpisah dari staging secrets.

Gunakan secret manager atau mekanisme deployment secret yang sesuai dengan platform.

11. CI/CD Architecture

Pipeline utama:

1. Source checkout.
2. Dependency installation.
3. Dependency validation.
4. Formatting and linting.
5. Static analysis.
6. Unit tests.
7. Integration tests.
8. Security checks.
9. Database migration validation.
10. Frontend build.
11. Backend build.
12. Container image build.
13. Artifact scanning.
14. Artifact publication.
15. Staging deployment.
16. Smoke tests.
17. Release approval.
18. Production deployment.
19. Post-deployment verification.

Tidak semua tahap harus aktif pada MVP, tetapi pipeline harus memiliki jalur penambahan yang jelas.

11.1 CI Rules

Pull request harus melewati required checks sebelum merge.

Main branch harus selalu merepresentasikan kondisi source code yang telah melewati kebijakan CI.

Build yang gagal tidak boleh dipromosikan ke production.

11.2 Release Traceability

Setiap release harus memiliki:

- Release version.
- Commit SHA.
- Build ID.
- Artifact digest.
- Deployment timestamp.
- Environment.
- Migration version.
- Deployment result.

12. Database Migration Strategy

Database migration harus dikelola melalui versioned migration files.

Ketentuan:

- Migration harus dapat direview.
- Migration harus diuji di CI.
- Backup harus dipertimbangkan sebelum perubahan berisiko tinggi.
- Migration tidak boleh bergantung pada perubahan manual.
- Destructive migration memerlukan pemeriksaan khusus.
- Migration harus memiliki recovery plan.

12.1 Expand and Contract

Untuk perubahan schema yang berpotensi memengaruhi kompatibilitas:

1. Tambahkan struktur baru.
2. Deploy aplikasi yang kompatibel dengan struktur lama dan baru.
3. Migrasikan data.
4. Verifikasi hasil.
5. Hapus struktur lama melalui release terpisah.

Jangan menggabungkan perubahan destruktif dan deployment aplikasi tanpa strategi kompatibilitas.

12.2 Rollback

Rollback aplikasi dan rollback database adalah dua operasi berbeda.

Jangan menganggap setiap migration dapat dibalik dengan aman.

Untuk perubahan data destruktif, gunakan backup dan forward-fix strategy jika rollback langsung berisiko.

13. Deployment Strategy

Strategi awal:

Controlled Rolling or Replace Deployment, sesuai kemampuan hosting platform dan kebutuhan availability.

Untuk MVP, deployment sederhana dengan maintenance window dapat diterima jika kebutuhan uptime belum mengharuskan zero downtime.

13.1 Deployment Steps

1. Validate release artifact.
2. Validate environment configuration.
3. Verify database connectivity.
4. Run approved migration.
5. Deploy application.
6. Start or update workers.
7. Verify readiness.
8. Execute smoke tests.
9. Verify critical workflows.
10. Mark release successful.

13.2 Health Checks

Bedakan:

- Liveness: proses masih hidup.
- Readiness: aplikasi siap menerima traffic.
- Dependency health: status database, queue, dan storage.

Dependency failure tidak boleh selalu menyebabkan liveness gagal.

Readiness harus mencerminkan apakah aplikasi dapat menjalankan fungsi penting sesuai deployment policy.

14. Rollback and Recovery

Rollback harus mempertimbangkan:

- Application artifact.
- Database schema.
- Background jobs.
- Queue messages.
- Asset storage.
- External provider operations.
- Configuration changes.

14.1 Rollback Conditions

Rollback dapat dipertimbangkan jika:

- Application fails to start.
- Critical health checks fail.
- Error rate meningkat melewati threshold.
- Authentication gagal.
- Database compatibility bermasalah.
- Critical production workflow gagal.

14.2 Rollback Rules

- Gunakan artifact release sebelumnya yang sudah diverifikasi.
- Pertahankan migration compatibility.
- Jangan menghapus data baru secara otomatis.
- Periksa job yang sedang berjalan.
- Verifikasi asset dan metadata.
- Jalankan smoke tests setelah rollback.

Rollback tidak boleh mengklaim membatalkan operasi eksternal yang sudah diterima provider.

15. Worker Deployment

Worker harus dapat di-deploy dan dioperasikan secara terpisah dari API.

Ketentuan:

- Version compatibility dengan job schema.
- Graceful shutdown.
- Job lease handling.
- Retry and recovery.
- Resource limits.
- Concurrency configuration.
- Worker health metrics.
- Safe deployment during active jobs.

Job yang sedang berjalan harus diselesaikan atau ditangani melalui recovery mechanism sebelum worker dihentikan.

16. Resource and Capacity Management

Monitor:

- CPU.
- Memory.
- Disk.
- Network.
- Database connections.
- Queue depth.
- Worker concurrency.
- Storage growth.
- Media processing workload.

Media processing memerlukan resource profile yang berbeda dari API.

Jangan menjalankan transcoding atau analisis video berat pada API worker tanpa batas resource dan isolasi.

Capacity scaling harus berdasarkan metrik penggunaan aktual.

17. Infrastructure as Code

Infrastructure configuration sebaiknya dikelola sebagai code.

Cakupan dapat meliputi:

- Network configuration.
- Application deployment.
- Database provisioning.
- Storage provisioning.
- Queue configuration.
- Secret references.
- Monitoring configuration.
- Backup policies.

Perubahan infrastructure harus dapat direview dan ditelusuri.

Tool IaC belum ditentukan. Pemilihannya mengikuti deployment platform dan kebutuhan tim.

18. Security Requirements

Minimum deployment controls:

- TLS.
- Network segmentation.
- Restricted administrative access.
- Least-privilege service accounts.
- Secure secret management.
- Container image scanning.
- Dependency vulnerability checks.
- Firewall rules.
- Database access restrictions.
- Private storage.
- Backup encryption.
- Deployment audit logs.
- Secure CI credentials.
- Protected release approvals.

Production deployment credentials harus memiliki scope minimum yang diperlukan.

19. Backup and Disaster Recovery

Deployment harus terintegrasi dengan ADR-0019.

Persyaratan:

- Database backups.
- Asset storage backups or versioning.
- Configuration recovery.
- Secret recovery procedures.
- Release artifact retention.
- Restore testing.
- Recovery runbooks.
- RPO and RTO targets.

RPO dan RTO harus ditentukan berdasarkan dampak bisnis dan kemampuan infrastruktur.

Jangan mengklaim disaster recovery siap sebelum restore drill berhasil.

20. Deployment Observability

Setiap deployment harus menghasilkan event:

- Deployment started.
- Artifact verified.
- Migration started.
- Migration completed.
- Application started.
- Readiness passed.
- Smoke tests passed.
- Deployment completed.
- Rollback started.
- Rollback completed.
- Deployment failed.

Setiap event harus memiliki release ID dan commit SHA.

Integrasi mengikuti ADR-0013.

21. MVP Scope

Prioritas MVP:

1. Environment separation.
2. Versioned configuration.
3. Secret separation.
4. Automated CI.
5. Reproducible application build.
6. Basic deployment automation.
7. Database migration workflow.
8. Health and readiness checks.
9. Smoke tests.
10. Release traceability.
11. Basic rollback procedure.
12. Backup integration.

Kubernetes, multi-region deployment, advanced blue-green releases, dan service mesh bukan kebutuhan awal.

22. Implementation Sequence

Phase 1: Repository and Infrastructure Discovery

- Inspect current repository.
- Inspect application entrypoints.
- Identify runtime requirements.
- Identify database.
- Identify asset storage.
- Identify worker processes.
- Identify current hosting environment.

Phase 2: Environment Foundation

- Define environment configuration.
- Separate secrets.
- Define runtime settings.
- Define health endpoints.
- Define release identifiers.

Phase 3: CI Pipeline

- Dependency installation.
- Linting and static analysis.
- Unit tests.
- Integration tests.
- Build validation.
- Security checks.

Phase 4: Deployment Automation

- Build release artifact.
- Deploy to staging.
- Run migrations.
- Run smoke tests.
- Validate readiness.
- Promote approved release.

Phase 5: Production Hardening

- Backup automation.
- Rollback procedure.
- Deployment monitoring.
- Worker lifecycle management.
- Security hardening.

Phase 6: Scale Optimization

- Resource monitoring.
- Separate worker pools.
- Horizontal scaling.
- Storage optimization.
- Infrastructure automation.

23. Testing Requirements

Unit and Build Tests

- Configuration validation.
- Build reproducibility.
- Dependency lock validation.
- Health endpoint behavior.

CI Tests

- Lint.
- Static analysis.
- Unit tests.
- Integration tests.
- Security scanning.
- Migration validation.

Deployment Tests

- Clean deployment.
- Existing installation upgrade.
- Missing configuration.
- Invalid secret.
- Database unavailable.
- Storage unavailable.
- Worker startup failure.
- Readiness failure.
- Smoke test failure.

Recovery Tests

- Application rollback.
- Migration compatibility.
- Worker restart.
- Queue recovery.
- Backup restoration.
- Asset integrity after restore.

End-to-End Test

1. Merge an approved change.
2. Build a release artifact.
3. Deploy to staging.
4. Run migrations.
5. Run smoke tests.
6. Verify production workflow.
7. Promote release.
8. Verify production health.
9. Simulate deployment failure.
10. Execute recovery procedure.

24. Risks and Mitigations

Risk| Mitigation
Environment drift| Versioned configuration
Secret exposure| Secret management
Failed migrations| Migration validation and recovery
Worker incompatibility| Versioned job contracts
Deployment downtime| Health gates and compatible releases
Failed rollback| Retained immutable artifacts
Media resource exhaustion| Worker isolation
Database/storage inconsistency| Reconciliation
CI credential compromise| Scoped credentials
Premature infrastructure complexity| Incremental deployment evolution

25. Consequences

Positive

- Deployment becomes reproducible.
- Releases become traceable.
- Environment differences become controlled.
- Database changes become safer.
- Workers can scale independently.
- Recovery procedures become explicit.
- Infrastructure can evolve incrementally.

Trade-offs

- CI/CD maintenance effort.
- Infrastructure configuration complexity.
- Need for migration governance.
- Additional artifact and backup storage.
- Deployment verification adds release time.

26. Decision Validation Checklist

- [ ] Environment separation is defined.
- [ ] Git is the source of truth.
- [ ] Build artifacts are immutable and traceable.
- [ ] Configuration is separate from source code.
- [ ] Secrets are managed securely.
- [ ] CI validation is defined.
- [ ] Database migrations are versioned.
- [ ] Worker deployment is considered separately.
- [ ] Health and readiness checks exist.
- [ ] Rollback strategy is documented.
- [ ] Backup and restore are integrated.
- [ ] Deployment events are observable.
- [ ] Resource limits are defined.
- [ ] Infrastructure complexity is introduced incrementally.

27. Review and Acceptance Conditions

This ADR can move from Proposed to Accepted when:

1. Deployment topology is agreed.
2. Environment boundaries are defined.
3. Build and release strategy is approved.
4. Migration strategy is validated.
5. Worker deployment strategy is agreed.
6. Security controls are reviewed.
7. Observability is reconciled with ADR-0013.
8. Backup and recovery are reconciled with ADR-0019.
9. Hosting platform requirements are known.
10. Repository discovery confirms implementation feasibility.

Review this ADR if:

- Traffic or production volume increases substantially.
- High availability becomes a business requirement.
- Multi-region deployment becomes necessary.
- A new hosting platform is adopted.
- Compliance requirements change.

---

Final Principle:

Every MovieAIProducer release must be reproducible, traceable, verifiable, and recoverable.

A successful deployment is not merely an application that starts. It is a release whose configuration, dependencies, data compatibility, worker behavior, and critical production workflows have all been verified.
