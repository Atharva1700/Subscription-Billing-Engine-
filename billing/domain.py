"""Pure billing domain: plans, proration and discount strategies. No I/O."""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol


@dataclass(frozen=True)
class Plan:
    name: str
    monthly_cents: int

    def __post_init__(self):
        if not self.name:
            raise ValueError("plan name required")
        if self.monthly_cents < 0:
            raise ValueError("price must not be negative")


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    def __post_init__(self):
        if self.end <= self.start:
            raise ValueError("period must be non-empty")

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def remaining(self, on: date) -> int:
        """Days left after `on`, clamped to [0, days]."""
        return min(max((self.end - on).days, 0), self.days)


class ProrationStrategy(Protocol):
    def net_change(self, old: Plan, new: Plan, period: Period, on: date) -> int:
        """Cents to charge (positive) or credit (negative) for switching plans on `on`."""


def _round_cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class DayRatioProration:
    """Credit the unused part of the old plan, charge the unused part of the new plan."""

    def net_change(self, old: Plan, new: Plan, period: Period, on: date) -> int:
        left = period.remaining(on)
        if left == 0:
            return 0
        ratio = Decimal(left) / Decimal(period.days)
        delta = (Decimal(new.monthly_cents) - Decimal(old.monthly_cents)) * ratio
        return _round_cents(delta)


class NoDiscount:
    def apply(self, amount_cents: int) -> int:
        return amount_cents


class PercentDiscount:
    def __init__(self, percent: int):
        if not 0 <= percent <= 100:
            raise ValueError("percent must be between 0 and 100")
        self.percent = percent

    def apply(self, amount_cents: int) -> int:
        if amount_cents <= 0:
            return amount_cents
        off = _round_cents(Decimal(amount_cents) * self.percent / 100)
        return amount_cents - off


class FixedDiscount:
    def __init__(self, cents: int):
        if cents < 0:
            raise ValueError("discount must not be negative")
        self.cents = cents

    def apply(self, amount_cents: int) -> int:
        if amount_cents <= 0:
            return amount_cents
        return max(amount_cents - self.cents, 0)


def apply_discounts(amount_cents: int, discounts) -> int:
    for d in discounts:
        amount_cents = d.apply(amount_cents)
    return amount_cents
