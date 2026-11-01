from datetime import date

import pytest

from billing.domain import (DayRatioProration, FixedDiscount, NoDiscount, PercentDiscount,
                            Period, Plan, apply_discounts)

BASIC = Plan("basic", 1000)
PRO = Plan("pro", 3000)
JAN = Period(date(2026, 1, 1), date(2026, 1, 31))  # 30 days


def test_plan_rejects_empty_name_and_negative_price():
    with raises_exact(ValueError, "plan name required"):
        Plan("", 100)
    with raises_exact(ValueError, "price must not be negative"):
        Plan("x", -1)


def test_period_rejects_empty_and_reports_days():
    with raises_exact(ValueError, "period must be non-empty"):
        Period(date(2026, 1, 5), date(2026, 1, 5))
    assert JAN.days == 30


def test_remaining_clamps_before_start_and_after_end():
    assert JAN.remaining(date(2025, 12, 1)) == 30
    assert JAN.remaining(date(2026, 2, 10)) == 0


def test_proration_on_period_end_is_zero():
    assert DayRatioProration().net_change(BASIC, PRO, JAN, JAN.end) == 0


def test_proration_upgrade_mid_period_charges_difference():
    # 15 of 30 days left: (3000 - 1000) * 0.5 = 1000
    assert DayRatioProration().net_change(BASIC, PRO, JAN, date(2026, 1, 16)) == 1000


def test_proration_downgrade_gives_negative_credit():
    assert DayRatioProration().net_change(PRO, BASIC, JAN, date(2026, 1, 16)) == -1000


def test_proration_rounds_half_up_to_cents():
    # 1 of 3 days left, difference 100: 33.333 -> 33; 2 of 3: 66.67 -> 67
    p = Period(date(2026, 3, 1), date(2026, 3, 4))
    assert DayRatioProration().net_change(Plan("a", 0), Plan("b", 100), p, date(2026, 3, 3)) == 33
    assert DayRatioProration().net_change(Plan("a", 0), Plan("b", 100), p, date(2026, 3, 2)) == 67


def test_proration_rounds_negative_half_up():
    p = Period(date(2026, 3, 1), date(2026, 3, 4))  # 3 days
    # -100 * 1/3 = -33.33 -> -33 ; -100 * 2/3 = -66.67 -> -67
    assert DayRatioProration().net_change(Plan("b", 100), Plan("a", 0), p, date(2026, 3, 3)) == -33
    assert DayRatioProration().net_change(Plan("b", 100), Plan("a", 0), p, date(2026, 3, 2)) == -67


def test_no_change_of_price_is_zero():
    assert DayRatioProration().net_change(BASIC, Plan("basic2", 1000), JAN, date(2026, 1, 10)) == 0


def test_percent_discount_bounds():
    with raises_exact(ValueError, "percent must be between 0 and 100"):
        PercentDiscount(-1)
    with raises_exact(ValueError, "percent must be between 0 and 100"):
        PercentDiscount(101)


def test_percent_discount_applies_to_positive_amounts_only():
    d = PercentDiscount(10)
    assert d.apply(1000) == 900
    assert d.apply(0) == 0
    assert d.apply(-500) == -500


def test_percent_discount_rounds_half_up():
    assert PercentDiscount(50).apply(3) == 1  # 1.5 off rounds to 2 off, leaves 1


def test_fixed_discount_never_goes_below_zero():
    with raises_exact(ValueError, "discount must not be negative"):
        FixedDiscount(-5)
    d = FixedDiscount(300)
    assert d.apply(1000) == 700
    assert d.apply(200) == 0
    assert d.apply(-100) == -100


def test_no_discount_is_identity():
    assert NoDiscount().apply(123) == 123


def test_discounts_compose_in_order():
    assert apply_discounts(1000, [PercentDiscount(10), FixedDiscount(100)]) == 800
    assert apply_discounts(1000, [FixedDiscount(100), PercentDiscount(10)]) == 810
    assert apply_discounts(1000, []) == 1000


# --- boundary and attribute tests (added after the first mutation run) ---

def raises_exact(exc, message):
    """Assert the exception message exactly (pytest's match= is a substring search)."""
    return _Exact(exc, message)


class _Exact:
    def __init__(self, exc, message):
        self.exc, self.message = exc, message

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        assert kind is not None and issubclass(kind, self.exc), "expected exception"
        assert value.args == (self.message,), value.args
        return True


def test_plan_accepts_zero_price_and_keeps_fields():
    p = Plan("free", 0)
    assert (p.name, p.monthly_cents) == ("free", 0)


def test_period_accepts_one_day_and_keeps_bounds():
    p = Period(date(2026, 1, 1), date(2026, 1, 2))
    assert p.days == 1
    assert (p.start, p.end) == (date(2026, 1, 1), date(2026, 1, 2))


def test_remaining_on_start_is_full_period():
    assert JAN.remaining(JAN.start) == 30


def test_percent_boundaries_are_valid_and_stored():
    assert PercentDiscount(0).percent == 0
    assert PercentDiscount(0).apply(500) == 500
    assert PercentDiscount(100).percent == 100
    assert PercentDiscount(100).apply(500) == 0


def test_percent_rounding_is_half_up_on_exact_halves():
    # 50% of 5 is 2.5 -> off rounds up to 3 -> 2 left (half-even would give 3 left)
    assert PercentDiscount(50).apply(5) == 2


def test_fixed_zero_is_valid_and_stored():
    assert FixedDiscount(0).cents == 0
    assert FixedDiscount(0).apply(700) == 700


def test_fixed_discount_equal_to_amount_gives_zero_not_negative():
    assert FixedDiscount(200).apply(200) == 0


def test_proration_half_cent_rounds_up_for_positive_delta():
    # delta 1 cent * 1/2 = 0.5 -> 1 (half-up); half-even would give 0
    p = Period(date(2026, 1, 1), date(2026, 1, 3))
    assert DayRatioProration().net_change(Plan("a", 0), Plan("b", 1), p, date(2026, 1, 2)) == 1


def test_one_cent_amounts_are_discounted_correctly():
    assert PercentDiscount(50).apply(1) == 0  # 0.5 off rounds to 1 off
    assert FixedDiscount(300).apply(1) == 0
