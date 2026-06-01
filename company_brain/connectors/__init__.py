"""Source connectors that turn customer systems into memory records."""

from .notion import NotionConnector

__all__ = ["NotionConnector"]
