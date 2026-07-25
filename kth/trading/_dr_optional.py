"""Optional-import shim for kth_dr — the DR plugin isn't always installed."""
from __future__ import annotations


def get_enrich_dr_premium():
    """Returns kth_dr's enrich_dr_premium, or a ('', None) no-op if kth_dr isn't importable."""
    try:
        from kth_dr.loader_dr import enrich_dr_premium
        return enrich_dr_premium
    except ImportError:
        return lambda t, c, get_close: ('', None)
