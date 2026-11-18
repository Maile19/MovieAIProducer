# Observability, Logging & Monitoring Specification - MovieAIProducer

## 1. Vision
This specification establishes an observability framework ensuring MovieAIProducer is transparent, debuggable, and verifiable. It treats logs, metrics, and traces as first-class citizens, enabling precise tracking of AI pipeline performance, production job status, and cost metrics.

## 2. Pillars of Observability
- **Logs:** Structured JSON logs capturing operational events (PII/Secret-masked).
- **Metrics:** Quantitative data (Latency, Error Rates, Queue Depth, Generation Costs, QC scores).
- **Tracing:** Correlation IDs tracking requests across Frontend, API, Orchestrator, and Provider Adapters.

## 3. Operational Implementation
- **Standardized Format:** All logs must follow a structured JSON schema including `correlation_id`, `project_id`, `scene_id`, and `shot_id`.
- **Health Indicators:** Implementation of `Liveness` and `Readiness` endpoints.
- **Provider Observability:** Specialized monitoring for AI Model latency, failure rates, and token/usage consumption (Cost tracking).
- **Continuity & QC Monitoring:** Tracking of continuity failures and aggregate QC scores per project/scene.

## 4. Monitoring Layers
- **System Metrics:** API latency, throughput, DB connections, Worker queue depth.
- **AI Pipeline Metrics:** Stage completion rates, revision frequency, provider success/failure rates.
- **Business/Production Metrics:** Project progress, budget consumption, and approval bottlenecks.

## 5. Incident & Alerting
- **Severity Levels:** SEV-1 (Critical) to SEV-4 (Minor).
- **Alerting Rules:** Threshold-based alerts (e.g., error rate > 5%, cost budget depletion) routed via appropriate channels, preventing "alert fatigue" through deduplication.
- **Investigation:** Every critical incident requires a post-mortem referencing the `correlation_id` to trace the failure origin.

## 6. Implementation Guidelines
- **Zero-Secret Policy:** Explicitly ensure logs/traces never contain API keys, session tokens, or sensitive user prompt content.
- **Performance:** Observability overhead must be minimal (use asynchronous logging/metrics).
- **Traceability:** Every cinematic shot must be linkable to its generation logs, provider job ID, and QC result.
