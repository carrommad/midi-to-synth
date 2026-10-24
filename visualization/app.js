// Roland S-1 Multi-Graph Audio Visualizer Lab
let audioCtx = null;
let sourceNode = null;
let inputGainNode = null;
let splitterNode = null;
let analyserLeft = null;
let analyserRight = null;
let analyserFine = null;
let monitorGainNode = null;
let notchFilter1 = null; // 6.4 kHz USB switching whistle notch
let notchFilter2 = null; // 12.8 kHz 2nd harmonic notch
let stream = null;
let animationId = null;
let isFrozen = false;

// DOM Elements
const toggleAudioBtn = document.getElementById('toggleAudioBtn');
const freezeBtn = document.getElementById('freezeBtn');
const deviceSelect = document.getElementById('deviceSelect');
const monitorToggle = document.getElementById('monitorToggle');
const monitorState = document.getElementById('monitorState');
let monitorOn = false;
const filterWhineToggle = document.getElementById('filterWhineToggle');
const filterWhineState = document.getElementById('filterWhineState');
let filterWhineOn = true;
const inputGain = document.getElementById('inputGain');
const gainVal = document.getElementById('gainVal');

const pitchReadout = document.getElementById('pitchReadout');
const freqReadout = document.getElementById('freqReadout');
const vcfReadout = document.getElementById('vcfReadout');
const rmsReadout = document.getElementById('rmsReadout');
const meterLevel = document.getElementById('meterLevel');
const clipIndicator = document.getElementById('clipIndicator');
let clipHoldFrames = 0;

// Canvases
const oscCanvas = document.getElementById('oscCanvas');
const fftCanvas = document.getElementById('fftCanvas');
const waterfallCanvas = document.getElementById('waterfallCanvas');
const harmonicsCanvas = document.getElementById('harmonicsCanvas');
const spectrogramCanvas = document.getElementById('spectrogramCanvas');
const chromaCanvas = document.getElementById('chromaCanvas');
const phaseCanvas = document.getElementById('phaseCanvas');

const oscCtx = oscCanvas.getContext('2d');
const fftCtx = fftCanvas.getContext('2d');
const waterfallCtx = waterfallCanvas.getContext('2d');
const harmonicsCtx = harmonicsCanvas.getContext('2d');
const specCtx = spectrogramCanvas.getContext('2d');
const chromaCtx = chromaCanvas.getContext('2d');
const phaseCtx = phaseCanvas.getContext('2d');

// UI Controls
const triggerSync = document.getElementById('triggerSync');
const autoScaleOsc = document.getElementById('autoScaleOsc');
const oscZoom = document.getElementById('oscZoom');
const vGain = document.getElementById('vGain');
let oscPeakSmooth = 0;

// V-Gain only applies when Auto Gain is off
function syncVGainState() {
  if (!vGain || !autoScaleOsc) return;
  vGain.disabled = autoScaleOsc.checked;
  vGain.title = autoScaleOsc.checked ? 'Disable Auto Gain to use V-Gain' : 'Vertical Scale';
}
if (autoScaleOsc) autoScaleOsc.addEventListener('change', syncVGainState);
syncVGainState();
const logScale = document.getElementById('logScale');
const showHarmonics = document.getElementById('showHarmonics');
const waterfallLog = document.getElementById('waterfallLog');
const specScale = document.getElementById('specScale');

// Mel scale conversion formulas (O'Shaughnessy / HTK)
function hzToMel(hz) {
  return 2595 * Math.log10(1 + hz / 700);
}
function melToHz(mel) {
  return 700 * (Math.pow(10, mel / 2595) - 1);
}

// 3D Waterfall Camera State (Default set to Isometric perspective)
const camera3D = {
  yaw: 0.52,      // isometric yaw angle
  pitch: 0.62,    // isometric elevation
  zoom: 1.05,     // viewport zoom
  panX: -25,      // centered composition
  panY: 8,        // baseline offset
  isDragging: false,
  lastMouseX: 0,
  lastMouseY: 0
};

// Circular history buffer for 3D waterfall: 180 persistent background slices
const WATERFALL_SLICES = 180;
let waterfallFrameCount = 0;
let waterfallHistory = [];

const NOTE_STRINGS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

function noteFromPitch(frequency) {
  const noteNum = 12 * (Math.log(frequency / 440) / Math.log(2));
  return Math.round(noteNum) + 69;
}

// Pitch detection: normalized autocorrelation with confidence gating.
// Returns -1 when the signal is too quiet or not clearly periodic (e.g. noise).
const PITCH_WINDOW = 4096;     // samples analysed (enough for ~30 Hz periods)
const PITCH_MIN_RMS = 0.003;   // ~ -50 dBFS
const PITCH_MIN_CLARITY = 0.9; // 0..1, periodicity confidence
const PITCH_MIN_HZ = 30;
const PITCH_MAX_HZ = 4000;

function autoCorrelate(fullBuf, sampleRate) {
  const buf = fullBuf.length > PITCH_WINDOW ? fullBuf.subarray(fullBuf.length - PITCH_WINDOW) : fullBuf;
  const SIZE = buf.length;

  let energy = 0;
  for (let i = 0; i < SIZE; i++) energy += buf[i] * buf[i];
  if (Math.sqrt(energy / SIZE) < PITCH_MIN_RMS) return -1;

  const minLag = Math.max(2, Math.floor(sampleRate / PITCH_MAX_HZ));
  const maxLag = Math.min(SIZE - 2, Math.ceil(sampleRate / PITCH_MIN_HZ));
  const nsdf = new Float32Array(maxLag + 2);

  // Normalized square difference function (McLeod): 1 = perfectly periodic
  for (let lag = minLag; lag <= maxLag + 1; lag++) {
    let acf = 0, m = 0;
    for (let j = 0; j < SIZE - lag; j++) {
      const a = buf[j], b = buf[j + lag];
      acf += a * b;
      m += a * a + b * b;
    }
    nsdf[lag] = m > 0 ? (2 * acf) / m : 0;
  }

  // Find local peaks in NSDF and pick the highest clarity peak
  let maxPeakVal = 0;
  let bestLag = -1;
  for (let lag = minLag + 1; lag < maxLag; lag++) {
    if (nsdf[lag] > nsdf[lag - 1] && nsdf[lag] >= nsdf[lag + 1] && nsdf[lag] > 0) {
      if (nsdf[lag] > maxPeakVal) {
        maxPeakVal = nsdf[lag];
        bestLag = lag;
      }
    }
  }
  if (maxPeakVal < PITCH_MIN_CLARITY || bestLag <= 0) return -1;
  const T0 = bestLag;

  // Parabolic interpolation for sub-sample accuracy
  const x1 = nsdf[T0 - 1], x2 = nsdf[T0], x3 = nsdf[T0 + 1];
  const a = (x1 + x3 - 2 * x2) / 2;
  const b = (x3 - x1) / 2;
  let period = T0;
  if (a) period = T0 - b / (2 * a);

  return sampleRate / period;
}

async function populateDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter(d => d.kind === 'audioinput');
    deviceSelect.innerHTML = '<option value="">Default Input</option>';
    audioInputs.forEach((d, i) => {
      const opt = document.createElement('option');
      opt.value = d.deviceId;
      let lbl = d.label || `Input ${i + 1}`;
      lbl = lbl.replace(/^default\s*-\s*/i, '').trim();
      opt.textContent = lbl.length > 20 ? `${lbl.slice(0, 18)}…` : lbl;
      opt.title = d.label || `Input ${i + 1}`;
      if (d.label.toLowerCase().includes('s-1') || d.label.toLowerCase().includes('roland') || d.label.toLowerCase().includes('headset')) {
        opt.selected = true;
      }
      deviceSelect.appendChild(opt);
    });
  } catch (err) {
    console.warn("Could not list audio devices:", err);
  }
}

function resizeCanvases() {
  [oscCanvas, fftCanvas, waterfallCanvas, harmonicsCanvas, spectrogramCanvas, chromaCanvas, phaseCanvas].forEach(cvs => {
    const rect = cvs.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const targetW = Math.floor(rect.width * dpr);
    const targetH = Math.floor(rect.height * dpr);
    if (cvs.width !== targetW || cvs.height !== targetH) {
      cvs.width = targetW || 300;
      cvs.height = targetH || 200;
    }
  });
}
window.addEventListener('resize', resizeCanvases);

// Audio Engine Init
async function startAudio() {
  if (audioCtx && audioCtx.state === 'running') {
    stopAudio();
    return;
  }

  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const constraints = {
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        deviceId: deviceSelect.value ? { exact: deviceSelect.value } : undefined
      }
    };
    stream = await navigator.mediaDevices.getUserMedia(constraints);

    sourceNode = audioCtx.createMediaStreamSource(stream);

    // Input digital gain amplifier (boost low mic signals from synth jack)
    inputGainNode = audioCtx.createGain();
    inputGainNode.gain.value = parseFloat(inputGain.value);
    sourceNode.connect(inputGainNode);

    // Stereo split
    splitterNode = audioCtx.createChannelSplitter(2);
    analyserLeft = audioCtx.createAnalyser();
    analyserRight = audioCtx.createAnalyser();

    // Fast analysers (2048 ≈ 43 ms at 48 kHz): scope, FFT, waterfall, spectrogram, goniometer
    analyserLeft.fftSize = 2048;
    analyserLeft.smoothingTimeConstant = 0.5;
    analyserRight.fftSize = 2048;
    analyserRight.smoothingTimeConstant = 0.5;

    // Fine analyser (8192 ≈ 5.9 Hz/bin): pitch, harmonics, chromagram
    analyserFine = audioCtx.createAnalyser();
    analyserFine.fftSize = 8192;
    analyserFine.smoothingTimeConstant = 0.5;

    splitterNode.connect(analyserLeft, 0);
    splitterNode.connect(analyserRight, 1);
    splitterNode.connect(analyserFine, 0);

    // Monitoring pass-through to speakers/headphones
    monitorGainNode = audioCtx.createGain();
    monitorGainNode.gain.value = monitorOn ? 1.0 : 0;
    monitorGainNode.connect(audioCtx.destination);

    // Steep Notch Filters for Ground Loop Whine (~6.4 kHz fundamental & ~12.8 kHz harmonic)
    notchFilter1 = audioCtx.createBiquadFilter();
    notchFilter1.type = 'notch';
    notchFilter1.frequency.value = 6450;
    notchFilter1.Q.value = 12.0;

    notchFilter2 = audioCtx.createBiquadFilter();
    notchFilter2.type = 'notch';
    notchFilter2.frequency.value = 12900;
    notchFilter2.Q.value = 12.0;

    // Apply or bypass whine filter (all destination nodes are now ready)
    updateWhineFilterRouting();

    toggleAudioBtn.textContent = 'Stop Audio';
    toggleAudioBtn.classList.add('active-stop');
    freezeBtn.disabled = false;

    resizeCanvases();
    renderLoop();
  } catch (err) {
    console.error("Audio initialization failed:", err);
    alert(`Could not start audio: ${err.message}`);
  }
}

function stopAudio() {
  if (animationId) cancelAnimationFrame(animationId);
  if (stream) stream.getTracks().forEach(track => track.stop());
  if (audioCtx) audioCtx.close();
  audioCtx = null;
  toggleAudioBtn.textContent = 'Start Audio';
  toggleAudioBtn.classList.remove('active-stop');
  freezeBtn.disabled = true;
  pitchReadout.textContent = '--';
  freqReadout.textContent = '0.0 Hz';
  vcfReadout.textContent = '-- Hz';
  rmsReadout.innerHTML = '-&infin; / -&infin; dB';
  meterLevel.style.width = '0%';
}

// Frequency axis helpers
const AXIS_FREQS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
function formatHz(hz) {
  return hz >= 1000 ? `${hz / 1000}k` : `${hz}`;
}
function drawAxisLabel(ctx, text, x, y, align = 'center') {
  ctx.fillStyle = 'rgba(139, 155, 180, 0.85)';
  ctx.font = '10px JetBrains Mono';
  ctx.textAlign = align;
  ctx.textBaseline = 'alphabetic';
  ctx.fillText(text, x, y);
}

// Drawing routines
function drawGrid(ctx, w, h, xDivs = 8, yDivs = 6) {
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 1; i < xDivs; i++) {
    const x = (w / xDivs) * i;
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
  }
  for (let j = 1; j < yDivs; j++) {
    const y = (h / yDivs) * j;
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
  }
  ctx.stroke();

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
  ctx.beginPath();
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();
}

// 1. Oscilloscope with Auto-Gain and Peak-Anchored Edge Sync
function renderOscilloscope(dataTimeL, w, h, fundFreq = 0, sampleRate = 48000) {
  oscCtx.fillStyle = '#080a0f';
  oscCtx.fillRect(0, 0, w, h);
  drawGrid(oscCtx, w, h);

  const zoom = parseInt(oscZoom.value, 10);
  const sampleCount = Math.floor(dataTimeL.length / zoom);

  // Compute peak amplitude in buffer to determine vertical scale
  let maxAmp = 0.001;
  for (let i = 0; i < dataTimeL.length; i++) {
    const absVal = Math.abs(dataTimeL[i]);
    if (absVal > maxAmp) maxAmp = absVal;
  }

  // Calculate vertical scaling multiplier
  let vertScale = 1.0;

  if (autoScaleOsc && autoScaleOsc.checked) {
    // Smoothed peak: fast attack, slow release; fill 88% of viewport
    oscPeakSmooth = maxAmp > oscPeakSmooth
      ? maxAmp
      : oscPeakSmooth * 0.97 + maxAmp * 0.03;
    // Floor (~-34 dBFS peak) so background noise is not blown up to full screen
    const OSC_AUTO_FLOOR = 0.02;
    vertScale = Math.min(300.0, 0.88 / Math.max(OSC_AUTO_FLOOR, oscPeakSmooth));
  } else if (vGain) {
    vertScale = parseFloat(vGain.value);
  }

  // Robust Hardware-Grade Schmitt Trigger:
  // Arms below -hysteresis, fires upon crossing 0 with positive slope.
  // Perfectly stabilizes PWM (pulse-width modulation), square waves, sawtooths, and sub-mixes.
  let startIdx = 0;
  if (triggerSync.checked && maxAmp > 0.005) {
    const searchLimit = Math.max(0, dataTimeL.length - sampleCount - 1);
    const hysteresis = maxAmp * 0.12;
    let armed = false;
    let found = false;

    // Pass 1: Standard rising-edge Schmitt trigger
    for (let i = 0; i < searchLimit; i++) {
      if (!armed) {
        if (dataTimeL[i] < -hysteresis) armed = true;
      } else if (dataTimeL[i] >= 0) {
        startIdx = i;
        found = true;
        break;
      }
    }

    // Pass 2: Fallback for falling-edge (e.g. sharp downward sawtooth) if no rising edge found
    if (!found) {
      armed = false;
      for (let i = 0; i < searchLimit; i++) {
        if (!armed) {
          if (dataTimeL[i] > hysteresis) armed = true;
        } else if (dataTimeL[i] <= 0) {
          startIdx = i;
          found = true;
          break;
        }
      }
    }
  }

  oscCtx.lineWidth = 2.5;
  oscCtx.strokeStyle = '#00ff88';
  oscCtx.shadowColor = '#00ff88';
  oscCtx.shadowBlur = 8;
  oscCtx.beginPath();

  const sliceWidth = w / sampleCount;
  let x = 0;
  for (let i = 0; i < sampleCount; i++) {
    const rawVal = dataTimeL[startIdx + i] || 0;
    const v = Math.max(-1.1, Math.min(1.1, rawVal * vertScale));
    const y = ((1 - v) / 2) * h;
    if (i === 0) oscCtx.moveTo(x, y);
    else oscCtx.lineTo(x, y);
    x += sliceWidth;
  }
  oscCtx.stroke();
  oscCtx.shadowBlur = 0;
}

// 2. FFT Spectrum & Resonance Tracker
function renderFFT(dataFreqL, w, h, sampleRate) {
  fftCtx.fillStyle = '#080a0f';
  fftCtx.fillRect(0, 0, w, h);
  drawGrid(fftCtx, w, h);

  const isLog = logScale.checked;
  const binCount = dataFreqL.length;
  const nyquist = sampleRate / 2;

  let maxVal = -Infinity;
  let maxBin = 0;

  fftCtx.beginPath();
  fftCtx.strokeStyle = '#00f0ff';
  fftCtx.lineWidth = 2;
  fftCtx.shadowColor = '#00f0ff';
  fftCtx.shadowBlur = 6;

  for (let i = 0; i < binCount; i++) {
    const db = dataFreqL[i];
    if (db > maxVal && i > 1) {
      maxVal = db;
      maxBin = i;
    }

    const y = Math.max(0, Math.min(h, h - ((db + 100) / 100) * h));
    let x = 0;
    if (isLog) {
      const minLog = Math.log10(20);
      const maxLog = Math.log10(nyquist);
      const currentLog = Math.log10(Math.max(20, (i * nyquist) / binCount));
      x = ((currentLog - minLog) / (maxLog - minLog)) * w;
    } else {
      x = (i / binCount) * w;
    }

    if (i === 0) fftCtx.moveTo(x, y);
    else fftCtx.lineTo(x, y);
  }
  fftCtx.stroke();
  fftCtx.shadowBlur = 0;

  // Frequency axis (Hz)
  const fftLabels = isLog ? AXIS_FREQS : [2000, 5000, 10000, 15000, 20000].filter(f => f < nyquist);
  fftCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  fftCtx.lineWidth = 1;
  for (const f of fftLabels) {
    if (f >= nyquist) continue;
    if (isLog && f === 50) continue; // prevent 50 and 100 collision
    const fx = isLog
      ? ((Math.log10(f) - Math.log10(20)) / (Math.log10(nyquist) - Math.log10(20))) * w
      : (f / nyquist) * w;
    fftCtx.beginPath();
    fftCtx.moveTo(fx, 0);
    fftCtx.lineTo(fx, h - 14);
    fftCtx.stroke();

    if (fx <= 2) {
      drawAxisLabel(fftCtx, formatHz(f), 6, h - 3, 'left');
    } else {
      drawAxisLabel(fftCtx, formatHz(f), fx, h - 3, 'center');
    }
  }

  // Estimate VCF Cutoff / Resonant peak (prominent peak above 80 Hz to reject AC line hum)
  const minVcfBin = Math.max(2, Math.round((80 / nyquist) * binCount));
  let peakVal = -Infinity;
  let peakBin = 0;

  for (let i = minVcfBin; i < binCount; i++) {
    if (dataFreqL[i] > peakVal) {
      peakVal = dataFreqL[i];
      peakBin = i;
    }
  }

  // Only display cutoff if peak is legitimately prominent and above noise threshold (-60 dB)
  if (peakVal > -60 && peakBin >= minVcfBin) {
    const peakFreq = (peakBin * nyquist) / binCount;
    vcfReadout.textContent = `${Math.round(peakFreq)} Hz`;

    let peakX = 0;
    if (isLog) {
      const minLog = Math.log10(20);
      const maxLog = Math.log10(nyquist);
      peakX = ((Math.log10(peakFreq) - minLog) / (maxLog - minLog)) * w;
    } else {
      peakX = (peakBin / binCount) * w;
    }
    const peakY = Math.max(0, Math.min(h, h - ((peakVal + 100) / 100) * h));

    if (showHarmonics.checked) {
      fftCtx.fillStyle = '#ffaa00';
      fftCtx.font = '11px JetBrains Mono';
      fftCtx.fillText(`${Math.round(peakFreq)} Hz (${Math.round(peakVal)} dB)`, Math.min(w - 110, peakX + 6), Math.max(16, peakY - 8));
      fftCtx.beginPath();
      fftCtx.arc(peakX, peakY, 4, 0, Math.PI * 2);
      fftCtx.fill();
    }
  } else {
    vcfReadout.textContent = '-- Hz';
  }
}

// Dynamic AGC Auto-scaling for Spectrograms
let dynamicPeakDb = -45.0;
let dynamicFloorDb = -85.0;

function updateDynamicRange(dataFreqL, nyquist) {
  let localPeak = -120;
  let localFloor = 0;
  const maxIdx = Math.floor(dataFreqL.length * (12000 / nyquist));

  for (let i = 2; i < maxIdx; i++) {
    const val = dataFreqL[i];
    if (val > localPeak) localPeak = val;
    if (val < localFloor) localFloor = val;
  }

  // Smooth attack / decay tracking
  if (localPeak > dynamicPeakDb) {
    dynamicPeakDb = dynamicPeakDb * 0.7 + localPeak * 0.3; // fast attack
  } else {
    dynamicPeakDb = dynamicPeakDb * 0.98 + localPeak * 0.02; // slow release
  }

  // Keep sensible bounds (upper floor -40 dB keeps silence flat instead of amplifying noise)
  dynamicPeakDb = Math.max(-40.0, Math.min(-5.0, dynamicPeakDb));
  // Noise floor is placed ~50 dB below peak
  dynamicFloorDb = dynamicPeakDb - 48.0;
}

// 3. 3D Waterfall Spectrum (Interactive POV perspective with Mel Frequency Warping & Auto-Scaling)
function render3DWaterfall(dataFreqL, w, h, sampleRate) {
  waterfallCtx.fillStyle = '#080a0f';
  waterfallCtx.fillRect(0, 0, w, h);

  const reducedBins = 64;
  const slice = new Float32Array(reducedBins);
  const nyquist = (sampleRate || 48000) / 2;
  const binCount = dataFreqL.length;
  const isLog = !waterfallLog || waterfallLog.checked;

  const minHz = 20;
  const maxHz = Math.min(nyquist, 12000);
  const minLog = Math.log10(minHz);
  const maxLog = Math.log10(maxHz);
  const minMel = hzToMel(30);
  const maxMel = hzToMel(maxHz);

  // Push new slice every 2 animation frames for smooth cascading flow
  waterfallFrameCount++;
  if (waterfallFrameCount % 2 === 0) {
    for (let i = 0; i < reducedBins; i++) {
      const frac = i / (reducedBins - 1);
      let hz = 0;
      if (isLog) {
        hz = Math.pow(10, minLog + frac * (maxLog - minLog));
      } else {
        hz = melToHz(minMel + frac * (maxMel - minMel));
      }
      const bin = Math.min(binCount - 1, Math.max(0, Math.round((hz / nyquist) * binCount)));
      slice[i] = dataFreqL[bin];
    }
    waterfallHistory.unshift(slice);
    if (waterfallHistory.length > WATERFALL_SLICES) waterfallHistory.pop();
  }

  const totalSlices = waterfallHistory.length;
  const zoom = camera3D.zoom;

  // Render from back (oldest) to front (newest)
  for (let s = totalSlices - 1; s >= 0; s--) {
    const data = waterfallHistory[s];
    const progress = s / WATERFALL_SLICES; // 0 (front/now) to 1 (back/old)

    // Camera perspective transformations
    const depthX = progress * (w * camera3D.yaw) * zoom;
    const depthY = progress * (h * camera3D.pitch) * zoom;

    const sliceW = (w * 0.76) * zoom * (1 - progress * 0.08);
    const sliceH = (h * 0.44) * zoom * (1 - progress * 0.12);

    const startX = (w * 0.08) + depthX + camera3D.panX;
    const baseY = (h * 0.85) - depthY + camera3D.panY;

    // Smooth spectral color progression: electric cyan -> vibrant cobalt -> deep violet
    const colorProgress = Math.pow(progress, 0.7);
    const hue = 175 + colorProgress * 100;

    // High persistence across all 180 background lines (minimum 42% opacity)
    const alpha = Math.max(0.42, 1 - progress * 0.45);

    waterfallCtx.strokeStyle = `hsla(${hue}, 100%, 55%, ${alpha})`;
    waterfallCtx.lineWidth = s === 0 ? 2.4 : 1.3;
    waterfallCtx.beginPath();

    const dx = sliceW / reducedBins;
    for (let i = 0; i < reducedBins; i++) {
      const db = data[i];
      // Auto-scale 0 to 1 based on tracked dynamic peak & floor
      const norm = Math.max(0, Math.min(1, (db - dynamicFloorDb) / (dynamicPeakDb - dynamicFloorDb)));
      const px = startX + i * dx;
      const py = baseY - norm * sliceH;

      if (i === 0) waterfallCtx.moveTo(px, py);
      else waterfallCtx.lineTo(px, py);
    }
    waterfallCtx.stroke();
  }

  // Frequency labels under the front (newest) slice (skip 50 Hz on log scale to prevent 50/100 overlap)
  const frontStartX = (w * 0.08) + camera3D.panX;
  const frontBaseY = (h * 0.85) + camera3D.panY;
  const frontW = (w * 0.76) * zoom;
  let lastLabelX = -999;
  for (const f of AXIS_FREQS) {
    if (f < minHz || f > maxHz) continue;
    if (isLog && f === 50) continue; // prevent 50 and 100 collision
    let frac = 0;
    if (isLog) {
      frac = (Math.log10(f) - minLog) / (maxLog - minLog);
    } else {
      frac = (hzToMel(f) - minMel) / (maxMel - minMel);
    }
    const lx = frontStartX + frac * frontW;
    if (lx < 0 || lx > w - 10) continue;
    if (Math.abs(lx - lastLabelX) < 20) continue; // guarantee minimum label spacing
    lastLabelX = lx;
    drawAxisLabel(waterfallCtx, formatHz(f), Math.max(12, lx), Math.min(h - 3, frontBaseY + 14));
  }
}

// Pitch memory and harmonic bar smoothing to eliminate intermittent dropouts
let lastValidFundFreq = 0;
let pitchHoldCounter = 0;
const smoothedHarmonicNorms = new Float32Array(16).fill(0);

// Fallback spectral peak detector for fundamental frequency when time-domain autocorrelation misses
function getSpectralFundamental(dataFreqL, nyquist) {
  const binCount = dataFreqL.length;
  let maxDb = -120;
  let peakBin = 0;
  const maxSearchBin = Math.floor(binCount * (1500 / nyquist));

  for (let b = 2; b < maxSearchBin; b++) {
    if (dataFreqL[b] > maxDb) {
      maxDb = dataFreqL[b];
      peakBin = b;
    }
  }
  if (maxDb > -75 && peakBin > 1) {
    return (peakBin * nyquist) / binCount;
  }
  return 0;
}

// 4. Harmonic Series (Discrete Partials 1f0 - 16f0 with Pitch Hold and Smoothing)
function renderHarmonics(dataFreqL, fundFreq, sampleRate, w, h) {
  harmonicsCtx.fillStyle = '#080a0f';
  harmonicsCtx.fillRect(0, 0, w, h);
  drawGrid(harmonicsCtx, w, h, 16, 4);

  const partialCount = 16;
  const barWidth = (w / partialCount) - 4;
  const nyquist = sampleRate / 2;
  const binCount = dataFreqL.length;

  // Latch pitch so bars don't vanish intermittently on minor cycle inconsistencies
  if (fundFreq > 20) {
    lastValidFundFreq = fundFreq;
    pitchHoldCounter = 30; // Hold for ~0.5s of audio dropouts
  } else if (pitchHoldCounter > 0) {
    pitchHoldCounter--;
  } else {
    // If autocorrelation missed, fallback to FFT spectral peak
    const specFund = getSpectralFundamental(dataFreqL, nyquist);
    if (specFund > 20) {
      lastValidFundFreq = specFund;
      pitchHoldCounter = 15;
    } else {
      lastValidFundFreq = 0;
    }
  }

  const activeFund = lastValidFundFreq;

  for (let p = 1; p <= partialCount; p++) {
    const pFreq = activeFund * p;
    let ampDb = -120;

    if (activeFund > 20 && pFreq < nyquist) {
      const centerBin = Math.round((pFreq / nyquist) * binCount);
      const searchRadius = Math.max(2, Math.round(binCount * (12 / nyquist)));
      for (let b = Math.max(0, centerBin - searchRadius); b <= Math.min(binCount - 1, centerBin + searchRadius); b++) {
        if (dataFreqL[b] > ampDb) ampDb = dataFreqL[b];
      }
    }

    const targetNorm = activeFund > 20
      ? Math.max(0, Math.min(1, (ampDb - dynamicFloorDb) / (dynamicPeakDb - dynamicFloorDb)))
      : 0;

    // Smooth decay to prevent flicker (instant attack, gentle decay)
    if (targetNorm > smoothedHarmonicNorms[p - 1]) {
      smoothedHarmonicNorms[p - 1] = targetNorm;
    } else {
      smoothedHarmonicNorms[p - 1] = smoothedHarmonicNorms[p - 1] * 0.82 + targetNorm * 0.18;
    }

    const norm = smoothedHarmonicNorms[p - 1];
    const barHeight = norm * (h - 38);
    const x = (p - 1) * (barWidth + 4) + 2;
    const y = h - barHeight - 22;

    const isOdd = p % 2 !== 0;
    harmonicsCtx.fillStyle = isOdd ? 'rgba(0, 255, 136, 0.88)' : 'rgba(255, 170, 0, 0.88)';
    harmonicsCtx.fillRect(x, y, barWidth, barHeight);

    // Label with partial and harmonic number
    harmonicsCtx.fillStyle = norm > 0.4 ? (isOdd ? '#00ff88' : '#ffaa00') : '#8b9bb4';
    harmonicsCtx.font = '10px JetBrains Mono';
    harmonicsCtx.textAlign = 'center';
    harmonicsCtx.fillText(`${p}f`, x + barWidth / 2, h - 6);
  }
}

// 5. Spectrogram Waterfall Heatmap (Auto-Scaled 0 to 1)
function renderSpectrogram(dataFreqL, w, h, sampleRate) {
  // Shift existing canvas down by 2px
  specCtx.drawImage(spectrogramCanvas, 0, 0, w, h - 2, 0, 2, w, h - 2);

  const nyquist = (sampleRate || 48000) / 2;
  const binCount = dataFreqL.length;
  const outBins = 160;
  const sliceW = w / outBins;
  const mode = specScale ? specScale.value : 'mel';

  const minHz = 30;
  const maxHz = Math.min(nyquist, 12000);
  const minMel = hzToMel(minHz);
  const maxMel = hzToMel(maxHz);
  const minLog = Math.log10(minHz);
  const maxLog = Math.log10(maxHz);

  for (let i = 0; i < outBins; i++) {
    const fraction = i / (outBins - 1);
    let hz = 0;

    if (mode === 'mel') {
      hz = melToHz(minMel + fraction * (maxMel - minMel));
    } else if (mode === 'log') {
      hz = Math.pow(10, minLog + fraction * (maxLog - minLog));
    } else {
      hz = minHz + fraction * (maxHz - minHz);
    }

    const bin = Math.min(binCount - 1, Math.max(0, Math.round((hz / nyquist) * binCount)));
    const db = dataFreqL[bin];

    // Normalized strictly from 0 (noise floor) to 1 (peak harmonic)
    const norm = Math.max(0, Math.min(1, (db - dynamicFloorDb) / (dynamicPeakDb - dynamicFloorDb)));

    // Roland glowing heat palette: black -> purple/blue -> fiery orange -> bright yellow/white
    const r = Math.floor(Math.min(255, Math.pow(norm, 0.85) * 280));
    const g = Math.floor(Math.min(255, Math.pow(norm, 1.6) * 255));
    const b = Math.floor(Math.min(255, Math.pow(norm, 3.0) * 320 + (norm > 0.05 ? 35 : 0)));

    specCtx.fillStyle = `rgb(${r},${g},${b})`;
    specCtx.fillRect(i * sliceW, 0, Math.ceil(sliceW) + 1, 2);
  }
}

// 6. Chromagram Pitch-Class Dial
function renderChromagram(dataFreqL, sampleRate, w, h) {
  chromaCtx.fillStyle = '#080a0f';
  chromaCtx.fillRect(0, 0, w, h);

  const chroma = new Array(12).fill(0);
  const nyquist = sampleRate / 2;
  const binCount = dataFreqL.length;

  // Accumulate energy per pitch class across all octaves
  for (let i = 2; i < binCount / 2; i++) {
    const freq = (i * nyquist) / binCount;
    if (freq < 50 || freq > 4500) continue;
    const midi = noteFromPitch(freq);
    const pClass = ((midi % 12) + 12) % 12;
    const linAmp = Math.pow(10, dataFreqL[i] / 20);
    chroma[pClass] += linAmp;
  }

  let maxChroma = Math.max(...chroma, 0.000001);
  const cx = w / 2;
  const cy = h / 2;
  const rOuter = Math.min(w, h) * 0.38;
  const rInner = rOuter * 0.45;

  // Signal presence threshold (above -65 dB peak)
  const hasSignal = dynamicPeakDb > -65.0 && maxChroma > 0.0001;

  for (let i = 0; i < 12; i++) {
    const angleStart = (i * Math.PI * 2) / 12 - Math.PI / 2;
    const angleEnd = ((i + 1) * Math.PI * 2) / 12 - Math.PI / 2;
    const val = hasSignal ? Math.min(1, chroma[i] / maxChroma) : 0;

    chromaCtx.beginPath();
    chromaCtx.arc(cx, cy, rInner + val * (rOuter - rInner), angleStart, angleEnd);
    chromaCtx.arc(cx, cy, rInner, angleEnd, angleStart, true);
    chromaCtx.closePath();

    chromaCtx.fillStyle = hasSignal
      ? `hsla(${i * 30}, 85%, 55%, ${0.20 + val * 0.80})`
      : 'rgba(255, 255, 255, 0.03)';
    chromaCtx.fill();

    // Label
    const midAngle = (angleStart + angleEnd) / 2;
    const lx = cx + Math.cos(midAngle) * (rOuter + 14);
    const ly = cy + Math.sin(midAngle) * (rOuter + 14);
    chromaCtx.fillStyle = (hasSignal && val > 0.4) ? '#00f0ff' : '#8b9bb4';
    chromaCtx.font = '10px JetBrains Mono';
    chromaCtx.textAlign = 'center';
    chromaCtx.textBaseline = 'middle';
    chromaCtx.fillText(NOTE_STRINGS[i], lx, ly);
  }
}

// 7. Stereo Phase Scope (Goniometer with dynamic auto-expansion)
let phasePeakSmooth = 0.05;

function renderPhaseScope(dataTimeL, dataTimeR, w, h) {
  phaseCtx.fillStyle = 'rgba(8, 10, 15, 0.25)';
  phaseCtx.fillRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;
  const targetRadius = Math.min(w, h) * 0.40;

  const len = Math.min(dataTimeL.length, dataTimeR.length);

  // Compute peak magnitude in recent window for dynamic scaling
  let peakMag = 0.001;
  for (let i = 0; i < len; i += 4) {
    const l = Math.abs(dataTimeL[i]);
    const r = Math.abs(dataTimeR[i]);
    if (l > peakMag) peakMag = l;
    if (r > peakMag) peakMag = r;
  }

  // Smooth attack / slow decay
  if (peakMag > phasePeakSmooth) {
    phasePeakSmooth = phasePeakSmooth * 0.6 + peakMag * 0.4;
  } else {
    phasePeakSmooth = phasePeakSmooth * 0.96 + peakMag * 0.04;
  }

  // Auto-gain multiplier (fill ~80% of reticle, clamped to avoid blowing up silence)
  const normFloor = 0.02; // ~ -34 dB minimum reference
  const gain = Math.min(40.0, 0.82 / Math.max(normFloor, phasePeakSmooth));
  const scale = targetRadius * gain;

  phaseCtx.strokeStyle = '#bb86fc';
  phaseCtx.shadowColor = '#bb86fc';
  phaseCtx.shadowBlur = 6;
  phaseCtx.lineWidth = 1.8;
  phaseCtx.beginPath();

  for (let i = 0; i < len; i += 2) {
    const l = dataTimeL[i];
    const r = dataTimeR[i];
    const x = cx + ((l - r) * 0.707) * scale;
    const y = cy - ((l + r) * 0.707) * scale;
    if (i === 0) phaseCtx.moveTo(x, y);
    else phaseCtx.lineTo(x, y);
  }
  phaseCtx.stroke();
  phaseCtx.shadowBlur = 0;

  // Reticle
  phaseCtx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
  phaseCtx.beginPath();
  phaseCtx.arc(cx, cy, targetRadius * 0.95, 0, Math.PI * 2);
  phaseCtx.arc(cx, cy, targetRadius * 0.50, 0, Math.PI * 2);
  phaseCtx.moveTo(cx - targetRadius, cy); phaseCtx.lineTo(cx + targetRadius, cy);
  phaseCtx.moveTo(cx, cy - targetRadius); phaseCtx.lineTo(cx, cy + targetRadius);
  phaseCtx.stroke();
}

// Main Render Loop
function renderLoop() {
  if (!audioCtx) return;
  animationId = requestAnimationFrame(renderLoop);
  if (isFrozen) return;

  const bufferLength = analyserLeft.fftSize;
  const dataTimeL = new Float32Array(bufferLength);
  const dataTimeR = new Float32Array(bufferLength);
  const dataFreqL = new Float32Array(analyserLeft.frequencyBinCount);

  analyserLeft.getFloatTimeDomainData(dataTimeL);
  analyserRight.getFloatTimeDomainData(dataTimeR);
  analyserLeft.getFloatFrequencyData(dataFreqL);

  // High-resolution data for pitch / harmonics / chroma
  const fineTime = new Float32Array(analyserFine.fftSize);
  const fineFreq = new Float32Array(analyserFine.frequencyBinCount);
  analyserFine.getFloatTimeDomainData(fineTime);
  analyserFine.getFloatFrequencyData(fineFreq);

  // Meter & Pitch computation
  let sumSquares = 0;
  let peak = 0;
  for (let i = 0; i < dataTimeL.length; i++) {
    const val = dataTimeL[i];
    sumSquares += val * val;
    if (Math.abs(val) > peak) peak = Math.abs(val);
  }
  const rms = Math.sqrt(sumSquares / dataTimeL.length);
  const rmsDb = rms > 0.00001 ? 20 * Math.log10(rms) : -100;
  const peakDb = peak > 0.00001 ? 20 * Math.log10(peak) : -100;

  rmsReadout.textContent = `${rmsDb > -90 ? rmsDb.toFixed(1) : '-inf'} / ${peakDb > -90 ? peakDb.toFixed(1) : '-inf'} dB`;
  const meterPct = Math.max(0, Math.min(100, (peakDb + 60) * (100 / 60)));
  meterLevel.style.width = `${meterPct}%`;

  // Clip detection on raw input (pre digital gain); hold ~1 s
  const gainNow = inputGainNode ? inputGainNode.gain.value : 1;
  if (gainNow > 0 && peak / gainNow >= 0.98) clipHoldFrames = 60;
  else if (clipHoldFrames > 0) clipHoldFrames--;
  if (clipIndicator) clipIndicator.classList.toggle('active', clipHoldFrames > 0);

  const freq = autoCorrelate(fineTime, audioCtx.sampleRate);
  if (freq !== -1 && freq > 20 && freq < 4000) {
    const midi = noteFromPitch(freq);
    const note = NOTE_STRINGS[midi % 12];
    const octave = Math.floor(midi / 12) - 1;
    pitchReadout.textContent = `${note}${octave}`;
    freqReadout.textContent = `${freq.toFixed(1)} Hz`;
  } else {
    pitchReadout.textContent = '--';
    freqReadout.textContent = '-- Hz';
  }

  // Update dynamic range AGC for spectrogram auto-scaling
  updateDynamicRange(dataFreqL, audioCtx.sampleRate / 2);

  // Draw 6 comprehensive synth graphs
  renderOscilloscope(dataTimeL, oscCanvas.width, oscCanvas.height, freq > 20 ? freq : 0, audioCtx.sampleRate);
  renderFFT(dataFreqL, fftCanvas.width, fftCanvas.height, audioCtx.sampleRate);
  render3DWaterfall(dataFreqL, waterfallCanvas.width, waterfallCanvas.height, audioCtx.sampleRate);
  renderHarmonics(fineFreq, freq > 20 ? freq : 0, audioCtx.sampleRate, harmonicsCanvas.width, harmonicsCanvas.height);
  renderSpectrogram(dataFreqL, spectrogramCanvas.width, spectrogramCanvas.height, audioCtx.sampleRate);
  renderChromagram(fineFreq, audioCtx.sampleRate, chromaCanvas.width, chromaCanvas.height);
  renderPhaseScope(dataTimeL, dataTimeR, phaseCanvas.width, phaseCanvas.height);
}

// Event Listeners
toggleAudioBtn.addEventListener('click', startAudio);
freezeBtn.addEventListener('click', () => {
  isFrozen = !isFrozen;
  freezeBtn.textContent = isFrozen ? 'Resume' : 'Freeze View';
  freezeBtn.classList.toggle('frozen', isFrozen);
});

// 3D Waterfall Camera Interaction (Drag: Rotate/Orbit, Ctrl+Drag: Pan/Move Inside, Scroll: Zoom)
waterfallCanvas.addEventListener('mousedown', (e) => {
  camera3D.isDragging = true;
  camera3D.lastMouseX = e.clientX;
  camera3D.lastMouseY = e.clientY;
});

window.addEventListener('mousemove', (e) => {
  if (!camera3D.isDragging) return;
  const dx = e.clientX - camera3D.lastMouseX;
  const dy = e.clientY - camera3D.lastMouseY;
  camera3D.lastMouseX = e.clientX;
  camera3D.lastMouseY = e.clientY;

  if (e.ctrlKey || e.metaKey || e.shiftKey || e.buttons === 2) {
    // Ctrl + Drag: Pan/Move directly inside the graph coordinate space
    camera3D.panX += dx * 1.2;
    camera3D.panY += dy * 1.2;
  } else {
    // Normal Drag: Orbit (Yaw & Pitch)
    camera3D.yaw += dx * 0.0035;
    camera3D.pitch = Math.max(0.02, Math.min(1.4, camera3D.pitch - dy * 0.0035));
  }
});

// Prevent context menu when right-clicking to pan
waterfallCanvas.addEventListener('contextmenu', (e) => e.preventDefault());

window.addEventListener('mouseup', () => {
  camera3D.isDragging = false;
});

waterfallCanvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
  camera3D.zoom = Math.max(0.4, Math.min(3.0, camera3D.zoom * zoomFactor));
}, { passive: false });

inputGain.addEventListener('input', () => {
  const g = parseFloat(inputGain.value);
  gainVal.textContent = `${g.toFixed(1)}x`;
  if (inputGainNode && audioCtx) {
    inputGainNode.gain.setTargetAtTime(g, audioCtx.currentTime, 0.02);
  }
});

monitorToggle.addEventListener('change', () => {
  monitorOn = monitorToggle.checked;
  if (monitorState) {
    monitorState.textContent = monitorOn ? 'On' : 'Off';
  }
  if (monitorGainNode && audioCtx) {
    monitorGainNode.gain.setTargetAtTime(monitorOn ? 1.0 : 0, audioCtx.currentTime, 0.02);
  }
});

function updateWhineFilterRouting() {
  if (!audioCtx || !inputGainNode || !notchFilter1 || !notchFilter2) return;
  try {
    inputGainNode.disconnect();
    notchFilter1.disconnect();
    notchFilter2.disconnect();
  } catch (e) {
    // ignore disconnect errors during re-route
  }

  if (filterWhineOn) {
    // Route: inputGain -> Notch1 (6.4k) -> Notch2 (12.8k) -> Splitter / Monitor
    inputGainNode.connect(notchFilter1);
    notchFilter1.connect(notchFilter2);
    if (splitterNode) notchFilter2.connect(splitterNode);
    if (monitorGainNode) notchFilter2.connect(monitorGainNode);
  } else {
    // Direct bypass
    if (splitterNode) inputGainNode.connect(splitterNode);
    if (monitorGainNode) inputGainNode.connect(monitorGainNode);
  }
}

filterWhineToggle.addEventListener('change', () => {
  filterWhineOn = filterWhineToggle.checked;
  if (filterWhineState) {
    filterWhineState.textContent = filterWhineOn ? 'On' : 'Off';
  }
  updateWhineFilterRouting();
});

deviceSelect.addEventListener('change', () => {
  if (audioCtx) startAudio();
});

// Drag and drop reordering for chart panels
const chartsLayout = document.getElementById('chartsLayout');
const STORAGE_PANEL_ORDER_KEY = 'roland_s1_charts_order';

function initDraggablePanels() {
  if (!chartsLayout) return;

  // Restore saved panel order from localStorage
  const savedOrder = localStorage.getItem(STORAGE_PANEL_ORDER_KEY);
  if (savedOrder) {
    try {
      const orderIds = JSON.parse(savedOrder);
      const panelsById = new Map();
      chartsLayout.querySelectorAll('.chart-panel').forEach(p => {
        const id = p.getAttribute('data-panel-id');
        if (id) panelsById.set(id, p);
      });
      orderIds.forEach(id => {
        const panel = panelsById.get(id);
        if (panel) chartsLayout.appendChild(panel);
      });
    } catch (e) {
      console.warn("Could not restore panel order:", e);
    }
  }

  let draggedPanel = null;

  chartsLayout.querySelectorAll('.chart-panel').forEach(panel => {
    panel.setAttribute('draggable', 'true');

    panel.addEventListener('dragstart', (e) => {
      // Don't drag when interacting with controls or canvas
      if (['INPUT', 'SELECT', 'CANVAS', 'BUTTON', 'LABEL', 'OPTION'].includes(e.target.tagName)) {
        e.preventDefault();
        return;
      }
      draggedPanel = panel;
      panel.classList.add('panel-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', panel.getAttribute('data-panel-id') || 'panel');
    });

    panel.addEventListener('dragend', () => {
      chartsLayout.querySelectorAll('.chart-panel').forEach(p => {
        p.classList.remove('panel-dragging');
        p.classList.remove('panel-drag-over');
      });
      draggedPanel = null;
      resizeCanvases();
    });

    panel.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (!draggedPanel || draggedPanel === panel) return;
      panel.classList.add('panel-drag-over');
    });

    panel.addEventListener('dragleave', (e) => {
      if (!panel.contains(e.relatedTarget)) {
        panel.classList.remove('panel-drag-over');
      }
    });

    panel.addEventListener('drop', (e) => {
      e.preventDefault();
      panel.classList.remove('panel-drag-over');
      if (!draggedPanel || draggedPanel === panel) return;

      const rect = panel.getBoundingClientRect();
      const midX = rect.left + rect.width / 2;
      const midY = rect.top + rect.height / 2;

      // Determine before vs after insertion
      const isBefore = (e.clientY < midY - 20) || (Math.abs(e.clientY - midY) <= 40 && e.clientX < midX);

      if (isBefore) {
        chartsLayout.insertBefore(draggedPanel, panel);
      } else {
        chartsLayout.insertBefore(draggedPanel, panel.nextSibling);
      }

      savePanelOrder();
      resizeCanvases();
    });
  });

  function savePanelOrder() {
    const currentOrder = Array.from(chartsLayout.querySelectorAll('.chart-panel'))
      .map(p => p.getAttribute('data-panel-id'))
      .filter(Boolean);
    try {
      localStorage.setItem(STORAGE_PANEL_ORDER_KEY, JSON.stringify(currentOrder));
    } catch (err) {
      console.warn("Could not save panel order:", err);
    }
  }
}

initDraggablePanels();
populateDevices();
