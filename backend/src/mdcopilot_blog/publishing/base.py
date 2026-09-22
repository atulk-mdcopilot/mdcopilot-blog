"""Shared publishing types."""

from pydantic import BaseModel


class Issue(BaseModel):
    field: str
    message: str
