#!/usr/bin/env python3
"""Original score authored for Signal Garden; this is an example asset, not a runtime preset."""
from pathlib import Path
import argparse
import wave

import numpy as np


def compose(destination: Path, duration: float = 16, sample_rate: int = 48000):
    rng = np.random.default_rng(71039)
    mix = np.zeros((round(duration * sample_rate), 2), dtype=np.float64)

    def add(sound, start, gain=1, pan=0):
        first = round(start * sample_rate)
        lo, hi = max(0, first), min(len(mix), first + len(sound))
        if hi <= lo:
            return
        stereo = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)])
        mix[lo:hi] += sound[lo - first:hi - first, None] * stereo * gain

    def clock(seconds):
        return np.arange(round(seconds * sample_rate)) / sample_rate

    def section(time):
        if time < 2.2:
            return .35 + .65 * time / 2.2
        if 6.6 < time < 8.5:
            return .08
        if time > 13.8:
            return max(0, (15.9 - time) / 2.1)
        return .7 + .3 * np.clip((time - 8.5) / 3, 0, 1)

    beat = 60 / 107
    # Bass speaks in asymmetric phrases; the scene receives none of this score data.
    roots = [73.4162, 65.4064, 87.3071, 97.9989]
    for index in range(29):
        at = .18 + index * beat
        strength = section(at)
        t = clock(.52)
        pitch = 48 + 85 * np.exp(-t * 28)
        phase = np.cumsum(pitch) * 2 * np.pi / sample_rate
        kick = np.sin(phase) * np.exp(-t * 10) + .08 * rng.normal(size=t.size) * np.exp(-t * 120)
        if index % 4 in (0, 2, 3):
            add(kick, at, .40 * strength)
        if index % 2 == 0:
            t = clock(.95)
            frequency = roots[(index // 8) % len(roots)]
            sub = (np.sin(2 * np.pi * frequency * t) + .22 * np.sin(2 * np.pi * frequency * 2 * t)) * (1 - np.exp(-t * 70)) * np.exp(-t * 4.8)
            add(sub, at + .035, .31 * strength, -.08)

    # Rounded struck tones and their quiet echoes provide melodic contour.
    notes = [293.665, 440, 523.251, 349.228, 587.33, 440, 391.995, 659.255]
    for index in range(48):
        at = .38 + index * beat / 2
        if at > 15.3 or (index % 8 in (3, 6)):
            continue
        t = clock(1.7)
        frequency = notes[(index * 3 + index // 8) % len(notes)]
        bell = (np.sin(2 * np.pi * frequency * t) * np.exp(-t * 3.8) + .26 * np.sin(2 * np.pi * frequency * 2.003 * t) * np.exp(-t * 8) + .08 * np.sin(2 * np.pi * frequency * 4.11 * t) * np.exp(-t * 14)) * (1 - np.exp(-t * 230))
        gain = .115 * (.3 + .7 * section(at))
        pan = (-1 if index % 2 else 1) * .47
        add(bell, at, gain, pan)
        add(bell, at + beat * .75, gain * .28, -pan)

    # Bright taps: high-pass noise has a distinct spectrum from the bass and bells.
    for index in range(112):
        at = .18 + index * beat / 4
        if at > 15.6 or (at < 8.5 and index % 4 not in (0, 3)):
            continue
        t = clock(.105)
        noise = rng.normal(size=t.size)
        high = np.r_[0, np.diff(noise)]
        tap = (high * .30 + np.sin(2 * np.pi * 6900 * t) * .15) * np.exp(-t * 75)
        add(tap, at, (.042 + .028 * (index % 4 == 3)) * section(at), .6 * np.sin(index * 2.1))

    # Soft harmonic air survives the central pause, letting motion visibly settle.
    t = clock(duration)
    air = sum(np.sin(2 * np.pi * f * t + .25 * np.sin(t * .8 + i)) / (i + 1) for i, f in enumerate([146.832, 220, 261.626, 329.628]))
    air *= .032 * np.minimum(t / 2, 1) * np.clip((duration - t) / 2.5, 0, 1)
    add(air, 0)
    fade = np.minimum(np.arange(len(mix)) / (sample_rate * .03), 1) * np.minimum(np.arange(len(mix))[::-1] / (sample_rate * .6), 1)
    mix = np.tanh(mix * 1.1)
    mix *= .88 / max(float(np.max(np.abs(mix))), .88)
    mix *= fade[:, None]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes((mix * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=Path(__file__).with_name("soundtrack.wav"))
    compose(parser.parse_args().output)
