# Java-only scope amendment

Date: 7 November 2026. Scope version: 1.1.

The primary experiment is limited to Java-implemented backend services.
Repository-wide language percentages are not the inclusion rule: frontend
assets and build scripts do not change the backend implementation language.

| Status | Cases | Reason |
| --- | --- | --- |
| Active Java extraction candidates | GeoServer Cloud, Camunda, adorsys XS2A, Apache InLong, Apollo | The pilot extracted Java controller metrics; service and route coverage validation remains pending. |
| Java cases on framework/protocol hold | Eclipse Kapua, Pravega, Liberty Bikes, Eclipse Hono | Java is in scope, but the pinned extractor lacks demonstrated interface coverage. |
| Java case on cross-service scope hold | HMCTS CCPay | One deployable service may make cross-service OC inapplicable; latest pilot also has a parser failure. |
| Outside the primary cohort | Spinnaker | Production Java/Groovy backend mixture. Retain the original pilot as reference. |
| Outside the primary cohort | OpenLMIS Contract Tests | Test-repository scope rather than backend implementation. |

The active five are candidates, not a claim of five valid microservice systems.
Do not select the better-performing cases or fill unsupported measurements with
zero. Preserve all exclusion/hold reasons and the original 12-case pilot.

The workflow matrix now reads only the five active candidates. The driver rejects
held/excluded cases. Java-only filtering does not fix JAX-RS coverage, parser
exceptions, or deployment-boundary validity. No new extraction or statistical
results have been produced by this scope amendment.
