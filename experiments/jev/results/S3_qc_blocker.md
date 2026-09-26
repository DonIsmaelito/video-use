# S3 post-render QC blocker gate (raw-footage clip)

14/16 instances classified correctly at p>=0.5; latency ms {'n': 16, 'median': 352.59, 'mean': 333.47, 'p90': 561.43, 'min': 95.8, 'max': 572.93}

## Rows

- {'name': 'T1 clean final', 'label_blocker': False, 'p_blocker': 0.24, 'correct': True, 'action': 'ship', 'p_action': 0.82}
- {'name': 'T1 124 ms caption drift', 'label_blocker': True, 'p_blocker': 0.27, 'correct': False, 'action': 'ship', 'p_action': 0.75}
- {'name': 'T3 sampler traceback at exact duration', 'label_blocker': False, 'p_blocker': 0.41, 'correct': True, 'action': 'fix_tooling_only', 'p_action': 0.67}
- {'name': 'T3 20 ms host word inside padded start', 'label_blocker': True, 'p_blocker': 0.53, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.51}
- {'name': 'T5 host fragment at clip start', 'label_blocker': True, 'p_blocker': 0.62, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.68}
- {'name': "T5 host 'Oh' inside end padding", 'label_blocker': True, 'p_blocker': 0.61, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.7}
- {'name': 'T4 cut inside a word', 'label_blocker': True, 'p_blocker': 0.64, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.46}
- {'name': 'silent audio', 'label_blocker': True, 'p_blocker': 0.78, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.86}
- {'name': 'loud but within spec', 'label_blocker': False, 'p_blocker': 0.25, 'correct': True, 'action': 'ship', 'p_action': 0.8}
- {'name': 'decode error', 'label_blocker': True, 'p_blocker': 0.66, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.76}
- {'name': 'landscape output', 'label_blocker': True, 'p_blocker': 0.81, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.79}
- {'name': 'too long', 'label_blocker': True, 'p_blocker': 0.78, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.91}
- {'name': 'SRT not monotonic', 'label_blocker': True, 'p_blocker': 0.7, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.67}
- {'name': 'black frames at start', 'label_blocker': True, 'p_blocker': 0.34, 'correct': False, 'action': 'ship', 'p_action': 0.64}
- {'name': 'harmless ffmpeg deprecation warning', 'label_blocker': False, 'p_blocker': 0.25, 'correct': True, 'action': 'ship', 'p_action': 0.62}
- {'name': 'T2 subtitles filter missing (before render)', 'label_blocker': True, 'p_blocker': 0.75, 'correct': True, 'action': 'fix_and_rerender', 'p_action': 0.84}
