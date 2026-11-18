# Development & Contribution Guidelines - MovieAIProducer

## 1. Vision
This document standardizes contribution protocols to ensure MovieAIProducer remains modular, secure, and maintainable. All contributors (human or AI) must adhere to these standards to maintain architectural integrity and quality gates.

## 2. Core Principles
- **Clean Architecture:** Domain logic remains isolated from infrastructure and presentation layers.
- **Source of Truth:** GitHub is the source of truth for code, documentation, and history.
- **Traceability:** Every change must have a clear purpose, architectural justification, and verification evidence.
- **Plan → Execute → Monitor:** Adherence to this strict operational loop is mandatory.

## 3. Workflow Protocol
- **Discovery:** Audit the repository and architecture documentation before proposing any changes.
- **Small Changes:** Implement features incrementally with isolated commits.
- **File SOP:** Read → Review → Backup → Plan → Edit → Test → Clean → Report.
- **Testing:** Unit, Integration, API, and Regression tests are mandatory for all changes.
- **Documentation:** Architecture, API specs, and Data Models must be updated *before* or *during* code changes, never after the fact.

## 4. Coding Standards
- **Modular Monolith:** Strict module boundaries. No circular dependencies.
- **Explicit Interfaces:** AI providers and external services must interact via standardized adapters.
- **Security:** Strict PII/Secret handling (No commits of keys, no logs of sensitive data).
- **Naming:** Follow project-standard naming conventions for domain entities and resources.

## 5. Pull Request & Commit Rules
- **Conventional Commits:** Use `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- **Review:** All changes require explicit approval, verification of test results, and compliance with acceptance criteria.
- **Definition of Done:** Documentation updated, tests passed, regression checked, no unresolved critical defects.

## 6. Security & Integrity
- **Secrets:** Use `.env` (excluded from Git) and secret managers.
- **Data Integrity:** Database migrations must be tested and backward-compatible (Expand-and-Contract).
- **Injection Protection:** Strict validation of AI prompts, file uploads, and user input.

## 7. AI Agent Guidelines
- Agents must adhere to `AGENTS.md`.
- No self-authored requirements without approval.
- Execution must provide a full report on files inspected, changed, tests executed, and risks identified.
