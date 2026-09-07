from importlib.metadata import entry_points
from ..schema import NormalizedResult
from .generic import parse_delimited, parse_fixed_width, parse_regex
from .astm import parse_astm
from .hl7 import parse_hl7_oru
from .mindray_bc3000plus import parse_bc3000plus

BUILTINS = {
    "generic-delimited": parse_delimited,
    "generic-fixed-width": parse_fixed_width,
    "generic-regex": parse_regex,
    "astm": parse_astm,
    "hl7-oru": parse_hl7_oru,
    "mindray-bc3000plus": parse_bc3000plus,
}


def parse_with_profile(payload: bytes | str, profile: dict, *, device_key: str) -> NormalizedResult:
    parser_name = profile.get("parser", "")
    if parser_name in BUILTINS:
        return BUILTINS[parser_name](payload, profile=profile, device_key=device_key)

    for ep in entry_points(group="orby4middleware.protocols"):
        if ep.name == parser_name:
            return ep.load()(payload, profile=profile, device_key=device_key)
    raise ValueError(f"unknown parser: {parser_name}")
