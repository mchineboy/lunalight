#!/usr/bin/env python3
"""Simulate lunalight physics, terrain and sprite/background collision.

Mirrors src/lunalight.bas closely enough to validate the attract-mode autopilot
before spending emulator time on it. Sprite pixels come from the real shape
data; collision uses the same char cells the BASIC terrain routine POKEs.
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARGEN = Path('/opt/homebrew/Cellar/vice/3.10/share/vice/C64/chargen-901225-01.bin')

SPRITE_ROWS = 21
CHAR_X0 = 24
CHAR_Y0 = 50
TERRAIN_ROW0 = 12


def load_sprites():
    raw = Path(ROOT, 'sprites/lsprite.prg').read_bytes()
    addr = raw[0] | raw[1] << 8
    data = raw[2:]
    shapes = {}
    for ptr in (187, 188, 189, 190, 191, 192, 193, 194):
        base = ptr * 64 - addr
        blk = data[base:base + 63]
        rows = []
        for r in range(SPRITE_ROWS):
            bits = 0
            for b in range(3):
                bits = bits << 8 | blk[r * 3 + b]
            rows.append(bits)
        shapes[ptr] = rows
    return shapes


def load_chars():
    rom = CHARGEN.read_bytes()
    return {code: list(rom[code * 8:code * 8 + 8]) for code in (100, 160)}


SHAPES = load_sprites()
CHARS = load_chars()


KA = 0.03  # pixels per tenth of velocity per physics step


class Planet:
    def __init__(self, mars):
        if mars:
            self.gv, self.th, self.ni, self.nb, self.nc, self.ns, self.sl = 46, 34, 24, 33, 41, 4, 8
        else:
            self.gv, self.th, self.ni, self.nb, self.nc, self.ns, self.sl = 20, 20, 18, 28, 35, 3, 5


def sgn(x):
    return (x > 0) - (x < 0)


def gen_terrain(rng):
    """Lines 1105-1200: height map, five pads, char cells."""
    def rv():
        return rng.randrange(256)

    h = [0] * 40
    hh, sg = 3, 0
    for c in range(40):
        if sg <= 0:
            tg = 1 + rv() * 12 // 256
            sg = 3 + rv() * 5 // 256
            if tg == hh:
                tg = 13 - hh
        ds = sgn(tg - hh)
        if rv() < 64:
            ds *= 2
        hh = max(1, min(12, hh + ds))
        h[c] = hh
        sg -= 1
    for c in range(1, 39):
        r = rv()
        if r < 52:
            h[c] = max(1, min(12, h[c] + (r & 2) - 1))

    px = [0] * 6
    pw = [0] * 6
    py = [0] * 6
    pb = [0] * 6
    rf = [0] * 6
    ph = [0] * 6
    base = [0, 1, 9, 17, 25, 33]
    ro = rv() * 5 // 256
    fz = 0
    for i in range(1, 6):
        cs = base[i] + rv() * 3 // 256
        pw[i] = 3 + (rv() & 1)
        ce = cs + pw[i] - 1
        zz = i + ro
        if zz > 5:
            zz -= 5
        if zz in (1, 3):
            hh = 9 + rv() * 4 // 256
        elif zz in (2, 5):
            hh = 3 + (rv() & 1)
        else:
            hh = 5 + rv() * 4 // 256
        pb[i] = 800 if hh > 8 else 600
        if hh < 5:
            pb[i] = 500
            if fz == 0:
                rf[i] = 1
                fz = 1
        ph[i] = hh
        for c in range(cs, ce + 1):
            h[c] = hh
        for d in (1, 2):
            if cs - d >= 0:
                if hh > 8:
                    h[cs - d] = hh - d
                elif hh < 4:
                    h[cs - d] = hh + d * 2
                else:
                    h[cs - d] = hh + d // 2
            if ce + d < 40:
                if hh > 8:
                    h[ce + d] = hh - d
                elif hh < 4:
                    h[ce + d] = hh + d * 2
                else:
                    h[ce + d] = hh + d // 2
        py[i] = 242 - hh * 8
        px[i] = 24 + cs * 8

    cells = {}
    for c in range(40):
        for ln in range(13 - h[c], 13):
            cells[(TERRAIN_ROW0 + ln, c)] = 160
    for i in range(1, 6):
        cs = (px[i] - 24) // 8
        ln = 13 - ph[i]
        for c in range(cs, cs + pw[i]):
            cells[(TERRAIN_ROW0 + ln, c)] = 100
    return h, px, pw, py, pb, rf, ph, cells


def collides(shape, sx, sy, cells):
    rows = SHAPES[shape]
    for r in range(SPRITE_ROWS):
        bits = rows[r]
        if not bits:
            continue
        y = sy + r
        row = (y - CHAR_Y0) // 8
        if row < 0:
            continue
        line = (y - CHAR_Y0) % 8
        for k in range(24):
            if not (bits >> (23 - k)) & 1:
                continue
            col = (sx + k - CHAR_X0) // 8
            if not 0 <= col < 40:
                continue
            code = cells.get((row, col))
            if code is None:
                continue
            if (CHARS[code][line] >> (7 - ((sx + k - CHAR_X0) % 8))) & 1:
                return True
    return False


class Sim:
    """One attract attempt on a fixed terrain."""

    def __init__(self, planet, terrain, pp, hm, n2, pad, fe=1000):
        self.pl = planet
        self.h, self.px, self.pw, self.py, self.pb, self.rf, self.ph, self.cells = terrain
        self.pp, self.hm, self.fe = pp, hm, fe
        self.po, self.m2, self.pz, self.e2 = 28, n2 * 10, 28, 0
        self.p, self.q = 187, 0
        self.al = pad
        self.tx = self.px[pad] + (self.pw[pad] - 3) * 4
        self.ap = 0
        wx = self.tx - 56
        if wx < 32:
            wx = self.tx + 56
        self.pp, self.e2 = (wx - 256, 1) if wx > 255 else (wx, 0)

    def world_x(self):
        return self.pp + 256 * self.e2

    def control(self):
        ae = self.tx - self.world_x()
        if self.ap == 0:
            av = 0
            if self.po > 112:
                av = -4
            if self.po < 96:
                av = 4
            aa = abs(ae)
            ah = 0
            if aa > 0:
                ah = 1
            if aa > 4:
                ah = 2
            if aa > 12:
                ah = 3
            if aa > 25:
                ah = 4
            if aa > 40:
                ah = 6
            if ae < 0:
                ah = -ah
            if ae == 0 and self.hm == 0 and self.po > 96:
                self.ap = 1
        else:
            ag = self.py[self.al] - self.po
            av = 3
            if ag > 8:
                av = 6
            if ag > 25:
                av = 12
            if ag > 60:
                av = 25
            ah = 0
            if ae != 0:
                self.ap = 0
        af = math.floor(self.m2 / 10) > av
        if self.hm < ah:
            self.p, self.fr = 188, 0
        elif self.hm > ah:
            self.p, self.fr = 194, 0
        else:
            self.p, self.fr = 187, 16 if not af else 0

    def step(self):
        """Lines 200-495 for one physics tick."""
        pl = self.pl
        self.control()
        if self.fe == 0 or self.fr == 16:
            self.q = 0
            self.m2 += pl.gv
        else:
            self.q = 8
            self.fe -= 1
            if self.p == 187:
                self.m2 -= pl.th
            elif self.p == 188:
                self.m2 += -pl.th + 1
                self.hm += 1
            elif self.p == 194:
                self.m2 += -pl.th + 1
                self.hm -= 1
        self.pz += self.m2 * KA
        if self.pz < 25:
            self.pz = 25
        self.po = int(self.pz)
        self.pp += self.hm
        if self.e2 == 0 and self.pp < 1:
            self.e2, self.pp = 1, 87 + self.pp
        elif self.e2 == 1 and self.pp < 1:
            self.e2, self.pp = 0, 255 + self.pp
        elif self.e2 == 0 and self.pp > 255:
            self.e2, self.pp = 1, self.pp - 255
        elif self.e2 and self.pp > 86:
            self.e2, self.pp = 0, self.pp - 87
        hz = 0
        if collides(self.p, self.world_x(), self.po, self.cells) and self.po > 120:
            hz = 1
        if self.po > 190 and self.e2 == 0 and self.pp < 5:
            hz = 1
        if self.po > 195 and self.e2 and self.pp > 84:
            hz = 1
        return hz

    def run(self, limit=20000):
        for n in range(limit):
            if self.step():
                return self.outcome(n)
            if self.fe < 80:
                return ('fuel', n, None)
        return ('timeout', limit, None)

    def outcome(self, n):
        vm = math.floor(self.m2 / 10)
        if abs(self.hm) > 2:
            return ('crash-hm', n, self.hm)
        if self.p != 187:
            return ('crash-tilt', n, self.p)
        if vm > self.pl.sl:
            return ('crash-vel', n, vm)
        pf = self.world_x()
        for i in range(1, 6):
            if pf < self.px[i] or pf >= self.px[i] + self.pw[i] * 8:
                continue
            if abs(self.po - self.py[i]) > 4:
                continue
            return ('land', n, i)
        return ('crash-nopad', n, (pf, self.po, [(self.px[i], self.py[i]) for i in range(1, 6)]))


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    tally = {}
    worst = (0, None)
    for seed in range(trials):
        rng = random.Random(seed)
        for mars in (0, 1):
            pl = Planet(mars)
            terrain = gen_terrain(rng)
            ep, hp, n2 = 250, -8, pl.ni
            for attempt in range(12):
                pad = attempt % 5 + 1
                if n2 > pl.nc:
                    n2 = pl.nb
                sim = Sim(pl, terrain, ep, hp, n2, pad)
                n2 += pl.ns
                kind, n, info = sim.run()
                tally[kind] = tally.get(kind, 0) + 1
                if kind == 'land' and n > worst[0]:
                    worst = (n, (seed, mars, pad, 1000 - sim.fe))
                if kind != 'land':
                    print(f'seed={seed} mars={mars} pad={pad} -> {kind} @{n} {info} '
                          f'tx={sim.tx} px={sim.px[pad]} pw={sim.pw[pad]} py={sim.py[pad]}')
                ep -= 23
                if ep == 20:
                    ep = 250
                hp += 2
                if hp > 8:
                    hp = -8
    print(tally, 'slowest landing frames/fuel:', worst)


if __name__ == '__main__':
    main()
