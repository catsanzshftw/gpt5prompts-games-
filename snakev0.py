# Snake — classic rules, WASD, beeps/boops, PS1-ish vibes + Menu/Leaderboard/Trophies
# files = OFF | 60 FPS | walls = death | grow = +1 | no external assets
# Controls (play): WASD/Arrows = move, P = pause, R = restart, V = toggle PS1 vibes, Esc = back/quit

import pygame, random, sys, math, time, array, string

# ---------------------------- Config ---------------------------------
GRID_SIZE   = 20                 # pixels per cell
GRID_W      = 32                 # grid columns
GRID_H      = 24                 # grid rows
FPS         = 60
START_LEN   = 4
SNAKE_SPEED = 8                  # cells per second (logic tick)
BORDER_WALL = True               # True = die on wall (classic), False = wrap
PS1_WOBBLE  = 0.35               # screen wobble strength (0..1)
MAX_LEADERS = 10                 # top-N in session leaderboard
NAME_DEFAULT = "CAT"             # default initials for entry
# ---------------------------------------------------------------------

WIDTH, HEIGHT = GRID_W * GRID_SIZE, GRID_H * GRID_SIZE

# Init audio first for low latency
pygame.mixer.pre_init(22050, -16, 1, 256)
pygame.init()
pygame.display.set_caption("Snake — classic + PS1 nostalgia")
screen  = pygame.display.set_mode((WIDTH, HEIGHT))
clock   = pygame.time.Clock()
font    = pygame.font.SysFont("consolas", 20)
bigfont = pygame.font.SysFont("consolas", 36, bold=True)

try:
    pygame.mixer.init()
except pygame.error:
    pass  # keep going without sound if mixer fails

# Colors
BLACK=(12,12,12); DK=(24,24,24); LIT=(220,220,220)
GREEN=(56,188,72); RED=(220,48,64); YEL=(252,188,52); CYAN=(48,200,220)
BG=(16,16,18)

def tone(freq=440, ms=90, vol=0.4, shape="square"):
    """Generate a tone Sound without numpy. 16-bit mono, 22.05kHz."""
    if not pygame.mixer.get_init():
        class _Silent: 
            def play(self): pass
        return _Silent()
    sr = 22050
    n = max(1, int(sr * (ms/1000.0)))
    buf = array.array("h")
    amp = int(32767 * max(0.0, min(1.0, vol)))
    phase = 0.0
    inc = (freq / sr)
    attack = max(1,int(n*0.02)); release = max(1,int(n*0.08))
    for i in range(n):
        if shape == "square":
            s = 1.0 if (phase % 1.0) < 0.5 else -1.0
        elif shape == "tri":
            x = (phase % 1.0)
            s = 4.0*abs(x-0.5)-1.0
        else:
            s = math.sin(phase*2*math.pi)
        phase += inc
        a = 1.0
        if i < attack: a = i/attack
        if i > n-release: a = max(0.0, (n-i)/release)
        buf.append(int(amp * s * a))
    return pygame.mixer.Sound(buffer=buf.tobytes())

# UI / game sounds
SND_TURN    = tone(920, 28, 0.25, "square")
SND_EAT     = tone(320,120, 0.35, "square")
SND_DIE     = tone( 80,420, 0.5 , "tri")
SND_UI_MOVE = tone(660, 40, 0.25, "square")
SND_UI_SEL  = tone(420, 80, 0.35, "square")
SND_TROPHY  = tone(880,150, 0.40, "tri")

# Prebaked overlays for PS1 vibes
def make_dither_surface():
    d = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        for x in range((y//2)%2, WIDTH, 2):
            d.set_at((x,y), (0,0,0,24))
    return d
def make_scanlines():
    s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 3):
        pygame.draw.line(s, (0,0,0,28), (0,y), (WIDTH,y))
    return s
DITHER = make_dither_surface()
SCANLINES = make_scanlines()

def ps1_vibes(t):
    """Cheap PS1-ish look: overlay + slight affine wobble."""
    screen.blit(DITHER,(0,0))
    screen.blit(SCANLINES,(0,0))
    strip_h = 4
    wob = int(2 * PS1_WOBBLE * math.sin(t*6.0))
    for y in range(0, HEIGHT, strip_h):
        src = pygame.Rect(0, y, WIDTH, strip_h)
        off = wob if ((y//strip_h)&1)==0 else -wob
        screen.blit(screen, (off, y), src)

def text(s, x, y, c=LIT, center=False, shadow=True, f=font):
    img = f.render(s, True, c)
    pos = (x - (img.get_width()//2 if center else 0),
           y - (img.get_height()//2 if center else 0))
    if shadow:
        sh = f.render(s, True, DK); screen.blit(sh, (pos[0]+1, pos[1]+1))
    screen.blit(img, pos)

def grid_to_px(cell):
    x, y = cell
    return x*GRID_SIZE, y*GRID_SIZE, GRID_SIZE, GRID_SIZE

def rand_empty(exclude):
    while True:
        p = (random.randrange(GRID_W), random.randrange(GRID_H))
        if p not in exclude: return p

# ---------------------- App / Scenes / State -------------------------
STATE_MENU       = "menu"
STATE_PLAY       = "play"
STATE_GAMEOVER   = "gameover"
STATE_LEADER     = "leaderboard"
STATE_TROPHIES   = "trophies"
STATE_HOWTO      = "howto"
STATE_NAMEENTRY  = "nameentry"

MENU_ITEMS = ["Start", "Leaderboard", "Trophies", "How To", "Quit"]

TROPHY_DEFS = [
    ("FIRST_BITE",  "First Bite",      "Eat your first snack"),
    ("EAT_5",       "Snack Attack",    "Eat 5 snacks"),
    ("EAT_10",      "Gourmet",         "Eat 10 snacks"),
    ("SPEED_12",    "Zoomer",          "Reach speed 12.0+"),
    ("LEN_20",      "Long Boi",        "Reach length 20"),
    ("ZEN_60",      "Just Vibes",      "Survive 60 seconds"),
]

def new_app():
    return {
        "state": STATE_MENU,
        "menu_idx": 0,
        "leaderboard": [],     # list of dicts: {"name":str,"score":int,"speed":float,"time":float}
        "vibes": True,
        "popups": [],          # list of (msg, t_start)
        "trophies": {k: False for k,_,_ in TROPHY_DEFS},
        "namebuf": list(NAME_DEFAULT),
        "game": None,
    }

APP = new_app()

def restart_game(seed=None):
    random.seed(seed or time.time_ns())
    sx, sy = GRID_W//2, GRID_H//2
    snake = [(sx - i, sy) for i in range(START_LEN)]  # rightward
    direction = (1,0)
    pending = []
    food = rand_empty(set(snake))
    return {
        'snake': snake, 'direction': direction, 'pending': pending,
        'food': food, 'score': 0, 'speed': SNAKE_SPEED, 'alive': True,
        'paused': False, 'time_accum': 0.0, 'lifetime': 0.0, 'ate': 0
    }

def unlock_trophy(tid):
    if not APP["trophies"].get(tid, False):
        APP["trophies"][tid] = True
        APP["popups"].append(("TROPHY UNLOCKED — " + next(n for k,n,_ in TROPHY_DEFS if k==tid), time.perf_counter()))
        SND_TROPHY.play()

def check_trophies(G):
    if G['score'] >= 1: unlock_trophy("FIRST_BITE")
    if G['score'] >= 5: unlock_trophy("EAT_5")
    if G['score'] >=10: unlock_trophy("EAT_10")
    if G['speed'] >= 12.0: unlock_trophy("SPEED_12")
    if len(G['snake']) >= 20: unlock_trophy("LEN_20")
    if G['lifetime'] >= 60.0: unlock_trophy("ZEN_60")

def push_score(name, score, speed, tsec):
    APP["leaderboard"].append({"name":name, "score":score, "speed":speed, "time":tsec})
    APP["leaderboard"].sort(key=lambda r:(-r["score"], r["time"]))
    if len(APP["leaderboard"]) > MAX_LEADERS:
        APP["leaderboard"] = APP["leaderboard"][:MAX_LEADERS]

# ---------------------------- Gameplay --------------------------------
def step_logic(G, dt):
    if not G['alive'] or G['paused']: 
        return
    G['lifetime'] += dt
    G['time_accum'] += dt
    step_dt = 1.0/max(1,G['speed'])
    while G['time_accum'] >= step_dt:
        G['time_accum'] -= step_dt
        # queued turns: take first valid (no instant reversal)
        if G['pending']:
            nx, ny = G['pending'].pop(0)
            if (nx, ny) != (-G['direction'][0], -G['direction'][1]):
                G['direction'] = (nx, ny)
                SND_TURN.play()
        hx, hy = G['snake'][0]
        dx, dy = G['direction']
        nx, ny = hx+dx, hy+dy

        if BORDER_WALL:
            if nx < 0 or nx >= GRID_W or ny < 0 or ny >= GRID_H:
                G['alive'] = False; SND_DIE.play(); return
        else:
            nx %= GRID_W; ny %= GRID_H

        new_head = (nx, ny)
        if new_head in G['snake']:
            G['alive'] = False; SND_DIE.play(); return

        G['snake'].insert(0, new_head)

        if new_head == G['food']:
            G['score'] += 1
            G['ate'] += 1
            G['speed'] = min(18, G['speed'] + 0.20)  # gentle speed-up
            G['food'] = rand_empty(set(G['snake']))
            SND_EAT.play()
        else:
            G['snake'].pop()

        check_trophies(G)

def draw_grid_bg():
    screen.fill(BG)
    gsurf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    gl = (255,255,255,28)
    for x in range(0, WIDTH, GRID_SIZE):
        pygame.draw.line(gsurf, gl, (x,0), (x,HEIGHT))
    for y in range(0, HEIGHT, GRID_SIZE):
        pygame.draw.line(gsurf, gl, (0,y), (WIDTH,y))
    screen.blit(gsurf,(0,0))

def draw_snake_and_food(G):
    # food (red)
    x,y,w,h = grid_to_px(G['food'])
    pygame.draw.rect(screen, RED, (x+2,y+2,w-4,h-4), border_radius=4)
    # snake (bright head + green body)
    for i, cell in enumerate(G['snake']):
        col = LIT if i==0 else GREEN
        x,y,w,h = grid_to_px(cell)
        pygame.draw.rect(screen, col, (x+1,y+1,w-2,h-2), border_radius=4)

def draw_popups(t):
    # PS1 trophy popups (top-left)
    ttl = 2.4
    dy = 0
    now = t
    keep = []
    for msg, ts in APP["popups"]:
        a = (now - ts) / ttl
        if a < 1.0:
            y = 12 + dy
            # slide in/out
            slide = int( max(0, 40*(1.0-min(a*3,1.0))) )
            alpha = 255 if a < 0.85 else int(255*(1.0 - (a-0.85)/0.15))
            box = pygame.Surface((min(360, WIDTH-20), 26), pygame.SRCALPHA)
            box.fill((0,0,0,160))
            screen.blit(box, (12 - slide, y))
            text(msg, 20 - slide, y+6, c=YEL, shadow=False)
            dy += 30
            keep.append((msg, ts))
    APP["popups"] = keep

# --------------------------- Scene: Menu -------------------------------
def draw_menu(t):
    draw_grid_bg()
    # Title
    text("S N A K E", WIDTH//2, 46, c=LIT, center=True, f=bigfont)
    text("PS1 Nostalgia Edition", WIDTH//2, 78, c=CYAN, center=True)
    # Items
    for i, item in enumerate(MENU_ITEMS):
        sel = (i == APP["menu_idx"])
        c = YEL if sel else LIT
        text(("> " if sel else "  ") + item, WIDTH//2 - 40, 120 + i*26, c=c, shadow=sel)
    # Footer
    text("V: vibes {}   Esc: quit".format("ON" if APP["vibes"] else "OFF"), 8, HEIGHT-24, c=LIT, shadow=False)
    if APP["vibes"]: ps1_vibes(t)

def handle_menu(events):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_q):
                pygame.quit(); sys.exit(0)
            elif e.key in (pygame.K_UP, pygame.K_w):
                APP["menu_idx"] = (APP["menu_idx"] - 1) % len(MENU_ITEMS); SND_UI_MOVE.play()
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                APP["menu_idx"] = (APP["menu_idx"] + 1) % len(MENU_ITEMS); SND_UI_MOVE.play()
            elif e.key == pygame.K_v:
                APP["vibes"] = not APP["vibes"]; SND_UI_MOVE.play()
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                SND_UI_SEL.play()
                sel = MENU_ITEMS[APP["menu_idx"]]
                if sel == "Start":
                    APP["game"] = restart_game()
                    APP["state"] = STATE_PLAY
                elif sel == "Leaderboard":
                    APP["state"] = STATE_LEADER
                elif sel == "Trophies":
                    APP["state"] = STATE_TROPHIES
                elif sel == "How To":
                    APP["state"] = STATE_HOWTO
                elif sel == "Quit":
                    pygame.quit(); sys.exit(0)

# ------------------------ Scene: Leaderboard ---------------------------
def draw_leaderboard(t):
    draw_grid_bg()
    text("LEADERBOARD (session)", WIDTH//2, 40, c=YEL, center=True, f=bigfont)
    if not APP["leaderboard"]:
        text("No scores yet. Play a round!", WIDTH//2, HEIGHT//2, c=LIT, center=True)
    else:
        y = 90
        for i, r in enumerate(APP["leaderboard"]):
            line = f"{i+1:>2}. {r['name']:<3}   Score {r['score']:<3}   Spd {r['speed']:.1f}   {int(r['time'])}s"
            text(line, 40, y, c=LIT, shadow=False); y += 26
    text("Esc / M: menu    (Session-only; files=OFF)", 8, HEIGHT-24, c=LIT, shadow=False)
    if APP["vibes"]: ps1_vibes(t)

def handle_leaderboard(events):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_RETURN, pygame.K_SPACE):
                APP["state"] = STATE_MENU; SND_UI_SEL.play()

# ------------------------- Scene: Trophies -----------------------------
def draw_trophies(t):
    draw_grid_bg()
    text("TROPHIES", WIDTH//2, 40, c=YEL, center=True, f=bigfont)
    y = 90
    for tid, name, desc in TROPHY_DEFS:
        got = APP["trophies"][tid]
        c = CYAN if got else LIT
        prefix = "[✓]" if got else "[ ]"
        text(f"{prefix} {name} — {desc}", 40, y, c=c, shadow=False); y += 26
    text("Esc / M: menu", 8, HEIGHT-24, c=LIT, shadow=False)
    if APP["vibes"]: ps1_vibes(t)

def handle_trophies(events):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_RETURN, pygame.K_SPACE):
                APP["state"] = STATE_MENU; SND_UI_SEL.play()

# --------------------------- Scene: How To -----------------------------
def draw_howto(t):
    draw_grid_bg()
    text("HOW TO PLAY", WIDTH//2, 40, c=YEL, center=True, f=bigfont)
    lines = [
        "WASD / Arrows: move   •   P: pause   •   R: restart",
        "V: PS1 vibes   •   Esc: back/quit",
        "Eat red snacks to grow. Walls are deadly. Score +1 per snack.",
        "Session-only leaderboard (no disk writes).",
        "Trophies pop up mid-run. Good luck!"
    ]
    y = 96
    for ln in lines:
        text(ln, WIDTH//2, y, c=LIT, center=True, shadow=False); y += 26
    text("Esc / M: menu", 8, HEIGHT-24, c=LIT, shadow=False)
    if APP["vibes"]: ps1_vibes(t)

def handle_howto(events):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_RETURN, pygame.K_SPACE):
                APP["state"] = STATE_MENU; SND_UI_SEL.play()

# ------------------------ Scene: Name Entry ----------------------------
def draw_nameentry(t, score, speed, life):
    draw_grid_bg()
    text("NEW HIGH SCORE!", WIDTH//2, 40, c=YEL, center=True, f=bigfont)
    text(f"Score {score}   Speed {speed:.1f}   {int(life)}s", WIDTH//2, 78, c=LIT, center=True)
    # Name buffer
    shown = "".join(APP["namebuf"])
    caret = "_" if int(t*2)%2==0 else " "
    text("Enter initials:", WIDTH//2, 120, c=LIT, center=True)
    text(shown + caret, WIDTH//2, 152, c=CYAN, center=True, f=bigfont)
    text("Type letters, Backspace, Enter to save   Esc to cancel", WIDTH//2, HEIGHT-40, c=LIT, center=True)
    if APP["vibes"]: ps1_vibes(t)

def handle_nameentry(events, score, speed, life):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                APP["state"] = STATE_MENU; SND_UI_SEL.play()
            elif e.key == pygame.K_BACKSPACE:
                if APP["namebuf"]:
                    APP["namebuf"].pop(); SND_UI_MOVE.play()
            elif e.key == pygame.K_RETURN:
                name = ("".join(APP["namebuf"]) or NAME_DEFAULT)[:8]
                push_score(name, score, speed, life); SND_UI_SEL.play()
                APP["state"] = STATE_MENU
            else:
                ch = e.unicode.upper()
                if ch in string.ascii_uppercase + string.digits + "-_":
                    if len(APP["namebuf"]) < 8:
                        APP["namebuf"].append(ch); SND_UI_MOVE.play()

# --------------------------- Scene: Play -------------------------------
def handle_play(events, G):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                APP["state"] = STATE_MENU; SND_UI_SEL.play(); return
            if k == pygame.K_r:
                d_pause = G['paused']
                APP["game"] = restart_game(); APP["game"]['paused'] = d_pause; return
            if k == pygame.K_p:
                G['paused'] = not G['paused']
            if k == pygame.K_v:
                APP["vibes"] = not APP["vibes"]
            # movement (WASD + arrows)
            if   k in (pygame.K_UP,    pygame.K_w): G['pending'].append((0,-1))
            elif k in (pygame.K_DOWN,  pygame.K_s): G['pending'].append((0, 1))
            elif k in (pygame.K_LEFT,  pygame.K_a): G['pending'].append((-1,0))
            elif k in (pygame.K_RIGHT, pygame.K_d): G['pending'].append((1, 0))

def draw_play(t, G):
    draw_grid_bg()
    draw_snake_and_food(G)
    text(f"Score {G['score']}  Speed {G['speed']:.1f}  Time {int(G['lifetime'])}s  FPS {int(clock.get_fps())}",
         8, 6, c=LIT, shadow=False)
    if not G['alive']:
        text("GAME OVER", WIDTH//2, HEIGHT//2-28, c=LIT, center=True, f=bigfont)
        text("Enter: save score   R: restart   M/Esc: menu", WIDTH//2, HEIGHT//2+6, c=LIT, center=True)
    if G['paused'] and G['alive']:
        text("PAUSED", WIDTH//2, HEIGHT//2, c=LIT, center=True, f=bigfont)
    draw_popups(t)
    if APP["vibes"]: ps1_vibes(t)

def handle_gameover_keys(events, G):
    for e in events:
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit(0)
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_m, pygame.K_ESCAPE):
                APP["state"] = STATE_MENU; SND_UI_SEL.play()
            elif e.key == pygame.K_r:
                APP["game"] = restart_game(); SND_UI_SEL.play()
                APP["state"] = STATE_PLAY
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                SND_UI_SEL.play()
                APP["state"] = STATE_NAMEENTRY

# ------------------------------ Main ----------------------------------
def main():
    t0 = time.perf_counter()
    APP["state"] = STATE_MENU
    while True:
        dt = clock.tick(FPS) / 1000.0
        t = time.perf_counter() - t0
        events = pygame.event.get()

        if APP["state"] == STATE_MENU:
            handle_menu(events); draw_menu(t)

        elif APP["state"] == STATE_LEADER:
            handle_leaderboard(events); draw_leaderboard(t)

        elif APP["state"] == STATE_TROPHIES:
            handle_trophies(events); draw_trophies(t)

        elif APP["state"] == STATE_HOWTO:
            handle_howto(events); draw_howto(t)

        elif APP["state"] == STATE_PLAY:
            G = APP["game"]
            handle_play(events, G)
            if G['alive']:
                step_logic(G, dt)
            else:
                # listen for save/restart/menu while showing gameover text
                handle_gameover_keys(events, G)
            draw_play(t, G)

        elif APP["state"] == STATE_NAMEENTRY:
            G = APP["game"]
            handle_nameentry(events, G['score'], G['speed'], G['lifetime'])
            draw_nameentry(t, G['score'], G['speed'], G['lifetime'])

        pygame.display.flip()

if __name__ == "__main__":
    main()
