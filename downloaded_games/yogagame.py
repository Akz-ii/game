"""
YOGA CHALLENGE  -  version 1
==================================

How a round works:
  0. On the menu you press RANDOM POSE, or click the pose you want to practice.
  1. The anime pose image is shown for a few seconds (memorize it!)
  2. The image disappears. The webcam turns on. 3-2-1 countdown.
  3. You perform the pose from memory. MediaPipe Pose tracks your body.
  4. Your body is compared with the TARGET SKELETON found in the reference photo.
  5. You get a score from 0-100 and a results screen.

The anime image is NEVER drawn while you are performing the pose.

Run it with:   python game.py
"""

import math
import os
import random
import time

import cv2
import mediapipe as mp
import numpy as np
import pygame

try:
    from PIL import Image, ImageSequence     # Pillow: needed to play the win/lose GIFs
except ImportError:
    Image = None


# =====================================================================
#  1. TARGET POSES  -  AUTOMATIC  (manual override is optional)
# =====================================================================
#
# You do NOT have to type any coordinates.
#
# Put photos of REAL PEOPLE doing the poses (for example cosplayers) in the
# "yogaposes" folder. When the game starts, MediaPipe finds the body in each photo
# and uses it as the target skeleton automatically.
#
# Good reference photos:
#   - ONE person, facing the camera (not from behind or sideways)
#   - the whole body visible if the pose uses the legs
#   - nothing blocking the body, clear lighting
#   - body parts that are cut off or hidden are simply ignored in the score
#
# OPTIONAL: if a picture can't be detected, or the detected skeleton looks
# wrong on the results screen, you can type the joints yourself below.
# An entry whose key is the image's file name OVERRIDES automatic detection
# for that image.
#
# Each point is (x, y) in PIXELS of the original image:
#     x = pixels from the LEFT edge,  y = pixels from the TOP edge.
# "left_..." means the LEFT side of the PICTURE as you look at it (mirror-style),
# "right_..." means the RIGHT side of the picture.

TARGET_POSES = {
    # "luffy.jpg": {
    #     "left_shoulder":  (0, 0),
    #     "right_shoulder": (0, 0),
    #     "left_elbow":     (0, 0),
    #     "right_elbow":    (0, 0),
    #     "left_wrist":     (0, 0),
    #     "right_wrist":    (0, 0),
    #     "left_hip":       (0, 0),
    #     "right_hip":      (0, 0),
    #     "left_knee":      (0, 0),
    #     "right_knee":     (0, 0),
    #     "left_ankle":     (0, 0),
    #     "right_ankle":    (0, 0),
    # },
}


# =====================================================================
#  2. SETTINGS  (safe to change)
# =====================================================================

POSES_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yogaposes")
                            # folder with your reference photos (next to game.py)
CAMERA_INDEX = 0            # 0 = default webcam. Try 1 if the wrong camera opens

MEMORIZE_SECONDS = 3        # how long the anime image is shown
COUNTDOWN_SECONDS = 3       # webcam countdown before the pose starts
HOLD_SECONDS = 5            # how long you have to perform the pose

# Result screen: the two GIFs live in a folder called "result" next to game.py
RESULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result")
WIN_SCORE = 60              # this score or higher -> WIN_GIF, lower -> LOSE_GIF
WIN_GIF = "won.gif"         # file names inside the result folder
LOSE_GIF = "fail.gif"

WINDOW_W, WINDOW_H = 1100, 720
CAM_DISPLAY_H = 480         # webcam picture height on screen (width follows the camera)
MIN_VISIBILITY = 0.5        # MediaPipe confidence needed to trust a body point (0-1)
MUSIC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.mp3")

# --- Scoring settings (make the game harder or easier here) ---
# An angle mistake of ANGLE_FREE degrees or less costs nothing.
# An angle mistake of ANGLE_ZERO degrees or more gives 0 points for that bone.
ANGLE_FREE = 8
ANGLE_ZERO = 45

# Same idea for joint positions (measured in "torso lengths").
POS_FREE = 0.08
POS_ZERO = 0.60

# How much each part counts towards the final score (they don't have to add to 1).
WEIGHTS = {
    "left_arm":  0.25,
    "right_arm": 0.25,
    "legs":      0.20,
    "torso":     0.10,   # shoulder line + hip line tilt
    "position":  0.20,   # overall body shape after normalizing size
}

# "Just standing there" protection:
# The game checks how well a person standing straight with arms down would score
# on the current pose. Body parts that such a person would ALREADY get right
# (for example straight legs) count for much less in the final score, so the
# score depends mostly on the parts of the pose that really are different.
# 0.15 = a part that matches plain standing still counts 15% as much as normal.
IMPORTANCE_FLOOR = 0.15

# Makes the score harsher. 1.0 = no change. Higher = harder
# (with 1.5 an 80% match becomes a score of about 72).
SHARPEN = 1.5

# Hold it! The score is the best AVERAGE over this many seconds, so one lucky
# frame doesn't count - you have to keep the pose for a moment.
SUSTAIN_SECONDS = 0.6

# Score ranges: (minimum score, text, color)
RATINGS = [
    (95, "PERFECT!",   (255, 215,   0)),
    (85, "GREAT!",     ( 80, 220, 100)),
    (70, "GOOD",       (100, 200, 255)),
    (50, "OK",         (255, 170,  60)),
    ( 0, "TRY AGAIN",  (255,  90,  90)),
]

# Colors
BG_COLOR = (25, 25, 35)
WHITE = (255, 255, 255)
GRAY = (160, 160, 170)
YELLOW = (255, 220, 80)
RED = (255, 90, 90)
PLAYER_COLOR = (60, 230, 120)
TARGET_COLOR = (255, 170, 60)


# =====================================================================
#  3. BODY DEFINITIONS
# =====================================================================

# Our joint names -> MediaPipe Pose landmark numbers
JOINT_IDS = {
    "left_shoulder": 11,  "right_shoulder": 12,
    "left_elbow":    13,  "right_elbow":    14,
    "left_wrist":    15,  "right_wrist":    16,
    "left_hip":      23,  "right_hip":      24,
    "left_knee":     25,  "right_knee":     26,
    "left_ankle":    27,  "right_ankle":    28,
}

# Lines drawn between joints to make a stick figure
BONES = [
    ("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"),
    ("left_shoulder", "left_hip"),       ("right_shoulder", "right_hip"),
    ("left_shoulder", "left_elbow"),     ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),   ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"),           ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),         ("right_knee", "right_ankle"),
]

# Which bones belong to which score group
LEFT_ARM = [("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist")]
RIGHT_ARM = [("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist")]
LEGS = [("left_hip", "left_knee"), ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"), ("right_knee", "right_ankle")]
TORSO = [("left_shoulder", "right_shoulder"), ("left_hip", "right_hip")]

TORSO_JOINTS = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]

# A person standing straight with arms hanging down (torso length = 1, hips in the
# middle, y grows downwards). Used to check what "just standing there" would score.
NEUTRAL_POSE = {
    "left_shoulder": (-0.40, -1.00),  "right_shoulder": (0.40, -1.00),
    "left_elbow":    (-0.48, -0.42),  "right_elbow":    (0.48, -0.42),
    "left_wrist":    (-0.56,  0.10),  "right_wrist":    (0.56,  0.10),
    "left_hip":      (-0.22,  0.00),  "right_hip":      (0.22,  0.00),
    "left_knee":     (-0.30,  0.90),  "right_knee":     (0.30,  0.90),
    "left_ankle":    (-0.38,  1.80),  "right_ankle":    (0.38,  1.80),
}


# =====================================================================
#  4. SCORING  (pure math, no graphics)
# =====================================================================

def direction_angle(a, b):
    """Angle (in degrees) of the line going from point a to point b."""
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def angle_difference(angle1, angle2):
    """Smallest difference between two angles, 0 to 180 degrees."""
    return abs((angle1 - angle2 + 180) % 360 - 180)


def linear_score(error, free, zero):
    """error <= free -> 1.0,  error >= zero -> 0.0,  straight line in between."""
    value = 1 - (error - free) / (zero - free)
    return max(0.0, min(1.0, value))


def middle(p, q):
    return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)


def normalize(pose):
    """
    Make a skeleton independent of body size and camera distance:
      - move it so the middle of the hips is at (0, 0)
      - divide by the torso length (hips-middle to shoulders-middle)
    Returns None if the shoulders/hips are not all known.
    """
    if any(name not in pose for name in TORSO_JOINTS):
        return None
    shoulders = middle(pose["left_shoulder"], pose["right_shoulder"])
    hips = middle(pose["left_hip"], pose["right_hip"])
    torso_length = math.dist(shoulders, hips)
    if torso_length < 1e-6:
        return None
    return {name: ((x - hips[0]) / torso_length, (y - hips[1]) / torso_length)
            for name, (x, y) in pose.items()}


def part_scores(target, player):
    """
    Compare a skeleton with the target, part by part.
    Returns raw scores from 0.0 to 1.0 (or None if the target doesn't use that part).
    """

    def bones_score(bones):
        """Compare the DIRECTION of each bone (e.g. shoulder -> elbow)."""
        scores = []
        for a, b in bones:
            if a not in target or b not in target:
                continue                    # target doesn't use this bone: ignore it
            if a not in player or b not in player:
                scores.append(0.0)          # we can't see the player's bone: 0 points
                continue
            error = angle_difference(direction_angle(target[a], target[b]),
                                     direction_angle(player[a], player[b]))
            scores.append(linear_score(error, ANGLE_FREE, ANGLE_ZERO))
        return sum(scores) / len(scores) if scores else None

    parts = {
        "left_arm":  bones_score(LEFT_ARM),
        "right_arm": bones_score(RIGHT_ARM),
        "legs":      bones_score(LEGS),
        "torso":     bones_score(TORSO),
        "position":  None,
    }

    # Overall body shape: compare normalized joint positions
    target_n = normalize(target)
    player_n = normalize(player)
    if target_n is not None:
        distances = []
        for name, point in target_n.items():
            if player_n is not None and name in player_n:
                distances.append(math.dist(point, player_n[name]))
            else:
                distances.append(POS_ZERO)  # joint not visible: worst score
        parts["position"] = linear_score(sum(distances) / len(distances),
                                         POS_FREE, POS_ZERO)
    return parts


def score_pose(target, player):
    """
    Compare the player's skeleton with the target skeleton.

    Both are dictionaries like {"left_elbow": (x, y), ...}.
    Returns {"overall": 0-100, "parts": {"left_arm": 0-100 or None, ...}}
    """
    parts = part_scores(target, player)

    # What would someone standing straight (arms down) score on this pose?
    standing = part_scores(target, NEUTRAL_POSE)

    # Weighted average. Parts that plain standing already gets right count less.
    total = 0.0
    weight_sum = 0.0
    for name, value in parts.items():
        if value is None:
            continue
        importance = max(IMPORTANCE_FLOOR, 1 - standing[name])
        weight = WEIGHTS[name] * importance
        total += weight * value
        weight_sum += weight
    raw = total / weight_sum if weight_sum > 0 else 0.0

    return {
        "overall": int(round(100 * raw ** SHARPEN)),
        "parts": {name: (None if v is None else int(round(100 * v ** SHARPEN)))
                  for name, v in parts.items()},
    }


def average_results(results):
    """Average several score_pose() results into one (used for the 'hold it' score)."""
    parts = {}
    for key in results[0]["parts"]:
        values = [r["parts"][key] for r in results if r["parts"][key] is not None]
        parts[key] = int(round(sum(values) / len(values))) if values else None
    overall = sum(r["overall"] for r in results) / len(results)
    return {"overall": int(round(overall)), "parts": parts}


def get_rating(score):
    """Returns (text, color) for a score."""
    for minimum, text, color in RATINGS:
        if score >= minimum:
            return text, color
    return RATINGS[-1][1], RATINGS[-1][2]


# =====================================================================
#  5. WEBCAM + MEDIAPIPE
# =====================================================================

def process_frame(frame, pose_detector):
    """
    Takes one OpenCV webcam frame.
    Returns:
      surface - a pygame picture of the webcam (mirrored, like a mirror)
      player  - dict of the player's joints in that mirrored picture
    """
    # Resize to a fixed height (keeps the camera's shape, so angles stay correct)
    h, w = frame.shape[:2]
    scale = CAM_DISPLAY_H / h
    frame = cv2.resize(frame, (int(w * scale), CAM_DISPLAY_H))
    h, w = frame.shape[:2]

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    small_rgb = cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LINEAR)
    results = pose_detector.process(small_rgb)

    player = {}
    if results.pose_landmarks:
        for name, index in JOINT_IDS.items():
            landmark = results.pose_landmarks.landmark[index]
            if landmark.visibility >= MIN_VISIBILITY:
                # (1 - x) mirrors the point so it matches the mirrored picture
                player[name] = ((1 - landmark.x) * w, landmark.y * h)

    mirrored = cv2.flip(rgb, 1)
    surface = pygame.image.frombuffer(mirrored.tobytes(), (w, h), "RGB")
    return surface, player


# =====================================================================
#  6. DRAWING HELPERS
# =====================================================================

_font_cache = {}


def get_font(size):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def draw_text(screen, text, size, color, x, y, align="center", shadow=False):
    """Draw text. (x, y) is the middle / left / right of the text, see 'align'."""
    image = get_font(size).render(text, True, color)
    rect = image.get_rect()
    if align == "center":
        rect.center = (x, y)
    elif align == "left":
        rect.midleft = (x, y)
    else:
        rect.midright = (x, y)
    if shadow:
        dark = get_font(size).render(text, True, (0, 0, 0))
        screen.blit(dark, rect.move(3, 3))
    screen.blit(image, rect)


def draw_skeleton(screen, points, color):
    """Draw a stick figure. points = {"left_elbow": (x, y), ...} in screen pixels."""
    for a, b in BONES:
        if a in points and b in points:
            pygame.draw.line(screen, color, points[a], points[b], 6)
    for x, y in points.values():
        pygame.draw.circle(screen, color, (int(x), int(y)), 8)


def scale_to_fit(image, max_w, max_h):
    w, h = image.get_size()
    s = min(max_w / w, max_h / h)
    return pygame.transform.smoothscale(image, (max(1, int(w * s)), max(1, int(h * s))))


def find_result_gif(filename):
    """Find e.g. won.gif inside the result folder (ignores capital letters and spaces)."""
    if not os.path.isdir(RESULT_FOLDER):
        return None
    wanted = filename.lower().replace(" ", "")
    for f in os.listdir(RESULT_FOLDER):
        if f.lower().replace(" ", "") == wanted:
            return os.path.join(RESULT_FOLDER, f)
    return None


def load_gif(filename, max_w, max_h):
    """
    Load an animated GIF from the result folder.
    Returns {"frames": [...], "durations": [...], "total": ms} or None if it can't be loaded.
    """
    path = find_result_gif(filename)
    if path is None:
        note("gif", f"{filename} not found in the 'result' folder")
        return None
    if Image is None:
        note("gif", "Pillow is not installed - run: pip install pillow")
        return None
    try:
        frames, durations = [], []
        with Image.open(path) as gif:
            for frame in ImageSequence.Iterator(gif):
                duration = frame.info.get("duration", 100)
                if duration <= 10:
                    duration = 100                    # browsers do the same for 0-10 ms
                rgba = frame.convert("RGBA")
                surface = pygame.image.frombuffer(rgba.tobytes(), rgba.size, "RGBA")
                frames.append(scale_to_fit(surface.convert_alpha(), max_w, max_h))
                durations.append(duration)
        return {"frames": frames, "durations": durations, "total": sum(durations)}
    except Exception as error:
        note("gif", f"{filename} could not be loaded: {error}")
        return None


def gif_frame(gif, seconds):
    """Which picture of the animated GIF to show after 'seconds' (it loops forever)."""
    t = int(seconds * 1000) % gif["total"]
    for surface, duration in zip(gif["frames"], gif["durations"]):
        if t < duration:
            return surface
        t -= duration
    return gif["frames"][-1]


# =====================================================================
#  7. LOADING POSES AND STARTING ROUNDS
# =====================================================================

LOAD_NOTES = []      # problems found while loading pictures (shown on the title screen)


def note(kind, text):
    """Print a message in the terminal and remember it for the title screen."""
    print(f"[{kind}] {text}")
    LOAD_NOTES.append(f"{text}")


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp")


# ---- Automatic detection settings ----
SAVE_PREVIEWS = True        # save pictures showing the detected skeleton (see below)
PREVIEW_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "detection_previews")

# Parts of the picture we try, in order:  (left, top, right, bottom, border)
# All numbers are fractions of the picture. "border" adds empty space around the
# part, which helps when the body touches the edge of the picture.
# The first two use the whole picture. The others look at parts of it, which
# helps with group photos and small figures.
DETECTION_ATTEMPTS = [
    (0.0, 0.0, 1.0, 1.0, 0.0),   # whole picture
    (0.0, 0.0, 1.0, 1.0, 0.3),   # whole picture + extra border
    (0.0, 0.0, 0.6, 1.0, 0.1),   # left part
    (0.4, 0.0, 1.0, 1.0, 0.1),   # right part
    (0.2, 0.0, 0.8, 1.0, 0.1),   # middle part
]


def read_picture(path):
    """Read a picture with OpenCV. Works with file names in any language on Windows."""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def looks_like_a_body(target):
    """Simple sanity check so we don't accept nonsense skeletons."""
    if any(name not in target for name in TORSO_JOINTS):
        return False
    shoulders = middle(target["left_shoulder"], target["right_shoulder"])
    hips = middle(target["left_hip"], target["right_hip"])
    torso_length = math.dist(shoulders, hips)
    shoulder_width = abs(target["left_shoulder"][0] - target["right_shoulder"][0])
    return (torso_length > 1
            and hips[1] > shoulders[1]                 # hips below shoulders
            and shoulder_width > 0.15 * torso_length)  # not squashed flat


def detect_target_from_image(image_bgr, detector):
    """
    Find a person in a picture with MediaPipe.
    Returns (target, used_part_of_picture), or (None, False) if nobody was found.
    'target' has the same format as a TARGET_POSES entry, in ORIGINAL picture pixels.
    """
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    full_h, full_w = rgb.shape[:2]

    best, best_quality = None, 0.0
    for number, (left, top, right, bottom, border) in enumerate(DETECTION_ATTEMPTS):
        x0, y0 = int(left * full_w), int(top * full_h)
        x1, y1 = int(right * full_w), int(bottom * full_h)
        crop = rgb[y0:y1, x0:x1]
        pad = int(border * max(crop.shape[:2]))
        if pad > 0:
            crop = cv2.copyMakeBorder(crop, pad, pad, pad, pad,
                                      cv2.BORDER_CONSTANT, value=(128, 128, 128))
        crop = np.ascontiguousarray(crop)
        h, w = crop.shape[:2]

        results = detector.process(crop)
        if not results.pose_landmarks:
            continue

        target, quality = {}, 0.0
        for name, index in JOINT_IDS.items():
            landmark = results.pose_landmarks.landmark[index]
            if landmark.visibility >= MIN_VISIBILITY:
                # MediaPipe names joints by the person's OWN left/right. A person
                # facing the camera has their own left on the RIGHT of the picture.
                # Our game names joints by the side of the PICTURE, so we swap.
                if name.startswith("left_"):
                    picture_name = "right_" + name[5:]
                else:
                    picture_name = "left_" + name[6:]
                # convert back to pixel positions in the ORIGINAL picture
                target[picture_name] = (x0 + landmark.x * w - pad,
                                        y0 + landmark.y * h - pad)
                quality += landmark.visibility

        if not looks_like_a_body(target):
            continue
        if number < 2:
            return target, False            # found on the whole picture: use it
        if quality > best_quality:
            best, best_quality = target, quality

    return best, best is not None


def save_preview(filename, image_bgr, target):
    """Save a copy of the picture with the skeleton drawn on it (to check it by eye)."""
    try:
        preview = image_bgr.copy()
        size = max(2, max(preview.shape[:2]) // 200)
        for a, b in BONES:
            if a in target and b in target:
                cv2.line(preview, (int(target[a][0]), int(target[a][1])),
                         (int(target[b][0]), int(target[b][1])), (0, 255, 0), size)
        for name, (x, y) in target.items():
            # blue dots = LEFT side of the picture, red dots = RIGHT side
            color = (255, 100, 0) if name.startswith("left_") else (0, 0, 255)
            cv2.circle(preview, (int(x), int(y)), size * 2, color, -1)
        os.makedirs(PREVIEW_FOLDER, exist_ok=True)
        out_path = os.path.join(PREVIEW_FOLDER, os.path.splitext(filename)[0] + ".png")
        ok, buffer = cv2.imencode(".png", preview)
        if ok:
            buffer.tofile(out_path)
    except Exception as error:          # a preview problem must never stop the game
        print(f"[preview] could not save preview for {filename}: {error}")


def load_poses():
    """Load every image in the yogaposes folder and get its target skeleton."""
    poses = []
    LOAD_NOTES.clear()

    if not os.path.isdir(POSES_FOLDER):
        note("error", f"The folder '{POSES_FOLDER}' does not exist.")
        return poses

    files = []
    for f in sorted(os.listdir(POSES_FOLDER)):
        if f.lower().endswith(IMAGE_EXTENSIONS):
            files.append(f)
        elif f.lower() not in ("desktop.ini", "thumbs.db") and not f.startswith("."):
            note("ignored", f"{f}: not a supported picture file "
                 f"(use {', '.join(IMAGE_EXTENSIONS)}; sub-folders are not searched)")

    # A separate MediaPipe detector for still photos (only used while loading)
    detector = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1,
                                      min_detection_confidence=0.3)

    for filename in files:
        path = os.path.join(POSES_FOLDER, filename)

        image_bgr = read_picture(path)
        if image_bgr is None:
            note("skipped", f"{filename}: the file could not be read")
            continue

        if filename in TARGET_POSES:
            target = TARGET_POSES[filename]
            source = "manual"
        else:
            target, partial = detect_target_from_image(image_bgr, detector)
            source = "auto"
            if target is None:
                note("skipped", f"{filename}: no person found")
                continue
            if partial:
                source = "auto, found in PART of the picture - check its preview"

        unknown = [name for name in target if name not in JOINT_IDS]
        if unknown:
            note("skipped", f"{filename}: unknown joint name(s): {unknown}")
            continue

        missing_torso = [name for name in TORSO_JOINTS if name not in target]
        if missing_torso:
            note("skipped", f"{filename}: torso not fully visible (need both shoulders and hips)")
            continue

        if SAVE_PREVIEWS:
            save_preview(filename, image_bgr, target)

        image = pygame.image.load(path).convert_alpha()
        poses.append({"name": filename, "image": image, "target": target})
        print(f"[loaded] {filename} ({source}: {len(target)} of 12 joints)")

    detector.close()

    print(f"--> {len(poses)} of {len(files)} pictures loaded.")
    if SAVE_PREVIEWS and poses:
        print(f"    Previews of the detected skeletons are in: {PREVIEW_FOLDER}")
    for filename in TARGET_POSES:
        if filename not in files:
            print(f"[note] TARGET_POSES has '{filename}' but that file is not in the yogaposes folder.")
    return poses


def new_round(poses, last_name, chosen=None):
    """
    Start a round.
    chosen = a pose picked from the menu, or None for RANDOM mode
    (random mode never picks the same pose twice in a row if there is a choice).
    """
    if chosen is not None:
        pose = chosen
    else:
        choices = [p for p in poses if p["name"] != last_name] or poses
        pose = random.choice(choices)
    return {
        "pose": pose,
        "image_big": scale_to_fit(pose["image"], 640, 470),      # memorize screen
        "image_result": scale_to_fit(pose["image"], 480, 340),   # result screen
        "recent": [],          # (time, score) of the last moments, for the "hold it" score
        "best": None,          # best score result during the attempt
        "best_photo": None,    # webcam photo taken at that best moment
        "photo_result": None,  # that photo, resized for the result screen
        "result_gif": None,    # win or lose GIF chosen for the result screen
        "live_score": 0,
    }


# =====================================================================
#  8. SCREENS
# =====================================================================

# Menu layout: a RANDOM button, and below it a grid of clickable pose thumbnails
THUMB = 150                  # thumbnail size in pixels
GRID_COLS = 6                # thumbnails per row
GRID_ROWS = 2                # rows visible at once (scroll with the mouse wheel)
GRID_GAP = 20
GRID_LEFT = (WINDOW_W - (GRID_COLS * THUMB + (GRID_COLS - 1) * GRID_GAP)) // 2
GRID_TOP = 215
GRID_ROW_HEIGHT = 205


def menu_layout(count, scroll_row):
    """
    Where everything on the menu is. Used for drawing AND for mouse clicks,
    so what you see is always what you click.
    Returns (random_button_rect, [(pose_number, thumbnail_rect), ...]).
    """
    random_rect = pygame.Rect(0, 0, 420, 66)
    random_rect.center = (WINDOW_W // 2, 135)

    cells = []
    first = scroll_row * GRID_COLS
    for slot in range(GRID_COLS * GRID_ROWS):
        number = first + slot
        if number >= count:
            break
        row, col = divmod(slot, GRID_COLS)
        rect = pygame.Rect(GRID_LEFT + col * (THUMB + GRID_GAP),
                           GRID_TOP + row * GRID_ROW_HEIGHT, THUMB, THUMB)
        cells.append((number, rect))
    return random_rect, cells


def draw_menu_screen(screen, poses, scroll_row, mouse_pos):
    draw_text(screen, "YOGA CHALLENGE", 72, YELLOW, WINDOW_W // 2, 42)
    draw_text(screen, "Memorize the pose - it disappears - then perform it from memory!",
              28, GRAY, WINDOW_W // 2, 80)

    random_rect, cells = menu_layout(len(poses), scroll_row)

    # Random mode button
    hovering = random_rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, (255, 205, 50) if hovering else (230, 170, 30),
                     random_rect, border_radius=14)
    draw_text(screen, "RANDOM POSE", 46, (30, 30, 40), random_rect.centerx, random_rect.centery)

    # Choose a specific pose
    draw_text(screen, "...or click a pose to practice it:", 30, GRAY, WINDOW_W // 2, 192)
    for number, rect in cells:
        pose = poses[number]
        hovering = rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, WHITE, rect, border_radius=8)
        thumb = pose["thumb"]
        screen.blit(thumb, thumb.get_rect(center=rect.center))
        if hovering:
            pygame.draw.rect(screen, YELLOW, rect.inflate(10, 10), 4, border_radius=10)
        draw_text(screen, pose["label"], 24, WHITE if hovering else GRAY,
                  rect.centerx, rect.bottom + 20)

    total_rows = math.ceil(len(poses) / GRID_COLS)
    if total_rows > GRID_ROWS:
        last = min(len(poses), (scroll_row + GRID_ROWS) * GRID_COLS)
        draw_text(screen, f"Mouse wheel = more poses   (showing {scroll_row * GRID_COLS + 1}-{last} of {len(poses)})",
                  24, GRAY, WINDOW_W // 2, 622)

    # Pictures that could not be loaded (details are also printed in the terminal)
    if LOAD_NOTES:
        text = LOAD_NOTES[0]
        draw_text(screen, text if len(text) <= 100 else text[:97] + "...",
                  22, RED, WINDOW_W // 2, 655)
        if len(LOAD_NOTES) > 1:
            draw_text(screen, f"...and {len(LOAD_NOTES) - 1} more problem(s) (see the terminal window)",
                      22, RED, WINDOW_W // 2, 679)

    draw_text(screen, "Stand back so the camera sees your whole body   |   SPACE = random pose   |   ESC = quit",
              24, GRAY, WINDOW_W // 2, 705)


def draw_memorize_screen(screen, rnd, remaining):
    draw_text(screen, "YOGA CHALLENGE", 36, GRAY, WINDOW_W // 2, 22)
    draw_text(screen, "MEMORIZE THIS POSE!", 64, YELLOW, WINDOW_W // 2, 80)
    image = rnd["image_big"]
    rect = image.get_rect(center=(WINDOW_W // 2, 375))
    pygame.draw.rect(screen, WHITE, rect.inflate(16, 16))   # white backing
    screen.blit(image, rect)
    draw_text(screen, f"{remaining:.1f}s", 56, WHITE, WINDOW_W // 2, 680)


def draw_camera_screen(screen, rnd, state, elapsed, cam_surface, player):
    """Used for both COUNTDOWN and PERFORM. The anime image is NOT drawn here."""
    draw_text(screen, "YOGA CHALLENGE", 36, GRAY, WINDOW_W // 2, 22)

    if cam_surface is None:
        draw_text(screen, "Waiting for webcam...", 48, WHITE, WINDOW_W // 2, 360)
        return

    cam_w, cam_h = cam_surface.get_size()
    cam_x = (WINDOW_W - cam_w) // 2
    cam_y = 135
    screen.blit(cam_surface, (cam_x, cam_y))

    # Player's skeleton drawn on top of the webcam
    shifted = {name: (x + cam_x, y + cam_y) for name, (x, y) in player.items()}
    draw_skeleton(screen, shifted, PLAYER_COLOR)

    # Warning if some body parts needed for this pose can't be seen
    target = rnd["pose"]["target"]
    if any(name not in player for name in target):
        draw_text(screen, "I can't see your whole body - step back!",
                  36, RED, WINDOW_W // 2, cam_y + cam_h - 30, shadow=True)

    if state == "COUNTDOWN":
        remaining = COUNTDOWN_SECONDS - elapsed
        draw_text(screen, "GET READY", 64, YELLOW, WINDOW_W // 2, 85)
        draw_text(screen, str(max(1, math.ceil(remaining))), 300, WHITE,
                  WINDOW_W // 2, cam_y + cam_h // 2, shadow=True)
        draw_text(screen, "The pose is hidden now - remember it!",
                  44, WHITE, WINDOW_W // 2, 660)
    else:
        remaining = max(0.0, HOLD_SECONDS - elapsed)
        _, color = get_rating(rnd["live_score"])
        draw_text(screen, str(rnd["live_score"]), 100, color, WINDOW_W // 2, 85)
        draw_text(screen, "HOLD YOUR POSE", 52, WHITE, WINDOW_W // 2, 648)
        draw_text(screen, f"{remaining:.1f}s", 44, YELLOW, WINDOW_W // 2, 692)


def draw_result_screen(screen, rnd, elapsed):
    result = rnd["best"]
    score = result["overall"]
    rating_text, rating_color = get_rating(score)

    # --- Top band:  score  |  win/lose GIF  |  rating ---
    draw_text(screen, f"{score} / 100", 96, rating_color, 250, 90)
    draw_text(screen, rating_text, 64, rating_color, 850, 90)
    if rnd["result_gif"] is not None:
        frame = gif_frame(rnd["result_gif"], elapsed)
        screen.blit(frame, frame.get_rect(center=(WINDOW_W // 2, 90)))

    # --- Two panels: the anime reference and YOUR PHOTO from the best moment ---
    panel_y = 185
    left_panel = pygame.Rect(50, panel_y, 480, 340)
    right_panel = pygame.Rect(570, panel_y, 480, 340)
    pygame.draw.rect(screen, WHITE, left_panel, border_radius=10)
    pygame.draw.rect(screen, (45, 45, 60), right_panel, border_radius=10)

    reference = rnd["image_result"]
    screen.blit(reference, reference.get_rect(center=left_panel.center))

    photo = rnd["photo_result"]
    if photo is not None:
        screen.blit(photo, photo.get_rect(center=right_panel.center))
    else:
        draw_text(screen, "No photo", 40, GRAY, right_panel.centerx, right_panel.centery)

    draw_text(screen, "ANIME REFERENCE", 32, GRAY, left_panel.centerx, panel_y + 360)
    draw_text(screen, "YOUR POSE", 32, GRAY, right_panel.centerx, panel_y + 360)

    # --- Score breakdown in one row ---
    names = [("left_arm", "Left arm"), ("right_arm", "Right arm"),
             ("legs", "Legs"), ("torso", "Shoulders & hips")]
    shown = [(label, result["parts"][key]) for key, label in names
             if result["parts"][key] is not None]           # skip parts this pose doesn't use
    for i, (label, value) in enumerate(shown):
        center_x = int((i + 0.5) * WINDOW_W / len(shown))
        draw_text(screen, label, 30, GRAY, center_x, 592)
        draw_text(screen, f"{value}%", 52, YELLOW, center_x, 630)

    draw_text(screen, "SPACE = play again    ESC = menu", 28, GRAY, WINDOW_W // 2, 695)


# =====================================================================
#  9. MAIN GAME LOOP
# =====================================================================

def start_background_music():
    """Start the looped background track from the project root."""
    if not os.path.exists(MUSIC_FILE):
        print(f"[music] '{MUSIC_FILE}' not found; skipping background music.")
        return
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(MUSIC_FILE)
        pygame.mixer.music.set_volume(0.55)
        pygame.mixer.music.play(-1)
    except Exception as exc:
        print(f"[music] Could not play '{MUSIC_FILE}': {exc}")


def main():
    pygame.init()
    start_background_music()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Yoga Challenge")
    clock = pygame.time.Clock()

    poses = load_poses()
    if not poses:
        print()
        print("No poses could be loaded.")
        print(f"Put photos of a person doing each pose in: {POSES_FOLDER}")
        print("(one person, facing the camera, body visible). Then run the game again.")
        pygame.quit()
        return

    # Small picture + short name for each pose (used by the menu)
    for number, pose in enumerate(poses, start=1):
        pose["thumb"] = scale_to_fit(pose["image"], THUMB, THUMB)
        stem = os.path.splitext(pose["name"])[0]
        pose["label"] = (stem if stem.isascii() else f"Pose {number}")[:17]

    # Win / lose animations for the result screen (loaded once)
    gifs = {"win": load_gif(WIN_GIF, 240, 160),
            "lose": load_gif(LOSE_GIF, 240, 160)}

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("Could not open the webcam. Is another program using it?")
        print("You can also try CAMERA_INDEX = 1 in the settings.")
        pygame.quit()
        return

    pose_detector = mp.solutions.pose.Pose(
        model_complexity=0,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    )

    state = "MENU"           # MENU -> MEMORIZE -> COUNTDOWN -> PERFORM -> RESULT
    state_start = time.time()
    rnd = None               # data for the current round
    last_name = None
    chosen = None            # None = RANDOM mode, otherwise the pose picked in the menu
    scroll_row = 0           # how far the menu grid is scrolled
    max_scroll = max(0, math.ceil(len(poses) / GRID_COLS) - GRID_ROWS)
    running = True

    while running:
        # ---------- keyboard / mouse / window events ----------
        start_now = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == "MENU":
                        running = False                  # ESC on the menu quits
                    else:
                        state = "MENU"                   # ESC anywhere else = back to menu
                        state_start = time.time()
                elif event.key == pygame.K_SPACE and state in ("MENU", "RESULT"):
                    if state == "MENU":
                        chosen = None                    # SPACE on the menu = random pose
                    start_now = True                     # on the result screen = play again

            elif event.type == pygame.MOUSEWHEEL and state == "MENU":
                scroll_row = max(0, min(max_scroll, scroll_row - event.y))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and state == "MENU":
                random_rect, cells = menu_layout(len(poses), scroll_row)
                if random_rect.collidepoint(event.pos):
                    chosen = None                        # random mode
                    start_now = True
                for number, rect in cells:
                    if rect.collidepoint(event.pos):
                        chosen = poses[number]           # this specific pose
                        start_now = True

        if start_now:
            rnd = new_round(poses, last_name, chosen)
            last_name = rnd["pose"]["name"]
            state = "MEMORIZE"
            state_start = time.time()

        # ---------- webcam ----------
        # We read a frame every loop so the camera never falls behind,
        # but we only USE it during COUNTDOWN and PERFORM.
        ok, frame = cap.read()
        cam_surface, player = None, {}
        if ok and state in ("COUNTDOWN", "PERFORM"):
            cam_surface, player = process_frame(frame, pose_detector)

        elapsed = time.time() - state_start
        screen.fill(BG_COLOR)

        # ---------- what happens in each state ----------
        if state == "MENU":
            draw_menu_screen(screen, poses, scroll_row, pygame.mouse.get_pos())

        elif state == "MEMORIZE":
            draw_memorize_screen(screen, rnd, max(0.0, MEMORIZE_SECONDS - elapsed))
            if elapsed >= MEMORIZE_SECONDS:
                state = "COUNTDOWN"          # the image is gone from now on
                state_start = time.time()

        elif state == "COUNTDOWN":
            draw_camera_screen(screen, rnd, state, elapsed, cam_surface, player)
            if elapsed >= COUNTDOWN_SECONDS:
                state = "PERFORM"
                state_start = time.time()

        elif state == "PERFORM":
            # Score this frame, then average the last SUSTAIN_SECONDS.
            # The average is what counts, so you have to HOLD the pose.
            now = time.time()
            rnd["recent"].append((now, score_pose(rnd["pose"]["target"], player)))
            rnd["recent"] = [(t, r) for t, r in rnd["recent"] if now - t <= SUSTAIN_SECONDS]
            held = average_results([r for _, r in rnd["recent"]])
            rnd["live_score"] = held["overall"]

            # Keep the BEST held moment as the final score, and take a photo of the webcam then.
            held_long_enough = now - rnd["recent"][0][0] >= SUSTAIN_SECONDS * 0.8
            if held_long_enough and (rnd["best"] is None or held["overall"] > rnd["best"]["overall"]):
                rnd["best"] = held
                if cam_surface is not None:
                    rnd["best_photo"] = cam_surface.copy()

            draw_camera_screen(screen, rnd, state, elapsed, cam_surface, player)

            if elapsed >= HOLD_SECONDS:
                if rnd["best"] is None:
                    rnd["best"] = held
                if rnd["best_photo"] is not None:
                    rnd["photo_result"] = scale_to_fit(rnd["best_photo"], 480, 340)
                won = rnd["best"]["overall"] >= WIN_SCORE
                rnd["result_gif"] = gifs["win"] if won else gifs["lose"]
                state = "RESULT"
                state_start = time.time()

        elif state == "RESULT":
            draw_result_screen(screen, rnd, elapsed)

        pygame.display.flip()
        clock.tick(60)

    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.quit()
    cap.release()
    pose_detector.close()
    pygame.quit()


if __name__ == "__main__":
    main()
