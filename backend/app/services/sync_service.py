"""Delta synchronisation for the offline-first mobile application.

The service is deliberately independent of the ORM model classes. The router
builds a `SyncRegistry` that names the tables to synchronise, and this module
reads the columns through SQLAlchemy introspection. A new table joins the sync
by joining the registry.

Conflict rule, from the architecture specification: last write wins, and the
server is the authority. A push that carries a stale `version` or a stale
`updated_at` is refused, and the answer holds the server record so that the
client can show the "conflict resolved" message.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.errors import ValidationError

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE: Final[int] = 500
MAX_PAGE_SIZE: Final[int] = 2000
MAX_PUSH_CHANGES: Final[int] = 1000

OP_CREATE: Final[str] = "create"
OP_UPDATE: Final[str] = "update"
OP_DELETE: Final[str] = "delete"
VALID_OPS: Final[frozenset[str]] = frozenset({OP_CREATE, OP_UPDATE, OP_DELETE})

#: Columns that a client may never write.
PROTECTED_COLUMNS: Final[frozenset[str]] = frozenset(
    {"id", "user_id", "created_at", "password_hash"}
)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SyncResource:
    """One table that takes part in the synchronisation."""

    name: str
    model: type[Any]
    user_column: str | None = "user_id"
    read_only: bool = False
    exclude: frozenset[str] = frozenset()

    @property
    def mapper(self) -> Any:
        """Return the SQLAlchemy mapper of the model."""
        return inspect(self.model)

    @property
    def columns(self) -> dict[str, Any]:
        """Return every mapped column, by attribute name."""
        return {attr.key: attr.columns[0] for attr in self.mapper.column_attrs}

    def has(self, column: str) -> bool:
        """Return True if the model has that column."""
        return column in self.columns

    @property
    def scope_column(self) -> str | None:
        """Return the column that holds the owner, if the model has one."""
        if self.user_column and self.has(self.user_column):
            return self.user_column
        return None


class SyncRegistry:
    """The set of resources that the sync endpoints expose."""

    def __init__(self, resources: Sequence[SyncResource]) -> None:
        self._resources: tuple[SyncResource, ...] = tuple(resources)
        self._by_name = {resource.name: resource for resource in resources}

    def __iter__(self) -> Any:
        """Iterate over the resources, in registration order."""
        return iter(self._resources)

    @property
    def names(self) -> tuple[str, ...]:
        """Return every resource name."""
        return tuple(self._by_name)

    def get(self, name: str) -> SyncResource:
        """Return one resource, or raise `ValidationError`."""
        try:
            return self._by_name[name]
        except KeyError:
            raise ValidationError(
                f"'{name}' is not a resource that this server synchronises.",
                details={"known_resources": list(self._by_name)},
            ) from None


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResourceChanges:
    """The changes of one table since the client's last sync."""

    updated: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[dict[str, Any]] = field(default_factory=list)
    has_more: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the changes as a plain dictionary."""
        return {
            "updated": self.updated,
            "deleted": self.deleted,
            "has_more": self.has_more,
        }


@dataclass(frozen=True, slots=True)
class SyncChanges:
    """The answer of `GET /api/sync/changes`."""

    server_time: datetime
    since: datetime | None
    resources: dict[str, ResourceChanges]

    @property
    def has_more(self) -> bool:
        """Return True if any table held back rows."""
        return any(changes.has_more for changes in self.resources.values())

    @property
    def count(self) -> int:
        """Return the number of rows in the answer."""
        return sum(
            len(changes.updated) + len(changes.deleted)
            for changes in self.resources.values()
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the answer as a plain dictionary."""
        return {
            "server_time": self.server_time.isoformat(),
            "since": self.since.isoformat() if self.since else None,
            "has_more": self.has_more,
            "count": self.count,
            "changes": {
                name: changes.to_dict() for name, changes in self.resources.items()
            },
        }


@dataclass(frozen=True, slots=True)
class PushResult:
    """The answer of `POST /api/sync/push`."""

    server_time: datetime
    applied: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the answer as a plain dictionary."""
        return {
            "server_time": self.server_time.isoformat(),
            "applied": self.applied,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "applied_count": len(self.applied),
            "conflict_count": len(self.conflicts),
            "error_count": len(self.errors),
        }


# --------------------------------------------------------------------------
# Pull
# --------------------------------------------------------------------------


async def collect_changes(
    session: AsyncSession,
    registry: SyncRegistry,
    *,
    since: datetime | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    resources: Sequence[str] | None = None,
) -> SyncChanges:
    """Return every change since `since`, table by table."""
    page = max(1, min(limit, MAX_PAGE_SIZE))
    moment = _utc_now()
    wanted = [registry.get(name) for name in resources] if resources else list(registry)

    result: dict[str, ResourceChanges] = {}
    for resource in wanted:
        result[resource.name] = await _changes_for(
            session, resource, since=since, user_id=user_id, limit=page
        )
    return SyncChanges(server_time=moment, since=since, resources=result)


async def _changes_for(
    session: AsyncSession,
    resource: SyncResource,
    *,
    since: datetime | None,
    user_id: uuid.UUID | None,
    limit: int,
) -> ResourceChanges:
    """Read the changed rows of one table."""
    model = resource.model
    if not resource.has("updated_at"):
        logger.debug("The table %s has no updated_at column.", resource.name)
        return ResourceChanges()

    soft_delete = resource.has("deleted_at")
    statement = select(model)
    if since is not None:
        statement = statement.where(model.updated_at > since)
    scope = resource.scope_column
    if scope and user_id is not None:
        statement = statement.where(getattr(model, scope) == user_id)
    statement = statement.order_by(model.updated_at.asc()).limit(limit + 1)

    rows = list((await session.execute(statement)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]

    updated: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    for row in rows:
        if soft_delete and getattr(row, "deleted_at", None) is not None:
            deleted.append(
                {
                    "id": _json_safe(getattr(row, "id", None)),
                    "deleted_at": _json_safe(row.deleted_at),
                }
            )
        else:
            updated.append(serialise_row(row, resource))
    return ResourceChanges(updated=updated, deleted=deleted, has_more=has_more)


def serialise_row(row: Any, resource: SyncResource) -> dict[str, Any]:
    """Turn one ORM row into a JSON-safe dictionary."""
    hidden = resource.exclude | {"password_hash"}
    return {
        name: _json_safe(getattr(row, name, None))
        for name in resource.columns
        if name not in hidden
    }


# --------------------------------------------------------------------------
# Push
# --------------------------------------------------------------------------


async def apply_push(
    session: AsyncSession,
    registry: SyncRegistry,
    changes: Sequence[Mapping[str, Any]],
    *,
    user_id: uuid.UUID | None = None,
) -> PushResult:
    """Apply the changes that the mobile application queued while offline.

    Every change is applied on its own. One bad change does not stop the rest:
    it is reported in `errors`, and the client can retry it.
    """
    if len(changes) > MAX_PUSH_CHANGES:
        raise ValidationError(
            f"Send {MAX_PUSH_CHANGES} changes or less in one push.",
            details={"received": len(changes)},
        )

    applied: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, change in enumerate(changes):
        try:
            outcome = await _apply_one(session, registry, change, user_id=user_id)
        except ValidationError as exc:
            errors.append(
                {
                    "index": index,
                    "resource": change.get("resource"),
                    "id": change.get("id"),
                    "message": exc.message,
                }
            )
            continue
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.warning("A pushed change failed: %s", exc)
            errors.append(
                {
                    "index": index,
                    "resource": change.get("resource"),
                    "id": change.get("id"),
                    "message": "The database refused this change.",
                }
            )
            continue

        if outcome.get("conflict"):
            conflicts.append(outcome["conflict"])
        else:
            applied.append(outcome["applied"])

    await session.commit()
    return PushResult(
        server_time=_utc_now(),
        applied=applied,
        conflicts=conflicts,
        errors=errors,
    )


async def _apply_one(
    session: AsyncSession,
    registry: SyncRegistry,
    change: Mapping[str, Any],
    *,
    user_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Apply one create, update, or delete."""
    resource = registry.get(str(change.get("resource", "")))
    if resource.read_only:
        raise ValidationError(f"The resource '{resource.name}' is read only.")

    operation = str(change.get("op", OP_UPDATE)).lower()
    if operation not in VALID_OPS:
        raise ValidationError(
            f"'{operation}' is not an operation. Use create, update, or delete."
        )

    record_id = _coerce_uuid(change.get("id"))
    if record_id is None:
        raise ValidationError("Every change needs an id.")

    data = change.get("data") or {}
    if not isinstance(data, Mapping):
        raise ValidationError("The data field must be an object.")

    existing = await session.get(resource.model, record_id)

    if operation == OP_DELETE:
        return await _apply_delete(session, resource, existing, record_id, user_id)

    if existing is None:
        return await _apply_create(session, resource, record_id, data, user_id)

    _assert_owner(resource, existing, user_id)
    conflict = _detect_conflict(resource, existing, change)
    if conflict is not None:
        return {"conflict": conflict}

    _write_columns(resource, existing, data)
    _bump_version(resource, existing)
    await session.flush()
    return {
        "applied": {
            "resource": resource.name,
            "id": str(record_id),
            "op": OP_UPDATE,
            "version": getattr(existing, "version", None),
            "updated_at": _json_safe(getattr(existing, "updated_at", None)),
        }
    }


async def _apply_create(
    session: AsyncSession,
    resource: SyncResource,
    record_id: uuid.UUID,
    data: Mapping[str, Any],
    user_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Insert a row that the client created while it was offline."""
    instance = resource.model()
    instance.id = record_id
    scope = resource.scope_column
    if scope and user_id is not None:
        setattr(instance, scope, user_id)
    _write_columns(resource, instance, data)
    if resource.has("version"):
        instance.version = 1
    session.add(instance)
    await session.flush()
    return {
        "applied": {
            "resource": resource.name,
            "id": str(record_id),
            "op": OP_CREATE,
            "version": getattr(instance, "version", None),
            "updated_at": _json_safe(getattr(instance, "updated_at", None)),
        }
    }


async def _apply_delete(
    session: AsyncSession,
    resource: SyncResource,
    existing: Any,
    record_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Delete a row, or mark it deleted if the table supports that."""
    if existing is None:
        # The row is already gone. A repeated delete is not an error.
        return {
            "applied": {
                "resource": resource.name,
                "id": str(record_id),
                "op": OP_DELETE,
                "version": None,
                "updated_at": None,
            }
        }
    _assert_owner(resource, existing, user_id)
    if resource.has("deleted_at"):
        existing.deleted_at = _utc_now()
        _bump_version(resource, existing)
    else:
        await session.delete(existing)
    await session.flush()
    return {
        "applied": {
            "resource": resource.name,
            "id": str(record_id),
            "op": OP_DELETE,
            "version": getattr(existing, "version", None),
            "updated_at": _json_safe(getattr(existing, "updated_at", None)),
        }
    }


def _detect_conflict(
    resource: SyncResource, existing: Any, change: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Return a conflict record if the server copy is newer than the client copy.

    The client sends the version and the timestamp that it started from. If the
    server has moved on since then, the server copy wins.
    """
    client_version = change.get("base_version", change.get("version"))
    server_version = getattr(existing, "version", None)
    if (
        resource.has("version")
        and isinstance(client_version, int)
        and isinstance(server_version, int)
        and client_version < server_version
    ):
        return _conflict(resource, existing, "The server record is a newer version.")

    client_updated = _coerce_datetime(
        change.get("base_updated_at", change.get("updated_at"))
    )
    server_updated = getattr(existing, "updated_at", None)
    if (
        client_updated is not None
        and isinstance(server_updated, datetime)
        and _aware(server_updated) > _aware(client_updated)
    ):
        return _conflict(
            resource, existing, "The server record changed after the client copy."
        )
    return None


def _conflict(resource: SyncResource, existing: Any, reason: str) -> dict[str, Any]:
    """Build one conflict record for the answer."""
    return {
        "resource": resource.name,
        "id": str(getattr(existing, "id", "")),
        "reason": reason,
        "resolution": "server_wins",
        "server": serialise_row(existing, resource),
    }


def _assert_owner(
    resource: SyncResource, instance: Any, user_id: uuid.UUID | None
) -> None:
    """Refuse a change to a record of another user."""
    scope = resource.scope_column
    if not scope or user_id is None:
        return
    owner = getattr(instance, scope, None)
    if owner is not None and str(owner) != str(user_id):
        raise ValidationError("This record belongs to another user.")


def _write_columns(
    resource: SyncResource, instance: Any, data: Mapping[str, Any]
) -> None:
    """Copy the writable fields of `data` onto the row, with type coercion."""
    columns = resource.columns
    for key, value in data.items():
        if key in PROTECTED_COLUMNS or key in resource.exclude:
            continue
        column = columns.get(key)
        if column is None:
            continue
        setattr(instance, key, _coerce(value, column))


def _bump_version(resource: SyncResource, instance: Any) -> None:
    """Raise the version counter by one."""
    if not resource.has("version"):
        return
    current = getattr(instance, "version", None)
    instance.version = (current or 0) + 1


# --------------------------------------------------------------------------
# Type helpers
# --------------------------------------------------------------------------


def _coerce(value: Any, column: Any) -> Any:
    """Turn a JSON value into the Python type that the column needs."""
    if value is None:
        return None
    try:
        python_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        return value

    if python_type is uuid.UUID:
        return _coerce_uuid(value)
    if python_type is datetime:
        return _coerce_datetime(value)
    if python_type is date:
        return _coerce_date(value)
    if python_type is Decimal:
        return _coerce_decimal(value)
    if python_type is bool:
        return _coerce_bool(value)
    if python_type is int and not isinstance(value, bool):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"'{value}' is not a whole number.") from exc
    if python_type is float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"'{value}' is not a number.") from exc
    if python_type is str and not isinstance(value, str):
        return str(value)
    return value


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    """Read a UUID out of a UUID or a string."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"'{value}' is not a UUID.") from exc


def _coerce_datetime(value: Any) -> datetime | None:
    """Read a timestamp out of a datetime or an ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValidationError(f"'{value}' is not a timestamp.") from exc
    raise ValidationError(f"'{value}' is not a timestamp.")


def _coerce_date(value: Any) -> date | None:
    """Read a date out of a date, a datetime, or an ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError as exc:
            raise ValidationError(f"'{value}' is not a date.") from exc
    raise ValidationError(f"'{value}' is not a date.")


def _coerce_decimal(value: Any) -> Decimal | None:
    """Read a decimal amount."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"'{value}' is not an amount.") from exc


def _coerce_bool(value: Any) -> bool:
    """Read a true or false value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _json_safe(value: Any) -> Any:
    """Turn a database value into something that JSON accepts."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return value


def _aware(moment: datetime) -> datetime:
    """Return a timestamp with a time zone. Naive input counts as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


def parse_since(value: str | datetime | None) -> datetime | None:
    """Read the `since` query parameter of `GET /api/sync/changes`."""
    if value is None or value == "":
        return None
    return _coerce_datetime(value)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MAX_PUSH_CHANGES",
    "OP_CREATE",
    "OP_DELETE",
    "OP_UPDATE",
    "PushResult",
    "ResourceChanges",
    "SyncChanges",
    "SyncRegistry",
    "SyncResource",
    "apply_push",
    "collect_changes",
    "parse_since",
    "serialise_row",
]
