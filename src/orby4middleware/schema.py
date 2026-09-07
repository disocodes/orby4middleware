from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, field_validator


class Observation(BaseModel):
    code: str
    value: str | int | float | bool | None
    unit: str | None = None
    display: str | None = None
    loinc: str | None = None
    flag: str | None = None
    reference_range: str | None = None


class NormalizedResult(BaseModel):
    device_key: str
    profile_id: str
    accession: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observations: list[Observation]
    source_meta: dict[str, Any] = Field(default_factory=dict)
    raw_payload: str | None = None

    @field_validator("accession")
    @classmethod
    def accession_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("accession/sample identifier is required")
        return value


class OrderMapIn(BaseModel):
    accession: str
    patient_id: str
    encounter_id: str | None = None
    service_request_id: str | None = None


class DeviceIn(BaseModel):
    device_key: str
    manufacturer: str
    model: str
    profile_id: str
    validation_status: str = "experimental"
    config: dict[str, Any] = Field(default_factory=dict)


class DeliveryRequest(BaseModel):
    target_type: str
    target: str
