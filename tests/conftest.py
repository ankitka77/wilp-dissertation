"""Repository-level pytest bootstrap for legacy and shared imports."""

from __future__ import annotations

import pytest

import project_bootstrap  # noqa: F401


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Sort collected tests deterministically by path and node id."""

    items.sort(key=lambda item: (str(item.path), item.nodeid))
