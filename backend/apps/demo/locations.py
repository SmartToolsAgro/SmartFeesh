"""Demo cold rooms and trucks: the stand-ins of docs/spec/sample/locations.csv, until the client's lists arrive.

Camion 1 goes to the demo driver; the sample's other drivers are not demo logins, so trucks 2 and 3 have none.
"""

from apps.core.models import Organization, User
from apps.fleet import selectors as fleet_selectors
from apps.fleet import services as fleet
from apps.inventory import selectors, services
from apps.inventory.services import LocationKind

# name, sells at the counter (Q8)
COLD_ROOMS = [
    ("Chambre froide 1 (frais)", True),
    ("Chambre froide 2 (congelé)", True),
]
# name, plate, gets the demo driver
TRUCKS = [
    ("Camion 1", "101 TU 2001", True),
    ("Camion 2", "102 TU 2002", False),
    ("Camion 3", "103 TU 2003", False),
]


def seed_locations(*, organization: Organization, actor: User | None, driver: User | None) -> int:
    """Create the demo cold rooms and trucks that do not exist yet. Returns how many locations were created."""
    existing = {
        name.lower() for name in selectors.locations_of(organization, status="all").values_list("name", flat=True)
    }
    created = 0
    for name, counter_sales in COLD_ROOMS:
        if name.lower() not in existing:
            services.create_location(
                organization=organization,
                actor=actor,
                kind=LocationKind.COLD_ROOM,
                name=name,
                counter_sales=counter_sales,
            )
            created += 1
    driver_has_truck = (
        driver is not None and fleet_selectors.trucks_of(organization, status="all").filter(driver=driver).exists()
    )
    for name, plate, for_driver in TRUCKS:
        if name.lower() in existing:
            continue
        fleet.create_truck(
            organization=organization,
            actor=actor,
            name=name,
            plate=plate,
            driver=driver if for_driver and not driver_has_truck else None,
        )
        created += 1
    return created
