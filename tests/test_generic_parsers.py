from orby4middleware.parsers.generic import parse_delimited, parse_regex


def test_delimited():
    profile = {"id":"x","protocol":"serial","config":{}}
    result = parse_delimited("S|ACC123\rR|WBC|6.8|10^9/L|N\rR|HGB|142|g/L|N\r",
                             profile=profile, device_key="dev1")
    assert result.accession == "ACC123"
    assert [o.code for o in result.observations] == ["WBC", "HGB"]


def test_regex():
    profile = {"id":"x","config":{
        "accession_regex": r"SAMPLE=([A-Z0-9]+)",
        "result_regex": r"(?P<code>[A-Z]+)=(?P<value>[0-9.]+),(?P<unit>[^\\r\\n]+)"
    }}
    result = parse_regex("SAMPLE=ABC123\nWBC=6.8,10^9/L\n", profile=profile, device_key="d")
    assert result.accession == "ABC123"
    assert result.observations[0].value == "6.8"
