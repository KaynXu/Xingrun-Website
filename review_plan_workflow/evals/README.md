# Review Plan Eval Fixtures

These fixtures define the minimum quality regression set for the review-plan workflow.

Each fixture contains an input payload, expected criteria, and deterministic checks. The runner is intentionally lightweight so the team can run it in normal unit tests without a separate eval platform or live LLM calls.

Run fixture definition validation:

```bash
python3 -m review_plan_workflow.evals.runner --validate-fixtures-only
```

Supported check operators:

- `containsAny`: plan text must include at least one listed marker.
- `containsAll`: plan text must include every listed marker.
- `notContainsAny`: plan text must not include any listed marker.
- `daysExactly`: plan must use the exact review-day list.
- `minQualityScore`: deterministic quality gate score must meet the threshold.
- `schemaValid`: final review-plan schema validity must match the expected boolean.

Math and physics fixtures default to China school-course context. IELTS fixtures remain independent IELTS exam cases.
