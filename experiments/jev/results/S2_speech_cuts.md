# S2 internal cuts with Jev vs the LLM's EDL ranges

## T1_job_vs_task: window [5312.3, 5388.9], LLM wrote 11 ranges (10 removed regions)
- gaps >= 0.4 s: {'n': 20, 'tp': 0, 'fp': 0, 'fn': 10, 'precision': 0.0, 'recall': 0.0}
- phrases: {'n': 21, 'tp': 0, 'fp': 0, 'fn': 1, 'precision': 0.0, 'recall': 0.0}
- 41 Jev calls in 1.3 s; latency {'n': 41, 'median': 146, 'mean': 232.41, 'p90': 599, 'min': 95, 'max': 690}

  - phrase [5311.76-5315.18] p=0.48 jev_cut=False llm_cut=False 'If we s- if we scare this country into thinking that AI'
  - gap    [5315.18-5315.78] p=0.49 jev_cut=False llm_cut=False '0.6s'
  - phrase [5315.78-5315.90] p=0.24 jev_cut=False llm_cut=False 'is'
  - gap    [5315.90-5317.68] p=0.48 jev_cut=False llm_cut=True '1.78s'
  - phrase [5317.68-5318.90] p=0.31 jev_cut=False llm_cut=False 'somehow a nuclear bomb'
  - gap    [5318.90-5320.24] p=0.36 jev_cut=False llm_cut=True '1.34s'
  - phrase [5320.24-5321.66] p=0.27 jev_cut=False llm_cut=False 'so that everybody hates AI'
  - gap    [5321.66-5322.98] p=0.59 jev_cut=False llm_cut=True '1.32s'
  - phrase [5322.98-5324.12] p=0.24 jev_cut=False llm_cut=False "and everybody's afraid of AI,"
  - gap    [5324.12-5325.60] p=0.34 jev_cut=False llm_cut=True '1.48s'
  - phrase [5325.60-5327.06] p=0.21 jev_cut=False llm_cut=False "I don't know how you're helping"
  - gap    [5327.06-5328.10] p=0.39 jev_cut=False llm_cut=True '1.04s'
  - phrase [5328.10-5330.22] p=0.3 jev_cut=False llm_cut=False "the United States. You're doing a disservice."
  - gap    [5330.22-5331.24] p=0.32 jev_cut=False llm_cut=True '1.02s'
  - phrase [5331.24-5336.02] p=0.14 jev_cut=False llm_cut=False "If we scare everybody out of doing software engineering jobs because it's gonna "
  - gap    [5336.02-5336.66] p=0.4 jev_cut=False llm_cut=False '0.64s'
  - phrase [5336.66-5338.62] p=0.12 jev_cut=False llm_cut=False "and we don't have any software engineers as a result of that,"
  - gap    [5338.62-5339.20] p=0.5 jev_cut=False llm_cut=False '0.58s'
  - phrase [5339.20-5340.84] p=0.17 jev_cut=False llm_cut=False "we're doing a disservice to the United States."
  - gap    [5340.84-5341.70] p=0.32 jev_cut=False llm_cut=False '0.86s'
  - phrase [5341.70-5347.16] p=0.13 jev_cut=False llm_cut=False 'If we scare everybody out of radiology, so nobody wants to be a radiologist beca'
  - gap    [5347.16-5347.82] p=0.44 jev_cut=False llm_cut=False '0.66s'
  - phrase [5347.82-5357.00] p=0.15 jev_cut=False llm_cut=False 'and no AI is gonna do a worse job than a radiologist, and we, we misunderstand t'
  - gap    [5357.00-5357.50] p=0.58 jev_cut=False llm_cut=False '0.5s'
  - phrase [5357.50-5358.90] p=0.25 jev_cut=False llm_cut=False 'task to read a scan.'
  - gap    [5358.90-5359.40] p=0.28 jev_cut=False llm_cut=False '0.5s'
  - phrase [5359.40-5361.38] p=0.17 jev_cut=False llm_cut=False 'If we misunderstand that so profoundly'
  - gap    [5361.38-5362.00] p=0.4 jev_cut=False llm_cut=False '0.62s'
  - phrase [5362.00-5365.40] p=0.17 jev_cut=False llm_cut=False 'and we scare everybody out of d-- going to radiology school,'
  - gap    [5365.40-5365.90] p=0.43 jev_cut=False llm_cut=False '0.5s'
  - phrase [5365.90-5369.34] p=0.2 jev_cut=False llm_cut=False "we're not gonna have enough radiologists and good enough healthcare. And so I..."
  - gap    [5369.34-5371.86] p=0.4 jev_cut=False llm_cut=True '2.52s'
  - phrase [5371.86-5372.94] p=0.26 jev_cut=False llm_cut=True "I'm making the case"
  - gap    [5372.94-5374.56] p=0.58 jev_cut=False llm_cut=True '1.62s'
  - phrase [5374.56-5374.70] p=0.51 jev_cut=False llm_cut=False 'that'
  - gap    [5374.70-5375.34] p=0.38 jev_cut=False llm_cut=False '0.64s'
  - phrase [5375.34-5376.66] p=0.53 jev_cut=False llm_cut=False 'when you make these--'
  - gap    [5376.66-5377.64] p=0.42 jev_cut=False llm_cut=True '0.98s'
  - phrase [5377.64-5382.64] p=0.17 jev_cut=False llm_cut=False 'make a premise that is so extreme, everything goes from zero or infinity.'
  - gap    [5382.64-5384.64] p=0.39 jev_cut=False llm_cut=True '2.0s'
  - phrase [5384.64-5388.82] p=0.15 jev_cut=False llm_cut=False "We end up scaring people in a way that's just not true. Life is not like that."
## T4_plumbers: window [782.9, 834.2], LLM wrote 10 ranges (9 removed regions)
- gaps >= 0.4 s: {'n': 14, 'tp': 1, 'fp': 0, 'fn': 11, 'precision': 1.0, 'recall': 0.08}
- phrases: {'n': 23, 'tp': 6, 'fp': 3, 'fn': 9, 'precision': 0.67, 'recall': 0.4}
- 37 Jev calls in 0.6 s; latency {'n': 37, 'median': 123, 'mean': 120.43, 'p90': 139, 'min': 95, 'max': 167}

  - phrase [780.66-782.70] p=0.54 jev_cut=False llm_cut=False 'scaling up CoWoS versus scaling up-'
  - phrase [782.90-784.16] p=0.21 jev_cut=False llm_cut=False 'I went to the hardest one, by the way.'
  - phrase [784.54-784.90] p=0.28 jev_cut=False llm_cut=False 'Which is?'
  - gap    [784.90-785.68] p=0.26 jev_cut=False llm_cut=False '0.78s'
  - phrase [785.68-786.04] p=0.39 jev_cut=False llm_cut=False 'Plumbers.'
  - phrase [786.04-787.28] p=0.88 jev_cut=True llm_cut=False '([laughs])'
  - phrase [787.32-787.58] p=0.63 jev_cut=True llm_cut=False 'Yeah.'
  - phrase [787.62-788.04] p=0.36 jev_cut=False llm_cut=False "That's true."
  - phrase [788.28-790.20] p=0.12 jev_cut=False llm_cut=True 'Yeah, yeah. I actually went to the hardest one.'
  - phrase [790.26-790.52] p=0.75 jev_cut=True llm_cut=True 'Yeah.'
  - phrase [790.56-792.94] p=0.31 jev_cut=False llm_cut=True 'Yeah, plumbers and electricians. And the reason for that is because,'
  - gap    [792.94-793.56] p=0.34 jev_cut=False llm_cut=True '0.62s'
  - phrase [793.56-797.24] p=0.37 jev_cut=False llm_cut=True 'because-- and this is one of the concerns that I have about, about the do- the d'
  - gap    [797.24-798.04] p=0.32 jev_cut=False llm_cut=True '0.8s'
  - phrase [798.04-798.20] p=0.94 jev_cut=True llm_cut=True 'um,'
  - gap    [798.20-799.16] p=0.47 jev_cut=False llm_cut=True '0.96s'
  - phrase [799.16-802.36] p=0.35 jev_cut=False llm_cut=True 'describing the end of, end of work and killing of jobs. And'
  - gap    [802.36-803.12] p=0.26 jev_cut=False llm_cut=True '0.76s'
  - phrase [803.12-804.90] p=0.67 jev_cut=True llm_cut=True 'y- you know, one of the things that, that,'
  - gap    [804.90-805.60] p=0.23 jev_cut=False llm_cut=True '0.7s'
  - phrase [805.60-808.44] p=0.18 jev_cut=False llm_cut=True 'that, um, if we discourage people from being software engineers,'
  - gap    [808.44-809.64] p=0.65 jev_cut=True llm_cut=True '1.2s'
  - phrase [809.64-811.28] p=0.15 jev_cut=False llm_cut=True "we're gonna run out of software engineers."
  - gap    [811.28-811.96] p=0.26 jev_cut=False llm_cut=True '0.68s'
  - phrase [811.96-814.48] p=0.53 jev_cut=False llm_cut=True 'And, and, uh, the same prediction ten years ago,'
  - gap    [814.48-815.32] p=0.31 jev_cut=False llm_cut=True '0.84s'
  - phrase [815.32-817.40] p=0.69 jev_cut=True llm_cut=True 'some of the, some of the doomers were, were, uh,'
  - gap    [817.40-818.08] p=0.31 jev_cut=False llm_cut=True '0.68s'
  - phrase [818.08-818.70] p=0.78 jev_cut=True llm_cut=True 'uh, saying that--'
  - gap    [818.70-819.32] p=0.25 jev_cut=False llm_cut=True '0.62s'
  - phrase [819.32-822.26] p=0.23 jev_cut=False llm_cut=True 'were, were telling people, "D- whatever you do, don\'t be a radiologist."'
  - gap    [822.26-822.98] p=0.27 jev_cut=False llm_cut=True '0.72s'
  - phrase [822.98-826.02] p=0.67 jev_cut=True llm_cut=True 'And you might hear some of those, uh, some of those videos are still on the web.'
  - gap    [826.02-826.52] p=0.15 jev_cut=False llm_cut=True '0.5s'
  - phrase [826.52-833.62] p=0.2 jev_cut=False llm_cut=True "You know, radiology is, is gonna be the first career to go. Nobody's-- The world"
  - gap    [833.62-834.20] p=0.19 jev_cut=False llm_cut=False '0.58s'
  - phrase [834.20-836.42] p=0.85 jev_cut=True llm_cut=False 'Oh, but okay, so going back to this point about, well,'


# Re-scored with majority-overlap labels (a phrase or gap counts as LLM-cut only when more than half of it lies in a removed region)

## T1_job_vs_task
- gaps: LLM removed 10/20; Jev p>=0.6: tp=0 fp=0 fn=10 P=0.00 R=0.00; Jev p>=0.45: tp=3 fp=3 fn=7 P=0.50 R=0.30; rule gap>=0.9s: tp=10 fp=0 fn=0 P=1.00 R=1.00
  mean Jev p on LLM-removed gaps 0.43 vs kept gaps 0.42; gap lengths removed ['1.78s', '1.34s', '1.32s', '1.48s', '1.04s', '1.02s', '2.52s', '1.62s', '0.98s', '2.0s'] kept ['0.6s', '0.64s', '0.58s', '0.86s', '0.66s', '0.5s', '0.5s', '0.62s', '0.5s', '0.64s']
- phrases: LLM removed 0/21; Jev p>=0.6: tp=0 fp=0 fn=0 P=0.00 R=0.00; Jev p>=0.5: tp=0 fp=2 fn=0 P=0.00 R=0.00
  - p=0.53 llm_removed=False 'when you make these--'
  - p=0.51 llm_removed=False 'that'
  - p=0.48 llm_removed=False 'If we s- if we scare this country into thinking that AI'
  - p=0.31 llm_removed=False 'somehow a nuclear bomb'
  - p=0.3 llm_removed=False "the United States. You're doing a disservice."
  - p=0.27 llm_removed=False 'so that everybody hates AI'
  - p=0.26 llm_removed=False "I'm making the case"
  - p=0.25 llm_removed=False 'task to read a scan.'
## T4_plumbers
- gaps: LLM removed 12/14; Jev p>=0.6: tp=1 fp=0 fn=11 P=1.00 R=0.08; Jev p>=0.45: tp=2 fp=0 fn=10 P=1.00 R=0.17; rule gap>=0.9s: tp=2 fp=0 fn=10 P=1.00 R=0.17
  mean Jev p on LLM-removed gaps 0.32 vs kept gaps 0.23; gap lengths removed ['0.62s', '0.8s', '0.96s', '0.76s', '0.7s', '1.2s', '0.68s', '0.84s', '0.68s', '0.62s', '0.72s', '0.5s'] kept ['0.78s', '0.58s']
- phrases: LLM removed 8/23; Jev p>=0.6: tp=6 fp=3 fn=2 P=0.67 R=0.75; Jev p>=0.5: tp=6 fp=5 fn=2 P=0.55 R=0.75
  - p=0.94 llm_removed=True 'um,'
  - p=0.88 llm_removed=False '([laughs])'
  - p=0.85 llm_removed=False 'Oh, but okay, so going back to this point about, well,'
  - p=0.78 llm_removed=True 'uh, saying that--'
  - p=0.75 llm_removed=True 'Yeah.'
  - p=0.69 llm_removed=True 'some of the, some of the doomers were, were, uh,'
  - p=0.67 llm_removed=True 'y- you know, one of the things that, that,'
  - p=0.67 llm_removed=True 'And you might hear some of those, uh, some of those videos are still o'
