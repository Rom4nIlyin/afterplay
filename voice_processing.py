"""Local, streaming speech cleanup. No network, subprocess or shared DSP state."""
from fractions import Fraction
import hashlib
import math
from pathlib import Path

RATE = 48000
TIME_BASE = Fraction(1, RATE)
MODEL = Path(__file__).resolve().parent / 'models/speech.rnnn'
MODEL_SHA256 = '70bb6685eb0c2a1d18e2918dca3fbfbd39317010b1802eb1b6ea73a92f3fdec0'
# RNNoise's overlap/add window delays the signal by one 10 ms frame.
DELAY = 480


def pull(graph):
    import av
    while True:
        try:
            yield graph.pull()
        except (av.error.BlockingIOError, av.error.EOFError):
            return


class VoiceProcessor:
    """48 kHz stereo PCM in/out; center voice, suppress noise, level and limit."""
    def __init__(self, gain=100, model=MODEL):
        import av
        model = Path(model)
        if not model.is_file() or hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256:
            raise RuntimeError('Модель очистки голоса отсутствует или повреждена. Переустановите обновление AFTERPLAY.')
        self.frames = 0
        self.level = 1.
        self.energy = .01
        self.gain = gain / 100
        self.finished = False
        self.clean = av.filter.Graph()
        self.clean.threads = 1
        nodes = [self.clean.add('abuffer', sample_rate=str(RATE), sample_fmt='flt',
                                channel_layout='stereo', time_base='1/48000'),
                 self.clean.add('pan', 'mono|c0=0.5*c0+0.5*c1'),
                 self.clean.add('highpass', frequency='100', poles='2'),
                 # Pass options separately: Windows drive letters and spaces are literal.
                 self.clean.add('arnndn', model=str(model), mix='1'),
                 self.clean.add('aformat', sample_fmts='flt', channel_layouts='mono'),
                 self.clean.add('abuffersink')]
        self._link(self.clean, nodes)
        self.output = av.filter.Graph()
        self.output.threads = 1
        nodes = [self.output.add('abuffer', sample_rate=str(RATE), sample_fmt='flt',
                                 channel_layout='mono', time_base='1/48000'),
                 self.output.add('acompressor', threshold='0.04', ratio='3', attack='5',
                                 release='180', makeup='2', knee='2.8', detection='rms'),
                 self.output.add('alimiter', limit='0.89', attack='5', release='80', level='0', latency='1'),
                 self.output.add('aformat', sample_fmts='flt', channel_layouts='stereo'),
                 self.output.add('abuffersink')]
        self._link(self.output, nodes)

    @staticmethod
    def _link(graph, nodes):
        for left, right in zip(nodes, nodes[1:]):
            left.link_to(right)
        graph.configure()

    def _level(self, frame):
        import numpy as np
        samples = frame.to_ndarray()
        energy = float(np.mean(samples * samples))
        seconds = frame.samples / RATE
        # Freeze gain in pauses so fans and keyboard noise are never amplified
        # by an AGC searching for speech. RNNoise runs before this measurement.
        if energy > .0001:
            weight = 1 - math.exp(-seconds / .15)
            self.energy += weight * (energy - self.energy)
            target = min(4., max(.25, .1 / math.sqrt(self.energy)))
        else:
            target = self.level
        tau = .04 if target < self.level else 1.2
        envelope = target + (self.level - target) * np.exp(-np.arange(1, frame.samples + 1) / (RATE * tau))
        self.level = float(envelope[-1])
        samples = (samples * envelope).astype('float32')
        import av
        result = av.AudioFrame.from_ndarray(samples, format='flt', layout='mono')
        result.sample_rate = RATE
        result.pts = frame.pts
        result.time_base = TIME_BASE
        return result

    def _drain(self):
        for frame in pull(self.clean):
            self.output.push(self._level(frame))
        return self._result()

    def _result(self):
        import av
        import numpy as np
        result = []
        for frame in pull(self.output):
            start = round(frame.pts * frame.time_base * RATE) - DELAY
            left, right = max(0, -start), min(frame.samples, self.frames - start)
            if right <= left:
                continue
            samples = frame.to_ndarray()[:, left * 2:right * 2]
            # Manual volume is last: AGC must not undo 0% / reduced volume.
            samples = np.ascontiguousarray(samples * self.gain, dtype='float32')
            block = av.AudioFrame.from_ndarray(samples, format='flt', layout='stereo')
            block.sample_rate = RATE
            block.pts = start + left
            block.time_base = TIME_BASE
            result.append(block)
        return result

    def process(self, frame):
        if self.finished:
            raise RuntimeError('Voice processor is closed')
        frame.pts = self.frames
        frame.time_base = TIME_BASE
        self.frames += frame.samples
        self.clean.push(frame)
        return self._drain()

    def flush(self):
        if self.finished:
            return []
        self.finished = True
        import av
        import numpy as np
        # Flush the RNNoise overlap without extending the captured duration.
        # Include the limiter's lookahead, and finish on a whole RNNoise frame.
        # EOF padding in native filters must stay outside the captured range.
        padding = 2 * DELAY + (-self.frames) % DELAY
        pad = av.AudioFrame.from_ndarray(np.zeros((1, padding * 2), dtype='float32'), format='flt', layout='stereo')
        pad.sample_rate = RATE
        pad.pts = self.frames
        pad.time_base = TIME_BASE
        self.clean.push(pad)
        self.clean.push(None)
        result = self._drain()
        self.output.push(None)
        return result + self._result()
