from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from orby4middleware.db import Base, make_engine
from orby4middleware.models import OrderMap
from orby4middleware.schema import NormalizedResult, Observation
from orby4middleware.service import persist_result


def db_session():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def sample():
    return NormalizedResult(device_key="d1", profile_id="p1", accession="A1",
        observed_at=datetime.now(timezone.utc), observations=[Observation(code="WBC", value=5.5)],
        raw_payload="raw")


def test_unmatched_is_held_and_deduplicated():
    db=db_session()
    r, created=persist_result(db, sample())
    assert created and r.status == "UNMATCHED" and r.patient_id is None
    r2, created2=persist_result(db, sample())
    assert not created2 and r2.id == r.id


def test_exact_accession_matches():
    db=db_session(); db.add(OrderMap(accession="A1", patient_id="P1")); db.commit()
    r, _=persist_result(db, sample())
    assert r.status == "MATCHED" and r.patient_id == "P1"
