const MANIFEST_KIND = "sonic-seed-v0";

const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const meter = document.getElementById("meter");
const meterCtx = meter.getContext("2d");
const palette = document.querySelector(".palette");

let audioCtx = null;
let analyser = null;
let masterGain = null;
let voices = [];
let manifest = null;
let running = false;
let last = performance.now();

async function loadSonicManifest() {
  const response = await fetch("./program.sonic.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`program.sonic.json ${response.status}`);
  }
  const data = await response.json();
  if (data.kind !== MANIFEST_KIND || !Array.isArray(data.voices)) {
    throw new Error("invalid sonic manifest");
  }
  manifest = data;
}

function resizeMeter() {
  const scale = window.devicePixelRatio || 1;
  meter.width = Math.floor(window.innerWidth * scale);
  meter.height = Math.floor(window.innerHeight * scale);
  meter.style.width = `${window.innerWidth}px`;
  meter.style.height = `${window.innerHeight}px`;
  meterCtx.setTransform(scale, 0, 0, scale, 0, 0);
}

function start() {
  if (running || !manifest) {
    return;
  }
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  masterGain = audioCtx.createGain();
  masterGain.gain.value = 0.5;
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;
  masterGain.connect(analyser);
  analyser.connect(audioCtx.destination);

  const now = audioCtx.currentTime;
  const barSeconds = manifest.bar_seconds || 4;
  voices = manifest.voices.map((voice) => createVoice(voice, now, barSeconds));
  running = true;
  startButton.setAttribute("aria-pressed", "true");
  stopButton.setAttribute("aria-pressed", "false");
}

function stop() {
  if (!running) {
    return;
  }
  for (const voice of voices) {
    try {
      voice.shutdown();
    } catch (_err) {
      // ignore
    }
  }
  voices = [];
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
  analyser = null;
  masterGain = null;
  running = false;
  startButton.setAttribute("aria-pressed", "false");
  stopButton.setAttribute("aria-pressed", "true");
  meterCtx.clearRect(0, 0, meter.width, meter.height);
}

function createVoice(voice, baseTime, barSeconds) {
  const startAt = baseTime + voice.start_offset * barSeconds;
  if (voice.role === "bus" || voice.amplitude <= 0) {
    return { shutdown: () => {}, voice };
  }

  const osc = audioCtx.createOscillator();
  osc.type = mapWaveform(voice.waveform);
  osc.frequency.value = voice.frequency_hz;

  const gain = audioCtx.createGain();
  gain.gain.value = 0;
  shapeEnvelope(gain.gain, voice, startAt, barSeconds);

  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(startAt);

  if (voice.role === "modulator") {
    const lfo = audioCtx.createOscillator();
    lfo.type = "sine";
    lfo.frequency.value = Math.max(0.05, voice.amplitude * 4);
    const lfoGain = audioCtx.createGain();
    lfoGain.gain.value = voice.amplitude * 50;
    lfo.connect(lfoGain);
    lfoGain.connect(osc.frequency);
    lfo.start(startAt);
    return {
      voice,
      shutdown: () => {
        osc.stop();
        lfo.stop();
      },
    };
  }

  return {
    voice,
    shutdown: () => osc.stop(),
  };
}

function mapWaveform(name) {
  if (name === "triangle" || name === "sawtooth" || name === "square") {
    return name;
  }
  return "sine";
}

function shapeEnvelope(gainParam, voice, startAt, barSeconds) {
  const peak = voice.amplitude;
  if (voice.envelope === "percussive") {
    gainParam.setValueAtTime(0, startAt);
    gainParam.linearRampToValueAtTime(peak, startAt + 0.02);
    gainParam.exponentialRampToValueAtTime(Math.max(0.0001, peak * 0.05), startAt + 0.6);
  } else if (voice.envelope === "swelling") {
    gainParam.setValueAtTime(0, startAt);
    gainParam.linearRampToValueAtTime(peak, startAt + 0.8);
  } else if (voice.envelope === "tremolo") {
    gainParam.setValueAtTime(peak, startAt);
    const cycles = 8;
    for (let i = 0; i < cycles; i += 1) {
      const at = startAt + (i / cycles) * barSeconds;
      gainParam.linearRampToValueAtTime(peak * (i % 2 === 0 ? 1 : 0.2), at);
    }
  } else {
    gainParam.setValueAtTime(0, startAt);
    gainParam.linearRampToValueAtTime(peak, startAt + 0.1);
  }
}

function draw() {
  meterCtx.clearRect(0, 0, meter.width, meter.height);
  if (!analyser) {
    requestAnimationFrame(draw);
    return;
  }
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  const width = window.innerWidth;
  const height = window.innerHeight;
  const binCount = Math.min(data.length, 96);
  const cellWidth = width / binCount;
  for (let i = 0; i < binCount; i += 1) {
    const v = data[i] / 255;
    const cellHeight = v * height * 0.7;
    const hue = 220 - i * 1.8;
    meterCtx.fillStyle = `hsl(${hue}, 70%, ${30 + v * 40}%)`;
    meterCtx.fillRect(i * cellWidth, height - cellHeight, cellWidth - 1, cellHeight);
  }
  requestAnimationFrame(draw);
}

palette.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }
  if (button.dataset.action === "start") {
    start();
  } else if (button.dataset.action === "stop") {
    stop();
  }
});

window.addEventListener("resize", resizeMeter);

loadSonicManifest()
  .catch(() => {
    manifest = null;
  })
  .finally(() => {
    resizeMeter();
    requestAnimationFrame(draw);
  });
