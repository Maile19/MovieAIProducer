# Testing Strategy & Quality Assurance Framework - MovieAIProducer

## 1. Purpose
This document establishes the testing strategy to ensure business logic correctness, architectural integrity, continuity persistence, and professional production-grade quality for all AI-generated content.

## 2. Core Testing Principles
- **Automated First:** Critical paths must have automated test coverage.
- **Isolation:** AI provider integrations must use mocks/adapters for testing; core logic tests must not depend on external model availability.
- **Continuity Verification:** Tests must specifically validate Character/World DNA consistency across scenes.
- **Regression Focused:** Every significant change must trigger relevant regression suites.
- **Evidence-Based:** No task is "DONE" without explicit test evidence and passing results.

## 3. Testing Layers
- **Unit Tests:** Business logic (Domain layer), DNA/State transitions, Prompt compiler rules.
- **Integration Tests:** Database repositories, Provider adapters, File storage interaction.
- **API Tests:** Request/Response contract validation, Authorization checks.
- **Pipeline Tests:** End-to-end (E2E) workflow validation for the 12-step cinematic framework.
- **Continuity & QC Tests:** Automated checks for character/environment drift and quality threshold compliance.
- **Security Tests:** Vulnerability scanning, secret detection, and input validation.

## 4. Test Coverage Strategy
- **Critical Paths:** 100% coverage for MPB versioning, scene state transitions, and approval workflows.
- **Provider Adapters:** 100% contract coverage (validation of adapter response handling).
- **Domain Logic:** Unit test coverage for all continuity and QC business rules.

## 5. Execution Environment
- **Development:** Automated suites (Pytest) on local machines.
- **CI/CD:** Automated gate-keeping (GitHub Actions) requiring all tests to pass before merge.
- **Conformance:** Live conformance testing against actual AI providers for adapter verification.
