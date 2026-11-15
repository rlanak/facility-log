"""Who may change what in a facility (web mode).

Everyone with the Discord role sees every shared facility, but changing it
is up to the owner (14/11/2026 — it started as "shared, no restrictions",
and one ill-meant member could wreck the whole regiment's numbers):

- the **owner** does everything: buildings, Metas, item origins, reports,
  the Discord panel, and who else may edit;
- a member the owner **allowed** — on every building or on chosen ones —
  records stock (typed, print, save), sets production and private queues
  there, nothing else;
- any other member only reads;
- an **admin** (a Discord role in DISCORD_ADMIN_ROLE_IDS, checked at login)
  hands a facility to an owner — the only way one created before owners
  existed gets someone in charge — and is the only one who changes what is
  global (the resource list). Being admin does not make them an editor.

Local mode has no accounts: everything is allowed, as always.
The gate (auth.write_denied) applies this to every write under /api/.
"""

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import auth, models


@dataclass(frozen=True)
class Access:
    manage: bool = False  # the owner
    admin: bool = False
    all_buildings: bool = False
    building_ids: frozenset = frozenset()

    def can_edit(self, building_id: int) -> bool:
        return self.manage or self.all_buildings or building_id in self.building_ids

    def as_dict(self) -> dict:
        return {
            "manage": self.manage,
            "admin": self.admin,
            "buildings": "all" if self.manage or self.all_buildings else sorted(self.building_ids),
        }


FULL = Access(manage=True, admin=True, all_buildings=True)


def access_for(db: Session, facility: models.Facility, user) -> Access:
    """`user`: auth.SessionUser (or None)."""
    if not auth.config.enabled:
        return FULL
    if user is None:
        return Access()
    if facility.owner_id is not None and facility.owner_id == user.id:
        return Access(manage=True, admin=user.is_admin, all_buildings=True)
    rows = db.scalars(
        select(models.FacilityPermission).where(
            models.FacilityPermission.facility_id == facility.id, models.FacilityPermission.user_id == user.id
        )
    ).all()
    return Access(
        admin=user.is_admin,
        all_buildings=any(row.building_id is None for row in rows),
        building_ids=frozenset(row.building_id for row in rows if row.building_id is not None),
    )


def list_permissions(db: Session, facility: models.Facility) -> list[dict]:
    """[{user_id, name, avatar_url, all, building_ids}] for everyone the
    owner allowed, by name."""
    rows = db.scalars(
        select(models.FacilityPermission).where(models.FacilityPermission.facility_id == facility.id)
    ).all()
    by_user: dict[int, dict] = {}
    for row in rows:
        entry = by_user.setdefault(row.user_id, {"user_id": row.user_id, "all": False, "building_ids": []})
        if row.building_id is None:
            entry["all"] = True
        else:
            entry["building_ids"].append(row.building_id)
    out = []
    for user_id, entry in by_user.items():
        user = db.get(models.User, user_id)
        if not user:
            continue
        entry["name"], entry["avatar_url"] = user.name, user.avatar_url
        entry["building_ids"].sort()
        out.append(entry)
    return sorted(out, key=lambda e: e["name"].lower())


def set_permission(db: Session, facility: models.Facility, user_id: int, everything: bool, building_ids: list[int]) -> None:
    """Replaces what `user_id` may edit here. Nothing chosen = read only again.
    Buildings of another facility are ignored."""
    db.execute(
        delete(models.FacilityPermission).where(
            models.FacilityPermission.facility_id == facility.id, models.FacilityPermission.user_id == user_id
        )
    )
    if everything:
        db.add(models.FacilityPermission(facility_id=facility.id, user_id=user_id, building_id=None))
    else:
        own = {b.id for b in facility.buildings}
        for building_id in sorted(set(building_ids) & own):
            db.add(models.FacilityPermission(facility_id=facility.id, user_id=user_id, building_id=building_id))
    db.commit()


def forget_building(db: Session, building_id: int) -> None:
    """A deleted building takes its permission rows along."""
    db.execute(delete(models.FacilityPermission).where(models.FacilityPermission.building_id == building_id))
