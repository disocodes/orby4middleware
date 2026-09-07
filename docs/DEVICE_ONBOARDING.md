# Device onboarding

## 1. Identify the exact interface
Collect manufacturer, exact model, firmware/software revision, host/LIS manual, cable pinout,
protocol, serial/TCP settings, framing/handshake rules and sample/result examples.

## 2. Select an adapter
Prefer, in order:

1. FHIR/REST API
2. HL7 v2/MLLP
3. ASTM-style protocol
4. file/CSV export
5. generic serial fixed-width/delimited/regex profile
6. model-specific plugin

This ordering is operational, not a claim that newer is always clinically superior.

## 3. Observe before parsing
Use `orby4-edge capture` with de-identified QC/test samples. Capture both printable and hexadecimal
representations if control bytes are present.

## 4. Define parameter mappings
Map analyzer-specific names to local canonical codes and, where appropriate, standard terminologies
such as LOINC. Do not copy a LOINC mapping from another model without verifying semantics and units.

## 5. Validate
Test normal/abnormal values, flags, units, decimals, negative/overflow values, malformed frames,
duplicate retransmission, analyzer reboot, network outage, missing accession, and clock/timezone.

## 6. Promote profile status
- `experimental`: parser/profile exists but is not site validated.
- `vendor-documented`: built against an official interface specification.
- `validated-lab`: tested against a real instrument and site workflow.

A profile can be validated at one site without claiming universal validation for every firmware.
