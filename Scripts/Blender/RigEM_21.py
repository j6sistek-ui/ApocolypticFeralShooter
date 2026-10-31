"""RigEM_21.py - cut, rig, animate and export the EM_21 (MP5K-style) SMG from the
EM Apocalyptic Guns Vol 23 pack. Blender 5.2 headless, idempotent:

  blender.exe -b --python RigEM_21.py                 # full build + proofs + verify
  blender.exe -b --python RigEM_21.py -- --stage cut  # stop after the cut, debug renders
  blender.exe -b --python RigEM_21.py -- --verify     # re-import checks only (fresh scene)

All landmark numbers in CFG are SOURCE coordinates in cm, i.e. the FBX after the importer's
own transform (muzzle on -X, gun's left side on -Y, up +Z). The script then turns the gun
180 deg about Z (muzzle +X, right side -Y = UE +Y) and moves grip_r to the origin.
Outputs: SourceAssets/EM_Apocalyptic_Guns/Rigged/EM_21/. Never touches Content or the editor.

2026-10-30: 'hand_l_target' (non-deforming child of body, rest at the grip_l head) is the PALM-CENTRE
IK target for the body's left hand. It is keyed only in Reload: mag-release touch, down to the belt,
carries the fresh magazine (hand == magazine + cup offset at every carry key), HK slap on the charging
handle, back to grip_l. The dropped magazine falls 56 cm, is hidden with bone SCALE 0.001 for the hold
and pops in at the hand at the belt (never a visible mag rising from below the hand).

2026-10-30 (evening, DESIGN B5/B6): hand_l_target also carries the left hand's ORIENTATION and FINGER CURL.
Its pose ROTATION is a delta from the rest (identity == however the stance aim pose holds the hand at the
support grip), authored in UE gun space from the measured Rifle-stance palm normal / finger direction and
converted to Blender armature space with the Y mirror (derived + round-trip asserted in
check_rotation_convention). Its bone SCALE (uniform, UE reads X) is the curl: 1.0 = aim-pose fingers,
0 = open reference pose, 1.6 = tightest. Beats: touch the mag release palm +Y (curl 1.0), belt palm up-inward
(0.8), grab/carry palm on the mag's left face fingers forward-down (1.3), HK slap palm DOWN on the ring handle
2.5 cm above it (0.6), back to identity / 1.0 by f144. Proofs draw a PALM PROXY (8 x 10 cm plate, 6 cm finger
arrow, 4 cm palm-normal stick) plus the curl as text instead of a sphere.
"""
import bpy, bmesh, sys, os, json, math, time, subprocess
from mathutils import Vector, Matrix, Euler, Quaternion

SRC = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\FBX\EM_Apocalyptic_Guns_FBX\EM_21_Apocalyptic_Guns\EM_21_Apocalyptic_Guns.fbx"
OUT = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\Rigged\EM_21"
FPS = 60

CFG = dict(
    # 1.0 = keep the FBX's own cm. The brief assumed inches (x2.54); measured length 34.22 cm
    # matches a real MP5K (32.5 cm, 21 cm tall, 5 cm wide); x2.54 would give an 87 cm SMG.
    scale=1.0,
    # magazine = union of UV islands whose bounds sit fully inside this box (source cm)
    mag_box=dict(x=(-10.0, -0.5), y=(-1.75, 1.75), z=(-2.5, 9.3)),
    # charging handle = ring + arm lever on each side of the cocking tube (stylised MP5 handle)
    lever_ring=(-1.3, 17.15), lever_ring_r=0.95,          # (x, z), radius cm
    lever_arm=((-1.3, 17.15), (-3.25, 13.95)), lever_arm_r=0.75,
    lever_min_abs_y=(1.5, 1.3),             # per side (-1, +1): outboard of the receiver skin                                  # outboard of the receiver skin
    lever_sides=(-1, 1),                                  # -1 = gun left (source -Y), +1 = right
    # trigger blade inside the guard
    trig_box=dict(x=(0.6, 2.7), y=(-0.7, 0.7), z=(8.3, 10.1)), trig_seed=(1.9, 0.0, 9.3),
    # cap style: centre-fan depth in cm into the part (None = BEAUTY triangulation)
    poke_depth={"magazine": {"part": 0.15, "body": 1.5}},
    # landmarks (source cm)
    grip_top=(6.9, 0.0, 8.0),       # origin / grip_r: pistol-grip top, centre line
    trig_pivot=(1.6, 0.0, 10.1),
    muzzle_x=-21.1, bore_z=14.35,
    sight=(5.5, 0.0, 18.3),         # rear-sight block top, centre line
    grip_l=(-9.0, 0.0, 11.4),       # under the tube between mag and suppressor box
    eject=(-2.0, None, 14.3),       # right side (source +Y), y filled from geometry
)

# ---------------------------------------------------------------- helpers
def argv_after():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

def log(*a):
    print("[EM21]", *a, flush=True)

def reset():
    bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    return sc

def fcurves_of(action):
    """Blender 4.4+/5 layered actions: gather every F-curve."""
    fcs = []
    if hasattr(action, "layers") and len(action.layers):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    cb = strip.channelbag(slot)
                    if cb:
                        fcs.extend(cb.fcurves)
    elif hasattr(action, "fcurves"):
        fcs.extend(action.fcurves)
    return fcs

def uv_islands(bm, uv):
    def key(l):
        u = l[uv].uv
        return (round(u.x, 5), round(u.y, 5))
    lab = {}
    n = 0
    for f in bm.faces:
        if f in lab:
            continue
        lab[f] = n
        st = [f]
        while st:
            x = st.pop()
            for l in x.loops:
                for l2 in l.edge.link_loops:
                    g = l2.face
                    if g in lab:
                        continue
                    a1, b1 = key(l), key(l.link_loop_next)
                    if l2.vert == l.vert:
                        a2, b2 = key(l2), key(l2.link_loop_next)
                    else:
                        a2, b2 = key(l2.link_loop_next), key(l2)
                    if a1 == a2 and b1 == b2:
                        lab[g] = n
                        st.append(g)
        n += 1
    isl = [[] for _ in range(n)]
    for f, i in lab.items():
        isl[i].append(f)
    return isl

def inbox(p, box):
    return all(box[k][0] <= p[i] <= box[k][1] for i, k in enumerate("xyz"))

def segdist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length

def enclose(sel, rounds=4):
    """Add faces all of whose edge-neighbours are selected (pinholes in a selection)."""
    for _ in range(rounds):
        add = set()
        for f in list(sel):
            for e in f.edges:
                for g in e.link_faces:
                    if g in sel or g in add:
                        continue
                    if all(any(h in sel for h in ee.link_faces if h is not g) for ee in g.edges):
                        add.add(g)
        if not add:
            break
        sel |= add
    return sel

def border_loops(edges):
    """Count connected chains among a set of edges."""
    edges = set(edges)
    seen = set()
    n = 0
    for e in edges:
        if e in seen:
            continue
        n += 1
        st = [e]
        seen.add(e)
        while st:
            x = st.pop()
            for v in x.verts:
                for y in v.link_edges:
                    if y in edges and y not in seen:
                        seen.add(y)
                        st.append(y)
    return n

# ---------------------------------------------------------------- cut
def cut_part(bm, sel, uv, name, smooth_caps=False, poke_depth=None):
    """Split `sel` faces from the rest along their border, cap both openings.
    Returns report dict and the set of the part's faces (incl. its cap)."""
    sel = set(sel)
    border = [e for e in bm.edges
              if any(f in sel for f in e.link_faces) and any(f not in sel for f in e.link_faces)]
    rep = dict(faces_moved=len(sel), border_edges=len(border), border_loops=border_loops(border),
               verts_moved=len({v for f in sel for v in f.verts}))
    if not border:
        rep["case"] = "island"
        return rep, sel, [], []
    rep["case"] = "shared"
    pre_boundary = {e for e in bm.edges if e.is_boundary}
    bmesh.ops.split_edges(bm, edges=border)
    new_b = [e for e in bm.edges if e.is_boundary and e not in pre_boundary]
    part_e = [e for e in new_b if e.link_faces[0] in sel]
    body_e = [e for e in new_b if e.link_faces[0] not in sel]
    caps = {}
    for side, es in (("part", part_e), ("body", body_e)):
        if not es:
            caps[side] = []
            continue
        res = bmesh.ops.holes_fill(bm, edges=es, sides=0)
        faces = list(res["faces"])
        if faces and poke_depth is not None:
            # convex-ish opening (mag well / mag top): centre fan, centre pushed `depth` cm into
            # the part so the well reads as a recess instead of BEAUTY shards on a non-planar loop
            depth = poke_depth[side] * 0.01
            nrm = sum((f.normal for f in faces), Vector()).normalized()
            pk = bmesh.ops.poke(bm, faces=faces, center_mode='MEAN_WEIGHTED')
            for v in pk["verts"]:
                v.co -= nrm * depth
            faces = list(pk["faces"])
        elif faces:
            tri = bmesh.ops.triangulate(bm, faces=faces, quad_method='BEAUTY', ngon_method='BEAUTY')
            faces = list(tri["faces"])
        # winding: cap normal should point away from the adjacent surface's inside, i.e.
        # opposite to the average normal of the faces it closes over is wrong - use the
        # rule that each boundary edge must be traversed in opposite directions.
        for f in faces:
            # flat + hard rim for a machined opening (mag well); smooth for scars on a
            # sculpted surface (handle/trigger footprint) so the fan does not read as facets
            f.smooth = smooth_caps
            if not smooth_caps:
                for e in f.edges:
                    if any(g not in faces for g in e.link_faces):
                        e.smooth = False
        # UV: sample a tiny patch around the UV centre of an adjacent original face
        nb = None
        for f in faces:
            for e in f.edges:
                for g in e.link_faces:
                    if g not in faces:
                        nb = g
                        break
                if nb: break
            if nb: break
        if nb is not None and faces:
            anchor = sum((l[uv].uv for l in nb.loops), Vector((0, 0))) / len(nb.loops)
            cen = sum((v.co for f in faces for v in f.verts), Vector()) / sum(len(f.verts) for f in faces)
            nrm = sum((f.normal for f in faces), Vector()).normalized()
            ax = nrm.orthogonal().normalized()
            ay = nrm.cross(ax)
            for f in faces:
                for l in f.loops:
                    d = l.vert.co - cen
                    l[uv].uv = anchor + Vector((d.dot(ax), d.dot(ay))) * 0.05   # 5 cm -> 0.0025 uv
        caps[side] = faces
    rep["cap_tris_part"] = len(caps["part"])
    rep["cap_tris_body"] = len(caps["body"])
    rep["cap_loops_part"] = border_loops(part_e)
    rep["cap_loops_body"] = border_loops(body_e)
    return rep, sel | set(caps["part"]), caps["part"], caps["body"]

def select_parts(bm, uv):
    S = 100.0  # metres -> cm
    cen = {f: f.calc_center_median() * S for f in bm.faces}
    out = {}
    # magazine: UV islands fully in box
    isl = uv_islands(bm, uv)
    mag = set()
    n_isl = 0
    for fs in isl:
        pts = [v.co * S for f in fs for v in f.verts]
        mn = [min(p[i] for p in pts) for i in range(3)]
        mx = [max(p[i] for p in pts) for i in range(3)]
        if inbox(mn, CFG["mag_box"]) and inbox(mx, CFG["mag_box"]):
            mag |= set(fs)
            n_isl += 1
    mag = enclose(mag)
    out["magazine"] = (mag, dict(method="uv_islands_in_box", uv_islands_total=len(isl), uv_islands_used=n_isl))

    # levers (charging handle), flood-filled inside the side silhouette
    ring = Vector(CFG["lever_ring"]); a, b = (Vector(p) for p in CFG["lever_arm"])
    def lever_pred(f, side):
        c = cen[f]
        if side * c.y < CFG["lever_min_abs_y"][0 if side < 0 else 1]:
            return False
        p = Vector((c.x, c.z))
        return (p - ring).length < CFG["lever_ring_r"] or segdist(p, a, b) < CFG["lever_arm_r"]
    handle = set()
    for side in CFG["lever_sides"]:
        cand = [f for f in bm.faces if lever_pred(f, side)]
        seedp = Vector((ring.x, side * 2.65, ring.y))
        seed = min(cand, key=lambda f: (cen[f] - seedp).length)
        sel = {seed}; st = [seed]
        cs = set(cand)
        while st:
            x = st.pop()
            for e in x.edges:
                for g in e.link_faces:
                    if g in cs and g not in sel:
                        sel.add(g); st.append(g)
        handle |= enclose(sel)
    out["charging_handle"] = (handle, dict(method="flood_in_side_silhouette", sides=list(CFG["lever_sides"])))

    # trigger
    tb = CFG["trig_box"]
    cand = {f for f in bm.faces if inbox(cen[f], tb)}
    seedp = Vector(CFG["trig_seed"])
    seed = min(cand, key=lambda f: (cen[f] - seedp).length)
    sel = {seed}; st = [seed]
    while st:
        x = st.pop()
        for e in x.edges:
            for g in e.link_faces:
                if g in cand and g not in sel:
                    sel.add(g); st.append(g)
    out["trigger"] = (enclose(sel), dict(method="flood_in_box"))
    # no overlaps
    out["charging_handle"] = (out["charging_handle"][0] - out["magazine"][0], out["charging_handle"][1])
    out["trigger"] = (out["trigger"][0] - out["magazine"][0] - out["charging_handle"][0], out["trigger"][1])
    return out

def import_and_cut():
    t0 = time.time()
    bpy.ops.import_scene.fbx(filepath=SRC, use_custom_normals=False)
    bpy.context.scene.render.fps = FPS          # the importer sets the source file's 30 fps
    bpy.context.scene.render.fps_base = 1.0
    src = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    for o in list(bpy.data.objects):
        if o is not src:
            bpy.data.objects.remove(o)
    bpy.context.view_layer.objects.active = src
    src.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    src.name = "SK_EM21"; src.data.name = "SK_EM21"
    me = src.data
    if CFG["scale"] != 1.0:
        me.transform(Matrix.Scale(CFG["scale"], 4))
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    # loose islands before cutting
    seen = set(); islands = []
    for v in bm.verts:
        if v in seen: continue
        st = [v]; seen.add(v); n = 0
        while st:
            x = st.pop(); n += 1
            for e in x.link_edges:
                y = e.other_vert(x)
                if y not in seen:
                    seen.add(y); st.append(y)
        islands.append(n)
    report = dict(source_faces=len(bm.faces), source_verts=len(bm.verts),
                  source_tris=sum(len(f.verts) - 2 for f in bm.faces),
                  source_loose_islands=len(islands), island_vert_counts=sorted(islands, reverse=True),
                  source_boundary_edges=sum(1 for e in bm.edges if e.is_boundary))
    lay = bm.faces.layers.int.new("em_part")
    capl = bm.faces.layers.int.new("em_cap")
    parts = select_parts(bm, uv)
    groups = {}
    caps = {}
    for name in ("magazine", "charging_handle", "trigger"):
        sel, meta = parts[name]
        rep, faces, cp, cb = cut_part(bm, sel, uv, name, smooth_caps=(name != "magazine"),
                                      poke_depth=CFG["poke_depth"].get(name))
        rep.update(meta)
        report[name] = rep
        groups[name] = faces
        caps[name] = (cp, cb)
        log(name, rep)
    bm.normal_update()
    # record per-face group via int face layers (created before any cut)
    ids = {"body": 0, "magazine": 1, "charging_handle": 2, "trigger": 3}
    for f in bm.faces:
        f[lay] = 0
        f[capl] = 0
    for name, fs in groups.items():
        nv = sum(1 for f in fs if f.is_valid)
        log("group", name, len(fs), "valid", nv)
        for f in fs:
            if f.is_valid:
                f[lay] = ids[name]
    for name, (cp, cb) in caps.items():
        for f in cp + cb:
            if f.is_valid:
                f[capl] = 1
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = p.use_smooth  # keep flags
    report["minutes_cut"] = round((time.time() - t0) / 60, 2)
    return src, report

# ---------------------------------------------------------------- debug render (cut stage)
def setup_render(sc, w=1600, h=900):
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_backface_culling = True     # a hole must show background, not inner faces
    sh.show_specular_highlight = True
    sc.render.resolution_x = w; sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0.05, 0.055, 0.06)
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'Standard'

def get_cam(sc):
    cam = bpy.data.objects.get("ProofCam")
    if cam is None:
        cam = bpy.data.objects.new("ProofCam", bpy.data.cameras.new("ProofCam"))
        sc.collection.objects.link(cam)
    sc.camera = cam
    return cam

def aim(cam, loc, target, lens=50.0, ortho=None):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.data.clip_start = 0.005; cam.data.clip_end = 20

def color_parts(obj, mode="parts"):
    """Diagnostic materials by em_part / em_cap face attributes."""
    me = obj.data
    cols = [(0.62, 0.62, 0.6, 1), (0.85, 0.25, 0.2, 1), (0.2, 0.45, 0.9, 1), (0.2, 0.75, 0.3, 1), (0.95, 0.85, 0.1, 1)]
    mats = []
    for i, c in enumerate(cols):
        m = bpy.data.materials.get(f"dbg{i}") or bpy.data.materials.new(f"dbg{i}")
        m.diffuse_color = c
        mats.append(m)
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    part = me.attributes["em_part"].data
    cap = me.attributes["em_cap"].data
    for p in me.polygons:
        p.material_index = 4 if cap[p.index].value else part[p.index].value

def render_to(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

def composite(paths, out_path, w=1600, h=900):
    """Side-by-side two 800x900 renders into one 1600x900 PNG."""
    imgs = [bpy.data.images.load(p, check_existing=False) for p in paths]
    out = bpy.data.images.new("comp", w, h, alpha=False)
    import array
    buf = array.array('f', [0.0]) * (w * h * 4)
    x0 = 0
    for im in imgs:
        iw, ih = im.size
        px = array.array('f', [0.0]) * (iw * ih * 4)
        im.pixels.foreach_get(px)
        for y in range(ih):
            s = y * iw * 4
            d = (y * w + x0) * 4
            buf[d:d + iw * 4] = px[s:s + iw * 4]
        x0 += iw
    out.pixels.foreach_set(buf)
    out.filepath_raw = out_path
    out.file_format = 'PNG'
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)

# ---------------------------------------------------------------- rig / anim / export
BONES_DEFORM = ["body", "magazine", "charging_handle", "trigger"]
BONES_SOCKET = ["muzzle", "ejection_port", "sight", "grip_r", "grip_l", "mag_well"]
BONES_TARGET = ["hand_l_target"]    # non-deforming IK target for the body's left hand (palm centre), rest = grip_l
BONE_ORDER = ["root"] + BONES_DEFORM + BONES_SOCKET + BONES_TARGET
BONES_ANIMATED = ["root", "body", "magazine", "charging_handle", "trigger"] + BONES_TARGET   # keyed f0 + last frame of every clip
# Left-hand choreography constants, Blender metres: X forward, +Y = gun LEFT (UE -Y), Z up.
HAND_CUP_M = Vector((0.025, 0.03, -0.06))   # palm centre vs the magazine bone head: 2.5 cm fwd (curved mag), 3 cm left (1.6 half width + palm), 6 cm down
HAND_BELT_M = Vector((0.05, 0.12, -0.38))   # fresh-mag pick-up point, UE (+5, -12, -38) cm from grip_r: low and LEFT so the forearm stays clear
HAND_HK_M = Vector((0.0, 0.03, 0.025))      # palm vs the charging handle for the HK slap, UE (0, -3, +2.5): palm DOWN on the ring, 2.5 cm up so the hand sits on, not in, the handle (was +1 cm: fingers sank into the receiver, capture 2026-10-30)
HAND_TOUCH_M = Vector((0.01, 0.03, -0.02))  # mag-release touch vs the magazine head (left face, near the top)
MAG_DROP_M = -0.56                          # the empty mag free-falls this far (56 cm below the well) and is then hidden
MAG_HIDE_SCALE = 0.001
# ---- left-hand ORIENTATION / CURL (DESIGN B5). UE gun space: X fwd, Y right, Z up. The aim pose's hand at the
# support grip is the REST (identity delta); MEASURE 2026-10-30 (Scripts/MeasureHandAxes.py, Rifle stance, PIE):
REST_FINGER_UE = Vector((0.876, 0.477, -0.07))     # wrist -> middle_01_l: forward, leaning right (wrapping under the handguard)
REST_PALM_UE = Vector((-0.325, 0.692, 0.645))      # out of the palm (hand_l local -Y): right-and-up toward the barrel from under-left
# beat: (palm normal UE, finger direction UE, curl). The finger direction is re-projected perpendicular to the normal.
HAND_BEATS = {
    "rest": (REST_PALM_UE, REST_FINGER_UE, 1.0),
    "touch": (Vector((0, 1, 0)), REST_FINGER_UE, 1.0),            # mag release: palm toward +Y (the mag's left face), minimal twist of the fingers
    "belt": (Vector((0, 0.6, 0.8)), Vector((1, 0, 0)), 0.8),      # fresh-mag pick-up: palm up-inward, fingers forward, relaxed
    "grab": (Vector((0, 1, 0)), Vector((0.85, 0, -0.5)), 1.3),    # palm on the mag's left face, fingers forward-down wrapping its front, tight
    "slap": (Vector((0, 0, -1)), Vector((1, 0, 0)), 0.6),         # HK slap: palm DOWN on the ring handle, fingers forward, open-ish
}
HAND_BACK_T, HAND_BACK_CURL = 0.3, 0.9                           # f134 'back' = 30 % of the way from identity to the slap delta, curl 0.9
UE_MIRROR = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, 1)))           # Blender armature space <-> UE gun space (Blender -Y = UE +Y); self-inverse
PART_BONE = {0: "body", 1: "magazine", 2: "charging_handle", 3: "trigger"}
CLIPS = {  # name: last frame (clip spans 0..N at 60 fps, N/60 s)
    "Idle": 1, "Fire": 6, "DryFire": 9, "Reload": 144, "Chamber": 66,
}
# Convention copied from Scripts/Blender/RigM4A1.py (FBX_COMMON, bone axes, armature name),
# which its author verified in UE 5.8: Z-up FBX, default bone axes, identity-rest bones (+Y, roll 0),
# unit scale 1.0 + FBX_SCALE_NONE, armature OBJECT named 'Armature' so UE drops the Null.
ARMATURE_OBJECT_NAME = "Armature"
FBX_AXES = dict(axis_forward='-Y', axis_up='Z', primary_bone_axis='Y', secondary_bone_axis='X',
                use_space_transform=True, bake_space_transform=False, use_triangles=False,
                use_custom_props=False, use_metadata=True, colors_type='NONE')
EXPORT_CM_UNITS = False   # True = unit scale 0.01 export (node scale 1); off to match the M4A1

def src_to_final(p_cm, origin_cm):
    """source cm -> final Blender metres: grip_r at origin, muzzle +X (turn 180 about Z)."""
    d = (Vector(p_cm) - Vector(origin_cm)) * CFG["scale"]
    return Vector((-d.x, -d.y, d.z)) * 0.01

def to_ue_cm(v):
    return [round(v.x * 100, 3), round(-v.y * 100, 3), round(v.z * 100, 3)]

def landmarks(obj):
    """Measure socket/pivot positions on the cut mesh (source cm)."""
    me = obj.data
    part = [d.value for d in me.attributes["em_part"].data]
    cap = [d.value for d in me.attributes["em_cap"].data]
    V = [v.co * 100.0 for v in me.vertices]
    def cap_centroid(pid):
        vs = {vi for p in me.polygons if part[p.index] == pid and cap[p.index] for vi in p.vertices}
        return sum((V[i] for i in vs), Vector()) / len(vs)
    lm = {}
    mag_top = cap_centroid(1)
    lm["mag_top"] = Vector((mag_top.x, 0.0, mag_top.z))
    trig = cap_centroid(3)
    lm["trig_pivot"] = Vector((trig.x, 0.0, trig.z))
    ring = CFG["lever_ring"]
    lm["handle"] = Vector((ring[0], 0.0, ring[1]))
    mz = [v for v in V if v.x < CFG["muzzle_x"] + 0.4]
    lm["muzzle"] = Vector((min(v.x for v in V), (min(v.y for v in mz) + max(v.y for v in mz)) / 2,
                           (min(v.z for v in mz) + max(v.z for v in mz)) / 2))
    rs = [v for v in V if 3.0 < v.x < 9.0 and abs(v.y) < 1.0]
    lm["sight"] = Vector((CFG["sight"][0], 0.0, max(v.z for v in rs)))
    gl = [v for v in V if -10.0 < v.x < -8.0 and abs(v.y) < 0.5 and 9.0 < v.z < 13.0]
    lm["grip_l"] = Vector((CFG["grip_l"][0], 0.0, min(v.z for v in gl)))
    ej = [v for v in V if -3.0 < v.x < -1.0 and 13.5 < v.z < 15.0]
    lm["eject"] = Vector((CFG["eject"][0], max(v.y for v in ej), CFG["eject"][2]))
    gp = [v for v in V if v.x > 3.0 and 6.5 < v.z < 7.5]
    lm["grip_top"] = Vector((sum(v.x for v in gp) / len(gp), 0.0, CFG["grip_top"][2]))
    return lm

def build_armature(sc, obj, lm, origin):
    arm_data = bpy.data.armatures.new("EM_21_Skeleton")
    arm = bpy.data.objects.new(ARMATURE_OBJECT_NAME, arm_data)
    sc.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    for o in sc.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    heads = {
        "root": Vector(), "body": Vector(), "grip_r": Vector(),
        "magazine": src_to_final(lm["mag_top"], origin),
        "mag_well": src_to_final(lm["mag_top"], origin),
        "charging_handle": src_to_final(lm["handle"], origin),
        "trigger": src_to_final(lm["trig_pivot"], origin),
        "muzzle": src_to_final(lm["muzzle"], origin),
        "ejection_port": src_to_final(lm["eject"], origin),
        "sight": src_to_final(lm["sight"], origin),
        "grip_l": src_to_final(lm["grip_l"], origin),
        "hand_l_target": src_to_final(lm["grip_l"], origin),    # rest == grip_l: outside reloads the IK target is the support grip
    }
    lengths = {"root": 0.10, "body": 0.08}
    eb = {}
    for n in BONE_ORDER:
        b = arm_data.edit_bones.new(n)
        b.head = heads[n]
        L = lengths.get(n, 0.025)
        # M4A1 convention: Blender +Y with roll 0 = identity rest = UE bone X forward, Y right, Z up;
        # ejection_port points Blender +X so its UE bone X points out of the gun's right side
        b.tail = heads[n] + (Vector((L, 0, 0)) if n == "ejection_port" else Vector((0, L, 0)))
        b.roll = 0.0
        b.use_deform = n in BONES_DEFORM
        eb[n] = b
    eb["body"].parent = eb["root"]
    for n in BONES_DEFORM[1:] + BONES_SOCKET + BONES_TARGET:
        eb[n].parent = eb["root"] if n == "grip_r" else eb["body"]
    bpy.ops.object.mode_set(mode='OBJECT')
    # skin: rigid, one bone per vertex
    me = obj.data
    part = [d.value for d in me.attributes["em_part"].data]
    vpart = {}
    clash = 0
    for p in me.polygons:
        for vi in p.vertices:
            if vi in vpart and vpart[vi] != part[p.index]:
                clash += 1
            vpart[vi] = part[p.index]
    assert clash == 0, f"{clash} vertices shared between parts - split incomplete"
    for vg in list(obj.vertex_groups):
        obj.vertex_groups.remove(vg)
    groups = {n: obj.vertex_groups.new(name=n) for n in BONES_DEFORM}
    by = {n: [] for n in BONES_DEFORM}
    for vi in range(len(me.vertices)):
        by[PART_BONE[vpart.get(vi, 0)]].append(vi)
    for n, ids in by.items():
        groups[n].add(ids, 1.0, 'REPLACE')
    obj.parent = arm
    mod = obj.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    return arm, heads, {n: len(ids) for n, ids in by.items()}

def w2l(v):
    """world-space vector -> bone-local for a bone pointing +X with Z up (local X = -Y world)."""
    return Vector(v)          # identity-rest bones: pose space == armature space

def vec_b2ue(v):
    """Blender armature-space vector -> UE gun space (mirror Y); the same map goes back."""
    return UE_MIRROR @ Vector(v)

def quat_ue2b(q):
    """Rotation quaternion UE gun space <-> Blender armature space (involution).
    Derivation: the spaces differ by the reflection M = diag(1,-1,1) (M == M^-1, det -1). A rotation R expressed
    in UE space is M R M in Blender space; for R = (axis a, angle t) that is (axis M a, angle -t) because a
    reflection reverses the sense of every rotation. Quaternion (w, v) -> (w, -M v) = (w, -x, +y, -z). So +a deg
    about UE X == -a about Blender X, about UE Z == -a about Blender Z, about UE Y == -a about Blender -Y == +a
    about Blender Y. UE's FBX importer applies the same component map (FFbxDataConverter::ConvertRotToQuat:
    (x,-y,z,-w) == (-x,y,-z,w) up to the overall sign), so the UE bone track equals this script's UE-space intent.
    Verified numerically by check_rotation_convention() on every run."""
    return Quaternion((q.w, -q.x, q.y, -q.z))

quat_b2ue = quat_ue2b

def quat_canon(q):
    """Same rotation with w >= 0 so .axis/.angle report the short arc (angle in [0, 180])."""
    q = q.normalized()
    return Quaternion((-q.w, -q.x, -q.y, -q.z)) if q.w < 0 else q

def quat_delta_deg(a, b):
    return math.degrees(quat_canon(a.rotation_difference(b)).angle)

def check_rotation_convention():
    """Round-trip the Blender<->UE rotation map on test vectors; raises if the derivation is wrong."""
    M = UE_MIRROR
    tests = [((1, 0, 0), 30.0), ((0, 1, 0), 45.0), ((0, 0, 1), 60.0), ((0.3, -0.5, 0.8), 123.0), ((-0.7, 0.2, 0.1), -77.0)]
    vecs = [Vector((0.2, 0.7, -0.4)), Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-0.3, 0.9, 0.5))]
    worst = 0.0
    for ax, deg in tests:
        q_ue = Quaternion(Vector(ax).normalized(), math.radians(deg))   # rotation in UE space, standard quaternion maths (as FQuat)
        q_b = quat_ue2b(q_ue)
        R_b = (M @ q_ue.to_matrix() @ M)                                 # the same rotation conjugated into Blender space
        worst = max(worst, quat_delta_deg(q_b, R_b.to_quaternion()))
        worst = max(worst, quat_delta_deg(quat_b2ue(q_b), q_ue))         # involution
        for v_b in vecs:
            lhs = M @ (q_b @ v_b)                                        # rotate in Blender, then convert
            rhs = q_ue @ (M @ v_b)                                       # convert, then rotate in UE
            worst = max(worst, (lhs - rhs).length)
    # the three named claims: UE X +a == Blender X -a, UE Z +a == Blender Z -a, UE Y +a == Blender Y +a
    for ax, sgn in (((1, 0, 0), -1), ((0, 0, 1), -1), ((0, 1, 0), +1)):
        q_ue = Quaternion(Vector(ax), math.radians(40.0))
        worst = max(worst, quat_delta_deg(quat_ue2b(q_ue), Quaternion(Vector(ax), math.radians(sgn * 40.0))))
    assert worst < 1e-6, f"Blender<->UE rotation convention round-trip failed ({worst})"
    return worst

def hand_frame(finger, normal):
    """Right-handed 3x3 with columns (finger, side, palm normal); the finger is re-projected perpendicular to the normal."""
    n = Vector(normal).normalized()
    f = Vector(finger)
    f = (f - n * f.dot(n)).normalized()
    s = n.cross(f)
    return Matrix((f, s, n)).transposed()

def beat_quat_ue(name):
    """UE gun-space delta that turns the rest palm/finger frame into the beat's frame."""
    if name == "back":
        return quat_canon(Quaternion((1, 0, 0, 0)).slerp(beat_quat_ue("slap"), HAND_BACK_T))
    n, f, _c = HAND_BEATS[name]
    R0 = hand_frame(HAND_BEATS["rest"][1], HAND_BEATS["rest"][0])
    R1 = hand_frame(f, n)
    return quat_canon((R1 @ R0.transposed()).to_quaternion())

def beat_curl(name):
    return HAND_BACK_CURL if name == "back" else HAND_BEATS[name][2]

def beat_quat_b(name):
    return quat_ue2b(beat_quat_ue(name))

def beat_vectors_ue(name):
    """(finger, palm normal) in UE gun space after the beat's delta (what the palm proxy shows)."""
    q = beat_quat_ue(name)
    return q @ Vector(HAND_BEATS["rest"][1]).normalized(), q @ Vector(HAND_BEATS["rest"][0]).normalized()

def quat_report(q_ue):
    q = quat_canon(q_ue)
    return dict(ue_axis=[round(x, 3) for x in q.axis] if q.angle > 1e-9 else [0.0, 0.0, 0.0],
                ue_deg=round(math.degrees(q.angle), 2), ue_quat_wxyz=[round(x, 5) for x in q])

def set_interp(arm, bone, frame, interp, easing='AUTO', path_suffix=None):
    for fc in fcurves_of(arm.animation_data.action):
        if f'pose.bones["{bone}"]' not in fc.data_path:
            continue
        if path_suffix and not fc.data_path.endswith(path_suffix):
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.01:
                kp.interpolation = interp
                kp.easing = easing

def make_clip(arm, name, keys, n_frames, scale_keys=None):
    """keys: {bone: [(frame, loc_world_m or None, (axis_world, deg) | Quaternion(armature space) | None, interp, easing)]}
    scale_keys: {bone: [(frame, uniform_scale, interp[, easing])]} - keyed after loc/rot, interpolation set on the
    scale F-curves only (CONSTANT holds give the hidden-magazine hold; hand_l_target's uniform scale = finger curl,
    UE reads X). Every bone in BONES_TARGET also gets scale 1.0 at f0 and the last frame so the exporter bakes a
    rotation AND a scale track that start and end at identity / 1.0. Consecutive quaternion keys are sign-aligned
    (dot >= 0) so Blender's component-wise interpolation never spins the long way round."""
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    animated = list(BONES_ANIMATED)
    full = {b: [(0, None, None, 'BEZIER', 'AUTO'), (n_frames, None, None, 'BEZIER', 'AUTO')] for b in animated}
    for b, ks in keys.items():
        seen = {k[0]: k for k in full[b]}
        for k in ks:
            seen[k[0]] = k
        full[b] = [seen[f] for f in sorted(seen)]
    for b, ks in full.items():
        pb = arm.pose.bones[b]
        prev_q = None
        for (f, loc, rot, interp, easing) in ks:
            pb.location = w2l(loc if loc is not None else Vector())
            if isinstance(rot, Quaternion):
                q = rot.normalized()
            elif rot:
                ax, deg = rot
                q = Quaternion(w2l(Vector(ax)).normalized(), math.radians(deg))
            else:
                q = Quaternion((1, 0, 0, 0))
            if prev_q is not None and prev_q.dot(q) < 0.0:
                q = Quaternion((-q.w, -q.x, -q.y, -q.z))      # same rotation, short arc from the previous key
            prev_q = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("location", frame=f, group=b)
            pb.keyframe_insert("rotation_quaternion", frame=f, group=b)
    act = arm.animation_data.action
    act.name = f"A_EM21_{name}"
    for b, ks in full.items():
        for (f, loc, rot, interp, easing) in ks:
            set_interp(arm, b, f, interp, easing)
    sfull = {b: {0: (0, 1.0, 'BEZIER', 'AUTO'), n_frames: (n_frames, 1.0, 'BEZIER', 'AUTO')} for b in BONES_TARGET}
    for b, sks in (scale_keys or {}).items():
        d = sfull.setdefault(b, {})
        for k in sks:
            d[k[0]] = tuple(k) + (('AUTO',) if len(k) == 3 else ())
    for b, d in sfull.items():
        pb = arm.pose.bones[b]
        sks = [d[f] for f in sorted(d)]
        for (f, sv, interp, easing) in sks:
            pb.scale = (sv, sv, sv)
            pb.keyframe_insert("scale", frame=f, group=b)
        pb.scale = (1, 1, 1)
        for (f, sv, interp, easing) in sks:
            set_interp(arm, b, f, interp, easing, path_suffix=".scale")
    return act

def clip_keys(heads):
    """Per-clip key tuples (frame, pose location m, (axis, deg) or None, interp, easing). Identity-rest
    bones: pose location == armature-space offset from the rest head, so hand_l_target keys are
    H(world target) = target - grip_l head, magazine keys are offsets from the magazine head.
    Returns (keys, scale_keys)."""
    X = lambda x, z=0.0: Vector((x, 0, z))
    TR = (0, 1, 0)      # world +Y: positive angle swings the trigger blade rearward
    MR = (1, 0, 0)      # magazine roll about the bore axis
    B, A = 'BEZIER', 'AUTO'
    GL, MG, CH = heads["grip_l"], heads["magazine"], heads["charging_handle"]
    H = lambda p: Vector(p) - GL
    c = {"Idle": {}}
    c["Fire"] = {"trigger": [(0, None, None, B, A), (2, None, (TR, 8), B, A),
                             (4, None, (TR, 8), B, A), (6, None, None, B, A)]}
    c["DryFire"] = {"trigger": [(0, None, None, B, A), (3, None, (TR, 8), B, A),
                                (5, None, (TR, 8), B, A), (9, None, None, B, A)]}
    back, notch = -0.08, 0.006
    handle_back = CH + Vector((back, 0, notch))
    # Fresh magazine: pops in at the left hand at the belt on f75 (position = hand - cup offset), rides the
    # hand into the well (hand == mag + cup at every key, same interpolation -> same curve), seats f102.
    mag_rel = {75: HAND_BELT_M - HAND_CUP_M - MG, 88: Vector((0, 0, -0.105)), 96: Vector((0, 0, -0.012)),
               99: Vector((0, 0, 0.002)), 102: Vector()}
    carry_interp = {75: ('QUAD', 'EASE_OUT'), 88: ('QUAD', 'EASE_IN_OUT'), 96: ('LINEAR', A),
                    99: ('QUAD', 'EASE_OUT'), 102: (B, A)}
    carry_hand = lambda f: H(MG + mag_rel[f] + HAND_CUP_M)
    touch = H(MG + HAND_TOUCH_M)
    # Left-hand orientation / curl beats on the SAME frames (and interpolation) as the position keys: identity at
    # f0 and f144, touch f10-f25, belt f57 (relaxed, hand closes on the mag during the hold: grab by f75), carry
    # f75-f102, slap f108-f124, 'back' f134. f66 is a position HOLD key (same value as f57/f75) added for the belt.
    hand_beat = {0: "rest", 10: "touch", 20: "touch", 25: "touch", 57: "belt", 66: "belt", 75: "grab", 88: "grab",
                 96: "grab", 99: "grab", 102: "grab", 108: "slap", 116: "slap", 120: "slap", 124: "slap",
                 134: "back", 144: "rest"}
    RQ = {f: beat_quat_b(b) for f, b in hand_beat.items()}
    c["Reload"] = {
        "charging_handle": [
            (0, X(0), None, B, A),
            (12, X(back), None, B, A),                     # pulled back
            (18, X(back, notch), None, 'CONSTANT', A),     # up into the notch, bolt held open
            (116, X(back, notch), None, 'QUAD', 'EASE_IN'),  # HK slap: accelerates forward/down
            (120, X(0.004), None, B, A),                   # snaps just past rest
            (124, X(0), None, B, A),
        ],
        "magazine": [
            (0, X(0), None, B, A),
            (20, X(0), None, B, A),
            (25, Vector((0, 0, -0.006)), None, 'QUAD', 'EASE_IN'),        # release: drops by itself
            (57, Vector((0, 0, MAG_DROP_M)), (MR, 10), 'CONSTANT', A),    # 56 cm below the well, hidden (scale) and held
            (75, mag_rel[75], (MR, -6), *carry_interp[75]),               # pops in at the left hand at the belt
            (88, mag_rel[88], None, *carry_interp[88]),                   # lined up under the well
            (96, mag_rel[96], None, *carry_interp[96]),                   # entering the well
            (99, mag_rel[99], None, *carry_interp[99]),                   # seats with a snap
            (102, mag_rel[102], None, *carry_interp[102]),
        ],
        "hand_l_target": [
            (0, H(GL), RQ[0], B, A),                                      # support grip, identity orientation
            (10, H(Vector((0.13, 0.03, 0.005))), RQ[10], B, A),           # under/left of the handguard, palm already toward +Y
            (20, touch, RQ[20], 'LINEAR', A),                             # touches the mag release (mag left face), palm +Y
            (25, touch, RQ[25], B, A),
            (57, H(HAND_BELT_M), RQ[57], 'LINEAR', A),                    # down to the belt, palm up-inward, relaxed
            (66, H(HAND_BELT_M), RQ[66], B, A),                           # hold at the belt (position unchanged), hand starts closing on the mag
            (75, H(HAND_BELT_M), RQ[75], *carry_interp[75]),              # grab: fresh mag pops in here, palm on its left face, curl 1.3
            (88, carry_hand(88), RQ[88], *carry_interp[88]),              # mid-carry, grab orientation held
            (96, carry_hand(96), RQ[96], *carry_interp[96]),
            (99, carry_hand(99), RQ[99], *carry_interp[99]),
            (102, carry_hand(102), RQ[102], *carry_interp[102]),          # seated
            (108, H(handle_back + HAND_HK_M), RQ[108], 'LINEAR', A),      # up to the charging handle (in the notch), palm DOWN
            (116, H(handle_back + HAND_HK_M), RQ[116], 'QUAD', 'EASE_IN'),  # HK slap: rides the handle forward
            (120, H(CH + Vector((0.004, 0, 0)) + HAND_HK_M), RQ[120], B, A),
            (124, H(CH + HAND_HK_M), RQ[124], B, A),
            (134, H(Vector((0.13, 0.04, 0.015))), RQ[134], B, A),         # back under/left of the handguard, turning back
            (144, H(GL), RQ[144], B, A),                                  # support grip, identity
        ],
    }
    hand_interp = {k[0]: (k[3], k[4]) for k in c["Reload"]["hand_l_target"]}
    scales = {"Reload": {"magazine": [(0, 1.0, 'CONSTANT'), (57, MAG_HIDE_SCALE, 'CONSTANT'), (75, 1.0, B),
                                      (CLIPS["Reload"], 1.0, B)],
                         "hand_l_target": [(f, beat_curl(b), *hand_interp[f]) for f, b in sorted(hand_beat.items())]}}
    c["Reload"]["_hand_beats"] = hand_beat
    c["Chamber"] = {"charging_handle": [
        (0, X(0), None, B, A), (6, X(0), None, B, A),
        (22, X(back), None, B, A), (27, X(back), None, 'QUAD', 'EASE_IN'),
        (31, X(0.004), None, B, A), (35, X(0), None, B, A)]}
    return c, scales

def export_fbx(path, objs, anim):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True,
        object_types={o.type for o in objs},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', global_scale=1.0,
        use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=True,
        add_leaf_bones=False, use_armature_deform_only=False, armature_nodetype='NULL',
        bake_anim=anim, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
        path_mode='STRIP', embed_textures=False, batch_mode='OFF', **FBX_AXES)

def proof(sc, arm, act, frame, out_name, views, markers=(), placers=()):
    """views: [(view_fn(arm)->(loc, target, lens), width_px, frame_or_None)], widths sum to 1600.
    markers: [(object, bone)] - the object is moved to the bone's pose head at each rendered frame.
    placers: [fn(arm, sc, cam, frame)] - called after the camera is aimed (palm proxy, HUD text)."""
    arm.animation_data.action = act
    tmp = []
    for i, (fn, w, fr) in enumerate(views):
        f_now = frame if fr is None else fr
        sc.frame_set(f_now)
        for mo, bn in markers:
            mo.location = arm.matrix_world @ arm.pose.bones[bn].head
        loc, tgt, lens = fn(arm)
        sc.render.resolution_x = w; sc.render.resolution_y = 900
        cam = get_cam(sc)
        aim(cam, loc, tgt, lens=lens)
        for pl in placers:
            pl(arm, sc, cam, f_now)
        p = os.path.join(OUT, "_debug", f"_{out_name[:-4]}_{i}.png")
        render_to(sc, p)
        tmp.append(p)
    composite(tmp, os.path.join(OUT, out_name))

def make_marker(sc, name, radius_m, color):
    """Small shaded sphere (proof renders only; removed before export)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius_m)
    bm.to_mesh(me); bm.free()
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    return o

def _mat(name, color):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = color
    return m

def _box(sc, name, size, centre, color, back_color=None):
    """Axis-aligned box; with back_color every face except the local +Z one gets that second material."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(centre), verts=bm.verts)
    if back_color is not None:
        for f in bm.faces:
            f.material_index = 0 if f.normal.z > 0.5 else 1
    bm.to_mesh(me); bm.free()
    me.materials.append(_mat(name + "_mat", color))
    if back_color is not None:
        me.materials.append(_mat(name + "_back_mat", back_color))
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    return o

def make_palm_proxy(sc):
    """DESIGN B6 palm proxy, authored in a local frame X = finger direction, Y = across the palm, Z = palm normal:
    an 8 x 10 cm plate (10 along the fingers; ORANGE = palm side, dark brown = back of the hand), a 6 cm arrow
    from the finger edge along +X (on the palm side) and a 4 cm stick along +Z (out of the palm). Placed by
    place_palm_proxy from the keyed delta."""
    objs = [_box(sc, "PalmPlate", (0.10, 0.08, 0.004), (0, 0, 0), (0.95, 0.55, 0.10, 1.0), back_color=(0.30, 0.16, 0.05, 1.0)),
            _box(sc, "FingerArrowShaft", (0.045, 0.008, 0.006), (0.0725, 0, 0.005), (0.10, 0.60, 0.95, 1.0)),
            _box(sc, "PalmNormalStick", (0.006, 0.006, 0.04), (0, 0, 0.022), (0.20, 0.85, 0.30, 1.0))]
    me = bpy.data.meshes.new("FingerArrowHead")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=12, radius1=0.013, radius2=0.0, depth=0.02)
    bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(math.radians(90.0), 3, 'Y'), verts=bm.verts)  # +Z -> +X
    bmesh.ops.translate(bm, vec=Vector((0.10, 0, 0.005)), verts=bm.verts)
    bm.to_mesh(me); bm.free()
    me.materials.append(_mat("FingerArrowHead_mat", (0.10, 0.60, 0.95, 1.0)))
    o = bpy.data.objects.new("FingerArrowHead", me)
    sc.collection.objects.link(o)
    objs.append(o)
    cu = bpy.data.curves.new("ProofHud", type='FONT')
    cu.size = 0.011
    cu.materials.append(_mat("ProofHud_mat", (0.95, 0.95, 0.95, 1.0)))
    hud = bpy.data.objects.new("ProofHud", cu)
    sc.collection.objects.link(hud)
    return objs, hud

def rest_frame_b():
    """The aim pose's hand frame (finger, side, palm normal) expressed in Blender armature space."""
    return hand_frame(vec_b2ue(HAND_BEATS["rest"][1]), vec_b2ue(HAND_BEATS["rest"][0]))

def place_palm_proxy(objs, hud, bone="hand_l_target", lines=None):
    """Returns a placer: proxy = (pose rotation of the bone = keyed delta) x (rest hand frame) at the bone head;
    the HUD text sits in the camera's lower-left corner and names the frame, beat delta (UE axis-angle) and curl."""
    R_rest = rest_frame_b()
    def placer(arm, sc, cam, f):
        pb = arm.pose.bones[bone]
        pm = arm.matrix_world @ pb.matrix
        R_pose = pm.to_3x3().normalized()                      # delta from the identity rest (uniform curl scale removed)
        M = Matrix.Translation(pm.translation) @ (R_pose @ R_rest).to_4x4()
        for o in objs:
            o.matrix_world = M
        q_ue = quat_canon(quat_b2ue(R_pose.to_quaternion()))
        curl = pb.matrix.to_scale().x
        ax = q_ue.axis if q_ue.angle > 1e-6 else Vector((0, 0, 0))
        txt = f"f{f}  curl {curl:.2f}\ndelta {math.degrees(q_ue.angle):.0f} deg about UE ({ax.x:+.2f} {ax.y:+.2f} {ax.z:+.2f})"
        if lines:
            txt += "\n" + lines(f)
        hud.data.body = txt
        k = 50.0 / cam.data.lens                               # keep the same screen size / position for any lens
        hud.data.size = 0.011 * k
        # cam.matrix_world is stale right after aim() (no depsgraph update yet): build it from location/rotation
        cam_m = Matrix.Translation(cam.location) @ cam.rotation_euler.to_matrix().to_4x4()
        hud.matrix_world = cam_m @ Matrix.Translation(Vector((-0.090 * k, -0.085 * k, -0.30)))
    return placer

def to_cm_units(sc, arm, obj, acts, S=100.0):
    """Rescale mesh, bones and location keys by 100 and set unit scale 0.01 (same physical size)."""
    obj.data.transform(Matrix.Scale(S, 4))
    obj.data.update()
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in arm.data.edit_bones:
        h, t, r = eb.head.copy(), eb.tail.copy(), eb.roll
        eb.head = h * S; eb.tail = t * S; eb.roll = r
    bpy.ops.object.mode_set(mode='OBJECT')
    for act in acts.values():
        for fc in fcurves_of(act):
            if fc.data_path.endswith(".location"):
                for kp in fc.keyframe_points:
                    kp.co.y *= S; kp.handle_left.y *= S; kp.handle_right.y *= S
                fc.update()
    sc.unit_settings.scale_length = 1.0 / S

def hole_probe(sc, arm, act, frame, view_fn, points, radius_px, tag):
    """Render with a magenta world and count magenta pixels around projected cut locations.
    Backface culling is on, so any opening left by a cut shows the world colour."""
    from bpy_extras.object_utils import world_to_camera_view
    arm.animation_data.action = act
    sc.frame_set(frame)
    W = H = 600
    sc.render.resolution_x = W; sc.render.resolution_y = H
    old = tuple(sc.world.color)
    sc.world.color = (1.0, 0.0, 1.0)
    loc, tgt, lens = view_fn(arm)
    cam = get_cam(sc)
    aim(cam, loc, tgt, lens=lens)
    bpy.context.view_layer.update()
    path = os.path.join(OUT, "_debug", f"holeprobe_{tag}.png")
    render_to(sc, path)
    sc.world.color = old
    im = bpy.data.images.load(path, check_existing=False)
    px = list(im.pixels)
    out = []
    for pt in points:
        pw = pt(arm) if callable(pt) else pt
        c = world_to_camera_view(sc, cam, pw)
        cx, cy = c.x * W, c.y * H
        n = tot = 0
        for y in range(int(cy - radius_px), int(cy + radius_px) + 1):
            for x in range(int(cx - radius_px), int(cx + radius_px) + 1):
                if 0 <= x < W and 0 <= y < H and (x - cx) ** 2 + (y - cy) ** 2 <= radius_px ** 2:
                    i = (y * W + x) * 4
                    r, g, b = px[i], px[i + 1], px[i + 2]
                    tot += 1
                    if r - g > 0.3 and b - g > 0.3:          # magenta, any view transform
                        n += 1
        out.append(dict(screen=[round(cx), round(cy)], pixels=tot, magenta=n))
    bpy.data.images.remove(im)
    return out

def build_rest(sc, obj, report):
    T = {}
    t0 = time.time()
    conv_err = check_rotation_convention()
    log("rotation convention round-trip worst error", conv_err)
    lm = landmarks(obj)
    origin = lm["grip_top"]
    obj.data.transform(Matrix.Translation(-origin * 0.01 * CFG["scale"]))
    obj.data.transform(Matrix.Rotation(math.pi, 4, 'Z'))
    obj.data.update()
    xs = [v.co.x for v in obj.data.vertices]; ys = [v.co.y for v in obj.data.vertices]; zs = [v.co.z for v in obj.data.vertices]
    bounds = dict(min_cm=[round(min(a) * 100, 2) for a in (xs, ys, zs)], max_cm=[round(max(a) * 100, 2) for a in (xs, ys, zs)])
    length_cm = round((max(xs) - min(xs)) * 100, 2)
    log("length cm", length_cm, bounds)
    arm, heads, vcount = build_armature(sc, obj, lm, origin)
    T["rig"] = time.time() - t0; t0 = time.time()
    mat = obj.data.materials[0] if obj.data.materials else None
    if mat:
        mat.diffuse_color = (0.6, 0.6, 0.58, 1)
    acts = {}
    ck, cs = clip_keys(heads)
    hand_beat = ck["Reload"].pop("_hand_beats")
    for name, n in CLIPS.items():
        acts[name] = make_clip(arm, name, ck.get(name, {}), n, scale_keys=cs.get(name))
        acts[name].use_fake_user = True
    T["anim"] = time.time() - t0; t0 = time.time()
    # hand target vs the gun body: per-cm x-slice bounding boxes of the body part (final coords, cm);
    # the palm centre must never sit inside one (0.3 cm margin) on any Reload frame
    part_attr = [d.value for d in obj.data.attributes["em_part"].data]
    slices = {}
    for p in obj.data.polygons:
        if part_attr[p.index] != 0:
            continue
        for vi in p.vertices:
            q = obj.data.vertices[vi].co * 100
            sl = slices.setdefault(int(math.floor(q.x)), [1e9, -1e9, 1e9, -1e9])
            sl[0] = min(sl[0], q.y); sl[1] = max(sl[1], q.y); sl[2] = min(sl[2], q.z); sl[3] = max(sl[3], q.z)
    arm.animation_data.action = acts["Reload"]
    hand_path = []; pen = []
    for f in range(0, CLIPS["Reload"] + 1):
        sc.frame_set(f)
        h = arm.matrix_world @ arm.pose.bones["hand_l_target"].head
        hc = h * 100
        hand_path.append([f] + to_ue_cm(h))
        sl = slices.get(int(math.floor(hc.x)))
        if sl and sl[0] + 0.3 < hc.y < sl[1] - 0.3 and sl[2] + 0.3 < hc.z < sl[3] - 0.3:
            pen.append(f)
    report["hand_target_body_penetration_frames"] = pen
    assert not pen, f"hand_l_target inside the gun body on frames {pen}"
    # proofs: Workbench, backface culling ON so any hole shows background
    os.makedirs(os.path.join(OUT, "_debug"), exist_ok=True)
    setup_render(sc, 800, 900)
    sc.display.shading.color_type = 'SINGLE'
    sc.display.shading.single_color = (0.62, 0.62, 0.6)
    mw = heads["mag_well"]; tr = heads["trigger"]; ch = heads["charging_handle"]
    gun_c = Vector((0.12, 0, 0.0))
    low_c = Vector((0.085, 0, -0.05))
    def bone_head(a, n):
        return a.matrix_world @ a.pose.bones[n].head
    three_q = lambda a: (gun_c + Vector((0.30, -0.58, 0.19)), gun_c, 50)            # right three-quarter
    three_q_low = lambda a: (low_c + Vector((0.30, -0.56, 0.10)), low_c, 48)
    well_cu = lambda a: (mw + Vector((0.07, -0.14, -0.06)), mw + Vector((0, 0, -0.01)), 50)
    well_under = lambda a: (mw + Vector((0.06, -0.07, -0.13)), mw, 55)                # into the empty, capped well
    mag_top = lambda a: (bone_head(a, "magazine") + Vector((0.05, -0.08, 0.12)), bone_head(a, "magazine") + Vector((0, 0, -0.02)), 55)
    trig_cu = lambda a: (tr + Vector((0.0, -0.13, -0.012)), tr + Vector((0, 0, -0.012)), 75)
    handle_cu = lambda a: (ch + Vector((0.0, 0.19, 0.06)), ch + Vector((-0.04, 0, -0.005)), 45)
    proof(sc, arm, acts["Idle"], 0, "proof_rest.png", [(three_q, 800, None), (well_cu, 800, None)])
    proof(sc, arm, acts["Fire"], 3, "proof_fire.png",            # three-quarter | trigger rest | trigger fired
          [(three_q, 800, None), (trig_cu, 400, 0), (trig_cu, 400, None)])
    proof(sc, arm, acts["Reload"], 45, "proof_reload_mag_out.png",
          [(three_q_low, 800, None), (well_under, 400, None), (mag_top, 400, None)])
    proof(sc, arm, acts["Reload"], 102, "proof_reload_seat.png", [(three_q, 800, None), (well_cu, 800, None)])
    proof(sc, arm, acts["Chamber"], 24, "proof_chamber_back.png",
          [(three_q, 800, None), (handle_cu, 800, None)])
    proof(sc, arm, acts["Reload"], 65, "proof_reload_mag_hidden.png",     # empty mag gone (scale 0.001), well empty
          [(three_q_low, 800, None), (well_under, 800, None)])
    # left-hand target proofs (DESIGN B6): PALM PROXY at hand_l_target (palm centre): orange 8x10 plate in the palm
    # plane, blue 6 cm arrow = finger direction, green 4 cm stick = palm normal, rest frame from the MEASURE report
    # rotated by the keyed delta; HUD text = frame, delta (UE axis-angle), curl. MATERIAL colours, culling off so the
    # plate shows from either side.
    proxy, hud = make_palm_proxy(sc)
    beat_at = lambda f: "beat " + hand_beat[max(fb for fb in hand_beat if fb <= f)]
    placer = place_palm_proxy(proxy, hud, lines=lambda f: f"EM_21 Reload {beat_at(f)}")
    sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_backface_culling = False
    hand_wide = lambda a: (Vector((0.40, 0.60, 0.12)), Vector((0.08, 0.03, 0.01)), 40)               # left-front three-quarter
    hand_wide_low = lambda a: (Vector((0.42, 0.62, -0.04)), Vector((0.08, 0.05, -0.15)), 36)         # gun + belt
    hand_cu = lambda a: (bone_head(a, "hand_l_target") + Vector((0.21, 0.30, 0.105)), bone_head(a, "hand_l_target"), 50)    # 38 cm out: the 8x10 plate plus its surroundings
    hand_cu_r = lambda a: (bone_head(a, "hand_l_target") + Vector((0.24, -0.27, 0.135)), bone_head(a, "hand_l_target"), 50)  # from the gun's right: shows the palm side on the grab
    proof(sc, arm, acts["Reload"], 22, "proof_reload_hand_touch.png", [(hand_wide, 800, None), (hand_cu, 800, None)], placers=[placer])
    proof(sc, arm, acts["Reload"], 60, "proof_reload_hand_belt.png", [(hand_wide_low, 800, None), (hand_cu, 800, None)], placers=[placer])
    proof(sc, arm, acts["Reload"], 75, "proof_reload_hand_grab.png", [(hand_wide_low, 800, None), (hand_cu_r, 800, None)], placers=[placer])
    proof(sc, arm, acts["Reload"], 88, "proof_reload_hand_carry.png", [(hand_wide_low, 800, None), (hand_cu, 800, None)], placers=[placer])
    proof(sc, arm, acts["Reload"], 112, "proof_reload_hand_slap.png", [(hand_wide, 800, None), (hand_cu, 800, None)], placers=[placer])
    proof(sc, arm, acts["Reload"], 134, "proof_reload_hand_back.png", [(hand_wide, 800, None), (hand_cu, 800, None)], placers=[placer])
    sc.display.shading.color_type = 'SINGLE'
    for o in proxy + [hud]:
        d = o.data
        is_mesh = isinstance(d, bpy.types.Mesh)
        bpy.data.objects.remove(o)
        (bpy.data.meshes if is_mesh else bpy.data.curves).remove(d)
    # automatic see-through test at every cut (magenta world, backface culling)
    sc.display.shading.show_backface_culling = True
    hp = {}
    side_l = lambda a: (ch + Vector((0.0, 0.20, 0.0)), ch + Vector((0, 0, -0.01)), 50)
    side_r = lambda a: (ch + Vector((0.0, -0.20, 0.0)), ch + Vector((0, 0, -0.01)), 50)
    scar = [ch + Vector((0.0, 0.0, 0.0)), ch + Vector((0.0097, 0.0, -0.016))]
    hp["mag_well_empty"] = hole_probe(sc, arm, acts["Reload"], 45, well_under, [mw + Vector((0, 0, -0.005))], 25, "well")
    hp["mag_top_dropped"] = hole_probe(sc, arm, acts["Reload"], 45, mag_top, [lambda a: bone_head(a, "magazine")], 25, "magtop")
    hp["handle_scar_left"] = hole_probe(sc, arm, acts["Chamber"], 24, side_l, [p + Vector((0, 0.02, 0)) for p in scar], 12, "scar_l")
    hp["handle_scar_right"] = hole_probe(sc, arm, acts["Chamber"], 24, side_r, [p + Vector((0, -0.02, 0)) for p in scar], 12, "scar_r")
    hp["trigger_root_fired"] = hole_probe(sc, arm, acts["Fire"], 3, trig_cu, [tr + Vector((0, 0, 0.002))], 6, "trig")
    report["hole_probe"] = hp
    report["hole_probe_total_magenta"] = sum(r["magenta"] for v in hp.values() for r in v)
    # positive control: the open trigger guard in front of the blade MUST show the world colour
    ctl = hole_probe(sc, arm, acts["Idle"], 0, trig_cu, [tr + Vector((0.013, 0, -0.008))], 4, "control")
    report["hole_probe_control_guard_opening"] = ctl
    assert ctl[0]["magenta"] > 0, "hole probe control failed - probe cannot see background"
    assert report["hole_probe_total_magenta"] == 0, "see-through at a cut"
    log("hole probe", json.dumps(hp))
    T["proofs"] = time.time() - t0
    bones = {}
    for b in arm.data.bones:
        bones[b.name] = dict(parent=b.parent.name if b.parent else None, deform=b.use_deform,
                             head_blender_m=[round(x, 5) for x in b.head_local],
                             head_ue_cm=to_ue_cm(b.head_local), verts=vcount.get(b.name, 0))
    # ---- units: M4A1 convention = unit scale 1.0 + FBX_SCALE_NONE. The FBX then carries scale 100
    # on the 'Armature' Null and the mesh node with bone values in metres; UE drops the Null because
    # of its name. EXPORT_CM_UNITS=True switches to unit scale 0.01 (every node scale 1) instead.
    t0 = time.time()
    if EXPORT_CM_UNITS:
        to_cm_units(sc, arm, obj, acts)
    for a in ("em_part", "em_cap"):
        if a in obj.data.attributes:
            obj.data.attributes.remove(obj.data.attributes[a])
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    export_fbx(os.path.join(OUT, "SK_EM21.fbx"), [arm, obj], anim=False)
    for name, n in CLIPS.items():
        arm.animation_data.action = acts[name]
        sc.frame_start = 0; sc.frame_end = n
        sc.frame_set(0)     # bone node defaults in the FBX are written from the current pose: keep it at rest
        export_fbx(os.path.join(OUT, f"A_EM21_{name}.fbx"), [arm, obj], anim=True)
    sc.frame_start = 0; sc.frame_end = 144
    arm.animation_data.action = acts["Idle"]
    T["export"] = time.time() - t0
    hi = {k[0]: (k[3], k[4]) for k in ck["Reload"]["hand_l_target"]}
    for f, b in sorted(hand_beat.items()):
        r = quat_report(beat_quat_ue(b))
        log(f"hand beat f{f:3d} {b:5s}: UE axis {r['ue_axis']} {r['ue_deg']:6.1f} deg, curl {beat_curl(b):.2f}")
    rig = dict(
        gun="EM_21", source=SRC, skeleton="EM_21_Skeleton", armature_object_name=ARMATURE_OBJECT_NAME, fps=FPS,
        convention="Matches Scripts/Blender/RigM4A1.py. UE: X forward (muzzle +X), Y right, Z up; origin = grip_r "
                   "(pistol-grip top, centre line). Blender: muzzle +X, gun right side -Y, unit scale 1.0 (1 m = 100 UU). "
                   "FBX: axis_forward -Y / up Z, primary bone Y / secondary X, no leaf bones, FBX_SCALE_NONE, "
                   "use_tspace, mesh included in every clip file (UE 5.8 Interchange).",
        bone_orientation="every bone has identity rest (Blender +Y, roll 0 -> UE bone X fwd, Y right, Z up) except "
                         "ejection_port (Blender +X -> UE bone X out of the right side); charging_handle slides along "
                         "-X, magazine drops along -Z with roll about X (and scales to 0.001 while hidden), trigger "
                         "rotates about +Y (blade rearward); hand_l_target translates, ROTATES (delta from the aim pose's "
                         "hand, identity rest) and carries the finger curl as its uniform bone scale (UE reads X).",
        export_cm_units=EXPORT_CM_UNITS,
        scale_factor=CFG["scale"],
        scale_note="FBX is authored in cm (Blender importer gives the object 0.01 scale). The inch hypothesis "
                   "(x2.54) is rejected: 34.22 raw units -> 86.9 cm. Real MP5K is 32.5 x 21 x 5 cm; this mesh is "
                   "34.2 x 21.1 x 5.3 cm at 1:1 (incl. suppressor box). Pack check: EM_13 bolt-action = 119.7 cm.",
        length_cm=length_cm, bounds=bounds, bones=bones,
        sockets={n: bones[n]["head_ue_cm"] for n in BONES_SOCKET},
        hand_target=dict(
            bone="hand_l_target", parent="body", deform=False,
            meaning="PALM CENTRE target for the body's left hand (the support IK subtracts half the wrist->middle_01 "
                    "offset). Rest == grip_l head, so outside Reload the IK target equals the support grip. Keyed in "
                    "Reload only (f0 and f144 exactly at grip_l); Idle/Fire/DryFire/Chamber hold the rest pose. "
                    "ROTATION (DESIGN B1/B5) = delta from the aim pose's hand orientation (identity at f0/end); the "
                    "C++ applies D = WeaponRotation * socket rotation * WeaponRotation^-1 to hand_l after the IK. "
                    "SCALE (uniform; UE reads the bone-local X) = finger curl: 1.0 aim-pose fingers, 0 open, 1.6 tightest.",
            rotation_convention=dict(
                ue_from_blender_quat="(w, x, y, z)_blender -> (w, -x, y, -z)_ue; involution; = conjugation by the Y mirror",
                ue_axis_claims="+a about UE X == -a about Blender X; +a about UE Z == -a about Blender Z; +a about UE Y == +a about Blender Y",
                round_trip_worst_error=conv_err),
            rest_hand_frame_ue=dict(finger_dir=[round(x, 3) for x in HAND_BEATS["rest"][1]],
                                    palm_normal=[round(x, 3) for x in HAND_BEATS["rest"][0]],
                                    source="MEASURE 2026-10-30 Rifle stance (Scripts/MeasureHandAxes.py)"),
            beats={b: dict(palm_normal_ue=[round(x, 3) for x in beat_vectors_ue(b)[1]],
                           finger_dir_ue=[round(x, 3) for x in beat_vectors_ue(b)[0]], curl=beat_curl(b),
                           **quat_report(beat_quat_ue(b))) for b in ("rest", "touch", "belt", "grab", "slap", "back")},
            rotation_keys=[dict(frame=f, beat=b, interp=hi[f][0], easing=hi[f][1],
                                blender_quat_wxyz=[round(x, 5) for x in beat_quat_b(b)], **quat_report(beat_quat_ue(b)))
                           for f, b in sorted(hand_beat.items())],
            curl_keys=[dict(frame=f, beat=b, curl=beat_curl(b), interp=hi[f][0], easing=hi[f][1])
                       for f, b in sorted(hand_beat.items())],
            max_consecutive_key_delta_deg=round(max(quat_delta_deg(beat_quat_ue(a), beat_quat_ue(b)) for a, b in
                                                    zip([v for _f, v in sorted(hand_beat.items())][:-1],
                                                        [v for _f, v in sorted(hand_beat.items())][1:])), 2),
            rest_ue_cm=bones["grip_l"]["head_ue_cm"],
            cup_offset_blender_m=[round(x, 4) for x in HAND_CUP_M], cup_offset_ue_cm=to_ue_cm(HAND_CUP_M),
            belt_blender_m=[round(x, 4) for x in HAND_BELT_M], belt_ue_cm=to_ue_cm(HAND_BELT_M),
            hk_offset_ue_cm=to_ue_cm(HAND_HK_M), touch_offset_ue_cm=to_ue_cm(HAND_TOUCH_M),
            hk_offset_note="palm centre 2.5 cm above the ring handle (was 1.0): palm-down slap sits on the handle, fingers clear the receiver",
            release_touch_frames=[20, 25], belt_frames=[57, 75], grab_frame=75, mid_carry_frame=88, seat_frame=102,
            hk_slap_frames=[108, 124], carry_frames=[75, 102],
            reload_keys_ue_cm=[dict(frame=f, pos=to_ue_cm(heads["grip_l"] + loc), interp=i, easing=e)
                               for (f, loc, _r, i, e) in ck["Reload"]["hand_l_target"]],
            reload_path_ue_cm=hand_path,
            body_penetration_frames=pen),
        magazine_reload=dict(
            release_frame=25, drop_cm=round(MAG_DROP_M * 100, 2), drop_end_frame=57,
            hidden_frames=[57, 74], hide_scale=MAG_HIDE_SCALE, pop_in_frame=75,
            pop_in_ue_cm=to_ue_cm(heads["magazine"] + [k for k in ck["Reload"]["magazine"] if k[0] == 75][0][1]),
            seat_frame=102,
            note="the empty mag drops by itself (SMG), is hidden by bone scale 0.001 from f57 and pops in at the "
                 "left hand at the belt on f75 (position = hand target - cup offset); it never rises from below the hand",
            scale_keys=[dict(frame=f, scale=sv, interp=i) for (f, sv, i) in cs["Reload"]["magazine"]]),
        cut=report,
        clips={f"A_EM21_{n}": dict(frames=f + 1, seconds=round(f / FPS, 4), keyed_bones=sorted(ck.get(n, {}).keys()))
               for n, f in CLIPS.items()},
        minutes=dict(cut=report.get("minutes_cut"), **{k: round(v / 60, 2) for k, v in T.items()}),
        landmarks_source_cm={k: [round(x, 3) for x in v] for k, v in lm.items()},
    )
    json.dump(rig, open(os.path.join(OUT, "em21_rig.json"), "w"), indent=1)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "EM_21_rig.blend"))
    log("build done", json.dumps(rig["minutes"]))
    r = subprocess.run([bpy.app.binary_path, "-b", "--python", os.path.abspath(__file__), "--", "--verify"],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "[EM21]" in line:
            print(line)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("verify failed")

# ---------------------------------------------------------------- verify (fresh scene)
def verify():
    rig = json.load(open(os.path.join(OUT, "em21_rig.json")))
    res = {"pass": [], "rotation_convention_round_trip_error": check_rotation_convention()}
    fails = []
    def check(cond, msg):
        (res["pass"] if cond else fails).append(msg)
    def imp(path):
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False,
                                 primary_bone_axis='Y', secondary_bone_axis='X',
                                 axis_forward='-Y', axis_up='Z')
        return [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    # raw FBX header / node checks (what UE will read)
    from io_scene_fbx import parse_fbx
    def child(e, name):
        for c in e.elems:
            if c.id == name.encode():
                return c
    res["fbx_nodes"] = {}
    for fn in ["SK_EM21.fbx"] + [f"A_EM21_{n}.fbx" for n in CLIPS]:
        root, _ = parse_fbx.parse(os.path.join(OUT, fn))
        g = {p.props[0].decode(): p.props[-1] for p in child(child(root, "GlobalSettings"), "Properties70").elems}
        check(abs(g["UnitScaleFactor"] - 1.0) < 1e-6, f"{fn}: UnitScaleFactor {g['UnitScaleFactor']} (cm)")
        objs_ = {m.props[1].split(b"\x00")[0].decode() for m in child(root, "Objects").elems if m.id == b"Model"}
        if fn != "SK_EM21.fbx":
            check("SK_EM21" in objs_, f"{fn}: carries the mesh (UE 5.8 Interchange needs it)")
        check(abs(g.get("CustomFrameRate", 0) - FPS) < 1e-6, f"{fn}: frame rate {g.get('CustomFrameRate')}")
        scales = {}
        for m in child(root, "Objects").elems:
            if m.id != b"Model":
                continue
            nm = m.props[1].split(b"\x00")[0].decode()
            sc_ = [1.0, 1.0, 1.0]
            p70 = child(m, "Properties70")
            for p in (p70.elems if p70 else []):
                if p.props[0] == b"Lcl Scaling":
                    sc_ = list(p.props[-3:])
            scales[nm] = sc_
        bad = {k: v for k, v in scales.items() if k in BONE_ORDER and max(abs(x - 1.0) for x in v) > 1e-5}
        check(not bad, f"{fn}: every bone node scale 1 {bad}")
        res.setdefault("fbx_non_bone_node_scales", {})[fn] = {k: v for k, v in scales.items() if k not in BONE_ORDER}
        res["fbx_nodes"][fn] = sorted(scales)
    sc = reset()
    arm = imp(os.path.join(OUT, "SK_EM21.fbx"))
    mesh = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    W = [mesh.matrix_world @ v.co * 100 for v in mesh.data.vertices]
    mn = [min(p[i] for p in W) for i in range(3)]; mx = [max(p[i] for p in W) for i in range(3)]
    L = mx[0] - mn[0]
    res["sk_bounds_cm"] = [[round(x, 2) for x in mn], [round(x, 2) for x in mx]]
    res["sk_length_cm"] = round(L, 2)
    res["armature_object"] = dict(name=arm.name, scale=[round(s, 5) for s in arm.scale])
    check(abs(L - rig["length_cm"]) < 0.2, f"SK length {L:.2f} cm == {rig['length_cm']}")
    check(all(abs(a - b) < 0.2 for a, b in zip(mn + mx, rig["bounds"]["min_cm"] + rig["bounds"]["max_cm"])), "SK bounds match build")
    check(mx[0] > 20 and mn[0] < 0, "muzzle on +X, grip origin inside the gun")
    names = sorted(b.name for b in arm.data.bones)
    res["bones"] = names
    check(names == sorted(BONE_ORDER), f"bone list {names}")
    check("hand_l_target" in names, "hand_l_target present in SK")
    if "hand_l_target" in names:
        hb = arm.data.bones["hand_l_target"]
        check(hb.parent is not None and hb.parent.name == "body", "hand_l_target parented to body")
        dgl = (hb.head_local - arm.data.bones["grip_l"].head_local).length * 100
        check(dgl < 0.3, f"hand_l_target rest at grip_l ({dgl:.3f} cm)")
    for b in arm.data.bones:
        hw = (arm.matrix_world @ b.head_local) * 100
        exp = Vector(rig["bones"][b.name]["head_blender_m"]) * 100
        d = (hw - exp).length
        check(d < 0.05, f"bone {b.name} head within {d:.3f} cm of build")
        rot = arm.matrix_world.to_3x3().normalized() @ b.matrix_local.to_3x3()
        yax, zax = rot.col[1].normalized(), rot.col[2].normalized()
        if b.name == "ejection_port":
            check(yax.x > 0.999, f"bone {b.name} points Blender +X (UE: out of the right side)")
        else:
            check(yax.y > 0.999 and zax.z > 0.999, f"bone {b.name} identity rest (Blender +Y, roll 0)")
    bad = 0
    for v in mesh.data.vertices:
        gs = [g for g in v.groups if g.weight > 0]
        if len(gs) != 1 or abs(gs[0].weight - 1.0) > 1e-4:
            bad += 1
    check(bad == 0, f"rigid skin: {bad} vertices not exactly one bone at 1.0")
    vg = {mesh.vertex_groups[g.group].name for v in mesh.data.vertices for g in v.groups}
    check(vg == set(BONES_DEFORM), f"weighted bones {sorted(vg)}")
    res["sk_verts"] = len(mesh.data.vertices)
    res["sk_tris"] = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    res["sk_materials"] = [m.name for m in mesh.data.materials]
    sk_rest = {b.name: arm.matrix_world @ b.matrix_local for b in arm.data.bones}
    expect = {"Idle": {}, "Fire": dict(trig=8.0), "DryFire": dict(trig=8.0),
              "Reload": dict(mag_dz=round(MAG_DROP_M * 100, 2), handle_dx=-8.0), "Chamber": dict(handle_dx=-8.0)}
    res["clips"] = {}
    for name, n in CLIPS.items():
        sc = reset()
        arm = imp(os.path.join(OUT, f"A_EM21_{name}.fbx"))
        act = arm.animation_data.action if arm.animation_data else None
        check(act is not None, f"{name}: has action")
        f0, f1 = act.frame_range
        frames = int(round(f1 - f0)) + 1
        secs = (f1 - f0) / sc.render.fps
        check(frames == n + 1 and abs(secs - n / FPS) < 1e-3, f"{name}: {frames} frames, {secs:.3f} s at {sc.render.fps} fps")
        own = {b.name: arm.matrix_world @ b.matrix_local for b in arm.data.bones}
        rdiff = max((own[k].translation - sk_rest[k].translation).length * 100 for k in own)
        adiff = max(math.degrees(own[k].to_quaternion().rotation_difference(sk_rest[k].to_quaternion()).angle) for k in own)
        check(rdiff < 0.01 and adiff < 0.01, f"{name}: file rest pose == SK rest ({rdiff:.4f} cm, {adiff:.4f} deg)")
        rest = sk_rest      # measure motion against the skeletal mesh's bind pose
        stats = {b: dict(max_disp=0.0, min_dz=0.0, min_dx=0.0, max_ang=0.0) for b in rest}
        for f in range(int(round(f0)), int(round(f1)) + 1):
            sc.frame_set(f)
            for pb in arm.pose.bones:
                m = arm.matrix_world @ pb.matrix
                d = (m.translation - rest[pb.name].translation) * 100
                s = stats[pb.name]
                s["max_disp"] = max(s["max_disp"], d.length)
                s["min_dz"] = min(s["min_dz"], d.z); s["min_dx"] = min(s["min_dx"], d.x)
                q = rest[pb.name].to_quaternion().rotation_difference(m.to_quaternion())
                s["max_ang"] = max(s["max_ang"], math.degrees(q.angle))
        sc.frame_set(int(round(f1)))
        end_disp = max(((arm.matrix_world @ pb.matrix).translation - rest[pb.name].translation).length * 100 for pb in arm.pose.bones)
        e = expect[name]
        mov = {b: {k: round(v, 3) for k, v in s.items()} for b, s in stats.items() if s["max_disp"] > 1e-3 or s["max_ang"] > 1e-2}
        res["clips"][name] = dict(frames=frames, seconds=round(secs, 4), moving=mov, end_disp_cm=round(end_disp, 4))
        check(stats["root"]["max_disp"] < 1e-3 and stats["root"]["max_ang"] < 1e-2, f"{name}: root still")
        check(stats["body"]["max_disp"] < 1e-3 and stats["body"]["max_ang"] < 1e-2, f"{name}: body still")
        check(end_disp < 1e-3, f"{name}: ends at rest ({end_disp:.4f} cm)")
        if "trig" in e:
            check(abs(stats["trigger"]["max_ang"] - e["trig"]) < 0.1, f"{name}: trigger {stats['trigger']['max_ang']:.2f} deg")
            check(set(mov) == {"trigger"}, f"{name}: only trigger moves {sorted(mov)}")
        if "mag_dz" in e:
            check(abs(stats["magazine"]["min_dz"] - e["mag_dz"]) < 0.1, f"{name}: magazine drops {stats['magazine']['min_dz']:.2f} cm")
        if "handle_dx" in e:
            check(abs(stats["charging_handle"]["min_dx"] - e["handle_dx"]) < 0.1, f"{name}: handle back {stats['charging_handle']['min_dx']:.2f} cm")
        for f in (int(round(f0)), int(round(f1))):
            sc.frame_set(f)
            pb = arm.pose.bones["hand_l_target"]
            a = math.degrees(quat_canon((arm.matrix_world @ pb.matrix).to_3x3().normalized().to_quaternion()).angle)
            sx = pb.matrix.to_scale().x
            check(a < 2.0 and abs(sx - 1.0) < 0.02, f"{name}: hand_l_target identity / scale 1 at scene frame {f} ({a:.3f} deg, {sx:.4f})")
        if name == "Idle":
            check(not mov, f"Idle: nothing moves {sorted(mov)}")
        if name == "Chamber":
            check(set(mov) == {"charging_handle"}, f"Chamber: only handle moves {sorted(mov)}")
        if name == "Reload":
            check(set(mov) == {"charging_handle", "magazine", "hand_l_target"}, f"Reload: handle+mag+hand move {sorted(mov)}")
            ht = rig["hand_target"]; mr = rig["magazine_reload"]
            cup = Vector(ht["cup_offset_blender_m"]) * 100
            off = int(round(f0))    # the FBX importer puts FBX time 0 at scene frame f0 (1): source frame f == scene frame f + off
            last = CLIPS[name]
            def F(f):
                sc.frame_set(f + off)
            def P(b):
                return (arm.matrix_world @ arm.pose.bones[b].matrix).translation * 100
            def S(b):
                return sum(arm.pose.bones[b].matrix.to_scale()) / 3.0
            for f in (0, last):
                F(f)
                d = (P("hand_l_target") - P("grip_l")).length
                check(d < 0.3, f"Reload: hand_l_target at grip_l on f{f} ({d:.3f} cm)")
            for f, tag in ((ht["grab_frame"], "grab"), (ht["mid_carry_frame"], "mid-carry"), (ht["seat_frame"], "seat")):
                F(f)
                d = (P("hand_l_target") - P("magazine") - cup).length
                check(d < 2.0, f"Reload: hand_l_target within 2 cm of magazine+cup at {tag} f{f} ({d:.3f} cm)")
            F(ht["grab_frame"])
            d = (P("hand_l_target") - Vector(ht["belt_blender_m"]) * 100).length
            check(d < 0.3, f"Reload: hand at the belt on the grab frame ({d:.3f} cm)")
            check(stats["hand_l_target"]["max_disp"] > 35.0, f"Reload: hand reaches the belt ({stats['hand_l_target']['max_disp']:.1f} cm)")
            # ---- orientation (delta from the identity rest, reported in UE gun space) and curl (uniform scale, UE reads X)
            def Q_ue(b):
                q = (arm.matrix_world @ arm.pose.bones[b].matrix).to_3x3().normalized().to_quaternion()
                return quat_canon(quat_b2ue(q))
            def SX(b):
                return arm.pose.bones[b].matrix.to_scale().x
            for f in (0, last):
                F(f)
                a = math.degrees(Q_ue("hand_l_target").angle)
                check(a < 2.0, f"Reload: hand_l_target rotation identity on f{f} ({a:.3f} deg)")
                sx = SX("hand_l_target")
                check(abs(sx - 1.0) < 0.02, f"Reload: hand_l_target scale 1.0 on f{f} ({sx:.4f})")
            prev = None; worst_step = 0.0; bad_scale = []; finite = True
            for f in range(0, last + 1):
                F(f)
                sx = SX("hand_l_target")
                if not (0.4 <= sx <= 1.6):
                    bad_scale.append(f)
                if f % 6 == 0:
                    q = Q_ue("hand_l_target")
                    if not all(math.isfinite(x) for x in q):
                        finite = False
                    if prev is not None:
                        worst_step = max(worst_step, quat_delta_deg(prev, q))
                    prev = q
            check(finite, "Reload: hand_l_target rotation finite on every 6th frame")
            check(worst_step < 150.0, f"Reload: hand_l_target consecutive sampled rotation deltas < 150 deg (max {worst_step:.1f})")
            check(not bad_scale, f"Reload: hand_l_target curl within [0.4, 1.6] on every frame {bad_scale}")
            measured_rot, measured_curl = [], []
            worst_rot = worst_curl = 0.0
            for rk, ckey in zip(ht["rotation_keys"], ht["curl_keys"]):
                F(rk["frame"])
                q = Q_ue("hand_l_target")
                q_auth = Quaternion(rk["ue_quat_wxyz"])
                d = quat_delta_deg(q, q_auth)
                sx = SX("hand_l_target")
                worst_rot = max(worst_rot, d); worst_curl = max(worst_curl, abs(sx - ckey["curl"]))
                r = quat_report(q)
                measured_rot.append(dict(frame=rk["frame"], beat=rk["beat"], **r, vs_authored_deg=round(d, 3)))
                measured_curl.append(dict(frame=rk["frame"], beat=rk["beat"], curl=round(sx, 4), vs_authored=round(sx - ckey["curl"], 4)))
                log(f"beat f{rk['frame']:3d} {rk['beat']:5s}: rotation UE axis {r['ue_axis']} {r['ue_deg']:6.1f} deg "
                    f"(authored {rk['ue_deg']:.1f}, diff {d:.2f}), curl {sx:.3f} (authored {ckey['curl']:.2f})")
            check(worst_rot < 1.0, f"Reload: re-imported hand rotation matches the authored beats (worst {worst_rot:.3f} deg)")
            check(worst_curl < 0.02, f"Reload: re-imported curl matches the authored beats (worst {worst_curl:.4f})")
            res["clips"][name]["hand_rotation_keys_measured"] = measured_rot
            res["clips"][name]["hand_curl_keys_measured"] = measured_curl
            res["clips"][name]["hand_rotation_max_step_deg"] = round(worst_step, 2)
            for rk, m in zip(ht["rotation_keys"], measured_rot):
                rk["verified_ue_axis"], rk["verified_ue_deg"] = m["ue_axis"], m["ue_deg"]
            for ckey, m in zip(ht["curl_keys"], measured_curl):
                ckey["verified_curl"] = m["curl"]
            ht["verified_max_consecutive_sampled_delta_deg"] = round(worst_step, 2)
            res["clips"][name]["hand_rot_path_ue"] = []
            for f in range(0, last + 1, 6):
                F(f)
                r = quat_report(Q_ue("hand_l_target"))
                res["clips"][name]["hand_rot_path_ue"].append([f, r["ue_axis"], r["ue_deg"], round(SX("hand_l_target"), 3)])
            hidden = (mr["hidden_frames"][0] + mr["hidden_frames"][1]) // 2
            F(0); s0 = S("magazine")
            F(hidden); sm = S("magazine")
            F(mr["pop_in_frame"]); sp = S("magazine"); mag_pop = P("magazine")
            F(last); s1 = S("magazine")
            check(abs(s0 - 1) < 1e-3 and abs(s1 - 1) < 1e-3, f"Reload: magazine scale 1 at f0/end ({s0:.4f}, {s1:.4f})")
            check(sm < 0.01, f"Reload: magazine hidden mid-hold f{hidden} (scale {sm:.4f})")
            check(abs(sp - 1) < 1e-3, f"Reload: magazine visible on pop-in f{mr['pop_in_frame']} (scale {sp:.4f})")
            dpop = (mag_pop - Vector(ht["belt_blender_m"]) * 100 + cup).length
            check(dpop < 0.3, f"Reload: magazine pops in at hand - cup ({dpop:.3f} cm)")
            # never a visible mag rising from below the hand: on every visible frame after the drop the
            # fresh mag is within cup reach of the hand
            bad_rise = []
            for f in range(mr["release_frame"], last + 1):
                F(f)
                if S("magazine") < 0.5 or f <= mr["drop_end_frame"]:
                    continue
                if (P("magazine") + cup - P("hand_l_target")).length > 2.0 and f <= mr["seat_frame"]:
                    bad_rise.append(f)
            check(not bad_rise, f"Reload: fresh mag always in the hand after pop-in {bad_rise}")
            res["clips"][name]["hand_path_ue_cm"] = []
            for f in range(0, last + 1, 4):
                F(f)
                res["clips"][name]["hand_path_ue_cm"].append([f] + to_ue_cm(P("hand_l_target") / 100))
    res["fails"] = fails
    res["n_pass"] = len(res["pass"])
    json.dump(res, open(os.path.join(OUT, "em21_verify.json"), "w"), indent=1)
    json.dump(rig, open(os.path.join(OUT, "em21_rig.json"), "w"), indent=1)   # carries the verified rotation/curl values
    log("VERIFY", "PASS" if not fails else "FAIL", res["n_pass"], "checks passed,", len(fails), "failed")
    for f in fails:
        log("  FAIL", f)
    if fails:
        raise SystemExit(2)

# ---------------------------------------------------------------- main
def main():
    args = argv_after()
    os.makedirs(OUT, exist_ok=True)
    if "--verify" in args:
        return verify()
    stage = args[args.index("--stage") + 1] if "--stage" in args else "all"
    sc = reset()
    obj, report = import_and_cut()
    if stage == "cut":
        dbg = os.path.join(OUT, "_debug"); os.makedirs(dbg, exist_ok=True)
        color_parts(obj)
        setup_render(sc)
        sc.display.shading.color_type = 'MATERIAL'
        cam = get_cam(sc)
        views = {
            "left": ((-0.02, -0.6, 0.12), (-0.02, 0, 0.12), 0.30),
            "right": ((-0.02, 0.6, 0.12), (-0.02, 0, 0.12), 0.30),
            "lever_l": ((-0.015, -0.4, 0.165), (-0.015, 0, 0.155), 0.07),
            "trig": ((0.015, 0.4, 0.09), (0.015, 0, 0.09), 0.06),
            "under": ((-0.03, 0.0, -0.5), (-0.03, 0.0, 0.1), 0.2),
        }
        for k, (loc, tgt, os_) in views.items():
            aim(cam, loc, tgt, ortho=os_)
            render_to(sc, os.path.join(dbg, f"cut_{k}.png"))
        # mag pulled down 6 cm and lever pushed sideways to expose the caps
        me = obj.data
        part = me.attributes["em_part"].data
        offs = {1: Vector((0, 0, -0.06)), 2: Vector((0.0, 0, 0.0)), 3: Vector((0, 0, 0))}
        vpart = {}
        for p in me.polygons:
            for vi in p.vertices:
                vpart[vi] = part[p.index].value
        for vi, pi in vpart.items():
            if pi == 1:
                me.vertices[vi].co += offs[1]
            if pi == 2:
                me.vertices[vi].co += Vector((0.06, 0, 0))
        aim(cam, (0.25, 0.35, -0.15), (-0.03, 0, 0.07), lens=60)
        render_to(sc, os.path.join(dbg, "cut_exploded_r.png"))
        aim(cam, (0.2, -0.35, 0.05), (0.0, 0, 0.12), lens=55)
        render_to(sc, os.path.join(dbg, "cut_exploded_l.png"))
        json.dump(report, open(os.path.join(dbg, "cut_report.json"), "w"), indent=1)
        return
    build_rest(sc, obj, report)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
