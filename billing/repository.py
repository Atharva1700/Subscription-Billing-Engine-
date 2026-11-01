"""Repository port and SQLite adapter for subscriptions."""
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol

from .domain import Period, Plan


@dataclass
class Subscription:
    id: Optional[int]
    customer: str
    plan: Plan
    period: Period


class SubscriptionRepository(Protocol):
    def add(self, sub: Subscription) -> Subscription: ...
    def get(self, sub_id: int) -> Optional[Subscription]: ...
    def update(self, sub: Subscription) -> None: ...


class SQLiteSubscriptionRepository:
    def __init__(self, path: str = ":memory:"):
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS subscriptions ("
            " id INTEGER PRIMARY KEY, customer TEXT NOT NULL,"
            " plan_name TEXT NOT NULL, monthly_cents INTEGER NOT NULL,"
            " period_start TEXT NOT NULL, period_end TEXT NOT NULL)")
        self.con.commit()

    def add(self, sub: Subscription) -> Subscription:
        cur = self.con.execute(
            "INSERT INTO subscriptions (customer, plan_name, monthly_cents, period_start, period_end)"
            " VALUES (?, ?, ?, ?, ?)",
            (sub.customer, sub.plan.name, sub.plan.monthly_cents,
             sub.period.start.isoformat(), sub.period.end.isoformat()))
        self.con.commit()
        sub.id = cur.lastrowid
        return sub

    def get(self, sub_id: int) -> Optional[Subscription]:
        row = self.con.execute(
            "SELECT id, customer, plan_name, monthly_cents, period_start, period_end"
            " FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
        if row is None:
            return None
        return Subscription(
            id=row[0], customer=row[1], plan=Plan(row[2], row[3]),
            period=Period(date.fromisoformat(row[4]), date.fromisoformat(row[5])))

    def update(self, sub: Subscription) -> None:
        self.con.execute(
            "UPDATE subscriptions SET plan_name = ?, monthly_cents = ? WHERE id = ?",
            (sub.plan.name, sub.plan.monthly_cents, sub.id))
        self.con.commit()
