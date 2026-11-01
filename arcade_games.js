/**
 * ARCADE GAMES SUITE: BASKETBALL, COW MILKING, WALL PAINTER, HEAD FRUIT CATCH, YOGA & ANIME POSES
 * Modular Physical Motion Games for Blade Arena (Solo, 1-Device Dual, and 2-Device Online)
 */

// =====================================================================
//  1. HOOP SHOTS BASKETBALL
// =====================================================================

export class Basketball {
  constructor(id, x, y, owner = 'shared') {
    this.id = id;
    this.x = x;
    this.y = y;
    this.vx = 0;
    this.vy = 0;
    this.radius = 28;
    this.state = 'floor'; // 'floor', 'held', 'flying', 'scored'
    this.holder = null;   // 'p1' or 'p2'
    this.pickupProgress = 0;
    this.owner = owner;
    this.angle = 0;
    this.spin = 0;
    this.trail = [];
    this.scoredCooldown = 0;
  }

  update(dt, floorY, hoops) {
    if (this.state === 'flying' || this.state === 'scored') {
      this.vy += 1500 * dt; // Gravity
      this.x += this.vx * dt;
      this.y += this.vy * dt;
      this.angle += (this.vx * 0.05 + this.spin) * dt;

      // Floor bounce
      if (this.y + this.radius >= floorY) {
        this.y = floorY - this.radius;
        this.vy = -this.vy * 0.62;
        this.vx *= 0.85;
        if (Math.abs(this.vy) < 50) {
          this.vy = 0;
          this.state = 'floor';
          this.holder = null;
        }
      }

      // Wall bounds
      if (this.x - this.radius < 20) {
        this.x = 20 + this.radius;
        this.vx = -this.vx * 0.6;
      } else if (this.x + this.radius > window.innerWidth - 20) {
        this.x = window.innerWidth - 20 - this.radius;
        this.vx = -this.vx * 0.6;
      }

      // Trail
      this.trail.push({ x: this.x, y: this.y, alpha: 0.6 });
      if (this.trail.length > 8) this.trail.shift();
      this.trail.forEach(t => t.alpha *= 0.88);

      // Backboard & rim collisions for each active hoop
      for (const hoop of hoops) {
        // Backboard
        const bx = hoop.facingRight ? hoop.boardX : hoop.boardX;
        const distBoard = Math.abs(this.x - bx);
        if (distBoard < this.radius + 12 && this.y >= hoop.boardTop && this.y <= hoop.boardBottom) {
          this.vx = (hoop.facingRight ? 1 : -1) * Math.abs(this.vx) * 0.65 + (hoop.facingRight ? 80 : -80);
          this.spin = (Math.random() - 0.5) * 6;
        }

        // Rim front tip bounce
        const tipDist = Math.hypot(this.x - hoop.rimTipX, this.y - hoop.rimY);
        if (tipDist < this.radius + 8) {
          const nx = (this.x - hoop.rimTipX) / (tipDist || 1);
          const ny = (this.y - hoop.rimY) / (tipDist || 1);
          const dot = this.vx * nx + this.vy * ny;
          if (dot < 0) {
            this.vx -= 1.6 * dot * nx;
            this.vy -= 1.6 * dot * ny;
          }
        }

        // Basket score detection (passing downwards through the rim opening)
        if (this.state === 'flying' && this.vy > 0 && this.scoredCooldown <= 0) {
          const inX = hoop.facingRight ? (this.x >= hoop.rimTipX && this.x <= hoop.boardX) : (this.x >= hoop.boardX && this.x <= hoop.rimTipX);
          if (inX && Math.abs(this.y - hoop.rimY) < 26) {
            this.state = 'scored';
            this.scoredCooldown = 1.0;
            hoop.swishTime = 0.55;
            return { scored: true, hoopOwner: hoop.owner, points: Math.abs(this.x - hoop.boardX) > 400 ? 3 : 2 };
          }
        }
      }
    }

    if (this.scoredCooldown > 0) this.scoredCooldown -= dt;
    return null;
  }

  draw(ctx) {
    ctx.save();
    // Trail
    for (const t of this.trail) {
      ctx.fillStyle = `rgba(240, 120, 32, ${t.alpha * 0.4})`;
      ctx.beginPath();
      ctx.arc(t.x, t.y, this.radius * 0.8, 0, Math.PI * 2);
      ctx.fill();
    }

    // Shadow on floor
    const floorY = window.innerHeight - 60;
    const shadowDist = Math.max(0, floorY - this.y);
    const shadowAlpha = Math.max(0.1, 0.5 - shadowDist / 600);
    const shadowW = Math.max(10, this.radius * (1 - shadowDist / 800));
    ctx.fillStyle = `rgba(0, 0, 0, ${shadowAlpha})`;
    ctx.beginPath();
    ctx.ellipse(this.x, floorY + 4, shadowW * 1.3, shadowW * 0.4, 0, 0, Math.PI * 2);
    ctx.fill();

    // Basketball body with 3D gradient
    ctx.translate(this.x, this.y);
    ctx.rotate(this.angle);

    const grad = ctx.createRadialGradient(-this.radius * 0.35, -this.radius * 0.35, this.radius * 0.1, 0, 0, this.radius);
    grad.addColorStop(0, '#ff9642');
    grad.addColorStop(0.65, '#e86018');
    grad.addColorStop(1, '#9e3408');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
    ctx.fill();

    // Basketball black seams
    ctx.strokeStyle = 'rgba(25, 12, 6, 0.85)';
    ctx.lineWidth = 2.5;

    // Cross seams
    ctx.beginPath();
    ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(-this.radius, 0);
    ctx.lineTo(this.radius, 0);
    ctx.moveTo(0, -this.radius);
    ctx.lineTo(0, this.radius);
    ctx.stroke();

    // Curved ribs
    ctx.beginPath();
    ctx.ellipse(0, 0, this.radius * 0.6, this.radius, 0, 0, Math.PI * 2);
    ctx.stroke();

    // Highlight sheen
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.beginPath();
    ctx.ellipse(-this.radius * 0.38, -this.radius * 0.38, this.radius * 0.3, this.radius * 0.18, -Math.PI / 4, 0, Math.PI * 2);
    ctx.fill();

    // Pickup progress ring
    if (this.state === 'floor' && this.pickupProgress > 0) {
      ctx.rotate(-this.angle); // Keep ring upright
      ctx.strokeStyle = '#ffd028';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(0, 0, this.radius + 12, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * this.pickupProgress);
      ctx.stroke();
    }

    ctx.restore();
  }
}

export class HoopGame {
  constructor(arena) {
    this.arena = arena;
    this.balls = [];
    this.hoops = [];
    this.particles = [];
    this.floaters = [];
    this.floorY = window.innerHeight - 60;
    this.timeLimit = 60;
    this.timeLeft = 60;
    this.scores = { p1: 0, p2: 0 };
    this.reset();
  }

  reset() {
    this.floorY = window.innerHeight - 60;
    this.balls = [];
    this.hoops = [];
    this.particles = [];
    this.floaters = [];
    this.timeLeft = this.timeLimit;
    this.scores = { p1: 0, p2: 0 };

    const isLocalDual = this.arena.playMode === 'local';

    if (isLocalDual) {
      // P1 Hoop (Left side, facing right)
      this.hoops.push({
        owner: 'p1',
        color: '#00f0ff',
        boardX: window.innerWidth * 0.12,
        boardTop: window.innerHeight * 0.22,
        boardBottom: window.innerHeight * 0.46,
        rimY: window.innerHeight * 0.42,
        rimTipX: window.innerWidth * 0.24,
        facingRight: true,
        swishTime: 0
      });

      // P2 Hoop (Right side, facing left)
      this.hoops.push({
        owner: 'p2',
        color: '#ff3366',
        boardX: window.innerWidth * 0.88,
        boardTop: window.innerHeight * 0.22,
        boardBottom: window.innerHeight * 0.46,
        rimY: window.innerHeight * 0.42,
        rimTipX: window.innerWidth * 0.76,
        facingRight: false,
        swishTime: 0
      });

      // 3 balls for P1, 3 balls for P2
      for (let i = 0; i < 3; i++) {
        const b1 = new Basketball(`p1_${i}`, window.innerWidth * 0.28 + i * 55, this.floorY - 28, 'p1');
        this.balls.push(b1);
        const b2 = new Basketball(`p2_${i}`, window.innerWidth * 0.58 + i * 55, this.floorY - 28, 'p2');
        this.balls.push(b2);
      }
    } else {
      // Solo or Online Shared Hoop on Right
      this.hoops.push({
        owner: 'shared',
        color: '#ffd028',
        boardX: window.innerWidth * 0.86,
        boardTop: window.innerHeight * 0.20,
        boardBottom: window.innerHeight * 0.45,
        rimY: window.innerHeight * 0.41,
        rimTipX: window.innerWidth * 0.72,
        facingRight: false,
        swishTime: 0
      });

      for (let i = 0; i < 4; i++) {
        const b = new Basketball(`ball_${i}`, window.innerWidth * 0.18 + i * 75, this.floorY - 28, 'shared');
        this.balls.push(b);
      }
    }
  }

  update(now, dt) {
    if (this.arena.state === 'PLAY' && this.timeLeft > 0) {
      this.timeLeft = Math.max(0, this.timeLeft - dt);
      if (this.timeLeft === 0) {
        this.arena.state = 'GAMEOVER';
        this.arena.showResults();
      }
    }

    // Hoop swish animations
    for (const h of this.hoops) {
      if (h.swishTime > 0) h.swishTime -= dt;
    }

    // Hand interactions (Pick up & Wave Throw)
    const players = [
      { role: 'p1', pos: this.arena.p1Point, spd: this.arena.p1Speed, dir: this.arena.p1FingerDir },
      { role: 'p2', pos: this.arena.p2Point, spd: this.arena.p2Speed, dir: this.arena.p2FingerDir }
    ];

    for (const p of players) {
      if (!p.pos) continue;
      if (p.role === 'p2' && this.arena.playMode !== 'local') continue;

      // Check held ball for throw
      let heldBall = this.balls.find(b => b.holder === p.role);
      if (heldBall) {
        heldBall.x = p.pos.x;
        heldBall.y = p.pos.y - 10;

        // Wave throw trigger: responsive flick or directional swipe
        if (p.spd > 260) {
          const vx = (p.dir ? p.dir.x : 0.8) * p.spd * 0.95;
          const vy = (p.dir && p.dir.y < 0 ? p.dir.y : -0.7) * p.spd * 0.95 - 200;
          heldBall.state = 'flying';
          heldBall.holder = null;
          heldBall.vx = Math.max(-1200, Math.min(1200, vx));
          heldBall.vy = Math.max(-1400, Math.min(-300, vy));
          heldBall.spin = (Math.random() - 0.5) * 8;
          (this.arena.sounds || this.arena.sound)?.playWhoosh();

          if (this.arena.playMode === 'online') {
            this.arena.multiplayer.throwBasketball({
              id: heldBall.id,
              x: heldBall.x,
              y: heldBall.y,
              vx: heldBall.vx,
              vy: heldBall.vy
            });
          }
        }
      } else {
        // Find nearest floor ball to pick up
        for (const ball of this.balls) {
          if (ball.state !== 'floor') continue;
          if (this.arena.playMode === 'local' && ball.owner !== 'shared' && ball.owner !== p.role) continue;

          const dist = Math.hypot(p.pos.x - ball.x, p.pos.y - ball.y);
          if (dist < 90) {
            ball.pickupProgress += dt * 4.0; // Responsive ~0.25s pickup
            if (ball.pickupProgress >= 1.0) {
              ball.state = 'held';
              ball.holder = p.role;
              ball.pickupProgress = 0;
              (this.arena.sounds || this.arena.sound)?.playTargetHit();
            }
          } else {
            ball.pickupProgress = Math.max(0, ball.pickupProgress - dt * 2.0);
          }
        }
      }
    }

    // Update ball physics
    for (const b of this.balls) {
      const res = b.update(dt, this.floorY, this.hoops);
      if (res && res.scored) {
        (this.arena.sounds || this.arena.sound)?.playSwish();
        const scorer = (b.holder || (this.arena.playMode === 'local' ? (b.x < window.innerWidth / 2 ? 'p1' : 'p2') : 'p1'));
        this.scores[scorer] += res.points;
        this.arena.scores[scorer] = this.scores[scorer];
        this.arena.updateScoreboardUI();

        // Net swish burst particles
        for (let i = 0; i < 16; i++) {
          this.particles.push({
            x: b.x + (Math.random() - 0.5) * 20,
            y: b.y + (Math.random() - 0.5) * 20,
            vx: (Math.random() - 0.5) * 240,
            vy: (Math.random() - 0.5) * 200 - 80,
            color: '#ffd028',
            radius: 3 + Math.random() * 3,
            life: 1.0
          });
        }

        this.floaters.push({
          x: b.x,
          y: b.y - 40,
          text: `+${res.points} SWISH!`,
          color: '#ffd028',
          t: now
        });

        if (this.arena.playMode === 'online' && this.arena.multiplayer.role === scorer) {
          this.arena.multiplayer.scoreBasketball(res.points);
        } else if (this.arena.playMode === 'local') {
          const targetPts = this.arena.targetWins * 2;
          if (this.scores[scorer] >= targetPts) {
            const winnerName = scorer === 'p1' ? 'PLAYER 1 (LEFT)' : 'PLAYER 2 (RIGHT)';
            this.arena.showDualResultModal(`🏆 ${winnerName} WINS HOOPS!`, `Score: P1 [${this.scores.p1}] - P2 [${this.scores.p2}]`, true);
          }
        }
      }
    }

    // Particles & floaters
    this.particles.forEach(p => {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 400 * dt;
      p.life -= dt * 1.8;
    });
    this.particles = this.particles.filter(p => p.life > 0);
    this.floaters = this.floaters.filter(f => now - f.t < 0.9);
  }

  draw(ctx, now) {
    const W = window.innerWidth;
    const H = window.innerHeight;

    // Court Floor line with wood grain look
    ctx.save();
    ctx.fillStyle = 'rgba(28, 20, 16, 0.95)';
    ctx.fillRect(0, this.floorY, W, H - this.floorY);
    ctx.strokeStyle = '#e08838';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, this.floorY);
    ctx.lineTo(W, this.floorY);
    ctx.stroke();

    // Free throw key markings
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.lineWidth = 2;
    ctx.strokeRect(W * 0.25, this.floorY, W * 0.5, H - this.floorY);
    ctx.restore();

    // Draw Hoops
    for (const h of this.hoops) {
      ctx.save();
      // Backboard Glass + Glow Border
      const bw = 18;
      const bx = h.facingRight ? h.boardX - bw : h.boardX;
      ctx.fillStyle = 'rgba(20, 35, 60, 0.75)';
      ctx.strokeStyle = h.color;
      ctx.lineWidth = 3;
      ctx.fillRect(bx, h.boardTop, bw, h.boardBottom - h.boardTop);
      ctx.strokeRect(bx, h.boardTop, bw, h.boardBottom - h.boardTop);

      // Inner target square on backboard
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      const innerW = 12;
      const innerH = 65;
      ctx.strokeRect(bx, h.rimY - innerH + 8, innerW, innerH);

      // Metal Rim (Orange ring)
      ctx.strokeStyle = '#ff5500';
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.moveTo(h.boardX, h.rimY);
      ctx.lineTo(h.rimTipX, h.rimY);
      ctx.stroke();

      // Rim tip cap
      ctx.fillStyle = '#ff8800';
      ctx.beginPath();
      ctx.arc(h.rimTipX, h.rimY, 6, 0, Math.PI * 2);
      ctx.fill();

      // Animated Basketball Net
      const swishOffset = h.swishTime > 0 ? Math.sin(h.swishTime * 20) * 18 : 0;
      const netTopLeft = Math.min(h.boardX, h.rimTipX);
      const netTopRight = Math.max(h.boardX, h.rimTipX);
      const netW = netTopRight - netTopLeft;
      const netH = 75;

      ctx.strokeStyle = 'rgba(250, 250, 255, 0.85)';
      ctx.lineWidth = 1.8;

      // Net cross ropes
      for (let i = 0; i <= 6; i++) {
        const t = i / 6;
        const xTop = netTopLeft + netW * t;
        const xBottom = netTopLeft + netW * 0.2 + (netW * 0.6) * t + swishOffset;
        ctx.beginPath();
        ctx.moveTo(xTop, h.rimY);
        ctx.quadraticCurveTo((xTop + xBottom) / 2 + swishOffset * 0.5, h.rimY + netH * 0.5, xBottom, h.rimY + netH);
        ctx.stroke();
      }
      for (let j = 1; j <= 4; j++) {
        const ny = h.rimY + (netH * j) / 5;
        const shrink = 1 - (j / 5) * 0.4;
        const nx1 = netTopLeft + (netW * (1 - shrink)) / 2 + swishOffset * (j / 5);
        const nx2 = netTopRight - (netW * (1 - shrink)) / 2 + swishOffset * (j / 5);
        ctx.beginPath();
        ctx.moveTo(nx1, ny);
        ctx.lineTo(nx2, ny);
        ctx.stroke();
      }

      ctx.restore();
    }

    // Draw Balls
    for (const b of this.balls) b.draw(ctx);

    // Draw Particles
    for (const p of this.particles) {
      ctx.fillStyle = p.color;
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;

    // Floater scores
    for (const f of this.floaters) {
      const dt = now - f.t;
      ctx.fillStyle = f.color;
      ctx.font = 'bold 22px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(f.text, f.x, f.y - dt * 45);
    }

    // Top HUD: Timer & Baskets
    ctx.save();
    ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    ctx.strokeStyle = '#ffd028';
    ctx.lineWidth = 1.5;
    ctx.fillRect(W / 2 - 140, 18, 280, 52);
    ctx.strokeRect(W / 2 - 140, 18, 280, 52);

    ctx.fillStyle = '#ffd028';
    ctx.font = 'bold 18px Orbitron, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`TIME: ${Math.ceil(this.timeLeft)}s`, W / 2, 42);

    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Space Grotesk, monospace';
    ctx.fillText(`SCORE: P1 [${this.scores.p1}]  |  P2 [${this.scores.p2}]`, W / 2, 60);
    ctx.restore();
  }
}

// =====================================================================
//  2. MILK THE COW DUEL
// =====================================================================

export class CowGame {
  constructor(arena) {
    this.arena = arena;
    this.stations = [];
    this.timeLimit = 45;
    this.reset();
  }

  reset() {
    this.stations = [];
    const isLocalDual = this.arena.playMode === 'local';
    const W = window.innerWidth;
    const H = window.innerHeight;

    if (isLocalDual) {
      this.stations.push({
        role: 'p1',
        title: 'PLAYER 1 (CYAN)',
        color: '#00f0ff',
        cx: W * 0.28,
        cy: H * 0.44,
        fill: 0,
        lastHandY: null,
        streams: [],
        foam: [],
        done: false,
        time: 0
      });

      this.stations.push({
        role: 'p2',
        title: 'PLAYER 2 (RED)',
        color: '#ff3366',
        cx: W * 0.72,
        cy: H * 0.44,
        fill: 0,
        lastHandY: null,
        streams: [],
        foam: [],
        done: false,
        time: 0
      });
    } else {
      this.stations.push({
        role: 'p1',
        title: 'SOLO / ONLINE COW',
        color: '#ffd028',
        cx: W * 0.5,
        cy: H * 0.44,
        fill: 0,
        lastHandY: null,
        streams: [],
        foam: [],
        done: false,
        time: 0
      });
    }
  }

  update(now, dt) {
    const players = [
      { role: 'p1', pos: this.arena.p1Point, lastSeen: this.arena.p1LastSeen },
      { role: 'p2', pos: this.arena.p2Point, lastSeen: this.arena.p2LastSeen }
    ];

    for (const st of this.stations) {
      if (st.done) continue;
      const p = players.find(x => x.role === st.role);
      if (!p || !p.pos) {
        st.lastHandY = null;
        continue;
      }

      // Udder interaction zone
      const udderW = 240;
      const udderH = 220;
      const inZone = Math.abs(p.pos.x - st.cx) < udderW / 2 && p.pos.y > st.cy - 70 && p.pos.y < st.cy + 150;

      if (inZone) {
        if (st.lastHandY !== null) {
          const dy = p.pos.y - st.lastHandY;
          // Downward motion triggers milk stream!
          if (dy > 2 && dy < 100) {
            const added = dy * 0.12;
            st.fill = Math.min(100, st.fill + added);
            (this.arena.sounds || this.arena.sound)?.playMilkSquirt();

            // Spawn 3 milk streams down to the bucket
            for (let k = 0; k < 3; k++) {
              st.streams.push({
                x: st.cx + (k - 1) * 26 + (Math.random() - 0.5) * 10,
                y: st.cy + 25,
                vy: 550 + Math.random() * 200,
                targetY: st.cy + 240,
                life: 1.0
              });
            }

            if (this.arena.playMode === 'online' && this.arena.multiplayer.role === st.role) {
              this.arena.multiplayer.squirtMilk(st.fill, p.pos.y);
            }

            if (st.fill >= 100 && !st.done) {
              st.done = true;
              st.time = now;
              (this.arena.sounds || this.arena.sound)?.playPoseSuccess();
              this.arena.scores[st.role] += 1;
              this.arena.updateScoreboardUI();

              if (this.arena.playMode === 'online' && this.arena.multiplayer.role === st.role) {
                this.arena.multiplayer.finishCow(now);
              } else if (this.arena.playMode === 'local') {
                const winnerName = st.role === 'p1' ? 'PLAYER 1 (LEFT)' : 'PLAYER 2 (RIGHT)';
                const isMatchOver = (this.arena.scores.p1 >= this.arena.targetWins || this.arena.scores.p2 >= this.arena.targetWins);
                this.arena.showDualResultModal(`${winnerName} WINS!`, `Filled Bucket First! (P1: ${this.arena.scores.p1} vs P2: ${this.arena.scores.p2})`, isMatchOver);
              } else if (this.arena.playMode === 'solo') {
                this.arena.showResults('BUCKET FILLED 100%!', 'Great Milking Speed!');
              }
            }
          }
        }
        st.lastHandY = p.pos.y;
      } else {
        st.lastHandY = null;
      }

      // Update streams
      for (const s of st.streams) {
        s.y += s.vy * dt;
        if (s.y >= s.targetY) {
          s.life = 0;
          // Foam splash
          st.foam.push({
            x: s.x + (Math.random() - 0.5) * 20,
            y: st.targetY + (Math.random() - 0.5) * 8,
            r: 4 + Math.random() * 5,
            life: 0.6
          });
        }
      }
      st.streams = st.streams.filter(s => s.life > 0);
      st.foam.forEach(f => f.life -= dt);
      st.foam = st.foam.filter(f => f.life > 0);
    }
  }

  draw(ctx, now) {
    for (const st of this.stations) {
      ctx.save();
      const cx = st.cx;
      const cy = st.cy;

      // Stylized Cow Body Patch
      ctx.fillStyle = '#f8f8fa';
      ctx.beginPath();
      ctx.ellipse(cx, cy - 130, 160, 95, 0, 0, Math.PI * 2);
      ctx.fill();

      // Cow Black Spots
      ctx.fillStyle = '#222228';
      ctx.beginPath();
      ctx.ellipse(cx - 75, cy - 145, 45, 35, 0.4, 0, Math.PI * 2);
      ctx.ellipse(cx + 80, cy - 120, 50, 42, -0.3, 0, Math.PI * 2);
      ctx.fill();

      // Udder base (Pink)
      ctx.fillStyle = '#f7b0c0';
      ctx.strokeStyle = '#e0859a';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(cx, cy - 30, 68, 0, Math.PI);
      ctx.fill();
      ctx.stroke();

      // 4 Teats
      const teatOffsets = [-40, -14, 14, 40];
      for (const ox of teatOffsets) {
        ctx.fillStyle = '#f295aa';
        ctx.strokeStyle = '#d6758c';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(cx + ox - 8, cy + 22, 16, 36, 8);
        ctx.fill();
        ctx.stroke();
      }

      // Yellow Squeeze Zone Box
      ctx.strokeStyle = st.color;
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 6]);
      ctx.strokeRect(cx - 100, cy - 20, 200, 150);
      ctx.setLineDash([]);

      ctx.fillStyle = st.color;
      ctx.font = 'bold 12px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${st.title} - PULL DOWN TO MILK`, cx, cy - 30);

      // Downward Milk Streams
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 4;
      for (const s of st.streams) {
        ctx.beginPath();
        ctx.moveTo(s.x, s.y - 18);
        ctx.lineTo(s.x, s.y);
        ctx.stroke();
      }

      // Foam bubbles
      for (const f of st.foam) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        ctx.fill();
      }

      // Milk Bucket / Jug
      const bucketY = cy + 250;
      const bucketW = 150;
      const bucketH = 130;

      // Bucket Glass Outline
      ctx.fillStyle = 'rgba(180, 215, 240, 0.2)';
      ctx.strokeStyle = '#8ab4d0';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cx - bucketW / 2, bucketY - bucketH);
      ctx.lineTo(cx - bucketW * 0.38, bucketY);
      ctx.lineTo(cx + bucketW * 0.38, bucketY);
      ctx.lineTo(cx + bucketW / 2, bucketY - bucketH);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Liquid Milk Fill inside bucket
      const fillH = (bucketH - 12) * (st.fill / 100);
      if (fillH > 2) {
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.moveTo(cx - bucketW * 0.38, bucketY - 4);
        ctx.lineTo(cx + bucketW * 0.38, bucketY - 4);
        ctx.lineTo(cx + bucketW * 0.38 + (bucketW * 0.12) * (st.fill / 100), bucketY - fillH);
        ctx.lineTo(cx - bucketW * 0.38 - (bucketW * 0.12) * (st.fill / 100), bucketY - fillH);
        ctx.closePath();
        ctx.fill();

        // Foam wave on top of milk
        ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.beginPath();
        ctx.ellipse(cx, bucketY - fillH, (bucketW * 0.42) * (0.8 + 0.2 * (st.fill / 100)), 7, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // Percentage Label Badge
      ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
      ctx.fillRect(cx - 50, bucketY + 12, 100, 28);
      ctx.strokeStyle = st.color;
      ctx.strokeRect(cx - 50, bucketY + 12, 100, 28);

      ctx.fillStyle = st.fill >= 100 ? '#10f084' : '#ffd028';
      ctx.font = 'bold 15px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${Math.round(st.fill)}% FULL`, cx, bucketY + 31);

      if (st.done) {
        ctx.fillStyle = '#10f084';
        ctx.font = 'bold 24px Orbitron, monospace';
        ctx.fillText('WINNER! CUP FILLED!', cx, cy - 80);
      }

      ctx.restore();
    }
  }
}

// =====================================================================
//  3. WALL PAINTER DUEL
// =====================================================================

export class PainterGame {
  constructor(arena) {
    this.arena = arena;
    this.offscreen = document.createElement('canvas');
    this.offscreen.width = window.innerWidth;
    this.offscreen.height = window.innerHeight;
    this.offCtx = this.offscreen.getContext('2d');
    this.gridW = 36;
    this.gridH = 24;
    this.gridP1 = new Uint8Array(this.gridW * this.gridH);
    this.gridP2 = new Uint8Array(this.gridW * this.gridH);
    this.coverageP1 = 0;
    this.coverageP2 = 0;
    this.winTarget = 95;
    this.brushR = 75;
    this.reset();
  }

  reset() {
    this.offscreen.width = window.innerWidth;
    this.offscreen.height = window.innerHeight;
    this.offCtx.clearRect(0, 0, this.offscreen.width, this.offscreen.height);
    this.gridP1.fill(0);
    this.gridP2.fill(0);
    this.coverageP1 = 0;
    this.coverageP2 = 0;
  }

  update(now, dt) {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const isLocalDual = this.arena.playMode === 'local';

    const players = [
      { role: 'p1', pos: this.arena.p1Point, color: '#00f0ff', grid: this.gridP1 },
      { role: 'p2', pos: this.arena.p2Point, color: '#ff3366', grid: this.gridP2 }
    ];

    for (const p of players) {
      if (!p.pos) continue;
      if (p.role === 'p2' && !isLocalDual) continue;

      // In local dual, P1 paints left half, P2 paints right half
      const xMin = isLocalDual ? (p.role === 'p1' ? 0 : W / 2) : 0;
      const xMax = isLocalDual ? (p.role === 'p1' ? W / 2 : W) : W;

      if (p.pos.x >= xMin && p.pos.x <= xMax) {
        // Splat paint on offscreen canvas
        this.offCtx.save();
        this.offCtx.fillStyle = p.color;
        this.offCtx.beginPath();
        this.offCtx.arc(p.pos.x, p.pos.y, this.brushR, 0, Math.PI * 2);
        this.offCtx.fill();
        this.offCtx.restore();

        // Mark cells in grid
        const cellW = W / this.gridW;
        const cellH = H / this.gridH;
        const colStart = Math.max(0, Math.floor((p.pos.x - this.brushR) / cellW));
        const colEnd = Math.min(this.gridW - 1, Math.floor((p.pos.x + this.brushR) / cellW));
        const rowStart = Math.max(0, Math.floor((p.pos.y - this.brushR) / cellH));
        const rowEnd = Math.min(this.gridH - 1, Math.floor((p.pos.y + this.brushR) / cellH));

        for (let r = rowStart; r <= rowEnd; r++) {
          for (let c = colStart; c <= colEnd; c++) {
            const cx = (c + 0.5) * cellW;
            const cy = (r + 0.5) * cellH;
            if (Math.hypot(p.pos.x - cx, p.pos.y - cy) <= this.brushR) {
              p.grid[r * this.gridW + c] = 1;
            }
          }
        }
      }
    }

    // Calculate coverage %
    if (isLocalDual) {
      const halfTotal = (this.gridW * this.gridH) / 2;
      let countP1 = 0;
      let countP2 = 0;
      for (let r = 0; r < this.gridH; r++) {
        for (let c = 0; c < this.gridW / 2; c++) {
          if (this.gridP1[r * this.gridW + c]) countP1++;
        }
        for (let c = Math.floor(this.gridW / 2); c < this.gridW; c++) {
          if (this.gridP2[r * this.gridW + c]) countP2++;
        }
      }
      this.coverageP1 = Math.min(100, (countP1 / halfTotal) * 100);
      this.coverageP2 = Math.min(100, (countP2 / halfTotal) * 100);
    } else {
      const total = this.gridW * this.gridH;
      let count = 0;
      for (let i = 0; i < total; i++) if (this.gridP1[i]) count++;
      this.coverageP1 = Math.min(100, (count / total) * 100);
    }

    // Check Win condition
    if (this.arena.state === 'PLAY') {
      if (this.coverageP1 >= this.winTarget) {
        this.arena.scores.p1 += 1;
        this.arena.state = 'CLEAR';
        (this.arena.sounds || this.arena.sound)?.playPoseSuccess();
        if (typeof this.arena.showResults === 'function') this.arena.showResults('WALL 95% COVERED!', 'Player 1 Wins!');
      } else if (isLocalDual && this.coverageP2 >= this.winTarget) {
        this.arena.scores.p2 += 1;
        this.arena.state = 'CLEAR';
        (this.arena.sounds || this.arena.sound)?.playPoseSuccess();
        if (typeof this.arena.showResults === 'function') this.arena.showResults('WALL 95% COVERED!', 'Player 2 Wins!');
      }
    }
  }

  draw(ctx, now) {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const isLocalDual = this.arena.playMode === 'local';

    // Dark cyber brick backdrop
    ctx.save();
    ctx.fillStyle = '#0c0f16';
    ctx.fillRect(0, 0, W, H);

    // Wall grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, H);
      ctx.stroke();
    }
    for (let y = 0; y < H; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }

    // Render offscreen painted layer
    ctx.drawImage(this.offscreen, 0, 0);

    // Split dividing neon line for 1-Device dual
    if (isLocalDual) {
      ctx.strokeStyle = '#ffd028';
      ctx.lineWidth = 3;
      ctx.setLineDash([12, 8]);
      ctx.beginPath();
      ctx.moveTo(W / 2, 0);
      ctx.lineTo(W / 2, H);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw Glowing Roller Cursors
    const rollers = [
      { role: 'p1', pos: this.arena.p1Point, color: '#00f0ff' },
      { role: 'p2', pos: this.arena.p2Point, color: '#ff3366' }
    ];

    for (const r of rollers) {
      if (!r.pos) continue;
      if (r.role === 'p2' && !isLocalDual) continue;

      ctx.save();
      ctx.translate(r.pos.x, r.pos.y);

      // Roller metal arm
      ctx.strokeStyle = '#d0d8e8';
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.moveTo(0, 20);
      ctx.lineTo(0, 48);
      ctx.lineTo(26, 48);
      ctx.lineTo(26, 0);
      ctx.stroke();

      // Roller cylinder
      ctx.fillStyle = r.color;
      ctx.beginPath();
      ctx.roundRect(-42, -18, 84, 36, 8);
      ctx.fill();

      ctx.restore();
    }

    // Top Coverage HUD
    ctx.fillStyle = 'rgba(10, 15, 25, 0.88)';
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 1.5;
    ctx.fillRect(W / 2 - 180, 16, 360, 56);
    ctx.strokeRect(W / 2 - 180, 16, 360, 56);

    ctx.fillStyle = '#00f0ff';
    ctx.font = 'bold 15px Orbitron, monospace';
    ctx.textAlign = 'center';
    if (isLocalDual) {
      ctx.fillText(`P1: ${Math.round(this.coverageP1)}%   VS   P2: ${Math.round(this.coverageP2)}%`, W / 2, 38);
    } else {
      ctx.fillText(`WALL COVERED: ${Math.round(this.coverageP1)}% / 95%`, W / 2, 38);
    }

    // Progress Bar Track
    ctx.fillStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.fillRect(W / 2 - 140, 48, 280, 12);
    ctx.fillStyle = isLocalDual ? (this.coverageP1 > this.coverageP2 ? '#00f0ff' : '#ff3366') : '#10f084';
    ctx.fillRect(W / 2 - 140, 48, 280 * (Math.max(this.coverageP1, this.coverageP2) / 100), 12);

    ctx.restore();
  }
}

// =====================================================================
//  4. FRUIT CATCH (HEAD BASKET)
// =====================================================================

export class CatchGame {
  constructor(arena) {
    this.arena = arena;
    this.fruits = [];
    this.particles = [];
    this.floaters = [];
    this.baskets = {
      p1: { x: window.innerWidth * 0.3, y: window.innerHeight * 0.65, w: 150, h: 52, faceSeen: false },
      p2: { x: window.innerWidth * 0.7, y: window.innerHeight * 0.65, w: 150, h: 52, faceSeen: false }
    };
    this.timeLimit = 45;
    this.timeLeft = 45;
    this.spawnTimer = 0;
    this.reset();
  }

  reset() {
    this.fruits = [];
    this.particles = [];
    this.floaters = [];
    this.timeLeft = this.timeLimit;
    this.spawnTimer = 0;
    this.baskets.p1.x = window.innerWidth * 0.3;
    this.baskets.p2.x = window.innerWidth * 0.7;
  }

  update(now, dt) {
    const W = window.innerWidth;
    const H = window.innerHeight;

    if (this.arena.state === 'PLAY') {
      this.timeLeft = Math.max(0, this.timeLeft - dt);
      if (this.timeLeft === 0) {
        this.arena.state = 'GAMEOVER';
        this.arena.showResults();
      }

      // Fruit Spawner
      this.spawnTimer -= dt;
      if (this.spawnTimer <= 0) {
        this.spawnTimer = 0.85 + Math.random() * 0.55;
        const kinds = ['apple', 'orange', 'lime', 'plum', 'star', 'bomb'];
        const weights = [0.25, 0.25, 0.2, 0.15, 0.08, 0.07];
        const rand = Math.random();
        let sum = 0;
        let chosen = 'apple';
        for (let i = 0; i < kinds.length; i++) {
          sum += weights[i];
          if (rand <= sum) {
            chosen = kinds[i];
            break;
          }
        }

        // Spawn position near active baskets
        const x = 60 + Math.random() * (W - 120);
        this.fruits.push({
          id: Math.random().toString(36).substring(2, 7),
          kind: chosen,
          x,
          y: -40,
          vy: 110 + Math.random() * 65,
          radius: chosen === 'star' ? 24 : 34,
          rot: Math.random() * Math.PI,
          spin: (Math.random() - 0.5) * 3
        });
      }
    }

    // Move falling fruits
    for (const f of this.fruits) {
      f.y += f.vy * dt;
      f.rot += f.spin * dt;

      // Check collision with baskets
      const isLocalDual = this.arena.playMode === 'local';
      const activeBaskets = isLocalDual ? [this.baskets.p1, this.baskets.p2] : [this.baskets.p1];

      for (let i = 0; i < activeBaskets.length; i++) {
        const b = activeBaskets[i];
        const role = i === 0 ? 'p1' : 'p2';

        if (Math.abs(f.x - b.x) < b.w * 0.52 && f.y >= b.y - 20 && f.y <= b.y + 25) {
          f.caught = true;

          if (f.kind === 'bomb') {
            (this.arena.sounds || this.arena.sound)?.playThud();
            this.arena.scores[role] = Math.max(0, this.arena.scores[role] - 3);
            this.floaters.push({ x: f.x, y: f.y - 20, text: 'BOMB! -3', color: '#ff3366', t: now });
          } else if (f.kind === 'star') {
            (this.arena.sounds || this.arena.sound)?.playCatch();
            this.arena.scores[role] += 3;
            this.floaters.push({ x: f.x, y: f.y - 20, text: '+3 STAR!', color: '#ffd028', t: now });
          } else {
            (this.arena.sounds || this.arena.sound)?.playCatch();
            this.arena.scores[role] += 1;
            this.floaters.push({ x: f.x, y: f.y - 20, text: '+1 JUICY!', color: '#10f084', t: now });
          }

          this.arena.updateScoreboardUI();

          // Particle burst
          for (let k = 0; k < 12; k++) {
            this.particles.push({
              x: f.x,
              y: f.y,
              vx: (Math.random() - 0.5) * 180,
              vy: (Math.random() - 0.5) * 160 - 60,
              color: f.kind === 'bomb' ? '#ff3366' : '#ffd028',
              r: 3 + Math.random() * 4,
              life: 0.8
            });
          }

          if (this.arena.playMode === 'online' && this.arena.multiplayer.role === role) {
            this.arena.multiplayer.catchFruitScored(f.id, f.kind === 'star' ? 3 : 1);
          } else if (this.arena.playMode === 'local') {
            const targetScore = this.arena.targetWins * 3;
            if (this.arena.scores[role] >= targetScore) {
              const winnerName = role === 'p1' ? 'PLAYER 1 (LEFT)' : 'PLAYER 2 (RIGHT)';
              this.arena.showDualResultModal(`🏆 ${winnerName} WINS CATCH!`, `Final Score: P1 [${this.arena.scores.p1}] - P2 [${this.arena.scores.p2}]`, true);
            }
          }
          break;
        }
      }
    }

    this.fruits = this.fruits.filter(f => !f.caught && f.y < H + 60);

    // Particles & floaters
    this.particles.forEach(p => {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 320 * dt;
      p.life -= dt * 1.5;
    });
    this.particles = this.particles.filter(p => p.life > 0);
    this.floaters = this.floaters.filter(f => now - f.t < 0.85);
  }

  setFace(role, normX, normY, normW) {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const b = this.baskets[role];
    if (!b) return;
    const targetX = normX * W;
    const targetY = Math.max(120, normY * H - 35); // Above head
    b.x += (targetX - b.x) * 0.28;
    b.y += (targetY - b.y) * 0.28;
    b.w = Math.max(130, normW * W * 1.35);
    b.faceSeen = true;
  }

  draw(ctx, now) {
    const W = window.innerWidth;

    // Draw Baskets
    const isLocalDual = this.arena.playMode === 'local';
    const activeBaskets = isLocalDual ? [
      { ...this.baskets.p1, role: 'P1', color: '#00f0ff' },
      { ...this.baskets.p2, role: 'P2', color: '#ff3366' }
    ] : [
      { ...this.baskets.p1, role: 'YOU', color: '#ffd028' }
    ];

    for (const b of activeBaskets) {
      ctx.save();
      ctx.translate(b.x, b.y);

      // Wicker Basket Body
      ctx.fillStyle = '#c8924b';
      ctx.strokeStyle = '#7c4d18';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(-b.w / 2, 0);
      ctx.quadraticCurveTo(0, b.h * 1.3, b.w / 2, 0);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Wicker cross-hatch pattern
      ctx.strokeStyle = 'rgba(75, 40, 10, 0.45)';
      ctx.lineWidth = 1.5;
      for (let i = -b.w / 2 + 15; i < b.w / 2; i += 18) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i * 0.6, b.h * 0.85);
        ctx.stroke();
      }

      // Basket Rim (Player color)
      ctx.strokeStyle = b.color;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.ellipse(0, 0, b.w / 2, 14, 0, 0, Math.PI * 2);
      ctx.stroke();

      // Player Badge
      ctx.fillStyle = b.color;
      ctx.font = 'bold 12px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(b.role, 0, 24);

      ctx.restore();
    }

    // Draw Falling Fruits
    for (const f of this.fruits) {
      ctx.save();
      ctx.translate(f.x, f.y);
      ctx.rotate(f.rot);

      if (f.kind === 'apple') {
        ctx.fillStyle = '#eb2434';
        ctx.beginPath();
        ctx.arc(0, 0, f.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#48b832';
        ctx.fillRect(-2, -f.radius - 8, 4, 10);
      } else if (f.kind === 'orange') {
        ctx.fillStyle = '#ff8812';
        ctx.beginPath();
        ctx.arc(0, 0, f.radius, 0, Math.PI * 2);
        ctx.fill();
      } else if (f.kind === 'lime') {
        ctx.fillStyle = '#62cc2a';
        ctx.beginPath();
        ctx.arc(0, 0, f.radius, 0, Math.PI * 2);
        ctx.fill();
      } else if (f.kind === 'plum') {
        ctx.fillStyle = '#8b2ca5';
        ctx.beginPath();
        ctx.arc(0, 0, f.radius, 0, Math.PI * 2);
        ctx.fill();
      } else if (f.kind === 'star') {
        ctx.fillStyle = '#ffd028';
        ctx.beginPath();
        for (let i = 0; i < 5; i++) {
          const a = (i * Math.PI * 2) / 5 - Math.PI / 2;
          const a2 = a + Math.PI / 5;
          if (i === 0) ctx.moveTo(Math.cos(a) * f.radius, Math.sin(a) * f.radius);
          else ctx.lineTo(Math.cos(a) * f.radius, Math.sin(a) * f.radius);
          ctx.lineTo(Math.cos(a2) * f.radius * 0.45, Math.sin(a2) * f.radius * 0.45);
        }
        ctx.closePath();
        ctx.fill();
      } else if (f.kind === 'bomb') {
        ctx.fillStyle = '#222226';
        ctx.beginPath();
        ctx.arc(0, 0, f.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#ff3366';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fillStyle = '#ff8800';
        ctx.fillRect(-3, -f.radius - 12, 6, 12);
      }

      ctx.restore();
    }

    // Particles & floaters
    for (const p of this.particles) {
      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.life;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;

    for (const fl of this.floaters) {
      const dt = now - fl.t;
      ctx.fillStyle = fl.color;
      ctx.font = 'bold 20px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(fl.text, fl.x, fl.y - dt * 40);
    }

    // Top HUD
    ctx.save();
    ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    ctx.strokeStyle = '#10f084';
    ctx.lineWidth = 1.5;
    ctx.fillRect(W / 2 - 140, 18, 280, 52);
    ctx.strokeRect(W / 2 - 140, 18, 280, 52);

    ctx.fillStyle = '#10f084';
    ctx.font = 'bold 18px Orbitron, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`TIME: ${Math.ceil(this.timeLeft)}s`, W / 2, 42);

    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Space Grotesk, monospace';
    ctx.fillText(`CATCHES: P1 [${this.arena.scores.p1}]  |  P2 [${this.arena.scores.p2}]`, W / 2, 60);
    ctx.restore();
  }
}

// =====================================================================
//  5. YOGA & ANIME POSE CHALLENGE
// =====================================================================

export const POSE_DATABASE = {
  yoga: [
    {
      id: 'tree',
      name: 'Tree Pose (Vrksasana)',
      desc: 'Stand on one leg, bend opposite knee outward, raise hands overhead!',
      targetAngles: { leftElbow: 160, rightElbow: 160, leftShoulder: 165, rightShoulder: 165, leftKnee: 175, rightKnee: 70 }
    },
    {
      id: 'warrior',
      name: 'Warrior II (Virabhadrasana)',
      desc: 'Wide stance, front knee bent 90°, arms stretched horizontal front & back!',
      targetAngles: { leftElbow: 175, rightElbow: 175, leftShoulder: 90, rightShoulder: 90, leftKnee: 110, rightKnee: 170 }
    },
    {
      id: 'triangle',
      name: 'Triangle Pose (Trikonasana)',
      desc: 'Straight legs, reach one hand down, other arm vertical pointing up!',
      targetAngles: { leftElbow: 170, rightElbow: 170, leftShoulder: 40, rightShoulder: 155, leftKnee: 175, rightKnee: 175 }
    },
    {
      id: 'goddess',
      name: 'Goddess Pose (Utkata Konasana)',
      desc: 'Deep wide squat, elbows bent 90° with open palms up!',
      targetAngles: { leftElbow: 90, rightElbow: 90, leftShoulder: 90, rightShoulder: 90, leftKnee: 115, rightKnee: 115 }
    },
    {
      id: 'cobra',
      name: 'Cobra Pose',
      desc: 'Chest raised high, shoulders back, arms supporting upper torso!',
      targetAngles: { leftElbow: 140, rightElbow: 140, leftShoulder: 65, rightShoulder: 65, leftKnee: 175, rightKnee: 175 }
    }
  ],
  anime: [
    {
      id: 'kamehameha',
      name: 'Kamehameha Stance',
      desc: 'Both wrists cupped together at your side hip, deep battle crouch!',
      targetAngles: { leftElbow: 75, rightElbow: 85, leftShoulder: 55, rightShoulder: 45, leftKnee: 125, rightKnee: 135 }
    },
    {
      id: 'naruto',
      name: 'Naruto Hokage Run',
      desc: 'Torso leaned forward, lock both arms straight behind your back!',
      targetAngles: { leftElbow: 175, rightElbow: 175, leftShoulder: 30, rightShoulder: 30, leftKnee: 130, rightKnee: 160 }
    },
    {
      id: 'jojo',
      name: 'JoJo Menacing Stand',
      desc: 'Dramatic pose: one hand shading your face, hips cocked sideways!',
      targetAngles: { leftElbow: 55, rightElbow: 120, leftShoulder: 120, rightShoulder: 70, leftKnee: 165, rightKnee: 130 }
    },
    {
      id: 'titan',
      name: 'Titan Heart Salute',
      desc: 'Right fist clenched over heart/chest, left arm behind back!',
      targetAngles: { leftElbow: 155, rightElbow: 50, leftShoulder: 25, rightShoulder: 55, leftKnee: 175, rightKnee: 175 }
    },
    {
      id: 'spirit',
      name: 'Spirit Bomb (Genki Dama)',
      desc: 'Raise both arms high in a wide V towards the sky to gather energy!',
      targetAngles: { leftElbow: 175, rightElbow: 175, leftShoulder: 160, rightShoulder: 160, leftKnee: 170, rightKnee: 170 }
    }
  ]
};

export class PoseGame {
  constructor(arena, category = 'yoga') {
    this.arena = arena;
    this.category = category; // 'yoga' or 'anime'
    this.phase = 'MEMORIZE';  // 'MEMORIZE', 'COUNTDOWN', 'PERFORM', 'RESULTS'
    this.phaseTimer = 3.5;
    this.poseIndex = 0;
    this.accuracyP1 = 0;
    this.accuracyP2 = 0;
    this.sustainedSamplesP1 = [];
    this.sustainedSamplesP2 = [];
    this.scoreP1 = 0;
    this.scoreP2 = 0;
    this.reset();
  }

  reset() {
    this.phase = 'MEMORIZE';
    this.phaseTimer = 3.5;
    this.accuracyP1 = 0;
    this.accuracyP2 = 0;
    this.sustainedSamplesP1 = [];
    this.sustainedSamplesP2 = [];
  }

  getCurrentPose() {
    const list = POSE_DATABASE[this.category] || POSE_DATABASE.yoga;
    return list[this.poseIndex % list.length];
  }

  calculateJointAngle(a, b, c) {
    if (!a || !b || !c) return 180;
    const v1 = { x: a.x - b.x, y: a.y - b.y };
    const v2 = { x: c.x - b.x, y: c.y - b.y };
    const dot = v1.x * v2.x + v1.y * v2.y;
    const mag1 = Math.hypot(v1.x, v1.y) || 1;
    const mag2 = Math.hypot(v2.x, v2.y) || 1;
    const cosAngle = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
    return Math.round((Math.acos(cosAngle) * 180) / Math.PI);
  }

  comparePose(landmarks) {
    if (!landmarks || landmarks.length < 29) return 0;
    const target = this.getCurrentPose().targetAngles;

    // Joint landmarks
    const ls = landmarks[11];
    const rs = landmarks[12];
    const le = landmarks[13];
    const re = landmarks[14];
    const lw = landmarks[15];
    const rw = landmarks[16];
    const lh = landmarks[23];
    const rh = landmarks[24];
    const lk = landmarks[25];
    const rk = landmarks[26];
    const la = landmarks[27];
    const ra = landmarks[28];

    // Compute player angles
    const angles = {
      leftElbow: this.calculateJointAngle(ls, le, lw),
      rightElbow: this.calculateJointAngle(rs, re, rw),
      leftShoulder: this.calculateJointAngle(lh, ls, le),
      rightShoulder: this.calculateJointAngle(rh, rs, re),
      leftKnee: this.calculateJointAngle(lh, lk, la),
      rightKnee: this.calculateJointAngle(rh, rk, ra)
    };

    let totalScore = 0;
    let count = 0;

    for (const [key, targetAngle] of Object.entries(target)) {
      const err = Math.abs((angles[key] || 180) - targetAngle);
      // Angle error <= 8 deg gives 100%, drops to 0 at 45 deg
      let limbScore = 0;
      if (err <= 8) limbScore = 100;
      else if (err >= 45) limbScore = 0;
      else limbScore = 100 * (1 - (err - 8) / 37);

      totalScore += limbScore;
      count++;
    }

    return Math.round(totalScore / (count || 1));
  }

  update(now, dt) {
    this.phaseTimer -= dt;

    if (this.phase === 'MEMORIZE' && this.phaseTimer <= 0) {
      this.phase = 'COUNTDOWN';
      this.phaseTimer = 3.0;
    } else if (this.phase === 'COUNTDOWN' && this.phaseTimer <= 0) {
      this.phase = 'PERFORM';
      this.phaseTimer = 5.0; // 5-second hold phase
      this.sustainedSamplesP1 = [];
      this.sustainedSamplesP2 = [];
    } else if (this.phase === 'PERFORM') {
      // Evaluate pose in real time
      if (this.arena.lastPoseLandmarks) {
        this.accuracyP1 = this.comparePose(this.arena.lastPoseLandmarks);
        this.sustainedSamplesP1.push(this.accuracyP1);
      }

      if (this.phaseTimer <= 0) {
        this.phase = 'RESULTS';
        this.phaseTimer = 4.0;

        // Calculate sustained average
        const avgP1 = this.sustainedSamplesP1.length > 0 ?
          Math.round(this.sustainedSamplesP1.reduce((a, b) => a + b, 0) / this.sustainedSamplesP1.length) : 0;
        this.scoreP1 = avgP1;

        if (this.scoreP1 >= 70) {
          (this.arena.sounds || this.arena.sound)?.playPoseSuccess();
          this.arena.scores.p1 += 1;
        } else {
          (this.arena.sounds || this.arena.sound)?.playThud();
        }
        this.arena.updateScoreboardUI();
      }
    } else if (this.phase === 'RESULTS' && this.phaseTimer <= 0) {
      // Advance to next pose
      this.poseIndex++;
      this.phase = 'MEMORIZE';
      this.phaseTimer = 3.5;
    }
  }

  draw(ctx, now) {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const pose = this.getCurrentPose();

    ctx.save();

    if (this.phase === 'MEMORIZE') {
      // Pose Card Overlay
      ctx.fillStyle = 'rgba(10, 15, 25, 0.9)';
      ctx.fillRect(W / 2 - 280, H / 2 - 200, 560, 400);
      ctx.strokeStyle = '#ffd028';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(W / 2 - 280, H / 2 - 200, 560, 400);

      ctx.fillStyle = '#ffd028';
      ctx.font = 'bold 26px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText('MEMORIZE THIS POSE!', W / 2, H / 2 - 145);

      ctx.fillStyle = '#00f0ff';
      ctx.font = 'bold 22px Orbitron, monospace';
      ctx.fillText(pose.name, W / 2, H / 2 - 95);

      ctx.fillStyle = '#ffffff';
      ctx.font = '16px Space Grotesk, sans-serif';
      ctx.fillText(pose.desc, W / 2, H / 2 - 50);

      // Stylized stick figure reference
      this.drawReferenceStickFigure(ctx, W / 2, H / 2 + 65, pose.id);

      ctx.fillStyle = '#10f084';
      ctx.font = 'bold 18px Orbitron, monospace';
      ctx.fillText(`STARTING IN: ${Math.ceil(this.phaseTimer)}s`, W / 2, H / 2 + 165);

    } else if (this.phase === 'COUNTDOWN') {
      ctx.fillStyle = '#ffd028';
      ctx.font = 'bold 72px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(Math.ceil(this.phaseTimer), W / 2, H / 2);

      ctx.fillStyle = '#ffffff';
      ctx.font = '22px Orbitron, monospace';
      ctx.fillText('GET READY TO STRIKE POSE!', W / 2, H / 2 + 70);

    } else if (this.phase === 'PERFORM') {
      // Big Arc Accuracy Meter
      const meterX = W / 2;
      const meterY = 120;
      const radius = 55;

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.lineWidth = 10;
      ctx.beginPath();
      ctx.arc(meterX, meterY, radius, -Math.PI, 0);
      ctx.stroke();

      const accColor = this.accuracyP1 >= 85 ? '#10f084' : (this.accuracyP1 >= 65 ? '#ffd028' : '#ff3366');
      ctx.strokeStyle = accColor;
      ctx.lineWidth = 10;
      ctx.beginPath();
      ctx.arc(meterX, meterY, radius, -Math.PI, -Math.PI + Math.PI * (this.accuracyP1 / 100));
      ctx.stroke();

      ctx.fillStyle = accColor;
      ctx.font = 'bold 24px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${this.accuracyP1}%`, meterX, meterY - 12);

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 14px Orbitron, monospace';
      ctx.fillText(`HOLD POSE: ${this.phaseTimer.toFixed(1)}s`, meterX, meterY + 28);

    } else if (this.phase === 'RESULTS') {
      ctx.fillStyle = 'rgba(10, 15, 25, 0.9)';
      ctx.fillRect(W / 2 - 240, H / 2 - 140, 480, 280);
      ctx.strokeStyle = this.scoreP1 >= 70 ? '#10f084' : '#ff3366';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(W / 2 - 240, H / 2 - 140, 480, 280);

      const rating = this.scoreP1 >= 92 ? 'PERFECT!' : (this.scoreP1 >= 80 ? 'GREAT!' : (this.scoreP1 >= 65 ? 'GOOD!' : 'TRY AGAIN!'));
      ctx.fillStyle = this.scoreP1 >= 70 ? '#10f084' : '#ff3366';
      ctx.font = 'bold 36px Orbitron, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(rating, W / 2, H / 2 - 60);

      ctx.fillStyle = '#ffd028';
      ctx.font = 'bold 28px Orbitron, monospace';
      ctx.fillText(`ACCURACY: ${this.scoreP1}%`, W / 2, H / 2);

      ctx.fillStyle = '#ffffff';
      ctx.font = '14px Space Grotesk, sans-serif';
      ctx.fillText(`Next Pose in ${Math.ceil(this.phaseTimer)}s...`, W / 2, H / 2 + 65);
    }

    ctx.restore();
  }

  drawReferenceStickFigure(ctx, cx, cy, poseId) {
    ctx.save();
    ctx.strokeStyle = '#ffd028';
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';

    // Head
    ctx.beginPath();
    ctx.arc(cx, cy - 65, 16, 0, Math.PI * 2);
    ctx.stroke();

    // Torso
    ctx.beginPath();
    ctx.moveTo(cx, cy - 49);
    ctx.lineTo(cx, cy + 10);
    ctx.stroke();

    if (poseId === 'tree') {
      // Arms raised V
      ctx.beginPath();
      ctx.moveTo(cx, cy - 35);
      ctx.lineTo(cx - 24, cy - 70);
      ctx.lineTo(cx - 6, cy - 90);
      ctx.moveTo(cx, cy - 35);
      ctx.lineTo(cx + 24, cy - 70);
      ctx.lineTo(cx + 6, cy - 90);
      ctx.stroke();
      // Legs: one straight, one bent
      ctx.beginPath();
      ctx.moveTo(cx, cy + 10);
      ctx.lineTo(cx - 10, cy + 70);
      ctx.moveTo(cx, cy + 10);
      ctx.lineTo(cx + 30, cy + 35);
      ctx.lineTo(cx - 5, cy + 40);
      ctx.stroke();
    } else if (poseId === 'kamehameha') {
      // Hands cupped at hip
      ctx.beginPath();
      ctx.moveTo(cx, cy - 35);
      ctx.lineTo(cx + 35, cy - 10);
      ctx.lineTo(cx + 42, cy + 10);
      ctx.moveTo(cx, cy - 35);
      ctx.lineTo(cx + 20, cy - 5);
      ctx.lineTo(cx + 38, cy + 10);
      ctx.stroke();
      // Crouched legs
      ctx.beginPath();
      ctx.moveTo(cx, cy + 10);
      ctx.lineTo(cx - 28, cy + 42);
      ctx.lineTo(cx - 32, cy + 70);
      ctx.moveTo(cx, cy + 10);
      ctx.lineTo(cx + 24, cy + 42);
      ctx.lineTo(cx + 30, cy + 70);
      ctx.stroke();
    } else {
      // Default warrior / T-pose
      ctx.beginPath();
      ctx.moveTo(cx - 45, cy - 35);
      ctx.lineTo(cx + 45, cy - 35);
      ctx.moveTo(cx, cy + 10);
      ctx.lineTo(cx - 22, cy + 70);
      ctx.moveTo(cx, cy + 10);
      ctx.lineTo(cx + 22, cy + 70);
      ctx.stroke();
    }

    ctx.restore();
  }
}
