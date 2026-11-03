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
SPEED_CURVES = {'footspeed_l', 'footspeed_r', 'movedata_speed'}
# Only these four generated packages predate curve retiming; refuse to overwrite a locally edited copy.
V1_HASHES = {
    'QA_Crouch_SlowWalk_Fwd': '6e6c5895b85fe1d0e420a38d21d5003b60bc05dc171b9a86b651832ccbcc2169',
    'QA_Crouch_SlowWalk_Bwd': '85540bfe9e6110bf23fce130573e1ae3777a17e60c96da286bf4ec230a41df81',
    'QA_Crouch_SlowWalk_Left': 'f00945e3046461ff3550abc800f7556c108ca593f5bd97b0df1942ac2efdad43',
    'QA_Crouch_SlowWalk_Right': '7944284e0d25231b10c03ffdaca1c066a15c57da874041db481e9ca7a45b5372',
}


def native_hash(asset_path):
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return hashlib.sha256((content / (asset_path.removeprefix('/Game/') + '.uasset')).read_bytes()).hexdigest()


def root_motion_sample(sequence, at, options):
    pose = u.AnimPoseExtensions.get_anim_pose_at_time(sequence, at, options)
    return pose.get_bone_pose('root', u.AnimPoseSpaces.WORLD).translation


def retime_curves(source, controller, frames):
    """Retain the source curve's knot times and sample between them when stretching the walk."""
    types = u.RawCurveTrackTypes
    source_duration = source.get_play_length()
    duration = frames / SAMPLE_HZ
    value_at = u.AnimationLibrary.get_float_value_at_time
    for name in u.AnimationLibrary.get_animation_curve_names(source, types.RCT_FLOAT):
        # The Foot Placement node consumes joint speed, so it varies inversely with cycle duration.
        # Untouched constant timecodes have neither a phase nor a speed to adjust.
        scale = source_duration / duration if str(name).lower() in SPEED_CURVES else 1.
        times, values = u.AnimationLibrary.get_float_keys(source, name)
        if not values or min(values) == max(values) and (scale == 1. or not values[0]):
            continue
        identifier = u.AnimationCurveIdentifier()
        identifier.set_curve_identifier(name, types.RCT_FLOAT)
        knots = sorted({0., source_duration, *(t for t in times if 0. < t < source_duration)})
        # Keep sharp peaks at their authored key times. Intermediate readings preserve cubic source curves.
        samples = [a + (b-a)*i/4 for a,b in zip(knots, knots[1:]) for i in range(4)] + [source_duration]
        keys = [u.RichCurveKey(time=t * duration / source_duration, value=scale * value_at(source, name, t),
                               interp_mode=u.RichCurveInterpMode.RCIM_LINEAR) for t in samples]
        if not controller.set_curve_keys(identifier, keys, False):
            raise RuntimeError(f'Could not retime {name} from {source.get_name()}')


def slow_clip(source_path, dest_path):
    source = u.load_asset(source_path)
    if not source:
        raise RuntimeError('Missing owned walk ' + source_path)
    library = u.EditorAssetLibrary
    fingerprint = f'/{SLOW_SPEED}/{native_hash(source_path)}'
    recipe = 'v2' + fingerprint
    if library.does_asset_exist(dest_path):
        existing = u.load_asset(dest_path)
        tag = str(library.get_metadata_tag(existing, TAG))
        if tag == recipe:
            return existing
        if tag != 'v1' + fingerprint or native_hash(dest_path) != V1_HASHES.get(existing.get_name()):
            raise RuntimeError('Existing slow walk has a different recipe or source: ' + dest_path)
        controller = u.HoverAuthoring.get_local_animation_controller(existing)
        controller.open_bracket('Update slow-walk curve timing', False)
        try:
            retime_curves(source, controller, round(existing.get_play_length() * SAMPLE_HZ))
        finally:
            controller.close_bracket(False)
        library.set_metadata_tag(existing, TAG, recipe)
        if not library.save_loaded_asset(existing, False):
            raise RuntimeError('Could not save updated curves on ' + dest_path)
        return existing

    options = u.AnimPoseEvaluationOptions()
    options.set_editor_property('should_retarget', False)
    options.set_editor_property('extract_root_motion', False)
    duration = source.get_play_length()
    movement = root_motion_sample(source, duration, options) - root_motion_sample(source, 0, options)
    distance = math.hypot(movement.x, movement.y)
    if not 275 <= distance / duration <= 325:
        raise RuntimeError(f'Unexpected source speed {distance / duration:.2f} on {source_path}')
    # These owned derivatives contain bone animation. Do not silently retime a future event-bearing source.
    if (u.AnimationLibrary.get_animation_notify_events(source) or u.AnimationLibrary.get_animation_sync_markers(source)
            or u.AnimationLibrary.get_animation_curve_names(source, u.RawCurveTrackTypes.RCT_TRANSFORM)):
        raise RuntimeError('The source now has timed events, markers or transform curves: ' + source_path)
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
        retime_curves(source, controller, frames)
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
