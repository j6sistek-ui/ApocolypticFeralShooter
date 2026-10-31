"""RigM4A1.py - rig the M4A1 modular kit for Unreal and author its mechanical clips.

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python Scripts/Blender/RigM4A1.py

Stages (all in one run):
  1. import Lowpoly.fbx, scale to life size (20 inch barrel = 50.8 cm), rotate to the
     Unreal convention (muzzle +X, Z up, right side on Blender -Y which Unreal reads as +Y),
     origin at the pistol-grip top (right hand), apply transforms.
  2. build armature 'M4A1_Skeleton' (root/body/bolt_carrier/charging_handle/magazine/
     trigger/selector/mag_release/bolt_catch + socket bones) and rigid-skin one joined
     mesh 'SK_M4A1' with one material slot per vendor material instance.
  3. author Idle/Fire/DryFire/Reload/Chamber at 60 fps.
  4. export SK_M4A1.fbx and one A_M4A1_<Clip>.fbx per clip.
  5. proof renders (Workbench, three-quarter from the right + top view).
  6. re-import every FBX in a fresh scene and assert bounds / bones / key motion.
  7. write m4a1_rig.json.

v2 (2026-10-29, clip set rework after the senior review; skeleton, bone names, axes, origin,
scale, mesh FBX and export settings are unchanged):
  Clip-only re-run (keeps SK_M4A1.fbx untouched, loads the rig from M4A1_rig.blend):
    blender.exe -b --python Scripts/Blender/RigM4A1.py -- --clips-only
  A full run (no argument) rebuilds the rig as before and then authors the same v2 clips.
  Clips (60 fps): Idle, IdleEmpty (bolt held open), Fire (full 9.0 cm stroke, trigger held),
  FireLast (stops on the bolt catch at the hold-open position = IdleEmpty pose), DryFire
  (unchanged), Reload (EMPTY: starts held open, gravity drop, mag parked out of sight at -70 cm,
  new mag on a hand arc, bolt-catch release slam), ReloadTactical (bolt home throughout, same
  mag motion), Chamber (9.0 cm pull, 2-frame slam).
  Rules: full stroke 9.0 cm, hold-open 8.2 cm (= stroke - 0.8); 1-2 frame moves are LINEAR (the
  60 fps bake drops easing on them anyway), easing only on 3+ frame moves. The bolt_catch
  engaged pose is a 10 deg roll about the fore-aft pin axis (top of the paddle out), pivot at
  the paddle's lower inboard edge. Clips that do not end on the rest pose (IdleEmpty, FireLast)
  are exported from a temporary rest pre-roll key at frame -5 so every FBX still carries the
  rest pose as its node default transforms; the pre-roll is outside the baked range and is
  removed after export. Proofs: proof2_<clip>_fNNN.png (right-side cutaway built on a proof-only
  mesh copy, carrier close-up with stroke ruler, muzzle-side section through the mag release and
  bolt catch, trigger close-up) plus Reload / ReloadTactical frame strips.
  m4a1_rig.json gains 'clips_v2' (other keys, e.g. ue_verification and notes, are preserved).

v3 (2026-10-30, left-hand choreography; skeleton gains ONE non-deforming bone, everything else in
the rig, the export settings and the v2 clip mechanics are unchanged):
  'hand_l_target' (child of body, rest at the grip_l head, identity orientation) is the PALM-CENTRE
  target of the body's left-hand IK. Keyed only in Reload / ReloadTactical; at frame 0 and the last
  frame it sits exactly on grip_l (every other clip carries it at rest = grip_l), so outside a
  reload the IK target equals the support grip. Reload hand path (60 fps): f0-f12 grip_l -> the
  drum's left face (cup offset = measured left face + 1.5 cm clearance, 6 cm below the mag top),
  f12-f27 pulls the magazine DOWN WITH IT 12 cm (the mag is re-keyed to ride the hand, QUAD ease-in,
  and free-falls from the release point with the release velocity + the v2 gravity/drift/tilt model
  to the -70 cm park), f27-f56 hand down to the belt (+6, -14, -42 UE cm from grip_r), f56 the
  fresh mag POPS IN at the hand (bone scale 0.001 -> 1.0; the dropped mag was scaled to 0.001 once
  58 cm below the well so a visible mag never rises from below), f66-f102 hand = magazine + cup at
  every mag key (carry + seat), Reload only: f104-f118 palm on the bolt catch (+2 cm gun-left of the
  paddle) for the f115 release, back to grip_l by f144 (ReloadTactical: seat held to f106, grip_l
  from f130). The exporter bakes every bone (deform-only OFF, bake_anim_use_all_bones) so the
  target's track and the magazine scale track reach UE. Proofs: proof2_<clip>_fNNN_hand.png (gun's
  left side / front / three-quarter, hand target = yellow-green sphere) plus a Reload hand strip.
  Re-import checks: hand_l_target present, == grip_l at f0 / f144 (0.3 cm), within 2 cm of
  magazine + cup at the grab, release and mid-carry frames, magazine scale ~0.001 mid-hold and 1.0
  at f0 / pop-in / carry / end.

v4 (2026-10-30 evening, hand ORIENTATION + finger CURL from the rig; no bone, position key, clip length,
export setting or v2/v3 check changes - the owner approved the positions: "the clip and reloads were much
better"):
  hand_l_target now also carries a ROTATION track (a DELTA from its rest: the bone's rest orientation is the
  identity, so the pose quaternion IS the delta, authored in ARMATURE space and converted from the UE gun-space
  design through the Blender<->UE reflection, see M_UE_BL / verify_frame_conversion) meaning "turn the left
  hand this much from how the Rifle aim pose holds it at the support grip", and a SCALE X track = finger curl
  (1.0 = the aim pose's fingers, 0 = open reference hand, 1.6 = tightest). Beats (Reload; ReloadTactical the
  same without the bolt catch): f12 grab = palm flat on the drum's LEFT face (palm normal UE +Y), fingers
  wrapping forward-down under the drum front, curl 1.3; f12-f27 pull the same; f56 belt = relaxed, palm
  up-inward, curl 0.8; f66-f102 pop-in hold + carry back in the grab orientation, 1.3; f110-f118 bolt-catch
  press = palm on the left receiver (+Y), fingers forward (+X), 1.1; identity / 1.0 at f0 and the last frame
  (f144; ReloadTactical from f130). Rotation keys sit on the position keys of each beat with the same
  easing; quaternion keys are kept on the shortest path (sign continuity per bone). The exporter already
  bakes all bones; every clip keys location, rotation AND scale of the target at f0 and its last frame.
  Proofs: the hand marker sphere is replaced by a PALM PROXY (10 x 8 cm plate: yellow PALM face, dark-green
  back of the hand, red 6 cm finger arrow, blue thumb-side cube) placed from the measured aim-pose hand
  frame rotated by the keyed delta, plus a see-through (x-ray) view from the gun's right so the palm face
  shows against the magazine / receiver, and the curl / delta printed on each hand proof.
  Re-import checks (every clip): hand_l_target rotation identity at f0 / last frame (< 2 deg), scale X
  1.0 +- 0.02 there, curl within [0.4, 1.6] on every frame, consecutive (every frame and every 6th frame)
  rotation steps < 150 deg, and the re-imported delta at every beat frame equals the design (< 1 deg, curl
  +- 0.02). m4a1_rig.json gains a top-level 'hand_l_target' (rotation_keys / curl_keys per clip, the beat
  table in UE gun-space axis-angle, the frame conversion proof) and clips_v2.clips.*.keys.hand_l_target gets
  rotation_keys / curl_keys too.
"""
import bpy
import bmesh
import json
import math
import os
import sys
import traceback
from mathutils import Matrix, Vector, Quaternion, Euler

SRC_FBX = r"M:\UnrealProjects\AFS\SourceAssets\M4A1_Modular\Lowpoly.fbx"
# AFS_M4A1_OUT / AFS_M4A1_RECEIPTS redirect the outputs (dry run on a copy of Rigged)
OUT_DIR = os.environ.get("AFS_M4A1_OUT", r"M:\UnrealProjects\AFS\SourceAssets\M4A1_Modular\Rigged")
RECEIPT_DIR = os.environ.get("AFS_M4A1_RECEIPTS", r"D:\AFS_Comparisons\M4A1_20261029")
FPS = 60
BARREL_REAL_M = 0.508  # 20 inch
ARMATURE_OBJECT_NAME = "Armature"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(RECEIPT_DIR, exist_ok=True)

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print("[RigM4A1]", s)
    sys.stdout.flush()


# ----------------------------------------------------------------------------
# part -> material slot (vendor material instance names) and part -> bone
# ----------------------------------------------------------------------------
SLOT_ORDER = ["Barrel", "BoltCarrier", "BufferTube", "Buttstock", "ChargingHandle", "Flashlight",
              "FrontGrip", "FrontRail", "GasBlock", "Glass", "Laser", "Magazine", "Muzzel",
              "OffsetRail", "Optic", "PistolGrip", "Receiver_Lower", "Receiver_Upper", "RedDot",
              "Reflex", "Silencer", "SmallRail"]

PART_TO_SLOT = {
    "AR_15_RAPTOR_LT_CHARGING_HANDLE_5_56": "ChargingHandle",
    "Barrel_20_inch_for_AR_15": "Barrel",
    "Bolt_Carrier": "BoltCarrier",
    "Colt_M4_Carbine_Lower_Receiver": "Receiver_Lower",
    "EMG_SAI_QD_Rail": "FrontRail",
    "EOTech_ATPIAL_AN_PEQ_15": "Laser",
    "FAB_Defense_GL_SHOCK_AR15_M16_Shock_Absorbing_Butt_Stock": "Buttstock",
    "Glas_grp": "Glass",
    "JP_Enterprises_Ar_15_M16_Adjustable_Gas_Blocks_A2_Style_6cc5332": "GasBlock",
    "Magpul_Industries_M_lok_Alum_Rail": "SmallRail",
    "Magpul_PMAG_D_60__AR_M4": "Magazine",
    "MAGPUL_PTS_AAC_Blackout_51T_Flash_Hider": "Muzzel",
    "NcSTAR_MPR45_45_Degree_Offset_Rail_Mount": "OffsetRail",
    "NcSTAR_MPR45_45_Degree_Offset_Rail_Mount1": "OffsetRail",
    "Primary_Arms_SLx_3_Compact_3x32_Gen_II_Prism_Scope": "Optic",
    "PTS_Fortis_SHIFT__Vertical_Grip": "FrontGrip",
    "Red_grp": "RedDot",
    "SDN_6_Fast_attach_7_62mm_silencer": "Silencer",
    "Strike_SI_AR_Advanced_Receiver_Extension": "BufferTube",
    "Tactical_Dynamics_CNC_Aluminum_Skeletonized_Pistol_Grip_f9e76ff": "PistolGrip",
    "Vltor_MUR_MODULAR_UPPER_RECEIVER": "Receiver_Upper",
    "Zenit_BelOMO_PK_06": "Reflex",
    "Zenitco_Klesch_2IKS": "Flashlight",
}

PART_TO_BONE = {
    "Bolt_Carrier": "bolt_carrier",
    "AR_15_RAPTOR_LT_CHARGING_HANDLE_5_56": "charging_handle",
    "Magpul_PMAG_D_60__AR_M4": "magazine",
}
# lower receiver sub-meshes identified by bounds (see probe in the receipt folder)
LOWER_SUBMESH_TO_BONE = {
    "pCube210": "trigger",          # centreline, hangs 3 cm below the receiver into the guard
    "pCylinder180": "selector",     # left side above the grip, 3 cm lever
    "polySurface78": "selector",    # right-side ambi selector paddle
    "pCylinder174": "mag_release",  # right side button forward of the trigger
    "pCylinder182": "mag_release",  # left side catch bar
    "pCylinder183": "bolt_catch",   # left side vertical paddle above the mag well
}

MOVING_BONES = ["bolt_carrier", "charging_handle", "magazine", "trigger", "selector",
                "mag_release", "bolt_catch"]
SOCKET_BONES = ["muzzle", "ejection_port", "sight", "grip_r", "grip_l", "mag_well"]
# v3: non-deforming IK target bones (no geometry, like the sockets) that ARE animated
TARGET_BONES = ["hand_l_target"]
HAND_TARGET = "hand_l_target"
BONE_ORDER = ["root", "body"] + MOVING_BONES + SOCKET_BONES + TARGET_BONES
# every clip keys these at rest on frame 0 and the last frame so the exporter bakes a full track
KEYED_BONES = MOVING_BONES + TARGET_BONES

# distinct viewport colours so the proof renders show which part moved
SLOT_COLOR = {
    "BoltCarrier": (1.0, 0.45, 0.05, 1), "ChargingHandle": (1.0, 0.85, 0.1, 1),
    "Magazine": (0.15, 0.45, 1.0, 1), "Receiver_Lower": (0.55, 0.55, 0.58, 1),
    "Receiver_Upper": (0.62, 0.62, 0.65, 1), "Glass": (0.6, 0.85, 0.95, 1),
    "RedDot": (1, 0, 0, 1),
}
BONE_COLOR = {"trigger": (1.0, 0.1, 0.1, 1), "mag_release": (0.2, 1.0, 0.3, 1),
              "bolt_catch": (0.9, 0.2, 0.9, 1), "selector": (0.2, 0.9, 0.9, 1)}


def wbounds(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(p[i] for p in pts) for i in range(3)))
    mx = Vector((max(p[i] for p in pts) for i in range(3)))
    return mn, mx


def world_verts(ob):
    mw = ob.matrix_world
    return [mw @ v.co for v in ob.data.vertices]


def bounds_of(obs):
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in obs:
        a, b = wbounds(o)
        for i in range(3):
            mn[i] = min(mn[i], a[i])
            mx[i] = max(mx[i], b[i])
    return mn, mx


def select_only(obs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (obs[0] if obs else None)


# ============================================================================
# 1. import + scale + orient
# ============================================================================
def stage_import():
    bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
    scn = bpy.context.scene
    scn.unit_settings.system = 'METRIC'
    scn.unit_settings.scale_length = 1.0
    scn.unit_settings.length_unit = 'METERS'
    scn.render.fps = FPS
    scn.render.fps_base = 1.0
    bpy.ops.import_scene.fbx(filepath=SRC_FBX)
    bpy.context.view_layer.update()
    # the FBX importer sets the scene frame rate from the kit file (24 fps): force 60 after it
    for s in bpy.data.scenes:
        s.render.fps = FPS
        s.render.fps_base = 1.0
    log("scene fps", scn.render.fps)

    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
    log("imported meshes", len(meshes), "empties", len(empties))

    # part of every mesh = its parent empty (direct child of LR_grp)
    part_of = {}
    for o in meshes:
        p = o.parent
        while p is not None and p.parent is not None and p.parent.name != "LR_grp":
            p = p.parent
        part_of[o.name] = p.name if p else None
    missing = sorted(set(part_of.values()) - set(PART_TO_SLOT))
    if missing:
        raise RuntimeError("unmapped parts: %s" % missing)

    # --- scale factor from the 20 inch barrel: the longest mesh under the barrel empty
    barrel_meshes = [o for o in meshes if part_of[o.name] == "Barrel_20_inch_for_AR_15"]
    barrel = max(barrel_meshes, key=lambda o: (wbounds(o)[1] - wbounds(o)[0]).y)
    bmn, bmx = wbounds(barrel)
    barrel_len = bmx.y - bmn.y
    scale = BARREL_REAL_M / barrel_len
    log("barrel mesh", barrel.name, "kit length m", round(barrel_len, 5), "-> scale", round(scale, 5))
    # sanity: magazine width
    mag = [o for o in meshes if part_of[o.name] == "Magpul_PMAG_D_60__AR_M4"]
    mmn, mmx = bounds_of(mag)
    log("magazine kit dims m", [round(v, 4) for v in (mmx - mmn)], "-> cm",
        [round(v * scale * 100, 1) for v in (mmx - mmn)])
    gmn, gmx = bounds_of(meshes)
    log("kit bounds m", [round(v, 4) for v in gmn], [round(v, 4) for v in gmx])

    # --- origin: pistol grip top (centre of the grip's top face, kit frame)
    grip = [o for o in meshes if part_of[o.name] ==
            "Tactical_Dynamics_CNC_Aluminum_Skeletonized_Pistol_Grip_f9e76ff"]
    gv = []
    for o in grip:
        gv += world_verts(o)
    ztop = max(v.z for v in gv)
    top = [v for v in gv if v.z > ztop - 0.002]
    oy = sum(v.y for v in top) / len(top)
    origin_kit = Vector((0.0, oy, ztop))
    log("origin (kit frame)", [round(v, 5) for v in origin_kit])

    # kit frame: -Y muzzle, +Y stock, +Z up, -X right side.
    # Unreal/Blender frame: +X muzzle, +Z up, right side on Blender -Y.
    rot = Matrix.Rotation(math.radians(90.0), 4, 'Z')   # (x,y,z) -> (-y, x, z)
    conv = rot @ Matrix.Scale(scale, 4)
    origin_new = conv @ origin_kit
    conv = Matrix.Translation(-origin_new) @ conv

    # bake the conversion into every mesh: compute the target world matrices first, then
    # unparent (which would otherwise drop the parent's transform), then assign.
    targets = {o.name: conv @ o.matrix_world.copy() for o in meshes}
    for o in meshes:
        o.parent = None
        o.matrix_parent_inverse = Matrix.Identity(4)
    for o in meshes:
        o.matrix_world = targets[o.name]
    bpy.context.view_layer.update()
    select_only(meshes, meshes[0])
    bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for e in empties:
        bpy.data.objects.remove(e, do_unlink=True)
    bpy.context.view_layer.update()
    gmn, gmx = bounds_of(meshes)
    length = gmx.x - gmn.x
    log("life-size bounds m", [round(v, 4) for v in gmn], [round(v, 4) for v in gmx],
        "length cm", round(length * 100, 2))
    return meshes, part_of, scale, (gmn, gmx)


# ============================================================================
# 2. armature + skinning
# ============================================================================
def stage_rig(meshes, part_of, bounds):
    gmn, gmx = bounds
    by_part = {}
    for o in meshes:
        by_part.setdefault(part_of[o.name], []).append(o)
    bone_of = {}
    for o in meshes:
        part = part_of[o.name]
        if part == "Colt_M4_Carbine_Lower_Receiver" and o.name in LOWER_SUBMESH_TO_BONE:
            bone_of[o.name] = LOWER_SUBMESH_TO_BONE[o.name]
        else:
            bone_of[o.name] = PART_TO_BONE.get(part, "body")
    found = sorted(set(bone_of.values()))
    log("bones with geometry", found)
    for b in ["trigger", "bolt_carrier", "charging_handle", "magazine"]:
        if b not in found:
            raise RuntimeError("required moving bone has no geometry: " + b)

    def part_bounds(part):
        return bounds_of(by_part[part])

    def bone_geo_bounds(bone):
        return bounds_of([o for o in meshes if bone_of[o.name] == bone])

    heads = {}
    heads["root"] = Vector((0, 0, 0))
    lmn, lmx = part_bounds("Colt_M4_Carbine_Lower_Receiver")
    heads["body"] = Vector(((lmn.x + lmx.x) / 2, 0.0, (lmn.z + lmx.z) / 2))
    # bolt carrier: head at the rear of the carrier (inside the receiver) on the bore axis
    cmn, cmx = bone_geo_bounds("bolt_carrier")
    heads["bolt_carrier"] = Vector(((cmn.x + cmx.x) / 2, 0.0, (cmn.z + cmx.z) / 2))
    hmn, hmx = bone_geo_bounds("charging_handle")
    heads["charging_handle"] = Vector((hmn.x + 0.01, 0.0, (hmn.z + hmx.z) / 2))
    mmn, mmx = bone_geo_bounds("magazine")
    # magazine bone at the top of the magazine (where it meets the well)
    heads["magazine"] = Vector(((mmn.x + mmx.x) / 2, (mmn.y + mmx.y) / 2, mmx.z))
    tmn, tmx = bone_geo_bounds("trigger")
    heads["trigger"] = Vector(((tmn.x + tmx.x) / 2, 0.0, tmx.z))   # pivot at the trigger pin (top)
    for ob in ("selector", "mag_release", "bolt_catch"):
        if ob in found:
            a, b = bone_geo_bounds(ob)
            heads[ob] = (a + b) / 2
    # sockets
    smn, smx = part_bounds("SDN_6_Fast_attach_7_62mm_silencer")
    heads["muzzle"] = Vector((smx.x, (smn.y + smx.y) / 2, (smn.z + smx.z) / 2))
    umn, umx = part_bounds("Vltor_MUR_MODULAR_UPPER_RECEIVER")
    # ejection port: right side (-Y) of the upper, behind the barrel extension, on the bore axis
    bore_z = heads["bolt_carrier"].z
    port_x = umx.x - 0.065  # ~6.5 cm behind the front of the upper = middle of the port
    heads["ejection_port"] = Vector((port_x, umn.y - 0.002, bore_z + 0.004))
    # sight: optical axis of the prism scope at the ocular, found from the Glass part spheres
    glass = by_part["Glas_grp"]
    optic_mn, optic_mx = part_bounds("Primary_Arms_SLx_3_Compact_3x32_Gen_II_Prism_Scope")
    lenses = []
    for o in glass:
        a, b = wbounds(o)
        c = (a + b) / 2
        if optic_mn.x - 0.01 < c.x < optic_mx.x + 0.01 and c.z > optic_mn.z:
            lenses.append((a, b))
    if lenses:
        ocular = min(lenses, key=lambda ab: ab[0].x)
        heads["sight"] = Vector(((ocular[0].x + ocular[1].x) / 2, (ocular[0].y + ocular[1].y) / 2,
                                 (ocular[0].z + ocular[1].z) / 2))
    else:
        heads["sight"] = Vector((optic_mn.x, 0.0, (optic_mn.z + optic_mx.z) / 2))
    heads["grip_r"] = Vector((0, 0, 0))
    fmn, fmx = part_bounds("PTS_Fortis_SHIFT__Vertical_Grip")
    heads["grip_l"] = (fmn + fmx) / 2
    # mag well: the magazine cross-section centre at the receiver's lower edge above the mag
    lower_verts = []
    for o in by_part["Colt_M4_Carbine_Lower_Receiver"]:
        if bone_of[o.name] == "body":
            lower_verts += world_verts(o)
    well = [v for v in lower_verts if mmn.x + 0.01 < v.x < mmx.x - 0.01 and abs(v.y) < 0.01]
    well_z = min(v.z for v in well) if well else lmn.z
    heads["mag_well"] = Vector(((mmn.x + mmx.x) / 2, 0.0, well_z))
    # v3: left-hand IK target rests exactly on the support grip
    heads[HAND_TARGET] = heads["grip_l"].copy()

    # --- build armature
    arm_data = bpy.data.armatures.new("M4A1_Skeleton")
    # UE's FBX importers drop the armature object node when it is named 'Armature', so the
    # imported skeleton starts at 'root' instead of an extra 'm4a1_skeleton' bone.
    arm = bpy.data.objects.new(ARMATURE_OBJECT_NAME, arm_data)
    bpy.context.scene.collection.objects.link(arm)
    select_only([arm], arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    parents = {"root": None, "body": "root", "grip_r": "root"}
    for b in MOVING_BONES + SOCKET_BONES + TARGET_BONES:
        parents.setdefault(b, "body")
    lengths = {"root": 0.08, "body": 0.12}
    for name in BONE_ORDER:
        if name not in heads:
            continue
        b = eb.new(name)
        h = heads[name]
        L = lengths.get(name, 0.03)
        b.head = h
        # A Blender bone along +Y with roll 0 has the identity rest matrix, which the FBX
        # exporter + UE import turn into an identity bone orientation in Unreal component
        # space (bone X = forward, Y = right, Z = up). Verified in UE 5.8 via AnimPose.
        if name == "ejection_port":
            b.tail = h + Vector((L, 0, 0))    # Blender +X -> UE bone X points to the gun's right (+Y)
        else:
            b.tail = h + Vector((0, L, 0))    # identity: UE bone X = forward
        b.roll = 0.0
        b.use_deform = name in ("body",) + tuple(MOVING_BONES)
    for name in BONE_ORDER:
        if name in eb and parents.get(name):
            eb[name].parent = eb[parents[name]]
            eb[name].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    log("bones", [b.name for b in arm_data.bones])

    # --- materials -> slot names, vertex groups, join
    for o in meshes:
        slot = PART_TO_SLOT[part_of[o.name]]
        for i, m in enumerate(o.data.materials):
            if m is None:
                continue
            if m.name != slot:
                if slot in bpy.data.materials:
                    o.data.materials[i] = bpy.data.materials[slot]
                else:
                    m.name = slot
        vg = o.vertex_groups.new(name=bone_of[o.name])
        vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    # per-part sanity: every material slot named
    select_only(meshes, meshes[0])
    bpy.ops.object.join()
    sk = bpy.context.view_layer.objects.active
    sk.name = "SK_M4A1"
    sk.data.name = "SK_M4A1"
    # reorder material slots to SLOT_ORDER
    poly_mat = [sk.data.materials[p.material_index].name for p in sk.data.polygons]
    used = set(poly_mat)
    sk.data.materials.clear()
    for s in SLOT_ORDER:
        mat = bpy.data.materials.get(s)
        if mat is None:
            mat = bpy.data.materials.new(s)
        sk.data.materials.append(mat)
    idx = {s: i for i, s in enumerate(SLOT_ORDER)}
    for p, mn in zip(sk.data.polygons, poly_mat):
        p.material_index = idx[mn]
    log("material slots", [m.name for m in sk.data.materials], "unused:", sorted(set(SLOT_ORDER) - used))
    # viewport colours
    for m in sk.data.materials:
        m.use_nodes = True
        col = SLOT_COLOR.get(m.name, (0.42, 0.42, 0.44, 1.0))
        m.diffuse_color = col
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = col
    # weights sanity: every vertex in exactly one group, weight 1
    bad = 0
    for v in sk.data.vertices:
        if len(v.groups) != 1 or abs(v.groups[0].weight - 1.0) > 1e-6:
            bad += 1
    if bad:
        raise RuntimeError("%d vertices not rigidly weighted" % bad)
    # armature modifier + parent
    sk.parent = arm
    mod = sk.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    bpy.context.view_layer.update()
    log("SK_M4A1 verts", len(sk.data.vertices), "tris", sum(len(p.vertices) - 2 for p in sk.data.polygons))
    return arm, sk, heads, bone_of


# ============================================================================
# 3. animation
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


class ClipAuthor:
    """Keys bones in armature space: translation T (metres) and rotation (degrees) about the
    bone head, with ease control. Every bone animated here is a child of 'body' which never
    moves, so matrix_basis = rest_local^-1 @ desired."""

    def __init__(self, arm, name, frames):
        self.arm = arm
        self.name = name
        self.frames = frames
        self.act = bpy.data.actions.new(name)
        self.act.use_fake_user = True
        ensure_slot(arm, self.act)
        self.act.frame_range = (0, frames)
        self.act.use_frame_range = True
        self.keys = []  # (bone, frame, T, rot_axis, rot_deg, interp, easing, pivot, scale)

    def key(self, bone, frame, T=(0, 0, 0), rot=None, interp='BEZIER', easing='AUTO', pivot=None, scale=None):
        """rot = (axis, degrees) about the bone head, or about `pivot` (armature space, metres); v4: or an
        arbitrary armature-space rotation as a 3x3 Matrix / Quaternion about the head (the hand target's
        delta from rest). scale = uniform bone scale (v3: the magazine is hidden at 0.001 during the drop
        hold) or, v4, a per-axis (sx, sy, sz) tuple (the hand target's scale X is the finger curl); a bone
        with any scale key, and every TARGET bone, gets a scale channel on every one of its keys (1.0)."""
        self.keys.append((bone, frame, Vector(T), rot, interp, easing, pivot, scale))

    def apply(self):
        arm = self.arm
        bpy.context.scene.frame_set(0)
        for pb in arm.pose.bones:
            pb.rotation_mode = 'QUATERNION'
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
        animated = sorted(set(k[0] for k in self.keys))
        # every clip keys the whole list of moving bones (and the hand target) at 0 and at the end
        # (rest) so the exporter bakes a complete track and UE gets clean start/end poses
        for b in KEYED_BONES:
            if b in arm.pose.bones and b not in animated:
                self.keys.append((b, 0, Vector(), None, 'BEZIER', 'AUTO', None, None))
                self.keys.append((b, self.frames, Vector(), None, 'BEZIER', 'AUTO', None, None))
        # v4: the target bones always carry a scale channel (curl = scale X; 1.0 at f0 / end of every clip)
        scaled_bones = set(k[0] for k in self.keys if k[7] is not None) | set(b for b in TARGET_BONES if b in arm.pose.bones)
        last_q = {}
        # keys are applied in frame order per bone so the quaternion sign can be kept continuous (v4: the
        # hand target turns up to ~70 deg between beats; a sign flip would make the bake spin the long way)
        for (bone, frame, T, rot, interp, easing, pivot, scale) in sorted(self.keys, key=lambda k: (k[0], k[1])):
            pb = arm.pose.bones[bone]
            rest = pb.bone.matrix_local
            head = rest.translation if pivot is None else Vector(pivot)
            R = Matrix.Identity(4)
            if rot is not None:
                if isinstance(rot, (Matrix, Quaternion)):
                    R3 = rot.to_matrix() if isinstance(rot, Quaternion) else rot.to_3x3()
                    R = Matrix.Translation(head) @ R3.to_4x4() @ Matrix.Translation(-head)
                else:
                    axis, deg = rot
                    R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
            desired = Matrix.Translation(T) @ R @ rest
            basis = rest.inverted() @ desired
            pb.matrix_basis = basis
            q = basis.to_quaternion().normalized()
            prev = last_q.get(bone)
            if prev is not None and q.dot(prev) < 0.0:
                q = -q                      # same rotation, the sign that is nearest the previous key
            pb.rotation_quaternion = q
            last_q[bone] = q.copy()
            pb.keyframe_insert("location", frame=frame, group=bone)
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=bone)
            if bone in scaled_bones:
                if scale is None:
                    s = (1.0, 1.0, 1.0)
                elif isinstance(scale, (tuple, list)):
                    s = tuple(float(v) for v in scale)
                else:
                    s = (float(scale),) * 3
                pb.scale = s
                pb.keyframe_insert("scale", frame=frame, group=bone)
                pb.scale = (1, 1, 1)
        # interpolation / easing per key
        for fc in _fcurves(self.act):
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = 'AUTO'
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'
        for (bone, frame, T, rot, interp, easing, pivot, scale) in self.keys:
            if interp == 'BEZIER' and easing == 'AUTO':
                continue
            for fc in _fcurves(self.act):
                if not fc.data_path.startswith('pose.bones["%s"]' % bone):
                    continue
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-3:
                        kp.interpolation = interp
                        kp.easing = easing
        for fc in _fcurves(self.act):
            fc.update()
        bpy.context.scene.frame_set(0)
        return self.act


def _fcurves(act):
    if hasattr(act, "layers") and len(act.layers):
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
        return out
    return list(act.fcurves)


# ---- v2 mechanical constants (see the v2 note in the module docstring)
STROKE_CM = 9.0                    # full carrier stroke under recoil = charging stroke
HOLD_OPEN_CM = STROKE_CM - 0.8     # carrier resting on the engaged bolt catch
TRIGGER_PULL_DEG = 8.0
MAG_RELEASE_PRESS_CM = 0.4         # right-side button pushed in toward the gun's left (Blender +Y)
BOLT_CATCH_AXIS = 'X'              # roll pin runs fore-aft
BOLT_CATCH_ENGAGED_DEG = -10.0     # negative about +X = top of the left-side paddle swings out (+Y)
MAG_GRAVITY = 9.6                  # m/s^2: 30 cm in 0.25 s (free fall, slight drag leaving the well)
MAG_PARK_CM = -70.0                # old mag parked out of any plausible frame
# v2 new-mag hand-arc start (8, 3, -40) Blender cm is superseded in v3 by the belt pop-in point
# (hand belt target minus the cup offset); DERIVED["mag_new_start_bl_cm"] holds the live value.
MAG_NEW_START_CM = (8.0, 3.0, -40.0)

# ---- v3 left-hand choreography (Blender frame: +X fwd, +Y gun-LEFT, +Z up; UE Y = -Blender Y)
HAND_CUP_CLEAR_CM = 1.5            # palm centre sits this far off the magazine's left face
HAND_CUP_DOWN_CM = 6.0             # ... and this far below the magazine top (the bone head)
HAND_PULL_CM = 12.0                # the mag rides in the hand for the first 12 cm of travel (f12-f27)
HAND_BELT_UE_CM = (6.0, -14.0, -42.0)      # belt pouch, low and LEFT of the gun (UE cm from grip_r)
HAND_BOLT_CATCH_OFF_UE_CM = (0.0, -2.0, 0.0)  # palm on the left-side paddle (UE cm from the bolt_catch head)
MAG_HIDE_BELOW_CM = 58.0           # the falling mag is scaled to MAG_HIDDEN_SCALE once this far below the well
MAG_HIDDEN_SCALE = 0.001
F_GRAB, F_RELEASE, F_BELT, F_CARRY, F_SEAT = 12, 27, 56, 66, 102
DERIVED = {}                       # filled by author_clips: cup offset, pop-in point, hand keys, frames

# ---- v4 left-hand ORIENTATION + CURL. hand_l_target's pose ROTATION is a DELTA from its rest (the bone's rest
# orientation is the identity, so pose rotation == delta, armature space) meaning "turn the left hand this much
# from how the Rifle aim pose holds it at the support grip"; its pose SCALE X is the finger curl (1.0 = the aim
# pose's fingers as-is, 0.0 = the open reference hand, up to 1.6 = extrapolated tighter grip). The rest hand
# frame is the Rifle aim pose's hand_l frame measured in a nullrhi PIE (Scripts/MeasureHandAxes.py, receipt
# D:/AFS_Comparisons/GunRigs_20261029/hand_axes.json, 2026-10-30 23:17): hand_l local +X = finger direction
# (wrist -> middle_01_l), local -Y = palm normal (out of the palm), local -Z = thumb side. UE gun space, X fwd,
# Y right, Z up, unit vectors.
HAND_REST_FINGER_UE = (0.876, 0.477, -0.07)
HAND_REST_PALM_UE = (-0.325, 0.692, 0.645)
# beat -> (palm normal, finger direction, curl) in UE gun space; None = rest (identity delta, curl 1.0)
HAND_BEATS_UE = {
    "rest": (None, None, 1.0),
    # palm flat against the drum's LEFT face (normal +Y, toward the gun), fingers wrapping forward and down
    # under the drum front; the thumb (hand -Z) then points forward-up, as a left hand on a drum's left does
    "grab": ((0.0, 1.0, 0.0), (0.7071, 0.0, -0.7071), 1.3),
    # belt pouch: relaxed, palm up and inward (toward the gun), fingers forward, thumb out to the left
    "belt": ((0.0, 0.6, 0.8), (1.0, 0.0, 0.0), 0.8),
    # bolt-catch press (empty Reload only): palm flat on the left receiver wall (+Y), fingers forward, thumb up
    "catch": ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), 1.1),
}
HAND_CURL_RANGE = (0.4, 1.6)
HAND_MAX_STEP_DEG = 150.0          # no consecutive key / sampled frame may turn the hand further (shortest path)
HAND_PROXY_CM = (10.0, 8.0)        # proof palm proxy: along the fingers x across the palm
HAND_PROXY_ARROW_CM = 6.0          # finger-direction arrow from the plate's front edge

# Blender armature space <-> UE gun space. Both are X fwd, Z up; Blender +Y is the gun's LEFT where UE +Y is its
# RIGHT, so vectors map through the reflection M = diag(1, -1, 1) (M == M^-1 == M^T, det M = -1). A rotation R
# (3x3) maps as R' = M R M^-1 = M R M, so that for every vector M (R v) == R' (M v). In axis-angle terms a
# rotation of +a about the axis n in UE becomes a rotation of -a about M n in Blender, because det M = -1 flips
# the sense of every rotation (M [n]x M = -[M n]x): UE +a about X -> Blender -a about X; UE +a about Z ->
# Blender -a about Z; UE +a about Y -> Blender -a about -Y = +a about +Y. Quaternion (w, x, y, z) ->
# (w, -x, y, -z), the same formula both ways. verify_frame_conversion() asserts all of this numerically on test
# rotations and vectors before any clip is authored; do not trust the prose, trust the assert.
M_UE_BL = Matrix(((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)))


def ue_to_bl(v):
    """UE cm (X fwd, Y right, Z up) -> Blender armature metres (+Y = gun-left)."""
    return Vector((v[0] * 0.01, -v[1] * 0.01, v[2] * 0.01))


def dir_ue_to_bl(v):
    """Direction (no units) UE gun space -> Blender armature space; the reflection is its own inverse."""
    return Vector((v[0], -v[1], v[2]))


dir_bl_to_ue = dir_ue_to_bl


def rot_ue_to_bl(R):
    """3x3 rotation UE gun space -> Blender armature space (R' = M R M); its own inverse."""
    return M_UE_BL @ R.to_3x3() @ M_UE_BL


rot_bl_to_ue = rot_ue_to_bl


def quat_ue_to_bl(q):
    """Unit quaternion UE gun space -> Blender armature space (and back): (w, x, y, z) -> (w, -x, y, -z)."""
    return Quaternion((q.w, -q.x, q.y, -q.z))


quat_bl_to_ue = quat_ue_to_bl


def axis_angle_ue(q_bl):
    """(axis [x, y, z] in UE gun space, degrees in [0, 180]) of a Blender-armature-space delta quaternion."""
    qu = quat_bl_to_ue(q_bl.normalized())
    if qu.w < 0.0:
        qu = -qu                      # canonical sign: angle in [0, 180]
    deg = math.degrees(qu.angle)
    axis = qu.axis if deg > 1e-6 else Vector((0.0, 0.0, 1.0))
    return [round(c, 4) for c in axis], round(deg, 3)


def _qdiff(a, b):
    """Angle (deg, 0..180) of the rotation taking unit quaternion a to b; sign-insensitive."""
    ang = math.degrees(a.normalized().rotation_difference(b.normalized()).angle)
    return min(ang, 360.0 - ang)


def verify_frame_conversion():
    """Numeric proof of the Blender<->UE rotation map: for test rotations given as UE (axis, deg) and test
    vectors, M (R_ue v) == R_bl (M v); the quaternion form equals the matrix form; the round trip is the
    identity; and the three stated axis rules hold (UE +a about X / Y / Z == Blender -a / +a / -a about
    X / Y / Z). Raises on any mismatch (> 1e-5, mathutils is float32); logs the worst error. Also checks the hand helpers: the rest
    frame is orthonormal with the measured palm axis and the beat deltas rotate rest -> beat exactly."""
    tests = [((1, 0, 0), 37.0), ((0, 1, 0), 37.0), ((0, 0, 1), 37.0), ((0.3, 0.5, -0.8), 70.0),
             ((-0.6, 0.2, 0.4), -123.0), ((0.2, -0.9, 0.1), 171.0)]
    vecs = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((0.2, -0.7, 0.4))]
    worst = 0.0
    for axis, deg in tests:
        n = Vector(axis).normalized()
        q_ue = Quaternion(n, math.radians(deg))
        R_ue = q_ue.to_matrix()
        R_bl = rot_ue_to_bl(R_ue)
        q_bl = quat_ue_to_bl(q_ue)
        worst = max(worst, max((R_bl - q_bl.to_matrix()).col[i].length for i in range(3)))
        for v in vecs:
            a = dir_ue_to_bl(R_ue @ v)            # rotate in UE, then map the result
            b = R_bl @ dir_ue_to_bl(v)            # map, then rotate with the converted rotation
            worst = max(worst, (a - b).length)
        worst = max(worst, (quat_bl_to_ue(q_bl) - q_ue).magnitude)                       # round trip
        worst = max(worst, max((rot_bl_to_ue(R_bl) - R_ue).col[i].length for i in range(3)))
        q_rule = Quaternion(dir_ue_to_bl(n), math.radians(-deg))                        # -a about M n
        worst = max(worst, min((q_rule - q_bl).magnitude, (q_rule + q_bl).magnitude))
    for axis, bl_axis, sign in (((1, 0, 0), 'X', -1.0), ((0, 1, 0), 'Y', +1.0), ((0, 0, 1), 'Z', -1.0)):
        q_bl = quat_ue_to_bl(Quaternion(Vector(axis), math.radians(30.0)))
        q_exp = Matrix.Rotation(math.radians(sign * 30.0), 3, bl_axis).to_quaternion()
        worst = max(worst, min((q_exp - q_bl).magnitude, (q_exp + q_bl).magnitude))
    # hand frame helpers
    R0 = HAND_REST_FRAME_UE
    worst = max(worst, max((R0.transposed() @ R0 - Matrix.Identity(3)).col[i].length for i in range(3)))
    worst = max(worst, (R0.col[0] - Vector(HAND_REST_FINGER_UE).normalized()).length)
    assert R0.col[1].dot(Vector(HAND_REST_PALM_UE)) < -0.99, "rest palm axis is not -Y of the hand frame"
    for beat in HAND_BEATS_UE:
        D_ue, curl = hand_beat_delta_ue(beat)
        palm, fingers, _ = HAND_BEATS_UE[beat]
        if palm is None:
            continue
        Rb = hand_frame_ue(palm, fingers)
        worst = max(worst, max((D_ue @ R0 - Rb).col[i].length for i in range(3)))
        assert HAND_CURL_RANGE[0] <= curl <= HAND_CURL_RANGE[1], "curl %s out of range" % beat
    assert worst < 1e-5, "Blender<->UE frame conversion failed, worst error %g" % worst   # mathutils is float32
    log("frame conversion Blender<->UE verified, worst error %.2e: UE +a about X/Y/Z == Blender -a/+a/-a "
        "about X/Y/Z; quaternion (w,x,y,z) -> (w,-x,y,-z); beat deltas rotate the rest hand frame exactly" % worst)
    return worst


def hand_frame_ue(palm_normal, finger_dir):
    """Orthonormal hand frame (columns = the hand's local X, Y, Z in UE gun space) from a palm normal and a
    finger direction: X = fingers, -Y = palm normal (made perpendicular to X), Z = X x Y (UE algebra, the
    same cross-product convention the PIE measurement used, so -Z is the thumb side)."""
    X = Vector(finger_dir).normalized()
    P = Vector(palm_normal)
    P = (P - X * P.dot(X)).normalized()
    Y = -P
    Z = X.cross(Y)
    return Matrix((X, Y, Z)).transposed()


HAND_REST_FRAME_UE = hand_frame_ue(HAND_REST_PALM_UE, HAND_REST_FINGER_UE)


def hand_beat_delta_ue(beat):
    """(D, curl): the UE gun-space rotation turning the rest hand frame into the beat's frame, D = R_beat R_rest^T
    (so D maps the rest finger / palm directions onto the beat's), and the beat's finger curl."""
    palm, fingers, curl = HAND_BEATS_UE[beat]
    if palm is None:
        return Matrix.Identity(3), curl
    return hand_frame_ue(palm, fingers) @ HAND_REST_FRAME_UE.transposed(), curl


def hand_beat_delta_bl(beat):
    """The same delta as an armature-space 3x3 (what the pose bone is keyed with) plus the curl."""
    D_ue, curl = hand_beat_delta_ue(beat)
    return rot_ue_to_bl(D_ue), curl


def hand_frame_bl_from_delta(q_bl):
    """Posed hand frame in Blender armature space as a right-handed 3x3 (columns X = fingers, Y = back of the
    hand, Z = X x Y in Blender algebra = the THUMB side, since the reflection flips the cross product:
    M (X_ue x Y_ue) = -(M X_ue) x (M Y_ue) and the thumb is -Z_ue). Used to place the proof palm proxy."""
    D_bl = q_bl.normalized().to_matrix()
    X = D_bl @ dir_ue_to_bl(HAND_REST_FRAME_UE.col[0])
    Y = D_bl @ dir_ue_to_bl(HAND_REST_FRAME_UE.col[1])
    return Matrix((X, Y, X.cross(Y))).transposed()


def mag_cup_offset(arm):
    """Palm-centre offset from the magazine bone head (Blender m): the drum's left face measured on
    the SK_M4A1 magazine vertices in a 3 cm band around HAND_CUP_DOWN_CM below the top, plus the
    palm clearance; HAND_CUP_DOWN_CM down."""
    sk = bpy.data.objects.get("SK_M4A1")
    gi = {g.index: g.name for g in sk.vertex_groups}
    head = arm.data.bones["magazine"].head_local
    z0 = head.z - HAND_CUP_DOWN_CM * 0.01
    ys = [v.co.y for v in sk.data.vertices
          if gi[v.groups[0].group] == "magazine" and abs(v.co.z - z0) <= 0.015]
    face_y = max(ys) if ys else head.y + 0.012
    off = Vector((0.0, face_y - head.y + HAND_CUP_CLEAR_CM * 0.01, -HAND_CUP_DOWN_CM * 0.01))
    return off, face_y


def bolt_catch_pivot(arm):
    """Lower inboard edge of the bolt_catch paddle (it lies on the left receiver wall)."""
    sk = bpy.data.objects.get("SK_M4A1")
    gi = {g.index: g.name for g in sk.vertex_groups}
    pts = [v.co for v in sk.data.vertices if gi[v.groups[0].group] == "bolt_catch"]
    head = arm.data.bones["bolt_catch"].head_local
    return Vector((head.x, min(p.y for p in pts), min(p.z for p in pts)))


def author_clips(arm, heads):
    """v2 clip set. Frames are 60 fps; f = round(seconds * 60)."""
    clips = {}
    cm = 0.01
    S = STROKE_CM * cm
    H = HOLD_OPEN_CM * cm
    TRIG = ('Y', TRIGGER_SIGN * TRIGGER_PULL_DEG)
    TRIG0 = ('Y', 0.0)
    piv = bolt_catch_pivot(arm)
    log("bolt_catch pivot (Blender cm)", [round(v * 100, 3) for v in piv])
    # v4: prove the Blender<->UE rotation map and the hand beat table before any rotation key is authored
    DERIVED["frame_conversion_worst_err"] = verify_frame_conversion()
    DERIVED["hand_beats_ue"] = {}
    for beat, (palm, fingers, curl) in HAND_BEATS_UE.items():
        D_ue, _ = hand_beat_delta_ue(beat)
        axis, deg = axis_angle_ue(rot_ue_to_bl(D_ue).to_quaternion())
        DERIVED["hand_beats_ue"][beat] = {
            "palm_normal_ue": list(palm) if palm else list(-HAND_REST_FRAME_UE.col[1]),
            "finger_dir_ue": list(fingers) if fingers else list(HAND_REST_FRAME_UE.col[0]),
            "curl": curl, "delta_axis_ue": axis, "delta_deg": deg}
        log("hand beat", beat, "delta UE axis", axis, "deg", deg, "curl", curl)
    CATCH_ON = (BOLT_CATCH_AXIS, BOLT_CATCH_ENGAGED_DEG)
    CATCH_OFF = (BOLT_CATCH_AXIS, 0.0)
    L = 'LINEAR'

    def catch(c, f, on, interp=L, easing='AUTO'):
        c.key("bolt_catch", f, rot=CATCH_ON if on else CATCH_OFF, interp=interp, easing=easing, pivot=piv)

    # ---- Idle: 2 frames rest (unchanged)
    c = ClipAuthor(arm, "A_M4A1_Idle", 1)
    c.key("bolt_carrier", 0)
    c.key("bolt_carrier", 1)
    clips["Idle"] = c.apply()

    # ---- IdleEmpty: 2 frames, carrier held open on the engaged catch, mag seated. Loop.
    c = ClipAuthor(arm, "A_M4A1_IdleEmpty", 1)
    for f in (0, 1):
        c.key("bolt_carrier", f, (-H, 0, 0), interp=L)
        catch(c, f, True)
    clips["IdleEmpty"] = c.apply()

    # ---- Fire: 0.117 s (f0..7). Full stroke back over 2 frames (linear), forward over 4 with
    # QUAD ease-in (spring accelerates the carrier home), 1-frame settle into battery.
    # Trigger pulled at f0 and held through f6 (full-auto reads right), released only at f7.
    def fire_trigger(c):
        c.key("trigger", 0, rot=TRIG, interp=L)
        c.key("trigger", 6, rot=TRIG, interp=L)
        c.key("trigger", 7, rot=TRIG0, interp=L)

    c = ClipAuthor(arm, "A_M4A1_Fire", 7)
    c.key("bolt_carrier", 0, (0, 0, 0), interp=L)
    c.key("bolt_carrier", 2, (-S, 0, 0), interp='QUAD', easing='EASE_IN')
    c.key("bolt_carrier", 6, (-0.3 * cm, 0, 0), interp=L)    # lock-up bounce
    c.key("bolt_carrier", 7, (0, 0, 0), interp=L)
    fire_trigger(c)
    clips["Fire"] = c.apply()

    # ---- FireLast: as Fire, but the empty follower lifts the catch while the carrier is at the
    # rear (f1-f3) and the carrier comes forward onto it (f2-f4), 1.5 mm bounce, rests held open.
    # Last frame = IdleEmpty pose (trigger released, catch engaged, carrier at hold-open).
    c = ClipAuthor(arm, "A_M4A1_FireLast", 7)
    c.key("bolt_carrier", 0, (0, 0, 0), interp=L)
    c.key("bolt_carrier", 2, (-S, 0, 0), interp=L)
    c.key("bolt_carrier", 4, (-H, 0, 0), interp=L)            # hits the catch
    c.key("bolt_carrier", 5, (-H - 0.15 * cm, 0, 0), interp=L)
    c.key("bolt_carrier", 6, (-H, 0, 0), interp=L)
    c.key("bolt_carrier", 7, (-H, 0, 0), interp=L)
    catch(c, 0, False)
    catch(c, 1, False)
    catch(c, 3, True)
    catch(c, 7, True)
    fire_trigger(c)
    clips["FireLast"] = c.apply()

    # ---- DryFire: 0.15 s (0..9) trigger pull only (unchanged from v1)
    c = ClipAuthor(arm, "A_M4A1_DryFire", 9)
    c.key("trigger", 0, rot=('Y', 0.0), interp='QUAD', easing='EASE_OUT')
    c.key("trigger", 1, rot=('Y', TRIGGER_SIGN * 8.0), interp='SINE', easing='EASE_IN_OUT')
    c.key("trigger", 4, rot=('Y', TRIGGER_SIGN * 8.0), interp='SINE', easing='EASE_IN_OUT')
    c.key("trigger", 7, rot=('Y', 0.0))
    c.key("trigger", 9, rot=('Y', 0.0))
    clips["DryFire"] = c.apply()

    # ---- v3 geometry for the left hand (armature space, metres)
    cup, face_y = mag_cup_offset(arm)
    mag_head = arm.data.bones["magazine"].head_local.copy()
    grip_l = arm.data.bones["grip_l"].head_local.copy()
    catch_head = arm.data.bones["bolt_catch"].head_local.copy()
    belt = ue_to_bl(HAND_BELT_UE_CM)
    catch_pt = catch_head + ue_to_bl(HAND_BOLT_CATCH_OFF_UE_CM)
    new_start_abs = belt - cup                  # magazine head when the fresh mag pops into the palm
    new_start = new_start_abs - mag_head        # ... as a key delta from the rest head
    pull = HAND_PULL_CM * cm
    park = -MAG_PARK_CM * cm
    DERIVED["cup_offset_bl_cm"] = [round(v * 100, 3) for v in cup]
    DERIVED["mag_left_face_y_bl_cm"] = round(face_y * 100, 3)
    DERIVED["mag_new_start_bl_cm"] = [round(v * 100, 3) for v in new_start]
    DERIVED["mag_pop_in_head_bl_cm"] = [round(v * 100, 3) for v in new_start_abs]
    DERIVED["belt_bl_cm"] = [round(v * 100, 3) for v in belt]
    DERIVED["bolt_catch_hand_bl_cm"] = [round(v * 100, 3) for v in catch_pt]
    log("hand cup offset (Blender cm)", DERIVED["cup_offset_bl_cm"], "mag left face y", DERIVED["mag_left_face_y_bl_cm"],
        "pop-in mag head", DERIVED["mag_new_start_bl_cm"], "belt", DERIVED["belt_bl_cm"], "catch palm", DERIVED["bolt_catch_hand_bl_cm"])

    # ---- magazine + mag release motion shared by Reload and ReloadTactical (0..144 = 2.4 s)
    def mag_swap(c):
        """Returns the magazine key list [(frame, T(m), tilt_deg, interp, easing, scale)]."""
        P = MAG_RELEASE_PRESS_CM * cm
        c.key("mag_release", 0, (0, 0, 0), interp='SINE', easing='EASE_IN_OUT')
        c.key("mag_release", 6, (0, P, 0), interp=L)                       # pressed by 0.10 s
        c.key("mag_release", 12, (0, P, 0), interp='SINE', easing='EASE_IN_OUT')  # held to 0.20 s
        c.key("mag_release", 16, (0, 0, 0), interp=L)                      # springs back
        c.key("mag_release", 144, (0, 0, 0), interp=L)
        mk = []

        def mag(f, T, tilt, interp='BEZIER', easing='AUTO', scale=1.0):
            mk.append((f, Vector(T), tilt, interp, easing, scale))

        # old mag (v3): seated until the catch lets go at f12 (0.20 s) when the left hand has closed
        # on the drum; the hand pulls it straight down 12 cm over f12-f27 (QUAD ease-in, same curve
        # as the hand so they move together), then lets go. From the release point it free-falls
        # with the release velocity + the v2 gravity model, sampled every frame (linear between
        # per-frame samples = exact after the bake), small forward drift and forward tilt (bottom
        # swings forward) growing from the release, parked at -70 cm and held there. Once it is
        # MAG_HIDE_BELOW_CM below the well the bone is scaled to MAG_HIDDEN_SCALE (hidden) and it
        # stays hidden until the pop-in at the belt: a visible mag never rises from below the hand.
        mag(0, (0, 0, 0), 0.0, L)
        mag(F_GRAB, (0, 0, 0), 0.0, 'QUAD', 'EASE_IN')
        mag(F_RELEASE, (0, 0, -pull), 0.0, L)
        v0 = 2.0 * pull / ((F_RELEASE - F_GRAB) / FPS)   # end velocity of the QUAD ease-in pull
        f = F_RELEASE + 1
        hidden_from = None
        while True:
            t = (f - F_RELEASE) / FPS
            d = pull + v0 * t + 0.5 * MAG_GRAVITY * t * t
            parked = d >= park
            d = min(d, park)
            k = (d - pull) / (park - pull)
            tilt = MAG_TILT_SIGN * 16.0 * (k ** 0.6)
            hidden = d >= MAG_HIDE_BELOW_CM * cm
            if hidden and hidden_from is None:
                hidden_from = f
            mag(f, (1.5 * cm * k, 0.0, -d), tilt, 'CONSTANT' if parked else L,
                scale=MAG_HIDDEN_SCALE if hidden else 1.0)
            if parked:
                break
            f += 1
        DERIVED["mag_release_velocity_mps"] = round(v0, 3)
        DERIVED["mag_hidden_from_frame"] = hidden_from
        DERIVED["mag_parked_frame"] = f
        # fresh mag: pops in at the belt in the palm (scale 1.0) at f56 (0.933 s) when the hand
        # closes there, held to f66 while the hand closes, then rides the hand up and back to the
        # well, aligns, is pushed home (QUAD ease-in) and seats at 1.70 s, then a 3-frame
        # overshoot/snap as the catch drops in.
        T0 = MAG_TILT_SIGN
        mag(F_BELT, new_start, T0 * 10.0, L)
        mag(F_CARRY, new_start, T0 * 10.0)
        mag(80, (5.0 * cm, 2.0 * cm, -18.0 * cm), T0 * 7.0)
        mag(92, (1.2 * cm, 0.5 * cm, -4.5 * cm), T0 * 2.0)
        mag(97, (0.0, 0.0, -2.2 * cm), 0.0, 'QUAD', 'EASE_IN')
        mag(F_SEAT, (0.0, 0.0, 0.0), 0.0, L)     # seated, 1.70 s
        mag(103, (0.0, 0.0, 0.35 * cm), 0.0, L)
        mag(104, (0.0, 0.0, 0.1 * cm), 0.0, L)
        mag(105, (0.0, 0.0, 0.0), 0.0, L)
        mag(144, (0.0, 0.0, 0.0), 0.0, L)
        for (f, T, tilt, interp, easing, scale) in mk:
            c.key("magazine", f, T, rot=('Y', tilt), interp=interp, easing=easing, scale=scale)
        return mk

    # ---- v3 left hand (palm centre) for Reload / ReloadTactical, armature space; the bone's rest
    # head is grip_l so the key translation is pos - grip_l. Snaps are LINEAR holds, reaches eased.
    def hand_swap(c, mk, empty):
        """v4: every hand key also carries the beat's ORIENTATION delta (armature space, from the UE gun-space
        design through the verified reflection) and CURL (scale X); the position keys are unchanged. Returns
        (position records, rotation key records, curl key records)."""
        rec, rot_rec, curl_rec = [], [], []

        def hand(f, pos, interp='BEZIER', easing='AUTO', phase='', beat='rest'):
            pos = Vector(pos)
            D_bl, curl = hand_beat_delta_bl(beat)
            c.key(HAND_TARGET, f, pos - grip_l, rot=D_bl, interp=interp, easing=easing, scale=(curl, 1.0, 1.0))
            axis, deg = axis_angle_ue(D_bl.to_quaternion())
            rec.append({"frame": f, "t_s": round(f / FPS, 4), "phase": phase, "interp": interp, "easing": easing,
                        "ue_cm": ue_cm(pos), "rel_grip_l_ue_cm": ue_cm(pos - grip_l),
                        "beat": beat, "rot_ue_axis": axis, "rot_ue_deg": deg, "curl": curl})
            rot_rec.append({"frame": f, "t_s": round(f / FPS, 4), "beat": beat, "axis_ue": axis, "deg": deg,
                            "interp": interp, "easing": easing})
            curl_rec.append({"frame": f, "t_s": round(f / FPS, 4), "beat": beat, "curl": curl, "interp": interp, "easing": easing})

        mag_at = {f: T for (f, T, tilt, interp, easing, scale) in mk}
        grab = mag_head + cup
        hand(0, grip_l, 'SINE', 'EASE_IN_OUT', 'reach: grip_l -> drum left face', 'rest')
        hand(F_GRAB, grab, 'QUAD', 'EASE_IN', 'grab: palm cups the drum, pulls it down with the hand', 'grab')
        hand(F_RELEASE, mag_head + mag_at[F_RELEASE] + cup, 'BEZIER', 'AUTO', 'release: lets the mag fall, hand on to the belt', 'grab')
        hand(F_BELT, belt, L, 'AUTO', 'belt: hand closes on the fresh mag (pop-in)', 'belt')
        for (f, T, tilt, interp, easing, scale) in mk:
            if F_CARRY <= f <= F_SEAT:
                hand(f, mag_head + T + cup, interp, easing, 'carry: hand = magazine + cup' if f < F_SEAT else 'seat', 'grab')
        if empty:
            hand(104, grab, 'BEZIER', 'AUTO', 'seat held, then up to the bolt catch', 'grab')
            hand(110, catch_pt, L, 'AUTO', 'palm on the bolt catch paddle', 'catch')
            hand(118, catch_pt, 'BEZIER', 'AUTO', 'catch pressed (f115), carrier home (f117)', 'catch')
            hand(144, grip_l, L, 'AUTO', 'rest: back on grip_l', 'rest')
        else:
            hand(106, grab, 'BEZIER', 'AUTO', 'seat held', 'grab')
            hand(130, grip_l, L, 'AUTO', 'back on grip_l', 'rest')
            hand(144, grip_l, L, 'AUTO', 'rest', 'rest')
        # authored consecutive-key turn must stay well under the shortest-path limit
        for a, b in zip(rot_rec, rot_rec[1:]):
            qa = hand_beat_delta_bl(a["beat"])[0].to_quaternion()
            qb = hand_beat_delta_bl(b["beat"])[0].to_quaternion()
            step = math.degrees(qa.rotation_difference(qb).angle)
            step = min(step, 360.0 - step)
            b["step_from_prev_key_deg"] = round(step, 2)
            assert step < HAND_MAX_STEP_DEG, "hand turn f%d -> f%d is %.1f deg" % (a["frame"], b["frame"], step)
        return rec, rot_rec, curl_rec

    # ---- Reload (EMPTY): starts in the IdleEmpty pose; bolt-catch release 1.85-1.92 s, carrier
    # slams home over 2 frames (33 ms) at f115-117, 2-frame settle, rest from 2.05 s.
    c = ClipAuthor(arm, "A_M4A1_Reload", 144)
    mk = mag_swap(c)
    hk, hr, hc = hand_swap(c, mk, empty=True)
    DERIVED.setdefault("hand_keys", {})["Reload"] = hk
    DERIVED.setdefault("hand_rot_keys", {})["Reload"] = hr
    DERIVED.setdefault("hand_curl_keys", {})["Reload"] = hc
    DERIVED["mag_keys"] = [{"frame": f, "bl_cm": [round(v * 100, 3) for v in T], "tilt_deg": round(tilt, 2),
                            "interp": interp, "easing": easing, "scale": scale} for (f, T, tilt, interp, easing, scale) in mk]
    catch(c, 0, True)
    catch(c, 111, True, interp='SINE', easing='EASE_IN_OUT')   # palm on the paddle at 1.85 s
    catch(c, 115, False)                                      # pressed flush -> carrier free
    catch(c, 144, False)
    c.key("bolt_carrier", 0, (-H, 0, 0), interp=L)
    c.key("bolt_carrier", 115, (-H, 0, 0), interp=L)
    c.key("bolt_carrier", 117, (0, 0, 0), interp=L)             # 2-frame slam (33 ms)
    c.key("bolt_carrier", 118, (-0.4 * cm, 0, 0), interp=L)     # settle
    c.key("bolt_carrier", 119, (0, 0, 0), interp=L)
    c.key("bolt_carrier", 144, (0, 0, 0), interp=L)
    clips["Reload"] = c.apply()

    # ---- ReloadTactical: bolt home throughout, same mag motion, no catch; rest from 1.75 s
    c = ClipAuthor(arm, "A_M4A1_ReloadTactical", 144)
    mk = mag_swap(c)
    hk, hr, hc = hand_swap(c, mk, empty=False)
    DERIVED["hand_keys"]["ReloadTactical"] = hk
    DERIVED["hand_rot_keys"]["ReloadTactical"] = hr
    DERIVED["hand_curl_keys"]["ReloadTactical"] = hc
    c.key("bolt_carrier", 0, (0, 0, 0), interp=L)
    c.key("bolt_carrier", 144, (0, 0, 0), interp=L)
    clips["ReloadTactical"] = c.apply()

    # ---- Chamber: 1.1 s (0..66). Hand grabs at f8, pulls 9.0 cm over 0.35 s with QUAD ease-in to
    # the buffer stop at f29, holds 0.1 s, lets go at f35: 2-frame slam (33 ms), 2-frame settle.
    c = ClipAuthor(arm, "A_M4A1_Chamber", 66)
    for b in ("charging_handle", "bolt_carrier"):
        c.key(b, 0, (0, 0, 0), interp=L)
        c.key(b, 8, (0, 0, 0), interp='QUAD', easing='EASE_IN')
        c.key(b, 29, (-S, 0, 0), interp=L)
        c.key(b, 35, (-S, 0, 0), interp=L)
        c.key(b, 37, (0, 0, 0), interp=L)
        c.key(b, 38, (-0.5 * cm, 0, 0), interp=L)
        c.key(b, 39, (0, 0, 0), interp=L)
        c.key(b, 66, (0, 0, 0), interp=L)
    clips["Chamber"] = c.apply()
    return clips


# trigger pull: bottom of the trigger moves back (-X). Rotation about Blender +Y by angle a
# maps the vector (0,0,-1) to (-sin a, 0, -cos a) -> back for positive a.
TRIGGER_SIGN = +1.0
# magazine forward tilt: bottom swings forward (+X) -> negative rotation about Blender +Y
MAG_TILT_SIGN = -1.0


# ============================================================================
# 4. export
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


PREROLL_FRAME = -5


def pose_is_rest(arm):
    for pb in arm.pose.bones:
        m = pb.matrix_basis
        if (m.translation.length > 1e-5) or (abs(m.to_quaternion().angle) > 1e-4):
            return False, pb.name
        if max(abs(s - 1.0) for s in m.to_scale()) > 1e-5:
            return False, pb.name
    return True, None


def sample_fcurves(act, n):
    return {(fc.data_path, fc.array_index): [fc.evaluate(f) for f in range(0, n + 1)] for fc in _fcurves(act)}


def add_rest_preroll(act, n):
    """Clips that do not end on the rest pose get a CONSTANT rest key at PREROLL_FRAME so the
    exporter can be run with the scene parked on a rest frame (the node default transforms it
    writes come from the current pose). Handles of the real keys are frozen first (FREE) so the
    curve over 0..n is bit-for-bit unchanged; asserted by sampling."""
    before = sample_fcurves(act, n)
    for fc in _fcurves(act):
        for kp in fc.keyframe_points:
            kp.handle_left_type = 'FREE'
            kp.handle_right_type = 'FREE'
    for fc in _fcurves(act):
        if fc.data_path.endswith(".location"):
            v = 0.0
        elif fc.data_path.endswith(".rotation_quaternion"):
            v = 1.0 if fc.array_index == 0 else 0.0
        elif fc.data_path.endswith(".scale"):
            v = 1.0
        else:
            raise RuntimeError("unexpected channel %s" % fc.data_path)
        kp = fc.keyframe_points.insert(PREROLL_FRAME, v, options={'FAST'})
        kp.interpolation = 'CONSTANT'
        fc.update()
    after = sample_fcurves(act, n)
    worst = max(abs(a - b) for k in before for a, b in zip(before[k], after[k]))
    assert worst < 1e-7, "pre-roll changed clip %s by %g" % (act.name, worst)
    return worst


def remove_preroll(act):
    for fc in _fcurves(act):
        for kp in reversed(list(fc.keyframe_points)):
            if kp.co.x < -0.5:
                fc.keyframe_points.remove(kp)
        fc.update()


def export_all(arm, sk, clips, export_mesh=True):
    paths = {}
    scn = bpy.context.scene
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    scn.frame_set(0)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
    mesh_path = os.path.join(OUT_DIR, "SK_M4A1.fbx")
    if export_mesh:
        # mesh + armature, no animation
        select_only([arm, sk], arm)
        bpy.ops.export_scene.fbx(filepath=mesh_path, use_selection=True, object_types={'ARMATURE', 'MESH'},
                                 bake_anim=False, **FBX_COMMON)
        log("exported", mesh_path, os.path.getsize(mesh_path))
    else:
        log("mesh FBX left untouched (--clips-only):", mesh_path, os.path.getsize(mesh_path))
    paths["mesh"] = mesh_path
    # one action per file (mesh + armature, see below)
    for name, act in clips.items():
        ensure_slot(arm, act)
        n = int(act.frame_range[1])
        scn.frame_start = 0
        scn.frame_end = n
        scn.name = act.name
        # The exporter writes each bone node's default transform from the CURRENT pose
        # (fbx_object_tx(rest=False)); importers treat that as the reference pose. So export
        # with the scene parked on a rest-pose frame: the last frame when the clip ends on rest,
        # otherwise a temporary rest pre-roll key outside the baked range.
        scn.frame_set(n)
        bpy.context.view_layer.update()
        ok, _ = pose_is_rest(arm)
        export_frame = n
        if not ok:
            add_rest_preroll(act, n)
            export_frame = PREROLL_FRAME
            log("clip", act.name, "does not end on rest: exporting from rest pre-roll frame", PREROLL_FRAME)
        scn.frame_set(export_frame)
        bpy.context.view_layer.update()
        ok, bad = pose_is_rest(arm)
        if not ok:
            raise RuntimeError("clip %s: export frame %d is not the rest pose (bone %s)" % (act.name, export_frame, bad))
        assert abs(scn.render.fps / scn.render.fps_base - FPS) < 1e-6, "scene fps is %s" % scn.render.fps
        # mesh + armature in every clip file: UE 5.8 Interchange refuses armature-only FBX
        # ("nothing to import"); the legacy importer accepts both. Import with
        # 'import only animations' onto SK_M4A1's skeleton.
        select_only([arm, sk], arm)
        p = os.path.join(OUT_DIR, act.name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={'ARMATURE', 'MESH'},
                                 bake_anim=True, bake_anim_use_all_bones=True,
                                 bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                                 bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                                 bake_anim_simplify_factor=0.0, **FBX_COMMON)
        if export_frame != n:
            remove_preroll(act)
        paths[name] = p
        log("exported", p, os.path.getsize(p), "frames 0 ..", n, "(export pose frame %d)" % export_frame)
    ad.action = None
    scn.frame_start = 0
    return paths


# ============================================================================
# 5. proof renders (v1 helpers, kept for reference; v2 uses render_proofs_v2 below)
# ============================================================================
def setup_render(gmn, gmx):
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_WORKBENCH'
    scn.display.shading.light = 'STUDIO'
    scn.display.shading.color_type = 'MATERIAL'
    scn.display.shading.show_cavity = True
    scn.display.shading.show_object_outline = True
    scn.display.shading.show_specular_highlight = True
    scn.render.film_transparent = False
    world = bpy.data.worlds.new("Proof") if not bpy.data.worlds else bpy.data.worlds[0]
    scn.world = world
    world.color = (0.5, 0.5, 0.5)
    scn.view_settings.view_transform = 'Standard'
    scn.render.image_settings.file_format = 'PNG'
    scn.render.resolution_percentage = 100
    center = Vector(((gmn.x + gmx.x) / 2, (gmn.y + gmx.y) / 2, (gmn.z + gmx.z) / 2 - 0.08))
    cams = {}
    for name, direction, up, ortho in (
            ("Cam34", Vector((0.45, -1.0, 0.38)), Vector((0, 0, 1)), 1.75),
            ("CamTop", Vector((0.0, -0.0001, 1.0)), Vector((0, 1, 0)), 1.3)):
        cd = bpy.data.cameras.new(name)
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
        cd.clip_end = 50
        cam = bpy.data.objects.new(name, cd)
        scn.collection.objects.link(cam)
        d = direction.normalized()
        cam.location = center + d * 5.0
        rot = (-d).to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot.to_euler()
        if name == "CamTop":
            # keep the muzzle pointing to the right of the image (+X image right, +Y image up)
            cam.rotation_euler = Euler((0, 0, 0))
            cam.location = center + Vector((0, 0, 5))
        cams[name] = cam
    return cams


def render_proof(arm, act, frame, filename, cams):
    scn = bpy.context.scene
    ensure_slot(arm, act)
    scn.frame_start = 0
    scn.frame_end = int(act.frame_range[1])
    scn.frame_set(frame)
    bpy.context.view_layer.update()
    tmp = {}
    for cam_name, res in (("Cam34", (1600, 640)), ("CamTop", (1600, 260))):
        scn.camera = cams[cam_name]
        scn.render.resolution_x, scn.render.resolution_y = res
        p = os.path.join(RECEIPT_DIR, "tmp_%s_%s.png" % (cam_name, filename))
        scn.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tmp[cam_name] = p
    # stack the two views into one 1600x900 image
    import numpy as np
    a = bpy.data.images.load(tmp["Cam34"])
    b = bpy.data.images.load(tmp["CamTop"])
    pa = np.array(a.pixels[:]).reshape(a.size[1], a.size[0], 4)
    pb = np.array(b.pixels[:]).reshape(b.size[1], b.size[0], 4)
    stacked = np.concatenate([pb, pa], axis=0)  # blender rows go bottom-up: top view at the bottom
    out = bpy.data.images.new("proof", 1600, 900, alpha=True)
    out.pixels = stacked.ravel().tolist()
    out.filepath_raw = os.path.join(OUT_DIR, filename)
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(a)
    bpy.data.images.remove(b)
    bpy.data.images.remove(out)
    log("proof", os.path.join(OUT_DIR, filename), "frame", frame)
    return os.path.join(OUT_DIR, filename)


# ----------------------------------------------------------------------------
# 5b. v2 proofs: cutaway / section views so the internal parts read
# ----------------------------------------------------------------------------
PROOF2_FRAMES = {
    "Idle": [0],
    "IdleEmpty": [0],
    "Fire": [0, 2, 4, 7],
    "FireLast": [2, 3, 4, 7],
    "DryFire": [0, 2],
    "Reload": [0, 6, 12, 18, 27, 36, 56, 66, 80, 84, 102, 115, 116, 117, 144],
    "ReloadTactical": [0, 27, 102, 120],
    "Chamber": [0, 29, 36, 37],
}
PROOF2_STRIPS = {
    "Reload": [0.0, 0.3, 0.45, 0.6, 1.1, 1.4, 1.7, 1.95, 2.4],
    "ReloadTactical": [0.0, 0.45, 1.7, 2.0],
}
# v3 hand-target proofs (gun's left side / front / three-quarter, marker sphere on hand_l_target)
HAND_PROOF_FRAMES = {
    "Reload": [0, 12, 20, 27, 40, 56, 66, 80, 92, 102, 110, 118, 130, 144],
    "ReloadTactical": [12, 56, 80, 106, 130],
}
HAND_STRIP_FRAMES = {"Reload": [0, 12, 27, 40, 56, 80, 102, 110, 144]}
HAND_PANEL_L_RES = (800, 880)      # v4 hand proof: the left-side tile (also the strip tile)
HAND_XRAY_ALPHA = 0.35             # the right-side hand panel is rendered see-through so the palm face shows
# faces of these slots (body bone only) on the gun's right half are cut away on the proof copy
CUT_SLOTS = ("Receiver_Upper", "Receiver_Lower", "BufferTube", "Buttstock", "Barrel")
PROOF_PART_COLOR = {"trigger": (1.0, 0.08, 0.08, 1), "mag_release": (0.1, 1.0, 0.25, 1),
                    "bolt_catch": (0.95, 0.15, 0.95, 1), "selector": (0.15, 0.9, 0.95, 1)}


def _proof_mat(name, col):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = col
    return m


def build_proof_scene(arm, sk):
    """Proof-only objects (never exported or saved): PROOF_cut (right half of the receiver,
    buffer tube, stock and barrel extension removed; small parts recoloured), PROOF_full
    (recoloured, uncut) and stroke / drop rulers. The original SK_M4A1 is hidden from render."""
    scn = bpy.context.scene
    objs = {}
    for name, cut in (("PROOF_cut", True), ("PROOF_full", False)):
        ob = sk.copy()
        ob.data = sk.data.copy()
        ob.name = name
        scn.collection.objects.link(ob)
        me = ob.data
        base = len(me.materials)
        order = list(PROOF_PART_COLOR)
        for b in order:
            me.materials.append(_proof_mat("PROOF_" + b, PROOF_PART_COLOR[b]))
        gi = {g.index: g.name for g in ob.vertex_groups}
        vbone = [gi[v.groups[0].group] for v in me.vertices]
        slot_names = [m.name for m in me.materials]
        bm = bmesh.new()
        bm.from_mesh(me)
        kill = []
        for f in bm.faces:
            b = vbone[f.verts[0].index]
            if b in PROOF_PART_COLOR:
                f.material_index = base + order.index(b)
            elif cut and b == "body" and slot_names[f.material_index] in CUT_SLOTS:
                c = f.calc_center_median()
                if c.y < 0.0 and (slot_names[f.material_index] != "Barrel" or c.x < 0.18):
                    kill.append(f)
        if kill:
            bmesh.ops.delete(bm, geom=kill, context='FACES')
        bm.to_mesh(me)
        bm.free()
        objs[name] = ob
        log("proof object", name, "faces removed", len(kill))
    sk.hide_render = True
    # rulers (fixed, not parented): carrier rear-face ticks + magazine-top drop ticks
    cmin_x = min(v.co.x for v in sk.data.vertices
                 if sk.vertex_groups[sk.data.vertices[v.index].groups[0].group].name == "bolt_carrier")
    mag_top = arm.data.bones["magazine"].head_local.z
    white, yellow, red = (1, 1, 1, 1), (1, 0.9, 0.0, 1), (1, 0.05, 0.05, 1)

    def box(name, center, size, col):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(center)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(_proof_mat("PROOF_" + name, col))
        ob = bpy.data.objects.new(name, me)
        scn.collection.objects.link(ob)
        return ob

    rc = []
    for nm, dx, col in (("tick_rest", 0.0, white), ("tick_holdopen", -HOLD_OPEN_CM, yellow),
                        ("tick_stroke", -STROKE_CM, red)):
        rc.append(box("RULER_c_" + nm, (cmin_x + dx * 0.01, -0.08, 0.092), (0.0016, 0.002, 0.014), col))
    rc.append(box("RULER_c_base", (cmin_x - 0.045, -0.08, 0.0855), (0.11, 0.002, 0.0008), white))
    rm = []
    for nm, dz, col in (("seat", 0.0, white), ("m30", -30.0, yellow), ("m70", MAG_PARK_CM, red)):
        rm.append(box("RULER_m_" + nm, (0.225, -0.08, mag_top + dz * 0.01), (0.03, 0.002, 0.003), col))
    objs["ruler_carrier"] = rc
    objs["ruler_mag"] = rm
    # v4: PALM PROXY (replaces the v3 marker sphere): parts modelled in the hand's Blender-local right-handed
    # frame (X = fingers, Y = back of the hand, Z = thumb side, see hand_frame_bl_from_delta) under an empty
    # that is moved onto the posed hand_l_target and turned by its keyed delta every proof frame. Yellow plate
    # = the PALM face (-Y), dark green = the back of the hand, red bar + cube = the finger direction, blue cube
    # = the thumb side, so a viewer can tell which way the palm faces and whether the hand is mirrored.
    cmv = 0.01
    L_, W_ = HAND_PROXY_CM
    A_ = HAND_PROXY_ARROW_CM

    def part(name, center, size, col):
        return box(name, [c * cmv for c in center], [s * cmv for s in size], col)

    proxy_root = bpy.data.objects.new("PROOF_hand_proxy", None)
    scn.collection.objects.link(proxy_root)
    parts = [part("hand_palm_face", (0.0, -0.15, 0.0), (L_, 0.3, W_), (1.0, 0.9, 0.1, 1)),
             part("hand_palm_back", (0.0, 0.15, 0.0), (L_, 0.3, W_), (0.08, 0.3, 0.1, 1)),
             part("hand_finger_arrow", (L_ / 2 + A_ / 2, 0.0, 0.0), (A_, 0.7, 0.7), (1.0, 0.1, 0.05, 1)),
             part("hand_finger_tip", (L_ / 2 + A_ + 0.7, 0.0, 0.0), (1.6, 1.6, 1.6), (1.0, 0.1, 0.05, 1)),
             part("hand_thumb_side", (1.0, 0.0, W_ / 2 + 0.9), (1.8, 1.8, 1.8), (0.15, 0.4, 1.0, 1))]
    for p in parts:
        p.parent = proxy_root
    objs["hand_proxy"] = [proxy_root] + parts
    log("ruler: carrier rear face rest x cm", round(cmin_x * 100, 2), "mag top z cm", round(mag_top * 100, 2),
        "palm proxy %gx%g cm + %g cm arrow" % (L_, W_, A_))
    return objs


def make_ortho_cam(name, center, forward, up, ortho, dist=2.0, clip_start=0.01, clip_end=10.0):
    cd = bpy.data.cameras.new(name)
    cd.type = 'ORTHO'
    cd.ortho_scale = ortho
    cd.clip_start = clip_start
    cd.clip_end = clip_end
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    f = Vector(forward).normalized()
    u = Vector(up).normalized()
    r = f.cross(u).normalized()
    u = r.cross(f).normalized()
    rot = Matrix((r, u, -f)).transposed().to_4x4()
    cam.matrix_world = Matrix.Translation(Vector(center) - f * dist) @ rot
    return cam


def proof_panels():
    """(key, camera, resolution, visible object keys, caption)."""
    Y = (0, 1, 0)
    Z = (0, 0, 1)
    sec_x = 0.094   # section plane through the mag release bar, just ahead of the bolt catch
    return [
        ("A", make_ortho_cam("P2_A", (0.175, 0, -0.291), Y, Z, 1.049), (800, 780),
         ("PROOF_cut", "ruler_carrier", "ruler_mag", "hand_proxy"),
         "right side, right half cut away; mag ticks: yellow -30, red -70; hand = palm proxy (yellow palm / red fingers)"),
        ("B", make_ortho_cam("P2_B", (-0.01, 0, 0.055), Y, Z, 0.40), (800, 300),
         ("PROOF_cut", "ruler_carrier"),
         "carrier rear ticks: white home, yellow hold-open -8.2, red stroke -9.0"),
        ("C", make_ortho_cam("P2_C", (sec_x, 0.003, 0.029), (-1, 0, 0), Z, 0.14, dist=1.0, clip_start=1.0),
         (800, 300), ("PROOF_full",),
         "section x=9.4 looking aft (gun-left = image right): release green, catch magenta"),
        ("D", make_ortho_cam("P2_D", (0.065, 0, 0.005), Y, Z, 0.18), (800, 300),
         ("PROOF_cut",), "trigger (red) close-up, right side cut away"),
    ]


def hand_proof_panels():
    """v3/v4 hand-target views: L = the gun's LEFT side (camera on +Y looking -Y; muzzle to the image left),
    F = front view looking aft (image right = gun-left), Q = three-quarter from left-front-above, R (v4) =
    the gun's RIGHT side rendered see-through (x-ray) so the yellow PALM face of the proxy shows against the
    magazine / receiver it is supposed to face. Uncut recoloured mesh + palm proxy. (key, cam, res, visible,
    caption, xray)."""
    Z = (0, 0, 1)
    return [
        ("L", make_ortho_cam("P3_L", (0.12, 0.0, -0.20), (0, -1, 0), Z, 0.90), HAND_PANEL_L_RES,
         ("PROOF_full", "hand_proxy", "ruler_mag"),
         "gun's LEFT side (muzzle left); palm proxy: yellow = palm, dark green = back, red = fingers, blue = thumb", False),
        ("F", make_ortho_cam("P3_F", (0.14, 0.03, -0.17), (-1, 0, 0), Z, 1.45, dist=1.5), (800, 340),
         ("PROOF_full", "hand_proxy"),
         "front view looking aft (image right = gun-LEFT): hand left of / below the receiver", False),
        ("Q", make_ortho_cam("P3_Q", (0.12, 0.0, -0.18), (-0.55, -0.75, -0.35), Z, 1.15, dist=3.0), (800, 330),
         ("PROOF_full", "hand_proxy"), "three-quarter from the left-front-above", False),
        ("R", make_ortho_cam("P3_R", (0.12, 0.0, -0.16), (0, 1, 0), Z, 1.35), (800, 330),
         ("PROOF_full", "hand_proxy"),
         "gun's RIGHT side, x-ray: the yellow PALM face must show through the mag (grab/carry) / receiver (catch)", True),
    ]


def pose_values(arm):
    """Key values at the current frame, armature space (Blender) -> printed in UE cm/deg."""
    def d(b):
        pb = arm.pose.bones[b]
        return (pb.matrix.translation - pb.bone.head_local) * 100.0

    def ang(b):
        pb = arm.pose.bones[b]
        q = (pb.bone.matrix_local.inverted() @ pb.matrix).to_quaternion()
        return math.degrees(q.angle)
    m = d("magazine")
    out = {"carrier_x": round(d("bolt_carrier").x, 2), "chandle_x": round(d("charging_handle").x, 2),
           "mag_ue": [round(m.x, 1), round(-m.y, 1), round(m.z, 1)], "mag_tilt": round(ang("magazine"), 1),
           "trigger_deg": round(ang("trigger"), 1), "catch_deg": round(ang("bolt_catch"), 1),
           "magrel_in_cm": round(d("mag_release").y, 2)}
    if HAND_TARGET in arm.pose.bones:
        pbm = arm.pose.bones["magazine"]
        out["mag_scale"] = round((pbm.bone.matrix_local.inverted() @ pbm.matrix).to_scale().x, 4)
        hp = arm.pose.bones[HAND_TARGET].matrix.translation * 100.0     # absolute, armature cm
        out["hand_ue"] = [round(hp.x, 1), round(-hp.y, 1), round(hp.z, 1)]
        cup = Vector(DERIVED.get("cup_offset_bl_cm", (0, 0, 0)))
        magp = pbm.matrix.translation * 100.0 + cup
        out["hand_minus_magcup_cm"] = round((hp - magp).length, 2)
        gl = arm.data.bones["grip_l"].head_local * 100.0
        out["hand_minus_grip_l_cm"] = round((hp - gl).length, 2)
        # v4: orientation delta (UE gun-space axis-angle), curl and the resulting palm / finger directions
        pbh = arm.pose.bones[HAND_TARGET]
        _, q_bl, scl = (pbh.bone.matrix_local.inverted() @ pbh.matrix).decompose()
        axis, deg = axis_angle_ue(q_bl)
        D_ue = quat_bl_to_ue(q_bl).to_matrix()
        out["hand_rot_ue"] = {"axis": axis, "deg": deg}
        out["hand_curl"] = round(scl.x, 3)
        out["palm_normal_ue"] = [round(v, 2) for v in (D_ue @ (-HAND_REST_FRAME_UE.col[1]))]
        out["finger_dir_ue"] = [round(v, 2) for v in (D_ue @ HAND_REST_FRAME_UE.col[0])]
    return out


def _font(size):
    from PIL import ImageFont
    for f in (r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_proofs_v2(arm, sk, clips):
    from PIL import Image, ImageDraw
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_WORKBENCH'
    sh = scn.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.show_object_outline = True
    sh.show_specular_highlight = True
    sh.show_backface_culling = False
    scn.render.film_transparent = False
    world = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("Proof")
    scn.world = world
    world.color = (0.36, 0.38, 0.42)
    scn.view_settings.view_transform = 'Standard'
    scn.render.image_settings.file_format = 'PNG'
    scn.render.resolution_percentage = 100
    objs = build_proof_scene(arm, sk)
    panels = proof_panels()
    hand_panels = hand_proof_panels()
    every = [objs["PROOF_cut"], objs["PROOF_full"]] + objs["hand_proxy"] + objs["ruler_carrier"] + objs["ruler_mag"]
    tmpdir = os.path.join(RECEIPT_DIR, "proof2_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    f_big, f_small = _font(22), _font(16)
    out = {}
    a_tiles = {}
    hand_tiles = {}

    def visible(keys):
        vis = set()
        for k in keys:
            v = objs[k]
            for o in (v if isinstance(v, list) else [v]):
                vis.add(o.name)
        for o in every:
            o.hide_render = o.name not in vis

    def place_proxy():
        """v4: the palm proxy root onto the posed hand_l_target, turned by the keyed delta (the hand's
        measured rest frame rotated by the pose quaternion, in Blender armature space)."""
        pb = arm.pose.bones[HAND_TARGET]
        pose_m = arm.matrix_world @ pb.matrix
        _, q_bl, _ = (pb.bone.matrix_local.inverted() @ pb.matrix).decompose()
        objs["hand_proxy"][0].matrix_world = Matrix.Translation(pose_m.translation) @ hand_frame_bl_from_delta(q_bl).to_4x4()

    def set_frame(clip, frame):
        act = clips[clip]
        ensure_slot(arm, act)
        scn.frame_start = 0
        scn.frame_end = int(act.frame_range[1])
        scn.frame_set(frame)
        bpy.context.view_layer.update()
        place_proxy()
        bpy.context.view_layer.update()
        return pose_values(arm)

    def hand_lines(clip, frame, vals):
        cup = DERIVED.get("cup_offset_bl_cm", (0, 0, 0))
        r = vals.get("hand_rot_ue", {"axis": [0, 0, 1], "deg": 0.0})
        return ["A_M4A1_%s f%03d t=%.3f s  LEFT HAND = PALM PROXY %gx%g cm: yellow = PALM face, dark green = back, red = fingers, blue = thumb side" % (
                    clip, frame, frame / FPS, HAND_PROXY_CM[0], HAND_PROXY_CM[1]),
                "hand_l_target UE cm %s  |hand-(mag+cup)| %.2f  |hand-grip_l| %.1f   CURL (scale X) %.2f" % (
                    vals.get("hand_ue"), vals.get("hand_minus_magcup_cm", -1), vals.get("hand_minus_grip_l_cm", -1), vals.get("hand_curl", 1.0)),
                "delta from the aim-pose hand: %.1f deg about UE axis %s  ->  palm normal UE %s  fingers UE %s" % (
                    r["deg"], r["axis"], vals.get("palm_normal_ue"), vals.get("finger_dir_ue")),
                "mag UE cm %s tilt %.0f scale %.3f   cup UE [%.1f, %.2f, %.1f]  belt UE %s  carrier %+.1f" % (
                    vals["mag_ue"], vals["mag_tilt"], vals.get("mag_scale", 1.0), cup[0], -cup[1], cup[2], list(HAND_BELT_UE_CM), vals["carrier_x"])]

    HAND_VAL_KEYS = ("hand_ue", "mag_ue", "mag_scale", "hand_minus_magcup_cm", "hand_minus_grip_l_cm",
                     "hand_rot_ue", "hand_curl", "palm_normal_ue", "finger_dir_ue")

    def render_hand_frame(clip, frame):
        vals = set_frame(clip, frame)
        canvas = Image.new("RGB", (1600, 1000), (20, 20, 20))
        draw = ImageDraw.Draw(canvas)
        pos = {"L": (0, 120), "F": (800, 0), "Q": (800, 340), "R": (800, 670)}
        for key, cam, res, vis, caption, xray in hand_panels:
            visible(vis)
            scn.camera = cam
            scn.render.resolution_x, scn.render.resolution_y = res
            sh.show_xray = bool(xray)         # v4: the right-side panel is see-through so the palm face shows
            sh.xray_alpha = HAND_XRAY_ALPHA
            p = os.path.join(tmpdir, "%s_f%03d_hand_%s.png" % (clip, frame, key))
            scn.render.filepath = p
            bpy.ops.render.render(write_still=True)
            sh.show_xray = False
            im = Image.open(p).convert("RGB")
            canvas.paste(im, pos[key])
            if key == "L":
                hand_tiles[(clip, frame)] = im.copy()
            x0, y0 = pos[key]
            draw.text((x0 + 8, y0 + res[1] - 22), "%s: %s" % (key, caption), fill=(255, 255, 255), font=f_small)
        draw.line([(800, 0), (800, 1000)], fill=(0, 0, 0), width=3)
        draw.line([(0, 120), (800, 120)], fill=(0, 0, 0), width=3)
        draw.line([(800, 340), (1600, 340)], fill=(0, 0, 0), width=3)
        draw.line([(800, 670), (1600, 670)], fill=(0, 0, 0), width=3)
        f_mid = _font(18)
        for i, s in enumerate(hand_lines(clip, frame, vals)):
            draw.text((10, 8 + i * 27), s, fill=(255, 255, 120) if i == 0 else (255, 255, 255), font=f_mid)
        name = "proof2_%s_f%03d_hand.png" % (clip, frame)
        path = os.path.join(OUT_DIR, name)
        canvas.save(path)
        log("proof2 hand", path, {k: vals[k] for k in HAND_VAL_KEYS if k in vals})
        return path, vals

    def render_frame(clip, frame):
        vals = set_frame(clip, frame)
        canvas = Image.new("RGB", (1600, 900), (20, 20, 20))
        draw = ImageDraw.Draw(canvas)
        pos = {"A": (0, 120), "B": (800, 0), "C": (800, 300), "D": (800, 600)}
        for key, cam, res, vis, caption in panels:
            visible(vis)
            scn.camera = cam
            scn.render.resolution_x, scn.render.resolution_y = res
            p = os.path.join(tmpdir, "%s_f%03d_%s.png" % (clip, frame, key))
            scn.render.filepath = p
            bpy.ops.render.render(write_still=True)
            im = Image.open(p).convert("RGB")
            canvas.paste(im, pos[key])
            if key == "A":
                a_tiles[(clip, frame)] = im.copy()
            x0, y0 = pos[key]
            draw.text((x0 + 8, y0 + res[1] - 22), "%s: %s" % (key, caption), fill=(255, 255, 255), font=f_small)
        draw.line([(800, 0), (800, 900)], fill=(0, 0, 0), width=3)
        draw.line([(0, 120), (800, 120)], fill=(0, 0, 0), width=3)
        draw.line([(800, 300), (1600, 300)], fill=(0, 0, 0), width=3)
        draw.line([(800, 600), (1600, 600)], fill=(0, 0, 0), width=3)
        lines = ["A_M4A1_%s  f%03d  t=%.3f s" % (clip, frame, frame / FPS),
                 "carrier X %+.2f cm   ch.handle X %+.2f cm" % (vals["carrier_x"], vals["chandle_x"]),
                 "mag (UE cm) %s  tilt %.1f deg" % (vals["mag_ue"], vals["mag_tilt"]),
                 "trigger %.1f deg  bolt catch %.1f deg  mag release in %.2f cm" % (
                     vals["trigger_deg"], vals["catch_deg"], vals["magrel_in_cm"])]
        for i, s in enumerate(lines):
            draw.text((10, 8 + i * 26), s, fill=(255, 255, 120) if i == 0 else (255, 255, 255), font=f_big)
        name = "proof2_%s_f%03d.png" % (clip, frame)
        path = os.path.join(OUT_DIR, name)
        canvas.save(path)
        log("proof2", path, vals)
        return path, vals

    for clip, frames in PROOF2_FRAMES.items():
        for fr in frames:
            p, vals = render_frame(clip, fr)
            out.setdefault(clip, []).append({"frame": fr, "t": round(fr / FPS, 4), "png": p, "values": vals})
    # strips (panel A tiles, labelled with the time)
    for clip, times in PROOF2_STRIPS.items():
        frames = [int(round(t * FPS)) for t in times]
        for fr in frames:
            if (clip, fr) not in a_tiles:
                p, vals = render_frame(clip, fr)
                out.setdefault(clip, []).append({"frame": fr, "t": round(fr / FPS, 4), "png": p, "values": vals})
        cols = 5 if len(frames) > 4 else 4
        rows = (len(frames) + cols - 1) // cols
        tw = 1600 // cols
        th = int(tw * 780 / 800)
        strip = Image.new("RGB", (1600, rows * th + 40), (20, 20, 20))
        sd = ImageDraw.Draw(strip)
        sd.text((10, 8), "A_M4A1_%s strip (right side cutaway; ticks: white seated, yellow -30 cm, red -70 cm)" % clip,
                fill=(255, 255, 120), font=f_big)
        for i, fr in enumerate(frames):
            im = a_tiles[(clip, fr)].resize((tw, th))
            x, y = (i % cols) * tw, 40 + (i // cols) * th
            strip.paste(im, (x, y))
            sd.rectangle([x, y, x + tw - 1, y + th - 1], outline=(0, 0, 0), width=2)
            sd.text((x + 8, y + 6), "t=%.2f s (f%d)" % (fr / FPS, fr), fill=(255, 255, 255), font=f_big)
        sp = os.path.join(OUT_DIR, "proof2_%s_strip.png" % clip)
        strip.save(sp)
        out.setdefault("strips", {})[clip] = sp
        log("proof2 strip", sp)
    # v3 hand-target proofs + strip
    for clip, frames in HAND_PROOF_FRAMES.items():
        if clip not in clips:
            continue
        for fr in frames:
            p, vals = render_hand_frame(clip, fr)
            out.setdefault("hand", {}).setdefault(clip, []).append(
                {"frame": fr, "t": round(fr / FPS, 4), "png": p,
                 "values": {k: vals[k] for k in HAND_VAL_KEYS if k in vals}})
    for clip, frames in HAND_STRIP_FRAMES.items():
        if clip not in clips:
            continue
        for fr in frames:
            if (clip, fr) not in hand_tiles:
                render_hand_frame(clip, fr)
        cols = 5 if len(frames) > 4 else 4
        rows = (len(frames) + cols - 1) // cols
        tw = 1600 // cols
        th = int(tw * HAND_PANEL_L_RES[1] / HAND_PANEL_L_RES[0])
        strip = Image.new("RGB", (1600, rows * th + 40), (20, 20, 20))
        sd = ImageDraw.Draw(strip)
        sd.text((10, 8), "A_M4A1_%s LEFT HAND strip (gun's left side; palm proxy: yellow palm / dark back / red fingers / blue thumb)" % clip,
                fill=(255, 255, 120), font=f_big)
        for i, fr in enumerate(frames):
            im = hand_tiles[(clip, fr)].resize((tw, th))
            x, y = (i % cols) * tw, 40 + (i // cols) * th
            strip.paste(im, (x, y))
            sd.rectangle([x, y, x + tw - 1, y + th - 1], outline=(0, 0, 0), width=2)
            sd.text((x + 8, y + 6), "t=%.2f s (f%d)" % (fr / FPS, fr), fill=(255, 255, 255), font=f_big)
        sp = os.path.join(OUT_DIR, "proof2_%s_hand_strip.png" % clip)
        strip.save(sp)
        out.setdefault("hand_strips", {})[clip] = sp
        log("proof2 hand strip", sp)
    # leave the scene as it was (proof objects are never saved: the .blend is saved earlier)
    for o in every:
        bpy.data.objects.remove(o, do_unlink=True)
    sk.hide_render = False
    arm.animation_data.action = None
    return out


# ============================================================================
# 6. verification by re-import (v2)
# ============================================================================
def bone_world_head(arm, name):
    pb = arm.pose.bones[name]
    return (arm.matrix_world @ pb.matrix).translation


def _hold_open():
    return -HOLD_OPEN_CM


def v2_checks():
    """clip -> (last frame, [(bone, frame, kind, expect)]). kind 'd' = head delta, Blender cm
    (None = don't care); 'rot' = rotation magnitude deg vs rest. Frames are 60 fps."""
    HO, S = _hold_open(), -STROKE_CM
    Z = (0, 0, 0)
    parked_f = DERIVED["mag_parked_frame"]
    hidden_f = DERIVED["mag_hidden_from_frame"]
    new_start = tuple(DERIVED["mag_new_start_bl_cm"])
    mid_hold = (hidden_f + F_BELT) // 2
    # v3 magazine: seated to f12, 12 cm down with the hand by f27, free fall, parked at -70,
    # hidden (scale 0.001) from hidden_f to f55, pops in at the belt point f56 (scale 1), held to
    # f66, carried up, seated f102. Hand target: on grip_l at f0 / f144, on the mag + cup at the
    # grab / release / carry frames.
    mag_swap = [("magazine", 12, "d", Z), ("magazine", 27, "d", (0, 0, -HAND_PULL_CM)),
                ("magazine", parked_f, "d", (None, None, MAG_PARK_CM)), ("magazine", mid_hold, "d", (None, None, MAG_PARK_CM)),
                ("magazine", 55, "d", (None, None, MAG_PARK_CM)), ("magazine", 56, "d", new_start),
                ("magazine", 66, "d", new_start), ("magazine", 80, "d", (5.0, 2.0, -18.0)),
                ("magazine", 102, "d", Z), ("magazine", 103, "d", (0, 0, 0.35)), ("magazine", 105, "d", Z),
                ("magazine", 144, "d", Z), ("magazine", 144, "rot", 0.0),
                ("magazine", 0, "scale", 1.0), ("magazine", 27, "scale", 1.0), ("magazine", hidden_f - 1, "scale", 1.0),
                ("magazine", hidden_f, "scale", MAG_HIDDEN_SCALE), ("magazine", mid_hold, "scale", MAG_HIDDEN_SCALE),
                ("magazine", 55, "scale", MAG_HIDDEN_SCALE), ("magazine", 56, "scale", 1.0), ("magazine", 80, "scale", 1.0),
                ("magazine", 144, "scale", 1.0),
                ("mag_release", 6, "d", (0, MAG_RELEASE_PRESS_CM, 0)), ("mag_release", 12, "d", (0, MAG_RELEASE_PRESS_CM, 0)),
                ("mag_release", 16, "d", Z),
                (HAND_TARGET, 0, "hand_grip", 0.3), (HAND_TARGET, 144, "hand_grip", 0.3),
                (HAND_TARGET, 12, "hand_mag", 2.0), (HAND_TARGET, 20, "hand_mag", 2.0), (HAND_TARGET, 27, "hand_mag", 2.0),
                (HAND_TARGET, 66, "hand_mag", 2.0), (HAND_TARGET, 80, "hand_mag", 2.0), (HAND_TARGET, 86, "hand_mag", 2.0),
                (HAND_TARGET, 92, "hand_mag", 2.0), (HAND_TARGET, 102, "hand_mag", 2.0),
                (HAND_TARGET, 56, "p", DERIVED["belt_bl_cm"]),
                # v4: orientation delta + curl at the beat frames equal the design table (UE gun space)
                (HAND_TARGET, 12, "hand_beat", "grab"), (HAND_TARGET, 27, "hand_beat", "grab"), (HAND_TARGET, 56, "hand_beat", "belt"),
                (HAND_TARGET, 66, "hand_beat", "grab"), (HAND_TARGET, 80, "hand_beat", "grab"), (HAND_TARGET, 92, "hand_beat", "grab"),
                (HAND_TARGET, 102, "hand_beat", "grab")]
    beats_empty = [(HAND_TARGET, 104, "hand_beat", "grab"), (HAND_TARGET, 110, "hand_beat", "catch"), (HAND_TARGET, 118, "hand_beat", "catch")]
    beats_tact = [(HAND_TARGET, 106, "hand_beat", "grab"), (HAND_TARGET, 130, "hand_beat", "rest")]
    rest_hand = [(HAND_TARGET, 0, "hand_grip", 0.3)]
    return {
        "Idle": (1, [("bolt_carrier", 0, "d", Z), ("bolt_carrier", 1, "d", Z), ("bolt_catch", 1, "rot", 0.0)] + rest_hand
                 + [(HAND_TARGET, 1, "hand_grip", 0.3)]),
        "IdleEmpty": (1, [("bolt_carrier", 0, "d", (HO, 0, 0)), ("bolt_carrier", 1, "d", (HO, 0, 0)),
                          ("bolt_catch", 0, "rot", 10.0), ("bolt_catch", 1, "rot", 10.0), ("magazine", 1, "d", Z),
                          ("trigger", 1, "rot", 0.0)]),
        "Fire": (7, [("bolt_carrier", 0, "d", Z), ("bolt_carrier", 1, "d", (S / 2, 0, 0)), ("bolt_carrier", 2, "d", (S, 0, 0)),
                     ("bolt_carrier", 6, "d", (-0.3, 0, 0)), ("bolt_carrier", 7, "d", Z), ("charging_handle", 2, "d", Z)]
                 + [("trigger", f, "rot", 8.0) for f in range(0, 7)] + [("trigger", 7, "rot", 0.0)]),
        "FireLast": (7, [("bolt_carrier", 2, "d", (S, 0, 0)), ("bolt_carrier", 4, "d", (HO, 0, 0)),
                         ("bolt_carrier", 7, "d", (HO, 0, 0)), ("bolt_catch", 0, "rot", 0.0), ("bolt_catch", 3, "rot", 10.0),
                         ("bolt_catch", 7, "rot", 10.0), ("trigger", 6, "rot", 8.0), ("trigger", 7, "rot", 0.0),
                         ("magazine", 7, "d", Z)]),
        "DryFire": (9, [("bolt_carrier", 1, "d", Z), ("trigger", 1, "rot", 8.0), ("trigger", 4, "rot", 8.0),
                        ("trigger", 9, "rot", 0.0)]),
        "Reload": (144, [("bolt_carrier", 0, "d", (HO, 0, 0)), ("bolt_carrier", 115, "d", (HO, 0, 0)),
                         ("bolt_carrier", 116, "d", (HO / 2, 0, 0)), ("bolt_carrier", 117, "d", Z),
                         ("bolt_carrier", 118, "d", (-0.4, 0, 0)), ("bolt_carrier", 119, "d", Z), ("bolt_carrier", 144, "d", Z),
                         ("bolt_catch", 0, "rot", 10.0), ("bolt_catch", 111, "rot", 10.0), ("bolt_catch", 115, "rot", 0.0),
                         ("bolt_catch", 144, "rot", 0.0)] + mag_swap + beats_empty),
        "ReloadTactical": (144, [("bolt_carrier", f, "d", Z) for f in range(0, 145)]
                           + [("bolt_catch", f, "rot", 0.0) for f in range(0, 145, 4)] + mag_swap + beats_tact),
        "Chamber": (66, [(b, f, "d", e) for b in ("charging_handle", "bolt_carrier")
                         for f, e in ((8, Z), (29, (S, 0, 0)), (35, (S, 0, 0)), (36, (S / 2, 0, 0)), (37, Z),
                                      (38, (-0.5, 0, 0)), (39, Z), (66, Z))] + rest_hand
                    + [(HAND_TARGET, 66, "hand_grip", 0.3), (HAND_TARGET, 30, "hand_grip", 0.3)]),
    }


def fbx_model_defaults(path, bones):
    """Lcl Translation / Lcl Rotation written for each bone node (the node default transform
    that importers use as the reference pose), read with Blender's own binary FBX parser."""
    from io_scene_fbx import parse_fbx
    root, _ver = parse_fbx.parse(path)
    out = {}
    for e in root.elems:
        if e.id != b"Objects":
            continue
        for m in e.elems:
            if m.id != b"Model":
                continue
            name = m.props[1].split(b"\x00")[0].decode()
            if name not in bones:
                continue
            vals = {}
            for p in m.elems:
                if p.id != b"Properties70":
                    continue
                for q in p.elems:
                    key = q.props[0].decode() if isinstance(q.props[0], bytes) else q.props[0]
                    if key in ("Lcl Translation", "Lcl Rotation"):
                        vals[key] = [float(v) for v in q.props[4:7]]
            out[name] = vals
    return out


def verify_reimport_v2(paths, heads, expect_bones, json_heads_ue):
    report = {}
    # ---- mesh (left as is in --clips-only; re-checked here anyway)
    bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
    bpy.ops.import_scene.fbx(filepath=paths["mesh"])
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    mn, mx = bounds_of(meshes)
    names = [b.name for b in arms[0].data.bones]
    slots = [m.name for m in meshes[0].data.materials]
    report["mesh"] = {"length_cm": round((mx.x - mn.x) * 100, 2), "bones": names, "slots": slots}
    assert 100 < (mx.x - mn.x) * 100 < 130
    assert sorted(names) == sorted(expect_bones), "mesh bone mismatch"
    assert slots == SLOT_ORDER, "slot order mismatch %s" % slots
    moving = [b for b in KEYED_BONES if b in expect_bones]
    assert HAND_TARGET in names, "mesh FBX lacks %s" % HAND_TARGET
    ref_defaults = fbx_model_defaults(paths["mesh"], set(expect_bones))
    cup_bl = Vector(DERIVED["cup_offset_bl_cm"]) * 0.01
    checks = v2_checks()
    for clip, (last, tests) in checks.items():
        bpy.ops.wm.read_homefile(use_empty=True)  # NOT read_factory_settings: in Blender 5.2 it wipes the owner's extension wheels (PIL/cv2)
        bpy.ops.import_scene.fbx(filepath=paths[clip], anim_offset=0.0)
        bpy.context.view_layer.update()
        scn = bpy.context.scene
        fps_in = scn.render.fps / scn.render.fps_base
        scn.render.fps = FPS     # the importer may leave another rate; frames are what we sample
        scn.render.fps_base = 1.0
        arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
        acts = list(bpy.data.actions)
        assert len(acts) == 1, "clip %s: %d actions" % (clip, len(acts))
        act = acts[0]
        fr = [round(v, 3) for v in act.frame_range]
        nkeys = max(len(fc.keyframe_points) for fc in _fcurves(act))
        names = [b.name for b in arm.data.bones]
        res = {"fbx": paths[clip], "fps_after_import": fps_in, "action": act.name, "frame_range": fr,
               "keys_per_curve": nkeys, "length_s": round((fr[1] - fr[0]) / FPS, 4), "tests": []}
        log("clip", clip, "fps after import", fps_in, "frame range", fr, "keys", nkeys)
        assert abs(fps_in - FPS) < 1e-6, "clip %s imported at %s fps" % (clip, fps_in)
        assert sorted(names) == sorted(expect_bones) and len(names) == len(expect_bones), "clip %s bone mismatch %s" % (clip, names)
        assert fr == [0.0, float(last)], "clip %s frame range %s expected [0, %d]" % (clip, fr, last)
        assert nkeys == last + 1, "clip %s has %d keys, expected %d" % (clip, nkeys, last + 1)
        # v4: every clip must carry the hand target at identity / curl 1.0 on its first and last frame, and the
        # re-imported rest orientation of the target must still be the identity (the delta convention needs it)
        tests = list(tests) + [(HAND_TARGET, 0, "hand_rot_id", 2.0), (HAND_TARGET, last, "hand_rot_id", 2.0),
                               (HAND_TARGET, 0, "hand_curl", 1.0), (HAND_TARGET, last, "hand_curl", 1.0)]
        hand_rest3 = arm.pose.bones[HAND_TARGET].bone.matrix_local.to_3x3()
        res["hand_rest_orientation_deg"] = round(math.degrees(hand_rest3.to_quaternion().angle), 5)
        assert res["hand_rest_orientation_deg"] < 0.01, "clip %s: re-imported %s rest orientation is not identity" % (clip, HAND_TARGET)

        def hand_delta(pb):
            """(armature-space delta quaternion, bone-local scale) of the re-imported hand target now. The
            delta is pose rotation * rest^-1 (== the local pose rotation for the identity rest, asserted
            above); the scale comes from the local basis so the root's scale never enters."""
            _, _, scl = (pb.bone.matrix_local.inverted() @ pb.matrix).decompose()
            q_arm = (pb.matrix.to_3x3().normalized() @ pb.bone.matrix_local.to_3x3().inverted()).to_quaternion()
            return q_arm.normalized(), scl
        # rest pose of the file = the rig's rest pose (json bone heads, UE cm -> Blender m)
        edit_heads = {b.name: (arm.matrix_world @ b.head_local).copy() for b in arm.data.bones}
        worst = 0.0
        for b, ue in json_heads_ue.items():
            ref = Vector((ue[0], -ue[1], ue[2])) * 0.01
            worst = max(worst, (edit_heads[b] - ref).length)
        res["rest_heads_max_err_cm"] = round(worst * 100, 4)
        assert worst < 1e-4, "clip %s rest heads differ from the rig by %.4f cm" % (clip, worst * 100)
        # node default transforms (reference pose) identical to the mesh file's (= rest)
        dflt = fbx_model_defaults(paths[clip], set(expect_bones))
        dworst = 0.0
        for b in moving:
            for k in ("Lcl Translation", "Lcl Rotation"):
                a = ref_defaults[b].get(k, [0, 0, 0])
                c = dflt[b].get(k, [0, 0, 0])
                dworst = max(dworst, max(abs(x - y) for x, y in zip(a, c)))
        res["node_default_max_diff_vs_mesh_fbx"] = dworst
        assert dworst < 1e-3, "clip %s node default transforms differ from rest by %g" % (clip, dworst)
        for bone, frame, kind, expect in tests:
            scn.frame_set(frame)
            bpy.context.view_layer.update()
            pb = arm.pose.bones[bone]
            if kind == "d":
                d = (bone_world_head(arm, bone) - edit_heads[bone]) * 100.0
                ok = all(e is None or abs(d[i] - e) <= 0.05 for i, e in enumerate(expect))
                rec = {"bone": bone, "frame": frame, "delta_cm": [round(v, 3) for v in d], "expect_cm": list(expect), "ok": ok}
            elif kind == "scale":
                rest_m = arm.matrix_world @ pb.bone.matrix_local
                pose_m = arm.matrix_world @ pb.matrix
                s = (rest_m.inverted() @ pose_m).to_scale()
                ok = max(abs(v - expect) for v in s) <= (0.0005 if expect < 0.5 else 0.01)
                rec = {"bone": bone, "frame": frame, "scale": [round(v, 5) for v in s], "expect_scale": expect, "ok": ok}
            elif kind == "hand_grip":
                # v3: the hand target sits on grip_l (absolute heads, world cm)
                dist = (bone_world_head(arm, bone) - bone_world_head(arm, "grip_l")).length * 100.0
                ok = dist <= expect
                rec = {"bone": bone, "frame": frame, "dist_to_grip_l_cm": round(dist, 4), "tol_cm": expect, "ok": ok}
            elif kind == "hand_mag":
                # v3: the hand target cups the magazine: within `expect` cm of magazine head + cup offset
                target = bone_world_head(arm, "magazine") + arm.matrix_world.to_3x3() @ cup_bl
                dist = (bone_world_head(arm, bone) - target).length * 100.0
                ok = dist <= expect
                rec = {"bone": bone, "frame": frame, "dist_to_mag_plus_cup_cm": round(dist, 4), "tol_cm": expect, "ok": ok}
            elif kind == "p":
                # absolute position (armature/world cm, Blender frame)
                p = bone_world_head(arm, bone) * 100.0
                ok = all(abs(p[i] - e) <= 0.05 for i, e in enumerate(expect))
                rec = {"bone": bone, "frame": frame, "pos_cm": [round(v, 3) for v in p], "expect_cm": list(expect), "ok": ok}
            elif kind in ("hand_rot_id", "hand_curl", "hand_beat"):
                # v4: orientation delta (reported as UE gun-space axis-angle) and curl (local scale X)
                q_arm, scl = hand_delta(pb)
                axis, deg = axis_angle_ue(q_arm)
                if kind == "hand_rot_id":
                    ok = deg <= expect
                    rec = {"bone": bone, "frame": frame, "rot_ue_deg": deg, "rot_ue_axis": axis, "tol_deg": expect, "ok": ok}
                elif kind == "hand_curl":
                    ok = abs(scl.x - expect) <= 0.02 and abs(scl.y - 1.0) <= 0.02 and abs(scl.z - 1.0) <= 0.02
                    rec = {"bone": bone, "frame": frame, "curl": round(scl.x, 4), "scale": [round(v, 4) for v in scl],
                           "expect_curl": expect, "ok": ok}
                else:
                    D_ue, curl = hand_beat_delta_ue(expect)
                    diff = _qdiff(quat_bl_to_ue(q_arm), D_ue.to_quaternion())
                    ok = diff <= 1.0 and abs(scl.x - curl) <= 0.02
                    rec = {"bone": bone, "frame": frame, "beat": expect, "rot_ue_axis": axis, "rot_ue_deg": deg,
                           "diff_vs_design_deg": round(diff, 4), "curl": round(scl.x, 4), "expect_curl": curl, "ok": ok}
                    res.setdefault("hand_beats", []).append(rec)
                    log("  hand beat", clip, "f%03d" % frame, expect, "UE axis", axis, "deg", deg,
                        "curl", round(scl.x, 3), "diff vs design deg", round(diff, 4))
            else:
                rest_m = arm.matrix_world @ pb.bone.matrix_local
                pose_m = arm.matrix_world @ pb.matrix
                angle = math.degrees((rest_m.inverted() @ pose_m).to_quaternion().angle)
                ok = abs(angle - expect) <= 0.1
                rec = {"bone": bone, "frame": frame, "rot_deg": round(angle, 3), "expect_deg": expect, "ok": ok}
            res["tests"].append(rec)
            if not ok:
                log("FAIL", clip, rec)
            assert ok, "clip %s: %s" % (clip, rec)
        # per-frame traces for the reviewer's points
        trace = {}
        hand_q = []
        for f in range(0, last + 1):
            scn.frame_set(f)
            bpy.context.view_layer.update()
            trace.setdefault("bolt_carrier_x_cm", []).append(round((bone_world_head(arm, "bolt_carrier") - edit_heads["bolt_carrier"]).x * 100, 3))
            trace.setdefault("magazine_z_cm", []).append(round((bone_world_head(arm, "magazine") - edit_heads["magazine"]).z * 100, 2))
            qh, sh = hand_delta(arm.pose.bones[HAND_TARGET])
            hand_q.append(qh)
            trace.setdefault("hand_rot_ue_deg", []).append(axis_angle_ue(qh)[1])
            trace.setdefault("hand_curl", []).append(round(sh.x, 4))
            if clip in ("Reload", "ReloadTactical"):
                pbm = arm.pose.bones["magazine"]
                trace.setdefault("magazine_scale", []).append(round((pbm.bone.matrix_local.inverted() @ pbm.matrix).to_scale().x, 4))
                hp = bone_world_head(arm, HAND_TARGET) * 100.0
                trace.setdefault("hand_l_target_ue_cm", []).append([round(hp.x, 2), round(-hp.y, 2), round(hp.z, 2)])
                mt = (bone_world_head(arm, "magazine") + arm.matrix_world.to_3x3() @ cup_bl) * 100.0
                trace.setdefault("hand_minus_magcup_cm", []).append(round((hp - mt).length, 3))
        if clip in ("Reload", "ReloadTactical"):
            z = trace["magazine_z_cm"]
            parked_f, hidden_f = DERIVED["mag_parked_frame"], DERIVED["mag_hidden_from_frame"]
            assert all(z[i + 1] <= z[i] + 1e-6 for i in range(12, parked_f)), "old mag does not fall monotonically"
            assert all(v <= MAG_PARK_CM + 0.01 for v in z[parked_f:F_BELT]), "mag visible during the hidden hold"
            sc = trace["magazine_scale"]
            assert all(s <= MAG_HIDDEN_SCALE + 0.0005 for s in sc[hidden_f:F_BELT]), "mag not hidden (scale) during the hold"
            assert all(abs(s - 1.0) <= 0.01 for s in sc[:hidden_f - 1] + sc[F_BELT:]), "mag scale not 1.0 while visible"
            assert all(abs(v - z[F_BELT]) <= 0.01 for v in z[F_BELT:F_CARRY + 1]), "popped-in mag does not hold at the belt"
            assert max(z[F_CARRY:103]) <= 0.0 + 1e-6 and all(z[i + 1] >= z[i] - 1e-6 for i in range(F_CARRY, 102)), "new mag arc not monotonic up"
            # the hand target never rises above the receiver while it is beside the gun (no penetration
            # of the body: it is only ever on the drum's left face, at the belt, or on the bolt catch)
            hz = [p[2] for p in trace["hand_l_target_ue_cm"]]
            hy = [p[1] for p in trace["hand_l_target_ue_cm"]]
            assert min(hy) < -2.0 and max(hy) <= -1.0, "hand target crossed to the gun's right side (UE +Y) %s" % max(hy)
            assert all(hz[f] < -1.0 for f in range(F_GRAB, F_SEAT + 1)), "hand target above the mag well during the swap"
            assert all(d <= 2.0 for d in trace["hand_minus_magcup_cm"][F_CARRY:F_SEAT + 1]), "hand does not carry the fresh mag"
            assert all(d <= 2.0 for d in trace["hand_minus_magcup_cm"][F_GRAB:F_RELEASE + 1]), "hand does not pull the old mag"
        if clip == "ReloadTactical":
            assert max(abs(v) for v in trace["bolt_carrier_x_cm"]) < 1e-3
        # v4: hand orientation / curl invariants on every clip: curl inside its range on every frame, finite,
        # no consecutive frame (and no consecutive 6th-frame sample) turns the hand further than the shortest-
        # path limit, and clips that never key the hand stay at identity / 1.0 throughout
        hc = trace["hand_curl"]
        hr = trace["hand_rot_ue_deg"]
        assert all(math.isfinite(v) for v in hc + hr), "clip %s: non-finite hand curl / rotation" % clip
        assert all(HAND_CURL_RANGE[0] - 1e-6 <= v <= HAND_CURL_RANGE[1] + 1e-6 for v in hc), "clip %s: curl out of %s: %s" % (
            clip, HAND_CURL_RANGE, (min(hc), max(hc)))
        steps = [_qdiff(hand_q[i], hand_q[i + 1]) for i in range(len(hand_q) - 1)]
        samp = list(range(0, last + 1, 6))
        steps6 = [_qdiff(hand_q[a], hand_q[b]) for a, b in zip(samp, samp[1:])]
        res["hand_rot_ue_deg_max"] = round(max(hr), 3)
        res["hand_curl_range"] = [round(min(hc), 4), round(max(hc), 4)]
        res["hand_max_step_deg_per_frame"] = round(max(steps), 3) if steps else 0.0
        res["hand_max_step_deg_per_6_frames"] = round(max(steps6), 3) if steps6 else 0.0
        assert res["hand_max_step_deg_per_frame"] < HAND_MAX_STEP_DEG and res["hand_max_step_deg_per_6_frames"] < HAND_MAX_STEP_DEG, \
            "clip %s: hand turns the long way round (%s / %s deg)" % (clip, res["hand_max_step_deg_per_frame"], res["hand_max_step_deg_per_6_frames"])
        if clip not in ("Reload", "ReloadTactical"):
            assert max(hr) < 2.0 and all(abs(v - 1.0) <= 0.02 for v in hc), "clip %s moves the hand orientation / curl" % clip
        log("clip", clip, "hand rot max deg", res["hand_rot_ue_deg_max"], "curl range", res["hand_curl_range"],
            "max step deg /frame", res["hand_max_step_deg_per_frame"], "/6 frames", res["hand_max_step_deg_per_6_frames"])
        # direction checks: trigger bottom moves back, bolt catch top moves out (+Y, gun-left),
        # mag release moves toward the gun's left (+Y)
        def point_motion(bone, f0, f1, offset):
            scn.frame_set(f0)
            bpy.context.view_layer.update()
            m0 = (arm.matrix_world @ arm.pose.bones[bone].matrix).copy()
            scn.frame_set(f1)
            bpy.context.view_layer.update()
            m1 = (arm.matrix_world @ arm.pose.bones[bone].matrix).copy()
            loc = m0.inverted() @ (m0.translation + Vector(offset))
            return (m1 @ loc) - (m0 @ loc)
        if clip in ("Fire", "DryFire"):
            fpull = 0 if clip == "Fire" else 1
            mv = point_motion("trigger", last, fpull, (0, 0, -0.03))
            res["trigger_bottom_dx_cm"] = round(mv.x * 100, 3)
            assert mv.x < -0.002, "trigger did not pull back"
        if clip in ("IdleEmpty", "Reload"):
            mv = point_motion("bolt_catch", 144 if clip == "Reload" else 0, 0, (0, 0, 0.015))
            if clip == "IdleEmpty":
                # IdleEmpty never shows rest: compare against the edit pose instead
                pb = arm.pose.bones["bolt_catch"]
                scn.frame_set(0)
                bpy.context.view_layer.update()
                m0 = arm.matrix_world @ pb.bone.matrix_local
                m1 = arm.matrix_world @ pb.matrix
                loc = m0.inverted() @ (m0.translation + Vector((0, 0, 0.015)))
                mv = (m1 @ loc) - (m0 @ loc)
            res["bolt_catch_top_dy_cm"] = round(mv.y * 100, 3)
            assert mv.y > 0.001, "bolt catch top does not swing out"
        if clip in ("Reload", "ReloadTactical"):
            mv = point_motion("mag_release", 0, 6, (0, -0.015, 0))
            res["mag_release_dy_cm"] = round(mv.y * 100, 3)
            assert mv.y > 0.003
        res["trace"] = trace
        report[clip] = res
    return report


# ============================================================================
# main
# ============================================================================
BLEND_PATH = os.path.join(OUT_DIR, "M4A1_rig.blend")
JSON_PATH = os.path.join(OUT_DIR, "m4a1_rig.json")
CLIP_ORDER = ["Idle", "IdleEmpty", "Fire", "FireLast", "DryFire", "Reload", "ReloadTactical", "Chamber"]
NEW_IN_V2 = ["IdleEmpty", "FireLast", "ReloadTactical"]


def ue_cm(v):
    """Blender metres (right side on -Y) -> Unreal cm (X fwd, Y right, Z up)."""
    return [round(v.x * 100, 3), round(-v.y * 100, 3), round(v.z * 100, 3)]


def clear_save_handlers():
    """Third-party add-on save handlers (e.g. the comfyui add-on) crash headless saves."""
    removed = []
    for lst_name in ("save_pre", "save_post", "save_post_fail"):
        lst = getattr(bpy.app.handlers, lst_name, None)
        if lst is None:
            continue
        for h in list(lst):
            removed.append((lst_name, h))
            lst.remove(h)
    log("cleared save handlers", ["%s:%s.%s" % (n, getattr(h, "__module__", "?"), getattr(h, "__name__", "?"))
                                  for n, h in removed])
    return removed


def restore_save_handlers(removed):
    """Put them back after the save so the add-ons unregister cleanly at exit."""
    for lst_name, h in removed:
        lst = getattr(bpy.app.handlers, lst_name)
        if h not in lst:
            lst.append(h)


def load_rig_blend():
    """--clips-only: the approved rig (armature + skinned mesh) from M4A1_rig.blend; the old
    A_M4A1_* actions are removed so the v2 actions keep their exact names."""
    bpy.ops.wm.open_mainfile(filepath=BLEND_PATH, load_ui=False)
    for s in bpy.data.scenes:
        s.render.fps = FPS
        s.render.fps_base = 1.0
    arm = bpy.data.objects[ARMATURE_OBJECT_NAME]
    sk = bpy.data.objects["SK_M4A1"]
    names = [b.name for b in arm.data.bones]
    pre_v3 = [b for b in BONE_ORDER if b not in TARGET_BONES]
    assert sorted(names) in (sorted(BONE_ORDER), sorted(pre_v3)), "rig bones changed: %s" % names
    added = []
    if HAND_TARGET not in names:
        # v3 on a v2 .blend: add the non-deforming hand target (rest at grip_l, identity orientation,
        # child of body) so SK_M4A1.fbx must be re-exported in this run
        select_only([arm], arm)
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        b = eb.new(HAND_TARGET)
        b.head = eb["grip_l"].head.copy()
        b.tail = b.head + Vector((0, 0.03, 0))
        b.roll = 0.0
        b.use_deform = False
        b.parent = eb["body"]
        b.use_connect = False
        bpy.ops.object.mode_set(mode='OBJECT')
        added.append(HAND_TARGET)
        log("added bone", HAND_TARGET, "at grip_l head; the mesh FBX will be re-exported")
    if arm.animation_data:
        arm.animation_data.action = None
    old = [a.name for a in bpy.data.actions]
    for a in list(bpy.data.actions):
        if a.name.startswith("A_M4A1_"):
            bpy.data.actions.remove(a)
    log("loaded", BLEND_PATH, "removed old actions", old)
    heads = {b.name: b.head_local.copy() for b in arm.data.bones}
    return arm, sk, heads, added


def clip_design_v2():
    """Names, lengths and authored key values for m4a1_rig.json 'clips_v2' (UE cm / deg;
    bolt_carrier / charging_handle X < 0 = rearward; magazine Y in UE is the gun's right)."""
    HO = -HOLD_OPEN_CM
    S = -STROKE_CM
    sx, sy, sz = DERIVED["mag_new_start_bl_cm"]
    parked_f, hidden_f = DERIVED["mag_parked_frame"], DERIVED["mag_hidden_from_frame"]
    mag = {"release_press_s": [0.0, 0.1], "release_held_until_s": 0.2, "release_back_s": 0.267,
           "v3_note": "the left hand pulls the mag down the first 12 cm (f12-f27); the drop starts from the release point",
           "pull_s": [round(F_GRAB / FPS, 4), round(F_RELEASE / FPS, 4)], "pull_cm": HAND_PULL_CM, "pull_interp": "QUAD ease-in",
           "release_velocity_mps": DERIVED["mag_release_velocity_mps"],
           "drop_start_s": round(F_RELEASE / FPS, 4),
           "drop_model": "z = -(%.2f + v0 (t - %.3f) + 0.5 * %.1f m/s^2 * (t - %.3f)^2), per-frame keys" % (
               HAND_PULL_CM / 100, F_RELEASE / FPS, MAG_GRAVITY, F_RELEASE / FPS),
           "z_cm_at_0.45s": -HAND_PULL_CM, "z_cm_parked": MAG_PARK_CM, "parked_from_s": round(parked_f / FPS, 4),
           "hidden_scale": MAG_HIDDEN_SCALE, "hidden_below_well_cm": MAG_HIDE_BELOW_CM,
           "hidden_hold_s": [round(hidden_f / FPS, 4), round((F_BELT - 1) / FPS, 4)],
           "hidden_hold_frames": [hidden_f, F_BELT - 1],
           "drop_tilt_deg_max": 16.0, "drop_forward_drift_cm": 1.5,
           "pop_in_s": round(F_BELT / FPS, 4), "pop_in_frame": F_BELT,
           "pop_in_note": "scale 0.001 -> 1.0 and position = hand belt target - cup offset on the same frame",
           "new_mag_start_s": round(F_BELT / FPS, 4), "new_mag_start_ue_cm": [sx, -sy, sz], "new_mag_start_tilt_deg": 10.0,
           "held_in_hand_until_s": round(F_CARRY / FPS, 4),
           "new_mag_arc_ue_cm": {"1.333s": [5.0, -2.0, -18.0], "1.533s": [1.2, -0.5, -4.5], "1.617s": [0.0, 0.0, -2.2]},
           "seated_s": 1.7, "overshoot_ue_cm": {"1.717s": 0.35, "1.733s": 0.1, "1.75s": 0.0}}
    cup = DERIVED["cup_offset_bl_cm"]
    hand_common = {
        "bone": HAND_TARGET, "meaning": "left PALM CENTRE target for the body's hand_l two-bone IK (gun space)",
        "rest": "grip_l head; identical to grip_l at frame 0 and the last frame",
        "cup_offset_ue_cm": [cup[0], -cup[1], cup[2]],
        "cup_rule": "magazine head + (0, left face + %.1f cm clearance, -%.1f cm)" % (HAND_CUP_CLEAR_CM, HAND_CUP_DOWN_CM),
        "belt_ue_cm": list(HAND_BELT_UE_CM),
        "bolt_catch_palm_ue_cm": ue_cm(Vector(DERIVED["bolt_catch_hand_bl_cm"]) * 0.01),
    }
    return {
        "Idle": {"frames": 2, "seconds": 0.0167, "loop": True, "keys": "rest; bolt home, mag seated"},
        "IdleEmpty": {"frames": 2, "seconds": 0.0167, "loop": True,
                      "keys": {"bolt_carrier_x_cm": HO, "bolt_catch_deg": abs(BOLT_CATCH_ENGAGED_DEG), "magazine": "seated"}},
        "Fire": {"frames": 8, "seconds": round(7 / FPS, 4), "loop": False,
                 "keys": {"bolt_carrier_x_cm": {"f0": 0.0, "f1": S / 2, "f2": S, "f6": -0.3, "f7": 0.0},
                          "bolt_carrier_interp": "f0-2 linear back, f2-6 QUAD ease-in forward, f6-7 settle",
                          "trigger_deg": {"f0-f6": TRIGGER_PULL_DEG, "f7": 0.0}, "charging_handle": "home"}},
        "FireLast": {"frames": 8, "seconds": round(7 / FPS, 4), "loop": False,
                     "keys": {"bolt_carrier_x_cm": {"f0": 0.0, "f2": S, "f4": HO, "f5": HO - 0.15, "f6": HO, "f7": HO},
                              "bolt_catch_deg": {"f0-f1": 0.0, "f3-f7": abs(BOLT_CATCH_ENGAGED_DEG)},
                              "trigger_deg": {"f0-f6": TRIGGER_PULL_DEG, "f7": 0.0}, "last_frame": "= IdleEmpty pose"}},
        "DryFire": {"frames": 10, "seconds": 0.15, "loop": False,
                    "keys": {"trigger_deg": {"f0": 0.0, "f1-f4": 8.0, "f7-f9": 0.0}}, "note": "unchanged from v1"},
        "Reload": {"frames": 145, "seconds": 2.4, "loop": False, "type": "EMPTY reload (bolt locked back at start)",
                   "keys": {"start_pose": "IdleEmpty", "mag_release_in_cm": MAG_RELEASE_PRESS_CM, "magazine": mag,
                            "bolt_catch_deg": {"f0-f111": abs(BOLT_CATCH_ENGAGED_DEG), "f115-f144": 0.0},
                            "bolt_catch_press_s": [1.85, 1.9167],
                            "bolt_carrier_x_cm": {"f0-f115": HO, "f116": HO / 2, "f117": 0.0, "f118": -0.4, "f119-f144": 0.0},
                            "slam_ms": 33.3, "rest_from_s": 2.4,
                            "hand_l_target": dict(hand_common, keys=DERIVED["hand_keys"]["Reload"],
                                                  rotation_keys=DERIVED["hand_rot_keys"]["Reload"],
                                                  curl_keys=DERIVED["hand_curl_keys"]["Reload"],
                                                  bolt_catch_beat_frames=[104, 118])}},
        "ReloadTactical": {"frames": 145, "seconds": 2.4, "loop": False, "type": "tactical (round chambered)",
                           "keys": {"bolt_carrier_x_cm": "0 every frame", "bolt_catch_deg": "0 every frame",
                                    "mag_release_in_cm": MAG_RELEASE_PRESS_CM, "magazine": mag, "rest_from_s": 2.1667,
                                    "hand_l_target": dict(hand_common, keys=DERIVED["hand_keys"]["ReloadTactical"],
                                                          rotation_keys=DERIVED["hand_rot_keys"]["ReloadTactical"],
                                                          curl_keys=DERIVED["hand_curl_keys"]["ReloadTactical"])}},
        "Chamber": {"frames": 67, "seconds": 1.1, "loop": False,
                    "keys": {"charging_handle_and_bolt_carrier_x_cm": {"f0-f8": 0.0, "f29": S, "f35": S, "f36": S / 2,
                                                                       "f37": 0.0, "f38": -0.5, "f39-f66": 0.0},
                             "pull_s": [0.1333, 0.4833], "pull_interp": "QUAD ease-in (0.35 s)", "hold_s": 0.1,
                             "slam_ms": 33.3}},
    }


def anim_events_v2():
    """Suggested notify times (seconds) for the C++ side."""
    return {
        "Fire": {"carrier_full_rear": 0.0333, "carrier_home": 0.1167},
        "FireLast": {"carrier_full_rear": 0.0333, "bolt_locked_open": 0.0667},
        "Reload": {"mag_release": 0.0, "hand_on_mag": round(F_GRAB / FPS, 4), "mag_pull": round(F_GRAB / FPS, 4),
                   "mag_drop": round(F_RELEASE / FPS, 4), "spawn_dropped_mag_prop": round(F_RELEASE / FPS, 4),
                   "old_mag_hidden": round(DERIVED["mag_hidden_from_frame"] / FPS, 4),
                   "hand_at_belt": round(F_BELT / FPS, 4), "new_mag_in_hand": round(F_BELT / FPS, 4),
                   "mag_lift_start": round(F_CARRY / FPS, 4), "mag_seated_refill_ammo": 1.7,
                   "hand_on_bolt_catch": round(110 / FPS, 4), "bolt_release": 1.9167,
                   "bolt_home": 1.95, "can_fire": 2.0, "hand_back_on_grip": 2.4},
        "ReloadTactical": {"mag_release": 0.0, "hand_on_mag": round(F_GRAB / FPS, 4), "mag_pull": round(F_GRAB / FPS, 4),
                           "mag_drop": round(F_RELEASE / FPS, 4), "spawn_dropped_mag_prop": round(F_RELEASE / FPS, 4),
                           "old_mag_hidden": round(DERIVED["mag_hidden_from_frame"] / FPS, 4),
                           "hand_at_belt": round(F_BELT / FPS, 4), "new_mag_in_hand": round(F_BELT / FPS, 4),
                           "mag_lift_start": round(F_CARRY / FPS, 4), "mag_seated_refill_ammo": 1.7, "can_fire": 1.75,
                           "hand_back_on_grip": round(130 / FPS, 4)},
        "Chamber": {"pull_start": 0.1333, "full_rear": 0.4833, "release": 0.5833, "bolt_home": 0.6167},
    }


def write_json(clip_frames, paths, report, proofs2, full_data=None, rig_update=None):
    old = {}
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH) as f:
            old = json.load(f)
    data = dict(old)
    if full_data:
        data.update(full_data)
    if rig_update:
        data.update(rig_update)   # v3: bone list / heads now include hand_l_target (also in --clips-only)
    if "clips_v1_superseded" not in data and "clips" in old:
        data["clips_v1_superseded"] = {
            "note": "v1 clip set (bolt 7.5 cm, no hold-open, floating mag). The A_M4A1_*.fbx files now hold v2; "
                    "the v1 proof PNGs (proof_*.png, 'proofs') are kept for comparison.",
            "clips": old.get("clips"),
            "verification": {k: v for k, v in old.get("verification", {}).items() if k != "mesh"}}
    data["clips"] = {k: {"fbx": paths[k], "frames": clip_frames[k] + 1, "fps": FPS,
                         "seconds": round(clip_frames[k] / FPS, 4)} for k in CLIP_ORDER}
    data["verification"] = report
    design = clip_design_v2()
    for k in CLIP_ORDER:
        design[k]["asset"] = "A_M4A1_" + k
        design[k]["fbx"] = paths[k]
        design[k]["reimport"] = {kk: report[k][kk] for kk in ("frame_range", "keys_per_curve", "length_s",
                                                             "rest_heads_max_err_cm", "node_default_max_diff_vs_mesh_fbx")}
        design[k]["reimport"]["tests_passed"] = sum(1 for t in report[k]["tests"] if t["ok"])
        design[k]["proofs"] = [e["png"] for e in proofs2.get(k, [])]
        if k in proofs2.get("strips", {}):
            design[k]["strip"] = proofs2["strips"][k]
    cup = DERIVED["cup_offset_bl_cm"]
    data["clips_v2"] = {
        "version": "v3 2026-10-30 (v2 mechanics + left-hand target + magazine hide/pop-in)",
        "v3_hand_target": {
            "bone": HAND_TARGET, "parent": "body", "deform": False,
            "rest_ue_cm": rig_update["bone_heads_cm"][HAND_TARGET] if rig_update else None,
            "equals_grip_l_at": "frame 0 and the last frame of every clip (only Reload / ReloadTactical move it)",
            "cup_offset_ue_cm": [cup[0], -cup[1], cup[2]],
            "mag_left_face_y_ue_cm": -DERIVED["mag_left_face_y_bl_cm"],
            "belt_ue_cm": list(HAND_BELT_UE_CM),
            "bolt_catch_palm_ue_cm": ue_cm(Vector(DERIVED["bolt_catch_hand_bl_cm"]) * 0.01),
            "pull_cm": HAND_PULL_CM, "frames": {"grab": F_GRAB, "release": F_RELEASE, "belt": F_BELT, "carry": F_CARRY, "seat": F_SEAT,
                                                "bolt_catch_beat": [104, 118], "rest": 144},
            "keys": DERIVED["hand_keys"],
            "magazine_keys_bl_cm": DERIVED["mag_keys"],
            "magazine_hidden_frames": [DERIVED["mag_hidden_from_frame"], F_BELT - 1],
            "magazine_parked_frame": DERIVED["mag_parked_frame"],
            "magazine_hidden_scale": MAG_HIDDEN_SCALE,
            "exporter": "bake_anim_use_all_bones=True, use_armature_deform_only=False: the non-deforming target "
                        "and the magazine scale track are baked into every clip FBX",
            "hand_proofs": proofs2.get("hand", {}),
            "hand_strips": proofs2.get("hand_strips", {}),
        },
        "fps": FPS,
        "stroke_cm": STROKE_CM,
        "hold_open_cm": HOLD_OPEN_CM,
        "trigger_pull_deg": TRIGGER_PULL_DEG,
        "mag_release_press_cm": MAG_RELEASE_PRESS_CM,
        "bolt_catch": {"engaged_deg": abs(BOLT_CATCH_ENGAGED_DEG), "axis": "fore-aft (bone X)",
                       "sense": "top of the left-side paddle swings out (away from the receiver)",
                       "pivot_note": "rotation about the paddle's lower inboard edge, expressed as bone rotation + translation"},
        "units": "UE component space cm (X forward, Y right, Z up) unless noted; the script keys in Blender space "
                 "where +Y is the gun's LEFT, so the new mag start (+8, +3, -40) Blender = (+8, -3, -40) UE "
                 "(support-hand side)",
        "easing_rule": "1-2 frame moves LINEAR (slams, recoil stroke); easing only on 3+ frame moves",
        "export_note": "IdleEmpty and FireLast do not end on rest; they are exported from a temporary rest "
                       "pre-roll key (frame -5, outside the baked 0..N range) so the FBX node defaults stay the "
                       "rest pose; verified against SK_M4A1.fbx node defaults on re-import",
        "clip_order": CLIP_ORDER,
        "new_in_v2": NEW_IN_V2,
        "import_script_must_add": ["A_M4A1_" + k for k in NEW_IN_V2],
        "clips": design,
        "anim_events_s": anim_events_v2(),
        "ue_note": "'ue_verification' predates v2 (v1 clips). Re-import with the clip list extended by "
                   "IdleEmpty, FireLast, ReloadTactical and the v2 expectations (Fire f2 = -9.0, Reload f0 = -8.2, "
                   "Reload mag f27 z = -30, f48 z = -70, mag Y sign flips in UE).",
        "strips": proofs2.get("strips", {}),
    }
    data["proofs_v2"] = proofs2
    # v4: the hand orientation / curl contract for the C++ side and the reviewer (top-level, per the design)
    data["hand_l_target"] = {
        "version": "v4 2026-10-30",
        "convention": "hand_l_target ROTATION in every clip is a DELTA from its rest (identity) meaning 'turn the left "
                      "hand by this much from how the stance aim pose holds it at the support grip'; component-space "
                      "delta D = WeaponRotation * SocketRotation(gun space) * WeaponRotation^-1. SCALE X (bone-local) is the "
                      "finger curl: 1.0 = the aim pose's fingers, 0.0 = open reference hand, 1.6 = tightest. Identity / 1.0 at "
                      "frame 0 and the last frame of every clip.",
        "rest_hand_frame_ue": {"finger_dir": list(HAND_REST_FINGER_UE), "palm_normal": list(HAND_REST_PALM_UE),
                               "stance": "Rifle", "source": "Scripts/MeasureHandAxes.py -> D:/AFS_Comparisons/GunRigs_20261029/hand_axes.json",
                               "axes": "hand_l local +X = fingers, -Y = palm normal, -Z = thumb side"},
        "beats_ue": DERIVED.get("hand_beats_ue"),
        "frame_conversion": {"rule": "UE gun space (X fwd, Y right, Z up) <-> Blender armature space (X fwd, Y LEFT, Z up): "
                                     "vectors v' = (x, -y, z); rotations R' = M R M with M = diag(1,-1,1); a rotation of +a about "
                                     "UE X / Y / Z is -a / +a / -a about Blender X / Y / Z; quaternion (w,x,y,z) -> (w,-x,y,-z)",
                             "verified_worst_error": DERIVED.get("frame_conversion_worst_err")},
        "rotation_keys": DERIVED.get("hand_rot_keys"),
        "curl_keys": DERIVED.get("hand_curl_keys"),
        "curl_range": list(HAND_CURL_RANGE), "max_step_deg": HAND_MAX_STEP_DEG,
        "reimport": {k: {"beats": report[k].get("hand_beats", []),
                         "rot_ue_deg_max": report[k].get("hand_rot_ue_deg_max"), "curl_range": report[k].get("hand_curl_range"),
                         "max_step_deg_per_frame": report[k].get("hand_max_step_deg_per_frame"),
                         "max_step_deg_per_6_frames": report[k].get("hand_max_step_deg_per_6_frames"),
                         "rest_orientation_deg": report[k].get("hand_rest_orientation_deg")} for k in CLIP_ORDER},
        "proof_palm_proxy": "proof2_<clip>_fNNN_hand.png: %gx%g cm plate (yellow = palm face, dark green = back), %g cm red finger "
                            "arrow, blue thumb-side cube; panel R is an x-ray from the gun's right" % (HAND_PROXY_CM[0], HAND_PROXY_CM[1], HAND_PROXY_ARROW_CM),
    }
    data["clips_v2"]["version"] = "v4 2026-10-30 (v3 + hand_l_target rotation delta / curl scale X; see hand_l_target)"
    notes = list(data.get("notes", []))
    n2 = ("v2 clips (2026-10-29): Idle, IdleEmpty, Fire, FireLast, DryFire, Reload (empty), ReloadTactical, Chamber; "
          "see clips_v2. Skeleton and SK_M4A1.fbx unchanged.")
    if n2 not in notes:
        notes.append(n2)
    n3 = ("v3 (2026-10-30): skeleton gains the non-deforming 'hand_l_target' (child of body, rest = grip_l); "
          "SK_M4A1.fbx and all clip FBX re-exported; Reload/ReloadTactical carry the left-hand palm target and "
          "the magazine hide (scale 0.001) / pop-in at the belt; see clips_v2.v3_hand_target. UE must re-import SK_M4A1 + clips.")
    if n3 not in notes:
        notes.append(n3)
    n4 = ("v4 (2026-10-30 evening): hand_l_target also carries a ROTATION (delta from rest) and SCALE X (finger curl) "
          "track in Reload / ReloadTactical, identity / 1.0 elsewhere and at f0 / end; positions unchanged. See 'hand_l_target'. "
          "UE must re-import the clips; the C++ support-hand node reads the socket rotation and bone-local scale X.")
    if n4 not in notes:
        notes.append(n4)
    data["notes"] = notes
    data["log_v2"] = LOG
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=1)
    with open(os.path.join(RECEIPT_DIR, "rig_m4a1_v2_receipt.json"), "w") as f:
        json.dump(data, f, indent=1)
    log("wrote", JSON_PATH)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    clips_only = "--clips-only" in argv
    full_data = None
    added_bones = []
    if clips_only:
        arm, sk, heads, added_bones = load_rig_blend()
        with open(JSON_PATH) as f:
            jheads = json.load(f)["bone_heads_cm"]
        worst = max(max(abs(a - b) for a, b in zip(ue_cm(heads[k]), jheads[k])) for k in jheads if k in heads)
        assert worst < 0.01, "rig in the .blend differs from m4a1_rig.json by %.4f cm" % worst
        log("rig .blend matches m4a1_rig.json bone heads (max diff cm)", worst)
    else:
        meshes, part_of, scale, bounds = stage_import()
        arm, sk, heads, bone_of = stage_rig(meshes, part_of, bounds)
    assert HAND_TARGET in heads and (heads[HAND_TARGET] - heads["grip_l"]).length < 1e-6, "hand target rest != grip_l"
    clips = author_clips(arm, heads)
    clips = {k: clips[k] for k in CLIP_ORDER}
    # keep an editable .blend for humans (rig + v2 actions; proof objects are added after this)
    arm.animation_data.action = None
    removed_handlers = clear_save_handlers()
    try:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    finally:
        restore_save_handlers(removed_handlers)
    log("saved", BLEND_PATH)
    paths = export_all(arm, sk, clips, export_mesh=(not clips_only) or bool(added_bones))
    proofs2 = render_proofs_v2(arm, sk, clips)
    json_heads = {b: ue_cm(heads[b]) for b in heads}
    rig_update = {"bones": [b for b in BONE_ORDER if b in heads], "bone_heads_cm": json_heads,
                  "sockets_cm": {b: json_heads[b] for b in SOCKET_BONES},
                  "target_bones_cm": {b: json_heads[b] for b in TARGET_BONES if b in heads}}
    if not clips_only:
        part_part = {}
        for mesh_name, b in bone_of.items():
            part_part.setdefault(b, []).append(mesh_name)
        full_data = {
            "scale_factor": round(scale, 6),
            "axes": "Unreal: X forward (muzzle), Y right, Z up; origin at pistol-grip top centre (grip_r)",
            "bones": [b for b in BONE_ORDER if b in heads],
            "bone_heads_cm": json_heads,
            "sockets_cm": {b: json_heads[b] for b in SOCKET_BONES},
            "armature_object_name": ARMATURE_OBJECT_NAME,
            "material_slots": SLOT_ORDER,
            "part_to_slot": {p: PART_TO_SLOT[p] for p in sorted(PART_TO_SLOT)},
            "bone_to_kit_meshes": part_part,
            "fbx_mesh": paths["mesh"],
            "log": LOG,
        }
    expect_bones = [b for b in BONE_ORDER if b in heads]
    clip_frames = {k: int(clips[k].frame_range[1]) for k in clips}   # actions die with read_homefile below
    report = verify_reimport_v2(paths, heads, expect_bones, json_heads)
    if full_data:
        full_data["length_cm"] = report["mesh"]["length_cm"]
    write_json(clip_frames, paths, report, proofs2, full_data, rig_update)
    log("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        with open(os.path.join(RECEIPT_DIR, "rig_m4a1_error.txt"), "w") as f:
            f.write(traceback.format_exc() + "\n\n" + "\n".join(LOG))
        sys.exit(1)
