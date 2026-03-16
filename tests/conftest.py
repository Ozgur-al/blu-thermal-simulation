"""Shared pytest fixtures and session-level setup."""
from __future__ import annotations

import pytest


def pytest_configure(config):
    """Set pyvista to offscreen before any test collection imports."""
    try:
        import pyvista as pv
        pv.OFF_SCREEN = True
    except ImportError:
        pass
