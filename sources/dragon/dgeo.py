import numpy as np

def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)

_rng = np.random.RandomState(7)
_T = _rng.rand(256, 256).astype(np.float32)

def vnoise2(x, y):
    xi = np.floor(x).astype(np.int64); yi = np.floor(y).astype(np.int64)
    fx = x - xi; fy = y - yi
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a = _T[xi & 255, yi & 255]; b = _T[(xi + 1) & 255, yi & 255]
    c = _T[xi & 255, (yi + 1) & 255]; d = _T[(xi + 1) & 255, (yi + 1) & 255]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

def fbm2(x, y, octv=5, lac=2.03, gain=0.5):
    s = 0.0; amp = 1.0; tot = 0.0
    for i in range(octv):
        s = s + amp * vnoise2(x + 17.3 * i, y - 9.1 * i); tot += amp
        x = x * lac + 3.7; y = y * lac - 1.3; amp *= gain
    return s / tot

def catmull(points, n_per=60):
    P = np.asarray(points, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t = np.linspace(0, 1, n_per, endpoint=False)[:, None]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2][None])
    return np.vstack(out)

def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)

def transport(C, ref=(1.0, 0.0, 0.0)):
    """Parallel-transport frames along polyline C. returns T,U,R."""
    T = unit(np.gradient(C, axis=0))
    U = np.zeros_like(C)
    r = np.asarray(ref, float)
    u = r - T[0] * np.dot(r, T[0]); u /= np.linalg.norm(u)
    U[0] = u
    for i in range(1, len(C)):
        u = U[i - 1] - T[i] * np.dot(U[i - 1], T[i])
        U[i] = u / np.linalg.norm(u)
    R = np.cross(T, U)
    return T, U, R

class Path:
    def __init__(self, ctrl, step=0.5):
        pts = catmull(ctrl, 80)
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
        # sigma=0 at the control point (0,0,0)
        i0 = np.argmin(np.linalg.norm(pts, axis=1))
        sig = d - d[i0]
        self.sig = np.arange(sig[0], sig[-1], step)
        self.P = np.stack([np.interp(self.sig, sig, pts[:, k]) for k in range(3)], 1)
        self.T, self.U, self.R = transport(self.P, ref=(1, 0, 0))
        self.step = step
    def at(self, s):
        s = np.asarray(s, float)
        out = []
        for A in (self.P, self.U, self.R):
            out.append(np.stack([np.interp(s, self.sig, A[:, k]) for k in range(3)], -1))
        return out  # P,U,R

def sweep(C, U, R, a, b, n, phi0=0.0):
    """tube around polyline C with elliptical section (a along U, b along R). returns verts (M*n,3), quads idx."""
    M = len(C)
    ph = phi0 + np.linspace(0, 2 * np.pi, n, endpoint=False)
    cs, sn = np.cos(ph), np.sin(ph)
    V = C[:, None, :] + (a[:, None] * cs[None, :])[:, :, None] * U[:, None, :] + (b[:, None] * sn[None, :])[:, :, None] * R[:, None, :]
    return V.reshape(-1, 3)

def sweep_faces(M, n):
    i = np.arange(M - 1)[:, None]; j = np.arange(n)[None, :]
    a = i * n + j; b = i * n + (j + 1) % n; c = (i + 1) * n + (j + 1) % n; d = (i + 1) * n + j
    return np.stack([a, b, c, d], -1).reshape(-1, 4)

def rot_about(v, axis, ang):
    axis = unit(axis)
    c, s = np.cos(ang), np.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * np.dot(v, axis) * (1 - c)
