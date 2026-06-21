"""Filesystem-safe model name slug for cache directory naming."""
from __future__ import annotations


def model_slug(model_name: str) -> str:
    """'NeoQuasar/Kronos-small@a3f1c2d' -> 'NeoQuasar_Kronos-small-a3f1c2d'"""
    return model_name.replace("/", "_").replace("@", "-").replace("\\", "_")
