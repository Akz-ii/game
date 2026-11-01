"""
HOOP SHOTS - PICK UP BASKETBALLS AND THROW THEM BY WAVING YOUR HAND
====================================================================

How to play:
  1. Hold ONE hand up in front of the webcam. The ring on the screen is your hand.
  2. Press SPACE. Basketballs lie on the floor at the bottom left.
  3. PICK UP a ball: hold your hand over it until the yellow ring fills up.
     The ball now follows your hand.
  4. THROW it: give your hand a quick WAVE (flick) towards the hoop.
     The faster and higher you wave, the harder and higher the ball flies.
  5. The ball goes through the hoop from above = a BASKET! Balls that miss land on the floor,
     so just pick them up again. Score as many baskets as you can before time runs out.

Keys:   SPACE = start / play again     R = restart     ESC = quit

Run it with:   python hoop_shots.py
"""

import math
import os
import random
import threading
import time

import cv2
import mediapipe as mp
import pygame


# =====================================================================
#  1. SETTINGS  (safe to change)
# =====================================================================

CAMERA_INDEX = 0             # 0 = default webcam. Try 1 if the wrong camera opens
WINDOW_W, WINDOW_H = 960, 720

# --- Game rules ---
TIME_LIMIT = 60              # seconds per game
BALLS = 5                    # basketballs on the floor
BALL_R = 30                  # ball size (bigger = easier to score)

# --- Picking up ---
PICKUP_RADIUS = 85           # your hand must be this close (pixels) to a ball to grab it
PICKUP_TIME = 0.35           # seconds you must hold your hand over a ball to pick it up

# --- Throwing (the WAVE) ---
THROW_TRIGGER = 900          # your hand must move faster than this (pixels per second) to count as a wave
THROW_POWER = 0.8            # ball speed = hand speed x this. Ball flies too far? make it smaller
MAX_THROW = 2100             # the fastest a ball can ever be thrown (pixels per second)
HOLD_MIN = 0.4               # after picking up, you can't throw for this long (so lifting a ball doesn't throw it)
FLICK_MAX_TIME = 0.15        # the throw happens when your hand slows down, or after this many seconds

# --- Physics ---
GRAVITY = 1500               # how fast balls fall (pixels per second, per second)
FLOOR_BOUNCE = 0.65          # 1.0 = perfectly bouncy, 0.0 = no bounce
WALL_BOUNCE = 0.6
BOARD_BOUNCE = 0.55
RIM_BOUNCE = 0.6

# --- The hoop (it never moves) ---
FLOOR_Y = 620                # the floor
RIM_Y = 290                  # height of the rim
RIM_LEFT = 680               # the front of the rim. The rim runs from here to the backboard (a wider hoop = easier)
BOARD_X = 830                # the backboard
BOARD_W = 22
BOARD_TOP, BOARD_BOTTOM = 160, 310
RIM_TIP_R = 8                # thickness of the front of the rim (balls bounce off it)

# --- Hand tracking ---
EDGE_REACH = 1.2             # above 1.0 = your hand reaches the screen edges without leaving the camera picture
SMOOTH_STILL = 0.6           # smoothing when your hand is still/slow. LOWER = steadier ring, but a little slower
SMOOTH_FAST = 0.02           # HIGHER = less delay when your hand moves fast (but a bit more shake)
FOLLOW_SPEED = 40            # how quickly the ring glides to the newest hand position (higher = snappier)
HAND_GRACE = 0.25            # seconds the hand still counts after the camera last saw it
HAND_MODEL_COMPLEXITY = 0    # 0 = Lite model for locked 60 FPS real-time tracking
DETECT_CONFIDENCE = 0.3      # lower = finds the hand again more easily
TRACK_CONFIDENCE = 0.3       # lower = keeps following the hand even when it is blurry

# Colors
WHITE = (255, 255, 255)
YELLOW = (255, 220, 80)
GREEN = (90, 235, 120)
ORANGE = (255, 150, 50)
CYAN = (110, 225, 255)
GRAY = (200, 200, 210)
BALL_COLOR = (232, 112, 32)
BALL_LINE = (70, 30, 10)

# Camera picture size used for tracking (same shape as the window)
CAM_W = 640
CAM_H = int(CAM_W * WINDOW_H / WINDOW_W)


# =====================================================================
#  2. CAMERA + TEXT  (no image files needed)
# =====================================================================

def open_camera():
    """
    Open the webcam and make sure it really delivers pictures.
    On Windows the default camera backend often opens but gives no pictures,
    so we also try DirectShow (CAP_DSHOW) and Media Foundation (CAP_MSMF).
    Returns an opened camera, or None.
    """
    backends = [cv2.CAP_ANY]
    if os.name == "nt":                      # Windows
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(CAMERA_INDEX, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # less delay (some cameras ignore this)
        # Cameras need a moment to wake up: wait up to ~3 seconds for a real picture
        for _ in range(30):
            ok, frame = cap.read()
            if ok and frame is not None:
                print(f"[camera] working (backend {backend})")
                return cap
            time.sleep(0.1)
        cap.release()
    return None


def grab_frame(cap):
    """
    Read one webcam picture. Returns an RGB picture (CAM_W x CAM_H), mirrored like a mirror,
    or None if the camera gave nothing this time.
    """
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    # Cut the picture to the window's shape (from the middle) so nothing is stretched
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
    frame = cv2.flip(frame, 1)                               # mirror
    frame = cv2.resize(frame, (WINDOW_W, WINDOW_H), interpolation=cv2.INTER_LINEAR)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


class CameraThread:
    """
    Reads the webcam in the background and always keeps only the NEWEST picture,
    so the hand never lags behind because of old pictures piling up.
    """

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
        """Returns (picture, capture_time, picture_number)."""
        with self.lock:
            return self.rgb, self.stamp, self.frame_id

    def stop(self):
        self.running = False
        self.thread.join(timeout=1.0)


_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def draw_text(screen, text, size, color, x, y, align="center"):
    """Draw text with a dark shadow so it can be read on top of the camera picture."""
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


# =====================================================================
#  3. HAND TRACKING
# =====================================================================

def find_palm(rgb, hands):
    """
    Returns the middle of your palm as (x, y) in WINDOW pixels, or None if no hand is seen.
    EDGE_REACH stretches the positions so you can reach the screen edges easily.
    """
    rgb.flags.writeable = False                    # lets MediaPipe skip a copy (a bit faster)
    results = hands.process(rgb)
    rgb.flags.writeable = True
    if not results.multi_hand_landmarks:
        return None
    lm = results.multi_hand_landmarks[0].landmark

    ids = (0, 5, 9, 13, 17)                        # wrist + base of each finger = the palm
    x = sum(lm[i].x for i in ids) / len(ids)
    y = sum(lm[i].y for i in ids) / len(ids)
    x = (x - 0.5) * EDGE_REACH + 0.5
    y = (y - 0.5) * EDGE_REACH + 0.5
    return min(max(x, 0.0), 1.0) * WINDOW_W, min(max(y, 0.0), 1.0) * WINDOW_H


class OneEuro:
    """
    Smooths one number that jitters (like the hand's x or y).
    Hand still  -> very smooth, no shaking.   Hand moving fast -> almost no delay.
    (This is the "One Euro filter", the usual trick for smooth hand tracking.)
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.x, self.dx, self.t = None, 0.0, None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, value, t):
        if self.t is None:                            # first value: nothing to smooth yet
            self.x, self.dx, self.t = value, 0.0, t
            return value
        dt = max(1e-3, t - self.t)
        self.t = t
        speed = (value - self.x) / dt
        self.dx += self._alpha(30.0, dt) * (speed - self.dx)
        cutoff = SMOOTH_STILL + SMOOTH_FAST * abs(self.dx)      # faster hand = less smoothing
        self.x += self._alpha(cutoff, dt) * (value - self.x)
        return self.x


class HandTracker:
    """
    Finds the hand in a background thread. MediaPipe is slow (it can take 20-40 ms per picture),
    and when it ran inside the game loop every slow picture made the whole game stutter.
    Now the game keeps drawing smoothly at 60 fps while this thread works as fast as it can.
    """

    def __init__(self, camera):
        self.camera = camera
        self.hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1,
                                              model_complexity=HAND_MODEL_COMPLEXITY,
                                              min_detection_confidence=DETECT_CONFIDENCE,
                                              min_tracking_confidence=TRACK_CONFIDENCE)
        self.lock = threading.Lock()
        self.palm, self.stamp, self.result_id = None, 0.0, 0
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
            small_rgb = cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LINEAR)
            palm = find_palm(small_rgb, self.hands)
            with self.lock:
                self.palm, self.stamp = palm, stamp
                self.result_id += 1

    def latest(self):
        """Returns (palm position or None, when the picture was taken, result number)."""
        with self.lock:
            return self.palm, self.stamp, self.result_id

    def stop(self):
        self.running = False
        self.thread.join(timeout=1.0)
        self.hands.close()


def hand_velocity(history, now):
    """How fast the hand is moving (pixels per second), measured over the last 0.12 seconds."""
    recent = [h for h in history if now - h[0] <= 0.12]
    if len(recent) < 2:
        return 0.0, 0.0
    (t0, x0, y0), (t1, x1, y1) = recent[0], recent[-1]
    if t1 - t0 < 0.04:
        return 0.0, 0.0
    return (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)


def check_throw(flick, v, now):
    """
    Detects the WAVE. While the hand moves fast we remember its fastest moment.
    When the hand slows down again (the end of the wave), we return that fastest velocity = the throw.
    Returns (vx, vy) when the ball should be thrown, otherwise None.
    """
    speed = math.hypot(v[0], v[1])
    if speed >= THROW_TRIGGER:
        if flick["start"] is None:
            flick["start"], flick["peak"] = now, 0.0
        if speed > flick["peak"]:
            flick["peak"], flick["peak_v"] = speed, v
    elif flick["start"] is None:
        return None                                   # no wave going on

    if speed < flick["peak"] * 0.75 or now - flick["start"] > FLICK_MAX_TIME:
        thrown = flick["peak_v"]
        flick.update(start=None, peak=0.0, peak_v=(0.0, 0.0))
        return thrown
    return None


# =====================================================================
#  4. BALLS AND HOOP PHYSICS
# =====================================================================

def new_balls():
    """The balls start in a row on the floor at the left of the screen."""
    balls = []
    for i in range(BALLS):
        x = 110 + i * (440 / max(1, BALLS - 1))
        balls.append({"x": x, "y": float(FLOOR_Y - BALL_R), "vx": 0.0, "vy": 0.0,
                      "angle": random.uniform(0, 6.28), "held": False, "grab": 0.0,
                      "scored": False, "touched": False, "no_pick_until": 0.0})
    return balls


def move_ball(b, dt):
    """
    Move one flying ball: gravity, bounces off the floor, walls, backboard and the front of the rim.
    Returns True if the ball dropped through the hoop this frame.
    """
    scored = False
    steps = 3                                           # small steps so fast balls can't skip through things
    sub = dt / steps
    for _ in range(steps):
        b["vy"] += GRAVITY * sub
        old_y = b["y"]
        b["x"] += b["vx"] * sub
        b["y"] += b["vy"] * sub
        b["angle"] += b["vx"] * sub / BALL_R

        # side walls
        if b["x"] < BALL_R:
            b["x"], b["vx"] = BALL_R, abs(b["vx"]) * WALL_BOUNCE
        elif b["x"] > WINDOW_W - BALL_R:
            b["x"], b["vx"] = WINDOW_W - BALL_R, -abs(b["vx"]) * WALL_BOUNCE

        # backboard: a wall on the right side of the hoop
        if b["x"] + BALL_R > BOARD_X and BOARD_TOP < b["y"] < BOARD_BOTTOM + BALL_R:
            b["x"] = BOARD_X - BALL_R
            if b["vx"] > 0:
                b["vx"] = -b["vx"] * BOARD_BOUNCE
                b["touched"] = True

        # front of the rim: a small round bumper
        dx, dy = b["x"] - RIM_LEFT, b["y"] - RIM_Y
        dist = math.hypot(dx, dy)
        if 0 < dist < BALL_R + RIM_TIP_R:
            nx, ny = dx / dist, dy / dist
            b["x"] = RIM_LEFT + nx * (BALL_R + RIM_TIP_R)
            b["y"] = RIM_Y + ny * (BALL_R + RIM_TIP_R)
            vn = b["vx"] * nx + b["vy"] * ny
            if vn < 0:
                b["vx"] -= (1 + RIM_BOUNCE) * vn * nx
                b["vy"] -= (1 + RIM_BOUNCE) * vn * ny
                b["touched"] = True

        # the basket: the ball's middle drops down past the rim, between the front of the rim and the board
        if old_y < RIM_Y <= b["y"] and b["vy"] > 0 and RIM_LEFT < b["x"] < BOARD_X and not b["scored"]:
            b["scored"] = True
            scored = True

        # floor
        if b["y"] > FLOOR_Y - BALL_R:
            b["y"] = FLOOR_Y - BALL_R
            b["vy"] = -b["vy"] * FLOOR_BOUNCE if abs(b["vy"]) > 160 else 0.0
            b["vx"] *= max(0.0, 1.0 - 2.2 * sub)       # rolling slows down
            if abs(b["vx"]) < 8 and b["vy"] == 0.0:
                b["vx"] = 0.0
    return scored


# =====================================================================
#  5. DRAWING
# =====================================================================

def draw_ball(screen, b):
    x, y = int(b["x"]), int(b["y"])
    pygame.draw.circle(screen, BALL_COLOR, (x, y), BALL_R)
    a = b["angle"]
    for k in (0, math.pi / 2):                          # the black lines spin with the ball
        dx, dy = math.cos(a + k) * BALL_R, math.sin(a + k) * BALL_R
        pygame.draw.line(screen, BALL_LINE, (x - dx, y - dy), (x + dx, y + dy), 3)
    pygame.draw.circle(screen, BALL_LINE, (x, y), BALL_R, 3)
    pygame.draw.circle(screen, (255, 175, 110), (x - BALL_R // 3, y - BALL_R // 3), 5)   # shine
    if not b["held"] and b["grab"] > 0.02:              # the "picking up" ring
        ring = pygame.Rect(0, 0, BALL_R * 2 + 18, BALL_R * 2 + 18)
        ring.center = (x, y)
        progress = min(1.0, b["grab"] / PICKUP_TIME)
        pygame.draw.arc(screen, YELLOW, ring, math.pi / 2, math.pi / 2 + 2 * math.pi * progress, 7)


def draw_hoop_back(screen):
    """The pole and backboard (drawn behind the balls)."""
    pygame.draw.rect(screen, (90, 90, 100), (BOARD_X + 6, BOARD_BOTTOM, 10, FLOOR_Y - BOARD_BOTTOM))
    board = pygame.Rect(BOARD_X, BOARD_TOP, BOARD_W, BOARD_BOTTOM - BOARD_TOP)
    pygame.draw.rect(screen, (245, 245, 250), board, border_radius=4)
    pygame.draw.rect(screen, (60, 60, 70), board, 3, border_radius=4)
    pygame.draw.rect(screen, (230, 60, 50), (BOARD_X, RIM_Y - 40, BOARD_W, 40))


def draw_hoop_front(screen, now, net_until):
    """The net and the rim (drawn in front of the balls, so a scoring ball drops 'into' the net)."""
    wiggle = math.sin(now * 28) * 7 * max(0.0, (net_until - now) / 0.5)
    n = 6
    top = [(RIM_LEFT + (BOARD_X - RIM_LEFT) * i / n, RIM_Y) for i in range(n + 1)]
    bottom = [(RIM_LEFT + 24 + (BOARD_X - RIM_LEFT - 48) * i / n + wiggle, RIM_Y + 75) for i in range(n + 1)]
    for i in range(n + 1):
        pygame.draw.line(screen, (240, 240, 240), top[i], bottom[i], 2)
        if i < n:
            pygame.draw.line(screen, (240, 240, 240), top[i], bottom[i + 1], 2)
            pygame.draw.line(screen, (240, 240, 240), top[i + 1], bottom[i], 2)
    pygame.draw.line(screen, (0, 0, 0), (RIM_LEFT, RIM_Y + 3), (BOARD_X, RIM_Y + 3), 9)
    pygame.draw.line(screen, (255, 90, 30), (RIM_LEFT, RIM_Y), (BOARD_X, RIM_Y), 8)
    pygame.draw.circle(screen, (255, 90, 30), (RIM_LEFT, RIM_Y), RIM_TIP_R)


def draw_hand(screen, pos, near_ball):
    """A ring showing where your hand is."""
    p = (int(pos[0]), int(pos[1]))
    color = GREEN if near_ball else WHITE
    pygame.draw.circle(screen, (0, 0, 0), (p[0] + 2, p[1] + 2), 26, 4)
    pygame.draw.circle(screen, color, p, 26, 4)
    pygame.draw.circle(screen, color, p, 5)


def draw_title(screen):
    draw_text(screen, "HOOP SHOTS", 120, ORANGE, WINDOW_W // 2, 200)
    draw_text(screen, "Pick up the balls and throw them into the hoop - by waving!", 36, CYAN, WINDOW_W // 2, 280)
    draw_text(screen, "1. Hold ONE hand up. Hold it over a ball until the ring fills: you pick it up.", 28, WHITE, WINDOW_W // 2, 360)
    draw_text(screen, "2. Carry the ball, then give your hand a quick WAVE towards the hoop.", 28, WHITE, WINDOW_W // 2, 394)
    draw_text(screen, "3. Ball drops through the hoop from above = a basket!", 28, WHITE, WINDOW_W // 2, 428)
    draw_text(screen, f"You have {TIME_LIMIT} seconds. Missed balls land on the floor - pick them up again.", 28, WHITE, WINDOW_W // 2, 462)
    size = 54 + int(5 * math.sin(time.perf_counter() * 5))
    draw_text(screen, "PRESS SPACE TO START", size, YELLOW, WINDOW_W // 2, 545)
    draw_text(screen, "R = restart   |   ESC = quit", 26, GRAY, WINDOW_W // 2, 600)


# =====================================================================
#  6. MAIN GAME LOOP
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Hoop Shots")
    clock = pygame.time.Clock()

    cap = open_camera()
    if cap is None:
        print("Could not get any picture from the webcam.")
        print("1. Close other programs that use the camera (Zoom, Teams, browser tabs, Camera app).")
        print("2. Windows Settings > Privacy & security > Camera: allow desktop apps to use the camera.")
        print(f"3. Try another number: CAMERA_INDEX = {1 - CAMERA_INDEX if CAMERA_INDEX in (0, 1) else 0} in the settings.")
        pygame.quit()
        return

    camera = CameraThread(cap)
    tracker = HandTracker(camera)
    last_frame_id = -1
    last_result_id = -1

    dim = pygame.Surface((WINDOW_W, WINDOW_H))        # darkens the camera so things pop
    dim.set_alpha(110)
    dim.fill((0, 0, 0))
    floor = pygame.Surface((WINDOW_W, WINDOW_H - FLOOR_Y), pygame.SRCALPHA)
    floor.fill((185, 115, 55, 200))
    pygame.draw.rect(floor, (120, 70, 30, 255), (0, 0, WINDOW_W, 6))
    background = None

    state = "TITLE"                # TITLE -> PLAY -> OVER -> (SPACE) -> PLAY
    pos = None                     # palm position shown on screen (glides smoothly)
    target = None                  # newest filtered palm position that pos glides towards
    filter_x, filter_y = OneEuro(), OneEuro()
    last_seen = -10.0              # when the camera picture with the newest hand was taken
    history = []                   # recent hand positions: (time, x, y)
    balls = new_balls()
    held = None                    # the ball in your hand (or None)
    hold_since = 0.0
    flick = {"start": None, "peak": 0.0, "peak_v": (0.0, 0.0)}
    score, best = 0, 0
    play_start = 0.0
    net_until = 0.0
    floaters = []
    prev = time.perf_counter()
    running = True

    def start_game(now):
        nonlocal state, balls, held, score, play_start, net_until, floaters
        state, balls, held, score = "PLAY", new_balls(), None, 0
        play_start, net_until, floaters = now, 0.0, []
        flick.update(start=None, peak=0.0, peak_v=(0.0, 0.0))
        print("[game] Go! Pick up a ball and wave it into the hoop")

    while running:
        # ---------- keyboard / window ----------
        space_pressed = restart_pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    space_pressed = True
                elif event.key == pygame.K_r:
                    restart_pressed = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                space_pressed = True

        # ---------- camera + hand ----------
        rgb, _, frame_id = camera.latest()
        now = time.perf_counter()
        dt = min(0.05, now - prev)
        prev = now

        if rgb is not None and frame_id != last_frame_id:         # show the newest camera picture
            last_frame_id = frame_id
            background = pygame.image.frombuffer(rgb.tobytes(), (WINDOW_W, WINDOW_H), "RGB")

        palm, stamp, result_id = tracker.latest()                 # newest hand position (found in the background)
        if result_id != last_result_id:
            last_result_id = result_id
            if palm is not None:
                if target is None or stamp - last_seen > HAND_GRACE:
                    filter_x.reset()                              # hand just appeared: start fresh
                    filter_y.reset()
                    target = (filter_x.filter(palm[0], stamp), filter_y.filter(palm[1], stamp))
                    pos = target
                    history.clear()
                else:
                    target = (filter_x.filter(palm[0], stamp), filter_y.filter(palm[1], stamp))
                last_seen = stamp
        if target is not None and now - last_seen > HAND_GRACE:
            target = pos = None                                   # hand really gone
        if target is not None and pos is not None:                # glide a little each frame: smooth at 60 fps
            k = 1.0 - math.exp(-dt * FOLLOW_SPEED)
            pos = (pos[0] + (target[0] - pos[0]) * k, pos[1] + (target[1] - pos[1]) * k)
        hand_visible = pos is not None

        if pos is not None:
            history.append((now, pos[0], pos[1]))
        else:
            history.clear()
        history[:] = [h for h in history if now - h[0] <= 0.3]

        # ---------- start / restart ----------
        if (space_pressed and state in ("TITLE", "OVER")) or (restart_pressed and state != "TITLE"):
            start_game(now)

        # ---------- time ----------
        time_left = max(0.0, TIME_LIMIT - (now - play_start)) if state == "PLAY" else 0.0
        if state == "PLAY" and time_left <= 0.0:
            state = "OVER"
            best = max(best, score)
            print(f"[game] Time's up - {score} baskets")

        # ---------- hand and ball: pick up / carry / throw ----------
        near_ball = False
        if held is not None and (pos is None or state != "PLAY"):
            held["held"] = False                      # lost your hand (or time ran out): drop the ball
            held["no_pick_until"] = now + 0.6
            held = None

        if state == "PLAY" and pos is not None:
            if held is None:
                nearest, nearest_d = None, PICKUP_RADIUS
                for b in balls:
                    speed = math.hypot(b["vx"], b["vy"])
                    d = math.hypot(b["x"] - pos[0], b["y"] - pos[1])
                    if speed < 500 and now >= b["no_pick_until"] and d <= nearest_d:
                        nearest, nearest_d = b, d
                for b in balls:
                    if b is nearest:
                        b["grab"] += dt                # hold your hand over the ball to pick it up
                    else:
                        b["grab"] = max(0.0, b["grab"] - 2 * dt)
                near_ball = nearest is not None
                if nearest is not None and nearest["grab"] >= PICKUP_TIME:
                    held, hold_since = nearest, now
                    held.update(held=True, grab=0.0, vx=0.0, vy=0.0)
                    flick.update(start=None, peak=0.0, peak_v=(0.0, 0.0))
            else:
                held["x"], held["y"] = pos            # the ball follows your hand
                if now - hold_since >= HOLD_MIN:
                    v = check_throw(flick, hand_velocity(history, now), now)
                    if v is not None:
                        vx, vy = v[0] * THROW_POWER, v[1] * THROW_POWER
                        speed = math.hypot(vx, vy)
                        if speed > MAX_THROW:
                            vx, vy = vx * MAX_THROW / speed, vy * MAX_THROW / speed
                        held.update(held=False, vx=vx, vy=vy, scored=False, touched=False,
                                    no_pick_until=now + 0.6)
                        print(f"[game] thrown at {min(speed, MAX_THROW):.0f} px/s")
                        held = None

        # ---------- ball physics ----------
        for b in balls:
            if b["held"]:
                continue
            if move_ball(b, dt):
                score += 1
                net_until = now + 0.5
                text, color = ("SWISH!", YELLOW) if not b["touched"] else ("BASKET!", WHITE)
                floaters.append({"x": (RIM_LEFT + BOARD_X) / 2, "y": RIM_Y - 30, "t": now,
                                 "text": text, "color": color})
                print(f"[game] {text} total {score}")

        # ---------- drawing ----------
        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill((25, 25, 35))
        screen.blit(dim, (0, 0))
        screen.blit(floor, (0, FLOOR_Y))

        draw_hoop_back(screen)
        for b in balls:
            if not b["held"]:
                draw_ball(screen, b)
        draw_hoop_front(screen, now, net_until)
        if held is not None:
            draw_ball(screen, held)                   # the ball in your hand is drawn on top
        if pos is not None and state != "TITLE":
            draw_hand(screen, pos, near_ball or held is not None)

        for f in floaters:
            draw_text(screen, f["text"], 64, f["color"], int(f["x"]), int(f["y"] - (now - f["t"]) * 70))
        floaters[:] = [f for f in floaters if now - f["t"] < 0.9]

        if state == "TITLE":
            draw_title(screen)
        else:
            draw_text(screen, f"BASKETS  {score}", 44, YELLOW, 20, 30, align="left")
            draw_text(screen, f"{int(math.ceil(time_left))}", 70, WHITE if time_left > 10 else (255, 90, 90),
                      WINDOW_W // 2, 40)
            if hand_visible:
                draw_text(screen, "HAND OK", 28, GREEN, WINDOW_W - 20, 30, align="right")
            else:
                draw_text(screen, "FINDING HAND...", 28, YELLOW, WINDOW_W - 20, 30, align="right")

        if state == "PLAY" and held is not None and now - hold_since < 4.0:
            draw_text(screen, "WAVE YOUR HAND TOWARDS THE HOOP!", 36, WHITE, WINDOW_W // 2, 110)
        elif state == "PLAY" and score == 0 and now - play_start < 6.0:
            draw_text(screen, "Hold your hand over a ball to pick it up", 36, WHITE, WINDOW_W // 2, 110)
        elif state == "OVER":
            draw_text(screen, "TIME'S UP!", 110, ORANGE, WINDOW_W // 2, 270)
            draw_text(screen, f"You scored {score} basket{'s' if score != 1 else ''}   |   BEST {best}", 46, WHITE,
                      WINDOW_W // 2, 350)
            draw_text(screen, "SPACE = play again   |   ESC = quit", 34, WHITE, WINDOW_W // 2, 420)

        pygame.display.flip()
        clock.tick(60)

    tracker.stop()
    camera.stop()
    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()
