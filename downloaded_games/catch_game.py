"""
FRUIT CATCH - STAND UNDER THE FRUIT
===================================

How to play (1 or 2 people, one webcam):
  1. Step in front of the camera. A BASKET pops up on top of your head and follows you.
     (A second person gets their own basket - P1 and P2.)
  2. Press SPACE. Fruit falls slowly from the sky.
  3. Move left and right and stand UNDER the falling fruit so it drops into your basket.
  4. When the time is up, whoever caught the most fruit wins!

The camera finds each person by their face (MediaPipe Face Detection) and puts the
basket on top of them - no hands needed, just move your whole body.

Run it with:   python catch_game.py
"""

import itertools
import math
import os
import random
import threading
import time
import socket
import json

import cv2
import mediapipe as mp
import numpy as np
import pygame


class NetworkPeer:
    """Lightweight peer-to-peer UDP networking for playing across different computers."""
    def __init__(self, port=5006):
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

    def connect(self, host, port=5006):
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
#  1. SETTINGS  (safe to change)
# =====================================================================

CAMERA_INDEX = 0             # 0 = default webcam. Try 1 if the wrong camera opens
WINDOW_W, WINDOW_H = 960, 720

GAME_SECONDS = 45            # how long a round lasts
FRUIT_RADIUS = 38            # size of the falling fruit
FALL_SPEED = (95, 150)       # how fast fruit falls, pixels per second (smaller = slower)
SPAWN_START = 1.4            # seconds between new fruit at the start...
SPAWN_END = 0.8              # ...getting faster until the end
MAX_FRUITS = 7               # most fruits in the sky at once
NEAR_BASKET_CHANCE = 0.7     # 70% of fruit falls close to a basket so it can be caught
FACE_GRACE = 1.5             # keep the basket this long (seconds) after the camera loses your face
BASKET_FOLLOW = 14.0         # how quickly the basket follows you (bigger = snappier)
BASKET_MIN_WIDTH = 150       # the basket is at least this wide (pixels); it grows with your face size

# Colors
WHITE = (255, 255, 255)
YELLOW = (255, 220, 80)
RED = (255, 70, 70)
GREEN = (90, 235, 120)
ORANGE = (255, 165, 60)
CYAN = (110, 225, 255)
GRAY = (200, 200, 210)

PLAYER_COLORS = [CYAN, ORANGE]
PLAYER_X = (WINDOW_W / 4, WINDOW_W * 3 / 4)     # where each player is expected to stand at the start

# Camera picture size used for tracking (same shape as the window)
CAM_W = 640
CAM_H = int(CAM_W * WINDOW_H / WINDOW_W)


# =====================================================================
#  2. FRUITS + CAMERA  (drawn with code - no image files needed)
# =====================================================================

FRUITS = {
    "apple":  {"skin": (205, 35, 45),  "flesh": (250, 238, 205), "core": (235, 215, 160), "seed": (80, 45, 30)},
    "orange": {"skin": (250, 140, 20), "flesh": (255, 190, 70),  "core": (255, 215, 120), "seed": (255, 228, 160)},
    "lime":   {"skin": (80, 165, 45),  "flesh": (190, 235, 110), "core": (215, 245, 150), "seed": (235, 250, 190)},
    "plum":   {"skin": (110, 45, 140), "flesh": (240, 185, 90),  "core": (225, 160, 70),  "seed": (110, 70, 40)},
}


def shade(color, amount):
    """A lighter (amount > 0) or darker (amount < 0) version of a color."""
    return tuple(max(0, min(255, int(c + amount))) for c in color)


def make_fruit(kind, r, cut):
    """
    Draw a fruit on its own transparent picture.
    cut=False: a whole fruit.   cut=True: the inside of a cut fruit (used for the halves).
    """
    f = FRUITS[kind]
    pad = int(r * 0.45)                       # room around the fruit for stems and leaves
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
        pygame.draw.circle(surf, shade(f["skin"], -45), (c, c), r)               # darker edge
        pygame.draw.circle(surf, f["skin"], (c - o, c - o), int(r * 0.93))
        pygame.draw.circle(surf, shade(f["skin"], 30), (c - int(r * 0.22), c - int(r * 0.22)), int(r * 0.5))
        pygame.draw.ellipse(surf, shade(f["skin"], 110),                          # shiny spot
                            (c - int(r * 0.58), c - int(r * 0.64), int(r * 0.42), int(r * 0.26)))
        if kind in ("apple", "plum"):                                             # stem
            pygame.draw.line(surf, (90, 55, 30), (c, c - int(r * 0.85)),
                             (c + int(r * 0.1), c - int(r * 1.3)), 8)
        if kind in ("apple", "orange"):                                           # leaf
            pygame.draw.ellipse(surf, (70, 170, 60),
                                (c + int(r * 0.12), c - int(r * 1.12), int(r * 0.44), int(r * 0.22)))
        if kind == "lime":                                                        # little tip
            pygame.draw.circle(surf, shade(f["skin"], -60), (c, c - r + 6), 7)
    return surf


# ---- camera ----


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
    Reads the webcam in the background and always keeps only the NEWEST picture.
    Without this, the game waits for the camera on every loop and old pictures pile up,
    so the hand looks like it jumps or disappears during a fast swipe.
    Each picture is stamped with the moment it was captured.
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


# ---- finding people ----


def find_faces(rgb, face_model):
    small_rgb = cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LINEAR)
    small_rgb.flags.writeable = False
    results = face_model.process(small_rgb)
    small_rgb.flags.writeable = True
    faces = []
    if results.detections:
        for d in results.detections:
            bb = d.location_data.relative_bounding_box
            w, h = bb.width * WINDOW_W, bb.height * WINDOW_H
            if w < 20 or h < 20:
                continue
            faces.append(((bb.xmin + bb.width / 2) * WINDOW_W,
                          (bb.ymin + bb.height / 2) * WINDOW_H, w, h))
    faces.sort(key=lambda f: f[2] * f[3], reverse=True)
    return faces[:2]


def person_anchor(i, pl):
    """
    Where player i's body is: (x, y, size). Uses the player's face if the camera has seen it
    (shoulders are about 1.8 face-heights below the face center), otherwise a default spot on
    that player's side of the screen.
    """
    f = pl["face"]
    if f is not None:
        return f["x"], f["y"] + f["h"] * 1.8, max(f["w"], 40.0)
    return PLAYER_X[i], WINDOW_H * 0.65, 130.0


def assign_faces(faces, players, frame_time):
    """
    Match the faces the camera sees to player 1 and player 2.
    Each face goes to the player whose last known spot is closest, so each person
    keeps their own number even when they move around.
    """
    if not faces:
        return
    anchors = [person_anchor(i, pl) for i, pl in enumerate(players)]
    best, best_total = None, 1e18
    for assign in itertools.product([None, 0, 1], repeat=len(faces)):
        used = [a for a in assign if a is not None]
        if len(used) != len(set(used)):
            continue
        total = 0.0
        for f, a in zip(faces, assign):
            total += 1e4 if a is None else math.hypot(f[0] - anchors[a][0], f[1] - anchors[a][1])
        if total < best_total:
            best, best_total = assign, total
    for f, a in zip(faces, best):
        if a is None:
            continue
        old = players[a]["face"]
        if old is not None and frame_time - old["t"] < 1.5:      # smooth a little so the box doesn't jitter
            k = 0.5
            x, y = old["x"] * (1 - k) + f[0] * k, old["y"] * (1 - k) + f[1] * k
            w, h = old["w"] * (1 - k) + f[2] * k, old["h"] * (1 - k) + f[3] * k
        else:
            x, y, w, h = f
        players[a]["face"] = {"x": x, "y": y, "w": w, "h": h, "t": frame_time}


# ---- text ----


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
#  3. PLAYERS, BASKETS AND FALLING FRUIT
# =====================================================================

def new_player():
    """Everything the game remembers about one person."""
    return {"face": None,          # where the camera last saw this person's face: x, y, w, h, t
            "active": False,       # True while this person has a basket
            "born": 0.0,           # when the basket popped up
            "bx": 0.0,             # basket center x (smoothed)
            "top": 0.0,            # y of the basket's rim (smoothed)
            "bw": BASKET_MIN_WIDTH, "bh": 80.0,
            "stack": [],           # colors of the last few caught fruits (they peek out of the basket)
            "score": 0,
            "played": False}


def update_basket(pl, now, dt):
    """Put the basket on top of the person's head and let it follow them smoothly."""
    f = pl["face"]
    if f is None or now - f["t"] > FACE_GRACE:
        pl["active"] = False                       # nobody there: the basket goes away
        return
    bw = max(float(BASKET_MIN_WIDTH), f["w"] * 2.1)
    bh = bw * 0.55
    bottom = f["y"] - f["h"] * 0.5 + 6             # the basket sits on the head
    top = max(60.0, bottom - bh)
    if not pl["active"]:                           # a new basket pops up
        pl["active"] = True
        pl["born"] = now
        pl["bx"], pl["top"] = f["x"], top
    k = min(1.0, dt * BASKET_FOLLOW)
    pl["bx"] += (f["x"] - pl["bx"]) * k
    pl["top"] += (top - pl["top"]) * k
    pl["bw"], pl["bh"] = bw, bh


def spawn_fruit(players):
    """A new fruit starts at the top of the screen. Most fall near a basket so they can be caught."""
    active = [pl for pl in players if pl["active"]]
    if active and random.random() < NEAR_BASKET_CHANCE:
        x = random.choice(active)["bx"] + random.uniform(-230, 230)
    else:
        x = random.uniform(0, WINDOW_W)
    x = min(max(x, FRUIT_RADIUS + 10), WINDOW_W - FRUIT_RADIUS - 10)
    return {"kind": random.choice(list(FRUITS)), "x": x, "base_x": x, "y": -FRUIT_RADIUS * 1.5,
            "vy": random.uniform(*FALL_SPEED), "phase": random.uniform(0, 6.28),
            "angle": random.uniform(0, 360), "spin": random.uniform(-40, 40)}


def update_fruits(fruits, dt, now):
    for fr in fruits:
        fr["y"] += fr["vy"] * dt
        fr["x"] = fr["base_x"] + 14 * math.sin(now * 1.6 + fr["phase"])    # a gentle drifting sway
        fr["angle"] += fr["spin"] * dt
    fruits[:] = [fr for fr in fruits if fr["y"] < WINDOW_H + FRUIT_RADIUS * 2]


def caught_by(fr, players):
    """Index of the player whose basket this fruit just dropped into, or None."""
    for i, pl in enumerate(players):
        if not pl["active"]:
            continue
        half = pl["bw"] / 2 - 6 + FRUIT_RADIUS * 0.3
        if abs(fr["x"] - pl["bx"]) > half:
            continue
        mouth = pl["top"]
        if mouth - FRUIT_RADIUS * 0.2 <= fr["y"] + FRUIT_RADIUS * 0.4 <= mouth + pl["bh"] * 0.7:
            return i
    return None


def pop_effect(particles, floaters, fr, color, now):
    """Juice burst and a '+1' where the fruit was caught."""
    skin = FRUITS[fr["kind"]]["skin"]
    flesh = FRUITS[fr["kind"]]["flesh"]
    for _ in range(14):
        angle = random.uniform(-math.pi, 0)         # sprays upward out of the basket
        speed = random.uniform(80, 260)
        particles.append({"x": fr["x"], "y": fr["y"], "vx": math.cos(angle) * speed,
                          "vy": math.sin(angle) * speed, "life": random.uniform(0.35, 0.7),
                          "r": random.randint(3, 6), "color": random.choice((skin, flesh))})
    floaters.append({"x": fr["x"], "y": fr["y"] - 20, "t": now, "text": "+1", "color": color})


def update_particles(particles, dt):
    for p in particles:
        p["vy"] += 700 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["life"] -= dt
    particles[:] = [p for p in particles if p["life"] > 0]


# =====================================================================
#  4. DRAWING
# =====================================================================

def draw_fruits(screen, fruits, fruit_imgs):
    for fr in fruits:
        img = pygame.transform.rotate(fruit_imgs[fr["kind"]], fr["angle"])
        screen.blit(img, img.get_rect(center=(int(fr["x"]), int(fr["y"]))))


def draw_basket(screen, pl, index, now):
    """A woven basket sitting on the person's head. It pops up with a little grow-in."""
    if not pl["active"]:
        return
    grow = min(1.0, (now - pl["born"]) / 0.35)
    grow = 1 - (1 - grow) ** 3                      # starts fast, settles gently
    w, h = pl["bw"] * grow, pl["bh"] * grow
    cx = pl["bx"]
    bottom = pl["top"] + pl["bh"]
    top = bottom - h
    color = PLAYER_COLORS[index]

    for n, skin in enumerate(pl["stack"][-4:]):     # caught fruit peeking over the rim
        r = max(4, int(w * 0.1))
        pygame.draw.circle(screen, shade(skin, -40), (int(cx + (n - 1.5) * w * 0.2), int(top - w * 0.01)), r + 2)
        pygame.draw.circle(screen, skin, (int(cx + (n - 1.5) * w * 0.2), int(top - w * 0.01)), r)

    body = [(cx - w / 2, top), (cx + w / 2, top), (cx + w * 0.36, bottom), (cx - w * 0.36, bottom)]
    pygame.draw.polygon(screen, (166, 110, 58), body)
    for k in (1, 2, 3):                             # woven rows
        f = k / 4
        y = top + h * f
        half = w / 2 - (w / 2 - w * 0.36) * f
        pygame.draw.line(screen, (120, 78, 38), (cx - half, y), (cx + half, y), 3)
    for k in (-2, -1, 0, 1, 2):                     # woven columns
        pygame.draw.line(screen, (134, 88, 44), (cx + k * w * 0.2, top), (cx + k * w * 0.14, bottom), 2)
    pygame.draw.polygon(screen, (95, 60, 28), body, 4)

    rim = pygame.Rect(0, 0, int(w * 1.08), max(8, int(14 * grow)))
    rim.center = (int(cx), int(top))
    pygame.draw.rect(screen, color, rim, border_radius=7)
    pygame.draw.rect(screen, shade(color, -80), rim, 2, border_radius=7)
    if grow > 0.8:
        draw_text(screen, f"P{index + 1}", 30, WHITE, int(cx), int(top + h * 0.55))


def draw_effects(screen, particles, floaters, now):
    for p in particles:
        radius = max(1, int(p["r"] * min(1.0, p["life"] / 0.3)))
        pygame.draw.circle(screen, p["color"], (int(p["x"]), int(p["y"])), radius)
    for f in floaters:
        age = now - f["t"]
        draw_text(screen, f["text"], 54, f["color"], int(f["x"]), int(f["y"] - age * 70))
    floaters[:] = [f for f in floaters if now - f["t"] < 0.8]


def draw_hud(screen, players, time_left, show_time):
    for i, pl in enumerate(players):
        if not (pl["active"] or pl["played"]):
            continue
        left = (i == 0)
        x = 20 if left else WINDOW_W - 20
        draw_text(screen, f"P{i + 1}   {pl['score']}", 48, PLAYER_COLORS[i], x, 34,
                  align="left" if left else "right")
    if show_time:
        color = WHITE if time_left > 10 else RED
        draw_text(screen, f"{int(math.ceil(time_left))}", 76, color, WINDOW_W // 2, 44)


def draw_title(screen, players):
    draw_text(screen, "FRUIT CATCH", 130, YELLOW, WINDOW_W // 2, 95)
    draw_text(screen, "Stand under the falling fruit to catch it in your basket!", 38, CYAN, WINDOW_W // 2, 170)
    if not any(pl["active"] for pl in players):
        draw_text(screen, "Step in front of the camera - a basket will pop up on you.", 34, YELLOW, WINDOW_W // 2, 235)
    draw_text(screen, "1. Stand in front of the camera - a basket appears on your head (1 or 2 players).", 28, WHITE, WINDOW_W // 2, 540)
    draw_text(screen, "2. Press SPACE. Fruit falls slowly from the sky.", 28, WHITE, WINDOW_W // 2, 574)
    draw_text(screen, f"3. Move left and right under the fruit. Most fruit in {GAME_SECONDS} seconds wins!", 28, WHITE, WINDOW_W // 2, 608)
    size = 54 + int(5 * math.sin(time.perf_counter() * 5))
    draw_text(screen, "PRESS SPACE TO START", size, YELLOW, WINDOW_W // 2, 655)
    draw_text(screen, "(click the game window first if nothing happens)   |   ESC = quit", 26, GRAY, WINDOW_W // 2, 698)


def draw_result(screen, players):
    cx = WINDOW_W // 2
    played = [i for i, pl in enumerate(players) if pl["played"]]
    draw_text(screen, "TIME'S UP!", 110, YELLOW, cx, 130)
    if len(played) >= 2:
        a, b = players[0]["score"], players[1]["score"]
        if a == b:
            draw_text(screen, f"IT'S A TIE!  {a} - {b}", 80, WHITE, cx, 230)
        else:
            win = 0 if a > b else 1
            draw_text(screen, f"PLAYER {win + 1} WINS!", 96, PLAYER_COLORS[win], cx, 230)
            draw_text(screen, f"{a}  -  {b}", 64, WHITE, cx, 305)
    elif len(played) == 1:
        i = played[0]
        draw_text(screen, f"You caught {players[i]['score']} fruit!", 80, PLAYER_COLORS[i], cx, 230)
    else:
        draw_text(screen, "Nobody played this round.", 60, WHITE, cx, 230)
    draw_text(screen, "SPACE = play again   |   ESC = quit", 34, WHITE, cx, WINDOW_H - 36)


# =====================================================================
#  5. MAIN GAME LOOP
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Fruit Catch - Stand Under the Fruit")
    clock = pygame.time.Clock()

    cap = open_camera()
    if cap is None:
        print("Could not get any picture from the webcam.")
        print("1. Close other programs that use the camera (Zoom, Teams, browser tabs, Camera app).")
        print("2. Windows Settings > Privacy & security > Camera: allow desktop apps to use the camera.")
        print(f"3. Try another number: CAMERA_INDEX = {1 - CAMERA_INDEX if CAMERA_INDEX in (0, 1) else 0} in the settings.")
        pygame.quit()
        return

    face_model = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.4)
    camera = CameraThread(cap)
    last_frame_id = -1

    fruit_imgs = {kind: make_fruit(kind, FRUIT_RADIUS, cut=False) for kind in FRUITS}
    dim = pygame.Surface((WINDOW_W, WINDOW_H))        # darkens the camera so the fruit pops
    dim.set_alpha(60)
    dim.fill((0, 0, 0))
    background = None

    players = [new_player(), new_player()]
    state = "TITLE"                # TITLE -> PLAYING -> RESULT -> (SPACE) -> PLAYING ...
    fruits, particles, floaters = [], [], []
    game_start = 0.0
    next_spawn = 0.0
    message_text, message_until = "", 0.0
    prev = time.perf_counter()
    running = True

    while running:
        # ---------- keyboard / window ----------
        space_pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    space_pressed = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                space_pressed = True

        # ---------- camera + people ----------
        rgb, frame_time, frame_id = camera.latest()
        now = time.perf_counter()
        dt = min(0.1, now - prev)
        prev = now

        if rgb is not None and frame_id != last_frame_id:
            last_frame_id = frame_id
            background = pygame.image.frombuffer(rgb.tobytes(), (WINDOW_W, WINDOW_H), "RGB")
            assign_faces(find_faces(rgb, face_model), players, frame_time)

        for pl in players:
            update_basket(pl, now, dt)

        # ---------- start a round ----------
        if space_pressed and state in ("TITLE", "RESULT"):
            if any(pl["active"] for pl in players):
                state = "PLAYING"
                game_start = now
                next_spawn = now + 1.0
                fruits, particles, floaters = [], [], []
                for pl in players:
                    pl["score"] = 0
                    pl["stack"] = []
                    pl["played"] = False
                print(f"[game] Round started - {GAME_SECONDS} seconds. Catch the fruit!")
            else:
                message_text = "Step in front of the camera first!"
                message_until = now + 2.0

        # ---------- game logic ----------
        time_left = GAME_SECONDS
        if state == "PLAYING":
            elapsed = now - game_start
            time_left = max(0.0, GAME_SECONDS - elapsed)
            for pl in players:
                if pl["active"]:
                    pl["played"] = True
            if time_left <= 0:
                state = "RESULT"
                fruits = []
                print("[game] Time's up! " + "  ".join(f"P{i + 1}: {pl['score']}" for i, pl in enumerate(players) if pl["played"]))
            else:
                if now >= next_spawn and len(fruits) < MAX_FRUITS:
                    fruits.append(spawn_fruit(players))
                    gap = SPAWN_START + (SPAWN_END - SPAWN_START) * (elapsed / GAME_SECONDS)
                    next_spawn = now + gap * random.uniform(0.8, 1.2)
                update_fruits(fruits, dt, now)
                for fr in fruits[:]:
                    who = caught_by(fr, players)
                    if who is not None:
                        players[who]["score"] += 1
                        players[who]["stack"].append(FRUITS[fr["kind"]]["skin"])
                        pop_effect(particles, floaters, fr, PLAYER_COLORS[who], now)
                        fruits.remove(fr)
        update_particles(particles, dt)

        # ---------- drawing ----------
        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill((25, 25, 35))
        screen.blit(dim, (0, 0))

        draw_fruits(screen, fruits, fruit_imgs)
        for i, pl in enumerate(players):
            draw_basket(screen, pl, i, now)
        draw_effects(screen, particles, floaters, now)
        draw_hud(screen, players, time_left, state == "PLAYING")

        if state == "TITLE":
            draw_title(screen, players)
        elif state == "RESULT":
            draw_result(screen, players)

        if now < message_until:
            draw_text(screen, message_text, 40, YELLOW, WINDOW_W // 2, WINDOW_H - 110)

        pygame.display.flip()
        clock.tick(60)

    camera.stop()
    cap.release()
    face_model.close()
    pygame.quit()


if __name__ == "__main__":
    main()
