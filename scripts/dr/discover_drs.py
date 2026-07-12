#!/usr/bin/env python3
"""CLI entrypoint: discover DRs from seed list.

Usage:
    python scripts/dr/discover_drs.py
"""
import sys
sys.path.insert(0, ".")
from kth_dr.discover_drs import main

if __name__ == "__main__":
    main()
