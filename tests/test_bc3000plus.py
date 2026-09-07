from orby4middleware.catalog import profile_by_id
from orby4middleware.parsers.mindray_bc3000plus import parse_bc3000plus


def test_bc3000plus_profile_parses_configured_frame():
    p=profile_by_id("mindray-bc3000plus-serial-v1")
    # Synthetic frame constructed only to verify configured field extraction.
    frame="A12345678" + "006.8" + "04.70" + "00142" + "042.0" + "089.4" + "030.2" + "00338" + "00265" + "\r"
    r=parse_bc3000plus(frame, profile=p, device_key="bc1")
    assert r.accession == "12345678"
    assert r.observations[0].code == "WBC"
