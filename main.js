/**
 * BLADE ARENA - MOTION ARCADE & DUAL PLAYER SYSTEM
 * High-Precision Version: Aspect-Ratio Preserving Hand Tracking,
 * Trajectory Arc Raycasting, Persistent Dual Hand Identification,
 * and Dual Split-Screen Fruit Targets.
 */

import { HoopGame, CowGame, PainterGame, CatchGame, PoseGame } from './arcade_games.js';

// =====================================================================
//  1. CONFIGURATION & CONSTANTS
// =====================================================================

const CONFIG = {
  windowW: window.innerWidth,
  windowH: window.innerHeight,
  minSliceSpeed: 260.0,       // Light, effortless responsive cuts
  minSliceDist: 42.0,         // Crisp snap distance
  sliceWindow: 0.32,          // Slicing stroke window
  maxWobble: 1.95,            // Generous path wobble to support natural curved swings
  earlyStrictness: 1.40,
  fruitRadius: 110,
  hitboxMultiplier: 1.50,     // Generous 1.5x hitbox for satisfying, 100% reliable slicing
  gravity: 1800,
  dualFruitMode: 'split',     // 'split' (Left P1 vs Right P2) or 'center' (Shared single fruit)
};

const FRUITS = {
  apple:  { name: 'Apple',  skin: '#d2232d', flesh: '#fcf0d2', core: '#ebd7a0', seed: '#502d1e' },
  orange: { name: 'Orange', skin: '#ff8714', flesh: '#ffc346', core: '#ffdc78', seed: '#ffe6a0' },
  lime:   { name: 'Lime',   skin: '#50af2d', flesh: '#c3f073', core: '#dcf596', seed: '#ebfac8' },
  plum:   { name: 'Plum',   skin: '#732d91', flesh: '#f5b95a', core: '#e1a046', seed: '#6e4628' },
};

// =====================================================================
//  2. WEB AUDIO SYNTHESIZER
// =====================================================================

class WebSoundManager {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.initialized = false;
  }

  init() {
    if (this.initialized) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AudioCtx();
      this.initialized = true;
    } catch (e) {
      console.warn('AudioContext unavailable:', e);
    }
  }

  playSlice() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;

    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1400, t);
    osc.frequency.exponentialRampToValueAtTime(260, t + 0.18);
    gain.gain.setValueAtTime(0.35, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.18);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.18);

    const bufferSize = this.ctx.sampleRate * 0.12;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.35));
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;
    const noiseGain = this.ctx.createGain();
    noiseGain.gain.setValueAtTime(0.3, t);
    noiseGain.gain.exponentialRampToValueAtTime(0.01, t + 0.12);
    noise.connect(noiseGain);
    noiseGain.connect(this.ctx.destination);
    noise.start(t);
  }

  playTargetHit() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(600, t);
    osc.frequency.exponentialRampToValueAtTime(1200, t + 0.08);
    gain.gain.setValueAtTime(0.35, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.08);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.08);
  }

  playDeflect() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    [1200, 2400].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(idx === 0 ? 0.35 : 0.2, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t);
      osc.stop(t + 0.25);
    });
  }

  playGong() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    [880, 1760].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(idx === 0 ? 0.35 : 0.18, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.45);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t);
      osc.stop(t + 0.45);
    });
  }

  playWhoosh() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(320, t);
    osc.frequency.exponentialRampToValueAtTime(140, t + 0.14);
    gain.gain.setValueAtTime(0.18, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.14);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.14);
  }

  playThud() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(120, t);
    osc.frequency.exponentialRampToValueAtTime(40, t + 0.22);
    gain.gain.setValueAtTime(0.4, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.22);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.22);
  }

  playBowRelease() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(460, t);
    osc.frequency.exponentialRampToValueAtTime(140, t + 0.15);
    gain.gain.setValueAtTime(0.4, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.15);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.15);
  }

  playBalloonPop() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(820, t);
    osc.frequency.exponentialRampToValueAtTime(95, t + 0.11);
    gain.gain.setValueAtTime(0.45, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.11);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.11);

    const bufferSize = this.ctx.sampleRate * 0.08;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.22));
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;
    const noiseGain = this.ctx.createGain();
    noiseGain.gain.setValueAtTime(0.38, t);
    noiseGain.gain.exponentialRampToValueAtTime(0.01, t + 0.08);
    noise.connect(noiseGain);
    noiseGain.connect(this.ctx.destination);
    noise.start(t);
  }

  playSwish() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const bufferSize = this.ctx.sampleRate * 0.22;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.sin((i / bufferSize) * Math.PI);
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(2200, t);
    filter.Q.setValueAtTime(3.0, t);
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.4, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.22);
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);
    noise.start(t);
  }

  playBallBounce() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(160, t);
    osc.frequency.exponentialRampToValueAtTime(55, t + 0.12);
    gain.gain.setValueAtTime(0.45, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.12);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.12);
  }

  playMilkSquirt() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(750, t);
    osc.frequency.exponentialRampToValueAtTime(220, t + 0.09);
    gain.gain.setValueAtTime(0.3, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.09);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.09);
  }

  playPaintStroke() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(280, t);
    osc.frequency.linearRampToValueAtTime(180, t + 0.08);
    gain.gain.setValueAtTime(0.15, t);
    gain.gain.exponentialRampToValueAtTime(0.01, t + 0.08);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.08);
  }

  playCatch() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    [523.25, 659.25, 783.99].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t + idx * 0.04);
      gain.gain.setValueAtTime(0.25, t + idx * 0.04);
      gain.gain.exponentialRampToValueAtTime(0.01, t + idx * 0.04 + 0.16);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t + idx * 0.04);
      osc.stop(t + idx * 0.04 + 0.16);
    });
  }

  playPoseSuccess() {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const t = this.ctx.currentTime;
    [440, 554.37, 659.25, 880].forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, t + idx * 0.06);
      gain.gain.setValueAtTime(0.28, t + idx * 0.06);
      gain.gain.exponentialRampToValueAtTime(0.01, t + idx * 0.06 + 0.35);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t + idx * 0.06);
      osc.stop(t + idx * 0.06 + 0.35);
    });
  }
}

// =====================================================================
//  3. ACCURATE COORDINATE MAPPING (ASPECT-RATIO PRESERVING)
// =====================================================================

function getCameraTransform(video, canvasW, canvasH) {
  if (!video || !video.videoWidth || !video.videoHeight) {
    return { scale: 1, offsetX: 0, offsetY: 0, renderW: canvasW, renderH: canvasH };
  }
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  const canvasAspect = canvasW / canvasH;
  const videoAspect = vw / vh;

  let renderW, renderH, offsetX, offsetY;
  if (canvasAspect > videoAspect) {
    // Canvas is wider than video: scale to fit width, center vertically
    renderW = canvasW;
    renderH = canvasW / videoAspect;
    offsetX = 0;
    offsetY = (canvasH - renderH) / 2;
  } else {
    // Canvas is taller than video: scale to fit height, center horizontally
    renderH = canvasH;
    renderW = canvasH * videoAspect;
    offsetX = (canvasW - renderW) / 2;
    offsetY = 0;
  }
  return { scale: renderW / vw, offsetX, offsetY, renderW, renderH };
}

function mapNormalizedLandmark(tip, transform) {
  // tip.x is [0, 1] from left to right in camera sensor
  // Since we mirror the camera horizontally for natural interaction:
  const xMirrored = (1.0 - tip.x);
  const canvasX = transform.offsetX + xMirrored * transform.renderW;
  const canvasY = transform.offsetY + tip.y * transform.renderH;
  return { x: canvasX, y: canvasY };
}

// =====================================================================
//  4. MATH & CONTINUOUS COLLISION ENGINE (ARC RAYCASTING)
// =====================================================================

function distSegmentToPoint(p1, p2, p) {
  const x1 = p1.x, y1 = p1.y;
  const x2 = p2.x, y2 = p2.y;
  const px = p.x, py = p.y;
  const dx = x2 - x1, dy = y2 - y1;
  const segLenSq = dx * dx + dy * dy;

  if (segLenSq <= 1e-6) {
    return { dist: Math.hypot(px - x1, py - y1), proj: { x: x1, y: y1 }, t: 0.0 };
  }

  const t = Math.max(0.0, Math.min(1.0, ((px - x1) * dx + (py - y1) * dy) / segLenSq));
  const projX = x1 + t * dx;
  const projY = y1 + t * dy;
  const dist = Math.hypot(px - projX, py - projY);

  return { dist, proj: { x: projX, y: projY }, t };
}

class AdaptiveBladeFilter {
  constructor(minCutoff = 3.5, beta = 0.22) {
    this.xPrev = null;
    this.yPrev = null;
    this.dx = 0.0;
    this.dy = 0.0;
    this.tPrev = null;
    this.minCutoff = minCutoff;
    this.beta = beta;
  }

  filter(x, y, t) {
    if (this.xPrev === null || this.tPrev === null) {
      this.xPrev = x;
      this.yPrev = y;
      this.tPrev = t;
      return { x, y, speed: 0.0 };
    }

    const dt = Math.max(1e-4, t - this.tPrev);
    this.tPrev = t;

    const vx = (x - this.xPrev) / dt;
    const vy = (y - this.yPrev) / dt;

    this.dx = 0.65 * this.dx + 0.35 * vx;
    this.dy = 0.65 * this.dy + 0.35 * vy;
    const smoothSpeed = Math.hypot(this.dx, this.dy);

    // High-responsiveness low-latency 1 Euro filter
    const cutoff = this.minCutoff + this.beta * smoothSpeed;
    const tau = 1.0 / (2.0 * Math.PI * cutoff);
    let alpha = 1.0 / (1.0 + tau / dt);
    alpha = Math.min(1.0, Math.max(0.70, alpha));

    // Zero-lag 100% direct pass-through during any intentional movement or slice flick
    if (smoothSpeed > 220) alpha = 1.0;

    const xHat = alpha * x + (1.0 - alpha) * this.xPrev;
    const yHat = alpha * y + (1.0 - alpha) * this.yPrev;
    this.xPrev = xHat;
    this.yPrev = yHat;

    return { x: xHat, y: yHat, speed: smoothSpeed };
  }
}

class SliceDetector {
  constructor() {
    this.history = [];
    this.lastSliceTime = 0.0;
    this.cooldown = 0.18;
  }

  addSample(t, x, y, speed) {
    this.history.push({ t, x, y, speed });
    this.history = this.history.filter(p => t - p.t <= 0.40);
  }

  reset() {
    this.history = [];
    this.lastSliceTime = 0.0;
  }

  /**
   * Multi-Window Arc Raycasting Collision Engine:
   * Scans candidate sub-strokes from newest backwards, ensuring even rapid
   * 0.08s flicks are detected immediately without speed dilution.
   * Checks every sub-segment against the fruit's circular hitbox.
   */
  checkSlice(now, fruitCenter, fruitRadius, strict = 1.0) {
    if (now - this.lastSliceTime < this.cooldown) return null;
    if (this.history.length < 2) return null;

    const newest = this.history[this.history.length - 1];
    if (now - newest.t > 0.16) return null;

    const recent = this.history.filter(p => newest.t - p.t <= CONFIG.sliceWindow);
    if (recent.length < 2) return null;

    const minSpeed = CONFIG.minSliceSpeed * strict;
    const minDistance = CONFIG.minSliceDist * strict;
    const hitRadius = fruitRadius * CONFIG.hitboxMultiplier;

    // Scan from newest to oldest for the fastest valid slice segment
    for (let j = recent.length - 2; j >= 0; j--) {
      const p0 = recent[j];
      const dt = newest.t - p0.t;
      if (dt <= 0.01) continue;

      const strokeDist = Math.hypot(newest.x - p0.x, newest.y - p0.y);
      if (strokeDist < minDistance) continue;

      const avgSpeed = strokeDist / dt;
      let peakSpeed = avgSpeed;
      for (let k = j; k < recent.length; k++) {
        if (recent[k].speed > peakSpeed) peakSpeed = recent[k].speed;
      }

      if (avgSpeed < minSpeed && peakSpeed < minSpeed * 1.15) continue;

      // Path wobble check (generous for natural curved sword swings)
      let totalPath = 0.0;
      for (let k = j; k < recent.length - 1; k++) {
        totalPath += Math.hypot(recent[k+1].x - recent[k].x, recent[k+1].y - recent[k].y);
      }
      if (totalPath > CONFIG.maxWobble * strokeDist) continue;

      // Arc Continuous Raycasting across every sub-segment in this candidate stroke
      let bestHitDist = Infinity;
      let bestProj = null;
      let bestDir = null;

      for (let k = recent.length - 1; k > j; k--) {
        const pA = recent[k - 1];
        const pB = recent[k];
        const hitRes = distSegmentToPoint(pA, pB, fruitCenter);
        if (hitRes.dist < bestHitDist) {
          bestHitDist = hitRes.dist;
          bestProj = hitRes.proj;
          const segDist = Math.hypot(pB.x - pA.x, pB.y - pA.y) || 1;
          bestDir = { x: (pB.x - pA.x) / segDist, y: (pB.y - pA.y) / segDist };
        }
      }

      const isHit = bestHitDist <= hitRadius;
      const accuracyPct = Math.max(0, Math.min(100, (1.0 - (bestHitDist / hitRadius)) * 100));
      const cutOffset = bestProj ? {
        x: bestProj.x - fruitCenter.x,
        y: bestProj.y - fruitCenter.y
      } : { x: 0, y: 0 };

      if (isHit || j === 0) {
        this.lastSliceTime = now;
        return {
          hit: isHit,
          direction: bestDir || { x: (newest.x - p0.x) / strokeDist, y: (newest.y - p0.y) / strokeDist },
          peakSpeed: Math.max(peakSpeed, avgSpeed),
          avgSpeed,
          accuracy: accuracyPct,
          distToCenter: bestHitDist,
          cutOffset,
          startPt: p0,
          endPt: newest
        };
      }
    }
    return null;
  }
}

// =====================================================================
//  5. PROCEDURAL FRUITS & DUAL TARGET RENDERING
// =====================================================================

class Fruit {
  constructor(kindKey, x, y, owner = 'shared') {
    this.kindKey = kindKey;
    this.data = FRUITS[kindKey];
    this.x = x;
    this.y = y;
    this.owner = owner; // 'shared', 'p1', 'p2'
    this.state = 'whole';
    this.vy = 0;
    this.halves = [];
    this.particles = [];
    this.slash = null;
  }

  getCenter(now) {
    if (this.state === 'whole') {
      return { x: this.x, y: this.y + 8 * Math.sin(now * 2.5) };
    }
    return { x: this.x, y: this.y };
  }

  slice(direction, now, cutOffset = { x: 0, y: 0 }) {
    this.state = 'sliced';
    const c = this.getCenter(now);
    const r = CONFIG.fruitRadius;
    const nx = -direction.y;
    const ny = direction.x;
    const maxOff = r * 0.72;
    const ox = Math.max(-maxOff, Math.min(maxOff, cutOffset.x));
    const oy = Math.max(-maxOff, Math.min(maxOff, cutOffset.y));

    this.halves = [
      { side: 1, x: c.x, y: c.y, vx: 1 * nx * 320 + (Math.random() * 80 - 40), vy: 1 * ny * 320 - 160, angle: 0, spin: 1.5, direction, offset: { x: ox, y: oy } },
      { side: -1, x: c.x, y: c.y, vx: -1 * nx * 320 + (Math.random() * 80 - 40), vy: -1 * ny * 320 - 160, angle: 0, spin: -1.5, direction, offset: { x: ox, y: oy } }
    ];

    const cutCenterX = c.x + ox;
    const cutCenterY = c.y + oy;
    const colors = [this.data.flesh, this.data.skin, '#ffffff', '#ffd028'];

    for (let i = 0; i < 40; i++) {
      const side = Math.random() > 0.5 ? 1 : -1;
      const speed = Math.random() * 500 + 200;
      const angle = Math.atan2(side * ny, side * nx) + (Math.random() * 1.6 - 0.8);
      this.particles.push({
        x: cutCenterX, y: cutCenterY,
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 120,
        life: Math.random() * 0.6 + 0.4, maxLife: Math.random() * 0.6 + 0.4,
        radius: Math.random() * 5 + 3,
        color: colors[Math.floor(Math.random() * colors.length)]
      });
    }

    this.slash = { t: now, x: cutCenterX, y: cutCenterY, dx: direction.x, dy: direction.y };
  }

  update(dt) {
    if (this.state === 'sliced') {
      this.halves.forEach(h => {
        h.vy += CONFIG.gravity * dt;
        h.x += h.vx * dt;
        h.y += h.vy * dt;
        h.angle += h.spin * dt;
      });
      this.particles.forEach(p => {
        p.vy += CONFIG.gravity * 0.7 * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.life -= dt;
      });
      this.particles = this.particles.filter(p => p.life > 0);
    } else if (this.state === 'falling') {
      this.vy += CONFIG.gravity * dt;
      this.y += this.vy * dt;
    }
  }

  draw(ctx, now, isCutActive, isAimed = false) {
    const c = this.getCenter(now);
    const r = CONFIG.fruitRadius;

    if (this.state === 'whole' || this.state === 'falling') {
      this.drawWholeFruit(ctx, c.x, c.y, r);
      if (this.state === 'whole') {
        this.drawReticle(ctx, c.x, c.y, r, isCutActive, now, isAimed);
      }
    } else if (this.state === 'sliced') {
      this.halves.forEach(h => this.drawHalfFruit(ctx, h, r));
      this.particles.forEach(p => {
        const alpha = Math.max(0, p.life / p.maxLife);
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * alpha, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      });

      if (this.slash) {
        const age = now - this.slash.t;
        if (age < 0.25) {
          const fade = 1 - age / 0.25;
          const halfLen = r * 1.8;
          ctx.save();
          const slashGlow = this.owner === 'p2' ? 'rgba(255, 51, 102, 0.9)' : 'rgba(0, 240, 255, 0.9)';
          ctx.strokeStyle = slashGlow;
          ctx.lineWidth = 18 * fade;
          ctx.beginPath();
          ctx.moveTo(this.slash.x - this.slash.dx * halfLen, this.slash.y - this.slash.dy * halfLen);
          ctx.lineTo(this.slash.x + this.slash.dx * halfLen, this.slash.y + this.slash.dy * halfLen);
          ctx.stroke();

          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 6 * fade;
          ctx.stroke();
          ctx.restore();
        }
      }
    }
  }

  drawWholeFruit(ctx, cx, cy, r) {
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cx, cy + r * 0.85, r * 0.75, r * 0.2, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
    ctx.fill();

    const grad = ctx.createRadialGradient(cx - r * 0.25, cy - r * 0.25, r * 0.1, cx, cy, r);
    grad.addColorStop(0, this.data.flesh);
    grad.addColorStop(0.35, this.data.skin);
    grad.addColorStop(1, '#1a0408');

    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    ctx.ellipse(cx - r * 0.35, cy - r * 0.38, r * 0.28, r * 0.16, -Math.PI / 6, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.38)';
    ctx.fill();

    ctx.strokeStyle = '#50321e';
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(cx, cy - r * 0.9);
    ctx.quadraticCurveTo(cx + r * 0.1, cy - r * 1.3, cx + r * 0.2, cy - r * 1.25);
    ctx.stroke();

    ctx.fillStyle = '#46af3c';
    ctx.beginPath();
    ctx.ellipse(cx + r * 0.25, cy - r * 1.15, r * 0.35, r * 0.18, Math.PI / 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  drawReticle(ctx, cx, cy, r, isCutActive, now, isAimed) {
    ctx.save();
    const auraColor = isAimed ? (this.owner === 'p2' ? '#ff3366' : '#00f0ff') : 'rgba(255, 255, 255, 0.25)';

    // Circular aim bounds
    ctx.strokeStyle = auraColor;
    ctx.lineWidth = isAimed ? 3.5 : 2;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();

    // Bullseye center (100% accuracy sweet spot)
    ctx.strokeStyle = isAimed ? '#ffd028' : 'rgba(255, 208, 40, 0.65)';
    ctx.lineWidth = isAimed ? 3 : 2;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.28, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(cx, cy, 4, 0, Math.PI * 2);
    ctx.fill();

    // Player owner label in split dual mode
    if (this.owner !== 'shared') {
      ctx.fillStyle = this.owner === 'p1' ? '#00f0ff' : '#ff3366';
      ctx.font = 'bold 16px Orbitron, monospace';
      ctx.textAlign = 'center';
      const labelText = isAimed ? (this.owner === 'p1' ? '🎯 P1 AIM LOCKED!' : '🎯 P2 AIM LOCKED!') : (this.owner === 'p1' ? 'P1 TARGET' : 'P2 TARGET');
      ctx.fillText(labelText, cx, cy - r - 15);
    }

    if (isCutActive) {
      const pulse = r + 24 + 10 * Math.sin(now * 24);
      ctx.strokeStyle = '#ffd028';
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
      ctx.stroke();

      ctx.strokeStyle = this.owner === 'p2' ? '#ff3366' : '#00f0ff';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(cx, cy, pulse + 8, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  drawHalfFruit(ctx, half, r) {
    ctx.save();
    ctx.translate(half.x, half.y);
    ctx.rotate(half.angle);

    const cutDir = half.direction;
    const nx = -cutDir.y;
    const ny = cutDir.x;
    const side = half.side;
    const ox = half.offset.x;
    const oy = half.offset.y;

    ctx.save();
    ctx.beginPath();
    const len = r * 3;
    ctx.moveTo(ox + cutDir.x * len, oy + cutDir.y * len);
    ctx.lineTo(ox - cutDir.x * len, oy - cutDir.y * len);
    ctx.lineTo(ox - cutDir.x * len + side * nx * len, oy - cutDir.y * len + side * ny * len);
    ctx.lineTo(ox + cutDir.x * len + side * nx * len, oy + cutDir.y * len + side * ny * len);
    ctx.closePath();
    ctx.clip();

    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fillStyle = this.data.skin;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, 0, r * 0.88, 0, Math.PI * 2);
    ctx.fillStyle = this.data.flesh;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, 0, r * 0.32, 0, Math.PI * 2);
    ctx.fillStyle = this.data.core;
    ctx.fill();

    for (let i = 0; i < 6; i++) {
      const angle = (i * 60 + 15) * Math.PI / 180;
      ctx.beginPath();
      ctx.ellipse(Math.cos(angle) * r * 0.45, Math.sin(angle) * r * 0.45, 5, 8, angle, 0, Math.PI * 2);
      ctx.fillStyle = this.data.seed;
      ctx.fill();
    }
    ctx.restore();
    ctx.restore();
  }
}

// Target Blitz Targets
class BlitzTarget {
  constructor(id, x, y, radius, duration, player = 'p1') {
    this.id = id;
    this.x = x;
    this.y = y;
    this.radius = radius;
    this.duration = duration;
    this.player = player;
    this.createdAt = performance.now() / 1000;
    this.color = player === 'p1' ? '#00f0ff' : '#ff3366';
  }

  update(now) {
    const age = now - this.createdAt;
    return age < this.duration;
  }

  draw(ctx, now) {
    const age = now - this.createdAt;
    const progress = Math.max(0, 1 - age / this.duration);

    ctx.save();
    ctx.strokeStyle = this.color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius + 10 * progress, 0, Math.PI * 2);
    ctx.stroke();

    const grad = ctx.createRadialGradient(this.x, this.y, 2, this.x, this.y, this.radius);
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.5, this.color);
    grad.addColorStop(1, 'rgba(0,0,0,0.8)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

// Ninja Deflect Projectiles
class Shuriken {
  constructor(id, x, y, vx, vy, radius = 28) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.vx = vx;
    this.vy = vy;
    this.radius = radius;
    this.angle = 0;
    this.spin = 12;
  }

  update(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
    this.angle += this.spin * dt;
    return this.y < CONFIG.windowH + 50 && this.x > -50 && this.x < CONFIG.windowW + 50;
  }

  draw(ctx) {
    ctx.save();
    ctx.translate(this.x, this.y);
    ctx.rotate(this.angle);

    ctx.fillStyle = '#ff8800';
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      ctx.rotate(Math.PI / 2);
      ctx.lineTo(this.radius, 0);
      ctx.lineTo(this.radius * 0.35, this.radius * 0.35);
    }
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#0a0d14';
    ctx.beginPath();
    ctx.arc(0, 0, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

// =====================================================================
//  5B. BALLOON ARCHER ENGINE (PRECISION BOW & PROJECTILES)
// =====================================================================

function segHitsCircle(ax, ay, bx, by, cx, cy, r) {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((cx - ax) * dx + (cy - ay) * dy) / len2));
  const px = ax + dx * t;
  const py = ay + dy * t;
  return Math.hypot(cx - px, cy - py) <= r;
}

class Balloon {
  constructor(id, x, y, radius, color, vx = 0, phase = 0, owner = 'shared') {
    this.id = id;
    this.x = x;
    this.y = y;
    this.y0 = y;
    this.radius = radius;
    this.color = color;
    this.vx = vx;
    this.phase = phase;
    this.owner = owner;
    this.alive = true;
  }

  update(now, dt, minX = 60, maxX = CONFIG.windowW - 60) {
    if (!this.alive) return;
    this.x += this.vx * dt;
    if (this.x < minX) {
      this.x = minX;
      this.vx = Math.abs(this.vx);
    } else if (this.x > maxX) {
      this.x = maxX;
      this.vx = -Math.abs(this.vx);
    }
    this.y = this.y0 + 10 * Math.sin(now * 2.0 + this.phase);
  }

  draw(ctx, now) {
    if (!this.alive) return;
    const x = this.x;
    const y = this.y;
    const r = this.radius;

    ctx.save();
    // String
    ctx.strokeStyle = 'rgba(240, 240, 255, 0.6)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, y + r * 1.15);
    for (let k = 1; k <= 7; k++) {
      ctx.lineTo(x + 5 * Math.sin(k * 0.9 + now * 3 + this.phase), y + r * 1.15 + k * 8);
    }
    ctx.stroke();

    // 3D Spherical Radial Gradient highlight
    const grad = ctx.createRadialGradient(x - r * 0.32, y - r * 0.35, 3, x, y, r * 1.1);
    grad.addColorStop(0, '#ffffff');
    grad.addColorStop(0.35, this.color);
    grad.addColorStop(1, 'rgba(10, 15, 25, 0.85)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.ellipse(x, y, r * 0.88, r * 1.08, 0, 0, Math.PI * 2);
    ctx.fill();

    // Gloss Specular Reflection Oval
    ctx.fillStyle = 'rgba(255, 255, 255, 0.65)';
    ctx.beginPath();
    ctx.ellipse(x - r * 0.35, y - r * 0.40, r * 0.22, r * 0.35, -Math.PI / 6, 0, Math.PI * 2);
    ctx.fill();

    // Tie Knot
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.moveTo(x, y + r * 1.05);
    ctx.lineTo(x - 6, y + r * 1.15);
    ctx.lineTo(x + 6, y + r * 1.15);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
  }
}

class Arrow {
  constructor(id, x, y, dx, dy, speed, player = 'p1', length = 85) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.dx = dx;
    this.dy = dy;
    this.speed = speed;
    this.player = player;
    this.length = length;
    this.alive = true;
    this.trail = [];
  }

  update(dt) {
    if (!this.alive) return false;
    this.trail.push({ x: this.x, y: this.y, t: performance.now() });
    if (this.trail.length > 8) this.trail.shift();

    this.x += this.dx * this.speed * dt;
    this.y += this.dy * this.speed * dt;

    if (this.x < -100 || this.x > CONFIG.windowW + 100 || this.y < -100 || this.y > CONFIG.windowH + 100) {
      this.alive = false;
      return false;
    }
    return true;
  }

  getTail() {
    return {
      x: this.x - this.dx * this.length,
      y: this.y - this.dy * this.length
    };
  }

  draw(ctx) {
    if (!this.alive) return;
    const tip = { x: this.x, y: this.y };
    const tail = this.getTail();
    const px = -this.dy;
    const py = this.dx;

    ctx.save();
    // Smoke / Energy trail
    this.trail.forEach((pt, i) => {
      const alpha = (i / this.trail.length) * 0.4;
      ctx.fillStyle = this.player === 'p1' ? `rgba(0, 240, 255, ${alpha})` : `rgba(255, 60, 60, ${alpha})`;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 3 * (i / this.trail.length), 0, Math.PI * 2);
      ctx.fill();
    });

    // Arrow Shaft (Ash Wood)
    ctx.strokeStyle = '#c8a46e';
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(tail.x, tail.y);
    ctx.lineTo(tip.x, tip.y);
    ctx.stroke();

    // Steel Arrowhead
    const headLen = 18;
    const headWidth = 7;
    const b1x = tip.x - this.dx * headLen + px * headWidth;
    const b1y = tip.y - this.dy * headLen + py * headWidth;
    const b2x = tip.x - this.dx * headLen - px * headWidth;
    const b2y = tip.y - this.dy * headLen - py * headWidth;

    ctx.fillStyle = '#e8ecf2';
    ctx.strokeStyle = '#1e2530';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(tip.x, tip.y);
    ctx.lineTo(b1x, b1y);
    ctx.lineTo(tip.x - this.dx * (headLen * 0.65), tip.y - this.dy * (headLen * 0.65));
    ctx.lineTo(b2x, b2y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Feathers / Fletching
    const featherCol = this.player === 'p1' ? '#00f0ff' : '#ff3366';
    ctx.strokeStyle = featherCol;
    ctx.lineWidth = 3;
    for (const s of [-1, 1]) {
      const f0x = tail.x + this.dx * 8;
      const f0y = tail.y + this.dy * 8;
      const f1x = tail.x - this.dx * 4 + px * 8 * s;
      const f1y = tail.y - this.dy * 4 + py * 8 * s;
      ctx.beginPath();
      ctx.moveTo(f0x, f0y);
      ctx.lineTo(f1x, f1y);
      ctx.stroke();
    }

    ctx.restore();
  }
}

class Bow {
  constructor(player = 'p1') {
    this.player = player;
    this.color = player === 'p1' ? '#00f0ff' : '#ff3366';
    this.woodColor = player === 'p1' ? '#a5682a' : '#883a20';
    this.palm = null;
    this.aim = { x: 0, y: -1 };
    this.anchor = null;
    this.origin = null;
    this.drawAmount = 0.0;
    this.peakDraw = 0.0;
    this.fullSince = null;
    this.lockedUntil = 0.0;
    this.lastSeen = 0.0;
    this.aimHist = [];

    this.bowForward = 45;
    this.bowHalf = 75;
    this.bowBend = 35;
    this.drawDistance = 125;
    this.drawRate = 1.35;
    this.minDraw = 0.28;
    this.fullHold = 0.35;
    this.releaseDrop = 0.18;
    this.arrowSpeedRange = [580, 1250];
    this.arrowLen = 85;
    this.reloadTime = 0.35;
  }

  update(rawPalm, rawAim, now, dt, canShoot = true) {
    if (rawPalm) {
      if (!this.palm || now - this.lastSeen > 0.5) {
        this.palm = { x: rawPalm.x, y: rawPalm.y };
        this.aim = { x: rawAim.x, y: rawAim.y };
        this.anchor = null;
      } else {
        const kp = 0.72;
        const ka = 0.55;
        this.palm.x += (rawPalm.x - this.palm.x) * kp;
        this.palm.y += (rawPalm.y - this.palm.y) * kp;

        const nx = this.aim.x * (1 - ka) + rawAim.x * ka;
        const ny = this.aim.y * (1 - ka) + rawAim.y * ka;
        const d = Math.hypot(nx, ny);
        if (d > 1e-5) {
          this.aim = { x: nx / d, y: ny / d };
        }
      }
      this.lastSeen = now;
      this.aimHist.push({ t: now, aim: { ...this.aim } });
    }

    this.aimHist = this.aimHist.filter(h => now - h.t <= 0.5);

    if (!this.palm || now - this.lastSeen > 0.5) {
      this.palm = null;
      this.anchor = null;
      this.origin = null;
      this.drawAmount = 0;
      this.peakDraw = 0;
      this.fullSince = null;
      return null;
    }

    if (!this.anchor) {
      this.anchor = { ...this.palm };
      this.origin = { ...this.palm };
    }

    if (now < this.lockedUntil) {
      this.anchor = { ...this.palm };
      this.origin = { ...this.palm };
      this.drawAmount = 0;
      this.peakDraw = 0;
      this.fullSince = null;
      return null;
    }

    const pulled = (this.anchor.x - this.palm.x) * this.aim.x + (this.anchor.y - this.palm.y) * this.aim.y;
    const target = Math.min(1.0, Math.max(0.0, pulled / this.drawDistance));

    if (target < 0.08 && this.drawAmount < 0.08 && this.peakDraw < 0.08) {
      const k = Math.min(1.0, dt / 0.35);
      this.anchor.x += (this.palm.x - this.anchor.x) * k;
      this.anchor.y += (this.palm.y - this.anchor.y) * k;
      this.origin = { ...this.palm };
    }

    if (target > this.drawAmount) {
      this.drawAmount = Math.min(target, this.drawAmount + this.drawRate * dt);
    } else {
      this.drawAmount = target;
    }

    if (this.drawAmount >= 0.08) {
      this.peakDraw = Math.max(this.peakDraw, this.drawAmount);
    }

    let shot = null;
    if (canShoot && this.peakDraw >= this.minDraw) {
      let released = false;
      if (this.drawAmount <= this.peakDraw - this.releaseDrop) {
        released = true;
      } else if (this.drawAmount >= 0.97) {
        if (this.fullSince === null) {
          this.fullSince = now;
        } else if (now - this.fullSince >= this.fullHold) {
          released = true;
        }
      } else {
        this.fullSince = null;
      }

      if (!rawPalm && now - this.lastSeen > 0.12) {
        released = true;
      }

      if (released) {
        const older = this.aimHist.filter(h => now - h.t >= 0.08);
        const shotAim = older.length > 0 ? older[older.length - 1].aim : this.aim;
        const power = this.peakDraw;
        const geom = this.getGeometry(power);
        const tip = {
          x: geom.nock.x + shotAim.x * this.arrowLen,
          y: geom.nock.y + shotAim.y * this.arrowLen
        };
        const speed = this.arrowSpeedRange[0] + (this.arrowSpeedRange[1] - this.arrowSpeedRange[0]) * power;

        shot = {
          tip,
          aim: shotAim,
          power,
          speed,
          player: this.player
        };

        this.drawAmount = 0.0;
        this.peakDraw = 0.0;
        this.fullSince = null;
        this.lockedUntil = now + this.reloadTime;
        this.anchor = { ...this.palm };
        this.origin = { ...this.palm };
      }
    }

    if (!shot && this.drawAmount < 0.05) {
      this.peakDraw = 0.0;
      this.fullSince = null;
    }

    return shot;
  }

  getGeometry(drawVal = this.drawAmount) {
    const origin = this.origin || this.palm || { x: 0, y: 0 };
    const ax = this.aim.x;
    const ay = this.aim.y;
    const px = -ay;
    const py = ax;
    const cx = origin.x + ax * this.bowForward;
    const cy = origin.y + ay * this.bowForward;

    const limb = [];
    for (let k = 0; k <= 12; k++) {
      const t = -1 + k / 6.0;
      limb.push({
        x: cx + px * this.bowHalf * t - ax * this.bowBend * t * t,
        y: cy + py * this.bowHalf * t - ay * this.bowBend * t * t
      });
    }

    const restX = cx - ax * this.bowBend;
    const restY = cy - ay * this.bowBend;
    const nock = {
      x: restX - ax * 95 * drawVal,
      y: restY - ay * 95 * drawVal
    };

    return { limb, nock, cx, cy };
  }

  draw(ctx, ready = true) {
    if (!this.palm) return;
    const geom = this.getGeometry();
    const limb = geom.limb;
    const nock = geom.nock;

    ctx.save();
    // Bow limb shadow
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.6)';
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.moveTo(limb[0].x + 3, limb[0].y + 3);
    for (let i = 1; i < limb.length; i++) ctx.lineTo(limb[i].x + 3, limb[i].y + 3);
    ctx.stroke();

    // Bow limb wood
    ctx.strokeStyle = this.woodColor;
    ctx.lineWidth = 7;
    ctx.beginPath();
    ctx.moveTo(limb[0].x, limb[0].y);
    for (let i = 1; i < limb.length; i++) ctx.lineTo(limb[i].x, limb[i].y);
    ctx.stroke();

    // Metallic accents
    ctx.strokeStyle = this.color;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Bowstring
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(limb[0].x, limb[0].y);
    ctx.lineTo(nock.x, nock.y);
    ctx.lineTo(limb[limb.length - 1].x, limb[limb.length - 1].y);
    ctx.stroke();

    if (ready) {
      const arrowTip = {
        x: nock.x + this.aim.x * this.arrowLen,
        y: nock.y + this.aim.y * this.arrowLen
      };

      ctx.strokeStyle = '#c8a46e';
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.moveTo(nock.x, nock.y);
      ctx.lineTo(arrowTip.x, arrowTip.y);
      ctx.stroke();

      ctx.fillStyle = '#e8ecf2';
      ctx.beginPath();
      ctx.arc(arrowTip.x, arrowTip.y, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Aiming laser dots
      if (this.drawAmount > 0.08) {
        const numDots = Math.min(18, Math.floor(4 + this.drawAmount * 14));
        for (let k = 1; k <= numDots; k++) {
          const dx = arrowTip.x + this.aim.x * (36 * k);
          const dy = arrowTip.y + this.aim.y * (36 * k);
          const alpha = 1.0 - (k / (numDots + 1)) * 0.7;
          ctx.fillStyle = this.player === 'p1' ? `rgba(0, 240, 255, ${alpha})` : `rgba(255, 60, 60, ${alpha})`;
          ctx.beginPath();
          ctx.arc(dx, dy, 3.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    // Power gauge ring
    const ringRadius = 38;
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(this.palm.x, this.palm.y, ringRadius, 0, Math.PI * 2);
    ctx.stroke();

    if (this.drawAmount > 0.02) {
      const ringColor = this.drawAmount >= 0.95 ? '#10f084' : (this.drawAmount >= this.minDraw ? '#ffd028' : '#00f0ff');
      ctx.strokeStyle = ringColor;
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.arc(this.palm.x, this.palm.y, ringRadius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * this.drawAmount);
      ctx.stroke();

      ctx.fillStyle = ringColor;
      ctx.font = 'bold 12px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${Math.round(this.drawAmount * 100)}%`, this.palm.x, this.palm.y);
    }

    ctx.restore();
  }
}

// =====================================================================
//  6. MULTIPLAYER WEBSOCKET CLIENT (2 LAPTOPS)
// =====================================================================

class MultiplayerClient {
  constructor(onEvent) {
    this.onEvent = onEvent;
    this.ws = null;
    this.role = null;
    this.roomId = null;
    this.connected = false;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.connected = true;
      this.onEvent({ type: 'connected' });

      const params = new URLSearchParams(window.location.search);
      const roomParam = params.get('room');
      if (roomParam) {
        this.joinRoom(roomParam);
      }
    };

    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        this.onEvent(msg);
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.onEvent({ type: 'disconnected' });
    };
  }

  createRoom(game = 'slice', targetWins = 5) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'create-room', game, targetWins }));
  }

  joinRoom(roomId) {
    if (!this.connected) return;
    this.roomId = roomId.toUpperCase();
    this.ws.send(JSON.stringify({ type: 'join-room', roomId: this.roomId }));
  }

  startMatch(targetWins = 5) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'start-match', targetWins }));
  }

  startRound(fruitKind, waitTime) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'start-round', fruitKind, waitTime }));
  }

  signalCut() {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'signal-cut' }));
  }

  sendSliceAttempt(data) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'slice-attempt', ...data }));
  }

  sendTargetHit(targetId, points = 1) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'target-hit', targetId, points }));
  }

  syncBlade(point, speed) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-blade', point, speed }));
  }

  shootArrow(arrow) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'shoot-arrow', arrow }));
  }

  syncBow(bow) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-bow', bow }));
  }

  popBalloon(balloonIndex, points = 1) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'pop-balloon', balloonIndex, points }));
  }

  syncBalloons(balloons, round) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-balloons', balloons, round }));
  }

  throwBasketball(ball) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'throw-basketball', ball }));
  }

  scoreBasketball(points = 2) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'basketball-scored', points }));
  }

  squirtMilk(fill, squirtY) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'milk-squirt', fill, squirtY }));
  }

  finishCow(timeElapsed) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'cow-finished', timeElapsed }));
  }

  paintStroke(stroke, coverage) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'paint-stroke', stroke, coverage }));
  }

  finishPaint(timeElapsed) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'paint-finished', timeElapsed }));
  }

  syncCatchBasket(x, y, w) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-catch-basket', x, y, w }));
  }

  syncCatchFruits(fruits) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-catch-fruits', fruits }));
  }

  catchFruitScored(fruitId, points = 1) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'catch-fruit-scored', fruitId, points }));
  }

  syncPoseChallenge(pose) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-pose-challenge', pose }));
  }

  syncPoseScore(score, rating) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'sync-pose-score', score, rating }));
  }

  poseRoundComplete(winnerRole, p1Score, p2Score) {
    if (!this.connected) return;
    this.ws.send(JSON.stringify({ type: 'pose-round-complete', winnerRole, p1Score, p2Score }));
  }
}

// =====================================================================
//  7. MAIN GAME CONTROLLER & PRECISION ARENA
// =====================================================================

class GameArena {
  constructor() {
    this.canvas = document.getElementById('gameCanvas');
    this.ctx = this.canvas.getContext('2d');
    this.video = document.getElementById('webcam');

    // UI Elements
    this.gameSelect = document.getElementById('gameSelect');
    this.tabSolo = document.getElementById('tabSolo');
    this.tabDualLocal = document.getElementById('tabDualLocal');
    this.tabDualOnline = document.getElementById('tabDualOnline');

    this.trackingBadge = document.getElementById('trackingBadge');
    this.trackingText = document.getElementById('trackingText');
    this.roomBadge = document.getElementById('roomBadge');
    this.roomBadgeText = document.getElementById('roomBadgeText');

    this.dualScoreboard = document.getElementById('dualScoreboard');
    this.p1ScoreEl = document.getElementById('p1Score');
    this.p2ScoreEl = document.getElementById('p2Score');
    this.targetWinsLabel = document.getElementById('targetWinsLabel');

    this.speedoP1 = document.getElementById('speedoP1');
    this.speedP1Value = document.getElementById('speedP1Value');
    this.speedoP1Fill = document.getElementById('speedoP1Fill');

    this.speedoP2 = document.getElementById('speedoP2');
    this.speedP2Value = document.getElementById('speedP2Value');
    this.speedoP2Fill = document.getElementById('speedoP2Fill');

    this.bannerTitle = document.getElementById('bannerTitle');
    this.bannerSubtitle = document.getElementById('bannerSubtitle');
    this.actionPrompt = document.getElementById('actionPrompt');
    this.practiceTag = document.getElementById('practiceTag');

    this.resultModal = document.getElementById('resultModal');
    this.soloResultGrid = document.getElementById('soloResultGrid');
    this.dualResultGrid = document.getElementById('dualResultGrid');
    this.dualWinnerAnnounce = document.getElementById('dualWinnerAnnounce');
    this.dualRoundStats = document.getElementById('dualRoundStats');
    this.soloRankBox = document.getElementById('soloRankBox');
    this.btnNextRound = document.getElementById('btnNextRound');

    this.multiplayerModal = document.getElementById('multiplayerModal');
    this.btnCloseMultiplayer = document.getElementById('btnCloseMultiplayer');
    this.tabHostRoom = document.getElementById('tabHostRoom');
    this.tabJoinRoom = document.getElementById('tabJoinRoom');
    this.hostSection = document.getElementById('hostSection');
    this.joinSection = document.getElementById('joinSection');
    this.btnCreateRoom = document.getElementById('btnCreateRoom');
    this.roomShareInfo = document.getElementById('roomShareInfo');
    this.displayRoomCode = document.getElementById('displayRoomCode');
    this.shareUrlInput = document.getElementById('shareUrlInput');
    this.btnCopyLink = document.getElementById('btnCopyLink');
    this.guestWaitStatus = document.getElementById('guestWaitStatus');
    this.btnStartOnlineMatch = document.getElementById('btnStartOnlineMatch');
    this.targetWinsSelect = document.getElementById('targetWinsSelect');
    this.joinRoomCodeInput = document.getElementById('joinRoomCodeInput');
    this.btnJoinRoomSubmit = document.getElementById('btnJoinRoomSubmit');
    this.joinStatusText = document.getElementById('joinStatusText');

    this.settingsModal = document.getElementById('settingsModal');
    this.btnSettings = document.getElementById('btnSettings');
    this.btnCloseSettings = document.getElementById('btnCloseSettings');
    this.btnSound = document.getElementById('btnSound');
    this.iconSoundOn = document.getElementById('iconSoundOn');
    this.iconSoundOff = document.getElementById('iconSoundOff');
    this.btnFullscreen = document.getElementById('btnFullscreen');

    this.inputModeSelect = document.getElementById('inputMode');
    this.dualTargetModeSelect = document.getElementById('dualTargetMode');
    this.speedSensInput = document.getElementById('speedSens');
    this.speedSensVal = document.getElementById('speedSensVal');
    this.hitboxScaleInput = document.getElementById('hitboxScale');
    this.hitboxScaleVal = document.getElementById('hitboxScaleVal');
    this.toggleCameraBg = document.getElementById('toggleCameraBg');
    this.toggleDebug = document.getElementById('toggleDebug');

    this.sounds = new WebSoundManager();
    this.multiplayer = new MultiplayerClient(this.handleMultiplayerEvent.bind(this));

    // Player 1 Engine
    this.filterP1 = new AdaptiveBladeFilter();
    this.detectorP1 = new SliceDetector();
    this.p1Point = null;
    this.p1Speed = 0;

    // Player 2 Engine
    this.filterP2 = new AdaptiveBladeFilter();
    this.detectorP2 = new SliceDetector();
    this.p2Point = null;
    this.p2Speed = 0;

    // Persistent Hand Position & Direction History (prevents identity swapping)
    this.p1LastSeen = null;
    this.p2LastSeen = null;
    this.p1TrackedPos = null;
    this.p2TrackedPos = null;
    this.p1FingerDir = { x: 0, y: -1 };
    this.p2FingerDir = { x: 0, y: -1 };

    // Game modes & state
    this.currentGame = 'slice';
    this.playMode = 'solo';
    this.state = 'TITLE';
    this.stateStart = 0;
    this.waitTime = 3.0;
    this.cutTime = 0.0;
    this.targetWins = 5;
    this.scores = { p1: 0, p2: 0 };
    this.stats = { rounds: 0, wins: 0, best: null };

    // Fruits: Solo has 1 fruit; Local Dual has 2 split fruits (P1 Left, P2 Right)
    this.fruitP1 = new Fruit('apple', CONFIG.windowW / 2, CONFIG.windowH / 2 + 25, 'p1');
    this.fruitP2 = new Fruit('orange', CONFIG.windowW / 2, CONFIG.windowH / 2 + 25, 'p2');

    // Target Blitz
    this.blitzTargets = [];
    this.lastTargetSpawn = 0;
    this.targetIdCounter = 0;

    // Ninja Deflect
    this.shurikens = [];
    this.lastShurikenSpawn = 0;
    this.shurikenLives = 3;

    // Balloon Archer
    this.bowP1 = new Bow('p1');
    this.bowP2 = new Bow('p2');
    this.balloons = [];
    this.arrows = [];
    this.archeryParticles = [];
    this.archeryFloaters = [];
    this.archeryRound = 1;
    this.archeryArrowsLeft = 7;
    this.archeryScore = 0;

    // Additional Arcade Games Suite
    this.hoopGame = new HoopGame(this);
    this.cowGame = new CowGame(this);
    this.painterGame = new PainterGame(this);
    this.catchGame = new CatchGame(this);
    this.poseGame = new PoseGame(this, 'yoga');
    this.lastPoseLandmarks = null;
    this.faceModel = null;
    this.poseModel = null;

    this.cameraBg = true;
    this.debugOverlay = false;
    this.lastFrameTime = performance.now();
    this.fps = 60;
    this.cameraTransform = { scale: 1, offsetX: 0, offsetY: 0, renderW: CONFIG.windowW, renderH: CONFIG.windowH };

    this.initCanvasSize();
    this.bindEvents();
    this.initMediaPipe();
    this.multiplayer.connect();

    this.loop = this.loop.bind(this);
    requestAnimationFrame(this.loop);
  }

  initCanvasSize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.0); // Lock DPR to 1.0 for instant 60 FPS
    this.canvas.width = window.innerWidth * dpr;
    this.canvas.height = window.innerHeight * dpr;
    if (dpr !== 1) {
      this.ctx.scale(dpr, dpr);
    }

    CONFIG.windowW = window.innerWidth;
    CONFIG.windowH = window.innerHeight;
    this.cameraTransform = getCameraTransform(this.video, CONFIG.windowW, CONFIG.windowH);
    this.resetFruitPositions();
  }

  resetFruitPositions() {
    if (this.playMode === 'local' && CONFIG.dualFruitMode === 'split') {
      // Split mode: Left target for P1, Right target for P2!
      this.fruitP1.x = CONFIG.windowW * 0.28;
      this.fruitP1.y = CONFIG.windowH / 2 + 25;
      this.fruitP1.owner = 'p1';

      this.fruitP2.x = CONFIG.windowW * 0.72;
      this.fruitP2.y = CONFIG.windowH / 2 + 25;
      this.fruitP2.owner = 'p2';
    } else {
      // Solo or shared center fruit
      this.fruitP1.x = CONFIG.windowW / 2;
      this.fruitP1.y = CONFIG.windowH / 2 + 25;
      this.fruitP1.owner = 'shared';
    }
  }

  bindEvents() {
    window.addEventListener('resize', () => this.initCanvasSize());

    this.gameSelect.addEventListener('change', (e) => this.setGame(e.target.value));

    [this.tabSolo, this.tabDualLocal, this.tabDualOnline].forEach(tab => {
      tab.addEventListener('click', (e) => this.setPlayMode(e.target.dataset.mode));
    });

    window.addEventListener('keydown', (e) => {
      this.sounds.init();
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault();
        this.handleStartAction();
      } else if (e.code === 'KeyD') {
        this.debugOverlay = !this.debugOverlay;
        this.toggleDebug.checked = this.debugOverlay;
      }
    });

    // Mouse / Touch fallback
    this.canvas.addEventListener('mousemove', (e) => {
      if (this.inputModeSelect.value !== 'camera') {
        const now = performance.now() / 1000;
        const res = this.filterP1.filter(e.clientX, e.clientY, now);
        this.p1Point = { x: res.x, y: res.y };
        this.p1Speed = res.speed;
        this.detectorP1.addSample(now, res.x, res.y, res.speed);

        if (this.playMode === 'online') {
          this.multiplayer.syncBlade(this.p1Point, this.p1Speed);
        }
      }
    });

    this.actionPrompt.addEventListener('click', () => {
      this.sounds.init();
      this.handleStartAction();
    });

    this.btnNextRound.addEventListener('click', () => this.handleStartAction());

    this.btnSettings.addEventListener('click', () => this.settingsModal.classList.remove('hidden'));
    this.btnCloseSettings.addEventListener('click', () => this.settingsModal.classList.add('hidden'));

    this.btnSound.addEventListener('click', () => {
      this.sounds.init();
      this.sounds.enabled = !this.sounds.enabled;
      this.iconSoundOn.style.display = this.sounds.enabled ? 'block' : 'none';
      this.iconSoundOff.style.display = this.sounds.enabled ? 'none' : 'block';
    });

    this.btnFullscreen.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });

    this.tabHostRoom.addEventListener('click', () => {
      this.tabHostRoom.classList.add('active');
      this.tabJoinRoom.classList.remove('active');
      this.hostSection.classList.remove('hidden');
      this.joinSection.classList.add('hidden');
    });

    this.tabJoinRoom.addEventListener('click', () => {
      this.tabJoinRoom.classList.add('active');
      this.tabHostRoom.classList.remove('active');
      this.joinSection.classList.remove('hidden');
      this.hostSection.classList.add('hidden');
    });

    this.btnCloseMultiplayer.addEventListener('click', () => {
      this.multiplayerModal.classList.add('hidden');
    });

    this.btnCreateRoom.addEventListener('click', () => {
      this.targetWins = parseInt(this.targetWinsSelect.value);
      this.multiplayer.createRoom(this.currentGame, this.targetWins);
    });

    this.btnCopyLink.addEventListener('click', () => {
      navigator.clipboard.writeText(this.shareUrlInput.value).then(() => {
        this.btnCopyLink.textContent = '✅ LINK COPIED!';
        setTimeout(() => { this.btnCopyLink.textContent = '📋 COPY LINK'; }, 2000);
      });
    });

    this.btnStartOnlineMatch.addEventListener('click', () => {
      this.multiplayerModal.classList.add('hidden');
      this.multiplayer.startMatch(this.targetWins);
    });

    this.btnJoinRoomSubmit.addEventListener('click', () => {
      let code = this.joinRoomCodeInput.value.trim();
      if (code.includes('?room=')) {
        code = new URL(code).searchParams.get('room') || code;
      }
      if (code) {
        this.multiplayer.joinRoom(code);
        this.joinStatusText.textContent = `Connecting to ${code}...`;
      }
    });

    this.speedSensInput.addEventListener('input', (e) => {
      CONFIG.minSliceSpeed = parseFloat(e.target.value);
      this.speedSensVal.textContent = `${CONFIG.minSliceSpeed.toFixed(0)} px/s`;
    });

    this.hitboxScaleInput.addEventListener('input', (e) => {
      CONFIG.hitboxMultiplier = parseFloat(e.target.value);
      this.hitboxScaleVal.textContent = `${CONFIG.hitboxMultiplier.toFixed(2)}x`;
    });

    if (this.dualTargetModeSelect) {
      this.dualTargetModeSelect.addEventListener('change', (e) => {
        CONFIG.dualFruitMode = e.target.value;
        this.resetFruitPositions();
      });
    }

    this.toggleCameraBg.addEventListener('change', (e) => {
      this.cameraBg = e.target.checked;
    });

    this.toggleDebug.addEventListener('change', (e) => {
      this.debugOverlay = e.target.checked;
    });
  }

  setGame(game) {
    this.currentGame = game;
    this.gameSelect.value = game;
    this.state = 'TITLE';
    this.resultModal.classList.add('hidden');
    this.actionPrompt.style.display = 'block';

    if (game === 'slice') {
      this.bannerTitle.textContent = 'FRUIT SLICE';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Left Fruit (P1) vs Right Fruit (P2)' : 'Reflex & Accuracy Duel';
      this.resetFruitPositions();
    } else if (game === 'archery') {
      this.bannerTitle.textContent = 'BALLOON ARCHER';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Dual Bows: P1 (Cyan) vs P2 (Red)!' : 'Hand-Tracked Bow & Arrow Reflex Challenge';
      this.archeryRound = 1;
      this.archeryArrowsLeft = 7;
      this.archeryScore = 0;
      this.arrows = [];
      this.spawnBalloons(1);
      this.practiceTag.textContent = '🏹 Aim with fingers, pull hand back slowly to bend bow, and release to shoot!';
    } else if (game === 'blitz') {
      this.bannerTitle.textContent = 'TARGET BLITZ';
      this.bannerSubtitle.textContent = 'High-Speed Cardio Strike';
      this.blitzTargets = [];
    } else if (game === 'deflect') {
      this.bannerTitle.textContent = 'NINJA DEFLECT';
      this.bannerSubtitle.textContent = 'Blade Shield Survival';
      this.shurikens = [];
      this.shurikenLives = 3;
    } else if (game === 'hoop') {
      this.bannerTitle.textContent = 'HOOP SHOTS BASKETBALL';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Dual Hoops: P1 (Left Cyan) vs P2 (Right Red)!' : 'Pick Up Basketball & Wave Hand Toward Hoop to Shoot!';
      this.hoopGame.reset();
      this.practiceTag.textContent = '🏀 Hover hand over ball on floor to pick up, then wave/flick hand toward hoop to shoot!';
    } else if (game === 'cow') {
      this.bannerTitle.textContent = 'MILK THE COW';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Cow Milking Race: P1 (Cyan) vs P2 (Red)!' : 'Place Hand in Yellow Udder Box & Pull Down to Squeeze Milk!';
      this.cowGame.reset();
      this.practiceTag.textContent = '🥛 Pull your hand down repeatedly to squirt milk into the cup until it reaches 100%!';
    } else if (game === 'paint') {
      this.bannerTitle.textContent = 'WALL PAINTER';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Paint Territory Race: P1 (Cyan) vs P2 (Red)!' : 'Wave Hand as a Paint Roller to Cover Wall!';
      this.painterGame.reset();
      this.practiceTag.textContent = '🎨 Move your hand across the screen to coat the wall with neon paint!';
    } else if (game === 'catch') {
      this.bannerTitle.textContent = 'FRUIT CATCH';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Head Basket Duel: P1 (Cyan) vs P2 (Red)!' : 'Stand Under Falling Fruit With Basket On Your Head!';
      this.catchGame.reset();
      this.practiceTag.textContent = '🧺 Move your head left/right to catch falling fruit into your basket!';
    } else if (game === 'yoga') {
      this.bannerTitle.textContent = 'YOGA POSE MASTER';
      this.bannerSubtitle.textContent = 'Memorize Yoga Pose & Match Skeleton Posture!';
      this.poseGame.category = 'yoga';
      this.poseGame.reset();
      this.practiceTag.textContent = '🧘 Memorize the pose, hold it when countdown ends, and earn high accuracy!';
    } else if (game === 'anime') {
      this.bannerTitle.textContent = 'ANIME POSE CHALLENGE';
      this.bannerSubtitle.textContent = 'Iconic Anime Battle Stances & Reflex Scoring!';
      this.poseGame.category = 'anime';
      this.poseGame.reset();
      this.practiceTag.textContent = '⚡ Strike Kamehameha, Naruto Run, JoJo Stand & Titan Salute!';
    }

    if (this.playMode === 'online' && this.multiplayer.role === 'p1') {
      this.multiplayer.ws.send(JSON.stringify({ type: 'select-game', game }));
    }
  }

  spawnBalloons(roundNo) {
    const BALLOON_COLORS = ['#eb3c46', '#468cf5', '#5acd6e', '#facd3c', '#be64e6'];
    const count = 3;
    const speed = Math.min(130.0, 30.0 * (roundNo - 1));
    this.balloons = [];

    if (this.playMode === 'local') {
      // Split arena: P1 targets on Left, P2 targets on Right!
      for (let i = 0; i < count; i++) {
        const x1 = CONFIG.windowW * 0.12 + (CONFIG.windowW * 0.32) * (i / (count - 1 || 1));
        const color1 = BALLOON_COLORS[(i + roundNo) % BALLOON_COLORS.length];
        const b1 = new Balloon(`p1_${i}`, x1, 140 + (i % 2) * 25, 42, color1, speed * (i % 2 === 0 ? 1 : -1), i * 1.5, 'p1');
        this.balloons.push(b1);

        const x2 = CONFIG.windowW * 0.56 + (CONFIG.windowW * 0.32) * (i / (count - 1 || 1));
        const color2 = BALLOON_COLORS[(i + roundNo + 1) % BALLOON_COLORS.length];
        const b2 = new Balloon(`p2_${i}`, x2, 140 + (i % 2) * 25, 42, color2, speed * (i % 2 === 0 ? -1 : 1), i * 1.5 + 1.0, 'p2');
        this.balloons.push(b2);
      }
    } else {
      // Solo or Online Shared
      for (let i = 0; i < count; i++) {
        const x = (CONFIG.windowW * (i + 1)) / (count + 1) + (Math.random() - 0.5) * 60;
        const color = BALLOON_COLORS[(i + roundNo) % BALLOON_COLORS.length];
        const b = new Balloon(`b_${i}`, x, 140 + (i % 2) * 25, 44, color, speed * (i % 2 === 0 ? 1 : -1), i * 1.6, 'shared');
        this.balloons.push(b);
      }
    }

    if (this.playMode === 'online' && this.multiplayer.role === 'p1') {
      this.multiplayer.syncBalloons(this.balloons.map(b => ({
        id: b.id, x: b.x, y: b.y, y0: b.y0, radius: b.radius, color: b.color, vx: b.vx, phase: b.phase, owner: b.owner
      })), roundNo);
    }
  }

  popBalloonEffect(balloon, now) {
    for (let i = 0; i < 28; i++) {
      const angle = Math.random() * Math.PI * 2;
      const spd = Math.random() * 380 + 120;
      this.archeryParticles.push({
        x: balloon.x,
        y: balloon.y,
        vx: Math.cos(angle) * spd,
        vy: Math.sin(angle) * spd - 90,
        color: balloon.color,
        life: Math.random() * 0.5 + 0.4,
        maxLife: 0.8,
        radius: Math.random() * 6 + 3
      });
    }
    this.archeryFloaters.push({
      x: balloon.x,
      y: balloon.y - 15,
      t: now,
      text: 'POP! +100',
      color: '#ffd028'
    });
  }

  setPlayMode(mode) {
    this.playMode = mode;
    if (this.handsModel) {
      this.handsModel.setOptions({
        maxNumHands: mode === 'local' ? 2 : 1
      });
    }
    [this.tabSolo, this.tabDualLocal, this.tabDualOnline].forEach(tab => {
      tab.classList.toggle('active', tab.dataset.mode === mode);
    });

    this.resetFruitPositions();
    if (this.currentGame === 'archery') {
      this.spawnBalloons(this.archeryRound);
    }

    if (mode === 'solo') {
      this.dualScoreboard.classList.add('hidden');
      this.speedoP2.classList.add('hidden');
      this.roomBadge.classList.add('hidden');
      this.actionPrompt.style.display = 'block';
    } else if (mode === 'local') {
      this.dualScoreboard.classList.remove('hidden');
      this.speedoP2.classList.remove('hidden');
      this.roomBadge.classList.add('hidden');
      this.scores = { p1: 0, p2: 0 };
      this.updateScoreboardUI();
      this.actionPrompt.style.display = 'block';
      this.bannerSubtitle.textContent = this.currentGame === 'archery' ? 'P1 Shoots Left Balloons  |  P2 Shoots Right Balloons' : 'P1 Cuts Left Fruit  |  P2 Cuts Right Fruit';
    } else if (mode === 'online') {
      this.multiplayerModal.classList.remove('hidden');
      this.dualScoreboard.classList.remove('hidden');
      this.speedoP2.classList.remove('hidden');
    }
  }

  assignHands(detectedHands, now) {
    const W = CONFIG.windowW;
    const H = CONFIG.windowH;
    const defaultP1Anchor = { x: W * 0.28, y: H * 0.5 };
    const defaultP2Anchor = { x: W * 0.72, y: H * 0.5 };

    // Reset tracked positions if not seen recently (> 1.2s)
    if (!this.p1LastSeen || (now - this.p1LastSeen > 1.2)) {
      this.p1TrackedPos = null;
    }
    if (!this.p2LastSeen || (now - this.p2LastSeen > 1.2)) {
      this.p2TrackedPos = null;
    }

    const anchorP1 = this.p1TrackedPos || defaultP1Anchor;
    const anchorP2 = this.p2TrackedPos || defaultP2Anchor;

    let p1Assigned = null;
    let p2Assigned = null;

    if (this.playMode === 'solo') {
      if (detectedHands.length === 1) {
        p1Assigned = detectedHands[0];
      } else if (detectedHands.length >= 2) {
        // Pick the hand closest to last P1 position
        const d0 = Math.hypot(detectedHands[0].x - anchorP1.x, detectedHands[0].y - anchorP1.y);
        const d1 = Math.hypot(detectedHands[1].x - anchorP1.x, detectedHands[1].y - anchorP1.y);
        p1Assigned = d0 <= d1 ? detectedHands[0] : detectedHands[1];
      }
    } else {
      // Local Dual Mode (2 Players on 1 Screen)
      if (detectedHands.length >= 2) {
        const h0 = detectedHands[0];
        const h1 = detectedHands[1];

        // Cost of Assignment 1: h0 -> P1, h1 -> P2
        const distP1_h0 = Math.hypot(h0.x - anchorP1.x, h0.y - anchorP1.y);
        const distP2_h1 = Math.hypot(h1.x - anchorP2.x, h1.y - anchorP2.y);
        const bias0 = (h0.x > W * 0.5 ? 250 : 0) + (h1.x < W * 0.5 ? 250 : 0);
        const cost1 = distP1_h0 + distP2_h1 + bias0;

        // Cost of Assignment 2: h1 -> P1, h0 -> P2
        const distP1_h1 = Math.hypot(h1.x - anchorP1.x, h1.y - anchorP1.y);
        const distP2_h0 = Math.hypot(h0.x - anchorP2.x, h0.y - anchorP2.y);
        const bias1 = (h1.x > W * 0.5 ? 250 : 0) + (h0.x < W * 0.5 ? 250 : 0);
        const cost2 = distP1_h1 + distP2_h0 + bias1;

        if (cost1 <= cost2) {
          p1Assigned = h0;
          p2Assigned = h1;
        } else {
          p1Assigned = h1;
          p2Assigned = h0;
        }
      } else if (detectedHands.length === 1) {
        const h = detectedHands[0];
        // Decide whether this single hand belongs to P1 or P2
        const dP1 = Math.hypot(h.x - anchorP1.x, h.y - anchorP1.y);
        const dP2 = Math.hypot(h.x - anchorP2.x, h.y - anchorP2.y);
        const sideScoreP1 = dP1 + (h.x > W * 0.52 ? 300 : 0);
        const sideScoreP2 = dP2 + (h.x < W * 0.48 ? 300 : 0);

        if (sideScoreP1 <= sideScoreP2) {
          p1Assigned = h;
        } else {
          p2Assigned = h;
        }
      }
    }

    return { p1Assigned, p2Assigned };
  }

  async initMediaPipe() {
    if (!window.Hands || !window.Camera) {
      this.trackingText.textContent = 'MOUSE MODE';
      this.trackingBadge.className = 'tracking-badge warning';
      return;
    }

    try {
      this.mpCanvas = document.createElement('canvas');
      this.mpCanvas.width = 320;
      this.mpCanvas.height = 240;
      this.mpCtx = this.mpCanvas.getContext('2d', { willReadFrequently: true });

      const hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
      });
      this.handsModel = hands;

      hands.setOptions({
        maxNumHands: this.playMode === 'local' ? 2 : 1,
        modelComplexity: 0, // 0 = Lite ultra-fast model for 60 FPS in browser
        minDetectionConfidence: 0.35,
        minTrackingConfidence: 0.35
      });

      hands.onResults((results) => {
        if (this.inputModeSelect.value === 'mouse') return;
        const now = performance.now() / 1000;

        // Update camera aspect transform whenever video updates
        this.cameraTransform = getCameraTransform(this.video, CONFIG.windowW, CONFIG.windowH);

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
          this.trackingBadge.className = 'tracking-badge ready';

          // Extract landmark coordinates with finger pointing angle for laser aim
          const detectedHands = results.multiHandLandmarks.map((lms) => {
            const tip = lms[8];
            const pip = lms[6];
            const ptTip = mapNormalizedLandmark(tip, this.cameraTransform);
            const ptPip = mapNormalizedLandmark(pip, this.cameraTransform);
            const fdx = ptTip.x - ptPip.x;
            const fdy = ptTip.y - ptPip.y;
            const flen = Math.hypot(fdx, fdy) || 1;
            return {
              x: ptTip.x,
              y: ptTip.y,
              dir: { x: fdx / flen, y: fdy / flen },
              lms
            };
          });

          // PERSISTENT HUNGARIAN TRACKING (Guarantees zero identity flipping for 2 players)
          const { p1Assigned, p2Assigned } = this.assignHands(detectedHands, now);

          if (p1Assigned) {
            const resP1 = this.filterP1.filter(p1Assigned.x, p1Assigned.y, now);
            this.p1Point = { x: resP1.x, y: resP1.y };
            this.p1Speed = resP1.speed;
            this.p1FingerDir = p1Assigned.dir;
            this.p1TrackedPos = { x: resP1.x, y: resP1.y };
            this.detectorP1.addSample(now, resP1.x, resP1.y, resP1.speed);
            this.p1LastSeen = now;

            if (this.playMode === 'online') {
              this.multiplayer.syncBlade(this.p1Point, this.p1Speed);
            }
          }

          if (p2Assigned && this.playMode === 'local') {
            const resP2 = this.filterP2.filter(p2Assigned.x, p2Assigned.y, now);
            this.p2Point = { x: resP2.x, y: resP2.y };
            this.p2Speed = resP2.speed;
            this.p2FingerDir = p2Assigned.dir;
            this.p2TrackedPos = { x: resP2.x, y: resP2.y };
            this.detectorP2.addSample(now, resP2.x, resP2.y, resP2.speed);
            this.p2LastSeen = now;
          }

          if (p1Assigned && p2Assigned && this.playMode === 'local') {
            this.trackingText.textContent = '2 BLADES LOCKED (P1 & P2)';
          } else if (p1Assigned) {
            this.trackingText.textContent = 'P1 BLADE READY';
          } else if (p2Assigned && this.playMode === 'local') {
            this.trackingText.textContent = 'P2 BLADE READY';
          }
        } else {
          this.trackingBadge.className = 'tracking-badge warning';
          this.trackingText.textContent = 'NO HAND SEEN';
        }
      });

      // MediaPipe Face Detection for Fruit Catch (Head Basket)
      if (window.FaceDetection) {
        this.faceModel = new window.FaceDetection({
          locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`
        });
        this.faceModel.setOptions({
          model: 'short',
          minDetectionConfidence: 0.4
        });
        this.faceModel.onResults((results) => {
          if (this.currentGame !== 'catch') return;
          if (results.detections && results.detections.length > 0) {
            this.trackingBadge.className = 'tracking-badge ready';
            this.trackingText.textContent = `${results.detections.length} HEAD(S) LOCKED`;
            const sorted = results.detections.map(d => {
              const bb = d.locationData.relativeBoundingBox;
              return { x: bb.xmin + bb.width / 2, y: bb.ymin, w: bb.width };
            }).sort((a, b) => a.x - b.x);

            if (sorted[0]) {
              this.catchGame.setFace('p1', sorted[0].x, sorted[0].y, sorted[0].w);
            }
            if (sorted[1] && this.playMode === 'local') {
              this.catchGame.setFace('p2', sorted[1].x, sorted[1].y, sorted[1].w);
            }
          }
        });
      }

      // MediaPipe Pose for Yoga & Anime Challenges
      if (window.Pose) {
        this.poseModel = new window.Pose({
          locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
        });
        this.poseModel.setOptions({
          modelComplexity: 0, // 0 = Lite ultra-fast pose model
          smoothLandmarks: true,
          minDetectionConfidence: 0.4,
          minTrackingConfidence: 0.4
        });
        this.poseModel.onResults((results) => {
          if (this.currentGame !== 'yoga' && this.currentGame !== 'anime') return;
          if (results.poseLandmarks) {
            this.trackingBadge.className = 'tracking-badge ready';
            this.trackingText.textContent = 'BODY POSE TRACKED';
            this.lastPoseLandmarks = results.poseLandmarks;
          }
        });
      }

      this.isProcessingFrame = false;
      const camera = new window.Camera(this.video, {
        onFrame: async () => {
          if (this.isProcessingFrame) return; // Drop frame if previous is still computing!
          this.isProcessingFrame = true;
          try {
            if (this.mpCtx && this.video.videoWidth > 0) {
              this.mpCtx.drawImage(this.video, 0, 0, 320, 240);
              const imgTarget = this.mpCanvas;
              if (this.currentGame === 'catch') {
                if (this.faceModel) await this.faceModel.send({ image: imgTarget });
              } else if (this.currentGame === 'yoga' || this.currentGame === 'anime') {
                if (this.poseModel) await this.poseModel.send({ image: imgTarget });
              } else {
                await hands.send({ image: imgTarget });
              }
            }
          } catch (e) {
            // ignore
          } finally {
            this.isProcessingFrame = false;
          }
        },
        width: 640,
        height: 480
      });
      await camera.start();
    } catch (err) {
      console.warn('Camera initialization error:', err);
    }
  }

  handleMultiplayerEvent(msg) {
    if (msg.type === 'room-created') {
      this.multiplayer.role = 'p1';
      this.multiplayer.roomId = msg.roomId;
      this.roomShareInfo.classList.remove('hidden');
      this.displayRoomCode.textContent = msg.roomId;
      this.shareUrlInput.value = msg.joinUrl;
      this.roomBadge.classList.remove('hidden');
      this.roomBadgeText.textContent = `ROOM: ${msg.roomId} (HOST)`;
    } else if (msg.type === 'room-joined') {
      this.multiplayer.role = 'p2';
      this.multiplayer.roomId = msg.roomId;
      this.multiplayerModal.classList.add('hidden');
      this.roomBadge.classList.remove('hidden');
      this.roomBadgeText.textContent = `ROOM: ${msg.roomId} (GUEST)`;
      this.scores = msg.scores;
      this.targetWins = msg.targetWins;
      this.updateScoreboardUI();
      if (msg.game) this.setGame(msg.game);
    } else if (msg.type === 'player-joined') {
      this.guestWaitStatus.textContent = 'Guest Connected! Ready to Fight.';
      this.guestWaitStatus.className = 'status-item ready';
      this.btnStartOnlineMatch.classList.remove('disabled');
      this.btnStartOnlineMatch.removeAttribute('disabled');
    } else if (msg.type === 'game-changed') {
      this.setGame(msg.game);
    } else if (msg.type === 'match-started') {
      this.multiplayerModal.classList.add('hidden');
      this.scores = msg.scores;
      this.targetWins = msg.targetWins;
      this.updateScoreboardUI();
      this.startOnlineRound();
    } else if (msg.type === 'round-start') {
      this.state = 'WAIT';
      this.stateStart = performance.now() / 1000;
      this.waitTime = msg.waitTime;
      this.fruitP1 = new Fruit(msg.fruitKind, CONFIG.windowW / 2, CONFIG.windowH / 2 + 25, 'shared');
      this.detectorP1.reset();
      this.detectorP2.reset();
      this.bannerTitle.textContent = 'WAIT FOR IT...';
      this.bannerTitle.className = 'banner-title';
      this.bannerSubtitle.textContent = 'Synchronized Duel: Keep blades ready!';
      this.actionPrompt.style.display = 'none';
      this.resultModal.classList.add('hidden');
    } else if (msg.type === 'signal-cut') {
      this.state = 'CUT';
      this.cutTime = performance.now() / 1000;
      this.sounds.playGong();
      this.bannerTitle.textContent = 'CUT!';
      this.bannerTitle.className = 'banner-title cut-pulse';
      this.bannerSubtitle.textContent = 'SWIPE NOW!';
    } else if (msg.type === 'round-won') {
      this.state = 'RESULT';
      this.scores = msg.scores;
      this.updateScoreboardUI();

      if (this.fruitP1 && this.fruitP1.state === 'whole') {
        this.fruitP1.slice(msg.direction || { x: 1, y: 0 }, performance.now() / 1000, msg.cutOffset || { x: 0, y: 0 });
        this.sounds.playSlice();
      }

      const winnerText = msg.winnerRole === this.multiplayer.role ? 'YOU WON THE ROUND!' : 'OPPONENT WON THE ROUND!';
      this.showDualResultModal(winnerText, `Reaction: ${Math.round(msg.reactionMs)}ms | Speed: ${Math.round(msg.speed)} px/s`);
    } else if (msg.type === 'opponent-blade') {
      this.p2Point = msg.point;
      this.p2Speed = msg.speed;
      this.detectorP2.addSample(performance.now() / 1000, msg.point.x, msg.point.y, msg.speed);
    } else if (msg.type === 'target-scored') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      this.sounds.playTargetHit();
    } else if (msg.type === 'opponent-arrow') {
      const ar = msg.arrow;
      this.arrows.push(new Arrow(ar.id || Date.now(), ar.tip.x, ar.tip.y, ar.aim.x, ar.aim.y, ar.speed, 'p2'));
      this.sounds.playBowRelease();
    } else if (msg.type === 'opponent-bow') {
      this.bowP2.palm = msg.bow.palm;
      this.bowP2.aim = msg.bow.aim;
      this.bowP2.drawAmount = msg.bow.drawAmount;
    } else if (msg.type === 'balloon-popped') {
      const targetB = this.balloons.find(b => b.id === msg.balloonIndex && b.alive);
      if (targetB) {
        targetB.alive = false;
        this.popBalloonEffect(targetB, performance.now() / 1000);
        this.sounds.playBalloonPop();
      }
      this.scores = msg.scores;
      this.updateScoreboardUI();
    } else if (msg.type === 'balloons-spawned') {
      this.balloons = msg.balloons.map(b => new Balloon(b.id, b.x, b.y, b.radius, b.color, b.vx, b.phase, b.owner));
      this.archeryRound = msg.round;
    } else if (msg.type === 'opponent-basketball') {
      const ball = msg.ball;
      const b = new Basketball(ball.id || Date.now(), ball.x, ball.y, 'p2');
      b.vx = ball.vx;
      b.vy = ball.vy;
      b.state = 'flying';
      this.hoopGame.balls.push(b);
      this.sounds.playWhoosh();
    } else if (msg.type === 'basketball-scored') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      this.sounds.playSwish();
    } else if (msg.type === 'opponent-milk-squirt') {
      const st = this.cowGame.stations.find(s => s.role === 'p2');
      if (st) {
        st.fill = msg.fill;
        for (let k = 0; k < 3; k++) {
          st.streams.push({
            x: st.cx + (k - 1) * 26 + (Math.random() - 0.5) * 10,
            y: st.cy + 25,
            vy: 600,
            targetY: st.cy + 240,
            life: 1.0
          });
        }
      }
    } else if (msg.type === 'cow-round-won') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      const winnerText = msg.winnerRole === this.multiplayer.role ? 'YOU FILLED THE CUP FIRST!' : 'OPPONENT FILLED THE CUP!';
      this.showDualResultModal(winnerText, `Time: ${(msg.timeElapsed % 60).toFixed(1)}s`);
    } else if (msg.type === 'opponent-paint-stroke') {
      if (this.painterGame.offCtx) {
        this.painterGame.offCtx.save();
        this.painterGame.offCtx.fillStyle = '#ff3366';
        this.painterGame.offCtx.beginPath();
        this.painterGame.offCtx.arc(msg.stroke.x, msg.stroke.y, this.painterGame.brushR, 0, Math.PI * 2);
        this.painterGame.offCtx.fill();
        this.painterGame.offCtx.restore();
        this.painterGame.coverageP2 = msg.coverage || this.painterGame.coverageP2;
      }
    } else if (msg.type === 'paint-round-won') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      const winnerText = msg.winnerRole === this.multiplayer.role ? 'YOU PAINTED THE WALL FIRST!' : 'OPPONENT COVERED THE WALL!';
      this.showDualResultModal(winnerText, 'Wall 95% Painted!');
    } else if (msg.type === 'opponent-catch-basket') {
      this.catchGame.baskets.p2.x = msg.x;
      this.catchGame.baskets.p2.y = msg.y;
      this.catchGame.baskets.p2.w = msg.w || 150;
    } else if (msg.type === 'catch-fruits-spawned') {
      this.catchGame.fruits = msg.fruits;
    } else if (msg.type === 'catch-fruit-scored') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      this.sounds.playCatch();
    } else if (msg.type === 'pose-challenge-selected') {
      this.poseGame.category = msg.pose.category || 'yoga';
      this.poseGame.poseIndex = msg.pose.index || 0;
      this.poseGame.phase = 'MEMORIZE';
      this.poseGame.phaseTimer = 3.5;
    } else if (msg.type === 'opponent-pose-score') {
      this.poseGame.accuracyP2 = msg.score;
    } else if (msg.type === 'pose-round-won') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      const winnerText = msg.winnerRole === this.multiplayer.role ? 'YOU HAD BETTER POSE ACCURACY!' : 'OPPONENT WON THE POSE DUEL!';
      this.showDualResultModal(winnerText, `P1: ${msg.p1Score}% | P2: ${msg.p2Score}%`);
    } else if (msg.type === 'match-won') {
      this.scores = msg.scores;
      this.updateScoreboardUI();
      const championText = msg.champion === this.multiplayer.role ? '🏆 YOU ARE THE ULTIMATE CHAMPION!' : 'OPPONENT WON THE MATCH!';
      this.showDualResultModal(championText, `Final Score: P1 [${msg.scores.p1}] - P2 [${msg.scores.p2}]`);
    }
  }

  updateScoreboardUI() {
    this.p1ScoreEl.textContent = this.scores.p1;
    this.p2ScoreEl.textContent = this.scores.p2;
    this.targetWinsLabel.textContent = `FIRST TO ${this.targetWins}`;
  }

  handleStartAction() {
    const now = performance.now() / 1000;
    if (this.playMode === 'online') {
      if (this.multiplayer.role === 'p1') {
        this.startOnlineRound();
      }
      return;
    }

    if (this.state === 'TITLE' || this.state === 'RESULT' || this.state === 'CLEAR') {
      if (this.currentGame === 'archery') {
        this.resultModal.classList.add('hidden');
        this.state = 'PLAY';
        this.archeryRound = 1;
        this.archeryScore = 0;
        this.archeryArrowsLeft = 7;
        this.arrows = [];
        this.spawnBalloons(1);
        this.bannerTitle.textContent = 'ROUND 1';
        this.bannerSubtitle.textContent = 'Draw your bow and pop all 3 balloons!';
        this.actionPrompt.style.display = 'none';
        this.practiceTag.style.display = 'none';
        return;
      }

      if (this.currentGame === 'hoop') {
        this.resultModal.classList.add('hidden');
        this.state = 'PLAY';
        this.hoopGame.reset();
        this.bannerTitle.textContent = 'HOOP SHOTS!';
        this.bannerSubtitle.textContent = 'Wave hand toward hoop to shoot!';
        this.actionPrompt.style.display = 'none';
        this.practiceTag.style.display = 'none';
        return;
      }

      if (this.currentGame === 'cow') {
        this.resultModal.classList.add('hidden');
        this.state = 'PLAY';
        this.cowGame.reset();
        this.bannerTitle.textContent = 'MILK THE COW!';
        this.bannerSubtitle.textContent = 'Pull down on udder to fill the cup!';
        this.actionPrompt.style.display = 'none';
        this.practiceTag.style.display = 'none';
        return;
      }

      if (this.currentGame === 'paint') {
        this.resultModal.classList.add('hidden');
        this.state = 'PLAY';
        this.painterGame.reset();
        this.bannerTitle.textContent = 'WALL PAINTER!';
        this.bannerSubtitle.textContent = 'Cover the wall with neon paint!';
        this.actionPrompt.style.display = 'none';
        this.practiceTag.style.display = 'none';
        return;
      }

      if (this.currentGame === 'catch') {
        this.resultModal.classList.add('hidden');
        this.state = 'PLAY';
        this.catchGame.reset();
        this.bannerTitle.textContent = 'FRUIT CATCH!';
        this.bannerSubtitle.textContent = 'Stand under fruit with your head basket!';
        this.actionPrompt.style.display = 'none';
        this.practiceTag.style.display = 'none';
        return;
      }

      if (this.currentGame === 'yoga' || this.currentGame === 'anime') {
        this.resultModal.classList.add('hidden');
        this.state = 'PLAY';
        this.poseGame.reset();
        this.bannerTitle.textContent = this.currentGame === 'yoga' ? 'YOGA POSE MASTER!' : 'ANIME POSE CHALLENGE!';
        this.bannerSubtitle.textContent = 'Memorize the pose!';
        this.actionPrompt.style.display = 'none';
        this.practiceTag.style.display = 'none';
        return;
      }

      this.resultModal.classList.add('hidden');
      this.state = 'WAIT';
      this.stateStart = now;
      this.waitTime = 2.0 + Math.random() * 2.5;

      const fruitKeys = Object.keys(FRUITS);
      const k1 = fruitKeys[Math.floor(Math.random() * fruitKeys.length)];
      const k2 = fruitKeys[Math.floor(Math.random() * fruitKeys.length)];
      this.fruitP1 = new Fruit(k1, CONFIG.windowW / 2, CONFIG.windowH / 2 + 25, 'p1');
      this.fruitP2 = new Fruit(k2, CONFIG.windowW / 2, CONFIG.windowH / 2 + 25, 'p2');
      this.resetFruitPositions();

      this.detectorP1.reset();
      this.detectorP2.reset();

      this.bannerTitle.textContent = 'WAIT FOR IT...';
      this.bannerTitle.className = 'banner-title';
      this.bannerSubtitle.textContent = this.playMode === 'local' ? 'Keep blades steady... CUT! is coming' : 'Keep blade steady... CUT! is coming';
      this.actionPrompt.style.display = 'none';
      this.practiceTag.style.display = 'none';
    }
  }

  startOnlineRound() {
    const fruitKeys = Object.keys(FRUITS);
    const fruitKind = fruitKeys[Math.floor(Math.random() * fruitKeys.length)];
    const waitTime = 2.0 + Math.random() * 2.5;
    this.multiplayer.startRound(fruitKind, waitTime);
  }

  update(now, dt) {
    this.speedP1Value.innerHTML = `${Math.round(this.p1Speed)} <small>px/s</small>`;
    const fillP1 = Math.min(100, Math.max(0, (this.p1Speed / 2200) * 100));
    this.speedoP1Fill.style.width = `${fillP1}%`;

    if (this.playMode !== 'solo') {
      this.speedP2Value.innerHTML = `${Math.round(this.p2Speed)} <small>px/s</small>`;
      const fillP2 = Math.min(100, Math.max(0, (this.p2Speed / 2200) * 100));
      this.speedoP2Fill.style.width = `${fillP2}%`;
    }

    // GAME 1: FRUIT SLICE
    if (this.currentGame === 'slice') {
      const cP1 = this.fruitP1.getCenter(now);
      const cP2 = (this.playMode === 'local' && CONFIG.dualFruitMode === 'split') ? this.fruitP2.getCenter(now) : cP1;

      // Precision Arc Raycasting
      const sliceP1 = this.detectorP1.checkSlice(now, cP1, CONFIG.fruitRadius);
      const sliceP2 = (this.playMode === 'local') ? this.detectorP2.checkSlice(now, cP2, CONFIG.fruitRadius) : null;

      if (this.state === 'TITLE') {
        if (this.fruitP1.state === 'whole' && sliceP1 && sliceP1.hit) {
          this.fruitP1.slice(sliceP1.direction, now, sliceP1.cutOffset);
          this.sounds.playSlice();
          this.practiceTag.textContent = `⚔️ PRACTICE HIT! Speed: ${Math.round(sliceP1.peakSpeed)} px/s | Accuracy: ${Math.round(sliceP1.accuracy)}% (BULLSEYE!)`;
          setTimeout(() => { this.resetFruitPositions(); this.fruitP1.state = 'whole'; }, 1300);
        }
        if (this.playMode === 'local' && this.fruitP2.state === 'whole' && sliceP2 && sliceP2.hit) {
          this.fruitP2.slice(sliceP2.direction, now, sliceP2.cutOffset);
          this.sounds.playSlice();
          setTimeout(() => { this.resetFruitPositions(); this.fruitP2.state = 'whole'; }, 1300);
        }
      } else if (this.state === 'WAIT') {
        const waited = now - this.stateStart;
        if (waited >= this.waitTime) {
          if (this.playMode === 'online' && this.multiplayer.role === 'p1') {
            this.multiplayer.signalCut();
          } else if (this.playMode !== 'online') {
            this.state = 'CUT';
            this.cutTime = now;
            this.sounds.playGong();
            this.bannerTitle.textContent = 'CUT!';
            this.bannerTitle.className = 'banner-title cut-pulse';
            this.bannerSubtitle.textContent = 'SWIPE NOW!';
          }
        }
      } else if (this.state === 'CUT') {
        const elapsed = now - this.cutTime;

        // Slicing Evaluation
        if (this.playMode === 'local') {
          const p1Hit = sliceP1 && sliceP1.hit;
          const p2Hit = sliceP2 && sliceP2.hit;

          if (p1Hit && p2Hit) {
            // Both players hit on the exact same frame! Compare peak speed to determine champion
            if (sliceP2.peakSpeed > sliceP1.peakSpeed) {
              this.scores.p2++;
              this.updateScoreboardUI();
              const target = (CONFIG.dualFruitMode === 'split') ? this.fruitP2 : this.fruitP1;
              target.slice(sliceP2.direction, now, sliceP2.cutOffset);
              this.sounds.playSlice();
              this.state = 'RESULT';
              this.showDualResultModal('PLAYER 2 (RIGHT) WINS DUEL!', `⚡ Faster Cut! Speed: ${Math.round(sliceP2.peakSpeed)} vs ${Math.round(sliceP1.peakSpeed)} px/s`);
            } else {
              this.scores.p1++;
              this.updateScoreboardUI();
              this.fruitP1.slice(sliceP1.direction, now, sliceP1.cutOffset);
              this.sounds.playSlice();
              this.state = 'RESULT';
              this.showDualResultModal('PLAYER 1 (LEFT) WINS DUEL!', `⚡ Faster Cut! Speed: ${Math.round(sliceP1.peakSpeed)} vs ${Math.round(sliceP2.peakSpeed)} px/s`);
            }
          } else if (p1Hit) {
            this.scores.p1++;
            this.updateScoreboardUI();
            this.fruitP1.slice(sliceP1.direction, now, sliceP1.cutOffset);
            this.sounds.playSlice();
            this.state = 'RESULT';
            this.showDualResultModal('PLAYER 1 (LEFT) WINS ROUND!', `Speed: ${Math.round(sliceP1.peakSpeed)} px/s | Accuracy: ${Math.round(sliceP1.accuracy)}%`);
          } else if (p2Hit) {
            this.scores.p2++;
            this.updateScoreboardUI();
            const target = (CONFIG.dualFruitMode === 'split') ? this.fruitP2 : this.fruitP1;
            target.slice(sliceP2.direction, now, sliceP2.cutOffset);
            this.sounds.playSlice();
            this.state = 'RESULT';
            this.showDualResultModal('PLAYER 2 (RIGHT) WINS ROUND!', `Speed: ${Math.round(sliceP2.peakSpeed)} px/s | Accuracy: ${Math.round(sliceP2.accuracy)}%`);
          }
        } else if (this.playMode === 'online') {
          if (sliceP1 && sliceP1.hit) {
            this.multiplayer.sendSliceAttempt({
              hit: true,
              reactionMs: elapsed * 1000,
              speed: sliceP1.peakSpeed,
              accuracy: sliceP1.accuracy,
              direction: sliceP1.direction,
              cutOffset: sliceP1.cutOffset
            });
          }
        } else {
          // Solo Win
          if (sliceP1 && sliceP1.hit) {
            this.state = 'RESULT';
            this.stats.rounds++;
            this.stats.wins++;
            const reactionMs = elapsed * 1000;
            if (!this.stats.best || reactionMs < this.stats.best) this.stats.best = reactionMs;
            this.fruitP1.slice(sliceP1.direction, now, sliceP1.cutOffset);
            this.sounds.playSlice();
            this.showSoloResultModal('win', reactionMs, sliceP1.peakSpeed, sliceP1.accuracy);
          }
        }
      }

      this.fruitP1.update(dt);
      if (this.playMode === 'local') this.fruitP2.update(dt);
    }

    // GAME 2: TARGET BLITZ
    else if (this.currentGame === 'blitz') {
      if (now - this.lastTargetSpawn > 0.8) {
        this.lastTargetSpawn = now;
        const targetX = Math.random() * (CONFIG.windowW - 200) + 100;
        const targetY = Math.random() * (CONFIG.windowH - 240) + 120;
        const playerOwner = (this.playMode === 'local' && targetX > CONFIG.windowW / 2) ? 'p2' : 'p1';
        this.blitzTargets.push(new BlitzTarget(++this.targetIdCounter, targetX, targetY, 38, 2.5, playerOwner));
      }

      this.blitzTargets = this.blitzTargets.filter(t => t.update(now));

      if (this.p1Point && this.p1Speed > 220) {
        this.blitzTargets.forEach((t, idx) => {
          if (Math.hypot(this.p1Point.x - t.x, this.p1Point.y - t.y) <= t.radius + 20) {
            this.blitzTargets.splice(idx, 1);
            this.scores.p1++;
            this.updateScoreboardUI();
            this.sounds.playTargetHit();
            if (this.playMode === 'online') this.multiplayer.sendTargetHit(t.id, 1);
          }
        });
      }

      if (this.p2Point && this.p2Speed > 220 && this.playMode === 'local') {
        this.blitzTargets.forEach((t, idx) => {
          if (Math.hypot(this.p2Point.x - t.x, this.p2Point.y - t.y) <= t.radius + 20) {
            this.blitzTargets.splice(idx, 1);
            this.scores.p2++;
            this.updateScoreboardUI();
            this.sounds.playTargetHit();
          }
        });
      }
    }

    // GAME 3: NINJA DEFLECT
    else if (this.currentGame === 'deflect') {
      if (now - this.lastShurikenSpawn > 1.2) {
        this.lastShurikenSpawn = now;
        const sx = Math.random() * (CONFIG.windowW - 160) + 80;
        const vx = (Math.random() - 0.5) * 80;
        const vy = Math.random() * 150 + 220;
        this.shurikens.push(new Shuriken(Date.now(), sx, -20, vx, vy));
      }

      this.shurikens = this.shurikens.filter(s => {
        const alive = s.update(dt);
        if (!alive && s.y >= CONFIG.windowH) {
          this.sounds.playThud();
          this.shurikenLives--;
          if (this.shurikenLives <= 0) {
            this.state = 'RESULT';
            this.showSoloResultModal('defeat', 0, 0, 0);
          }
        }
        return alive;
      });

      [this.p1Point, this.p2Point].forEach((pt, pIdx) => {
        if (!pt) return;
        const speed = pIdx === 0 ? this.p1Speed : this.p2Speed;
        if (speed > 250) {
          this.shurikens.forEach((s, sIdx) => {
            if (Math.hypot(pt.x - s.x, pt.y - s.y) <= s.radius + 30) {
              this.shurikens.splice(sIdx, 1);
              if (pIdx === 0) this.scores.p1++;
              else this.scores.p2++;
              this.updateScoreboardUI();
              this.sounds.playDeflect();
            }
          });
        }
      });
    }

    // GAME 4: BALLOON ARCHER
    else if (this.currentGame === 'archery') {
      const canShootP1 = (this.state === 'PLAY' || this.state === 'TITLE') && (this.state === 'TITLE' || this.archeryArrowsLeft > 0);
      const shot1 = this.bowP1.update(this.p1Point, this.p1FingerDir, now, dt, canShootP1);
      if (shot1) {
        if (this.state === 'PLAY') this.archeryArrowsLeft--;
        this.arrows.push(new Arrow(Date.now(), shot1.tip.x, shot1.tip.y, shot1.aim.x, shot1.aim.y, shot1.speed, 'p1'));
        this.sounds.playBowRelease();
        if (this.playMode === 'online') {
          this.multiplayer.shootArrow(shot1);
        }
      }

      if (this.playMode === 'local') {
        const canShootP2 = (this.state === 'PLAY' || this.state === 'TITLE');
        const shot2 = this.bowP2.update(this.p2Point, this.p2FingerDir, now, dt, canShootP2);
        if (shot2) {
          this.arrows.push(new Arrow(Date.now() + 1, shot2.tip.x, shot2.tip.y, shot2.aim.x, shot2.aim.y, shot2.speed, 'p2'));
          this.sounds.playBowRelease();
        }
      }

      if (this.playMode === 'online' && this.p1Point) {
        this.multiplayer.syncBow({ palm: this.bowP1.palm, aim: this.bowP1.aim, drawAmount: this.bowP1.drawAmount });
      }

      // Update flying arrows
      this.arrows = this.arrows.filter(ar => {
        const alive = ar.update(dt);
        if (!alive) return false;

        const tail = ar.getTail();
        for (const b of this.balloons) {
          if (!b.alive) continue;
          if (this.playMode === 'local') {
            if (ar.player === 'p1' && b.owner === 'p2') continue;
            if (ar.player === 'p2' && b.owner === 'p1') continue;
          }

          if (segHitsCircle(tail.x, tail.y, ar.x, ar.y, b.x, b.y, b.radius)) {
            b.alive = false;
            this.sounds.playBalloonPop();
            this.popBalloonEffect(b, now);

            if (ar.player === 'p1') {
              this.scores.p1++;
              this.archeryScore++;
            } else {
              this.scores.p2++;
            }
            this.updateScoreboardUI();

            if (this.playMode === 'online') {
              this.multiplayer.popBalloon(b.id, 1);
            }
            return false;
          }
        }
        return true;
      });

      // Update balloons
      if (this.playMode === 'local') {
        this.balloons.forEach(b => {
          if (b.owner === 'p1') b.update(now, dt, 40, CONFIG.windowW * 0.48 - 30);
          else b.update(now, dt, CONFIG.windowW * 0.52 + 30, CONFIG.windowW - 40);
        });
      } else {
        this.balloons.forEach(b => b.update(now, dt, 60, CONFIG.windowW - 60));
      }

      // Update particles & floaters
      this.archeryParticles.forEach(p => {
        p.vy += 850 * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.life -= dt;
      });
      this.archeryParticles = this.archeryParticles.filter(p => p.life > 0);

      this.archeryFloaters = this.archeryFloaters.filter(f => now - f.t < 0.85);

      // State check for Round Clear / Game Over
      if (this.state === 'PLAY') {
        const remaining = this.balloons.filter(b => b.alive).length;
        if (remaining === 0) {
          this.state = 'CLEAR';
          this.sounds.playGong();
          this.bannerTitle.textContent = `ROUND ${this.archeryRound} CLEARED!`;
          this.bannerSubtitle.textContent = 'All Balloons Popped! Reloading...';
          setTimeout(() => {
            if (this.state === 'CLEAR' && this.currentGame === 'archery') {
              this.archeryRound++;
              this.archeryArrowsLeft = 7;
              this.spawnBalloons(this.archeryRound);
              this.state = 'PLAY';
              this.bannerTitle.textContent = `ROUND ${this.archeryRound}`;
              this.bannerSubtitle.textContent = 'Pop all the balloons before running out of arrows!';
            }
          }, 1800);
        } else if (this.archeryArrowsLeft === 0 && this.arrows.length === 0) {
          this.state = 'RESULT';
          this.showSoloResultModal('defeat', 0, 0, 0);
          document.getElementById('resultTitle').textContent = 'OUT OF ARROWS!';
          document.getElementById('resultBadge').textContent = `POPPED ${this.archeryScore}`;
        }
      }
    } else if (this.currentGame === 'hoop') {
      this.hoopGame.update(now, dt);
    } else if (this.currentGame === 'cow') {
      this.cowGame.update(now, dt);
    } else if (this.currentGame === 'paint') {
      this.painterGame.update(now, dt);
    } else if (this.currentGame === 'catch') {
      this.catchGame.update(now, dt);
    } else if (this.currentGame === 'yoga' || this.currentGame === 'anime') {
      this.poseGame.update(now, dt);
    }
  }

  showSoloResultModal(outcome, reactionMs, speed, accuracy) {
    this.soloResultGrid.classList.remove('hidden');
    this.dualResultGrid.classList.add('hidden');
    this.soloRankBox.classList.remove('hidden');

    const resultTitle = document.getElementById('resultTitle');
    const resultBadge = document.getElementById('resultBadge');

    if (outcome === 'win') {
      resultBadge.textContent = 'ROUND CLEARED';
      resultBadge.style.color = '#10f084';
      resultBadge.style.borderColor = '#10f084';
      resultTitle.textContent = accuracy >= 90 ? 'PERFECT BULLSEYE!' : 'NICE CUT!';
      resultTitle.className = 'result-title';

      document.getElementById('resReaction').textContent = `${Math.round(reactionMs)} ms`;
      document.getElementById('resSpeed').textContent = `${Math.round(speed)} px/s`;
      document.getElementById('resAccuracy').textContent = `${Math.round(accuracy)}%`;
      document.getElementById('resRankBadge').textContent = 'S+';
    } else {
      resultBadge.textContent = 'FAULT';
      resultTitle.textContent = 'DEFEAT!';
      resultTitle.className = 'result-title defeat';
      document.getElementById('resRankBadge').textContent = 'F';
    }
    this.resultModal.classList.remove('hidden');
  }

  showDualResultModal(winnerTitle, statsSubtitle) {
    this.soloResultGrid.classList.add('hidden');
    this.soloRankBox.classList.add('hidden');
    this.dualResultGrid.classList.remove('hidden');

    document.getElementById('resultBadge').textContent = 'DUEL RESULT';
    document.getElementById('resultTitle').textContent = 'ROUND COMPLETE';
    this.dualWinnerAnnounce.textContent = winnerTitle;
    this.dualRoundStats.textContent = statsSubtitle;

    this.resultModal.classList.remove('hidden');
  }

  draw(now) {
    this.ctx.clearRect(0, 0, CONFIG.windowW, CONFIG.windowH);

    // Pixel-perfect video mirror alignment
    if (this.cameraBg && this.video.readyState >= 2) {
      const t = this.cameraTransform;
      this.ctx.save();
      this.ctx.translate(CONFIG.windowW, 0);
      this.ctx.scale(-1, 1);
      this.ctx.globalAlpha = 0.35;
      this.ctx.drawImage(this.video, -t.offsetX - t.renderW + CONFIG.windowW, t.offsetY, t.renderW, t.renderH);
      this.ctx.restore();
    }

    // Active game rendering
    if (this.currentGame === 'slice') {
      const isCutActive = this.state === 'CUT';
      const cP1 = this.fruitP1.getCenter(now);
      const isAimedP1 = this.p1Point && Math.hypot(this.p1Point.x - cP1.x, this.p1Point.y - cP1.y) < CONFIG.fruitRadius * 1.5;

      this.fruitP1.draw(this.ctx, now, isCutActive, isAimedP1);

      if (this.playMode === 'local' && CONFIG.dualFruitMode === 'split') {
        const cP2 = this.fruitP2.getCenter(now);
        const isAimedP2 = this.p2Point && Math.hypot(this.p2Point.x - cP2.x, this.p2Point.y - cP2.y) < CONFIG.fruitRadius * 1.5;
        this.fruitP2.draw(this.ctx, now, isCutActive, isAimedP2);
      }
    } else if (this.currentGame === 'blitz') {
      this.blitzTargets.forEach(t => t.draw(this.ctx, now));
    } else if (this.currentGame === 'deflect') {
      this.ctx.save();
      this.ctx.strokeStyle = '#00f0ff';
      this.ctx.lineWidth = 4;
      this.ctx.beginPath();
      this.ctx.moveTo(0, CONFIG.windowH - 60);
      this.ctx.lineTo(CONFIG.windowW, CONFIG.windowH - 60);
      this.ctx.stroke();
      this.ctx.restore();

      this.shurikens.forEach(s => s.draw(this.ctx));
    } else if (this.currentGame === 'archery') {
      // Draw floating balloons
      this.balloons.forEach(b => b.draw(this.ctx, now));

      // Draw flying arrows
      this.arrows.forEach(a => a.draw(this.ctx));

      // Draw bows
      this.bowP1.draw(this.ctx, this.state === 'TITLE' || this.archeryArrowsLeft > 0);
      if (this.playMode !== 'solo') {
        this.bowP2.draw(this.ctx, true);
      }

      // Draw pop explosion particles
      this.archeryParticles.forEach(p => {
        this.ctx.save();
        this.ctx.fillStyle = p.color;
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, Math.max(1, p.radius * (p.life / p.maxLife)), 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();
      });

      // Draw floaters
      this.archeryFloaters.forEach(f => {
        const age = now - f.t;
        this.ctx.save();
        this.ctx.fillStyle = f.color;
        this.ctx.font = 'bold 24px Orbitron, monospace';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(f.text, f.x, f.y - age * 70);
        this.ctx.restore();
      });

      // Draw Archery Quiver HUD
      this.drawArcheryHUD();
    } else if (this.currentGame === 'hoop') {
      this.hoopGame.draw(this.ctx, now);
    } else if (this.currentGame === 'cow') {
      this.cowGame.draw(this.ctx, now);
    } else if (this.currentGame === 'paint') {
      this.painterGame.draw(this.ctx, now);
    } else if (this.currentGame === 'catch') {
      this.catchGame.draw(this.ctx, now);
    } else if (this.currentGame === 'yoga' || this.currentGame === 'anime') {
      this.poseGame.draw(this.ctx, now);
    }

    // Draw Blade Trails with precision crosshairs (in slice/blitz/deflect)
    if (this.currentGame === 'slice' || this.currentGame === 'blitz' || this.currentGame === 'deflect') {
      this.drawBladeTrail(this.detectorP1.history, '#00f0ff', 'rgba(0, 240, 255, 0.5)', now, 'P1 BLADE', this.p1FingerDir);
      if (this.playMode !== 'solo') {
        this.drawBladeTrail(this.detectorP2.history, '#ff3366', 'rgba(255, 51, 102, 0.5)', now, 'P2 BLADE', this.p2FingerDir);
      }
    }

    // Split-line divider in Same-Device Dual
    if (this.playMode === 'local') {
      this.ctx.save();
      this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
      this.ctx.lineWidth = 2;
      this.ctx.setLineDash([8, 8]);
      this.ctx.beginPath();
      this.ctx.moveTo(CONFIG.windowW / 2, 0);
      this.ctx.lineTo(CONFIG.windowW / 2, CONFIG.windowH);
      this.ctx.stroke();
      this.ctx.restore();
    }

    if (this.debugOverlay) {
      this.drawDebugStats(now);
    }
  }

  drawBladeTrail(history, coreColor, glowColor, now, label, dir = null) {
    const pts = history.filter(p => now - p.t <= 0.28);
    if (pts.length < 2) {
      if (pts.length === 1) {
        this.drawFingertipCrosshair(pts[0].x, pts[0].y, coreColor, label, dir);
      }
      return;
    }

    const n = pts.length;
    // Outer glow line
    for (let i = 1; i < n; i++) {
      const w = 4 + (16 * i) / n;
      this.ctx.strokeStyle = glowColor;
      this.ctx.lineWidth = w + 10;
      this.ctx.beginPath();
      this.ctx.moveTo(pts[i - 1].x, pts[i - 1].y);
      this.ctx.lineTo(pts[i].x, pts[i].y);
      this.ctx.stroke();
    }

    // Inner blade core
    for (let i = 1; i < n; i++) {
      const w = 3 + (10 * i) / n;
      this.ctx.strokeStyle = coreColor;
      this.ctx.lineWidth = w;
      this.ctx.beginPath();
      this.ctx.moveTo(pts[i - 1].x, pts[i - 1].y);
      this.ctx.lineTo(pts[i].x, pts[i].y);
      this.ctx.stroke();

      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = Math.max(1, w - 3);
      this.ctx.stroke();
    }

    // Draw precision fingertip crosshair with directional guide
    const tip = pts[pts.length - 1];
    this.drawFingertipCrosshair(tip.x, tip.y, coreColor, label, dir);
  }

  drawFingertipCrosshair(x, y, color, label, dir = null) {
    this.ctx.save();

    // Directional laser pointer
    if (dir && (dir.x !== 0 || dir.y !== 0)) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
      this.ctx.lineTo(x + dir.x * 40, y + dir.y * 40);
      this.ctx.strokeStyle = color;
      this.ctx.lineWidth = 2.5;
      this.ctx.stroke();

      this.ctx.beginPath();
      this.ctx.arc(x + dir.x * 40, y + dir.y * 40, 3, 0, Math.PI * 2);
      this.ctx.fillStyle = '#ffffff';
      this.ctx.fill();
    }

    // Glowing center dot (physical fingertip)
    this.ctx.beginPath();
    this.ctx.arc(x, y, 9, 0, Math.PI * 2);
    this.ctx.fillStyle = color;
    this.ctx.globalAlpha = 0.45;
    this.ctx.fill();
    this.ctx.globalAlpha = 1.0;

    this.ctx.beginPath();
    this.ctx.arc(x, y, 5, 0, Math.PI * 2);
    this.ctx.fillStyle = '#ffffff';
    this.ctx.fill();

    // Crosshair ring
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    this.ctx.arc(x, y, 17, 0, Math.PI * 2);
    this.ctx.stroke();

    // Crosshair ticks
    const tick = 6;
    [0, Math.PI/2, Math.PI, 3*Math.PI/2].forEach(ang => {
      this.ctx.beginPath();
      this.ctx.moveTo(x + Math.cos(ang) * 17, y + Math.sin(ang) * 17);
      this.ctx.lineTo(x + Math.cos(ang) * (17 + tick), y + Math.sin(ang) * (17 + tick));
      this.ctx.stroke();
    });

    // Label with solid background badge
    this.ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    this.ctx.fillRect(x + 18, y - 24, 85, 18);
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 1;
    this.ctx.strokeRect(x + 18, y - 24, 85, 18);

    this.ctx.fillStyle = color;
    this.ctx.font = 'bold 10px Orbitron, monospace';
    this.ctx.fillText(label, x + 24, y - 11);
    this.ctx.restore();
  }

  drawDebugStats(now) {
    this.ctx.save();
    this.ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    this.ctx.fillRect(20, 120, 300, 190);
    this.ctx.strokeStyle = '#00f0ff';
    this.ctx.strokeRect(20, 120, 300, 190);

    this.ctx.fillStyle = '#ffd028';
    this.ctx.font = '14px Orbitron, monospace';
    this.ctx.fillText('[PRECISION TELEMETRY]', 35, 145);

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '12px Space Grotesk, monospace';
    this.ctx.fillText(`Render FPS: ${Math.round(this.fps)}`, 35, 172);
    this.ctx.fillText(`P1 Blade: ${Math.round(this.p1Speed)} px/s`, 35, 194);
    this.ctx.fillText(`P2 Blade: ${Math.round(this.p2Speed)} px/s`, 35, 216);
    this.ctx.fillText(`Min Slice Spd: ${CONFIG.minSliceSpeed} px/s`, 35, 238);
    this.ctx.fillText(`Hitbox Scale: ${CONFIG.hitboxMultiplier}x`, 35, 260);
    this.ctx.fillText(`2P Mode: ${CONFIG.dualFruitMode.toUpperCase()} TARGETS`, 35, 282);
    this.ctx.restore();
  }

  drawArcheryHUD() {
    this.ctx.save();
    // Round info badge at bottom left
    this.ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    this.ctx.strokeStyle = '#ffd028';
    this.ctx.lineWidth = 1.5;
    this.ctx.fillRect(20, CONFIG.windowH - 75, 230, 52);
    this.ctx.strokeRect(20, CONFIG.windowH - 75, 230, 52);

    this.ctx.fillStyle = '#ffd028';
    this.ctx.font = 'bold 15px Orbitron, monospace';
    this.ctx.textAlign = 'left';
    this.ctx.fillText(`ROUND ${this.archeryRound}`, 32, CONFIG.windowH - 52);

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = '12px Space Grotesk, monospace';
    this.ctx.fillText(`POPPED: ${this.scores.p1} BALLOONS`, 32, CONFIG.windowH - 33);

    // Quiver remaining at bottom right
    const quiverX = CONFIG.windowW - 240;
    const quiverY = CONFIG.windowH - 75;
    this.ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    this.ctx.strokeStyle = '#00f0ff';
    this.ctx.lineWidth = 1.5;
    this.ctx.fillRect(quiverX, quiverY, 220, 52);
    this.ctx.strokeRect(quiverX, quiverY, 220, 52);

    this.ctx.fillStyle = '#00f0ff';
    this.ctx.font = 'bold 13px Orbitron, monospace';
    this.ctx.textAlign = 'left';
    this.ctx.fillText(`QUIVER: ${this.archeryArrowsLeft} / 7 ARROWS`, quiverX + 16, quiverY + 22);

    for (let i = 0; i < 7; i++) {
      const ax = quiverX + 22 + i * 26;
      const ay = quiverY + 36;
      const hasArrow = i < this.archeryArrowsLeft;
      this.ctx.strokeStyle = hasArrow ? '#ffd028' : '#444c5c';
      this.ctx.lineWidth = 2.5;
      this.ctx.beginPath();
      this.ctx.moveTo(ax, ay + 6);
      this.ctx.lineTo(ax, ay - 6);
      this.ctx.stroke();

      this.ctx.fillStyle = hasArrow ? '#ffffff' : '#333842';
      this.ctx.beginPath();
      this.ctx.arc(ax, ay - 6, 2.5, 0, Math.PI * 2);
      this.ctx.fill();
    }
    this.ctx.restore();
  }

  loop() {
    const nowMs = performance.now();
    const dt = Math.min(0.1, (nowMs - this.lastFrameTime) / 1000);
    this.lastFrameTime = nowMs;
    this.fps = 0.92 * this.fps + 0.08 * (1 / (dt || 0.016));
    const now = nowMs / 1000;

    this.update(now, dt);
    this.draw(now);
    requestAnimationFrame(this.loop);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  new GameArena();
});
