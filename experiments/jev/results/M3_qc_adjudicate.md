# M3 layout-QC adjudication (motion design)

Instances: 9 failing layout-QC commands, 8 with a label derived from the LLM's next action.
- agreement: 2/8 = 0.25
- Jev latency ms: {'n': 9, 'median': 471.53, 'mean': 362.37, 'p90': 491.44, 'min': 94.66, 'max': 512.45}
- LLM think time after the QC failure (s): {'n': 5, 'median': 9.7, 'mean': 10.46, 'p90': 12.9, 'min': 4.5, 'max': 16.8}

## Confusion (rows = label, cols = Jev)

- measurement_artifact_adjust_check: {'measurement_artifact_adjust_check': 1, 'real_collision_edit_source': 1, 'tooling_error_not_a_design_verdict': 1}
- real_collision_edit_source: {'real_collision_edit_source': 1, 'tooling_error_not_a_design_verdict': 1}
- tooling_error_not_a_design_verdict: {'real_collision_edit_source': 3}

## Rows

- lane-1-631d46cb0c32 label=None jev=real_collision_edit_source p=0.8 viol=["elements 'brand' and 'workTitle' overlap at 13.600s"] next="/bin/bash -lc 'tail -c 4500 edit/verify/engine-check.log && tail -c 1800 edit/verify/render.log'"
- lane-1-32a5502e1c80 label=measurement_artifact_adjust_check jev=measurement_artifact_adjust_check p=0.7 viol=["elements '#disk' and '#ray1' overlap at 7.400s", "elements '#disk' and '#ray4' overlap at 7.400s"] next='/bin/bash -lc "python - <<\'PY\'\np=\'edit/animations/sunshine/measure.cjs\';s=open(p).read().replace(\\"a'
- lane-1-9da35ab24ebe label=measurement_artifact_adjust_check jev=real_collision_edit_source p=0.75 viol=["elements 'paperBody' and 'spark' overlap at 10.700s"] next='/bin/bash -lc "python - <<\'PY\'\nimport json\nj=json.load(open(\'edit/layout_manifest.json\'));print(j[\'f'
- lane-1-0c961eb8934b label=real_collision_edit_source jev=real_collision_edit_source p=0.8 viol=["elements 'seed' and 'roots' overlap at 2.500s"] next='/bin/bash -lc "cat > edit/publish.py <<\'PY\'\nimport subprocess,json,os,sys\nfrom pathlib import Path\ns'
- lane-1-0c961eb8934b label=tooling_error_not_a_design_verdict jev=real_collision_edit_source p=0.84 viol=["elements 'tree' and 'cloud' overlap at 18.000s"] next="/bin/bash -lc 'mv edit/animations/growth/opening.html edit/verify/opening.html.txt\nLD_LIBRARY_PATH=/"
- lane-1-6eca5ba640fc label=measurement_artifact_adjust_check jev=tooling_error_not_a_design_verdict p=0.48 viol=None next='/bin/bash -lc "sed -i \'s/scale:1.12/scale:1.04/\' edit/animations/gpu/build.py\ncd edit/animations/gpu'
- lane-1-6eca5ba640fc label=real_collision_edit_source jev=tooling_error_not_a_design_verdict p=0.44 viol=None next='/bin/bash -lc "python - <<\'PY\'\nimport json,os\nfrom pathlib import Path\np=Path(\'edit/live\');(p/\'statu'
- lane-1-6eca5ba640fc label=tooling_error_not_a_design_verdict jev=real_collision_edit_source p=0.58 viol=["elements 'o0-11' and 'o1-12' overlap at 25.467s"] next="/bin/bash -lc 'ffmpeg -v error -y -i edit/live/opening-draft.mp4 -vf scale=1280:720 -c:v libx264 -pi"
- lane-1-254a9b2a86f2 label=tooling_error_not_a_design_verdict jev=real_collision_edit_source p=0.75 viol=["elements 'text17' and 'p3' overlap at 14.033s"] next="/bin/bash -lc 'LD_LIBRARY_PATH=/runs/lane-1-254a9b2a86f2/input/edit/runtime/usr/lib/x86_64-linux-gnu"
