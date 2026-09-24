"""
reports.py - numbers for the dashboard charts.

The two views in schema.sql do the adding up; these functions only pick
out the logged-in user's rows.
"""

from . import db


def monthly_flow(user_id: int) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT month, money_in, money_out FROM v_monthly_flow WHERE user_id = ? ORDER BY month",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def top_merchants(user_id: int, limit: int = 10) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT merchant, payments, total FROM v_merchant_spend
               WHERE user_id = ? ORDER BY total DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
