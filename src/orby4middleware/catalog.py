from functools import lru_cache
from importlib.resources import files
import yaml


@lru_cache
def load_catalog() -> dict:
    path = files("orby4middleware").joinpath("profiles/catalog.yml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def profile_by_id(profile_id: str) -> dict | None:
    catalog = load_catalog()
    for profile in catalog.get("profiles", []):
        if profile.get("id") == profile_id:
            return profile
    return None
