# Compatibility model

orby4middleware aims for broad compatibility by implementing protocol families and configurable
model profiles. It does **not** claim that every device from a listed brand works without validation.

## Protocol families

| Family | Typical devices | Adapter |
|---|---|---|
| RS-232/RS-422 fixed width | legacy hematology/chemistry | fixed-width profile/plugin |
| Serial delimited | legacy analyzers | delimiter profile/plugin |
| ASTM-style | laboratory analyzers | ASTM parser + transport |
| HL7 v2/MLLP | analyzers/LIS/EMR | HL7 parser/sender |
| File/CSV | legacy middleware/export | file watcher/importer |
| REST/JSON | newer analyzers/platforms | HTTP adapter |
| FHIR | modern clinical systems | FHIR adapter |
| DICOM/DICOMweb | imaging modalities | Orthanc integration |

## Manufacturer catalog

The built-in catalog contains onboarding entries for common and legacy brands including:

Mindray, Sysmex, Beckman Coulter, Abbott, Roche, Siemens Healthineers, HORIBA, Nihon Kohden,
Boule, Diatron, Erba, DIRUI, URIT, Genrui, EDAN, Stago, Werfen/Instrumentation Laboratory,
bioMérieux, BD, Cepheid, Radiometer, ARKRAY, Tosoh, Snibe, Autobio, Rayto, HUMAN, Randox,
Agappe, Transasia, GE HealthCare, Philips, Canon Medical, Fujifilm, Carestream, Agfa,
Samsung Medison, Esaote, Shimadzu, Hitachi, Leica Biosystems and generic/custom devices.

Catalog entries help users choose a manufacturer/model/protocol template. Only explicitly listed
model profiles have parser implementations or validated mappings.
