import http from 'http';
import os from 'os';
import { WebSocketServer, WebSocket } from 'ws';
import { createServer as createViteServer } from 'vite';

const PORT = 3000;

function getLocalIps() {
  const interfaces = os.networkInterfaces();
  const ips = [];
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name] || []) {
      if (iface.family === 'IPv4' && !iface.internal) {
        // Prioritize Wi-Fi or real LAN
        const isWifi = name.toLowerCase().includes('wi-fi') || name.toLowerCase().includes('wlan');
        ips.push({ name, address: iface.address, isWifi });
      }
    }
  }
  // Sort Wi-Fi first, then 172.x/192.168.x
  ips.sort((a, b) => {
    if (a.isWifi && !b.isWifi) return -1;
    if (!a.isWifi && b.isWifi) return 1;
    if (a.address.startsWith('172.') && !b.address.startsWith('172.')) return -1;
    return 0;
  });
  return ips.length > 0 ? ips[0].address : 'localhost';
}

const localIp = getLocalIps();

// Active multiplayer rooms
const rooms = new Map();

function broadcastToRoom(room, message, senderWs = null) {
  const payload = JSON.stringify(message);
  [room.host, room.guest].forEach(client => {
    if (client && client.readyState === WebSocket.OPEN && client !== senderWs) {
      client.send(payload);
    }
  });
}

function broadcastToAll(room, message) {
  const payload = JSON.stringify(message);
  [room.host, room.guest].forEach(client => {
    if (client && client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  });
}

async function start() {
  const server = http.createServer((req, res) => {
    if (req.url === '/api/info') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        localIp,
        port: PORT,
        activeRooms: Array.from(rooms.keys())
      }));
      return;
    }
  });

  const wss = new WebSocketServer({ server });

  wss.on('connection', (ws) => {
    let currentRoomId = null;
    let playerRole = null; // 'p1' (host) or 'p2' (guest)

    ws.on('message', (raw) => {
      try {
        const msg = JSON.parse(raw);

        if (msg.type === 'create-room') {
          const roomId = (msg.roomId || Math.random().toString(36).substring(2, 7)).toUpperCase();
          currentRoomId = roomId;
          playerRole = 'p1';

          rooms.set(roomId, {
            id: roomId,
            game: msg.game || 'slice',
            host: ws,
            guest: null,
            scores: { p1: 0, p2: 0 },
            targetWins: msg.targetWins || 5,
            state: 'lobby',
            roundActive: false,
          });

          ws.send(JSON.stringify({
            type: 'room-created',
            roomId,
            role: 'p1',
            localIp,
            port: PORT,
            joinUrl: `http://${localIp}:${PORT}/?room=${roomId}`
          }));
          console.log(`[multiplayer] Room ${roomId} created by Host`);

        } else if (msg.type === 'join-room') {
          const roomId = (msg.roomId || '').toUpperCase();
          const room = rooms.get(roomId);

          if (!room) {
            ws.send(JSON.stringify({ type: 'error', message: `Room "${roomId}" not found!` }));
            return;
          }

          if (room.guest && room.guest.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'error', message: `Room "${roomId}" is already full!` }));
            return;
          }

          currentRoomId = roomId;
          playerRole = 'p2';
          room.guest = ws;
          room.state = 'ready';

          ws.send(JSON.stringify({
            type: 'room-joined',
            roomId,
            role: 'p2',
            game: room.game,
            scores: room.scores,
            targetWins: room.targetWins
          }));

          // Notify Host that Guest joined
          if (room.host && room.host.readyState === WebSocket.OPEN) {
            room.host.send(JSON.stringify({
              type: 'player-joined',
              role: 'p2',
              scores: room.scores
            }));
          }
          console.log(`[multiplayer] Guest joined Room ${roomId}`);

        } else if (msg.type === 'select-game') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            room.game = msg.game;
            room.scores = { p1: 0, p2: 0 };
            broadcastToAll(room, { type: 'game-changed', game: msg.game });
          }

        } else if (msg.type === 'start-match') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            room.scores = { p1: 0, p2: 0 };
            room.targetWins = msg.targetWins || 5;
            room.state = 'playing';
            broadcastToAll(room, {
              type: 'match-started',
              game: room.game,
              targetWins: room.targetWins,
              scores: room.scores
            });
          }

        } else if (msg.type === 'start-round') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            room.roundActive = true;
            const waitTime = msg.waitTime || (2.0 + Math.random() * 2.5);
            const fruitKind = msg.fruitKind || 'apple';
            broadcastToAll(room, {
              type: 'round-start',
              waitTime,
              fruitKind,
              timestamp: Date.now()
            });
          }

        } else if (msg.type === 'signal-cut') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            broadcastToAll(room, {
              type: 'signal-cut',
              timestamp: Date.now()
            });
          }

        } else if (msg.type === 'slice-attempt') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (!room || !room.roundActive) return;

          // If valid hit during active round:
          if (msg.hit) {
            room.roundActive = false; // round over, first hit won!
            room.scores[playerRole] += 1;

            broadcastToAll(room, {
              type: 'round-won',
              winnerRole: playerRole,
              scores: room.scores,
              reactionMs: msg.reactionMs,
              speed: msg.speed,
              accuracy: msg.accuracy,
              direction: msg.direction,
              cutOffset: msg.cutOffset
            });

            // Check match win condition
            if (room.scores[playerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: playerRole,
                scores: room.scores
              });
            }
          } else {
            // Fault (too early or miss)
            broadcastToRoom(room, {
              type: 'opponent-miss',
              role: playerRole,
              reason: msg.reason
            }, ws);
          }

        } else if (msg.type === 'target-hit') {
          // Used in Target Blitz / Ninja Deflect
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            room.scores[playerRole] += (msg.points || 1);
            broadcastToAll(room, {
              type: 'target-scored',
              role: playerRole,
              scores: room.scores,
              targetId: msg.targetId
            });
          }

        } else if (msg.type === 'sync-blade') {
          // Stream opponent blade position for live ghost trail
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-blade',
              role: playerRole,
              point: msg.point,
              speed: msg.speed
            }, ws);
          }

        } else if (msg.type === 'shoot-arrow') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-arrow',
              role: playerRole,
              arrow: msg.arrow
            }, ws);
          }

        } else if (msg.type === 'sync-bow') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-bow',
              role: playerRole,
              bow: msg.bow
            }, ws);
          }

        } else if (msg.type === 'pop-balloon') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            room.scores[playerRole] += (msg.points || 1);
            broadcastToAll(room, {
              type: 'balloon-popped',
              role: playerRole,
              balloonIndex: msg.balloonIndex,
              scores: room.scores
            });
            if (room.scores[playerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: playerRole,
                scores: room.scores
              });
            }
          }

        } else if (msg.type === 'sync-balloons') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            broadcastToRoom(room, {
              type: 'balloons-spawned',
              balloons: msg.balloons,
              round: msg.round
            }, ws);
          }

        // --- BASKETBALL HOOP SHOTS ---
        } else if (msg.type === 'throw-basketball') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-basketball',
              role: playerRole,
              ball: msg.ball
            }, ws);
          }

        } else if (msg.type === 'basketball-scored') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            room.scores[playerRole] += (msg.points || 2);
            broadcastToAll(room, {
              type: 'basketball-scored',
              role: playerRole,
              points: msg.points || 2,
              scores: room.scores
            });
            if (room.scores[playerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: playerRole,
                scores: room.scores
              });
            }
          }

        // --- MILK THE COW ---
        } else if (msg.type === 'milk-squirt') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-milk-squirt',
              role: playerRole,
              fill: msg.fill,
              squirtY: msg.squirtY
            }, ws);
          }

        } else if (msg.type === 'cow-finished') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            room.scores[playerRole] += 1;
            broadcastToAll(room, {
              type: 'cow-round-won',
              winnerRole: playerRole,
              scores: room.scores,
              timeElapsed: msg.timeElapsed
            });
            if (room.scores[playerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: playerRole,
                scores: room.scores
              });
            }
          }

        // --- WALL PAINTER ---
        } else if (msg.type === 'paint-stroke') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-paint-stroke',
              role: playerRole,
              stroke: msg.stroke,
              coverage: msg.coverage
            }, ws);
          }

        } else if (msg.type === 'paint-finished') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            room.scores[playerRole] += 1;
            broadcastToAll(room, {
              type: 'paint-round-won',
              winnerRole: playerRole,
              scores: room.scores,
              timeElapsed: msg.timeElapsed
            });
            if (room.scores[playerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: playerRole,
                scores: room.scores
              });
            }
          }

        // --- FRUIT CATCH (HEAD BASKET) ---
        } else if (msg.type === 'sync-catch-basket') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-catch-basket',
              role: playerRole,
              x: msg.x,
              y: msg.y,
              w: msg.w
            }, ws);
          }

        } else if (msg.type === 'sync-catch-fruits') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            broadcastToRoom(room, {
              type: 'catch-fruits-spawned',
              fruits: msg.fruits
            }, ws);
          }

        } else if (msg.type === 'catch-fruit-scored') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            room.scores[playerRole] += (msg.points || 1);
            broadcastToAll(room, {
              type: 'catch-fruit-scored',
              role: playerRole,
              fruitId: msg.fruitId,
              scores: room.scores
            });
            if (room.scores[playerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: playerRole,
                scores: room.scores
              });
            }
          }

        // --- YOGA & ANIME POSE CHALLENGE ---
        } else if (msg.type === 'sync-pose-challenge') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room && playerRole === 'p1') {
            broadcastToRoom(room, {
              type: 'pose-challenge-selected',
              pose: msg.pose
            }, ws);
          }

        } else if (msg.type === 'sync-pose-score') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            broadcastToRoom(room, {
              type: 'opponent-pose-score',
              role: playerRole,
              score: msg.score,
              rating: msg.rating
            }, ws);
          }

        } else if (msg.type === 'pose-round-complete') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            if (msg.winnerRole) {
              room.scores[msg.winnerRole] += 1;
            }
            broadcastToAll(room, {
              type: 'pose-round-won',
              winnerRole: msg.winnerRole,
              p1Score: msg.p1Score,
              p2Score: msg.p2Score,
              scores: room.scores
            });
            if (msg.winnerRole && room.scores[msg.winnerRole] >= room.targetWins) {
              room.state = 'game-over';
              broadcastToAll(room, {
                type: 'match-won',
                champion: msg.winnerRole,
                scores: room.scores
              });
            }
          }

        // --- UNIVERSAL GAME ACTION FORWARDER ---
        } else if (msg.type === 'game-action') {
          if (!currentRoomId) return;
          const room = rooms.get(currentRoomId);
          if (room) {
            if (msg.broadcastToAll) {
              broadcastToAll(room, { ...msg.data, role: playerRole, action: msg.action });
            } else {
              broadcastToRoom(room, { ...msg.data, role: playerRole, action: msg.action }, ws);
            }
          }
        }
      } catch (e) {
        console.error('[multiplayer] WebSocket error parsing message:', e);
      }
    });

    ws.on('close', () => {
      if (currentRoomId && rooms.has(currentRoomId)) {
        const room = rooms.get(currentRoomId);
        if (room.host === ws) {
          console.log(`[multiplayer] Host disconnected from ${currentRoomId}`);
          if (room.guest && room.guest.readyState === WebSocket.OPEN) {
            room.guest.send(JSON.stringify({ type: 'opponent-left', message: 'Host disconnected' }));
          }
          rooms.delete(currentRoomId);
        } else if (room.guest === ws) {
          console.log(`[multiplayer] Guest disconnected from ${currentRoomId}`);
          room.guest = null;
          room.state = 'waiting-guest';
          if (room.host && room.host.readyState === WebSocket.OPEN) {
            room.host.send(JSON.stringify({ type: 'opponent-left', message: 'Guest disconnected' }));
          }
        }
      }
    });
  });

  // Attach Vite middleware for fast HMR and web serving
  const vite = await createViteServer({
    server: {
      middlewareMode: true,
      hmr: { server }
    },
    appType: 'spa'
  });

  server.on('request', vite.middlewares);

  server.listen(PORT, '0.0.0.0', () => {
    console.log(`
===========================================================
  🎮 FRUIT SLICE & PHYSICAL MOTION ARCADE (DUAL-PLAYER)
===========================================================
  ➜ Local Web App:     http://localhost:${PORT}/
  ➜ Network Link (LAN): http://${localIp}:${PORT}/
  ➜ Multiplayer Rooms: Ready on WebSocket (port ${PORT})
===========================================================
    `);
  });
}

start();
