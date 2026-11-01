from datetime import date

from fastapi.testclient import TestClient

from billing.api import create_app
from billing.domain import Period, Plan
from billing.repository import SQLiteSubscriptionRepository
from billing.service import BillingService


def make_service(**kw):
    return BillingService(SQLiteSubscriptionRepository(), **kw)


def test_repository_round_trip():
    repo = SQLiteSubscriptionRepository()
    svc = BillingService(repo)
    sub = svc.subscribe("ann", Plan("basic", 1000), Period(date(2026, 1, 1), date(2026, 1, 31)))
    got = repo.get(sub.id)
    assert got.customer == "ann" and got.plan == Plan("basic", 1000)
    assert repo.get(999) is None


def test_service_change_plan_persists_new_plan():
    svc = make_service()
    sub = svc.subscribe("ann", Plan("basic", 1000), Period(date(2026, 1, 1), date(2026, 1, 31)))
    q = svc.change_plan(sub.id, Plan("pro", 3000), date(2026, 1, 16))
    assert (q.prorated_cents, q.discounted_cents) == (1000, 1000)
    assert svc.repo.get(sub.id).plan.name == "pro"


def test_service_discount_applies_to_charges_not_credits():
    from billing.domain import PercentDiscount
    svc = make_service(discounts=[PercentDiscount(50)])
    sub = svc.subscribe("ann", Plan("basic", 1000), Period(date(2026, 1, 1), date(2026, 1, 31)))
    up = svc.change_plan(sub.id, Plan("pro", 3000), date(2026, 1, 16))
    assert (up.prorated_cents, up.discounted_cents) == (1000, 500)
    down = svc.change_plan(sub.id, Plan("basic", 1000), date(2026, 1, 16))
    assert down.discounted_cents == down.prorated_cents == -1000


def test_service_rejects_date_outside_period_and_unknown_subscription():
    import pytest
    svc = make_service()
    sub = svc.subscribe("ann", Plan("basic", 1000), Period(date(2026, 1, 1), date(2026, 1, 31)))
    with pytest.raises(ValueError):
        svc.change_plan(sub.id, Plan("pro", 3000), date(2026, 2, 15))
    with pytest.raises(KeyError):
        svc.change_plan(12345, Plan("pro", 3000), date(2026, 1, 10))
    with pytest.raises(ValueError):
        svc.subscribe("", Plan("basic", 1000), Period(date(2026, 1, 1), date(2026, 1, 31)))


def test_api_subscribe_and_change_plan():
    client = TestClient(create_app(percent_off=10))
    r = client.post("/subscriptions", json={"customer": "ann", "plan": {"name": "basic", "monthly_cents": 1000},
                                            "period_start": "2026-01-01", "period_end": "2026-01-31"})
    assert r.status_code == 201
    sid = r.json()["id"]
    r = client.post(f"/subscriptions/{sid}/change-plan",
                    json={"plan": {"name": "pro", "monthly_cents": 3000}, "on": "2026-01-16"})
    assert r.status_code == 200
    body = r.json()
    assert body["prorated_cents"] == 1000 and body["charged_cents"] == 900


def test_api_error_codes():
    client = TestClient(create_app())
    assert client.post("/subscriptions/999/change-plan",
                       json={"plan": {"name": "pro", "monthly_cents": 3000}, "on": "2026-01-16"}).status_code == 404
    bad = client.post("/subscriptions", json={"customer": "ann", "plan": {"name": "basic", "monthly_cents": -1},
                                              "period_start": "2026-01-01", "period_end": "2026-01-31"})
    assert bad.status_code == 422
    empty = client.post("/subscriptions", json={"customer": "ann", "plan": {"name": "basic", "monthly_cents": 1},
                                                "period_start": "2026-01-05", "period_end": "2026-01-05"})
    assert empty.status_code == 422
