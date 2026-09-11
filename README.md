# BLOCKHAVEN

A complete block-world game platform written in **pure Python 3 (standard
library only)** and **vanilla JavaScript**. It has two halves:

* **The UI** — the website: accounts, profiles with a live 3D character, an
  avatar editor, an item market with Unusual rolls, an inventory bound to your
  account, friends/followers/posts/comments/messages, a world browser and an
  administrator dashboard.
* **The Game View** — press **Load** on a world and you drop into a first- or
  third-person block shooter running in your browser, served from the same
  port on its own sub-page (`/burger_tycoon`, `/capture_the_flag`,
  `/fortress_team_2`).

No frameworks, no build step, no `pip install`, no asset files. Every texture,
sound, mesh and map is generated at runtime.

```
python3 main.py
```

Then open **http://<your-ip>:8972/** on any machine on your network.

---

## Quick start

```bash
python3 main.py                 # website + all three game hosts on port 8972
python3 main.py --port 9000     # somewhere else
python3 main.py --no-games      # website only
python3 main.py --reset         # wipe the database and re-seed
python3 main.py --debug         # verbose tracebacks, no static caching
```

Requirements: Python 3.9+ and a browser with WebGL. That is the whole list.

### Accounts created on first run

| Account | Password | Notes |
| --- | --- | --- |
| `admin_system` | `passman69` | Administrator. Can open `/admin-dashboard`. Owns two Unusual hats. |
| `admin_test` | `passman69` | Ordinary player used to demonstrate the Unusual system (Unusual Propeller Beanie + Unusual Mohawk Spikes). |
| `builderman_x`, `RetroKid2007`, `BlockSmith`, `NoobSlayer99`, `PixelPatty`, `CartPusher`, `FlagRunner`, `GrillMaster` | `blockhaven` | Demo players so the social features have something to show. |

Everyone else who registers starts with **2,000 credits**, a Basic Pistol, a
Basic Shotgun and a Basic Stick.

---

## The worlds

| World | URL | Mode | Round size |
| --- | --- | --- | --- |
| **Burger Tycoon** | `/burger_tycoon` | Endless tycoon, 8 claimable plots, 4 players per plot | 24 |
| **Capture The Flag** | `/capture_the_flag` | First to 3 captures, then a shuffle vote | 16 |
| **Fortress Team 2** | `/fortress_team_2` | Payload push, teams swap each round, first to 3 round wins | 24 |

When a world's instance fills up the host opens another one, so the browser can
legitimately read "2 instances — 30 players" for a world whose round size is
24.

### Burger Tycoon
Claim one of eight plots, then grow a flat plate into a burger empire: floor,
grill, counter, walls, fry station, roof, neon sign, second grill, seating,
drive-thru, walk-in freezer, second floor, rooftop garden and finally the
Golden Arches. Idle machines drip coins into your plot's bank; the fry station
and freezer are hands-on (stand there and press **E**). Walk over the green
collector pad to bank the coins. Plot coins are a scratch currency that never
touches your site credits. When the last member of a crew leaves, the plot
resets to bare ground and the next player to arrive starts fresh.

### Capture The Flag
Crossroads-style: two stone forts across a green valley, a central arch, four
hill outposts and two wooden bridges. Grab the enemy flag, run it back to your
own (which must be at home), first to three wins. Killing a carrier drops the
flag; touching your own dropped flag returns it.

### Fortress Team 2
Dustworks: a desert payload map. Blue pushes the bomb cart along the rails
toward Red's pit; stand near it to move it, stand near it as Red to block it.
Three checkpoints add time and lock the cart's rollback. Teams swap ends after
each round, and the match ends at three round wins.

---

## Controls

| Key | Action |
| --- | --- |
| `W A S D` | Move |
| `Space` | Jump |
| `Shift` | Walk slowly |
| Mouse | Look / fire |
| `1`–`5` | Hotbar slots |
| `R` | Reload |
| `E` | Interact (tycoon buttons, machines, plot claiming) |
| `P` | Toggle first / third person |
| `Y` | Chat &nbsp;&nbsp; `U` Team chat |
| `Tab` | Scoreboard |
| `Esc` | Pause menu → settings, key bindings, quit to profile |

While the chat box is open every other binding is ignored so you can type
freely. **Double-click a name** in chat or on the scoreboard to open that
player's profile in a new tab.

---

## Architecture

```
main.py                    entry point: seeds the DB, starts the web server and
                           supervises one game-host process per world
app/
  config.py                ports, tunables, secrets
  security.py              PBKDF2 passwords, HMAC tickets, CSRF, input cleaning
  db.py                    SQLite (WAL) with a thread-local connection pool
  bootstrap.py             idempotent first-run seeding + catalogue sync
  webapp.py                routing, sessions, CSRF, websocket backend resolver
  http/
    server.py              threaded HTTP/1.1 server + websocket reverse proxy
    router.py              Request/Response and the pattern router
    templating.py          a small compiling template engine
  models/
    catalog.py             THE item catalogue (hats, faces, clothing, weapons,
                           tiers and Unusual particle effects)
    users.py avatars.py inventory.py economy.py market.py worlds.py
  social/
    friends.py follows.py posts.py comments.py messages.py feed.py
  views/                   one module per area of the site
  game/
    supervisor.py          spawns/restarts the per-world host processes
    host.py                a game host: accepts proxied websockets, runs ticks
    instance.py            the shared engine: players, movement validation,
                           hit detection, damage, chat, rounds, shuffle votes
    protocol.py            RFC 6455 websocket implementation
    registry.py            live host/instance stats for the website
    maps/                  builder.py + the three map generators
    worlds/                capture_the_flag.py fortress_team2.py burger_tycoon.py
static/
  js/engine/               WebGL renderer, geometry, textures, avatar rig,
                           particles, synthesised audio
  js/game/                 client, netcode, physics, HUD, settings
  js/ui/                   site behaviour, 3D thumbnails, per-page scripts
  css/                     site.css (Web 1.0 chrome) and game.css (HUD)
templates/                 server-rendered pages
tools/                     dev server helper, bot client, test suites
```

### Processes and ports

Everything the network sees is on **one port (8972)**. Internally:

```
browser ──HTTP──▶ web server (main process, port 8972)
        └─WS────▶ web server ──raw TCP──▶ game host process (127.0.0.1:899x)
```

The web server validates your session, mints a short-lived HMAC-signed join
ticket containing your avatar, and then reverse-proxies the websocket byte for
byte into the world's host process. Each world therefore simulates on its own
CPU core, and a busy match cannot slow the website down. Hosts push a heartbeat
(instances, players, kills, visits) back to the web server every 2.5 seconds,
and the supervisor restarts any host that dies.

### Server authority

* **Credits, items and inventory.** Clients send intents ("buy `hat_crown`"),
  never values. Prices come from the server-side catalogue, the Unusual roll
  happens on the server, and the charge plus the grant happen in one SQLite
  transaction with an append-only ledger.
* **Equipping.** Every slot change is checked against the inventory row's owner
  and the item's slot, so a forged request cannot wear something you do not
  own.
* **Movement.** The client simulates its own character for responsiveness, but
  the server caps distance per tick, rejects impossible climbs, snaps back
  players that never touch the ground, and its copy of your position is the one
  everybody else — and every hit test — sees.
* **Shooting.** Fire rate, ammunition, range, spread and line-of-sight are all
  resolved server-side from the server's own copy of the world.
* **Admin actions** run through exactly the same code paths (`economy.adjust`,
  `inventory.grant`) as normal play, so the dashboard cannot create state the
  game itself could not.

---

## Items, tiers and Unusuals

The catalogue lives in `app/models/catalog.py` and is mirrored into the
database on boot — adding a hat is one dict and a restart.

* **Normal** — yellow. Every item ships this way.
* **Unusual** — purple, with a permanent particle effect. Rolled at **0.5% on
  hat purchases only**. Twelve effects ship: Burning Flames, Scorching Flames,
  Cloud Nine, Starstruck, Void Mist, Frostbite, Circuitry, Bubbly, Ember Storm,
  Sunbeam, Toxic Haze and Static Charge.

Effects render on the hat in every world and on every avatar preview across the
site. Each owned copy of an item is its own database row, so an Unusual is a
specific copy with a serial number — not a flag on an item type.

## Avatars

Six independently colourable body parts (head, torso, both arms, both legs),
plus `face`, `hat`, `shirt`, `pants` and `back` cosmetic slots and five
**usable** hotbar slots. One rig drives the profile preview, the editor, the
market thumbnails and the game itself, so anything added to the catalogue shows
up everywhere at once.

---

## Development tools

```bash
tools/devserver.sh start --port 8972    # start/stop/restart/log helper
tools/sitetests.py                      # HTTP-level tests for the website
tools/checkmaps.py                      # static map validation
tools/simclient.py --world capture_the_flag --bots 4 --seconds 20
tools/gametests.py                      # full gameplay test suite
tools/gametests.py ctf combat tycoon    # or a subset
```

`BLOCKHAVEN_TYCOON_COINS=200000 python3 main.py` starts every Burger Tycoon
crew with a large float, which is handy when you want to look at a finished
restaurant without building one first.

`gametests.py` drives real websocket clients against the running servers and
asserts on what the servers broadcast: flag captures, damage and the kill feed,
fire-rate clamping, movement correction, cart pushing, tycoon buying and
income, instance overflow, visit accounting and the end-of-round shuffle vote.

## Data

Everything lives in `data/blockhaven.sqlite3` (WAL mode). Delete it, or run
with `--reset`, to start over. `data/secret.key` holds the HMAC secret used for
sessions and join tickets.
