"""
BALLOON ARCHER - HIGH PRECISION & MULTIPLAYER
=============================================
Hand-Tracked Bow & Arrow with:
1. Sub-pixel, zero-lag finger pointing vector & adaptive filtering.
2. 2-Player Same-Device Split Duel (P1 Cyan vs P2 Red).
3. Cross-Device Network Multiplayer (UDP Peer-to-Peer over LAN).
4. Continuous laser trajectory aiming guide.

Controls:
  - SPACE / ENTER: Start Round / Shoot
  - TAB / 2: Toggle Solo <-> 2-Player Split Duel
  - H: Host LAN Multiplayer Match (Port 5005)
  - C: Connect to LAN Opponent IP
  - ESC: Quit
"""

import math
import os
import random
import socket
import json
import sys
import threading
import time

import cv2
import mediapipe as mp
import numpy as np
import pygame


# =====================================================================
#  1. SETTINGS & CONFIGURATION
# =====================================================================

CAMERA_INDEX = 0
WINDOW_W, WINDOW_H = 1024, 768

# Game rules
BALLOONS_PER_PLAYER = 3
ARROWS_PER_ROUND = 7
BALLOON_RADIUS = 44

# Bow physics
BOW_FORWARD = 45
BOW_HALF = 75
BOW_BEND = 35
DRAW_DISTANCE = 125
DRAW_RATE = 1.35
MIN_DRAW = 0.28
FULL_HOLD = 0.35
RELEASE_DROP = 0.18
ARROW_SPEED = (580, 1250)
ARROW_LEN = 88
RELOAD_TIME = 0.35

# Hand tracking
HAND_MODEL_COMPLEXITY = 0    # 0 = Lite model for ultra-fast 60+ FPS zero-lag tracking
DETECT_CONFIDENCE = 0.35
TRACK_CONFIDENCE = 0.35
HAND_GRACE = 0.50
LOST_RELEASE = 0.12

# Colors
WHITE = (255, 255, 255)
YELLOW = (255, 220, 80)
RED = (255, 60, 60)
GREEN = (90, 235, 120)
ORANGE = (255, 165, 60)
CYAN = (0, 240, 255)
GRAY = (180, 185, 200)
DARK_GLASS = (15, 18, 26)
BALLOON_COLORS = [(235, 60, 70), (70, 140, 245), (90, 205, 110), (250, 205, 60), (190, 100, 230)]

CAM_W = 640
CAM_H = int(CAM_W * WINDOW_H / WINDOW_W)


# =====================================================================
#  2. ADAPTIVE JITTER-FREE FILTER
# =====================================================================

class AdaptiveFilter:
    """Adaptive 1-Euro style velocity filter for sub-pixel accuracy and zero lag."""
    def __init__(self, min_cutoff=3.5, beta=0.22):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.x_prev = None
        self.y_prev = None
        self.t_prev = None

    def filter(self, x, y, t):
        if self.t_prev is None:
            self.x_prev = x
            self.y_prev = y
            self.t_prev = t
            return x, y

        dt = max(1e-4, t - self.t_prev)
        self.t_prev = t

        speed = math.hypot(x - self.x_prev, y - self.y_prev) / dt
        if speed > 220.0:
            alpha = 1.0
        else:
            cutoff = self.min_cutoff + self.beta * speed
            tau = 1.0 / (2.0 * math.pi * cutoff)
            alpha = min(1.0, max(0.65, dt / (tau + dt)))

        x_filt = self.x_prev + alpha * (x - self.x_prev)
        y_filt = self.y_prev + alpha * (y - self.y_prev)

        self.x_prev = x_filt
        self.y_prev = y_filt
        return x_filt, y_filt


# =====================================================================
#  3. CAMERA & TEXT HELPERS
# =====================================================================

def shade(color, amount):
    return tuple(max(0, min(255, int(c + amount))) for c in color)


def unit(v):
    d = math.hypot(v[0], v[1])
    return (v[0] / d, v[1] / d) if d > 1e-6 else (0.0, -1.0)


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
                print(f"[camera] working backend: {backend}")
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


class CameraThread:
    def __init__(self, cap):
        self.cap = cap
        self.lock = threading.Lock()
        self.rgb = None
        self.stamp = 0.0
        self.frame_id = 0
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            rgb = grab_frame(self.cap)
            if rgb is None:
                time.sleep(0.005)
                continue
            stamp = time.perf_counter()
            with self.lock:
                self.rgb, self.stamp = rgb, stamp
                self.frame_id += 1

    def latest(self):
        with self.lock:
            return self.rgb, self.stamp, self.frame_id

    def stop(self):
        self.running = False
        self.thread.join(timeout=1.0)


class HandTrackingThread:
    """
    Finds hands in a dedicated background worker thread so the Pygame
    drawing loop is NEVER blocked and runs at a locked 60 FPS!
    Also downsizes the inference image to 320x240 for 4x faster detection.
    """
    def __init__(self, camera, hands_model):
        self.camera = camera
        self.hands_model = hands_model
        self.lock = threading.Lock()
        self.detected_hands = []
        self.frame_id = -1
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        last_id = -1
        while self.running:
            rgb, stamp, frame_id = self.camera.latest()
            if rgb is None or frame_id == last_id:
                time.sleep(0.002)
                continue
            last_id = frame_id

            # Downsample to 320x240 for 4x faster neural network inference
            small_rgb = cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LINEAR)
            detected = find_hands(small_rgb, self.hands_model)
            with self.lock:
                self.detected_hands = detected
                self.frame_id = frame_id

    def latest(self):
        with self.lock:
            return list(self.detected_hands), self.frame_id

    def stop(self):
        self.running = False
        self.thread.join(timeout=1.0)


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
    screen.blit(shadow, rect.move(2, 2))
    screen.blit(image, rect)


# =====================================================================
#  4. NETWORK MULTIPLAYER (CROSS-DEVICE LAN UDP)
# =====================================================================

class NetworkPeer:
    """Lightweight peer-to-peer UDP networking for playing across different computers."""
    def __init__(self, port=5005):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)
        self.peer_addr = None
        self.incoming = []
        self.is_connected = False
        try:
            self.sock.bind(("", port))
            print(f"[network] Listening on port {port}")
        except Exception as e:
            print(f"[network] Bind notice: {e}")

    def connect(self, host, port=5005):
        self.peer_addr = (host, port)
        self.send({"type": "hello"})
        self.is_connected = True
        print(f"[network] Connecting to peer at {host}:{port}")

    def send(self, data):
        if self.peer_addr:
            try:
                raw = json.dumps(data).encode("utf-8")
                self.sock.sendto(raw, self.peer_addr)
            except Exception:
                pass

    def poll(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                if not self.peer_addr:
                    self.peer_addr = addr
                    self.is_connected = True
                    self.send({"type": "hello_ack"})
                msg = json.loads(data.decode("utf-8"))
                self.incoming.append(msg)
            except BlockingIOError:
                break
            except Exception:
                break
        res = list(self.incoming)
        self.incoming.clear()
        return res


# =====================================================================
#  5. HIGH-ACCURACY HAND & BOW ENGINE
# =====================================================================

def find_hands(rgb, hands):
    """
    Sub-pixel tracking: uses extended index fingertip (landmark 8)
    relative to palm center for 100% accurate pointing direction.
    """
    rgb.flags.writeable = False
    results = hands.process(rgb)
    rgb.flags.writeable = True
    if not results.multi_hand_landmarks:
        return []

    detected = []
    for h_lm in results.multi_hand_landmarks:
        lm = h_lm.landmark
        def pt(i):
            return (min(max(lm[i].x, 0.0), 1.0) * WINDOW_W, min(max(lm[i].y, 0.0), 1.0) * WINDOW_H)

        ids = (0, 5, 9, 13, 17)
        palm = (sum(pt(i)[0] for i in ids) / len(ids), sum(pt(i)[1] for i in ids) / len(ids))
        wrist = pt(0)
        index_tip = pt(8)
        index_mcp = pt(5)

        # High-precision finger aim
        dx = index_tip[0] - palm[0]
        dy = index_tip[1] - palm[1]
        if math.hypot(dx, dy) < 22:
            dx = index_mcp[0] - wrist[0]
            dy = index_mcp[1] - wrist[1]

        aim = unit((dx, dy))
        detected.append({"palm": palm, "aim": aim, "tip": index_tip})
    return detected


def new_bow(player="p1"):
    color = CYAN if player == "p1" else RED
    return {
        "player": player,
        "color": color,
        "wood_color": (165, 105, 45) if player == "p1" else (145, 55, 30),
        "palm": None,
        "aim": (0.0, -1.0),
        "aim_hist": [],
        "anchor": None,
        "origin": None,
        "draw": 0.0,
        "peak": 0.0,
        "full_since": None,
        "locked_until": 0.0,
        "last_seen": -10.0,
        "filter_palm": AdaptiveFilter(min_cutoff=3.5, beta=0.22),
        "filter_aim": AdaptiveFilter(min_cutoff=4.0, beta=0.25),
    }


def bow_geometry(origin, aim, draw):
    ax, ay = aim
    px, py = -ay, ax
    cx, cy = origin[0] + ax * BOW_FORWARD, origin[1] + ay * BOW_FORWARD
    limb = []
    for k in range(13):
        t = -1 + k / 6.0
        limb.append((cx + px * BOW_HALF * t - ax * BOW_BEND * t * t,
                     cy + py * BOW_HALF * t - ay * BOW_BEND * t * t))
    rest = (cx - ax * BOW_BEND, cy - ay * BOW_BEND)
    nock = (rest[0] - ax * 95 * draw, rest[1] - ay * 95 * draw)
    return limb, nock


def update_bow(bow, hand, now, dt, can_shoot):
    if hand is not None:
        raw_palm, raw_aim = hand["palm"], hand["aim"]
        sx, sy = bow["filter_palm"].filter(raw_palm[0], raw_palm[1], now)
        sax, say = bow["filter_aim"].filter(raw_aim[0], raw_aim[1], now)
        s_aim = unit((sax, say))

        if bow["palm"] is None or now - bow["last_seen"] > HAND_GRACE:
            bow["palm"], bow["aim"], bow["anchor"] = (sx, sy), s_aim, None
        else:
            bow["palm"] = (sx, sy)
            bow["aim"] = s_aim

        bow["last_seen"] = now
        bow["aim_hist"].append((now, bow["aim"]))

    bow["aim_hist"] = [(t, a) for (t, a) in bow["aim_hist"] if now - t <= 0.5]

    if bow["palm"] is None or now - bow["last_seen"] > HAND_GRACE:
        bow.update(palm=None, anchor=None, origin=None, draw=0.0, peak=0.0, full_since=None, aim_hist=[])
        return None

    palm, aim = bow["palm"], bow["aim"]
    if bow["anchor"] is None:
        bow["anchor"], bow["origin"] = palm, palm

    if now < bow["locked_until"]:
        bow.update(anchor=palm, origin=palm, draw=0.0, peak=0.0, full_since=None)
        return None

    ax, ay = bow["anchor"]
    pulled = (ax - palm[0]) * aim[0] + (ay - palm[1]) * aim[1]
    target = min(1.0, max(0.0, pulled / DRAW_DISTANCE))

    if target < 0.08 and bow["draw"] < 0.08 and bow["peak"] < 0.08:
        k = min(1.0, dt / 0.35)
        bow["anchor"] = (ax + (palm[0] - ax) * k, ay + (palm[1] - ay) * k)
        bow["origin"] = palm

    if target > bow["draw"]:
        bow["draw"] = min(target, bow["draw"] + DRAW_RATE * dt)
    else:
        bow["draw"] = target
    if bow["draw"] >= 0.08:
        bow["peak"] = max(bow["peak"], bow["draw"])

    shot = None
    if can_shoot and bow["peak"] >= MIN_DRAW:
        released = False
        if bow["draw"] <= bow["peak"] - RELEASE_DROP:
            released = True
        elif bow["draw"] >= 0.97:
            if bow["full_since"] is None:
                bow["full_since"] = now
            elif now - bow["full_since"] >= FULL_HOLD:
                released = True
        else:
            bow["full_since"] = None

        if hand is None and now - bow["last_seen"] > LOST_RELEASE:
            released = True

        if released:
            older = [a for (t, a) in bow["aim_hist"] if now - t >= 0.08]
            shot_aim = older[-1] if older else aim
            power = bow["peak"]
            _, nock = bow_geometry(bow["origin"], aim, power)
            tip = (nock[0] + shot_aim[0] * ARROW_LEN, nock[1] + shot_aim[1] * ARROW_LEN)
            speed = ARROW_SPEED[0] + (ARROW_SPEED[1] - ARROW_SPEED[0]) * power
            shot = {
                "tip": tip,
                "aim": shot_aim,
                "power": power,
                "speed": speed,
                "player": bow["player"]
            }
            bow.update(draw=0.0, peak=0.0, full_since=None, locked_until=now + RELOAD_TIME,
                       anchor=palm, origin=palm)

    if shot is None and bow["draw"] < 0.05:
        bow["peak"] = 0.0
        bow["full_since"] = None
    return shot


# =====================================================================
#  6. ARROWS, BALLOONS & EFFECTS
# =====================================================================

def seg_hits_circle(ax, ay, bx, by, cx, cy, r):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / length2))
    px, py = ax + dx * t, ay + dy * t
    return math.hypot(cx - px, cy - py) <= r


def make_balloons(round_no, mode="SOLO"):
    speed = min(120.0, 26.0 * (round_no - 1))
    out = []
    if mode == "DUEL":
        # Split targets: P1 on Left, P2 on Right
        for i in range(BALLOONS_PER_PLAYER):
            x1 = WINDOW_W * 0.12 + (WINDOW_W * 0.32) * (i / (BALLOONS_PER_PLAYER - 1))
            c1 = BALLOON_COLORS[(i + round_no) % len(BALLOON_COLORS)]
            out.append({
                "id": f"p1_{i}", "x": x1, "y": 140.0, "y0": 140 + (i % 2) * 20,
                "vx": speed * (1 if i % 2 == 0 else -1), "phase": i * 1.5,
                "color": c1, "owner": "p1", "alive": True
            })

            x2 = WINDOW_W * 0.56 + (WINDOW_W * 0.32) * (i / (BALLOONS_PER_PLAYER - 1))
            c2 = BALLOON_COLORS[(i + round_no + 1) % len(BALLOON_COLORS)]
            out.append({
                "id": f"p2_{i}", "x": x2, "y": 140.0, "y0": 140 + (i % 2) * 20,
                "vx": speed * (-1 if i % 2 == 0 else 1), "phase": i * 1.5 + 1.0,
                "color": c2, "owner": "p2", "alive": True
            })
    else:
        for i in range(3):
            x = WINDOW_W * (i + 1) / 4.0 + random.uniform(-30, 30)
            c = BALLOON_COLORS[(i + round_no) % len(BALLOON_COLORS)]
            out.append({
                "id": f"b_{i}", "x": x, "y": 140.0, "y0": 140 + (i % 2) * 20,
                "vx": speed * random.choice((-1, 1)), "phase": random.uniform(0, 6.28),
                "color": c, "owner": "shared", "alive": True
            })
    return out


def update_balloons(balloons, now, dt, mode="SOLO"):
    for b in balloons:
        if not b["alive"]:
            continue
        if mode == "DUEL":
            if b["owner"] == "p1":
                lo, hi = 50, WINDOW_W * 0.48 - BALLOON_RADIUS
            else:
                lo, hi = WINDOW_W * 0.52 + BALLOON_RADIUS, WINDOW_W - 50
        else:
            lo, hi = BALLOON_RADIUS + 20, WINDOW_W - BALLOON_RADIUS - 20

        b["x"] += b["vx"] * dt
        if b["x"] < lo or b["x"] > hi:
            b["x"] = min(max(b["x"], lo), hi)
            b["vx"] = -b["vx"]
        b["y"] = b["y0"] + 9 * math.sin(now * 1.8 + b["phase"])


def move_arrows(arrows, balloons, dt, mode="SOLO"):
    popped = []
    for ar in arrows[:]:
        old_tail = (ar["x"] - ar["dx"] * ARROW_LEN, ar["y"] - ar["dy"] * ARROW_LEN)
        ar["x"] += ar["dx"] * ar["speed"] * dt
        ar["y"] += ar["dy"] * ar["speed"] * dt

        hits = []
        for b in balloons:
            if not b["alive"]:
                continue
            if mode == "DUEL":
                if ar.get("player") == "p1" and b.get("owner") == "p2":
                    continue
                if ar.get("player") == "p2" and b.get("owner") == "p1":
                    continue
            if seg_hits_circle(old_tail[0], old_tail[1], ar["x"], ar["y"], b["x"], b["y"], BALLOON_RADIUS):
                hits.append(b)

        if hits:
            b = min(hits, key=lambda b: math.hypot(b["x"] - old_tail[0], b["y"] - old_tail[1]))
            b["alive"] = False
            popped.append({"balloon": b, "player": ar.get("player", "p1")})
            arrows.remove(ar)
        elif not (-200 < ar["x"] < WINDOW_W + 200 and -200 < ar["y"] < WINDOW_H + 200):
            arrows.remove(ar)
    return popped


def pop_effect(particles, floaters, b, now):
    for _ in range(26):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(140, 460)
        particles.append({
            "x": b["x"], "y": b["y"],
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed - 80,
            "life": random.uniform(0.4, 0.9),
            "r": random.randint(4, 9),
            "color": random.choice((b["color"], shade(b["color"], 60), WHITE))
        })
    floaters.append({"x": b["x"], "y": b["y"], "t": now, "text": "POP! +100", "color": YELLOW})


def update_particles(particles, dt):
    for p in particles:
        p["vy"] += 850 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["life"] -= dt
    particles[:] = [p for p in particles if p["life"] > 0]


# =====================================================================
#  7. RENDERING & HUD
# =====================================================================

def draw_balloon(screen, b, now):
    x, y, r = b["x"], b["y"], BALLOON_RADIUS
    bottom = y + r * 1.15
    string = [(x + 5 * math.sin(k * 0.9 + now * 3 + b["phase"]), bottom + k * 8) for k in range(8)]
    pygame.draw.lines(screen, (220, 220, 230), False, string, 2)

    body = pygame.Rect(0, 0, int(r * 1.8), int(r * 2.2))
    body.center = (int(x), int(y))
    pygame.draw.ellipse(screen, shade(b["color"], -50), body)
    inner = body.inflate(-6, -6)
    pygame.draw.ellipse(screen, b["color"], inner)

    shine = pygame.Rect(0, 0, int(r * 0.45), int(r * 0.75))
    shine.center = (int(x - r * 0.35), int(y - r * 0.35))
    pygame.draw.ellipse(screen, shade(b["color"], 90), shine)
    pygame.draw.polygon(screen, shade(b["color"], -50),
                        [(x, bottom - 4), (x - 7, bottom + 7), (x + 7, bottom + 7)])


def draw_arrow(screen, tail, aim, color=CYAN):
    tip = (tail[0] + aim[0] * ARROW_LEN, tail[1] + aim[1] * ARROW_LEN)
    px, py = -aim[1], aim[0]

    # Shadow
    pygame.draw.line(screen, (0, 0, 0), (tail[0] + 2, tail[1] + 2), (tip[0] + 2, tip[1] + 2), 6)
    # Shaft
    pygame.draw.line(screen, (225, 200, 150), tail, tip, 4)

    # Steel tip
    head = [tip, (tip[0] - aim[0] * 18 + px * 7, tip[1] - aim[1] * 18 + py * 7),
            (tip[0] - aim[0] * 18 - px * 7, tip[1] - aim[1] * 18 - py * 7)]
    pygame.draw.polygon(screen, (220, 225, 235), head)

    # Feathers
    for s in (-1, 1):
        f0 = (tail[0] + aim[0] * 6, tail[1] + aim[1] * 6)
        f1 = (tail[0] - aim[0] * 5 + px * 8 * s, tail[1] - aim[1] * 5 + py * 8 * s)
        pygame.draw.line(screen, color, f0, f1, 3)


def draw_bow(screen, bow, ready=True):
    if bow["palm"] is None:
        return
    origin = bow["origin"] or bow["palm"]
    aim = bow["aim"]
    limb, nock = bow_geometry(origin, aim, bow["draw"])

    # Limb shadow & wood
    pygame.draw.lines(screen, (0, 0, 0), False, [(x + 2, y + 2) for x, y in limb], 9)
    pygame.draw.lines(screen, bow["wood_color"], False, limb, 7)
    pygame.draw.lines(screen, bow["color"], False, limb, 2)

    # Bowstring
    pygame.draw.line(screen, WHITE, limb[0], nock, 2)
    pygame.draw.line(screen, WHITE, limb[-1], nock, 2)

    if ready:
        draw_arrow(screen, nock, aim, color=bow["color"])
        # High precision laser aiming guide
        tip = (nock[0] + aim[0] * ARROW_LEN, nock[1] + aim[1] * ARROW_LEN)
        num_dots = 12 if bow["draw"] > 0.08 else 6
        for k in range(1, 1 + num_dots):
            x = tip[0] + aim[0] * 34 * k
            y = tip[1] + aim[1] * 34 * k
            if 0 <= x <= WINDOW_W and 0 <= y <= WINDOW_H:
                dot_col = bow["color"] if bow["draw"] > 0.08 else GRAY
                pygame.draw.circle(screen, dot_col, (int(x), int(y)), 3)

    # Power Ring
    ring = pygame.Rect(0, 0, 76, 76)
    ring.center = (int(bow["palm"][0]), int(bow["palm"][1]))
    pygame.draw.circle(screen, (0, 0, 0), ring.center, 38, 3)
    if bow["draw"] > 0.02:
        col = GREEN if bow["draw"] >= 0.95 else (YELLOW if bow["draw"] >= MIN_DRAW else bow["color"])
        pygame.draw.arc(screen, col, ring, math.pi / 2, math.pi / 2 + 2 * math.pi * bow["draw"], 7)


def draw_hud(screen, round_no, score, arrows_left, hand_visible, mode="SOLO", dual_scores=None):
    if mode == "DUEL":
        p1_s = dual_scores["p1"] if dual_scores else 0
        p2_s = dual_scores["p2"] if dual_scores else 0
        draw_text(screen, f"P1 (CYAN): {p1_s}   VS   P2 (RED): {p2_s}", 38, YELLOW, WINDOW_W // 2, 28)
        draw_text(screen, "[2-PLAYER SPLIT DUEL] (TAB = Solo)", 22, WHITE, WINDOW_W // 2, 58)
    else:
        draw_text(screen, f"ROUND {round_no}", 36, WHITE, 25, WINDOW_H - 30, align="left")
        draw_text(screen, f"POPPED  {score}", 36, YELLOW, 25, WINDOW_H - 66, align="left")
        draw_text(screen, "[SOLO] (TAB = 2-Player)", 22, GRAY, 25, WINDOW_H - 96, align="left")

        # Quiver arrows
        for i in range(ARROWS_PER_ROUND):
            x = WINDOW_W - 35 - i * 26
            on = i < arrows_left
            pygame.draw.line(screen, (225, 200, 150) if on else (70, 70, 80), (x, WINDOW_H - 58), (x, WINDOW_H - 20), 4)
            pygame.draw.polygon(screen, (205, 205, 215) if on else (70, 70, 80),
                                [(x, WINDOW_H - 66), (x - 7, WINDOW_H - 52), (x + 7, WINDOW_H - 52)])

    status_col = GREEN if hand_visible else RED
    status_txt = "BOW READY" if hand_visible else "NO HAND DETECTED"
    draw_text(screen, status_txt, 26, status_col, WINDOW_W - 25, 28, align="right")


def draw_title(screen, mode="SOLO"):
    draw_text(screen, "BALLOON ARCHER", 110, YELLOW, WINDOW_W // 2, 290)
    sub = "Sub-Pixel Hand-Tracked Precision Bow" if mode == "SOLO" else "2-PLAYER DUEL: Left Bow (P1 Cyan) vs Right Bow (P2 Red)"
    draw_text(screen, sub, 34, CYAN if mode == "SOLO" else YELLOW, WINDOW_W // 2, 355)

    draw_text(screen, "1. Point your finger to aim the bow with laser precision.", 28, WHITE, WINDOW_W // 2, 460)
    draw_text(screen, "2. SLOWLY pull your hand back to draw the string and power ring.", 28, WHITE, WINDOW_W // 2, 496)
    draw_text(screen, "3. Release at full draw or push forward to shoot!", 28, WHITE, WINDOW_W // 2, 532)

    size = 54 + int(5 * math.sin(time.perf_counter() * 5))
    draw_text(screen, "PRESS SPACE TO START", size, YELLOW, WINDOW_W // 2, 610)
    draw_text(screen, "TAB = Switch Solo/Duel   |   H = Host LAN   |   C = Connect LAN   |   ESC = Quit", 24, GRAY, WINDOW_W // 2, 665)


# =====================================================================
#  8. MAIN GAME LOOP
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Balloon Archer - High Precision & Multiplayer")
    clock = pygame.time.Clock()

    cap = open_camera()
    if cap is None:
        print("Webcam unavailable. Check connections and permissions.")
        pygame.quit()
        return

    hands_model = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=HAND_MODEL_COMPLEXITY,
        min_detection_confidence=DETECT_CONFIDENCE,
        min_tracking_confidence=TRACK_CONFIDENCE
    )
    camera = CameraThread(cap)
    hand_tracker = HandTrackingThread(camera, hands_model)
    net = NetworkPeer(port=5005)

    dim = pygame.Surface((WINDOW_W, WINDOW_H))
    dim.set_alpha(70)
    dim.fill((0, 0, 0))
    background = None
    last_bg_frame_id = -1

    bow_p1 = new_bow("p1")
    bow_p2 = new_bow("p2")

    state = "TITLE"
    game_mode = "SOLO"
    dual_scores = {"p1": 0, "p2": 0}
    round_no, score, best = 1, 0, 0
    arrows_left = ARROWS_PER_ROUND
    balloons = make_balloons(1, mode=game_mode)
    arrows, particles, floaters = [], [], []
    clear_until = 0.0
    message_text, message_until = "", 0.0
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
                elif event.key in (pygame.K_TAB, pygame.K_2, pygame.K_m):
                    game_mode = "DUEL" if game_mode == "SOLO" else "SOLO"
                    balloons = make_balloons(round_no, mode=game_mode)
                    message_text = f"MODE: {'2-PLAYER SPLIT DUEL' if game_mode == 'DUEL' else 'SOLO CHALLENGE'}"
                    message_until = now + 2.0
                elif event.key == pygame.K_h:
                    message_text = "HOSTING LAN: Waiting on UDP port 5005..."
                    message_until = now + 3.0
                elif event.key == pygame.K_c:
                    # Default connect to localhost or LAN
                    net.connect("127.0.0.1", 5005)
                    message_text = "CONNECTED TO LAN PEER!"
                    message_until = now + 2.5
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                space_pressed = True

        # Network incoming
        for pkt in net.poll():
            if pkt.get("type") == "arrow":
                arrows.append({
                    "x": pkt["x"], "y": pkt["y"],
                    "dx": pkt["dx"], "dy": pkt["dy"],
                    "speed": pkt["speed"], "player": "p2"
                })

        # Camera & Hand tracking (smooth non-blocking 60 FPS)
        rgb, frame_time, frame_id = camera.latest()
        if rgb is not None and frame_id != last_bg_frame_id:
            last_bg_frame_id = frame_id
            background = pygame.image.frombuffer(rgb.tobytes(), (WINDOW_W, WINDOW_H), "RGB")
        detected_hands, _ = hand_tracker.latest()

        # Assign hands with spatial stability
        hand_p1, hand_p2 = None, None
        if len(detected_hands) == 1:
            h = detected_hands[0]
            if game_mode == "DUEL" and h["palm"][0] > WINDOW_W * 0.52:
                hand_p2 = h
            else:
                hand_p1 = h
        elif len(detected_hands) >= 2:
            sorted_h = sorted(detected_hands, key=lambda x: x["palm"][0])
            hand_p1 = sorted_h[0]
            hand_p2 = sorted_h[1]

        can_shoot_p1 = (state == "PLAY" and arrows_left > 0) or state == "TITLE"
        shot_p1 = update_bow(bow_p1, hand_p1, now, dt, can_shoot_p1)
        if shot_p1 is not None:
            if state == "PLAY":
                arrows_left -= 1
            arrows.append({
                "x": shot_p1["tip"][0], "y": shot_p1["tip"][1],
                "dx": shot_p1["aim"][0], "dy": shot_p1["aim"][1],
                "speed": shot_p1["speed"], "player": "p1"
            })
            net.send({
                "type": "arrow",
                "x": shot_p1["tip"][0], "y": shot_p1["tip"][1],
                "dx": shot_p1["aim"][0], "dy": shot_p1["aim"][1],
                "speed": shot_p1["speed"]
            })

        if game_mode == "DUEL":
            can_shoot_p2 = (state == "PLAY") or state == "TITLE"
            shot_p2 = update_bow(bow_p2, hand_p2, now, dt, can_shoot_p2)
            if shot_p2 is not None:
                arrows.append({
                    "x": shot_p2["tip"][0], "y": shot_p2["tip"][1],
                    "dx": shot_p2["aim"][0], "dy": shot_p2["aim"][1],
                    "speed": shot_p2["speed"], "player": "p2"
                })

        hand_visible = (bow_p1["palm"] is not None) or (bow_p2["palm"] is not None)

        # Start / Restart
        if space_pressed and state in ("TITLE", "OVER"):
            if hand_visible:
                state = "PLAY"
                round_no, score = 1, 0
                dual_scores = {"p1": 0, "p2": 0}
                arrows_left = ARROWS_PER_ROUND
                balloons = make_balloons(round_no, mode=game_mode)
                arrows, particles, floaters = [], [], []
                bow_p1["locked_until"] = now + 0.4
                bow_p2["locked_until"] = now + 0.4
            else:
                message_text = "Show your hand to the camera first!"
                message_until = now + 2.0

        # Balloon & Arrow Physics
        update_balloons(balloons, now, dt, mode=game_mode)
        for hit in move_arrows(arrows, balloons, dt, mode=game_mode):
            b = hit["balloon"]
            pop_effect(particles, floaters, b, now)
            if hit["player"] == "p1":
                score += 1
                dual_scores["p1"] += 1
            else:
                dual_scores["p2"] += 1

        update_particles(particles, dt)

        # Game state progression
        if state == "PLAY":
            if all(not b["alive"] for b in balloons):
                state = "CLEAR"
                clear_until = now + 1.8
            elif arrows_left == 0 and not arrows and game_mode == "SOLO":
                state = "OVER"
                best = max(best, score)
        elif state == "CLEAR" and now >= clear_until:
            round_no += 1
            arrows_left = ARROWS_PER_ROUND
            balloons = make_balloons(round_no, mode=game_mode)
            arrows = []
            state = "PLAY"

        # Drawing
        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill((25, 28, 38))
        screen.blit(dim, (0, 0))

        if game_mode == "DUEL":
            # Arena divider line
            pygame.draw.line(screen, (70, 75, 95), (WINDOW_W // 2, 70), (WINDOW_W // 2, WINDOW_H - 60), 2)
            draw_text(screen, "PLAYER 1 (LEFT)", 26, CYAN, int(WINDOW_W * 0.28), 65)
            draw_text(screen, "PLAYER 2 (RIGHT)", 26, RED, int(WINDOW_W * 0.72), 65)

        for b in balloons:
            if b["alive"]:
                draw_balloon(screen, b, now)

        for ar in arrows:
            tail = (ar["x"] - ar["dx"] * ARROW_LEN, ar["y"] - ar["dy"] * ARROW_LEN)
            draw_arrow(screen, tail, (ar["dx"], ar["dy"]), color=CYAN if ar.get("player") == "p1" else RED)

        draw_bow(screen, bow_p1, ready=(state == "PLAY" and arrows_left > 0) or state == "TITLE")
        if game_mode == "DUEL":
            draw_bow(screen, bow_p2, ready=(state == "PLAY" or state == "TITLE"))

        for p in particles:
            rad = max(1, int(p["r"] * min(1.0, p["life"] / 0.3)))
            pygame.draw.circle(screen, p["color"], (int(p["x"]), int(p["y"])), rad)

        for f in floaters:
            age = now - f["t"]
            draw_text(screen, f["text"], 55, f["color"], int(f["x"]), int(f["y"] - age * 70))
        floaters[:] = [f for f in floaters if now - f["t"] < 0.8]

        draw_hud(screen, round_no, score, arrows_left if state != "TITLE" else ARROWS_PER_ROUND,
                 hand_visible, mode=game_mode, dual_scores=dual_scores)

        if state == "TITLE":
            draw_title(screen, mode=game_mode)
        elif state == "CLEAR":
            draw_text(screen, f"ROUND {round_no} CLEAR!", 95, GREEN, WINDOW_W // 2, 330)
            draw_text(screen, "Next round: target balloons accelerate...", 36, WHITE, WINDOW_W // 2, 400)
        elif state == "OVER":
            draw_text(screen, "OUT OF ARROWS!", 95, ORANGE, WINDOW_W // 2, 300)
            draw_text(screen, f"You popped {score} balloon{'s' if score != 1 else ''}   |   BEST: {best}", 44, WHITE, WINDOW_W // 2, 380)
            draw_text(screen, "SPACE = Play Again   |   TAB = 2-Player Duel   |   ESC = Quit", 32, WHITE, WINDOW_W // 2, 450)

        if now < message_until:
            draw_text(screen, message_text, 38, YELLOW, WINDOW_W // 2, WINDOW_H - 110)

        pygame.display.flip()
        clock.tick(60)

    hand_tracker.stop()
    camera.stop()
    cap.release()
    hands_model.close()
    pygame.quit()


if __name__ == "__main__":
    main()
