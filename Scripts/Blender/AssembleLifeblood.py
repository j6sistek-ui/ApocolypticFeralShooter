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

Pass 3 (2026-11-01, owner: "the main words on the top part, under LIFEBLOOD ... needs to be cleaned up"):
  body textures   kept at the source 4096 (were cut to 2048, which softened the baked sign further); the other parts
                  keep their sizes. clean.json parts.SM_Lifeblood_Body.textures records the px.
  front subtitle  "PERK MACHINE", its two divider lines and the heartbeat under it were baked soft, wobbly and smudged
                  (texel streaks, the line leaning ~0.6 degree). fix_front_subtitle(): the front sign band is rendered
                  flat and orthographic (Workbench texture colour, 10000 px per source unit over FRONT_VIEW); the old
                  elements are measured there (letter extent, per-letter cap height, word gap, line ends and height,
                  heartbeat baseline / beat extent, the three colours) and masked (anything with green in it, the glass
                  and its red glow have none, but only inside subtitle_seed(): the measured letters, lines and pulse,
                  padded, so glass detail in the box - the grey stripe at the left frame, the white highlight and
                  specks on the lower edge - stays; where a stripe crosses a divider line only the line's pink is cut;
                  the baseline's faint red tails, which have no green, are followed out and cut along the baseline),
                  inpainted (cv2 TELEA, then smoothed; the divider-line holes are filled column by column from the
                  glass just above and below instead, so the stripe runs on through) and redrawn crisp: the text level in
                  SUB_FONT (Arial Bold, best of ten Windows sans by overlap with the old letters) at the measured size,
                  centre, ink extent and word gap (uniform tracking solved for both); the divider lines symmetric and
                  level with their outward fade, the outer SUB_LINE_TAPER of each narrowing to a point; the heartbeat as a clean polyline (SUB_BEAT) on a tapered baseline;
                  faint screen-blended halos (SUB_GLOW) for the lit-glass look. LIFEBLOOD and the heart are untouched
                  (SUB_BOX stops 6 mm under LIFEBLOOD). Texels: every texel within 2.5 texels of a front-skin triangle
                  whose position falls in SUB_BOX (nearest island wins, so seam padding is ours unless another island
                  owns it) takes the new colour, sampled with a box filter over its own sheared footprint; texels where
                  nothing changed keep their exact values. The old relief in the normal map sits off the old colour, so
                  the normal map is replaced over the box (feathered) with the new elements embossed (SUB_RELIEF), in
                  each texel's own tangent frame. ORM has no letter imprint and is left alone. Debug images
                  front_sub_before.png / _after_view.png / _masks.png in the render folder; numbers in clean.json
                  parts.SM_Lifeblood_Body.front_subtitle.
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
# front subtitle (pass 3): flat front view of the sign band, measured and repainted, then pushed into the texels
FRONT_PX_PER_UNIT = 10000                                     # 3600 x 1000 px over FRONT_VIEW (~4.7 px per 4K texel)
FRONT_VIEW = {'x': (-0.18, 0.18), 'z': (0.54, 0.64)}
SUB_BOX = {'x': (-0.1405, 0.1405), 'z': (0.5555, 0.6085)}    # under LIFEBLOOD (its bottom is z 0.6145), inside the frame
SUB_FONT = 'C:/Windows/Fonts/arialbd.ttf'                     # best of 10 Windows sans against the old letters (IoU 0.53)
SUB_LINE_T, SUB_PULSE_T = 0.0012, 0.0017                      # crisp stroke widths
SUB_LINE_FADE = 0.30                                          # divider line alpha at its outer end (the old ones fade out)
SUB_LINE_TAPER = 0.35                                         # outer part of each divider narrowing to a point (as the old)
SUB_SEED_PAD = 0.003                                          # old-element search reaches this far past the measured extents
SUB_LINE_BAND = 0.004                                         # ... and this far above / below each divider line's height
SUB_PULSE_BAND = 0.0008                                       # half height of the old baseline's faint red tails (always cut)
SUB_GLOW = {'text': (0.0009, 0.16, (0.95, 0.40, 0.34)),       # (sigma, strength, colour) of the screen-blended halos
            'lines': (0.0013, 0.35, (1.0, 0.16, 0.10))}
SUB_RELIEF = 0.00035                                          # emboss height of the new elements in the normal map
SUB_NRM_FEATHER = 0.0015                                      # the normal map is replaced over the box, feathered inside
# heartbeat, stroke centres: x across the measured beat, z as a fraction of the measured up / down excursion
SUB_BEAT = ((0.0, 0.0), (0.08, 0.31), (0.225, -0.78), (0.38, 1.0), (0.55, -1.0), (0.76, 0.68), (0.91, -0.46), (1.0, 0.0))

PARTS = [  # (object name, source file, texture size)
    ('SM_Lifeblood_Body', 'lifeblood_machine', 4096),        # full source size: the sign text needs every texel
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


# ---- pass 3: front subtitle ("PERK MACHINE", divider lines, heartbeat) -------------------------------------------
def measure_subtitle(V, P, XR, ZR):
    """Find the old subtitle elements in the flat front view V (rows top-down, sRGB 0..1)."""
    H, W = V.shape[:2]
    xc = (XR[0] + XR[1]) / 2

    def R(z): return int(round((ZR[1] - z) * P - 0.5))
    def C(x): return int(round((x - xc) * P + W / 2 - 0.5))
    def Xc(c): return (c + 0.5 - W / 2) / P + xc
    def Zr(r): return ZR[1] - (r + 0.5) / P
    lum, sat, G = V.mean(2), V.max(2) - V.min(2), V[..., 1]
    m = {}
    # letters: white, low saturation, between the divider lines; one column run per letter
    r0, r1, c0, c1 = R(0.607), R(0.583), C(-0.093), C(0.093)
    wh = (lum[r0:r1, c0:c1] > 0.45) & (sat[r0:r1, c0:c1] < 0.3)
    on = wh.sum(0) > 2
    segs, s = [], None
    for c in range(len(on) + 1):
        v = c < len(on) and on[c]
        if v and s is None:
            s = c
        elif not v and s is not None:
            if c - s > 0.0015 * P:
                rr = np.where(wh[:, s:c].any(1))[0]
                segs.append((Xc(c0 + s), Xc(c0 + c - 1), Zr(r0 + rr.max()), Zr(r0 + rr.min())))
            s = None
    gaps = [b[0] - a[1] for a, b in zip(segs[:-1], segs[1:])]
    hgt = float(np.median([t[3] - t[2] for t in segs]))          # per letter: the old line is tilted
    mid = float(np.median([(t[3] + t[2]) / 2 for t in segs]))
    m['letters'] = len(segs)
    m['text_x'] = [segs[0][0], segs[-1][1]]
    m['baseline_z'], m['cap_top_z'] = mid - hgt / 2, mid + hgt / 2
    m['word_gap'] = max(gaps)
    m['old_tilt_z_right_minus_left'] = segs[-1][2] - segs[0][2]
    core = (lum[r0:r1, c0:c1] > 0.7) & (sat[r0:r1, c0:c1] < 0.2)
    m['text_rgb'] = np.median(V[r0:r1, c0:c1][core], 0).tolist()
    # divider lines: pink rows either side of the text
    m['lines'] = []
    lr0, lr1 = R(0.599), R(0.591)
    for sg in (-1, 1):
        a_, b_ = sorted((C(sg * 0.090), C(sg * 0.140)))
        g = G[lr0:lr1, a_:b_]
        pk = g > 0.10
        cols = np.where(pk.any(0))[0]
        xs = sorted((Xc(a_ + cols.min()), Xc(a_ + cols.max())), key=abs)
        gw = g * pk
        m['lines'].append({'inner_x': xs[0], 'outer_x': xs[1],
                           'z': Zr(float((gw * np.arange(lr0, lr1)[:, None]).sum() / gw.sum()))})
    lp = np.zeros_like(G, bool)
    lp[lr0:lr1] = True
    lp[:, C(-0.09):C(0.09)] = False
    lp[:, :C(SUB_BOX['x'][0])] = False
    lp[:, C(SUB_BOX['x'][1]):] = False
    sel = lp & (G > 0.10)
    m['line_rgb'] = np.median(V[sel & (G > 0.85 * G[sel].max())], 0).tolist()
    # heartbeat: tapered baseline with a beat in the middle
    pr0, pr1, pc0, pc1 = R(0.5845), R(0.556), C(-0.065), C(0.065)
    g = G[pr0:pr1, pc0:pc1]
    pk = g > 0.15
    rows = np.arange(pr0, pr1)
    cz = []
    for j in range(pk.shape[1]):
        rr = np.where(pk[:, j])[0]
        if len(rr):
            gw = g[:, j] * pk[:, j]
            cz.append((Xc(pc0 + j), Zr(pr0 + rr.max()), Zr(pr0 + rr.min()), Zr(float((gw * rows).sum() / gw.sum()))))
    cz = np.array(cz)
    thick = cz[:, 2] - cz[:, 1]
    flat = thick < 2.5 * np.median(thick)
    half = float(np.median(thick[flat])) / 2
    m['pulse_base_z'] = float(np.median(cz[flat, 3]))
    m['pulse_x'] = [float(cz[:, 0].min()), float(cz[:, 0].max())]
    m['beat_x'] = [float(cz[~flat, 0].min()), float(cz[~flat, 0].max())]
    m['beat_up'] = float(cz[:, 2].max() - m['pulse_base_z'] - half)
    m['beat_down'] = float(m['pulse_base_z'] - cz[:, 1].min() - half)
    sel = np.zeros_like(G, bool)
    sel[pr0:pr1, pc0:pc1] = pk
    m['pulse_rgb'] = np.median(V[sel & (G > 0.85 * G[sel].max())], 0).tolist()
    # the baseline's faint red tails (no green) run on past the measured pulse: follow the red until it is glass
    rb0, rb1 = R(m['pulse_base_z'] + 0.001), R(m['pulse_base_z'] - 0.001) + 1
    red = V[rb0:rb1, :, 0].max(0)
    m['pulse_tail_x'] = []
    for sg, xe in ((-1, m['pulse_x'][0]), (1, m['pulse_x'][1])):
        a_, b_ = sorted((C(sg * 0.075), C(sg * 0.090)))
        bgr = float(np.median(V[rb0:rb1, a_:b_, 0]))
        c = C(xe)
        while abs(Xc(c + sg)) < 0.085 and red[c + sg] > bgr + 0.010:
            c += sg
        m['pulse_tail_x'].append(float(Xc(c)))
    return m


def subtitle_seed(m, P, XR, ZR, H, W):
    """Where old elements may be (view grid): the letters, the two divider lines and the heartbeat with its baseline
    tails, from the measurements and padded. Glass detail elsewhere in SUB_BOX (the grey stripe at the left frame, the
    white highlight and specks on the lower edge) is never treated as old."""
    xc = (XR[0] + XR[1]) / 2
    seed = np.zeros((H, W), bool)

    def rect(x0, x1, z0, z1):
        seed[max(0, int((ZR[1] - z1) * P)):max(0, int((ZR[1] - z0) * P)),
             max(0, int((x0 - xc) * P + W / 2)):max(0, int((x1 - xc) * P + W / 2))] = True
    p = SUB_SEED_PAD
    rect(m['text_x'][0] - p, m['text_x'][1] + p, m['baseline_z'] - p, m['cap_top_z'] + p)
    for l_ in m['lines']:
        a_, b_ = sorted((l_['inner_x'], l_['outer_x']))
        rect(a_ - p, b_ + p, l_['z'] - SUB_LINE_BAND, l_['z'] + SUB_LINE_BAND)
    x0, x1 = min(m['pulse_x'][0], m['pulse_tail_x'][0]), max(m['pulse_x'][1], m['pulse_tail_x'][1])
    rect(x0 - p, x1 + p, m['pulse_base_z'] - m['beat_down'] - p, m['pulse_base_z'] + m['beat_up'] + p)
    return seed


def draw_subtitle(m, P, XR, ZR, W, H, S=2):
    """New crisp elements as alpha layers on the view grid (drawn at S x, box-filtered down): text, lines + pulse."""
    from PIL import Image, ImageDraw, ImageFont
    xc = (XR[0] + XR[1]) / 2

    def cx(x): return ((x - xc) * P + W / 2) * S
    def rz(z): return (ZR[1] - z) * P * S
    text_l = Image.new('L', (W * S, H * S), 0)
    lp_l = Image.new('L', (W * S, H * S), 0)
    # text: level, measured cap height and ink extent, uniform tracking + word space solved for extent and word gap
    cap = m['cap_top_z'] - m['baseline_z']
    f = ImageFont.truetype(SUB_FONT, 600)
    g = {}
    for ch in set('PERKMACHINE'):
        im = Image.new('L', (1200, 1200), 0)
        ImageDraw.Draw(im).text((200, 200), ch, font=f, fill=255)
        g[ch] = (im, im.getbbox(), f.getlength(ch))
    hb = g['H'][1]
    k = cap / (hb[3] - hb[1])
    words = ('PERK', 'MACHINE')

    def ink(t, s):
        pen, res = 0.0, []
        for wi, wd in enumerate(words):
            if wi:
                pen += s
            for ch in wd:
                im, bb, adv = g[ch]
                res.append((ch, pen + (bb[0] - 200) * k, pen + (bb[2] - 200) * k))
                pen += adv * k + t
        return res

    def meas(t, s):
        r = ink(t, s)
        return np.array([r[-1][2] - r[0][1], r[len(words[0])][1] - r[len(words[0]) - 1][2]])
    b0 = meas(0, 0)
    A = np.c_[meas(1e-3, 0) - b0, meas(0, 1e-3) - b0] / 1e-3
    t, s = np.linalg.solve(A, np.array([m['text_x'][1] - m['text_x'][0], m['word_gap']]) - b0)
    res = ink(t, s)
    off = (m['text_x'][0] + m['text_x'][1]) / 2 - (res[0][1] + res[-1][2]) / 2
    for ch, a, _ in res:
        im, bb, _ = g[ch]
        sz = (max(1, int(round((bb[2] - bb[0]) * k * P * S))), max(1, int(round((bb[3] - bb[1]) * k * P * S))))
        gl = im.crop(bb).resize(sz, Image.LANCZOS)
        ztop = m['baseline_z'] + cap - (bb[1] - hb[1]) * k
        text_l.paste(gl, (int(round(cx(a + off))), int(round(rz(ztop)))), gl)
    lay = {'font': SUB_FONT.split('/')[-1], 'tracking_of_cap': round(float(t / cap), 4),
           'space_of_cap': round(float(s / cap), 4), 'cap_height': round(cap, 5), 'baseline_z': round(m['baseline_z'], 5),
           'text_x': [round(float(res[0][1] + off), 5), round(float(res[-1][2] + off), 5)]}
    # divider lines: level at the mean old height, symmetric (mean inner / outer ends), fading outwards, the outer
    # SUB_LINE_TAPER of each narrowing to a point like the old ones (drawn at 4x for the thin tip)
    zl = float(np.mean([l_['z'] for l_ in m['lines']]))
    xin = float(np.mean([abs(l_['inner_x']) for l_ in m['lines']]))
    xout = float(np.mean([abs(l_['outer_x']) for l_ in m['lines']]))
    n = 200
    top = int(rz(zl + SUB_LINE_T)) - 2                         # a strip around the lines only
    hs = int(rz(zl - SUB_LINE_T)) + 2 - top
    ln_l = Image.new('L', (W * S * 4, hs * 4), 0)
    d4 = ImageDraw.Draw(ln_l)

    def hw(u): return SUB_LINE_T / 2 * min(1.0, (1 - u) / SUB_LINE_TAPER)

    def q(x, z): return (cx(x) * 4, (rz(z) - top) * 4)
    for sg in (-1, 1):
        for i in range(n):
            u0, u1 = i / n, (i + 1) / n
            a = 1 - (1 - SUB_LINE_FADE) * ((u0 + u1) / 2) ** 1.3
            xa, xb = sg * (xin + (xout - xin) * u0), sg * (xin + (xout - xin) * u1)
            d4.polygon([q(xa, zl + hw(u0)), q(xb, zl + hw(u1)), q(xb, zl - hw(u1)), q(xa, zl - hw(u0))],
                       fill=int(255 * a))
    lp_l.paste(ln_l.resize((W * S, hs), Image.BOX), (0, top))
    d = ImageDraw.Draw(lp_l)
    lay.update({'line_z': round(zl, 5), 'line_inner_x': round(xin, 5), 'line_outer_x': round(xout, 5),
                'line_width': SUB_LINE_T, 'line_taper': SUB_LINE_TAPER})
    # heartbeat: baseline fading out from the beat, beat as one polyline with round joins
    zb = m['pulse_base_z']
    bx0, bx1 = m['beat_x']
    pc = (bx0 + bx1) / 2
    hl = max(pc - m['pulse_x'][0], m['pulse_x'][1] - pc) + 0.004
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        a = (1 - (u0 + u1) / 2) ** 1.5
        for sg in (-1, 1):
            xa, xb = pc + sg * (bx1 - pc + (hl - (bx1 - pc)) * u0), pc + sg * (bx1 - pc + (hl - (bx1 - pc)) * u1)
            d.rectangle([cx(min(xa, xb)), rz(zb + SUB_PULSE_T / 2), cx(max(xa, xb)), rz(zb - SUB_PULSE_T / 2) - 1],
                        fill=int(255 * a))
    pts = [(cx(bx0 + u * (bx1 - bx0)), rz(zb + (v * m['beat_up'] if v > 0 else v * m['beat_down']))) for u, v in SUB_BEAT]
    pw = SUB_PULSE_T * P * S
    d.line(pts, fill=255, width=int(round(pw)), joint='curve')
    for p in pts:
        d.ellipse([p[0] - pw / 2, p[1] - pw / 2, p[0] + pw / 2, p[1] + pw / 2], fill=255)
    lay.update({'pulse_z': round(zb, 5), 'beat_x': [round(bx0, 5), round(bx1, 5)], 'pulse_half_len': round(hl, 5),
                'beat_up': round(m['beat_up'], 5), 'beat_down': round(m['beat_down'], 5), 'pulse_width': SUB_PULSE_T})
    text = np.asarray(text_l.resize((W, H), Image.BOX)).astype(np.float32) / 255
    lp = np.asarray(lp_l.resize((W, H), Image.BOX)).astype(np.float32) / 255
    return text, lp, lay


def subtitle_composite(bg, text, lp, glow, lp_rgb, text_rgb):
    out = 1 - (1 - bg) * (1 - glow)
    out = out * (1 - lp[..., None]) + lp_rgb * lp[..., None]
    out = out * (1 - text[..., None]) + text_rgb * text[..., None]
    return np.clip(out, 0, 1)


def subtitle_view(V, P, XR, ZR):
    """In the flat front view: old-element mask, inpainted glass behind them, the new layers and halos."""
    import cv2
    H, W = V.shape[:2]
    xc = (XR[0] + XR[1]) / 2
    m = measure_subtitle(V, P, XR, ZR)
    text, lp, lay = draw_subtitle(m, P, XR, ZR, W, H)
    box = np.zeros((H, W), np.float32)
    r0, r1 = int((ZR[1] - SUB_BOX['z'][1]) * P), int((ZR[1] - SUB_BOX['z'][0]) * P)
    c0, c1 = int((SUB_BOX['x'][0] - xc) * P + W / 2), int((SUB_BOX['x'][1] - xc) * P + W / 2)
    box[r0:r1, c0:c1] = 1
    lum, sat, G = V.mean(2), V.max(2) - V.min(2), V[..., 1]
    Xs = (np.arange(W) + 0.5 - W / 2) / P + xc
    Zs = ZR[1] - (np.arange(H) + 0.5) / P
    seed = subtitle_seed(m, P, XR, ZR, H, W)
    # old elements: anything with green in it (the glass and its red glow have none) or light and unsaturated, but only
    # where the measured elements are (seed)
    old = ((G > 0.03) | ((lum > 0.25) & (sat < 0.4))) & (box > 0) & seed
    # grey glass stripes (columns that are greenish down the whole box, off the line rows) cross the divider lines'
    # outer ends: there only the line's own pink counts as old
    zl = float(np.mean([l_['z'] for l_ in m['lines']]))
    off_line = np.abs(Zs - zl) > SUB_LINE_BAND
    rows = np.arange(H)[(box[:, c0] > 0) & off_line]
    stripe = (np.median(G[rows], 0) > 0.03) & (np.abs(Xs) > 0.10)
    stripe = cv2.dilate(stripe.astype(np.uint8)[None], np.ones((1, 7), np.uint8))[0] > 0
    pink = (G > 0.10) | (V[..., 0] - G > 0.05)
    old &= ~stripe[None, :] | pink
    # the baseline's faint red tails have no green: always cut along the baseline out to where the red ends
    tz = (np.abs(Zs - m['pulse_base_z']) < SUB_PULSE_BAND)[:, None]
    tx = ((Xs > m['pulse_tail_x'][0] - 0.0005) & (Xs < m['pulse_tail_x'][1] + 0.0005))[None, :]
    old |= tz & tx & (box > 0)
    old = cv2.morphologyEx(old.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    hole = cv2.dilate(old, np.ones((11, 11), np.uint8))
    hole[box == 0] = 0
    pad = 40
    sl = (slice(r0 - pad, r1 + pad), slice(c0 - pad, c1 + pad))
    clean = V.copy()
    clean[sl] = cv2.inpaint((V[sl] * 255 + 0.5).astype(np.uint8), hole[sl] * 255, 15,
                            cv2.INPAINT_TELEA).astype(np.float32) / 255
    # TELEA leaves blotches where the old letters' dark shadow fed it: smooth the filled part
    soft = cv2.GaussianBlur(cv2.dilate(hole, np.ones((7, 7), np.uint8)).astype(np.float32), (0, 0), 3)[..., None]
    clean = clean * (1 - soft) + cv2.GaussianBlur(clean, (0, 0), 0.0012 * P) * soft
    # the divider lines are horizontal over vertically-running glass (the stripe): fill their holes column by column
    # between the glass just above and below instead, and keep the untouched glass there exact
    nfill = 0
    for l_ in m['lines']:
        a_, b_ = sorted((l_['inner_x'], l_['outer_x']))
        ca = max(c0, int((max(a_ - SUB_SEED_PAD, -0.5) - xc) * P + W / 2))
        cb = min(c1, int((b_ + SUB_SEED_PAD - xc) * P + W / 2))
        ra = max(r0, int((ZR[1] - l_['z'] - SUB_LINE_BAND - 0.001) * P))
        rb = min(r1, int((ZR[1] - l_['z'] + SUB_LINE_BAND + 0.001) * P))
        for c in range(ca, cb):
            if abs(Xs[c]) < m['text_x'][1] + SUB_SEED_PAD:
                continue                                       # the letters' hole, TELEA's
            hr = np.nonzero(hole[ra:rb, c])[0]
            if len(hr) and (hr[0] < 3 or hr[-1] > rb - ra - 4):
                continue                                       # hole runs off the band: leave it to TELEA
            clean[ra:rb, c] = V[ra:rb, c]
            if not len(hr):
                continue
            u, v = ra + hr[0] - 1, ra + hr[-1] + 1
            t = ((np.arange(u + 1, v) - u) / (v - u))[:, None]
            clean[u + 1:v, c] = V[u - 2:u + 1, c].mean(0) * (1 - t) + V[v:v + 3, c].mean(0) * t
            nfill += 1
    lay.update({'stripe_columns': int(stripe[c0:c1].sum()), 'line_fill_columns': nfill,
                'pulse_tail_x': [round(v_, 5) for v_ in m['pulse_tail_x']]})
    oldm = cv2.GaussianBlur(cv2.dilate(hole, np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 2.0) * box
    (gt, gts, gtc), (gl, gls, glc) = SUB_GLOW['text'], SUB_GLOW['lines']
    glow = np.clip(cv2.GaussianBlur(text, (0, 0), gt * P)[..., None] * gts * np.array(gtc, np.float32) +
                   cv2.GaussianBlur(lp, (0, 0), gl * P)[..., None] * gls * np.array(glc, np.float32), 0, 1)
    # the lines are dimmer and pinker than the pulse in the old sign: colour the line/pulse layer by height
    zz = ZR[1] - (np.arange(H) + 0.5) / P
    is_pulse = (zz < (lay['line_z'] + lay['pulse_z']) / 2).astype(np.float32)[:, None, None]
    lp_rgb = (np.array(m['pulse_rgb'], np.float32) * is_pulse + np.array(m['line_rgb'], np.float32) * (1 - is_pulse))
    lp_rgb = np.broadcast_to(lp_rgb, (H, W, 3)).astype(np.float32)
    L = {'text': text, 'lp': lp, 'glow': glow.astype(np.float32), 'lp_rgb': lp_rgb,
         'text_rgb': np.array(m['text_rgb'], np.float32)}
    return m, lay, clean, oldm, hole, L


def front_texel_map(o, w, h, XR, ZR):
    """Texel -> triangle map for the front-most skin in the view (any normal: Tripo folds slivers into the glass).
    Every face competes for the texels within 2.5 texels of its UV triangle, nearest edge wins, so texels just outside
    our islands are ours (seam padding) unless they belong to another island. Returns tid (-1 none, -2 foreign, else a
    row of tris: uv0, inverse UV jacobian, P0, dP/du, dP/dv, face normal) and the candidate face count."""
    import cv2
    bm = bmesh.new()
    bm.from_mesh(o.data)
    tree = BVHTree.FromBMesh(bm)
    uvl = bm.loops.layers.uv[0]
    GS = 0.0005           # front-most depth on a 0.5 mm grid, min over 3 x 3 so a ray through a crack does not count
    gx = np.arange(XR[0] - 0.012, XR[1] + 0.012, GS)
    gz = np.arange(ZR[0] - 0.012, ZR[1] + 0.012, GS)
    yf = np.full((len(gz), len(gx)), 9.0, np.float32)
    for j, zz in enumerate(gz):
        for i, xx in enumerate(gx):
            hh = tree.ray_cast(Vector((xx, -2, zz)), Vector((0, 1, 0)))
            if hh[0] is not None:
                yf[j, i] = hh[0].y
    yf = cv2.erode(yf, np.ones((3, 3), np.uint8))
    best = np.full((h, w), -1e9, np.float32)
    tid = np.full((h, w), -1, np.int32)
    tris, ncand = [], 0
    for f in bm.faces:
        c = f.calc_center_median()
        cand = False
        if XR[0] - 0.01 < c.x < XR[1] + 0.01 and ZR[0] - 0.01 < c.z < ZR[1] + 0.01:
            cand = c.y < yf[int(round((c.z - gz[0]) / GS)), int(round((c.x - gx[0]) / GS))] + 0.002
        ncand += cand
        ls = list(f.loops)
        for k in range(1, len(ls) - 1):
            tri = (ls[0], ls[k], ls[k + 1])
            uv = np.array([[l_[uvl].uv.x * w - 0.5, l_[uvl].uv.y * h - 0.5] for l_ in tri])
            d = np.array([[uv[1, 0] - uv[0, 0], uv[2, 0] - uv[0, 0]], [uv[1, 1] - uv[0, 1], uv[2, 1] - uv[0, 1]]])
            if abs(np.linalg.det(d)) < 1e-9:
                continue
            di = np.linalg.inv(d)
            if cand:
                co = np.array([l_.vert.co[:] for l_ in tri])
                J = np.c_[co[1] - co[0], co[2] - co[0]] @ di
                ti = len(tris)
                tris.append(np.r_[uv[0], di.ravel(), co[0], J[:, 0], J[:, 1], np.array(f.normal[:])])
            else:
                ti = -2
            c0, c1 = max(int(math.floor(uv[:, 0].min() - 3)), 0), min(int(math.ceil(uv[:, 0].max() + 3)), w - 1)
            r0, r1 = max(int(math.floor(uv[:, 1].min() - 3)), 0), min(int(math.ceil(uv[:, 1].max() + 3)), h - 1)
            if c1 < c0 or r1 < r0:
                continue
            cc, rr = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
            px, py = cc - uv[0, 0], rr - uv[0, 1]
            b1 = di[0, 0] * px + di[0, 1] * py
            b2 = di[1, 0] * px + di[1, 1] * py
            g0 = math.hypot(di[0, 0] + di[1, 0], di[0, 1] + di[1, 1])
            sd = np.minimum(np.minimum((1 - b1 - b2) / g0, b1 / math.hypot(di[0, 0], di[0, 1])),
                            b2 / math.hypot(di[1, 0], di[1, 1]))          # signed distance to the triangle, texels
            sub = best[r0:r1 + 1, c0:c1 + 1]
            ok = (sd > sub) & (sd > -2.5)
            sub[ok] = sd[ok]
            tid[r0:r1 + 1, c0:c1 + 1][ok] = ti
    bm.free()
    return tid, np.array(tris), ncand


def subtitle_texels(V, P, XR, ZR, base_px, nrm_px, tid, tris, view):
    """Push the view-space repaint into the texels whose front-skin position is in SUB_BOX (arrays bottom-up)."""
    import cv2
    m, lay, clean, oldm, hole, L = view
    H, W = V.shape[:2]
    xc = (XR[0] + XR[1]) / 2
    rr, cc = np.nonzero(tid >= 0)
    T = tris[tid[rr, cc]]
    du, dv = cc - T[:, 0], rr - T[:, 1]
    pos = T[:, 6:9] + T[:, 9:12] * du[:, None] + T[:, 12:15] * dv[:, None]
    x, z = pos[:, 0], pos[:, 2]
    pad = 0.003
    inb = ((x > SUB_BOX['x'][0] - pad) & (x < SUB_BOX['x'][1] + pad) &
           (z > SUB_BOX['z'][0] - pad) & (z < SUB_BOX['z'][1] + pad))
    rr, cc, T, x, z = rr[inb], cc[inb], T[inb], x[inb], z[inb]
    nn = len(x)
    padn = -nn % 1024              # cv2.remap wants maps under 32767 per side
    vc = (x - xc) * P + W / 2 - 0.5
    vr = (ZR[1] - z) * P - 0.5

    def remap(img, mc, mr):
        mc = np.r_[mc, np.zeros(padn)].astype(np.float32).reshape(-1, 1024)
        mr = np.r_[mr, np.zeros(padn)].astype(np.float32).reshape(-1, 1024)
        o_ = cv2.remap(img, mc, mr, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return o_.reshape(-1, 1 if o_.ndim == 2 else o_.shape[2])[:nn]
    tpu = 1.0 / float(np.median(np.linalg.norm(T[:, 9:12], axis=1)))     # texels per unit here

    def samp(img, blur=False):
        if blur:
            img = cv2.GaussianBlur(img, (0, 0), 0.45 * P / tpu)
        return remap(img, vc, vr)

    def samp_fp(img, k=4):
        """Box filter over the texel's own parallelogram (the islands are sheared up to ~40 degrees)."""
        acc = 0
        for i in range(k):
            for j in range(k):
                p_ = T[:, 9:12] * ((i + 0.5) / k - 0.5) + T[:, 12:15] * ((j + 0.5) / k - 0.5)
                acc = acc + remap(img, vc + p_[:, 0] * P, vr - p_[:, 2] * P)
        return acc / (k * k)
    t0 = base_px[rr, cc, :3]
    om = samp(oldm, True)[:, 0]
    vb = samp(V)
    plain = (om < 1e-3) & (samp(hole.astype(np.float32), True)[:, 0] < 1e-3)
    off = np.median(t0[plain] - vb[plain], 0) if plain.any() else np.zeros(3, np.float32)
    bg = t0 * (1 - om[:, None]) + (samp(clean) + off) * om[:, None]
    new = subtitle_composite(bg, samp_fp(L['text'])[:, 0], samp_fp(L['lp'])[:, 0], samp(L['glow'], True),
                             samp(L['lp_rgb']), L['text_rgb'])
    changed = int((np.abs(new - t0).max(1) > 1 / 512).sum())
    base_px[rr, cc, :3] = new
    # normal map: replaced over the box (the old relief is offset from the old colour), the new elements embossed:
    # surface P + h N has normal N - grad h; written in each texel's own tangent frame (dP/du, dP/dv, N)
    hgt = cv2.GaussianBlur(np.maximum(L['text'], L['lp']), (0, 0), 0.6 * P / tpu)
    hx = cv2.Sobel(hgt, cv2.CV_32F, 1, 0, ksize=3) / 8 * P * SUB_RELIEF
    hz = -cv2.Sobel(hgt, cv2.CV_32F, 0, 1, ksize=3) / 8 * P * SUB_RELIEF
    N = T[:, 15:18] / np.linalg.norm(T[:, 15:18], axis=1, keepdims=True)
    n_obj = N.copy()
    n_obj[:, 0] -= samp(hx)[:, 0]
    n_obj[:, 2] -= samp(hz)[:, 0]
    n_obj /= np.linalg.norm(n_obj, axis=1, keepdims=True)
    Tu = T[:, 9:12] - N * (T[:, 9:12] * N).sum(1, keepdims=True)
    Tu /= np.linalg.norm(Tu, axis=1, keepdims=True)
    Bv = np.cross(N, Tu)
    Bv *= np.sign((Bv * T[:, 12:15]).sum(1, keepdims=True))
    new_n = np.c_[(n_obj * Tu).sum(1), (n_obj * Bv).sum(1), (n_obj * N).sum(1)] * 0.5 + 0.5
    front = N[:, 1] < -0.9
    new_n[~front] = (0.5, 0.5, 1.0)                    # folded slivers in the glass: flat
    nm = np.clip(np.minimum(np.minimum(x - SUB_BOX['x'][0], SUB_BOX['x'][1] - x),
                            np.minimum(z - SUB_BOX['z'][0], SUB_BOX['z'][1] - z)) / SUB_NRM_FEATHER, 0, 1)
    nm = nm * nm * (3 - 2 * nm)
    nm = np.where(front | (np.abs(x) < SUB_BOX['x'][1] - 0.004), nm, 0.0)     # tilted faces at the frame keep theirs
    nchanged = 0
    if nrm_px is not None:
        n0 = nrm_px[rr, cc, :3]
        nrm_px[rr, cc, :3] = n0 * (1 - nm[:, None]) + new_n * nm[:, None]
        nchanged = int((nm > 1e-3).sum())
    return {'view_to_texture_offset': [round(float(v), 4) for v in off], 'texels_per_unit': round(tpu, 1),
            'texels_in_box': nn, 'texels_changed': changed, 'normal_texels_replaced': nchanged}


def fix_front_subtitle(o, others):
    """Repaint the soft, smudged front subtitle (docstring, pass 3). Source units, after the side labels."""
    from PIL import Image
    sc = bpy.context.scene
    hidden = [(x, x.hide_render) for x in others]
    for x, _ in hidden:
        x.hide_render = True
    eng, vt = sc.render.engine, sc.view_settings.view_transform
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'FLAT'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = False
    sc.display.shading.show_shadows = False
    sc.view_settings.view_transform = 'Standard'
    sc.world = sc.world or bpy.data.worlds.new('w')
    sc.world.color = (1, 0, 1)
    P, XR, ZR = FRONT_PX_PER_UNIT, FRONT_VIEW['x'], FRONT_VIEW['z']
    W, H = int(round((XR[1] - XR[0]) * P)), int(round((ZR[1] - ZR[0]) * P))
    cd = bpy.data.cameras.new('front_cam')
    cd.type, cd.ortho_scale = 'ORTHO', W / P
    cam = bpy.data.objects.new('front_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = ((XR[0] + XR[1]) / 2, -2, (ZR[0] + ZR[1]) / 2)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.render.filepath = OUT + 'front_sub_before.png'
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cd)
    sc.render.engine, sc.view_settings.view_transform = eng, vt
    for x, hr in hidden:
        x.hide_render = hr
    V = np.asarray(Image.open(OUT + 'front_sub_before.png').convert('RGB')).astype(np.float32) / 255
    view = subtitle_view(V, P, XR, ZR)
    m, lay, clean, oldm, hole, L = view
    after = subtitle_composite(clean, L['text'], L['lp'], L['glow'], L['lp_rgb'], L['text_rgb'])
    Image.fromarray((after * 255 + 0.5).astype(np.uint8)).save(OUT + 'front_sub_after_view.png')
    Image.fromarray((np.dstack([oldm, L['text'], L['lp']]) * 255).astype(np.uint8)).save(OUT + 'front_sub_masks.png')
    mat = o.material_slots[0].material
    texs = [n_.image for n_ in mat.node_tree.nodes if n_.type == 'TEX_IMAGE' and n_.image]
    base = next(i for i in texs if i.name.endswith('_BaseColor'))
    nrmi = next((i for i in texs if i.name.endswith('_Normal')), None)
    w, h = base.size
    tid, tris, ncand = front_texel_map(o, w, h, XR, ZR)
    a = np.empty(w * h * 4, np.float32)
    base.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    b = None
    if nrmi is not None and tuple(nrmi.size) == (w, h):
        b = np.empty(w * h * 4, np.float32)
        nrmi.pixels.foreach_get(b)
        b = b.reshape(h, w, 4)
    rep = subtitle_texels(V, P, XR, ZR, a, b, tid, tris, view)
    base.pixels.foreach_set(a.ravel())
    base.update()
    if b is not None:
        nrmi.pixels.foreach_set(b.ravel())
        nrmi.update()

    def rnd(v):
        if isinstance(v, dict):
            return {k_: rnd(x_) for k_, x_ in v.items()}
        if isinstance(v, (list, tuple)):
            return [rnd(x_) for x_ in v]
        return round(float(v), 5) if isinstance(v, (float, np.floating)) else v
    rep.update({'measured_old': rnd(m), 'new_layout': rnd(lay), 'front_skin_faces': int(ncand),
                'texture_px': [w, h], 'box_yz': SUB_BOX, 'glow': SUB_GLOW, 'relief': SUB_RELIEF,
                'normal_replaced': b is not None,
                'files': {k_: OUT + 'front_sub_%s.png' % k_ for k_ in ('before', 'after_view', 'masks')}})
    return rep


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
rec = {'script': 'Scripts/Blender/AssembleLifeblood.py', 'date': '2026-10-31',
       'pass3': '2026-11-01: body textures at 4096, front subtitle repainted', 'parts': {}}
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
rec['parts']['SM_Lifeblood_Body']['front_subtitle'] = fix_front_subtitle(body, [o for o in objs.values() if o is not body])
print('FRONT_SUBTITLE', {k_: v for k_, v in rec['parts']['SM_Lifeblood_Body']['front_subtitle'].items()
                         if k_ not in ('measured_old', 'files')}, flush=True)
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
