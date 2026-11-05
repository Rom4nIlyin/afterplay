"""Continuous sample clock for callback devices with jittery WASAPI timestamps."""
import math


class SampleClock:
    def __init__(self,rate):
        self.rate=rate;self.epoch=None;self.frames=0;self.portaudio_offset=None

    def stamp(self,frames,info,now,overflow=False):
        adc=info.get('input_buffer_adc_time',0)
        current=info.get('current_time',0)
        if math.isfinite(adc) and math.isfinite(current) and adc>0 and current>0 and abs(adc-current)<10:
            if self.portaudio_offset is None:self.portaudio_offset=now-current
            timestamp=adc+self.portaudio_offset
        elif math.isfinite(adc) and adc>0 and abs(adc-now)<30:timestamp=adc
        else:timestamp=now-frames/self.rate
        expected=self.epoch+self.frames/self.rate if self.epoch is not None else timestamp
        # Preserve actual device pauses/overruns. Ordinary callback jitter and
        # small ADC clock corrections must never splice individual PCM blocks.
        gap=self.epoch is not None and (timestamp-expected>.1 or (overflow and timestamp>expected+1/self.rate))
        if self.epoch is None or gap:
            self.epoch=timestamp;self.frames=0
        timestamp=self.epoch+self.frames/self.rate
        self.frames+=frames
        return timestamp,gap
