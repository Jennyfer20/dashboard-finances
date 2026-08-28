"""Cree les tables BudgetLab dans la base Postgres pointee par DATABASE_URL.

Usage : python scripts/init_db.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db  # noqa: E402

init_db()
print("Tables creees (ou deja presentes).")
