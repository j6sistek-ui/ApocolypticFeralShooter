"""ReexportEM11ForUE.py - re-export the EM_11 rig from EM11_rig.blend in the UE-safe M4A1 convention.

Why: RigEM_11.py (as of 2026-10-29 22:10) wrote SK_EM11.fbx / A_EM11_*.fbx with the armature OBJECT named
'EM_11_Skeleton' (UE inserts an extra x100-scaled root bone unless the top Null is named exactly 'Armature',
see Rigged/EM_21/notes.md "Must know" 1) and the clip files armature-only (UE 5.8 Interchange rejects
armature-only FBX; RigM4A1 finding). This script leaves the RigEM_11 outputs untouched and writes a corrected
set to Rigged/EM_11/ue_export/: object renamed 'Armature' (data block keeps 'EM_11_Skeleton'), every clip
file carries mesh + armature, all other settings identical to RigEM_11.py FBX_COMMON / export_all.

CPU only (no renders). Never uses factory settings (they wipe the owner's extension wheels).
Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b
      "M:\\UnrealProjects\\AFS\\SourceAssets\\EM_Apocalyptic_Guns\\Rigged\\EM_11\\EM11_rig.blend"
      --python M:\\UnrealProjects\\AFS\\Scripts\\Blender\\ReexportEM11ForUE.py
The .blend is opened read-only in practice: this script never saves it.
"""
import json
import os

import bpy

SRC_DIR = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\Rigged\EM_11"
OUT_DIR = os.path.join(SRC_DIR, "ue_export")
PREFIX = "EM11"
CLIPS = ["Idle", "Fire", "DryFire", "Reload", "Chamber"]
FPS = 60

FBX_COMMON = dict(  # copied from RigEM_11.py (identical to RigM4A1.py)
    global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
    use_space_transform=True, bake_space_transform=False,
    axis_forward='-Y', axis_up='Z',
    mesh_smooth_type='FACE', use_tspace=True, use_triangles=False, use_custom_props=False,
    add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
    use_armature_deform_only=False, armature_nodetype='NULL',
    path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_metadata=True,
    colors_type='NONE',
)


def log(*a):
    print("EM11_REEXPORT", *a, flush=True)


def select_only(obs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (obs[0] if obs else None)


def ensure_slot(ob, act):
    ad = ob.animation_data or ob.animation_data_create()
    ad.action = act
    if hasattr(act, "slots"):
        if ad.action_slot is None:
            if len(act.slots) == 0:
                act.slots.new('OBJECT', ob.name)
            ad.action_slot = act.slots[0]
    return ad


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {"blend": bpy.data.filepath, "out_dir": OUT_DIR, "files": {}}
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    assert len(arms) == 1, "expected one armature, got %s" % [o.name for o in arms]
    arm = arms[0]
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
    assert len(meshes) == 1, "expected one skinned mesh, got %s" % [o.name for o in meshes]
    sk = meshes[0]
    report["armature_object_before"] = arm.name
    report["armature_data"] = arm.data.name
    report["mesh_object"] = sk.name
    if arm.name != "Armature":
        arm.name = "Armature"
    assert arm.name == "Armature", "rename failed: %s" % arm.name
    report["armature_object_after"] = arm.name
    report["bones"] = [b.name for b in arm.data.bones]
    scn = bpy.context.scene
    scn.render.fps = FPS
    scn.render.fps_base = 1.0
    acts = {c: bpy.data.actions.get("A_%s_%s" % (PREFIX, c)) for c in CLIPS}
    missing = [c for c, a in acts.items() if a is None]
    assert not missing, "actions missing in the .blend: %s (have %s)" % (missing, [a.name for a in bpy.data.actions])
    # Mesh file (rest pose, no animation).
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
    report["files"]["mesh"] = {"path": p, "bytes": os.path.getsize(p)}
    log("exported", p, os.path.getsize(p))
    # Clip files: mesh + armature (UE 5.8 Interchange needs the mesh), baked like RigEM_11.export_all.
    for clip in CLIPS:
        act = acts[clip]
        ensure_slot(arm, act)
        scn.frame_start = 0
        scn.frame_end = int(act.frame_range[1])
        scn.name = act.name
        scn.frame_set(scn.frame_end)  # bind pose is written from the current pose: rest
        bpy.context.view_layer.update()
        for pb in arm.pose.bones:
            m = pb.matrix_basis
            if m.translation.length > 1e-5 or abs(m.to_quaternion().angle) > 1e-4:
                raise RuntimeError("clip %s does not end on rest: %s" % (act.name, pb.name))
        select_only([arm, sk], arm)
        p = os.path.join(OUT_DIR, act.name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={'ARMATURE', 'MESH'},
                                 bake_anim=True, bake_anim_use_all_bones=True,
                                 bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                                 bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                                 bake_anim_simplify_factor=0.0, **FBX_COMMON)
        report["files"][clip] = {"path": p, "bytes": os.path.getsize(p), "frame_range": list(act.frame_range),
                                 "seconds": round(act.frame_range[1] / FPS, 4)}
        log("exported", p, os.path.getsize(p), "frames", scn.frame_end)
    ad.action = None
    scn.name = "Scene"
    with open(os.path.join(OUT_DIR, "reexport_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    log("done", json.dumps(report))


main()
