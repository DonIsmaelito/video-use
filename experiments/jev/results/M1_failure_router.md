# M1 failure-class router (motion design)

Instances: 103 failed commands from 21 observer runs (gpt-6-astra low).

- failure_class agreement with regex silver labels: 49/74 = 0.662
- next_action agreement with what the LLM actually did next: 22/83 = 0.265
- next_action gated (p>=0.45, margin>=0.15): 22/80 = 0.275 at coverage 0.964
- retry_same probability when the agent did retry the identical command: {'n': 0}
- retry_same probability when the agent changed something: {'n': 103, 'median': 0.1, 'mean': 0.12, 'p90': 0.21, 'min': 0.03, 'max': 0.4}
- Jev latency ms: {'n': 103, 'median': 135.71, 'mean': 152.68, 'p90': 179.84, 'min': 90.66, 'max': 429.03}
- LLM think time before next command after a failure (s): {'n': 87, 'median': 7.5, 'mean': 9.81, 'p90': 17.6, 'min': 0.1, 'max': 82.8}

## Confusion: next_action (rows = agent's actual, cols = Jev)

- inspect_or_read: {'fix_environment': 16, 'edit_source_or_script': 2, 'inspect_or_read': 9}
- edit_source_or_script: {'fix_environment': 12, 'inspect_or_read': 7, 'edit_source_or_script': 3}
- run_check: {'fix_environment': 4}
- fix_environment: {'fix_environment': 10, 'inspect_or_read': 6, 'edit_source_or_script': 12}
- render: {'fix_environment': 2}

## Confusion: failure_class (rows = silver, cols = Jev)

- missing_module_or_tool: {'missing_module_or_tool': 6, 'wrong_path_or_missing_file': 3}
- wrong_path_or_missing_file: {'wrong_path_or_missing_file': 13}
- lint_error_in_authored_content: {'lint_error_in_authored_content': 5, 'wrong_path_or_missing_file': 1}
- browser_binary_missing: {'missing_shared_library_or_system_package': 12, 'wrong_path_or_missing_file': 8, 'browser_binary_missing': 6}
- layout_or_frame_qc_failure: {'layout_or_frame_qc_failure': 9}
- missing_shared_library_or_system_package: {'missing_shared_library_or_system_package': 2}
- script_hang_or_timeout: {'script_hang_or_timeout': 8, 'wrong_path_or_missing_file': 1}
