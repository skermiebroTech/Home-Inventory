"""Delta synchronisation for the offline-first mobile application.

The service is independent of the model classes. A router builds a
`SyncRegistry` that names the tables to synchronise, and this module reads the
columns through SQLAlchemy introspection. A new table joins the sync by
joining the registry.

Ownership. A table with a `user_id` column is filtered on it. A child table
such as `item_photos` has no `user_id`, so the registry names its parent, and
this module joins the parent to filter the reads and to check the writes.

Conflicts. The architecture specification says last write wins, with the
server as the authority. A push that carries a stale `base_version` or a stale
timestamp is refused, and the answer names the server version so that the
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

from sqlalchemy import Select, inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.errors import ValidationError

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE: Final[int] = 500
MAX_PAGE_SIZE: Final[int] = 5000
MAX_PUSH_CHANGES: Final[int] = 500

OP_CREATE: Final[str] = "create"
OP_UPDATE: Final[str] = "update"
OP_DELETE: Final[str] = "delete"
VALID_OPS: Final[frozenset[str]] = frozenset({OP_CREATE, OP_UPDATE, OP_DELETE})

#: Columns that a client may never write.
PROTECTED_COLUMNS: Final[frozenset[str]] = frozenset(
    {"id", "user_id", "created_at", "password_hash", "search_vector"}
)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParentScope:
    """How a child table reaches the user who owns it."""

    foreign_key: str
    model: type[Any]
    user_column: str = "user_id"


@dataclass(frozen=True, slots=True)
class SyncResource:
    """One table that takes part in the synchronisation."""

    name: str
    model: type[Any]
    user_column: str | None = "user_id"
    parent: ParentScope | None = None
    read_only: bool = False
    exclude: frozenset[str] = frozenset()
    #: Relationship names to load with the row. A response schema that holds
    #: a nested list needs them, because async code cannot load a
    #: relationship later, when the schema reads the attribute.
    load: tuple[str, ...] = ()

    @property
    def columns(self) -> dict[str, Any]:
        """Return every mapped column, by attribute name."""
        return {attr.key: attr.columns[0] for attr in inspect(self.model).column_attrs}

    def has(self, column: str) -> bool:
        """Return True if the model has that column."""
        return column in self.columns

    @property
    def scope_column(self) -> str | None:
        """Return the owner column of this table, if it has one."""
        if self.user_column and self.has(self.user_column):
            return self.user_column
        return None

    def scoped(self, statement: Select[Any], user_id: uuid.UUID | None) -> Select[Any]:
        """Add the ownership filter to a select."""
        if user_id is None:
            return statement
        column = self.scope_column
        if column is not None:
            return statement.where(getattr(self.model, column) == user_id)
        if self.parent is not None:
            parent = self.parent
            return statement.join(
                parent.model,
                parent.model.id == getattr(self.model, parent.foreign_key),
            ).where(getattr(parent.model, parent.user_column) == user_id)
        # A shared table, such as tags. Every user of this installation sees it.
        return statement


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
class RowChanges:
    """The rows of one table that changed since the client's last sync."""

    updated: list[Any] = field(default_factory=list)
    deleted: list[uuid.UUID] = field(default_factory=list)
    has_more: bool = False


@dataclass(frozen=True, slots=True)
class PushOutcome:
    """What the server did with one pushed change."""

    applied: bool
    resource: str
    record_id: uuid.UUID
    op: str
    version: int | None = None
    conflict_reason: str | None = None
    error: str | None = None

    @property
    def conflicted(self) -> bool:
        """Return True if the server refused the change and kept its own row."""
        return self.conflict_reason is not None


@dataclass(frozen=True, slots=True)
class PushResult:
    """The result of one push batch."""

    server_time: datetime
    outcomes: list[PushOutcome] = field(default_factory=list)

    @property
    def applied(self) -> list[PushOutcome]:
        """Return the changes that the server wrote."""
        return [outcome for outcome in self.outcomes if outcome.applied]

    @property
    def conflicts(self) -> list[PushOutcome]:
        """Return the changes that lost to a newer server row."""
        return [outcome for outcome in self.outcomes if outcome.conflicted]

    @property
    def errors(self) -> list[PushOutcome]:
        """Return the changes that the server could not read."""
        return [
            outcome
            for outcome in self.outcomes
            if outcome.error is not None and not outcome.conflicted
        ]


# --------------------------------------------------------------------------
# Pull
# --------------------------------------------------------------------------


async def fetch_changes(
    session: AsyncSession,
    resource: SyncResource,
    *,
    since: datetime | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> RowChanges:
    """Return the rows of one table that changed since `since`.

    A soft deleted row goes into `deleted` instead of `updated`, so that the
    client removes it from its own database.
    """
    model = resource.model
    if not resource.has("updated_at"):
        logger.debug("The table %s has no updated_at column.", resource.name)
        return RowChanges()

    page = max(1, min(limit, MAX_PAGE_SIZE))
    statement: Select[Any] = select(model)
    if since is not None:
        statement = statement.where(model.updated_at > since)
    statement = resource.scoped(statement, user_id)
    for relationship in resource.load:
        statement = statement.options(selectinload(getattr(model, relationship)))
    statement = statement.order_by(model.updated_at.asc(), model.id).limit(page + 1)

    rows = list((await session.execute(statement)).scalars().unique().all())
    has_more = len(rows) > page
    rows = rows[:page]

    soft_delete = resource.has("deleted_at")
    updated: list[Any] = []
    deleted: list[uuid.UUID] = []
    for row in rows:
        if soft_delete and getattr(row, "deleted_at", None) is not None:
            deleted.append(row.id)
        else:
            updated.append(row)
    return RowChanges(updated=updated, deleted=deleted, has_more=has_more)


def serialise_row(row: Any, resource: SyncResource) -> dict[str, Any]:
    """Turn one ORM row into a JSON-safe dictionary."""
    hidden = resource.exclude | {"password_hash", "search_vector"}
    return {
        name: json_safe(getattr(row, name, None))
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
    it is reported, and the client can correct it and send it again.
    """
    if len(changes) > MAX_PUSH_CHANGES:
        raise ValidationError(
            f"Send {MAX_PUSH_CHANGES} changes or less in one push.",
            details={"received": len(changes)},
        )

    outcomes: list[PushOutcome] = []
    for change in changes:
        resource_name = str(change.get("resource", ""))
        record_id = change.get("id")
        try:
            # Each change gets a savepoint. A database failure then rolls
            # back that change alone, and every change before it in the
            # batch still counts.
            async with session.begin_nested():
                outcomes.append(await _apply_one(session, registry, change, user_id))
        except ValidationError as exc:
            outcomes.append(
                PushOutcome(
                    applied=False,
                    resource=resource_name,
                    record_id=_safe_uuid(record_id),
                    op=str(change.get("op", "")),
                    error=exc.message,
                )
            )
        except SQLAlchemyError as exc:
            # The savepoint is already rolled back. The session stays usable,
            # so the rest of the batch goes on.
            logger.warning("A pushed change failed: %s", exc)
            outcomes.append(
                PushOutcome(
                    applied=False,
                    resource=resource_name,
                    record_id=_safe_uuid(record_id),
                    op=str(change.get("op", "")),
                    error=_readable_error(exc),
                )
            )

    await session.commit()
    return PushResult(server_time=utc_now(), outcomes=outcomes)


def _readable_error(exc: SQLAlchemyError) -> str:
    """Turn a database failure into a sentence that names the cause.

    The common one is a change that points at a row this server does not
    have, such as a location that another client deleted.
    """
    if isinstance(exc, IntegrityError):
        text = str(exc.orig or exc)
        if "ForeignKeyViolation" in text or "foreign key" in text.lower():
            return (
                "This change names a row that the server does not have, such "
                "as a location that is gone. Correct it and send it again."
            )
        if "UniqueViolation" in text or "duplicate key" in text.lower():
            return "A row with that value already exists on the server."
    return "The database refused this change."


async def _apply_one(
    session: AsyncSession,
    registry: SyncRegistry,
    change: Mapping[str, Any],
    user_id: uuid.UUID | None,
) -> PushOutcome:
    """Apply one create, update, or delete."""
    resource = registry.get(str(change.get("resource", "")))
    if resource.read_only:
        raise ValidationError(f"The resource '{resource.name}' is read only.")

    operation = str(change.get("op", OP_UPDATE)).lower()
    if operation not in VALID_OPS:
        raise ValidationError(
            f"'{operation}' is not an operation. Use create, update, or delete."
        )

    record_id = coerce_uuid(change.get("id"))
    if record_id is None:
        raise ValidationError("Every change needs an id.")

    data = change.get("data") or {}
    if not isinstance(data, Mapping):
        raise ValidationError("The data field must be an object.")

    existing = await session.get(resource.model, record_id)

    if existing is None:
        if operation == OP_DELETE:
            # The row is already gone. A repeated delete is not an error.
            return PushOutcome(
                applied=True, resource=resource.name, record_id=record_id, op=OP_DELETE
            )
        return await _create(session, resource, record_id, data, user_id)

    await _assert_owner(session, resource, existing, user_id)

    if operation == OP_DELETE:
        return await _delete(session, resource, existing, record_id)

    conflict = _conflict_reason(resource, existing, change)
    if conflict is not None:
        return PushOutcome(
            applied=False,
            resource=resource.name,
            record_id=record_id,
            op=operation,
            version=getattr(existing, "version", None),
            conflict_reason=conflict,
        )

    _write_columns(resource, existing, data)
    _bump_version(resource, existing)
    await session.flush()
    return PushOutcome(
        applied=True,
        resource=resource.name,
        record_id=record_id,
        op=OP_UPDATE,
        version=getattr(existing, "version", None),
    )


async def _create(
    session: AsyncSession,
    resource: SyncResource,
    record_id: uuid.UUID,
    data: Mapping[str, Any],
    user_id: uuid.UUID | None,
) -> PushOutcome:
    """Insert a row that the client created while it was offline."""
    instance = resource.model()
    instance.id = record_id
    scope = resource.scope_column
    if scope and user_id is not None:
        setattr(instance, scope, user_id)
    _write_columns(resource, instance, data)
    if resource.has("version"):
        instance.version = 1

    await _assert_owner(session, resource, instance, user_id)
    session.add(instance)
    await session.flush()
    return PushOutcome(
        applied=True,
        resource=resource.name,
        record_id=record_id,
        op=OP_CREATE,
        version=getattr(instance, "version", None),
    )


async def _delete(
    session: AsyncSession,
    resource: SyncResource,
    existing: Any,
    record_id: uuid.UUID,
) -> PushOutcome:
    """Delete a row, or mark it deleted if the table keeps tombstones."""
    if resource.has("deleted_at"):
        existing.deleted_at = utc_now()
        _bump_version(resource, existing)
    else:
        await session.delete(existing)
    await session.flush()
    return PushOutcome(
        applied=True,
        resource=resource.name,
        record_id=record_id,
        op=OP_DELETE,
        version=getattr(existing, "version", None),
    )


def _conflict_reason(
    resource: SyncResource, existing: Any, change: Mapping[str, Any]
) -> str | None:
    """Return why the server keeps its own row, or None to accept the change.

    The client sends the version, and the timestamp, that it started from. If
    the server has moved on since then, the server copy wins.
    """
    client_version = change.get("base_version")
    server_version = getattr(existing, "version", None)
    if (
        resource.has("version")
        and isinstance(client_version, int)
        and isinstance(server_version, int)
        and client_version < server_version
    ):
        return (
            f"The server holds version {server_version}. "
            f"The client edited version {client_version}."
        )

    client_updated = coerce_datetime(change.get("base_updated_at"))
    server_updated = getattr(existing, "updated_at", None)
    if (
        client_updated is not None
        and isinstance(server_updated, datetime)
        and aware(server_updated) > aware(client_updated)
    ):
        return "The server record changed after the client copy was made."
    return None


async def _assert_owner(
    session: AsyncSession,
    resource: SyncResource,
    instance: Any,
    user_id: uuid.UUID | None,
) -> None:
    """Refuse a change to a record that belongs to another user."""
    if user_id is None:
        return

    column = resource.scope_column
    if column is not None:
        owner = getattr(instance, column, None)
        if owner is not None and str(owner) != str(user_id):
            raise ValidationError("This record belongs to another user.")
        return

    parent = resource.parent
    if parent is None:
        # A shared table, such as tags.
        return

    parent_id = getattr(instance, parent.foreign_key, None)
    if parent_id is None:
        raise ValidationError(
            f"This change needs a {parent.foreign_key} that names an existing row."
        )
    owner_row = await session.get(parent.model, parent_id)
    if owner_row is None:
        raise ValidationError(f"No row matches {parent.foreign_key} {parent_id}.")
    if str(getattr(owner_row, parent.user_column, "")) != str(user_id):
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
        setattr(instance, key, coerce(value, column))


def _bump_version(resource: SyncResource, instance: Any) -> None:
    """Raise the version counter by one."""
    if not resource.has("version"):
        return
    instance.version = (getattr(instance, "version", None) or 0) + 1


# --------------------------------------------------------------------------
# Type helpers
# --------------------------------------------------------------------------


def coerce(value: Any, column: Any) -> Any:
    """Turn a JSON value into the Python type that the column needs."""
    if value is None:
        return None
    try:
        python_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        return value

    if python_type is uuid.UUID:
        return coerce_uuid(value)
    if python_type is datetime:
        return coerce_datetime(value)
    if python_type is date:
        return coerce_date(value)
    if python_type is Decimal:
        return coerce_decimal(value)
    if python_type is bool:
        return coerce_bool(value)
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


def coerce_uuid(value: Any) -> uuid.UUID | None:
    """Read a UUID out of a UUID or a string."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"'{value}' is not a UUID.") from exc


def _safe_uuid(value: Any) -> uuid.UUID:
    """Return a UUID for a report line, even when the client sent nonsense."""
    try:
        return coerce_uuid(value) or uuid.UUID(int=0)
    except ValidationError:
        return uuid.UUID(int=0)


def coerce_datetime(value: Any) -> datetime | None:
    """Read a timestamp out of a datetime or an ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError(f"'{value}' is not a timestamp.") from exc
    raise ValidationError(f"'{value}' is not a timestamp.")


def coerce_date(value: Any) -> date | None:
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


def coerce_decimal(value: Any) -> Decimal | None:
    """Read a decimal amount."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"'{value}' is not an amount.") from exc


def coerce_bool(value: Any) -> bool:
    """Read a true or false value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def json_safe(value: Any) -> Any:
    """Turn a database value into something that JSON accepts."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes | bytearray):
        return value.decode("utf-8", "replace")
    return value


def aware(moment: datetime) -> datetime:
    """Return a timestamp with a time zone. Naive input counts as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MAX_PUSH_CHANGES",
    "OP_CREATE",
    "OP_DELETE",
    "OP_UPDATE",
    "ParentScope",
    "PushOutcome",
    "PushResult",
    "RowChanges",
    "SyncRegistry",
    "SyncResource",
    "apply_push",
    "coerce_datetime",
    "fetch_changes",
    "json_safe",
    "serialise_row",
    "utc_now",
]
