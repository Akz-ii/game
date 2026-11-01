"""
WALL PAINTER - COVER THE WHOLE SCREEN WITH RED PAINT USING YOUR HAND
=====================================================================

How to play:
  1. Hold ONE hand up in front of the webcam. The middle of your palm is a big paint roller.
  2. Press SPACE to start.
  3. Move your hand around - everywhere it goes leaves THICK red paint on the "wall".
  4. Cover the whole screen as fast as you can! The bar at the top shows how much is painted.
  5. When the wall is painted, your time is shown. SPACE = play again.

Keys:   SPACE = start / play again     R = wipe the paint and restart     ESC = quit

Run it with:   python wall_painter.py
"""

import math
import os
import threading
import time

import cv2
import mediapipe as mp
import numpy as np
import pygame


# =====================================================================
#  1. SETTINGS  (safe to change)
# =====================================================================

CAMERA_INDEX = 0             # 0 = default webcam. Try 1 if the wrong camera opens
WINDOW_W, WINDOW_H = 960, 720

# --- Paint ---
BRUSH_RADIUS = 100           # how THICK the paint stroke is (bigger = thicker = faster to finish)
PAINT_COLOR = (215, 25, 35)  # the red paint (R, G, B)
WIN_PERCENT = 96             # the wall counts as finished at this much painted (100 = every last corner)

# --- Hand tracking ---
EDGE_REACH = 1.25            # above 1.0 = your hand reaches the screen edges without leaving the camera picture
SMOOTHING = 0.7              # 1.0 = follow the hand exactly, lower = smoother but slower to follow
HAND_GRACE = 0.25            # seconds the hand still counts after the camera last saw it
BRIDGE_TIME = 1.5            # if the camera loses your hand for less than this, the line is joined up
                             # when it finds the hand again (no gaps in your stroke)
HAND_MODEL_COMPLEXITY = 0    # 0 = Lite model for locked 60 FPS real-time tracking
DETECT_CONFIDENCE = 0.3      # lower = finds the hand again more easily
TRACK_CONFIDENCE = 0.3       # lower = keeps following the hand even when it is blurry

# Colors
WHITE = (255, 255, 255)
YELLOW = (255, 220, 80)
GREEN = (90, 235, 120)
CYAN = (110, 225, 255)
GRAY = (200, 200, 210)

# Camera picture size used for tracking (same shape as the window)
CAM_W = 640
CAM_H = int(CAM_W * WINDOW_H / WINDOW_W)

# How the screen is split up to measure how much is painted (10x10 pixel squares)
CELL = 10
GRID_W, GRID_H = WINDOW_W // CELL, WINDOW_H // CELL
CELL_X = (np.arange(GRID_W) * CELL + CELL / 2)[None, :]
CELL_Y = (np.arange(GRID_H) * CELL + CELL / 2)[:, None]


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
            with self.lock:
                self.rgb = rgb
                self.frame_id += 1

    def latest(self):
        """Returns (picture, picture_number)."""
        with self.lock:
            return self.rgb, self.frame_id

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
    small_rgb = cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LINEAR)
    small_rgb.flags.writeable = False                    # lets MediaPipe skip a copy (a bit faster)
    results = hands.process(small_rgb)
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


# =====================================================================
#  4. PAINTING
# =====================================================================

def mark_covered(covered, x, y, r):
    """Remember that the squares under a round brush at (x, y) are now painted."""
    x0 = max(0, int((x - r) // CELL))
    x1 = min(GRID_W, int((x + r) // CELL) + 1)
    y0 = max(0, int((y - r) // CELL))
    y1 = min(GRID_H, int((y + r) // CELL) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    inside = (CELL_X[:, x0:x1] - x) ** 2 + (CELL_Y[y0:y1, :] - y) ** 2 <= r * r
    covered[y0:y1, x0:x1] |= inside


def paint_stroke(canvas, covered, start, end):
    """Paint a thick, smooth line from start to end by stamping round dabs of paint along it."""
    if start is None:
        start = end
    dist = math.hypot(end[0] - start[0], end[1] - start[1])
    steps = max(1, int(dist / (BRUSH_RADIUS * 0.15)))
    for i in range(steps + 1):
        t = i / steps
        x = start[0] + (end[0] - start[0]) * t
        y = start[1] + (end[1] - start[1]) * t
        pygame.draw.circle(canvas, PAINT_COLOR, (int(x), int(y)), BRUSH_RADIUS)
        mark_covered(covered, x, y, BRUSH_RADIUS)


def percent_painted(covered):
    return 100.0 * covered.sum() / covered.size


# =====================================================================
#  5. DRAWING THE SCREEN
# =====================================================================

def draw_brush(screen, pos):
    """A ring showing where (and how big) your paint roller is."""
    p = (int(pos[0]), int(pos[1]))
    pygame.draw.circle(screen, (0, 0, 0), (p[0] + 2, p[1] + 2), BRUSH_RADIUS, 3)
    pygame.draw.circle(screen, WHITE, p, BRUSH_RADIUS, 3)
    pygame.draw.circle(screen, WHITE, p, 5)


def draw_progress(screen, percent):
    bar = pygame.Rect(0, 0, 420, 28)
    bar.center = (WINDOW_W // 2, 30)
    pygame.draw.rect(screen, (0, 0, 0), bar.inflate(8, 8), border_radius=10)
    pygame.draw.rect(screen, (60, 60, 70), bar, border_radius=8)
    fill = bar.copy()
    fill.width = int(bar.width * min(1.0, percent / WIN_PERCENT))
    if fill.width > 0:
        pygame.draw.rect(screen, PAINT_COLOR, fill, border_radius=8)
    draw_text(screen, f"{int(percent)}% PAINTED", 28, WHITE, WINDOW_W // 2, 30)


def draw_title(screen):
    draw_text(screen, "WALL PAINTER", 120, (255, 90, 90), WINDOW_W // 2, 280)
    draw_text(screen, "Cover the whole screen with thick red paint - using your hand!", 34, CYAN, WINDOW_W // 2, 355)
    draw_text(screen, "1. Hold ONE hand up. The middle of your palm is the paint roller.", 28, WHITE, WINDOW_W // 2, 450)
    draw_text(screen, "2. Move it around: everywhere it goes, it leaves thick red paint.", 28, WHITE, WINDOW_W // 2, 484)
    draw_text(screen, "3. Paint every part of the wall as fast as you can!", 28, WHITE, WINDOW_W // 2, 518)
    size = 54 + int(5 * math.sin(time.perf_counter() * 5))
    draw_text(screen, "PRESS SPACE TO START", size, YELLOW, WINDOW_W // 2, 610)
    draw_text(screen, "R = wipe the paint   |   ESC = quit", 26, GRAY, WINDOW_W // 2, 665)


# =====================================================================
#  6. MAIN GAME LOOP
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Wall Painter")
    clock = pygame.time.Clock()

    cap = open_camera()
    if cap is None:
        print("Could not get any picture from the webcam.")
        print("1. Close other programs that use the camera (Zoom, Teams, browser tabs, Camera app).")
        print("2. Windows Settings > Privacy & security > Camera: allow desktop apps to use the camera.")
        print(f"3. Try another number: CAMERA_INDEX = {1 - CAMERA_INDEX if CAMERA_INDEX in (0, 1) else 0} in the settings.")
        pygame.quit()
        return

    hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1,
                                     model_complexity=HAND_MODEL_COMPLEXITY,
                                     min_detection_confidence=DETECT_CONFIDENCE,
                                     min_tracking_confidence=TRACK_CONFIDENCE)
    camera = CameraThread(cap)
    last_frame_id = -1

    dim = pygame.Surface((WINDOW_W, WINDOW_H))        # darkens the camera so the paint pops
    dim.set_alpha(90)
    dim.fill((0, 0, 0))
    background = None

    canvas = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)     # the paint lives here
    covered = np.zeros((GRID_H, GRID_W), dtype=bool)                   # which squares are painted

    state = "TITLE"                # TITLE -> PLAY -> DONE -> (SPACE) -> PLAY
    pos = None                     # smoothed palm position
    last_seen = -10.0
    last_paint = None              # where the brush was on the previous frame
    start_time = None              # set when the first paint touches the wall
    final_time = 0.0
    best = None
    running = True

    def wipe():
        canvas.fill((0, 0, 0, 0))
        covered[:] = False

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
                elif event.key == pygame.K_r and state != "TITLE":
                    wipe()
                    state, start_time, last_paint = "PLAY", None, None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                space_pressed = True

        # ---------- camera + hand ----------
        rgb, frame_id = camera.latest()
        now = time.perf_counter()

        hand = None                                   # only a NEW camera picture can give a new hand position
        if rgb is not None and frame_id != last_frame_id:
            last_frame_id = frame_id
            background = pygame.image.frombuffer(rgb.tobytes(), (WINDOW_W, WINDOW_H), "RGB")
            hand = find_palm(rgb, hands)

        if hand is not None:
            if now - last_seen > BRIDGE_TIME:
                last_paint = None                     # hand was gone for a long time: start a new line
            if pos is None or now - last_seen > HAND_GRACE:
                pos = hand                            # hand found again: jump to it (the line is joined up)
            else:
                pos = (pos[0] + (hand[0] - pos[0]) * SMOOTHING,
                       pos[1] + (hand[1] - pos[1]) * SMOOTHING)
            last_seen = now
        elif pos is not None and now - last_seen > HAND_GRACE:
            pos = None                                # hand really gone (last_paint is kept to join the line)
        hand_visible = pos is not None

        # ---------- start / restart ----------
        if space_pressed and state in ("TITLE", "DONE"):
            wipe()
            state, start_time, last_paint = "PLAY", None, None
            print("[game] Paint the whole wall!")

        # ---------- painting ----------
        if state == "PLAY" and pos is not None:
            paint_stroke(canvas, covered, last_paint, pos)
            last_paint = pos
            if start_time is None:
                start_time = now

            if percent_painted(covered) >= WIN_PERCENT:
                canvas.fill(PAINT_COLOR + (255,))     # finish off the last little gaps
                final_time = now - start_time
                best = final_time if best is None else min(best, final_time)
                state = "DONE"
                print(f"[game] Wall painted in {final_time:.1f} seconds")

        # ---------- drawing ----------
        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill((25, 25, 35))
        screen.blit(dim, (0, 0))
        screen.blit(canvas, (0, 0))

        if state != "DONE" and pos is not None:
            draw_brush(screen, pos)

        if state == "TITLE":
            draw_title(screen)
        else:
            draw_progress(screen, 100.0 if state == "DONE" else percent_painted(covered))
            elapsed = final_time if state == "DONE" else ((now - start_time) if start_time else 0.0)
            draw_text(screen, f"TIME  {elapsed:.1f}s", 36, YELLOW, 20, 30, align="left")
            if hand_visible:
                draw_text(screen, "HAND OK", 28, GREEN, WINDOW_W - 20, 30, align="right")
            else:
                draw_text(screen, "FINDING HAND...", 28, YELLOW, WINDOW_W - 20, 30, align="right")

        if state == "PLAY" and start_time is None:
            draw_text(screen, "Move your hand to start painting!", 40, WHITE, WINDOW_W // 2, WINDOW_H // 2)
        elif state == "DONE":
            draw_text(screen, "WALL PAINTED!", 110, WHITE, WINDOW_W // 2, 300)
            draw_text(screen, f"Your time: {final_time:.1f}s   |   BEST: {best:.1f}s", 46, WHITE, WINDOW_W // 2, 390)
            draw_text(screen, "SPACE = play again   |   ESC = quit", 34, WHITE, WINDOW_W // 2, 455)

        pygame.display.flip()
        clock.tick(60)

    camera.stop()
    cap.release()
    hands.close()
    pygame.quit()


if __name__ == "__main__":
    main()
