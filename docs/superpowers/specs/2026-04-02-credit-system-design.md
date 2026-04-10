# Credit System Design

## Summary

This design adds an organization-shared credit system for AI-cost-bearing features in Xingrun-Summary.

Goals:

- Let each organization consume from a shared credit pool.
- Let organization owners recharge credits through Xiaohongshu orders.
- Record per-call AI token usage and convert usage to internal credits.
- Let owners review organization balance, recharge history, and member-level consumption.
- Block AI usage when an organization does not have enough credits.

Non-goals for phase 1:

- Direct online payment inside this app.
- Fully automatic Xiaohongshu virtual delivery if platform delivery capabilities are unclear.
- Automatic refund reconciliation from Xiaohongshu. Phase 1 supports manual adjustment with preserved ledger history.

## Current Context

The current product already has:

- Organizations and role-based access with `super_owner`, `owner`, `admin`, and `member`.
- Organization-scoped membership and owner approval flows.
- Several AI-backed features with real provider cost, including lesson plan generation, consultation batch parsing, and legacy lesson feedback draft generation.
- A React frontend and Flask backend in one repository backed by SQLite.

The existing model is a good fit for organization-shared credits because users already belong to one organization and owner-only admin surfaces already exist.

## Product Decisions

The approved product direction is:

- Credits are owned by the organization, not by an individual user.
- `owner` accounts recharge organization credits.
- Members, admins, and owners all consume from the same organization pool when they use AI features.
- Owners can inspect per-member consumption details.
- Xiaohongshu is the primary recharge channel.
- Phase 1 recharge entry is a fixed redemption page, not a unique per-order link.
- The owner logs in, enters Xiaohongshu order information, and the server validates the order before crediting the organization.
- Phase 1 uses a fixed redemption page with `order number + helper verification field`, recommended as masked phone suffix.

## Recharge Architecture

### Recommended phase 1 flow

1. The customer buys a Xiaohongshu product that represents a credit package.
2. The product page, order note, or automated message sends the customer to a fixed redemption page.
3. The customer logs in as an `owner`.
4. The owner submits:
   - Xiaohongshu order number
   - Helper verification field, recommended as buyer phone last 4 digits
5. The backend validates the order against Xiaohongshu:
   - order exists
   - payment succeeded
   - ordered product or SKU maps to a configured credit package
   - order is not refunded or closed
   - order has not already been redeemed
   - helper verification field matches
6. If valid, the backend records the redemption and credits the owner’s organization pool.
7. The order becomes non-redeemable for any future attempt.

### Why a fixed redemption page was chosen

- It avoids dependency on Xiaohongshu being able to deliver a unique secure link per order.
- It still keeps verification server-side, so users cannot obtain credits by typing arbitrary values unless the platform confirms the order.
- It lets the app bind the recharge to the currently logged-in owner and therefore to one organization.

### Why not accept a raw order number without verification

Order number alone is not a trustworthy credential. The backend must verify a real paid order from Xiaohongshu before granting credits. If Xiaohongshu platform permissions are temporarily unavailable, the redemption flow must fall back to manual review rather than trust user input.

## Data Model

The credit system should use explicit ledgers instead of only storing a mutable balance field. Balance fields may exist for faster reads, but all value changes must be backed by immutable ledger rows.

### `organization_credit_accounts`

One row per organization summarizing its current state.

Suggested fields:

- `organization_id`
- `credit_balance`
- `total_recharged`
- `total_consumed`
- `updated_at`

Purpose:

- Fast balance reads for UI and authorization checks.
- Derived summary values backed by ledger rows.

### `organization_credit_ledger`

Immutable organization credit ledger for every balance change.

Suggested fields:

- `id`
- `organization_id`
- `direction` with values `credit` or `debit`
- `amount`
- `balance_after`
- `source_type` with values such as:
  - `xhs_order_redeem`
  - `manual_adjustment`
  - `ai_usage`
  - `refund_reversal`
- `source_id`
- `note`
- `operator_user_id`
- `created_at`

Purpose:

- Full recharge and deduction audit trail.
- Refund compensation without deleting history.
- Reliable reporting and support debugging.

### `xhs_order_redemptions`

Tracks each Xiaohongshu order that can add credits.

Suggested fields:

- `id`
- `platform` default `xiaohongshu`
- `platform_order_id`
- `product_id`
- `sku_id`
- `product_name`
- `paid_amount`
- `currency`
- `buyer_masked_phone`
- `order_status`
- `redeem_status` with values `pending`, `redeemed`, `refunded`, `blocked`
- `credit_amount`
- `redeemed_organization_id`
- `redeemed_by_user_id`
- `redeemed_at`
- `raw_order_payload`
- `created_at`
- `updated_at`

Constraints:

- `platform + platform_order_id` must be unique.
- One order can only be redeemed once.

Purpose:

- Prevent duplicate redemption.
- Preserve source payload for support and later reconciliation.
- Support future refund handling and order analytics.

### `ai_usage_ledger`

One row per AI call that incurs or attempts to incur credit usage.

Suggested fields:

- `id`
- `organization_id`
- `user_id`
- `feature_key`
- `provider`
- `model`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `token_cost_raw`
- `credit_cost_final`
- `source_record_type`
- `source_record_id`
- `request_id`
- `created_at`

Purpose:

- Owner-facing member usage analytics.
- Internal cost understanding by provider, model, and feature.
- Support future pricing-rule changes without losing raw usage context.

## Charging Rules

### Approved direction

Phase 1 should use mixed charging:

- Display simple feature-based credit pricing to customers.
- Internally record real token usage for every AI call.
- Store both raw token usage and final charged credits.

### Why mixed charging

Pure token-based pricing is accurate but hard for owners to understand because the same feature may cost different amounts from one run to another. Pure flat pricing is easy to explain but can drift too far from real cost. A mixed model preserves understandable UX while retaining operational accuracy.

### Recommended phase 1 rule shape

- `consultation_ai_parse`: fixed base credit, with optional extra charge if token usage crosses a configured threshold
- `legacy_lesson_feedback_draft`: fixed per-run charge
- `lesson_plan_generate`: fixed per-run charge
- `audio_transcription`: separated from lesson generation when present so cost is understandable and tunable

The pricing configuration should be stored in one place and not be hardcoded inline inside route handlers.

## AI Call Integration

All AI-cost-bearing entry points should use one shared accounting layer instead of performing ad hoc checks in each route.

### Shared backend workflow

1. Resolve current authenticated user and organization.
2. Determine feature key and pricing rule.
3. Check whether the organization has enough credits for the minimum required charge.
4. Call the provider.
5. Extract or estimate token usage.
6. Convert usage to final credit charge.
7. Write:
   - one `ai_usage_ledger` row
   - one `organization_credit_ledger` debit row
   - one updated `organization_credit_accounts` balance
8. Return the feature result.

### Failure handling

- If balance is insufficient before the call, reject the request with a clear recharge message.
- If the provider fails before usable output is produced, do not charge credits.
- If a partial-output scenario exists in a future feature, the charging rule must explicitly define whether the attempt is chargeable.

### Likely phase 1 integration points

- lesson review generation
- consultation AI batch parsing
- legacy lesson feedback draft generation
- any future token-consuming AI helper route

## Owner Experience

Phase 1 should add a dedicated credit center instead of burying this inside settings.

### Credit center sections

1. Overview
   - current balance
   - lifetime recharge total
   - lifetime usage total
   - recent recharge time
   - recent AI usage time

2. Redeem recharge
   - order number input
   - helper verification input
   - redemption result feedback

3. Member usage
   - member name
   - total consumed credits
   - usage count
   - last usage time
   - drill-down into per-call records

4. Organization ledger
   - recharge entries
   - AI usage deductions
   - manual adjustments
   - refund reversals

### Access rules

- Only `owner` and `super_owner` can redeem orders into an organization.
- Owners can view organization-level and member-level credit analytics.
- `admin` and `member` may see low-balance or insufficient-credit errors during AI use but cannot redeem orders.

## Security and Anti-Abuse Rules

Phase 1 should enforce the following:

- One Xiaohongshu order can only be redeemed once.
- Only the authenticated owner’s organization can receive the redeemed credits.
- Redemption always requires server-side platform validation.
- Order number input is never trusted on its own.
- The helper verification field is required for public fixed-page redemption.
- Raw platform payloads should be stored carefully and only shown in masked form in admin surfaces.

If platform order validation is unavailable at runtime, the product should fail closed:

- do not issue credits automatically
- allow manual review or support handling instead

## Refund and Reversal Handling

Phase 1 should support manual reversal while keeping the data model ready for automation later.

Recommended behavior:

- If a redeemed order later refunds, a support operator creates a negative organization ledger entry.
- The original redemption row remains intact and the redemption record status moves to `refunded`.
- If the organization balance is not high enough to absorb the reversal, the organization is marked for follow-up instead of deleting historical usage rows.

This preserves accounting history and avoids hiding already-consumed value.

## API Surface

The exact route names can change during implementation, but phase 1 needs these capabilities:

- redeem Xiaohongshu order into current owner organization
- fetch organization credit overview
- fetch organization credit ledger
- fetch member credit usage summary
- fetch member usage details
- perform AI balance precheck and deduction through shared backend service

The backend should keep the platform-validation logic and the credit-accounting logic in reusable service functions rather than embedding them deeply in Flask route bodies.

## Testing Strategy

Minimum automated coverage for phase 1:

- order redemption succeeds for valid owner, valid order, and valid verification field
- duplicate redemption fails
- non-owner redemption fails
- wrong verification data fails
- refunded or closed order fails
- AI deduction writes both usage and ledger rows
- insufficient credit blocks AI usage
- member usage summary aggregates correctly
- organization balance updates correctly after recharge and deduction

Tests should focus on the shared accounting services first, then verify the public API layer.

## Rollout Plan

Recommended delivery slices:

1. Add database tables and data-access helpers.
2. Add owner credit center read APIs and redemption API.
3. Add shared AI charging service.
4. Integrate charging service into the first AI routes.
5. Add owner UI for overview, redemption, and member usage.
6. Add manual adjustment and reversal tools for operations if needed.

This sequencing gives value early while keeping accounting consistent.

## Open Assumptions Locked For Planning

These assumptions were made during design and should be treated as scope for the implementation plan unless changed explicitly:

- Xiaohongshu platform access likely exists for order validation and callbacks.
- Phase 1 uses a fixed redemption page rather than a one-time delivery link.
- Phase 1 uses `owner login + order number + phone suffix` as the public redemption flow.
- Credits are shared by the whole organization.
- Owners need per-member usage visibility.
- Mixed charging is preferred over purely token-based or purely flat-rate charging.
