# Operator Console

The browser console is available at `/admin` and is intended to onboard devices without editing YAML by hand.

## Safety model

Saving a device configuration and enabling clinical result delivery are separate operations.

Automatic delivery is locked until:

1. the device has completed a successful parse preview; and
2. its validation state is no longer `experimental`.

An unmatched accession is always held. The gateway does not use patient-name similarity or other fuzzy matching to assign a result.

## Five-step onboarding workflow

### 1. Identity

Choose a manufacturer, model/profile and a unique device key. The catalog is protocol-oriented: presence of a manufacturer does not mean every model is already validated.

### 2. Connection

Record the device connection settings:

- RS-232/serial: port, baud, data bits, parity and stop bits;
- TCP or HL7 MLLP: host and port;
- REST/FHIR: base URL;
- DICOM: AE title and Orthanc/DICOMweb endpoint;
- file integration: watched folder/path.

Connection settings are kept separately from parser settings so an interface can be moved without redefining its message format.

### 3. Parser

For legacy devices, choose or configure the message format.

The console supports visual fields for:

- fixed-width messages, including accession slices and per-result start/end positions;
- delimited serial messages;
- regex-configured proprietary messages;
- ASTM-style analyzers;
- HL7 v2 ORU messages;
- Mindray BC-3000 Plus;
- structured REST/JSON results;
- FHIR R4 Bundles containing Observations.

The saved `parser_config` is merged over the catalog profile at runtime. It does not alter the shared catalog definition.

### 4. Preview and mapping

Paste a de-identified sample frame/message and run **Test parse**.

A successful preview records the accession and observation count but does not create a clinical result.

After preview, map source result codes to:

- target/local code;
- display name;
- LOINC code;
- unit;
- enabled/disabled state.

The original source observation codes are retained in result metadata for auditability.

### 5. Validate and deliver

Record the validation status and evidence. Recommended site validation includes:

- exact device model and firmware;
- interface manual/revision;
- known sample frames;
- accession matching;
- parameter values and units;
- flags/reference ranges;
- duplicate handling;
- comparison against the device printout/interface software;
- EMR acknowledgement behavior.

Configure the target as FHIR, HL7/MLLP or REST/JSON. Automatic delivery can then be enabled if the validation gate passes.

## Imaging modalities

CT, MRI, CR/DR, X-ray, ultrasound and other DICOM modalities should send DICOM to Orthanc/PACS. Orby records the modality/DICOMweb connection boundary and handles clinical-system interoperability around it.

The current laboratory `NormalizedResult` pipeline should not be used to represent image pixels as laboratory observations. ImagingStudy/DiagnosticReport orchestration is a separate extension point.

## API equivalents

The console uses the same public API used by automation:

- `POST /api/v1/devices`
- `PUT /api/v1/devices/{id}/configuration`
- `POST /api/v1/devices/{id}/preview`
- `POST /api/v1/devices/{id}/validation`
- `PUT /api/v1/devices/{id}/delivery`
- `POST /api/v1/orders`
- `POST /api/v1/results/raw/{device_key}`
- `POST /api/v1/results/normalized`
- `GET /api/v1/results`
- `GET /api/v1/deliveries`
- `GET /api/v1/audit`
