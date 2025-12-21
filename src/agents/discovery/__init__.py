"""Discovery agents for finding lender product pages."""

from .web_search_discovery import WebSearchDiscovery
from .google_custom_search import GoogleCustomSearchAPI

__all__ = ["WebSearchDiscovery", "GoogleCustomSearchAPI"]
