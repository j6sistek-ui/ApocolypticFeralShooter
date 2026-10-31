"""AuthorGunRigs.py - per-weapon UHoverGunRig assets, their DA_HoverPilot.GunRigs keys, and a headless proof.

Author (idempotent, read-back verified):
  /Game/HoverPrototype/Weapons/Rigs/DA_GunRig_M4A1   SK_M4A1, all 8 v2 clips (Idle, IdleEmpty, Fire, FireLast,
                                                     DryFire, Reload, ReloadTactical, Chamber), per-shot brass
  /Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM11   SK_EM11 (AK), 5 clips; no bolt hold-open, so FireLast /
                                                     IdleEmpty / ReloadTactical stay null (Fire / Idle / Reload)
  /Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM21   SK_EM21 (SMG), 5 clips
  /Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM08   SK_EM08 (revolver), 5 clips, empties fall 0.37 s into the
                                                     Reload, cylinder indexes +60 deg (clip sign) per Fire/DryFire/Chamber
  DA_HoverPilot.GunRigs (HoverAuthoring.bind_gun_rig):
    DA_AFS_Ballista (exact)                 -> DA_GunRig_M4A1   Vexa's starting rifle in L_NYC_Survival
    DA_Weapon_Pistol (DA_Weapon_Pistol_001) -> DA_GunRig_EM08
    DA_Weapon_Rifle  (DA_Weapon_Rifle_00N)  -> DA_GunRig_EM11
    DA_Weapon_Rifle_002 (exact)             -> DA_GunRig_EM21   no SMG definition exists; one rifle tier shows it
  The DA's loose Weapon|Rigged fields (the M4A1 default rig) are left as ImportM4A1.py bound them.
  Reload-IK fields (2026-10-30, design items 4-8): every rig carries Stance (Pistol for DA_GunRig_EM08, Rifle
  otherwise; picks PistolAim / RifleAim as the body's upper-body pose), HandTargetSocket 'hand_l_target' (the
  palm-centre bone the gun's Reload clips key; the support IK follows it live) and bGripAtPalm True (the right
  palm centre is the seat). Stance is written by enum name (unreal.HoverGunStance.PISTOL).
  Grip seat (2026-10-31, owner 00:10: "closed fist at the bottom of the receiver, pistol grip hanging empty"):
  GripSeatOffset (gun cm from grip_r, where the right PALM CENTRE sits: grip_r is every rig's grip TOP centre, the
  fist closes around the grip's middle) and GripRotationOffset (gun-space pitch/yaw/roll applied about the seat so
  the grip axis runs through the fist) per rig, measured by Scripts/MeasureGripSeat.py (grip geometry from the SK_*
  vertices, the fist from the stance pose in PIE; receipt D:/AFS_Comparisons/GripSeat_20261031/measure.json). The
  rotation's pitch/yaw part is a barrel-vs-aim-ray deviation (an aim error: FireShot fires along the barrel), held at
  3 deg; the full alignment the pose would want (about 20 deg of pitch on the AR grip) is in the receipt for tuning.

Verify (CPU only: -nullrhi PIE of L_NYC_Survival, no pixels): drives the real input path
(HoverAuthoring.test_key LeftMouseButton, UHoverCombatBridge.reload / select_quickbar), samples the held
gun component's (WorldGunSkel) bolt_carrier / magazine component-space offsets from their idle pose on every
world tick (fixed 1/30 s step), counts brass (StaticMeshActors owned by the weapon), reads
AHoverPilot.GunCylinderAngle, and harvests HOVER_GUN log lines. Hands (design item 8): per tick through each
reload it reads the body's left palm centre (midpoint of hand_l / middle_01_l) against the gun's hand_l_target
socket and grip_l, and hand_r's world rotation; asserts palm within 6 cm of hand_l_target at 0.75 / 1.5 / 1.9 s
(clip seconds x ReloadTime / 2.4) of the M4A1 empty reload and 0.75 / 1.2 s of the EM_08 reload, hand_r turned
less than 12 deg from the reload start to 1.2 s, and the palm within 6 cm of grip_l while aiming just before. Fire
(design A3, 2026-10-30): a 5-round M4A1 burst and the three EM_08 shots are sampled on every tick: the left palm
within 4 cm of hand_l_target, never ahead of the muzzle, no driver montage (IsActionPlaying false), and the stance
fire additive's spine_03 kick peak (2-10 deg). Gun rides the hand (2026-10-30 23:30, "her hand is not on the grip"):
on every burst tick the right palm sits within 0.5 cm of the grip SEAT (grip_r + GripSeatOffset; 2026-10-31, was
grip_r itself), hand_r's component-space delta from the pre-press tick matches the pilot's GunHandKick within 3 deg
(and the gun's world rotation is mesh * kick * mesh^-1 * the aim-ray rotation * GripRotationOffset within 1 deg), every
bone under hand_r keeps its aim-pose local rotation within 1 deg, and on the rifle
hand_r's delta peaks at >= 2 deg (the kick still happens). Hand orientation (design B7): at the M4A1 0.75 / 1.5 s and EM_08
0.75 s marks hand_l's rotation relative to the gun equals the clip's hand_l_target delta applied to the pre-reload
relative rotation within 15 deg (identity delta until the rigs key rotation: the hand keeps its aim orientation).
Grip seat (2026-10-31): the right palm also stays within 0.5 cm of the seat on every tick of both M4A1 reloads and the
EM_08 reload, and at rest (the aimed, settled tick before the first shot of each gun) the muzzle direction is within
6 deg of the aim ray (GunAimWorldRotation's X) and of the camera's control rotation.
Rig flash fields (design C1): MuzzleFlashScale / MuzzleLightScale per rig; warm flash (2026-10-31): MuzzleFlashOverride
(NS_GunFire on all four; null: the definition's Niagara flash), bOverrideMuzzleLightColor / MuzzleLightColorOverride
(orange point light), MuzzleLightRadiusOverride (150 cm; 0: the tier's 320), TracerOverride / bTracerOverrideTierColor /
TracerOverrideLifetime (null / True / 0: the tier's tracer; CaptureGuns.py TRACER_TRIAL writes them in memory). Zombies are destroyed as they spawn so HP
never moves. The vendor DA_Weapon_Pistol_001 spawns BP_Weapon_Pistol_001 (a plain AZE_WeaponBase), which
never calls ApplyGunRig; to equip it as a rigged gun its WeaponActorClass is switched to HoverCyberRifle IN
MEMORY ONLY for the EM_08 step and restored right after (never saved; the .uasset hash is recorded before and
after). Changes only the unsaved Play world otherwise.

Receipt: D:/AFS_Comparisons/GunRigs_20261029/author_receipt.json

Run (never concurrently with another AFS editor):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorGunRigs.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GunRigs_20261029/author.log"
Flags (inside the quoted value, after the script path): --author-only, --verify-only, --resave (save every rig even
when no field changed, so a rig picks up new C++ fields / class layout on disk)
"""
import hashlib
import json
import math
import re
import sys
import time
import traceback
from pathlib import Path

import unreal as u

ARGS = sys.argv[1:]
DO_AUTHOR = '--verify-only' not in ARGS
DO_VERIFY = '--author-only' not in ARGS
FORCE_SAVE = '--resave' in ARGS

OUT = Path('D:/AFS_Comparisons/GunRigs_20261029')
RECEIPT = OUT / 'author_receipt.json'
PROJECT = Path('M:/UnrealProjects/AFS')
RIGS = '/Game/HoverPrototype/Weapons/Rigs'
DA_PATH = '/Game/HoverPrototype/DA_HoverPilot'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
M4 = '/Game/HoverPrototype/Weapons/M4A1'
EM = '/Game/HoverPrototype/Weapons/EM'
BALLISTA = '/Game/HoverPrototype/ZombieEngine/DA_AFS_Ballista'
PISTOL = '/Game/ZESP/ZE/Data/Weapons/DA_Weapon_Pistol_001'
RIFLE1 = '/Game/ZESP/ZE/Data/Weapons/DA_Weapon_Rifle_001'
RIFLE2 = '/Game/ZESP/ZE/Data/Weapons/DA_Weapon_Rifle_002'
PISTOL_AMMO = '/Game/ZESP/ZE/Data/Ammo/DA_AMMO_Pistol'  # DA_Weapon_Pistol_001.AmmoDefinition
CLIP_FIELDS = ['Idle', 'Fire', 'DryFire', 'Reload', 'Chamber', 'FireLast', 'IdleEmpty', 'ReloadTactical']
SOCKET_DEFAULTS = {'MuzzleSocket': 'muzzle', 'EjectSocket': 'ejection_port', 'SightSocket': 'sight',
                   'GripSocket': 'grip_r', 'SupportSocket': 'grip_l', 'MagWellSocket': 'mag_well'}


def em_clips(n):
    base = '%s/EM_%s/Anims/A_EM%s_' % (EM, n, n)
    clips = {c: base + c for c in ('Idle', 'Fire', 'DryFire', 'Reload', 'Chamber')}
    clips.update({'FireLast': None, 'IdleEmpty': None, 'ReloadTactical': None})
    return clips


# Field values per rig (cpp names). Clip/mesh values are asset paths, None clears the field.
RIG_SPECS = {
    'DA_GunRig_M4A1': {
        'Mesh': M4 + '/SK_M4A1',
        'Stance': 'Rifle', 'HandTargetSocket': 'hand_l_target', 'bGripAtPalm': True,
        'clips': {c: M4 + '/Anims/A_M4A1_' + c for c in CLIP_FIELDS},
        'bEjectsPerShot': True, 'EjectDelay': 0.0, 'EjectDirection': (1, 0, .25), 'EjectImpulse': 0.0,
        'CylinderBone': 'None', 'IndexDegrees': 0.0,
        'FallbackMuzzle': (45, 0, 4), 'FallbackGrip': (0, 0, 0), 'FallbackSupportGrip': (22, 0, -3),
        'FallbackSight': (5, 0, 9),
        # Grip seat (MeasureGripSeat.py 2026-10-31): AR grip axis (-0.514, 0, -0.858), 31 deg rake, 10 cm long, 5.9 deep
        # x 2.5 wide; its 4.5 cm point A (-1.0, 0, -3.9) lands on the rifle fist's tunnel centre (3.3, -1.7, 0) from the
        # palm. The pose's fist wants (21, -13, 2) deg; swing held at 3 deg (barrel vs aim ray), 1776 grip vertices.
        'GripSeatOffset': (-4.38, 1.61, -3.56), 'GripRotationOffset': (2.6, -1.5, 4.12),
        # 2026-10-30 22:00 GPU capture (CaptureGuns.py, design C2): at 1.0 / 0.6 (180 cd) the hands camera read
        # flash_luma_ratio 5.1, saturated 7 % (targets 2.4 / 8 %), the point light whitening the receiver and
        # both hands; the sprite alone (light off, tick +3) already read 2.3. 2026-10-31 00:40 gallery: every
        # candidate sprite lit the hands identically, so the whiteout is the POINT LIGHT under the night exposure:
        # light to 9 cd (0.03) with a 150 cm reach, and the Zombie Engine's white NS_GunFire burst (0.05 s, reads
        # orange under the warm light) at 3x as the flash itself.
        'MuzzleFlashScale': 3.0, 'MuzzleLightScale': 0.03, 'MuzzleLightRadiusOverride': 150.0,
        # Warm flash (owner 2026-10-30 23:40: "more red/orange, instead of comic book blue"): NS_GunFire replaces the
        # Ballista's blue NS_BallistaMuzzle; the point light goes orange. The tracer stays the tier's (the trial
        # fields are written in memory by CaptureGuns.py TRACER_TRIAL only).
        'MuzzleFlashOverride': '/Game/ZESP/ZE/FX/Weapon/NS_GunFire',
        'bOverrideMuzzleLightColor': True, 'MuzzleLightColorOverride': (1.0, 0.62, 0.30),
        'TracerOverride': None, 'bTracerOverrideTierColor': True, 'TracerOverrideLifetime': 0.0,
        'Description': 'M4A1 (SK_M4A1, Blender rig v2): all 8 clips; the last round locks the bolt back '
                       '(FireLast -> IdleEmpty) until the empty Reload releases it; ReloadTactical keeps it '
                       'home. One casing per round at ejection_port. Authored by Scripts/AuthorGunRigs.py.',
    },
    'DA_GunRig_EM11': {
        'Mesh': EM + '/EM_11/SK_EM11', 'clips': em_clips('11'),
        'Stance': 'Rifle', 'HandTargetSocket': 'hand_l_target', 'bGripAtPalm': True,
        'bEjectsPerShot': True, 'EjectDelay': 0.0, 'EjectDirection': (1, 0, .25), 'EjectImpulse': 0.0,
        'CylinderBone': 'None', 'IndexDegrees': 0.0,
        'FallbackMuzzle': (45, 0, 4), 'FallbackGrip': (0, 0, 0), 'FallbackSupportGrip': (22, 0, -3),
        'FallbackSight': (5, 0, 9),
        # Grip seat (MeasureGripSeat.py 2026-10-31): AK grip axis (-0.287, 0, -0.958), 17 deg rake, 9 cm, 5.8 deep x 4.4
        # wide (409 vertices); A (-2.25, -0.08, -4.31); fist wants (7, -13, 2) deg, swing held at 3 deg.
        'GripSeatOffset': (-5.66, 1.47, -4.13), 'GripRotationOffset': (1.38, -2.66, 2.41),
        # 22:00 capture at 0.8 / 0.45 (135 cd): ratio 4.3, saturated 13 % (targets 1.8 / 4 %); sprite alone 2.05.
        # 2026-10-31: light 6 cd (0.02) at 150 cm, NS_GunFire burst at 3x (see the M4A1 note).
        'MuzzleFlashScale': 3.0, 'MuzzleLightScale': 0.02, 'MuzzleLightRadiusOverride': 150.0,
        'MuzzleFlashOverride': '/Game/ZESP/ZE/FX/Weapon/NS_GunFire',
        'bOverrideMuzzleLightColor': True, 'MuzzleLightColorOverride': (1.0, 0.62, 0.30),
        'TracerOverride': None, 'bTracerOverrideTierColor': True, 'TracerOverrideLifetime': 0.0,
        'Description': 'EM_11 (AK pattern, 99 cm): 5 clips. An AK has no bolt hold-open, so FireLast, IdleEmpty '
                       'and ReloadTactical are intentionally null: the last round plays Fire, the empty gun '
                       'idles bolt home and both reloads play Reload. Authored by Scripts/AuthorGunRigs.py.',
    },
    'DA_GunRig_EM21': {
        'Mesh': EM + '/EM_21/SK_EM21', 'clips': em_clips('21'),
        'Stance': 'Rifle', 'HandTargetSocket': 'hand_l_target', 'bGripAtPalm': True,
        'bEjectsPerShot': True, 'EjectDelay': 0.0, 'EjectDirection': (1, 0, .25), 'EjectImpulse': 0.0,
        'CylinderBone': 'None', 'IndexDegrees': 0.0,
        # 34 cm SMG: fallbacks from its own socket bones (import receipt), used only if a socket goes missing.
        'FallbackMuzzle': (28, 0, 6.3), 'FallbackGrip': (0, 0, 0), 'FallbackSupportGrip': (15.8, 0, 3.6),
        'FallbackSight': (1.3, 0, 10.3),
        # Grip seat (MeasureGripSeat.py 2026-10-31): the SMG's stubby grip is 6 cm tall (axis (-0.347, 0, -0.938), 20 deg,
        # 5.0 deep x 2.6 wide, 583 vertices), so the seat point sits 3 cm down it: A (-1.14, 0.01, -2.81); fist wants
        # (10, -13, 2) deg, swing held at 3 deg.
        'GripSeatOffset': (-4.55, 1.58, -2.59), 'GripRotationOffset': (1.89, -2.33, 2.84),
        # 22:00 capture at 0.6 / 0.3 (90 cd): ratio 7.0, saturated 20 %, the whole torso white from the game
        # camera; the sprite alone read 3.3 (a 34 cm gun inside a Ballista-sized flash). 2026-10-31: light 3 cd
        # (0.01) at 150 cm, NS_GunFire burst at 1.5x for the 34 cm gun (see the M4A1 note).
        'MuzzleFlashScale': 1.5, 'MuzzleLightScale': 0.01, 'MuzzleLightRadiusOverride': 150.0,
        'MuzzleFlashOverride': '/Game/ZESP/ZE/FX/Weapon/NS_GunFire',
        'bOverrideMuzzleLightColor': True, 'MuzzleLightColorOverride': (1.0, 0.62, 0.30),
        'TracerOverride': None, 'bTracerOverrideTierColor': True, 'TracerOverrideLifetime': 0.0,
        'Description': 'EM_21 (SMG, 34 cm, charging-handle action): 5 clips; FireLast / IdleEmpty / '
                       'ReloadTactical null. No SMG weapon definition exists yet, so it is keyed to '
                       'DA_Weapon_Rifle_002 (exact) for testing. Authored by Scripts/AuthorGunRigs.py.',
    },
    'DA_GunRig_EM08': {
        'Mesh': EM + '/EM_08/SK_EM08', 'clips': em_clips('08'),
        # Pistol: the body holds DA_HoverPilot.PistolAim (MF_Pistol_Idle_ADS), both hands on the one grip; the
        # rig's grip_l sits at the Pistol aim pose's NATIVE left palm offset from the seated grip_r, (2.0, -8.5, -3.0)
        # cm (design B4, 2026-10-30; was the centre-line (2.5, 0, -3.7), which pulled the left hand 5 cm into the
        # frame), so at aim the support IK is a no-op and the left hand wraps the right as the pose author made it.
        'Stance': 'Pistol', 'HandTargetSocket': 'hand_l_target', 'bGripAtPalm': True,
        'bEjectsPerShot': False, 'EjectDelay': 0.37, 'EjectDirection': (1, 0, .25), 'EjectImpulse': 0.0,
        # Signed like the clips: UE's own A_EM08_Fire/DryFire/Chamber data turns the cylinder +60 deg about its X
        # (ValidateGunClips.py, w >= 0 quaternion convention = FQuat(X, +a)), and AHoverPilot::FinalizeGunPose applies
        # this value about that same axis; the 2026-10-30 capture trace shows every roll step the same way, no snap.
        'CylinderBone': 'cylinder', 'IndexDegrees': 60.0,
        'FallbackMuzzle': (16, 0, 3), 'FallbackGrip': (0, 0, 0), 'FallbackSupportGrip': (4, 0, -6),
        'FallbackSight': (3, 0, 5),
        # Grip seat (MeasureGripSeat.py 2026-10-31): the revolver's grip_r sits at the top FRONT of a 7.2 cm deep, 1.9 wide,
        # 8 cm grip whose axis (-0.324, 0, -0.946; 19 deg) crosses z = 0 at x = -4.3; A (-5.63, 0.02, -3.78); the PISTOL
        # pose's fist (3781 vertices). The fist's bar tilts 12 deg left, so the roll (free: about the barrel) is 15 deg;
        # fist wants (13, -8, 14) deg, swing held at 3 deg.
        'GripSeatOffset': (-9.15, 1.56, -3.49), 'GripRotationOffset': (2.56, -1.56, 15.08),
        # Revolver flash: bright but short (the light keeps the tier's MuzzleLightSeconds).
        # 22:00 capture at 0.7 / 0.35 (105 cd): ratio 5.1 / 7.5 (hands / cylinder camera), saturated 25-37 %;
        # sprite alone 2.6. 2026-10-31: light 3 cd (0.01) at 150 cm, NS_GunFire burst at 1.5x; still
        # bright-but-short (MuzzleLightSeconds unchanged; see the M4A1 note).
        'MuzzleFlashScale': 1.5, 'MuzzleLightScale': 0.01, 'MuzzleLightRadiusOverride': 150.0,
        'MuzzleFlashOverride': '/Game/ZESP/ZE/FX/Weapon/NS_GunFire',
        'bOverrideMuzzleLightColor': True, 'MuzzleLightColorOverride': (1.0, 0.62, 0.30),
        'TracerOverride': None, 'bTracerOverrideTierColor': True, 'TracerOverrideLifetime': 0.0,
        'Description': 'EM_08 (revolver, 30 cm): 5 clips, no magazine. No brass per shot: the spent rounds fall '
                       'together 0.37 s into the Reload clip (rate-scaled to the reload time). The cylinder '
                       'indexes 60 deg per Fire, DryFire and Chamber (GunCylinderAngle). Fallback offsets '
                       'scaled for a 30 cm gun. Authored by Scripts/AuthorGunRigs.py.',
    },
}
# (definition asset, rig, exact key, expected stored key, why)
BINDINGS = [
    (BALLISTA, 'DA_GunRig_M4A1', True, 'DA_AFS_Ballista', "Vexa's starting rifle (DA_NYCWaves StartingWeapons)"),
    (PISTOL, 'DA_GunRig_EM08', False, 'DA_Weapon_Pistol', 'vendor pistol row(s)'),
    (RIFLE1, 'DA_GunRig_EM11', False, 'DA_Weapon_Rifle', 'vendor rifle rows _001.._005'),
    (RIFLE2, 'DA_GunRig_EM21', True, 'DA_Weapon_Rifle_002',
     'no SMG definition exists: one rifle tier shows the SMG for testing'),
]

REPORT = {'ok': False, 'errors': [], 'warnings': [], 'notes': [], 'author': {}, 'verify': {}, 'assertions': [],
          'python_names': {},
          'claim': 'Editor authoring plus a CPU-only -nullrhi PIE of L_NYC_Survival; numbers only, no pixels'}
EA = u.EditorAssetLibrary


def log(*a):
    line = 'GUNRIGS ' + ' '.join(str(x) for x in a)
    print(line, flush=True)
    u.log(line)


def save_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(REPORT, indent=1, default=str))
    except Exception:
        print('GUNRIGS receipt write failed', traceback.format_exc(), flush=True)


def assertion(step, name, ok, measured, expected=None):
    REPORT['assertions'].append({'step': step, 'name': name, 'ok': bool(ok), 'measured': measured,
                                 'expected': expected})
    log('ASSERT', step, name, 'PASS' if ok else 'FAIL', json.dumps(measured, default=str)[:300])
    if not ok:
        REPORT['errors'].append('%s %s failed: %s' % (step, name, json.dumps(measured, default=str)[:400]))


# ---------------------------------------------------------------------------------------------
# Helpers.

def pythonize(cpp):
    name = cpp[1:] if len(cpp) > 1 and cpp[0] == 'b' and cpp[1].isupper() else cpp
    out = name[0].lower()
    for i in range(1, len(name)):
        c, prev = name[i], name[i - 1]
        nxt = name[i + 1] if i + 1 < len(name) else ''
        if c.isupper() and (prev.islower() or prev.isdigit() or (prev.isupper() and nxt.islower())):
            out += '_'
        out += c.lower()
    return out


def pname(holder, cpp, scope):
    key = scope + '.' + cpp
    if key not in REPORT['python_names']:
        name = pythonize(cpp)
        holder.get_editor_property(name)  # raises when the name is wrong
        REPORT['python_names'][key] = name
    return REPORT['python_names'][key]


def pathish(v):
    if v is None:
        return None
    t = v.get_path_name() if hasattr(v, 'get_path_name') else str(v)
    t = t.strip().strip("'\"")
    return t.split('.')[0] if t.startswith('/') else t


def norm(v):
    if v is None:
        return None
    if isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, u.Vector):
        return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]
    if isinstance(v, u.Rotator):
        return [round(v.pitch, 4), round(v.yaw, 4), round(v.roll, 4)]  # (pitch, yaw, roll) like the spec tuples
    if isinstance(v, u.Name):
        return str(v)
    if isinstance(v, u.LinearColor):
        return [round(v.r, 4), round(v.g, 4), round(v.b, 4), round(v.a, 4)]
    if hasattr(v, 'get_path_name'):
        return pathish(v)
    return str(v)


def same(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-3
    return a == b


def sha1(path):
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except Exception as e:
        return 'ERR %s' % e


def content_file(asset_path):
    return PROJECT / 'Content' / (asset_path[len('/Game/'):] + '.uasset')


def vexpr(t):
    return u.Vector(float(t[0]), float(t[1]), float(t[2]))


def rexpr(t):
    """(pitch, yaw, roll) degrees -> unreal.Rotator (whose positional order is roll, pitch, yaw)."""
    return u.Rotator(roll=float(t[2]), pitch=float(t[0]), yaw=float(t[1]))


def load(path):
    if not EA.does_asset_exist(path):
        raise RuntimeError('missing asset ' + path)
    a = EA.load_asset(path)
    if not a:
        raise RuntimeError('failed to load ' + path)
    return a


# ---------------------------------------------------------------------------------------------
# Authoring.

def rig_values(spec):
    vals = {'Mesh': load(spec['Mesh'])}
    for c in CLIP_FIELDS:
        p = spec['clips'].get(c)
        vals[c] = load(p) if p else None
        if vals[c] is not None and not isinstance(vals[c], u.AnimSequence):
            raise RuntimeError('%s is a %s, not an AnimSequence' % (p, vals[c].get_class().get_name()))
    for cpp, default in SOCKET_DEFAULTS.items():
        vals[cpp] = u.Name(default)
    vals['bSocketsDriveOffsets'] = True
    # Design C1 (2026-10-30): per-gun flash / light multipliers (M4A1 1.0 / 0.6, EM_11 0.8 / 0.45, EM_21 0.6 / 0.3,
    # EM_08 0.7 / 0.35) on the tier's 300 cd and the definition's Niagara scale.
    for cpp in ('bEjectsPerShot', 'EjectDelay', 'EjectImpulse', 'IndexDegrees', 'Description', 'MuzzleFlashScale',
                'MuzzleLightScale', 'MuzzleLightRadiusOverride', 'bTracerOverrideTierColor', 'TracerOverrideLifetime'):
        vals[cpp] = spec[cpp]
    vals['CylinderBone'] = u.Name(spec['CylinderBone'])
    for cpp in ('EjectDirection', 'FallbackMuzzle', 'FallbackGrip', 'FallbackSupportGrip', 'FallbackSight'):
        vals[cpp] = vexpr(spec[cpp])
    # Reload-IK fields: the stance enum by NAME (EHoverGunStance is exposed as unreal.HoverGunStance with RIFLE /
    # PISTOL members; norm() renders either side as 'HoverGunStance.PISTOL' for the read-back), the palm-centre
    # bone the Reload clips key for the left hand, and the right-palm grip seat.
    vals['Stance'] = getattr(u.HoverGunStance, spec['Stance'].upper())
    vals['HandTargetSocket'] = u.Name(spec['HandTargetSocket'])
    vals['bGripAtPalm'] = bool(spec['bGripAtPalm'])
    # Grip seat (2026-10-31): where the right palm centre sits from grip_r, and the gun's extra rotation about it.
    vals['GripSeatOffset'] = vexpr(spec['GripSeatOffset'])
    vals['GripRotationOffset'] = rexpr(spec['GripRotationOffset'])
    # Warm flash (2026-10-31): a Niagara system path or None (the definition's flash), and the orange point light.
    ov = spec.get('MuzzleFlashOverride')
    vals['MuzzleFlashOverride'] = load(ov) if ov else None
    if vals['MuzzleFlashOverride'] is not None and not isinstance(vals['MuzzleFlashOverride'], u.NiagaraSystem):
        raise RuntimeError('%s is not a NiagaraSystem' % ov)
    vals['bOverrideMuzzleLightColor'] = bool(spec['bOverrideMuzzleLightColor'])
    c = spec['MuzzleLightColorOverride']
    vals['MuzzleLightColorOverride'] = u.LinearColor(float(c[0]), float(c[1]), float(c[2]), 1.0)
    # Tracer trial fields (2026-10-31): a Niagara trail path or None (the feel tier's tracer stays).
    tr = spec.get('TracerOverride')
    vals['TracerOverride'] = load(tr) if tr else None
    if vals['TracerOverride'] is not None and not isinstance(vals['TracerOverride'], u.NiagaraSystem):
        raise RuntimeError('%s is not a NiagaraSystem' % tr)
    return vals


def author_rig(name, spec, factory, tools):
    path = RIGS + '/' + name
    info = {'path': path}
    if EA.does_asset_exist(path):
        rig = load(path)
        info['state'] = 'existing'
    else:
        rig = tools.create_asset(name, RIGS, u.HoverGunRig, factory)
        if not rig:
            raise RuntimeError('create_asset failed for ' + path)
        info['state'] = 'created'
    if not isinstance(rig, u.HoverGunRig):
        raise RuntimeError('%s is a %s' % (path, rig.get_class().get_name()))
    vals = rig_values(spec)
    changes = []
    for cpp, v in vals.items():
        n = pname(rig, cpp, 'HoverGunRig')
        if not same(norm(rig.get_editor_property(n)), norm(v)):
            rig.set_editor_property(n, v)
            changes.append(cpp)
    info['changes'] = changes
    if changes or info['state'] == 'created' or FORCE_SAVE:
        if not EA.save_loaded_asset(rig, False):
            REPORT['errors'].append('save failed for ' + path)
        info['saved'] = True
        info['forced'] = bool(FORCE_SAVE and not changes and info['state'] != 'created')
    # Read back every field.
    back, bad = {}, []
    for cpp, v in vals.items():
        got = norm(rig.get_editor_property(pname(rig, cpp, 'HoverGunRig')))
        back[cpp] = got
        if not same(got, norm(v)):
            bad.append({'field': cpp, 'expected': norm(v), 'actual': got})
    info['readback'] = back
    info['readback_mismatches'] = bad
    assertion('author', name + ' readback', not bad, {'mismatches': bad, 'fields': len(back)})
    return rig, info


def definition_rows():
    """Every ZE_WeaponDefinition the registry knows, with its spawned class and rig resolution."""
    rows = []
    try:
        reg = u.AssetRegistryHelpers.get_asset_registry()
        assets = reg.get_assets_by_class(u.TopLevelAssetPath('/Script/ZombieEngineStudio', 'ZE_WeaponDefinition'))
    except Exception:
        REPORT['warnings'].append('asset registry query failed: ' + traceback.format_exc(limit=1))
        assets = []
    for a in assets:
        path = str(a.package_name)
        try:
            d = load(path)
            cls = d.get_editor_property('weapon_actor_class')
            rows.append({'path': path, 'name': d.get_name(), 'weapon_type': str(d.get_editor_property('weapon_type')),
                         'actor_class': cls.get_name() if cls else None})
        except Exception:
            rows.append({'path': path, 'error': traceback.format_exc(limit=1)})
    return sorted(rows, key=lambda r: r['path'])


def clip_end_poses():
    """Raw magazine / bolt_carrier deltas on the last frames of the M4A1 one-shot clips (diagnostic)."""
    opts = u.AnimPoseEvaluationOptions()
    for prop_, val in (('evaluation_type', u.AnimDataEvalType.RAW), ('retarget', False),
                       ('extract_root_motion', False)):
        try:
            opts.set_editor_property(prop_, val)
        except Exception:
            pass
    out = {}
    for c in ('Reload', 'ReloadTactical', 'Chamber'):
        seq = load(M4 + '/Anims/A_M4A1_' + c)
        n = u.AnimationLibrary.get_num_frames(seq)
        rows = {}
        for f in (n - 2, n - 1, n):
            pose = u.AnimPoseExtensions.get_anim_pose_at_frame(seq, f, opts)
            row = {}
            for b in ('magazine', 'bolt_carrier'):
                cur = u.AnimPoseExtensions.get_bone_pose(pose, b, u.AnimPoseSpaces.WORLD).translation
                ref = u.AnimPoseExtensions.get_ref_bone_pose(pose, b, u.AnimPoseSpaces.WORLD).translation
                row[b] = [round(cur.x - ref.x, 3), round(cur.y - ref.y, 3), round(cur.z - ref.z, 3)]
            rows['f%d' % f] = row
        out[c] = rows
    return out


def author():
    A = REPORT['author']
    tools = u.AssetToolsHelpers.get_asset_tools()
    factory = u.DataAssetFactory()
    factory.set_editor_property('data_asset_class', u.HoverGunRig.static_class())
    rigs = {}
    A['rigs'] = {}
    for name, spec in RIG_SPECS.items():
        rig, info = author_rig(name, spec, factory, tools)
        rigs[name] = rig
        A['rigs'][name] = info
    da = load(DA_PATH)
    A['da'] = {'path': DA_PATH, 'class': da.get_class().get_name()}
    loose = {}
    for cpp in ('RiggedGun', 'GunIdle', 'GunFire', 'GunDryFire', 'GunReload', 'GunChamber'):
        loose[cpp] = norm(da.get_editor_property(pname(da, cpp, 'HoverPilotAssets')))
    A['da']['loose_before'] = loose
    field = pname(da, 'GunRigs', 'HoverPilotAssets')
    current = {str(k): pathish(v) for k, v in da.get_editor_property(field).items()}
    A['da']['gun_rigs_before'] = current
    binds = []
    for def_path, rig_name, exact, want_key, why in BINDINGS:
        d = load(def_path)
        key = want_key
        rig_path = RIGS + '/' + rig_name
        row = {'definition': def_path, 'definition_name': d.get_name(), 'rig': rig_path, 'exact': exact,
               'expected_key': want_key, 'why': why,
               'normalized': str(u.HoverGunRig.normalize_weapon_key(u.Name(d.get_name())))}
        if current.get(key) == rig_path:
            row['state'] = 'already bound'
            row['stored_key'] = key
        else:
            stored = u.HoverAuthoring.bind_gun_rig(da, u.Name(d.get_name()), rigs[rig_name], exact)
            row['state'] = 'bound'
            row['stored_key'] = str(stored)
        binds.append(row)
        assertion('author', 'bind %s' % d.get_name(), row['stored_key'] == want_key,
                  {'stored_key': row['stored_key'], 'state': row['state']}, want_key)
    A['bindings'] = binds
    if any(b['state'] == 'bound' for b in binds):
        if not EA.save_loaded_asset(da, False):
            REPORT['errors'].append('save failed for ' + DA_PATH)
        A['da']['saved'] = True
    after = {str(k): pathish(v) for k, v in da.get_editor_property(field).items()}
    A['da']['gun_rigs'] = after
    want = {b[3]: RIGS + '/' + b[1] for b in BINDINGS}
    assertion('author', 'DA_HoverPilot.gun_rigs readback', all(after.get(k) == v for k, v in want.items()),
              after, want)
    loose_after = {cpp: norm(da.get_editor_property(pname(da, cpp, 'HoverPilotAssets'))) for cpp in loose}
    A['da']['loose_after'] = loose_after
    assertion('author', 'loose M4A1 default rig intact', loose_after == loose and
              loose_after.get('RiggedGun') == M4 + '/SK_M4A1', loose_after)
    # Which rig each definition resolves to (AHoverPilot::FindGunRig: exact key, then normalized).
    rows = definition_rows()
    for r in rows:
        if 'name' not in r:
            continue
        key = r['name'] if r['name'] in after else str(u.HoverGunRig.normalize_weapon_key(u.Name(r['name'])))
        r['rig'] = after.get(key, '(default: DA loose fields)')
        r['rig_shows_in_game'] = r['actor_class'] == 'HoverCyberRifle'
    A['definitions'] = rows
    vendor = [r['name'] for r in rows if r.get('name') and r.get('actor_class') != 'HoverCyberRifle'
              and any(k in r.get('weapon_type', '').upper() for k in ('RIFLE', 'PISTOL'))]
    if vendor:
        REPORT['notes'].append('These definitions spawn a vendor BP_Weapon_* actor (plain AZE_WeaponBase), which '
                               'never calls AHoverPilot::ApplyGunRig, so their GunRigs keys take effect only once '
                               'their WeaponActorClass is HoverCyberRifle (an owned DA_NYC_* definition): %s'
                               % vendor)
    smg = [r for r in rows if 'smg' in (r.get('name') or '').lower()]
    A['smg_definitions'] = smg
    if not smg:
        REPORT['notes'].append('No SMG weapon definition exists (EZE_WeaponType has only Rifle/Pistol/Melee/Bomb and '
                               'no DA_*SMG* asset); DA_GunRig_EM21 is keyed to DA_Weapon_Rifle_002 (exact) so one '
                               'rifle tier shows the SMG for testing')
    try:
        A['m4a1_clip_end_poses'] = clip_end_poses()
    except Exception:
        A['m4a1_clip_end_poses'] = traceback.format_exc(limit=2)
    log('author done', {k: v['state'] for k, v in A['rigs'].items()}, after)


# ---------------------------------------------------------------------------------------------
# Verify (PIE, slate post-tick state machine; one step per world tick).

TIMEOUT = 540.0
COMP = u.RelativeTransformSpace.RTS_COMPONENT
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'done': False, 'pc': None,
     'last_t': None, 'phase': 'boot', 'pt': None, 'hp': [], 'zombies_removed': 0, 'shells_seen': set(),
     'shell_log': [], 'pistol_class': None}
V = REPORT['verify']


def prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            return getattr(obj, name)
        except Exception:
            return None


def world():
    return u.HoverAuthoring.get_playtest_world()


def gun(p):
    return prop(p, 'world_gun_skel')


def weapon(p):
    c = prop(p, 'combat')
    return c.get_weapon() if c else None


def bone(p, name):
    g = gun(p)
    try:
        t = g.get_socket_transform(name, COMP).translation
        return [t.x, t.y, t.z]
    except Exception:
        return None


def mesh_loc(p, name):
    try:
        v = p.mesh.get_socket_location(name)
        return [v.x, v.y, v.z]
    except Exception:
        return None


def palm_l(p):
    """Left palm centre (world cm): midpoint of hand_l and middle_01_l, the point the support IK places."""
    a, b = mesh_loc(p, 'hand_l'), mesh_loc(p, 'middle_01_l')
    return [(a[i] + b[i]) * 0.5 for i in range(3)] if a and b else None


def gun_world(p, name):
    """World location of a socket/bone on the held gun, None when the rig lacks it."""
    g = gun(p)
    try:
        if not g.does_socket_exist(name):
            return None
        v = g.get_socket_location(name)
        return [v.x, v.y, v.z]
    except Exception:
        return None


def dist(a, b):
    return round(math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))), 2) if a and b else None


def hand_r_quat(p):
    try:
        q = p.mesh.get_socket_rotation('hand_r').quaternion()
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return None


def quat_deg(a, b):
    if not a or not b:
        return None
    d = abs(sum(a[i] * b[i] for i in range(4)))
    return round(math.degrees(2.0 * math.acos(min(1.0, d))), 2)


def socket_quat(p, name):
    try:
        q = p.mesh.get_socket_rotation(name).quaternion()
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return None


def gun_quat(p):
    try:
        q = gun(p).get_world_transform().rotation
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return None


def target_rot_gun(p):
    """hand_l_target's rotation in gun (component) space: the clip's keyed delta (identity at rest)."""
    try:
        g = gun(p)
        if not g.does_socket_exist('hand_l_target'):
            return None
        q = g.get_socket_transform('hand_l_target', COMP).rotation
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return None


def q_mul(a, b):
    """UE FQuat a*b: rotate by b first, then a."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def q_inv(q):
    return [-q[0], -q[1], -q[2], q[3]]


def q_rotate(q, v):
    """FQuat::RotateVector: T = 2 * cross(Q.xyz, V); V + W * T + cross(Q.xyz, T)."""
    qx, qy, qz, qw = q
    tx, ty, tz = 2.0 * (qy * v[2] - qz * v[1]), 2.0 * (qz * v[0] - qx * v[2]), 2.0 * (qx * v[1] - qy * v[0])
    return [v[0] + qw * tx + (qy * tz - qz * ty), v[1] + qw * ty + (qz * tx - qx * tz), v[2] + qw * tz + (qx * ty - qy * tx)]


def hand_sample(p):
    """One tick of reload hands: palm -> hand_l_target, palm -> grip_l, wrist -> grip_l (cm), hand_r world quat, and
    (design B7) hand_l's world quat, the gun's world quat and hand_l_target's gun-space rotation delta."""
    palm = palm_l(p)
    return {'palm_to_target_cm': dist(palm, gun_world(p, 'hand_l_target')),
            'palm_to_grip_l_cm': dist(palm, gun_world(p, 'grip_l')),
            'wrist_to_grip_l_cm': dist(mesh_loc(p, 'hand_l'), gun_world(p, 'grip_l')),
            'palm_r_to_seat_cm': dist(palm_r(p), seat_world(p)),
            'hand_r_q': hand_r_quat(p), 'hand_l_q': socket_quat(p, 'hand_l'), 'gun_q': gun_quat(p),
            'target_rot_gun_q': target_rot_gun(p)}


def bones_under(p, root):
    """Names of every bone under root on the body mesh (Vexa: thumb/index/middle/ring/pinky *_01/_02/_03_r and the
    *_metacarpal_r bones under hand_r), in skeleton order."""
    m = p.mesh
    out = []
    for i in range(m.get_num_bones()):
        name = m.get_bone_name(i)
        q = name
        while True:
            q = m.get_parent_bone(q)
            if q is None or str(q) in ('', 'None'):
                break
            if str(q) == root:
                out.append(str(name))
                break
    return out


def local_quats(p, names):
    """Parent-relative rotation of each named bone (q_parent^-1 * q_bone, from the world socket rotations)."""
    out = {}
    for n in names:
        par = p.mesh.get_parent_bone(n)
        a, b = socket_quat(p, str(par)), socket_quat(p, n)
        if a and b:
            out[n] = q_mul(q_inv(a), b)
    return out


def pilot_quat(p, name):
    try:
        q = p.get_editor_property(name)
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return None


def mesh_quat(p):
    try:
        q = p.mesh.get_world_transform().rotation
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return None


def palm_r(p):
    """Right palm centre (world cm): midpoint of hand_r and middle_01_r, where a bGripAtPalm rig seats its grip seat."""
    a, b = mesh_loc(p, 'hand_r'), mesh_loc(p, 'middle_01_r')
    return [(a[i] + b[i]) * 0.5 for i in range(3)] if a and b else None


def seat_world(p):
    """The held rig's grip seat (grip_r + GripSeatOffset, gun space) in world cm: what UpdateGunTransform puts at the
    right palm centre. The gun component's own transform has scale 1 (the x100 sits on the root bone)."""
    try:
        g = gun(p)
        rig = p.get_gun_rig()
        if not g or not rig or not g.does_socket_exist('grip_r'):
            return None
        grip = g.get_socket_transform('grip_r', u.RelativeTransformSpace.RTS_COMPONENT).translation
        off = rig.get_editor_property('grip_seat_offset')
        w = g.get_world_transform().transform_location(u.Vector(grip.x + off.x, grip.y + off.y, grip.z + off.z))
        return [w.x, w.y, w.z]
    except Exception:
        return None


def rig_rot_q(p):
    """The held rig's GripRotationOffset as a quaternion [x, y, z, w] (identity when unreadable)."""
    try:
        q = p.get_gun_rig().get_editor_property('grip_rotation_offset').quaternion()
        return [q.x, q.y, q.z, q.w]
    except Exception:
        return [0.0, 0.0, 0.0, 1.0]


def rest_muzzle_check(step, label, p):
    """Grip seat (2026-10-31): at rest the drawn barrel (the gun component's X) must stay within 6 deg of the aim ray
    (GunAimWorldRotation's X: the aim-only rotation, before the hand kick and the rig's GripRotationOffset) and of the
    camera's control rotation. The deviation IS the rig's swing (pitch/yaw part of GripRotationOffset), 3 deg by design."""
    gq, aq = gun_quat(p), pilot_quat(p, 'gun_aim_world_rotation')
    try:
        cr = S['pc'].get_control_rotation().quaternion()
        cq = [cr.x, cr.y, cr.z, cr.w]
    except Exception:
        cq = None
    fwd = lambda q: q_rotate(q, [1.0, 0.0, 0.0]) if q else None
    ang = lambda a, b: round(math.degrees(math.acos(max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3)))))), 2) if a and b else None
    out = {'barrel_vs_aim_ray_deg': ang(fwd(gq), fwd(aq)), 'barrel_vs_control_rotation_deg': ang(fwd(gq), fwd(cq)),
           'kick_deg': prop(p, 'gun_hand_kick_deg'), 'rig_rot_q': rig_rot_q(p),
           'rig_rot_deg': round(2.0 * math.degrees(math.acos(min(1.0, abs(rig_rot_q(p)[3])))), 2)}
    assertion(step, '%s: muzzle direction within 6 deg of the aim ray and of the control rotation' % label,
              out['barrel_vs_aim_ray_deg'] is not None and out['barrel_vs_aim_ray_deg'] <= 6.0 and
              out['barrel_vs_control_rotation_deg'] is not None and out['barrel_vs_control_rotation_deg'] <= 6.0, out, '<= 6 deg')
    return out


def fire_sample(p):
    """One tick of a burst (design A3): left palm -> hand_l_target (cm), the palm's position along the gun against the
    muzzle, whether a driver montage is playing, spine_03's world quat (the stance additive's kick), ammo, clip.
    Gun-rides-the-hand (2026-10-30 23:30): the right palm -> grip_r distance, hand_r's and the body mesh's world quats
    (hand_r in component space = mesh^-1 * hand_r), the gun's world quat, the pilot's exposed kick (GunHandKick,
    component space), its angle, the aim-ray-only world rotation (GunAimWorldRotation) and the rest flag, plus the
    parent-relative rotation of every bone under hand_r (the grip shape the additive must not touch)."""
    g = gun(p)
    palm = palm_l(p)
    grip_r = gun_world(p, 'grip_r')
    mz = bone(p, 'muzzle')
    if S.get('r_fingers') is None:
        S['r_fingers'] = bones_under(p, 'hand_r')
    along = None
    try:
        fwd = g.get_forward_vector()
        if palm and grip_r:
            along = sum((palm[i] - grip_r[i]) * f for i, f in enumerate((fwd.x, fwd.y, fwd.z)))
    except Exception:
        pass
    act = None
    try:
        lb = prop(p, 'locomotion_bridge')
        act = bool(lb.is_action_playing()) if lb else None
    except Exception:
        pass
    return {'palm_to_target_cm': dist(palm, gun_world(p, 'hand_l_target')),
            'palm_along_gun_cm': round(along, 2) if along is not None else None,
            'muzzle_x_cm': round(mz[0], 2) if mz else None,
            'palm_ahead_of_muzzle': (along > mz[0] - 3.0) if along is not None and mz else None,
            'action_playing': act, 'spine_03_q': socket_quat(p, 'spine_03'), 'head_q': socket_quat(p, 'head'),
            'ammo': ammo(p), 'clip': clip_name(p),
            'palm_r_to_grip_r_cm': dist(palm_r(p), grip_r),
            'palm_r_to_seat_cm': dist(palm_r(p), seat_world(p)), 'rig_rot_q': rig_rot_q(p),
            'hand_r_q': hand_r_quat(p), 'mesh_q': mesh_quat(p), 'gun_q': gun_quat(p),
            'kick_q': pilot_quat(p, 'gun_hand_kick'), 'kick_deg': prop(p, 'gun_hand_kick_deg'),
            'aim_q': pilot_quat(p, 'gun_aim_world_rotation'), 'rest_valid': prop(p, 'gun_hand_rest_valid'),
            'splay_deg': anim_prop(p, 'stance_fire_finger_splay_deg'),
            'r_fingers': local_quats(p, S['r_fingers'])}


def anim_prop(p, name):
    try:
        return prop(p.mesh.get_anim_instance(), name)
    except Exception:
        return None


def finger_drift(rows, base):
    """Per-bone max angle of each row's finger locals from base's, and the largest tick-to-tick change."""
    worst, rate, prev = {}, 0.0, None
    for r in rows:
        f = r.get('r_fingers') or {}
        for n, q in f.items():
            q0 = (base.get('r_fingers') or {}).get(n)
            if q0:
                worst[n] = max(worst.get(n, 0.0), quat_deg(q0, q))
            if prev and prev.get(n):
                rate = max(rate, quat_deg(prev[n], q))
        prev = f
    return worst, rate


def q_cs(mesh_q, world_q):
    """A world rotation in the body mesh's component space."""
    return q_mul(q_inv(mesh_q), world_q) if mesh_q and world_q else None


def ride_assertions(step, label, rows, base, require_kick, quiet=None):
    """Gun-rides-the-hand (owner 2026-10-30 23:30, "her hand is not on the grip"), on EVERY tick of the burst:
    (a) the right palm (midpoint hand_r / middle_01_r) within 0.5 cm of the grip SEAT, grip_r + the rig's
        GripSeatOffset (2026-10-31; the palm-to-grip_r distance is still recorded: it is now the seat offset's length);
    (b) the angle between hand_r's component-space delta from the pre-press tick and the pilot's applied gun kick
        (GunHandKick, component space) < 3 deg, and the gun's actual world rotation == mesh * kick * mesh^-1 * the
        aim-ray rotation * the rig's GripRotationOffset within 1 deg (the exposed kick is what sits on the component);
    (c) every bone under hand_r keeps its aim-pose parent-relative rotation: the aim LOOP itself moves the fingers
        slowly (1-2 deg over a second, measured in `quiet`, the same loop sampled for as long with no shot), so the
        burst's drift from the pre-press tick must stay within max(1 deg, 1.5 x the quiet drift + 0.5), its
        tick-to-tick change under 1 deg (the kick moves hand_r up to 15 deg in a tick; splayed fingers would move
        alike), and the hold must have had work to do: the node's removed splay peaks >= 2 deg;
    (d) the kick itself still happens: max hand_r delta >= 2 deg when require_kick (the rifle additive)."""
    out = {}
    if not rows or not base.get('hand_r_q') or not base.get('mesh_q'):
        for name in ('right palm within 0.5 cm of the grip seat', 'gun kick follows hand_r', 'fingers hold', 'hand_r kicks'):
            assertion(step, '%s: %s' % (label, name), False, 'no hand_r / mesh samples')
        return out
    h0 = q_cs(base['mesh_q'], base['hand_r_q'])
    palm = [r['palm_r_to_seat_cm'] for r in rows if r.get('palm_r_to_seat_cm') is not None]
    palm_grip = [r['palm_r_to_grip_r_cm'] for r in rows if r.get('palm_r_to_grip_r_cm') is not None]
    hand_deg, follow, actual, fingers, rest = [], [], [], {}, 0
    for r in rows:
        h = q_cs(r.get('mesh_q'), r.get('hand_r_q'))
        if not h:
            continue
        hd = q_mul(h, q_inv(h0))
        hand_deg.append(quat_deg([0.0, 0.0, 0.0, 1.0], hd))
        if r.get('kick_q'):
            follow.append(quat_deg(hd, r['kick_q']))
        if r.get('kick_q') and r.get('aim_q') and r.get('gun_q') and r.get('mesh_q'):
            m = r['mesh_q']
            want = q_mul(q_mul(q_mul(q_mul(m, r['kick_q']), q_inv(m)), r['aim_q']), r.get('rig_rot_q') or [0.0, 0.0, 0.0, 1.0])
            actual.append(quat_deg(want, r['gun_q']))
        rest += 1 if r.get('rest_valid') else 0
    fingers, rate = finger_drift(rows, base)
    quiet_worst, quiet_rate = finger_drift(quiet or [], (quiet or [{}])[0])
    quiet_max = max(quiet_worst.values()) if quiet_worst else None
    splay = [r['splay_deg'] for r in rows if r.get('splay_deg') is not None]
    out.update({'ticks': len(rows), 'ticks_rest_valid': rest,
                'quiet_ticks': len(quiet or []), 'quiet_finger_drift_max_deg': quiet_max,
                'quiet_finger_rate_max_deg_per_tick': quiet_rate if quiet else None,
                'finger_rate_max_deg_per_tick': rate, 'removed_splay_peak_deg': max(splay) if splay else None,
                'removed_splay_ticks': sum(1 for s in splay if s > 0.5),
                'palm_r_to_seat_max_cm': max(palm) if palm else None,
                'palm_r_to_grip_r_max_cm': max(palm_grip) if palm_grip else None,
                'palm_r_to_grip_r_min_cm': min(palm_grip) if palm_grip else None,
                'hand_r_kick_max_deg': max(hand_deg) if hand_deg else None,
                'gun_kick_vs_hand_max_deg': max(follow) if follow else None, 'kick_ticks': len(follow),
                'gun_actual_vs_exposed_max_deg': max(actual) if actual else None,
                'pilot_kick_deg_max': max((r['kick_deg'] for r in rows if r.get('kick_deg') is not None), default=None),
                'finger_bones': len(fingers), 'finger_hold_max_deg': max(fingers.values()) if fingers else None,
                'finger_hold_worst': sorted(fingers.items(), key=lambda kv: -kv[1])[:5]})
    assertion(step, '%s: right palm within 0.5 cm of the grip seat (grip_r + GripSeatOffset) on every tick' % label,
              bool(palm) and out['palm_r_to_seat_max_cm'] <= 0.5,
              {'max_cm': out['palm_r_to_seat_max_cm'], 'ticks': len(palm), 'palm_to_grip_r_cm': [out['palm_r_to_grip_r_min_cm'], out['palm_r_to_grip_r_max_cm']]},
              '<= 0.5 cm')
    assertion(step, '%s: gun kick follows hand_r (component-space delta vs GunHandKick < 3 deg, every tick)' % label,
              bool(follow) and len(follow) == len(hand_deg) and rest == len(rows) and out['gun_kick_vs_hand_max_deg'] < 3.0,
              {k: out[k] for k in ('gun_kick_vs_hand_max_deg', 'kick_ticks', 'ticks', 'ticks_rest_valid')},
              '< 3 deg on every tick, rest cached throughout')
    assertion(step, '%s: gun world rotation == mesh * kick * mesh^-1 * aim ray * GripRotationOffset (< 1 deg, every tick)' % label,
              bool(actual) and len(actual) == len(rows) and out['gun_actual_vs_exposed_max_deg'] < 1.0,
              {'max_deg': out['gun_actual_vs_exposed_max_deg'], 'ticks': len(actual)}, '< 1 deg')
    bound = max(1.0, 1.5 * quiet_max + 0.5) if quiet_max is not None else 1.0
    assertion(step, '%s: every bone under hand_r keeps its aim-pose local rotation through the shots' % label,
              bool(fingers) and out['finger_hold_max_deg'] <= bound and rate < 1.0,
              {k: out[k] for k in ('finger_bones', 'finger_hold_max_deg', 'finger_hold_worst', 'finger_rate_max_deg_per_tick',
                                   'quiet_finger_drift_max_deg', 'quiet_finger_rate_max_deg_per_tick', 'quiet_ticks')},
              '<= max(1 deg, 1.5 x quiet loop drift + 0.5) = %.2f deg from the pre-press tick, < 1 deg per tick' % bound)
    assertion(step, '%s: the hold had work to do (additive finger splay removed, peak >= 2 deg)' % label,
              bool(splay) and out['removed_splay_peak_deg'] >= 2.0,
              {k: out[k] for k in ('removed_splay_peak_deg', 'removed_splay_ticks')}, '>= 2 deg')
    if require_kick:
        assertion(step, '%s: hand_r kicks (max delta >= 2 deg)' % label,
                  out['hand_r_kick_max_deg'] is not None and out['hand_r_kick_max_deg'] >= 2.0,
                  {'hand_r_kick_max_deg': out['hand_r_kick_max_deg'], 'pilot_kick_deg_max': out['pilot_kick_deg_max']},
                  '>= 2 deg')
    return out


def burst_assertions(step, label, rows, base, want_shots, kick_range=(2.0, 10.0), quiet=None):
    """Design A3: through the shots the left palm stays within 4 cm of hand_l_target on EVERY tick and never ahead of
    the muzzle (dot(palm - grip_r, gun forward) < muzzle.x - 3 cm); no TPFireAction montage on the driver; the stance
    additive's upper-body kick (spine_03 / head peak vs the pre-press tick) must sit in kick_range: the rifle additive
    (MA_Rifle_Fire_Add) kicks spine_03 about 2.6 deg, the pistol one (MA_Pistol_Fire_Add) moves the arms and the head
    (about 2.5 deg) more than the spine (about 1 deg), so the EM_08 range starts lower."""
    dists = [r['palm_to_target_cm'] for r in rows if r['palm_to_target_cm'] is not None]
    ahead = [r for r in rows if r['palm_ahead_of_muzzle']]
    acts = [r for r in rows if r['action_playing']]
    kicks = [max(quat_deg(base['spine_03_q'], r['spine_03_q']), quat_deg(base['head_q'], r['head_q']))
             for r in rows if r['spine_03_q'] and base.get('spine_03_q') and r['head_q'] and base.get('head_q')]
    fired = (base['ammo'] - rows[-1]['ammo']) if base.get('ammo') is not None and rows[-1]['ammo'] is not None else None
    out = {'ticks': len(rows), 'shots_fired': fired, 'palm_to_target_max_cm': max(dists) if dists else None,
           'ticks_palm_ahead_of_muzzle': len(ahead), 'muzzle_x_cm': rows[0]['muzzle_x_cm'],
           'palm_along_gun_max_cm': max((r['palm_along_gun_cm'] for r in rows if r['palm_along_gun_cm'] is not None),
                                        default=None),
           'ticks_action_playing': len(acts), 'action_playing_readable': all(r['action_playing'] is not None for r in rows),
           'upper_body_kick_peak_deg': max(kicks) if kicks else None,
           'spine_03_kick_peak_deg': max((quat_deg(base['spine_03_q'], r['spine_03_q']) for r in rows
                                          if r['spine_03_q'] and base.get('spine_03_q')), default=None),
           'head_kick_peak_deg': max((quat_deg(base['head_q'], r['head_q']) for r in rows
                                      if r['head_q'] and base.get('head_q')), default=None),
           'clips_seen': sorted(set(r['clip'] for r in rows if r['clip']))}
    assertion(step, '%s: %d rounds fired' % (label, want_shots), fired == want_shots, fired, want_shots)
    assertion(step, '%s: left palm within 4 cm of hand_l_target on every tick' % label,
              bool(dists) and out['palm_to_target_max_cm'] <= 4.0,
              {'max_cm': out['palm_to_target_max_cm'], 'ticks': len(dists)}, '<= 4 cm')
    assertion(step, '%s: left palm never ahead of the muzzle' % label, not ahead,
              {k: out[k] for k in ('ticks_palm_ahead_of_muzzle', 'palm_along_gun_max_cm', 'muzzle_x_cm')},
              'dot(palm - grip_r, fwd) < muzzle.x - 3 cm on every tick')
    assertion(step, '%s: no driver montage (LocomotionBridge.IsActionPlaying false throughout)' % label,
              out['action_playing_readable'] and not acts, {'ticks_action_playing': len(acts), 'ticks': len(rows)})
    assertion(step, '%s: stance fire additive kicks the upper body (spine_03 / head peak %s-%s deg)' % (
        label, kick_range[0], kick_range[1]),
              out['upper_body_kick_peak_deg'] is not None and kick_range[0] <= out['upper_body_kick_peak_deg'] <= kick_range[1],
              {k: out[k] for k in ('upper_body_kick_peak_deg', 'spine_03_kick_peak_deg', 'head_kick_peak_deg')},
              '%s-%s deg' % kick_range)
    out['ride'] = ride_assertions(step, label, rows, base, require_kick=kick_range[0] >= 2.0, quiet=quiet)
    return out


def marks_of(tr, k, marks):
    """Palm -> hand_l_target at each clip mark (clip s x k = game s), from the nearest tick within 0.05 s."""
    out = {}
    for mark in marks:
        want = mark * k
        rows = [r for r in tr if abs(r[0] - want) <= 0.05]
        row = min(rows, key=lambda r: abs(r[0] - want)) if rows else None
        out[str(mark)] = {'clip_s': mark, 'game_s': round(row[0], 3) if row else None,
                          'palm_to_target_cm': row[1]['palm_to_target_cm'] if row else None,
                          'palm_to_grip_l_cm': row[1]['palm_to_grip_l_cm'] if row else None}
    return out


def hand_assertions(step, label, tr, k, marks, D, aim_before, rot_marks=()):
    """Design item 8. tr rows: (game s since reload start, hand_sample dict). The body keeps its aim pose and the
    support IK follows the gun's hand_l_target, so the palm must sit on that socket at the clip marks (6 cm), the
    gun hand must not turn (< 12 deg from the start to 1.2 s; the aim ray is fixed, the aim loop sways a little),
    and before the reload the palm must already be on grip_l (6 cm), which hand_l_target equals at rest.
    Design B7 (rot_marks): hand_l's rotation relative to the gun (gun_q^-1 * hand_l_q) at each mark equals the clip's
    delta (hand_l_target's gun-space rotation on that tick) applied to the pre-reload relative rotation, within 15
    deg. With unkeyed clips (identity delta) this says the hand keeps its aim-pose orientation through the reload."""
    out = {'marks': marks_of(tr, k, marks), 'aim_before': aim_before, 'ticks': len(tr)}
    for mark, row in out['marks'].items():
        ok = row['palm_to_target_cm'] is not None and row['palm_to_target_cm'] <= 6.0
        assertion(step, '%s: left palm within 6 cm of hand_l_target at %s s (clip)' % (label, mark), ok, row,
                  '<= 6 cm; None = no hand_l_target socket on the rig or no tick near the mark')
    rot = out['rotation'] = {}
    r0 = (q_mul(q_inv(aim_before['gun_q']), aim_before['hand_l_q'])
          if aim_before and aim_before.get('gun_q') and aim_before.get('hand_l_q') else None)
    for mark in rot_marks:
        want = mark * k
        rows = [r for r in tr if abs(r[0] - want) <= 0.05 and r[1].get('hand_l_q') and r[1].get('gun_q')]
        row = min(rows, key=lambda r: abs(r[0] - want)) if rows else None
        entry = {'clip_s': mark, 'game_s': round(row[0], 3) if row else None}
        if row and r0:
            s = row[1]
            rel = q_mul(q_inv(s['gun_q']), s['hand_l_q'])
            delta = s.get('target_rot_gun_q') or [0.0, 0.0, 0.0, 1.0]
            expect = q_mul(delta, r0)
            entry.update({'clip_delta_deg': quat_deg([0.0, 0.0, 0.0, 1.0], delta),
                          'hand_l_vs_expected_deg': quat_deg(rel, expect),
                          'hand_l_vs_pre_reload_deg': quat_deg(rel, r0)})
        rot[str(mark)] = entry
        assertion(step, '%s: hand_l rotation vs gun == clip delta x pre-reload rotation at %s s (< 15 deg)' % (label, mark),
                  entry.get('hand_l_vs_expected_deg') is not None and entry['hand_l_vs_expected_deg'] < 15.0, entry,
                  '< 15 deg')
    q0 = next((r[1]['hand_r_q'] for r in tr if r[1]['hand_r_q']), None)
    until = min(1.2, D)
    window = [r for r in tr if r[0] <= until + 1e-3 and r[1]['hand_r_q']]
    end_row = min(window, key=lambda r: abs(r[0] - until)) if window else None
    out['hand_r'] = {'deg_at_window_end': quat_deg(q0, end_row[1]['hand_r_q']) if end_row else None,
                     'deg_max_in_window': max((quat_deg(q0, r[1]['hand_r_q']) for r in window), default=None),
                     'window_s': round(until, 3)}
    assertion(step, '%s: gun hand (hand_r) turns < 12 deg from reload start to 1.2 s' % label,
              out['hand_r']['deg_at_window_end'] is not None and out['hand_r']['deg_at_window_end'] < 12.0,
              out['hand_r'], '< 12 deg')
    # Grip seat (2026-10-31): the right palm never leaves the seat through the reload either.
    seat = [r[1]['palm_r_to_seat_cm'] for r in tr if r[1].get('palm_r_to_seat_cm') is not None]
    out['palm_r_to_seat'] = {'max_cm': max(seat) if seat else None, 'ticks': len(seat)}
    assertion(step, '%s: right palm within 0.5 cm of the grip seat on every reload tick' % label,
              bool(seat) and out['palm_r_to_seat']['max_cm'] <= 0.5, out['palm_r_to_seat'], '<= 0.5 cm')
    ok_aim = bool(aim_before) and aim_before.get('palm_to_grip_l_cm') is not None and \
        aim_before['palm_to_grip_l_cm'] <= 6.0
    assertion(step, '%s: left palm within 6 cm of grip_l while aiming before the reload' % label, ok_aim,
              aim_before, '<= 6 cm')
    return out


def clip_name(p):
    try:
        inst = gun(p).get_anim_instance()
        a = inst.get_animation_asset() if inst else None
        return a.get_name() if a else None
    except Exception:
        return None


def clip_time(p):
    try:
        return round(gun(p).get_position(), 4)
    except Exception:
        return None


def rig_name(p):
    r = p.get_gun_rig()
    return r.get_name() if r else None


def mesh_name(p):
    g = gun(p)
    try:
        m = g.get_skeletal_mesh_asset()
    except Exception:
        m = prop(g, 'skeletal_mesh_asset')
    return m.get_name() if m else None


def ammo(p):
    w = weapon(p)
    return w.get_current_clip_ammo() if w else None


def press(down):
    u.HoverAuthoring.test_key(S['pc'], 'LeftMouseButton', 1.0 if down else 0.0, False)


def delta(cur, rest):
    return [round(cur[i] - rest[i], 3) for i in range(3)] if cur and rest else None


def shells(w, p):
    """New brass since the last call: StaticMeshActors owned by the held weapon (EjectRigShellAt)."""
    rifle = weapon(p)
    if not rifle:
        return 0
    n = 0
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.StaticMeshActor):
        if a.get_owner() == rifle:
            key = a.get_name()
            if key not in S['shells_seen']:
                S['shells_seen'].add(key)
                n += 1
    return n


def clear_zombies(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if not cls:
        return
    for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
        z.destroy_actor()
        S['zombies_removed'] += 1


def definition_facts(d):
    cs = prop(d, 'combat_stats')
    shell = prop(d, 'bullet_shell_mesh')
    cls = prop(d, 'weapon_actor_class')
    return {'name': d.get_name(), 'automatic': prop(d, 'automatic'), 'fire_rate': prop(d, 'fire_rate'),
            'magazine': prop(d, 'magazine_size'), 'reload_time': prop(cs, 'reload_time') if cs else None,
            'shells_per_shot': prop(d, 'shells_per_shot'), 'shell_mesh': str(shell) if shell else None,
            'shell_lifetime': prop(d, 'shell_life_time'), 'actor_class': cls.get_name() if cls else None}


def new_phase(name, t, **kw):
    S['phase'] = name
    S['pt'] = t
    S.update(kw)
    log('phase', name, 't=%.3f' % t)


def rest_of(p):
    return {'bolt': bone(p, 'bolt_carrier'), 'mag': bone(p, 'magazine')}


# Phase handlers. Each gets (w, p, t, el) with el = seconds since the phase began; returns nothing.

def ph_boot(w, p, t, el):
    rifle = weapon(p)
    if rifle and rig_name(p) == 'DA_GunRig_M4A1' and el >= 2.5:
        d = rifle.get_weapon_definition()
        V['a'] = {'rig': rig_name(p), 'mesh': mesh_name(p), 'rigged': p.uses_rigged_gun(), 'weapon':
                  rifle.get_class().get_name(), 'definition': definition_facts(d), 'clip_ammo': ammo(p),
                  'hp': p.get_health(), 'clip': clip_name(p)}
        assertion('a', 'equip rig/mesh (live)', V['a']['rig'] == 'DA_GunRig_M4A1' and V['a']['mesh'] == 'SK_M4A1'
                  and V['a']['rigged'], V['a'])
        S['def_m4'] = d
        S['rest'] = rest_of(p)
        V['rest_m4'] = S['rest']
        new_phase('single', t, shot=0, trace=[], shot_t=None, shot_ammo=None, shot_shells=0)
    elif el > 20:
        raise RuntimeError('boot: rig never became DA_GunRig_M4A1 (rig=%s weapon=%s)' % (rig_name(p), rifle))


def ph_single(w, p, t, el):
    """(b) three single shots, 0.5 s apart; bolt rearward then home after each."""
    if S['shot_t'] is None:
        if el >= 0.1:
            if S['shot'] == 0:
                V['b_rest_muzzle'] = rest_muzzle_check('b', 'M4A1 at rest before the first shot', p)
            S['shot_ammo'] = ammo(p)
            S['trace'] = []
            S['shot_shells'] = 0
            press(True)
            S['shot_t'] = t
        return
    dt = t - S['shot_t']
    if 0 < dt < 0.04:
        press(False)
    d = delta(bone(p, 'bolt_carrier'), S['rest']['bolt'])
    S['trace'].append([round(dt, 3), d[0] if d else None, clip_name(p)])
    S['shot_shells'] += shells(w, p)
    if dt >= 0.45:
        xs = [x for _, x, _ in S['trace'] if x is not None]
        early = [x for tt, x, _ in S['trace'] if x is not None and tt <= 0.1]
        late = [x for tt, x, _ in S['trace'] if x is not None and tt >= 0.3]
        m = {'shot': S['shot'] + 1, 'ammo_before': S['shot_ammo'], 'ammo_after': ammo(p),
             'bolt_min_first_0.1s': min(early) if early else None, 'bolt_after_0.3s': late,
             'shells': S['shot_shells'], 'trace': S['trace']}
        V.setdefault('b', []).append(m)
        ok = (m['bolt_min_first_0.1s'] is not None and m['bolt_min_first_0.1s'] <= -7.0 and late and
              all(abs(x) <= 0.3 for x in late) and m['ammo_after'] == m['ammo_before'] - 1)
        assertion('b', 'shot %d bolt rearward then home' % m['shot'], ok,
                  {k: m[k] for k in ('ammo_before', 'ammo_after', 'bolt_min_first_0.1s', 'bolt_after_0.3s',
                                     'shells')}, 'min <= -7 cm (clip f2 = -9) in 0.1 s, |x| <= 0.3 after 0.3 s')
        S['shot'] += 1
        S['shot_t'] = None
        S['pt'] = t
        if S['shot'] >= 3:
            V['b_shells_per_shot'] = [s['shells'] for s in V['b']]
            new_phase('burst', t, burst_t=None, released=None, rows=[], base=None, ammo0=None, held=False)


def ph_burst(w, p, t, el):
    """(b2) design A3: a 5-round burst (the Ballista is automatic at 8 rounds/s, so TPFireEveryN = 4 would have put
    the old driver montage on shots 1 and 5) with fire_sample() on every tick from the press to 0.6 s after the
    release; then burst_assertions()."""
    if S['burst_t'] is None:
        # 1 s after the last single shot: the rifle additive (0.67 s) is quiet and the pilot has re-read hand_r's rest
        # (UpdateGunTransform caches it only on quiet frames with the aim layer up), so the burst's kick has a rest.
        # The quiet aim loop is sampled meanwhile (0.8-2.0 s, as long as the burst window) for the fingers' own drift.
        if el >= 0.8:
            S.setdefault('quiet_rows', []).append(fire_sample(p))
        if el >= 2.0:
            S['base'] = fire_sample(p)
            S['rows'] = []
            S['ammo0'] = ammo(p)
            press(True)
            S['held'] = True
            S['burst_t'] = t
        return
    S['rows'].append([round(t - S['burst_t'], 3), fire_sample(p)])
    a = ammo(p)
    if S['released'] is None:
        if (a is not None and S['ammo0'] - a >= 5) or t - S['burst_t'] > 3.0:
            press(False)
            S['held'] = False
            S['released'] = t
        elif not prop(S['def_m4'], 'automatic'):
            press(not S['held'])  # semi: re-press every tick
            S['held'] = not S['held']
        return
    if t - S['released'] >= 0.6:
        rows = [r[1] for r in S['rows']]
        V['b2'] = burst_assertions('b2', 'M4A1 5-shot burst', rows, S['base'], 5, quiet=S.get('quiet_rows'))
        V['b2']['trace'] = S['rows']
        V['b2']['base'] = S['base']
        V['b2']['quiet_trace'] = S.get('quiet_rows')
        new_phase('empty', t, held=False, empty_t=None, trace=[], fired=0, shell_count=0)


def ph_empty(w, p, t, el):
    """(c) hold the trigger until the magazine is empty; the bolt stays locked back (-8.2)."""
    a = ammo(p)
    if S['empty_t'] is None:
        auto = prop(S['def_m4'], 'automatic')
        if a and a > 0:
            if not S['held']:
                press(True)
                S['held'] = True
            elif not auto and int(el / 0.15) % 2 == 1:  # semi: re-press
                press(False)
                S['held'] = False
        else:
            press(False)
            S['held'] = False
            S['empty_t'] = t
            S['empty_at'] = el
        S['shell_count'] += shells(w, p)
        if el > 40:
            raise RuntimeError('empty: magazine never emptied (ammo=%s)' % a)
        return
    dt = t - S['empty_t']
    d = delta(bone(p, 'bolt_carrier'), S['rest']['bolt'])
    S['trace'].append([round(dt, 3), d[0] if d else None, clip_name(p), a])
    if dt >= 1.2:
        held = [x for tt, x, _, _ in S['trace'] if tt >= 0.15 and x is not None]
        clips = sorted(set(c for _, _, c, _ in S['trace'] if c))
        V['c'] = {'seconds_to_empty': round(S['empty_at'], 3), 'ammo': a, 'shells_while_emptying': S['shell_count'],
                  'ticks_checked': len(held), 'bolt_min': min(held) if held else None,
                  'bolt_max': max(held) if held else None, 'clips_seen': clips, 'trace': S['trace']}
        ok = a == 0 and len(held) >= 10 and all(abs(x + 8.2) <= 0.4 for x in held)
        assertion('c', 'last round leaves the bolt locked back', ok,
                  {k: V['c'][k] for k in ('ammo', 'ticks_checked', 'bolt_min', 'bolt_max', 'clips_seen')},
                  'bolt -8.2 +-0.4 cm on every tick from 0.15 s to 1.2 s after the last round (IdleEmpty)')
        new_phase('reload_empty', t, started=False, trace=[], done_t=None, mag_size=weapon(p).get_magazine_size())


def ph_reload(w, p, t, el, tactical):
    step = 'e' if tactical else 'd'
    c = prop(p, 'combat')
    if not S['started']:
        S['ammo_before'] = ammo(p)
        S['aim_before'] = hand_sample(p)  # aim pose up (GunRaisedTime from the shots), nothing pressed
        S['hands'] = []
        c.reload()
        S['started'] = True
        S['r_t'] = t
        return
    dt = t - S['r_t']
    b = delta(bone(p, 'bolt_carrier'), S['rest']['bolt'])
    m = delta(bone(p, 'magazine'), S['rest']['mag'])
    rel = c.is_reloading()
    S['trace'].append([round(dt, 3), b[0] if b else None, m[2] if m else None, clip_name(p), rel, ammo(p),
                       clip_time(p)])
    S['hands'].append((round(dt, 3), hand_sample(p)))
    if not rel and S['done_t'] is None and dt > 0.05:
        S['done_t'] = dt
    if S['done_t'] is not None and dt >= S['done_t'] + 0.5:
        D = S['done_t']
        k = D / 2.4  # clip seconds -> game seconds (PlayGunReload rate-scales the 2.4 s clip to ReloadTime)
        tr = S['trace']
        first_clip = next((r[3] for r in tr if r[3]), None)
        mags = [(r[0], r[2]) for r in tr if r[2] is not None]
        zmin_t, zmin = min(mags, key=lambda r: r[1]) if mags else (None, None)
        parked = [tt for tt, z in mags if z <= -65]
        # Settled pose after the hand-over tick (the clip-to-Idle tick is reported separately).
        end_mag = [z for tt, z in mags if tt >= D + 0.05]
        boundary = [[tt, z] for tt, z in mags if abs(tt - D) <= 0.04]
        out = {'reload_seconds': round(D, 3), 'clip_to_game_scale': round(k, 4), 'first_clip': first_clip,
               'ammo_before': S['ammo_before'], 'ammo_after': ammo(p), 'magazine_size': S['mag_size'],
               'mag_z_min': zmin, 'mag_z_min_at_s': zmin_t,
               'mag_parked_window_s': [min(parked), max(parked)] if parked else None,
               'mag_z_at_end': end_mag[:3], 'mag_z_at_handover_tick': boundary, 'trace': tr}
        if not tactical:
            hold = [x for tt, x, *_ in tr if x is not None and tt <= 1.83 * k]
            home = [x for tt, x, *_ in tr if x is not None and 2.0 * k <= tt <= D]
            release = next((tt for tt, x, *_ in tr if x is not None and tt > 0.5 and abs(x) <= 0.3), None)
            out.update({'bolt_locked_ticks': len(hold), 'bolt_locked_min': min(hold) if hold else None,
                        'bolt_locked_max': max(hold) if hold else None,
                        'bolt_home_at_s': release, 'bolt_home_expected_s': round(1.95 * k, 3),
                        'bolt_after_release': home[:3]})
            ok_bolt = (hold and all(abs(x + 8.2) <= 0.4 for x in hold) and home and all(abs(x) <= 0.3 for x in home)
                       and release is not None and abs(release - 1.95 * k) <= 0.1)
            V['d'] = out
            assertion('d', 'empty Reload clip plays', first_clip == 'A_M4A1_Reload', first_clip, 'A_M4A1_Reload')
            assertion('d', 'bolt locked until the release, then home', ok_bolt,
                      {k2: out[k2] for k2 in ('bolt_locked_ticks', 'bolt_locked_min', 'bolt_locked_max',
                                              'bolt_home_at_s', 'bolt_home_expected_s', 'bolt_after_release')},
                      'bolt -8.2 until 1.83 s x scale, home (|x|<=0.3) from 2.0 s x scale; release at 1.95 s x scale')
        else:
            bolts = [x for _, x, *_ in tr if x is not None]
            out.update({'bolt_abs_max': max(abs(x) for x in bolts) if bolts else None, 'bolt_ticks': len(bolts)})
            V['e'] = out
            assertion('e', 'ReloadTactical clip plays', first_clip == 'A_M4A1_ReloadTactical', first_clip,
                      'A_M4A1_ReloadTactical')
            assertion('e', 'bolt stays home all through', bolts and out['bolt_abs_max'] <= 0.3,
                      {'bolt_abs_max': out['bolt_abs_max'], 'ticks': len(bolts)}, '|bolt| <= 0.3 cm every tick')
        ok_mag = (zmin is not None and abs(zmin + 70) <= 3 and parked and 0.5 * k <= min(parked) and
                  max(parked) <= 1.15 * k and end_mag and all(abs(z) <= 0.3 for z in end_mag))
        assertion(step, 'magazine drops to about -70 then seats', ok_mag,
                  {k2: out[k2] for k2 in ('mag_z_min', 'mag_z_min_at_s', 'mag_parked_window_s', 'mag_z_at_end',
                                          'clip_to_game_scale')},
                  'z min -70 +-3 cm, parked (z<=-65) inside [0.5, 1.15] s x scale, 0 at the end')
        assertion(step, 'ammo refills', out['ammo_after'] == S['mag_size'],
                  {'before': out['ammo_before'], 'after': out['ammo_after']}, S['mag_size'])
        # Hands (item 8): asserted on the empty reload, recorded on the tactical one.
        if not tactical:
            out['hands'] = hand_assertions('d', 'M4A1 empty reload', S['hands'], k, (0.75, 1.5, 1.9), D,
                                           S['aim_before'], rot_marks=(0.75, 1.5))
        else:
            out['hands'] = {'marks': marks_of(S['hands'], k, (0.75, 1.5, 1.9)), 'aim_before': S['aim_before']}
        out['hands_trace'] = S['hands']
        if not tactical:
            new_phase('tac_shots', t, shot=0, shot_t=None)
        else:
            new_phase('equip_em08', t, requested=False)


def ph_tac_shots(w, p, t, el):
    """(e) two single shots before the tactical reload."""
    if S['shot_t'] is None:
        if el >= 0.1:
            press(True)
            S['shot_t'] = t
        return
    dt = t - S['shot_t']
    if 0 < dt < 0.04:
        press(False)
    if dt >= 0.45:
        S['shot'] += 1
        S['shot_t'] = None
        S['pt'] = t
        if S['shot'] >= 2:
            V['e_shots_ammo'] = ammo(p)
            new_phase('reload_tac', t, started=False, trace=[], done_t=None)


def ph_equip_em08(w, p, t, el):
    """(f) give and equip DA_Weapon_Pistol_001 (bound to DA_GunRig_EM08 by its normalized key)."""
    c = prop(p, 'combat')
    if not S['requested']:
        d = S['pistol_def']
        S['pistol_class'] = d.get_editor_property('weapon_actor_class')
        V['f_vendor_actor_class'] = S['pistol_class'].get_name() if S['pistol_class'] else None
        d.set_editor_property('weapon_actor_class', u.HoverCyberRifle.static_class())
        V['f_actor_class_in_memory'] = d.get_editor_property('weapon_actor_class').get_name()
        # Python returns the out FGuid alone (None when AddItemDefinition returns false).
        res = c.inventory.add_item_definition(d, 1)
        guid = res[1] if isinstance(res, tuple) else res
        ok = guid is not None and (res[0] if isinstance(res, tuple) else True)
        quick = c.inventory.assign_instance_to_quickbar(guid, 2) if ok else False
        V['f_give'] = {'added': ok, 'quickbar_2': quick, 'definition': definition_facts(d)}
        c.select_quickbar(2)
        S['requested'] = True
        S['req_t'] = t
        return
    if rig_name(p) == 'DA_GunRig_EM08' and S.get('em_t') is None:
        S['em_t'] = t
        rifle = weapon(p)
        before = rifle.get_reserve_ammo()
        c.refill_ammo()  # tops up the definition's AmmoDefinition in the inventory and fills the cylinder
        after_refill = rifle.get_reserve_ammo()
        extra = None
        if after_refill < 2 * rifle.get_magazine_size():
            res = c.inventory.add_item_definition(S['pistol_ammo'], 24)
            extra = res is not None
        V['f_ammo'] = {'ammo_type_id': str(prop(S['pistol_def'], 'ammo_type_id')), 'reserve_before': before,
                       'reserve_after_refill_ammo': after_refill, 'added_24_pistol_rounds': extra,
                       'reserve': rifle.get_reserve_ammo()}
    if S.get('em_t') is not None and t - S['em_t'] >= 1.5:
        rifle = weapon(p)
        V['f_equip'] = {'rig': rig_name(p), 'mesh': mesh_name(p), 'rigged': p.uses_rigged_gun(),
                        'weapon': rifle.get_class().get_name() if rifle else None,
                        'definition': rifle.get_weapon_definition().get_name() if rifle else None,
                        'seconds_to_equip': round(S['em_t'] - S['req_t'], 3), 'clip_ammo': ammo(p),
                        'reserve': rifle.get_reserve_ammo() if rifle else None,
                        'cylinder_after_equip_chamber': p.get_editor_property('gun_cylinder_angle')}
        assertion('f', 'EM_08 equip rig/mesh (live)', V['f_equip']['rig'] == 'DA_GunRig_EM08' and
                  V['f_equip']['mesh'] == 'SK_EM08' and V['f_equip']['rigged'], V['f_equip'])
        shells(w, p)  # baseline
        new_phase('em08_fire', t, shot=0, shot_t=None, cyl0=p.get_editor_property('gun_cylinder_angle'),
                  em_shells=0, em_ammo0=ammo(p))
    elif el > 8:
        raise RuntimeError('equip_em08: rig is %s after 8 s (weapon %s)' % (rig_name(p), weapon(p)))


def press_key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)


def ph_em08_fire(w, p, t, el):
    """(f) three revolver shots 0.5 s apart; design A3 samples the hands on every tick from the first press. The aim
    (RightMouseButton) is held 1 s first so the pistol aim pose is settled before the kick baseline: the M4A1's
    GunRaisedTime has run out by now and a first shot from the lowered gun would blend the whole upper body up
    (about 28 deg of spine), which is not the additive. Released after the shots; the reload then runs on
    GunRaisedTime as before."""
    if S['shot_t'] is None:
        if S['shot'] == 0 and S.get('fire_base') is None:
            if S.get('aim_t') is None:
                press_key('RightMouseButton', True)
                S['aim_t'] = t
                S['em_quiet_rows'] = []
                return
            # The pistol aim layer is up after .5 s; the quiet loop is then sampled for 1.6 s (the three shots' span)
            # for the fingers' own drift before the kick baseline.
            if t - S['aim_t'] >= 0.6:
                S['em_quiet_rows'].append(fire_sample(p))
            if t - S['aim_t'] < 2.2:
                return
            S['fire_base'] = fire_sample(p)
            V['f_rest_muzzle'] = rest_muzzle_check('f', 'EM_08 at rest (aimed, settled)', p)
            S['fire_rows'] = []
            S['pt'] = t
            el = 0.0
        if S['shot'] > 0:
            S['fire_rows'].append([round(el, 3), fire_sample(p)])
        if el >= 0.1:
            press(True)
            S['shot_t'] = t
        return
    dt = t - S['shot_t']
    S['fire_rows'].append([round(dt, 3), fire_sample(p)])
    if 0 < dt < 0.04:
        press(False)
    S['em_shells'] += shells(w, p)
    if dt >= 0.5:
        S['shot'] += 1
        S['shot_t'] = None
        S['pt'] = t
        if S['shot'] >= 3:
            cyl1 = p.get_editor_property('gun_cylinder_angle')
            adv = round((cyl1 - S['cyl0']) % 360.0, 3)
            V['f_fire'] = {'cylinder_before': S['cyl0'], 'cylinder_after': cyl1, 'advanced_deg': adv,
                           'ammo_before': S['em_ammo0'], 'ammo_after': ammo(p), 'shells_during_shots': S['em_shells']}
            assertion('f', 'GunCylinderAngle advanced 180 over 3 shots', abs(adv - 180.0) < 1e-3 and
                      V['f_fire']['ammo_after'] == S['em_ammo0'] - 3, V['f_fire'], 180.0)
            assertion('f', 'no brass per revolver shot', S['em_shells'] == 0, S['em_shells'], 0)
            rows = [r[1] for r in S['fire_rows']]
            V['f_fire']['hands'] = burst_assertions('f', 'EM_08 three shots', rows, S['fire_base'], 3,
                                                    kick_range=(1.0, 10.0), quiet=S.get('em_quiet_rows'))
            V['f_fire']['hands']['trace'] = S['fire_rows']
            V['f_fire']['hands']['base'] = S['fire_base']
            V['f_fire']['hands']['quiet_trace'] = S.get('em_quiet_rows')
            press_key('RightMouseButton', False)
            new_phase('em08_reload', t, started=False, done_t=None, events=[])


def ph_em08_reload(w, p, t, el):
    c = prop(p, 'combat')
    if not S['started']:
        S['em_ammo_before'] = ammo(p)
        S['aim_before'] = hand_sample(p)  # pistol stance: both hands on the grip, palm on grip_l
        S['hands'] = []
        c.reload()
        S['started'] = True
        S['r_t'] = t
        return
    dt = t - S['r_t']
    S['hands'].append((round(dt, 3), hand_sample(p)))
    n = shells(w, p)
    if n:
        S['events'].append([round(dt, 3), n])
    if not c.is_reloading() and S['done_t'] is None and dt > 0.05:
        S['done_t'] = dt
    if S['done_t'] is not None and dt >= S['done_t'] + 0.4:
        D = S['done_t']
        d = S['pistol_def']
        mag = weapon(p).get_magazine_size()
        per = max(1, prop(d, 'shells_per_shot') or 1)
        spent = mag - S['em_ammo_before']
        want = min(spent, 8) * per
        got = sum(n for _, n in S['events'])
        first = S['events'][0][0] if S['events'] else None
        expect_t = 0.37 * D / 2.4
        V['f_reload'] = {'reload_seconds': round(D, 3), 'spent': spent, 'shells_per_shot': per,
                         'casings_expected': want, 'casings': got, 'events': S['events'],
                         'first_casing_s': first, 'expected_s': round(expect_t, 3), 'ammo_after': ammo(p),
                         'magazine': mag}
        assertion('f', 'empties fall during the reload window', got == want and first is not None and
                  abs(first - expect_t) <= 0.1 and all(tt <= D for tt, _ in S['events']),
                  {k: V['f_reload'][k] for k in ('casings', 'casings_expected', 'first_casing_s', 'expected_s',
                                                 'reload_seconds')},
                  'min(spent, 8) x ShellsPerShot casings at 0.37 s x (ReloadTime / 2.4)')
        assertion('f', 'revolver reload refills', V['f_reload']['ammo_after'] == mag,
                  V['f_reload']['ammo_after'], mag)
        V['f_reload']['hands'] = hand_assertions('f', 'EM_08 reload', S['hands'], D / 2.4, (0.75, 1.2), D,
                                                 S['aim_before'], rot_marks=(0.75,))
        V['f_reload']['hands_trace'] = S['hands']
        new_phase('swap_back', t, requested=False)


def restore_pistol():
    if S.get('pistol_class') is not None and S.get('pistol_def') is not None:
        S['pistol_def'].set_editor_property('weapon_actor_class', S['pistol_class'])
        V['f_actor_class_restored'] = S['pistol_def'].get_editor_property('weapon_actor_class').get_name()
        S['pistol_class'] = None


def ph_swap_back(w, p, t, el):
    """(g) quickbar slot 1 (DA_AFS_Ballista) -> DA_GunRig_M4A1 / SK_M4A1 again."""
    c = prop(p, 'combat')
    if not S['requested']:
        c.select_quickbar(1)
        S['requested'] = True
        return
    if rig_name(p) == 'DA_GunRig_M4A1' and el >= 1.0:
        rifle = weapon(p)
        V['g'] = {'rig': rig_name(p), 'mesh': mesh_name(p), 'rigged': p.uses_rigged_gun(),
                  'definition': rifle.get_weapon_definition().get_name() if rifle else None,
                  'clip_ammo_restored': ammo(p), 'seconds': round(el, 3)}
        assertion('g', 'swap back to M4A1 (live)', V['g']['rig'] == 'DA_GunRig_M4A1' and V['g']['mesh'] == 'SK_M4A1'
                  and V['g']['definition'] == 'DA_AFS_Ballista', V['g'])
        restore_pistol()
        new_phase('finish', t)
    elif el > 8:
        raise RuntimeError('swap_back: rig is %s after 8 s' % rig_name(p))


PHASES = {'boot': ph_boot, 'single': ph_single, 'burst': ph_burst, 'empty': ph_empty,
          'reload_empty': lambda w, p, t, el: ph_reload(w, p, t, el, False), 'tac_shots': ph_tac_shots,
          'reload_tac': lambda w, p, t, el: ph_reload(w, p, t, el, True), 'equip_em08': ph_equip_em08,
          'em08_fire': ph_em08_fire, 'em08_reload': ph_em08_reload, 'swap_back': ph_swap_back}


def log_path():
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        return m.group(1) if m else None
    except Exception:
        return None


def harvest_log():
    try:
        u.SystemLibrary.execute_console_command(None, 'FlushLog')
    except Exception:
        pass
    path = log_path()
    L = V.setdefault('log', {'path': path})
    if not path or not Path(path).exists():
        REPORT['errors'].append('abslog not found; HOVER_GUN lines not harvested (pass -abslog=...)')
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    # The pilot logs HOVER_GUN in BeginPlay, before the first post-tick; everything after authoring is PIE.
    marks = [i for i, l in enumerate(lines) if 'GUNRIGS author done' in l or 'GUNRIGS verify start' in l]
    pie = marks[-1] if marks else 0
    gl = [l for l in lines[pie:] if 'HOVER_GUN ' in l]
    L['hover_gun_lines'] = gl
    L['missing_socket_lines'] = [l for l in gl if 'missing' in l]
    bad = [l for l in lines if ('HOVER_GUN' in l or 'GunRig' in l) and
           re.search(r'Error|ensure|Ensure condition', l) and 'GUNRIGS ASSERT' not in l and 'GUNRIGS' not in l]
    L['error_or_ensure_lines'] = bad
    L['ensures_anywhere_after_pie'] = [l for l in lines[pie:] if 'Ensure condition failed' in l][:20]
    m4 = [l for l in gl if 'rigged=1' in l and 'mesh=SK_M4A1' in l and 'rig=DA_GunRig_M4A1' in l]
    em = [l for l in gl if 'rigged=1' in l and 'mesh=SK_EM08' in l and 'rig=DA_GunRig_EM08' in l]
    assertion('a', 'log: HOVER_GUN rigged=1 mesh=SK_M4A1 rig=DA_GunRig_M4A1 at start', bool(m4), m4[:1])
    assertion('a', "log: no 'socket ... missing'", not L['missing_socket_lines'], L['missing_socket_lines'][:5])
    assertion('f', 'log: HOVER_GUN rig=DA_GunRig_EM08 mesh=SK_EM08', bool(em), em[:1])
    assertion('g', 'log: M4A1 line again after the EM_08 line', bool(em) and any(
        gl.index(l) > gl.index(em[0]) for l in m4), [l for l in m4 if bool(em) and gl.index(l) > gl.index(em[0])][:1])
    assertion('h', "no error/ensure lines with 'HOVER_GUN' or 'GunRig'", not bad, bad[:5])


def finish():
    if S['end']:
        return
    try:
        press(False)
    except Exception:
        pass
    try:
        restore_pistol()
    except Exception:
        REPORT['errors'].append('pistol class restore: ' + traceback.format_exc())
    hp = [h for _, h in S['hp']]
    V['h'] = {'hp_start': hp[0] if hp else None, 'hp_min': min(hp) if hp else None, 'samples': len(hp),
              'zombies_removed': S['zombies_removed']}
    if S['phase'] == 'finish':
        assertion('h', 'HP never dropped', hp and min(hp) >= hp[0], V['h'])
    else:
        REPORT['errors'].append('verify stopped in phase %s' % S['phase'])
    save_receipt()
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    S['end'] = time.monotonic()


def complete():
    try:
        harvest_log()
    except Exception:
        REPORT['errors'].append('harvest: ' + traceback.format_exc())
    after = sha1(content_file(PISTOL))
    V['vendor_pistol_sha1_after'] = after
    assertion('h', 'vendor DA_Weapon_Pistol_001 unchanged on disk', after == V.get('vendor_pistol_sha1_before'),
              {'before': V.get('vendor_pistol_sha1_before'), 'after': after})
    REPORT['ok'] = not REPORT['errors'] and all(a['ok'] for a in REPORT['assertions'])
    save_receipt()
    print('GUNRIGS_RESULT ok=%s assertions=%d failed=%d errors=%d receipt=%s' % (
        REPORT['ok'], len(REPORT['assertions']), sum(1 for a in REPORT['assertions'] if not a['ok']),
        len(REPORT['errors']), RECEIPT), flush=True)
    for e in REPORT['errors']:
        print('GUNRIGS error', e[:500], flush=True)


def tick(_dt):
    if S['busy']:
        return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not world():
                if not S['done']:
                    S['done'] = True
                    complete()
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('verify timeout in phase %s' % S['phase'])
        if not S['play']:
            if time.monotonic() - S['start'] > 5:
                u.HoverAuthoring.set_playtest_fixed_step(True)
                u.HoverAuthoring.start_playtest()
                S['play'] = True
            return
        w = world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        if S['pc'] != pc:
            S['pc'] = pc
            u.HoverAuthoring.isolate_test_input(pc)
        p = pc.get_controlled_pawn()
        t = u.GameplayStatics.get_time_seconds(w)
        if t == S['last_t']:
            return  # the post-tick callback can fire more than once per world tick
        S['last_t'] = t
        if S['pt'] is None:
            new_phase('boot', t)
            V['pawn'] = p.get_class().get_name()
            V['mode'] = u.GameplayStatics.get_game_mode(w).get_class().get_name()
        clear_zombies(w)
        S['hp'].append([round(t, 3), p.get_health()])
        if S['phase'] == 'finish':
            finish()
            return
        PHASES[S['phase']](w, p, t, t - S['pt'])
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
        print('GUNRIGS_ERROR', REPORT['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


def main():
    try:
        if DO_AUTHOR:
            author()
    except Exception:
        REPORT['errors'].append('author: ' + traceback.format_exc())
    save_receipt()
    if not DO_VERIFY or REPORT['errors']:
        REPORT['ok'] = not REPORT['errors'] and all(a['ok'] for a in REPORT['assertions'])
        save_receipt()
        print('GUNRIGS_RESULT ok=%s (author only) errors=%d receipt=%s' % (REPORT['ok'], len(REPORT['errors']),
                                                                         RECEIPT), flush=True)
        u.SystemLibrary.quit_editor()
        return
    V['vendor_pistol_sha1_before'] = sha1(content_file(PISTOL))
    # EditorAssetLibrary refuses to load during PIE: fetch the vendor pistol definition now.
    S['pistol_def'] = load(PISTOL)
    S['pistol_ammo'] = load(PISTOL_AMMO)
    log('verify start')
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP):
        REPORT['errors'].append('load_level %s failed' % MAP)
        save_receipt()
        u.SystemLibrary.quit_editor()
        return
    u.EditorPythonScripting.set_keep_python_script_alive(True)
    S['handle'] = u.register_slate_post_tick_callback(tick)


main()
