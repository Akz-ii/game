"""
MILK THE COW - FILL THE CUP BY MOVING YOUR HAND DOWN
=====================================================

How to play:
  1. Hold ONE hand up in front of the webcam. The ring on the screen is your hand.
  2. Press SPACE. Put your hand next to the cow's udder (inside the yellow box).
  3. Move your hand DOWN - like squeezing the udder. Milk squirts into the cup!
  4. Lift your hand back up (no milk on the way up) and pull DOWN again.
  5. Keep going until the cup is FULL. Try to beat your best time!

Only moving DOWN gives milk, so you have to keep pulling down again and again.

Keys:   SPACE = start / play again     R = empty the cup and restart     ESC = quit

Run it with:   python milk_the_cow.py
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

# --- Milking ---
MILK_PER_PIXEL = 0.06        # milk per pixel of downward hand movement (bigger = fills faster)
CUP_CAPACITY = 100.0         # the cup is full at this amount (leave at 100 = 100%)
MIN_STEP = 3                 # downward moves smaller than this (pixels per frame) are ignored (hand shake)
MAX_STEP = 70                # moves bigger than this in one frame are ignored (tracking jumps)
MILK_ZONE = pygame.Rect(330, 290, 300, 280)   # your hand must be inside this box to milk

# --- Hand tracking ---
EDGE_REACH = 1.2             # above 1.0 = your hand reaches the screen edges without leaving the camera picture
SMOOTHING = 0.6              # 1.0 = follow the hand exactly, lower = smoother but slower to follow
HAND_GRACE = 0.25            # seconds the hand still counts after the camera last saw it
HAND_MODEL_COMPLEXITY = 0    # 0 = Lite model for locked 60 FPS real-time tracking
DETECT_CONFIDENCE = 0.3      # lower = finds the hand again more easily
TRACK_CONFIDENCE = 0.3       # lower = keeps following the hand even when it is blurry

# Colors
WHITE = (255, 255, 255)
YELLOW = (255, 220, 80)
GREEN = (90, 235, 120)
CYAN = (110, 225, 255)
GRAY = (200, 200, 210)
OUTLINE = (40, 40, 45)
COW_WHITE = (247, 247, 247)
COW_SPOT = (55, 55, 62)
PINK = (245, 170, 180)
DARK_PINK = (222, 128, 145)
MILK_WHITE = (253, 253, 255)
GLASS = (205, 228, 242)
GLASS_EDGE = (120, 160, 190)

# Camera picture size used for tracking (same shape as the window)
CAM_W = 640
CAM_H = int(CAM_W * WINDOW_H / WINDOW_W)
PREVIEW_W, PREVIEW_H = 200, 150            # the little camera picture in the corner

# Where things are on the screen
TEAT_TIPS = [(440, 356), (466, 356), (492, 356), (518, 356)]     # where the milk comes out
CUP_X, CUP_TOP, CUP_BOTTOM = WINDOW_W // 2, 570, 700
CUP_TOP_W, CUP_BOTTOM_W = 190, 140


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
    frame = cv2.resize(frame, (CAM_W, CAM_H))
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
    """Draw text with a dark shadow so it can be read on top of the picture."""
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
#  4. MILK
# =====================================================================

def squirt(particles):
    """Shoot a few drops of milk from the udder down towards the cup."""
    for _ in range(3):
        x, y = random.choice(TEAT_TIPS)
        particles.append({"x": x + random.uniform(-2, 2), "y": float(y),
                          "vx": random.uniform(-12, 12), "vy": random.uniform(160, 280)})


def update_particles(particles, dt):
    for p in particles:
        p["vy"] += 1400 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
    particles[:] = [p for p in particles if p["y"] < CUP_TOP + 10]     # drops disappear into the cup


def cup_width(y):
    """How wide the cup is at height y (it gets narrower towards the bottom)."""
    t = (y - CUP_TOP) / (CUP_BOTTOM - CUP_TOP)
    return CUP_TOP_W + (CUP_BOTTOM_W - CUP_TOP_W) * t


# =====================================================================
#  5. DRAWING THE SCREEN
# =====================================================================

def draw_scene(screen, now):
    """Sky, sun, clouds and a grass field."""
    screen.fill((150, 210, 250))
    pygame.draw.circle(screen, (255, 235, 120), (860, 90), 50)
    for base_x, y in ((120, 70), (460, 40), (700, 120)):
        x = (base_x + now * 12) % (WINDOW_W + 300) - 150
        for dx, dy, w, h in ((0, 0, 110, 44), (30, -18, 80, 44), (-30, -8, 70, 36)):
            pygame.draw.ellipse(screen, (250, 252, 255), (x + dx, y + dy, w, h))
    pygame.draw.rect(screen, (70, 160, 80), (0, 400, WINDOW_W, WINDOW_H - 400))
    pygame.draw.rect(screen, (55, 135, 65), (0, 400, WINDOW_W, 14))


def draw_cow(screen, now, milking, mooing):
    """A simple cow drawn from shapes. It wags its tail faster while being milked."""
    pygame.draw.ellipse(screen, (50, 125, 60), (260, 392, 470, 34))            # shadow

    # tail
    sway = math.sin(now * (9 if milking else 2.5)) * (26 if milking else 14)
    base, mid, end = (700, 160), (735 + sway * 0.5, 215), (745 + sway, 285)
    pygame.draw.lines(screen, OUTLINE, False, [base, mid, end], 8)
    pygame.draw.circle(screen, OUTLINE, (int(end[0]), int(end[1]) + 8), 14)

    # legs
    for x in (300, 360, 580, 640):
        leg = pygame.Rect(x, 260, 36, 145)
        pygame.draw.rect(screen, COW_WHITE, leg)
        pygame.draw.rect(screen, OUTLINE, leg, 3)
        pygame.draw.rect(screen, OUTLINE, (x, 390, 36, 18))                   # hoof

    # body with spots
    body = pygame.Rect(250, 90, 460, 210)
    pygame.draw.ellipse(screen, COW_WHITE, body)
    for spot in ((350, 150, 90, 60), (520, 125, 110, 60), (590, 185, 70, 50), (400, 235, 80, 40)):
        pygame.draw.ellipse(screen, COW_SPOT, spot)
    pygame.draw.ellipse(screen, OUTLINE, body, 4)

    # udder and teats
    udder = pygame.Rect(410, 282, 140, 60)
    pygame.draw.ellipse(screen, PINK, udder)
    pygame.draw.ellipse(screen, OUTLINE, udder, 3)
    for i in range(4):
        teat = pygame.Rect(433 + i * 26, 328, 14, 28)
        pygame.draw.rect(screen, DARK_PINK, teat, border_radius=6)
        pygame.draw.rect(screen, OUTLINE, teat, 2, border_radius=6)

    # head
    pygame.draw.polygon(screen, (235, 220, 180), [(165, 128), (150, 92), (188, 120)])     # horns
    pygame.draw.polygon(screen, (235, 220, 180), [(240, 122), (262, 90), (268, 128)])
    for ear in ((92, 138, 58, 28), (262, 136, 58, 28)):
        pygame.draw.ellipse(screen, COW_WHITE, ear)
        pygame.draw.ellipse(screen, OUTLINE, ear, 3)
    head = pygame.Rect(133, 122, 144, 136)
    pygame.draw.ellipse(screen, COW_WHITE, head)
    pygame.draw.ellipse(screen, COW_SPOT, (150, 128, 44, 34))                              # spot on the head
    pygame.draw.ellipse(screen, OUTLINE, head, 4)
    snout = pygame.Rect(120, 205, 96, 58)
    pygame.draw.ellipse(screen, PINK, snout)
    pygame.draw.ellipse(screen, OUTLINE, snout, 3)
    pygame.draw.circle(screen, DARK_PINK, (148, 236), 6)                                   # nostrils
    pygame.draw.circle(screen, DARK_PINK, (188, 236), 6)
    for ex in (172, 236):                                                                  # eyes
        pygame.draw.circle(screen, WHITE, (ex, 172), 11)
        pygame.draw.circle(screen, OUTLINE, (ex, 172), 11, 2)
        pygame.draw.circle(screen, OUTLINE, (ex, 174), 5)

    if mooing:
        bubble = pygame.Rect(40, 20, 170, 70)
        pygame.draw.ellipse(screen, WHITE, bubble)
        pygame.draw.ellipse(screen, OUTLINE, bubble, 3)
        draw_text(screen, "MOO!", 52, OUTLINE, bubble.centerx, bubble.centery)


def draw_cup(screen, fraction):
    """The glass cup under the cow. 'fraction' is how full it is (0 to 1)."""
    handle = pygame.Rect(CUP_X + 78, CUP_TOP + 25, 70, 70)
    pygame.draw.ellipse(screen, GLASS_EDGE, handle, 9)

    outline = [(CUP_X - CUP_TOP_W / 2, CUP_TOP), (CUP_X + CUP_TOP_W / 2, CUP_TOP),
               (CUP_X + CUP_BOTTOM_W / 2, CUP_BOTTOM), (CUP_X - CUP_BOTTOM_W / 2, CUP_BOTTOM)]
    pygame.draw.polygon(screen, GLASS, outline)

    if fraction > 0.0:
        floor = CUP_BOTTOM - 6
        level = floor - (floor - CUP_TOP - 6) * min(1.0, fraction)
        w_level, w_floor = cup_width(level) - 12, cup_width(floor) - 12
        milk = [(CUP_X - w_level / 2, level), (CUP_X + w_level / 2, level),
                (CUP_X + w_floor / 2, floor), (CUP_X - w_floor / 2, floor)]
        pygame.draw.polygon(screen, MILK_WHITE, milk)
        foam = pygame.Rect(0, 0, int(w_level), 14)
        foam.center = (CUP_X, int(level))
        pygame.draw.ellipse(screen, WHITE, foam)

    pygame.draw.polygon(screen, GLASS_EDGE, outline, 5)


def draw_particles(screen, particles):
    for p in particles:
        tail = (p["x"] - p["vx"] * 0.025, p["y"] - p["vy"] * 0.025)
        pygame.draw.line(screen, MILK_WHITE, tail, (p["x"], p["y"]), 6)


def draw_zone(screen, now, in_zone, show_arrows):
    """The box where your hand milks, with arrows showing which way to move."""
    color = GREEN if in_zone else YELLOW
    pygame.draw.rect(screen, (0, 0, 0), MILK_ZONE.move(2, 2), 4, border_radius=18)
    pygame.draw.rect(screen, color, MILK_ZONE, 4, border_radius=18)
    if show_arrows:
        shift = (now * 140) % 110
        for x in (MILK_ZONE.left + 32, MILK_ZONE.right - 32):
            y = MILK_ZONE.top + 40 + shift
            pygame.draw.line(screen, color, (x, y - 40), (x, y + 6), 8)
            pygame.draw.polygon(screen, color, [(x, y + 26), (x - 18, y + 2), (x + 18, y + 2)])


def draw_hand(screen, pos, in_zone):
    """A ring showing where your hand is."""
    p = (int(pos[0]), int(pos[1]))
    color = GREEN if in_zone else WHITE
    pygame.draw.circle(screen, (0, 0, 0), (p[0] + 2, p[1] + 2), 34, 4)
    pygame.draw.circle(screen, color, p, 34, 4)
    pygame.draw.circle(screen, color, p, 6)


def draw_title(screen):
    draw_text(screen, "MILK THE COW", 120, (255, 255, 255), WINDOW_W // 2, 160)
    draw_text(screen, "Fill the cup - just by moving your hand DOWN!", 38, (40, 90, 140), WINDOW_W // 2, 250)
    draw_text(screen, "1. Hold ONE hand up. The ring on screen is your hand.", 28, OUTLINE, WINDOW_W // 2, 340)
    draw_text(screen, "2. Put it next to the udder, in the yellow box.", 28, OUTLINE, WINDOW_W // 2, 374)
    draw_text(screen, "3. Move it DOWN, lift it back up, and DOWN again - milk squirts!", 28, OUTLINE, WINDOW_W // 2, 408)
    size = 54 + int(5 * math.sin(time.perf_counter() * 5))
    draw_text(screen, "PRESS SPACE TO START", size, YELLOW, WINDOW_W // 2, 500)
    draw_text(screen, "R = empty the cup   |   ESC = quit", 26, OUTLINE, WINDOW_W // 2, 560)


# =====================================================================
#  6. MAIN GAME LOOP
# =====================================================================

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Milk the Cow")
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
    preview = None                 # the small camera picture in the corner

    state = "TITLE"                # TITLE -> PLAY -> DONE -> (SPACE) -> PLAY
    pos = None                     # smoothed palm position
    last_seen = -10.0
    prev_y = None                  # where the hand was (up/down) on the previous frame
    milk = 0.0
    particles = []
    start_time = None              # set when the first milk comes out
    final_time = 0.0
    best = None
    prev = time.perf_counter()
    running = True

    def restart():
        nonlocal milk, particles, start_time, prev_y, state
        milk, particles, start_time, prev_y = 0.0, [], None, None
        state = "PLAY"

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
                    restart()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                space_pressed = True

        # ---------- camera + hand ----------
        rgb, frame_id = camera.latest()
        now = time.perf_counter()
        dt = min(0.1, now - prev)
        prev = now

        hand = None                                   # only a NEW camera picture can give a new hand position
        if rgb is not None and frame_id != last_frame_id:
            last_frame_id = frame_id
            picture = pygame.image.frombuffer(rgb.tobytes(), (CAM_W, CAM_H), "RGB")
            preview = pygame.transform.scale(picture, (PREVIEW_W, PREVIEW_H))
            hand = find_palm(rgb, hands)

        if hand is not None:
            if pos is None or now - last_seen > HAND_GRACE:
                pos = hand                            # hand just appeared (or was lost for a moment)
                prev_y = None                         # don't count the jump as milking
            else:
                pos = (pos[0] + (hand[0] - pos[0]) * SMOOTHING,
                       pos[1] + (hand[1] - pos[1]) * SMOOTHING)
            last_seen = now
        elif pos is not None and now - last_seen > HAND_GRACE:
            pos, prev_y = None, None                  # hand really gone
        hand_visible = pos is not None

        # ---------- start / restart ----------
        if space_pressed and state in ("TITLE", "DONE"):
            restart()
            print("[game] Milk the cow until the cup is full!")

        # ---------- milking: only moving DOWN inside the box gives milk ----------
        milking = False
        in_zone = pos is not None and MILK_ZONE.collidepoint(pos)
        if state == "PLAY" and pos is not None:
            if in_zone and prev_y is not None:
                step = pos[1] - prev_y                # positive = the hand moved down
                if MIN_STEP <= step <= MAX_STEP:
                    milk = min(CUP_CAPACITY, milk + step * MILK_PER_PIXEL)
                    milking = True
                    squirt(particles)
                    if start_time is None:
                        start_time = now
            prev_y = pos[1]
        else:
            prev_y = None

        update_particles(particles, dt)

        if state == "PLAY" and milk >= CUP_CAPACITY:
            final_time = now - start_time if start_time else 0.0
            best = final_time if best is None else min(best, final_time)
            state = "DONE"
            print(f"[game] Cup full in {final_time:.1f} seconds")

        # ---------- drawing ----------
        draw_scene(screen, now)
        draw_cow(screen, now, milking, mooing=(state == "DONE"))
        draw_cup(screen, milk / CUP_CAPACITY)
        draw_particles(screen, particles)

        if state == "PLAY":
            draw_zone(screen, now, in_zone, show_arrows=not milking)
        if state != "DONE" and pos is not None:
            draw_hand(screen, pos, in_zone)

        if preview is not None:                       # small camera picture so you can see yourself
            screen.blit(preview, (16, WINDOW_H - PREVIEW_H - 16))
            pygame.draw.rect(screen, WHITE, (16, WINDOW_H - PREVIEW_H - 16, PREVIEW_W, PREVIEW_H), 3)

        if state == "TITLE":
            draw_title(screen)
        else:
            percent = int(milk / CUP_CAPACITY * 100)
            draw_text(screen, f"MILK {percent}%", 52, WHITE, CUP_X - 120, 640, align="right")
            elapsed = final_time if state == "DONE" else ((now - start_time) if start_time else 0.0)
            draw_text(screen, f"TIME  {elapsed:.1f}s", 36, (40, 90, 140), 20, 30, align="left")
            if hand_visible:
                draw_text(screen, "HAND OK", 28, (30, 140, 60), WINDOW_W - 20, 30, align="right")
            else:
                draw_text(screen, "FINDING HAND...", 28, (200, 120, 0), WINDOW_W - 20, 30, align="right")

        if state == "PLAY" and start_time is None:
            draw_text(screen, "Move your hand DOWN inside the yellow box!", 36, OUTLINE, WINDOW_W // 2, 60)
        elif state == "DONE":
            draw_text(screen, "CUP IS FULL!", 64, WHITE, 800, 540)
            draw_text(screen, f"TIME  {final_time:.1f}s", 40, OUTLINE, 800, 592)
            draw_text(screen, f"BEST  {best:.1f}s", 40, OUTLINE, 800, 630)
            draw_text(screen, "SPACE = play again", 30, OUTLINE, 800, 670)

        pygame.display.flip()
        clock.tick(60)

    camera.stop()
    cap.release()
    hands.close()
    pygame.quit()


if __name__ == "__main__":
    main()
