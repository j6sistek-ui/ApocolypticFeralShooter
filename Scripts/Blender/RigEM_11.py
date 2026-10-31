"""RigEM_11.py - cut the moving parts out of the merged EM_11 static mesh, rig it for Unreal and
author its mechanical clips. Idempotent: every run rebuilds everything from the vendor FBX.

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python Scripts/Blender/RigEM_11.py

Convention copied from Scripts/Blender/RigM4A1.py (parallel M4A1 workflow):
  Unreal X forward (muzzle +X), Z up, Y right (= Blender -Y), origin at the pistol-grip top centre
  (grip_r), 1 Blender m = 100 UU, every bone points +Y with roll 0 (identity in UE) except ejection_port (+X),
  FBX settings FBX_COMMON identical to the M4A1, armature OBJECT named 'Armature' (data block stays
  EM_11_Skeleton) so UE drops the x100-scaled Null instead of adding an extra root bone, and every
  clip file carries mesh + armature (UE 5.8 Interchange rejects armature-only FBX), exported from
  the clip's last (rest) frame. (Bone axes drift from the M4A1 reference, see stage_rig.)

Stages:
  1. import the vendor FBX (Blender honours its cm unit scale -> life size, see UNITS below),
     apply transforms, island report.
  2. cut magazine / charging-handle knob / trigger out of the single-island mesh with planar
     bisects + connectivity flood, cap both sides of every cut with a triangle fill (UV from the
     neighbouring surface), recentre on grip_r.
  3. armature EM_11_Skeleton + rigid skinning (every vertex weight 1.0 to exactly one bone).
  4. clips Idle/Fire/DryFire/Reload/Chamber at 60 fps. Reload also keys the non-deforming 'hand_l_target'
     bone (left-hand palm target for the body IK) and hides/pops the magazine (bone scale) so the empty mag
     never rises back into the well (2026-10-30 reload design, items 2+3). Since the 2026-10-30 evening pass
     (design B5) hand_l_target also carries a ROTATION track (delta from rest = how far to turn the left hand
     from the aim pose's hold) and a SCALE X track (finger curl, 1.0 = the aim pose's fingers), see HAND_ORI.
  5. export SK_EM11.fbx + A_EM11_<Clip>.fbx (every bone baked: translation, rotation and scale).
  6. proof renders (Workbench, 3/4 right + mag-well close-up + knob/trigger close-up); the hand target is drawn
     as a PALM PROXY (8 x 10 cm plate, finger arrow, thumb stub) in the keyed orientation, curl stamped as text.
  7. re-import every FBX in a fresh scene and assert bounds/bones/clip lengths/motion, hand rotation identity at
     the ends, < 150 deg between consecutive frames, curl 1.0 at the ends and within [0.4, 1.6].
  8. em11_rig.json (hand_l_target.rotation_keys / curl_keys hold the per-beat UE gun-space axis-angle + curl).

UNITS: the brief assumed inch units (x2.54). Measured: Blender's FBX importer applies the file's
UnitScaleFactor (object scale 0.01, cm) and the whole Vol 23 pack comes in life size: pistols
28-30 cm, the EM_13 bolt-action 119.7 cm (= 47.1 in, the source of the "48 units" note).
EM_11 imports at 99.3 cm, so SCALE = 1.0; x2.54 would make it 252 cm.
"""
import bpy
import bmesh
import json
import math
import os
import sys
import time
import traceback
from mathutils import Matrix, Quaternion, Vector

SRC_FBX = (r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\FBX\EM_Apocalyptic_Guns_FBX"
           r"\EM_11_Apocalyptic_Guns\EM_11_Apocalyptic_Guns.fbx")
OUT_DIR = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\Rigged\EM_11"
FPS = 60
SCALE = 1.0          # see UNITS above
PREFIX = "EM11"
ARM_NAME = "EM_11_Skeleton"          # armature DATA name only
# UE 5.8 Interchange drops the x100-scaled armature Null only when the OBJECT is named exactly
# 'Armature'; any other name becomes an extra scaled root bone (RigM4A1.py / RigEM_21.py convention).
ARMATURE_OBJECT_NAME = "Armature"
MESH_NAME = "SK_EM11"

os.makedirs(OUT_DIR, exist_ok=True)
LOG = []
PROOF_HAND = []          # per proof render: palm-proxy orientation (UE axis-angle), palm normal, finger dir, curl
T0 = time.time()


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append("%6.1fs %s" % (time.time() - T0, s))
    print("[RigEM_11]", s)
    sys.stdout.flush()


# ----------------------------------------------------------------------------
# Per-gun landmarks, metres, in the imported+applied vendor frame (muzzle already +X, Z up,
# gun's right side on -Y). Measured with slice profiles + ortho renders (see notes.md).
# This dict is the only part that changes per gun.
# ----------------------------------------------------------------------------
GUN = {
    # pistol-grip top centre: grip x range at z=0.165 is [-0.116,-0.080]; receiver underside 0.168
    "origin": Vector((-0.098, 0.0, 0.168)),
    "cuts": [
        {   # magazine: the receiver is 5.6 cm wide, the mag 4.8 cm; the crease runs from
            # z 0.164 (rear) to 0.148 (front) -> slanted plane ~2 mm under it
            "part": "magazine", "id": 1,
            "plane_a": Vector((0.025, 0.0, 0.1595)), "plane_b": Vector((0.118, 0.0, 0.1445)),
            "bisect_box": (Vector((0.0, -0.045, 0.11)), Vector((0.145, 0.045, 0.19))),
            "allow_min": Vector((0.003, -1, -1)), "allow_max": Vector((1, 1, 1)),
            "seed": Vector((0.07, -0.023, 0.10)), "extrude": 0.0,
        },
        {   # charging-handle knob: 1 cm nub on the right-side panel (panel surface y=-0.027..-0.0285)
            "part": "bolt_carrier", "id": 2,
            "plane_co": Vector((0.06, -0.0292, 0.262)), "plane_no": Vector((0, 1, 0)),
            "bisect_box": (Vector((0.046, -0.06, 0.247)), Vector((0.075, -0.02, 0.278))),
            "allow_min": Vector((0.046, -0.06, 0.247)), "allow_max": Vector((0.075, -0.02, 0.278)),
            "seed": Vector((0.06, -0.05, 0.262)), "extrude": 0.006,   # hidden stem into the receiver
        },
        {   # trigger blade: hangs from the guard opening top (z 0.211) to its tip at z 0.177
            "part": "trigger", "id": 3,
            "plane_co": Vector((-0.045, 0.0, 0.2035)), "plane_no": Vector((0, 0, 1)),
            "bisect_box": (Vector((-0.0595, -0.013, 0.195)), Vector((-0.024, 0.013, 0.2075))),
            "allow_min": Vector((-0.0595, -0.013, 0.174)), "allow_max": Vector((-0.024, 0.013, 0.2075)),
            "seed": Vector((-0.045, 0.0, 0.193)), "extrude": 0.003,
        },
    ],
    "ejection_port": Vector((0.09, -0.031, 0.265)),   # right-side panel, ahead of the knob
    "body_head": Vector((0.066, 0.0, 0.215)),
}

PARTS = {0: "body", 1: "magazine", 2: "bolt_carrier", 3: "trigger"}
MOVING_BONES = ["magazine", "bolt_carrier", "trigger"]
SOCKET_BONES = ["muzzle", "ejection_port", "sight", "grip_r", "grip_l", "mag_well"]
# hand_l_target (2026-10-30, reload design items 2+3): non-deforming child of body, rest at the grip_l head,
# +Y roll 0 like every other bone. It is the PALM-CENTRE target the C++ support-hand IK follows during a
# reload (AHoverPilot reads the gun's hand_l_target socket every tick). Keyed only in Reload; the rest keys the
# exporter bakes in the other clips equal grip_l, so outside reloads the IK target is the support grip.
HAND_BONES = ["hand_l_target"]
ANIM_BONES = MOVING_BONES + HAND_BONES          # bones ClipAuthor keys at f0 and the last frame of every clip
BONE_ORDER = ["root", "body"] + MOVING_BONES + SOCKET_BONES + HAND_BONES

BOLT_TRAVEL = 0.09
MAG_TILT = 25.0
TRIGGER_SIGN = +1.0     # +deg about Blender +Y moves the trigger bottom back (-X)
MAG_TILT_SIGN = -1.0    # -deg about Blender +Y swings the mag bottom forward (+X)

# --- left-hand reload choreography (gun space, Blender metres: X fwd, +Y = gun LEFT = UE -Y, Z up) ---
HAND_CUP_DOWN = 0.06         # palm centre 6 cm below the mag top (the lug / magazine bone head)
HAND_PALM_PAD = 0.010        # palm centre sits 1 cm outside the mag's left face (fingers wrap the body)
HAND_BELT = Vector((0.06, 0.14, -0.42))      # UE (+6, -14, -42) cm from grip_r: low and LEFT, forearm under the receiver
HAND_KNOB_PAD = 0.020        # pinch: palm centre 2 cm right of the charging-handle knob tip
MAG_HIDE_SCALE = 0.001       # empty mag hidden during the off-screen hold (bone scale, baked by the exporter)
MAG_G = 9.6                  # free-fall model shared with RigM4A1.py (z = -0.5*g*t^2)
HAND = {}                    # filled by stage_rig: cup point, knob pinch point (rest, armature space)
# re-import verification frames (also written to em11_rig.json for Scripts/ValidateGunClips.py)
HAND_VERIFY_FRAMES = {"mid_carry_frame": 80, "belt_frame": 58, "knob_back_frame": 122,
                      "mag_hidden_frame": 52, "mag_fall_end_frame": 45}
# Pinch lift (design B5, 2026-10-30 evening): the palm centre sits HAND_KNOB_LIFT above the receiver's top-cover
# edge at the knob (overhand reach: fingers drape down the right panel to the knob). Until then it sat at bore
# height and the curled fingers sank into the panel (owner capture 2026-10-30).
HAND_KNOB_LIFT = 0.020

# --- left-hand ORIENTATION + finger curl (design B5, 2026-10-30 evening) ---------------------------------------
# hand_l_target's ROTATION is a DELTA from rest (identity = however the stance aim pose holds the left hand at the
# support grip, so static clips and f0 / the last frame change nothing) and its bone-local SCALE X is the finger
# curl (1.0 = the aim pose's fingers as-is, 0 = the reference pose's open hand, 1.6 = tightest). The C++ support
# node turns hand_l by D = WeaponRot * socket rotation (gun space) * WeaponRot^-1 and slerps the 15 finger bones.
# Deltas are DESIGNED IN UE GUN SPACE (X fwd, Y right, Z up) from the measured Rifle aim-pose hand frame
# (Scripts/MeasureHandAxes.py -> D:/AFS_Comparisons/GunRigs_20261029/hand_axes.json, PIE 2026-10-30 23:17):
# hand_l local +X points along the fingers, local -Y out of the PALM, local -Z to the THUMB side. The columns
# below are those axes in gun space (the palm therefore faces right-and-up at the handguard from under-left).
REST_HAND_AXES_UE = {"X": (0.837, 0.546, -0.028), "Y": (0.401, -0.647, -0.649), "Z": (-0.372, 0.532, -0.761)}
# Beat orientations as (finger direction, palm normal) in gun space; the frame is Gram-Schmidt'ed, fingers win.
HAND_ORI = {
    "grab":   ((0.90, 0.0, -0.44), (0.0, 1.0, 0.0)),    # palm flat on the mag's LEFT face (+Y), fingers forward-down round the front, thumb up
    "belt":   ((0.90, 0.15, -0.30), (-0.3, 0.5, 0.8)),  # relaxed at the hip pouch: palm up and inward (toward the body: right, back)
    "front":  ((0.95, 0.0, -0.30), (0.0, 0.7, -0.7)),   # f106 crossing the mag front: palm rolls right-down
    "rise":   ((1.0, 0.0, -0.15), (0.0, 0.0, -1.0)),    # f108 rising up the right side: palm down
    "pinch":  ((1.0, 0.0, 0.0), (0.0, -0.64, -0.77)),   # overhand pinch above the receiver edge: palm faces down-LEFT (the gun side), thumb outboard
    "slide":  ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),      # f134 sliding down the right panel: palm toward the gun (-Y)
    "under":  ((1.0, 0.0, 0.0), (0.0, -0.7, 0.7)),      # f138 under the handguard's right side: palm up-left
    "cup_up": ((1.0, 0.0, 0.1), (0.0, 0.0, 1.0)),       # f141 palm up under the handguard, 48 deg short of rest
}
HAND_CURL = {"grab": 1.3, "belt": 0.8, "front": 1.0, "rise": 1.0, "pinch": 1.1, "slide": 1.0, "under": 1.0, "cup_up": 1.0}
HAND_ROT_MAX_STEP_DEG = 150.0        # never the long way round (consecutive keys / sampled frames)
HAND_CURL_RANGE = (0.4, 1.6)
# beat frames read back after re-import (also in em11_rig.json for Scripts/ValidateGunClips.py)
HAND_BEAT_FRAMES = {"grab": 8, "rock": 20, "pull": 30, "belt": 58, "carry": 80, "seat": 100, "snap_front": 106,
                    "snap_rise": 108, "pinch": 110, "rack_back": 122, "let_go": 130, "slide": 134, "under": 138,
                    "cup_up": 141, "end": 144}

# ----------------------------------------------------------------------------------------------------------------
# Blender armature space <-> UE gun space for ROTATIONS. Positions map by M = diag(1, -1, 1) (Blender -Y = UE +Y
# right), so any rotation maps by conjugation R_ue = M R_bl M^-1 = M R_bl M (M is its own inverse). Because M is
# a reflection the handedness flips: a rotation of +a about Blender X is -a about UE X, about Blender Z is -a
# about UE Z, about Blender +Y it is +a about UE +Y (the Y axis itself is mirrored, which cancels the sign).
# Quaternion form: (w, x, y, z)_bl -> (w, -x, y, -z)_ue. check_rotation_convention() proves all of this
# numerically at start-up (rotate test vectors both ways) instead of trusting the comment.
# ----------------------------------------------------------------------------------------------------------------
M_FLIP = Matrix(((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)))


def rot_bl_to_ue(R):
    return M_FLIP @ R.to_3x3() @ M_FLIP


def rot_ue_to_bl(R):
    return M_FLIP @ R.to_3x3() @ M_FLIP


def quat_bl_to_ue(q):
    return Quaternion((q.w, -q.x, q.y, -q.z))


def axis_angle_ue(R_ue):
    """(axis, degrees) of a UE gun-space rotation matrix; axis (0,0,1) for the identity"""
    q = R_ue.to_3x3().to_quaternion()
    ang = math.degrees(q.angle)
    if ang > 180.0:
        ang = 360.0 - ang
        q = Quaternion((-q.w, -q.x, -q.y, -q.z)).normalized()
    axis = q.axis if ang > 1e-6 else Vector((0, 0, 1))
    return [round(c, 4) for c in axis], round(ang, 2)


def frame_fp(finger, palm):
    """3x3 hand frame (columns X = fingers, Y = -palm normal, Z = X x Y) from a finger direction and a palm normal"""
    X = Vector(finger).normalized()
    P = Vector(palm)
    P = (P - P.dot(X) * X).normalized()
    Y = -P
    Z = X.cross(Y)
    return Matrix((X, Y, Z)).transposed()


REST_HAND_UE = frame_fp(REST_HAND_AXES_UE["X"], tuple(-c for c in REST_HAND_AXES_UE["Y"]))


def hand_delta_ue(ori):
    """gun-space rotation that turns the rest hand frame into the HAND_ORI[ori] frame"""
    F, P = HAND_ORI[ori]
    return frame_fp(F, P) @ REST_HAND_UE.inverted()


def hand_delta_bl(ori):
    return rot_ue_to_bl(hand_delta_ue(ori))


def hand_frame_ue(R_ue):
    """(palm normal, finger direction) in gun space for a UE delta applied to the rest hand frame"""
    H = R_ue.to_3x3() @ REST_HAND_UE
    return [round(-H[i][1], 3) for i in range(3)], [round(H[i][0], 3) for i in range(3)]


def check_rotation_convention():
    """numeric proof of the Blender<->UE rotation conversion: rotate test vectors both ways, round-trip, axis signs"""
    import random
    rnd = random.Random(11)
    tests = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((0.3, -0.7, 0.5)), Vector((-0.8, 0.2, 0.1))]
    worst = 0.0
    for _ in range(50):
        axis = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
        q_bl = Quaternion(axis, rnd.uniform(-math.pi, math.pi))
        R_bl = q_bl.to_matrix()
        R_ue = rot_bl_to_ue(R_bl)
        assert abs(R_ue.determinant() - 1.0) < 1e-5, "conjugated rotation is not proper"   # mathutils is float32
        for v in tests:
            worst = max(worst, (M_FLIP @ (R_bl @ v) - R_ue @ (M_FLIP @ v)).length)
        # quaternion shortcut agrees with the matrix conjugation (up to the q/-q sign)
        q_ue = R_ue.to_quaternion()
        q_sc = quat_bl_to_ue(q_bl)
        worst = max(worst, min((q_ue - q_sc).magnitude, (q_ue + q_sc).magnitude))
        # round trip
        worst = max(worst, max(abs(a - b) for ra, rb in zip(rot_ue_to_bl(R_ue), R_bl) for a, b in zip(ra, rb)))
    a = math.radians(37.0)
    signs = {}
    for ax, expect in (("X", -1.0), ("Y", 1.0), ("Z", -1.0)):
        R_ue = rot_bl_to_ue(Matrix.Rotation(a, 3, ax))
        got = axis_angle_ue(R_ue)
        signs[ax] = got
        want = Matrix.Rotation(expect * a, 3, ax)
        worst = max(worst, max(abs(p - q) for rp, rq in zip(R_ue, want) for p, q in zip(rp, rq)))
    # the rest hand frame must be a proper frame whose Z agrees with the measured hand_l Z (thumb side = -Z)
    Zm = Vector(REST_HAND_AXES_UE["Z"])
    zdot = Vector(tuple(REST_HAND_UE[i][2] for i in range(3))).dot(Zm)
    assert abs(REST_HAND_UE.determinant() - 1.0) < 1e-5 and zdot > 0.99, "rest hand frame handedness %s" % zdot
    assert worst < 1e-5, "rotation convention round-trip error %g" % worst   # float32 mathutils
    HAND["rotation_convention"] = {
        "rule": "R_ue = M R_bl M with M = diag(1,-1,1); +a about Blender X = -a about UE X, about Blender Z = -a about UE Z, "
                "about Blender +Y = +a about UE +Y; quaternion (w,x,y,z)_bl -> (w,-x,y,-z)_ue",
        "numeric_round_trip_max_err": worst, "axis_sign_check_37deg_bl": signs,
        "rest_hand_Z_vs_measured_dot": round(zdot, 4)}
    log("rotation convention verified: max err %.2e, 37 deg about Blender X/Y/Z -> UE" % worst,
        {k: v[1] * (1 if v[0][("XYZ".index(k))] > 0 else -1) for k, v in signs.items()})


def select_only(obs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (obs[0] if obs else None)


def bounds_pts(pts):
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def r3(v, k=100.0, nd=2):
    return [round(c * k, nd) for c in v]


def islands(bm):
    seen = set()
    out = []
    for f in bm.faces:
        if f.index in seen:
            continue
        comp = []
        st = [f]
        seen.add(f.index)
        while st:
            g = st.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        st.append(h)
        out.append(comp)
    return out


# ============================================================================
# 1. import
# ============================================================================
def stage_import():
    bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
    scn = bpy.context.scene
    scn.unit_settings.system = 'METRIC'
    scn.unit_settings.scale_length = 1.0
    scn.unit_settings.length_unit = 'METERS'
    bpy.ops.import_scene.fbx(filepath=SRC_FBX)
    # After the import: the FBX importer sets the scene to the source file's 30 fps, which exported every 60 fps
    # clip at double length (A_EM11_Fire 0.233 s in UE on 2026-10-30) when this ran before it.
    scn.render.fps = FPS
    scn.render.fps_base = 1.0
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    assert len(meshes) == 1, "expected one merged mesh, got %d" % len(meshes)
    ob = meshes[0]
    log("imported", ob.name, "obj scale", [round(s, 4) for s in ob.scale], "rot deg",
        [round(math.degrees(a), 2) for a in ob.rotation_euler], "polys", len(ob.data.polygons),
        "materials", [m.name for m in ob.data.materials])
    for o in list(bpy.data.objects):
        if o is not ob:
            bpy.data.objects.remove(o, do_unlink=True)
    select_only([ob], ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if SCALE != 1.0:
        ob.data.transform(Matrix.Scale(SCALE, 4))
    if ob.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
        log("cleared imported custom split normals (re-derived from smooth shading + sharp cap rims)")
    for p in ob.data.polygons:
        p.use_smooth = True
    mn, mx = bounds_pts([v.co for v in ob.data.vertices])
    log("life-size bounds cm", r3(mn), r3(mx), "length cm", round((mx.x - mn.x) * 100, 2))
    return ob


# ============================================================================
# 2. cuts
# ============================================================================
def plane_of(cut):
    if "plane_no" in cut:
        return cut["plane_co"].copy(), cut["plane_no"].normalized()
    a, b = cut["plane_a"], cut["plane_b"]
    d = (b - a).normalized()
    n = d.cross(Vector((0, 1, 0)))          # in the XZ plane, perpendicular to a->b
    if n.z < 0:
        n = -n                               # point up, toward the receiver
    return a.copy(), n.normalized()


def inbox(p, mn, mx, pad=0.0):
    return all(mn[i] - pad <= p[i] <= mx[i] + pad for i in range(3))


def cap_uvs(bm, uv, cap_faces, rim_faces, n):
    """Planar projection of the cap fitted into the centre half of the UV rect of the largest
    neighbouring surface face, so the cap samples the adjacent material instead of black."""
    best = None
    for f in rim_faces:
        us = [l[uv].uv.copy() for l in f.loops]
        a = min(u.x for u in us), min(u.y for u in us)
        b = max(u.x for u in us), max(u.y for u in us)
        area = (b[0] - a[0]) * (b[1] - a[1])
        if best is None or area > best[0]:
            best = (area, a, b)
    if best is None or best[0] <= 0:
        return None
    _, a, b = best
    cu, cv = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    hu, hv = (b[0] - a[0]) / 4, (b[1] - a[1]) / 4
    tmp = Vector((0, 1, 0)) if abs(n.y) < 0.9 else Vector((1, 0, 0))
    ua = n.cross(tmp).normalized()
    va = n.cross(ua).normalized()
    pts = [v.co for f in cap_faces for v in f.verts]
    us = [p.dot(ua) for p in pts]
    vs = [p.dot(va) for p in pts]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    for f in cap_faces:
        for l in f.loops:
            s = (l.vert.co.dot(ua) - u0) / max(u1 - u0, 1e-9)
            t = (l.vert.co.dot(va) - v0) / max(v1 - v0, 1e-9)
            l[uv].uv = (cu - hu + 2 * hu * s, cv - hv + 2 * hv * t)
    return [round(cu, 4), round(cv, 4), round(2 * hu, 5), round(2 * hv, 5)]


def winding_errors(faces):
    """count edges where two faces of the set traverse the edge in the same direction"""
    fs = set(faces)
    bad = 0
    seen = set()
    for f in faces:
        for l in f.loops:
            e = l.edge
            if e in seen:
                continue
            seen.add(e)
            lf = [x for x in e.link_loops if x.face in fs]
            if len(lf) == 2 and lf[0].vert == lf[1].vert:
                bad += 1
    return bad


def do_cut(bm, part, uv, cut, report):
    pid = cut["id"]
    co, n = plane_of(cut)
    bmn, bmx = cut["bisect_box"]
    amn, amx = cut["allow_min"], cut["allow_max"]
    rep = {"part": cut["part"], "plane_co_src_m": [round(c, 5) for c in co],
           "plane_normal": [round(c, 4) for c in n]}

    def d(p):
        return (p - co).dot(n)

    faces_before = len(bm.faces)
    # 1. bisect only the geometry inside the box (keeps the rest of the gun untouched)
    geo_f = [f for f in bm.faces if f[part] == 0 and any(inbox(v.co, bmn, bmx) for v in f.verts)]
    geo_e = list({e for f in geo_f for e in f.edges})
    geo_v = list({v for f in geo_f for v in f.verts})
    bmesh.ops.bisect_plane(bm, geom=geo_v + geo_e + geo_f, dist=1e-7, plane_co=co, plane_no=n)
    bm.faces.ensure_lookup_table()
    rep["faces_added_by_bisect"] = len(bm.faces) - faces_before

    # 2. flood from the seed across faces on the part side of the plane
    def allowed(f):
        c = f.calc_center_median()
        return f[part] == 0 and d(c) < 0 and inbox(c, amn, amx)

    cand = [f for f in bm.faces if allowed(f)]
    seed = min(cand, key=lambda f: (f.calc_center_median() - cut["seed"]).length)
    region = {seed}
    st = [seed]
    while st:
        f = st.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g not in region and allowed(g):
                    region.add(g)
                    st.append(g)
    # 3. the region boundary must lie on the plane (otherwise the allow box clipped the part)
    bnd = [e for e in {e for f in region for e in f.edges}
           if any(g not in region for g in e.link_faces)]
    off = [v for e in bnd for v in e.verts if abs(d(v.co)) > 2e-5]
    rep["boundary_edges"] = len(bnd)
    rep["boundary_verts_off_plane"] = len(off)
    if off:
        raise RuntimeError("%s: %d boundary verts off the cut plane (region leaked into allow-box edge)"
                           % (cut["part"], len(off)))
    rep["faces_moved"] = len(region)
    rep["orig_faces_moved"] = len({f[report["oid"]] for f in region})
    mn, mx = bounds_pts([v.co for f in region for v in f.verts])
    rep["part_bounds_src_cm"] = [r3(mn), r3(mx)]
    for f in region:
        f[part] = pid
    # 4. split and cap both sides
    bmesh.ops.split_edges(bm, edges=bnd)
    shared = [v for f in region for v in f.verts if any(g[part] != pid for g in v.link_faces)]
    if shared:
        raise RuntimeError("%s: %d verts still shared after split" % (cut["part"], len(shared)))
    part_open = [e for f in region for e in f.edges if len(e.link_faces) == 1]
    part_open = list(set(part_open))
    body_open = [e for e in bm.edges if len(e.link_faces) == 1 and e.link_faces[0][part] == 0
                 and all(abs(d(v.co)) < 2e-5 for v in e.verts)
                 and all(inbox(v.co, bmn, bmx, 0.002) for v in e.verts)]
    caps = {}
    for side, edges, want in (("part", part_open, n), ("body", body_open, -n)):
        rim = list({e.link_faces[0] for e in edges})
        res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=n)
        cf = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
        flip = [f for f in cf if f.normal.dot(want) < 0]
        if flip:
            bmesh.ops.reverse_faces(bm, faces=flip)
        for f in cf:
            f[part] = pid if side == "part" else 0
            f[report["cap"]] = pid
            f.smooth = False
            f.material_index = 0
        for e in edges:
            e.smooth = False                 # sharp rim: caps do not bend the side normals
        uvrect = cap_uvs(bm, uv, cf, rim, want)
        still_open = [e for e in edges if len(e.link_faces) < 2]
        caps[side] = {"loops_edges": len(edges), "cap_tris": len(cf), "flipped": len(flip),
                      "open_edges_after_fill": len(still_open), "uv_rect": uvrect,
                      "winding_errors_rim": winding_errors(cf + rim)}
        if still_open:
            raise RuntimeError("%s %s cap left %d open edges" % (cut["part"], side, len(still_open)))
        if side == "body":
            cen = Vector()
            vs = {v for f in cf for v in f.verts}
            for v in vs:
                cen += v.co
            caps[side]["centroid_src"] = cen / len(vs)
    rep["caps"] = caps
    # 5. optional hidden stem: push the part's cap into the body so a moved part never floats
    if cut["extrude"] > 0:
        pc = [f for f in bm.faces if f[report["cap"]] == pid and f[part] == pid]
        ret = bmesh.ops.extrude_face_region(bm, geom=pc)
        nv = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=nv, vec=n * cut["extrude"])
        for g in ret["geom"]:
            if isinstance(g, bmesh.types.BMFace):
                g[part] = pid
        # side walls created by the extrude
        for v in nv:
            for f in v.link_faces:
                f[part] = pid
        rep["stem_m"] = cut["extrude"]
    bm.faces.ensure_lookup_table()
    report["cuts"][cut["part"]] = rep
    log("cut", cut["part"], "faces moved", rep["faces_moved"], "(orig", rep["orig_faces_moved"], ")",
        "bounds cm", rep["part_bounds_src_cm"], "caps", {k: (v["cap_tris"], v["loops_edges"]) for k, v in caps.items()})
    return co, n


def stage_cut(ob):
    report = {"cuts": {}}
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    isl = islands(bm)
    report["islands_before"] = len(isl)
    report["faces_before"] = len(bm.faces)
    report["open_edges_before"] = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    report["case"] = ("island" if len(isl) > 1 else "shared")
    log("islands", len(isl), "faces", len(bm.faces), "open edges", report["open_edges_before"],
        "-> case:", report["case"])
    part = bm.faces.layers.int.new("part")
    cap = bm.faces.layers.int.new("cap")
    oid = bm.faces.layers.int.new("oid")
    report["oid"] = oid
    report["cap"] = cap
    for f in bm.faces:
        f[part] = 0
        f[cap] = 0
        f[oid] = f.index
    uv = bm.loops.layers.uv.active
    planes = {}
    for cut in GUN["cuts"]:
        planes[cut["part"]] = do_cut(bm, part, uv, cut, report)
    # recentre on grip_r
    o = GUN["origin"]
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=-o)
    bm.faces.ensure_lookup_table()
    isl = islands(bm)
    report["islands_after"] = len(isl)
    report["open_edges_after"] = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    # per part vertex sets (rigid)
    face_part = [f[part] for f in bm.faces]
    face_cap = [f[cap] for f in bm.faces]
    vpart = {}
    for f in bm.faces:
        for v in f.verts:
            vpart.setdefault(v.index, set()).add(f[part])
    multi = sum(1 for s in vpart.values() if len(s) > 1)
    if multi:
        raise RuntimeError("%d verts belong to two parts" % multi)
    bm.faces.layers.int.remove(part)
    bm.faces.layers.int.remove(cap)
    bm.faces.layers.int.remove(oid)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    del report["oid"]
    del report["cap"]
    report["faces_after"] = len(ob.data.polygons)
    report["part_face_counts"] = {PARTS[k]: face_part.count(k) for k in PARTS}
    report["cap_face_counts"] = {PARTS[k]: face_cap.count(k) for k in PARTS if k}
    log("after cuts: islands", report["islands_after"], "open edges", report["open_edges_after"],
        "faces", report["faces_after"], "per part", report["part_face_counts"])
    vgroup_of = {vi: PARTS[next(iter(s))] for vi, s in vpart.items()}
    return report, face_part, face_cap, vgroup_of, planes


# ============================================================================
# 3. armature + skinning
# ============================================================================
def stage_rig(ob, report, vgroup_of, planes):
    O = GUN["origin"]
    V = {}
    for vi, g in vgroup_of.items():
        V.setdefault(g, []).append(ob.data.vertices[vi].co.copy())
    allv = [v.co for v in ob.data.vertices]
    gmn, gmx = bounds_pts(allv)
    heads = {"root": Vector(), "grip_r": Vector(), "body": GUN["body_head"] - O}
    # muzzle: centre of the suppressor front face
    front = [p for p in allv if p.x > gmx.x - 0.003]
    fmn, fmx = bounds_pts(front)
    bore = Vector((gmx.x, (fmn.y + fmx.y) / 2, (fmn.z + fmx.z) / 2))
    heads["muzzle"] = bore
    # magazine: head on the front locking lug = front-top of the mag at the cut plane (AK pivot)
    co, n = planes["magazine"]
    co = co - O
    mag = V["magazine"]
    top = [p for p in mag if (p - co).dot(n) > -0.004]
    xf = max(p.x for p in top)
    zf = co.z - (xf - co.x) * n.x / n.z
    heads["magazine"] = Vector((xf, 0.0, zf))
    # bolt carrier = charging-handle knob, on the bore axis at the knob's x
    kmn, kmx = bounds_pts(V["bolt_carrier"])
    heads["bolt_carrier"] = Vector(((kmn.x + kmx.x) / 2, 0.0, bore.z))
    # trigger pivot: top of the blade, just above the cut
    tco, tn = planes["trigger"]
    tsec = [p for p in V["trigger"] if abs(p.z - (tco.z - O.z)) < 0.001]
    heads["trigger"] = Vector((sum(p.x for p in tsec) / len(tsec), 0.0, tco.z - O.z + 0.002))
    heads["ejection_port"] = GUN["ejection_port"] - O
    ring = [p for p in V["body"] if p.z > 0.37 - O.z and p.x > 0.03 - O.x]
    rmn, rmx = bounds_pts(ring)
    heads["sight"] = (rmn + rmx) / 2
    hg = [p for p in V["body"] if 0.23 - O.x < p.x < 0.25 - O.x and abs(p.y) < 0.03 and p.z > 0.15 - O.z]
    heads["grip_l"] = Vector((0.24 - O.x, 0.0, min(p.z for p in hg)))
    heads["mag_well"] = report["cuts"]["magazine"]["caps"]["body"]["centroid_src"] - O
    heads["hand_l_target"] = heads["grip_l"].copy()
    # palm cup point on the magazine: 6 cm below the lug, centred in X on the mag slice there, 1 cm outside
    # its LEFT face (+Y). Stored rest-relative so the clips can carry it rigidly with the mag.
    zc = heads["magazine"].z - HAND_CUP_DOWN
    sl = [p for p in mag if abs(p.z - zc) < 0.006]
    HAND["cup_rest"] = Vector((sum(p.x for p in sl) / len(sl), max(p.y for p in sl) + HAND_PALM_PAD, zc))
    HAND["cup_offset"] = HAND["cup_rest"] - heads["magazine"]
    HAND["mag_width_at_cup_cm"] = round((max(p.y for p in sl) - min(p.y for p in sl)) * 100, 2)
    # charging-handle knob pinch point (overhand, B5): knob centre x, HAND_KNOB_PAD beyond the knob's right (-Y) tip,
    # HAND_KNOB_LIFT above the receiver's top-cover edge at the knob. The edge is the highest right-panel vertex
    # (y < -2 cm, within 3 cm of the knob x, under 14 cm: measured profile at the knob x = panel to z 10-11 cm, a
    # 3 cm wide rear-sight rail z 11-15, then the 6-7 cm wide ring-sight housing z 16-25). The knob centre is 9.4.
    kx = (kmn.x + kmx.x) / 2
    cover = [p for p in V["body"] if abs(p.x - kx) < 0.03 and p.y < -0.02 and p.z < 0.14]
    HAND["top_cover_z"] = max(p.z for p in cover)
    assert 0.09 < HAND["top_cover_z"] < 0.14, "top cover edge at the knob off: %.3f m" % HAND["top_cover_z"]
    sight = [p for p in V["body"] if abs(p.x - kx) < 0.03 and p.z > 0.15]
    HAND["sight_housing_min_y"] = min(p.y for p in sight) if sight else None     # right edge of the ring sight above the knob
    HAND["knob_centre_rest"] = Vector((kx, (kmn.y + kmx.y) / 2, (kmn.z + kmx.z) / 2))
    HAND["knob_rest"] = Vector((kx, kmn.y - HAND_KNOB_PAD, HAND["top_cover_z"] + HAND_KNOB_LIFT))
    HAND["knob_offset"] = HAND["knob_rest"] - heads["bolt_carrier"]
    log("knob pinch: top cover edge z cm", round(HAND["top_cover_z"] * 100, 2), "palm centre UE", ue(HAND["knob_rest"]),
        "knob centre UE", ue(HAND["knob_centre_rest"]), "sight housing right edge y cm UE",
        None if HAND["sight_housing_min_y"] is None else round(-HAND["sight_housing_min_y"] * 100, 2))
    for c in report["cuts"].values():
        for s in c["caps"].values():
            if "centroid_src" in s:
                s["centroid_cm_ue"] = ue(s.pop("centroid_src") - O)

    arm_data = bpy.data.armatures.new(ARM_NAME)
    arm = bpy.data.objects.new(ARMATURE_OBJECT_NAME, arm_data)
    assert arm.name == ARMATURE_OBJECT_NAME, "armature object got renamed to %s (name clash)" % arm.name
    bpy.context.scene.collection.objects.link(arm)
    select_only([arm], arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    parents = {"root": None, "body": "root", "grip_r": "root"}
    for b in MOVING_BONES + SOCKET_BONES + HAND_BONES:
        parents.setdefault(b, "body")
    lengths = {"root": 0.08, "body": 0.12}
    for name in BONE_ORDER:
        b = eb.new(name)
        h = heads[name]
        L = lengths.get(name, 0.03)
        b.head = h
        # M4A1 convention (Scripts/Blender/RigM4A1.py): bones point Blender +Y with roll 0, which is an
        # identity rest orientation in UE component space (X forward, Y right, Z up); ejection_port points
        # Blender +X so its UE X axis is the gun's right. Until 2026-10-30 this rig pointed bones along +X,
        # which came into UE as a 90 deg yaw on root (ValidateGunClips.py read the bolt stroke on local Y and
        # the ejection_port's X pointed backwards, so EM_11 brass would have flown rearward). ClipAuthor.key
        # takes world-space deltas and converts through the rest matrix, so the clips are unaffected.
        b.tail = h + (Vector((L, 0, 0)) if name == "ejection_port" else Vector((0, L, 0)))
        b.roll = 0.0
        b.use_deform = name in ("body",) + tuple(MOVING_BONES)
    for name in BONE_ORDER:
        if parents.get(name):
            eb[name].parent = eb[parents[name]]
            eb[name].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')

    ob.name = MESH_NAME
    ob.data.name = MESH_NAME
    ob.vertex_groups.clear()
    groups = {g: ob.vertex_groups.new(name=g) for g in ["body"] + MOVING_BONES}
    by = {}
    for vi, g in vgroup_of.items():
        by.setdefault(g, []).append(vi)
    for g, idx in by.items():
        groups[g].add(idx, 1.0, 'REPLACE')
    bad = sum(1 for v in ob.data.vertices if len(v.groups) != 1 or abs(v.groups[0].weight - 1) > 1e-6)
    if bad:
        raise RuntimeError("%d vertices not rigidly weighted" % bad)
    report["vertex_counts"] = {g: len(i) for g, i in by.items()}
    ob.parent = arm
    mod = ob.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    bpy.context.view_layer.update()
    log("bones", [b.name for b in arm_data.bones], "verts per bone", report["vertex_counts"])
    return arm, heads


def ue(v):
    """Blender metres -> Unreal cm (X fwd, Y right = Blender -Y, Z up)"""
    return [round(v.x * 100, 3), round(-v.y * 100, 3), round(v.z * 100, 3)]


# ============================================================================
# 4. animation (ClipAuthor copied from RigM4A1.py)
# ============================================================================
def ensure_slot(ob, act):
    ad = ob.animation_data or ob.animation_data_create()
    ad.action = act
    if hasattr(act, "slots"):
        if ad.action_slot is None:
            if len(act.slots) == 0:
                act.slots.new('OBJECT', ob.name)
            ad.action_slot = act.slots[0]
    return ad


def _fcurves(act):
    if hasattr(act, "layers") and len(act.layers):
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
        return out
    return list(act.fcurves)


ROT_SEPARATE = set(HAND_BONES)     # bones whose rotation + scale-X tracks come from key_rot / key_curl, not from key()


class ClipAuthor:
    """Keys bones in armature space: translation T (m) after a rotation (deg) about the bone head.
    Animated bones are children of 'body', which never moves. Bones in ROT_SEPARATE (hand_l_target) get their
    rotation from key_rot (an armature-space delta matrix, any frame, shortest-path quaternion continuity) and
    their finger curl from key_curl (bone-local scale X), so a position key never stamps an identity rotation."""

    def __init__(self, arm, name, frames):
        self.arm = arm
        self.frames = frames
        self.act = bpy.data.actions.new(name)
        self.act.use_fake_user = True
        ensure_slot(arm, self.act)
        self.act.frame_range = (0, frames)
        self.act.use_frame_range = True
        self.keys = []
        self.scale_keys = []
        self.rot_keys = []
        self.curl_keys = []

    def key(self, bone, frame, T=(0, 0, 0), rot=None, interp='BEZIER', easing='AUTO'):
        assert not (bone in ROT_SEPARATE and rot is not None), "%s: use key_rot for its rotation" % bone
        self.keys.append((bone, frame, Vector(T), rot, interp, easing))

    def key_rot(self, bone, frame, R, interp='BEZIER', easing='AUTO'):
        """armature-space rotation delta (3x3 Matrix or Quaternion) applied about the bone head, as its own track"""
        R = R.to_matrix() if isinstance(R, Quaternion) else R.to_3x3()
        self.rot_keys.append((bone, frame, R.copy(), interp, easing))

    def key_curl(self, bone, frame, curl, interp='BEZIER', easing='AUTO'):
        """finger curl = bone-local scale X (1.0 = the aim pose's fingers); smooth, unlike the hide/show scale keys"""
        self.curl_keys.append((bone, frame, float(curl), interp, easing))

    def rot_on(self, bone, frame):
        """armature-space rotation of `bone` relative to its rest at `frame` of the action as keyed so far
        (used to turn the hand with the magazine's 25 deg tilt while it rides the cup point)"""
        scn = bpy.context.scene
        ensure_slot(self.arm, self.act)
        scn.frame_set(frame)
        bpy.context.view_layer.update()
        pb = self.arm.pose.bones[bone]
        return (pb.matrix.to_3x3() @ pb.bone.matrix_local.to_3x3().inverted()).normalized()

    def key_at(self, bone, frame, pos, **kw):
        """key a bone so its head sits at armature-space point `pos` (translation only)"""
        self.key(bone, frame, Vector(pos) - self.arm.pose.bones[bone].bone.matrix_local.translation, **kw)

    def key_scale(self, bone, frame, s, interp='CONSTANT'):
        """uniform bone scale key (hide/show); CONSTANT so hide and pop-in are steps, not fades"""
        self.scale_keys.append((bone, frame, float(s), interp))

    def point_on(self, bone, frame, rest_point):
        """armature-space position, at `frame` of the action as keyed so far, of a point given in rest
        space that rides rigidly on `bone` (used to glue the hand target to the mag / the knob)."""
        scn = bpy.context.scene
        ensure_slot(self.arm, self.act)
        scn.frame_set(frame)
        bpy.context.view_layer.update()
        pb = self.arm.pose.bones[bone]
        return pb.matrix @ pb.bone.matrix_local.inverted() @ Vector(rest_point)

    def apply(self):
        arm = self.arm
        ensure_slot(arm, self.act)
        bpy.context.scene.frame_set(0)
        for pb in arm.pose.bones:
            pb.rotation_mode = 'QUATERNION'
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
        animated = sorted(set(k[0] for k in self.keys))
        for b in ANIM_BONES:
            if b not in animated:
                self.keys.append((b, 0, Vector(), None, 'BEZIER', 'AUTO'))
                self.keys.append((b, self.frames, Vector(), None, 'BEZIER', 'AUTO'))
        for (bone, frame, T, rot, interp, easing) in self.keys:
            pb = arm.pose.bones[bone]
            rest = pb.bone.matrix_local
            head = rest.translation
            R = Matrix.Identity(4)
            if rot is not None:
                axis, deg = rot
                R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
            pb.matrix_basis = rest.inverted() @ (Matrix.Translation(T) @ R @ rest)
            pb.keyframe_insert("location", frame=frame, group=bone)
            if bone not in ROT_SEPARATE:
                pb.keyframe_insert("rotation_quaternion", frame=frame, group=bone)
        # ROT_SEPARATE bones: rotation deltas and curl as their own tracks, identity / 1.0 forced at f0 and the last
        # frame of EVERY clip (the exporter bakes both channels, so the C++ side reads identity outside reloads).
        # Keys go in frame order with q/-q continuity (ensure-shortest-path), so Blender's per-component quaternion
        # curves never swing the long way round between two keys.
        rot_keys = list(self.rot_keys)
        curl_keys = list(self.curl_keys)
        for b in ROT_SEPARATE:
            for f in (0, self.frames):
                if not any(k[0] == b and k[1] == f for k in rot_keys):
                    rot_keys.append((b, f, Matrix.Identity(3), 'BEZIER', 'AUTO'))
                if not any(k[0] == b and k[1] == f for k in curl_keys):
                    curl_keys.append((b, f, 1.0, 'BEZIER', 'AUTO'))
        rot_keys.sort(key=lambda k: (k[0], k[1]))
        q_prev = {}
        for (bone, frame, R, interp, easing) in rot_keys:
            pb = arm.pose.bones[bone]
            rest3 = pb.bone.matrix_local.to_3x3()
            q = (rest3.inverted() @ R @ rest3).to_quaternion().normalized()
            if bone in q_prev and q.dot(q_prev[bone]) < 0.0:
                q = Quaternion((-q.w, -q.x, -q.y, -q.z))
            q_prev[bone] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=bone)
            pb.rotation_quaternion = (1, 0, 0, 0)
        for (bone, frame, curl, interp, easing) in curl_keys:
            pb = arm.pose.bones[bone]
            pb.scale = (curl, 1.0, 1.0)
            pb.keyframe_insert("scale", frame=frame, group=bone)
            pb.scale = (1, 1, 1)
        for (bone, frame, s, interp) in self.scale_keys:
            pb = arm.pose.bones[bone]
            pb.scale = (s, s, s)
            pb.keyframe_insert("scale", frame=frame, group=bone)
            pb.scale = (1, 1, 1)
        for fc in _fcurves(self.act):
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = 'AUTO'
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'
        for (bone, frame, T, rot, interp, easing) in self.keys:
            if interp == 'BEZIER' and easing == 'AUTO':
                continue
            for fc in _fcurves(self.act):
                if not fc.data_path.startswith('pose.bones["%s"]' % bone) or fc.data_path.endswith(".scale"):
                    continue
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-3:
                        kp.interpolation = interp
                        kp.easing = easing
        for (bone, frame, R, interp, easing), path in [(k, ".rotation_quaternion") for k in rot_keys] + \
                [((k[0], k[1], None, k[3], k[4]), ".scale") for k in curl_keys]:
            if interp == 'BEZIER' and easing == 'AUTO':
                continue
            for fc in _fcurves(self.act):
                if fc.data_path != 'pose.bones["%s"]%s' % (bone, path):
                    continue
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-3:
                        kp.interpolation = interp
                        kp.easing = easing
        for (bone, frame, s, interp) in self.scale_keys:
            for fc in _fcurves(self.act):
                if fc.data_path == 'pose.bones["%s"].scale' % bone:
                    for kp in fc.keyframe_points:
                        if abs(kp.co.x - frame) < 1e-3:
                            kp.interpolation = interp
        for fc in _fcurves(self.act):
            fc.update()
        bpy.context.scene.frame_set(0)
        return self.act


def check_hand_clear(arm, act, sk, face_part):
    """Design rule: the hand target never penetrates the gun body. Samples every Reload frame against a
    BVH of the rest mesh: the body for all frames, the seated magazine only while it is seated (f0-f10,
    f100-f144; in between it is in the hand or gone). Inside = odd ray parity (closed islands)."""
    from mathutils.bvhtree import BVHTree
    me = sk.data
    verts = [v.co.copy() for v in me.vertices]
    body_polys = [list(p.vertices) for p, fp in zip(me.polygons, face_part) if fp == 0]
    mag_polys = [list(p.vertices) for p, fp in zip(me.polygons, face_part) if fp == 1]
    bvh_body = BVHTree.FromPolygons(verts, body_polys)
    bvh_mag = BVHTree.FromPolygons(verts, mag_polys)
    grip_l = arm.pose.bones["grip_l"].bone.matrix_local.translation
    ensure_slot(arm, act)
    scn = bpy.context.scene
    worst = {"body": (1e9, None), "magazine": (1e9, None)}
    inside = []
    # inside test by ray parity (3 skew rays, majority): the nearest-face normal sign is wrong in concave
    # corners such as the mag-well lip, which flagged a point 6 cm clear of the body on the first run.
    dirs = [Vector(d).normalized() for d in ((1, 0.13, 0.07), (0.1, 1, 0.21), (0.05, 0.17, 1))]

    def parity(bvh, p, d):
        n, o = 0, p.copy()
        for _ in range(64):
            hit = bvh.ray_cast(o, d, 10.0)
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + d * 1e-5
        return n % 2

    for f in range(0, int(act.frame_range[1]) + 1):
        scn.frame_set(f)
        bpy.context.view_layer.update()
        p = arm.pose.bones["hand_l_target"].matrix.translation.copy()
        tests = [("body", bvh_body)]
        if f <= 10 or f >= 100:
            tests.append(("magazine", bvh_mag))
        for label, bvh in tests:
            loc, nrm, idx, dist = bvh.find_nearest(p)
            if (p - grip_l).length < 0.01 and dist < 0.005:
                continue                                # grip_l itself is on the handguard surface
            if dist < worst[label][0]:
                worst[label] = (dist, f)
            if sum(parity(bvh, p, d) for d in dirs) >= 2:
                inside.append((f, label, r3(p), round(dist * 100, 2)))
    HAND["clearance_cm"] = {k: {"min_cm": round(v[0] * 100, 2), "frame": v[1]} for k, v in worst.items()}
    HAND["penetrations"] = inside
    log("hand target clearance cm", HAND["clearance_cm"], "penetrations", inside)
    scn.frame_set(0)
    assert not inside, "hand_l_target penetrates the gun: %s" % inside


def hand_delta_sample(arm, frame, bone="hand_l_target"):
    """(armature-space rotation delta of the hand target from its rest, bone-local scale X) at `frame`.
    Works in the authoring scene and on a re-imported armature: the object matrix W and the bone's rest rotation
    Rr are both divided out (pose 3x3 = Rr Rb Sb; delta = W Rr Rb Rr^-1 W^-1), the curl scale is removed first."""
    scn = bpy.context.scene
    scn.frame_set(frame)
    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    W3 = arm.matrix_world.to_3x3()
    sb = pb.matrix_basis.to_scale()
    A = W3 @ pb.matrix.to_3x3() @ Matrix.Diagonal(sb).inverted()
    Bm = W3 @ pb.bone.matrix_local.to_3x3()
    return (A @ Bm.inverted()).normalized(), sb.x


def rot_angle_deg(R):
    a = math.degrees(R.to_3x3().to_quaternion().angle)
    return min(a, 360.0 - a)


def hand_track_audit(arm, act, label, assert_ok=True):
    """B7 track rules on the hand target of `act`: rotation identity (< 2 deg) at f0 and the last frame, finite and
    < 150 deg between consecutive frames (every frame AND every 6th frame, ValidateGunClips samples the latter),
    scale X 1.0 +-0.02 at the ends and within [0.4, 1.6] always. Returns the numbers for the JSON."""
    ensure_slot(arm, act)
    n = int(act.frame_range[1])
    Rs, sx = {}, {}
    for f in range(n + 1):
        Rs[f], sx[f] = hand_delta_sample(arm, f)

    def step(a, b):
        return rot_angle_deg(Rs[b] @ Rs[a].inverted())

    ends = {str(f): round(rot_angle_deg(Rs[f]), 3) for f in (0, n)}
    s1 = max([step(f, f + 1) for f in range(n)] or [0.0])
    s6 = max([step(f, min(f + 6, n)) for f in range(0, n, 6)] or [0.0])
    res = {"frames": n, "identity_deg_f0_end": ends, "max_step_deg_every_frame": round(s1, 2),
           "max_step_deg_every_6th": round(s6, 2), "scale_x_f0_end": {str(f): round(sx[f], 4) for f in (0, n)},
           "scale_x_min_max": [round(min(sx.values()), 4), round(max(sx.values()), 4)],
           "finite": all(math.isfinite(v) for v in sx.values()) and all(all(math.isfinite(c) for r in R for c in r) for R in Rs.values())}
    log(label, "hand_l_target track audit", res)
    bpy.context.scene.frame_set(0)
    if assert_ok:
        assert res["finite"], "%s: non-finite hand track" % label
        assert all(v < 2.0 for v in ends.values()), "%s: hand rotation not identity at the ends %s" % (label, ends)
        assert s1 < HAND_ROT_MAX_STEP_DEG and s6 < HAND_ROT_MAX_STEP_DEG, "%s: hand rotation swings the long way %s" % (label, res)
        assert all(abs(v - 1.0) <= 0.02 for v in res["scale_x_f0_end"].values()), "%s: curl not 1.0 at the ends %s" % (label, res)
        assert HAND_CURL_RANGE[0] <= res["scale_x_min_max"][0] and res["scale_x_min_max"][1] <= HAND_CURL_RANGE[1], \
            "%s: curl out of range %s" % (label, res)
    return res


def author_clips(arm, sk, face_part):
    clips = {}
    cm = 0.01
    B = BOLT_TRAVEL
    TILT = MAG_TILT * MAG_TILT_SIGN

    c = ClipAuthor(arm, "A_%s_Idle" % PREFIX, 1)
    c.key("bolt_carrier", 0)
    c.key("bolt_carrier", 1)
    clips["Idle"] = c.apply()

    # Fire 0.12 s (0..7): carrier back 9 cm over 2 frames, forward over 4, 1-frame settle; trigger 8 deg
    log("idle ok")
    c = ClipAuthor(arm, "A_%s_Fire" % PREFIX, 7)
    c.key("bolt_carrier", 0, (0, 0, 0), interp='EXPO', easing='EASE_OUT')
    c.key("bolt_carrier", 2, (-B, 0, 0), interp='QUAD', easing='EASE_IN')
    c.key("bolt_carrier", 5, (-1.2 * cm, 0, 0), interp='QUAD', easing='EASE_IN')
    c.key("bolt_carrier", 6, (0, 0, 0), interp='QUAD', easing='EASE_OUT')
    c.key("bolt_carrier", 7, (0, 0, 0))
    c.key("trigger", 0, rot=('Y', 0.0), interp='QUAD', easing='EASE_OUT')
    c.key("trigger", 1, rot=('Y', TRIGGER_SIGN * 8.0), interp='SINE', easing='EASE_IN_OUT')
    c.key("trigger", 4, rot=('Y', 0.0))
    c.key("trigger", 7, rot=('Y', 0.0))
    clips["Fire"] = c.apply()

    # DryFire 0.15 s (0..9): trigger only
    c = ClipAuthor(arm, "A_%s_DryFire" % PREFIX, 9)
    c.key("trigger", 0, rot=('Y', 0.0), interp='QUAD', easing='EASE_OUT')
    c.key("trigger", 1, rot=('Y', TRIGGER_SIGN * 8.0), interp='SINE', easing='EASE_IN_OUT')
    c.key("trigger", 4, rot=('Y', TRIGGER_SIGN * 8.0), interp='SINE', easing='EASE_IN_OUT')
    c.key("trigger", 7, rot=('Y', 0.0))
    c.key("trigger", 9, rot=('Y', 0.0))
    clips["DryFire"] = c.apply()

    # Reload 2.4 s (0..144). AK: bolt starts forward. Left-hand choreography (design items 2+3, 2026-10-30):
    #   f0-f8    hand_l_target leaves grip_l for the mag's LEFT face (cup point: 6 cm below the lug, 1 cm outside)
    #   f8-f10   thumb on the lever (mag still)
    #   f10-f20  hand rocks the mag forward 25 deg about the lug (hand rides the cup point rigidly)
    #   f20-f30  hand pulls the mag DOWN WITH IT ~12 cm along the existing drop line, then releases
    #   f30-f45  empty mag free-falls (v0 from the pull + g) to ~58 cm below the well and is HIDDEN (scale 0.001)
    #   f30-f56  hand continues down to the belt (+6,-14,-42 cm UE); f56-f62 closes on the fresh mag
    #   f62      fresh mag POPS IN at the hand (scale 1, position = hand - rotated cup offset, 25 deg tilt)
    #   f62-f104 hand carries the mag: belt hold, rise f72-f86, lug hooked f92, locks f100, snap f101, rest f104
    #   f104-f110 hand snaps round the front of the mag and under the right side to the charging-handle knob
    #   f110-f126 hand racks the knob 9 cm back with the bolt_carrier keys, lets go at f126 (bolt slams f130)
    #   f130-f144 hand returns under the right side of the handguard to grip_l
    # The empty mag never rises back: it is hidden until the pop-in at the belt (MAGAZINE CONTINUITY rule).
    cup, knob = HAND["cup_rest"], HAND["knob_rest"]
    cup_off = HAND["cup_offset"]
    mag_head = arm.pose.bones["magazine"].bone.matrix_local.translation.copy()
    grip_l = arm.pose.bones["grip_l"].bone.matrix_local.translation.copy()
    # fresh mag at the belt: cup point (rotated by the 25 deg carry tilt) lands on the hand target
    pop_T = HAND_BELT - mag_head - (Matrix.Rotation(math.radians(TILT), 3, 'Y') @ cup_off)
    # free fall from the release point: pull speed 12 cm / 10 f = 0.72 m/s, g = 9.6
    v0 = 0.12 / (10.0 / FPS)

    def fall_z(f):
        t = (f - 30) / FPS
        return -0.12 - v0 * t - 0.5 * MAG_G * t * t

    c = ClipAuthor(arm, "A_%s_Reload" % PREFIX, 144)
    c.key("magazine", 0, (0, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("magazine", 10, (0, 0, 0), interp='QUAD', easing='EASE_IN')                 # thumb on the lever
    c.key("magazine", 20, (0, 0, 0), rot=('Y', TILT), interp='SINE', easing='EASE_IN_OUT')  # rocked out by the hand
    c.key("magazine", 30, (1.6 * cm, -0.8 * cm, -12.0 * cm), rot=('Y', TILT * 1.08), interp='QUAD', easing='EASE_IN')  # released
    c.key("magazine", 37, (2.8 * cm, -1.4 * cm, fall_z(37)), rot=('Y', TILT * 1.16), interp='LINEAR')
    c.key("magazine", 45, (4.0 * cm, -2.0 * cm, fall_z(45)), rot=('Y', TILT * 1.28), interp='LINEAR')  # ~58 cm down: hidden
    c.key("magazine", 61, pop_T, rot=('Y', TILT), interp='LINEAR')                    # still hidden, parked at the belt
    c.key("magazine", 62, pop_T, rot=('Y', TILT), interp='SINE', easing='EASE_IN_OUT')  # pops in, in the hand
    c.key("magazine", 72, pop_T, rot=('Y', TILT), interp='SINE', easing='EASE_IN_OUT')  # hand closed, rise starts
    c.key("magazine", 86, (0.5 * cm, 0.0, -6.0 * cm), rot=('Y', TILT), interp='QUAD', easing='EASE_OUT')
    c.key("magazine", 92, (0.0, 0.0, 0.0), rot=('Y', TILT), interp='QUAD', easing='EASE_IN')    # lug hooked
    c.key("magazine", 100, (0.0, 0.0, 0.0), rot=('Y', 0.0), interp='QUAD', easing='EASE_OUT')   # locks
    c.key("magazine", 101, (0.0, 0.0, 0.2 * cm), rot=('Y', -TILT * 0.06), interp='SINE', easing='EASE_IN_OUT')  # snap
    c.key("magazine", 104, (0.0, 0.0, 0.0), rot=('Y', 0.0))
    c.key("magazine", 144, (0.0, 0.0, 0.0), rot=('Y', 0.0))
    c.key_scale("magazine", 0, 1.0)
    c.key_scale("magazine", 45, MAG_HIDE_SCALE)       # hidden hold f45-f61
    c.key_scale("magazine", 62, 1.0)                  # pop-in at the hand
    c.key_scale("magazine", 144, 1.0)
    c.key("bolt_carrier", 0, (0, 0, 0))
    c.key("bolt_carrier", 110, (0, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 122, (-B, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 126, (-B, 0, 0), interp='QUAD', easing='EASE_IN')       # let go
    c.key("bolt_carrier", 130, (0, 0, 0), interp='QUAD', easing='EASE_OUT')       # slams home
    c.key("bolt_carrier", 131, (-0.6 * cm, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 134, (0, 0, 0))
    c.key("bolt_carrier", 144, (0, 0, 0))
    c.apply()                                         # pass 1: mechanical keys, so the hand can sample them
    H = "hand_l_target"
    hand_keys = {}

    def hk(frame, pos, **kw):
        hand_keys[frame] = Vector(pos)
        c.key_at(H, frame, pos, **kw)

    hk(0, grip_l, interp='SINE', easing='EASE_IN_OUT')
    for f in range(8, 31):                            # grab, rock, pull: glued to the mag's cup point
        hk(f, c.point_on("magazine", f, cup), **({"interp": 'SINE', "easing": 'EASE_IN_OUT'} if f == 30 else {}))
    hk(56, HAND_BELT, interp='SINE', easing='EASE_IN_OUT')      # at the belt
    for f in range(62, 105):                          # closes on the fresh mag and carries it into the well
        hk(f, c.point_on("magazine", f, cup), **({"interp": 'LINEAR'} if f == 104 else {}))
    # mag at z -8.4 cm spans x 12.9..24.1, y +-2.8; receiver <= +-4 cm wide at knob height: vias stay clear
    hk(106, (0.27, 0.035, -0.10), interp='LINEAR')    # forward along the mag's left face, past its front edge
    hk(108, (0.27, -0.065, -0.06), interp='LINEAR')   # across the front of the mag to the right side
    for f in range(110, 127):                         # pinches the knob and racks it with bolt_carrier
        hk(f, c.point_on("bolt_carrier", f, knob))
    hk(130, c.point_on("bolt_carrier", 126, knob) + Vector((0, -0.01, 0)), interp='SINE', easing='EASE_IN_OUT')  # let go
    hk(138, (0.22, -0.08, 0.02), interp='SINE', easing='EASE_IN_OUT')
    hk(141, (0.30, -0.045, 0.0), interp='SINE', easing='EASE_IN_OUT')
    hk(144, grip_l)
    # --- orientation (rotation delta from rest) + finger curl, same frames and easing as the position beats (B5) ---
    # grab/rock/pull and the carry ride the magazine rigidly: the hand turns with the mag's tilt (rot_on) on top of
    # the grab delta. The snap round the front (f104-f110) rolls the palm right -> down -> down-left in <= 55 deg
    # steps; the return (f130-f144) rolls it left -> up-left -> up -> rest (identity) in <= 92 deg steps.
    D = {k: hand_delta_bl(k) for k in HAND_ORI}
    rot_log = {}
    curl_log = {}

    def hr(frame, ori, ride=None, **kw):
        R = D[ori] if ori else Matrix.Identity(3)
        if ride is not None:
            R = c.rot_on(ride, frame) @ R
        c.key_rot(H, frame, R, **kw)
        rot_log[frame] = (ori or "rest", R.copy())

    def hc(frame, curl, **kw):
        c.key_curl(H, frame, curl, **kw)
        curl_log[frame] = curl

    hr(0, None, interp='SINE', easing='EASE_IN_OUT')
    for f in range(8, 31):
        hr(f, "grab", ride="magazine", **({"interp": 'SINE', "easing": 'EASE_IN_OUT'} if f == 30 else {}))
    hr(56, "belt", interp='SINE', easing='EASE_IN_OUT')
    hr(59, "belt", interp='SINE', easing='EASE_IN_OUT')
    for f in range(62, 105):
        hr(f, "grab", ride="magazine", **({"interp": 'LINEAR'} if f == 104 else {}))
    hr(106, "front", interp='LINEAR')
    hr(108, "rise", interp='LINEAR')
    for f in range(110, 127):
        hr(f, "pinch")
    hr(130, "pinch", interp='SINE', easing='EASE_IN_OUT')
    hr(134, "slide", interp='SINE', easing='EASE_IN_OUT')
    hr(138, "under", interp='SINE', easing='EASE_IN_OUT')
    hr(141, "cup_up", interp='SINE', easing='EASE_IN_OUT')
    hr(144, None)
    hc(0, 1.0, interp='SINE', easing='EASE_IN_OUT')
    hc(8, HAND_CURL["grab"])
    hc(30, HAND_CURL["grab"], interp='SINE', easing='EASE_IN_OUT')
    hc(56, HAND_CURL["belt"], interp='SINE', easing='EASE_IN_OUT')
    hc(59, HAND_CURL["belt"], interp='SINE', easing='EASE_IN_OUT')
    hc(62, HAND_CURL["grab"])                         # closes on the fresh mag as it pops in
    hc(104, HAND_CURL["grab"], interp='LINEAR')
    hc(106, HAND_CURL["front"], interp='LINEAR')
    hc(110, HAND_CURL["pinch"])
    hc(126, HAND_CURL["pinch"])
    hc(130, HAND_CURL["pinch"], interp='SINE', easing='EASE_IN_OUT')
    hc(138, HAND_CURL["under"], interp='SINE', easing='EASE_IN_OUT')
    hc(144, 1.0)
    clips["Reload"] = c.apply()                       # pass 2: hand keys added
    HAND["reload_keys"] = hand_keys
    HAND["rot_keys_bl"] = rot_log
    HAND["curl_keys"] = curl_log
    HAND["pop_T"] = pop_T
    HAND["phases"] = {"grab": [0, 8], "lever": [8, 10], "rock": [10, 20], "pull": [20, 30], "mag_free_fall": [30, 45],
                      "mag_hidden": [45, 62], "hand_to_belt": [30, 56], "hand_closes": [56, 62], "carry": [62, 104],
                      "to_knob": [104, 110], "rack": [110, 126], "let_go": [126, 130], "return": [130, 144]}
    # authored-track audit (before export): identity at the ends, no long-way swings, curl in range, per-key steps
    steps = []
    frames = sorted(rot_log)
    for a, b in zip(frames, frames[1:]):
        ang = math.degrees((rot_log[b][1] @ rot_log[a][1].inverted()).to_quaternion().angle)
        ang = min(ang, 360.0 - ang)
        steps.append((a, b, round(ang, 1)))
    HAND["rot_key_steps_deg"] = [s for s in steps if s[2] > 5.0]
    log("hand rotation key steps > 5 deg (f_from, f_to, deg):", HAND["rot_key_steps_deg"])
    assert all(s[2] < HAND_ROT_MAX_STEP_DEG for s in steps), "hand rotation key goes the long way: %s" % steps
    HAND["authored_track"] = hand_track_audit(arm, c.act, "authored Reload")
    check_hand_clear(arm, c.act, sk, face_part)

    # Chamber 1.1 s (0..66): rack 9 cm and release
    c = ClipAuthor(arm, "A_%s_Chamber" % PREFIX, 66)
    c.key("bolt_carrier", 0, (0, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 8, (0, 0, 0), interp='QUAD', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 30, (-B, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 38, (-B, 0, 0), interp='QUAD', easing='EASE_IN')
    c.key("bolt_carrier", 43, (0, 0, 0), interp='QUAD', easing='EASE_OUT')
    c.key("bolt_carrier", 44, (-0.6 * cm, 0, 0), interp='SINE', easing='EASE_IN_OUT')
    c.key("bolt_carrier", 47, (0, 0, 0))
    c.key("bolt_carrier", 66, (0, 0, 0))
    clips["Chamber"] = c.apply()
    return clips


# ============================================================================
# 5. export (settings identical to RigM4A1.py)
# ============================================================================
FBX_COMMON = dict(
    global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
    use_space_transform=True, bake_space_transform=False,
    axis_forward='-Y', axis_up='Z',
    mesh_smooth_type='FACE', use_tspace=True, use_triangles=False, use_custom_props=False,
    add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
    use_armature_deform_only=False, armature_nodetype='NULL',
    path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_metadata=True,
    colors_type='NONE',
)


def export_all(arm, sk, clips):
    paths = {}
    scn = bpy.context.scene
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    scn.frame_set(0)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
    select_only([arm, sk], arm)
    p = os.path.join(OUT_DIR, "SK_%s.fbx" % PREFIX)
    bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={'ARMATURE', 'MESH'},
                             bake_anim=False, **FBX_COMMON)
    paths["mesh"] = p
    log("exported", p, os.path.getsize(p))
    for name, act in clips.items():
        ensure_slot(arm, act)
        scn.frame_start = 0
        scn.frame_end = int(act.frame_range[1])
        scn.name = act.name
        scn.frame_set(scn.frame_end)          # bind pose is written from the current pose: rest
        bpy.context.view_layer.update()
        for pb in arm.pose.bones:
            m = pb.matrix_basis
            if m.translation.length > 1e-5 or abs(m.to_quaternion().angle) > 1e-4 \
                    or any(abs(s - 1.0) > 1e-4 for s in m.to_scale()):
                raise RuntimeError("clip %s does not end on rest: %s" % (act.name, pb.name))
        # mesh + armature in every clip file: UE 5.8 Interchange refuses armature-only FBX
        # ("nothing to import"); same as RigM4A1.py / RigEM_21.py. Import onto SK_EM11's skeleton.
        select_only([arm, sk], arm)
        p = os.path.join(OUT_DIR, act.name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={'ARMATURE', 'MESH'},
                                 bake_anim=True, bake_anim_use_all_bones=True,
                                 bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                                 bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                                 bake_anim_simplify_factor=0.0, **FBX_COMMON)
        paths[name] = p
        log("exported", p, os.path.getsize(p), "frames", scn.frame_end)
    ad.action = None
    scn.name = "Scene"
    return paths


# ============================================================================
# 6. proof renders: top band 3/4 right (ortho), bottom-left mag-well close-up,
#    bottom-right knob/trigger close-up
# ============================================================================
PART_COL = {"body": (0.50, 0.50, 0.52, 1), "magazine": (0.20, 0.45, 0.95, 1),
            "bolt_carrier": (1.0, 0.80, 0.10, 1), "trigger": (0.95, 0.15, 0.15, 1),
            "cap_body": (1.0, 0.45, 0.05, 1), "cap_part": (0.10, 0.85, 0.85, 1)}


def setup_render(arm, sk, face_part, face_cap):
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_WORKBENCH'
    scn.display.shading.light = 'STUDIO'
    scn.display.shading.color_type = 'MATERIAL'
    scn.display.shading.show_cavity = True
    scn.display.shading.show_object_outline = True
    scn.display.shading.show_specular_highlight = True
    scn.display.shading.show_backface_culling = True     # a hole would show through
    scn.render.film_transparent = False
    world = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("Proof")
    scn.world = world
    world.color = (0.35, 0.36, 0.38)
    scn.view_settings.view_transform = 'Standard'
    scn.render.image_settings.file_format = 'PNG'
    scn.render.resolution_percentage = 100
    # render-only material slots (the FBX was already written with the single vendor slot)
    keys = ["body", "magazine", "bolt_carrier", "trigger", "cap_body", "cap_part"]
    sk.data.materials.clear()
    for k in keys:
        m = bpy.data.materials.get("proof_" + k) or bpy.data.materials.new("proof_" + k)
        m.diffuse_color = PART_COL[k]
        sk.data.materials.append(m)
    for p, fp, fc in zip(sk.data.polygons, face_part, face_cap):
        if fc:
            p.material_index = 5 if fp else 4
        else:
            p.material_index = fp
    O = GUN["origin"]
    cams = {}

    def cam(name, ortho, lens, eye, tgt, scale=1.0):
        cd = bpy.data.cameras.new(name)
        if ortho:
            cd.type = 'ORTHO'
            cd.ortho_scale = scale
        else:
            cd.lens = lens
        cd.clip_start = 0.01
        cd.clip_end = 50
        co = bpy.data.objects.new(name, cd)
        scn.collection.objects.link(co)
        co.location = eye
        co.rotation_euler = (tgt - eye).to_track_quat('-Z', 'Y').to_euler()
        cams[name] = co

    # the top band is 60 px taller than the 2026-10-29 layout (620 instead of 560) and the 3/4 targets sit 30 px
    # higher, so the gun drops 60 px below the two-line render stamp that would otherwise cover the knob-side hand
    # (ortho px/m = 1600 / ortho_scale: 1231 for the 1.30 views, 727 for the 2.2 wide views)
    centre = Vector((0.02, 0.0, 0.10)) - O + Vector((0.0, 0.0, 30.0 * 1.30 / 1600.0))
    d = Vector((0.42, -1.0, 0.22)).normalized()
    cam("Cam34", True, 0, centre + d * 4.0, centre, 1.30)
    wide = centre + Vector((0.0, 0.0, -0.12 + 30.0 * (2.2 - 1.30) / 1600.0))   # mag-out framing: keeps the dropped mag in view
    cam("Cam34Wide", True, 0, wide + d * 4.0, wide, 2.2)
    cam("CamWell", False, 30, Vector((0.24, -0.30, -0.02)) - O, Vector((0.07, 0.0, 0.15)) - O)
    cam("CamBolt", False, 30, Vector((0.10, -0.34, 0.30)) - O, Vector((0.005, -0.02, 0.228)) - O)
    # left-side mirrors for the hand proofs: the hand target cups the gun's LEFT (+Y) face of the mag,
    # which the right-side cameras cannot see
    dl = Vector((0.42, 1.0, 0.22)).normalized()
    cam("Cam34L", True, 0, centre + dl * 4.0, centre, 1.30)
    cam("Cam34LWide", True, 0, wide + dl * 4.0, wide, 2.2)
    cam("CamWellL", False, 30, Vector((0.24, 0.30, -0.02)) - O, Vector((0.07, 0.0, 0.15)) - O)
    cams["_marker"] = build_palm_proxy(scn)
    # curl + delta text burnt into the top band by the render stamp (Workbench honours it); other stamp items off
    for attr in [a for a in dir(scn.render) if a.startswith("use_stamp")]:
        try:
            setattr(scn.render, attr, False)
        except AttributeError:
            pass
    scn.render.stamp_font_size = 26
    scn.render.stamp_foreground = (1.0, 1.0, 1.0, 1.0)
    scn.render.stamp_background = (0.0, 0.0, 0.0, 0.65)
    return cams


def build_palm_proxy(scn):
    """PALM PROXY for the proofs (B6, render only, never exported: export_all runs before this and selects only the
    armature + mesh). Replaces the 1.5 cm sphere: a flat 8 x 10 cm plate in the palm plane (magenta = the palm
    surface, dark purple = back of the hand, grey rim), a 6 cm bright-green arrow along the fingers and a 5.5 cm
    white stub toward the thumb side. Built in hand-local coordinates (x fingers, palm out at -y, thumb at -z) with
    the local y mirrored (local' = M local), then rotated by the REST hand frame converted to Blender space
    (R0_bl = M R0_ue M, a proper rotation, so face winding survives back-face culling): at identity it shows how the
    Rifle aim pose holds the left palm (up-right at the handguard from under-left); render_proof then applies the
    keyed delta, so a human can see the palm face the mag / knob / handguard at each beat."""
    bm = bmesh.new()
    parts = []          # (verts, material index)

    def add(op, mat_idx, **kw):
        before = set(bm.faces)
        op(bm, **kw)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            if f not in before:
                f.material_index = mat_idx
                f.smooth = False

    # plate: x +-5 cm (fingers), z +-4 cm (across), y +-0.15 cm; palm face is +y in the mirrored local frame
    add(bmesh.ops.create_cube, 2, size=1.0, matrix=Matrix.Diagonal((0.10, 0.003, 0.08, 1.0)))
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y > 0.5:
            f.material_index = 0           # palm surface
        elif f.normal.y < -0.5:
            f.material_index = 1           # back of the hand
    # finger arrow on the palm side: shaft 0..4.8 cm + cone to 6 cm along +x
    shaft = Matrix.Translation((0.024, 0.0045, 0.0)) @ Matrix.Rotation(math.radians(90), 4, 'Y') @ Matrix.Diagonal((1, 1, 1, 1))
    add(bmesh.ops.create_cone, 3, cap_ends=True, segments=12, radius1=0.0035, radius2=0.0035, depth=0.048, matrix=shaft)
    head = Matrix.Translation((0.054, 0.0045, 0.0)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
    add(bmesh.ops.create_cone, 3, cap_ends=True, segments=12, radius1=0.009, radius2=0.0, depth=0.012, matrix=head)
    # thumb stub: 0..5.5 cm along -z (the thumb side), on the palm side too
    thumb = Matrix.Translation((0.0, 0.0045, -0.0275)) @ Matrix.Diagonal((1, 1, 1, 1))
    add(bmesh.ops.create_cone, 4, cap_ends=True, segments=10, radius1=0.003, radius2=0.003, depth=0.055, matrix=thumb)
    # mirrored-local -> armature rest: v_bl = M R0_ue local = (M R0_ue M)(M local); the mesh is already in M local
    R0_bl = rot_ue_to_bl(REST_HAND_UE)
    assert abs(R0_bl.determinant() - 1.0) < 1e-5
    bmesh.ops.transform(bm, matrix=R0_bl.to_4x4(), verts=bm.verts)
    bm.normal_update()
    md = bpy.data.meshes.new("PalmProxy")
    bm.to_mesh(md)
    bm.free()
    proxy = bpy.data.objects.new("PalmProxy", md)
    scn.collection.objects.link(proxy)
    for name, col in (("proof_palm", (1.0, 0.05, 0.85, 1)), ("proof_palm_back", (0.22, 0.04, 0.26, 1)),
                      ("proof_palm_rim", (0.65, 0.65, 0.65, 1)), ("proof_finger_arrow", (0.15, 1.0, 0.2, 1)),
                      ("proof_thumb", (1.0, 1.0, 1.0, 1))):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = col
        proxy.data.materials.append(m)
    proxy.show_in_front = False
    return proxy


def place_palm_proxy(arm, proxy):
    """pin the proxy to the hand target at the current frame: translation + keyed delta (curl scale removed)"""
    pb = arm.pose.bones["hand_l_target"]
    Rd, sx = hand_delta_sample(arm, bpy.context.scene.frame_current)
    proxy.matrix_world = arm.matrix_world @ Matrix.Translation(pb.matrix.translation) @ Rd.to_4x4()
    R_ue = rot_bl_to_ue(Rd)
    axis, deg = axis_angle_ue(R_ue)
    palm, fingers = hand_frame_ue(R_ue)
    return {"curl": round(sx, 3), "axis_ue": axis, "deg": deg, "palm_normal_ue": palm, "finger_dir_ue": fingers}


def render_proof(arm, act, frame, filename, cams, tmpdir, main_cam="Cam34", well_cam="CamWell"):
    import numpy as np
    scn = bpy.context.scene
    ensure_slot(arm, act)
    scn.frame_start = 0
    scn.frame_end = int(act.frame_range[1])
    scn.frame_set(frame)
    bpy.context.view_layer.update()
    hs = place_palm_proxy(arm, cams["_marker"])
    hs.update({"clip": act.name, "frame": frame, "file": filename})
    PROOF_HAND.append(hs)
    note = ("%s f%d | palm proxy: curl %.2f | delta (UE gun space) axis (%.2f, %.2f, %.2f) %.1f deg | palm normal UE (%.2f, %.2f, %.2f)"
            " | fingers UE (%.2f, %.2f, %.2f)" % ((act.name, frame, hs["curl"]) + tuple(hs["axis_ue"]) + (hs["deg"],)
                                                  + tuple(hs["palm_normal_ue"]) + tuple(hs["finger_dir_ue"])))
    imgs = {}
    pick = {"Cam34": main_cam, "CamWell": well_cam, "CamBolt": "CamBolt"}
    for cam_name, res in (("Cam34", (1600, 620)), ("CamWell", (800, 340)), ("CamBolt", (800, 340))):
        scn.camera = cams[pick[cam_name]]
        scn.render.use_stamp = cam_name == "Cam34"
        scn.render.use_stamp_note = cam_name == "Cam34"
        scn.render.stamp_note_text = note
        scn.render.resolution_x, scn.render.resolution_y = res
        p = os.path.join(tmpdir, "tmp_%s.png" % cam_name)
        scn.render.filepath = p
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(p)
        imgs[cam_name] = np.array(im.pixels[:]).reshape(im.size[1], im.size[0], 4)
        bpy.data.images.remove(im)
    bottom = np.concatenate([imgs["CamWell"], imgs["CamBolt"]], axis=1)
    bottom[:, 798:802, :3] = 0.1      # divider
    stacked = np.concatenate([bottom, imgs["Cam34"]], axis=0)   # rows bottom-up
    stacked[338:342, :, :3] = 0.1
    out = bpy.data.images.new("proof", 1600, 960, alpha=True)
    out.pixels = stacked.ravel().tolist()
    out.filepath_raw = os.path.join(OUT_DIR, filename)
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    log("proof", filename, "clip", act.name, "frame", frame)
    return os.path.join(OUT_DIR, filename)


# ============================================================================
# 7. verification by re-import
# ============================================================================
def bone_world(arm, name):
    return arm.matrix_world @ arm.pose.bones[name].matrix


def fbx_scan(path):
    """Raw-byte scan, same test as Scripts/ImportEMGuns.py preflight."""
    with open(path, "rb") as f:
        data = f.read()
    return {"armature_node": data.count(ARMATURE_OBJECT_NAME.encode()) > 0,
            "data_name_leaked": data.count(ARM_NAME.encode()) > 0,
            "mesh_name": data.count(MESH_NAME.encode()) > 0,
            "geometry": data.count(b"Geometry") > 0}


def assert_ue_ready(path, label):
    """UE-ready: top armature node 'Armature' (no extra x100 root bone) and a mesh payload."""
    scan = fbx_scan(path)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    res = {"bytes": os.path.getsize(path), "scan": scan, "armature_object": [o.name for o in arms],
           "mesh_objects": [o.name for o in meshes],
           "mesh_polys": [len(o.data.polygons) for o in meshes],
           "mesh_parent": [o.parent.name if o.parent else None for o in meshes]}
    log("ue-ready", label, res)
    assert scan["armature_node"] and not scan["data_name_leaked"], "%s: armature node not 'Armature' %s" % (label, scan)
    assert scan["mesh_name"] and scan["geometry"], "%s: no mesh payload %s" % (label, scan)
    assert [o.name for o in arms] == [ARMATURE_OBJECT_NAME], "%s: armature objects %s" % (label, res["armature_object"])
    assert len(meshes) == 1 and meshes[0].name == MESH_NAME and len(meshes[0].data.polygons) > 0, \
        "%s: mesh objects %s" % (label, res["mesh_objects"])
    assert meshes[0].find_armature() == arms[0], "%s: mesh not skinned to the armature" % label
    return res


def verify_reimport(paths, heads):
    report = {}
    bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
    bpy.ops.import_scene.fbx(filepath=paths["mesh"])
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert len(meshes) == 1 and len(arms) == 1, "mesh FBX objects %s" % [o.name for o in bpy.data.objects]
    report["ue_ready"] = {"mesh": assert_ue_ready(paths["mesh"], "SK_%s" % PREFIX)}
    me = meshes[0]
    pts = [me.matrix_world @ v.co for v in me.data.vertices]
    mn, mx = bounds_pts(pts)
    length_cm = (mx.x - mn.x) * 100
    names = [b.name for b in arms[0].data.bones]
    groups = {g.index: g.name for g in me.vertex_groups}
    counts = {}
    bad = 0
    for v in me.data.vertices:
        if len(v.groups) != 1 or abs(v.groups[0].weight - 1.0) > 1e-5:
            bad += 1
        else:
            counts[groups[v.groups[0].group]] = counts.get(groups[v.groups[0].group], 0) + 1
    # rest-pose bone heads should match what we built
    head_err = max((arms[0].matrix_world @ b.head_local - heads[b.name]).length for b in arms[0].data.bones)
    report["mesh"] = {"length_cm": round(length_cm, 2), "bounds_cm": [r3(mn), r3(mx)], "bones": names,
                      "slots": [m.name for m in me.data.materials], "tris": sum(len(p.vertices) - 2 for p in me.data.polygons),
                      "verts_per_group": counts, "non_rigid_verts": bad, "max_bone_head_err_mm": round(head_err * 1000, 3)}
    log("reimport mesh", report["mesh"])
    assert 90 < length_cm < 110, "mesh length off: %.1f" % length_cm
    assert set(names) == set(BONE_ORDER), "bone mismatch %s" % (set(names) ^ set(BONE_ORDER))
    assert bad == 0, "%d non rigid verts" % bad
    assert set(counts) == {"body", "magazine", "bolt_carrier", "trigger"}, counts
    assert head_err < 1e-4, "bone heads moved by %f" % head_err

    B = BOLT_TRAVEL
    expected_frames = {"Idle": 1, "Fire": 7, "DryFire": 9, "Reload": 144, "Chamber": 66}
    checks = {
        "Idle": [("bolt_carrier", 1, (0, 0, 0)), ("magazine", 1, (0, 0, 0))],
        "Fire": [("bolt_carrier", 2, (-B, 0, 0)), ("bolt_carrier", 7, (0, 0, 0)), ("magazine", 2, (0, 0, 0))],
        "DryFire": [("bolt_carrier", 4, (0, 0, 0)), ("magazine", 4, (0, 0, 0))],
        # 2026-10-30 reload re-key: f45 is now the end of the free fall (~58 cm down, then hidden) and the mag
        # is parked at the belt pop-in point f61-f72 instead of rising from -45 cm (was f45 -30, f60 -45).
        "Reload": [("bolt_carrier", 0, (0, 0, 0)), ("magazine", 20, (0, 0, 0)),
                   ("magazine", 30, (0.016, -0.008, -0.12)), ("magazine", 45, (0.04, -0.02, None)),
                   ("magazine", 67, tuple(HAND["pop_T"])),
                   ("magazine", 100, (0, 0, 0)), ("magazine", 144, (0, 0, 0)),
                   ("bolt_carrier", 110, (0, 0, 0)), ("bolt_carrier", 122, (-B, 0, 0)),
                   ("bolt_carrier", 144, (0, 0, 0))],
        "Chamber": [("bolt_carrier", 30, (-B, 0, 0)), ("bolt_carrier", 66, (0, 0, 0))],
    }
    # hand_l_target (design items 2+3) and magazine hide/pop-in checks
    hand_checks = {"Reload": HAND_VERIFY_FRAMES}
    for clip, tests in checks.items():
        bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
        bpy.ops.import_scene.fbx(filepath=paths[clip], anim_offset=0.0)
        bpy.context.view_layer.update()
        scn = bpy.context.scene
        report["ue_ready"][clip] = assert_ue_ready(paths[clip], clip)
        arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
        names = [b.name for b in arm.data.bones]
        acts = list(bpy.data.actions)
        fr = [a.frame_range[:] for a in acts]
        res = {"bones": names, "actions": [a.name for a in acts], "action_frame_range": [list(f) for f in fr],
               "seconds": round((fr[0][1] - fr[0][0]) / FPS, 4), "tests": []}
        assert set(names) == set(BONE_ORDER), "clip %s bone mismatch" % clip
        assert len(acts) == 1, "clip %s actions %s" % (clip, res["actions"])
        assert abs((fr[0][1] - fr[0][0]) - expected_frames[clip]) < 0.01, "clip %s length %s" % (clip, fr)
        edit = {b.name: (arm.matrix_world @ b.head_local).copy() for b in arm.data.bones}
        for bone, frame, expect in tests:
            scn.frame_set(frame)
            bpy.context.view_layer.update()
            dlt = bone_world(arm, bone).translation - edit[bone]
            ok = all(expect[i] is None or abs(dlt[i] - expect[i]) < 0.004 for i in range(3))
            res["tests"].append({"bone": bone, "frame": frame, "delta_cm": r3(dlt), "ok": ok,
                                 "expect_cm": [None if e is None else round(e * 100, 2) for e in expect]})
            log("clip", clip, bone, "f", frame, "delta cm", r3(dlt), "OK" if ok else "FAIL")
            assert ok, "clip %s %s f%d delta %s expect %s" % (clip, bone, frame, dlt, expect)

        def pose_pt(bone, rest_pt):
            """world position of a rest-space point riding rigidly on `bone` at the current frame"""
            pb = arm.pose.bones[bone]
            return arm.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted() @ (arm.matrix_world.inverted() @ Vector(rest_pt))

        def hand_at(frame):
            scn.frame_set(frame)
            bpy.context.view_layer.update()
            return bone_world(arm, "hand_l_target").translation.copy()

        # hand_l_target: present, parked at grip_l at f0 and the last frame of every clip (within 0.3 cm)
        hres = {"present": "hand_l_target" in names, "parent": arm.data.bones["hand_l_target"].parent.name}
        assert hres["present"] and hres["parent"] == "body", hres
        last = expected_frames[clip]
        for f in (0, last):
            d = (hand_at(f) - bone_world(arm, "grip_l").translation).length
            hres["grip_l_dist_cm_f%d" % f] = round(d * 100, 3)
            assert d < 0.003, "clip %s hand_l_target off grip_l at f%d by %.2f cm" % (clip, f, d * 100)
        if clip in hand_checks:
            hc = hand_checks[clip]
            fm = hc["mid_carry_frame"]
            h = hand_at(fm)
            cup_rigid = pose_pt("magazine", HAND["cup_rest"])
            cup_plain = bone_world(arm, "magazine").translation + (arm.matrix_world.to_3x3() @ HAND["cup_offset"])
            hres["mid_carry"] = {"frame": fm, "hand_cm_ue": ue(h), "mag_cup_rigid_cm_ue": ue(cup_rigid),
                                 "dist_rigid_cm": round((h - cup_rigid).length * 100, 3),
                                 "dist_mag_plus_offset_cm": round((h - cup_plain).length * 100, 3),
                                 "mag_head_cm_ue": ue(bone_world(arm, "magazine").translation),
                                 "hand_minus_mag_head_cm_ue": ue(h - bone_world(arm, "magazine").translation),
                                 "note": "hand rides the mag rigidly: offset = mag rotation (25 deg carry tilt) applied to "
                                         "cup_offset_from_magazine_head_cm_ue; the unrotated sum is ~3 cm off"}
            assert hres["mid_carry"]["dist_rigid_cm"] < 2.0, "hand not carrying the mag at f%d: %s" % (fm, hres["mid_carry"])
            h = hand_at(hc["belt_frame"])
            hres["belt"] = {"frame": hc["belt_frame"], "hand_cm_ue": ue(h), "dist_cm": round((h - HAND_BELT).length * 100, 3)}
            assert hres["belt"]["dist_cm"] < 0.5, hres["belt"]
            h = hand_at(hc["knob_back_frame"])
            kb = pose_pt("bolt_carrier", HAND["knob_rest"])
            hres["knob_back"] = {"frame": hc["knob_back_frame"], "hand_cm_ue": ue(h), "knob_pinch_cm_ue": ue(kb),
                                 "dist_cm": round((h - kb).length * 100, 3), "bolt_dx_cm": round((kb - HAND["knob_rest"]).x * 100, 2)}
            assert hres["knob_back"]["dist_cm"] < 1.0 and hres["knob_back"]["bolt_dx_cm"] < -8.5, hres["knob_back"]
            # magazine hidden during the hold (scale ~0.001), visible (1.0) at f0, the fall end and the end
            sc = {}
            for f in (0, hc["mag_fall_end_frame"], hc["mag_hidden_frame"], 62, last):
                scn.frame_set(f)
                bpy.context.view_layer.update()
                sc[f] = round(bone_world(arm, "magazine").to_scale().x / arm.matrix_world.to_scale().x, 4)
            scn.frame_set(hc["mag_fall_end_frame"])
            bpy.context.view_layer.update()
            fall_dz = (bone_world(arm, "magazine").translation - edit["magazine"]).z
            hres["mag_scale"] = sc
            hres["mag_fall_end_dz_cm"] = round(fall_dz * 100, 2)
            assert sc[0] > 0.99 and sc[last] > 0.99 and sc[62] > 0.99, "mag scale not 1 at rest: %s" % sc
            assert sc[hc["mag_hidden_frame"]] < 0.01, "mag not hidden mid-hold: %s" % sc
            assert sc[hc["mag_fall_end_frame"]] < 0.01, "mag visible after the fall end: %s" % sc
            assert fall_dz < -0.55, "mag did not fall 55+ cm before hiding: %.1f cm" % (fall_dz * 100)
            log("clip Reload hand_l_target", hres)
        # B7: rotation (delta from rest) and curl (bone-local scale X) tracks of the re-imported hand target. The
        # re-imported bone must still be identity-oriented (else "scale X" would not be the gun's X) and the
        # per-beat delta must equal the authored one (the FBX bake/import round trip is lossless to < 3 deg).
        pbh = arm.pose.bones["hand_l_target"]
        rest_rot = rot_angle_deg((arm.matrix_world.to_3x3() @ pbh.bone.matrix_local.to_3x3()).normalized())
        hres["rest_rotation_deg_reimported"] = round(rest_rot, 3)
        assert rest_rot < 0.5, "re-imported hand_l_target rest rotation %.2f deg (must stay identity)" % rest_rot
        hres["track_audit"] = hand_track_audit(arm, acts[0], "reimport %s" % clip)
        if clip in hand_checks:
            beats = []
            worst = 0.0
            for beat, f in sorted(HAND_BEAT_FRAMES.items(), key=lambda kv: kv[1]):
                Rd, sx = hand_delta_sample(arm, f)
                R_ue = rot_bl_to_ue(Rd)
                axis, deg = axis_angle_ue(R_ue)
                palm, fingers = hand_frame_ue(R_ue)
                row = {"beat": beat, "frame": f, "axis_ue": axis, "deg": deg, "palm_normal_ue": palm,
                       "finger_dir_ue": fingers, "curl": round(sx, 3)}
                if f in HAND["rot_keys_bl"]:
                    err = rot_angle_deg(Rd @ HAND["rot_keys_bl"][f][1].inverted())
                    row["authored_ori"] = HAND["rot_keys_bl"][f][0]
                    row["vs_authored_deg"] = round(err, 3)
                    worst = max(worst, err)
                if f in HAND["curl_keys"]:
                    row["authored_curl"] = HAND["curl_keys"][f]
                    row["curl_err"] = round(abs(sx - HAND["curl_keys"][f]), 4)
                beats.append(row)
                log("clip Reload beat %-10s f%-3d curl %.2f  delta UE axis %s %.1f deg  palm %s fingers %s%s"
                    % (beat, f, sx, axis, deg, palm, fingers, ("  (vs authored %.2f deg)" % row["vs_authored_deg"]) if "vs_authored_deg" in row else ""))
            hres["beats"] = beats
            hres["max_beat_rotation_err_vs_authored_deg"] = round(worst, 3)
            assert worst < 3.0, "re-imported hand rotation differs from the authored keys by %.2f deg" % worst
            assert all(r.get("curl_err", 0.0) < 0.02 for r in beats), "re-imported curl differs: %s" % beats
        res["hand_l_target"] = hres

        def rigid_probe(bone, f0, f1, offset):
            scn.frame_set(f0)
            bpy.context.view_layer.update()
            m0 = bone_world(arm, bone).copy()
            scn.frame_set(f1)
            bpy.context.view_layer.update()
            m1 = bone_world(arm, bone).copy()
            pl = m0.inverted() @ (m0.translation + offset)
            dv = (m1 @ pl) - (m0 @ pl)
            ang = math.degrees((m0.to_3x3().inverted() @ m1.to_3x3()).to_quaternion().angle)
            return dv, ang

        if clip in ("Fire", "DryFire"):
            dv, ang = rigid_probe("trigger", 0, 1, Vector((0, 0, -0.025)))
            res["trigger_bottom_dx_cm"] = round(dv.x * 100, 3)
            res["trigger_angle_deg"] = round(ang, 2)
            log("clip", clip, "trigger tip dx cm", round(dv.x * 100, 3), "angle", round(ang, 2))
            assert dv.x < -0.002 and 7 < ang < 9, "trigger %f %f" % (dv.x, ang)
        if clip == "Reload":
            dv, ang = rigid_probe("magazine", 0, 20, Vector((0, 0, -0.15)))
            res["mag_tilt_f20_deg"] = round(ang, 2)
            res["mag_point_15cm_below_lug_dx_cm_f20"] = round(dv.x * 100, 2)
            log("clip Reload mag tilt f20", round(ang, 2), "deg; point 15 cm below lug dx cm", round(dv.x * 100, 2))
            assert 23 < ang < 27 and dv.x > 0.04, "mag tilt wrong %f %f" % (ang, dv.x)
            dv, ang = rigid_probe("magazine", 0, 101, Vector((0, 0, -0.15)))
            res["mag_snap_overshoot_f101_deg"] = round(ang, 2)
        report[clip] = res
    return report


# ============================================================================
# main
# ============================================================================
def main():
    times = {}
    check_rotation_convention()          # numeric proof of the Blender<->UE rotation mapping before anything is keyed
    t = time.time()
    ob = stage_import()
    times["import"] = round(time.time() - t, 1)
    t = time.time()
    report, face_part, face_cap, vgroup_of, planes = stage_cut(ob)
    times["cut"] = round(time.time() - t, 1)
    t = time.time()
    arm, heads = stage_rig(ob, report, vgroup_of, planes)
    log("authoring clips")
    clips = author_clips(arm, ob, face_part)
    log("clips authored")
    times["rig+clips"] = round(time.time() - t, 1)
    mn, mx = bounds_pts([v.co for v in ob.data.vertices])
    blend = os.path.join(OUT_DIR, "EM11_rig.blend")
    # third-party add-on save handlers (comfyui etc.) crash after read_factory_settings in -b runs
    for h in (bpy.app.handlers.save_pre, bpy.app.handlers.save_post):
        h.clear()
    bpy.context.preferences.filepaths.save_version = 0      # no .blend1 on re-runs
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    log("saved", blend)
    t = time.time()
    paths = export_all(arm, ob, clips)
    times["export"] = round(time.time() - t, 1)
    t = time.time()
    cams = setup_render(arm, ob, face_part, face_cap)
    tmpdir = os.path.join(OUT_DIR, "_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    proofs = [
        render_proof(arm, clips["Idle"], 0, "proof_rest.png", cams, tmpdir),
        render_proof(arm, clips["Fire"], 2, "proof_fire_bolt_back.png", cams, tmpdir),
        # hand proofs are shot from the gun's LEFT (Cam34L*/CamWellL): the hand target cups the mag's left face
        render_proof(arm, clips["Reload"], 10, "proof_reload_hand_grab.png", cams, tmpdir, "Cam34L", "CamWellL"),   # hand on the mag face
        render_proof(arm, clips["Reload"], 20, "proof_reload_rock.png", cams, tmpdir, "Cam34L", "CamWellL"),        # hand rocks it out
        render_proof(arm, clips["Reload"], 30, "proof_reload_hand_pull.png", cams, tmpdir, "Cam34LWide", "CamWellL"),  # pulled 12 cm, release
        render_proof(arm, clips["Reload"], 44, "proof_reload_mag_out.png", cams, tmpdir, "Cam34Wide"),              # last visible fall frame
        render_proof(arm, clips["Reload"], 58, "proof_reload_hand_belt.png", cams, tmpdir, "Cam34LWide", "CamWellL"),  # hand at the belt, mag hidden
        render_proof(arm, clips["Reload"], 80, "proof_reload_hand_carry.png", cams, tmpdir, "Cam34LWide", "CamWellL"), # mid-carry, fresh mag in hand
        render_proof(arm, clips["Reload"], 100, "proof_reload_seat.png", cams, tmpdir),
        render_proof(arm, clips["Reload"], 108, "proof_reload_hand_snap.png", cams, tmpdir),         # palm down, rising up the right side
        render_proof(arm, clips["Reload"], 110, "proof_reload_hand_pinch.png", cams, tmpdir),        # overhand pinch, bolt forward
        render_proof(arm, clips["Reload"], 122, "proof_reload_hand_rack.png", cams, tmpdir),         # hand on the knob, bolt back
        render_proof(arm, clips["Reload"], 138, "proof_reload_hand_return.png", cams, tmpdir),       # under the handguard, palm up-left
        render_proof(arm, clips["Chamber"], 32, "proof_chamber_back.png", cams, tmpdir),
    ]
    bpy.data.objects.remove(cams["_marker"], do_unlink=True)
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)
    times["renders"] = round(time.time() - t, 1)
    clip_info = {k: {"fbx": paths[k], "action": clips[k].name, "frames": int(clips[k].frame_range[1]),
                     "fps": FPS, "seconds": round(clips[k].frame_range[1] / FPS, 4)} for k in clips}
    t = time.time()
    verify = verify_reimport(paths, heads)
    times["verify"] = round(time.time() - t, 1)
    data = {
        "gun": "EM_11 (EM Apocalyptic Guns Vol 23)",
        "source_fbx": SRC_FBX,
        "scale_factor": SCALE,
        "units_note": "vendor FBX is cm (UnitScaleFactor honoured by the importer, object scale 0.01); "
                      "pack is life-size as imported (EM_13 bolt-action 119.7 cm = 47.1 in). x2.54 would give 252 cm.",
        "length_cm": verify["mesh"]["length_cm"],
        "bounds_cm_blender": verify["mesh"]["bounds_cm"],
        "axes": "Unreal: X forward (muzzle), Y right, Z up; origin at pistol-grip top centre (grip_r)",
        "origin_in_vendor_frame_cm": r3(GUN["origin"]),
        "armature_object_name": ARMATURE_OBJECT_NAME,
        "armature_data_name": ARM_NAME,
        "clip_fbx_contents": "mesh + armature (UE 5.8 Interchange rejects armature-only FBX)",
        "bones": BONE_ORDER,
        "bone_parents": {"root": None, "body": "root", "grip_r": "root",
                         **{b: "body" for b in MOVING_BONES + SOCKET_BONES + HAND_BONES if b != "grip_r"}},
        "deform_bones": ["body"] + MOVING_BONES,
        "hand_l_target": {
            "role": "palm-centre target for the body's left-hand IK during reloads (design items 2+3, 2026-10-30); "
                    "non-deforming child of body, rest at the grip_l head, +Y roll 0 like every other bone",
            "parent": "body", "deform": False, "rest_cm_ue": ue(heads["hand_l_target"]),
            "keyed_clips": ["Reload"],
            "other_clips": "rest keys only at f0 and the last frame (= grip_l, rotation identity, scale X 1.0), baked by the "
                           "exporter so all three tracks exist",
            "cup_point_rest_cm_ue": ue(HAND["cup_rest"]),
            "cup_offset_from_magazine_head_cm_ue": ue(HAND["cup_offset"]),
            "cup_rule": "6 cm below the magazine bone head (lug), X centred on the mag slice there, 1 cm outside the mag's "
                        "left face; during grab/rock/pull/carry the hand = magazine pose matrix applied to this rest point "
                        "(rigid, so the 25 deg tilt rotates the offset)",
            "mag_width_at_cup_cm": HAND["mag_width_at_cup_cm"],
            "belt_cm_ue": ue(HAND_BELT),
            "knob_pinch_rest_cm_ue": ue(HAND["knob_rest"]),
            "knob_centre_rest_cm_ue": ue(HAND["knob_centre_rest"]),
            "top_cover_edge_z_cm_ue": round(HAND["top_cover_z"] * 100, 2),
            "knob_rule": "overhand pinch (B5 2026-10-30 evening): palm centre at the knob x, 2 cm beyond the knob's right (+Y UE) "
                         "tip, HAND_KNOB_LIFT = 2 cm above the receiver's top-cover edge at the knob (was: knob centre height, "
                         "fingers sank into the panel); follows bolt_carrier f110-f126",
            "phases_frames": HAND["phases"],
            "reload_keys_cm_ue": {str(f): ue(p) for f, p in sorted(HAND["reload_keys"].items())},
            "rotation_convention": HAND["rotation_convention"],
            "rotation_meaning": "hand_l_target rotation = DELTA from rest (identity = the stance aim pose's hold of the left hand at "
                                "the support grip); the C++ support node applies D = WeaponRot * socket rot * WeaponRot^-1 to hand_l. "
                                "Designed in UE gun space (X fwd, Y right, Z up) from the measured Rifle aim-pose hand frame "
                                "(hand_l +X = fingers, -Y = palm normal, -Z = thumb side), keyed in Blender armature space via "
                                "R_bl = M R_ue M, quaternion keys with q/-q continuity, same frames and easing as the position beats.",
            "curl_meaning": "hand_l_target bone-local scale X = finger curl: 1.0 aim-pose fingers, 0 open (reference pose), "
                            "1.6 tightest; identity / 1.0 keyed at f0 and the last frame of every clip",
            "rest_hand_axes_ue": REST_HAND_AXES_UE,
            "beat_orientations_ue": {k: {"finger_dir": list(v[0]), "palm_normal": list(v[1]), "curl": HAND_CURL[k],
                                         "delta_axis_angle_ue": axis_angle_ue(hand_delta_ue(k))} for k, v in HAND_ORI.items()},
            "rotation_keys": {str(f): {"ori": o, "axis_ue": axis_angle_ue(rot_bl_to_ue(R))[0], "deg": axis_angle_ue(rot_bl_to_ue(R))[1],
                                       "palm_normal_ue": hand_frame_ue(rot_bl_to_ue(R))[0], "finger_dir_ue": hand_frame_ue(rot_bl_to_ue(R))[1]}
                              for f, (o, R) in sorted(HAND["rot_keys_bl"].items())},
            "rotation_key_steps_over_5deg": HAND["rot_key_steps_deg"],
            "curl_keys": {str(f): v for f, v in sorted(HAND["curl_keys"].items())},
            "beat_frames": HAND_BEAT_FRAMES,
            "authored_track_audit": HAND["authored_track"],
            "reimported_beats": verify["Reload"]["hand_l_target"].get("beats"),
            "proof_palm_proxy": {"plate_cm": [10, 8], "finger_arrow_cm": 6, "thumb_stub_cm": 5.5,
                                 "colours": "magenta = palm surface, dark purple = back of the hand, grey rim, green arrow = finger "
                                            "direction, white stub = thumb side; curl + delta stamped on the top band",
                                 "per_proof": PROOF_HAND},
            "magazine_continuity": {
                "release_frame": 30, "release_T_cm_ue": [1.6, 0.8, -12.0], "free_fall_g": MAG_G,
                "fall_end_frame": 45, "hidden_frames": [45, 61], "hide_scale": MAG_HIDE_SCALE,
                "pop_in_frame": 62, "pop_in_T_cm_ue": ue(HAND["pop_T"]), "pop_in_tilt_deg": MAG_TILT,
                "rule": "empty mag free-falls from the hand's release point, hides at ~58 cm below the well, stays hidden "
                        "until the hand closes at the belt, pops in at hand - rotated cup offset and rides the hand into the well",
            },
            "clearance_cm": HAND["clearance_cm"],
            "verify_frames": HAND_VERIFY_FRAMES,
        },
        "bone_heads_cm_ue": {b: ue(heads[b]) for b in BONE_ORDER},
        "sockets_cm_ue": {b: ue(heads[b]) for b in SOCKET_BONES},
        "bone_orientation": "every bone points Blender +Y with roll 0 (identity in UE component space), except ejection_port which points +X (UE X = gun right); "
                            "same as m4a1_rig.json. bolt_carrier slides along local -X, magazine pivots about Y at "
                            "its head (front locking lug), trigger rotates about Y at its head (pin).",
        "bolt_carrier_note": "the sculpt has no modelled AK bolt carrier (receiver side is a solid raised panel); "
                             "bolt_carrier drives only the charging-handle knob, which slides 9 cm back.",
        "material_slots": ["lambert9"],
        "cut_report": report,
        "clips": clip_info,
        "fbx_mesh": paths["mesh"],
        "fbx_export_settings": {k: (sorted(v) if isinstance(v, set) else v) for k, v in FBX_COMMON.items()},
        "proofs": proofs,
        "proof_colours": "grey body, blue magazine, yellow knob (bolt_carrier), red trigger, orange = body-side caps, cyan = part-side caps; "
                         "hand_l_target = palm proxy (magenta palm plate, purple back, green finger arrow, white thumb stub)",
        "verification": verify,
        "script_seconds": times,
        "log": LOG,
    }
    with open(os.path.join(OUT_DIR, "em11_rig.json"), "w") as f:
        json.dump(data, f, indent=1, default=lambda o: list(o) if hasattr(o, "__iter__") else str(o))
    log("DONE", times)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        with open(os.path.join(OUT_DIR, "rig_em11_error.txt"), "w") as f:
            f.write(traceback.format_exc() + "\n\n" + "\n".join(LOG))
        sys.exit(1)
