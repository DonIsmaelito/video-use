# M2 check gate (motion design)

Instances: 23 `motion_slot.py check` runs with a classifiable next action.
- agreement with the LLM's actual next step: 1/23 = 0.043
- Jev latency ms: {'n': 23, 'median': 126.02, 'mean': 212.1, 'p90': 454.86, 'min': 98.9, 'max': 504.77}
- LLM think time after the check output (s): {'n': 18, 'median': 9.7, 'mean': 14.28, 'p90': 23.5, 'min': 0.1, 'max': 58.7}

## Confusion (rows = actual, cols = Jev)

- fix_source: {'inspect_or_rerun': 6, 'fix_environment': 2, 'proceed_to_render': 3}
- inspect_or_rerun: {'fix_source': 1, 'inspect_or_rerun': 1, 'fix_environment': 1}
- fix_environment: {'inspect_or_rerun': 3, 'fix_source': 4}
- proceed_to_render: {'inspect_or_rerun': 2}
