"""AssembleLifeblood.py - build the Lifeblood perk machine from the owner's four Tripo parts (2026-10-31).

  blender -b --python M:/UnrealProjects/AFS/Scripts/Blender/AssembleLifeblood.py [-- <render_dir>]

Headless and re-runnable (sources are only read, outputs are overwritten). Scenes start with
read_homefile(use_empty=True), never factory settings (that wipes the owner's add-ons).

Sources  SourceAssets/PerkMachines/Lifeblood/Source/  (Tripo GLBs, each ~1 m on its longest side, one 4K PBR set each)
  lifeblood_machine.glb  cabinet: heart sign + labels baked on the upper glass, an empty alcove in the window where the
                         cylinder belongs, a low-detail coin plate baked on the lower front
  coin_slot_panel.glb    detailed INSERT QUARTER panel with a heart button
  first_aid_kit.glb      (misnamed) the curved tagline plate "RESTORE. REVIVE. SURVIVE. +"
  red_energy_core.glb    the blood cylinder: glass tube + blood baked in one texture, dark caps, two side rails

Output   SourceAssets/PerkMachines/Lifeblood/Clean/
  Lifeblood_Assembly.glb      SM_Lifeblood_Body, _CoinPanel, _Tagline, _Core as separate meshes, transforms applied,
                              pivot at the bottom centre, front on -Y (glTF/UE forward), 2.2 m tall
  SM_Lifeblood_<Part>.glb     each part alone, already in its assembled place (drop all at the same origin in UE)
  Lifeblood_Assembly.blend    the assembly (images packed)
  T_Lifeblood_Core_Emissive.png  blood mask from the core's base colour (blood white, metal/caps/rails black, soft edge)
  clean.json                  receipt (also written to the render folder)
Renders  D:/AFS_Comparisons/PerkMachines_20261031/Lifeblood/clean/  (Workbench texture colour + Eevee with the blood
         lit by the mask), assembly_sheet.png, concept_compare.png

Placement is measured on the cabinet in its own source units (survey 2026-10-31: ortho front render at 1045 px/m,
front-ray depth map, horizontal and vertical mesh sections), then everything is moved/scaled together:
  window alcove   half-round alcove behind the lower window, opening z 0.296-0.556, floor 0.281 (pocket) / 0.30 (lip and
                  back step), ceiling ~0.54; five baked rods stand on a ring of radius ~0.08 centred at (x -0.003,
                  y -0.040) with the front open: that ring is where Tripo meant the cylinder to stand, so the core is
                  centred there and sized so its caps sit inside the rods.
  coin plate      grey trapezoid z 0.125-0.2105, x -0.149..0.133 (top) / -0.130..0.123 (bottom), on a face tilted back
                  ~15 degrees; the detailed panel is tilted to the fitted plane of that face.
  tagline strip   dark strip under the alcove lip, z 0.224-0.276, x -0.159..0.152, vertical at y ~ -0.098; the baked
                  "RESTORE. REVIVE. SURVIVE." text is x -0.10..0.085, so the plate covers it (it reads once).

Pass 2 (2026-10-31, owner: "back to the blender clean ups"):
  rods            Tripo baked five rods into the alcove (axes found where face normals point all the way round in a
                  2 cm cell, mid-height). The two free-standing front ones, which showed beside the core, are
                  deleted with the stub islands left at their ends; the back three are fused to the back wall and
                  stay hidden behind the core. The alcove walls (same radius band) are kept.
  coin panel      narrowed to the plate's bottom width (it hung over the red jamb) and everything behind its plate
                  plane squashed to COIN_BACK_KEEP of its depth, so it no longer reads as a thick box from below.
  side labels     Tripo garbled the side text ("LIFEPAOON / PEIRK"). Each side is rendered flat and orthographic,
                  the light letters are inpainted (cv2), "LIFEBLOOD" and "- PERK -" are drawn into the same boxes in
                  a matching serif and colour. The side view before and after, and the label box, are baked into
                  the cabinet's own UVs (Cycles emission, planar projection along X, outer skin facing that side
                  only, raw values) and only the difference is added to the texture, so untouched texels and UV
                  seams stay exact; texels just outside the islands around the label are refilled from inside (Tripo's
                  seams cut through it). The normal map is flattened under the old and new letters.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = 'M:/UnrealProjects/AFS/'
SRC = ROOT + 'SourceAssets/PerkMachines/Lifeblood/Source/'
DST = ROOT + 'SourceAssets/PerkMachines/Lifeblood/Clean/'
CONCEPT = ROOT + 'Docs/References/PerkMachines/concept_lifeblood.jpg'
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = args[0] if args else 'D:/AFS_Comparisons/PerkMachines_20261031/Lifeblood/clean/'
os.makedirs(DST, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

TARGET_HEIGHT = 2.2           # m, whole machine
PROUD_MM = 3.0                # panels stand this far in front of the most forward cabinet point under them
CORE_TOP_GAP_MM = 2.0         # clearance under the alcove ceiling
CORE_SINK_MM = 1.0            # bottom cap pressed this far into the floor so it reads as seated
MERGE_DIST = 1e-5             # source units (~0.02 mm on the final machine)
STRAY_VERT_FRAC, STRAY_GAP_FRAC = 0.05, 0.03

# ---- measured in the cabinet's source units (see docstring) --------------------------------------------------------
CORE_CENTRE_XY = (-0.004, -0.040)
CORE_FLOOR_PROBE_Z, CORE_ALCOVE_MID_Z = 0.30, 0.42
COIN_RECT = {'x': (-0.140, 0.128), 'z': (0.130, 0.205)}      # inner part of the baked plate, used to fit its plane
COIN_CENTRE_XZ = (-0.006, 0.168)
COIN_WIDTH = 0.250                                            # the trapezoid's bottom width (average hung over the jamb)
COIN_BACK_KEEP = 0.4                                          # depth kept behind the coin panel's plate plane
TAG_RECT = {'x': (-0.120, 0.120), 'z': (0.237, 0.267)}      # flat part only (no frame sides, no lip edge)
TAG_CENTRE_XZ = (-0.004, 0.2505)
TAG_WIDTH = 0.250

ROD_AXES = ((-0.081, -0.020), (0.080, -0.019))  # the two free-standing front rods (the back three, at (-0.071, 0.030),
                                                 # (0.007, 0.035), (0.068, 0.033), are fused to the back wall and
                                                 # hidden by the core: cutting them holes the wall)
ROD_RADIUS, ROD_Z = 0.016, (0.303, 0.552)                    # faces this close to an axis (feet included) are cut
SIDE_SKIN_X = 0.17                                            # outer side skin only (the alcove walls face X too)
SIDE_PX_PER_UNIT = 2000                                       # flat side renders: 1000 x 2000 px over y +-0.25, z 0..1
SIDE_TEXT_BAND = {'z': (0.405, 0.485), 'y': (-0.045, 0.165)}  # the burgundy side panel around the garbled label
SIDE_FONT = 'C:/Windows/Fonts/timesbd.ttf'

PARTS = [  # (object name, source file, texture size)
    ('SM_Lifeblood_Body', 'lifeblood_machine', 2048),
    ('SM_Lifeblood_CoinPanel', 'coin_slot_panel', 1024),
    ('SM_Lifeblood_Tagline', 'first_aid_kit', 1024),
    ('SM_Lifeblood_Core', 'red_energy_core', 2048),
]


# ---- helpers --------------------------------------------------------------------------------------------------------
def tris_of(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def verts_np(o):
    a = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def vbounds(o):
    a = verts_np(o)
    return Vector(a.min(0)), Vector(a.max(0))


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def bvh_of(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def remove_strays(o):
    """Delete small pieces that float apart from the main body (same rule family as CleanPowerUps.py)."""
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
    lo, hi = vbounds(o)
    diag = (hi - lo).length
    kd = KDTree(len(pieces[0]))
    for j, i in enumerate(pieces[0]):
        kd.insert(co[i], j)
    kd.balance()
    doomed, removed, kept = set(), [], []
    for p in pieces[1:]:
        gap = min(kd.find(co[i])[2] for i in p)
        c = sum((co[i] for i in p), Vector()) / len(p)
        info = {'verts': len(p), 'gap_src': round(gap, 4), 'centre_src': [round(x, 3) for x in c]}
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


def uv_signature(me):
    if not me.uv_layers:
        return None
    a = np.empty(len(me.loops) * 2)
    me.uv_layers[0].data.foreach_get('uv', a)
    a = a.reshape(-1, 2)
    return len(me.loops), np.sort(np.round(a, 5), axis=0)


def weld_and_fix_normals(o):
    """Merge by distance (tiny), recalc face winding, then copy the source shading back with a Data Transfer of the
    custom normals from an untouched copy (Tripo normal maps were baked against those normals)."""
    me = o.data
    rep = {'verts_before': len(me.vertices), 'tris_before': tris_of(me)}
    uv0 = uv_signature(me)
    ref = o.copy()
    ref.data = me.copy()
    bpy.context.scene.collection.objects.link(ref)
    fn0 = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', fn0)
    bm = bmesh.new()
    bm.from_mesh(me)
    nv = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DIST)
    merged = nv - len(bm.verts)
    bm.normal_update()
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    # recalc can mis-flip faces on a non-manifold Tripo shell: keep a flip only if the new side looks out of the mesh
    tree = BVHTree.FromBMesh(bm)
    eps = 1e-4

    def escapes(f, n):
        c = f.calc_center_median()
        return tree.ray_cast(c + n * eps, n)[0] is None
    undo = [f for f, n0 in zip(bm.faces, before) if f.normal.dot(n0) < -0.5
            and escapes(f, -f.normal) and not escapes(f, f.normal)]
    if undo:
        bmesh.ops.reverse_faces(bm, faces=undo)
    reverted = len(undo)
    bm.to_mesh(me)
    bm.free()
    me.update()
    uv1 = uv_signature(me)
    uv_ok = uv0 is not None and uv1 is not None and uv0[0] == uv1[0] and np.allclose(uv0[1], uv1[1], atol=1e-5)
    if not uv_ok:   # never happened on these four, but honour "only if it does not break UVs"
        o.data = ref.data.copy()
        me = o.data
        merged = 0
    fn1 = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', fn1)
    flipped = int(((fn0.reshape(-1, 3) * fn1.reshape(-1, 3)).sum(1) < -0.5).sum()) if len(fn0) == len(fn1) else -1
    me.shade_smooth()
    mod = o.modifiers.new('keep_normals', 'DATA_TRANSFER')
    mod.object = ref
    mod.use_loop_data = True
    mod.data_types_loops = {'CUSTOM_NORMAL'}
    mod.loop_mapping = 'POLYINTERP_NEAREST'
    select_only(o)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    rd = ref.data
    bpy.data.objects.remove(ref)
    bpy.data.meshes.remove(rd)
    rep.update({'merged_verts': merged, 'uvs_intact': bool(uv_ok), 'faces_flipped_net': flipped,
                'recalc_flips_reverted_as_wrong': reverted if uv_ok else 0,
                'verts_after': len(me.vertices), 'tris_after': tris_of(me)})
    return rep


def import_part(fn):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SRC + fn + '.glb')
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
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
        if x is not o and x.name in bpy.data.objects:
            bpy.data.objects.remove(x)
    return o, len(meshes)


def texture_roles(mat):
    roles = {}
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return roles

    def walk(sock, role, depth=0):
        for l in sock.links:
            n = l.from_node
            if n.type == 'TEX_IMAGE' and n.image:
                roles.setdefault(n.image.name, role)
            elif depth < 6:
                for s in n.inputs:
                    walk(s, role, depth + 1)
    for name, role in (('Base Color', 'BaseColor'), ('Normal', 'Normal'), ('Metallic', 'ORM'),
                       ('Roughness', 'ORM'), ('Emission Color', 'Emissive'), ('Alpha', 'BaseColor')):
        if name in bsdf.inputs:
            walk(bsdf.inputs[name], role)
    return roles


def rename_and_resize(o, part, size):
    texs = {}
    for mi, slot in enumerate([s for s in o.material_slots if s.material]):
        mat = slot.material
        mat.name = 'M_Lifeblood_%s' % part if mi == 0 else 'M_Lifeblood_%s_%d' % (part, mi)
        roles = texture_roles(mat)
        for n in mat.node_tree.nodes:
            if n.type != 'TEX_IMAGE' or not n.image:
                continue
            img = n.image
            src = list(img.size)
            if max(src) > size:
                img.scale(size, size)
            role = roles.get(img.name, 'Tex%d' % len(texs))
            img.name = 'T_Lifeblood_%s_%s' % (part, role)
            texs[img.name] = {'source_px': src, 'px': list(img.size)}
    return texs


def ray_grid(bvh, xs, zs, y0=-2.0, direction=(0, 1, 0)):
    pts = []
    for x in xs:
        for z in zs:
            h = bvh.ray_cast(Vector((x, y0, z)), Vector(direction))
            if h[0] is not None:
                pts.append(h[0])
    return pts


def fit_front_plane(bvh, rect, n=13):
    """Least-squares plane y = a x + b z + c over the cabinet surface hit from the front in rect."""
    xs = np.linspace(rect['x'][0], rect['x'][1], n)
    zs = np.linspace(rect['z'][0], rect['z'][1], n)
    P = np.array([p[:] for p in ray_grid(bvh, xs, zs)])
    A = np.c_[P[:, 0], P[:, 2], np.ones(len(P))]
    (a, b, c), *_ = np.linalg.lstsq(A, P[:, 1], rcond=None)
    nrm = Vector((a, -1.0, b)).normalized()            # points out of the cabinet, towards -Y
    return (a, b, c), nrm, P


def panel_front_anchor(o):
    """Centre (bbox x/z) and the plate plane y of a panel whose readable face looks to -Y: median front hit over a
    border band, so raised bosses (coin box, button) do not count as the plate."""
    lo, hi = vbounds(o)
    bvh = bvh_of(o)
    xs = np.linspace(lo.x, hi.x, 41)[2:-2]
    zs = np.linspace(lo.z, hi.z, 21)[2:-2]
    band = [(x, z) for x in xs for z in zs
            if min(x - lo.x, hi.x - x) < 0.12 * (hi.x - lo.x) or min(z - lo.z, hi.z - z) < 0.18 * (hi.z - lo.z)]
    ys = []
    for x, z in band:
        h = bvh.ray_cast(Vector((x, lo.y - 1, z)), Vector((0, 1, 0)))
        if h[0] is not None:
            ys.append(h[0].y)
    return Vector(((lo.x + hi.x) / 2, float(np.median(ys)), (lo.z + hi.z) / 2)), lo, hi


def basis_from_front(nrm):
    up = Vector((0, 0, 1))
    up = (up - nrm * up.dot(nrm)).normalized()
    right = up.cross(nrm)
    return Matrix((right, -nrm, up)).transposed().to_4x4()   # columns: local X, Y, Z


def mount_panel(o, body_bvh, rect, centre_xz, width, proud, z_bias=0.0):
    """Scale o to width, tilt it to the fitted plane of the cabinet under rect, put its plate plane `proud` in front
    of the most forward cabinet point inside rect. Returns placement facts."""
    (a, b, c), nrm, P = fit_front_plane(body_bvh, rect)
    anchor, lo, hi = panel_front_anchor(o)
    s = width / (hi.x - lo.x)
    cx, cz = centre_xz
    cz += z_bias
    base = Vector((cx, a * cx + b * cz + c, cz))
    d = [(Vector(p) - base).dot(nrm) for p in P]
    target = base + nrm * (max(d) + proud)
    R = basis_from_front(nrm)
    M = Matrix.Translation(target) @ R @ Matrix.Scale(s, 4) @ Matrix.Translation(-anchor)
    o.data.transform(M)
    o.data.update()
    # settle: the plane max above is conservative on a folded face. Look straight at the panel (along -n); over the
    # panel's inner area the cabinet behind it must be at least `proud` further away, and the panel is moved along n
    # so the tightest inner spot is exactly `proud`. At the rim the cabinet may stand in front (the plate tucks under
    # the alcove lip / frame bar): that is counted as 'tucked'; only near-coplanar rim samples are a z-fight risk.
    right, up = R.col[0].xyz, R.col[2].xyz
    pw, ph = (hi.x - lo.x) * s, (hi.z - lo.z) * s
    pb = bvh_of(o)
    gaps = []
    for i in np.linspace(-0.47, 0.47, 25):
        for j in np.linspace(-0.47, 0.47, 13):
            org = target + right * (i * pw) + up * (j * ph) + nrm * 0.5
            hp = pb.ray_cast(org, -nrm)
            if hp[0] is None or hp[3] > 0.5 + 0.006:   # holes/recesses (coin slot) and rounded ends do not count
                continue
            hb = body_bvh.ray_cast(org, -nrm)
            if hb[0] is not None:
                gaps.append((abs(i) <= 0.36 and abs(j) <= 0.30, hb[3] - hp[3]))
    settle = min(g for inner, g in gaps if inner) - proud
    o.data.transform(Matrix.Translation(-nrm * settle))
    o.data.update()
    target = target - nrm * settle
    rim = [g - settle for inner, g in gaps if not inner]
    return {'_nrm': nrm, '_plate': target,
            'scale': round(s, 4), 'settled_back_src': round(settle, 4), 'settle_samples': len(gaps),
            'rim_tucked_samples': sum(1 for g in rim if g < -proud),
            'rim_zfight_risk_samples': sum(1 for g in rim if -proud <= g < 0.5 * proud), 'tilt_back_deg': round(math.degrees(math.asin(max(-1, min(1, nrm.z)))), 2),
            'plate_plane_centre_src': [round(v, 4) for v in target], 'surface_relief_src': round(max(d) - min(d), 4),
            'fit_points': len(P), 'height_src': round((hi.z - lo.z) * s, 4), 'width_src': round(width, 4)}


def place_core(o, body_bvh):
    """Centre the core on the rod ring, scale it to the alcove's floor-to-ceiling height (fixed point: the cap radius
    sets which floor/ceiling points count)."""
    lo, hi = vbounds(o)
    src_h = hi.z - lo.z
    cap_r_rel = 0.5 * (hi.y - lo.y) / src_h          # caps are the widest round part (depth axis)
    cx, cy = CORE_CENTRE_XY
    s = 0.25 / src_h
    floor = ceil = None
    for _ in range(4):
        r = cap_r_rel * src_h * s * 0.97
        floors, ceils = [], []
        for ang in range(0, 360, 15):
            for rr in (0.0, 0.5 * r, r):
                p = Vector((cx + rr * math.cos(math.radians(ang)), cy + rr * math.sin(math.radians(ang)),
                            CORE_ALCOVE_MID_Z))
                hd = body_bvh.ray_cast(p, Vector((0, 0, -1)))
                hu = body_bvh.ray_cast(p, Vector((0, 0, 1)))
                if hd[0] is not None:
                    floors.append(hd[0].z)
                if hu[0] is not None:
                    ceils.append(hu[0].z)
        floor, ceil = max(floors), min(ceils)
        s = (ceil - floor - CORE_TOP_GAP_MM / 1000 / K_EST + CORE_SINK_MM / 1000 / K_EST) / src_h
    base = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    target = Vector((cx, cy, floor - CORE_SINK_MM / 1000 / K_EST))
    o.data.transform(Matrix.Translation(target) @ Matrix.Scale(s, 4) @ Matrix.Translation(-base))
    o.data.update()
    # the rail brackets pass close to the two front rods: slide forward (towards -Y) in 1 mm steps (source units)
    # until nothing above the seated base touches the cabinet, at most 12 mm
    def touches_above_base():
        tc = bvh_of(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        n = sum(1 for _, j in body_bvh.overlap(tc) if bm.faces[j].calc_center_median().z > floor + 0.015)
        bm.free()
        return n
    tried = []
    shift = 0.0
    for step in range(13):
        n = touches_above_base()
        tried.append((round(-shift, 3), n))
        if n == 0:
            break
        o.data.transform(Matrix.Translation((0, -0.001, 0)))
        o.data.update()
        shift += 0.001
    else:
        best = min(tried, key=lambda t: (t[1], -t[0]))
        o.data.transform(Matrix.Translation((0, shift + best[0], 0)))
        o.data.update()
        shift = -best[0]
    cy -= shift
    return {'forward_shift_src': round(shift, 4), 'touch_search': tried,'scale': round(s, 4), 'floor_src': round(floor, 4), 'ceiling_src': round(ceil, 4),
            'centre_src': [cx, cy], 'cap_radius_src': round(cap_r_rel * src_h * s, 4),
            'height_src': round(src_h * s, 4)}


def flatten_behind_plate(o, nrm, plate, keep):
    """Squash everything behind the plate plane towards it (keep = fraction of depth kept); bosses in front stay."""
    me = o.data
    a = verts_np(o)
    n = np.array(nrm[:])
    d = (a - np.array(plate[:])) @ n
    back = d < 0
    a[back] -= np.outer(d[back] * (1 - keep), n)
    me.vertices.foreach_set('co', a.ravel())
    me.update()
    return {'verts_squashed': int(back.sum()), 'depth_behind_plate_src': round(float(-d.min()), 4),
            'depth_kept_src': round(float(-d.min() * keep), 4)}


def remove_rods(o):
    """Delete the five rods standing around the core (ROD_AXES) and the stub islands left at their ends."""
    def near_rod(c, r):
        return min(math.hypot(c.x - ax, c.y - ay) for ax, ay in ROD_AXES) < r
    bm = bmesh.new()
    bm.from_mesh(o.data)
    doomed = [f for f in bm.faces if ROD_Z[0] < f.calc_center_median().z < ROD_Z[1]
              and near_rod(f.calc_center_median(), ROD_RADIUS)]
    bmesh.ops.delete(bm, geom=doomed, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    # rod stubs left hanging on the floor and ceiling: small face islands inside the alcove
    seen, stubs = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        isl, todo = [], [f]
        seen.add(f)
        while todo:
            g = todo.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        todo.append(h)
        if len(isl) < 80:
            c = sum((g.calc_center_median() for g in isl), Vector()) / len(isl)
            if 0.28 < c.z < 0.57 and near_rod(c, 0.03):
                stubs.extend(isl)
    bmesh.ops.delete(bm, geom=stubs, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return {'faces_deleted': len(doomed), 'stub_faces_deleted': len(stubs)}


def fix_side_text(o, others):
    """Repaint the garbled side labels (docstring, pass 2). Works in the cabinet's source units, before placement."""
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    sc = bpy.context.scene
    hidden = [(x, x.hide_render) for x in others]
    for x, _ in hidden:
        x.hide_render = True
    eng = sc.render.engine
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'FLAT'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = False
    sc.display.shading.show_shadows = False
    vt = sc.view_settings.view_transform
    sc.view_settings.view_transform = 'Standard'
    sc.world = sc.world or bpy.data.worlds.new('w')
    sc.world.color = (1, 0, 1)
    cd = bpy.data.cameras.new('side_cam')
    cd.type, cd.ortho_scale = 'ORTHO', 1.0
    cam = bpy.data.objects.new('side_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    W, H, K = 1000, 2000, SIDE_PX_PER_UNIT
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    rep_, patches = {}, {}
    for side, sg in (('px', 1), ('nx', -1)):
        cam.location = (2 * sg, 0, 0.5)
        cam.rotation_euler = (math.pi / 2, 0, sg * math.pi / 2)
        path = OUT + 'side_%s_before.png' % side
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255
        r0 = int(H / 2 - (SIDE_TEXT_BAND['z'][1] - 0.5) * K)
        r1 = int(H / 2 - (SIDE_TEXT_BAND['z'][0] - 0.5) * K)
        c0, c1 = sorted(int(W / 2 + sg * y * K) for y in SIDE_TEXT_BAND['y'])
        band = img[r0:r1, c0:c1]
        lum = band.mean(2)
        sat = band.max(2) - band.min(2)
        light = (lum > 0.33) & (sat < 0.30)
        light[:, light.mean(0) > 0.4] = False           # the grey frame bars run through the whole band
        rows = np.where(light.sum(1) > 3)[0]
        lines, start = [], rows[0]
        for a, b in zip(rows[:-1], rows[1:]):
            if b - a > 4:
                lines.append((start, a))
                start = b
        lines.append((start, rows[-1]))
        lines = sorted(sorted(lines, key=lambda t: -(t[1] - t[0]))[:2])
        boxes = []
        for a, b in lines:
            cols = np.where(light[a:b + 1].sum(0) > 0)[0]
            boxes.append([r0 + a, r0 + b, c0 + cols.min(), c0 + cols.max()])
        (t0, t1, l0, l1), (u0, u1, m0, m1) = boxes        # the big word, then the "- PERK -" line
        mask = np.zeros((H, W), np.uint8)
        for a, b, c, d in boxes:
            win = mask[a - 3:b + 4, c - 3:d + 4]
            win[img[a - 3:b + 4, c - 3:d + 4].mean(2) > 0.26] = 255
        mask = cv2.dilate(mask, np.ones((11, 11), np.uint8))     # the old letters carry a dark drop shadow
        clean = cv2.inpaint((img * 255).astype(np.uint8), mask, 9, cv2.INPAINT_TELEA)
        txt = np.median(img[t0:t1 + 1, l0:l1 + 1][light[t0 - r0:t1 - r0 + 1, l0 - c0:l1 - c0 + 1]], axis=0)
        S4 = 4
        layer = Image.new('L', (W * S4, H * S4), 0)

        def word(text, box, track):
            a, b, c, d = box
            hpx = (b - a + 1) * S4
            f = ImageFont.truetype(SIDE_FONT, int(hpx * 1.45))
            tmp = Image.new('L', (int(hpx * 2 * len(text)), int(hpx * 3)), 0)
            td = ImageDraw.Draw(tmp)
            x = 0
            for ch in text:
                td.text((x, 0), ch, font=f, fill=255)
                x += td.textlength(ch, font=f) + track * hpx
            tmp = tmp.crop(tmp.getbbox()).resize((int((d - c + 1) * S4), int(hpx)), Image.LANCZOS)
            layer.paste(tmp, (int(c * S4), int(a * S4)), tmp)
        word('LIFEBLOOD', (t0, t1, l0, l1), 0.06)
        mid, ww = (m0 + m1) / 2, (u1 - u0 + 1) * 3.4
        word('PERK', (u0, u1, int(mid - ww / 2), int(mid + ww / 2)), 0.15)
        dr = ImageDraw.Draw(layer)
        ry, gap = int((u0 + u1) / 2 * S4), ww / 2 + (u1 - u0 + 1) * 1.2
        for xa, xb in ((m0, mid - gap), (mid + gap, m1)):
            dr.rectangle([int(xa * S4), ry - S4 // 2, int(xb * S4), ry + S4 // 2], fill=255)
        alpha = np.asarray(layer.resize((W, H), Image.LANCZOS)).astype(np.float32)[..., None] / 255
        out = clean.astype(np.float32) / 255 * (1 - alpha) + txt[None, None, :] * alpha
        box = np.zeros((H, W), np.float32)
        for a, b, c, d in boxes:
            box[a - 10:b + 11, c - 14:d + 15] = 1
        box = cv2.GaussianBlur(box, (0, 0), 3)
        letters = cv2.GaussianBlur(np.maximum(mask.astype(np.float32) / 255, alpha[..., 0]), (0, 0), 2)
        Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(OUT + 'side_%s_after.png' % side)
        oldm = cv2.GaussianBlur(cv2.dilate(mask, np.ones((5, 5), np.uint8)).astype(np.float32) / 255, (0, 0), 1.5)
        Image.fromarray((np.dstack([box, letters, oldm]) * 255).astype(np.uint8)).save(
            OUT + 'side_%s_masks.png' % side)
        patches[side] = {k: OUT + 'side_%s_%s.png' % (side, k) for k in ('before', 'after', 'masks')}

        def to_y(c):
            return round(sg * (c + 0.5 - W / 2) / K, 4)

        def to_z(r):
            return round(0.5 + (H / 2 - r - 0.5) / K, 4)
        rep_[side] = {'word_box_yz': [to_y(l0), to_y(l1), to_z(t1), to_z(t0)],
                      'perk_line_box_yz': [to_y(m0), to_y(m1), to_z(u1), to_z(u0)],
                      'text_rgb': [round(float(v), 3) for v in txt], 'inpainted_px': int((mask > 0).sum())}
    bpy.data.objects.remove(cam)
    sc.view_settings.view_transform = vt

    # bake both sides' masks into the cabinet's own UVs (planar projection along X, outer skin facing that side)
    mat = o.material_slots[0].material
    texs = [n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
    base = next(i for i in texs if i.name.endswith('_BaseColor'))
    nrmi = next((i for i in texs if i.name.endswith('_Normal')), None)
    w, h = base.size
    tm = bpy.data.materials.new('bake_side')
    tm.use_nodes = True
    nt = tm.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new('ShaderNodeOutputMaterial')
    emi = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(emi.outputs[0], outn.inputs[0])
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(nt.nodes.new('ShaderNodeTexCoord').outputs['Object'], sep.inputs[0])
    gsep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(nt.nodes.new('ShaderNodeNewGeometry').outputs['True Normal'], gsep.inputs[0])

    def math_node(op, a, b=None, c=None):
        m_ = nt.nodes.new('ShaderNodeMath')
        m_.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m_.inputs[i].default_value = v
            else:
                nt.links.new(v, m_.inputs[i])
        return m_.outputs[0]

    def side_sample(side, sg, which):
        cmb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(math_node('MULTIPLY_ADD', sep.outputs['Y'], sg * K / W, 0.5), cmb.inputs[0])
        nt.links.new(math_node('MULTIPLY_ADD', sep.outputs['Z'], K / H, 0.5 - 0.5 * K / H), cmb.inputs[1])
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(patches[side][which])
        t.image.colorspace_settings.name = 'Non-Color'     # raw values in, raw values out: no colour round trip
        t.extension = 'CLIP'
        nt.links.new(cmb.outputs[0], t.inputs[0])
        facing = math_node('GREATER_THAN' if sg > 0 else 'LESS_THAN', gsep.outputs['X'], 0.3 * sg)
        outer = math_node('GREATER_THAN', math_node('MULTIPLY', sep.outputs['X'], sg), SIDE_SKIN_X)
        col = nt.nodes.new('ShaderNodeMix')
        col.data_type = 'RGBA'
        col.inputs['A'].default_value = (0, 0, 0, 1)
        nt.links.new(math_node('MULTIPLY', facing, outer), col.inputs['Factor'])
        nt.links.new(t.outputs['Color'], col.inputs['B'])
        return col.outputs['Result']
    tgt = nt.nodes.new('ShaderNodeTexImage')
    nt.nodes.active = tgt
    keep_mats = [sl.material for sl in o.material_slots]
    for sl in o.material_slots:
        sl.material = tm
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 1
    sc.render.bake.margin = 16
    select_only(o)
    baked = {}
    for which in ('before', 'after', 'masks'):
        addc = nt.nodes.new('ShaderNodeMix')
        addc.data_type, addc.blend_type = 'RGBA', 'ADD'
        addc.inputs['Factor'].default_value = 1.0
        nt.links.new(side_sample('px', 1, which), addc.inputs['A'])
        nt.links.new(side_sample('nx', -1, which), addc.inputs['B'])
        nt.links.new(addc.outputs['Result'], emi.inputs['Color'])
        im = bpy.data.images.new('bake_' + which, w, h, alpha=False, float_buffer=True)
        im.colorspace_settings.name = 'Non-Color'
        tgt.image = im
        bpy.ops.object.bake(type='EMIT')
        px_ = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px_)
        baked[which] = px_.reshape(h, w, 4)[..., :3]
        bpy.data.images.remove(im)
    for sl, m_ in zip(o.material_slots, keep_mats):
        sl.material = m_
    bpy.data.materials.remove(tm)
    sc.render.engine = eng
    # only the change goes into the texture: where the side view did not change, before == after and the texture is
    # untouched, and UV-seam artefacts of the projection cancel out
    box, letters = np.clip(baked['masks'][..., :1], 0, 1), np.clip(baked['masks'][..., 1], 0, 1)
    oldm = np.clip(baked['masks'][..., 2:3], 0, 1)
    a = np.empty(w * h * 4, np.float32)
    base.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    # where the old letters were, the texture is sharper/blurrier than the side view, so a difference leaves fringes:
    # take the fixed view there, shifted by the texture-vs-view offset measured on the plain panel around it
    plain = (box[..., 0] > 0.9) & (oldm[..., 0] < 0.01) & (letters < 0.01)
    off = np.median(a[..., :3][plain] - baked['before'][plain], axis=0) if plain.any() else np.zeros(3)
    rep_['view_to_texture_offset'] = [round(float(v), 4) for v in off]
    delta = a[..., :3] + box * (baked['after'] - baked['before'])
    swap = baked['after'] + off[None, None, :]
    a[..., :3] = np.clip(delta * (1 - oldm) + swap * oldm, 0, 1)
    # Tripo's islands sit close together and the label is cut by seams: refill the texels just outside the islands
    # around the label from inside, so filtering at a seam does not pull dark atlas gaps into the letters
    cov = Image.new('L', (w, h), 0)
    cdr = ImageDraw.Draw(cov)
    uvd = o.data.uv_layers[0].data
    for poly in o.data.polygons:
        cdr.polygon([(uvd[li].uv.x * w - 0.5, uvd[li].uv.y * h - 0.5) for li in poly.loop_indices], fill=255)
    cov = np.asarray(cov) > 0
    near = cv2.dilate((box[..., 0] > 0.02).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    gap = (near & ~cov).astype(np.uint8) * 255
    rgb8 = (a[..., :3] * 255 + 0.5).astype(np.uint8)
    padded = cv2.inpaint(rgb8, gap, 3, cv2.INPAINT_TELEA).astype(np.float32) / 255
    a[..., :3] = np.where((gap > 0)[..., None], padded, a[..., :3])
    rep_['gap_texels_padded'] = int((gap > 0).sum())
    base.pixels.foreach_set(a.ravel())
    base.update()
    if nrmi is not None:
        nw, nh = nrmi.size
        mm = letters if (nw, nh) == (w, h) else cv2.resize(letters, (nw, nh))
        mm = mm[..., None]
        b = np.empty(nw * nh * 4, np.float32)
        nrmi.pixels.foreach_get(b)
        b = b.reshape(nh, nw, 4)
        b[..., :3] = b[..., :3] * (1 - mm) + np.array([0.5, 0.5, 1.0], np.float32) * mm
        nrmi.pixels.foreach_set(b.ravel())
        nrmi.update()
    for x, hr in hidden:
        x.hide_render = hr
    rep_['texels_changed'] = int((box[..., 0] > 0.5).sum())
    rep_['texels_normal_flattened'] = int((letters > 0.5).sum())
    rep_['normal_flattened'] = nrmi is not None
    return rep_


def overlap_report(a, b):
    pairs = bvh_of(a).overlap(bvh_of(b))
    return len(pairs)


def make_emissive_mask(core):
    """Blood = bright saturated red -> white; caps, rails, dark metal -> black; soft edges (two box blurs)."""
    mat = core.material_slots[0].material
    img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and
               n.image.name.endswith('_BaseColor'))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    sat = (r - np.maximum(g, b)) / np.maximum(r, 1e-4)

    def smooth(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0, 1)
        return t * t * (3 - 2 * t)
    m = smooth(0.50, 0.78, sat) * smooth(0.22, 0.45, r)

    def box(a, k=3):
        c = np.cumsum(np.pad(a, ((0, 0), (k + 1, k)), mode='edge'), axis=1)
        a = (c[:, 2 * k + 1:] - c[:, :-2 * k - 1]) / (2 * k + 1)
        c = np.cumsum(np.pad(a, ((k + 1, k), (0, 0)), mode='edge'), axis=0)
        return (c[2 * k + 1:] - c[:-2 * k - 1]) / (2 * k + 1)
    m = np.clip(box(box(m)), 0, 1).astype(np.float32)
    out = bpy.data.images.new('T_Lifeblood_Core_Emissive', w, h, alpha=False)
    out.colorspace_settings.name = 'Non-Color'
    rgba = np.dstack([m, m, m, np.ones_like(m)]).ravel()
    out.pixels.foreach_set(rgba)
    out.filepath_raw = DST + 'T_Lifeblood_Core_Emissive.png'
    out.file_format = 'PNG'
    out.save()
    return out, {'px': [w, h], 'coverage': round(float(m.mean()), 3), 'white_over_half': round(float((m > .5).mean()), 3)}


def export_glb(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_animations=False, export_image_format='AUTO')


# ---- build ----------------------------------------------------------------------------------------------------------
bpy.ops.wm.read_homefile(use_empty=True)
K_EST = TARGET_HEIGHT / 0.98
rec = {'script': 'Scripts/Blender/AssembleLifeblood.py', 'date': '2026-10-31', 'parts': {}}
objs = {}
for name, fn, size in PARTS:
    o, nsrc = import_part(fn)
    o.name = o.data.name = name
    r = {'source': 'Source/%s.glb' % fn, 'source_objects': nsrc, 'source_tris': tris_of(o.data)}
    lo, hi = vbounds(o)
    r['source_size_src'] = [round(v, 3) for v in hi - lo]
    r['strays'] = remove_strays(o)
    r['weld'] = weld_and_fix_normals(o)
    r['textures'] = rename_and_resize(o, name.split('_')[-1], size)
    rec['parts'][name] = r
    objs[name] = o
    print('CLEANED', name, r['weld'], r['strays']['removed'], flush=True)

body = objs['SM_Lifeblood_Body']
rec['parts']['SM_Lifeblood_Body']['rods'] = remove_rods(body)
rec['parts']['SM_Lifeblood_Body']['side_labels'] = fix_side_text(body, [o for o in objs.values() if o is not body])
print('SIDE_LABELS', rec['parts']['SM_Lifeblood_Body']['side_labels'], flush=True)
lo, hi = vbounds(body)
K = TARGET_HEIGHT / (hi.z - lo.z)
K_EST = K
src_shift = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
body_bvh = bvh_of(body)
proud_src = PROUD_MM / 1000 / K

place = {}
place['SM_Lifeblood_Core'] = place_core(objs['SM_Lifeblood_Core'], body_bvh)
place['SM_Lifeblood_CoinPanel'] = mount_panel(objs['SM_Lifeblood_CoinPanel'], body_bvh, COIN_RECT, COIN_CENTRE_XZ,
                                              COIN_WIDTH, proud_src)
cp = place['SM_Lifeblood_CoinPanel']
cp['flatten'] = flatten_behind_plate(objs['SM_Lifeblood_CoinPanel'], cp.pop('_nrm'), cp.pop('_plate'), COIN_BACK_KEEP)
place['SM_Lifeblood_Tagline'] = mount_panel(objs['SM_Lifeblood_Tagline'], body_bvh, TAG_RECT, TAG_CENTRE_XZ,
                                            TAG_WIDTH, proud_src)
for k_ in ('_nrm', '_plate'):
    place['SM_Lifeblood_Tagline'].pop(k_)

# one transform for all: cabinet bbox centre in X/Y and bottom to the origin, then scale to 2.2 m
FINAL = Matrix.Scale(K, 4) @ Matrix.Translation(-src_shift)
for o in objs.values():
    o.data.transform(FINAL)
    o.data.update()
    o.matrix_world = Matrix.Identity(4)

for n in ('SM_Lifeblood_Core', 'SM_Lifeblood_CoinPanel', 'SM_Lifeblood_Tagline'):
    place[n]['overlaps_body_tri_pairs'] = overlap_report(objs[n], body)
place['SM_Lifeblood_Core']['overlaps_coin_or_tagline'] = (overlap_report(objs['SM_Lifeblood_Core'],
                                                          objs['SM_Lifeblood_Tagline']))

mask_img, mask_info = make_emissive_mask(objs['SM_Lifeblood_Core'])

col = bpy.data.collections.new('Lifeblood')
bpy.context.scene.collection.children.link(col)
for o in objs.values():
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)

order = [objs[n] for n, _, _ in PARTS]
export_glb(order, DST + 'Lifeblood_Assembly.glb')
for o in order:
    export_glb([o], DST + o.name + '.glb')
for img in bpy.data.images:
    if img.size[0] and not img.packed_file:
        img.pack()
    elif img.is_dirty:
        img.pack()
bpy.ops.wm.save_as_mainfile(filepath=DST + 'Lifeblood_Assembly.blend', compress=True)

# ---- verify the written assembly -----------------------------------------------------------------------------------
for name in objs:
    o = objs[name]
    a, b = vbounds(o)
    rec['parts'][name].update({
        'tris': tris_of(o.data), 'size_m': [round(v, 3) for v in b - a],
        'min_m': [round(v, 3) for v in a], 'max_m': [round(v, 3) for v in b],
        'placement': place.get(name, {'scale_to_2_2m': round(K, 4)})})
    rec['parts'][name]['placement'] = dict(rec['parts'][name]['placement'])
    if name in place:
        p = rec['parts'][name]['placement']
        for k_ in list(p):
            if k_.endswith('_src') and isinstance(p[k_], (int, float)):
                p[k_.replace('_src', '_m')] = round(p[k_] * K, 4)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.gltf(filepath=DST + 'Lifeblood_Assembly.glb')
ms = [o for o in bpy.context.scene.objects if o.type == 'MESH']
pts = np.vstack([np.array([o.matrix_world @ Vector(c) for c in o.bound_box]) for o in ms])
rec['assembly'] = {
    'file': DST + 'Lifeblood_Assembly.glb', 'objects': sorted(o.name for o in ms),
    'tris_total': sum(tris_of(o.data) for o in ms),
    'size_m': [round(v, 3) for v in pts.max(0) - pts.min(0)],
    'pivot_check_m': {'min_z': round(float(pts[:, 2].min()), 4),
                      'centre_x': round(float(pts[:, 0].min() + pts[:, 0].max()) / 2, 4),
                      'centre_y': round(float(pts[:, 1].min() + pts[:, 1].max()) / 2, 4)},
    'images_in_glb': {i.name: list(i.size) for i in bpy.data.images if i.size[0]},
    'file_mb': round(os.path.getsize(DST + 'Lifeblood_Assembly.glb') / 1e6, 2),
    'scale_factor': round(K, 4)}
rec['part_files'] = {o: round(os.path.getsize(DST + o + '.glb') / 1e6, 2) for o in objs}
rec['emissive_mask'] = dict(mask_info, file=DST + 'T_Lifeblood_Core_Emissive.png',
                            note='not wired into the GLB; UE material: BaseColor * mask * pulse -> Emissive')
rec['blend'] = DST + 'Lifeblood_Assembly.blend'

# ---- renders ----------------------------------------------------------------------------------------------------------
sc = bpy.context.scene
sc.world = bpy.data.worlds.new('w')
cd = bpy.data.cameras.new('cam')
cd.lens = 50
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
H = TARGET_HEIGHT


def shoot(path, target, radius, az, el, rx=1024, ry=1024):
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    dist = radius / (18 / cd.lens) * 1.05      # fits `radius` along the image's longer side (sensor fit AUTO)
    a, e = math.radians(az), math.radians(el)
    cam.location = target + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def workbench():
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.render.film_transparent = False
    sc.world.color = (0.05, 0.05, 0.055)


mid = Vector((0, 0, H * 0.5))
win = Vector((0, 0, H * 0.20))   # replaced below by the measured window/coin region
core = next(o for o in ms if o.name.startswith('SM_Lifeblood_Core'))
coin = next(o for o in ms if o.name.startswith('SM_Lifeblood_CoinPanel'))
cpts = np.array([core.matrix_world @ Vector(c) for c in core.bound_box] +
                [coin.matrix_world @ Vector(c) for c in coin.bound_box])
win = Vector(((cpts[:, 0].min() + cpts[:, 0].max()) / 2, 0, (cpts[:, 2].min() + cpts[:, 2].max()) / 2))
win_r = (cpts[:, 2].max() - cpts[:, 2].min()) * 0.62
shots = {}
workbench()
VIEWS = {'front': (mid, H * 0.56, 0, 4), '34_left': (mid, H * 0.56, -38, 12), '34_right': (mid, H * 0.56, 38, 12),
         'closeup': (win, win_r, 18, 8), 'side_check': (win, win_r, 72, 4), 'below_check': (win, win_r, 30, -12)}
for tag, (t, r, az, el) in VIEWS.items():
    shots['wb_' + tag] = shoot(OUT + 'wb_%s.png' % tag, t, r, az, el)
shots['wb_compare'] = shoot(OUT + 'wb_compare.png', mid, H * 0.56, 32, 10, 683, 1024)

# Eevee: the core's blood lit through the mask (render-only; the exported GLB keeps the plain Tripo material)
sc.render.engine = 'BLENDER_EEVEE'
try:
    sc.eevee.taa_render_samples = 48
except AttributeError:
    pass
try:
    sc.world.use_nodes = True
except AttributeError:
    pass
wnt = sc.world.node_tree
bg = next((n for n in wnt.nodes if n.type == 'BACKGROUND'), None)
if bg is None:
    bg = wnt.nodes.new('ShaderNodeBackground')
    wout = next((n for n in wnt.nodes if n.type == 'OUTPUT_WORLD'), None) or wnt.nodes.new('ShaderNodeOutputWorld')
    wnt.links.new(bg.outputs[0], wout.inputs[0])
bg.inputs[0].default_value = (0.02, 0.02, 0.025, 1)
bg.inputs[1].default_value = 1.0
for nm, loc, energy, size in (('key', (1.8, -2.6, 3.0), 600, 2.0), ('fill', (-2.4, -1.5, 1.6), 180, 2.5),
                              ('rim', (0.5, 2.5, 3.2), 300, 1.5)):
    ld = bpy.data.lights.new(nm, 'AREA')
    ld.energy, ld.size = energy, size
    lo_ = bpy.data.objects.new(nm, ld)
    sc.collection.objects.link(lo_)
    lo_.location = loc
    lo_.rotation_euler = (Vector((0, 0, 1.1)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
mask = bpy.data.images.load(DST + 'T_Lifeblood_Core_Emissive.png')
mask.colorspace_settings.name = 'Non-Color'
cm = core.material_slots[0].material
nt = cm.node_tree
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
basetex = next(l.from_node for l in bsdf.inputs['Base Color'].links)
mt = nt.nodes.new('ShaderNodeTexImage')
mt.image = mask
mul = nt.nodes.new('ShaderNodeVectorMath')
mul.operation = 'MULTIPLY'
nt.links.new(basetex.outputs['Color'], mul.inputs[0])
nt.links.new(mt.outputs['Color'], mul.inputs[1])
nt.links.new(mul.outputs[0], bsdf.inputs['Emission Color'])
bsdf.inputs['Emission Strength'].default_value = 6.0
pl = bpy.data.lights.new('blood_glow', 'POINT')
pl.color, pl.energy, pl.shadow_soft_size = (1.0, 0.08, 0.05), 25, 0.15
plo = bpy.data.objects.new('blood_glow', pl)
sc.collection.objects.link(plo)
plo.location = Vector(((cpts[:, 0].min() + cpts[:, 0].max()) / 2, -0.15,
                       (np.array([core.matrix_world @ Vector(c) for c in core.bound_box])[:, 2].mean())))
shots['ev_34_right'] = shoot(OUT + 'ev_34_right.png', mid, H * 0.56, 38, 12)
shots['ev_closeup'] = shoot(OUT + 'ev_closeup.png', win, win_r, 18, 8)
shots['ev_compare'] = shoot(OUT + 'ev_compare.png', mid, H * 0.56, 32, 10, 683, 1024)
rec['renders'] = shots


def sheets():
    from PIL import Image, ImageDraw, ImageFont
    try:
        big = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 22)
        small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 16)
    except OSError:
        big = small = ImageFont.load_default()
    cell, head, lab = 512, 44, 26
    tiles = [('wb_front', 'Workbench front (-Y)'), ('wb_34_left', 'Workbench 3/4 left'),
             ('wb_34_right', 'Workbench 3/4 right'), ('wb_closeup', 'Workbench window + coin panel'),
             ('ev_34_right', 'Eevee 3/4, blood lit by mask'), ('ev_closeup', 'Eevee close-up')]
    sheet = Image.new('RGB', (cell * 3, head + 2 * (cell + lab)), (30, 30, 34))
    d = ImageDraw.Draw(sheet)
    a = rec['assembly']
    d.text((10, 10), 'Lifeblood assembly 2026-10-31   %s m   %d tris   4 meshes: Body, CoinPanel, Tagline, Core' % (
        ' x '.join('%.2f' % v for v in a['size_m']), a['tris_total']), fill=(235, 235, 235), font=big)
    for i, (k_, t) in enumerate(tiles):
        x, y = (i % 3) * cell, head + (i // 3) * (cell + lab)
        d.text((x + 8, y + 3), t, fill=(250, 200, 60), font=small)
        sheet.paste(Image.open(shots[k_]).convert('RGB').resize((cell, cell)), (x, y + lab))
    sheet.save(OUT + 'assembly_sheet.png')
    con = Image.open(CONCEPT).convert('RGB')
    con = con.resize((int(con.width * 1024 / con.height), 1024))
    wb = Image.open(shots['wb_compare']).convert('RGB')
    ev = Image.open(shots['ev_compare']).convert('RGB')
    cmp_ = Image.new('RGB', (con.width + wb.width + ev.width + 20, 1024 + 40), (30, 30, 34))
    d = ImageDraw.Draw(cmp_)
    xs_ = [0, con.width + 10, con.width + wb.width + 20]
    for x, im, t in zip(xs_, (con, wb, ev), ('owner concept', 'assembly, Workbench texture', 'assembly, Eevee')):
        cmp_.paste(im, (x, 40))
        d.text((x + 8, 8), t, fill=(250, 200, 60), font=big)
    cmp_.save(OUT + 'concept_compare.png')
    return OUT + 'assembly_sheet.png', OUT + 'concept_compare.png'


rec['sheet'], rec['concept_compare'] = sheets()
for path in (OUT + 'clean.json', DST + 'clean.json'):
    json.dump(rec, open(path, 'w'), indent=1, default=lambda x: float(x) if hasattr(x, '__float__') else str(x))
print('ASSEMBLE_LIFEBLOOD_DONE', json.dumps({n: (r['tris'], r['size_m']) for n, r in rec['parts'].items()}),
      flush=True)
