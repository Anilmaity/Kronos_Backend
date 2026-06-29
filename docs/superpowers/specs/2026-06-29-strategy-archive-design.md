# Strategy Archive — Design Spec

**Date:** 2026-06-29
**Status:** Approved (design); pending implementation plan
**Repos affected:** `Kronos_Backend` (Django/GraphQL), `kronos_frontend` (Next.js)
**Deploy target:** `algorobos` Lightsail box (backend) + Netlify (frontend), production

## Problem

Deployed strategies accumulate on the dashboard even after they are finished/retired.
The user wants a way to **manually archive** a strategy so it leaves the dashboard and
appears under a dedicated **Archive** tab, where it can be viewed and restored. Archived
strategies must not be shown on the main dashboard.

## Decision summary

Add a single `archived` boolean to `UserStrategy`. Archiving is a **manual user action**.
Archiving **auto-stops** the strategy and is **blocked while a position is open**.
Unarchiving returns the strategy to the dashboard but does **not** auto-redeploy it.

Alternatives rejected:
- `status` enum (ACTIVE/RETIRED/ARCHIVED): bigger refactor of all-boolean code. YAGNI.
- Derive archived from `deployed=False AND is_active=False`: cannot express a *manual*
  archive; would auto-sweep already-retired strategies into the archive unbidden.

## Data model

`apis/models.py` — `UserStrategy`:

```python
archived = models.BooleanField(default=False)
```

- Migration `apis/migrations/0006_userstrategy_archived.py` — additive column with a
  default, non-destructive, safe to run on the live shared Postgres.
- Expose `archived` on `UserStrategyType` (`apis/schema/types/user_strategy_type.py`)
  (it is currently a DjangoObjectType that only excludes `position_set`, so the field is
  exposed automatically once the model has it; confirm during implementation).

## Behavior

### Archive (`ArchiveStrategy` mutation)
1. Require auth (`@user_authenticate`) and verify ownership via `user_broker__user == user`.
2. **Guard:** reject if the strategy has any open position (`Position.objects.filter(
   user_strategy=us).exclude(quantity=0).exists()`), with a clear error: exit positions first.
3. Set `archived=True`, `deployed=False`, `is_active=False` (auto-stop).
4. Return the updated `UserStrategyType` (and a success boolean).

### Unarchive (`UnarchiveStrategy` mutation)
1. Auth + ownership check as above.
2. Set `archived=False`. Leave `deployed`/`is_active` as-is (stays stopped).
3. Return the updated `UserStrategyType`.

Unarchive deliberately does **not** redeploy — re-deploying is a separate, explicit action.

## Backend (Kronos_Backend, GraphQL)

- `apis/schema/mutation/user/archive_strategy.py` → class `ArchiveStrategy`
  (auto-discovered by the loader: filename snake_case → PascalCase class).
- `apis/schema/mutation/user/unarchive_strategy.py` → class `UnarchiveStrategy`.
- `apis/schema/query/archived_strategies.py` → class `ArchivedStrategies`
  (`@user_authenticate`, returns `UserStrategy.objects.filter(user_broker__user=user,
  archived=True)`), for the Archive tab.
- **Dashboard filtering:** the dashboard reads `getuserdata → userbroker.userstrategys`.
  The resolver that returns a broker's `userstrategys` must exclude `archived=True` so
  archived strategies disappear from the dashboard. Locate the exact resolver
  (`getuserdata` query and/or `UserBrokerType.resolve_userstrategys`) during
  implementation and add `.filter(archived=False)` / `.exclude(archived=True)`.

## Frontend (kronos_frontend, Next.js 14)

- **Nav:** add an `Archive` entry to `sidebarLinkArray` in
  `app/(main)/_components/constants.ts` (with an icon).
- **Route:** new `app/(main)/archive/page.tsx` + `app/(main)/archive/_components/main.tsx`.
- **Reuse** `StrategyTable` / `StrategyTableRow` / `StrategyBox` from the dashboard,
  fed by the archived query. The archive view is read-mostly: shows history/P&L and offers
  **Unarchive** (and a deep-link to re-deploy via the normal flow).
- **GraphQL ops** in `GraphQL/strategyControls.ts`: `ARCHIVE_STRATEGY`,
  `UNARCHIVE_STRATEGY`, `GET_ARCHIVED_STRATEGIES`.
- **Dashboard row menu:** add an **Archive** action (alongside Pause/Resume, Multiplier,
  Exit, Delete) in `StrategyTableRow`. On archive success, trigger the existing
  `useStrategyChangeHappend` refetch so the row drops off the dashboard.
- Archived strategies are hidden from the dashboard by the backend resolver; no extra
  client-side filtering needed beyond using the dedicated query for the Archive tab.

## Testing

- **Backend** (`python manage.py test apis`, in-memory SQLite):
  - `ArchiveStrategy` sets `archived=True, deployed=False, is_active=False`.
  - Archive is rejected when an open position exists (guard).
  - Archive/Unarchive rejected for a non-owner (ownership check).
  - `ArchivedStrategies` returns only the caller's archived rows.
  - Dashboard listing excludes archived rows.
- **Frontend:** `npm run lint` + `npm run build` (repo has no test runner), plus a manual
  click-through: archive from dashboard → row disappears → appears in Archive tab →
  unarchive → returns to dashboard.

## Deployment (order matters)

1. **Backend first** — scp changed files to `algorobos` (`/home/ubuntu/KronosStrategies`
   checkout is not a git repo for strategies; backend deployed similarly), then
   `docker compose -p kronos build kronos_backend-web`, run `migrate` against production
   Postgres, restart the service. Migration is additive/non-destructive.
2. **Frontend second** — push to Bitbucket `main`; Netlify auto-deploys to
   `app.algorobos.com`. The backend must be live first or the new `archived` field/query
   returns errors. **Confirm with the user before the frontend push** (it ships live).

## Risks / notes

- Schema change on the **shared production DB** used by all three repos. The column is
  additive with a default, so the SQLAlchemy mirrors in `KronosStrategies` and
  `Kronos_Backend/utils` keep working without change (they simply won't see the new column
  until/unless mirrored). No strategy-engine change is required for this feature.
- No open positions exist on the 5 currently-retired strategies, so they can be archived
  immediately once the feature ships.
