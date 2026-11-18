# ADR-0013: Observability Stack

- Project: MovieAIProducer
- ADR ID: ADR-0013
- Title: Observability Stack
- Version: 1.0
- Date: 2026-11-19
- Status: Proposed
- Decision Owners: Product Owner, Technical Architect, Infrastructure Owner
- Related ADRs: ADR-0001, ADR-0003, ADR-0005, ADR-0006, ADR-0007, ADR-0010, ADR-0011, ADR-0012

---

1. Context

MovieAIProducer mengoperasikan sistem produksi film berbasis AI yang melibatkan banyak komponen:

- Frontend application.
- Backend API.
- Domain modules.
- AI agents.
- LLM providers.
- Image generation providers.
- Video generation providers.
- Audio providers.
- Prompt compilation engine.
- Production workflow engine.
- Background workers.
- Asset storage.
- Continuity engine.
- Quality Control engine.
- Database.
- External integrations.

Proses produksi dapat berlangsung lama, bersifat asynchronous, dan bergantung pada provider eksternal.

Sistem harus mampu menjelaskan bukan hanya apakah aplikasi berjalan, tetapi juga apa yang terjadi selama produksi.

2. Problem Statement

Tanpa observability yang terstruktur, sistem berisiko mengalami:

- Sulit melacak kegagalan antarservice.
- Job berhenti tanpa diketahui.
- AI agent menghasilkan output yang tidak valid.
- Provider mengalami timeout atau degradation.
- Biaya generasi meningkat tanpa terdeteksi.
- Workflow terjebak dalam state tertentu.
- Asset gagal diproses.
- QC berjalan terlalu lama.
- Error tidak dapat direproduksi.
- Tidak tersedia informasi yang cukup untuk incident investigation.

Log saja tidak cukup untuk menjelaskan keseluruhan perilaku sistem.

3. Decision

MovieAIProducer menggunakan Unified, Structured, Correlation-Based Observability Architecture.

Observability dibangun melalui tiga pilar:

1. Logs.
2. Metrics.
3. Distributed Traces.

Ditambah:

4. Audit Events.
5. Operational Alerts.
6. AI and Production Cost Telemetry.

Arsitektur harus menggunakan instrumentation yang provider-independent dan mendukung OpenTelemetry sebagai standar instrumentasi.

Backend, worker, orchestration, dan provider adapters harus menggunakan standar observability yang konsisten.

Vendor observability belum ditetapkan. Pemilihan dilakukan berdasarkan kebutuhan, biaya, deployment, dan kapasitas operasional.

4. Architectural Principles

4.1 Observability by Design

Setiap domain penting harus menghasilkan telemetry yang relevan sejak awal implementasi.

4.2 Correlation Across Components

Setiap proses harus dapat ditelusuri melalui correlation identifiers.

4.3 Structured Data

Log dan event harus memiliki struktur yang dapat dicari dan dianalisis.

4.4 Privacy and Security

Telemetry tidak boleh membocorkan credential, token, data pribadi, atau konten produksi yang tidak diperlukan.

4.5 Actionable Monitoring

Dashboard dan alert harus mengarah pada tindakan operasional yang jelas.

4.6 Cost Awareness

Biaya AI, storage, media processing, dan infrastructure harus dapat diukur.

4.7 Vendor Independence

Instrumentation tidak boleh bergantung pada vendor tertentu.

5. Observability Architecture

Komponen konseptual:

5.1 Instrumentation Layer

Instrumentasi ditempatkan pada:

- API requests.
- Domain operations.
- AI agent execution.
- Workflow transitions.
- Job lifecycle.
- Provider calls.
- Storage operations.
- Media processing.
- QC runs.
- Approval operations.

5.2 Telemetry Collector

Mengumpulkan:

- Application logs.
- Infrastructure metrics.
- Distributed traces.
- Custom business metrics.
- Operational events.

OpenTelemetry Collector dapat digunakan sebagai komponen pengumpulan dan pemrosesan telemetry.

5.3 Telemetry Storage

Menyimpan telemetry sesuai jenisnya:

- Log storage.
- Metrics storage.
- Trace storage.
- Audit event storage.
- Cost and usage records.

Retention dan storage backend dapat berbeda sesuai kebutuhan.

5.4 Visualization Layer

Menyediakan:

- System health dashboard.
- API performance dashboard.
- Workflow dashboard.
- AI provider dashboard.
- Job processing dashboard.
- QC dashboard.
- Storage dashboard.
- Cost dashboard.
- Security dashboard.

5.5 Alerting Layer

Mengirim notifikasi saat kondisi penting terjadi.

Channel notifikasi ditentukan berdasarkan deployment dan integrasi yang tersedia.

6. Logging Architecture

Gunakan structured logging dengan format JSON pada production environment.

Setiap log entry minimal memiliki:

- timestamp.
- severity.
- service_name.
- environment.
- event_name.
- correlation_id.
- trace_id, jika tersedia.
- span_id, jika tersedia.
- actor_type, jika relevan.
- actor_id, jika aman.
- project_id, jika relevan.
- operation.
- outcome.
- error_code, jika terjadi kegagalan.

6.1 Log Levels

- TRACE: Detail eksekusi sangat granular, hanya bila diperlukan.
- DEBUG: Informasi debugging.
- INFO: Aktivitas normal.
- WARN: Kondisi abnormal yang belum menjadi kegagalan.
- ERROR: Operasi gagal.
- FATAL: Kegagalan kritis yang mengganggu proses utama.

6.2 Logging Rules

- Jangan mencatat password.
- Jangan mencatat access token.
- Jangan mencatat refresh token.
- Jangan mencatat API keys.
- Jangan mencatat signed URLs secara lengkap.
- Jangan mencatat secret provider.
- Jangan menyimpan seluruh prompt atau media secara otomatis dalam log.
- Redact sensitive fields.
- Hindari logging berlebihan pada loop dan polling.
- Gunakan error codes yang konsisten.

Konten prompt, script, dan media hanya boleh disimpan melalui mekanisme provenance atau artifact storage yang memiliki access policy tersendiri.

7. Distributed Tracing

Distributed tracing digunakan untuk menelusuri proses yang melintasi beberapa komponen.

Contoh alur:

1. User mengirim production request.
2. API menerima request.
3. Workflow engine membuat task.
4. Job dispatcher mengirim job.
5. Worker mengambil job.
6. Prompt compiler menyusun prompt.
7. Provider adapter mengirim request.
8. Provider menghasilkan output.
9. Asset service menyimpan hasil.
10. QC Engine memeriksa asset.
11. Workflow menerima hasil.

Setiap proses harus mempertahankan trace context ketika berpindah komponen.

7.1 Trace Attributes

Contoh attributes:

- service.name.
- operation.name.
- project.id.
- workflow.id.
- task.id.
- job.id.
- scene.id.
- shot.id.
- provider.id.
- model.id.
- asset.id.
- qc.run_id.

Attributes yang mengandung data sensitif harus dihilangkan atau disamarkan.

7.2 Long-Running Jobs

Job yang berjalan lama tidak harus mempertahankan satu span terbuka selama seluruh durasinya.

Gunakan trace yang terhubung melalui:

- Trace context propagation.
- Span links.
- Job identifiers.
- Correlation identifiers.

Hal ini menjaga tracing tetap praktis dan tidak menghasilkan span yang terlalu panjang.

8. Metrics Architecture

Metrics harus mencakup empat kelompok.

8.1 Infrastructure Metrics

- CPU utilization.
- Memory utilization.
- Disk usage.
- Disk I/O.
- Network throughput.
- Database connection usage.
- Worker utilization.
- Queue depth.
- Storage consumption.

8.2 Application Metrics

- API request count.
- API latency.
- HTTP error rate.
- Request throughput.
- Authentication failure rate.
- Database query latency.
- Background processing latency.
- Application exception count.

8.3 Production Metrics

- Active projects.
- Active production workflows.
- Completed scenes.
- Completed shots.
- Failed production tasks.
- Rework count.
- Pending approvals.
- QC pass rate.
- QC blocker rate.
- Asset processing failures.

8.4 AI Provider Metrics

- Provider request count.
- Provider success rate.
- Provider latency.
- Provider timeout count.
- Rate-limit responses.
- Retry count.
- Fallback count.
- Generation failure rate.
- Usage units.
- Estimated cost.
- Actual cost where available.

Provider usage and cost must distinguish measured values from estimates.

9. AI Agent Observability

Setiap AI agent execution harus dapat ditelusuri.

Minimum information:

- Agent ID.
- Agent type.
- Agent version.
- Task ID.
- Workflow ID.
- Project scope.
- Model provider.
- Model identifier.
- Execution status.
- Start time.
- End time.
- Token usage where available.
- Cost estimate.
- Retry count.
- Tool invocation summary.
- Output reference.
- Validation result.

9.1 Agent Execution Events

Contoh:

- "agent.execution.started"
- "agent.execution.completed"
- "agent.execution.failed"
- "agent.tool.invoked"
- "agent.tool.failed"
- "agent.output.validated"
- "agent.output.rejected"
- "agent.approval.required"

9.2 Agent Performance

Monitor:

- Completion rate.
- Failure rate.
- Average execution duration.
- Tool failure rate.
- Output validation failure.
- Retry frequency.
- Cost per task.
- Human rejection rate.

Agent quality metrics tidak boleh disamakan dengan sekadar jumlah output yang berhasil dibuat.

10. Provider Observability

Setiap provider adapter harus melaporkan:

- Provider identity.
- Model identity.
- Operation type.
- Request timestamp.
- Response timestamp.
- Request status.
- HTTP or provider error code.
- Latency.
- Usage information.
- Cost information.
- Retry status.
- Fallback information.

Provider health harus dapat ditentukan melalui bukti operasional.

Status konseptual:

- HEALTHY.
- DEGRADED.
- UNAVAILABLE.
- RATE_LIMITED.
- UNKNOWN.

Jangan menganggap provider sehat hanya karena API endpoint dapat dijangkau.

11. Workflow and Job Observability

Workflow Engine dan Async Job Processing harus menyediakan:

- Workflow status.
- Current stage.
- Current task.
- Task dependency status.
- Queue waiting time.
- Job execution duration.
- Retry count.
- Stale job count.
- Failed job count.
- Dead-letter count.
- Cancellation request status.
- Human approval waiting time.

11.1 Stuck Workflow Detection

Sistem harus mendeteksi:

- Workflow tidak mengalami progress.
- Task menunggu dependency terlalu lama.
- Job tidak memiliki heartbeat.
- Worker kehilangan lease.
- Approval tertunda.
- Provider job tidak memberikan status sesuai timeout policy.

Detection harus mempertimbangkan expected duration dan jenis job. Job panjang tidak boleh dianggap gagal hanya karena melewati batas waktu generik.

12. AI Cost and Usage Observability

Biaya merupakan bagian penting dari observability.

Sistem harus mengukur biaya berdasarkan:

- Project.
- User.
- Workflow.
- Scene.
- Shot.
- Task.
- Agent.
- Provider.
- Model.
- Modality.

Kategori biaya:

- LLM tokens.
- Image generation.
- Video generation.
- Voice generation.
- Music and SFX.
- Media analysis.
- Storage.
- Data transfer.
- Rendering.
- Infrastructure.

12.1 Cost Accuracy

Setiap cost record harus menunjukkan sumber:

- PROVIDER_REPORTED.
- CONTRACT_CALCULATED.
- ESTIMATED.
- UNKNOWN.

Jangan menampilkan estimated cost sebagai actual cost.

12.2 Budget Monitoring

Policy dapat menetapkan:

- Project budget.
- Workflow budget.
- Scene budget.
- Provider budget.
- Daily budget.
- Monthly budget.

Alert dapat dipicu saat penggunaan mendekati atau melewati batas.

Budget enforcement harus dilakukan oleh domain yang memiliki kewenangan atas pengeluaran, bukan hanya melalui dashboard observability.

13. Audit Events and Observability

Audit events berbeda dari application logs.

Audit events digunakan untuk mencatat tindakan yang membutuhkan akuntabilitas.

Contoh:

- User login.
- Permission changes.
- MPB approval.
- Production override.
- QC approval.
- Final delivery approval.
- Asset deletion.
- Security policy changes.

Audit event harus mempunyai:

- Actor.
- Action.
- Target resource.
- Timestamp.
- Result.
- Project context.
- Correlation ID.

Audit records mengikuti keamanan dan retention policy ADR-0011.

Telemetry tidak boleh menjadi satu-satunya penyimpanan authoritative untuk audit.

14. Alerting Architecture

Alert harus berdasarkan kondisi yang dapat ditindaklanjuti.

14.1 Critical Alerts

- API unavailable.
- Database unavailable.
- Storage unavailable.
- Critical job processing failure.
- Persistent queue backlog.
- Data integrity failure.
- Security incident.
- Backup failure.
- Major provider outage affecting production.

14.2 Warning Alerts

- Elevated API latency.
- High error rate.
- Provider degradation.
- Increasing queue depth.
- Storage approaching quota.
- Repeated job retries.
- QC processing delays.
- Unusual cost growth.

14.3 Alert Rules

Setiap alert harus memiliki:

- Alert ID.
- Severity.
- Trigger condition.
- Evaluation window.
- Notification policy.
- Owner.
- Runbook reference.
- Recovery condition.

Hindari alert yang terlalu sensitif sehingga menghasilkan notification fatigue.

15. Dashboards

Dashboard utama:

15.1 Executive Overview

- Overall platform health.
- Active projects.
- Production completion.
- Critical incidents.
- Estimated and reported costs.

15.2 System Health

- API latency.
- Error rate.
- CPU and memory.
- Database health.
- Storage health.

15.3 Production Operations

- Workflow progress.
- Active jobs.
- Failed jobs.
- Pending approvals.
- Rework backlog.

15.4 AI Provider Operations

- Provider availability.
- Model latency.
- Failure rates.
- Rate limits.
- Usage and cost.

15.5 Quality Operations

- QC completion.
- QC pass/fail.
- Critical blockers.
- Rework rate.
- Human review backlog.

15.6 Asset Operations

- Storage consumption.
- Upload failures.
- Processing backlog.
- Integrity failures.
- Orphaned objects.

15.7 Security Operations

- Failed logins.
- Authorization denials.
- Suspicious activity.
- Privileged operations.
- Token and session events.

Dashboard harus menampilkan waktu pengukuran, definisi metric, dan batasan data.

16. Sampling and Cardinality

Telemetry harus dirancang agar tidak membebani sistem.

Ketentuan:

- Trace sampling dapat diterapkan berdasarkan traffic.
- Error traces harus diprioritaskan.
- Critical workflows dapat menggunakan sampling policy khusus.
- Metrics label tidak boleh menggunakan nilai unik berjumlah sangat tinggi tanpa alasan.
- Prompt text dan raw content tidak boleh dijadikan metric labels.
- High-cardinality identifiers lebih cocok berada dalam trace atau log.

Sampling tidak boleh menghilangkan kebutuhan audit.

Audit records harus mengikuti persistence policy tersendiri.

17. Security and Privacy

Observability pipeline harus mengikuti prinsip:

- Least privilege.
- TLS in transit.
- Encryption at rest.
- Restricted telemetry access.
- Secret redaction.
- Personal data minimization.
- Project-level access controls.
- Retention policy.
- Audit access to sensitive telemetry.
- Secure export and integration.

Raw prompt, script, audio, dan video tidak boleh dikirim ke observability backend tanpa kebutuhan yang jelas dan persetujuan policy.

18. Retention Policy

Retention harus dikonfigurasi berdasarkan jenis data.

Data| Retention principle
Debug logs| Short-lived
Application logs| Operational retention
Metrics| Retain for trend analysis
Traces| Sampling and retention policy
Audit events| Security and governance policy
Cost records| Financial reconciliation requirements
QC records| Production traceability requirements

Nilai retensi final ditentukan berdasarkan biaya, kebutuhan operasional, kontrak, dan ketentuan hukum yang berlaku.

19. API and Instrumentation Standards

Instrumentation harus mendukung:

- OpenTelemetry traces.
- OpenTelemetry metrics.
- Structured logs.
- Consistent correlation IDs.
- Standard error codes.
- Semantic attributes.
- Context propagation.

Endpoint operasional dapat mencakup:

- "GET /health"
- "GET /health/live"
- "GET /health/ready"
- "GET /metrics"

Metrics endpoint harus dibatasi ke jaringan dan identitas operasional yang berwenang.

Health endpoint harus membedakan liveness dan readiness.

Jangan mengungkap secret, database credentials, atau detail internal sensitif melalui health responses.

20. Reliability and Failure Handling

Observability harus tetap aman ketika telemetry backend gagal.

Ketentuan:

- Aplikasi tidak boleh gagal hanya karena log exporter tidak tersedia.
- Telemetry harus memiliki buffering dan bounded queues bila diperlukan.
- Export failure harus terukur.
- Backpressure harus ditangani.
- Critical audit persistence tidak boleh bergantung hanya pada telemetry exporter.
- Disk exhaustion akibat log harus dicegah.
- Sampling dan throttling harus tersedia.

Kegagalan observability backend tidak boleh membuat data transaksi hilang atau mengubah hasil produksi.

21. MVP Scope

Prioritas MVP:

1. Structured JSON logging.
2. Correlation ID propagation.
3. Request and error metrics.
4. Workflow and job metrics.
5. Provider request metrics.
6. Basic distributed tracing.
7. System health endpoints.
8. Basic dashboards.
9. Critical alerting.
10. AI usage and cost records.
11. Security event visibility.
12. Log redaction.

Vendor-specific analytics dan advanced anomaly detection dapat ditambahkan setelah kebutuhan terukur.

22. Implementation Sequence

Phase 1: Instrumentation Foundation

- Define telemetry standards.
- Define correlation IDs.
- Define log schema.
- Add API instrumentation.
- Add error classification.

Phase 2: Application and Infrastructure Metrics

- Instrument backend.
- Instrument database.
- Instrument workers.
- Add health checks.
- Add basic dashboards.

Phase 3: Workflow and AI Observability

- Instrument workflow lifecycle.
- Instrument async jobs.
- Instrument agents.
- Instrument provider adapters.
- Record usage and cost.

Phase 4: Distributed Tracing

- Add trace propagation.
- Connect API and worker traces.
- Add provider spans.
- Add asset and QC spans.
- Validate long-running job trace links.

Phase 5: Alerting

- Define alert policies.
- Implement critical alerts.
- Implement warning alerts.
- Link alerts to runbooks.
- Test notification delivery.

Phase 6: Governance and Optimization

- Implement retention.
- Apply sampling.
- Monitor telemetry costs.
- Improve redaction.
- Review dashboards and alert quality.

23. Testing Requirements

Unit Tests

- Log schema validation.
- Secret redaction.
- Metric naming.
- Correlation ID generation.
- Cost classification.
- Error classification.

Integration Tests

- API to worker trace propagation.
- Provider trace propagation.
- Workflow event metrics.
- Storage instrumentation.
- QC instrumentation.
- Telemetry exporter failure.

Reliability Tests

- Collector unavailable.
- Telemetry queue full.
- Export timeout.
- High traffic.
- Log rotation.
- Disk pressure.
- Sampling behavior.

Security Tests

- Secret leakage.
- Sensitive prompt leakage.
- Unauthorized dashboard access.
- Metrics endpoint exposure.
- Audit record tampering.
- Cross-project telemetry access.

End-to-End Tests

1. Start production workflow.
2. Create job.
3. Execute AI provider call.
4. Store generated asset.
5. Run QC.
6. Trigger a simulated failure.
7. Trace the failure across components.
8. Verify metrics and logs.
9. Confirm alert delivery.
10. Verify no sensitive data appears in telemetry.

24. Risks and Mitigations

Risk| Mitigation
Excessive telemetry cost| Sampling and retention
High-cardinality metrics| Label governance
Sensitive data leakage| Redaction and minimization
Alert fatigue| Actionable thresholds
Missing distributed context| Context propagation
Telemetry backend failure| Buffering and graceful degradation
Inaccurate AI costs| Explicit source classification
Long-running trace problems| Span links and job correlation
Audit data loss| Separate authoritative audit persistence

25. Consequences

Positive

- System behavior becomes observable.
- Production failures become easier to investigate.
- AI provider reliability can be compared.
- Production costs become measurable.
- Workflow bottlenecks become visible.
- Security and approval events become traceable.
- Incident response becomes more systematic.

Trade-offs

- Additional infrastructure and storage costs.
- Instrumentation overhead.
- Telemetry governance complexity.
- Need for alert maintenance.
- Retention and privacy management requirements.

26. Decision Validation Checklist

- [ ] Logs, metrics, and traces are defined.
- [ ] OpenTelemetry instrumentation is supported.
- [ ] Correlation IDs propagate across components.
- [ ] AI agent execution is observable.
- [ ] Provider reliability is measurable.
- [ ] Workflow and job states are measurable.
- [ ] AI usage and cost sources are distinguished.
- [ ] Audit events remain independently authoritative.
- [ ] Sensitive data is redacted.
- [ ] Dashboards are defined.
- [ ] Critical alerts have runbooks.
- [ ] Telemetry failure does not break production.
- [ ] Sampling and cardinality policies exist.
- [ ] Retention policies are documented.

27. Review and Acceptance Conditions

This ADR can move from Proposed to Accepted when:

1. Telemetry architecture is approved.
2. Instrumentation standards are agreed.
3. Correlation strategy is defined.
4. Security and privacy requirements are reviewed.
5. Metrics and dashboard priorities are approved.
6. Cost tracking requirements are reconciled with provider architecture.
7. Audit persistence is reconciled with ADR-0011.
8. Job and workflow instrumentation is reconciled with ADR-0005 and ADR-0007.
9. Deployment and operational requirements are reviewed.
10. Repository discovery confirms implementation feasibility.

Review this ADR if:

- Platform scale changes substantially.
- Observability cost becomes disproportionate.
- A distributed deployment architecture is introduced.
- New privacy or compliance requirements emerge.
- Operational monitoring requirements change.

---

Final Principle:

MovieAIProducer must be able to explain what happened, where it happened, why it happened, which resources were affected, how much it cost, and what action is required.

A production system that cannot observe its own execution cannot reliably improve or recover.
