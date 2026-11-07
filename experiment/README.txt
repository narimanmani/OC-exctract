Java-backend CIMET/OC experiment - scope version 1.1

Active extraction candidates:
- GeoServer Cloud (geoserver/geoserver-cloud)
- Camunda (camunda/camunda)
- adorsys XS2A (adorsys/xs2a)
- Apache InLong (apache/inlong)
- Apollo (apolloconfig/apollo)

These are candidates, not validated prediction-bearing systems. Java-service
inventory, deployment boundaries and framework coverage must still pass.
Camunda's observed parser failure remains unresolved.

Language and framework are separate inclusion dimensions:
- Kapua, Pravega and Liberty Bikes have Java backends; their JAX-RS coverage is
  on hold for the pinned extractor.
- Hono is Java, but message/protocol coverage remains unvalidated.
- CCPay is Java; a single deployed service cannot establish cross-service OC.

Spinnaker is excluded from the Java-only primary cohort because production
backend code mixes Java and Groovy. Keep the original Spinnaker pilot as a
reference only. OpenLMIS Contract Tests is excluded because it is a test
repository, not because it is non-Java.

Frontend JavaScript does not exclude a Java backend. Validate Java implementation
at the deployed-service boundary. A later language inventory can exclude a
candidate service with substantial non-Java production implementation.
OC counts contributions within those same eligible service boundaries,
including deployment/configuration changes; it is not filtered to .java files
alone.

The workflow matrix reads only manifest.json systems, currently five candidates.
Held/excluded cases remain in the audit and cannot be launched by run_case.py.

The earlier 12-case pilot and its outputs remain unchanged:
https://github.com/narimanmani/OC-exctract/actions/runs/42340743237
Its source manifest is archived at archive/manifest_12case_pilot_7ed8cb1.json.
The Java-only scope amendment is not a new extraction or prediction result.

The pinned tools, immutable source cutoffs and pilot dates are preserved.
The adapter accumulates controller operations and preserves nonfinite metric
flags; upstream aggregate metrics remain a separate comparison.
Raw component maps are not deployment-validated services. Full weekly
extraction, organizational comparator validation, models, original-method
Granger tests and independent review remain subsequent stages.
