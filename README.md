# Subscription Billing Engine (prototype)

Python domain logic for plan changes with day-ratio proration and discount strategies, a
repository port with a SQLite adapter, and a FastAPI layer. Synthetic data only, and no real
payment or customer system is involved.

## Results against the stated targets

| Target | Result | Evidence |
|---|---|---|
| 100% domain branch coverage | **100%** (18/18 branches, `billing/domain.py`) | `results/coverage.txt` |
| 85%+ mutation kill rate under mutmut | **97.5%** raw (77/79); **100%** of killable mutants (77/77). The 2 survivors are equivalent | `results/mutation_stats.json` |

The mutation numbers need context. The first run killed **53 of 79 (67%)**. Adding tests for
boundaries, exact error messages and one-cent amounts raised it to **77 of 79**. Those tests were
written after seeing which mutants survived, so the final figure is partly tuned to the mutants.
The earlier run is in `results/` as well (`results_mutmut*.log`).

The two survivors are `amount_cents <= 0` changed to `< 0` in the discount `apply` methods. At
an amount of zero both versions return zero, so no test can tell them apart.

## What was not done

- **Test-driven development was not followed.** The code was written first and the tests came
  after, so the TDD wording in the resume bullet does not describe this build.
- **Mutation testing covers the domain unit tests only.** mutmut copies only the module under
  test into its work directory, so the service and API tests (`tests/test_service_and_api.py`)
  fail at collection there. Those tests are included in the pytest and coverage runs.
- **Docker not built.** The `Dockerfile` was written, but the sandbox Docker daemon was not
  running and Docker Hub could not be reached, so no image was built or run.
- **GitHub Actions not run.** `.github/workflows/ci.yml` was not executed. Its steps were run
  locally.

## How it works

- `billing/domain.py` (pure logic, no I/O): `Plan`, `Period`, `DayRatioProration` (credit for the
  unused old plan, charge for the unused new plan, half-up rounding to cents), and discount
  strategies `PercentDiscount`, `FixedDiscount` and `NoDiscount`. Discounts apply to charges only,
  never to credits, and compose in order.
- `billing/repository.py`: `SubscriptionRepository` protocol and `SQLiteSubscriptionRepository`.
- `billing/service.py`: `BillingService` joins the strategies with the repository.
- `billing/api.py`: FastAPI routes. `POST /subscriptions` returns 201. `POST
  /subscriptions/{id}/change-plan` returns 404 for an unknown subscription and 422 for a
  date outside the period.

## Run it

```
pip install -r requirements.txt
python -m pytest -q tests                                  # 30 tests
python -m coverage run --branch --source=billing.domain -m pytest -q tests && python -m coverage report -m
python -m mutmut run && python -m mutmut export-cicd-stats  # uses pyproject.toml
uvicorn billing.api:create_app --factory --port 8000       # after pip install
```

## Files

- `billing/`: domain, repository, service, API
- `tests/test_domain.py`, `tests/test_service_and_api.py`
- `results/`: coverage, pytest output, mutation stats, mutation run logs
- `Dockerfile` (not built), `.github/workflows/ci.yml` (not run)
