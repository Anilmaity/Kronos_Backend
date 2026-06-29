# Strategy Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user manually archive a deployed strategy so it leaves the dashboard and appears under a new Archive tab, from which it can be restored.

**Architecture:** Add one additive boolean `UserStrategy.archived`. Backend GraphQL gains `ArchiveStrategy`/`UnarchiveStrategy` mutations and an `ArchivedStrategies` query; the dashboard listing resolvers exclude archived rows. Frontend gains an Archive sidebar tab + route that lists archived strategies, plus an Archive row-action on the dashboard.

**Tech Stack:** Django 5, graphene/graphql-jwt, Postgres (prod) / SQLite (tests); Next.js 14 App Router, Apollo Client, shadcn/ui.

## Global Constraints
- Backend GraphQL files are auto-discovered: filename `snake_case.py` → class `PascalCase`. Mutations live in `apis/schema/mutation/user/`, queries in `apis/schema/query/`.
- User mutations use `@user_authenticate` and scope by `user_broker__user == info.context.user` (superuser may act on any).
- Archive auto-stops the strategy (`deployed=False, is_active=False`) and is blocked when an open position exists (`Position.objects.filter(user_strategy=us).exclude(quantity=0).exists()`).
- Unarchive sets `archived=False` only; never auto-redeploys.
- Deploy order: backend (with migration) first, frontend second.
- Frontend endpoint and backend both serve from `app.algorobos.com`.

---

### Task 1: Model field + migration

**Files:**
- Modify: `apis/models.py` (UserStrategy)
- Create: `apis/migrations/0006_userstrategy_archived.py`
- Test: `apis/tests.py`

- [ ] **Step 1:** Add to `UserStrategy` after `deployed`:
```python
    archived = models.BooleanField(default=False)
```
- [ ] **Step 2:** Generate migration: `python manage.py makemigrations apis` → expect `0006_userstrategy_archived.py`.
- [ ] **Step 3:** Add test `ArchiveModelTests` confirming default is False:
```python
class ArchiveModelTests(TestCase):
    def test_default_archived_false(self):
        us = _mk_user_strategy()
        self.assertFalse(us.archived)
```
- [ ] **Step 4:** Run `python manage.py test apis.ArchiveModelTests` → PASS.
- [ ] **Step 5:** Commit.

### Task 2: ArchiveStrategy + UnarchiveStrategy mutations

**Files:**
- Create: `apis/schema/mutation/user/archive_strategy.py` (class `ArchiveStrategy`)
- Create: `apis/schema/mutation/user/unarchive_strategy.py` (class `UnarchiveStrategy`)
- Test: `apis/tests.py`

**Interfaces produced:** GraphQL `ArchiveStrategy(userStrategyId: String!) { Response, UserStrategy }`, `UnarchiveStrategy(userStrategyId: String!) { Response, UserStrategy }`.

- [ ] **Step 1:** `archive_strategy.py`:
```python
import graphene
from apis.models import UserStrategy, Position
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class ArchiveStrategy(graphene.Mutation):
    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        user_strategy_id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, user_strategy_id):
        try:
            if info.context.user.is_superuser:
                us = UserStrategy.objects.get(id=user_strategy_id)
            else:
                us = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=user_strategy_id
                )
        except UserStrategy.DoesNotExist:
            return ArchiveStrategy(Response="Strategy Does Not Exist", UserStrategy=None)

        if Position.objects.filter(user_strategy=us).exclude(quantity=0).exists():
            return ArchiveStrategy(
                Response="Cannot archive: open positions exist. Exit the strategy first.",
                UserStrategy=us,
            )

        us.archived = True
        us.deployed = False
        us.is_active = False
        us.save()
        return ArchiveStrategy(Response="Success", UserStrategy=us)
```
- [ ] **Step 2:** `unarchive_strategy.py`:
```python
import graphene
from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class UnarchiveStrategy(graphene.Mutation):
    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        user_strategy_id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, user_strategy_id):
        try:
            if info.context.user.is_superuser:
                us = UserStrategy.objects.get(id=user_strategy_id)
            else:
                us = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=user_strategy_id
                )
        except UserStrategy.DoesNotExist:
            return UnarchiveStrategy(Response="Strategy Does Not Exist", UserStrategy=None)
        us.archived = False
        us.save()
        return UnarchiveStrategy(Response="Success", UserStrategy=us)
```
- [ ] **Step 3:** Tests `ArchiveMutationTests` (success sets flags; guard on open position; non-owner rejected; unarchive clears flag). Direct-call pattern like `SetMultiplierTests`.
- [ ] **Step 4:** Run `python manage.py test apis.ArchiveMutationTests` → PASS.
- [ ] **Step 5:** Commit.

### Task 3: ArchivedStrategies query + dashboard exclusion

**Files:**
- Create: `apis/schema/query/archived_strategies.py` (class `ArchivedStrategies`)
- Modify: `apis/schema/types/user_broker_type.py` (`resolve_userstrategys`)
- Modify: `apis/schema/types/user_type.py` (`resolve_userstrategys`)
- Test: `apis/tests.py`

**Interfaces produced:** GraphQL `archivedStrategies { ...UserStrategyType }`.

- [ ] **Step 1:** `archived_strategies.py`:
```python
import graphene
from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class ArchivedStrategies(graphene.ObjectType):
    archived_strategies = graphene.List(UserStrategyType)

    @user_authenticate
    def resolve_archived_strategies(self, info):
        return UserStrategy.objects.filter(
            user_broker__user=info.context.user, archived=True
        ).order_by("-created_at")
```
- [ ] **Step 2:** In `user_broker_type.py` `resolve_userstrategys`, add `.exclude(archived=True)` to both branches.
- [ ] **Step 3:** In `user_type.py` `resolve_userstrategys`, add `.exclude(archived=True)`.
- [ ] **Step 4:** Test `ArchiveQueryTests`: archived row appears in ArchivedStrategies and is excluded from broker/user resolvers.
- [ ] **Step 5:** Run `python manage.py test apis` (full) → PASS.
- [ ] **Step 6:** Commit.

### Task 4: Frontend GraphQL ops + Archive row action

**Files:**
- Modify: `GraphQL/strategyControls.ts`
- Modify: `app/(main)/dashboard/_components/StrategyTableRow.tsx`

- [ ] **Step 1:** Append to `strategyControls.ts`:
```ts
export const ARCHIVE_STRATEGY = gql`
  mutation ArchiveStrategy($userStrategyId: String!) {
    ArchiveStrategy(userStrategyId: $userStrategyId) { Response }
  }
`;
export const UNARCHIVE_STRATEGY = gql`
  mutation UnarchiveStrategy($userStrategyId: String!) {
    UnarchiveStrategy(userStrategyId: $userStrategyId) { Response }
  }
`;
export const GET_ARCHIVED_STRATEGIES = gql`
  query ArchivedStrategies {
    archivedStrategies {
      id
      name
      brokerName
      multiplyer
      isActive
      createdAt
      totalProfitLoss
      totalPositionCount
      strategy { id name }
    }
  }
`;
```
- [ ] **Step 2:** In `StrategyTableRow.tsx` import `ARCHIVE_STRATEGY`, add a `handleArchiveStrategy` that mutates and on `Response==="Success"` toasts + `setStrategyChangeHappend(true)` (else toast the Response message), and add a `MenubarItem` "Archive Strategy" after Delete.
- [ ] **Step 3:** `npm run lint` → clean.
- [ ] **Step 4:** Commit.

### Task 5: Archive tab (nav + route + table)

**Files:**
- Modify: `app/(main)/_components/constants.ts` (sidebar link, icon `MdArchive`)
- Create: `app/(main)/archive/page.tsx`
- Create: `app/(main)/archive/_components/main.tsx`

- [ ] **Step 1:** Add `MdArchive` import and `{ title: "Archive", path: "/archive", icon: MdArchive }` to `sidebarLinkArray`.
- [ ] **Step 2:** `archive/page.tsx` exporting metadata + `<ArchivePage />`.
- [ ] **Step 3:** `archive/_components/main.tsx`: client component querying `GET_ARCHIVED_STRATEGIES` (no-cache), rendering a table (No., Strategy, Broker, Created, Status, P&L, Unarchive button). Unarchive calls `UNARCHIVE_STRATEGY`, toasts, refetches. Empty state when none.
- [ ] **Step 4:** `npm run lint` && `npm run build` → success.
- [ ] **Step 5:** Commit.

### Task 6: Deploy

- [ ] **Backend:** scp changed backend files to `algorobos:/home/ubuntu/Kronos_Backend`, `docker compose -p kronos build kronos_backend-web`, `docker compose -p kronos run --rm kronos_backend-web python manage.py migrate apis`, `docker compose -p kronos up -d kronos_backend-web`. Verify `archivedStrategies` resolves.
- [ ] **Frontend:** commit on a branch, push to Bitbucket `main` (Netlify auto-deploys). Verify Archive tab on `app.algorobos.com`.

## Self-Review
- Spec coverage: model+migration (T1), mutations+guard+auth (T2), archived query + dashboard exclusion (T3), FE ops+row action (T4), FE tab/route (T5), deploy order (T6). ✓
- Placeholders: none — all code shown. ✓
- Type consistency: mutation names `ArchiveStrategy`/`UnarchiveStrategy`, query field `archivedStrategies`, GraphQL arg `userStrategyId` consistent across BE/FE. ✓
