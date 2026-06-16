# Review Plan Eval Fixtures

These fixtures define the minimum quality regression set for the review-plan workflow.

Each fixture contains an input payload, expected criteria, and deterministic checks. The runner is intentionally lightweight so the team can run it in normal unit tests without a separate eval platform or live LLM calls.

Run fixture definition validation:

```bash
python3 -m review_plan_workflow.evals.runner --validate-fixtures-only
```

Run an opt-in workflow eval for one fixture:

```bash
python3 -m review_plan_workflow.evals.runner \
  --run-workflow \
  --fixture math/algebra-weakness-6-week.json \
  --output /tmp/review-plan-eval-report.json
```

`--run-workflow` calls the real review-plan generation service and may call the configured LLM provider. Keep it out of normal unit tests; use fake generators in tests and run live evals manually when API keys and cost are expected.

Supported check operators:

- `containsAny`: plan text must include at least one listed marker.
- `containsAll`: plan text must include every listed marker.
- `notContainsAny`: plan text must not include any listed marker.
- `daysExactly`: plan must use the exact review-day list.
- `minQualityScore`: deterministic quality gate score must meet the threshold.
- `schemaValid`: final review-plan schema validity must match the expected boolean.

Math and physics fixtures default to China school-course context. IELTS fixtures remain independent IELTS exam cases.
