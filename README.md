# orby4middleware

**Vendor-neutral medical device, laboratory analyzer, and imaging modality interoperability middleware.**

orby4middleware is designed to sit between legacy/modern medical devices and an EMR, LIS, HIE,
or FHIR server. The core rule is simple: **normalize once, deliver many ways**.

> Status: early production-oriented implementation. It is not clinically validated software.
> Every device/model/profile must be site-validated before automatic clinical result delivery.

## Why it exists

Hospitals and laboratories often have a mixture of:

- old RS-232 analyzers using proprietary fixed-width or delimiter formats;
- ASTM/E1381/E1394-style analyzers;
- HL7 v2/MLLP analyzers and LIS systems;
- modern REST/JSON or FHIR-capable devices;
- CT/MRI/X-ray/ultrasound systems using DICOM/DICOMweb.

orby4middleware provides one gateway architecture for all of them without pretending that every
model from a manufacturer uses the same protocol.

## Architecture

```text
Legacy analyzers                     Modern devices                Imaging
RS232/RS422/TCP                      HL7/REST/FHIR                 DICOM
      |                                   |                         |
      v                                   v                         v
+----------------+                 +----------------+         +-----------+
| Orby Edge      |                 | Core ingest    |         | Orthanc*  |
| serial/TCP     |---------------->| normalization  |<--------| DICOMweb  |
| buffering      |    HTTPS        | matching/audit |         +-----------+
+----------------+                 +-------+--------+
                                          |
                           +--------------+--------------+
                           |              |              |
                           v              v              v
                        FHIR R4        HL7 ORU       REST/JSON
                           |              |              |
                           +--------------+--------------+
                                          |
                                         EMR

* optional component in Docker Compose
```

## Included protocol adapters

- Mindray BC-3000 Plus profile/parser and legacy serial handshake helper
- Generic fixed-width serial parser
- Generic delimiter serial parser
- Generic regex/configuration parser
- Generic ASTM-style record parser
- HL7 v2 ORU parser and MLLP sender
- REST/JSON ingest and delivery
- FHIR R4 `Observation` / `DiagnosticReport` bundle generation
- DICOM/DICOMweb integration boundary via optional Orthanc
- Plugin SDK for proprietary protocols

## Compatibility philosophy

There are two different claims and the project keeps them separate:

1. **Protocol-capable** — the gateway can speak the protocol family.
2. **Model-validated** — a specific model/profile has been verified against its vendor interface
   documentation and/or a real instrument at a site.

The catalog contains common manufacturers such as Mindray, Sysmex, Beckman Coulter, Abbott,
Roche, Siemens Healthineers, HORIBA, Nihon Kohden, Boule, Diatron, Erba, DIRUI, URIT, Genrui,
EDAN, Stago, Werfen/Instrumentation Laboratory, bioMérieux, BD, Cepheid, Radiometer, ARKRAY,
GE HealthCare, Philips, Canon Medical, Fujifilm, Carestream, Agfa, Samsung Medison, Esaote and
others. Presence in the catalog is **not** a claim that all models are automatically validated.

## Fast start

```bash
cp .env.example .env
docker compose up --build
```

Core API: `http://localhost:8080`

OpenAPI: `http://localhost:8080/docs`

Admin UI: `http://localhost:8080/admin`

Create an order/accession mapping first, then ingest a device result. Unmatched samples are held.

## Legacy analyzer onboarding

1. Get the official host/LIS interface manual for the exact model and firmware.
2. Connect the analyzer to an isolated edge PC using the correct RS-232/RS-422/USB adapter.
3. Run capture-only mode with de-identified test samples:

```bash
orby4-edge capture --port /dev/ttyUSB0 --baud 9600 --output raw-captures/device.bin
```

4. Build a YAML model profile using one of the generic parsers, or write a small plugin if required.
5. Add parser fixtures/tests.
6. Validate every mapped parameter, unit, flag, accession and duplicate condition.
7. Only then enable delivery to the clinical EMR.

See `docs/DEVICE_ONBOARDING.md` and `docs/COMPATIBILITY.md`.

## Docker profiles

The default Compose stack runs the Orby API plus PostgreSQL. Optional components are available:

```bash
# Include Orthanc for DICOM/DICOMweb
COMPOSE_PROFILES=imaging docker compose up --build

# Include HAPI FHIR JPA as a standalone FHIR endpoint
COMPOSE_PROFILES=fhir docker compose up --build
```

Open Integration Engine is intentionally documented as an external/optional integration-engine
peer rather than embedded into the Python package. See `docs/ARCHITECTURE.md`.

## Safety properties

- No fuzzy patient matching.
- Unmatched accessions are held for review.
- Raw inbound payloads can be retained for traceability.
- SHA-256 idempotency prevents simple duplicate ingestion.
- Delivery attempts and errors are audited.
- Device profiles carry validation status.
- The edge agent can spool locally during network/EMR outages.

## Tests

```bash
python -m pip install -e '.[dev]'
pytest
```

## License

Apache-2.0. Third-party services run under their own licenses; see `NOTICE.md`.
