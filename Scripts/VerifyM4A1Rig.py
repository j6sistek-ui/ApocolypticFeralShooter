"""VerifyM4A1Rig.py - headless check that the Blender-exported M4A1 rig imports into UE 5.8.

Imports SourceAssets/M4A1_Modular/Rigged/SK_M4A1.fbx into a scratch folder, then every
A_M4A1_*.fbx clip onto that skeleton two ways: Interchange (project default FBX path, via the
InterchangeManager with an animation-only override pipeline) and the legacy FBX importer
(Interchange.FeatureFlags.Import.FBX 0 + FbxImportUI). Records bounds, bone list, slot
order, clip frame counts/lengths and per-frame bone deltas (AnimPose), then deletes the
scratch folder. Receipt: D:/AFS_Comparisons/M4A1_20261029/ue_import_check.json

Run:
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/VerifyM4A1Rig.py" -nullrhi -unattended -nosplash
Pass 'keep' inside the quoted value after the script path to keep the scratch assets.
"""
import json
import os
import sys
import traceback
import unreal as u

RIGGED = r"M:\UnrealProjects\AFS\SourceAssets\M4A1_Modular\Rigged"
VARIANTS = r"D:\AFS_Comparisons\M4A1_20261029\anim_variants"
SCRATCH = "/Game/HoverPrototype/Weapon/M4A1_RigCheck"
RECEIPT = r"D:\AFS_Comparisons\M4A1_20261029\ue_import_check.json"
KEEP = "keep" in [a.lower() for a in sys.argv[1:]]
CLIPS = ["Idle", "Fire", "DryFire", "Reload", "Chamber"]
EXPECT_FRAMES = {"Idle": 2, "Fire": 8, "DryFire": 10, "Reload": 145, "Chamber": 67}  # keys at 60 fps
CHECKS = {  # clip -> (bone, frame, expected delta cm in component space X fwd / Y right / Z up)
    "Fire": [("bolt_carrier", 2, (-7.5, 0, 0)), ("bolt_carrier", 7, (0, 0, 0)), ("charging_handle", 2, (0, 0, 0))],
    "Reload": [("magazine", 45, (1.0, 3.0, -30.0)), ("magazine", 60, (None, None, -45.0)),
               ("bolt_carrier", 0, (-7.5, 0, 0)), ("bolt_carrier", 130, (0, 0, 0)), ("magazine", 111, (0, 0, 0))],
    "Chamber": [("charging_handle", 30, (-9.0, 0, 0)), ("bolt_carrier", 30, (-9.0, 0, 0))],
}
SOCKETS = ("muzzle", "ejection_port", "sight", "grip_r", "grip_l", "mag_well")
REPORT = {"ok": False, "errors": [], "mesh": {}, "interchange": {}, "legacy": {}, "bone_axes": {}, "notes": []}
EA = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()


def log(*a):
    u.log("[VerifyM4A1Rig] " + " ".join(str(x) for x in a))


def import_task(filename, name, options, dest=SCRATCH):
    task = u.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", options)
    AT.import_asset_tasks([task])
    paths = [str(p) for p in (task.get_editor_property("imported_object_paths") or [])]
    log("imported", os.path.basename(filename), "->", [p.split("/")[-1] for p in paths])
    return paths


def mesh_ui():
    ui = u.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("automated_import_should_detect_type", False)
    smd = ui.get_editor_property("skeletal_mesh_import_data")
    smd.set_editor_property("import_morph_targets", False)
    smd.set_editor_property("use_t0_as_ref_pose", False)
    smd.set_editor_property("convert_scene", True)
    smd.set_editor_property("normal_import_method", u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    return ui


def legacy_anim_ui(skel):
    ui = u.FbxImportUI()
    ui.set_editor_property("import_mesh", False)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("skeleton", skel)
    ui.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_ANIMATION)
    ui.set_editor_property("automated_import_should_detect_type", False)
    aid = ui.get_editor_property("anim_sequence_import_data")
    aid.set_editor_property("animation_length", u.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    aid.set_editor_property("import_bone_tracks", True)
    aid.set_editor_property("use_default_sample_rate", False)
    aid.set_editor_property("custom_sample_rate", 60)
    return ui


def interchange_anim_import(filename, name, skel):
    """Animation-only import through the Interchange manager with an override pipeline."""
    pipe = u.InterchangeGenericAssetsPipeline()
    common = pipe.get_editor_property("common_skeletal_meshes_and_animations_properties")
    common.set_editor_property("skeleton", skel)
    common.set_editor_property("import_only_animations", True)
    anim = pipe.get_editor_property("animation_pipeline")
    anim.set_editor_property("import_animations", True)
    anim.set_editor_property("import_bone_tracks", True)
    pipe.get_editor_property("mesh_pipeline").set_editor_property("import_skeletal_meshes", False)
    pipe.get_editor_property("mesh_pipeline").set_editor_property("import_static_meshes", False)
    pipe.get_editor_property("material_pipeline").set_editor_property("import_materials", False)
    pipe.set_editor_property("asset_name", name) if hasattr(pipe, "asset_name") else None
    try:
        pipe.set_editor_property("asset_name", name)
    except Exception:
        pass
    im = u.InterchangeManager.get_interchange_manager_scripted()
    sd = u.InterchangeManager.create_source_data(filename)
    params = u.ImportAssetParameters()
    params.set_editor_property("is_automated", True)
    params.set_editor_property("override_pipelines", [u.SoftObjectPath(pipe.get_path_name())])
    before = set(EA.list_assets(SCRATCH, recursive=True, include_folder=False))
    ok = im.import_asset(SCRATCH, sd, params)
    try:
        im.wait_until_all_tasks_done(False)
    except Exception:
        pass
    after = set(EA.list_assets(SCRATCH, recursive=True, include_folder=False))
    new = sorted(after - before)
    log("interchange", os.path.basename(filename), "ok", ok, "new", [p.split("/")[-1] for p in new])
    return new


def pose_checks(seq, clip):
    info = {}
    opts = u.AnimPoseEvaluationOptions()
    for prop, val in (("evaluation_type", u.AnimDataEvalType.RAW), ("retarget", False), ("extract_root_motion", False)):
        try:
            opts.set_editor_property(prop, val)
        except Exception:
            pass
    p0 = u.AnimPoseExtensions.get_anim_pose_at_frame(seq, 0, opts)
    names = [str(n) for n in u.AnimPoseExtensions.get_bone_names(p0)]
    info["pose_bones"] = names
    tests = []
    for (bone, frame, expect) in CHECKS.get(clip, []):
        pose = u.AnimPoseExtensions.get_anim_pose_at_frame(seq, frame, opts)
        cur = u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD).translation
        ref = u.AnimPoseExtensions.get_ref_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD).translation
        d = [cur.x - ref.x, cur.y - ref.y, cur.z - ref.z]
        ok = all(e is None or abs(d[i] - e) < 0.4 for i, e in enumerate(expect))
        tests.append({"bone": bone, "frame": frame, "delta_cm": [round(v, 3) for v in d], "expect_cm": list(expect), "ok": ok})
        log(clip, bone, "f%d" % frame, [round(v, 2) for v in d], expect, "OK" if ok else "FAIL")
    info["tests"] = tests
    if clip == "Idle":
        axes = {}
        for bn in names:
            t = u.AnimPoseExtensions.get_ref_bone_pose(p0, bn, u.AnimPoseSpaces.WORLD)
            xa = t.rotation.rotate_vector(u.Vector(1, 0, 0))
            ya = t.rotation.rotate_vector(u.Vector(0, 1, 0))
            za = t.rotation.rotate_vector(u.Vector(0, 0, 1))
            axes[bn] = {"loc_cm": [round(t.translation.x, 3), round(t.translation.y, 3), round(t.translation.z, 3)],
                        "x_axis": [round(xa.x, 3), round(xa.y, 3), round(xa.z, 3)],
                        "y_axis": [round(ya.x, 3), round(ya.y, 3), round(ya.z, 3)],
                        "z_axis": [round(za.x, 3), round(za.y, 3), round(za.z, 3)]}
        info["bone_axes"] = axes
    return info


def describe(paths, clip, mode):
    seqs = []
    for x in paths:
        a = u.load_asset(x.split(".")[0])
        if isinstance(a, u.AnimSequence):
            seqs.append(a)
    if not seqs:
        REPORT["errors"].append("%s %s: no AnimSequence imported" % (mode, clip))
        return {"imported": paths, "anim": None}
    seq = seqs[0]
    d = {"imported": paths, "asset": seq.get_path_name(), "skeleton": seq.get_editor_property("skeleton").get_path_name(),
         "num_frames": u.AnimationLibrary.get_num_frames(seq), "length_s": u.AnimationLibrary.get_sequence_length(seq)}
    try:
        d["tracks"] = [str(n) for n in u.AnimationLibrary.get_animation_track_names(seq)]
    except Exception as e:
        d["tracks"] = "ERR %s" % e
    keys = d["num_frames"] + 1
    if abs(keys - EXPECT_FRAMES[clip]) > 1 or abs(d["length_s"] - (EXPECT_FRAMES[clip] - 1) / 60.0) > 0.02:
        REPORT["errors"].append("%s %s: %d keys / %.4f s, expected %d keys at 60 fps" % (mode, clip, keys, d["length_s"], EXPECT_FRAMES[clip]))
    try:
        d.update(pose_checks(seq, clip))
        for t in d.get("tests", []):
            if not t["ok"]:
                REPORT["errors"].append("%s %s %s f%d delta %s expect %s" % (mode, clip, t["bone"], t["frame"], t["delta_cm"], t["expect_cm"]))
        if mode == "legacy" and "bone_axes" in d:
            REPORT["bone_axes"] = d.pop("bone_axes")
    except Exception:
        d["pose_error"] = traceback.format_exc()
        REPORT["errors"].append("%s %s pose eval failed" % (mode, clip))
    log(mode, clip, "keys", keys, "len", round(d["length_s"], 4), "skeleton", d["skeleton"].split("/")[-1])
    return d


def main():
    if EA.does_directory_exist(SCRATCH):
        EA.delete_directory(SCRATCH)
    # ---- skeletal mesh (Interchange, the project default)
    paths = import_task(os.path.join(RIGGED, "SK_M4A1.fbx"), "SK_M4A1", mesh_ui())
    mesh = u.load_asset(SCRATCH + "/SK_M4A1")
    assert isinstance(mesh, u.SkeletalMesh), "no skeletal mesh imported: %s" % paths
    skel = mesh.get_editor_property("skeleton")
    b = mesh.get_bounds()
    ext, org = b.box_extent, b.origin
    REPORT["mesh"] = {
        "paths": paths, "skeleton": skel.get_path_name(),
        "bounds_min_cm": [org.x - ext.x, org.y - ext.y, org.z - ext.z],
        "bounds_max_cm": [org.x + ext.x, org.y + ext.y, org.z + ext.z],
        "length_cm": ext.x * 2,
        "material_slots": [str(m.material_slot_name) for m in mesh.get_editor_property("materials")],
    }
    log("mesh length cm", ext.x * 2, "slots", len(REPORT["mesh"]["material_slots"]))
    # ---- clips via Interchange manager
    for clip in CLIPS:
        name = "A_M4A1_" + clip
        try:
            new = interchange_anim_import(os.path.join(RIGGED, name + ".fbx"), name, skel)
            REPORT["interchange"][clip] = describe(new, clip, "interchange")
        except Exception:
            REPORT["interchange"][clip] = {"error": traceback.format_exc()}
            REPORT["errors"].append("interchange %s raised" % clip)
    # ---- clips via the legacy importer
    u.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    try:
        for clip in CLIPS:
            name = "A_M4A1_" + clip
            p = import_task(os.path.join(RIGGED, name + ".fbx"), "L_" + name, legacy_anim_ui(skel))
            REPORT["legacy"][clip] = describe(p, clip, "legacy")
    finally:
        u.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 1")
    REPORT["ok"] = not REPORT["errors"]


try:
    main()
except Exception:
    REPORT["errors"].append(traceback.format_exc())
    log(traceback.format_exc())
finally:
    if not KEEP:
        try:
            if EA.does_directory_exist(SCRATCH):
                EA.delete_directory(SCRATCH)
                REPORT["scratch_deleted"] = True
        except Exception as e:
            REPORT["errors"].append("cleanup: %s" % e)
    os.makedirs(os.path.dirname(RECEIPT), exist_ok=True)
    with open(RECEIPT, "w") as f:
        json.dump(REPORT, f, indent=1, default=str)
    log("receipt", RECEIPT, "ok", REPORT["ok"], "errors", len(REPORT["errors"]))
