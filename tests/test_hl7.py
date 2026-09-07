from orby4middleware.parsers.hl7 import parse_hl7_oru
from orby4middleware.delivery import to_hl7_oru, to_fhir_bundle

MSG = """MSH|^~\\&|ANALYZER|LAB|ORBY|HOSP|20260908000100||ORU^R01|1|P|2.5.1\rPID|||P001\rOBR|1||ACC100|CBC|||20260908000000\rOBX|1|NM|6690-2^WBC^LN||6.8|10^9/L|4.0-11.0|N|||F\r"""


def test_hl7_parse_and_outputs():
    p={"id":"generic-hl7-oru-analyzer"}
    r=parse_hl7_oru(MSG, profile=p, device_key="a")
    assert r.accession == "ACC100"
    assert r.observations[0].code == "6690-2"
    hl7=to_hl7_oru(r, patient_id="P001")
    assert "ORU^R01" in hl7 and "ACC100" in hl7
    bundle=to_fhir_bundle(r, patient_id="P001")
    assert bundle["resourceType"] == "Bundle"
    assert any(e["resource"]["resourceType"] == "DiagnosticReport" for e in bundle["entry"])
