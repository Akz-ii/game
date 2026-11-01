"""
FRUIT SLICE - ULTRA REFLEX & ACCURACY CHALLENGE
==============================================

How to play:
  1. Hold ONE hand up in front of the webcam (top right should say HAND OK).
  2. Aim your blade at the fruit.
  3. Press SPACE. A fruit floats in and you have to WAIT.
  4. The moment the word  CUT!  shows up, SWIPE YOUR HAND across the fruit like a sword!
  5. Slicing through the fruit wins the round, scoring your:
     - REACTION TIME (how quickly you started your swing)
     - SLICE SPEED (in px/s, how fast your blade moved)
     - CUT ACCURACY (% centered, based on how cleanly you cut through the bullseye)
     - OVERALL RANK (S+, S, A, B)
  6. Swipe too EARLY (before CUT!) or too SLOW (time runs out) and you lose.
  7. On the Title screen, you can do unlimited PRACTICE SLICES to test your speed and aim!

Run it with:   python slice_game.py
"""

import math
import os
import random
import threading
import time

import cv2
import mediapipe as mp
import numpy as np
import pygame


# =====================================================================
#  1. SETTINGS & CALIBRATION (safe to customize)
# =====================================================================

CAMERA_INDEX = 0             # 0 = default webcam. Try 1 or 2 if wrong camera opens
WINDOW_W, WINDOW_H = 960, 720

# --- Game timing (seconds) ---
WAIT_RANGE = (2.0, 4.5)      # CUT! appears after a random wait between these two numbers
ARM_DELAY = 0.7              # swipes in the first 0.7s of waiting are ignored (settle hand)
CUT_WINDOW = 1.6             # time you have to slice after CUT! appears
MIN_REACTION = 0.10          # faster than 100ms was anticipation/guess, not reaction

# --- Slicing Speed & Responsiveness ---
# Hand speed is measured in pixels per second (px/s).
# Lower thresholds = lighter, faster response; Higher = requires more deliberate swings.
MIN_SLICE_SPEED = 260.0      # min speed (px/s) to count as a slice stroke
MIN_SLICE_DIST = 42.0        # min pixels hand must travel during slice
SLICE_WINDOW = 0.32          # search window (seconds)
MAX_WOBBLE = 1.95            # maximum path-to-straight-line ratio (filters erratic movement)
EARLY_STRICTNESS = 1.4       # strictness multiplier during WAIT state (prevents false alarms)

# --- Slicing Accuracy & Hitbox ---
FRUIT_RADIUS = 110
FRUIT_HIT_RADIUS_MULT = 1.50 # Generous 1.5x hitbox for satisfying, reliable slicing
GRAVITY = 1750               # falling speed of sliced pieces (px/s^2)

# --- Hand Tracking Tuning ---
HAND_MODEL_COMPLEXITY = 0    # 0 = Lite model for ultra-fast 60+ FPS zero-lag tracking
DETECT_CONFIDENCE = 0.45
TRACK_CONFIDENCE = 0.45

# Performance camera resolution
CAM_W = 640
CAM_H = int(CAM_W * WINDOW_H / WINDOW_W)

# Ratings & Thresholds
SPEED_RATINGS = [
    (1800, "⚡ LIGHTNING SPEED!"),
    (1300, "🔥 BLAZING FAST!"),
    (900, "⚡ SWIFT CUT!"),
    (550, "SOLID SPEED"),
    (0, "CASUAL CUT"),
]

ACCURACY_RATINGS = [
    (92, "🎯 PERFECT BULLSEYE!"),
    (80, "✨ CLEAN SLICE!"),
    (65, "GOOD CUT"),
    (0, "GRAZE HIT"),
]

REACTION_RATINGS = [
    (320, "NINJA REFLEXES!"),
    (480, "LIGHTNING FAST!"),
    (680, "GREAT!"),
    (950, "GOOD"),
    (99999, "OK"),
]

# Color Palette
WHITE = (255, 255, 255)
YELLOW = (255, 225, 75)
RED = (255, 65, 65)
GREEN = (80, 240, 125)
ORANGE = (255, 155, 45)
CYAN = (85, 230, 255)
PURPLE = (190, 85, 255)
GRAY = (195, 200, 210)
DARK_GRAY = (35, 38, 48)


# =====================================================================
#  2. PROCEDURAL SYNTHESIZED AUDIO (No external files needed)
# =====================================================================

class SoundManager:
    """Generates crisp procedural audio effects using Pygame mixer."""
    def __init__(self):
        self.enabled = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.enabled = True
            self.snd_slice = self._make_slice_sound()
            self.snd_gong = self._make_gong_sound()
            self.snd_whoosh = self._make_whoosh_sound()
            self.snd_thud = self._make_thud_sound()
        except Exception as e:
            print(f"[audio] Audio disabled: {e}")

    def _to_stereo(self, arr):
        arr = np.ascontiguousarray(arr, dtype=np.int16)
        return np.ascontiguousarray(np.column_stack((arr, arr)))

    def _make_slice_sound(self):
        dur = 0.22
        sr = 44100
        t = np.linspace(0, dur, int(sr * dur), False)
        # Fast exponential frequency whoosh with blade friction noise
        freq = 300 + 1200 * np.exp(-t * 22)
        sweep = np.sin(2 * np.pi * freq * t)
        noise = np.random.uniform(-0.35, 0.35, len(t))
        envelope = np.exp(-t * 18)
        wave = (sweep * 0.75 + noise * 0.45) * envelope * 24000
        return pygame.sndarray.make_sound(self._to_stereo(wave))

    def _make_gong_sound(self):
        dur = 0.40
        sr = 44100
        t = np.linspace(0, dur, int(sr * dur), False)
        # Two harmonic bell tones
        tone1 = np.sin(2 * np.pi * 880 * t) * np.exp(-t * 7)
        tone2 = np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 14) * 0.5
        wave = (tone1 + tone2) * 18000
        return pygame.sndarray.make_sound(self._to_stereo(wave))

    def _make_whoosh_sound(self):
        dur = 0.16
        sr = 44100
        t = np.linspace(0, dur, int(sr * dur), False)
        noise = np.random.uniform(-0.5, 0.5, len(t))
        envelope = np.sin(np.pi * (t / dur))
        wave = noise * envelope * 14000
        return pygame.sndarray.make_sound(self._to_stereo(wave))

    def _make_thud_sound(self):
        dur = 0.25
        sr = 44100
        t = np.linspace(0, dur, int(sr * dur), False)
        wave = np.sin(2 * np.pi * 90 * t) * np.exp(-t * 15) * 22000
        return pygame.sndarray.make_sound(self._to_stereo(wave))

    def play_slice(self):
        if self.enabled:
            self.snd_slice.play()

    def play_cut_signal(self):
        if self.enabled:
            self.snd_gong.play()

    def play_whoosh(self):
        if self.enabled:
            self.snd_whoosh.play()

    def play_thud(self):
        if self.enabled:
            self.snd_thud.play()


# =====================================================================
#  3. PROCEDURAL FRUITS & REALISTIC OFF-CENTER CUTS
# =====================================================================

FRUITS = {
    "apple":  {"skin": (210, 35, 45),  "flesh": (252, 240, 210), "core": (235, 215, 160), "seed": (80, 45, 30)},
    "orange": {"skin": (255, 135, 20), "flesh": (255, 195, 70),  "core": (255, 220, 120), "seed": (255, 230, 160)},
    "lime":   {"skin": (80, 175, 45),  "flesh": (195, 240, 115), "core": (220, 245, 150), "seed": (235, 250, 190)},
    "plum":   {"skin": (115, 45, 145), "flesh": (245, 185, 90),  "core": (225, 160, 70),  "seed": (110, 70, 40)},
}


def shade(color, amount):
    return tuple(max(0, min(255, int(c + amount))) for c in color)


def make_fruit(kind, r, cut):
    f = FRUITS[kind]
    pad = int(r * 0.45)
    size = 2 * (r + pad)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2

    if cut:
        pygame.draw.circle(surf, f["skin"], (c, c), r)
        pygame.draw.circle(surf, f["flesh"], (c, c), int(r * 0.88))
        pygame.draw.circle(surf, f["core"], (c, c), int(r * 0.30))
        for i in range(6):
            angle = math.radians(i * 60 + 15)
            sx = c + math.cos(angle) * r * 0.45
            sy = c + math.sin(angle) * r * 0.45
            pygame.draw.ellipse(surf, f["seed"], (int(sx - 5), int(sy - 8), 10, 16))
    else:
        o = int(r * 0.06)
        pygame.draw.circle(surf, shade(f["skin"], -45), (c, c), r)
        pygame.draw.circle(surf, f["skin"], (c - o, c - o), int(r * 0.93))
        pygame.draw.circle(surf, shade(f["skin"], 30), (c - int(r * 0.22), c - int(r * 0.22)), int(r * 0.5))
        pygame.draw.ellipse(surf, shade(f["skin"], 110),
                            (c - int(r * 0.58), c - int(r * 0.64), int(r * 0.42), int(r * 0.26)))
        if kind in ("apple", "plum"):
            pygame.draw.line(surf, (90, 55, 30), (c, c - int(r * 0.85)),
                             (c + int(r * 0.1), c - int(r * 1.3)), 8)
        if kind in ("apple", "orange"):
            pygame.draw.ellipse(surf, (70, 175, 60),
                                (c + int(r * 0.12), c - int(r * 1.12), int(r * 0.44), int(r * 0.22)))
        if kind == "lime":
            pygame.draw.circle(surf, shade(f["skin"], -60), (c, c - r + 6), 7)
    return surf


def make_halves(kind, r, direction, cut_offset=(0, 0)):
    """
    Cut fruit with an accurate cut line that passes through the exact offset
    where the player sliced through the fruit.
    """
    full = make_fruit(kind, r, cut=True)
    size = full.get_width()
    c = size / 2
    dx, dy = direction
    nx, ny = -dy, dx
    length = size * 2

    # Clamp cut offset so polygon doesn't clip past the entire fruit
    max_off = r * 0.72
    ox = max(-max_off, min(max_off, cut_offset[0]))
    oy = max(-max_off, min(max_off, cut_offset[1]))
    c_cut_x = c + ox
    c_cut_y = c + oy

    halves = []
    for side in (1, -1):
        half = full.copy()
        erase = -side
        points = [
            (c_cut_x + dx * length, c_cut_y + dy * length),
            (c_cut_x - dx * length, c_cut_y - dy * length),
            (c_cut_x - dx * length + erase * nx * length, c_cut_y - dy * length + erase * ny * length),
            (c_cut_x + dx * length + erase * nx * length, c_cut_y + dy * length + erase * ny * length),
        ]
        pygame.draw.polygon(half, (0, 0, 0, 0), points)
        halves.append(half)
    return halves, (nx, ny), (ox, oy)


def new_fruit(x=None, y=None):
    if x is None:
        x = WINDOW_W / 2
    if y is None:
        y = WINDOW_H / 2 + 25
    return {
        "kind": random.choice(list(FRUITS)),
        "x": x, "y": y,
        "state": "whole",
        "vy": 0.0,
        "halves": [],
        "particles": [],
        "slash": None,
    }


def fruit_center(fruit, now):
    if fruit["state"] == "whole":
        return fruit["x"], fruit["y"] + 8 * math.sin(now * 2.5)
    return fruit["x"], fruit["y"]


def slice_fruit(fruit, direction, now, cut_offset=(0, 0)):
    """Accurately slice the fruit along the user's stroke."""
    cx, cy = fruit_center(fruit, now)
    halves, (nx, ny), (ox, oy) = make_halves(fruit["kind"], FRUIT_RADIUS, direction, cut_offset)
    fruit["state"] = "sliced"
    fruit["halves"] = []

    for side, surf in zip((1, -1), halves):
        fruit["halves"].append({
            "surf": surf, "x": cx, "y": cy,
            "vx": side * nx * 290 + random.uniform(-40, 40),
            "vy": side * ny * 290 - 150,
            "angle": 0.0, "spin": side * random.uniform(70, 160),
        })

    colors = [FRUITS[fruit["kind"]]["flesh"], FRUITS[fruit["kind"]]["skin"], YELLOW, WHITE]
    cut_center_x = cx + ox
    cut_center_y = cy + oy

    # Fruit juice splash + sparks
    for _ in range(45):
        side = random.choice((1, -1))
        speed = random.uniform(180, 680)
        angle = math.atan2(side * ny, side * nx) + random.uniform(-0.85, 0.85)
        fruit["particles"].append({
            "x": cut_center_x, "y": cut_center_y,
            "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed - 130,
            "life": random.uniform(0.4, 0.95), "r": random.randint(4, 9),
            "color": random.choice(colors)
        })

    fruit["slash"] = {
        "t": now, "x": cut_center_x, "y": cut_center_y,
        "dx": direction[0], "dy": direction[1]
    }


def update_fruit(fruit, dt):
    for h in fruit["halves"]:
        h["vy"] += GRAVITY * dt
        h["x"] += h["vx"] * dt
        h["y"] += h["vy"] * dt
        h["angle"] += h["spin"] * dt
    for p in fruit["particles"]:
        p["vy"] += GRAVITY * 0.7 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["life"] -= dt
    fruit["particles"] = [p for p in fruit["particles"] if p["life"] > 0]
    if fruit["state"] == "falling":
        fruit["vy"] += GRAVITY * dt
        fruit["y"] += fruit["vy"] * dt


def draw_fruit(screen, fruit, whole_surfaces, now, glow):
    cx, cy = fruit_center(fruit, now)
    int_c = (int(cx), int(cy))

    if fruit["state"] in ("whole", "falling"):
        surf = whole_surfaces[fruit["kind"]]
        screen.blit(surf, surf.get_rect(center=int_c))

        if fruit["state"] == "whole":
            # Precision aim reticle & bullseye guide
            aim_color = (255, 255, 255, 90)
            reticle_surf = pygame.Surface((FRUIT_RADIUS * 3, FRUIT_RADIUS * 3), pygame.SRCALPHA)
            rc = FRUIT_RADIUS * 1.5

            # Subtle circular aim guide
            pygame.draw.circle(reticle_surf, (255, 255, 255, 60), (rc, rc), FRUIT_RADIUS, 2)
            # Bullseye center zone (sweet spot for 95-100% accuracy)
            pygame.draw.circle(reticle_surf, (255, 220, 80, 110), (rc, rc), int(FRUIT_RADIUS * 0.28), 2)
            pygame.draw.circle(reticle_surf, (255, 255, 255, 140), (rc, rc), 4)

            # Crosshair ticks
            tick_len = 14
            for ang in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
                x1 = rc + math.cos(ang) * (FRUIT_RADIUS - tick_len)
                y1 = rc + math.sin(ang) * (FRUIT_RADIUS - tick_len)
                x2 = rc + math.cos(ang) * (FRUIT_RADIUS + tick_len)
                y2 = rc + math.sin(ang) * (FRUIT_RADIUS + tick_len)
                pygame.draw.line(reticle_surf, (255, 255, 255, 90), (x1, y1), (x2, y2), 2)

            screen.blit(reticle_surf, (cx - rc, cy - rc))

            if glow:
                # Pulsing electric aura when CUT! is active
                radius = FRUIT_RADIUS + 22 + int(9 * math.sin(now * 22))
                pygame.draw.circle(screen, YELLOW, int_c, radius, 7)
                pygame.draw.circle(screen, RED, int_c, radius + 8, 3)

    for h in fruit["halves"]:
        rotated = pygame.transform.rotate(h["surf"], h["angle"])
        screen.blit(rotated, rotated.get_rect(center=(int(h["x"]), int(h["y"]))))

    for p in fruit["particles"]:
        radius = max(1, int(p["r"] * min(1.0, p["life"] / 0.4)))
        pygame.draw.circle(screen, p["color"], (int(p["x"]), int(p["y"])), radius)

    s = fruit["slash"]
    if s:
        age = now - s["t"]
        if age < 0.26:
            half_len = FRUIT_RADIUS * 1.85
            a = (s["x"] - s["dx"] * half_len, s["y"] - s["dy"] * half_len)
            b = (s["x"] + s["dx"] * half_len, s["y"] + s["dy"] * half_len)
            # Outer cyan glow
            w = max(2, int(22 * (1 - age / 0.26)))
            pygame.draw.line(screen, CYAN, a, b, w + 12)
            # Core white blade line
            pygame.draw.line(screen, WHITE, a, b, w)


# =====================================================================
#  4. MATH & SLICING ACCURACY ENGINE
# =====================================================================

def dist_segment_to_point(p1, p2, p):
    """
    Computes minimum distance from point p to segment p1->p2.
    Returns (distance, projected_point, t).
    """
    x1, y1 = p1
    x2, y2 = p2
    px, py = p
    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-6:
        return math.hypot(px - x1, py - y1), (x1, y1), 0.0
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    dist = math.hypot(px - proj_x, py - proj_y)
    return dist, (proj_x, proj_y), t


class AdaptiveBladeFilter:
    """
    Zero-latency adaptive filter:
    - Filters camera jitter at rest so the reticle is steady.
    - Swings into 100% RAW pass-through at high swipe speed for zero delay.
    """
    def __init__(self, min_cutoff=3.5, beta=0.22):
        self.x_prev = None
        self.y_prev = None
        self.dx = 0.0
        self.dy = 0.0
        self.t_prev = None
        self.min_cutoff = min_cutoff
        self.beta = beta

    def filter(self, x, y, t):
        if self.x_prev is None or self.t_prev is None:
            self.x_prev, self.y_prev, self.t_prev = x, y, t
            return x, y, 0.0
        dt = max(1e-4, t - self.t_prev)
        self.t_prev = t

        vx = (x - self.x_prev) / dt
        vy = (y - self.y_prev) / dt
        speed = math.hypot(vx, vy)

        self.dx = 0.65 * self.dx + 0.35 * vx
        self.dy = 0.65 * self.dy + 0.35 * vy
        smooth_speed = math.hypot(self.dx, self.dy)

        # Dynamic smoothing factor: alpha goes to 1.0 (zero lag) when moving or swiping
        cutoff = self.min_cutoff + self.beta * smooth_speed
        tau = 1.0 / (2.0 * math.pi * cutoff)
        alpha = 1.0 / (1.0 + tau / dt)
        alpha = min(1.0, max(0.70, alpha))

        if smooth_speed > 220:
            alpha = 1.0

        x_hat = alpha * x + (1.0 - alpha) * self.x_prev
        y_hat = alpha * y + (1.0 - alpha) * self.y_prev
        self.x_prev, self.y_prev = x_hat, y_hat
        return x_hat, y_hat, smooth_speed


# =====================================================================
#  5. ASYNC HIGH-SPEED VISION THREAD
# =====================================================================

def open_camera():
    backends = [cv2.CAP_ANY]
    if os.name == "nt":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(CAMERA_INDEX, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 60)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        for _ in range(25):
            ok, frame = cap.read()
            if ok and frame is not None:
                print(f"[camera] active on backend {backend}")
                return cap
            time.sleep(0.08)
        cap.release()
    return None


def grab_frame(cap):
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    h, w = frame.shape[:2]
    target = WINDOW_W / WINDOW_H
    if w / h > target:
        new_w = int(h * target)
        x0 = (w - new_w) // 2
        frame = frame[:, x0:x0 + new_w]
    else:
        new_h = int(w / target)
        y0 = (h - new_h) // 2
        frame = frame[y0:y0 + new_h]
    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (WINDOW_W, WINDOW_H), interpolation=cv2.INTER_LINEAR)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


class VisionThread:
    """
    Dedicated worker thread running Camera Capture + MediaPipe Hands asynchronously.
    Prevents any main-loop frame drops and delivers instantaneous 2-player landmark data.
    """
    def __init__(self, cap):
        self.cap = cap
        self.lock = threading.Lock()
        self.running = True
        self.frame_rgb = None
        self.stamp = 0.0
        self.frame_id = 0
        self.point = None
        self.speed = 0.0
        self.is_tracked = False
        self.landmarks = []

        # Persistent Dual Player tracking
        self.filter_p1 = AdaptiveBladeFilter(min_cutoff=3.5, beta=0.22)
        self.filter_p2 = AdaptiveBladeFilter(min_cutoff=3.5, beta=0.22)
        self.p1_point = None
        self.p1_speed = 0.0
        self.p1_tracked = False
        self.p2_point = None
        self.p2_speed = 0.0
        self.p2_tracked = False
        self.p1_last_seen = 0.0
        self.p2_last_seen = 0.0

        self.fps = 0.0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=HAND_MODEL_COMPLEXITY,
            min_detection_confidence=DETECT_CONFIDENCE,
            min_tracking_confidence=TRACK_CONFIDENCE
        )
        fps_t0 = time.perf_counter()
        fps_frames = 0

        while self.running:
            rgb = grab_frame(self.cap)
            if rgb is None:
                time.sleep(0.003)
                continue
            stamp = time.perf_counter()
            fps_frames += 1
            if stamp - fps_t0 >= 1.0:
                self.fps = fps_frames / (stamp - fps_t0)
                fps_frames = 0
                fps_t0 = stamp

            small_rgb = cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LINEAR)
            small_rgb.flags.writeable = False
            results = hands.process(small_rgb)
            small_rgb.flags.writeable = True

            detected_hands = []
            all_lms_pts = []

            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    lms_pts = []
                    for lm in hand_lms.landmark:
                        lx = min(max(lm.x, 0.0), 1.0) * WINDOW_W
                        ly = min(max(lm.y, 0.0), 1.0) * WINDOW_H
                        lms_pts.append((lx, ly))
                    tip = lms_pts[8]
                    detected_hands.append({"tip": tip, "lms": lms_pts})
                    all_lms_pts.extend(lms_pts)

            # Persistent Hand Assignment (P1 Left vs P2 Right)
            p1_raw = None
            p2_raw = None

            if len(detected_hands) >= 2:
                h0 = detected_hands[0]["tip"]
                h1 = detected_hands[1]["tip"]

                anchor_p1 = self.p1_point or (WINDOW_W * 0.28, WINDOW_H * 0.5)
                anchor_p2 = self.p2_point or (WINDOW_W * 0.72, WINDOW_H * 0.5)

                d1_0 = math.hypot(h0[0] - anchor_p1[0], h0[1] - anchor_p1[1])
                d2_1 = math.hypot(h1[0] - anchor_p2[0], h1[1] - anchor_p2[1])
                bias1 = (250 if h0[0] > WINDOW_W * 0.5 else 0) + (250 if h1[0] < WINDOW_W * 0.5 else 0)
                cost1 = d1_0 + d2_1 + bias1

                d1_1 = math.hypot(h1[0] - anchor_p1[0], h1[1] - anchor_p1[1])
                d2_0 = math.hypot(h0[0] - anchor_p2[0], h0[1] - anchor_p2[1])
                bias2 = (250 if h1[0] > WINDOW_W * 0.5 else 0) + (250 if h0[0] < WINDOW_W * 0.5 else 0)
                cost2 = d1_1 + d2_0 + bias2

                if cost1 <= cost2:
                    p1_raw = h0
                    p2_raw = h1
                else:
                    p1_raw = h1
                    p2_raw = h0

            elif len(detected_hands) == 1:
                h = detected_hands[0]["tip"]
                p1_active = (stamp - self.p1_last_seen < 0.45)
                p2_active = (stamp - self.p2_last_seen < 0.45)

                if p1_active and not p2_active:
                    p1_raw = h
                elif p2_active and not p1_active:
                    p2_raw = h
                else:
                    if h[0] < WINDOW_W * 0.50:
                        p1_raw = h
                    else:
                        p2_raw = h

            with self.lock:
                self.frame_rgb = rgb
                self.stamp = stamp
                self.frame_id += 1
                self.landmarks = all_lms_pts

                if p1_raw is not None:
                    sx, sy, cur_spd = self.filter_p1.filter(p1_raw[0], p1_raw[1], stamp)
                    self.p1_point = (sx, sy)
                    self.p1_speed = cur_spd
                    self.p1_tracked = True
                    self.p1_last_seen = stamp
                else:
                    if stamp - self.p1_last_seen > 0.35:
                        self.p1_tracked = False

                if p2_raw is not None:
                    sx2, sy2, cur_spd2 = self.filter_p2.filter(p2_raw[0], p2_raw[1], stamp)
                    self.p2_point = (sx2, sy2)
                    self.p2_speed = cur_spd2
                    self.p2_tracked = True
                    self.p2_last_seen = stamp
                else:
                    if stamp - self.p2_last_seen > 0.35:
                        self.p2_tracked = False

                # Global pointer for single-player / legacy compatibility
                if self.p1_tracked:
                    self.point = self.p1_point
                    self.speed = self.p1_speed
                    self.is_tracked = True
                elif self.p2_tracked:
                    self.point = self.p2_point
                    self.speed = self.p2_speed
                    self.is_tracked = True
                else:
                    self.point = None
                    self.speed = 0.0
                    self.is_tracked = False

        hands.close()

    def latest(self):
        with self.lock:
            return {
                "rgb": self.frame_rgb,
                "stamp": self.stamp,
                "frame_id": self.frame_id,
                "point": self.point,
                "speed": self.speed,
                "is_tracked": self.is_tracked,
                "p1_point": self.p1_point,
                "p1_speed": self.p1_speed,
                "p1_tracked": self.p1_tracked,
                "p2_point": self.p2_point,
                "p2_speed": self.p2_speed,
                "p2_tracked": self.p2_tracked,
                "landmarks": list(self.landmarks),
                "fps": self.fps,
            }

    def stop(self):
        self.running = False
        self.thread.join(timeout=1.0)


# =====================================================================
#  6. ACCURATE SLICE DETECTOR
# =====================================================================

class SliceDetector:
    """
    Evaluates hand trajectory history and detects both:
    1. Slicing Speed (instantaneous and peak stroke velocity).
    2. Slicing Accuracy (exact line-circle continuous collision with the fruit).
    """
    def __init__(self):
        self.history = []
        self.last_slice_time = 0.0
        self.cooldown = 0.22

    def add_sample(self, t, x, y, speed):
        self.history.append((t, x, y, speed))
        # Keep only recent samples
        self.history = [p for p in self.history if t - p[0] <= 0.40]

    def reset(self):
        self.history.clear()
        self.last_slice_time = 0.0

    def check_slice(self, now, fruit_center, fruit_radius, strict=1.0):
        if now - self.last_slice_time < self.cooldown:
            return None
        if len(self.history) < 2:
            return None

        newest_t, x1, y1, spd1 = self.history[-1]
        if now - newest_t > 0.15:
            return None

        recent = [p for p in self.history if newest_t - p[0] <= SLICE_WINDOW]
        if len(recent) < 2:
            return None

        min_dist = MIN_SLICE_DIST * strict
        min_speed = MIN_SLICE_SPEED * strict

        # Check from newest to oldest for the fastest stroke
        for j in range(len(recent) - 2, -1, -1):
            t0, x0, y0, spd0 = recent[j]
            dt = newest_t - t0
            if dt <= 0.01:
                continue
            dist = math.hypot(x1 - x0, y1 - y0)
            if dist < min_dist:
                continue
            avg_speed = dist / dt
            peak_spd = max(p[3] for p in recent[j:])
            if avg_speed < min_speed and peak_spd < min_speed * 1.15:
                continue

            # Path wobble check
            total_path = 0.0
            for k in range(j, len(recent) - 1):
                total_path += math.hypot(recent[k+1][1] - recent[k][1], recent[k+1][2] - recent[k][2])
            if total_path > MAX_WOBBLE * dist:
                continue

            dx = (x1 - x0) / dist
            dy = (y1 - y0) / dist

            # Arc Raycasting: Check every sub-segment in the stroke!
            best_hit_dist = float("inf")
            best_proj = (fruit_center[0], fruit_center[1])
            best_dir = (dx, dy)

            for k in range(len(recent) - 1, j, -1):
                pA = (recent[k - 1][1], recent[k - 1][2])
                pB = (recent[k][1], recent[k][2])
                d_seg, proj, _ = dist_segment_to_point(pA, pB, fruit_center)
                if d_seg < best_hit_dist:
                    best_hit_dist = d_seg
                    best_proj = proj
                    seg_len = math.hypot(pB[0] - pA[0], pB[1] - pA[1]) or 1.0
                    best_dir = ((pB[0] - pA[0]) / seg_len, (pB[1] - pA[1]) / seg_len)

            hit_radius = fruit_radius * FRUIT_HIT_RADIUS_MULT
            is_hit = best_hit_dist <= hit_radius
            accuracy_pct = max(0.0, min(100.0, (1.0 - (best_hit_dist / hit_radius)) * 100.0))
            cut_offset = (best_proj[0] - fruit_center[0], best_proj[1] - fruit_center[1])

            if is_hit or j == 0:
                self.last_slice_time = now
                return {
                    "hit": is_hit,
                    "direction": best_dir,
                    "peak_speed": max(peak_spd, avg_speed),
                    "avg_speed": avg_speed,
                    "accuracy": accuracy_pct,
                    "dist_to_center": best_hit_dist,
                    "cut_offset": cut_offset,
                    "start_pt": (x0, y0),
                    "end_pt": (x1, y1),
                }
        return None


# =====================================================================
#  7. DRAWING HELPERS & HUD
# =====================================================================

_fonts = {}

def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def draw_text(screen, text, size, color, x, y, align="center"):
    image = font(size).render(text, True, color)
    shadow = font(size).render(text, True, (0, 0, 0))
    rect = image.get_rect()
    if align == "center":
        rect.center = (x, y)
    elif align == "left":
        rect.midleft = (x, y)
    else:
        rect.midright = (x, y)
    screen.blit(shadow, rect.move(3, 3))
    screen.blit(image, rect)


def draw_trail(screen, history, now, show_tip, current_speed, custom_color=None, custom_glow=None, label=None):
    """Glowing energy blade trail with speed sparks."""
    points = [(x, y) for (t, x, y, s) in history if now - t <= 0.28]
    if len(points) < 2:
        if points and show_tip:
            tip = (int(points[-1][0]), int(points[-1][1]))
            tip_col = custom_color or CYAN
            pygame.draw.circle(screen, tip_col, tip, 16, 2)
            pygame.draw.circle(screen, WHITE, tip, 6)
            if label:
                draw_text(screen, label, 20, tip_col, tip[0] + 16, tip[1] - 12, align="left")
        return

    # Color changes based on current slicing speed or player
    if custom_color:
        trail_color = custom_color
        glow_color = custom_glow or (min(255, custom_color[0] + 40), min(255, custom_color[1] + 40), min(255, custom_color[2] + 40))
    else:
        if current_speed > 1400:
            trail_color = RED
            glow_color = ORANGE
        elif current_speed > 800:
            trail_color = YELLOW
            glow_color = (255, 140, 40)
        else:
            trail_color = CYAN
            glow_color = (40, 140, 255)

    n = len(points)
    # Outer glow
    for i in range(1, n):
        width = 3 + int(14 * i / n)
        pygame.draw.line(screen, glow_color, points[i - 1], points[i], width + 10)
    # Inner blade core
    for i in range(1, n):
        width = 2 + int(10 * i / n)
        pygame.draw.line(screen, trail_color, points[i - 1], points[i], width + 3)
        pygame.draw.line(screen, WHITE, points[i - 1], points[i], max(1, width - 2))

    if show_tip:
        tip = (int(points[-1][0]), int(points[-1][1]))
        pygame.draw.circle(screen, glow_color, tip, 18, 2)
        pygame.draw.circle(screen, trail_color, tip, 12, 2)
        pygame.draw.circle(screen, WHITE, tip, 6)
        if label:
            draw_text(screen, label, 20, trail_color, tip[0] + 16, tip[1] - 12, align="left")


def draw_speedometer(screen, current_speed, x, y):
    """Live interactive speedometer HUD."""
    w, h = 220, 20
    # Background glass
    bg_rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, (25, 28, 38), bg_rect, border_radius=10)
    pygame.draw.rect(screen, (60, 65, 80), bg_rect, 2, border_radius=10)

    # Speed ratio
    max_gauge_speed = 2200.0
    fill_ratio = min(1.0, max(0.0, current_speed / max_gauge_speed))
    fill_w = int(w * fill_ratio)

    if fill_ratio > 0.70:
        bar_color = RED
    elif fill_ratio > 0.40:
        bar_color = YELLOW
    elif fill_ratio > 0.20:
        bar_color = GREEN
    else:
        bar_color = CYAN

    if fill_w > 0:
        fill_rect = pygame.Rect(x, y, fill_w, h)
        pygame.draw.rect(screen, bar_color, fill_rect, border_radius=10)

    # Speed label
    draw_text(screen, f"SWIPE SPEED: {current_speed:.0f} px/s", 26, bar_color if current_speed > 400 else GRAY, x + w // 2, y - 14)


def draw_hud(screen, stats, hand_visible, current_speed, fps, mode="SOLO", dual_scores=None):
    if mode == "DUEL":
        p1_w = dual_scores["p1"] if dual_scores else 0
        p2_w = dual_scores["p2"] if dual_scores else 0
        draw_text(screen, f"P1 (CYAN): {p1_w}   VS   P2 (RED): {p2_w}", 40, YELLOW, WINDOW_W // 2, 28)
        draw_text(screen, "[2-PLAYER DUEL] (TAB = Solo)", 24, WHITE, WINDOW_W // 2, 60)
        draw_speedometer(screen, current_speed, WINDOW_W - 240, 72)
    else:
        best = f"{stats['best']:.0f} ms" if stats["best"] is not None else "-"
        draw_text(screen, f"WINS  {stats['wins']} / {stats['rounds']}", 36, WHITE, 20, 28, align="left")
        draw_text(screen, f"BEST  {best}", 30, GRAY, 20, 62, align="left")
        draw_text(screen, "[SOLO] (TAB = 2-Player)", 24, GRAY, 20, 92, align="left")

        if hand_visible:
            draw_text(screen, "BLADE READY", 30, GREEN, WINDOW_W - 20, 28, align="right")
        else:
            draw_text(screen, "NO HAND FOUND", 30, RED, WINDOW_W - 20, 28, align="right")

        draw_speedometer(screen, current_speed, WINDOW_W - 240, 72)


def get_rating_text(ratings_list, value):
    for limit, text in ratings_list:
        if value >= limit:
            return text
    return ratings_list[-1][1]


def get_reaction_text(reaction_ms):
    for limit, text in REACTION_RATINGS:
        if reaction_ms < limit:
            return text
    return REACTION_RATINGS[-1][1]


def calculate_rank(reaction_ms, speed_px, accuracy_pct):
    if reaction_ms < 420 and speed_px >= 1200 and accuracy_pct >= 88:
        return "S+", (255, 215, 0)
    elif reaction_ms < 600 and speed_px >= 900 and accuracy_pct >= 78:
        return "S", YELLOW
    elif reaction_ms < 850 and speed_px >= 600 and accuracy_pct >= 65:
        return "A", GREEN
    elif reaction_ms < 1100:
        return "B", CYAN
    else:
        return "C", GRAY


def draw_result(screen, outcome, reaction_ms, slice_speed, slice_acc, mode="SOLO"):
    if outcome == "p1_win":
        draw_text(screen, "PLAYER 1 (LEFT) WINS!", 90, CYAN, WINDOW_W // 2, 85)
        draw_text(screen, f"CYAN BLADE SLICED FIRST!  SPEED: {slice_speed:.0f} px/s", 42, WHITE, WINDOW_W // 2, 175)
        draw_text(screen, f"CUT ACCURACY: {slice_acc:.0f}%", 42, YELLOW, WINDOW_W // 2, 230)
    elif outcome == "p2_win":
        draw_text(screen, "PLAYER 2 (RIGHT) WINS!", 90, RED, WINDOW_W // 2, 85)
        draw_text(screen, f"RED BLADE SLICED FIRST!  SPEED: {slice_speed:.0f} px/s", 42, WHITE, WINDOW_W // 2, 175)
        draw_text(screen, f"CUT ACCURACY: {slice_acc:.0f}%", 42, YELLOW, WINDOW_W // 2, 230)
    elif outcome == "win":
        rank, rank_color = calculate_rank(reaction_ms, slice_speed, slice_acc)
        title = "PERFECT BULLSEYE!" if slice_acc >= 90 else "NICE CUT!"
        draw_text(screen, title, 110, GREEN if slice_acc < 90 else YELLOW, WINDOW_W // 2, 85)

        # Multi-metric score breakdown
        draw_text(screen, f"REACTION: {reaction_ms:.0f} ms  ({get_reaction_text(reaction_ms)})", 44, WHITE, WINDOW_W // 2, 160)
        draw_text(screen, f"SLICE SPEED: {slice_speed:.0f} px/s  ({get_rating_text(SPEED_RATINGS, slice_speed)})", 44, CYAN, WINDOW_W // 2, 208)
        draw_text(screen, f"CUT ACCURACY: {slice_acc:.0f}%  ({get_rating_text(ACCURACY_RATINGS, slice_acc)})", 44, YELLOW, WINDOW_W // 2, 256)

        # Big Rank Emblem
        draw_text(screen, f"RANK  {rank}", 72, rank_color, WINDOW_W // 2, 320)

    elif outcome == "early":
        draw_text(screen, "TOO EARLY!", 120, RED, WINDOW_W // 2, 100)
        draw_text(screen, "You swiped before  CUT!  appeared.", 42, WHITE, WINDOW_W // 2, 185)
        draw_text(screen, "Wait for the CUT! signal before slashing.", 34, GRAY, WINDOW_W // 2, 235)
    else:
        draw_text(screen, "TOO SLOW!", 120, ORANGE, WINDOW_W // 2, 100)
        draw_text(screen, "Time ran out - the fruit dropped away.", 42, WHITE, WINDOW_W // 2, 185)
        draw_text(screen, "Be ready to slash fast the instant CUT! appears!", 34, GRAY, WINDOW_W // 2, 235)

    draw_text(screen, "PRESS SPACE FOR NEXT ROUND   |   ESC = QUIT", 36, YELLOW, WINDOW_W // 2, WINDOW_H - 40)


def draw_title(screen, practice_feedback=None, practice_time=0.0, mode="SOLO"):
    draw_text(screen, "FRUIT SLICE", 125, YELLOW, WINDOW_W // 2, 85)
    subtitle = "Reflex, Speed & Accuracy Challenge" if mode == "SOLO" else "2-PLAYER DUEL: Left Fruit (P1 Cyan) vs Right Fruit (P2 Red)"
    draw_text(screen, subtitle, 36, CYAN if mode == "SOLO" else YELLOW, WINDOW_W // 2, 145)

    # Practice slice feedback banner
    now = time.perf_counter()
    if practice_feedback and (now - practice_time < 1.3):
        spd = practice_feedback["speed"]
        acc = practice_feedback["acc"]
        p_name = practice_feedback.get("player", "")
        txt = f"{p_name} PRACTICE HIT!  SPEED: {spd:.0f} px/s  |  ACCURACY: {acc:.0f}%"
        draw_text(screen, txt, 38, GREEN if acc >= 80 else YELLOW, WINDOW_W // 2, 205)
    else:
        draw_text(screen, "⚔️ Try practice slices on the fruit targets! ⚔️", 32, WHITE, WINDOW_W // 2, 205)

    draw_text(screen, "1. Hold hand(s) up until BLADE READY appears.", 30, WHITE, WINDOW_W // 2, 530)
    draw_text(screen, "2. Press TAB to switch between Solo & 2-Player Duel mode.", 30, YELLOW, WINDOW_W // 2, 564)
    draw_text(screen, "3. When  CUT!  appears, SWIPE FAST across the fruit to score!", 30, WHITE, WINDOW_W // 2, 598)

    size = 54 + int(5 * math.sin(time.perf_counter() * 5))
    draw_text(screen, "PRESS SPACE TO START", size, YELLOW, WINDOW_W // 2, 650)
    draw_text(screen, "TAB = Switch Mode (Solo/Duel)   |   ESC = Quit   |   D = Debug", 26, GRAY, WINDOW_W // 2, 695)


def draw_debug_overlay(screen, vision_data, fruit, slice_detector):
    """Debug overlay for calibration and inspection."""
    fps = vision_data["fps"]
    spd = vision_data["speed"]
    pt = vision_data["point"]
    cx, cy = fruit_center(fruit, time.perf_counter())

    # Debug panel background
    surf = pygame.Surface((360, 200), pygame.SRCALPHA)
    surf.fill((20, 25, 35, 210))
    screen.blit(surf, (15, 110))

    draw_text(screen, f"[DEBUG STATS]", 24, YELLOW, 25, 125, align="left")
    draw_text(screen, f"Vision FPS: {fps:.1f}", 22, WHITE, 25, 150, align="left")
    draw_text(screen, f"Hand Speed: {spd:.0f} px/s", 22, WHITE, 25, 172, align="left")
    draw_text(screen, f"Hand Tracked: {vision_data['is_tracked']}", 22, GREEN if vision_data['is_tracked'] else RED, 25, 194, align="left")
    if pt:
        draw_text(screen, f"Blade Point: ({pt[0]:.0f}, {pt[1]:.0f})", 22, WHITE, 25, 216, align="left")
    draw_text(screen, f"Min Slice Spd: {MIN_SLICE_SPEED:.0f} px/s", 22, GRAY, 25, 238, align="left")
    draw_text(screen, f"Min Slice Dist: {MIN_SLICE_DIST:.0f} px", 22, GRAY, 25, 260, align="left")
    draw_text(screen, f"Hit Radius: {FRUIT_RADIUS * FRUIT_HIT_RADIUS_MULT:.0f} px", 22, GRAY, 25, 282, align="left")

    # Draw hit area wireframe
    hit_r = int(FRUIT_RADIUS * FRUIT_HIT_RADIUS_MULT)
    pygame.draw.circle(screen, (255, 0, 0), (int(cx), int(cy)), hit_r, 2)


# =====================================================================
#  8. MAIN GAME LOOP
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Fruit Slice - Reflex & Accuracy Challenge")
    clock = pygame.time.Clock()

    sounds = SoundManager()

    cap = open_camera()
    if cap is None:
        print("Could not open camera. Please check camera connections and privacy settings.")
        pygame.quit()
        return

    vision = VisionThread(cap)
    detector_p1 = SliceDetector()
    detector_p2 = SliceDetector()

    whole_surfaces = {kind: make_fruit(kind, FRUIT_RADIUS, cut=False) for kind in FRUITS}
    dim = pygame.Surface((WINDOW_W, WINDOW_H))
    dim.set_alpha(70)
    dim.fill((0, 0, 0))

    state = "TITLE"
    game_mode = "SOLO"  # "SOLO" or "DUEL"
    dual_scores = {"p1": 0, "p2": 0}

    fruit = new_fruit(WINDOW_W // 2, WINDOW_H // 2 + 25)
    fruit_p1 = new_fruit(int(WINDOW_W * 0.28), WINDOW_H // 2 + 25)
    fruit_p2 = new_fruit(int(WINDOW_W * 0.72), WINDOW_H // 2 + 25)

    stats = {"rounds": 0, "wins": 0, "best": None}
    wait_time = 3.0
    cut_time = 0.0
    state_start = 0.0
    outcome = None
    reaction_ms = 0.0
    slice_speed = 0.0
    slice_acc = 0.0

    practice_feedback = None
    practice_time = 0.0
    message_text, message_until = "", 0.0
    debug_mode = False
    background = None
    last_bg_frame_id = -1
    prev = time.perf_counter()
    running = True

    while running:
        space_pressed = False
        now = time.perf_counter()
        dt = min(0.1, now - prev)
        prev = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    space_pressed = True
                elif event.key == pygame.K_d:
                    debug_mode = not debug_mode
                elif event.key in (pygame.K_TAB, pygame.K_2, pygame.K_m):
                    game_mode = "DUEL" if game_mode == "SOLO" else "SOLO"
                    message_text = f"MODE: {'2-PLAYER DUEL (Split Targets)' if game_mode == 'DUEL' else 'SOLO CHALLENGE'}"
                    message_until = now + 2.0
                    fruit = new_fruit(WINDOW_W // 2, WINDOW_H // 2 + 25)
                    fruit_p1 = new_fruit(int(WINDOW_W * 0.28), WINDOW_H // 2 + 25)
                    fruit_p2 = new_fruit(int(WINDOW_W * 0.72), WINDOW_H // 2 + 25)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                space_pressed = True

        # Vision data
        v_data = vision.latest()
        rgb = v_data["rgb"]
        frame_time = v_data["stamp"]

        p1_pt = v_data["p1_point"]
        p1_spd = v_data["p1_speed"]
        p1_tracked = v_data["p1_tracked"]

        p2_pt = v_data["p2_point"]
        p2_spd = v_data["p2_speed"]
        p2_tracked = v_data["p2_tracked"]

        hand_visible = v_data["is_tracked"]
        cur_speed = v_data["speed"]

        if rgb is not None and v_data["frame_id"] != last_bg_frame_id:
            last_bg_frame_id = v_data["frame_id"]
            background = pygame.image.frombuffer(rgb.tobytes(), (WINDOW_W, WINDOW_H), "RGB")

        if p1_pt is not None and p1_tracked:
            detector_p1.add_sample(frame_time, p1_pt[0], p1_pt[1], p1_spd)

        if p2_pt is not None and p2_tracked:
            detector_p2.add_sample(frame_time, p2_pt[0], p2_pt[1], p2_spd)

        # Slice checks
        if game_mode == "DUEL":
            cx1, cy1 = fruit_center(fruit_p1, now)
            cx2, cy2 = fruit_center(fruit_p2, now)
            slice_p1 = detector_p1.check_slice(now, (cx1, cy1), FRUIT_RADIUS)
            slice_p2 = detector_p2.check_slice(now, (cx2, cy2), FRUIT_RADIUS)
            slice_result = slice_p1 or slice_p2
        else:
            cx, cy = fruit_center(fruit, now)
            slice_res1 = detector_p1.check_slice(now, (cx, cy), FRUIT_RADIUS)
            slice_res2 = detector_p2.check_slice(now, (cx, cy), FRUIT_RADIUS) if p2_tracked else None
            slice_result = slice_res1 or slice_res2
            slice_p1 = None
            slice_p2 = None

        # Start a round
        if space_pressed and state in ("TITLE", "RESULT"):
            ready_to_start = (p1_tracked or p2_tracked or hand_visible)
            if ready_to_start:
                state = "WAIT"
                state_start = now
                wait_time = random.uniform(*WAIT_RANGE)
                if game_mode == "DUEL":
                    fruit_p1 = new_fruit(int(WINDOW_W * 0.28), WINDOW_H // 2 + 25)
                    fruit_p2 = new_fruit(int(WINDOW_W * 0.72), WINDOW_H // 2 + 25)
                else:
                    fruit = new_fruit(WINDOW_W // 2, WINDOW_H // 2 + 25)
                detector_p1.reset()
                detector_p2.reset()
                outcome = None
                print(f"[game] Round started ({game_mode}) - WAIT for CUT! ({wait_time:.1f}s)")
            else:
                message_text = "Show your hand(s) to the camera first!"
                message_until = now + 2.0

        # State logic
        if state == "TITLE":
            if game_mode == "DUEL":
                # P1 Practice slice
                if fruit_p1["state"] == "whole" and slice_p1 is not None:
                    if slice_p1["hit"]:
                        slice_fruit(fruit_p1, slice_p1["direction"], now, slice_p1["cut_offset"])
                        sounds.play_slice()
                        practice_time = now
                        practice_feedback = {"player": "P1 (CYAN)", "speed": slice_p1["peak_speed"], "acc": slice_p1["accuracy"]}
                    else:
                        sounds.play_whoosh()
                elif fruit_p1["state"] == "sliced" and now - practice_time > 1.2:
                    fruit_p1 = new_fruit(int(WINDOW_W * 0.28), WINDOW_H // 2 + 25)

                # P2 Practice slice
                if fruit_p2["state"] == "whole" and slice_p2 is not None:
                    if slice_p2["hit"]:
                        slice_fruit(fruit_p2, slice_p2["direction"], now, slice_p2["cut_offset"])
                        sounds.play_slice()
                        practice_time = now
                        practice_feedback = {"player": "P2 (RED)", "speed": slice_p2["peak_speed"], "acc": slice_p2["accuracy"]}
                    else:
                        sounds.play_whoosh()
                elif fruit_p2["state"] == "sliced" and now - practice_time > 1.2:
                    fruit_p2 = new_fruit(int(WINDOW_W * 0.72), WINDOW_H // 2 + 25)
            else:
                # Solo practice mode
                if fruit["state"] == "whole" and slice_result is not None:
                    if slice_result["hit"]:
                        slice_fruit(fruit, slice_result["direction"], now, slice_result["cut_offset"])
                        sounds.play_slice()
                        practice_time = now
                        practice_feedback = {"player": "", "speed": slice_result["peak_speed"], "acc": slice_result["accuracy"]}
                    else:
                        sounds.play_whoosh()
                        message_text = "Off target! Aim through the fruit's center."
                        message_until = now + 1.2
                elif fruit["state"] == "sliced" and now - practice_time > 1.2:
                    fruit = new_fruit(WINDOW_W // 2, WINDOW_H // 2 + 25)

        elif state == "WAIT":
            waited = now - state_start
            if game_mode == "DUEL":
                early_p1 = detector_p1.check_slice(now, (cx1, cy1), FRUIT_RADIUS, strict=EARLY_STRICTNESS)
                early_p2 = detector_p2.check_slice(now, (cx2, cy2), FRUIT_RADIUS, strict=EARLY_STRICTNESS)
                if waited >= ARM_DELAY:
                    if early_p1 is not None and early_p2 is None:
                        outcome = "p2_win"
                        reaction_ms, slice_speed, slice_acc = 0.0, early_p1["peak_speed"], 0.0
                        dual_scores["p2"] += 1
                        sounds.play_thud()
                        message_text = "FOUL! P1 swiped before CUT! -> P2 WINS!"
                        message_until = now + 2.5
                        state = "RESULT"
                    elif early_p2 is not None and early_p1 is None:
                        outcome = "p1_win"
                        reaction_ms, slice_speed, slice_acc = 0.0, early_p2["peak_speed"], 0.0
                        dual_scores["p1"] += 1
                        sounds.play_thud()
                        message_text = "FOUL! P2 swiped before CUT! -> P1 WINS!"
                        message_until = now + 2.5
                        state = "RESULT"
                    elif early_p1 is not None and early_p2 is not None:
                        outcome = "early"
                        reaction_ms, slice_speed, slice_acc = 0.0, max(early_p1["peak_speed"], early_p2["peak_speed"]), 0.0
                        sounds.play_thud()
                        state = "RESULT"
            else:
                early_check = detector_p1.check_slice(now, (cx, cy), FRUIT_RADIUS, strict=EARLY_STRICTNESS)
                if waited >= ARM_DELAY and early_check is not None:
                    outcome = "early"
                    reaction_ms, slice_speed, slice_acc = 0.0, early_check["peak_speed"], 0.0
                    stats["rounds"] += 1
                    sounds.play_thud()
                    state = "RESULT"

            if waited >= wait_time and state == "WAIT":
                state = "CUT"
                state_start = now
                cut_time = now
                sounds.play_cut_signal()
                print("[game] CUT! Swipe now!")

        elif state == "CUT":
            elapsed = now - cut_time
            if game_mode == "DUEL":
                p1_hit = (slice_p1 is not None and slice_p1["hit"])
                p2_hit = (slice_p2 is not None and slice_p2["hit"])

                if p1_hit and not p2_hit:
                    outcome = "p1_win"
                    reaction_ms = elapsed * 1000.0
                    slice_speed = slice_p1["peak_speed"]
                    slice_acc = slice_p1["accuracy"]
                    dual_scores["p1"] += 1
                    slice_fruit(fruit_p1, slice_p1["direction"], now, slice_p1["cut_offset"])
                    sounds.play_slice()
                    state = "RESULT"
                elif p2_hit and not p1_hit:
                    outcome = "p2_win"
                    reaction_ms = elapsed * 1000.0
                    slice_speed = slice_p2["peak_speed"]
                    slice_acc = slice_p2["accuracy"]
                    dual_scores["p2"] += 1
                    slice_fruit(fruit_p2, slice_p2["direction"], now, slice_p2["cut_offset"])
                    sounds.play_slice()
                    state = "RESULT"
                elif p1_hit and p2_hit:
                    if slice_p1["peak_speed"] >= slice_p2["peak_speed"]:
                        outcome = "p1_win"
                        reaction_ms = elapsed * 1000.0
                        slice_speed = slice_p1["peak_speed"]
                        slice_acc = slice_p1["accuracy"]
                        dual_scores["p1"] += 1
                    else:
                        outcome = "p2_win"
                        reaction_ms = elapsed * 1000.0
                        slice_speed = slice_p2["peak_speed"]
                        slice_acc = slice_p2["accuracy"]
                        dual_scores["p2"] += 1
                    slice_fruit(fruit_p1, slice_p1["direction"], now, slice_p1["cut_offset"])
                    slice_fruit(fruit_p2, slice_p2["direction"], now, slice_p2["cut_offset"])
                    sounds.play_slice()
                    state = "RESULT"
                elif elapsed >= CUT_WINDOW:
                    outcome = "slow"
                    reaction_ms, slice_speed, slice_acc = 0.0, 0.0, 0.0
                    fruit_p1["state"] = "falling"
                    fruit_p1["vy"] = -250.0
                    fruit_p2["state"] = "falling"
                    fruit_p2["vy"] = -250.0
                    sounds.play_thud()
                    state = "RESULT"
            else:
                if slice_result is not None:
                    if slice_result["hit"]:
                        if elapsed < MIN_REACTION:
                            outcome = "early"
                            reaction_ms, slice_speed, slice_acc = 0.0, slice_result["peak_speed"], 0.0
                            sounds.play_thud()
                        else:
                            outcome = "win"
                            reaction_ms = elapsed * 1000.0
                            slice_speed = slice_result["peak_speed"]
                            slice_acc = slice_result["accuracy"]
                            slice_fruit(fruit, slice_result["direction"], now, slice_result["cut_offset"])
                            sounds.play_slice()

                            stats["rounds"] += 1
                            stats["wins"] += 1
                            if stats["best"] is None or reaction_ms < stats["best"]:
                                stats["best"] = reaction_ms
                        state = "RESULT"
                    else:
                        sounds.play_whoosh()
                        message_text = "OFF TARGET! Aim at the fruit!"
                        message_until = now + 0.8
                elif elapsed >= CUT_WINDOW:
                    outcome = "slow"
                    reaction_ms, slice_speed, slice_acc = 0.0, 0.0, 0.0
                    fruit["state"] = "falling"
                    fruit["vy"] = -250.0
                    stats["rounds"] += 1
                    sounds.play_thud()
                    state = "RESULT"

        # Update fruit physics
        if game_mode == "DUEL":
            update_fruit(fruit_p1, dt)
            update_fruit(fruit_p2, dt)
        else:
            update_fruit(fruit, dt)

        # Drawing
        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill((25, 28, 38))
        screen.blit(dim, (0, 0))

        if game_mode == "DUEL":
            pygame.draw.line(screen, (70, 75, 95), (WINDOW_W // 2, 60), (WINDOW_W // 2, WINDOW_H - 50), 2)
            draw_text(screen, "PLAYER 1 (LEFT)", 28, CYAN, int(WINDOW_W * 0.28), 65)
            draw_text(screen, "PLAYER 2 (RIGHT)", 28, RED, int(WINDOW_W * 0.72), 65)
            draw_fruit(screen, fruit_p1, whole_surfaces, now, glow=(state == "CUT"))
            draw_fruit(screen, fruit_p2, whole_surfaces, now, glow=(state == "CUT"))
            draw_trail(screen, detector_p1.history, now, p1_tracked, p1_spd, custom_color=CYAN, custom_glow=(40, 180, 255), label="P1")
            draw_trail(screen, detector_p2.history, now, p2_tracked, p2_spd, custom_color=(255, 60, 60), custom_glow=(255, 120, 100), label="P2")
        else:
            draw_fruit(screen, fruit, whole_surfaces, now, glow=(state == "CUT"))
            draw_trail(screen, detector_p1.history, now, p1_tracked or hand_visible, p1_spd if p1_tracked else cur_speed)
            if p2_tracked:
                draw_trail(screen, detector_p2.history, now, True, p2_spd, custom_color=(255, 60, 60), custom_glow=(255, 120, 100), label="P2")

        draw_hud(screen, stats, hand_visible or p1_tracked or p2_tracked, max(p1_spd, p2_spd, cur_speed), v_data["fps"], mode=game_mode, dual_scores=dual_scores)

        if state == "TITLE":
            draw_title(screen, practice_feedback, practice_time, mode=game_mode)

        elif state == "WAIT":
            draw_text(screen, "WAIT FOR IT...", 95, WHITE, WINDOW_W // 2, 105)
            draw_text(screen, "Keep steady... CUT! is coming", 38, GRAY, WINDOW_W // 2, 168)

        elif state == "CUT":
            size = 195 + int(15 * math.sin(now * 26))
            draw_text(screen, "CUT!", size, RED, WINDOW_W // 2, 115)
            left = max(0.0, 1.0 - (now - cut_time) / CUT_WINDOW)
            bar = pygame.Rect(WINDOW_W // 2 - 260, WINDOW_H - 65, 520, 24)
            pygame.draw.rect(screen, (35, 40, 52), bar, border_radius=12)
            fill = bar.copy()
            fill.width = int(bar.width * left)
            if fill.width > 0:
                pygame.draw.rect(screen, YELLOW if left > 0.35 else RED, fill, border_radius=12)

        elif state == "RESULT":
            draw_result(screen, outcome, reaction_ms, slice_speed, slice_acc, mode=game_mode)

        if now < message_until:
            draw_text(screen, message_text, 42, YELLOW, WINDOW_W // 2, WINDOW_H - 110)

        if debug_mode:
            active_fruit = fruit_p1 if game_mode == "DUEL" else fruit
            draw_debug_overlay(screen, v_data, active_fruit, detector_p1)

        pygame.display.flip()
        clock.tick(60)

    vision.stop()
    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()
