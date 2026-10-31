"""ProbeNYCMeshYaw.py - read-only: measure each NYC roster definition's gait facing on its own body (2026-10-31).

For every moving sample of the definition's MovementBlendSpace, the clip is evaluated retargeted onto the
definition's AppearanceMesh (AnimPoseEvaluationOptions.optional_skeletal_mesh + should_retarget, the
compatible-skeleton path) and two component-space directions are averaged over the cycle:
  toes = (ball_l - foot_l) + (ball_r - foot_r)        (where the feet point)
  hips = perpendicular of thigh_l -> thigh_r          (where the pelvis faces; sign chosen toward the toes)
Nothing is saved. Receipt D:/AFS_Comparisons/ZombieDiversity_20261031/mesh_yaw_probe.json; quits the editor.
"""
import json
import math
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/ZombieDiversity_20261031/mesh_yaw_probe.json')
ENC = '/Game/HoverPrototype/NYC/DA_NYCEncounters'
R = {'definitions': {}, 'errors': []}


def facing(seq, mesh, fps=30):
    options = u.AnimPoseEvaluationOptions()
    options.optional_skeletal_mesh = mesh
    options.should_retarget = True
    length = seq.get_play_length()
    n = max(20, int(round(length * fps)))
    tx = ty = hx = hy = 0.0
    for i in range(n):
        t = min(i * length / n, length - 1e-4)
        pose = u.AnimPoseExtensions.get_anim_pose_at_time(seq, t, options)
        p = {b: pose.get_bone_pose(b, u.AnimPoseSpaces.WORLD).translation
             for b in ('foot_l', 'ball_l', 'foot_r', 'ball_r', 'thigh_l', 'thigh_r')}
        vx = (p['ball_l'].x - p['foot_l'].x) + (p['ball_r'].x - p['foot_r'].x)
        vy = (p['ball_l'].y - p['foot_l'].y) + (p['ball_r'].y - p['foot_r'].y)
        vn = math.hypot(vx, vy) or 1.0
        tx, ty = tx + vx / vn, ty + vy / vn
        lx, ly = p['thigh_r'].x - p['thigh_l'].x, p['thigh_r'].y - p['thigh_l'].y
        ln = math.hypot(lx, ly) or 1.0
        hx, hy = hx + lx / ln, hy + ly / ln
    toes = math.degrees(math.atan2(ty, tx))
    line = math.degrees(math.atan2(hy, hx))
    cands = [line + 90.0, line - 90.0]
    hips = min(cands, key=lambda a: abs(((a - toes) + 180.0) % 360.0 - 180.0))
    hips = ((hips + 180.0) % 360.0) - 180.0
    return {'toes_yaw': round(toes, 1), 'hips_yaw': round(hips, 1),
            'toes_consistency': round(math.hypot(tx, ty) / n, 3), 'length': round(length, 3)}


def main():
    enc = u.EditorAssetLibrary.load_asset(ENC)
    defs = list(enc.get_editor_property('standards')) + [enc.get_editor_property('brute'), enc.get_editor_property('kid')]
    for bosses in ('stone_golem', 'giant_kid'):
        try:
            v = enc.get_editor_property(bosses)
            if v:
                defs.append(v)
        except Exception:  # noqa: BLE001
            pass
    for d in defs:
        if not d:
            continue
        row = {'clips': []}
        R['definitions'][d.get_name()] = row
        try:
            mesh = d.get_editor_property('appearance_mesh')
            bs = d.get_editor_property('movement_blend_space')
            row['mesh'] = mesh.get_path_name() if mesh else None
            row['blend'] = bs.get_path_name() if bs else None
            for k in ('b_align_mesh_yaw', 'mesh_yaw_offset'):
                try:
                    row[k] = d.get_editor_property(k)
                except Exception:  # noqa: BLE001
                    pass
            if not mesh or not bs:
                continue
            for s in bs.get_editor_property('sample_data'):
                seq = s.get_editor_property('animation')
                speed = s.get_editor_property('sample_value').x
                if not seq or speed <= 0:
                    continue
                f = facing(seq, mesh)
                f.update({'clip': seq.get_path_name().split('.')[0], 'speed': speed})
                row['clips'].append(f)
        except Exception:  # noqa: BLE001
            row['error'] = traceback.format_exc(limit=2)
    OUT.write_text(json.dumps(R, indent=1, default=str))
    print('PROBE_MESH_YAW_DONE', json.dumps({k: [(c['clip'].rsplit('/', 1)[-1], c['speed'], c['toes_yaw'], c['hips_yaw'])
                                                  for c in v['clips']] for k, v in R['definitions'].items()}))


try:
    main()
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())
    OUT.write_text(json.dumps(R, indent=1, default=str))
    print('PROBE_MESH_YAW_ERROR', R['errors'][-1])
u.SystemLibrary.quit_editor()
