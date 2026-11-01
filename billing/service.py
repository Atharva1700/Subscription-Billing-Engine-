"""Application service: orchestrates domain strategies and the repository."""
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

from .domain import (DayRatioProration, NoDiscount, Period, Plan, ProrationStrategy,
                     apply_discounts)
from .repository import Subscription, SubscriptionRepository


@dataclass
class ChangeQuote:
    subscription_id: int
    old_plan: str
    new_plan: str
    prorated_cents: int
    discounted_cents: int


class BillingService:
    def __init__(self, repo: SubscriptionRepository,
                 proration: Optional[ProrationStrategy] = None,
                 discounts: Iterable = ()):
        self.repo = repo
        self.proration = proration or DayRatioProration()
        self.discounts = list(discounts) or [NoDiscount()]

    def subscribe(self, customer: str, plan: Plan, period: Period) -> Subscription:
        if not customer:
            raise ValueError("customer required")
        return self.repo.add(Subscription(None, customer, plan, period))

    def change_plan(self, sub_id: int, new_plan: Plan, on: date) -> ChangeQuote:
        sub = self.repo.get(sub_id)
        if sub is None:
            raise KeyError(sub_id)
        if not sub.period.start <= on <= sub.period.end:
            raise ValueError("date outside the billing period")
        net = self.proration.net_change(sub.plan, new_plan, sub.period, on)
        charged = apply_discounts(net, self.discounts) if net > 0 else net
        quote = ChangeQuote(sub_id, sub.plan.name, new_plan.name, net, charged)
        sub.plan = new_plan
        self.repo.update(sub)
        return quote
