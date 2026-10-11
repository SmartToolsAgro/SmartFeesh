"""Locks on things that have no row of their own to lock (ARCHITECTURE §4.3 locks rows when it can)."""

from django.db import connection


def lock_until_commit(key: str) -> None:
    """Wait until no other transaction holds `key`, then hold it until this transaction ends.

    A PostgreSQL advisory lock on a hash of the key ("lot:12"): two transactions that lock the same key
    run one after the other. Call it inside `transaction.atomic`. Two keys sharing a hash only wait for
    each other a little longer; nothing is wrong.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [key])


def lock_lot(batch_id: int) -> None:
    """Serialize the changes that decide a lot's result: its partnership terms and its closing (D-060, D-061)."""
    lock_until_commit(f"lot:{batch_id}")
