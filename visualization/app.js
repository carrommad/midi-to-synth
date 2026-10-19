// Roland S-1 Multi-Graph Audio Visualizer Lab
let audioCtx = null;
let sourceNode = null;
let inputGainNode = null;
let splitterNode = null;
let analyserLeft = null;
let analyserRight = null;
let monitorGainNode = null;
let stream = null;
let animationId = null;
let isFrozen = false;

// DOM Elements
const toggleAudioBtn = document.getElementById('toggleAudioBtn');
const freezeBtn = document.getElementById('freezeBtn');
const deviceSelect = document.getElementById('deviceSelect');
const monitorToggle = document.getElementById('monitorToggle');
const monitorVol = document.getElementById('monitorVol');
const inputGain = document.getElementById('inputGain');
const gainVal = document.getElementById('gainVal');

const pitchReadout = document.getElementById('pitchReadout');
const freqReadout = document.getElementById('freqReadout');
const vcfReadout = document.getElementById('vcfReadout');
const rmsReadout = document.getElementById('rmsReadout');
const meterLevel = document.getElementById('meterLevel');

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
const logScale = document.getElementById('logScale');
const showHarmonics = document.getElementById('showHarmonics');
const waterfallPreset = document.getElementById('waterfallPreset');
const specScale = document.getElementById('specScale');

// Mel scale conversion formulas (O'Shaughnessy / HTK)
function hzToMel(hz) {
  return 2595 * Math.log10(1 + hz / 700);
}
function melToHz(mel) {
  return 700 * (Math.pow(10, mel / 2595) - 1);
}

// 3D Waterfall Camera State (Default set to Front-High with wider angle & deep background)
const camera3D = {
  yaw: 0.08,      // slight angle offset for dimensional depth
  pitch: 0.38,    // increased view angle (higher elevation looking across cascade)
  zoom: 1.18,     // expanded viewport zoom
  panX: 0,        // centered horizon
  panY: 30,       // balanced vertical baseline
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

function autoCorrelate(buf, sampleRate) {
  const SIZE = buf.length;
  let rms = 0;
  for (let i = 0; i < SIZE; i++) rms += buf[i] * buf[i];
  rms = Math.sqrt(rms / SIZE);
  if (rms < 0.005) return -1;

  let r1 = 0, r2 = SIZE - 1, thres = 0.15;
  for (let i = 0; i < SIZE / 2; i++) {
    if (Math.abs(buf[i]) < thres) { r1 = i; break; }
  }
  for (let i = 1; i < SIZE / 2; i++) {
    if (Math.abs(buf[SIZE - i]) < thres) { r2 = SIZE - i; break; }
  }

  const buf2 = buf.slice(r1, r2);
  const c = new Array(buf2.length).fill(0);
  for (let i = 0; i < buf2.length; i++) {
    for (let j = 0; j < buf2.length - i; j++) {
      c[i] = c[i] + buf2[j] * buf2[j + i];
    }
  }

  let d = 0;
  while (c[d] > c[d + 1]) d++;
  let maxval = -1, maxpos = -1;
  for (let i = d; i < buf2.length; i++) {
    if (c[i] > maxval) {
      maxval = c[i];
      maxpos = i;
    }
  }
  let T0 = maxpos;
  if (T0 <= 0) return -1;

  const x1 = c[T0 - 1], x2 = c[T0], x3 = c[T0 + 1];
  const a = (x1 + x3 - 2 * x2) / 2;
  const b = (x3 - x1) / 2;
  if (a) T0 = T0 - b / (2 * a);

  return sampleRate / T0;
}

async function populateDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter(d => d.kind === 'audioinput');
    deviceSelect.innerHTML = '<option value="">Default Audio Input</option>';
    audioInputs.forEach((d, i) => {
      const opt = document.createElement('option');
      opt.value = d.deviceId;
      opt.textContent = d.label || `Audio Input ${i + 1}`;
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
    await populateDevices();

    sourceNode = audioCtx.createMediaStreamSource(stream);

    // Input digital gain amplifier (boost low mic signals from synth jack)
    inputGainNode = audioCtx.createGain();
    inputGainNode.gain.value = parseFloat(inputGain.value);
    sourceNode.connect(inputGainNode);

    // Stereo split
    splitterNode = audioCtx.createChannelSplitter(2);
    analyserLeft = audioCtx.createAnalyser();
    analyserRight = audioCtx.createAnalyser();

    analyserLeft.fftSize = 2048;
    analyserLeft.smoothingTimeConstant = 0.75;
    analyserRight.fftSize = 2048;
    analyserRight.smoothingTimeConstant = 0.75;

    inputGainNode.connect(splitterNode);
    splitterNode.connect(analyserLeft, 0);
    splitterNode.connect(analyserRight, 1);

    // Monitoring pass-through to speakers/headphones
    monitorGainNode = audioCtx.createGain();
    monitorGainNode.gain.value = monitorToggle.checked ? parseFloat(monitorVol.value) : 0;
    sourceNode.connect(monitorGainNode);
    monitorGainNode.connect(audioCtx.destination);

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

// 1. Oscilloscope with Auto-Gain and Edge Sync
function renderOscilloscope(dataTimeL, w, h) {
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
  const userMultiplier = vGain ? (parseFloat(vGain.value) / 5.0) : 1.0;

  if (autoScaleOsc && autoScaleOsc.checked) {
    // Fill 88% of vertical viewport, multiplied by user V-Gain slider
    if (maxAmp > 0.001) {
      vertScale = Math.min(300.0, (0.88 / maxAmp) * userMultiplier);
    }
  } else if (vGain) {
    vertScale = parseFloat(vGain.value);
  }

  // Robust Trigger search: find upward zero-crossing
  let startIdx = 0;
  if (triggerSync.checked) {
    const threshold = maxAmp * 0.1;
    for (let i = 0; i < dataTimeL.length - sampleCount - 1; i++) {
      if (dataTimeL[i] < -threshold && dataTimeL[i + 1] >= 0) {
        startIdx = i;
        break;
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

  // Estimate VCF Cutoff / Resonant peak (highest high-freq prominence)
  if (maxVal > -65 && maxBin > 1) {
    const peakFreq = (maxBin * nyquist) / binCount;
    vcfReadout.textContent = `${Math.round(peakFreq)} Hz`;

    let peakX = 0;
    if (isLog) {
      const minLog = Math.log10(20);
      const maxLog = Math.log10(nyquist);
      peakX = ((Math.log10(peakFreq) - minLog) / (maxLog - minLog)) * w;
    } else {
      peakX = (maxBin / binCount) * w;
    }
    const peakY = Math.max(0, Math.min(h, h - ((maxVal + 100) / 100) * h));

    if (showHarmonics.checked) {
      fftCtx.fillStyle = '#ffaa00';
      fftCtx.font = '11px JetBrains Mono';
      fftCtx.fillText(`${Math.round(peakFreq)} Hz (${Math.round(maxVal)} dB)`, Math.min(w - 110, peakX + 6), Math.max(16, peakY - 8));
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

  // Keep sensible bounds
  dynamicPeakDb = Math.max(-65.0, Math.min(-5.0, dynamicPeakDb));
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

  const minMel = hzToMel(30);
  const maxMel = hzToMel(Math.min(nyquist, 12000));

  // Push new slice every 2 animation frames for smooth cascading flow
  waterfallFrameCount++;
  if (waterfallFrameCount % 2 === 0) {
    for (let i = 0; i < reducedBins; i++) {
      const curMel = minMel + (i / (reducedBins - 1)) * (maxMel - minMel);
      const hz = melToHz(curMel);
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

  let maxChroma = Math.max(...chroma, 0.0001);
  const cx = w / 2;
  const cy = h / 2;
  const rOuter = Math.min(w, h) * 0.38;
  const rInner = rOuter * 0.45;

  for (let i = 0; i < 12; i++) {
    const angleStart = (i * Math.PI * 2) / 12 - Math.PI / 2;
    const angleEnd = ((i + 1) * Math.PI * 2) / 12 - Math.PI / 2;
    const val = chroma[i] / maxChroma;

    chromaCtx.beginPath();
    chromaCtx.arc(cx, cy, rInner + val * (rOuter - rInner), angleStart, angleEnd);
    chromaCtx.arc(cx, cy, rInner, angleEnd, angleStart, true);
    chromaCtx.closePath();

    chromaCtx.fillStyle = `hsla(${i * 30}, 85%, 55%, ${0.2 + val * 0.8})`;
    chromaCtx.fill();

    // Label
    const midAngle = (angleStart + angleEnd) / 2;
    const lx = cx + Math.cos(midAngle) * (rOuter + 14);
    const ly = cy + Math.sin(midAngle) * (rOuter + 14);
    chromaCtx.fillStyle = val > 0.6 ? '#00f0ff' : '#8b9bb4';
    chromaCtx.font = '10px JetBrains Mono';
    chromaCtx.textAlign = 'center';
    chromaCtx.textBaseline = 'middle';
    chromaCtx.fillText(NOTE_STRINGS[i], lx, ly);
  }
}

// 7. Stereo Phase Scope
function renderPhaseScope(dataTimeL, dataTimeR, w, h) {
  phaseCtx.fillStyle = 'rgba(8, 10, 15, 0.25)';
  phaseCtx.fillRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;
  const scale = Math.min(w, h) * 0.42;

  phaseCtx.strokeStyle = '#bb86fc';
  phaseCtx.shadowColor = '#bb86fc';
  phaseCtx.shadowBlur = 4;
  phaseCtx.lineWidth = 1.5;
  phaseCtx.beginPath();

  const len = Math.min(dataTimeL.length, dataTimeR.length);
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
  phaseCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  phaseCtx.beginPath();
  phaseCtx.arc(cx, cy, scale * 0.9, 0, Math.PI * 2);
  phaseCtx.moveTo(cx - scale, cy); phaseCtx.lineTo(cx + scale, cy);
  phaseCtx.moveTo(cx, cy - scale); phaseCtx.lineTo(cx, cy + scale);
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

  const freq = autoCorrelate(dataTimeL, audioCtx.sampleRate);
  if (freq !== -1 && freq > 20 && freq < 4000) {
    const midi = noteFromPitch(freq);
    const note = NOTE_STRINGS[midi % 12];
    const octave = Math.floor(midi / 12) - 1;
    pitchReadout.textContent = `${note}${octave}`;
    freqReadout.textContent = `${freq.toFixed(1)} Hz`;
  } else if (rms < 0.008) {
    pitchReadout.textContent = '--';
    freqReadout.textContent = '0.0 Hz';
  }

  // Update dynamic range AGC for spectrogram auto-scaling
  updateDynamicRange(dataFreqL, audioCtx.sampleRate / 2);

  // Draw 6 comprehensive synth graphs
  renderOscilloscope(dataTimeL, oscCanvas.width, oscCanvas.height);
  renderFFT(dataFreqL, fftCanvas.width, fftCanvas.height, audioCtx.sampleRate);
  render3DWaterfall(dataFreqL, waterfallCanvas.width, waterfallCanvas.height, audioCtx.sampleRate);
  renderHarmonics(dataFreqL, freq > 20 ? freq : 0, audioCtx.sampleRate, harmonicsCanvas.width, harmonicsCanvas.height);
  renderSpectrogram(dataFreqL, spectrogramCanvas.width, spectrogramCanvas.height, audioCtx.sampleRate);
  renderChromagram(dataFreqL, audioCtx.sampleRate, chromaCanvas.width, chromaCanvas.height);
  renderPhaseScope(dataTimeL, dataTimeR, phaseCanvas.width, phaseCanvas.height);
}

// Event Listeners
toggleAudioBtn.addEventListener('click', startAudio);
freezeBtn.addEventListener('click', () => {
  isFrozen = !isFrozen;
  freezeBtn.textContent = isFrozen ? 'Resume' : 'Freeze View';
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

// Camera POV Presets
waterfallPreset.addEventListener('change', () => {
  switch (waterfallPreset.value) {
    case 'iso':
      camera3D.yaw = 0.52;
      camera3D.pitch = 0.62;
      camera3D.zoom = 1.05;
      camera3D.panX = -25;
      camera3D.panY = 8;
      break;
    case 'front':
      camera3D.yaw = 0.08;
      camera3D.pitch = 0.38;
      camera3D.zoom = 1.18;
      camera3D.panX = 0;
      camera3D.panY = 30;
      break;
    case 'side':
      camera3D.yaw = 0.75;
      camera3D.pitch = 0.45;
      camera3D.zoom = 1.0;
      camera3D.panX = -30;
      camera3D.panY = 0;
      break;
    case 'top':
      camera3D.yaw = 0.0;
      camera3D.pitch = 0.95;
      camera3D.zoom = 1.1;
      camera3D.panX = 0;
      camera3D.panY = -25;
      break;
  }
});

inputGain.addEventListener('input', () => {
  const g = parseFloat(inputGain.value);
  gainVal.textContent = `${g.toFixed(1)}x`;
  if (inputGainNode && audioCtx) {
    inputGainNode.gain.setTargetAtTime(g, audioCtx.currentTime, 0.02);
  }
});

monitorToggle.addEventListener('change', () => {
  if (monitorGainNode && audioCtx) {
    const targetGain = monitorToggle.checked ? parseFloat(monitorVol.value) : 0;
    monitorGainNode.gain.setTargetAtTime(targetGain, audioCtx.currentTime, 0.02);
  }
});

monitorVol.addEventListener('input', () => {
  if (monitorGainNode && audioCtx && monitorToggle.checked) {
    monitorGainNode.gain.setTargetAtTime(parseFloat(monitorVol.value), audioCtx.currentTime, 0.02);
  }
});

deviceSelect.addEventListener('change', () => {
  if (audioCtx) startAudio();
});

populateDevices();
