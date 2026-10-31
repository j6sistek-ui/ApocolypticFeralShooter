"""RigEM_08.py - cut, rig, animate and export the EM_08 snub revolver (EM Apocalyptic Guns Vol 23).

Run (headless, idempotent, overwrites its own outputs only):
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python Scripts/Blender/RigEM_08.py

Do NOT call bpy.ops.wm.read_factory_settings() in this script: in Blender 5.2 it disables the
user's extensions and the extension wheel sync deletes their site-packages (PIL, cv2, ...).
The scene is cleared by hand instead.

Outputs (SourceAssets/EM_Apocalyptic_Guns/Rigged/EM_08/):
    SK_EM08.fbx, A_EM08_<Clip>.fbx, SK_EM08_rig.blend, proof_*.png, em08_rig.json
Conventions: Blender +X = muzzle = UE +X, Blender +Z = up, Blender -Y = gun's right = UE +Y.
1 Blender metre = 100 UU (FBX UnitScaleFactor 100, FBX_SCALE_NONE).

2026-10-30 design B4/B5/B6 (hand orientation + finger curl come from the rig):
  - grip_l and the hand_l_target rest moved to the NATIVE pistol aim pose's left palm offset (MEASURE report),
  - hand_l_target carries a ROTATION track (quaternion, delta from its identity rest, meaning "turn the left hand
    by this much from how the Pistol aim pose holds it at the support grip") and a SCALE X track (finger curl,
    1.0 = the aim pose's fingers, < 1 opens them, > 1 tightens), both identity / 1.0 at f0 and the last frame
    of every clip, keyed per beat in Reload only,
  - proofs draw the hand target as a PALM PROXY (orange plate in the palm plane, blue finger arrow, green palm
    normal stub, curl text) instead of a sphere.
"""
import bpy, bmesh, math, json, os, time
from mathutils import Vector, Matrix, Quaternion
from mathutils.kdtree import KDTree

T0 = time.time()
SRC = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\FBX\EM_Apocalyptic_Guns_FBX\EM_08_Apocalyptic_Guns\EM_08_Apocalyptic_Guns.fbx"
OUT = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\Rigged\EM_08"
FPS = 60
REPORT = {"gun": "EM_08", "source": SRC, "script": os.path.abspath(__file__) if "__file__" in dir() else "RigEM_08.py"}

def log(*a):
    print("EM08>", *a, flush=True)

# ---------------------------------------------------------------- geometry constants
# All in SOURCE coordinates (metres, after import + applied transforms, before the origin shift).
CYL_AXIS = (-0.0002, 0.1335)          # (y, z) of the cylinder axis (fitted from the outer shell)
CYL_R = 0.0243                         # cutter radius (shell radius ~0.0234 + bump margin)
CYL_X = (-0.0024, 0.0580)              # rear face ~-0.0022, front face ~0.0578
EJ_R, EJ_X = 0.0070, (0.0575, 0.0700)  # ejector stub coaxial with the cylinder, in front of it
CRANE_BOX = ((0.0630, 0.0790), (-0.0075, 0.0075), (0.1060, 0.1290))   # yoke post under the stub
HAMMER_BOX = ((-0.0900, -0.0665), (-0.0130, 0.0130), (0.1000, 0.1350))
TRIGGER_BOX = ((-0.0375, -0.0195), (-0.0100, 0.0100), (0.0700, 0.0970))

ORIGIN = Vector((-0.055, 0.0, 0.095))  # grip top: frame underside between backstrap and guard rear arm
CRANE_PIVOT = Vector((-0.0024, 0.0070, 0.1065))   # X-parallel hinge, left-low, at the yoke post foot
HAMMER_PIVOT = Vector((-0.0860, 0.0, 0.1000))     # rear-bottom of the hammer block
TRIGGER_PIVOT = Vector((-0.0300, 0.0, 0.0975))    # trigger root at the frame underside
CRANE_OPEN_DEG = -90.0                            # world rotation about +X (cylinder to gun's left, +Y)

# B4 (2026-10-30): grip_l AND the hand_l_target rest sit at the NATIVE Pistol aim pose's left palm offset from the
# seated grip_r (gun space X fwd, Y right, Z up), measured in a nullrhi PIE by Scripts/MeasureHandAxes.py
# (receipt D:/AFS_Comparisons/GunRigs_20261029/hand_axes.json, poses/pistol/t0/palm_l_minus_palm_r = mannequin
# (8.59, 2.0, -3.16) = gun (2.0, -8.59, -3.16) cm). Rounded to 0.5 cm and clamped to the gun's envelope (never
# more than 6 cm behind grip_r, never above it). With the rest AT the pose's own palm the support IK is a no-op at
# aim, so the left hand wraps the right hand the way the pose author made it instead of being pulled 5 cm into the
# frame (owner screenshot: left fingers through the frame above the trigger guard with the old (2.5, 0, -3.7)).
# If the MEASURE value were missing or implausible (> 12 cm from grip_r) the fallback (2.5, -1.0, -5.5) is used.
GRIP_L_OLD_UE_CM = (2.5, 0.0, -3.7)
MEASURE_PISTOL_PALM_UE_CM = (2.00, -8.59, -3.16)
GRIP_L_FALLBACK_UE_CM = (2.5, -1.0, -5.5)

def pick_grip_l():
    m = MEASURE_PISTOL_PALM_UE_CM
    if m is None or math.sqrt(sum(c * c for c in m)) > 12.0:
        return GRIP_L_FALLBACK_UE_CM, "FALLBACK: MEASURE pistol palm offset missing or > 12 cm from grip_r"
    r = [round(c * 2.0) / 2.0 for c in m]
    r[0] = max(r[0], -6.0)      # not more than 6 cm behind grip_r
    r[2] = min(r[2], 0.0)       # never above grip_r
    return tuple(r), "MEASURE pistol_native_palm_offset_gun_cm %s rounded to 0.5 cm" % (m,)

GRIP_L_UE_CM, GRIP_L_SOURCE = pick_grip_l()
# UE cm -> source metres: UE +Y (right) is Blender -Y
GRIP_L = ORIGIN + Vector((GRIP_L_UE_CM[0], -GRIP_L_UE_CM[1], GRIP_L_UE_CM[2])) * 0.01
log("grip_l UE cm", GRIP_L_UE_CM, "(was", GRIP_L_OLD_UE_CM, ")", GRIP_L_SOURCE)

# ---------------------------------------------------------------- scene utils
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                 bpy.data.armatures, bpy.data.actions, bpy.data.images):
        for d in list(coll):
            try:
                coll.remove(d)
            except Exception:
                pass
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0

def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj

def set_active(obj):
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        if o is not None and o != obj:
            o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

def mesh_islands(bm):
    bm.faces.ensure_lookup_table()
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, ids = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); ids.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index); stack.append(h)
        out.append(ids)
    out.sort(key=len, reverse=True)
    return out

def mesh_subset(me, face_ids, name):
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    keep = set(face_ids)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context='FACES')
    out = bpy.data.meshes.new(name); bm.to_mesh(out); bm.free()
    for m in me.materials:
        out.materials.append(m)
    return out

def merge_meshes(meshes, name):
    bm = bmesh.new()
    for m in meshes:
        bm.from_mesh(m)          # appends
    out = bpy.data.meshes.new(name); bm.to_mesh(out); bm.free()
    for m in meshes[0].materials:
        out.materials.append(m)
    return out

def bbox(me):
    xs = [v.co for v in me.vertices]
    return [min(c[i] for c in xs) for i in range(3)], [max(c[i] for c in xs) for i in range(3)]

def topo_stats(me):
    bm = bmesh.new(); bm.from_mesh(me)
    bd = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    nm = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    isl = mesh_islands(bm); bm.free()
    return {"faces": len(me.polygons), "verts": len(me.vertices), "boundary_edges": bd,
            "nonmanifold_edges": nm, "islands": len(isl)}

# ---------------------------------------------------------------- cutters
def inside_cyl(p, cy, cz, r, x0, x1):
    return x0 < p.x < x1 and math.hypot(p.y - cy, p.z - cz) < r

def inside_box(p, b):
    return b[0][0] < p.x < b[0][1] and b[1][0] < p.y < b[1][1] and b[2][0] < p.z < b[2][1]

def make_cutter(name, kind, params, cap_mat):
    bm = bmesh.new()
    if kind == 'cyl':
        (cy, cz), r, (x0, x1) = params
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=128, radius1=r, radius2=r, depth=x1 - x0)
        M = Matrix.Translation(((x0 + x1) / 2, cy, cz)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
    else:
        (x0, x1), (y0, y1), (z0, z1) = params
        bmesh.ops.create_cube(bm, size=1.0)
        M = Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)) @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1.0))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(cap_mat)
    return link(bpy.data.objects.new(name, me))

def boolean(me, cutter, op):
    tmp = link(bpy.data.objects.new("_bool_tmp", me))
    mod = tmp.modifiers.new("b", 'BOOLEAN')
    mod.operation = op
    mod.solver = 'EXACT'
    mod.object = cutter
    mod.material_mode = 'TRANSFER'
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    bpy.data.objects.remove(tmp, do_unlink=True)
    return out

# ---------------------------------------------------------------- phase 1: import + scale
clear_scene()
bpy.ops.import_scene.fbx(filepath=SRC)
src = [o for o in bpy.data.objects if o.type == 'MESH'][0]
src_dims_imported = list(src.dimensions)
REPORT["source_fbx_fps"] = bpy.context.scene.render.fps   # the importer sets the scene fps from the file (30)
bpy.context.scene.render.fps = FPS; bpy.context.scene.render.fps_base = 1.0
set_active(src)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
lo, hi = bbox(src.data)
L = hi[0] - lo[0]
scale = 1.0
if not (0.15 < L < 0.40):
    if 0.15 < L * 2.54 < 0.40:
        scale = 2.54
    elif 0.15 < L * 100 * 2.54 < 0.40:
        scale = 2.54 * 100
    src.data.transform(Matrix.Scale(scale, 4))
    lo, hi = bbox(src.data); L = hi[0] - lo[0]
REPORT["scale"] = {
    "fbx_unit_scale_factor_note": "source FBX UnitScaleFactor=1.0 (centimetres); Blender importer already yields metres",
    "imported_object_scale": 0.01, "imported_rotation_x_deg": 90.0,
    "extra_scale_factor_applied": scale,
    "x2.54_inch_hypothesis": "rejected: raw cm values give %.1f cm; x2.54 would give %.1f cm" % (L * 100, L * 254),
    "bounds_source_m": [lo, hi], "length_cm": round(L * 100, 2),
    "height_cm": round((hi[2] - lo[2]) * 100, 2), "width_cm": round((hi[1] - lo[1]) * 100, 2)}
log("length cm", L * 100, "scale", scale)
assert 0.20 < L < 0.31, "revolver length out of range"

# strip custom normals, add cap material slot
me0 = src.data
try:
    with bpy.context.temp_override(object=src, active_object=src, selected_objects=[src]):
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
except Exception as ex:
    log("custom normals clear skipped", ex)
gun_mat = me0.materials[0] if me0.materials else bpy.data.materials.new("EM_08_Apocalyptic_Guns")
gun_mat.name = "M_EM08_Neutral"
gun_mat.diffuse_color = (0.55, 0.55, 0.56, 1.0)
cap_mat = bpy.data.materials.new("_EM08_CapTmp")
me0.materials.clear(); me0.materials.append(gun_mat); me0.materials.append(cap_mat)
for p in me0.polygons:
    p.material_index = 0

src_topo = topo_stats(me0)
REPORT["source_topology"] = src_topo
REPORT["cut_case"] = ("island" if src_topo["islands"] > 1 else "shared") + \
    " -> boolean (mesh is ONE watertight manifold island; cylinder/hammer/trigger are fused to the frame, " \
    "so bounding-volume selection + separate would leave open holes; EXACT boolean cutters cut and cap both sides)"
log("source topo", src_topo)

# UV reference for caps: face centre -> (uv centroid, texel density)
bm_ref = bmesh.new(); bm_ref.from_mesh(me0); bm_ref.faces.ensure_lookup_table()
uvl = bm_ref.loops.layers.uv.active
ref_kd = KDTree(len(bm_ref.faces)); ref_info = []
for f in bm_ref.faces:
    ref_kd.insert(f.calc_center_median(), f.index)
    uvs = [l[uvl].uv.copy() for l in f.loops]
    uvc = sum(uvs, Vector((0, 0))) / len(uvs)
    a3 = max(f.calc_area(), 1e-12)
    a2 = 0.0
    for i in range(1, len(uvs) - 1):
        a2 += abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) / 2
    ref_info.append((uvc, math.sqrt(max(a2, 1e-14) / a3)))
ref_kd.balance()
REF_FACES = len(bm_ref.faces)

# ---------------------------------------------------------------- phase 2: sequential boolean cuts
CUTS = [
    ("cylinder", 'cyl', (CYL_AXIS, CYL_R, CYL_X)),
    ("ejector_rod", 'cyl', (CYL_AXIS, EJ_R, EJ_X)),
    ("crane", 'box', CRANE_BOX),
    ("hammer", 'box', HAMMER_BOX),
    ("trigger", 'box', TRIGGER_BOX),
]

def inside_fn(kind, params):
    if kind == 'cyl':
        (cy, cz), r, (x0, x1) = params
        return lambda p: inside_cyl(p, cy, cz, r, x0, x1)
    return lambda p: inside_box(p, params)

frame_me = me0.copy(); frame_me.name = "frame_work"
parts = {}
returned_centres = []   # (part, centre) of stray frame bits that fell inside a cutter and were given back
returned_meshes = []
cut_report = {}
for name, kind, params in CUTS:
    ins = inside_fn(kind, params)
    full = sum(1 for f in bm_ref.faces if all(ins(v.co) for v in f.verts))
    strad = sum(1 for f in bm_ref.faces if any(ins(v.co) for v in f.verts) and not all(ins(v.co) for v in f.verts))
    cutter = make_cutter("_cut_" + name, kind, params, cap_mat)
    part_me = boolean(frame_me, cutter, 'INTERSECT')
    rest_me = boolean(frame_me, cutter, 'DIFFERENCE')
    claimed = 0
    for k, rm in enumerate(list(returned_meshes)):
        got = boolean(rm, cutter, 'INTERSECT')
        if len(got.polygons):
            claimed += len(got.polygons)
            part_me = merge_meshes([part_me, got], name)
            returned_meshes[k] = boolean(rm, cutter, 'DIFFERENCE')
    bpy.data.objects.remove(cutter, do_unlink=True)
    # keep the largest island as the part, give stray islands (bits of frame inside the cutter) back
    bm = bmesh.new(); bm.from_mesh(part_me); isl = mesh_islands(bm); bm.free()
    returned = [len(i) for i in isl[1:]]
    keep = mesh_subset(part_me, isl[0], name)
    if len(isl) > 1:
        bmp = bmesh.new(); bmp.from_mesh(part_me); bmp.faces.ensure_lookup_table()
        for s_ in isl[1:]:
            cs_ = [bmp.faces[i].calc_center_median() for i in s_]
            returned_centres.append((name, sum(cs_, Vector()) / len(cs_)))
        bmp.free()
        # kept as separate meshes (merging coincident caps back into the frame breaks the exact solver);
        # later cutters still get to claim them below
        returned_meshes.append(mesh_subset(part_me, [i for s in isl[1:] for i in s], name + "_back"))
    frame_me = rest_me
    parts[name] = keep
    cut_report[name] = {"cutter": {"kind": kind, "params_source_m": params}, "topology_after_boolean": topo_stats(keep),
                        "orig_faces_fully_inside_moved": full, "orig_faces_straddling_cut": strad,
                        "part_islands_after_boolean": len(isl), "stray_islands_returned_to_frame_faces": returned,
                        "faces_claimed_from_earlier_returned_bits": claimed}
    log("cut", name, "full", full, "straddle", strad, "islands", len(isl), "returned", returned)

# frame slivers: small frame islands hugging a part go to that part
bm = bmesh.new(); bm.from_mesh(frame_me); bm.faces.ensure_lookup_table()
isl = mesh_islands(bm)
frame_keep = list(isl[0]); sliver_log = []
for s in isl[1:]:
    cs = [bm.faces[i].calc_center_median() for i in s]
    c = sum(cs, Vector()) / len(cs)
    target = None
    was_returned = [n for n, rc in returned_centres if (rc - c).length < 0.0015]
    for name, kind, params in CUTS:
        if name in was_returned:
            continue
        if kind == 'cyl':
            (cy, cz), r, (x0, x1) = params
            if x0 - 0.0015 < c.x < x1 + 0.0015 and math.hypot(c.y - cy, c.z - cz) < r + 0.0025:
                target = name
        else:
            (x0, x1), (y0, y1), (z0, z1) = params
            if x0 - .0015 < c.x < x1 + .0015 and y0 - .0015 < c.y < y1 + .0015 and z0 - .0015 < c.z < z1 + .0015:
                target = name
        if target:
            break
    if target and len(s) < 400:
        parts[target] = merge_meshes([parts[target], mesh_subset(frame_me, s, "sl")], target)
        sliver_log.append({"faces": len(s), "to": target, "centre": list(c)})
    else:
        frame_keep += s
        sliver_log.append({"faces": len(s), "to": "body(kept)", "centre": list(c), "was_returned_from": was_returned})
bm.free()
frame_me = mesh_subset(frame_me, frame_keep, "body")
REPORT["body_topology_after_boolean"] = topo_stats(frame_me)
REPORT["returned_island_centres"] = [(n, list(c)) for n, c in returned_centres]
returned_meshes = [m for m in returned_meshes if len(m.polygons)]
if returned_meshes:
    frame_me = merge_meshes([frame_me] + returned_meshes, "body")
parts = {"body": frame_me, **parts}
REPORT["frame_sliver_islands"] = sliver_log
log("slivers", sliver_log)

# ---------------------------------------------------------------- phase 3: cap UVs, triangulate ngons, normals
def finish_part(me):
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.get("map1") or bm.loops.layers.uv.active or bm.loops.layers.uv.new("map1")
    caps = set(f.index for f in bm.faces if f.material_index == 1)
    seen = set(); n_isl = 0
    for fi in caps:
        if fi in seen:
            continue
        stack, ids = [bm.faces[fi]], []
        seen.add(fi)
        while stack:
            g = stack.pop(); ids.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index in caps and h.index not in seen:
                        seen.add(h.index); stack.append(h)
        n_isl += 1
        c = sum((f.calc_center_median() for f in ids), Vector()) / len(ids)
        n = sum((f.normal * f.calc_area() for f in ids), Vector())
        if n.length < 1e-9:
            n = Vector((1, 0, 0))
        n.normalize()
        ax = max(range(3), key=lambda i: abs(n[i]))
        ua, va = [(1, 2), (0, 2), (0, 1)][ax]
        _, ri, _ = ref_kd.find(c)
        uvc, dens = ref_info[ri]
        for f in ids:
            f.material_index = 0
            for l in f.loops:
                d = l.vert.co - c
                l[uv].uv = (uvc.x + dens * d[ua], uvc.y + dens * d[va])
    open_edges = [e for e in bm.edges if len(e.link_faces) < 2]
    filled = 0
    if open_edges:   # sub-millimetre slits the exact solver leaves at cutter corners
        filled = len(bmesh.ops.holes_fill(bm, edges=open_edges, sides=0)["faces"])
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bm.to_mesh(me); bm.free()
    while len(me.materials) > 1:
        me.materials.pop(index=len(me.materials) - 1)
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(35))
    except Exception as ex:
        log("sharp from angle skipped", ex)
    return {"cap_faces": len(caps), "cap_islands": n_isl, "ngons_triangulated": len(ngons),
            "open_edges_filled": len(open_edges), "fill_faces": filled}

for name, me in parts.items():
    info = finish_part(me)
    info.update(topo_stats(me))
    cut_report.setdefault(name, {}).update({"final": info})
    log("part", name, info)
REPORT["cuts"] = cut_report

# ---------------------------------------------------------------- phase 4: join with vertex groups, origin shift
bm = bmesh.new(); ranges = {}
for name, me in parts.items():
    v0 = len(bm.verts)
    bm.from_mesh(me)
    ranges[name] = (v0, len(bm.verts))
bm.verts.ensure_lookup_table()
bmesh.ops.translate(bm, vec=-ORIGIN, verts=bm.verts)
sk_me = bpy.data.meshes.new("SK_EM08"); bm.to_mesh(sk_me); bm.free()
sk_me.materials.append(gun_mat)
sk = link(bpy.data.objects.new("SK_EM08", sk_me))
for name, (a, b) in ranges.items():
    vg = sk.vertex_groups.new(name=name)
    vg.add(list(range(a, b)), 1.0, 'REPLACE')
for p in sk_me.polygons:
    p.use_smooth = True
try:
    sk_me.set_sharp_from_angle(angle=math.radians(35))
except Exception:
    pass
for o in [src]:
    bpy.data.objects.remove(o, do_unlink=True)
REPORT["vertex_counts"] = {k: b - a for k, (a, b) in ranges.items()}

def S(v):
    """source coords -> rig coords (origin at grip_r)"""
    return Vector(v) - ORIGIN

# ---------------------------------------------------------------- phase 5: armature
lo, hi = bbox(sk_me)
# muzzle: front of the top barrel (bore ring sits ~13 mm above the cylinder axis)
bar = [v.co for v in sk_me.vertices if abs(v.co.y) < 0.01 and S((0, 0, 0.141)).z < v.co.z < S((0, 0, 0.156)).z]
mx = max(c.x for c in bar)
ring = [c for c in bar if c.x > mx - 0.003]
muzzle = Vector((mx, 0.0, (min(c.z for c in ring) + max(c.z for c in ring)) / 2))
zmax = hi[2]
sight = Vector((S((-0.006, 0, 0)).x, 0.0, zmax))
cyl_rear = S((CYL_X[0], CYL_AXIS[0], CYL_AXIS[1]))
Rcr = Matrix.Translation(S(CRANE_PIVOT)) @ Matrix.Rotation(math.radians(CRANE_OPEN_DEG), 4, 'X') @ Matrix.Translation(-S(CRANE_PIVOT))
eject_open = Rcr @ cyl_rear

BONES = [  # name, parent, head(rig coords), length, deform
    ("root", None, Vector((0, 0, 0)), 0.05, False),
    ("body", "root", Vector((0, 0, 0)), 0.05, True),
    ("crane", "body", S(CRANE_PIVOT), 0.03, True),
    ("cylinder", "crane", S((CYL_X[0], CYL_AXIS[0], CYL_AXIS[1])), CYL_X[1] - CYL_X[0], True),
    ("ejector_rod", "cylinder", S((CYL_X[1], CYL_AXIS[0], CYL_AXIS[1])), 0.012, True),
    ("hammer", "body", S(HAMMER_PIVOT), 0.02, True),
    ("trigger", "body", S(TRIGGER_PIVOT), 0.02, True),
    ("muzzle", "body", muzzle, 0.02, False),
    ("ejection_port", "body", eject_open, 0.02, False),
    ("sight", "body", sight, 0.02, False),
    ("grip_r", "root", Vector((0, 0, 0)), 0.02, False),
    ("grip_l", "body", S(GRIP_L), 0.02, False),
    ("mag_well", "cylinder", cyl_rear + Vector((-0.01, 0, 0)), 0.02, False),
    # left-hand IK target (palm centre), non-deforming; rests at grip_l so the support hand sits at the
    # support grip outside reloads. Keyed in Reload only (design 2026-10-30, items 2-3).
    ("hand_l_target", "body", S(GRIP_L), 0.02, False),
]
arm_data = bpy.data.armatures.new("EM_08_Skeleton")
arm = link(bpy.data.objects.new("Armature", arm_data))   # 'Armature' = UE drops it instead of adding a root bone
set_active(arm)
bpy.ops.object.mode_set(mode='EDIT')
for name, parent, head, ln, deform in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head = head
    # M4A1 convention (RigM4A1.py, UE 5.8 verified): a Blender bone along +Y with roll 0 has the
    # identity rest matrix -> identity bone orientation in UE component space (X fwd, Y right, Z up).
    # ejection_port points Blender +X, so its UE bone X points to the gun's right.
    eb.tail = head + (Vector((ln, 0, 0)) if name == "ejection_port" else Vector((0, ln, 0)))
    eb.roll = 0.0
    eb.use_deform = deform
    if parent:
        eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')
sk.parent = arm
mod = sk.modifiers.new("Armature", 'ARMATURE'); mod.object = arm
for pb in arm.pose.bones:
    pb.rotation_mode = 'XYZ'
HAND_BONE = "hand_l_target"
arm.pose.bones[HAND_BONE].rotation_mode = 'QUATERNION'   # B5: quaternion keys, shortest path enforced in finalize_action

def ue_cm(v):
    return [round(v.x * 100, 3), round(-v.y * 100, 3), round(v.z * 100, 3)]

# ---------------------------------------------------------------- Blender armature space <-> UE gun space (B5)
# Positions: UE (x, y, z) = Blender (x, -y, z), i.e. the mirror M = diag(1, -1, 1) (Blender -Y = UE +Y right).
# Rotations: a bone's local matrix is exported RAW (primary_bone_axis Y / secondary X = no bone correction in the
# Blender exporter, rest matrices are identity), so UE sees R_ue = M R_bl M^-1 = M R_bl M. A mirror conjugation
# keeps the rotation angle's magnitude, mirrors the axis and flips the sense (det M = -1):
#     Blender (axis a, angle t)  <->  UE (axis M a, angle -t)
# so  UE +t about X == Blender -t about X, UE +t about Z == Blender -t about Z, and UE +t about Y == Blender +t
# about Y (the Y axis itself is mirrored, so the two flips cancel). In quaternion terms (w, x, y, z) -> (w, -x, y, -z),
# an involution. rot_roundtrip_check() below proves it numerically on test vectors before any key is written.
def bl_vec(v_ue):
    return Vector((v_ue[0], -v_ue[1], v_ue[2]))

def ue_vec(v_bl):
    return Vector((v_bl[0], -v_bl[1], v_bl[2]))

def ue_quat_to_bl(q):
    return Quaternion((q.w, -q.x, q.y, -q.z))

bl_quat_to_ue = ue_quat_to_bl

def axis_angle_deg(q):
    q = q.normalized()
    if q.w < 0:          # report the representative with the angle in (0, 180]
        q = -q
    ang = math.degrees(q.angle)
    ax = q.axis if ang > 1e-5 else Vector((0, 0, 0))
    return [round(c, 4) for c in ax], round(ang, 3)

def rot_roundtrip_check():
    """M (R_bl v) == R_ue (M v) for every test vector and rotation, plus the three axis sign facts."""
    tests = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((0.3, -0.7, 0.65)), Vector((-0.8, 0.2, -0.5))]
    rots = [((1, 0, 0), 30.0), ((0, 1, 0), 45.0), ((0, 0, 1), -60.0), ((1, 1, 1), 120.0), ((0.2, -0.9, 0.4), 77.0),
            ((-0.5, 0.3, 0.8), -140.0)]
    worst = 0.0
    for ax, deg in rots:
        q_ue = Quaternion(Vector(ax).normalized(), math.radians(deg))
        q_bl = ue_quat_to_bl(q_ue)
        back = bl_quat_to_ue(q_bl)
        assert (back.inverted() @ q_ue).angle < 1e-9 or abs((back.inverted() @ q_ue).angle - 2 * math.pi) < 1e-9
        for v in tests:
            a = ue_vec(q_bl @ bl_vec(v))      # rotate in Blender space, read in UE
            b = q_ue @ v                      # rotate in UE space directly
            worst = max(worst, (a - b).length)
        # the matrix statement of the same thing: R_ue == M R_bl M
        Mm = Matrix.Diagonal((1, -1, 1))
        Rm = Mm @ q_bl.to_matrix() @ Mm
        worst = max(worst, max(abs(Rm[i][j] - q_ue.to_matrix()[i][j]) for i in range(3) for j in range(3)))
    assert worst < 1e-6, "Blender<->UE rotation conversion round trip failed: %.3e" % worst
    # sign facts, each read back as axis-angle in Blender space
    facts = {}
    for name, ax in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
        q_bl = ue_quat_to_bl(Quaternion(Vector(ax), math.radians(10.0)))
        a, d = axis_angle_deg(q_bl)
        signed = d * (1 if Vector(a).dot(Vector(ax)) > 0 else -1)
        facts[name] = round(signed, 3)
    assert facts == {"X": -10.0, "Y": 10.0, "Z": -10.0}, facts
    return {"worst_vector_error": worst, "ue_plus10deg_about_axis_equals_blender_deg_about_same_axis": facts,
            "quaternion_map": "(w, x, y, z)_ue <-> (w, -x, y, -z)_bl", "matrix_map": "R_ue = M R_bl M, M = diag(1,-1,1)"}

REPORT["rotation_convention"] = rot_roundtrip_check()
log("rotation convention verified", REPORT["rotation_convention"])

# ---- left-hand rest orientation (Pistol aim pose, MEASURE report 2026-10-30, gun space unit vectors):
# hand_l local +X points along the fingers, local -Y out of the PALM. At aim the palm faces the gun's right (+Y),
# wrapping the right hand, fingers forward leaning right and up.
REST_FINGER_UE = Vector((0.899, 0.34, 0.275)).normalized()
REST_PALM_UE = Vector((-0.396, 0.9, 0.184))
REST_PALM_UE = (REST_PALM_UE - REST_PALM_UE.dot(REST_FINGER_UE) * REST_FINGER_UE).normalized()

def hand_frame(finger, normal):
    """orthonormal 3x3 with columns (fingers, palm normal, side = fingers x normal); a proper rotation."""
    n = Vector(normal).normalized()
    f = Vector(finger); f = (f - f.dot(n) * n).normalized()
    s = f.cross(n)
    return Matrix((f, n, s)).transposed(), f, n

REST_FRAME_UE, _, _ = hand_frame(REST_FINGER_UE, REST_PALM_UE)

# Per-beat target orientation of the left hand in UE gun space (palm normal = where the palm faces, fingers = the
# direction the (straight) fingers would point) and the finger curl (bone scale X; 1.0 = aim-pose fingers).
# The delta D keyed on hand_l_target is the rotation taking the REST frame onto the TARGET frame (D = T R^-1), so
# the C++ side (FHoverSupportHandNode) can apply it to the aim pose's hand without knowing either frame.
#   cup:    palm up-right under the OPEN cylinder (it hangs 3.4 cm left of the bore, the palm sits 2.7 cm radially
#           out at left-low): normal +Z leaning +Y so the plate is tangent to the cylinder's surface, fingers
#           forward (+X) rising to wrap around it; curl 0.9 (slightly open around a 4.7 cm drum).
#   belt:   speedloader pouch, low and left: palm up leaning inward (+Y, toward the body), fingers forward, curl 0.8.
#   grab:   first touch at f15, 3.5 cm left of the mid-swing cylinder at axis height: the cup normal would put the
#           palm plane 2.1 cm from the axis (inside the 2.3 cm drum; the first proxy render showed the plate cutting
#           the cylinder), so the palm faces right-and-up 45/45 here (plane 2.5 cm out) and rolls 8 deg to the
#           cup by f18; curl 0.9.
#   loader: speedloader knob at the open cylinder's rear, 4.5 cm behind its rear face at axis height: palm up
#           leaning forward (toward the cylinder it pushes the loader into) and a little right, fingers forward-DOWN
#           so the palm's front edge dips under the drum (a palm-up/fingers-forward plate cut 0.8 cm into the
#           cylinder's lower half and 0.4 cm into the frame's left face in the first render; this one clears the
#           drum by 1.7 cm and overlaps the frame by 3 mm at one corner only); curl 1.0 (closed on the knob).
#   close:  same cup orientation riding the cylinder in, curl 0.7 (hand relaxes as the cylinder slides out of it).
BEATS = {
    "rest":   dict(n=REST_PALM_UE, f=REST_FINGER_UE, curl=1.0),
    "grab":   dict(n=(0.0, 0.72, 0.69), f=(0.8, -0.36, 0.27), curl=0.9),
    "cup":    dict(n=(0.0, 0.6, 0.8), f=(0.8, -0.36, 0.27), curl=0.9),
    "belt":   dict(n=(0.0, 0.5, 0.866), f=(0.9, 0.2, -0.115), curl=0.8),
    "loader": dict(n=(0.55, 0.35, 0.76), f=(0.8, 0.0, -0.6), curl=1.0),
    "close":  dict(n=(0.0, 0.6, 0.8), f=(0.8, -0.36, 0.27), curl=0.7),
}
BEAT_Q = {}     # name -> (q_ue delta, finger_ue, normal_ue)
for _name, _b in BEATS.items():
    T, f_, n_ = hand_frame(_b["f"], _b["n"])
    D = T @ REST_FRAME_UE.transposed()
    BEAT_Q[_name] = (D.to_quaternion().normalized(), f_, n_)
    chk_f = BEAT_Q[_name][0] @ REST_FINGER_UE; chk_n = BEAT_Q[_name][0] @ REST_PALM_UE
    assert (chk_f - f_).length < 1e-6 and (chk_n - n_).length < 1e-6, "beat frame %s is not a rotation of the rest" % _name
REPORT["hand_beats_ue"] = {k: {"palm_normal_gun": [round(c, 4) for c in v[2]], "finger_dir_gun": [round(c, 4) for c in v[1]],
                               "delta_axis_gun": axis_angle_deg(v[0])[0], "delta_deg": axis_angle_deg(v[0])[1],
                               "curl": BEATS[k]["curl"]} for k, v in BEAT_Q.items()}
for k, v in REPORT["hand_beats_ue"].items():
    log("beat", k, v)

REPORT["bones"] = [{"name": n, "parent": p, "head_blender_m": [round(c, 5) for c in h], "head_ue_cm": ue_cm(h),
                    "axis": "identity (Blender bone +Y, roll 0) -> UE bone X fwd/Y right/Z up" if n != "ejection_port" else "Blender +X -> UE bone X = gun right",
                    "deform": d} for n, p, h, ln, d in BONES]
REPORT["sockets"] = {n: {"parent": p, "ue_cm": ue_cm(h)} for n, p, h, ln, d in BONES
                     if n in ("muzzle", "ejection_port", "sight", "grip_r", "grip_l", "mag_well", "hand_l_target")}

# ---------------------------------------------------------------- phase 6: actions
# Animated bones have identity rest matrices, so pose space = world axes:
#   world rot about +X -> rotation_euler.x, about +Y -> rotation_euler.y, move along +X -> location.x
def fcurves_of(obj):
    act = obj.animation_data.action
    try:
        return list(act.fcurves)
    except AttributeError:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, obj.animation_data.action_slot)
        return list(cb.fcurves) if cb else []

def new_action(name, f0, f1):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = f0, f1
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    return act

def reset_pose():
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)

SNAPS = []   # (bone, frame, interpolation, easing)
def key(bone, f, worldY=None, worldX=None, moveX=None, loc=None, interp=None, easing='AUTO', rot_q=None, curl=None):
    """loc: full pose-space location (Blender m, bone rest frame = armature axes); overrides moveX.
    rot_q / curl: for the quaternion-mode hand target only: pose-space (= armature-space, identity rest) rotation
    and bone scale X (finger curl). Both default to identity / 1.0 so every hand key carries all three channels."""
    pb = arm.pose.bones[bone]
    r = Vector((0, 0, 0)); l = Vector((0, 0, 0))
    if worldY is not None:
        r.y = math.radians(worldY)
    if worldX is not None:
        r.x = math.radians(worldX)
    if moveX is not None:
        l.x = moveX
    if loc is not None:
        l = Vector(loc)
    pb.location = l
    if pb.rotation_mode == 'QUATERNION':
        pb.rotation_quaternion = Quaternion(rot_q).normalized() if rot_q is not None else Quaternion((1, 0, 0, 0))
        pb.scale = (float(curl) if curl is not None else 1.0, 1.0, 1.0)
        pb.keyframe_insert("rotation_quaternion", frame=f, group=bone)
        pb.keyframe_insert("scale", frame=f, group=bone)
    else:
        pb.rotation_euler = r
        pb.keyframe_insert("rotation_euler", frame=f, group=bone)
    pb.keyframe_insert("location", frame=f, group=bone)
    if interp:
        SNAPS.append((bone, f, interp, easing))

def ensure_shortest_quat_paths(fcs):
    """Flip whole quaternion keys into the hemisphere of the previous key (q and -q are the same rotation) so the
    per-component Bezier never swings the long way round between two beats (B5: every consecutive delta < 150 deg).
    Runs before the handle types are set, so the auto handles are rebuilt from the flipped values."""
    flipped = 0
    for path in sorted({fc.data_path for fc in fcs if fc.data_path.endswith("rotation_quaternion")}):
        comps = sorted([fc for fc in fcs if fc.data_path == path], key=lambda fc: fc.array_index)
        if len(comps) != 4:
            continue
        prev = None
        for i in range(len(comps[0].keyframe_points)):
            q = Vector([c.keyframe_points[i].co.y for c in comps])
            if prev is not None and q.dot(prev) < 0.0:
                for c in comps:
                    kp = c.keyframe_points[i]
                    kp.co.y = -kp.co.y; kp.handle_left.y = -kp.handle_left.y; kp.handle_right.y = -kp.handle_right.y
                q = -q; flipped += 1
            prev = q
    return flipped

def finalize_action():
    """Bezier auto-clamped everywhere, then the recorded snaps. Re-callable: SNAPS is cleared by clip()."""
    fcs = fcurves_of(arm)
    ensure_shortest_quat_paths(fcs)
    for fc in fcs:
        bone = fc.data_path.split('"')[1]
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
            for b, f, it, ea in SNAPS:
                if b == bone and abs(kp.co.x - f) < 1e-4:
                    kp.interpolation = it
                    kp.easing = ea
        fc.update()

# bones keyed at the first and last frame of every clip (the exporter bakes ALL bones anyway:
# bake_anim_use_all_bones=True, use_armature_deform_only=False, so the socket bones get tracks too)
MOVING_BONES = ("root", "body", "crane", "cylinder", "ejector_rod", "hammer", "trigger")
HAND_CLIPS = ("A_EM08_Reload",)      # the hand target MOVES only here (identity / grip_l / curl 1.0 everywhere else)

CLIPS = {}
def clip(name, f0, f1, build):
    act = new_action(name, f0, f1)
    for b in MOVING_BONES:
        key(b, f0); key(b, f1)
    # hand target: location + rotation + scale keyed identity / grip_l / 1.0 at both ends of EVERY clip (B5), so the
    # baked tracks start and end on the rest and static clips change nothing
    key(HAND_BONE, f0); key(HAND_BONE, f1)
    build()
    finalize_action()
    SNAPS.clear()
    CLIPS[name] = {"frames": [f0, f1], "seconds": round((f1 - f0) / FPS, 4), "action": act}

# ---- left-hand target choreography (gun space: X fwd, UE Y right = Blender -Y, Z up; Blender metres here)
HAND_REST = S(GRIP_L)                        # rest head = grip_l; pose location 0 == support grip
CUP_OFF = Vector((0.03, 0.025, -0.01))      # UE (3, -2.5, -1) cm: palm cups the cylinder's left face, slightly low
GRAB_OFF = Vector((0.03, 0.035, 0.0))       # UE (3, -3.5, 0) cm: first touch on the left face
BELT = Vector((0.04, 0.10, -0.36))          # UE (4, -10, -36) cm from grip_r: speedloader pouch, low and LEFT of the gun
LOADER_OFF = Vector((-0.035, 0.010, 0.0))   # UE (-3.5, -1, 0) cm behind/left of mag_well: palm holds the speedloader knob
HAND_KEYS = []                              # (frame, beat, world position, pose name) for the JSON and the proofs

def sample(bone, f):
    """armature-space head of a bone at frame f, from the keyed action (call after finalize_action)."""
    bpy.context.scene.frame_set(f)
    return arm.pose.bones[bone].matrix.translation.copy()

def hand_key(f, world_pos, beat, interp=None, easing='AUTO', pose="rest"):
    """key hand_l_target so its head lands at world_pos (armature space) at frame f, accounting for the
    parent body's pose (lock jolt): head = Body @ (rest + loc)  ->  loc = Body^-1 @ pos - rest.
    B5: the same frame's ROTATION is BEATS[pose]'s delta (UE gun space -> Blender armature space via
    ue_quat_to_bl), also compensated for the body's pose so the bone's ARMATURE-space rotation (= the socket's
    component-space rotation UE reads, which includes body) is exactly the designed delta; SCALE X = curl."""
    bpy.context.scene.frame_set(f)
    B = arm.pose.bones["body"].matrix.copy()
    loc = B.inverted() @ Vector(world_pos) - HAND_REST
    q_ue = BEAT_Q[pose][0]
    q_local = B.to_quaternion().inverted() @ ue_quat_to_bl(q_ue)
    key(HAND_BONE, f, loc=loc, interp=interp, easing=easing, rot_q=q_local, curl=BEATS[pose]["curl"])
    HAND_KEYS.append((f, beat, Vector(world_pos), pose))

def b_idle():
    pass

def b_fire():
    # double action: hammer cocks 30 deg over 2 frames, falls in 1; cylinder indexes 60 deg during the cock
    key("hammer", 0, worldY=0, interp='QUAD', easing='EASE_OUT')
    key("hammer", 2, worldY=-30, interp='LINEAR')
    key("hammer", 3, worldY=0)
    key("cylinder", 0, worldX=0, interp='SINE', easing='EASE_IN_OUT')
    key("cylinder", 2, worldX=-60)
    key("cylinder", 7, worldX=-60)
    key("trigger", 0, worldY=0, interp='QUAD', easing='EASE_OUT')
    key("trigger", 2, worldY=10); key("trigger", 3, worldY=10, interp='SINE', easing='EASE_IN_OUT')
    key("trigger", 7, worldY=0)
    # recoil on body (muzzle flip + 4 mm kick), snap in, ease out
    key("body", 3, worldY=0, moveX=0, interp='LINEAR')
    key("body", 4, worldY=-3.0, moveX=-0.004, interp='SINE', easing='EASE_OUT')
    key("body", 7, worldY=0, moveX=0)

def b_dryfire():
    key("hammer", 0, worldY=0, interp='QUAD', easing='EASE_OUT')
    key("hammer", 4, worldY=-30, interp='LINEAR')
    key("hammer", 5, worldY=0)
    key("cylinder", 0, worldX=0, interp='SINE', easing='EASE_IN_OUT')
    key("cylinder", 4, worldX=-60); key("cylinder", 12, worldX=-60)
    key("trigger", 0, worldY=0, interp='QUAD', easing='EASE_OUT')
    key("trigger", 4, worldY=10); key("trigger", 6, worldY=10)
    key("trigger", 12, worldY=0)

def b_reload():
    # 0-18 swing out (0.3 s) with a 3 deg overshoot, settle by 22
    key("crane", 0, worldX=0, interp='SINE', easing='EASE_IN_OUT')
    key("crane", 18, worldX=CRANE_OPEN_DEG - 3)
    key("crane", 22, worldX=CRANE_OPEN_DEG)
    # cylinder stays out until the speedloader beat (hand at mag_well f125), then swings in 128-138
    # (was 96-108 before the hand choreography: the loader has to meet an OPEN cylinder)
    key("crane", 128, worldX=CRANE_OPEN_DEG, interp='QUAD', easing='EASE_IN')   # accelerate into the frame
    key("crane", 138, worldX=0)
    key("crane", 144, worldX=0)
    # ejector punch 2 cm rearward and back
    key("ejector_rod", 22, moveX=0, interp='QUAD', easing='EASE_IN')
    key("ejector_rod", 28, moveX=-0.02)
    key("ejector_rod", 32, moveX=-0.02)
    key("ejector_rod", 44, moveX=0)
    # 44-90 hand cups the open cylinder; 90-125 speedloader fetch; 128-138 swing in; lock snap at 138
    key("cylinder", 138, worldX=0, interp='LINEAR')
    key("cylinder", 140, worldX=-4)     # bolt catches the cylinder notch
    key("cylinder", 142, worldX=0)
    key("body", 138, worldX=0, interp='LINEAR')
    key("body", 140, worldX=1.5)        # small lock jolt
    key("body", 144, worldX=0)
    key("hammer", 60, worldY=0); key("trigger", 60, worldY=0)
    # ---- left hand (palm centre). Apply the gun's interpolation first so the sampled cylinder is exact.
    finalize_action()
    # rotation (delta from the aim-pose hand) and curl ride the same keys as the positions (B5): identity / 1.0 at
    # both ends, cup orientation from the grab on, belt / loader beats, cup again while the cylinder closes
    hand_key(0, HAND_REST, "grip_l (support grip)", pose="rest")
    hand_key(15, sample("cylinder", 15) + GRAB_OFF, "grab: cylinder left face as it swings out", pose="grab")
    for f in (18, 22, 28, 32, 44, 90):                     # every crane/cylinder key while it is out
        hand_key(f, sample("cylinder", f) + CUP_OFF, "cup the open cylinder (ejector punch 22-44)", pose="cup")
    hand_key(115, BELT, "belt: speedloader pouch, low and left", pose="belt")
    hand_key(125, sample("mag_well", 125) + LOADER_OFF, "speedloader at mag_well (open cylinder rear)", pose="loader")
    for f in (130, 134, 138, 140):                         # cylinder closing + lock jolt
        hand_key(f, sample("cylinder", f) + CUP_OFF, "cup the cylinder as it closes/locks", pose="close")
    hand_key(144, HAND_REST, "grip_l (support grip)", pose="rest")
    # authoring-time guard: no beat-to-beat turn may exceed 150 deg (the shortest-path flip in finalize_action
    # then guarantees the baked track never spins the long way round either)
    worst = 0.0
    for (fa, _, _, pa), (fb, _, _, pb_) in zip(HAND_KEYS, HAND_KEYS[1:]):
        d = math.degrees((BEAT_Q[pa][0].inverted() @ BEAT_Q[pb_][0]).normalized().angle)
        d = min(d, 360.0 - d)
        worst = max(worst, d)
        log("hand turn f%d(%s) -> f%d(%s): %.1f deg" % (fa, pa, fb, pb_, d))
    assert worst < 150.0, "a hand beat turns %.1f deg" % worst
    REPORT["hand_max_beat_turn_deg"] = round(worst, 2)

def b_chamber():
    # hammer cock-and-decock (single-action cock indexes the cylinder; trigger eases the hammer down)
    key("hammer", 0, worldY=0); key("hammer", 12, worldY=-30); key("hammer", 26, worldY=-30)
    key("hammer", 40, worldY=0)
    key("cylinder", 0, worldX=0); key("cylinder", 12, worldX=-60); key("cylinder", 48, worldX=-60)
    key("trigger", 0, worldY=0); key("trigger", 14, worldY=0); key("trigger", 22, worldY=10)
    key("trigger", 36, worldY=10); key("trigger", 46, worldY=0)

clip("A_EM08_Idle", 0, 1, b_idle)
clip("A_EM08_Fire", 0, 7, b_fire)
clip("A_EM08_DryFire", 0, 12, b_dryfire)
clip("A_EM08_Reload", 0, 144, b_reload)
clip("A_EM08_Chamber", 0, 48, b_chamber)

# ---------------------------------------------------------------- phase 7: export
# identical to RigM4A1.py FBX_COMMON (UE 5.8 Interchange verified by the M4A1 workflow)
EXPORT = dict(use_selection=True,
              global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
              use_space_transform=True, bake_space_transform=False,
              axis_forward='-Y', axis_up='Z',
              mesh_smooth_type='FACE', use_tspace=True, use_triangles=False, use_custom_props=False,
              add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
              use_armature_deform_only=False, armature_nodetype='NULL',
              path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_metadata=True,
              colors_type='NONE', use_mesh_modifiers=False)
REPORT["export_settings"] = {k: v for k, v in EXPORT.items()}
REPORT["export_settings"]["anim"] = dict(bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                         bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                                         bake_anim_simplify_factor=0.0, bake_anim_use_all_bones=True,
                                         object_types=["ARMATURE", "MESH"], fps=FPS,
                                         note="clip FBX carry mesh+armature: UE Interchange refuses armature-only FBX")
os.makedirs(OUT, exist_ok=True)

def select_only(objs):
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        if o is not None:
            o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]

arm.animation_data.action = None
reset_pose()
select_only([arm, sk])
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "SK_EM08.fbx"), object_types={'ARMATURE', 'MESH'},
                         bake_anim=False, **EXPORT)
for name, c in CLIPS.items():
    arm.animation_data.action = c["action"]
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = c["frames"]
    select_only([arm, sk])
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name + ".fbx"), object_types={'ARMATURE', 'MESH'},
                             bake_anim=True, bake_anim_use_all_bones=True,
                             bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                             bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
                             **EXPORT)
    log("exported", name)
REPORT["clips"] = {n: {"frame_range": c["frames"], "frames": c["frames"][1] - c["frames"][0] + 1, "seconds": c["seconds"],
                       "fps": FPS, "fbx": os.path.join(OUT, n + ".fbx")} for n, c in CLIPS.items()}

# ---------------------------------------------------------------- phase 8: proof renders
import numpy as np
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_shadows = True
sh.show_object_outline = False; sh.show_backface_culling = False
try:
    sh.cavity_type = 'BOTH'
except Exception:
    pass
sc.render.film_transparent = False
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.color = (0.16, 0.17, 0.19)
try:
    sc.display_settings.display_device = 'sRGB'
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass
cam_data = bpy.data.cameras.new("ProofCam"); cam_data.lens = 50; cam_data.clip_start = 0.005
cam = link(bpy.data.objects.new("ProofCam", cam_data)); sc.camera = cam

def aim(loc, target, lens):
    cam.location = loc; cam_data.lens = lens
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

def stamp(text):
    r = sc.render
    for a in dir(r):
        if a.startswith("use_stamp_"):
            try:
                setattr(r, a, False)
            except Exception:
                pass
    r.use_stamp = bool(text)
    if text:
        r.use_stamp_note = True; r.stamp_note_text = text; r.stamp_font_size = 20

BILLBOARDS = []   # objects turned to face the camera on every shot (the curl text of the palm proxy)
def shot(path, w, h, loc, target, lens, text=""):
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    aim(loc, target, lens); stamp(text)
    for o in BILLBOARDS:        # face the camera, and sit on the camera's side of the palm plate, above it
        o.rotation_euler = cam.rotation_euler
        if PROXY_P is not None:
            cam_up = cam.rotation_euler.to_matrix() @ Vector((0, 1, 0))
            o.location = PROXY_P + (Vector(loc) - PROXY_P).normalized() * 0.05 + cam_up * 0.035
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

def load_px(path):
    img = bpy.data.images.load(path, check_existing=False)
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32); img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4); bpy.data.images.remove(img)
    return a

GUN_C = S((-0.012, 0.0, 0.0865))
LEFT34 = Vector((0.42, 0.80, 0.33)).normalized()
PROOFS = []

# hand-target PALM PROXY (B6): a flat 8 x 10 cm orange plate in the palm plane (8 across the palm, 10 along the
# fingers), a 6 cm blue arrow from the palm centre along the finger direction, a 3 cm green stub along the palm
# normal (the side the palm touches) and the curl value as billboard text. Placed from the KEYED pose: the MEASURE
# rest finger/palm vectors (Blender space) rotated by hand_l_target's evaluated armature-space rotation, so what
# the picture shows is what the baked track does. Render only: built after the exports, removed before the .blend
# is saved, never part of any FBX.
PROXY_OBJS = []
def make_palm_proxy():
    root = link(bpy.data.objects.new("_palm_proxy", None))
    def mat(name, rgba):
        m = bpy.data.materials.new(name); m.diffuse_color = rgba
        return m
    m_palm = mat("_M_Palm", (1.0, 0.42, 0.02, 1.0)); m_arrow = mat("_M_Fingers", (0.10, 0.45, 1.0, 1.0))
    m_norm = mat("_M_PalmNormal", (0.15, 0.95, 0.25, 1.0)); m_text = mat("_M_CurlText", (1.0, 1.0, 1.0, 1.0))
    def add(name, build, m):
        bm = bmesh.new(); build(bm)
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
        o = link(bpy.data.objects.new(name, me)); o.parent = root
        PROXY_OBJS.append(o)
        return o
    def along_y(bm, geom, y_centre):      # create_cone builds along local Z; the proxy's finger axis is local +Y
        bmesh.ops.transform(bm, matrix=Matrix.Translation((0, y_centre, 0)) @ Matrix.Rotation(-math.pi / 2, 4, 'X'), verts=geom["verts"])
    def plate(bm):                         # local X across the palm, Y along the fingers, Z = palm normal
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.transform(bm, matrix=Matrix.Diagonal((0.08, 0.10, 0.002, 1.0)), verts=bm.verts)
    def arrow(bm):                         # 4.5 cm shaft + 1.5 cm head = 6 cm from the palm centre
        along_y(bm, bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.0025, radius2=0.0025, depth=0.045), 0.0225)
        along_y(bm, bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.006, radius2=0.0, depth=0.015), 0.0525)
    def stub(bm):                          # 3 cm along the palm normal with a 4 mm ball at the end
        g = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.002, radius2=0.002, depth=0.03)
        bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 0.015)), verts=g["verts"])
        g = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.004)
        bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 0.03)), verts=g["verts"])
    add("_palm_plate", plate, m_palm); add("_palm_fingers", arrow, m_arrow); add("_palm_normal", stub, m_norm)
    cu = bpy.data.curves.new("_palm_text", 'FONT'); cu.body = "curl 1.0"; cu.size = 0.014; cu.align_x = 'CENTER'
    cu.materials.append(m_text)
    txt = link(bpy.data.objects.new("_palm_text", cu))
    PROXY_OBJS.append(txt); BILLBOARDS.append(txt)
    for o in PROXY_OBJS:
        o.hide_render = True
    return root, txt
proxy_root, proxy_text = make_palm_proxy()
PROXY_LOG = []   # per proof: frame, palm centre, finger/normal in UE gun space, curl (what the picture shows)
PROXY_P = None   # palm centre of the posed proxy (world), for the billboard text placement in shot()

def place_palm_proxy(frame):
    """pose the proxy from the EVALUATED hand_l_target (armature space): finger/normal = rest vectors rotated by
    the keyed delta; returns what it shows for the log."""
    pb = arm.pose.bones[HAND_BONE]
    W = arm.matrix_world @ pb.matrix
    p = W.translation.copy()
    R = W.to_3x3().normalized()                      # strip the curl scale, keep the rotation
    f_b = (R @ bl_vec(REST_FINGER_UE)).normalized(); n_b = (R @ bl_vec(REST_PALM_UE)).normalized()
    s_b = f_b.cross(n_b)
    M = Matrix((s_b, f_b, n_b)).transposed().to_4x4(); M.translation = p
    proxy_root.matrix_world = M
    curl = pb.matrix_basis.to_scale().x
    proxy_text.data.body = "curl %.2f" % curl
    global PROXY_P
    PROXY_P = p
    info = {"frame": frame, "palm_ue_cm": ue_cm(p), "finger_dir_gun": [round(c, 3) for c in ue_vec(f_b)],
            "palm_normal_gun": [round(c, 3) for c in ue_vec(n_b)], "curl": round(curl, 3)}
    PROXY_LOG.append(info)
    log("palm proxy", info)
    return info

def proof(fname, action, frame, close_target, close_off, text, close_rig=None, dist=0.64, shift=(0, 0, 0), hand=False):
    arm.animation_data.action = CLIPS[action]["action"] if action else None
    if not action:
        reset_pose()
    sc.frame_set(frame)
    for o in PROXY_OBJS:
        o.hide_render = not hand
    if hand:
        place_palm_proxy(frame)
    tmp_a = os.path.join(OUT, "_tmp_main.png"); tmp_b = os.path.join(OUT, "_tmp_close.png")
    right = LEFT34.cross(Vector((0, 0, 1))).normalized() * -1.0
    up = right.cross(-LEFT34).normalized()
    tgt = GUN_C + right * -0.025 + up * -0.03 + Vector(shift)   # push the gun right/up, clear of the bottom-left inset
    shot(tmp_a, 1600, 900, tgt + LEFT34 * dist, tgt, 50, text)
    ct = Vector(close_rig) if close_rig is not None else S(close_target)
    shot(tmp_b, 560, 420, ct + Vector(close_off), ct, 50)
    A = load_px(tmp_a); B = load_px(tmp_b)
    bw = 4; h, w = B.shape[:2]
    y0 = 16; y1 = y0 + h; x0 = 16; x1 = x0 + w     # bottom-left (array rows run bottom-up)
    A[y0 - bw:y1 + bw, x0 - bw:x1 + bw, :3] = 0.85
    A[y0:y1, x0:x1] = B
    img = bpy.data.images.new("proof", 1600, 900, alpha=False)
    img.pixels.foreach_set(A.ravel()); img.filepath_raw = os.path.join(OUT, fname); img.file_format = 'PNG'; img.save()
    bpy.data.images.remove(img)
    for p in (tmp_a, tmp_b):
        os.remove(p)
    PROOFS.append(os.path.join(OUT, fname))
    log("proof", fname)

HAM_C = (-0.075, 0.0, 0.118); CYL_C = (0.028, 0.0, 0.128)
proof("proof_rest.png", None, 0, CYL_C, (0.06, 0.16, 0.05), "EM_08 rest pose (bind)  |  inset: cylinder seated in the frame window, left side")
proof("proof_fire_hammer_back.png", "A_EM08_Fire", 2, HAM_C, (-0.02, 0.14, 0.03),
      "A_EM08_Fire frame 2 (0.033 s): hammer -30 deg, cylinder indexed 60 deg, trigger 10 deg  |  inset: hammer")
proof("proof_reload_cylinder_out.png", "A_EM08_Reload", 24, (0.005, 0.02, 0.12), (-0.11, 0.12, 0.07),
      "A_EM08_Reload frame 24 (0.40 s): cylinder swung out 90 deg on crane, ejector punching  |  inset: from rear-left, cylinder rear + recoil-shield caps")
proof("proof_reload_locked.png", "A_EM08_Reload", 143, CYL_C, (0.06, 0.16, 0.05),
      "A_EM08_Reload frame 143 (2.38 s): cylinder swung back and locked  |  inset: cylinder seated")
proof("proof_chamber.png", "A_EM08_Chamber", 12, HAM_C, (-0.02, 0.14, 0.03),
      "A_EM08_Chamber frame 12 (0.20 s): hammer cocked (cock-and-decock), cylinder indexed  |  inset: hammer")
# hand-target proofs (B6): palm proxy = hand_l_target (left palm centre, orange plate in the palm plane, blue arrow =
# fingers, green stub = palm normal, text = curl); inset looks at the hand from rear-left
HAND_AT = {f: p for f, _, p, _ in HAND_KEYS}
LEGEND = "  [palm proxy: orange plate = palm plane, blue arrow = fingers, green stub = palm normal]"
proof("proof_rest_hand.png", "A_EM08_Reload", 0, None, (-0.06, 0.14, 0.07), close_rig=HAND_AT[0], hand=True,
      text="A_EM08_Reload frame 0: REST - hand_l_target = grip_l at the Pistol aim pose's native palm %s cm (B4), identity "
           "rotation = the aim pose's hand (palm to the right, wrapping the right hand), curl 1.0" % (GRIP_L_UE_CM,) + LEGEND)
proof("proof_reload_hand_grab.png", "A_EM08_Reload", 15, None, (-0.07, 0.13, 0.06), close_rig=HAND_AT[15], hand=True,
      text="A_EM08_Reload frame 15 (0.25 s): GRAB - left palm reaches the cylinder's left face as it swings out; palm faces right-and-up 45/45 (rolls to the cup by f18), curl 0.9" + LEGEND)
proof("proof_reload_hand_cup.png", "A_EM08_Reload", 60, None, (-0.07, 0.13, 0.06), close_rig=HAND_AT[22], hand=True,
      text="A_EM08_Reload frame 60 (1.00 s): MID-CUP - palm cups the open cylinder (+3,-2.5,-1 cm), normal +Z leaning +Y, fingers forward/up, curl 0.9" + LEGEND)
proof("proof_reload_hand_belt.png", "A_EM08_Reload", 115, None, (0.0, 0.16, 0.05), close_rig=HAND_AT[115], hand=True,
      dist=1.45, shift=(0, 0, -0.14),
      text="A_EM08_Reload frame 115 (1.92 s): BELT - speedloader pouch (+4,-10,-36 cm), palm up-inward, curl 0.8, cylinder still out" + LEGEND)
proof("proof_reload_hand_loader.png", "A_EM08_Reload", 125, None, (-0.10, 0.12, 0.06), close_rig=HAND_AT[125], hand=True,
      text="A_EM08_Reload frame 125 (2.08 s): SPEEDLOADER - palm up leaning forward/right 3.5 cm behind mag_well on the open cylinder's axis, fingers forward-down under the drum, curl 1.0" + LEGEND)
proof("proof_reload_hand_close.png", "A_EM08_Reload", 134, None, (-0.07, 0.13, 0.06), close_rig=HAND_AT[134], hand=True,
      text="A_EM08_Reload frame 134 (2.23 s): CLOSE - palm rides the cylinder as it swings in (locks f138), cup orientation, curl 0.7" + LEGEND)
REPORT["proofs"] = PROOFS
REPORT["palm_proxy_log"] = PROXY_LOG

for o in PROXY_OBJS + [proxy_root]:
    bpy.data.objects.remove(o, do_unlink=True)
arm.animation_data.action = None
reset_pose()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SK_EM08_rig.blend"), compress=True)
if os.path.exists(os.path.join(OUT, "SK_EM08_rig.blend1")):
    os.remove(os.path.join(OUT, "SK_EM08_rig.blend1"))

# ---------------------------------------------------------------- phase 9: re-import verification (fresh scene)
EXPECT_BONES = [b[0] for b in BONES]
VER = {}
IMP = dict(automatic_bone_orientation=False, primary_bone_axis='Y', secondary_bone_axis='X', use_anim=True,
           ignore_leaf_bones=False, anim_offset=0.0)

def bone_world(armo, bname):
    return armo.matrix_world @ armo.pose.bones[bname].matrix

def delta(armo, bname, f, f_ref=0):
    sc.frame_set(f_ref); M0 = bone_world(armo, bname).copy()
    sc.frame_set(f); M1 = bone_world(armo, bname).copy()
    D = M1 @ M0.inverted()
    q = D.to_quaternion()
    ang = math.degrees(q.angle)
    ax = q.axis if ang > 1e-4 else Vector((0, 0, 0))
    return D, ang, ax, M0, M1

def check(cond, msg, bucket):
    bucket.append(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        log("VERIFY FAIL", msg)
    return cond

all_ok = True
clear_scene()
bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, "SK_EM08.fbx"), **IMP)
res = []
armo = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
mesho = [o for o in bpy.data.objects if o.type == 'MESH'][0]
names = [b.name for b in armo.data.bones]
all_ok &= check(sorted(names) == sorted(EXPECT_BONES), "bone list %s" % names, res)
all_ok &= check(armo.data.bones["root"].parent is None and armo.data.bones["cylinder"].parent.name == "crane"
                and armo.data.bones["ejector_rod"].parent.name == "cylinder", "hierarchy root/crane>cylinder>ejector_rod", res)
ws = [mesho.matrix_world @ v.co for v in mesho.data.vertices]
blo = [min(c[i] for c in ws) for i in range(3)]; bhi = [max(c[i] for c in ws) for i in range(3)]
Lr = bhi[0] - blo[0]
all_ok &= check(abs(Lr - L) < 0.002, "length %.2f cm (built %.2f cm)" % (Lr * 100, L * 100), res)
all_ok &= check(blo[0] < 0 < bhi[0] and blo[2] < 0 < bhi[2], "origin inside gun bounds %s %s" % (blo, bhi), res)
all_ok &= check(bhi[0] > 0.15 and blo[0] > -0.12, "muzzle on +X (max x %.3f, min x %.3f)" % (bhi[0], blo[0]), res)
worst = max((armo.matrix_world.to_3x3() @ bb.matrix_local.to_3x3()).to_quaternion().angle
            for bb in armo.data.bones if bb.name != "ejection_port")
all_ok &= check(math.degrees(worst) < 0.01, "rest bone orientation identity in world (worst %.4f deg) = M4A1 convention" % math.degrees(worst), res)
gh = (armo.matrix_world @ armo.data.bones["grip_r"].head_local)
all_ok &= check(gh.length < 1e-4, "grip_r at origin (%s)" % list(gh), res)
# B4: grip_l and the hand_l_target rest at the native pistol palm offset (both the same point)
gl = ue_cm(armo.matrix_world @ armo.data.bones["grip_l"].head_local)
ht = ue_cm(armo.matrix_world @ armo.data.bones[HAND_BONE].head_local)
all_ok &= check(all(abs(gl[i] - GRIP_L_UE_CM[i]) < 0.05 for i in range(3)),
                "grip_l at UE cm %s = B4 target %s (was %s)" % (gl, list(GRIP_L_UE_CM), list(GRIP_L_OLD_UE_CM)), res)
all_ok &= check(all(abs(gl[i] - ht[i]) < 0.05 for i in range(3)), "%s rest == grip_l (%s)" % (HAND_BONE, ht), res)
all_ok &= check(GRIP_L_UE_CM[0] >= -6.0 and GRIP_L_UE_CM[2] <= 0.0 and math.sqrt(sum(c * c for c in GRIP_L_UE_CM)) <= 12.0,
                "grip_l inside the envelope (x >= -6, z <= 0, <= 12 cm from grip_r)", res)
vg = {g.index: g.name for g in mesho.vertex_groups}
bad = 0; per = {}
for v in mesho.data.vertices:
    gs = [(vg[g.group], g.weight) for g in v.groups if g.weight > 1e-6]
    if len(gs) != 1 or abs(gs[0][1] - 1.0) > 1e-4:
        bad += 1
    else:
        per[gs[0][0]] = per.get(gs[0][0], 0) + 1
all_ok &= check(bad == 0, "rigid skinning: %d bad verts, per-bone %s" % (bad, per), res)
VER["SK_EM08.fbx"] = {"checks": res, "bounds_m": [blo, bhi], "length_cm": round(Lr * 100, 3)}

def verify_anim(fname, frames, tests):
    global all_ok
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, fname), **IMP)
    res = []
    armo = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    act = armo.animation_data.action if armo.animation_data else None
    ok = check(act is not None, "action present", res)
    ok &= check(any(o.type == 'MESH' for o in bpy.data.objects), "clip FBX carries the mesh (UE Interchange needs it)", res)
    if ok:
        fr = act.frame_range
        fps = sc.render.fps / sc.render.fps_base
        secs = (fr[1] - fr[0]) / fps
        exp_s = (frames[1] - frames[0]) / FPS
        ok &= check(abs(secs - exp_s) < 1e-3 and abs(fps - FPS) < 1e-3,
                    "clip length %.4f s (%d..%d @ %g fps), expected %.4f s" % (secs, fr[0], fr[1], fps, exp_s), res)
        ok &= check(sorted(b.name for b in armo.data.bones) == sorted(EXPECT_BONES), "bone list matches", res)
        for t in tests:
            ok &= t(armo, res)
    all_ok &= ok
    VER[fname] = {"checks": res}

def t_rot(bone, f, deg, axis, f_ref=0, tol=0.6, probe=None):
    def t(armo, res):
        D, ang, ax, M0, M1 = delta(armo, bone, f, f_ref)
        ok = check(abs(ang - deg) < tol and (deg < 1e-3 or abs(abs(ax.dot(Vector(axis))) - 1) < 0.02),
                   "%s f%d vs f%d: rotates %.2f deg about world %s (expected %.1f about %s)" %
                   (bone, f, f_ref, ang, [round(c, 3) for c in ax], deg, axis), res)
        if probe:
            off, comp, sign = probe
            p0 = M0.translation + Vector(off)
            p1 = D @ p0
            mv = (p1 - p0)[comp]
            ok &= check(mv * sign > 0, "%s probe moves %+.4f m on axis %d (expected sign %+d)" % (bone, mv, comp, sign), res)
        return ok
    return t

def t_move(bone, f, dist, axis, f_ref):
    def t(armo, res):
        sc.frame_set(f_ref); p0 = bone_world(armo, bone).translation.copy()
        sc.frame_set(f); p1 = bone_world(armo, bone).translation.copy()
        d = p1 - p0
        return check(abs(d.length - dist) < 5e-4 and abs(abs(d.normalized().dot(Vector(axis))) - 1) < 0.02 if dist > 0 else d.length < 1e-5,
                     "%s f%d vs f%d moves %.4f m along %s (expected %.4f along %s)" % (bone, f, f_ref, d.length,
                     [round(c, 3) for c in (d.normalized() if d.length > 1e-9 else d)], dist, axis), res)
    return t

def bone_local(armo, bname):
    pb = armo.pose.bones[bname]
    return pb.parent.matrix.inverted() @ pb.matrix if pb.parent else pb.matrix

def t_still(bone, frames):
    """bone static relative to its parent (body recoil/jolt may still move it in world space)"""
    def t(armo, res):
        mx = 0.0
        sc.frame_set(frames[0]); M0 = bone_local(armo, bone).copy()
        for f in range(frames[0], frames[1] + 1):
            sc.frame_set(f); M = bone_local(armo, bone)
            mx = max(mx, max(abs(M[i][j] - M0[i][j]) for i in range(3) for j in range(4)))
        return check(mx < 1e-4, "%s static relative to parent over %s (max matrix delta %.2e)" % (bone, frames, mx), res)
    return t

def t_cyl_open(f):
    def t(armo, res):
        sc.frame_set(f); p = bone_world(armo, "cylinder").translation
        return check(p.y > 0.025, "cylinder head at f%d is %.4f m to the gun's left (+Y Blender / -Y UE)" % (f, p.y), res)
    return t

def t_hand_present():
    """FBX carries no deform flag (the importer marks every bone deforming), so 'non-deforming' is proven by the
    mesh having no vertex group for the bone."""
    def t(armo, res):
        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        skinned = any(HAND_BONE in o.vertex_groups for o in meshes)
        return check(HAND_BONE in armo.data.bones and armo.data.bones[HAND_BONE].parent.name == "body" and not skinned,
                     "%s present, child of body, no vertex group (non-deforming)" % HAND_BONE, res)
    return t

def t_hand_near(f, ref_bone, off, tol, label, abs_pos=None):
    """hand_l_target head at frame f within tol (m) of ref_bone head + off (armature space), or of abs_pos."""
    def t(armo, res):
        sc.frame_set(f)
        h = bone_world(armo, HAND_BONE).translation.copy()
        p = (armo.matrix_world @ Vector(abs_pos)) if abs_pos is not None else (bone_world(armo, ref_bone).translation.copy() + Vector(off))
        d = (h - p).length
        return check(d < tol, "%s f%d %s: %.2f cm from %s (tol %.1f cm); hand UE cm %s" %
                     (HAND_BONE, f, label, d * 100, ref_bone if abs_pos is None else "target", tol * 100, ue_cm(h)), res)
    return t

# ---- B5/B7: hand_l_target rotation (delta from rest, read in UE gun space) and scale X (curl) tracks
def hand_world_quat(armo, f):
    """armature-space rotation of hand_l_target at f (rest is identity, so this IS the delta UE's socket reports
    in component space, body jolt included); the curl scale is stripped by column-normalising."""
    sc.frame_set(f)
    return bone_world(armo, HAND_BONE).to_3x3().normalized().to_quaternion().normalized()

def hand_curl(armo, f):
    sc.frame_set(f)
    return bone_local(armo, HAND_BONE).to_scale().x

def t_hand_ends(f0, f1):
    """rotation identity (< 2 deg) and scale X 1.0 (+-0.02) at the first and last frame"""
    def t(armo, res):
        ok = True
        for f in (f0, f1):
            q = hand_world_quat(armo, f); ang = math.degrees(q.angle); ang = min(ang, 360.0 - ang)
            s = hand_curl(armo, f)
            ok &= check(ang < 2.0, "%s f%d rotation identity (%.3f deg)" % (HAND_BONE, f, ang), res)
            ok &= check(abs(s - 1.0) < 0.02, "%s f%d scale X %.4f == 1.0" % (HAND_BONE, f, s), res)
        return ok
    return t

def t_hand_path(f0, f1, step=6):
    """finite, every consecutive sampled delta < 150 deg (every 6th frame + the last), scale X in [0.4, 1.6] on every frame"""
    def t(armo, res):
        frames = list(range(f0, f1 + 1, step))
        if frames[-1] != f1:
            frames.append(f1)
        worst = 0.0; finite = True
        prev = hand_world_quat(armo, frames[0])
        for f in frames[1:]:
            q = hand_world_quat(armo, f)
            finite &= all(math.isfinite(c) for c in q)
            d = math.degrees((prev.inverted() @ q).normalized().angle); d = min(d, 360.0 - d)
            worst = max(worst, d); prev = q
        smin, smax = 9.0, -9.0
        for f in range(f0, f1 + 1):
            s = hand_curl(armo, f); smin = min(smin, s); smax = max(smax, s)
        ok = check(finite and worst < 150.0, "%s consecutive %d-frame deltas finite, max %.1f deg (< 150)" % (HAND_BONE, step, worst), res)
        ok &= check(0.4 <= smin and smax <= 1.6, "%s scale X within [0.4, 1.6] over all frames (%.3f .. %.3f)" % (HAND_BONE, smin, smax), res)
        return ok
    return t

BEAT_FRAMES = [(0, "rest"), (15, "grab"), (60, "cup"), (90, "cup"), (115, "belt"), (125, "loader"), (134, "close"), (140, "close"), (144, "rest")]
MEASURED_BEATS = []   # filled by t_hand_beats for the JSON (rotation_keys / curl_keys)
def t_hand_beats(beats, tol_deg=2.0, tol_curl=0.02):
    """at each beat frame the re-imported rotation (UE gun space axis-angle) equals the designed delta and the curl
    equals the designed value; prints both for the reviewer"""
    def t(armo, res):
        ok = True
        for f, pose in beats:
            q_ue = bl_quat_to_ue(hand_world_quat(armo, f))
            want, f_ue, n_ue = BEAT_Q[pose]
            err = math.degrees((want.inverted() @ q_ue).normalized().angle); err = min(err, 360.0 - err)
            ax, deg = axis_angle_deg(q_ue)
            s = hand_curl(armo, f)
            fing = [round(c, 3) for c in (q_ue @ REST_FINGER_UE)]; norm = [round(c, 3) for c in (q_ue @ REST_PALM_UE)]
            ok &= check(err < tol_deg, "%s f%d (%s): rotation UE gun space axis %s %.2f deg, %.2f deg from design; "
                        "fingers %s palm normal %s" % (HAND_BONE, f, pose, ax, deg, err, fing, norm), res)
            ok &= check(abs(s - BEATS[pose]["curl"]) < tol_curl, "%s f%d (%s): curl %.3f (design %.2f)" % (HAND_BONE, f, pose, s, BEATS[pose]["curl"]), res)
            MEASURED_BEATS.append({"frame": f, "seconds": round(f / FPS, 4), "beat": pose, "ue_axis": ax, "ue_deg": deg,
                                   "design_error_deg": round(err, 3), "finger_dir_gun": fing, "palm_normal_gun": norm,
                                   "curl": round(s, 4), "curl_design": BEATS[pose]["curl"]})
            log("BEAT f%d %s: axis %s %.2f deg, curl %.3f" % (f, pose, ax, deg, s))
        return ok
    return t

verify_anim("A_EM08_Idle.fbx", (0, 1), [t_still("hammer", (0, 1)), t_still("cylinder", (0, 1)),
                                        t_hand_present(), t_hand_near(0, "grip_l", (0, 0, 0), 0.003, "at grip_l"),
                                        t_hand_near(1, "grip_l", (0, 0, 0), 0.003, "at grip_l"),
                                        t_hand_ends(0, 1), t_hand_path(0, 1)])
verify_anim("A_EM08_Fire.fbx", (0, 7), [
    t_rot("hammer", 2, 30, (0, 1, 0), probe=((0, 0, 0.02), 0, -1)),
    t_rot("hammer", 3, 0, (0, 1, 0)),
    t_rot("cylinder", 2, 60, (1, 0, 0)),
    t_rot("trigger", 2, 10, (0, 1, 0), probe=((0, 0, -0.02), 0, -1)),
    t_rot("body", 4, 3, (0, 1, 0), probe=((0.15, 0, 0), 2, +1)),
    t_still(HAND_BONE, (0, 7)), t_hand_ends(0, 7), t_hand_path(0, 7)])
verify_anim("A_EM08_DryFire.fbx", (0, 12), [
    t_rot("hammer", 4, 30, (0, 1, 0)), t_rot("cylinder", 4, 60, (1, 0, 0)), t_rot("trigger", 4, 10, (0, 1, 0)),
    t_still("body", (0, 12)), t_hand_ends(0, 12), t_hand_path(0, 12)])
verify_anim("A_EM08_Reload.fbx", (0, 144), [
    t_hand_ends(0, 144), t_hand_path(0, 144), t_hand_beats(BEAT_FRAMES),
    t_rot("crane", 22, 90, (1, 0, 0)), t_cyl_open(22), t_cyl_open(24),
    t_move("ejector_rod", 28, 0.02, (1, 0, 0), 22), t_move("ejector_rod", 44, 0.0, (1, 0, 0), 22),
    t_cyl_open(125),                                          # still out for the speedloader beat
    t_rot("crane", 143, 0, (1, 0, 0)), t_rot("cylinder", 143, 0, (1, 0, 0)),
    t_still("hammer", (0, 144)), t_still("trigger", (0, 144)),
    # left-hand target (design items 2-3): grip_l at both ends, cylinder + cup offset mid-carry, belt, loader
    t_hand_present(),
    t_hand_near(0, "grip_l", (0, 0, 0), 0.003, "at grip_l (frame 0)"),
    t_hand_near(144, "grip_l", (0, 0, 0), 0.003, "at grip_l (last frame)"),
    t_hand_near(15, "cylinder", GRAB_OFF, 0.02, "grab: cylinder + (3,-3.5,0) cm"),
    t_hand_near(60, "cylinder", CUP_OFF, 0.02, "mid-carry: cylinder + (3,-2.5,-1) cm"),
    t_hand_near(90, "cylinder", CUP_OFF, 0.02, "end of cup: cylinder + (3,-2.5,-1) cm"),
    t_hand_near(115, None, None, 0.02, "belt (4,-10,-36) cm", abs_pos=BELT),
    t_hand_near(125, "mag_well", LOADER_OFF, 0.02, "speedloader: mag_well + (-3.5,-1,0) cm"),
    t_hand_near(138, "cylinder", CUP_OFF, 0.02, "cup at lock: cylinder + (3,-2.5,-1) cm")])
verify_anim("A_EM08_Chamber.fbx", (0, 48), [
    t_rot("hammer", 12, 30, (0, 1, 0), probe=((0, 0, 0.02), 0, -1)), t_rot("hammer", 40, 0, (0, 1, 0)),
    t_rot("cylinder", 12, 60, (1, 0, 0)), t_rot("trigger", 22, 10, (0, 1, 0)),
    t_hand_ends(0, 48), t_hand_path(0, 48)])

REPORT["verification"] = VER
REPORT["verification_all_pass"] = bool(all_ok)
REPORT["runtime_s"] = round(time.time() - T0, 1)
REPORT["units"] = {"blender": "metres, scale_length 1.0", "fbx": "UnitScaleFactor 100 via FBX_SCALE_NONE -> 1 m = 100 UU",
                   "axes": "Blender +X muzzle = UE +X; Blender +Z = UE +Z; Blender +Y (gun left) = UE -Y",
                   "armature_object": "named 'Armature' so UE does not insert an extra root bone; data block 'EM_08_Skeleton'",
                   "bone_orientation": "same as M4A1: every bone identity in UE component space (X fwd, Y right, Z up; Blender rest bones point +Y), "
                                       "except ejection_port whose X points to the gun's right; hammer/trigger rotate about Y, cylinder/crane about X, "
                                       "ejector_rod slides along bone X (-2 cm = rearward)",
                   "matches": "Scripts/Blender/RigM4A1.py FBX_COMMON export settings, bone axes, armature naming, grip_r under root"}
REPORT["animation_notes"] = {
    "A_EM08_Chamber": "hammer cock-and-decock: cock 0-12 (cylinder indexes 60), hold, trigger eases hammer down 22-40",
    "cylinder_index": "60 deg per shot about -X (counter-clockwise seen from the rear). Mesh chambers are NOT 6-fold symmetric "
                      "(0, +-39, 180, 180+-39 deg), so the end pose differs from the start pose; see notes.md",
    "reload_timeline_frames": "0-18 swing out (overshoot 3 deg), 22 settled, 22-28 ejector punch 2 cm, 28-32 hold, 32-44 return, "
                              "44-90 hand cups the open cylinder, 90-115 hand to the belt, 115-125 speedloader up to mag_well, "
                              "128-138 swing in (ease-in), 138 lock snap (cylinder -4 deg catch + 1.5 deg body jolt), 142/144 settled "
                              "(2026-10-30: close moved from 96-108 so the loader meets an open cylinder)"}
REPORT["hand_target"] = {
    "bone": HAND_BONE, "parent": "body", "deform": False, "meaning": "left PALM CENTRE IK target (gun space)",
    "rest_ue_cm": ue_cm(HAND_REST), "rest_equals": "grip_l (SupportSocket): pose location 0 outside reloads",
    "keyed_in": list(HAND_CLIPS), "not_keyed_in": [n for n in CLIPS if n not in HAND_CLIPS],
    "offsets_ue_cm": {"grab": [3, -3.5, 0], "cup": [3, -2.5, -1], "belt_from_grip_r": [4, -10, -36],
                      "speedloader_from_mag_well": [-3.5, -1, 0]},
    "keys": [{"frame": f, "seconds": round(f / FPS, 4), "beat": beat, "pose": pose, "ue_cm": ue_cm(p),
              "curl": BEATS[pose]["curl"], "rot_ue_axis": axis_angle_deg(BEAT_Q[pose][0])[0], "rot_ue_deg": axis_angle_deg(BEAT_Q[pose][0])[1]}
             for f, beat, p, pose in HAND_KEYS],
    "interpolation": "Bezier auto-clamped (eased) between beats on location, quaternion and scale alike; holds are flat; "
                     "quaternion keys sign-flipped into one hemisphere (shortest path)",
    "grip_l_relative_to_grip_r_ue_cm": ue_cm(S(GRIP_L)),
    "grip_l_moved": True,
    "grip_l_old_ue_cm": list(GRIP_L_OLD_UE_CM), "grip_l_new_ue_cm": list(GRIP_L_UE_CM), "grip_l_source": GRIP_L_SOURCE,
    "grip_l_note": "B4 2026-10-30: grip_l and the hand_l_target rest moved from the centre-line (2.5, 0, -3.7) to the "
                   "Pistol aim pose's NATIVE left palm offset from the seated grip_r, %s cm (MEASURE report, rounded to "
                   "0.5 cm; envelope x >= -6, z <= 0 respected). At aim the support IK is now a no-op and the left hand "
                   "wraps the right hand as the pose author made it instead of being pulled 5 cm into the frame." % (list(GRIP_L_UE_CM),),
    # B5 rotation / curl convention for the C++ side (FHoverSupportHandNode) and ValidateGunClips.py
    "rotation_convention": "hand_l_target's rotation is a DELTA from its identity rest, read as the socket's gun-space "
                           "rotation (RTS_Component, scale stripped): D = T R^-1 with R = the Pistol aim pose's hand frame "
                           "(fingers %s, palm normal %s in gun space) and T the beat's frame. Identity at f0 and the last "
                           "frame of every clip. Blender authoring: R_ue = M R_bl M, M = diag(1,-1,1)." %
                           ([round(c, 3) for c in REST_FINGER_UE], [round(c, 3) for c in REST_PALM_UE]),
    "curl_convention": "bone-LOCAL scale X (not component scale, which carries root's x100): 1.0 = the aim pose's fingers, "
                       "0.0 = open reference hand, > 1 tighter, always within [0.4, 1.6]; 1.0 at f0 and the last frame of every clip",
    "rotation_keys": MEASURED_BEATS,                       # measured on the re-imported FBX (UE gun-space axis-angle)
    "curl_keys": [{"frame": b["frame"], "beat": b["beat"], "curl": b["curl"]} for b in MEASURED_BEATS],
    "beats_design": REPORT["hand_beats_ue"],
    "exporter": "use_armature_deform_only=False, bake_anim_use_all_bones=True -> the non-deforming target gets baked "
                "location, rotation and scale tracks"}

def jsonable(o):
    if isinstance(o, (Vector,)):
        return [round(c, 6) for c in o]
    if isinstance(o, float):
        return round(o, 6)
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o

with open(os.path.join(OUT, "em08_rig.json"), "w", encoding="utf-8") as fh:
    json.dump(jsonable(REPORT), fh, indent=2)
log("VERIFY ALL PASS" if all_ok else "VERIFY HAD FAILURES", "runtime", REPORT["runtime_s"])
