"""Generate original, short UI cues. No samples from Apple or other products."""
from pathlib import Path
import math
import struct
import wave

ROOT = Path(__file__).resolve().parents[1] / 'assets/sounds'
CUES = {
    'sent': (.16, [(0, .16, 430, 870, .32)]),
    'reply': (.32, [(0, .20, 660, 660, .30), (.09, .22, 880, 880, .23)]),
    'created': (.38, [(0, .18, 523, 523, .26), (.08, .19, 659, 659, .25), (.16, .20, 784, 784, .22)]),
    'listening': (.18, [(0, .17, 780, 780, .24)]),
    'ended': (.28, [(0, .13, 520, 520, .24), (.13, .14, 390, 390, .22)]),
    'saved': (.22, [(0, .20, 740, 990, .24)]),
    'error': (.20, [(0, .18, 260, 220, .20)]),
}

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    rate = 24000
    for name, (duration, notes) in CUES.items():
        samples = []
        for i in range(round(duration * rate)):
            t = i / rate
            value = 0.0
            for start, length, f0, f1, gain in notes:
                x = t - start
                if 0 <= x < length:
                    envelope = min(1, x / .012) * (1 - x / length) ** 2
                    phase = 2 * math.pi * (f0 * x + (f1 - f0) * x*x / (2*length))
                    value += gain * envelope * math.sin(phase)
            samples.append(round(max(-.8, min(.8, value)) * 32767))
        with wave.open(str(ROOT / f'chatai_{name}.wav'), 'wb') as out:
            out.setparams((1, 2, rate, len(samples), 'NONE', 'not compressed'))
            out.writeframes(struct.pack(f'<{len(samples)}h', *samples))

if __name__ == '__main__':
    main()
