"""Artifact Discovery module for Phase 9.

Responsibilities:
- Discover artifacts/phase{2..8}/latest directories
- Prefer manifest-first discovery and delegate parsing to Manifest Parser
- Produce discovery_index.json
"""

from .service import DiscoveryService

__all__ = ["DiscoveryService"]
