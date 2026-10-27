import numpy as np
from dgeo import *

L = 240.0
N_AROUND = 44
KEY_T = [0, 0.8, 1.9, 3.2, 4.5, 5.8, 7.0, 8.0]
KEY_S = [-62, -60, -29, 2, 50, 108, 172, 235]
_tt = np.arange(-2, 10, 1 / 240.0)
_ss = np.interp(_tt, KEY_T, KEY_S)
_k = np.exp(-0.5 * (np.arange(-120, 121) / 60.0) ** 2); _k /= _k.sum()
_ss = np.convolve(np.pad(_ss, 120, mode='edge'), _k, mode='same')[120:-120]
def sigma_h(t): return np.interp(t, _tt, _ss)

CTRL = [(-95, 85, -250), (-40, 50, -130), (-10, 15, -45), (0, 0, 0), (3, -9, 50), (-6, -10, 105),
        (-22, 0, 160), (-20, 22, 215), (0, 50, 270), (22, 85, 320), (30, 120, 380)]

def jaw_angle(t):  # radians, roar
    a = np.sin(np.pi * np.clip((t - 2.3) / 1.9, 0, 1)) ** 1.2 * 0.42
    return 0.04 + a
def bend_amt(t):   # neck bend towards camera (m)
    return 9.0 * smoothstep(2.6, 3.8, t) * (1 - smoothstep(4.6, 6.2, t))

# radius profile
_s = np.linspace(0, L, 2400)
_r = np.interp(_s, [0, 10, 40, 110, 170, 215, 240], [4.4, 5.4, 7.4, 7.4, 5.3, 2.7, 0.4])
_kk = np.exp(-0.5 * (np.arange(-60, 61) / 30.0) ** 2); _kk /= _kk.sum()
_r = np.convolve(np.pad(_r, 60, mode='edge'), _kk, mode='same')[60:-60]
def radius(s): return np.interp(s, _s, _r)

# head profile keypoints
HX = np.array([-3, 2, 6, 10, 14, 18, 22, 25, 27.5, 28.8])
HW = np.array([4.3, 5.3, 5.5, 4.7, 3.6, 2.8, 2.5, 2.8, 1.9, 0.0])
HH = np.array([4.3, 4.9, 5.0, 4.1, 3.1, 2.4, 2.1, 2.2, 1.3, 0.0])
HC = np.array([0.0, 0.7, 1.0, 0.7, 0.2, -0.2, -0.4, -0.4, -0.5, -0.6])
def hprof(x):
    return np.interp(x, HX, HW), np.interp(x, HX, HH), np.interp(x, HX, HC)

def cone_verts(base, dirv, rad, length, n=5):
    K = len(base)
    dirv = unit(dirv)
    ref = np.where(np.abs(dirv[:, [0]]) < 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    p1 = unit(np.cross(dirv, ref)); p2 = np.cross(dirv, p1)
    ph = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = base[:, None, :] + rad[:, None, None] * (np.cos(ph)[None, :, None] * p1[:, None, :] + np.sin(ph)[None, :, None] * p2[:, None, :])
    apex = (base + dirv * length[:, None])[:, None, :]
    V = np.concatenate([ring, apex], 1).reshape(-1, 3)
    i = np.arange(K)[:, None] * (n + 1); j = np.arange(n)[None, :]
    F = np.stack([i + j, i + (j + 1) % n, i + n + np.zeros_like(j)], -1).reshape(-1, 3)
    return V, F

def sphere_verts(c, rad, axis, nu=14, nv=8):
    axis = unit(np.asarray(axis, float))
    ref = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0, 1.0, 0])
    p1 = unit(np.cross(axis, ref)); p2 = np.cross(axis, p1)
    th = np.linspace(0, np.pi, nv)
    C = c[None, :] + rad * np.cos(th)[:, None] * axis[None, :]
    a = rad * np.sin(th)
    V = sweep(C, np.tile(p1, (nv, 1)), np.tile(p2, (nv, 1)), a, a, nu)
    return V, sweep_faces(nv, nu)

class Dragon:
    def __init__(self, seed=3):
        self.path = Path(CTRL)
        rng = np.random.RandomState(seed)
        self.S = np.linspace(0, L, 1300)
        self.rS = radius(self.S)
        # scale rows
        rows = []; s = 0.4
        while s < L - 2:
            rows.append(s); s += 0.085 * radius(s) * 1.05
        self.rows = np.array(rows); K = len(rows)
        self.nrows = K
        m = np.arange(N_AROUND)
        self.phi = (m[None, :] + 0.5 * (np.arange(K)[:, None] % 2)) * 2 * np.pi / N_AROUND
        self.phi = self.phi + rng.rand(K, N_AROUND) * 0.04
        self.rnd = rng.rand(K, N_AROUND)
        self.rows_r = radius(self.rows)
        # scale tile template
        self.uu = np.array([0, .25, .5, .75, 1.0]); self.vv = np.array([-1, 0, 1.0])
        # faces for one tile 5x3
        f = []
        for a in range(4):
            for b in range(2):
                f.append([a * 3 + b, a * 3 + b + 1, (a + 1) * 3 + b + 1, (a + 1) * 3 + b])
        self.tile_f = np.array(f)
        nt = K * N_AROUND
        self.scale_F = (self.tile_f[None] + (np.arange(nt) * 15)[:, None, None]).reshape(-1, 4)
        # scale attrs (rnd, belly, along, u)
        uu3 = np.repeat(self.uu, 3)
        attr = np.zeros((K, N_AROUND, 15, 4), np.float32)
        attr[..., 0] = self.rnd[..., None]
        attr[..., 1] = smoothstep(0.25, 0.85, -np.cos(self.phi))[..., None]
        attr[..., 2] = (self.rows / L)[:, None, None]
        attr[..., 3] = uu3[None, None, :]
        self.scale_attr = attr.reshape(-1, 4)
        # tube faces
        self.n_ring = 64
        self.tube_F = sweep_faces(len(self.S), self.n_ring)
        # spines
        sp = []; s = 2.0
        while s < 185:
            sp.append(s); s += 0.55 * radius(s) * 0.55 + 0.8
        self.sp_s = np.array(sp); self.sp_rnd = rng.rand(len(sp))
        # head
        self.hx = np.linspace(-3, 28.8, 40)
        self.skull_F = sweep_faces(len(self.hx), 22)
        self.jx = np.linspace(1.0, 26.0, 34)
        self.jaw_F = sweep_faces(len(self.jx), 18)
        ut = np.linspace(9, 26.5, 11)
        self.tooth_x = ut
        self.tooth_len = (0.9 + 1.2 * rng.rand(11)) * (1 + 0.8 * (ut > 23))
        self.horn_t = np.linspace(0, 1, 26)
        self.horn_F = sweep_faces(26, 8)
        self.wh_t = np.linspace(0, 1, 40)
        self.wh_F = sweep_faces(40, 5)

    # ---- centerline
    def centerline(self, t):
        sh = float(sigma_h(t)); S = self.S
        sg = sh - S
        P, U, R = self.path.at(sg)
        z = P[:, 2]
        m = smoothstep(2, 70, z)
        lam = 105.0; k = 2 * np.pi / lam; w = k * 14.0
        amp = 8.5 * (0.12 + 0.88 * smoothstep(0, 80, S)) * m
        off = (amp * np.sin(k * S - w * t))[:, None] * U + (0.65 * amp * np.cos(0.8 * k * S - 0.8 * w * t + 1.0))[:, None] * R
        C = P + off
        d = bend_amt(t)
        if d > 1e-3:
            q = np.clip(1 - S / 38.0, 0, 1) ** 2
            C = C + (d * q)[:, None] * unit(np.array([[0.25, -1.0, 0.2]]))
        return C

    def frames(self, C):
        # transport with reference to the world x so crest faces +x
        T, U, R = transport(C, ref=(1.0, 0.0, 0.0))
        return T, U, R

    def surf(self, Cf, Uf, Rf, s, phi, lift=0.0, rscale=1.0):
        C = np.stack([np.interp(s, self.S, Cf[:, k]) for k in range(3)], -1)
        U = np.stack([np.interp(s, self.S, Uf[:, k]) for k in range(3)], -1)
        R = np.stack([np.interp(s, self.S, Rf[:, k]) for k in range(3)], -1)
        r = radius(s) * rscale
        cs = np.cos(phi); sn = np.sin(phi)
        ra = r * np.where(cs < 0, 0.88, 1.0) + lift
        rb = r + lift
        return C + (ra * cs)[..., None] * U + (rb * sn)[..., None] * R

    def build(self, t):
        parts = {}
        C = self.centerline(t)
        T, U, R = self.frames(C)
        S = self.S
        # base tube
        ph = np.linspace(0, 2 * np.pi, self.n_ring, endpoint=False)
        cs, sn = np.cos(ph), np.sin(ph)
        rr = self.rS[:, None] * 0.955
        ra = rr * np.where(cs < 0, 0.88, 1.0)[None, :]
        Vt = C[:, None, :] + (ra * cs[None, :])[..., None] * U[:, None, :] + (rr * sn[None, :])[..., None] * R[:, None, :]
        parts['tube'] = (Vt.reshape(-1, 3), self.tube_F)
        # scales
        K, Na = self.phi.shape
        s0 = self.rows[:, None, None]
        ds = (0.085 * self.rows_r)[:, None, None]
        arc = (2 * np.pi / N_AROUND)
        u = self.uu[None, None, :, None]; v = self.vv[None, None, None, :]
        Lt = 1.85 * ds
        wd = 1.18 * arc * (1 - 0.82 * u ** 2.4)
        sg = s0[..., None] + u * Lt[..., None] if False else (s0[..., None] + (self.uu[None, None, :, None] * Lt[..., None]))
        ph_ = self.phi[:, :, None, None] + v * 0.5 * wd
        sg = np.broadcast_to(sg, ph_.shape)
        rnd = self.rnd[:, :, None, None]
        lift = (0.035 + (0.30 + 0.12 * rnd) * (u ** 1.4)) * Lt[..., None] - 0.10 * (v ** 2) * (wd * self.rows_r[:, None, None, None])
        lift = np.maximum(lift, 0.0) * 1.0 + 0.0
        Vs = self.surf(C, U, R, sg.ravel(), ph_.ravel(), lift.ravel() * 1.0 + 0.0, 0.985)
        parts['scales'] = (Vs, self.scale_F)
        # spines (dorsal)
        s_ = self.sp_s; r_ = radius(s_)
        b = (0.55 * r_ * 0.55 + 0.8)
        ht = r_ * (0.13 + 0.17 * self.sp_rnd) * (0.65 + 0.35 * smoothstep(120, 20, s_)) + 0.4
        base0 = self.surf(C, U, R, s_, np.zeros_like(s_), 0.0, 0.975)
        base1 = self.surf(C, U, R, s_ + b, np.zeros_like(s_), 0.0, 0.975)
        Cn = np.stack([np.interp(s_, S, C[:, k]) for k in range(3)], -1)
        Un = unit(base0 - Cn)
        Rn = np.stack([np.interp(s_, S, R[:, k]) for k in range(3)], -1)
        th = (0.16 * b)[:, None] * Rn
        apex = (base0 + base1) / 2 + Un * ht[:, None] + (base1 - base0) * 0.9
        Vsp = np.stack([base0 - th, base0 + th, base1 + th, base1 - th, apex], 1).reshape(-1, 3)
        i = (np.arange(len(s_)) * 5)[:, None]
        Fsp = np.stack([np.stack([i[:, 0] + a, i[:, 0] + (a + 1) % 4, i[:, 0] + 4], -1) for a in range(4)], 1).reshape(-1, 3)
        parts['spines'] = (Vsp, Fsp)
        # ---- head (built in LOCAL head coords; object matrix = [Fw,U0,Z0,C0])
        C0 = C[0]
        Fw = unit(C[0] - C[12])
        U0 = U[0] - Fw * np.dot(U[0], Fw); U0 = unit(U0)
        Z0 = np.cross(Fw, U0)
        def loc(x, y, z):
            x = np.asarray(x, float); y = np.asarray(y, float) + 0 * x; z = np.asarray(z, float) + 0 * x
            return np.stack([x, y, z], -1)
        EX = np.array([1.0, 0, 0]); EY = np.array([0, 1.0, 0]); EZ = np.array([0, 0, 1.0])
        nh = len(self.hx)
        w, h, c = hprof(self.hx)
        cen = loc(self.hx, c, 0 * self.hx)
        Vk = sweep(cen, np.tile(EY, (nh, 1)), np.tile(EZ, (nh, 1)), h, w, 22)
        parts['skull'] = (Vk, self.skull_F)
        wj_, hj_, cj_ = hprof(self.jx)
        sq = np.clip((29 - self.jx) / 6, 0.05, 1) ** 0.5
        wj = 0.80 * wj_ * sq; hj = (0.36 * hj_ + 0.25) * sq
        yj = cj_ - hj_ * 0.95 - hj * 0.55
        al = jaw_angle(t)
        xp = 2.0; yp = float(hprof(2.0)[2] - hprof(2.0)[1] * 0.8)
        def jrot(x, y):
            dx = x - xp; dy = y - yp
            return xp + dx * np.cos(al) + dy * np.sin(al), yp - dx * np.sin(al) + dy * np.cos(al)
        jx2, jy2 = jrot(self.jx, yj)
        cenj = loc(jx2, jy2, 0 * jx2)
        Uj = np.array([-np.sin(al), np.cos(al), 0.0])
        Vj = sweep(cenj, np.tile(Uj, (len(self.jx), 1)), np.tile(EZ, (len(self.jx), 1)), hj, wj, 18)
        parts['jaw'] = (Vj, self.jaw_F)
        tx = self.tooth_x; wt, ht_, ct = hprof(tx)
        bases = []; dirs = []; rads = []; lens = []
        for sg_ in (-1, 1):
            bases.append(loc(tx, ct - ht_ * 0.60, sg_ * wt * 0.80)); dirs.append(np.tile(-EY + 0.35 * EX, (len(tx), 1)))
            rads.append(0.22 + 0.04 * tx / 4); lens.append(self.tooth_len)
        lx = np.linspace(8, 24, 9)
        wl_, hl_, cl_ = hprof(lx); sql = np.clip((29 - lx) / 6, 0.05, 1) ** 0.5
        wl = 0.80 * wl_ * sql; hl = (0.36 * hl_ + 0.25) * sql
        yl = cl_ - hl_ * 0.95 - hl * 0.55 + hl * 0.62
        lx2, ly2 = jrot(lx, yl)
        for sg_ in (-1, 1):
            bases.append(loc(lx2, ly2, sg_ * wl * 0.85)); dirs.append(np.tile(Uj + 0.2 * EX, (len(lx), 1)))
            rads.append(np.full(len(lx), 0.2)); lens.append(0.8 + 0.7 * np.random.RandomState(5).rand(len(lx)))
        Vtt, Ftt = cone_verts(np.concatenate(bases), np.concatenate(dirs), np.concatenate(rads), np.concatenate(lens), 5)
        parts['teeth'] = (Vtt, Ftt)
        ex = 12.0; we, he, ce = hprof(ex)
        Ve = []
        for sg_ in (-1, 1):
            cpos = loc(ex, ce + he * 0.52, sg_ * we * 0.80)
            V1, F1 = sphere_verts(cpos, 0.75, EZ * sg_ + 0.3 * EX)
            Ve.append(V1)
        parts['eyes'] = (np.concatenate(Ve), np.concatenate([F1, F1 + len(Ve[0])]))
        Vh = []
        tt = self.horn_t
        specs = [(1.0, 1.0, 17, 10, 1.05), (7.5, 0.85, 10, 7, 0.55)]
        for (x0, yf, ln, up, rad0) in specs:
            for sg_ in (-1, 1):
                w0, h0, c0 = hprof(x0)
                p = np.stack([x0 - ln * tt + 3 * tt ** 2, c0 + h0 * yf * 0.85 + up * tt - 0.75 * up * tt ** 2, sg_ * (w0 * 0.55 + 4.5 * tt)], -1)
                Th, Uh, Rh = transport(p, ref=(0, 1.0, 0))
                rad = rad0 * (1 - tt) ** 0.85 + 0.04
                Vh.append(sweep(p, Uh, Rh, rad, rad, 8))
        parts['horns'] = (np.concatenate(Vh), np.concatenate([self.horn_F + k * len(Vh[0]) for k in range(len(Vh))]))
        Vw = []
        tw = self.wh_t
        for (Lw, sg_, yy) in [(44, 1, 0.0), (44, -1, 0.0), (28, 1, -1.2), (28, -1, -1.2)]:
            wn, hn, cn = hprof(24.0)
            ph0 = 0.9 * sg_
            p = np.stack([24.5 - 0.88 * Lw * tw,
                          cn + yy + 3.0 * tw * np.sin(2 * np.pi * 1.1 * tw - 2.6 * t + ph0) - 4.0 * tw ** 1.5,
                          sg_ * (1.6 + 9.0 * tw + 2.5 * tw * np.sin(2 * np.pi * 0.9 * tw - 2.1 * t + ph0))], -1)
            Th, Uh, Rh = transport(p, ref=(0, 1.0, 0))
            rad = 0.26 * (1 - tw) ** 0.7 + 0.035
            Vw.append(sweep(p, Uh, Rh, rad, rad, 5))
        parts['whiskers'] = (np.concatenate(Vw), np.concatenate([self.wh_F + k * len(Vw[0]) for k in range(len(Vw))]))
        info = dict(C0=C0, Fw=Fw, U0=U0, Z0=Z0, C=C)
        return parts, info
