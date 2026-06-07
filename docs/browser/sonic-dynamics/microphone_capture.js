// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Microphone -> ObservedVoice pipeline.
//
// Real-time audio analysis layer that bridges getUserMedia input and
// the inverse sonic projection (sonic_capture.js). Produces voices in
// the same shape as the forward projection emits, with the labels
// (opcode, name) deliberately absent -- those are recovered by the
// inverse using only the modality-observable fields.
//
// The DSP is intentionally pure vanilla (no library deps), matching
// the existing runtime's stance. The heuristics are good enough to
// prove the architecture end-to-end on isolated tones in the
// pentatonic scale used by the forward projection; robust real-world
// audio analysis is out of scope.

// Pentatonic scale shared with sonic_projection.PENTATONIC_HZ. The
// captured pitch is snapped to the nearest entry so the inverse can
// resolve the ontology signature deterministically.
const PENTATONIC_HZ = [
  220.000, 261.626, 293.665, 329.628, 391.995,
  440.000, 523.251, 587.330, 659.255, 783.991,
];

// Time the analyser dwells on the input before flushing observed
// voices to the caller. One bar at 96 BPM == 4s (see
// sonic_projection.build_sonic_manifest).
export const DEFAULT_BAR_SECONDS = 4.0;

// Minimum RMS above which the input is considered "voiced" -- below
// this threshold an onset candidate is ignored as silence/noise.
const ONSET_RMS_THRESHOLD = 0.02;

// Spectral-flux ratio above which a frame is considered an onset.
const ONSET_FLUX_RATIO = 1.6;

function rms(timeData) {
  let sum = 0;
  for (let i = 0; i < timeData.length; i += 1) {
    const v = timeData[i];
    sum += v * v;
  }
  return Math.sqrt(sum / timeData.length);
}

function spectralFlux(prev, current) {
  let flux = 0;
  for (let i = 0; i < current.length; i += 1) {
    const diff = current[i] - (prev ? prev[i] : 0);
    if (diff > 0) flux += diff;
  }
  return flux;
}

export function snapToPentatonic(hz) {
  let bestIdx = 0;
  let bestErr = Infinity;
  for (let i = 0; i < PENTATONIC_HZ.length; i += 1) {
    const err = Math.abs(PENTATONIC_HZ[i] - hz);
    if (err < bestErr) {
      bestErr = err;
      bestIdx = i;
    }
  }
  return PENTATONIC_HZ[bestIdx];
}

export function findFundamental(spectrum, sampleRate, fftSize) {
  // Peak picking on the magnitude spectrum, ignoring sub-audible bins
  // and bins above ~4 kHz where the pentatonic content lives.
  const binHz = sampleRate / fftSize;
  const minBin = Math.max(1, Math.floor(150 / binHz));
  const maxBin = Math.min(spectrum.length - 1, Math.floor(2000 / binHz));
  let peakBin = minBin;
  let peakVal = spectrum[minBin];
  for (let i = minBin + 1; i <= maxBin; i += 1) {
    if (spectrum[i] > peakVal) {
      peakVal = spectrum[i];
      peakBin = i;
    }
  }
  return peakBin * binHz;
}

export function classifyWaveform(spectrum, fundamentalHz, sampleRate, fftSize) {
  // Compare the magnitudes of the first few harmonics against the
  // fundamental. Reference profiles:
  //   sine     -> only fundamental
  //   triangle -> fundamental + odd harmonics, decaying as 1/n^2
  //   square   -> fundamental + odd harmonics, decaying as 1/n
  //   sawtooth -> all harmonics (odd + even), decaying as 1/n
  const binHz = sampleRate / fftSize;
  const harmonics = [];
  for (let n = 1; n <= 6; n += 1) {
    const bin = Math.round((n * fundamentalHz) / binHz);
    harmonics.push(bin < spectrum.length ? spectrum[bin] : 0);
  }
  const f0 = Math.max(1e-6, harmonics[0]);
  const odd = (harmonics[2] + harmonics[4]) / (2 * f0);
  const even = (harmonics[1] + harmonics[3] + harmonics[5]) / (3 * f0);

  if (odd < 0.1 && even < 0.1) return "sine";
  if (even < 0.15 && odd > 0.3) {
    // Distinguish square vs triangle by harmonic decay rate.
    // Square decays as 1/n, triangle as 1/n^2 so triangle's h3/h1
    // ratio is much smaller (~0.11) than square's (~0.33).
    return harmonics[2] / f0 < 0.2 ? "triangle" : "square";
  }
  return "sawtooth";
}

export function classifyEnvelope(amplitudeTrack) {
  // amplitudeTrack: array of per-frame RMS values covering the onset
  // window. Heuristics mirror the forward shape_envelope branches in
  // sonic_runtime.js.
  if (amplitudeTrack.length === 0) return "sustained";
  const peakIdx = amplitudeTrack.indexOf(Math.max(...amplitudeTrack));
  const peak = amplitudeTrack[peakIdx];
  const tail = amplitudeTrack[amplitudeTrack.length - 1];
  const attackFraction = peakIdx / amplitudeTrack.length;
  const decayRatio = tail / Math.max(1e-6, peak);

  // Tremolo: many local maxima alternating with low points.
  let crossings = 0;
  const mid = peak * 0.5;
  for (let i = 1; i < amplitudeTrack.length; i += 1) {
    if (
      (amplitudeTrack[i - 1] < mid && amplitudeTrack[i] >= mid) ||
      (amplitudeTrack[i - 1] >= mid && amplitudeTrack[i] < mid)
    ) {
      crossings += 1;
    }
  }
  if (crossings >= 4) return "tremolo";
  if (attackFraction < 0.1 && decayRatio < 0.2) return "percussive";
  if (attackFraction > 0.25) return "swelling";
  return "sustained";
}

export function buildObservedVoice({
  index,
  fundamentalHz,
  waveform,
  envelope,
  amplitude,
  startOffset,
  channel = 0,
  role = "source",
}) {
  return Object.freeze({
    index,
    role,
    waveform,
    envelope,
    frequency_hz: snapToPentatonic(fundamentalHz),
    amplitude: Math.max(0, Math.min(1, amplitude)),
    start_offset: Math.max(0, Math.min(1, startOffset)),
    channel,
  });
}

export class MicrophoneCapture {
  // Owns a one-shot capture over `barSeconds`. Holds the analyser,
  // accumulates per-frame spectra + amplitudes, then segments them
  // into onset-aligned windows and emits ObservedVoice records.

  constructor(audioContext, { barSeconds = DEFAULT_BAR_SECONDS } = {}) {
    this.audioContext = audioContext;
    this.barSeconds = barSeconds;
    this.analyser = audioContext.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.smoothingTimeConstant = 0.0;
    this._sourceNode = null;
    this._raf = 0;
    this._frames = []; // {t, spectrum: Uint8Array, time: Float32Array, rms}
    this._previousSpectrum = null;
  }

  attach(mediaStreamSource) {
    this._sourceNode = mediaStreamSource;
    mediaStreamSource.connect(this.analyser);
  }

  async run() {
    this._frames = [];
    this._previousSpectrum = null;
    const start = this.audioContext.currentTime;
    return new Promise((resolve) => {
      const tick = () => {
        const elapsed = this.audioContext.currentTime - start;
        if (elapsed >= this.barSeconds) {
          resolve(this.flush(start));
          return;
        }
        const spectrum = new Uint8Array(this.analyser.frequencyBinCount);
        const timeData = new Float32Array(this.analyser.fftSize);
        this.analyser.getByteFrequencyData(spectrum);
        this.analyser.getFloatTimeDomainData(timeData);
        this._frames.push({
          t: elapsed,
          spectrum,
          rms: rms(timeData),
          flux: spectralFlux(this._previousSpectrum, spectrum),
        });
        this._previousSpectrum = spectrum;
        this._raf = requestAnimationFrame(tick);
      };
      this._raf = requestAnimationFrame(tick);
    });
  }

  stop() {
    if (this._raf) cancelAnimationFrame(this._raf);
    if (this._sourceNode) {
      try { this._sourceNode.disconnect(this.analyser); } catch (_e) { /* ignore */ }
      this._sourceNode = null;
    }
  }

  flush(startTime) {
    // Walk the frame log, detect onsets via spectral-flux rise + RMS
    // gate, classify each onset window, and produce ObservedVoice
    // records. Indices are assigned in detection order.
    const frames = this._frames;
    if (frames.length === 0) return [];
    const fluxValues = frames.map((f) => f.flux);
    const meanFlux = fluxValues.reduce((s, v) => s + v, 0) / fluxValues.length;
    const observed = [];
    let lastOnsetFrame = -Infinity;
    const sampleRate = this.audioContext.sampleRate;
    const fftSize = this.analyser.fftSize;

    for (let i = 1; i < frames.length; i += 1) {
      const frame = frames[i];
      if (frame.rms < ONSET_RMS_THRESHOLD) continue;
      if (frame.flux < meanFlux * ONSET_FLUX_RATIO) continue;
      if (i - lastOnsetFrame < 4) continue; // de-bounce
      lastOnsetFrame = i;

      const windowEnd = Math.min(frames.length, i + 16);
      const window = frames.slice(i, windowEnd);
      const fundamental = findFundamental(frame.spectrum, sampleRate, fftSize);
      const waveform = classifyWaveform(
        frame.spectrum, fundamental, sampleRate, fftSize,
      );
      const envelope = classifyEnvelope(window.map((f) => f.rms));
      const amplitude = Math.max(...window.map((f) => f.rms));
      const startOffset = (frame.t / this.barSeconds) % 1.0;

      observed.push(buildObservedVoice({
        index: observed.length,
        fundamentalHz: fundamental,
        waveform,
        envelope,
        amplitude,
        startOffset,
      }));
    }
    return observed;
  }
}

export async function requestMicrophoneStream(audioContext) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("getUserMedia not available in this browser");
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  return audioContext.createMediaStreamSource(stream);
}
