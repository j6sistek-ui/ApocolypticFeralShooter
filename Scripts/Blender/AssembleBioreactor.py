"""AssembleBioreactor.py - quick assembly of the Bioreactor perk machine from the owner's Tripo parts (2026-10-31).

  blender -b --python M:/UnrealProjects/AFS/Scripts/Blender/AssembleBioreactor.py [-- <render_out_dir>]

Owner (2026-10-31): the Tripo version is sloppy around the edges, especially the centre tube; liquid cannot be
modelled well, so the tube becomes a plain Unreal glass cylinder with effects (Niagara bubbles, swirl) inside.
No modelling pass: the Tripo parts are only cleaned of loose stray fragments, scaled and placed.

Headless and re-runnable (sources only read, outputs overwritten). Starts from read_homefile(use_empty=True), never
factory settings. Steps:
  1. import the four parts (frame, screen head, sign plate, hose), apply transforms, delete loose strays
     (piece < 5 % of the vertices and > 1.5 % of the part's diagonal away from the main body);
  2. in the frame's own units: measure the gap between the two lugs on the frame's top ring, scale the screen head
     to fit that gap (uniform), drop it onto the ring by ray casts; then scale frame + head uniformly so the machine
     is TOTAL_H tall, pivot at the bottom centre of the frame footprint, front on -Y;
  3. sign plate: uniform scale to the width of the frame's small baked sign, bottom on the lower plinth step, pushed
     forward by ray casts so every part of it is SIGN_PROUD in front of the baked sign;
  4. hose: uniform scale + a small roll about Y so its two elbow ends land on the two round ports on the frame's
     right (+X) side (top ring and above the base);
  5. SM_Bioreactor_TubeGlass (capped 32-segment cylinder shell, GLASS_WALL thick, cylindrical UVs) sized from ray
     casts to the column clearance, tucked into the base seat and the top ring; SM_Bioreactor_TubeVolume (solid
     cylinder inside it) marks the liquid / Niagara volume;
  6. names, textures resized (frame/head 2048, sign 1024, hose 512), export Clean/Bioreactor_Assembly.glb (separate
     meshes), one GLB per part (all share the machine pivot so they snap together at 0,0,0), a .blend with the
     images packed; re-import check; Workbench renders, assembly_sheet.png, concept_compare.png and clean.json.
scifi_base.glb is not used (see SCIFI_BASE_NOTE).
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = 'M:/UnrealProjects/AFS/SourceAssets/PerkMachines/Bioreactor/'
SRC = ROOT + 'Source/'
DST = ROOT + 'Clean/'
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = args[0] if args else 'D:/AFS_Comparisons/PerkMachines_20261031/Bioreactor/clean/'
CONCEPT = 'M:/UnrealProjects/AFS/Docs/References/PerkMachines/concept_bioreactor.jpg'
os.makedirs(DST, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

TOTAL_H = 2.2           # frame + head, metres
HEAD_GAP_FILL = 0.96    # head width as a fraction of the gap between the top-ring lugs
SIGN_PROUD = 0.004      # sign plate in front of the baked sign, metres
GLASS_WALL = 0.008      # glass shell thickness, metres
TUBE_SEGMENTS = 32
TUBE_EMBED = 0.02       # how far the glass ends sink into the seat / top ring
PART_SRC = {  # part: (source glb, texture size)
    'Frame': ('futuristic_bioreactor', 2048),
    'Head': ('futuristic_device', 2048),
    'Sign': ('bioreactor_machine', 1024),
    'Hose': ('flexible_pipe', 512),
}
# Frame-native measurements read off orthographic renders of the source (800 px per metre), refined by ray casts:
SIGN_BOX_NATIVE = (-0.119, 0.119, 0.127, 0.321)    # baked sign on the base front: x0, x1, z0, z1
HOSE_PORTS_NATIVE = ((0.044, 0.840), (0.081, 0.415))  # round ports on the +X side: (y, z) top ring, above the base
SCIFI_BASE_NOTE = ('scifi_base.glb not used: the frame already has its own stepped base with the sign, which is the '
                   'concept\'s silhouette; the alternate pedestal has an open front recess (a dispense alcove) that '
                   'would sit under the sign, push the tube up and make the base too tall for 2.2 m.')
STRAY_VERT_FRAC, STRAY_GAP_FRAC = 0.05, 0.015
rec = {'script': 'Scripts/Blender/AssembleBioreactor.py', 'date': '2026-10-31', 'parts': {}, 'notes': []}


# ---------------------------------------------------------------- helpers
def tris_of(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def vb(o):
    a = np.array([v.co[:] for v in o.data.vertices])
    return Vector(a.min(axis=0)), Vector(a.max(axis=0))


def xform(o, m):
    o.data.transform(m)
    o.data.update()


def tree(o):
    return BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])


def ray(t, origin, d, dist=10.0):
    loc, _n, _i, _d = t.ray_cast(Vector(origin), Vector(d).normalized(), dist)
    return loc


def remove_strays(o):
    me = o.data
    co = [v.co.copy() for v in me.vertices]
    par = list(range(len(co)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    seen = {}
    for i, c in enumerate(co):
        k = (round(c.x, 5), round(c.y, 5), round(c.z, 5))
        if k in seen:
            par[find(i)] = find(seen[k])
        else:
            seen[k] = i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            par[a] = b
    comps = {}
    for i in range(len(co)):
        comps.setdefault(find(i), []).append(i)
    pieces = sorted(comps.values(), key=len, reverse=True)
    lo, hi = vb(o)
    diag = (hi - lo).length
    kd = KDTree(len(pieces[0]))
    for j, i in enumerate(pieces[0]):
        kd.insert(co[i], j)
    kd.balance()
    doomed, removed, kept = set(), [], []
    for p in pieces[1:]:
        gap = min(kd.find(co[i])[2] for i in p)
        info = {'verts': len(p), 'gap_frac': round(gap / diag, 4)}
        if len(p) < STRAY_VERT_FRAC * len(co) and gap > STRAY_GAP_FRAC * diag:
            doomed.update(p)
            removed.append(info)
        else:
            kept.append(info)
    if doomed:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in doomed], context='VERTS')
        bm.to_mesh(me)
        bm.free()
        me.update()
    return {'pieces': len(pieces), 'removed': removed, 'kept_small': kept[:12], 'kept_small_count': len(kept)}


def texture_role(img_name):
    n = img_name.lower()
    if n.endswith('_basecolor') or 'basecolor' in n:
        return 'BaseColor'
    if n.endswith('_normal') or 'normal' in n:
        return 'Normal'
    if n.endswith('_rm') or '_rm' in n:
        return 'RoughMetal'
    return 'Tex'


def import_part(part, src, texsize):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SRC + src + '.glb')
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    r = {'source': 'Source/%s.glb' % src, 'source_tris': sum(tris_of(o.data) for o in meshes)}
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    if o.parent:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for x in new:
        if x.name in bpy.data.objects and x is not o:
            bpy.data.objects.remove(x)
    r['strays'] = remove_strays(o)
    full = 'SM_Bioreactor_%s' % part
    o.name = o.data.name = full
    texs = {}
    for mi, slot in enumerate(o.material_slots):
        mat = slot.material
        if not mat:
            continue
        mat.name = 'M_Bioreactor_%s' % part if mi == 0 else 'M_Bioreactor_%s_%d' % (part, mi)
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                img = n.image
                srcpx = list(img.size)
                if max(srcpx) > texsize:
                    img.scale(texsize, texsize)
                img.name = 'T_Bioreactor_%s_%s' % (part, texture_role(img.name))
                texs[img.name] = {'source_px': srcpx, 'px': list(img.size)}
    r['textures'] = texs
    rec['parts'][full] = r
    return o


def make_cylinder(name, r_out, z0, z1, segs, wall=None, cx=0.0, cy=0.0):
    """Capped cylinder with cylindrical UVs (walls) and planar UVs (caps). With wall: a closed glass shell
    (outer surface + inward-facing inner surface)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')

    def shell(r, za, zb, inward):
        ring_a = [bm.verts.new((cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), za))
                  for i in range(segs)]
        ring_b = [bm.verts.new((cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), zb))
                  for i in range(segs)]
        h = zb - za
        for i in range(segs):
            j = (i + 1) % segs
            quad = [ring_a[i], ring_a[j], ring_b[j], ring_b[i]]
            uvs = [(i / segs, 0), ((i + 1) / segs, 0), ((i + 1) / segs, 1), (i / segs, 1)]
            if inward:
                quad, uvs = quad[::-1], uvs[::-1]
            f = bm.faces.new(quad)
            for loop, t in zip(f.loops, uvs):
                loop[uv].uv = t
        for ring, top in ((ring_a, False), (ring_b, True)):
            vs = ring if top != inward else ring[::-1]
            f = bm.faces.new(vs)
            for loop in f.loops:
                p = loop.vert.co
                loop[uv].uv = (0.5 + (p.x - cx) / (2 * r) * 0.5 + (0.0 if top else 0.0),
                               0.5 + (p.y - cy) / (2 * r) * 0.5)
        return h
    shell(r_out, z0, z1, False)
    if wall:
        shell(r_out - wall, z0 + wall, z1 - wall, True)
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def simple_material(name, base, alpha, transmission=0.0, rough=0.05, emission=None, estr=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*base, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Alpha'].default_value = alpha
    if 'Transmission Weight' in b.inputs:
        b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = 1.45
    if emission:
        b.inputs['Emission Color'].default_value = (*emission, 1.0)
        b.inputs['Emission Strength'].default_value = estr
    m.diffuse_color = (*base, alpha)   # Workbench / viewport colour
    try:
        m.surface_render_method = 'BLENDED'
    except AttributeError:
        m.blend_method = 'BLEND'
    return m


# ---------------------------------------------------------------- 1. import
bpy.ops.wm.read_homefile(use_empty=True)
P = {k: import_part(k, *v) for k, v in PART_SRC.items()}
frame, head, sign, hose = P['Frame'], P['Head'], P['Sign'], P['Hose']

# frame pivot: bottom centre of its footprint
lo, hi = vb(frame)
xform(frame, Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))
lo, hi = vb(head)
xform(head, Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))))

# ---------------------------------------------------------------- 2. head on the top ring (frame units)
ft = tree(frame)
lug_z = 0.955 * vb(frame)[1].z / 0.981
lefts, rights = [], []
for y in (-0.04, 0.0, 0.04):
    a = ray(ft, (0, y, lug_z), (-1, 0, 0))
    b = ray(ft, (0, y, lug_z), (1, 0, 0))
    if a:
        lefts.append(a.x)
    if b:
        rights.append(b.x)
gap_l, gap_r = max(lefts), min(rights)
ring = [v.co for v in frame.data.vertices if 0.82 <= v.co.z <= 0.90]
ring_y = (min(c.y for c in ring) + max(c.y for c in ring)) / 2
hlo, hhi = vb(head)
hk = (gap_r - gap_l) * HEAD_GAP_FILL / (hhi.x - hlo.x)
xform(head, Matrix.Translation(Vector(((gap_l + gap_r) / 2, ring_y, 0))) @ Matrix.Scale(hk, 4))
ht = tree(head)
hlo, hhi = vb(head)
drops = []
for ix in range(9):
    for iy in range(9):
        x = hlo.x + (hhi.x - hlo.x) * (0.05 + 0.9 * ix / 8)
        y = hlo.y + (hhi.y - hlo.y) * (0.05 + 0.9 * iy / 8)
        hb = ray(ht, (x, y, -1), (0, 0, 1))
        fb = ray(ft, (x, y, 5), (0, 0, -1))
        if hb and fb:
            drops.append(hb.z - fb.z)
dz = min(drops)
xform(head, Matrix.Translation((0, 0, -dz)))
native_top = vb(head)[1].z
S = TOTAL_H / native_top
for o in (frame, head):
    xform(o, Matrix.Scale(S, 4))
rec['scale'] = {'frame_and_head_uniform': round(S, 4), 'head_vs_frame': round(hk, 4),
                'lug_gap_native_m': [round(gap_l, 4), round(gap_r, 4)], 'head_drop_contacts': len(drops)}

# ---------------------------------------------------------------- 3. sign plate over the baked sign
ft = tree(frame)
x0, x1, z0, z1 = [v * S for v in SIGN_BOX_NATIVE]
slo, shi = vb(sign)
side = (x1 - x0) * 1.03
k = side / (shi.x - slo.x)
xform(sign, Matrix.Scale(k, 4))
slo, shi = vb(sign)
xform(sign, Matrix.Translation(Vector(((x0 + x1) / 2 - (slo.x + shi.x) / 2, 0, z0 + 0.003 - slo.z))))
st = tree(sign)
slo, shi = vb(sign)
need = []
# only inside the baked sign (the lower plinth step sticks out further forward just under it and must not count)
for ix in range(13):
    for iz in range(13):
        x = x0 + (x1 - x0) * (0.03 + 0.94 * ix / 12)
        z = z0 + (z1 - z0) * (0.08 + 0.90 * iz / 12)
        sf = ray(st, (x, -5, z), (0, 1, 0))        # front surface of the plate
        ff = ray(ft, (x, -5, z), (0, 1, 0))        # front surface of the frame (the baked sign)
        if sf and ff:
            need.append(ff.y - sf.y)                 # >0: plate already in front at this point
dy = min(need) - SIGN_PROUD
xform(sign, Matrix.Translation((0, dy, 0)))
slo, shi = vb(sign)
rec['sign'] = {'grid_points': len(need), 'baked_sign_front_y_range': [round(min(ray(ft, (x, -5, z), (0, 1, 0)).y
               for x in np.linspace(x0, x1, 7)[1:-1] for z in np.linspace(z0, z1, 7)[1:-1]), 4)],
               'face_size_m': round(side, 3), 'scale': round(k, 4), 'proud_m': SIGN_PROUD,
               'front_y': round(slo.y, 4), 'depth_m': round(shi.y - slo.y, 3), 'z_range': [round(slo.z, 3), round(shi.z, 3)]}

# ---------------------------------------------------------------- 4. hose between the two side ports
ports = []
for (py, pz) in HOSE_PORTS_NATIVE:
    p = ray(ft, (5, py * S, pz * S), (-1, 0, 0))
    ports.append(p)
top_port, bot_port = ports
co = np.array([v.co[:] for v in hose.data.vertices])
lo_h, hi_h = co.min(0), co.max(0)
bot_end = Vector(co[co[:, 0] < lo_h[0] + 0.012].mean(0))
top_end = Vector(co[co[:, 2] > hi_h[2] - 0.012].mean(0))
a = top_end - bot_end
b = top_port - bot_port
theta = math.atan2(b.x, b.z) - math.atan2(a.x, a.z)
hs = math.hypot(b.x, b.z) / math.hypot(a.x, a.z)
m = Matrix.Rotation(theta, 4, 'Y') @ Matrix.Scale(hs, 4)
be = m @ bot_end
target = Vector((bot_port.x - 0.006, (top_port.y + bot_port.y) / 2, bot_port.z))
xform(hose, Matrix.Translation(target - be) @ m)
rec['hose'] = {'scale': round(hs, 4), 'roll_about_y_deg': round(math.degrees(theta), 2),
               'top_port': [round(v, 3) for v in top_port], 'bottom_port': [round(v, 3) for v in bot_port]}

# ---------------------------------------------------------------- 5. glass tube + liquid volume
ft = tree(frame)
flo, fhi = vb(frame)


def hole(zc, guess):
    c = Vector(guess)
    hits = []
    for _ in range(3):
        hits = []
        for i in range(36):
            a_ = 2 * math.pi * i / 36
            p = ray(ft, (c.x, c.y, zc), (math.cos(a_), math.sin(a_), 0), 1.0)
            if p:
                hits.append(p)
        if len(hits) < 30:
            break
        c = Vector((sum(h.x for h in hits) / len(hits), sum(h.y for h in hits) / len(hits), zc))
    ds = sorted((Vector((h.x, h.y)) - Vector((c.x, c.y))).length for h in hits)
    return c, ds


ring_c, ring_d = hole(0.86 * S, (0, 0))
seat_c, seat_d = hole(0.335 * S, (0, 0))
col_c = Vector(((ring_c.x + seat_c.x) / 2, (ring_c.y + seat_c.y) / 2, 0))
_c, col_d = hole(0.58 * S, (col_c.x, col_c.y))
clear = col_d[0] if col_d else 0.3
r_ring = float(np.median(ring_d)) if ring_d else clear
r_seat = float(np.median(seat_d)) if seat_d else clear
r_out = min(clear - 0.012, max(r_ring, r_seat) + 0.015)
cx, cy = col_c.x, col_c.y
mid = 0.58 * S
ups, downs = [], []
for i in range(16):
    a_ = 2 * math.pi * i / 16
    x, y = cx + 0.9 * r_out * math.cos(a_), cy + 0.9 * r_out * math.sin(a_)
    u = ray(ft, (x, y, mid), (0, 0, 1), 2.0)
    d = ray(ft, (x, y, mid), (0, 0, -1), 2.0)
    if u:
        ups.append(u.z)
    if d:
        downs.append(d.z)
z_under = float(np.median(ups)) if len(ups) >= 8 else 0.83 * S   # glass narrower than the ring hole: end inside the ring band
z_seat = float(np.median(downs)) if downs else 0.37 * S
gz0, gz1 = z_seat - TUBE_EMBED * 0.5, z_under + TUBE_EMBED
# Checker 2026-10-31: below the cup rim the cup's inner wall sits 1-3 cm inside the glass radius (and off-centre), so
# the glass and liquid cut through it. Start the tube on the collar at the cup rim (about z 0.655 at this scale),
# as in the concept, instead of on the cup floor.
CUP_RIM_Z = 0.655
gz0 = max(gz0, CUP_RIM_Z)
glass = make_cylinder('SM_Bioreactor_TubeGlass', r_out, gz0, gz1, TUBE_SEGMENTS, wall=GLASS_WALL, cx=cx, cy=cy)
r_vol = r_out - GLASS_WALL - 0.004
vol = make_cylinder('SM_Bioreactor_TubeVolume', r_vol, gz0 + GLASS_WALL + 0.004, gz1 - GLASS_WALL - 0.004,
                    TUBE_SEGMENTS, cx=cx, cy=cy)
glass.data.materials.append(simple_material('M_Bioreactor_Glass', (0.75, 0.92, 1.0), 0.22, transmission=1.0))
vol.data.materials.append(simple_material('M_Bioreactor_Liquid', (0.0, 0.78, 0.9), 0.55, rough=0.1,
                                          emission=(0.0, 0.85, 1.0), estr=2.0))
rec['tube'] = {'axis_xy': [round(cx, 4), round(cy, 4)], 'ring_hole_centre': [round(ring_c.x, 4), round(ring_c.y, 4)],
               'seat_centre': [round(seat_c.x, 4), round(seat_c.y, 4)], 'column_clearance_r': round(clear, 4),
               'ring_hole_r': round(r_ring, 4), 'seat_r': round(r_seat, 4), 'glass_outer_r': round(r_out, 4),
               'glass_wall': GLASS_WALL, 'glass_z': [round(gz0, 4), round(gz1, 4)], 'volume_r': round(r_vol, 4),
               'segments': TUBE_SEGMENTS, 'ring_underside_hits': len(ups), 'seat_top_hits': len(downs)}

# ---------------------------------------------------------------- 6. export
order = [frame, head, sign, hose, glass, vol]
bpy.ops.object.select_all(action='DESELECT')
for o in order:
    o.select_set(True)
bpy.context.view_layer.objects.active = frame
asm = DST + 'Bioreactor_Assembly.glb'
gl_kw = dict(export_format='GLB', export_apply=True, export_yup=True, export_animations=False,
             export_image_format='AUTO')
bpy.ops.export_scene.gltf(filepath=asm, use_selection=True, **gl_kw)
for o in order:
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.gltf(filepath=DST + o.name + '.glb', use_selection=True, **gl_kw)
lo_all = Vector((min(vb(o)[0].x for o in order), min(vb(o)[0].y for o in order), min(vb(o)[0].z for o in order)))
hi_all = Vector((max(vb(o)[1].x for o in order), max(vb(o)[1].y for o in order), max(vb(o)[1].z for o in order)))
for o in order:
    lo, hi = vb(o)
    r = rec['parts'].setdefault(o.name, {'source': 'generated'})
    r.update({'tris': tris_of(o.data), 'bbox_min': [round(v, 3) for v in lo], 'bbox_max': [round(v, 3) for v in hi],
              'material': o.material_slots[0].material.name if o.material_slots else None,
              'glb': DST + o.name + '.glb', 'glb_mb': round(os.path.getsize(DST + o.name + '.glb') / 1e6, 2)})
rec['assembly'] = {'glb': asm, 'glb_mb': round(os.path.getsize(asm) / 1e6, 2),
                   'size_m': [round(v, 3) for v in hi_all - lo_all], 'bbox_min': [round(v, 3) for v in lo_all],
                   'bbox_max': [round(v, 3) for v in hi_all],
                   'pivot': 'origin = bottom centre of the frame footprint (the hose sticks out on +X, so the full '
                            'bbox is not centred on X)', 'front': '-Y (sign and screen face -Y)'}
rec['notes'].append(SCIFI_BASE_NOTE)

# ---------------------------------------------------------------- renders
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_cavity = True
sc.display.shading.show_shadows = False
sc.render.film_transparent = False
sc.world = sc.world or bpy.data.worlds.new('w')
sc.world.color = (0.16, 0.16, 0.17)
cd = bpy.data.cameras.new('cam')
cd.lens = 50
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam


def shoot(tag, az, el, lo, hi, res=(900, 1350), fill=0.9):
    sc.render.resolution_x, sc.render.resolution_y = res
    centre = (lo + hi) / 2
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    near, far = 0.2, 40.0
    for _ in range(30):
        dist = (near + far) / 2
        cam.location = centre + d * dist
        cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        ok = all(abs(p.x - 0.5) <= fill / 2 and abs(p.y - 0.5) <= fill / 2
                 for p in (world_to_camera_view(sc, cam, c) for c in corners))
        far, near = (dist, near) if ok else (far, dist)
    cam.location = centre + d * far
    cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
    path = os.path.join(OUT, 'bioreactor_%s.png' % tag)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


shots = {}
shots['front'] = shoot('front', 0, 6, lo_all, hi_all)
shots['34_left'] = shoot('34_left', -40, 10, lo_all, hi_all)
shots['34_right'] = shoot('34_right', 40, 10, lo_all, hi_all)
shots['back'] = shoot('back', 180, 10, lo_all, hi_all)
hlo, hhi = vb(head)
shots['close_head'] = shoot('close_head', 25, 12, hlo - Vector((0.05, 0.05, 0.12)), hhi + Vector((0.05, 0.05, 0.02)),
                            res=(900, 900), fill=0.85)
slo, shi = vb(sign)
shots['close_sign'] = shoot('close_sign', 25, 10, Vector((slo.x - 0.12, slo.y, slo.z - 0.12)),
                            Vector((shi.x + 0.12, shi.y, shi.z + 0.14)), res=(900, 900), fill=0.85)
rec['renders'] = shots

blend = DST + 'Bioreactor_Assembly.blend'
bpy.data.objects.remove(cam)
try:
    bpy.ops.file.pack_all()
except RuntimeError as ex:
    rec['notes'].append('pack_all: %s' % ex)
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
if os.path.exists(blend + '1'):
    os.remove(blend + '1')   # Blender's save backup of the previous run's file
rec['blend'] = blend

# ---------------------------------------------------------------- re-import check
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.gltf(filepath=asm)
ms = [o for o in bpy.context.scene.objects if o.type == 'MESH']
pts = [o.matrix_world @ Vector(c) for o in ms for c in o.bound_box]
rlo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
rhi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
rec['reimport_check'] = {'meshes': sorted(o.name for o in ms), 'tris': sum(tris_of(o.data) for o in ms),
                         'size_m': [round(v, 3) for v in rhi - rlo], 'min_z': round(rlo.z, 4),
                         'images': sorted('%s %dx%d' % (i.name, i.size[0], i.size[1]) for i in bpy.data.images
                                          if i.size[0])}

# ---------------------------------------------------------------- sheets
try:
    from PIL import Image, ImageDraw, ImageFont
    try:
        big = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 22)
        small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 16)
    except OSError:
        big = small = ImageFont.load_default()
    BG = (34, 34, 38)
    cw, chh, head_px = 450, 675, 44
    sheet = Image.new('RGB', (cw * 4 + 450, head_px + chh + 30), BG)
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), 'Bioreactor assembly 2026-10-31   %.2f x %.2f x %.2f m   %d tris   (Workbench texture colour; glass and '
           'liquid are placeholders for the Unreal glass material + Niagara)' % (*rec['assembly']['size_m'],
           rec['reimport_check']['tris']), fill=(230, 230, 230), font=big)
    for i, (tag, label) in enumerate((('front', 'front (-Y)'), ('34_left', '3/4 left'), ('34_right', '3/4 right'),
                                      ('back', 'back'))):
        sheet.paste(Image.open(shots[tag]).convert('RGB').resize((cw, chh)), (i * cw, head_px))
        d.text((i * cw + 8, head_px + chh + 4), label, fill=(220, 220, 220), font=small)
    for j, (tag, label) in enumerate((('close_head', 'head close-up'), ('close_sign', 'sign close-up'))):
        y = head_px + j * 340
        sheet.paste(Image.open(shots[tag]).convert('RGB').resize((330, 330)), (cw * 4 + 60, y))
        d.text((cw * 4 + 66, y + 4), label, fill=(250, 200, 50), font=small)
    sheet.save(os.path.join(OUT, 'assembly_sheet.png'))
    con = Image.open(CONCEPT).convert('RGB')
    h = 1350
    con = con.resize((int(con.width * h / con.height), h))
    ren = Image.open(shots['34_right']).convert('RGB')
    cmp_ = Image.new('RGB', (con.width + ren.width + 30, h + 50), BG)
    cmp_.paste(con, (0, 50))
    cmp_.paste(ren, (con.width + 30, 50))
    d = ImageDraw.Draw(cmp_)
    d.text((10, 12), 'concept', fill=(230, 230, 230), font=big)
    d.text((con.width + 40, 12), 'assembly, 3/4 right (glass + liquid are placeholders)', fill=(230, 230, 230), font=big)
    cmp_.save(os.path.join(OUT, 'concept_compare.png'))
    rec['sheets'] = [os.path.join(OUT, 'assembly_sheet.png'), os.path.join(OUT, 'concept_compare.png')]
except ImportError:
    rec['notes'].append('PIL missing in this Blender Python: sheets not written')
json.dump(rec, open(os.path.join(OUT, 'clean.json'), 'w'), indent=1)
print('ASSEMBLE_BIOREACTOR_DONE', json.dumps(rec['assembly']), flush=True)
