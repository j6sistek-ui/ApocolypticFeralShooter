"""ExportHeadhunter.py - per-part GLBs of the owner's Headhunter perk machine plus the blood helper meshes (2026-11-01).

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b C:/Users/j6sis/OneDrive/Desktop/Unhuntertitled.blend
      --python M:/UnrealProjects/AFS/Scripts/Blender/ExportHeadhunter.py

The owner's .blend is opened READ ONLY: nothing is saved back (no save call anywhere; only GLBs and a JSON receipt are
written). Never run with --factory-startup / read_factory_settings (that wipes the owner's add-ons on this machine).

Source: 12 objects SM_Headhunter_<Part> (Body, Sign, SelectPanel, CrosshairSkull, TubeRing, TubeCap, TubeBase,
TubeBolts, TubeRod, Emblem, EmblemBacking, TubeGlass), 2.2 m tall, transforms applied, all origins at the shared
pivot (bottom centre of the cabinet), front on -Y. Unreal sees this frame as (x, -y, z) * 100 cm, front on +Y.

Out: M:/UnrealProjects/AFS/SourceAssets/PerkMachines/Headhunter/Clean/
  SM_Headhunter_<Part>.glb       the 12 owner parts, one per file, shared pivot, material slot names kept
                                 (placeholder materials: Unreal gets the owner's Painter textures separately)
  SM_Headhunter_BloodPool.glb    the blood pool: a closed cylinder from the tube floor (the owner's red disc / puck is
                                 its floor; the puck is fully inside it) up to POOL_TOP, following the glass outline
                                 POOL_INSET inside it. Dense polar grid on the top (rings every ~1 cm) so the Unreal
                                 material can ripple it with world position offset; the side wall's top ring sits at
                                 POOL_TOP so it moves with the surface.
  SM_Headhunter_GlassBlood.glb   an open shell STREAK_INSET inside the glass, from under the tube ring to under the cap,
                                 for the blood smears / runs / headshot spatter on the inside of the glass. UV u runs
                                 round the tube (u = 0.25 at the front, 0.75 at the back), v = 0 bottom .. 1 top.
  SM_Headhunter_BloodDrop.glb    one small teardrop (8 mm), pivot at its centre, for the falling drops (C++ moved)
  headhunter_clean.json          receipt: per-part bounds, and the measurements the blood effects are built from, in
                                 Blender metres AND Unreal local cm (glass radius / centre / z range, red disc top and
                                 radius, cap underside, skull bounds and jaw tip, rod and its painted drip tip, pool)
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Vector

DST = 'M:/UnrealProjects/AFS/SourceAssets/PerkMachines/Headhunter/Clean/'
os.makedirs(DST, exist_ok=True)
PARTS = ['Body', 'Sign', 'SelectPanel', 'CrosshairSkull', 'TubeRing', 'TubeCap', 'TubeBase', 'TubeBolts', 'TubeRod',
         'Emblem', 'EmblemBacking', 'TubeGlass']
POOL_TOP = 1.17         # m. Visible glass runs 1.097 (tube ring top) .. 1.505 (cap lip); the skull jaw is at ~1.22 and
                        # the crosshair's lower tick reaches 1.145, so the pool stops 5 cm under the jaw and swallows the
                        # tick tip like the concept. Higher submerges the jaw.
POOL_FLOOR = 0.983      # m, just over the tube floor (0.981) so the pool bottom never z-fights it
POOL_INSET = 0.006      # pool wall this far inside the glass
STREAK_INSET = 0.0035   # glass-blood shell this far inside the glass (blood sits on the inner face)
STREAK_Z = (1.088, 1.525)
SEGS = 96
rec = {'source': bpy.data.filepath, 'parts': {}, 'measure': {}, 'notes': []}


def ue(v):
    """Blender metres -> Unreal local cm (glTF import maps (x, y, z) to (x, -y, z))."""
    return [round(v[0] * 100, 2), round(-v[1] * 100, 2), round(v[2] * 100, 2)]


def world_verts(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]


def bounds(vs):
    return (Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)]))


objs = {p: bpy.data.objects['SM_Headhunter_' + p] for p in PARTS}

# ---------------------------------------------------------------- measurements
glass_vs = world_verts(objs['TubeGlass'])
gcx = sum(v.x for v in glass_vs) / len(glass_vs)
gcy = sum(v.y for v in glass_vs) / len(glass_vs)
ring = {}
for v in glass_vs:
    a = math.atan2(v.y - gcy, v.x - gcx)
    ring.setdefault(round(a, 3), []).append(math.hypot(v.x - gcx, v.y - gcy))
glass_prof = sorted((a, min(rs)) for a, rs in ring.items())   # radius per vertex angle (the glass is not quite round)


def glass_r(a):
    """Glass radius at angle a (linear between the glass's own vertex columns)."""
    n = len(glass_prof)
    for i in range(n):
        a0, r0 = glass_prof[i]
        a1, r1 = glass_prof[(i + 1) % n]
        if i == n - 1:
            a1 += 2 * math.pi
        aa = a if a >= a0 else a + 2 * math.pi
        if a0 <= aa <= a1:
            t = (aa - a0) / max(a1 - a0, 1e-9)
            return r0 + (r1 - r0) * t
    return glass_prof[0][1]


glo, ghi = bounds(glass_vs)
rads = [r for _, r in glass_prof]
rec['measure']['glass'] = {'centre_m': [round(gcx, 4), round(gcy, 4)], 'centre_ue_cm': ue((gcx, gcy, 0))[:2],
                           'radius_min_m': round(min(rads), 4), 'radius_max_m': round(max(rads), 4),
                           'z_m': [round(glo.z, 4), round(ghi.z, 4)], 'columns': len(glass_prof),
                           'note': 'open cylinder, no caps; bottom end sits inside the tube base, top inside the cap'}
base_vs = world_verts(objs['TubeBase'])
inner = [v for v in base_vs if math.hypot(v.x - gcx, v.y - gcy) < min(rads) - 0.002]
puck = [v for v in inner if v.z > 1.0]
rec['measure']['red_disc'] = {
    'what': 'the owner\'s red placeholder: a raised puck on the tube floor (rounded top edge), kept as the pool floor',
    'top_z_m': round(max(v.z for v in puck), 4),
    'radius_m': round(max(math.hypot(v.x - gcx, v.y - gcy) for v in puck), 4),
    'floor_z_m': round(min(v.z for v in inner if v.z > 0.97), 4),
    'floor_radius_m': round(max(math.hypot(v.x - gcx, v.y - gcy) for v in inner if abs(v.z - 0.981) < 0.003), 4)}
cap_vs = world_verts(objs['TubeCap'])
under = [v for v in cap_vs if math.hypot(v.x - gcx, v.y - gcy) < min(rads) - 0.01]
rec['measure']['cap_underside'] = {'z_m': round(min(v.z for v in under), 4),
                                   'z_at_glass_m': round(min(v.z for v in cap_vs
                                                             if min(rads) - 0.03 < math.hypot(v.x - gcx, v.y - gcy) < min(rads)), 4)}
ring_vs = world_verts(objs['TubeRing'])
rec['measure']['tube_ring_top_z_m'] = round(max(v.z for v in ring_vs), 4)
sk_vs = world_verts(objs['CrosshairSkull'])
slo, shi = bounds(sk_vs)
skull = [v for v in sk_vs if v.y < -0.14]                 # the skull stands in front of the crosshair plane (y ~ -0.13)
klo, khi = bounds(skull)
jaw_cand = [v for v in skull if abs(v.x) < 0.045]
jaw = min(jaw_cand, key=lambda v: v.z)
rec['measure']['crosshair_skull'] = {'bounds_m': [[round(x, 4) for x in slo], [round(x, 4) for x in shi]],
                                     'skull_only_bounds_m': [[round(x, 4) for x in klo], [round(x, 4) for x in khi]],
                                     'jaw_tip_m': [round(x, 4) for x in jaw], 'jaw_tip_ue_cm': ue(jaw),
                                     'skull_centre_ue_cm': ue((klo + khi) / 2),
                                     'crosshair_plane_y_m': -0.13, 'lowest_point_z_m': round(slo.z, 4)}
rod_vs = world_verts(objs['TubeRod'])
rlo, rhi = bounds(rod_vs)
tip = min(rod_vs, key=lambda v: v.z)
rec['measure']['rod'] = {'bounds_m': [[round(x, 4) for x in rlo], [round(x, 4) for x in rhi]],
                         'what': 'hangs from the cap at the back right; its painted blood drip is a separate blob hanging '
                                 'lower', 'drip_tip_m': [round(x, 4) for x in tip], 'drip_tip_ue_cm': ue(tip)}

# ---------------------------------------------------------------- helper meshes


def mesh_object(name, bm):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def build_pool():
    """Closed pool: polar-grid top at POOL_TOP, side wall (top ring at POOL_TOP), flat bottom at POOL_FLOOR."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rs = [glass_r(2 * math.pi * i / SEGS - math.pi) - POOL_INSET for i in range(SEGS)]
    angs = [2 * math.pi * i / SEGS - math.pi for i in range(SEGS)]
    nr = 34
    rmax = max(rs)

    def pt(i, f, z):
        return (gcx + rs[i] * f * math.cos(angs[i]), gcy + rs[i] * f * math.sin(angs[i]), z)
    centre = bm.verts.new((gcx, gcy, POOL_TOP))
    rings = [[bm.verts.new(pt(i, (k / nr) ** 0.85, POOL_TOP)) for i in range(SEGS)] for k in range(1, nr + 1)]

    def puv(v):
        return (0.5 + (v.co.x - gcx) / (2 * rmax), 0.5 + (v.co.y - gcy) / (2 * rmax))
    for i in range(SEGS):
        j = (i + 1) % SEGS
        f = bm.faces.new([centre, rings[0][i], rings[0][j]])
        for lp in f.loops:
            lp[uv].uv = puv(lp.vert)
        for k in range(nr - 1):
            f = bm.faces.new([rings[k][i], rings[k + 1][i], rings[k + 1][j], rings[k][j]])
            for lp in f.loops:
                lp[uv].uv = puv(lp.vert)
    # side wall: own vertices (hard edge to the top), rings from the top down; the 2nd ring is 2.5 cm down so only
    # the top ring takes the surface's ripple offset in Unreal
    zs = [POOL_TOP, POOL_TOP - 0.025, POOL_TOP - 0.06, (POOL_TOP + POOL_FLOOR) / 2, POOL_FLOOR]
    side = [[bm.verts.new(pt(i, 1.0, z)) for i in range(SEGS)] for z in zs]
    for k in range(len(zs) - 1):
        for i in range(SEGS):
            j = (i + 1) % SEGS
            f = bm.faces.new([side[k][i], side[k][j], side[k + 1][j], side[k + 1][i]])
            for lp, t in zip(f.loops, ((i / SEGS, zs[k]), ((i + 1) / SEGS, zs[k]), ((i + 1) / SEGS, zs[k + 1]),
                                       (i / SEGS, zs[k + 1]))):
                lp[uv].uv = (t[0], (t[1] - POOL_FLOOR) / (POOL_TOP - POOL_FLOOR))
    bot = [bm.verts.new(pt(i, 1.0, POOL_FLOOR)) for i in range(SEGS)]
    f = bm.faces.new(bot[::-1])
    for lp in f.loops:
        lp[uv].uv = puv(lp.vert)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = mesh_object('SM_Headhunter_BloodPool', bm)
    # side wall smooth (flat facets showed as vertical stripes in Unreal), top and floor stay flat with a hard rim
    for p in o.data.polygons:
        p.use_smooth = abs(p.normal.z) < 0.5
    bm2 = bmesh.new()
    bm2.from_mesh(o.data)
    for e in bm2.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal) > 0.8:
            e.smooth = False
    bm2.to_mesh(o.data)
    bm2.free()
    return o


def build_streaks():
    """Open shell inside the glass; faces point inward (the material is two-sided anyway)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    nz = 10
    z0, z1 = STREAK_Z
    cols = []
    for i in range(SEGS + 1):     # duplicated seam column so u runs 0..1 without wrapping
        a = 2 * math.pi * i / SEGS - math.pi
        r = glass_r(a) - STREAK_INSET
        cols.append([bm.verts.new((gcx + r * math.cos(a), gcy + r * math.sin(a), z0 + (z1 - z0) * k / nz))
                     for k in range(nz + 1)])
    for i in range(SEGS):
        for k in range(nz):
            f = bm.faces.new([cols[i][k], cols[i][k + 1], cols[i + 1][k + 1], cols[i + 1][k]])
            for lp, t in zip(f.loops, ((i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k))):
                lp[uv].uv = (t[0] / SEGS, t[1] / nz)
    o = mesh_object('SM_Headhunter_GlassBlood', bm)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def build_drop():
    """8 mm teardrop, slightly pointed on top (+Z), pivot at the centre of the round part."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.004)
    for v in bm.verts:
        if v.co.z > 0:
            k = v.co.z / 0.004
            v.co.x *= 1 - 0.55 * k * k
            v.co.y *= 1 - 0.55 * k * k
            v.co.z *= 1 + 0.6 * k
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = (0.5, 0.5)
    o = mesh_object('SM_Headhunter_BloodDrop', bm)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def plain_material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return m


extra = {'BloodPool': build_pool(), 'GlassBlood': build_streaks(), 'BloodDrop': build_drop()}
for k, o in extra.items():
    o.data.materials.append(plain_material('M_Headhunter_' + k, (0.25, 0.01, 0.01)))
rec['measure']['pool'] = {'top_z_m': POOL_TOP, 'floor_z_m': POOL_FLOOR, 'inset_m': POOL_INSET,
                          'top_ue_cm': round(POOL_TOP * 100, 2),
                          'radius_m': [round(min(rads) - POOL_INSET, 4), round(max(rads) - POOL_INSET, 4)],
                          'visible_height_m': round(POOL_TOP - rec['measure']['tube_ring_top_z_m'], 4),
                          'visible_glass_m': round(rec['measure']['cap_underside']['z_m'] -
                                                   rec['measure']['tube_ring_top_z_m'], 4),
                          'jaw_clearance_m': round(jaw.z - POOL_TOP, 4)}
rec['measure']['glass_blood_shell'] = {'inset_m': STREAK_INSET, 'z_m': list(STREAK_Z),
                                       'radius_ue_cm': [round((min(rads) - STREAK_INSET) * 100, 2),
                                                        round((max(rads) - STREAK_INSET) * 100, 2)],
                                       'uv': 'u = (atan2(y - cy, x - cx) + pi) / 2pi in Blender (front -Y = 0.25, '
                                             'back = 0.75, right +X = 0.5), v = (z - z0) / (z1 - z0)'}
rec['measure']['ue_tube_centre_cm'] = ue((gcx, gcy, 0))[:2]

# ---------------------------------------------------------------- export
gl_kw = dict(export_format='GLB', export_apply=True, export_yup=True, export_animations=False,
             export_materials='PLACEHOLDER')
for name, o in list(((p, objs[p]) for p in PARTS)) + list(extra.items()):
    bpy.ops.object.select_all(action='DESELECT')
    o.hide_set(False)
    o.hide_select = False
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    path = DST + 'SM_Headhunter_%s.glb' % name
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, **gl_kw)
    vs = world_verts(o)
    lo, hi = bounds(vs)
    rec['parts'][name] = {'glb': path, 'glb_kb': round(os.path.getsize(path) / 1024, 1),
                          'tris': sum(len(p.vertices) - 2 for p in o.data.polygons),
                          'material': o.material_slots[0].material.name if o.material_slots else None,
                          'bbox_min_m': [round(x, 4) for x in lo], 'bbox_max_m': [round(x, 4) for x in hi],
                          'origin': [round(x, 4) for x in o.location], 'generated': name in extra}
with open(DST + 'headhunter_clean.json', 'w', encoding='utf-8') as f:
    json.dump(rec, f, indent=1)
print('HEADHUNTER_EXPORT done parts=%d' % len(rec['parts']))
