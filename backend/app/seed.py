"""Create tables and load the deterministic mock inventory.

Usage::

    python -m app.seed            # create tables + seed if empty
    python -m app.seed --reset    # wipe inventory tables and reseed
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import db as db_module
from app.models import Airline, Airport, FlightSchedule, Hotel
from app.providers.mock_data import CARRIERS, CITIES, generate_hotels, generate_schedules

log = logging.getLogger(__name__)


def inventory_is_seeded(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(Airport)) or 0) > 0


def seed_inventory(db: Session, reset: bool = False) -> dict[str, int]:
    if reset:
        for model in (Hotel, FlightSchedule, Airline, Airport):
            db.execute(delete(model))
        db.commit()
    elif inventory_is_seeded(db):
        return {"airports": 0, "airlines": 0, "flight_schedules": 0, "hotels": 0}

    db.add_all(
        Airport(
            iata=c.iata, name=c.airport, city=c.city, country=c.country, country_code=c.country_code,
            region=c.region, latitude=c.lat, longitude=c.lon, timezone=c.timezone, currency=c.currency,
            language=c.language, cost_index=c.cost_index, neighborhoods=list(c.neighborhoods),
        )
        for c in CITIES
    )
    db.add_all(Airline(code=c.code, name=c.name, hub=c.hub, rating=c.rating) for c in CARRIERS)
    db.flush()
    schedules = generate_schedules()
    db.add_all(FlightSchedule(**row) for row in schedules)
    hotels = generate_hotels()
    db.add_all(Hotel(**row) for row in hotels)
    db.commit()
    counts = {"airports": len(CITIES), "airlines": len(CARRIERS), "flight_schedules": len(schedules), "hotels": len(hotels)}
    log.info("Seeded inventory: %s", counts)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete and regenerate inventory tables")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db_module.init_db()
    with db_module.SessionLocal() as db:
        counts = seed_inventory(db, reset=args.reset)
    if any(counts.values()):
        print("Seeded:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    else:
        print("Inventory already present - nothing to do (use --reset to regenerate).")


if __name__ == "__main__":
    main()
