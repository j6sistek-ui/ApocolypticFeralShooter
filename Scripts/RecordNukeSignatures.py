"""RecordNukeSignatures.py - volatile NUKE power-up signature looks, recorded as seamless looping GIFs (2026-10-31).

Owner brief: the Nuke must read as a VOLATILE NUCLEAR DEVICE (sparks, tracers, micro explosions), never as gas / toxic
waste: no fog, no haze, no yellow-green. Effects only on and around the item; the trefoil and the real texture stay
readable; judged by animation.

Two modes in one file:
  * inside Unreal (GPU, -RenderOffscreen):  UnrealEditor.exe AFS.uproject -RenderOffscreen -unattended -nosplash
        -ResX=1280 -ResY=720 -DisablePlugins=NwiroIntegrationKit -stdout -FullStdOutLogOutput
        -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/RecordNukeSignatures.py
    loads L_PowerUpShowcase, starts PIE with the fixed 1/30 s step (same boot as Scripts/RecordPowerUpGifs.py), spawns
    the Nuke ALONE and records each look from a ~2 m camera (plus far looks from ~9 m).
  * system Python (PIL):  python M:/UnrealProjects/AFS/Scripts/RecordNukeSignatures.py
    assembles the frames into GIFs (one per look, a labelled grid, a far-camera strip); reuses the encoder of
    Scripts/AssemblePowerUpGifs.py (imported, not changed).

Everything moving is SCRIPT-DRIVEN and STATELESS: every look is a list of events (spark bursts, flash-pops, smoke
puffs, tracers, ticks) at fixed times inside one loop; each frame is computed from the loop phase alone (ballistic
particles evaluated analytically), so frame 36 == frame 0 and the GIF loops without a seam. Particles are the
harness's stretched glowing spheres (M_PU_GlowAdditive) but each has its own dynamic instance, so it cools from
white-hot to orange-red as it ages. Smoke puffs use a tiny translucent master made here
(/Game/HoverPrototype/PowerUps/Styles/Nuke/M_PU_NukeSmoke, project-owned). Real Niagara is used only where a look
says 'niagara' (pooled actors retriggered on the event times; vendor systems used as-is, user parameters set on the
component only, assets never edited) and in the optional bench (NUKE_BENCH=1).

Env: NUKE_LOOKS=N1,N2,N3,N4,N5,N6   NUKE_FAR=N5,N6   NUKE_BENCH=0|1   GIF_FPS=15  GIF_LOOP=2.4  NUKE_WARM=8
     NUKE_SETTLE=2.6 (>= one loop, so auto exposure has seen the flashes)  PU2_EV (exposure bias override)
Out: D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs_nuke/frames/<Key>[_far]/f000.png ... + frames/record.json
     D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs_nuke/nuke_<N>_<Name>.gif, nuke_grid.gif, nuke_far.gif,
     assemble.json
"""
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path

try:
    import unreal as u
except ImportError:  # system Python: assemble mode
    u = None

ROOT = Path('D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs_nuke')
OUT = ROOT / 'frames'
FPS = int(os.environ.get('GIF_FPS', '15'))
LOOP_S = float(os.environ.get('GIF_LOOP', '2.4'))
TICK = 1.0 / 30.0
NT = int(round(LOOP_S / TICK))            # ticks per loop (72)
EVERY = int(round(30 / FPS))
NFRAMES = NT // EVERY                     # 36

# ----------------------------------------------------------------------------------------------------------------
# palette (nuclear orange-white / hot yellow; nothing green)

WHITE = (1.0, 0.93, 0.82)
HOTY = (1.0, 0.72, 0.28)
ORANGE = (1.0, 0.40, 0.06)
DEEP = (0.75, 0.12, 0.02)
NUKE_C = (1.0, 0.42, 0.08)
KEY_C = (1.0, 0.70, 0.48)        # mix of the nuke colour and a warm white: keeps the real texture readable
TEMP = ((0.0, WHITE), (0.22, HOTY), (0.55, ORANGE), (1.0, DEEP))


def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def temp(f):
    f = max(0.0, min(1.0, f))
    for i in range(len(TEMP) - 1):
        f0, c0 = TEMP[i]
        f1, c1 = TEMP[i + 1]
        if f <= f1:
            return lerp3(c0, c1, (f - f0) / (f1 - f0))
    return TEMP[-1][1]


def hsh(*a):
    """Deterministic 0..1 hash of integers (per-frame crackle / twinkle / jitter)."""
    h = 2166136261
    for x in a:
        h = ((h ^ (int(x) & 0xffffffff)) * 16777619) & 0xffffffff
        h ^= h >> 13
        h = (h * 1274126177) & 0xffffffff
    return (h & 0xffffff) / float(0x1000000)


# ----------------------------------------------------------------------------------------------------------------
# looks as data: an event list per look (times in [0, LOOP_S)), built from the item's size

LOOK_META = {
    'N1': ('SparkCrackle', 'Spark Crackle'),
    'N2': ('MicroDetonations', 'Micro-Detonations'),
    'N3': ('TracerStreaks', 'Tracer Streaks'),
    'N4': ('UnstableCore', 'Unstable Core'),
    'N5': ('TickingBomb', 'Ticking Bomb'),
    'N6': ('Combo', 'Combo: Tick + Pops + Tracers'),
}


class Geo:
    """The Nuke as a simple surface of revolution (pivot at bottom centre). H, R from the mesh bounds."""

    def __init__(self, H=45.0, R=14.0, toward=(1.0, 0.0), right=(0.0, 1.0)):
        self.H, self.R = H, R
        self.B = toward      # horizontal unit vector item -> camera
        self.RT = right      # screen right

    def radius(self, zr):
        if zr < 0.08:
            return 0.86
        if zr < 0.74:
            return 0.9 + 0.1 * math.sin(math.pi * (zr - 0.08) / 0.66)
        if zr < 0.83:
            return 0.70
        return 0.60

    def dir(self, phi):
        c, s = math.cos(phi), math.sin(phi)
        return (c * self.B[0] + s * self.RT[0], c * self.B[1] + s * self.RT[1])

    def point(self, rng, zr=None, front=True, spread=55.0, out=1.0):
        """A point just off the casing and its outward normal (world axes, relative to the item's base)."""
        phi = math.radians(max(-120.0, min(120.0, rng.gauss(0.0, spread)))) if front else rng.uniform(-math.pi, math.pi)
        if zr is None:
            zr = rng.uniform(0.1, 0.8)
        d = self.dir(phi)
        r = self.R * self.radius(zr) + out
        nz = 0.0 if zr < 0.83 else 0.35
        if zr > 0.95:   # the cap's top
            r *= rng.uniform(0.0, 0.8)
            nz = 1.0
        p = (d[0] * r, d[1] * r, zr * self.H)
        n = norm((d[0], d[1], nz))
        return p, n

    SEAMS = (0.08, 0.30, 0.52, 0.74, 0.83, 0.97)

    def seam_point(self, rng, cap_bias=0.3):
        if rng.random() < cap_bias:
            zr = rng.choice((0.83, 0.97, 0.97))
        else:
            zr = rng.choice(self.SEAMS[:4]) + rng.uniform(-0.015, 0.015)
        return self.point(rng, zr, spread=60.0)


def norm(v):
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def cone(rng, n, ang_deg, up=0.0):
    """A random unit vector within ang_deg of n, biased upward by `up`."""
    a = math.radians(ang_deg)
    while True:
        r = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
        if 0.01 < r[0] ** 2 + r[1] ** 2 + r[2] ** 2 <= 1.0:
            break
    r = norm(r)
    k = math.tan(a)
    return norm((n[0] + r[0] * k, n[1] + r[1] * k, n[2] + r[2] * k + up))


def irregular_times(rng, rate, min_gap=0.05, cluster=0.0, cluster_gap=(0.04, 0.09), avoid=(), avoid_w=0.0):
    out = []
    t = rng.uniform(0.0, 1.0 / rate)
    while t < LOOP_S:
        if all(abs(((t - a + LOOP_S / 2) % LOOP_S) - LOOP_S / 2) > avoid_w for a in avoid):
            out.append(t)
            if rng.random() < cluster:
                t2 = t + rng.uniform(*cluster_gap)
                if t2 < LOOP_S:
                    out.append(t2)
                    t = t2
        t += max(min_gap, rng.expovariate(rate))
    return out


# particle constructors ------------------------------------------------------------------------------------------

def P_spark(te, p, v, life, width, I=45.0, g=-900.0, drag=1.0, streak=0.03, maxlen=10.0, twinkle=True, cool=1.0):
    return {'k': 'glow', 'te': te, 'p': p, 'v': v, 'life': life, 'w': width, 'I': I, 'g': g, 'drag': drag,
            'streak': streak, 'maxlen': maxlen, 'twinkle': twinkle, 'cool': cool}


def P_flash(te, p, s0, s1, life, I=80.0, power=2.2, vel=(0, 0, 0)):
    return {'k': 'flash', 'te': te, 'p': p, 'v': vel, 'life': life, 's0': s0, 's1': s1, 'I': I, 'g': 0.0, 'drag': 0.0,
            'power': power}


def P_glint(te, c, d, l0, l1, life, width=0.6, I=60.0):
    """A stationary radial streak from c along d (a star-shaped flash ray), growing from l0 to l1 cm."""
    return {'k': 'glint', 'te': te, 'p': c, 'v': (0, 0, 0), 'dir': d, 'l0': l0, 'l1': l1, 'life': life, 'w': width, 'I': I,
            'g': 0.0, 'drag': 0.0}


def star(rng, te, c, n, count, l=(4, 10), life=0.07, width=0.6, I=70.0, ang=70, G=None):
    if G is None:
        return [P_glint(te, c, cone(rng, n, ang, 0.0), l[0] * 0.4, rng.uniform(*l), life, width, I) for _ in range(count)]
    out = []
    a0 = rng.uniform(0, 2 * math.pi)
    for i in range(count):      # rays spread around the screen plane (right / up), tipped a little along the normal
        a = a0 + 2 * math.pi * (i + rng.uniform(-0.3, 0.3)) / count
        d = norm((math.cos(a) * G.RT[0] + 0.35 * n[0], math.cos(a) * G.RT[1] + 0.35 * n[1], math.sin(a) + 0.35 * n[2]))
        out.append(P_glint(te, c, d, l[0] * 0.4, rng.uniform(*l), life, width, I))
    return out


def P_smoke(te, p, s0, s1, life, opacity=0.75, vel=(0, 0, 25), glow=2.0):
    return {'k': 'smoke', 'te': te, 'p': p, 'v': vel, 'life': life, 's0': s0, 's1': s1, 'op': opacity, 'g': 0.0,
            'drag': 2.0, 'glow': glow}


def spark_burst(rng, te, p, n, count, speed=(140, 340), ang=40, up=0.6, life=(0.35, 0.75), width=(0.55, 0.85), **kw):
    out = []
    for _ in range(count):
        d = cone(rng, n, ang, up)
        s = rng.uniform(*speed)
        t0 = te + rng.uniform(0.0, 0.02)
        out.append(P_spark(t0, p, (d[0] * s, d[1] * s, d[2] * s), rng.uniform(*life), rng.uniform(*width), **kw))
    return out


def ring_burst(rng, te, center, count, speed=(260, 420), up=0.15, life=(0.3, 0.5), width=(0.6, 0.85), r0=15.0, **kw):
    """A horizontal ring of sparks thrown outward from the casing (in the air, nothing on the ground)."""
    out = []
    ph = rng.uniform(0, 2 * math.pi)
    for i in range(count):
        a = ph + 2 * math.pi * i / count + rng.uniform(-0.12, 0.12)
        d = norm((math.cos(a), math.sin(a), up + rng.uniform(-0.08, 0.12)))
        s = rng.uniform(*speed)
        p = (center[0] + math.cos(a) * r0, center[1] + math.sin(a) * r0, center[2])
        out.append(P_spark(te, p, (d[0] * s, d[1] * s, d[2] * s), rng.uniform(*life), rng.uniform(*width), **kw))
    return out


def addv(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)


# look builders: return {'parts': [...], 'events': [...], 'base': {...}} -----------------------------------------
#   events: {'te', 'core': (amp, tau) seam/emblem white-hot boost, 'light': (amp, tau) core light spike,
#            'pop': (amp, tau, pos) a moving pop light, 'swell': (amp, attack, release), 'shudder': (cm, tau),
#            'niagara': (system, scale, pos)}
#   base:   seam/emblem glow levels, light levels, crackle, haze

BASE = {'seam': 1.6, 'emblem': 1.1, 'rim': 0.5, 'key': 3.0, 'core': 1.2, 'crackle': 0.0, 'haze': False,
        'jitter': 0.0, 'emblem_pulse': 0.0}


def look_N1(G, seed=101):
    rng = random.Random(seed)
    parts, events = [], []
    for te in irregular_times(rng, 4.2, min_gap=0.07, cluster=0.4):
        p, n = G.seam_point(rng)
        parts += spark_burst(rng, te, p, n, rng.randint(6, 13))
        parts.append(P_flash(te, addv(p, n, 0.5), 1.2, 3.6, 0.08, I=70))
        lp = addv(p, n, 5)
        lp = (lp[0], lp[1], max(lp[2], 0.35 * G.H))
        events.append({'te': te, 'light': (7.0, 0.06), 'core': (3.5, 0.08), 'pop': (3.0, 0.05, lp)})
    # low-level dribble between the bursts: single sparks off the seams
    for te in irregular_times(rng, 9.0, min_gap=0.04):
        p, n = G.seam_point(rng, 0.2)
        parts += spark_burst(rng, te, p, n, rng.randint(1, 2), speed=(80, 200), life=(0.25, 0.5), width=(0.45, 0.6), I=30)
    base = dict(BASE, seam=2.4, emblem=1.1, crackle=0.55, core=1.5)
    return {'parts': parts, 'events': events, 'base': base}


def pop(rng, G, te, parts, events, big=1.0, niagara=None):
    p, n = G.point(rng, rng.uniform(0.25, 0.88), spread=50.0)
    q = addv(p, n, 1.5)
    parts.append(P_flash(te, q, 3.0 * big, 15.0 * big, 0.07, I=55 * big, power=4.0))    # soft blast glow
    parts.append(P_flash(te, q, 1.2 * big, 3.8 * big, 0.06, I=140 * big, power=1.4))    # white-hot core
    parts += star(rng, te, q, n, rng.randint(4, 6), l=(6 * big, 13 * big), life=0.07, width=0.75, I=95, G=G)
    for j in range(2):
        d = cone(rng, n, 35, 0.5)
        parts.append(P_smoke(te + 0.04 + 0.04 * j, addv(q, n, 2.5 + 2 * j), 5.0 * big, rng.uniform(15, 20) * big,
                             rng.uniform(0.45, 0.6), opacity=0.95, vel=(d[0] * 40, d[1] * 40, 35 + d[2] * 20), glow=6.0))
    parts += spark_burst(rng, te, q, n, rng.randint(3, 6), speed=(200, 450), ang=50, up=0.4, life=(0.2, 0.42),
                         width=(0.55, 0.8), I=55)
    ev = {'te': te, 'pop': (14.0 * big, 0.05, addv(q, n, 6)), 'core': (1.5 * big, 0.06), 'shudder': (0.6 * big, 0.05),
          'light': (2.0 * big, 0.05)}
    if niagara:
        ev['niagara'] = (niagara[0], niagara[1] * big, q)
    events.append(ev)


def look_N2(G, seed=202, niagara=None):
    rng = random.Random(seed)
    parts, events = [], []
    for te in irregular_times(rng, 5.5, min_gap=0.08, cluster=0.25, cluster_gap=(0.06, 0.1)):
        pop(rng, G, te, parts, events, rng.uniform(0.75, 1.15), niagara)
    base = dict(BASE, seam=1.8, emblem=1.2, crackle=0.15)
    return {'parts': parts, 'events': events, 'base': base}


def look_N3(G, seed=303):
    rng = random.Random(seed)
    parts, events = [], []
    for te in irregular_times(rng, 12.0, min_gap=0.03, cluster=0.5, cluster_gap=(0.02, 0.05)):
        k = rng.randint(2, 5)
        p, n = G.point(rng, rng.uniform(0.1, 0.95), front=rng.random() < 0.7, spread=70.0)
        for _ in range(k):
            d = cone(rng, n, 50, 0.25)
            s = rng.uniform(450, 850)
            parts.append(P_spark(te + rng.uniform(0, 0.02), p, (d[0] * s, d[1] * s, d[2] * s), rng.uniform(0.12, 0.2),
                                 rng.uniform(0.5, 0.7), I=75, g=-250, drag=0.6, streak=0.045, maxlen=30, twinkle=False,
                                 cool=0.7))
        parts.append(P_flash(te, addv(p, n, 0.5), 1.0, 2.6, 0.06, I=80, power=1.6))
        events.append({'te': te, 'light': (3.5, 0.05), 'core': (1.5, 0.05)})
    base = dict(BASE, seam=2.0, emblem=1.2, crackle=0.2)
    return {'parts': parts, 'events': events, 'base': base}


def look_N4(G, seed=404):
    rng = random.Random(seed)
    parts, events = [], []
    # geiger-like stutter: single ticks and triple stutters, irregular
    times = irregular_times(rng, 2.2, min_gap=0.22, cluster=0.6, cluster_gap=(0.07, 0.1))
    ph = math.radians(-12.0)              # the trefoil sits a little left of the camera axis (ITEM_TURN 22 deg)
    d = G.dir(ph)
    c = (d[0] * (G.R + 3.0), d[1] * (G.R + 3.0), 0.5 * G.H)
    n = (d[0], d[1], 0.0)
    for te in times:
        s = rng.uniform(0.75, 1.15)
        events.append({'te': te, 'core': (14.0 * s, 0.075), 'light': (14.0 * s, 0.07), 'shudder': (2.4 * s, 0.09),
                       'inner': (0.12 * s, 0.05)})
        parts += star(rng, te, c, n, rng.randint(6, 8), l=(10, 20), life=0.09, width=0.85, I=85 * s, G=G)
        parts.append(P_flash(te, c, 4.0, 11.0 * s, 0.08, I=35 * s, power=4.0))
    base = dict(BASE, seam=2.6, emblem=1.4, rim=0.9, crackle=0.3, core=1.8, haze=False, jitter=0.2, emblem_pulse=0.35)
    return {'parts': parts, 'events': events, 'base': base}


TICKS_N5 = (0.0, 0.55, 1.0, 1.36, 1.65, 1.88, 2.06, 2.20, 2.31)   # accelerating, then the loop resets


def tick(rng, G, te, s, parts, events):
    c = (0.0, 0.0, 0.52 * G.H)
    parts += ring_burst(rng, te, c, int(14 + 10 * s), r0=G.R * 0.95, I=50, g=-700, drag=1.4)
    parts.append(P_flash(te, (0.0, 0.0, 0.5 * G.H), 30.0, 52.0 * s, 0.1, I=2.2 * s, power=3.0))
    events.append({'te': te, 'swell': (0.13 * s, 0.035, 0.16), 'core': (10.0 * s, 0.09), 'light': (16.0 * s, 0.08),
                   'shudder': (0.3 * s, 0.06)})


def look_N5(G, seed=505):
    rng = random.Random(seed)
    parts, events = [], []
    n = len(TICKS_N5)
    for i, te in enumerate(TICKS_N5):
        s = 1.25 if i == 0 else 0.55 + 0.45 * i / (n - 1)
        tick(rng, G, te, s, parts, events)
    base = dict(BASE, seam=1.8, emblem=1.2, crackle=0.1)
    return {'parts': parts, 'events': events, 'base': base}


def look_N6(G, seed=606, niagara=None):
    rng = random.Random(seed)
    parts, events = [], []
    n = len(TICKS_N5)
    for i, te in enumerate(TICKS_N5):
        s = 1.25 if i == 0 else 0.55 + 0.45 * i / (n - 1)
        tick(rng, G, te, s, parts, events)
    for te in irregular_times(rng, 4.5, min_gap=0.1, avoid=TICKS_N5, avoid_w=0.06):
        pop(rng, G, te, parts, events, rng.uniform(0.8, 1.1), niagara)
    for te in irregular_times(rng, 6.0, min_gap=0.04, cluster=0.4, cluster_gap=(0.02, 0.05)):
        p, n_ = G.point(rng, rng.uniform(0.1, 0.95), front=rng.random() < 0.7, spread=70.0)
        for _ in range(rng.randint(1, 3)):
            d = cone(rng, n_, 50, 0.25)
            sp = rng.uniform(450, 850)
            parts.append(P_spark(te + rng.uniform(0, 0.02), p, (d[0] * sp, d[1] * sp, d[2] * sp), rng.uniform(0.12, 0.2),
                                 rng.uniform(0.5, 0.7), I=75, g=-250, drag=0.6, streak=0.045, maxlen=30, twinkle=False,
                                 cool=0.7))
    base = dict(BASE, seam=2.2, emblem=1.2, crackle=0.25)
    return {'parts': parts, 'events': events, 'base': base}


BUILDERS = {'N1': look_N1, 'N2': look_N2, 'N3': look_N3, 'N4': look_N4, 'N5': look_N5, 'N6': look_N6}


# ----------------------------------------------------------------------------------------------------------------
# evaluation (pure functions of the loop phase)

def age_of(te, ph):
    return (ph - te) % LOOP_S


def particle_state(q, a):
    k = q['drag']
    v0 = q['v']
    if k > 0:
        e = math.exp(-k * a)
        f = (1.0 - e) / k
    else:
        e, f = 1.0, a
    g = q['g']
    p = (q['p'][0] + v0[0] * f, q['p'][1] + v0[1] * f, q['p'][2] + v0[2] * f + 0.5 * g * a * a)
    v = (v0[0] * e, v0[1] * e, v0[2] * e + g * a)
    return p, v


def env_decay(a, amp, tau):
    return amp * math.exp(-a / tau)


def swell_env(a, amp, att, rel):
    if a < att:
        return amp * math.sin(0.5 * math.pi * a / att)
    return amp * math.exp(-(a - att) / rel)


def event_sum(events, ph, key):
    s = 0.0
    for e in events:
        v = e.get(key)
        if not v:
            continue
        a = age_of(e['te'], ph)
        if a > 8 * v[-1] and key != 'swell':
            continue
        if key == 'swell':
            s += swell_env(a, *v) if a < 1.2 else 0.0
        else:
            s += env_decay(a, v[0], v[1])
    return s


# ================================================================================================================
# RECORD MODE (inside Unreal)
# ================================================================================================================

if u is not None:
    sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
    import importlib  # noqa: E402

    import PowerUpStyleRecipes as REC  # noqa: E402

    importlib.reload(REC)

    WIDTH, HEIGHT = 1280, 720
    LOOK_KEYS = [x.strip() for x in os.environ.get('NUKE_LOOKS', 'N1,N2,N3,N4,N5,N6').split(',') if x.strip()]
    FAR_KEYS = [x.strip() for x in os.environ.get('NUKE_FAR', 'N5,N6').split(',') if x.strip()]
    BENCH = os.environ.get('NUKE_BENCH', '0') == '1'
    WARM = float(os.environ.get('NUKE_WARM', '8'))
    SETTLE = float(os.environ.get('NUKE_SETTLE', '2.6'))
    EV = float(os.environ.get('PU2_EV', 'nan'))
    NIAGARA_POP = os.environ.get('NUKE_NIAGARA_POP', '')          # e.g. /Game/.../NS_Simple_Core_Impact_1:0.2
    POOL_GLOW = 180
    POOL_SMOKE = 18
    POOL_POPL = 3
    POOL_NS = 4
    NUKE_MATS = '/Game/HoverPrototype/PowerUps/Styles/Nuke'
    SMOKE_MAT = NUKE_MATS + '/M_PU_NukeSmoke'
    CLOSE = {'dist': 200.0, 'height': 82.0, 'fov': 55.0}
    FAR = {'dist': 900.0, 'height': 165.0, 'fov': 55.0, 'wscale': 2.0}
    BENCH_LIST_R1 = [
        ('/Game/Sci_Fi_Weapons_VFX_AIO/VFX/NS_Simple_Core_Impact_1', 0.2, {}),
        ('/Game/Sci_Fi_Weapons_VFX_AIO/VFX/NS_Simple_Impact_1', 0.3, {}),
        ('/Game/Sci_Fi_Weapons_VFX_AIO/VFX/NS_Simple_Impact_2', 0.3, {}),
        ('/Game/Sci_Fi_Weapons_VFX_AIO/VFX/NS_Simple_Impact_3', 0.3, {}),
        ('/Game/Sci_Fi_Weapons_VFX_AIO/VFX/VFX_Ready/NS_Energy_Burst', 0.3, {}),
        ('/Game/Sci_Fi_Weapons_VFX_AIO/VFX/NS_Great_Impact', 0.1, {}),
        ('/Game/Vefects/Easy_Shockwaves_VFX/VFX/Shockwaves/Particles/Color_Variation/VFX_Shockwave_01_Orange_Small_1s', 1.0,
         {'floats': {'ScaleOverall': 0.15, 'Lifetime': 0.35}, 'colors': {'Color': (1.0, 0.5, 0.1)}}),
        ('/Game/ZESP/ZE/FX/Expo/NS_Explosion', 0.05, {}),
    ]
    VF = '/Game/Vefects/Easy_Shockwaves_VFX/VFX/Shockwaves/Particles/Color_Variation/'
    BENCH_LIST = [(VF + nm, 1.0, {'floats': {'Scale Overall': sc_, 'Lifetime Overall': 0.3, 'Emissiveness Overall': em},
                                  'colors': {'Color': (1.0, 0.45, 0.08)}})
                  for nm in ('VFX_Shockwave_01_Orange_Small_1s', 'VFX_Shockwave_Vertical_01_Orange_Small_1s')
                  for sc_, em in ((0.03, 20), (0.06, 20), (0.1, 33))]

    R = {'ok': True, 'errors': [], 'warnings': [], 'looks': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'fps': FPS,
         'loop_s': LOOP_S, 'nframes': NFRAMES, 'order': [], 'drops': {}, 'bench': {}, 'cams': {'close': CLOSE, 'far': FAR}}
    S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'done': False,
         't_first': None, 'k0t': None, 'prev_k': None, 'jobs': [], 'job': None, 'look': None, 'scene': None}
    LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
    F, RT = REC.view_basis()
    FACE_YAW = REC.VIEW_YAW + 90.0
    ITEM_TURN = 22.0
    HIDE_Z = -2000.0

    def log(*a):
        print('NUKE_GIF', *a, flush=True)

    def world():
        return u.HoverAuthoring.get_playtest_world()

    def V(t):
        return u.Vector(t[0], t[1], t[2])

    def LC(c, k=1.0, a=1.0):
        return u.LinearColor(c[0] * k, c[1] * k, c[2] * k, a)

    # ------------------------------------------------------------------------------------------------------------
    # the smoke master (project-owned, built once)

    def ensure_smoke_material():
        EAL = u.EditorAssetLibrary
        if EAL.does_asset_exist(SMOKE_MAT) and os.environ.get('NUKE_REBUILD') != '1':
            return u.load_asset(SMOKE_MAT)
        MEL = u.MaterialEditingLibrary
        AT = u.AssetToolsHelpers.get_asset_tools()
        folder, name = SMOKE_MAT.rsplit('/', 1)
        EAL.make_directory(folder)
        m = u.load_asset(SMOKE_MAT) or AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
        MEL.delete_all_material_expressions(m)
        m.set_editor_property('blend_mode', u.BlendMode.BLEND_TRANSLUCENT)
        m.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
        fails = []
        pos = [-1400, 0]

        def node(cls, **p):
            pos[1] += 80
            e = MEL.create_material_expression(m, cls, pos[0], pos[1])
            for k, v in p.items():
                e.set_editor_property(k, v)
            return e

        def link(a, out, b, inp):
            if not MEL.connect_material_expressions(a, out, b, inp):
                fails.append('%s.%s -> %s' % (a.get_class().get_name(), out, inp))

        def const(v):
            return node(u.MaterialExpressionConstant, r=float(v))

        def bin_(cls, a, b, ao='', bo=''):
            e = node(cls)
            link(a, ao, e, 'A')
            link(b, bo, e, 'B')
            return e

        col = node(u.MaterialExpressionVectorParameter, parameter_name='Color',
                   default_value=u.LinearColor(0.035, 0.03, 0.026, 1))
        gcol = node(u.MaterialExpressionVectorParameter, parameter_name='GlowColor', default_value=u.LinearColor(1, 0.4, 0.1, 1))
        glow = node(u.MaterialExpressionScalarParameter, parameter_name='Glow', default_value=0.0)
        em = bin_(u.MaterialExpressionAdd, col, bin_(u.MaterialExpressionMultiply, gcol, glow))
        if not MEL.connect_material_property(em, '', u.MaterialProperty.MP_EMISSIVE_COLOR):
            fails.append('emissive')
        nrm = node(u.MaterialExpressionVertexNormalWS)
        cam = node(u.MaterialExpressionCameraVectorWS)
        d = bin_(u.MaterialExpressionDotProduct, nrm, cam)
        ab = node(u.MaterialExpressionAbs)
        link(d, '', ab, '')
        mx = bin_(u.MaterialExpressionMax, ab, const(0.0001))
        pw = node(u.MaterialExpressionPower)
        link(mx, '', pw, 'Base')
        fp = node(u.MaterialExpressionScalarParameter, parameter_name='FacingPower', default_value=1.5)
        if not MEL.connect_material_expressions(fp, '', pw, 'Exponent'):
            link(fp, '', pw, 'Exp')
        tc = node(u.MaterialExpressionTextureCoordinate, u_tiling=1.5, v_tiling=1.5)
        pan = node(u.MaterialExpressionPanner, speed_x=0.05, speed_y=-0.35)
        link(tc, '', pan, 'Coordinate')
        nt = u.load_asset(REC.TEX + '/T_PU_Noise')
        tx = node(u.MaterialExpressionTextureSampleParameter2D, parameter_name='NoiseTex')
        tx.set_editor_property('texture', nt)
        try:
            srgb = nt.get_editor_property('srgb')
            tx.set_editor_property('sampler_type', u.MaterialSamplerType.SAMPLERTYPE_COLOR if srgb
                                   else u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        except Exception as e:  # noqa: BLE001
            fails.append('sampler %s' % e)
        link(pan, '', tx, 'UVs')
        nz = bin_(u.MaterialExpressionMultiply, tx, const(1.8), 'R')
        namt = node(u.MaterialExpressionScalarParameter, parameter_name='NoiseAmount', default_value=0.8)
        lp = node(u.MaterialExpressionLinearInterpolate)
        link(const(1.0), '', lp, 'A')
        link(nz, '', lp, 'B')
        link(namt, '', lp, 'Alpha')
        op = node(u.MaterialExpressionScalarParameter, parameter_name='Opacity', default_value=0.7)
        o = bin_(u.MaterialExpressionMultiply, bin_(u.MaterialExpressionMultiply, op, pw), lp)
        sat = node(u.MaterialExpressionSaturate)
        link(o, '', sat, '')
        if not MEL.connect_material_property(sat, '', u.MaterialProperty.MP_OPACITY):
            fails.append('opacity')
        MEL.recompile_material(m)
        EAL.save_loaded_asset(m)
        R['smoke_material'] = {'path': SMOKE_MAT, 'fails': fails,
                               'scalars': [str(x) for x in MEL.get_scalar_parameter_names(m)]}
        if fails:
            R['warnings'].append('smoke material link failures %s' % fails)
        return m

    # ------------------------------------------------------------------------------------------------------------
    # scene

    def spawn_sma(mesh, loc, rot=None, scale=(1, 1, 1), shadow=False):
        a = u.HoverAuthoring.spawn_playtest_actor(u.StaticMeshActor, u.Transform(location=V(loc), rotation=rot or u.Rotator(),
                                                                                 scale=V(scale)))
        c = a.static_mesh_component
        c.set_mobility(u.ComponentMobility.MOVABLE)
        c.set_static_mesh(mesh)
        a.set_actor_scale3d(V(scale))
        c.set_editor_property('cast_shadow', shadow)
        return a

    def spawn_light(loc, intensity, radius, color, shadows=False):
        a = u.HoverAuthoring.spawn_playtest_actor(u.PointLight, u.Transform(location=V(loc)))
        c = a.get_component_by_class(u.PointLightComponent)
        c.set_mobility(u.ComponentMobility.MOVABLE)
        c.set_editor_property('intensity_units', u.LightUnits.CANDELAS)
        c.set_intensity(intensity)
        c.set_attenuation_radius(radius)
        c.set_light_color(LC(color), True)
        c.set_cast_shadows(shadows)
        return a, c

    def build_scene():
        item = REC.ITEMS['Nuke']
        base = REC.view_to_world((0, 0, 0), item['y'])
        mesh = u.load_asset(item['mesh'])
        rot = u.Rotator(roll=0, pitch=0, yaw=FACE_YAW + ITEM_TURN)
        ia = spawn_sma(mesh, base, rot, (1, 1, 1), shadow=True)
        comp = ia.static_mesh_component
        fx2 = u.load_asset(REC.MATS + '/M_PU_ItemFX2')
        mid = comp.create_dynamic_material_instance(0, fx2)
        for k, suf in (('BaseColorTex', 'BaseColor'), ('NormalTex', 'Normal'), ('ORMTex', 'ORM')):
            t = u.load_asset(item['tex'] + suf)
            if t:
                mid.set_texture_parameter_value(k, t)
            else:
                R['errors'].append('missing texture ' + item['tex'] + suf)
        for k, v in (('Darken', 1.0), ('RimExponent', 3.0), ('EmblemBias', 0.4), ('EmblemGain', 4.0)):
            mid.set_scalar_parameter_value(k, v)
        mid.set_vector_parameter_value('RimColor', LC(ORANGE))
        mid.set_vector_parameter_value('Tint', LC((1.0, 1.0, 1.0)))
        mid.set_vector_parameter_value('InnerColor', LC(lerp3(WHITE, HOTY, 0.6)))
        origin, ext = ia.get_actor_bounds(False)
        H = max(10.0, (origin.z + ext.z) - base[2])
        Rr = float(os.environ.get('NUKE_R', '0') or 0) or max(5.0, 0.78 * min(ext.x, ext.y))   # side plates inflate the box
        R['item_bounds'] = {'H': round(H, 2), 'R': round(Rr, 2), 'origin': [origin.x, origin.y, origin.z],
                            'extent': [ext.x, ext.y, ext.z]}
        G = Geo(H, Rr, (-F[0], -F[1]), (RT[0], RT[1]))
        sc = {'item': ia, 'mid': mid, 'base': base, 'rot': rot, 'G': G}
        front = addv(base, (-F[0] * 24, -F[1] * 24, 34))
        sc['key'] = spawn_light(front, 3.0, 240, KEY_C, shadows=True)
        corep = addv(base, (-F[0] * 14 + RT[0] * 4, -F[1] * 14 + RT[1] * 4, 0.55 * H))
        sc['core'] = spawn_light(corep, 1.0, 300, lerp3(HOTY, ORANGE, 0.4))
        sc['popl'] = [spawn_light(addv(base, (0, 0, HIDE_Z)), 0.0, 120, lerp3(WHITE, HOTY, 0.5)) for _ in range(POOL_POPL)]
        sm = u.load_asset(REC.ENG_SPHERE)
        glowm = u.load_asset(REC.MATS + '/M_PU_GlowAdditive')
        smokem = ensure_smoke_material()
        hide = addv(base, (0, 0, HIDE_Z))
        sc['glow'] = []
        for _ in range(POOL_GLOW):
            a = spawn_sma(sm, hide, None, (0.001, 0.001, 0.001))
            m = a.static_mesh_component.create_dynamic_material_instance(0, glowm)
            m.set_scalar_parameter_value('FacingAmount', 1.0)
            m.set_scalar_parameter_value('FacingPower', 1.6)
            m.set_scalar_parameter_value('FadeDistance', 0.0)
            m.set_scalar_parameter_value('Intensity', 1.0)
            sc['glow'].append({'a': a, 'm': m, 'hidden': True, 'pw': 1.6})
        sc['smoke'] = []
        for _ in range(POOL_SMOKE):
            a = spawn_sma(sm, hide, None, (0.001, 0.001, 0.001))
            m = a.static_mesh_component.create_dynamic_material_instance(0, smokem)
            m.set_vector_parameter_value('Color', LC((0.006, 0.005, 0.0045)))
            m.set_vector_parameter_value('GlowColor', LC(lerp3(HOTY, ORANGE, 0.5)))
            m.set_scalar_parameter_value('FacingPower', 1.2)
            sc['smoke'].append({'a': a, 'm': m, 'hidden': True})
        hz = u.load_asset(REC.MATS + '/M_PU_HeatHaze')
        sc['haze_loc'] = addv(base, (0, 0, H + 20))
        ha = spawn_sma(sm, hide, None, (0.001, 0.001, 0.001))
        hm = ha.static_mesh_component.create_dynamic_material_instance(0, hz)
        for k, v in (('Strength', 3.0), ('Tiling', 2.5), ('Speed', 1.2), ('Refraction', 2.0), ('Opacity', 0.02)):
            hm.set_scalar_parameter_value(k, v)
        sc['haze'] = ha
        sc['ns'] = []
        for _ in range(POOL_NS):
            a = u.HoverAuthoring.spawn_playtest_actor(u.NiagaraActor, u.Transform(location=V(hide)))
            sc['ns'].append({'a': a, 'c': a.niagara_component, 'asset': None})
        S['scene'] = sc
        log('scene H=%.1f R=%.1f' % (H, Rr))

    # ------------------------------------------------------------------------------------------------------------
    # per-frame application

    def place(slot, p, v, length, width):
        a = slot['a']
        sp = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        if sp > 1e-3:
            rot = u.MathLibrary.find_look_at_rotation(V(p), V((p[0] + v[0], p[1] + v[1], p[2] + v[2])))
        else:
            rot = u.Rotator()
        a.set_actor_location_and_rotation(V(p), rot, False, True)
        a.set_actor_scale3d(V((max(length, width) / 100.0, width / 100.0, width / 100.0)))
        slot['hidden'] = False

    def hide(slot):
        if slot['hidden']:
            return
        sc = S['scene']
        slot['a'].set_actor_location(V(addv(sc['base'], (0, 0, HIDE_Z))), False, True)
        slot['a'].set_actor_scale3d(V((0.001, 0.001, 0.001)))
        slot['hidden'] = True

    def apply_look(look, ph, kk):
        """Set the whole scene for loop phase ph (kk = tick index inside the loop, for per-frame hashes)."""
        sc = S['scene']
        base = sc['base']
        b = look['base']
        ev = look['events']
        # ---- particles
        glow_list, smoke_list = [], []
        for i, q in enumerate(look['parts']):
            a = age_of(q['te'], ph)
            if a >= q['life']:
                continue
            p, v = particle_state(q, a)
            f = a / q['life']
            P = addv(base, p)
            if q['k'] == 'smoke':
                smoke_list.append((q, P, v, f))
            else:
                glow_list.append((q, P, v, f, i))
        drops = 0
        for j, slot in enumerate(sc['glow']):
            if j >= len(glow_list):
                hide(slot)
                continue
            q, P, v, f, i = glow_list[j]
            if q['k'] == 'glint':
                ln = q['l0'] + (q['l1'] - q['l0']) * f ** 0.4
                w = q['w'] * (1 - f) ** 0.4 * S.get('wscale', 1.0)
                inten = q['I'] * (1 - f) ** 1.5
                col = temp(f * 0.4)
                if slot['pw'] != 1.6:
                    slot['m'].set_scalar_parameter_value('FacingPower', 1.6)
                    slot['pw'] = 1.6
                place(slot, addv(P, q['dir'], ln * 0.5), q['dir'], ln, w)
            elif q['k'] == 'flash':
                s = q['s0'] + (q['s1'] - q['s0']) * (1 - (1 - f) ** 3)
                inten = q['I'] * (1 - f) ** 3
                col = temp(f * 0.5)
                if slot['pw'] != q['power']:
                    slot['m'].set_scalar_parameter_value('FacingPower', q['power'])
                    slot['pw'] = q['power']
                place(slot, P, (0, 0, 0), s, s)
            else:
                w = q['w'] * (1 - f) ** 0.5 * S.get('wscale', 1.0)
                sp = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
                ln = min(q['maxlen'], w + sp * q['streak'])
                tw = (0.45 + 0.9 * hsh(i, kk)) if q.get('twinkle') else 1.0
                inten = q['I'] * (1 - f) ** 0.7 * tw
                col = temp(min(1.0, f * q.get('cool', 1.0)))
                if slot['pw'] != 1.6:
                    slot['m'].set_scalar_parameter_value('FacingPower', 1.6)
                    slot['pw'] = 1.6
                place(slot, P, v, ln, w)
            slot['m'].set_vector_parameter_value('Color', LC(col, inten))
        drops += max(0, len(glow_list) - len(sc['glow']))
        for j, slot in enumerate(sc['smoke']):
            if j >= len(smoke_list):
                hide(slot)
                continue
            q, P, v, f = smoke_list[j]
            s = q['s0'] + (q['s1'] - q['s0']) * (1 - (1 - f) ** 2)
            place(slot, P, (0, 0, 0), s, s)
            slot['m'].set_scalar_parameter_value('Opacity', q['op'] * (1 - f) ** 1.6)
            slot['m'].set_scalar_parameter_value('Glow', q['glow'] * max(0.0, 1 - f * 6) ** 2)
        drops += max(0, len(smoke_list) - len(sc['smoke']))
        if drops:
            R['drops'][S['look']['key']] = max(R['drops'].get(S['look']['key'], 0), drops)
        # ---- item skin: seams + trefoil heat
        core = event_sum(ev, ph, 'core')
        crack = b['crackle'] * (hsh(kk, 77) - 0.5) * 2.0
        epulse = b['emblem_pulse'] * math.sin(2 * math.pi * 5 * ph / LOOP_S)
        seam = b['seam'] * (1 + 0.5 * crack) + core * 1.1
        emb = b['emblem'] * (1 + epulse + 0.4 * crack) + core
        hot = min(1.0, core / 6.0)
        m = sc['mid']
        m.set_scalar_parameter_value('SeamGlow', max(0.0, seam))
        m.set_scalar_parameter_value('EmblemGlow', max(0.0, emb))
        m.set_vector_parameter_value('SeamColor', LC(lerp3(ORANGE, WHITE, hot)))
        m.set_vector_parameter_value('EmblemColor', LC(lerp3(lerp3(NUKE_C, HOTY, 0.4), WHITE, hot)))
        m.set_scalar_parameter_value('RimIntensity', b['rim'] * (1 + 0.5 * crack) + 0.15 * core)
        m.set_scalar_parameter_value('InnerGlow', event_sum(ev, ph, 'inner'))
        # ---- item transform: swell + shudder
        sw = event_sum(ev, ph, 'swell')
        jit = b['jitter'] + event_sum(ev, ph, 'shudder')
        dx = (hsh(kk, 11) * 2 - 1) * jit
        dy = (hsh(kk, 12) * 2 - 1) * jit
        dyaw = (hsh(kk, 13) * 2 - 1) * jit * 1.6
        r0 = sc['rot']
        sc['item'].set_actor_location_and_rotation(V((base[0] + dx, base[1] + dy, base[2])),
                                                  u.Rotator(roll=r0.roll, pitch=r0.pitch, yaw=r0.yaw + dyaw), False, True)
        s = 1.0 + sw
        sc['item'].set_actor_scale3d(V((s, s, s)))
        # ---- lights
        sc['key'][1].set_intensity(b['key'] * (1 + 0.15 * crack))
        sc['core'][1].set_intensity(max(0.0, b['core'] * (1 + crack) + event_sum(ev, ph, 'light')))
        pops = []
        for e in ev:
            if e.get('pop'):
                a = age_of(e['te'], ph)
                if a < 6 * e['pop'][1]:
                    pops.append((a, e))
        pops.sort(key=lambda x: x[0])
        for j, (lt, lc_) in enumerate(sc['popl']):
            if j < len(pops):
                a, e = pops[j]
                amp, tau, pos = e['pop']
                lt.set_actor_location(V(addv(base, pos)), False, True)
                lc_.set_intensity(env_decay(a, amp, tau))
            else:
                lc_.set_intensity(0.0)
        # ---- heat haze (N4 only)
        if b['haze']:
            sc['haze'].set_actor_location(V(sc['haze_loc']), False, True)
            sc['haze'].set_actor_scale3d(V((0.5, 0.5, 0.7)))
        else:
            sc['haze'].set_actor_location(V(addv(base, (0, 0, HIDE_Z))), False, True)

    def niagara_triggers(look, prev_ph, ph):
        sc = S['scene']
        for e in look['events']:
            n = e.get('niagara')
            if not n:
                continue
            te = e['te']
            crossed = (prev_ph < te <= ph) if ph >= prev_ph else (te > prev_ph or te <= ph)
            if not crossed:
                continue
            slot = sc['ns'][S['ns_rr'] % len(sc['ns'])]
            S['ns_rr'] += 1
            path, scale, pos = n
            if slot['asset'] != path:
                slot['c'].set_asset(u.load_asset(path))
                slot['asset'] = path
            slot['a'].set_actor_location(V(addv(sc['base'], pos)), False, True)
            slot['a'].set_actor_scale3d(V((scale, scale, scale)))
            slot['c'].reset_system()
            slot['c'].activate(True)

    # ------------------------------------------------------------------------------------------------------------
    # bench of real Niagara candidates (optional)

    def bench_spawn():
        sc = S['scene']
        out = []
        for i, (path, scale, prm) in enumerate(BENCH_LIST):
            a_ = u.load_asset(path)
            info = {'path': path, 'scale': scale, 'ok': bool(a_)}
            if a_:
                try:
                    d = json.loads(u.HoverAuthoring.describe_flash_asset(a_))
                    info['user'] = [(q['name'], q.get('value')) for q in d.get('user_parameters', [])]
                    info['duration_s'] = d.get('duration_s')
                except Exception as e:  # noqa: BLE001
                    info['describe'] = str(e)
            R['bench'][str(i + 1)] = info
            if not a_:
                continue
            loc = addv(sc['base'], (RT[0] * (45 + 40 * i), RT[1] * (45 + 40 * i), 24))
            ac = u.HoverAuthoring.spawn_playtest_actor(u.NiagaraActor, u.Transform(location=V(loc)))
            c = ac.niagara_component
            c.set_asset(a_)
            for k, v in prm.get('floats', {}).items():
                c.set_variable_float(k, float(v))
            for k, v in prm.get('colors', {}).items():
                c.set_variable_linear_color(k, LC(v))
            ac.set_actor_scale3d(V((scale, scale, scale)))
            c.activate(True)
            out.append({'a': ac, 'c': c, 'off': 0.1 * i})
        S['bench'] = out

    def bench_tick(prev_ph, ph):
        per = 0.8
        for b in S.get('bench', []):
            for m in range(3):
                te = (b['off'] + per * m) % LOOP_S
                crossed = (prev_ph < te <= ph) if ph >= prev_ph else (te > prev_ph or te <= ph)
                if crossed:
                    b['c'].reset_system()
                    b['c'].activate(True)

    # ------------------------------------------------------------------------------------------------------------
    # camera + jobs

    def cam_at(cfg, target):
        loc = (target[0] - F[0] * cfg['dist'], target[1] - F[1] * cfg['dist'], cfg['height'])
        rot = u.MathLibrary.find_look_at_rotation(V(loc), V(target))
        S['cam'].set_actor_location_and_rotation(V(loc), rot, False, True)
        S['cam'].camera_component.set_field_of_view(cfg['fov'])
        S['pc'].set_view_target_with_blend(S['cam'], 0)

    def item_target(dz=0.0):
        sc = S['scene']
        return addv(sc['base'], (0, 0, 0.55 * sc['G'].H + dz))

    def set_ev():
        if math.isnan(EV):
            return
        for p in u.GameplayStatics.get_all_actors_of_class(world(), u.PostProcessVolume):
            s = p.get_editor_property('settings')
            s.set_editor_property('override_auto_exposure_bias', True)
            s.set_editor_property('auto_exposure_bias', EV)
            p.set_editor_property('settings', s)
        R['ev'] = EV

    def make_look(key):
        G = S['scene']['G']
        npop = None
        if NIAGARA_POP and key in ('N2', 'N6'):
            p, sc_ = NIAGARA_POP.rsplit(':', 1)
            npop = (p, float(sc_))
        fn = BUILDERS[key]
        lk = fn(G, niagara=npop) if key in ('N2', 'N6') else fn(G)
        lk['key'] = key
        lk['name'] = LOOK_META[key][1]
        lk['slug'] = LOOK_META[key][0]
        return lk

    def plan_jobs():
        jobs = []
        if BENCH:
            jobs.append({'kind': 'bench', 'dir': 'BENCH', 'key': 'N0', 'cam': {'dist': 340.0, 'height': 110.0, 'fov': 62.0},
                         'target_dy': 150.0})
        for k in LOOK_KEYS:
            jobs.append({'kind': 'look', 'dir': '%s_%s' % (k, LOOK_META[k][0]), 'key': k, 'cam': CLOSE})
        for k in FAR_KEYS:
            jobs.append({'kind': 'look', 'dir': '%s_%s_far' % (k, LOOK_META[k][0]), 'key': k, 'cam': FAR, 'far': True})
        S['jobs'] = jobs
        R['order'] = [j['dir'] for j in jobs]

    def start_job(k):
        if not S['jobs']:
            finish()
            return
        j = S['jobs'].pop(0)
        S['job'] = j
        if j['kind'] == 'bench':
            S['look'] = {'key': 'N0', 'name': 'Bench', 'parts': [], 'events': [], 'base': dict(BASE)}
            if not S.get('bench'):
                bench_spawn()
            sc = S['scene']
            tgt = addv(item_target(), (RT[0] * j['target_dy'], RT[1] * j['target_dy'], 0))
            cam_at(j['cam'], tgt)
        else:
            for b in S.get('bench', []):
                b['a'].destroy_actor()
            S['bench'] = []
            S['look'] = make_look(j['key'])
            cam_at(j['cam'], item_target(0.0 if not j.get('far') else 10.0))
        S['k_look0'] = k
        S['wscale'] = j['cam'].get('wscale', 1.0)
        d = OUT / j['dir']
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob('f*.png'):
            old.unlink()
        settle = max(int(round(SETTLE / TICK)), NT)
        k_start = k + settle
        k_start += (-(k_start - k)) % NT        # start on loop phase 0
        j.update({'dir_path': d, 'k_start': k_start, 'n': 0, 'phases': []})
        log('job', j['dir'], 'parts', len(S['look']['parts']), 'events', len(S['look']['events']))

    def capture_if_due(shown_k):
        j = S['job']
        if j is None or shown_k is None or shown_k < j['k_start']:
            return False
        rel = shown_k - j['k_start']
        if rel % EVERY:
            return False
        i = rel // EVERY
        if i >= NFRAMES:
            return True
        if i > j['n']:
            R['warnings'].append('%s: frames %d..%d skipped' % (j['dir'], j['n'], i - 1))
            j['n'] = i
        if i < j['n']:
            return False
        fn = j['dir_path'] / ('f%03d.png' % i)
        u.HoverAuthoring.capture_world_frame(str(fn))
        j['phases'].append(round(((shown_k - S['k_look0']) % NT) * TICK, 4))
        j['n'] += 1
        if j['n'] >= NFRAMES:
            lk = S['look']
            R['looks'][j['dir']] = {'key': j['key'], 'name': lk['name'], 'slug': lk.get('slug', 'Bench'),
                                    'far': bool(j.get('far')), 'bench': j['kind'] == 'bench', 'frames': j['n'],
                                    'dir': str(j['dir_path']), 'phases': j['phases'],
                                    'parts': len(lk['parts']), 'events': len(lk['events'])}
            log('recorded', j['dir'], j['n'])
            return True
        return False

    def finish():
        if S['end']:
            return
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'record.json').write_text(json.dumps(R, indent=1, default=str))
        LEVEL.editor_request_end_play()
        S['end'] = time.monotonic()

    def tick_cb(dt):
        if S['busy']:
            return
        S['busy'] = True
        try:
            if S['end']:
                if time.monotonic() - S['end'] > 3 and not world():
                    if not S['done']:
                        S['done'] = True
                        (OUT / 'record.json').write_text(json.dumps(R, indent=1, default=str))
                        log('DONE looks=%d errors=%d' % (len(R['looks']), len(R['errors'])))
                    u.unregister_slate_post_tick_callback(S['handle'])
                    u.EditorPythonScripting.set_keep_python_script_alive(False)
                    u.SystemLibrary.quit_editor()
                return
            if time.monotonic() - S['start'] > 2400:
                raise RuntimeError('timeout')
            if not S['play']:
                if time.monotonic() - S['start'] > 7:
                    try:
                        u.HoverAuthoring.configure_offscreen_display(WIDTH + 16, HEIGHT + 80)
                    except Exception as e:  # noqa: BLE001
                        R['errors'].append('configure_offscreen_display: %s' % e)
                    u.HoverAuthoring.start_playtest(WIDTH, HEIGHT + 32)
                    S['play'] = True
                return
            w = world()
            if not w:
                return
            pc = u.GameplayStatics.get_player_controller(w, 0)
            if not pc:
                return
            t = u.GameplayStatics.get_time_seconds(w)
            if S['pc'] is None:
                S['pc'] = pc
                S['t_first'] = t
                return
            if S['cam'] is None:
                if t - S['t_first'] < 2.0:
                    return
                u.HoverAuthoring.set_playtest_fixed_step(True)
                S['cam'] = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=u.Vector(0, 0, 500),
                                                                                            rotation=u.Rotator()))
                S['cam'].camera_component.set_editor_property('constrain_aspect_ratio', False)
                set_ev()
                build_scene()
                S['k0t'] = t
                S['ns_rr'] = 0
                # warm: the combo look (all materials, smoke, haze) for WARM seconds
                S['look'] = make_look('N6')
                S['look']['base']['haze'] = True
                S['k_look0'] = 0
                S['warm_until'] = int(round(WARM / TICK))
                cam_at(CLOSE, item_target())
                plan_jobs()
                R['viewport'] = str(u.HoverAuthoring.get_playtest_viewport_size())
                return
            k = int(round((t - S['k0t']) / TICK))
            if k == S['prev_k']:
                return
            # the frame on screen now shows the state applied for prev_k
            if S['job'] is None:
                if k >= (S.get('warm_until') or 0):
                    if S.get('warm_until') is not None:
                        u.HoverAuthoring.capture_world_frame(str(OUT / '_warmup.png'))
                        S['warm_until'] = None
                    start_job(k)
            elif capture_if_due(S['prev_k']):
                S['job'] = None
                start_job(k)
            if S['end']:
                return
            kk = (k - S['k_look0']) % NT
            ph = kk * TICK
            prev_ph = ((k - 1 - S['k_look0']) % NT) * TICK
            apply_look(S['look'], ph, kk)
            niagara_triggers(S['look'], prev_ph, ph)
            if S.get('bench'):
                bench_tick(prev_ph, ph)
            S['prev_k'] = k
        except Exception:  # noqa: BLE001
            R['errors'].append(traceback.format_exc())
            R['ok'] = False
            log('ERROR', R['errors'][-1][-1200:])
            finish()
        finally:
            S['busy'] = False

    OUT.mkdir(parents=True, exist_ok=True)
    assert LEVEL.load_level(REC.LEVEL), 'load_level failed'
    u.EditorPythonScripting.set_keep_python_script_alive(True)
    S['handle'] = u.register_slate_post_tick_callback(tick_cb)


# ================================================================================================================
# ASSEMBLE MODE (system Python + PIL)
# ================================================================================================================

def assemble():
    sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
    import AssemblePowerUpGifs as APG  # noqa: E402  (encoder reused, not modified)
    from PIL import Image, ImageDraw

    LOOK_MAX, GRID_MAX = 4.0e6, 8.0e6
    rec = json.loads((OUT / 'record.json').read_text())
    out = {'fps': FPS, 'looks': [], 'errors': [], 'record_errors': rec.get('errors'), 'drops': rec.get('drops')}

    def crop_c(im):
        w, h = im.size
        cw = min(w, 960)
        ch = round(cw * 9 / 16)
        x0, y0 = (w - cw) // 2, max(0, (h - ch) // 2)
        return im.crop((x0, y0, x0 + cw, y0 + ch))

    def label(img, num, name, big, small, pad=6, top=False):
        d = ImageDraw.Draw(img, 'RGBA')
        bn = d.textbbox((0, 0), num, font=big)
        bs = d.textbbox((0, 0), name, font=small) if name else (0, 0, 0, 0)
        wn, hn = bn[2] - bn[0], bn[3] - bn[1]
        ws, hs = bs[2] - bs[0], bs[3] - bs[1]
        w = pad + wn + pad + (ws + pad if name else 0)
        h = max(hn, hs) + 2 * pad
        y0 = 0 if top else img.size[1] - h
        d.rectangle((0, y0, w, y0 + h), fill=(0, 0, 0, 175))
        d.text((pad - bn[0], y0 + pad - bn[1]), num, font=big, fill=(255, 214, 120, 255))
        if name:
            d.text((pad + wn + pad - bs[0], y0 + pad + (hn - hs) - bs[1]), name, font=small, fill=(240, 240, 240, 255))

    def load(entry):
        files = sorted(Path(entry['dir']).glob('f*.png'))
        return [crop_c(Image.open(f).convert('RGB')) for f in files]

    close, far, bench = [], [], []
    for d in rec['order']:
        e = rec['looks'].get(d)
        if not e:
            out['errors'].append('%s not recorded' % d)
            continue
        (bench if e.get('bench') else far if e['far'] else close).append((d, e))

    big_f, small_f = APG.font(APG.FONT_BIG, 30), APG.font(APG.FONT_NAME, 19)
    tiles = []
    for d, e in close:
        big = load(e)
        stats = APG.motion_stats([im.resize((320, 180), Image.BILINEAR) for im in big])
        fr = [im.resize((640, 360), Image.LANCZOS) for im in big]
        for f in fr:
            label(f, e['key'], e['name'], big_f, small_f)
        path = ROOT / ('nuke_%s_%s.gif' % (e['key'], e['slug']))
        size = APG.save_gif(fr, path, FPS, thresh=APG.LOOK_T)
        if size > LOOK_MAX:
            size = APG.save_gif(fr, path, FPS, colors=160, thresh=6)
        derr = APG.decode_error(path, fr)
        out['looks'].append({'key': e['key'], 'name': e['name'], 'gif': str(path), 'bytes': size, 'frames': len(fr),
                             'motion': stats, 'decode_err': derr})
        tiles.append((e['key'], e['name'], big))
        print('%s %-30s %5.2f MB %s decode %s' % (e['key'], e['name'], size / 1e6, stats, derr), flush=True)

    if tiles:
        n = min(len(t[2]) for t in tiles)
        for cols, tw in ((3, 480), (3, 420), (3, 380), (2, 420), (3, 320)):
            th = round(tw * 9 / 16)
            rows = (len(tiles) + cols - 1) // cols
            gap = 4
            W, H = cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap
            bf = APG.font(APG.FONT_BIG, max(34, tw // 8))
            sf = APG.font(APG.FONT_NAME, max(14, tw // 26))
            frames = []
            for i in range(n):
                cv = Image.new('RGB', (W, H), (12, 12, 12))
                for k, (key, name, big) in enumerate(tiles):
                    t_ = big[i].resize((tw, th), Image.LANCZOS)
                    label(t_, key, name, bf, sf, pad=5, top=True)
                    cv.paste(t_, (gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + gap)))
                frames.append(cv)
            path = ROOT / 'nuke_grid.gif'
            size = APG.save_gif(frames, path, FPS, thresh=APG.GRID_T)
            print('grid %dx%d tile %d -> %.2f MB' % (cols, rows, tw, size / 1e6), flush=True)
            out['grid'] = {'gif': str(path), 'bytes': size, 'cols': cols, 'tile': [tw, th], 'size': [W, H]}
            if size <= GRID_MAX:
                break

    if far:
        fl = [(e['key'], e['name'], load(e)) for d, e in far]
        n = min(len(x[2]) for x in fl)
        tw, th, gap = 480, 270, 4
        W, H = len(fl) * tw + (len(fl) + 1) * gap, th + 2 * gap
        bf, sf = APG.font(APG.FONT_BIG, 30), APG.font(APG.FONT_NAME, 16)
        frames = []
        for i in range(n):
            cv = Image.new('RGB', (W, H), (12, 12, 12))
            for k, (key, name, big) in enumerate(fl):
                t_ = big[i].resize((tw, th), Image.LANCZOS)
                label(t_, key, name + '  ~9 m', bf, sf, pad=5)
                cv.paste(t_, (gap + k * (tw + gap), gap))
            frames.append(cv)
        path = ROOT / 'nuke_far.gif'
        size = APG.save_gif(frames, path, FPS, thresh=APG.LOOK_T)
        out['far'] = {'gif': str(path), 'bytes': size, 'looks': [x[0] for x in fl], 'size': [W, H]}
        print('far %.2f MB' % (size / 1e6), flush=True)

    for d, e in bench:
        big = load(e)
        fr = [im.resize((640, 360), Image.LANCZOS) for im in big]
        path = ROOT / 'bench' / 'nuke_bench.gif'
        path.parent.mkdir(exist_ok=True)
        out['bench'] = {'gif': str(path), 'bytes': APG.save_gif(fr, path, FPS, thresh=APG.LOOK_T)}
    (ROOT / 'assemble.json').write_text(json.dumps(out, indent=1))
    return 0 if not out['errors'] else 1


if u is None and __name__ == '__main__':
    sys.exit(assemble())
