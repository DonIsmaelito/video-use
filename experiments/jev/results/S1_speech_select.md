# S1 moment selection with Jev over the whole interview

Transcript: iltb_jensen.json; 2035 phrases, 94 answer-units, guest speaker speaker_1.
- Jev calls: 94 (three questions each) in 2.1 s wall with 8 workers; latency ms {'n': 94, 'median': 129.7, 'mean': 178.54, 'p90': 198.07, 'min': 95.07, 'max': 686.77}
- Time-base offset vs the benchmark transcript: -0.0 s from anchors [('valuations of a bunch of software companies', 0.6, 0.6, 0.0), ('something has to transform electrons to tokens', 32.14, 32.119, -0.0), ('I went to the hardest one, by the way', 782.85, 782.9, 0.0)]
- Recall of the six LLM-picked moments in Jev's top 10: 0.16666666666666666, top 20: 0.5; ranks {'electrons_to_tokens': 62, 'clip_238': 34, 'plumbers_radiologists': 8, 'cpu_cadillac_vs_gpu_f1': 12, 'ai_job_vs_task': 14, 'nvidia_without_ai': 57}
- LLM baseline for the same step (transcript reading + selection + filmstrip drill, model minutes per run): {'T1': 4.7, 'T2': 2.8, 'T3': 2.4, 'T4': 4.1, 'T5': 1.9}
- Stage 2 pairwise tournament over the top 10 (1.1 s): final order ['u0136', 'u0128', 'u0061', 'u0095', 'u0053', 'u0042', 'u0013', 'u0132', 'u0014', 'u0097']; target ranks after tournament {'electrons_to_tokens': None, 'clip_238': None, 'plumbers_radiologists': 7, 'cpu_cadillac_vs_gpu_f1': None, 'ai_job_vs_task': None, 'nvidia_without_ai': None}

## Top 15 units by (standalone + hook + payoff)/3

- #1 u0132 [5265.0-5305.4] 40.44s score=0.562 (s=0.3 h=0.67 p=0.72) Q: "It's just, like, hard to imagine that there's a lo" | 'China is the largest contributor to open source software in the world. Fact. Right? China is the largest contr'
- #2 u0061 [3257.1-3301.6] 44.51s score=0.542 (s=0.53 h=0.46 p=0.64) Q: 'Well, why not just do highest bidder?' | "Because it's, it's a bad b-business practice. You, you set your price, you set your price, and then, and then "
- #3 u0097 [4473.9-4491.3] 17.36s score=0.542 (s=0.25 h=0.57 p=0.81) Q: 'A few months ago, Jane Street spent about twenty t' | 'If you think the base model was here and the backdoor model was here, you can kind of linearly interpolate the'
- #4 u0014 [849.7-870.4] 20.76s score=0.536 (s=0.23 h=0.65 p=0.73) Q: 'How do you get to two X as many EUV machines a yea' | "Yeah None of th- none of that's impossible to scale quickly. You just need to-- You, you could do-- All of tha"
- #5 u0053 [2849.5-2914.2] 64.74s score=0.527 (s=0.39 h=0.49 p=0.7) Q: 'Wh-why do you go out of your way to not to pick wi' | "Because it's not our job to, number one. Number two, when Nvidia s-first started, there were sixty graphics co"
- #6 u0136 [5445.1-5494.0] 48.83s score=0.52 (s=0.14 h=0.83 p=0.59) Q: "It's just, like, hard to imagine that there's a lo" | 'literally caused the United States to concede the second-largest market in the world for no good reason at all'
- #7 u0042 [2319.4-2330.8] 11.38s score=0.517 (s=0.26 h=0.59 p=0.7) Q: "... 'cause they're paying you seventy percent marg" | "No, no, no. Don't forget, uh, even an ASIC's margin's really quite high. Nvidia's margin's six- s-seventy perc"
- #8 u0013 [782.9-833.6] 50.72s score=0.513 (s=0.16 h=0.64 p=0.74) Q: 'scaling up CoWoS versus scaling up-' | 'I went to the hardest one, by the way. Plumbers. Yeah. Yeah, yeah. I actually went to the hardest one. Yeah, p'
- #9 u0095 [4418.2-4450.3] 32.12s score=0.496 (s=0.24 h=0.86 p=0.39) Q: 'But if you have it earlier, we can prepare for it.' | 'Uh, listen, why are you, why are you causing one layer of the AI industry to lose an entire market so that you'
- #10 u0128 [5205.7-5244.3] 38.58s score=0.49 (s=0.25 h=0.66 p=0.56) Q: "And so w-we-- l-let's leave the benefit aside for " | 'I will also tell you the potential cost is we allow one of the most important layers of the AI stack, the chip'
- #11 u0086 [4304.4-4317.0] 12.6s score=0.482 (s=0.22 h=0.57 p=0.66) Q: 'But they, American labs do that.' | "And they don't run better. Th-Nvidia's success is perfect evidence. The fact that AI models are created on our"
- #12 u0030 [1863.8-1942.8] 78.98s score=0.471 (s=0.17 h=0.47 p=0.77) Q: 'build instead of the CUDA moat?' | "Everybody drives it pretty well, you know. It's got cruise control, you know, and everything is easy. But in a"
- #13 u0140 [5686.0-5705.3] 19.3s score=0.47 (s=0.24 h=0.58 p=0.59) Q: 'than to run their models on your one point six nan' | 'is there 10x difference between five nanometer and seven nanometer? The answer is no. Architecture matters. Ne'
- #14 u0134 [5371.9-5388.8] 16.96s score=0.463 (s=0.26 h=0.41 p=0.72) Q: "It's just, like, hard to imagine that there's a lo" | "I'm making the case that when you make these-- make a premise that is so extreme, everything goes from zero or"
- #15 u0122 [5013.2-5057.0] 43.86s score=0.461 (s=0.13 h=0.71 p=0.54) Q: 'And they, we have quotes from the founders of Chin' | "Because our chips are better. On balance, our chips are better. There's just no question about it. In the abse"

## LLM-picked windows

- electrons_to_tokens: window [30.4, 100.2] best Jev rank 62 (1 units overlap); top hit {'id': 'u0000', 'start': 32.119, 'end': 109.24, 'score': 0.267, 'text': "Well, in the end, something has to transform electrons to tokens. That transformation, um, there's no-- the transformation of electrons to t"}
- clip_238: window [238.1, 259.2] best Jev rank 34 (1 units overlap); top hit {'id': 'u0003', 'start': 217.1, 'end': 268.16, 'score': 0.359, 'text': 'all these tools are gonna skyrocket. It is very likely the number of instances of Synopsys Design Compiler is gonna skyrocket, and the numbe'}
- plumbers_radiologists: window [780.6, 834.2] best Jev rank 8 (1 units overlap); top hit {'id': 'u0013', 'start': 782.9, 'end': 833.62, 'score': 0.513, 'text': 'I went to the hardest one, by the way. Plumbers. Yeah. Yeah, yeah. I actually went to the hardest one. Yeah, plumbers and electricians. And '}
- cpu_cadillac_vs_gpu_f1: window [1833.8, 1897.6] best Jev rank 12 (2 units overlap); top hit {'id': 'u0030', 'start': 1863.832, 'end': 1942.812, 'score': 0.471, 'text': "Everybody drives it pretty well, you know. It's got cruise control, you know, and everything is easy. But in a lot of ways, NVIDIA's GPUs ar"}
- ai_job_vs_task: window [5312.3, 5388.9] best Jev rank 14 (2 units overlap); top hit {'id': 'u0134', 'start': 5371.862, 'end': 5388.822, 'score': 0.463, 'text': "I'm making the case that when you make these-- make a premise that is so extreme, everything goes from zero or infinity. We end up scaring p"}
- nvidia_without_ai: window [5988.4, 6040.5] best Jev rank 57 (1 units overlap); top hit {'id': 'u0147', 'start': 5988.534, 'end': 6062.274, 'score': 0.274, 'text': "Accelerated computing. Accelerated computing. The, the same thing we've been doing all along. Uh, the, the premise of our company is that Mo"}
