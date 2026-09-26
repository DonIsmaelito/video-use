# M4 delivery readiness + intentional hold (collection scenes)

Readiness: 144 instances (24 real exports + 5 perturbations each). Accuracy by kind: {'original': '7/24', 'technical_failure': '24/24', 'audio_present': '24/24', 'flat_black': '24/24', 'wrong_fps': '24/24', 'duration_out_of_range': '24/24'}; overall 0.882
Intentional hold: 10/12 = 0.833 on 12 near-identical ranges from the 8 scenes with beat tables
Jev latency ms: {'n': 156, 'median': 131.38, 'mean': 146.03, 'p90': 167.15, 'min': 91.55, 'max': 499.55}

## Hold rows

- {'scene': '01-pressure-type', 'range': [8.0333, 10.0], 'label_intentional': True, 'p_intentional': 0.84, 'correct': True}
- {'scene': '03-slice-clock', 'range': [0.0333, 1.3333], 'label_intentional': False, 'p_intentional': 0.18, 'correct': True}
- {'scene': '03-slice-clock', 'range': [4.2333, 5.0333], 'label_intentional': True, 'p_intentional': 0.75, 'correct': True}
- {'scene': '03-slice-clock', 'range': [5.8333, 6.7], 'label_intentional': True, 'p_intentional': 0.74, 'correct': True}
- {'scene': '04-ink-relay', 'range': [5.2667, 6.9667], 'label_intentional': True, 'p_intentional': 0.85, 'correct': True}
- {'scene': '04-ink-relay', 'range': [9.2333, 10.0], 'label_intentional': True, 'p_intentional': 0.82, 'correct': True}
- {'scene': '05-elastic-grid', 'range': [3.0333, 4.2333], 'label_intentional': True, 'p_intentional': 0.85, 'correct': True}
- {'scene': '05-elastic-grid', 'range': [6.9333, 8.3333], 'label_intentional': False, 'p_intentional': 0.18, 'correct': True}
- {'scene': '05-elastic-grid', 'range': [8.3667, 10.0], 'label_intentional': False, 'p_intentional': 0.42, 'correct': True}
- {'scene': '06-folded-arrows', 'range': [4.3333, 6.3333], 'label_intentional': True, 'p_intentional': 0.85, 'correct': True}
- {'scene': '06-folded-arrows', 'range': [8.5333, 10.0], 'label_intentional': False, 'p_intentional': 0.51, 'correct': False}
- {'scene': '08-orbit-score', 'range': [8.3667, 10.0], 'label_intentional': False, 'p_intentional': 0.51, 'correct': False}
