import sys, os, math, time, argparse
sys.path.insert(0, '/workspace/dragon')
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix, Quaternion
from dgeo import *
import dragon as DR
import osl_src

ap = argparse.ArgumentParser()
ap.add_argument('--frames', default='0')
ap.add_argument('--res', default='854x480')
ap.add_argument('--spp', type=int, default=32)
ap.add_argument('--out', default='/workspace/dragon/prev')
ap.add_argument('--fog', type=int, default=1)
ap.add_argument('--cloud', type=int, default=1)
ap.add_argument('--threads', type=int, default=8)
ap.add_argument('--sunrot', type=float, default=0.0)
ap.add_argument('--sunel', type=float, default=5.0)
ap.add_argument('--save', default='')
ap.add_argument('--vstep', type=float, default=1.0)
ap.add_argument('--fbase', type=float, default=-1)
ap.add_argument('--fhaze', type=float, default=-1)
ap.add_argument('--camoff', type=float, default=0.0)
ap.add_argument('--exposure', type=float, default=0.0)
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = ap.parse_args(argv)
CAMOFF = A.camoff
FPS = 24
TC = 1.9  # burst time

# ------------------------------------------------------------------ terrain (numpy)
CELL = 9.0
def h21(x, y):
    fx = (x * 0.1031) % 1.0; fy = (y * 0.1031) % 1.0
    d = fx * (fy + 33.33) + fy * (fx + 33.33) + fx * (fx + 33.33)
    return ((fx + d + fy + d) * (fx + d)) % 1.0

def plates(px, py):
    qx = px + 1.7 * np.sin(py * 0.31 + 1.1) + 0.8 * np.sin(py * 0.83 + px * 0.17)
    qy = py + 1.7 * np.sin(px * 0.29 + 0.3) + 0.8 * np.sin(px * 0.71 - py * 0.2)
    u = qx / CELL; v = qy / CELL
    iu = np.floor(u); iv = np.floor(v)
    d1 = np.full(px.shape, 1e9); d2 = np.full(px.shape, 1e9)
    cid_u = np.zeros(px.shape); cid_v = np.zeros(px.shape); fxn = np.zeros(px.shape); fyn = np.zeros(px.shape)
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            cu = iu + a; cv = iv + b
            fx = cu + 0.5 + 0.8 * (h21(cu, cv) - 0.5)
            fy = cv + 0.5 + 0.8 * (h21(cu + 57.1, cv - 23.7) - 0.5)
            d = np.sqrt((u - fx) ** 2 + (v - fy) ** 2) * CELL
            c1 = d < d1
            c2 = (~c1) & (d < d2)
            d2 = np.where(c1, d1, np.where(c2, d, d2))
            cid_u = np.where(c1, cu, cid_u); cid_v = np.where(c1, cv, cid_v)
            fxn = np.where(c1, fx, fxn); fyn = np.where(c1, fy, fyn)
            d1 = np.where(c1, d, d1)
    return d1, d2, cid_u, cid_v, fxn * CELL, fyn * CELL

def terrain_h(X, Y):
    r = np.sqrt(X * X + Y * Y)
    roll = 5.0 * (fbm2(X / 110 + 3, Y / 110 - 2, 4) - 0.5) * smoothstep(60, 260, r)
    rg = 1 - np.abs(2 * fbm2(X / 520 + 11, Y / 520 + 5, 5) - 1)
    mount = 190.0 * rg ** 2.2 * smoothstep(330, 900, r)
    rocky = 1.0 * (fbm2(X / 7 + 1, Y / 7, 4) - 0.5) * smoothstep(5, 70, r) + 0.18 * (fbm2(X / 2.2, Y / 2.2, 3) - 0.5)
    return roll + mount + rocky

# ------------------------------------------------------------------ helpers
def set_geometry(me, V, F):
    n = len(V); k = F.shape[1]; nf = len(F)
    me.clear_geometry()
    me.vertices.add(n); me.loops.add(nf * k); me.polygons.add(nf)
    me.vertices.foreach_set('co', V.astype(np.float32).ravel())
    me.loops.foreach_set('vertex_index', F.astype(np.int32).ravel())
    me.polygons.foreach_set('loop_start', (np.arange(nf) * k).astype(np.int32))
    me.polygons.foreach_set('use_smooth', np.ones(nf, bool))
    me.update(calc_edges=True)

def new_obj(name, mat=None):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None: me.materials.append(mat)
    return ob

def mk_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    return m, nt

def principled(nt):
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    return p, out

def osl_node(nt, name, src):
    txt = bpy.data.texts.new(name + '.osl'); txt.write(src)
    s = nt.nodes.new('ShaderNodeScript'); s.mode = 'INTERNAL'; s.script = txt
    return s

def setv(node, **kw):
    for k, v in kw.items(): node.inputs[k].default_value = v

# ------------------------------------------------------------------ setup
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W_, H_ = [int(x) for x in A.res.split('x')]
sc.render.resolution_x = W_; sc.render.resolution_y = H_; sc.render.resolution_percentage = 100
sc.render.fps = FPS
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'; cy.shading_system = True
cy.samples = A.spp; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.03; cy.adaptive_min_samples = 12
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'; cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
cy.max_bounces = 5; cy.diffuse_bounces = 2; cy.glossy_bounces = 3; cy.transmission_bounces = 2; cy.volume_bounces = 2
cy.transparent_max_bounces = 4
cy.sample_clamp_indirect = 5.0; cy.sample_clamp_direct = 0.0
cy.volume_step_rate = A.vstep; cy.volume_max_steps = 256
cy.seed = 7; cy.use_animated_seed = False
sc.render.threads_mode = 'FIXED'; sc.render.threads = A.threads
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '16'
sc.view_settings.view_transform = 'AgX'
looks = [i.identifier for i in sc.view_settings.bl_rna.properties['look'].enum_items]
for lk in looks:
    if 'Medium High' in lk: sc.view_settings.look = lk
sc.view_settings.exposure = A.exposure
sc.render.use_motion_blur = False

# world
world = bpy.data.worlds.new('W'); world.use_nodes = True; sc.world = world
wn = world.node_tree; wn.nodes.clear()
sky = wn.nodes.new('ShaderNodeTexSky'); sky.sky_type = 'NISHITA'
sky.sun_elevation = math.radians(A.sunel); sky.sun_rotation = math.radians(A.sunrot)
sky.air_density = 1.2; sky.dust_density = 2.2; sky.ozone_density = 1.0; sky.sun_size = math.radians(1.2); sky.sun_intensity = 1.0; sky.altitude = 0
bg = wn.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0
wo = wn.nodes.new('ShaderNodeOutputWorld')
wn.links.new(sky.outputs['Color'], bg.inputs['Color']); wn.links.new(bg.outputs[0], wo.inputs['Surface'])

# ------------------------------------------------------------------ ground
NR, NS = 257, 512
rr = 1.2 * (1.028 ** np.arange(NR)) - 1.2; rr[0] = 0.0
th = np.linspace(0, 2 * np.pi, NS, endpoint=False)
GX = rr[:, None] * np.cos(th)[None, :]; GY = rr[:, None] * np.sin(th)[None, :]
GR = np.sqrt(GX ** 2 + GY ** 2)
GH0 = terrain_h(GX, GY)
GH0[0, :] = GH0[0, 0]
near = GR < 100.0
nx = GX[near]; ny = GY[near]
d1, d2, cu_, cv_, fcx, fcy = plates(nx, ny)
P_dz = h21(cu_ + 3.3, cv_ + 9.1); P_tx = h21(cu_ + 11.7, cv_ - 4.2) - 0.5; P_ty = h21(cu_ - 7.7, cv_ + 2.2) - 0.5
P_dx = nx - fcx; P_dy = ny - fcy
nr_ = GR[near]
gi = np.arange(NR * NS).reshape(NR, NS)
gF = np.stack([gi[:-1, :], gi[:-1, (np.arange(NS) + 1) % NS], gi[1:, (np.arange(NS) + 1) % NS], gi[1:, :]], -1).reshape(-1, 4)

dragon = DR.Dragon()

def ground_pit_r(t):
    return 9.3 * smoothstep(TC - 0.05, TC + 0.4, t) + 0.0

def ground_Z(t):
    Z = GH0.copy()
    z = np.zeros(nr_.shape)
    r = nr_
    # dome
    Hd = 6.0 * smoothstep(0.4, TC, t) * (1 - 0.5 * smoothstep(TC, TC + 0.7, t))
    z += Hd * np.exp(-(r / 26.0) ** 2)
    # plates
    env = smoothstep(TC - 0.02, TC + 0.3, t) * np.exp(-(r / 42.0) ** 2)
    lift = (P_dz * 2.4 - 0.4) * env
    z += lift + (P_tx * P_dx + P_ty * P_dy) * 0.5 * env
    # pre-burst hairline crack heave
    z += 0.25 * smoothstep(0.8, TC, t) * np.exp(-(r / 30) ** 2) * (np.clip(1 - d2 + d1 + 0, 0, 1) * 0 + (P_dz - 0.5))
    # pit
    Rp = ground_pit_r(t)
    if Rp > 0.1:
        z -= 22.0 * smoothstep(Rp * 1.0, Rp * 0.45, r)
        z += 1.6 * np.exp(-((r - 1.45 * Rp) / 3.2) ** 2) * env
    Z[near.reshape(NR, NS)] += z
    return Z

mat_g, nt = mk_mat('ground')
p, out = principled(nt)
tc = nt.nodes.new('ShaderNodeTexCoord')
n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.35; n1.inputs['Detail'].default_value = 8
n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 4.0; n2.inputs['Detail'].default_value = 6
nt.links.new(tc.outputs['Object'], n1.inputs['Vector']); nt.links.new(tc.outputs['Object'], n2.inputs['Vector'])
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.010, 0.010, 0.011, 1); ramp.color_ramp.elements[1].color = (0.075, 0.060, 0.050, 1)
ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[1].position = 0.7
nt.links.new(n1.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.7; bump.inputs['Distance'].default_value = 0.4
nt.links.new(n2.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
p.inputs['Roughness'].default_value = 0.72
og = osl_node(nt, 'ground', osl_src.GROUND)
nt.links.new(tc.outputs['Object'], og.inputs['Pin'])
nt.links.new(og.outputs['Emit'], p.inputs['Emission Strength'])
p.inputs['Emission Color'].default_value = (1.0, 0.30, 0.05, 1)
OG = og
gobj = new_obj('ground', mat_g)
set_geometry(gobj.data, np.stack([GX.ravel(), GY.ravel(), GH0.ravel()], -1), gF)

# boulders (foreground + scattered)
def make_rock_mesh(name, seed, sub=3):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    rng = np.random.RandomState(seed)
    for v in bm.verts:
        c = np.array(v.co)
        n = fbm2(np.array(c[0] * 2.2 + c[2] * 1.3 + seed), np.array(c[1] * 2.2 - c[2] * 1.7), 4)
        v.co = Vector(c * (0.72 + 0.65 * n))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p_ in me.polygons: p_.use_smooth = True
    return me
mat_rock, nt = mk_mat('rock')
p, out = principled(nt); p.inputs['Base Color'].default_value = (0.016, 0.015, 0.016, 1); p.inputs['Roughness'].default_value = 0.8
tcr = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 8
bm_ = nt.nodes.new('ShaderNodeBump'); bm_.inputs['Strength'].default_value = 0.9
nt.links.new(tcr.outputs['Object'], nz.inputs['Vector']); nt.links.new(nz.outputs['Fac'], bm_.inputs['Height']); nt.links.new(bm_.outputs['Normal'], p.inputs['Normal'])
rock_meshes = [make_rock_mesh('rk%d' % i, 10 + i) for i in range(4)]
for m_ in rock_meshes: m_.materials.append(mat_rock)
rng = np.random.RandomState(21)
# foreground boulders
fg = [(-14, -128, 6, 3.5, 4), (11, -131, 5, 3, 3), (-5, -136, 3, 1.8, 2), (23, -118, 8, 4.5, 5), (-27, -113, 9, 5, 5),
      (4, -139, 2.2, 1.3, 1.4), (-9, -118, 3.2, 2, 1.8)]
for i, (x, y, sx, sz, sy) in enumerate(fg):
    ob = bpy.data.objects.new('fg%d' % i, rock_meshes[i % 4]); sc.collection.objects.link(ob)
    gz = float(terrain_h(np.array(x), np.array(y)))
    ob.location = (x, y, gz + sz * 0.25); ob.scale = (sx, sy, sz); ob.rotation_euler = (0, 0, rng.rand() * 6.28)
# scattered mid-distance rocks
for i in range(60):
    a = rng.rand() * 6.283; rdist = 30 + 280 * rng.rand() ** 1.2
    x, y = rdist * math.cos(a), rdist * math.sin(a)
    if abs(x) < 30 and abs(y) < 30: continue
    s_ = 1.5 + 6 * rng.rand() ** 2
    ob = bpy.data.objects.new('sr%d' % i, rock_meshes[i % 4]); sc.collection.objects.link(ob)
    gz = float(terrain_h(np.array(x), np.array(y)))
    ob.location = (x, y, gz + s_ * 0.2); ob.scale = (s_ * (0.8 + 0.6 * rng.rand()), s_ * (0.8 + 0.6 * rng.rand()), s_ * 0.55); ob.rotation_euler = (0, 0, rng.rand() * 6.28)

# debris
NDEB = 48
deb = []
for i in range(NDEB):
    ob = bpy.data.objects.new('deb%d' % i, rock_meshes[i % 4]); sc.collection.objects.link(ob)
    a = rng.rand() * 6.283; r0 = 6 + 8 * rng.rand()
    sp = 4 + 22 * rng.rand() ** 1.3
    deb.append(dict(ob=ob, p0=np.array([r0 * math.cos(a), r0 * math.sin(a), 1 + 3 * rng.rand()]),
                    v=np.array([sp * math.cos(a + 0.3 * rng.randn()), sp * math.sin(a + 0.3 * rng.randn()), 18 + 55 * rng.rand() ** 1.2]),
                    sz=(0.3 + 1.7 * rng.rand() ** 2.5) * np.array([1, 0.8 + 0.4 * rng.rand(), 0.7 + 0.4 * rng.rand()]),
                    ax=unit(rng.randn(3)), w=(rng.rand() - 0.5) * 3.0, t0=TC + 0.05 * rng.rand()))
G_ACC = 9.81

# ------------------------------------------------------------------ dragon objects + materials
def mat_scale():
    m, nt = mk_mat('scale'); p, out = principled(nt)
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'sc'
    sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(vc.outputs['Color'], sp.inputs['Color'])
    mixA = nt.nodes.new('ShaderNodeMix'); mixA.data_type = 'RGBA'
    mixA.inputs['A'].default_value = (0.010, 0.050, 0.060, 1); mixA.inputs['B'].default_value = (0.020, 0.115, 0.090, 1)
    nt.links.new(sp.outputs['Red'], mixA.inputs['Factor'])
    # tip brighten
    mixT = nt.nodes.new('ShaderNodeMix'); mixT.data_type = 'RGBA'
    mixT.inputs['B'].default_value = (0.10, 0.28, 0.22, 1)
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3.0
    nt.links.new(vc.outputs['Alpha'], pw.inputs[0])
    mulT = nt.nodes.new('ShaderNodeMath'); mulT.operation = 'MULTIPLY'; mulT.inputs[1].default_value = 0.55
    nt.links.new(pw.outputs[0], mulT.inputs[0])
    nt.links.new(mulT.outputs[0], mixT.inputs['Factor']); nt.links.new(mixA.outputs['Result'], mixT.inputs['A'])
    mixB = nt.nodes.new('ShaderNodeMix'); mixB.data_type = 'RGBA'
    mixB.inputs['B'].default_value = (0.20, 0.14, 0.07, 1)
    nt.links.new(sp.outputs['Green'], mixB.inputs['Factor']); nt.links.new(mixT.outputs['Result'], mixB.inputs['A'])
    nt.links.new(mixB.outputs['Result'], p.inputs['Base Color'])
    p.inputs['Metallic'].default_value = 0.55
    mr = nt.nodes.new('ShaderNodeMath'); mr.operation = 'MULTIPLY_ADD'; mr.inputs[1].default_value = 0.30; mr.inputs[2].default_value = 0.26
    nt.links.new(sp.outputs['Red'], mr.inputs[0]); nt.links.new(mr.outputs[0], p.inputs['Roughness'])
    p.inputs['Coat Weight'].default_value = 0.25; p.inputs['Coat Roughness'].default_value = 0.15
    ft = nt.nodes.new('ShaderNodeMath'); ft.operation = 'MULTIPLY_ADD'; ft.inputs[1].default_value = 500; ft.inputs[2].default_value = 280
    nt.links.new(sp.outputs['Red'], ft.inputs[0]); nt.links.new(ft.outputs[0], p.inputs['Thin Film Thickness'])
    p.inputs['Thin Film IOR'].default_value = 1.5
    return m
def mat_skin(col=(0.012, 0.055, 0.060), rough=0.45, cell=1.0, metal=0.35):
    m, nt = mk_mat('skin'); p, out = principled(nt)
    tcx = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature = 'SMOOTH_F1'; vo.inputs['Scale'].default_value = 0.9; vo.inputs['Smoothness'].default_value = 0.35
    vo.inputs['Randomness'].default_value = 0.8
    nt.links.new(tcx.outputs['Object'], vo.inputs['Vector'])
    vo2 = nt.nodes.new('ShaderNodeTexVoronoi'); vo2.feature = 'F1'; vo2.inputs['Scale'].default_value = 0.9; vo2.inputs['Randomness'].default_value = 0.8
    nt.links.new(tcx.outputs['Object'], vo2.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 1.0; bump.inputs['Distance'].default_value = 0.25
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(vo.outputs['Distance'], inv.inputs[1]); nt.links.new(inv.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    mx.inputs['A'].default_value = (col[0] * 0.6, col[1] * 0.6, col[2] * 0.6, 1); mx.inputs['B'].default_value = (col[0] * 1.6, col[1] * 1.7, col[2] * 1.3, 1)
    sepc = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(vo2.outputs['Color'], sepc.inputs['Color'])
    nt.links.new(sepc.outputs['Red'], mx.inputs['Factor'])
    nt.links.new(mx.outputs['Result'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    p.inputs['Coat Weight'].default_value = 0.2
    return m
def mat_simple(name, col, rough, metal=0.0, emit=None, es=0.0):
    m, nt = mk_mat(name); p, out = principled(nt)
    p.inputs['Base Color'].default_value = (*col, 1); p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    if emit is not None:
        p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = es
    return m
M_scale = mat_scale(); M_skin = mat_skin(); M_tube = mat_simple('tube', (0.006, 0.022, 0.025), 0.6)
M_horn = mat_simple('horn', (0.05, 0.035, 0.022), 0.32, 0.1); M_tooth = mat_simple('tooth', (0.45, 0.40, 0.30), 0.35)
M_eye = mat_simple('eye', (0.01, 0.01, 0.01), 0.3, emit=(1.0, 0.50, 0.06), es=60.0)
M_whisk = mat_simple('whisk', (0.02, 0.10, 0.09), 0.45, 0.3)
M_spine = mat_simple('spine', (0.07, 0.045, 0.02), 0.35, 0.2)
parts_obj = {}
for name, mat in [('tube', M_tube), ('scales', M_scale), ('spines', M_spine), ('skull', M_skin), ('jaw', M_skin), ('teeth', M_tooth),
                  ('eyes', M_eye), ('horns', M_horn), ('whiskers', M_whisk)]:
    parts_obj[name] = new_obj(name, mat)
HEAD_PARTS = ['skull', 'jaw', 'teeth', 'eyes', 'horns', 'whiskers']
_first = {'v': True}
def update_dragon(t):
    parts, info = dragon.build(t)
    for name, (V, F) in parts.items():
        ob = parts_obj[name]; me = ob.data
        if _first['v']:
            set_geometry(me, V, F)
            if name == 'scales':
                ca = me.color_attributes.new('sc', 'FLOAT_COLOR', 'POINT')
                ca.data.foreach_set('color', dragon.scale_attr.astype(np.float32).ravel())
        else:
            me.vertices.foreach_set('co', V.astype(np.float32).ravel()); me.update()
    _first['v'] = False
    M = Matrix(((info['Fw'][0], info['U0'][0], info['Z0'][0], info['C0'][0]),
                (info['Fw'][1], info['U0'][1], info['Z0'][1], info['C0'][1]),
                (info['Fw'][2], info['U0'][2], info['Z0'][2], info['C0'][2]),
                (0, 0, 0, 1)))
    for n in HEAD_PARTS: parts_obj[n].matrix_world = M
    return info

# ------------------------------------------------------------------ volumes
def make_volume(name, size, zmin, zmax, src, scatter, aniso):
    me = bpy.data.meshes.new(name)
    hx = size
    V = np.array([[-hx, -hx, zmin], [hx, -hx, zmin], [hx, hx, zmin], [-hx, hx, zmin], [-hx, -hx, zmax], [hx, -hx, zmax], [hx, hx, zmax], [-hx, hx, zmax]], float)
    F = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])
    set_geometry(me, V, F)
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    m, nt = mk_mat(name); out = nt.nodes.new('ShaderNodeOutputMaterial')
    g = nt.nodes.new('ShaderNodeNewGeometry'); o = osl_node(nt, name, src)
    vs = nt.nodes.new('ShaderNodeVolumeScatter'); vs.inputs['Color'].default_value = (*scatter, 1); vs.inputs['Anisotropy'].default_value = aniso
    nt.links.new(g.outputs['Position'], o.inputs['Pin']); nt.links.new(o.outputs['Density'], vs.inputs['Density'])
    nt.links.new(vs.outputs[0], out.inputs['Volume'])
    me.materials.append(m)
    m.cycles.volume_sampling = 'DISTANCE'; m.cycles.volume_interpolation = 'LINEAR'
    return ob, o
fog_ob = fog_n = cloud_ob = cloud_n = None
if A.fog: fog_ob, fog_n = make_volume('fog', 1500, -45, 330, osl_src.FOG, (0.80, 0.86, 0.95), 0.45)
if A.fog and A.fbase >= 0: fog_n.inputs['base'].default_value = A.fbase
if A.fog and A.fhaze >= 0: fog_n.inputs['haze'].default_value = A.fhaze
if A.cloud: cloud_ob, cloud_n = make_volume('cloud', 1500, 85, 175, osl_src.CLOUD, (1.0, 1.0, 1.0), 0.55)

# lights
ld = bpy.data.lights.new('fill', 'SUN'); ld.energy = 0.3; ld.color = (0.65, 0.78, 1.0); ld.angle = math.radians(12)
fill = bpy.data.objects.new('fill', ld); sc.collection.objects.link(fill)
fill.rotation_euler = (math.radians(55), 0, math.radians(15))   # shining from camera side (-y) downward... tuned later
pl = bpy.data.lights.new('pit', 'POINT'); pl.color = (1.0, 0.38, 0.1); pl.energy = 0; pl.shadow_soft_size = 3.0
pit = bpy.data.objects.new('pit', pl); sc.collection.objects.link(pit); pit.location = (0, 0, 4)

# ------------------------------------------------------------------ camera
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 22; cam_d.sensor_width = 36; cam_d.clip_end = 6000
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 1.2
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam

def head_center(t):
    C = dragon.centerline(t); Fw = unit(C[0] - C[12])
    return C[0] + Fw * 13.0
TS = np.arange(0, 7.6, 1 / 120.0)
HP = np.array([head_center(t) for t in TS])
def target_raw(i):
    t = TS[i]
    w = smoothstep(TC + 0.2, TC + 1.6, t)
    pre = np.array([0.0, 0.0, 24.0])
    hp = HP[i] + np.array([0, 0, CAMOFF])
    return pre * (1 - w) + hp * w
tgt = np.zeros_like(HP); x = target_raw(0).copy(); vel = np.zeros(3); om = 1 / 0.16; dt = 1 / 120.0
for i in range(len(TS)):
    tr = target_raw(i)
    acc = om * om * (tr - x) - 2 * om * vel
    vel += acc * dt; x += vel * dt; tgt[i] = x
def cam_pos(t):
    s = float(smoothstep(0, 7.6, t))
    cx = 4.0 * s
    cyy = -126.0 + 26.0 * s
    cz = 3.4 + 70.0 * float(smoothstep(1.8, 7.6, t)) ** 1.2
    return np.array([cx, cyy, cz])
def shake(t):
    rum = 0.35 + 0.8 * smoothstep(0.3, 1.8, t) * (1 - smoothstep(TC, TC + 0.2, t)) + 2.2 * np.exp(-np.maximum(t - TC, 0) / 0.55) * (t >= TC) + 0.25 * smoothstep(TC, 3, t)
    hw = lambda f, ph: math.sin(2 * math.pi * f * t + ph)
    yaw = 0.0014 * rum * (hw(0.7, 1) + 0.6 * hw(1.9, 2) + 0.3 * hw(4.3, 0.5) + 0.2 * hw(9.7, 1.3))
    pit_ = 0.0014 * rum * (hw(0.55, 3) + 0.6 * hw(2.3, 0.2) + 0.3 * hw(5.1, 2.5) + 0.2 * hw(11.3, 0.7))
    rol = 0.0007 * rum * (hw(0.8, 2) + 0.5 * hw(3.1, 1))
    return yaw, pit_, rol
def update_camera(t):
    i = min(int(round(t * 120)), len(TS) - 1)
    pos = cam_pos(t)
    gz = float(terrain_h(np.array(pos[0]), np.array(pos[1])))
    pos[2] = max(pos[2], gz + 2.6)
    tg = tgt[i]
    d = tg - pos
    q = Vector(d).to_track_quat('-Z', 'Y')
    yaw, pit_, rol = shake(t)
    q = q @ Quaternion((0, 1, 0), yaw) @ Quaternion((1, 0, 0), pit_) @ Quaternion((0, 0, 1), rol)
    cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = q
    sh = shake(t + 7.7)
    cam.location = Vector(pos) + Vector((sh[0] * 40, sh[1] * 40, sh[2] * 60))
    w = float(smoothstep(TC + 0.6, TC + 2.0, t))
    dg = np.linalg.norm(np.array([0, 0, 6.0]) - pos); dh = np.linalg.norm(HP[i] - pos)
    cam_d.dof.focus_distance = dg * (1 - w) + dh * w

# ------------------------------------------------------------------ per-frame state
def set_frame(f):
    t = f / FPS
    info = update_dragon(t)
    gobj.data.vertices.foreach_set('co', np.stack([GX.ravel(), GY.ravel(), ground_Z(t).ravel()], -1).astype(np.float32).ravel())
    gobj.data.update()
    # ground shader
    glow = 0.5 + 0.5 * smoothstep(0.3, TC, t)
    OG.inputs['t'].default_value = t
    OG.inputs['reveal'].default_value = 4 + 46 * float(smoothstep(0.15, TC + 0.3, t))
    OG.inputs['width'].default_value = 0.25 + 0.9 * float(smoothstep(TC - 0.2, TC + 0.5, t))
    OG.inputs['glow'].default_value = 4.5 * glow * (1.0 - 0.6 * float(smoothstep(TC + 1.0, TC + 4.0, t)))
    OG.inputs['cell'].default_value = CELL
    # fog
    if fog_n is not None:
        fn = fog_n
        fn.inputs['t'].default_value = t
        fn.inputs['swirl'].default_value = 1.6 * float(smoothstep(1.2, 4.2, t)) * (1 - 0.35 * float(smoothstep(5, 7.5, t)))
        te = max(t - TC, 0.0)
        fn.inputs['ring_r'].default_value = (8 + 160 * te ** 0.78) if t > TC else 0.0
        fn.inputs['ring_amt'].default_value = float(smoothstep(TC, TC + 0.15, t)) * (1 - 0.85 * float(smoothstep(TC + 1.5, TC + 5.5, t)))
        fn.inputs['dust'].default_value = 0.030 * math.exp(-te / 1.8) * float(smoothstep(TC, TC + 0.1, t))
        fn.inputs['dust_r'].default_value = 12 + 11 * te
    if cloud_n is not None:
        cloud_n.inputs['t'].default_value = t
    # pit light
    pl.energy = 60000.0 * (0.25 + 0.75 * float(smoothstep(0.3, TC, t))) * (1 - 0.6 * float(smoothstep(TC + 1, TC + 4, t)))
    # debris
    for d in deb:
        ob = d['ob']
        te = t - d['t0']
        if te < 0:
            ob.hide_render = True; ob.hide_viewport = True; continue
        ob.hide_render = False; ob.hide_viewport = False
        # ballistic with ground stop
        tl = None
        p = d['p0'] + d['v'] * te + np.array([0, 0, -0.5 * G_ACC * te * te])
        gz = 0.5
        if p[2] < gz:
            # find landing time
            a = -0.5 * G_ACC; b = d['v'][2]; c = d['p0'][2] - gz
            disc = b * b - 4 * a * c
            tl = (-b - math.sqrt(max(disc, 0))) / (2 * a)
            p = d['p0'] + d['v'] * tl + np.array([0, 0, -0.5 * G_ACC * tl * tl]); p[2] = gz + d['sz'][2] * 0.3
            te_rot = tl
        else:
            te_rot = te
        ob.location = p; ob.scale = d['sz']
        ob.rotation_mode = 'AXIS_ANGLE'; ob.rotation_axis_angle = (d['w'] * te_rot, *d['ax'])
    update_camera(t)
    return t

if __name__ == '__main__':
    os.makedirs(A.out, exist_ok=True)
    frames = []
    for tok in A.frames.split(','):
        if ':' in tok:
            a, b, *c = [int(x) for x in tok.split(':')]; frames += list(range(a, b, c[0] if c else 1))
        else: frames.append(int(tok))
    for f in frames:
        t0 = time.time()
        set_frame(f)
        sc.render.filepath = os.path.join(A.out, 'f%04d.png' % f)
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print('FRAME', f, 'setup %.1fs render %.1fs' % (t1 - t0, time.time() - t1), flush=True)
    if A.save:
        bpy.ops.wm.save_as_mainfile(filepath=A.save)
