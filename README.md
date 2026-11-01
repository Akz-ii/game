# 🎮 Motion Arcade - AI Physical Gaming Arena & Dual-Player System

> **Zero-Hardware Physical Gaming Arcade powered by MediaPipe AI & High-Performance HTML5 Canvas / Pygame**  
> Play with your physical body and hands using standard webcams. Supports **Solo**, **Same-Device 2-Player (Split-Screen)**, and **Cross-Device LAN Online Multiplayer**!

---

## 🌟 Featured Games Suite

1. **🍉 Fruit Slice Duel** (`slice_game.py` & Web Arcade)
   - High-precision sword slicing using raycasted trajectory arcs and sub-pixel adaptive filtering.
   - 1-Player reflex training and 2-Player simultaneous split-screen fruit cutting duel.

2. **🏹 Balloon Archer Duel** (`archery_game.py` & Web Arcade)
   - Real-time hand-tracked bow & arrow physics with laser aiming guides and dynamic tension draw mechanics.
   - Dual split arena with pop particle bursts and network arrow synchronization.

3. **🏀 Hoop Shots Basketball** (`hoop_shots.py` & Web Arcade)
   - Pick up basketballs by hovering your hand, flick/wave toward the hoop to shoot with realistic parabolic gravity and rim bounce physics.

4. **🥛 Milk the Cow** (`milk_the_cow.py` & Web Arcade)
   - Rapid-action hand pump mechanics. Squeeze and pull down on the cow udders to race to 100% full milk bucket!

5. **🎨 Wall Painter (Screen Rush)** (`wall_painter.py` & Web Arcade)
   - Territory coverage neon battle. Turn your hand into a paint roller and paint the screen before time runs out.

6. **🧺 Fruit Catch (Head Basket)** (`catch_game.py` & Web Arcade)
   - Uses AI Face Detection to anchor a collection basket right on top of your head! Move your body left and right to catch falling fruits while dodging bombs.

7. **🧘 Yoga Pose Master** (`yogagame.py` & Web Arcade)
   - Body skeleton tracking comparing your joint angles against reference yoga poses with real-time accuracy scoring.

8. **⚡ Anime Pose Challenge** (Web Arcade)
   - Strike iconic battle stances (Kamehameha, Naruto Run, JoJo Stand, Titan Salute) under countdown pressure!

---

## ⚡ Performance & Optimization Highlights

- **Locked 60 FPS**: Zero `shadowBlur` bottlenecks; utilizes GPU-accelerated alpha layered strokes.
- **Ultra-Fast AI Inference**: MediaPipe Lite models (`complexity: 0`) paired with 320x240 SIMD downsampling for sub-10ms latency.
- **Persistent Hungarian Tracking**: Dual-hand assignment algorithm prevents identity flips between Player 1 (Left) and Player 2 (Right).
- **Asynchronous Architecture**: Camera acquisition and neural network inference decoupled from the Pygame render loop on background daemon threads.

---

## 🚀 Quick Start

### 🌐 Option A: Web Arcade (Browser - No Python Required)

1. **Install dependencies**:
   ```bash
   npm install
   ```
2. **Start the server**:
   ```bash
   node server.js
   ```
3. Open your browser:
   - **Local Play**: `http://localhost:3000/`
   - **LAN Cross-Device Multiplayer**: Connect another laptop to `http://<your-ip>:3000/` (displayed in server console).

---

### 🐍 Option B: Standalone Python Games (Pygame + OpenCV)

1. **Install Python requirements**:
   ```bash
   pip install pygame opencv-python mediapipe numpy
   ```
2. **Run any game**:
   ```bash
   python archery_game.py
   python slice_game.py
   python downloaded_games/hoop_shots.py
   python downloaded_games/catch_game.py
   python downloaded_games/milk_the_cow.py
   python downloaded_games/yogagame.py
   python downloaded_games/wall_painter.py
   ```

---

## 👥 Multiplayer Controls

- **Same-Device 2-Player**:
  - Two players stand side-by-side in front of the webcam.
  - Player 1 controls the **Left (Cyan)** side.
  - Player 2 controls the **Right (Red)** side.
- **Cross-Device (2 Laptops)**:
  - **Host**: Click **"🌐 2 Laptops"** > **"Create Room"** > Copy link.
  - **Guest**: Open the link on the second laptop to instantly sync live blade positions, arrows, basketball throws, and scores over WebSockets.

---

## 📜 License
MIT License. Created by [Akz-ii](https://github.com/Akz-ii).
