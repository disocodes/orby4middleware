# Architecture

## Components

### Orby Edge
Runs close to legacy analyzers. It owns physical serial/TCP connectivity, protocol framing,
local buffering and secure forwarding. Keep edge listeners on trusted lab networks only.

### Orby Core
Provides normalized result ingestion, accession/order matching, persistence, audit, idempotency,
result review, and delivery to EMRs/LIS/HIEs.

### Optional ecosystem components
- **Orthanc**: DICOM store / DICOMweb bridge for imaging workflows.
- **HAPI FHIR**: standalone FHIR repository if the destination EMR is not itself the FHIR store.
- **Open Integration Engine**: useful as an adjacent enterprise routing/transformation engine when
  a hospital already standardizes on integration-engine channels.

## Normalized model

Every device adapter returns a `NormalizedResult` with:

- source device ID, manufacturer/model/profile;
- sample/accession identifier;
- observation timestamp;
- one or more observations (code, value, unit, flags, reference range);
- raw-payload hash and optional retained raw payload;
- protocol and source metadata.

Downstream delivery is independent of the original device protocol.

## Clinical matching boundary

The preferred correlation key is a laboratory accession/order identifier. Patient name matching is
never used automatically. A result with no exact order mapping enters `UNMATCHED`.

## Bidirectional future path

The model leaves room for bidirectional workflows (orders/worklists/query responses), but the first
release focuses on safe result ingestion. Bidirectional support must be enabled only for profiles
that explicitly document it.
