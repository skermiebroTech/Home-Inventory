"""Pydantic request and response schemas.

Every route returns ``Envelope[T]``. See ``app.schemas.common``.
"""

from app.schemas.common import Envelope, ErrorDetail, Message, ORMModel, Page, ok

__all__ = ["Envelope", "ErrorDetail", "Message", "ORMModel", "Page", "ok"]
