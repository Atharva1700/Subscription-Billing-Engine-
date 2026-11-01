"""FastAPI routes. Thin layer: validation and mapping only."""
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .domain import FixedDiscount, PercentDiscount, Period, Plan
from .repository import SQLiteSubscriptionRepository
from .service import BillingService


class PlanIn(BaseModel):
    name: str
    monthly_cents: int = Field(ge=0)


class SubscribeIn(BaseModel):
    customer: str
    plan: PlanIn
    period_start: date
    period_end: date


class ChangePlanIn(BaseModel):
    plan: PlanIn
    on: date


def create_app(db_path: str = ":memory:", percent_off: int = 0, fixed_off_cents: int = 0) -> FastAPI:
    discounts = []
    if percent_off:
        discounts.append(PercentDiscount(percent_off))
    if fixed_off_cents:
        discounts.append(FixedDiscount(fixed_off_cents))
    service = BillingService(SQLiteSubscriptionRepository(db_path), discounts=discounts)
    app = FastAPI(title="Subscription Billing Engine")

    @app.post("/subscriptions", status_code=201)
    def subscribe(body: SubscribeIn):
        try:
            sub = service.subscribe(body.customer, Plan(body.plan.name, body.plan.monthly_cents),
                                    Period(body.period_start, body.period_end))
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"id": sub.id, "customer": sub.customer, "plan": sub.plan.name}

    @app.post("/subscriptions/{sub_id}/change-plan")
    def change_plan(sub_id: int, body: ChangePlanIn):
        try:
            q = service.change_plan(sub_id, Plan(body.plan.name, body.plan.monthly_cents), body.on)
        except KeyError:
            raise HTTPException(404, "subscription not found")
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"subscription_id": q.subscription_id, "old_plan": q.old_plan, "new_plan": q.new_plan,
                "prorated_cents": q.prorated_cents, "charged_cents": q.discounted_cents}

    return app
