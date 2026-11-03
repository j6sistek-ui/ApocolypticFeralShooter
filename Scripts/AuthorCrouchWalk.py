"""Add 120 cm/s samples to Vexa's owned crouch database.

With the editor closed, run UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi
-ExecutePythonScript=<absolute-path-to-this-script>. Re-running reuses the four private assets.
Proof: Scripts/ProveWalking.py with WALK_MAP=explore and WALK_TESTS=crouchhalf,crouch,holdmove,walk.
"""
import hashlib
import math
from pathlib import Path

import unreal as u


POLISH = '/Game/HoverPrototype/Hybrid/Polish'
DATABASE = POLISH + '/PSD_DirectionalCrouch'
DIRECTIONS = ('Fwd', 'Bwd', 'Left', 'Right')
SLOW_SPEED = 120.0
SAMPLE_HZ = 30
TAG = 'AFS_CrouchWalkRecipe'


def native_hash(asset_path):
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return hashlib.sha256((content / (asset_path.removeprefix('/Game/') + '.uasset')).read_bytes()).hexdigest()


def root_motion_sample(sequence, at, options):
    pose = u.AnimPoseExtensions.get_anim_pose_at_time(sequence, at, options)
    return pose.get_bone_pose('root', u.AnimPoseSpaces.WORLD).translation


def slow_clip(source_path, dest_path):
    source = u.load_asset(source_path)
    if not source:
        raise RuntimeError('Missing owned walk ' + source_path)
    library = u.EditorAssetLibrary
    recipe = f'v1/{SLOW_SPEED}/{native_hash(source_path)}'
    if library.does_asset_exist(dest_path):
        existing = u.load_asset(dest_path)
        if str(library.get_metadata_tag(existing, TAG)) == recipe:
            return existing
        raise RuntimeError('Existing slow walk has a different recipe or source: ' + dest_path)

    options = u.AnimPoseEvaluationOptions()
    options.set_editor_property('should_retarget', False)
    options.set_editor_property('extract_root_motion', False)
    duration = source.get_play_length()
    movement = root_motion_sample(source, duration, options) - root_motion_sample(source, 0, options)
    distance = math.hypot(movement.x, movement.y)
    if not 275 <= distance / duration <= 325:
        raise RuntimeError(f'Unexpected source speed {distance / duration:.2f} on {source_path}')
    # These owned derivatives contain bone animation. Do not silently retime a future event-bearing source.
    if u.AnimationLibrary.get_animation_notify_events(source) or u.AnimationLibrary.get_animation_sync_markers(source):
        raise RuntimeError('The source now has timed markers or notifies: ' + source_path)
    frames = round(distance / SLOW_SPEED * SAMPLE_HZ)
    tracks = u.AnimationLibrary.get_animation_track_names(source)
    samples = [u.AnimPoseExtensions.get_anim_pose_at_time(source, duration * i / frames, options)
               for i in range(frames + 1)]
    slow = library.duplicate_asset(source_path, dest_path)
    if not slow:
        raise RuntimeError('Could not create ' + dest_path)
    controller = u.HoverAuthoring.get_local_animation_controller(slow)
    controller.open_bracket('Retiming existing directional crouch cycle', False)
    try:
        controller.set_number_of_frames(u.FrameNumber(frames), False)
        for bone in tracks:
            keys = [pose.get_bone_pose(bone, u.AnimPoseSpaces.LOCAL) for pose in samples]
            if not controller.set_bone_track_keys(
                bone, [k.translation for k in keys], [k.rotation for k in keys], [k.scale3d for k in keys], False
            ):
                raise RuntimeError(f'Failed to retime {dest_path}: {bone}')
    finally:
        controller.close_bracket(False)
    if abs(slow.get_play_length() - frames / SAMPLE_HZ) > .02:
        raise RuntimeError('Unexpected baked duration on ' + dest_path)
    library.set_metadata_tag(slow, TAG, recipe)
    if not library.save_loaded_asset(slow, False):
        raise RuntimeError('Failed to save ' + dest_path)
    return slow


def author():
    database = u.load_asset(DATABASE)
    if not database:
        raise RuntimeError('Missing owned pose database ' + DATABASE)
    existing = [database.get_animation_asset(i) for i in range(database.get_num_animation_assets())]
    required = [POLISH + '/Crouch/QA_Crouch_Walk_' + direction for direction in DIRECTIONS]
    if not all(u.load_asset(path) in existing for path in required):
        raise RuntimeError('The expected directional walks are absent from the live database')
    slow = [slow_clip(path, path.replace('/QA_Crouch_Walk_', '/QA_Crouch_SlowWalk_')) for path in required]
    missing = [clip for clip in slow if clip not in existing]
    if missing:
        field = 'DatabaseAnimationAssets'
        old = u.HoverAuthoring.describe_object_properties(database)[field]
        if not old.startswith('(') or not old.endswith(')'):
            raise RuntimeError('Unexpected format for database animation entries')
        # Keep all existing entries, sampling settings, and future user additions intact.
        entries = [f'(AnimAsset="{clip.get_path_name()}")' for clip in missing]
        new = old[:-1] + ',' + ','.join(entries) + ')'
        change = u.ClsComparisonAuthoring.set_local_animation_property
        imported = change(database, field, new)
        actual = [database.get_animation_asset(i) for i in range(database.get_num_animation_assets())]
        if not imported or actual != existing + missing:
            change(database, field, old)
            raise RuntimeError('Could not append and verify slow walks in the owned database')
        if not u.EditorAssetLibrary.save_loaded_asset(database, False):
            raise RuntimeError('Could not save ' + DATABASE)
    u.log(f'AFS_CROUCH_WALK database={DATABASE} new_entries={len(missing)} speed_cm_s={SLOW_SPEED}')


if __name__ == '__main__':
    author()
