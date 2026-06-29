"""Compatibility package for deployments that expect ``investment.*`` imports.

The source tree lives at the repository root, while much of the existing code
imports modules through the historical ``investment`` package name. Exposing the
repository root as this package path keeps those imports working without a
large, deployment-only rewrite.
"""
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

__path__ = [str(_PROJECT_ROOT)]

