"""AuthorZombieDiversity.py - NYC Survival zombie roster with real variety (2026-10-31), then quit the editor.

Owner, playtest 2026-10-31: "zombies all sound the same, walk backwards, no attack motion, common look";
"at least 5-10 usable zombies for diversity in the group. I saw 2-3 maybe?". This script authors the data half
of the answer (the runtime half, the AFS|Variety / AFS|Anim / AFS|Voice / AFS|Blood readers and the facing fix,
lives in C++). It must run AFTER the build that adds those UHoverCyberZombieDefinition fields; it checks for
them first and changes nothing if one is missing.

What it does (every created asset lives under /Game/HoverPrototype/NYC/Zombies/ or, for duplicated pack bodies,
/Game/HoverPrototype/ZombieEngine/Variants/NYCBodies/; pack, vendor and other-map assets are only read and
are hashed before/after to prove it):
  1. Bodies. Duplicates the two Etherion bodies (SK_Zombie, SK_Zombie_Type1) with their skeleton, and the
     ZombieMale whole body with its skeleton (only if it carries the 61 core mannequin bones), into NYCBodies,
     points each copy at the copied skeleton (UHoverAuthoring::SetCyberZombieSkeleton) and gives it 4 LODs
     (ConfigureCreatureLODs; skip with --no-lods). Pack skeletons are never edited.
  2. Compatibility. UHoverAuthoring::MakeSkeletonCompatible(body, source) for every roster body skeleton
     (Standard01-04, Brute, Kid, Lakeside Horror/BogZombie/Pirate/Plant, the NYC Etherion and ZombieMale copies)
     and every clip source it plays: ZESP SK_Mannequin (ABP_ZombieMaster, AM_Death), ZombieAnimationPack UE5,
     Etherion SKEL_Zombie, Feral UE4. Before/after lists are recorded.
  3. Montages from pack SEQUENCES (pack montages are never edited) under NYC/Zombies/Anim/<Set>/: attacks on
     slot UpperBody with an AFS_Contact track holding ZE_ZombieAnimNotify_AttackHit at the time of peak hand
     reach (AnimPoseExtensions, planar hand-to-pelvis distance, searched in 12-88 % of the clip; the Lakeside
     Variety montage times are recorded next to it for comparison); hit reactions, roars and deaths on
     DefaultSlot (deaths hold their last pose: auto blend-out off, as the Kid deaths). Gait blend spaces
     (BlendSpace1D, axis Speed) per type under NYC/Zombies/Anim/Gaits/ via UHoverAuthoring::BuildSpeedBlend1D.
     Every walk/run clip's in-place speed is measured on the target body (planted-foot speed relative to the
     root, retargeted onto the body mesh, times the runtime scale Height / mesh height, the
     RefineCharacterAssets.py method) and the sample RateScale is set to target / measured, clamped .65-1.65.
  4. Definitions under NYC/Zombies/Roster/ (duplicates of the closest existing DA, so stats, loot, behaviour
     tree and sizes carry over; the originals are never modified): eleven standard types, DA_NYC_Brute, and the
     NYC-owned DA_NYC_Kid updated in place. AggroSound / AttackSound / DeathSound stay empty on all of them
     (the AFS|Voice palettes replace them).
  5. Roster. DA_NYCEncounters.Standards = the eleven standards, Brute = DA_NYC_Brute, Kid stays DA_NYC_Kid.
     The roster is only written when at least MIN_STANDARDS types authored cleanly.

Idempotent: existing owned assets are checked and updated in place (only differing values are written; a
montage on the wrong clip or an asset of the wrong class stops that type). Nothing is saved if a preflight
check fails; a type that fails is left out of the roster and reported. Receipt:
D:/AFS_Comparisons/ZombieDiversity_20261031/author_receipt.json. Last stdout line: AUTHOR_ZOMBIES_DONE <summary>.

Run (never while another UnrealEditor.exe / UnrealEditor-Cmd.exe runs, and only after the runtime build):
  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "M:/UnrealProjects/AFS/AFS.uproject"
      -unattended -nullrhi -stdout -FullStdOutLogOutput
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorZombieDiversity.py"
Flags (inside the quoted -ExecutePythonScript value, after the script path):
  --dry-run   print the plan (types, clips, sounds, paths) and quit; nothing is loaded or saved. Also runs
              outside Unreal: python AuthorZombieDiversity.py --dry-run
  --no-lods   do not generate LODs on the NYCBodies copies (they keep the pack's single LOD)
"""
import hashlib
import json
import math
import sys
import time
import traceback
from pathlib import Path

try:
    import unreal as u
except ImportError:  # --dry-run works outside the editor
    u = None

ARGS = sys.argv[1:]
DRY_RUN = '--dry-run' in ARGS
NO_LODS = '--no-lods' in ARGS

OUT = Path('D:/AFS_Comparisons/ZombieDiversity_20261031')
RECEIPT = OUT / 'author_receipt.json'
MIN_STANDARDS = 10

# ---------------------------------------------------------------------------------------------
# Paths

NYC = '/Game/HoverPrototype/NYC'
ZOMBIES = NYC + '/Zombies'
ANIM = ZOMBIES + '/Anim'
GAITS = ANIM + '/Gaits'
ROSTER = ZOMBIES + '/Roster'
ENCOUNTERS = NYC + '/DA_NYCEncounters'
# AFS 2026-10-31 (integration): the NYC mode spawns from the DA_NYCWaves row ZombieTypes / DefaultZombieTypes
# first (HoverNYCSurvival.cpp ConfigureWave) and only falls back to Encounters.Standards when a row is empty, and
# AuthorNYCData.py copied the old four standards into every row. Keep the rows in step with the roster.
WAVES = NYC + '/DA_NYCWaves'
KID_DA = ZOMBIES + '/DA_NYC_Kid'

VARIANTS = '/Game/HoverPrototype/ZombieEngine/Variants'
LAKE = VARIANTS + '/Lakeside'
NYCB = VARIANTS + '/NYCBodies'  # SetCyberZombieSkeleton / ConfigureCreatureLODs only accept Variants paths

# Asset prefixes this script may save (plus the exact body skeletons in BODY_SKELETONS, which are owned
# /Game/HoverPrototype/ assets shared with Cyber City / Lakeside; only their compatible list may change).
OWNED_PREFIXES = (ZOMBIES + '/', NYCB + '/')
OWNED_EXACT = {ENCOUNTERS, WAVES}

ZESP_SKEL = '/Game/ZESP/Demo/Characters/Mannequins/Meshes/SK_Mannequin'
ZAP_SKEL = '/Game/ZombieAnimationPack/Demo/EpicContent/Mannequin_UE5/Meshes/SKEL_Mannequin'
ETH_SKEL = '/Game/Zombie/Meshes/SKEL_Zombie'
FER_SKEL = '/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton'
SOURCE_SKELETONS = {'ZESP': ZESP_SKEL, 'ZAP': ZAP_SKEL, 'ETH': ETH_SKEL, 'FER': FER_SKEL}

PACK = {
    'ZAP': '/Game/ZombieAnimationPack/Animations/Mannequin_UE5/',
    'ETH': '/Game/Zombie/Animations/',
    'FER': '/Game/FeralZombie/Animations/',
    'ZESP': '/Game/ZESP/ZE/Animations/Zombies/Zombie_001/',
}
ZESP_DEATH = PACK['ZESP'] + 'AM_Death'
ZESP_HIT = PACK['ZESP'] + 'AM_Hit'
ZESP_ATTACK_01 = PACK['ZESP'] + 'AM_Attack_01'
ZESP_ATTACK_02 = PACK['ZESP'] + 'AM_Attack_02'

# Pack bodies duplicated into NYCBodies: key -> (vendor skeleton, copied skeleton, [(vendor mesh, copied mesh)]).
ETH_BODY_SKEL = NYCB + '/Etherion/SKEL_NYC_Etherion'
ETH_MESH_A = NYCB + '/Etherion/Optimized/SK_NYC_EtherionA_LODs'
ETH_MESH_B = NYCB + '/Etherion/Optimized/SK_NYC_EtherionB_LODs'
ZM_BODY_SKEL = NYCB + '/ZombieMale/SKEL_NYC_ZombieMale'
ZM_MESH = NYCB + '/ZombieMale/Optimized/SK_NYC_ZombieMale_LODs'
BODY_COPIES = {
    'Etherion': (ETH_SKEL, ETH_BODY_SKEL, [('/Game/Zombie/Meshes/SK_Zombie', ETH_MESH_A),
                                          ('/Game/Zombie/Meshes/SK_Zombie_Type1', ETH_MESH_B)]),
    'ZombieMale': ('/Game/ZombieMale_AAB/Meshes/SK_Mannequin_SNP', ZM_BODY_SKEL,
                   [('/Game/ZombieMale_AAB/Meshes/SKM_ZombieM_Male_WholeBody', ZM_MESH)]),
}
LOD_COUNT = 4


def std(n, what):
    base = '%s/Standard%02d' % (VARIANTS, n)
    return {'da': '%s/DA_Standard%02d' % (base, n), 'mesh': '%s/Optimized/SK_Standard%02d_LODs' % (base, n),
            'skel': '%s/SK_Standard%02d_Skeleton' % (base, n)}[what]


def lake(body, what):
    base = '%s/%s' % (LAKE, body)
    return {'da': '%s/DA_%s' % (base, body), 'mesh': '%s/Optimized/SK_%s_LODs' % (base, body),
            'skel': '%s/SK_%s_Skeleton' % (base, body)}[what]


BRUTE_DA = VARIANTS + '/Brute/DA_Brute'
BRUTE_SKEL = VARIANTS + '/Brute/SK_Brute_Skeleton'
KID_SKEL = VARIANTS + '/Kid/SK_Kid_Skeleton'

# Every roster body skeleton that must accept the pack clips (and ABP_ZombieMaster's ZESP skeleton).
BODY_SKELETONS = {
    'Standard01': std(1, 'skel'), 'Standard02': std(2, 'skel'), 'Standard03': std(3, 'skel'),
    'Standard04': std(4, 'skel'), 'Brute': BRUTE_SKEL, 'Kid': KID_SKEL,
    'Horror': lake('Horror', 'skel'), 'BogZombie': lake('BogZombie', 'skel'), 'Pirate': lake('Pirate', 'skel'),
    'Plant': lake('Plant', 'skel'), 'Etherion': ETH_BODY_SKEL, 'ZombieMale': ZM_BODY_SKEL,
}


# ---------------------------------------------------------------------------------------------
# Clip and montage references

def clip(pack, name):
    return PACK[pack] + name


def lake_var(body, name):  # Lakeside Variety clip retargeted onto that body (e.g. Attack_A, Walk_C)
    return '%s/%s/Variety/%s_anim_%s' % (LAKE, body, body, name)


def lake_ret(body, name):  # Lakeside Retargeted ZESP clip / montage (e.g. AS_Zombie_Idle_Anim, AM_Death)
    return '%s/%s/Retargeted/%s_%s' % (LAKE, body, body, name)


def atk(path):
    return {'make': 'attack', 'source': path}


def hit(path):
    return {'make': 'hit', 'source': path}


def die(path):
    return {'make': 'death', 'source': path}


def roar(path):
    return {'make': 'roar', 'source': path}


def use(path):  # an existing montage, referenced as-is (never edited)
    return {'use': path}


SLOT = {'attack': 'UpperBody', 'hit': 'DefaultSlot', 'death': 'DefaultSlot', 'roar': 'DefaultSlot'}
HIT_TRACK = 'AFS_Contact'
REACH_WINDOW = (.12, .88)  # fraction of the clip searched for the peak hand reach


def set_of(source):
    """Montage folder / name prefix for a source clip: the pack (ZAP/ETH/FER/ZESP) or the Lakeside body."""
    for key, base in PACK.items():
        if source.startswith(base):
            return key
    if source.startswith(LAKE + '/'):
        return source[len(LAKE) + 1:].split('/')[0]
    raise ValueError('no montage set for ' + source)


def short_of(source):
    name = source.rsplit('/', 1)[1]
    for prefix in ('Anim_Zombie_', 'anim_'):
        if name.startswith(prefix):
            return name[len(prefix):]
    if '_anim_' in name:
        return name.split('_anim_', 1)[1]
    if '_AS_' in name:
        return name.split('_AS_', 1)[1]
    return name


def montage_path(ref):
    if 'use' in ref:
        return ref['use']
    s = set_of(ref['source'])
    return '%s/%s/AM_NYC_%s_%s' % (ANIM, s, s, short_of(ref['source']))


# ---------------------------------------------------------------------------------------------
# Sounds and blood

SND = '/Game/Zombie/Sound/'
V2_FOLDER = {'Attack': 'Attack', 'Death': 'Death', 'Exhale': 'ExhaleShort', 'Hiss': 'Hiss', 'Idle': 'Idle',
             'Inhale': 'Inhale', 'Pain': 'Pain', 'Roar': 'Roar', 'Speech': 'Speech'}


def v2(kind, *numbers):
    """ZombieV2 waves, e.g. v2('Idle', 1, 2, 3) -> S_Zombie_Idle_1..3."""
    return ['%sZombieV2/%s/S_Zombie_%s_%d' % (SND, V2_FOLDER[kind], kind, n) for n in numbers]


def zb(sub, *names):  # /Game/Zombie/Sound/Zombie/<sub>/S_Zombie_<name>
    return ['%sZombie/%s/S_Zombie_%s' % (SND, sub, n) for n in names]


def monster(sub, *names):  # /Game/Zombie/Sound/Monster/<sub>/S_Monster_<name>
    return ['%sMonster/%s/S_Monster_%s' % (SND, sub, n) for n in names]


def entity_roar(*letters):
    return ['%sEntity/Roar/S_Entity_Roar_%s' % (SND, x) for x in letters]


ENTITY_DEATH = SND + 'Entity/S_Entity_Death'
FOOTSTEPS = ['%sFootsteps/S_Zombie_Footstep_%d' % (SND, n) for n in (1, 2, 3, 4)]

BLOOD = '/Game/Blood_VFX_Pack/Particles/Systems/'
BLOOD_HIT = BLOOD + 'P_BigSplash_Hit'
BLOOD_HEAD = BLOOD + 'P_SplashWithBurst_01'
BLOOD_DEATH = BLOOD + 'P_Ground_Splash_Decal'

ETHERION_SKINS = ['/Game/Zombie/Materials/MI_Zombie_A', '/Game/Zombie/Materials/MI_Zombie_Brown',
                  '/Game/Zombie/Materials/MI_Zombie_Green', '/Game/Zombie/Materials/MI_Zombie_Skin_Black',
                  '/Game/Zombie/Materials/MI_Zombie_Skin_White']
# SK_Zombie body-shape morphs (the elf ear, fang and Type1 whole-body morphs are left out; they read as fantasy
# or fight the base body). SK_Zombie_Type1 only has JawOpen1 / Muscle / Skinny / TongueOut1.
ETHERION_A_MORPHS = ['JawOpen', 'Morph_Torso_Lopsided', 'Morph_Torso_Belly_L', 'Morph_Torso_Abs_L', 'Morph_Torso_Abs_S',
                     'Morph_Torso_Back_L', 'Morph_Torso_Width_L', 'Morph_Torso_Width_S', 'Morph_Torso_Depth_L',
                     'Morph_Torso_Depth_S', 'Morph_Torso_RibFlare_L', 'Morph_Arms_Forearms_L', 'Morph_Arms_Forearms_S',
                     'Morph_Arms_ShouldersBiceps_L', 'Morph_Arms_ShouldersBiceps_S', 'Morph_Legs_Calves_L',
                     'Morph_Legs_Thigh_L', 'Morph_Face_Width_L', 'Morph_Face_Width_S', 'Morph_Face_JawWidth_B',
                     'Morph_Face_JawWidth_S', 'Morph_Face_NeckFlab_L', 'Morph_Face_Neck_Thick', 'Morph_Face_Gums_L']
ETHERION_B_MORPHS = ['JawOpen1', 'Muscle', 'Skinny']


# ---------------------------------------------------------------------------------------------
# The roster. Speeds are cm/s targets for the blend-space samples; the RateScale makes the measured clip speed
# meet them. MaximumRunSpeed caps the NYC pursuit tiers (180 / 400 / 600), so shamblers stay slow.

def voice(idle, chase, attack, pain, death, pitch, interval, volume=1.0):
    return {'IdleVocals': idle, 'ChaseVocals': chase, 'AttackVocals': attack, 'PainVocals': pain,
            'DeathVocals': death, 'VoicePitch': pitch, 'VocalInterval': interval, 'VoiceVolume': volume}


TYPES = [
    dict(name='Shambler', identity='slow dragging shamble, low moans', template=std(1, 'da'), mesh=std(1, 'mesh'),
         body='Standard01', height=178.0, max_run=300.0, walk_speed=90.0,
         gait=[(clip('ZAP', 'anim_Idle_A'), 0.0), (clip('ZAP', 'anim_Walk_A'), 90.0), (clip('ZAP', 'anim_Run_A'), 260.0)],
         attacks=[atk(clip('ZAP', 'anim_Attack_A')), atk(clip('ZAP', 'anim_Attack_B'))],
         hits=[hit(clip('ZAP', 'anim_Taking_Damage_A')), hit(clip('ZAP', 'anim_Taking_Damage_B')),
               hit(clip('ZAP', 'anim_Taking_Damage_C'))],
         deaths=[use(ZESP_DEATH), die(clip('FER', 'Death_01'))],
         roar=None, roar_chance=0.0,
         voice=voice(v2('Idle', 1, 2, 3, 4, 5) + v2('Exhale', 1, 2, 3, 4, 5), v2('Idle', 6, 7, 8) + v2('Exhale', 6, 7, 8, 9, 10),
                     v2('Attack', 1, 2), v2('Pain', 1, 2, 3), v2('Death', 1, 2, 3) + zb('Death', 'Death'),
                     (.82, .92), (4.0, 9.0)),
         stride=55.0, step_volume=.55, scale=(.94, 1.06), rate=(.85, 1.0)),
    dict(name='Lurcher', identity='lurching lean-forward walker, mutters', template=std(2, 'da'), mesh=std(2, 'mesh'),
         body='Standard02', height=183.0, max_run=480.0, walk_speed=120.0,
         gait=[(clip('ZAP', 'anim_Idle_A'), 0.0), (clip('ZAP', 'anim_Walk_B'), 120.0), (clip('ZAP', 'anim_Run_A'), 380.0)],
         attacks=[atk(clip('ZAP', 'anim_Attack_C')), atk(clip('ZAP', 'anim_Attack_D'))],
         hits=[hit(clip('ZAP', 'anim_Taking_Damage_D')), hit(clip('ZAP', 'anim_Taking_Damage_E')),
               hit(clip('ZAP', 'anim_Taking_Damage_F'))],
         deaths=[use(ZESP_DEATH), die(clip('FER', 'Death_02'))],
         roar=None, roar_chance=0.0,
         voice=voice(v2('Speech', 1, 2, 3, 4, 5) + v2('Inhale', 1, 2, 3, 4, 5), v2('Speech', 6, 7, 8, 9, 10),
                     v2('Attack', 3, 4), v2('Pain', 4, 5, 6), v2('Death', 4, 5, 6), (.95, 1.05), (3.5, 8.0)),
         stride=65.0, step_volume=.6, scale=(.95, 1.05), rate=(.92, 1.08)),
    dict(name='Runner', identity='fast sprinter, roars on sight', template=std(3, 'da'), mesh=std(3, 'mesh'),
         body='Standard03', height=176.0, max_run=850.0, walk_speed=150.0,
         gait=[(clip('ETH', 'Anim_Zombie_Idle_B'), 0.0), (clip('ETH', 'Anim_Zombie_Walk'), 150.0),
               (clip('ETH', 'Anim_Zombie_Jog'), 320.0), (clip('ETH', 'Anim_Zombie_Run'), 540.0)],
         attacks=[atk(clip('ETH', 'Anim_Zombie_Attack')), atk(clip('FER', 'Attack_LeftSwipe')),
                  atk(clip('FER', 'Attack_RightSwipe'))],
         hits=[hit(clip('FER', 'HitReact_01')), hit(clip('FER', 'HitReact_02')), hit(clip('ZAP', 'anim_Taking_Damage_A'))],
         deaths=[die(clip('FER', 'Death_01')), die(clip('FER', 'Death_02'))],
         roar=roar(clip('FER', 'Idle_Roar_02')), roar_chance=.45,
         voice=voice(v2('Inhale', 6, 7, 8, 9, 10), v2('Roar', 1, 2, 3, 4, 5) + v2('Inhale', 6, 7, 8),
                     v2('Attack', 5, 1), v2('Pain', 7, 8, 9), v2('Death', 7, 8, 9, 10), (1.05, 1.15), (2.5, 6.0)),
         stride=95.0, step_volume=.65, scale=(.93, 1.02), rate=(.95, 1.12)),
    dict(name='Brawler', identity='heavy two-handed hitter, growls', template=std(4, 'da'), mesh=std(4, 'mesh'),
         body='Standard04', height=188.0, max_run=600.0, walk_speed=140.0,
         gait=[(clip('ETH', 'Anim_Zombie_Idle_D'), 0.0), (clip('ETH', 'Anim_Zombie_Walk'), 140.0),
               (clip('ETH', 'Anim_Zombie_Run'), 480.0)],
         attacks=[atk(clip('ETH', 'Anim_Zombie_Attack_B')), atk(clip('FER', 'StrongAttack_01')),
                  atk(clip('FER', 'StrongAttack_02')), atk(clip('FER', 'Attack_Combo'))],
         hits=[hit(clip('FER', 'HitReact_03')), hit(clip('FER', 'HitReact_04')), hit(clip('ZAP', 'anim_Taking_Damage_E'))],
         deaths=[use(ZESP_DEATH), die(clip('FER', 'Death_01'))],
         roar=roar(clip('ETH', 'Anim_Zombie_Roar')), roar_chance=.45,
         voice=voice(zb('AmbientSounds', 'Ambient_A', 'Ambient_B', 'Ambient_C', 'Ambient_D'),
                     zb('Roar', 'Roar_A', 'Roar_B', 'Roar_C', 'Roar_D') + v2('Roar', 6, 7, 8, 9, 10),
                     v2('Attack', 2, 3, 4), v2('Pain', 2, 4, 6, 8), zb('Death', 'Death', 'Death_B') + v2('Death', 2),
                     (.88, .98), (3.0, 7.0), 1.1),
         stride=80.0, step_volume=.75, scale=(1.0, 1.1), rate=(.92, 1.05)),
    dict(name='Horror', identity='skittering horror, hisses and whispers', template=lake('Horror', 'da'),
         mesh=lake('Horror', 'mesh'), body='Horror', height=185.0, max_run=700.0, walk_speed=120.0,
         gait=[(lake_ret('Horror', 'AS_Zombie_Idle_Anim'), 0.0), (lake_var('Horror', 'Walk_C'), 120.0),
               (lake_ret('Horror', 'AS_Zombie_Run_Anim'), 480.0)],
         attacks=[atk(lake_var('Horror', 'Attack_C')), atk(lake_var('Horror', 'Attack_D')),
                  atk(clip('FER', 'Attack_LeftSwipe'))],
         hits=[hit(lake_var('Horror', 'Taking_Damage_A')), hit(lake_var('Horror', 'Taking_Damage_C')),
               hit(clip('FER', 'HitReact_03'))],
         deaths=[use(lake_ret('Horror', 'AM_Death')), die(clip('FER', 'Death_02'))],
         roar=roar(clip('FER', 'Idle_Roar_01')), roar_chance=.3,
         voice=voice(v2('Hiss', 1, 2, 3, 4, 5) + v2('Speech', 1, 2, 3), v2('Hiss', 1, 3, 5) + v2('Speech', 4, 5, 6, 7),
                     v2('Attack', 1, 5), v2('Pain', 3, 5, 7), v2('Death', 5, 8) + [ENTITY_DEATH], (1.1, 1.2), (3.0, 7.0)),
         stride=75.0, step_volume=.55, scale=(.95, 1.05), rate=(.95, 1.1)),
    dict(name='Bog', identity='waterlogged slow wader, gurgles', template=lake('BogZombie', 'da'),
         mesh=lake('BogZombie', 'mesh'), body='BogZombie', height=180.0, max_run=320.0, walk_speed=80.0,
         gait=[(lake_ret('BogZombie', 'AS_Zombie_Idle_Anim'), 0.0), (lake_var('BogZombie', 'Walk_A'), 80.0),
               (lake_ret('BogZombie', 'AS_Zombie_Run_Anim'), 280.0)],
         attacks=[atk(lake_var('BogZombie', 'Attack_A')), atk(lake_var('BogZombie', 'Attack_B'))],
         hits=[hit(lake_var('BogZombie', 'Taking_Damage_B')), hit(lake_var('BogZombie', 'Taking_Damage_D'))],
         deaths=[use(lake_ret('BogZombie', 'AM_Death')), die(clip('FER', 'Death_01'))],
         roar=None, roar_chance=0.0,
         voice=voice(zb('AmbientSounds', 'Ambient_A', 'Ambient_B', 'Ambient_C', 'Ambient_D') + v2('Exhale', 1, 2, 3, 4),
                     zb('AmbientSounds', 'Ambient_B', 'Ambient_D') + zb('Roar', 'Roar_A', 'Roar_B'),
                     v2('Attack', 2, 4), v2('Pain', 1, 2), zb('Death', 'Death_B') + v2('Death', 9), (.8, .9), (5.0, 10.0)),
         stride=55.0, step_volume=.6, scale=(.96, 1.06), rate=(.85, 1.0)),
    dict(name='Pirate', identity='drowned sailor, rasping speech', template=lake('Pirate', 'da'),
         mesh=lake('Pirate', 'mesh'), body='Pirate', height=185.0, max_run=520.0, walk_speed=120.0,
         gait=[(lake_ret('Pirate', 'AS_Zombie_Idle_Anim'), 0.0), (lake_var('Pirate', 'Walk_B'), 120.0),
               (lake_ret('Pirate', 'AS_Zombie_Run_Anim'), 450.0)],
         attacks=[atk(lake_var('Pirate', 'Attack_B')), atk(lake_var('Pirate', 'Attack_D')),
                  atk(clip('ETH', 'Anim_Zombie_Attack'))],
         hits=[hit(lake_var('Pirate', 'Taking_Damage_E')), hit(lake_var('Pirate', 'Taking_Damage_F')),
               use(lake_ret('Pirate', 'AM_Hit'))],
         deaths=[use(lake_ret('Pirate', 'AM_Death')), die(clip('FER', 'Death_02'))],
         roar=None, roar_chance=0.0,
         voice=voice(v2('Speech', 2, 4, 6, 8, 10), v2('Speech', 1, 3, 5, 7, 9) + v2('Roar', 7, 8), v2('Attack', 3),
                     v2('Pain', 4, 8), v2('Death', 3, 6, 10), (.9, 1.0), (3.5, 8.0)),
         stride=70.0, step_volume=.6, scale=(.95, 1.05), rate=(.92, 1.08)),
    dict(name='Plant', identity='overgrown husk, clicking and hissing', template=lake('Plant', 'da'),
         mesh=lake('Plant', 'mesh'), body='Plant', height=180.0, max_run=520.0, walk_speed=130.0,
         # Review 2026-10-31: the vendor AS_Walking_Anim is turned in the clip (feet ~35-70 deg off the run on
         # every body), so the Plant walks on its own Lakeside Variety walk instead.
         gait=[(lake_ret('Plant', 'AS_Zombie_Idle_Anim'), 0.0), (lake_var('Plant', 'Walk_A'), 130.0),
               (lake_ret('Plant', 'AS_Zombie_Run_Anim'), 420.0)],
         attacks=[atk(lake_var('Plant', 'Attack_A')), atk(lake_var('Plant', 'Attack_C')),
                  atk(clip('ETH', 'Anim_Zombie_Attack_B'))],
         hits=[hit(lake_var('Plant', 'Taking_Damage_A')), hit(lake_var('Plant', 'Taking_Damage_F')),
               hit(clip('FER', 'HitReact_02'))],
         deaths=[use(lake_ret('Plant', 'AM_Death')), die(clip('FER', 'Death_01'))],
         roar=None, roar_chance=0.0,
         voice=voice(monster('AmbientSounds', 'Ambience_Clicking') + v2('Hiss', 1, 2, 3),
                     monster('AmbientSounds', 'Ambience_A', 'Ambience_B', 'Ambience_C') + v2('Hiss', 4, 5),
                     v2('Attack', 1, 5), v2('Pain', 6, 9), [ENTITY_DEATH] + v2('Death', 7), (1.0, 1.1), (4.0, 9.0)),
         stride=65.0, step_volume=.5, scale=(.95, 1.05), rate=(.92, 1.08)),
    dict(name='EtherionA', identity='city casualty, five skins, body-shape morphs', template=std(1, 'da'),
         mesh=ETH_MESH_A, body='Etherion', height=182.0, max_run=650.0, walk_speed=100.0,
         gait=[(clip('ETH', 'Anim_Zombie_Idle'), 0.0), (clip('ETH', 'Anim_Zombie_Walk_Slow'), 100.0),
               (clip('ETH', 'Anim_Zombie_Jog'), 300.0), (clip('ETH', 'Anim_Zombie_Run_B'), 560.0)],
         attacks=[atk(clip('ETH', 'Anim_Zombie_Attack')), atk(clip('ETH', 'Anim_Zombie_Attack_B')),
                  atk(clip('ZAP', 'anim_Attack_A'))],
         hits=[hit(clip('ZAP', 'anim_Taking_Damage_B')), hit(clip('ZAP', 'anim_Taking_Damage_D')),
               hit(clip('FER', 'HitReact_02'))],
         deaths=[use(ZESP_DEATH), die(clip('FER', 'Death_01')), die(clip('FER', 'Death_02'))],
         roar=None, roar_chance=0.0,
         voice=voice(v2('Speech', 2, 3, 4, 5, 6) + v2('Idle', 6, 7, 8, 9, 10), v2('Speech', 7, 8, 9, 10) + v2('Roar', 2, 3, 4),
                     v2('Attack', 1, 2, 3, 4, 5), v2('Pain', 1, 2, 3, 4, 5), v2('Death', 1, 2, 3, 4, 5), (.95, 1.03), (3.0, 8.0)),
         stride=70.0, step_volume=.6, scale=(.93, 1.07), rate=(.92, 1.08),
         skins=ETHERION_SKINS, morphs=ETHERION_A_MORPHS, morph_max=.7),
    dict(name='EtherionB', identity='sneaking stalker, five skins, muscle/skinny morphs', template=std(1, 'da'),
         mesh=ETH_MESH_B, body='Etherion', height=179.0, max_run=700.0, walk_speed=120.0,
         gait=[(clip('ETH', 'Anim_Zombie_Idle_C'), 0.0), (clip('ETH', 'Anim_Zombie_Walk_Sneak'), 120.0),
               (clip('ETH', 'Anim_Zombie_Run'), 500.0)],
         attacks=[atk(clip('ETH', 'Anim_Zombie_Attack_B')), atk(clip('FER', 'StrongAttack_03')),
                  atk(clip('FER', 'Attack_RightSwipe'))],
         hits=[hit(clip('FER', 'HitReact_01')), hit(clip('FER', 'HitReact_04')), hit(clip('ZAP', 'anim_Taking_Damage_F'))],
         deaths=[die(clip('FER', 'Death_02')), use(ZESP_DEATH)],
         roar=roar(clip('ETH', 'Anim_Zombie_Roar')), roar_chance=.3,
         voice=voice(v2('Inhale', 1, 2, 3, 4, 5) + v2('Hiss', 2, 3, 4), v2('Pain', 6, 7, 8, 9) + v2('Roar', 5, 6, 7),
                     v2('Attack', 2, 3, 4, 5), v2('Pain', 5, 6, 7, 8, 9), v2('Death', 6, 7, 8, 9, 10), (1.02, 1.1), (3.0, 7.0)),
         stride=75.0, step_volume=.5, scale=(.93, 1.07), rate=(.95, 1.1),
         skins=ETHERION_SKINS, morphs=ETHERION_B_MORPHS, morph_max=.6),
    dict(name='Drifter', identity='classic shuffling walker on the ZombieMale body', template=std(2, 'da'),
         mesh=ZM_MESH, body='ZombieMale', height=181.0, max_run=600.0, walk_speed=150.0,
         # Review 2026-10-31: ZAP gait instead of the vendor ZESP set, whose AS_Walking_Anim is turned in the clip.
         gait=[(clip('ZAP', 'anim_Idle_B'), 0.0), (clip('ZAP', 'anim_Walk_C'), 150.0),
               (clip('ZAP', 'anim_Run_A'), 480.0)],
         attacks=[use(ZESP_ATTACK_01), use(ZESP_ATTACK_02), atk(clip('ZAP', 'anim_Attack_C'))],
         hits=[use(ZESP_HIT), hit(clip('ZAP', 'anim_Taking_Damage_C')), hit(clip('ZAP', 'anim_Taking_Damage_E'))],
         deaths=[use(ZESP_DEATH), die(clip('FER', 'Death_02'))],
         roar=None, roar_chance=0.0,
         voice=voice(v2('Exhale', 6, 7, 8, 9, 10) + zb('AmbientSounds', 'Ambient_C', 'Ambient_D'),
                     v2('Idle', 1, 2, 3, 4) + v2('Roar', 8, 9, 10), v2('Attack', 1, 2, 3), v2('Pain', 2, 3, 4),
                     v2('Death', 2, 4) + zb('Death', 'Death'), (.88, .96), (4.0, 9.0)),
         stride=70.0, step_volume=.6, scale=(.95, 1.05), rate=(.92, 1.08)),
]

BRUTE = dict(name='Brute', identity='NYC brute: giant stride, monster roars, keeps Stomp/Smash', template=BRUTE_DA,
             body='Brute', gait=[(clip('ETH', 'Anim_Zombie_Idle'), 0.0), (clip('ETH', 'Anim_Zombie_Walk_Giant'), 150.0),
                                 (clip('ETH', 'Anim_Zombie_Jog'), 360.0)],
             extra_hits=[hit(clip('ZAP', 'anim_Taking_Damage_E'))],
             deaths=[use(ZESP_DEATH), die(clip('FER', 'Death_01'))],
             roar=roar(clip('ETH', 'Anim_Zombie_Roar')), roar_chance=.6,
             voice=voice(monster('AmbientSounds', 'Ambience_A', 'Ambience_B', 'Ambience_C', 'Ambience_D', 'Ambience_E'),
                         monster('Roar', 'Roar_A', 'Roar_B', 'Roar_C', 'Roar_D', 'Roar_E', 'Roar_F', 'Roar_G') +
                         entity_roar('A', 'B', 'C', 'D'), v2('Attack', 1, 2, 3, 4, 5), v2('Pain', 1, 2, 3),
                         [ENTITY_DEATH] + zb('Death', 'Death_B'), (.7, .8), (4.0, 8.0), 1.25),
             stride=110.0, step_volume=.9, scale=(.97, 1.06), rate=(.95, 1.05), blood_scale=1.4)

KID = dict(name='Kid', identity='feral kid (existing NYC Feral set) gains voice, roar, blood',
           deaths_existing=[ZOMBIES + '/AM_NYC_Kid_Death_01', ZOMBIES + '/AM_NYC_Kid_Death_02'],
           roar=roar(clip('FER', 'Idle_Roar_01')), roar_chance=.35,
           voice=voice(v2('Hiss', 1, 2, 3, 4, 5), v2('Speech', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10) + v2('Hiss', 2, 4),
                       v2('Attack', 1, 2, 3, 4, 5), v2('Pain', 1, 2, 3, 4, 5, 6, 7, 8, 9),
                       v2('Death', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), (1.4, 1.6), (2.0, 5.0), .9),
           stride=45.0, step_volume=.45, scale=(.9, 1.08), rate=(.95, 1.1), blood_scale=.7)

RATE_CLAMP = (.65, 1.65)
SOURCE_HEIGHT = {'ZAP': 180.0, 'ETH': 189.0, 'FER': 180.0, 'ZESP': 180.0}  # pack mannequin heights (fallback)

# Every new definition field written here (names from the shared contract; Python names are resolved).
NEW_FIELDS = ['SkinMaterials', 'SkinMaterialSlot', 'bRandomizeMorphTargets', 'MorphTargetNames', 'MorphTargetMax',
              'ScaleJitter', 'AnimRateJitter', 'DeathMontageVariants', 'SightRoarMontage', 'SightRoarChance',
              'IdleVocals', 'ChaseVocals', 'AttackVocals', 'PainVocals', 'DeathVocals', 'FootstepSounds',
              'VoicePitch', 'VoiceVolume', 'VocalInterval', 'FootstepVolume', 'FootstepStride', 'HitBlood',
              'HeadshotBlood', 'DeathBlood', 'BloodScale', 'bAlignMeshYaw', 'MeshYawOffset']
HELPERS = ['MakeSkeletonCompatible', 'BuildSpeedBlend1D', 'SetMontageSlot', 'SetCyberZombieSkeleton',
           'ConfigureCreatureLODs']

REPORT = {'ok': False, 'dry_run': DRY_RUN, 'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'errors': [], 'warnings': [],
          'preflight': {}, 'bodies': {}, 'compatibility': {}, 'montages': {}, 'blendspaces': {}, 'definitions': {},
          'brute': {}, 'kid': {}, 'encounters': {}, 'failed_types': {}, 'created': [], 'modified': [], 'saved': [],
          'untouched_hashes_before': {}, 'untouched_hashes_after': {}, 'untouched_changed': [], 'python_names': {},
          'readback_mismatches': [],
          'claim': 'Editor asset authoring only; no gameplay run and no rendered evidence. Notify times and blend '
                   'rates are measured from poses, not watched in a viewport.'}
EA = AT = AL = None
TOUCHED = {}  # asset path -> (asset, created)


# ---------------------------------------------------------------------------------------------
# Generic helpers (name resolution and compare rules as in AuthorNYCBosses.py)

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


def candidates(cpp):
    base = pythonize(cpp)
    alt = ''.join(('_' + ch if ch.isdigit() and i and not base[i - 1].isdigit() and base[i - 1] != '_' else ch)
                  for i, ch in enumerate(base))
    return [base] if alt == base else [base, alt]


def resolve(holder, cpp, scope):
    key = scope + '.' + cpp
    if key in REPORT['python_names']:
        return REPORT['python_names'][key]
    for name in candidates(cpp):
        try:
            holder.get_editor_property(name)
            REPORT['python_names'][key] = name
            return name
        except Exception:
            continue
    raise AttributeError('%s: no Python property for %s (tried %s)' % (scope, cpp, candidates(cpp)))


def pathish(value):
    if value is None:
        return None
    text = value.get_path_name() if hasattr(value, 'get_path_name') else str(value)
    text = text.strip().strip("'\"")
    return text.split('.')[0] if text.startswith('/') else text


def norm(value):
    if value is None:
        return None
    if u and isinstance(value, u.Name):
        text = str(value)
        return None if text == 'None' else text
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if hasattr(value, 'get_path_name'):
        return pathish(value)
    if u and isinstance(value, u.Vector2D):
        return [round(value.x, 4), round(value.y, 4)]
    if u and isinstance(value, u.SoftObjectPath):
        try:
            return pathish(value.export_text()) or None
        except Exception:
            return str(value)
    if isinstance(value, dict) or (u and isinstance(value, u.Map)):
        return sorted((str(k), norm(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)) or (u and isinstance(value, (u.Array, getattr(u, 'FixedArray', ())))):
        return [norm(v) for v in value]
    return str(value)


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-3
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def put(holder, cpp, value, scope, changes):
    """Write only when the normalized value differs; records the change; returns True when written."""
    name = resolve(holder, cpp, scope)
    if same(norm(holder.get_editor_property(name)), norm(value)):
        return False
    holder.set_editor_property(name, value)
    changes.append(cpp)
    return True


def check(holder, cpp, expected, scope):
    actual = norm(holder.get_editor_property(resolve(holder, cpp, scope)))
    if not same(actual, norm(expected)):
        REPORT['readback_mismatches'].append({'field': scope + '.' + cpp, 'expected': norm(expected), 'actual': actual})
        return False
    return True


def warn(text):
    REPORT['warnings'].append(text)


def file_of(asset_path):
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return content / (asset_path[len('/Game/'):] + '.uasset')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load(path, cls=None):
    assert EA.does_asset_exist(path), 'missing asset ' + path
    asset = EA.load_asset(path)
    assert asset, 'failed to load ' + path
    if cls is not None:
        assert isinstance(asset, cls), '%s is %s, not %s' % (path, asset.get_class().get_name(), cls.__name__)
    return asset


def owned(path):
    return path.startswith(OWNED_PREFIXES) or path in OWNED_EXACT or path in BODY_SKELETONS.values()


def touch(asset, created):
    path = pathish(asset)
    assert owned(path), 'refusing to modify non-owned asset ' + path
    prev = TOUCHED.get(path)
    TOUCHED[path] = (asset, created or (prev[1] if prev else False))


def skeleton_of(asset):
    for attempt in (lambda: asset.get_editor_property('skeleton'), lambda: asset.get_skeleton()):
        try:
            value = attempt()
            if value:
                return value
        except Exception:
            continue
    return None


def compatible_paths(skel):
    return [pathish(x) for x in (skel.get_editor_property('compatible_skeletons') or [])]


def bone_names(skel):
    pose = u.AnimPoseExtensions.get_reference_pose(skel)
    return [str(b) for b in u.AnimPoseExtensions.get_bone_names(pose)]


def helper(cpp_name):
    """UHoverAuthoring function by its C++ name (UE pythonizes acronyms and digits unpredictably, e.g.
    ConfigureCreatureLODs -> configure_creature_lo_ds), matched on letters only."""
    key = cpp_name.lower()
    fn = next((getattr(u.HoverAuthoring, n) for n in dir(u.HoverAuthoring) if n.replace('_', '') == key), None)
    assert fn, 'HoverAuthoring.%s is not exposed to Python (not compiled?)' % cpp_name
    return fn


def dirty_packages():
    fn = getattr(u.EditorLoadingAndSavingUtils, 'get_dirty_content_packages', None)
    return {p.get_name() for p in fn()} if fn else set()


def create_asset(name, pkg, cls, factory):
    asset = AT.create_asset(name, pkg, cls, factory)
    assert asset and isinstance(asset, cls), 'create_asset failed for %s/%s' % (pkg, name)
    return asset


# ---------------------------------------------------------------------------------------------
# 1. Bodies

def mesh_lods(mesh):
    try:
        return int(u.SkeletalMeshEditorSubsystem.get_lod_count(mesh))
    except Exception:
        return None


def copy_bodies(core_bones):
    for key, (vendor_skel_path, skel_path, meshes) in BODY_COPIES.items():
        info = REPORT['bodies'].setdefault(key, {'skeleton': skel_path, 'meshes': {}})
        try:
            vendor_skel = load(vendor_skel_path, u.Skeleton)
            bones = bone_names(vendor_skel)
            missing = sorted(set(core_bones) - set(bones))
            info.update({'vendor_skeleton': vendor_skel_path, 'bone_count': len(bones), 'missing_core_bones': missing})
            if missing:
                raise RuntimeError('%s lacks %d core mannequin bones (%s); body not used' % (
                    vendor_skel_path, len(missing), missing[:8]))
            created = not EA.does_asset_exist(skel_path)
            skel = EA.duplicate_asset(vendor_skel_path, skel_path) if created else load(skel_path, u.Skeleton)
            assert skel and isinstance(skel, u.Skeleton), 'duplicate_asset failed for ' + skel_path
            if created:
                touch(skel, True)
            info['skeleton_state'] = 'created' if created else 'existing'
            for vendor_mesh, mesh_path in meshes:
                row = info['meshes'].setdefault(mesh_path, {'vendor': vendor_mesh})
                made = not EA.does_asset_exist(mesh_path)
                mesh = EA.duplicate_asset(vendor_mesh, mesh_path) if made else load(mesh_path, u.SkeletalMesh)
                assert mesh and isinstance(mesh, u.SkeletalMesh), 'duplicate_asset failed for ' + mesh_path
                changed = made
                row['state'] = 'created' if made else 'existing'
                row['skeleton_before'] = pathish(skeleton_of(mesh))
                if row['skeleton_before'] != skel_path:
                    assert helper('SetCyberZombieSkeleton')(mesh, skel), \
                        'SetCyberZombieSkeleton refused %s -> %s (path gate or missing bone)' % (mesh_path, skel_path)
                    changed = True
                row['skeleton_after'] = pathish(skeleton_of(mesh))
                assert row['skeleton_after'] == skel_path, '%s skeleton is %s' % (mesh_path, row['skeleton_after'])
                row['materials'] = [(str(m.get_editor_property('material_slot_name')),
                                     pathish(m.get_editor_property('material_interface')))
                                    for m in mesh.get_editor_property('materials')]
                try:
                    row['physics_asset'] = pathish(mesh.get_editor_property('physics_asset'))
                except Exception:
                    row['physics_asset'] = 'n/a'
                row['lods_before'] = mesh_lods(mesh)
                row['lod_action'] = 'skipped (--no-lods)' if NO_LODS else 'none needed'
                if not NO_LODS and row['lods_before'] is not None and row['lods_before'] < LOD_COUNT:
                    try:
                        row['regenerate'] = bool(u.SkeletalMeshEditorSubsystem.regenerate_lod(mesh, LOD_COUNT, False, False))
                        row['configure'] = bool(helper('ConfigureCreatureLODs')(mesh))
                        if row['configure']:
                            row['regenerate_2'] = bool(u.SkeletalMeshEditorSubsystem.regenerate_lod(mesh, 0, False, False))
                        row['lod_action'] = 'generated'
                        changed = True
                    except Exception:
                        row['lod_action'] = 'failed'
                        warn('%s LOD generation failed (kept %s LODs): %s' % (mesh_path, row['lods_before'],
                                                                              traceback.format_exc(limit=2)))
                row['lods_after'] = mesh_lods(mesh)
                b = mesh.get_bounds()
                row['raw_height_cm'] = round(2 * b.box_extent.z, 1)
                if changed:
                    touch(mesh, made)
                try:
                    if made or AL.get_skeleton_preview_mesh(skel, False) is None:
                        AL.set_skeleton_preview_mesh(skel, mesh, True)
                        touch(skel, created)
                except Exception:
                    warn('%s preview mesh not set: %s' % (skel_path, traceback.format_exc(limit=1)))
            info['ok'] = True
        except Exception:
            info['ok'] = False
            info['error'] = traceback.format_exc()
            warn('body %s unavailable: %s' % (key, info['error'].strip().splitlines()[-1]))


# ---------------------------------------------------------------------------------------------
# 2. Skeleton compatibility

def make_compatible():
    sources = {k: load(p, u.Skeleton) for k, p in SOURCE_SKELETONS.items()}
    make = helper('MakeSkeletonCompatible')
    for body, path in BODY_SKELETONS.items():
        row = REPORT['compatibility'].setdefault(body, {'skeleton': path})
        if not EA.does_asset_exist(path):
            row['skipped'] = 'skeleton missing (body copy failed)'
            continue
        skel = load(path, u.Skeleton)
        row['before'] = compatible_paths(skel)
        row['results'] = {}
        for key, source in sources.items():
            if pathish(source) == path:
                continue
            ok = bool(make(skel, source))
            row['results'][key] = ok
            if not ok:
                REPORT['errors'].append('MakeSkeletonCompatible(%s, %s) returned False' % (path, pathish(source)))
        row['after'] = compatible_paths(skel)
        # MakeSkeletonCompatible leaves the package clean when nothing changed; it may also have fixed the
        # retargeting modes without changing the list, so the dirty flag decides what is saved.
        try:
            dirty = path in dirty_packages()
        except Exception:
            dirty = row['after'] != row['before']
        row['changed'] = dirty
        if dirty:
            touch(skel, False)


# ---------------------------------------------------------------------------------------------
# 3a. Measurements

def pose_points(seq, bones, mesh=None, fps=60):
    options = u.AnimPoseEvaluationOptions()
    if mesh is not None:
        options.optional_skeletal_mesh = mesh
        options.should_retarget = True
    length = seq.get_play_length()
    n = max(30, int(round(length * fps)))
    dt = length / n
    frames = []
    for i in range(n + 1):
        t = min(i * dt, length - 1e-4)
        pose = u.AnimPoseExtensions.get_anim_pose_at_time(seq, t, options)
        frames.append((t, {b: pose.get_bone_pose(b, u.AnimPoseSpaces.WORLD).translation for b in bones}))
    return frames, dt, length


def peak_reach(seq):
    """Time of the largest planar hand-to-pelvis distance inside REACH_WINDOW (the Lakeside Variety method)."""
    frames, _, length = pose_points(seq, ['pelvis', 'hand_l', 'hand_r', 'root'], fps=60)
    lo, hi = REACH_WINDOW[0] * length, REACH_WINDOW[1] * length
    best = (-1.0, None, None)
    curve = []
    for t, p in frames:
        pel = p['pelvis']
        d = {h: math.hypot(p[h].x - pel.x, p[h].y - pel.y) for h in ('hand_l', 'hand_r')}
        hand = max(d, key=d.get)
        curve.append((t, d[hand]))
        if lo <= t <= hi and d[hand] > best[0]:
            best = (d[hand], t, hand)
    start = curve[0][1]
    r0, r1 = frames[0][1]['root'], frames[-1][1]['root']
    p0, p1 = frames[0][1]['pelvis'], frames[-1][1]['pelvis']
    return {'time': round(best[1], 3), 'fraction': round(best[1] / length, 3), 'reach_cm': round(best[0], 1),
            'hand': best[2], 'reach_at_start_cm': round(start, 1), 'length': round(length, 3),
            'root_drift_cm': round(math.hypot(r1.x - r0.x, r1.y - r0.y), 1),
            'pelvis_drift_cm': round(math.hypot(p1.x - p0.x, p1.y - p0.y), 1)}


def drift(seq):
    frames, _, length = pose_points(seq, ['root', 'pelvis'], fps=15)
    r0, r1 = frames[0][1]['root'], frames[-1][1]['root']
    p0, p1 = frames[0][1]['pelvis'], frames[-1][1]['pelvis']
    return {'length': round(length, 3), 'root_drift_cm': round(math.hypot(r1.x - r0.x, r1.y - r0.y), 1),
            'pelvis_drift_cm': round(math.hypot(p1.x - p0.x, p1.y - p0.y), 1), 'pelvis_drop_cm': round(p0.z - p1.z, 1)}


def foot_speed(seq, mesh=None, scale=1.0):
    """Median planted-foot speed relative to the root in world cm/s (evaluated positions times scale); a frame
    pair counts as planted when the foot is within 2.5 cm of its lowest point and its vertical speed is under
    40 cm/s. Returns (speed or None if fewer than 3 planted pairs, planted pair count)."""
    frames, dt, _ = pose_points(seq, ['root', 'foot_l', 'foot_r'], mesh=mesh, fps=60)
    speeds = []
    for foot in ('foot_l', 'foot_r'):
        pts = [((p[foot].x - p['root'].x) * scale, (p[foot].y - p['root'].y) * scale, (p[foot].z - p['root'].z) * scale)
               for _, p in frames]
        low = min(v[2] for v in pts)
        for a, b in zip(pts, pts[1:]):
            if max(a[2], b[2]) > low + 2.5 or abs(b[2] - a[2]) / dt > 40:
                continue
            planar = math.hypot(b[0] - a[0], b[1] - a[1]) / dt
            if planar > 25:
                speeds.append(planar)
    speeds.sort()
    return (speeds[len(speeds) // 2] if len(speeds) >= 3 else None), len(speeds)


def measured_world_speed(seq, mesh, height):
    """World cm/s of a gait clip at rate 1 on this body (Kid / RefineCharacterAssets method), with fallbacks."""
    row = {}
    try:
        extent = mesh.get_bounds().box_extent.z
        scale = height / (2.0 * extent) if extent > 0 else 1.0
        row['runtime_scale'] = round(scale, 4)
        world, n = foot_speed(seq, mesh, scale)
        row.update({'planted_pairs': n})
        if world:
            row['world_cm_s'] = round(world, 1)
            row['method'] = 'on_body'
            return row
    except Exception:
        row['on_body_error'] = traceback.format_exc(limit=1)
    try:
        pack = set_of(seq.get_path_name().split('.')[0])
        # Pack clips evaluate at the pack mannequin's size; a Lakeside clip is already on the body's skeleton.
        scale = height / SOURCE_HEIGHT[pack] if pack in SOURCE_HEIGHT else row.get('runtime_scale', 1.0)
        world, n = foot_speed(seq, None, scale)
        row.update({'pack_planted_pairs': n})
        if world:
            row['world_cm_s'] = round(world, 1)
            row['method'] = 'pack_space_scaled'
            return row
    except Exception:
        row['pack_error'] = traceback.format_exc(limit=1)
    row['world_cm_s'] = None
    row['method'] = 'none (rate 1)'
    return row


def gait_facing(seq, mesh, fps=30):
    """Component-space facing of a gait clip retargeted onto the body (the compatible-skeleton path):
    toes = (ball_l - foot_l) + (ball_r - foot_r), hips = perpendicular of thigh_l -> thigh_r (sign toward the
    toes), each averaged over the cycle."""
    options = u.AnimPoseEvaluationOptions()
    options.optional_skeletal_mesh = mesh
    options.should_retarget = True
    length = seq.get_play_length()
    n = max(20, int(round(length * fps)))
    tx = ty = hx = hy = 0.0
    for i in range(n):
        t = min(i * length / n, length - 1e-4)
        pose = u.AnimPoseExtensions.get_anim_pose_at_time(seq, t, options)
        q = {b: pose.get_bone_pose(b, u.AnimPoseSpaces.WORLD).translation
             for b in ('foot_l', 'ball_l', 'foot_r', 'ball_r', 'thigh_l', 'thigh_r')}
        vx = (q['ball_l'].x - q['foot_l'].x) + (q['ball_r'].x - q['foot_r'].x)
        vy = (q['ball_l'].y - q['foot_l'].y) + (q['ball_r'].y - q['foot_r'].y)
        vn = math.hypot(vx, vy) or 1.0
        tx, ty = tx + vx / vn, ty + vy / vn
        lx, ly = q['thigh_r'].x - q['thigh_l'].x, q['thigh_r'].y - q['thigh_l'].y
        ln = math.hypot(lx, ly) or 1.0
        hx, hy = hx + lx / ln, hy + ly / ln
    toes = math.degrees(math.atan2(ty, tx))
    line = math.degrees(math.atan2(hy, hx))
    hips = min((line + 90.0, line - 90.0), key=lambda a: abs(((a - toes) + 180.0) % 360.0 - 180.0))
    return {'clip': pathish(seq), 'toes_yaw': round(toes, 1), 'hips_yaw': round(((hips + 180.0) % 360.0) - 180.0, 1),
            'toes_consistency': round(math.hypot(tx, ty) / n, 3)}


# AFS 2026-10-31 (review): MeshYawOffset per definition, recorded here instead of measured at runtime (the live check
# read stale off-screen poses, overwrote a shared cache and snapped at the 45 deg boundary). The values are the
# runtime walk-cycle measurements from the rendered proofs (proof_abs_5.log / proof_abs_6.log,
# HOVER_ZOMBIE_MESH_YAW_LIVE: component-space toe yaw of the animated pose on the live mesh, 2-3 zombies per type,
# every sample of a type rounding to the same quarter turn): Standard bodies 171..180 deg -> 180, Lakeside /
# Etherion / ZombieMale bodies 86..106 deg -> -90, Drifter / Plant / EtherionB (vendor AS_Walking_Anim and the sneak
# walk, turned in the clip itself) 50..77 deg -> -90, which also matches their run clips.
# AnimPose evaluation (gait_facing) cannot stand in for that measurement: it retargets the clip straight onto
# the body, while at runtime the clip passes through ABP_ZombieMaster's ZESP skeleton first, and for the Standard
# bodies the two differ by 90 deg. It is recorded next to each value as a cross-check only.
# Types never measured in a rendered run (Brute, Kid) are left unaligned (bAlignMeshYaw False, the pre-pass state).
MEASURED_MESH_YAW = {'Shambler': 180.0, 'Lurcher': 180.0, 'Runner': 180.0, 'Brawler': 180.0,
                     'Horror': -90.0, 'Bog': -90.0, 'Pirate': -90.0, 'Plant': -90.0,
                     'EtherionA': -90.0, 'EtherionB': -90.0, 'Drifter': -90.0}


def mesh_yaw(clips, mesh, label):
    """(bAlignMeshYaw, MeshYawOffset) for a type; records the AnimPose cross-check in the receipt."""
    info = {'measured_runtime_offset': MEASURED_MESH_YAW.get(label)}
    try:
        info['animpose_clips'] = [gait_facing(c, mesh) for c in clips]
    except Exception:
        info['animpose_error'] = traceback.format_exc(limit=1)
    REPORT.setdefault('mesh_yaw', {})[label] = info
    if label not in MEASURED_MESH_YAW:
        warn('%s: no runtime mesh-yaw measurement; mesh left unaligned' % label)
        return False, 0.0
    return True, float(MEASURED_MESH_YAW[label])


def moving_clips(gait):
    return [load(p, u.AnimSequence) for p, target in gait if target > 0]


# ---------------------------------------------------------------------------------------------
# 3b. Montages and blend spaces

MONTAGE_CACHE = {}


def lakeside_reference_time(source):
    """Notify time of the existing Lakeside Variety AM_<Clip> montage for a Variety sequence (comparison only)."""
    if '/Variety/' not in source or '_anim_' not in source:
        return None
    path = source.rsplit('/', 1)[0] + '/AM_' + source.split('_anim_', 1)[1]
    if not EA.does_asset_exist(path):
        return None
    try:
        m = EA.load_asset(path)
        return [round(AL.get_anim_notify_event_trigger_time(e), 3) for e in AL.get_animation_notify_events(m)]
    except Exception:
        return None


def ensure_montage(ref):
    """Create or verify the NYC montage for a ref; returns the montage (existing refs are loaded, never edited)."""
    path = montage_path(ref)
    if path in MONTAGE_CACHE:
        return MONTAGE_CACHE[path]
    if 'use' in ref:
        montage = load(path, u.AnimMontage)
        REPORT['montages'][path] = {'state': 'referenced (not edited)',
                                    'slots': [str(s) for s in AL.get_montage_slot_names(montage)],
                                    'length': round(montage.get_play_length(), 3)}
        MONTAGE_CACHE[path] = montage
        return montage
    role, source = ref['make'], ref['source']
    seq = load(source, u.AnimSequence)
    pkg, name = path.rsplit('/', 1)
    created = not EA.does_asset_exist(path)
    if created:
        factory = u.AnimMontageFactory()
        # SourceAnimation only: the engine factory requires TargetSkeleton unset or equal to the clip's skeleton.
        factory.set_editor_property('source_animation', seq)
        montage = create_asset(name, pkg, u.AnimMontage, factory)
    else:
        montage = load(path, u.AnimMontage)
    first = montage.get_first_anim_reference()
    assert first and pathish(first) == source, '%s plays %s, not %s; refusing to rewrite it' % (path, pathish(first), source)
    row = {'state': 'created' if created else 'existing', 'role': role, 'source': source,
           'skeleton': pathish(skeleton_of(montage))}
    changed = created
    slot = SLOT[role]
    before = [str(s) for s in AL.get_montage_slot_names(montage)]
    if before != [slot]:
        assert helper('SetMontageSlot')(montage, slot), 'SetMontageSlot refused %s -> %s' % (path, slot)
        changed = True
    row['slots'] = [str(s) for s in AL.get_montage_slot_names(montage)]
    if row['slots'] != [slot]:
        REPORT['readback_mismatches'].append({'field': path + '.slot', 'expected': [slot], 'actual': row['slots']})
    length = montage.get_play_length()
    row['length'] = round(length, 3)
    # Deaths hold the last pose (the vendor ragdolls at length - 0.1 s); everything else blends out normally.
    want_blend_out = role != 'death'
    if put(montage, 'bEnableAutoBlendOut', want_blend_out, 'AnimMontage', []):
        changed = True
    row['auto_blend_out'] = bool(montage.get_editor_property(resolve(montage, 'bEnableAutoBlendOut', 'AnimMontage')))
    if role == 'attack':
        reach = peak_reach(seq)
        row['peak_reach'] = reach
        row['lakeside_variety_times'] = lakeside_reference_time(source)
        at = min(max(reach['time'], .05), max(length - .05, .05))
        events = AL.get_animation_notify_events_for_track(montage, HIT_TRACK) \
            if AL.is_valid_anim_notify_track_name(montage, HIT_TRACK) else []
        have = [(AL.get_anim_notify_event_trigger_time(e), e.get_editor_property('notify')) for e in events]
        good = len(have) == 1 and abs(have[0][0] - at) < .01 and have[0][1] and \
            have[0][1].get_class().get_name() == 'ZE_ZombieAnimNotify_AttackHit'
        if not good:
            if AL.is_valid_anim_notify_track_name(montage, HIT_TRACK):
                AL.remove_animation_notify_events_by_track(montage, HIT_TRACK)
            else:
                AL.add_animation_notify_track(montage, HIT_TRACK, u.LinearColor(1, .3, .1, 1))
            notify = AL.add_animation_notify_event(montage, HIT_TRACK, at,
                                                   u.ZE_ZombieAnimNotify_AttackHit.static_class())
            assert notify, '%s: add_animation_notify_event failed' % path
            changed = True
        got = [(round(AL.get_anim_notify_event_trigger_time(e), 3),
                e.get_editor_property('notify').get_class().get_name() if e.get_editor_property('notify') else None)
               for e in AL.get_animation_notify_events_for_track(montage, HIT_TRACK)]
        row['notifies'] = got
        if got != [(round(at, 3), 'ZE_ZombieAnimNotify_AttackHit')]:
            REPORT['readback_mismatches'].append({'field': path + '.' + HIT_TRACK, 'expected': round(at, 3),
                                                  'actual': got})
    else:
        row['drift'] = drift(seq)
        if row['drift']['root_drift_cm'] > 40 or row['drift']['pelvis_drift_cm'] > 60:
            warn('%s (%s, DefaultSlot) moves the root %.0f cm / pelvis %.0f cm; it will pop back when it ends' % (
                path, role, row['drift']['root_drift_cm'], row['drift']['pelvis_drift_cm']))
    if changed:
        touch(montage, created)
    REPORT['montages'][path] = row
    MONTAGE_CACHE[path] = montage
    return montage


def sample_rows(bs):
    return [(pathish(s.get_editor_property('animation')), round(s.get_editor_property('sample_value').x, 2),
             round(s.get_editor_property('rate_scale'), 3)) for s in bs.get_editor_property('sample_data')]


def ensure_gait(type_name, gait, mesh, height, axis_max):
    path = '%s/BS_NYC_%s_Gait' % (GAITS, type_name)
    clips = [load(p, u.AnimSequence) for p, _ in gait]
    skel = skeleton_of(clips[0])
    for c in clips[1:]:
        assert pathish(skeleton_of(c)) == pathish(skel), '%s mixes skeletons (%s vs %s)' % (
            path, pathish(skel), pathish(skeleton_of(c)))
    info = {'skeleton': pathish(skel), 'axis_max': axis_max, 'measured': {}}
    want = []
    for (clip_path, target), seq in zip(gait, clips):
        rate = 1.0
        if target > 0:
            m = measured_world_speed(seq, mesh, height)
            info['measured'][clip_path] = m
            if m.get('world_cm_s'):
                rate = max(RATE_CLAMP[0], min(RATE_CLAMP[1], target / m['world_cm_s']))
                m['foot_slide_at_target'] = round(target / (m['world_cm_s'] * rate), 2)
            else:
                warn('%s: no planted-foot speed for %s; RateScale left at 1' % (path, clip_path))
        want.append((clip_path, round(float(target), 2), round(rate, 3)))
    created = not EA.does_asset_exist(path)
    if created:
        factory = u.BlendSpaceFactory1D()
        factory.set_editor_property('target_skeleton', skel)
        bs = create_asset(path.rsplit('/', 1)[1], GAITS, u.BlendSpace1D, factory)
    else:
        bs = load(path, u.BlendSpace1D)
    axis = bs.get_editor_property('blend_parameters')[0]
    have_axis = (str(axis.get_editor_property('display_name')), round(axis.get_editor_property('max'), 2))
    rows_match = lambda: same([list(r) for r in sample_rows(bs)], [list(w) for w in want])  # noqa: E731
    if created or not rows_match() or have_axis != ('Speed', round(axis_max, 2)):
        assert helper('BuildSpeedBlend1D')(bs, clips, [float(t) for _, t in gait], float(axis_max)), \
            'BuildSpeedBlend1D refused ' + path
        samples = list(bs.get_editor_property('sample_data'))  # copies; RateScale only, written back whole
        assert len(samples) == len(want), '%s has %d samples, expected %d' % (path, len(samples), len(want))
        for s, (clip_path, _, rate) in zip(samples, want):
            assert pathish(s.get_editor_property('animation')) == clip_path, '%s sample order' % path
            s.set_editor_property('rate_scale', rate)
        bs.set_editor_property('sample_data', samples)
        try:
            bs.set_preview_skeletal_mesh(mesh)
        except Exception:
            pass
        touch(bs, created)
        info['state'] = 'created' if created else 'rebuilt'
    else:
        info['state'] = 'unchanged'
    info['samples'] = sample_rows(bs)
    if not rows_match():
        REPORT['readback_mismatches'].append({'field': path + '.SampleData', 'expected': want, 'actual': info['samples']})
    axis = bs.get_editor_property('blend_parameters')[0]
    info['axis'] = [str(axis.get_editor_property('display_name')), axis.get_editor_property('min'),
                    axis.get_editor_property('max')]
    REPORT['blendspaces'][path] = info
    return bs


# ---------------------------------------------------------------------------------------------
# 4. Definitions

def ensure_definition(name, template):
    path = '%s/DA_NYC_%s' % (ROSTER, name)
    if EA.does_asset_exist(path):
        return load(path, u.HoverCyberZombieDefinition), False, path
    da = EA.duplicate_asset(template, path)
    assert da and isinstance(da, u.HoverCyberZombieDefinition), 'duplicate_asset failed %s -> %s' % (template, path)
    return da, True, path


def sounds(paths):
    return [load(p) for p in paths]


def common_fields(spec):
    """AFS|Voice / AFS|Blood / AFS|Variety values shared by standards, Brute and Kid."""
    v = spec['voice']
    fields = {
        'IdleVocals': sounds(v['IdleVocals']), 'ChaseVocals': sounds(v['ChaseVocals']),
        'AttackVocals': sounds(v['AttackVocals']), 'PainVocals': sounds(v['PainVocals']),
        'DeathVocals': sounds(v['DeathVocals']), 'FootstepSounds': sounds(FOOTSTEPS),
        'VoicePitch': u.Vector2D(*v['VoicePitch']), 'VoiceVolume': float(v['VoiceVolume']),
        'VocalInterval': u.Vector2D(*v['VocalInterval']), 'FootstepVolume': float(spec['step_volume']),
        'FootstepStride': float(spec['stride']),
        # HitBlood stays empty: P_BigSplash_Hit drew a flat 1-1.5 m red disc at the hit point (2026-10-31 stills);
        # an empty field keeps the proven NS_NS1_BloodShot body-hit path in AHoverCyberZombie::TakeDamage.
        'HitBlood': None, 'HeadshotBlood': load(BLOOD_HEAD), 'DeathBlood': load(BLOOD_DEATH),
        'BloodScale': float(spec.get('blood_scale', 1.0)),
        'ScaleJitter': u.Vector2D(*spec['scale']), 'AnimRateJitter': u.Vector2D(*spec['rate']),
        'SightRoarMontage': ensure_montage(spec['roar']) if spec.get('roar') else None,
        'SightRoarChance': float(spec['roar_chance']) if spec.get('roar') else 0.0,
        # The vendor one-shot sounds stay empty: the palettes above replace them.
        'AggroSound': None, 'AttackSound': None, 'DeathSound': None,
    }
    return fields


def write_definition(da, scope, fields, stats_values):
    changes = []
    for cpp, value in fields.items():
        put(da, cpp, value, scope, changes)
    if stats_values:
        stats = da.get_editor_property(resolve(da, 'Stats', scope))
        stats_changes = []
        for cpp, value in stats_values.items():
            put(stats, cpp, value, 'ZE_ZombieStats', stats_changes)
        if stats_changes:
            da.set_editor_property(resolve(da, 'Stats', scope), stats)
            changes.extend('Stats.' + c for c in stats_changes)
    ok = all([check(da, cpp, value, scope) for cpp, value in fields.items()])
    if stats_values:
        got = da.get_editor_property(resolve(da, 'Stats', scope))
        ok = all([check(got, cpp, value, 'ZE_ZombieStats') for cpp, value in stats_values.items()]) and ok
    return changes, ok


def summarize(fields, extra):
    row = dict(extra)
    for cpp, value in fields.items():
        n = norm(value)
        row[cpp] = ('%d: %s' % (len(n), [x.rsplit('/', 1)[-1] for x in n if isinstance(x, str)])) \
            if isinstance(n, list) and cpp.endswith(('Vocals', 'Sounds')) else n
    return row


def author_standard(spec, bodies_ok):
    name = spec['name']
    body = spec['body']
    if body in BODY_COPIES and not bodies_ok.get(body):
        raise RuntimeError('body %s is unavailable (see bodies)' % body)
    mesh = load(spec['mesh'], u.SkeletalMesh)
    template = load(spec['template'], u.HoverCyberZombieDefinition)
    height = spec['height']
    axis_max = max(spec['max_run'], spec['gait'][-1][1] + 50.0)
    blend = ensure_gait(name, spec['gait'], mesh, height, axis_max)
    attacks = [ensure_montage(r) for r in spec['attacks']]
    hits = [ensure_montage(r) for r in spec['hits']]
    deaths = [ensure_montage(r) for r in spec['deaths']]
    fields = common_fields(spec)
    fields.update({
        **dict(zip(('bAlignMeshYaw', 'MeshYawOffset'), mesh_yaw(moving_clips(spec['gait']), mesh, name))),
        'AppearanceMesh': mesh, 'MovementBlendSpace': blend, 'AttackMontages': attacks,
        'HitReactionMontages': hits, 'DeathMontage': deaths[0], 'DeathMontageVariants': deaths,
        'Height': float(height), 'MaximumRunSpeed': float(spec['max_run']),
        'SkinMaterials': [load(p) for p in spec.get('skins', [])],
        'bRandomizeMorphTargets': bool(spec.get('morphs')), 'MorphTargetNames': list(spec.get('morphs', [])),
        'MorphTargetMax': float(spec.get('morph_max', .8)),
    })
    if spec.get('skins'):
        slot = str(mesh.get_editor_property('materials')[0].get_editor_property('material_slot_name'))
        fields['SkinMaterialSlot'] = u.Name(slot)
    else:
        fields['SkinMaterialSlot'] = u.Name('None')
    if spec.get('morphs'):
        have = set(str(x) for x in mesh.get_all_morph_target_names())
        missing = [m for m in spec['morphs'] if m not in have]
        if missing:
            warn('%s: morphs not on %s: %s (dropped)' % (name, spec['mesh'], missing))
            fields['MorphTargetNames'] = [m for m in spec['morphs'] if m in have]
    da, created, path = ensure_definition(name, spec['template'])
    scope = 'HoverCyberZombieDefinition[%s]' % name
    changes, ok = write_definition(da, scope, fields, {'WalkSpeed': float(spec['walk_speed'])})
    if created or changes:
        touch(da, created)
    REPORT['definitions'][path] = summarize(fields, {
        'identity': spec['identity'], 'template': spec['template'], 'state': 'created' if created else 'existing',
        'changes': changes, 'readback_ok': ok, 'WalkSpeed': spec['walk_speed'],
        'template_stats': {k: template.get_editor_property('stats').get_editor_property(k)
                           for k in ('max_health', 'melee_damage', 'attack_range', 'attack_cooldown')}})
    assert ok, '%s read-back mismatch (see readback_mismatches)' % path
    return da


def author_brute():
    spec = BRUTE
    template = load(BRUTE_DA, u.HoverCyberZombieDefinition)
    mesh = template.get_editor_property('appearance_mesh')
    height = template.get_editor_property('height')
    max_run = template.get_editor_property('maximum_run_speed')
    blend = ensure_gait('Brute', spec['gait'], mesh, height, max(max_run, spec['gait'][-1][1] + 50.0))
    # Keep the Brute's own attacks (AM_Attack_01/02, AM_Brute_Stomp, AM_Brute_Smash) and hit reaction.
    attacks = list(template.get_editor_property('attack_montages'))
    hits = list(template.get_editor_property('hit_reaction_montages')) + [ensure_montage(r) for r in spec['extra_hits']]
    deaths = [ensure_montage(r) for r in spec['deaths']]
    fields = common_fields(spec)
    fields.update(dict(zip(('bAlignMeshYaw', 'MeshYawOffset'), mesh_yaw(moving_clips(spec['gait']), mesh, 'Brute'))))
    fields.update({'MovementBlendSpace': blend, 'AttackMontages': attacks, 'HitReactionMontages': hits,
                   'DeathMontage': deaths[0], 'DeathMontageVariants': deaths, 'SkinMaterials': [],
                   'SkinMaterialSlot': u.Name('None'), 'bRandomizeMorphTargets': False, 'MorphTargetNames': []})
    da, created, path = ensure_definition('Brute', BRUTE_DA)
    changes, ok = write_definition(da, 'HoverCyberZombieDefinition[Brute]', fields, {})
    if created or changes:
        touch(da, created)
    REPORT['brute'] = summarize(fields, {'path': path, 'identity': spec['identity'], 'state': 'created' if created else
                                         'existing', 'changes': changes, 'readback_ok': ok, 'kept_attacks':
                                         [pathish(a) for a in attacks]})
    assert ok, '%s read-back mismatch' % path
    return da


def author_kid():
    spec = KID
    da = load(KID_DA, u.HoverCyberZombieDefinition)
    deaths = [load(p, u.AnimMontage) for p in spec['deaths_existing']]
    fields = common_fields(spec)
    kid_clips = [x.get_editor_property('animation') for x in da.get_editor_property('movement_blend_space')
                 .get_editor_property('sample_data') if x.get_editor_property('sample_value').x > 0]
    fields.update(dict(zip(('bAlignMeshYaw', 'MeshYawOffset'),
                           mesh_yaw([c for c in kid_clips if c], da.get_editor_property('appearance_mesh'), 'Kid'))))
    fields.update({'DeathMontageVariants': deaths, 'SkinMaterials': [], 'SkinMaterialSlot': u.Name('None'),
                   'bRandomizeMorphTargets': False, 'MorphTargetNames': []})
    changes, ok = write_definition(da, 'HoverCyberZombieDefinition[Kid]', fields, {})
    if changes:
        touch(da, False)
    REPORT['kid'] = summarize(fields, {'path': KID_DA, 'identity': spec['identity'], 'state': 'updated_in_place',
                                       'changes': changes, 'readback_ok': ok})
    assert ok, '%s read-back mismatch' % KID_DA
    return da


# ---------------------------------------------------------------------------------------------
# Run

def read_only_paths():
    paths = set(SOURCE_SKELETONS.values()) | {BRUTE_DA, ZESP_DEATH, ZESP_HIT, ZESP_ATTACK_01, ZESP_ATTACK_02}
    for vendor_skel, _, meshes in BODY_COPIES.values():
        paths.add(vendor_skel)
        paths.update(v for v, _ in meshes)
    for spec in TYPES:
        paths.add(spec['mesh'])
    for spec in TYPES + [BRUTE]:
        paths.add(spec['template'])
        paths.update(p for p, _ in spec['gait'])
    for spec in TYPES + [BRUTE, KID]:
        for key in ('attacks', 'hits', 'deaths', 'extra_hits'):
            for ref in spec.get(key, []):
                paths.add(ref.get('use') or ref['source'])
        if spec.get('roar'):
            paths.add(spec['roar']['source'])
        v = spec['voice']
        for key in ('IdleVocals', 'ChaseVocals', 'AttackVocals', 'PainVocals', 'DeathVocals'):
            paths.update(v[key])
    paths.update(FOOTSTEPS + [BLOOD_HIT, BLOOD_HEAD, BLOOD_DEATH] + ETHERION_SKINS)
    for body in ('Horror', 'BogZombie', 'Pirate', 'Plant'):
        paths.add(lake(body, 'da'))
        paths.add(lake(body, 'mesh'))
    return sorted(p for p in paths if not owned(p))


def preflight():
    pf = REPORT['preflight']
    letters = {n.replace('_', '') for n in dir(u.HoverAuthoring)}
    pf['helpers'] = {h: h.lower() in letters for h in HELPERS}
    cdo = u.get_default_object(u.HoverCyberZombieDefinition)
    pf['fields'] = {}
    for cpp in NEW_FIELDS:
        try:
            pf['fields'][cpp] = resolve(cdo, cpp, 'HoverCyberZombieDefinition')
        except Exception:
            pf['fields'][cpp] = None
    pf['missing_helpers'] = [h for h, ok in pf['helpers'].items() if not ok]
    pf['missing_fields'] = [f for f, n in pf['fields'].items() if n is None]
    try:
        pf['attack_notify_class'] = u.ZE_ZombieAnimNotify_AttackHit.static_class().get_name()
    except Exception:
        pf['attack_notify_class'] = None
    missing_assets = [p for p in read_only_paths() if not EA.does_asset_exist(p)]
    pf['missing_assets'] = missing_assets
    problems = []
    if pf['missing_helpers']:
        problems.append('HoverAuthoring helpers not compiled: %s' % pf['missing_helpers'])
    if pf['missing_fields']:
        problems.append('UHoverCyberZombieDefinition lacks the contract fields %s (run after the runtime build)'
                        % pf['missing_fields'])
    if not pf['attack_notify_class']:
        problems.append('ZE_ZombieAnimNotify_AttackHit is not reachable from Python')
    if missing_assets:
        problems.append('source assets missing: %s' % missing_assets)
    for tool in ('get_reference_pose', 'get_anim_pose_at_time'):
        if not hasattr(u.AnimPoseExtensions, tool):
            problems.append('AnimPoseExtensions.%s unavailable' % tool)
    return problems


def save_all():
    for path, (asset, created) in sorted(TOUCHED.items()):
        assert owned(path), 'refusing to save non-owned asset ' + path
        (REPORT['created'] if created else REPORT['modified']).append(path)
        if EA.save_loaded_asset(asset, False):
            REPORT['saved'].append(path)
        else:
            REPORT['errors'].append('save_loaded_asset failed for ' + path)


def main():
    global EA, AT, AL
    EA = u.EditorAssetLibrary
    AT = u.AssetToolsHelpers.get_asset_tools()
    AL = u.AnimationLibrary
    reads = read_only_paths()
    REPORT['untouched_hashes_before'] = {p: sha(file_of(p)) for p in reads}
    problems = preflight()
    if problems:
        REPORT['errors'].extend('preflight: ' + p for p in problems)
        return

    core = bone_names(load(std(1, 'skel'), u.Skeleton))
    REPORT['core_bone_count'] = len(core)
    copy_bodies(core)
    bodies_ok = {k: REPORT['bodies'].get(k, {}).get('ok', False) for k in BODY_COPIES}
    make_compatible()

    standards = []
    for spec in TYPES:
        try:
            standards.append(author_standard(spec, bodies_ok))
        except Exception:
            REPORT['failed_types'][spec['name']] = traceback.format_exc()
    brute = kid = None
    try:
        brute = author_brute()
    except Exception:
        REPORT['failed_types']['Brute'] = traceback.format_exc()
    try:
        kid = author_kid()
    except Exception:
        REPORT['failed_types']['Kid'] = traceback.format_exc()

    enc = load(ENCOUNTERS)
    REPORT['encounters']['before'] = {'Standards': norm(enc.get_editor_property('standards')),
                                      'Brute': norm(enc.get_editor_property('brute')),
                                      'Kid': norm(enc.get_editor_property('kid'))}
    if len(standards) >= MIN_STANDARDS:
        changes = []
        put(enc, 'Standards', standards, 'HoverNYCEncounterSettings', changes)
        if brute is not None:
            put(enc, 'Brute', brute, 'HoverNYCEncounterSettings', changes)
        if changes:
            touch(enc, False)
        REPORT['encounters']['changes'] = changes
        check(enc, 'Standards', standards, 'HoverNYCEncounterSettings')
        sync_wave_types(standards)
    else:
        REPORT['errors'].append('only %d standard types authored (need %d); DA_NYCEncounters left unchanged'
                                % (len(standards), MIN_STANDARDS))
    REPORT['encounters']['after'] = {'Standards': norm(enc.get_editor_property('standards')),
                                     'Brute': norm(enc.get_editor_property('brute')),
                                     'Kid': norm(enc.get_editor_property('kid'))}
    for name, tb in REPORT['failed_types'].items():
        REPORT['errors'].append('type %s failed: %s' % (name, tb.strip().splitlines()[-1]))

    save_all()
    REPORT['untouched_hashes_after'] = {p: sha(file_of(p)) for p in reads}
    REPORT['untouched_changed'] = [p for p, h in REPORT['untouched_hashes_before'].items()
                                   if REPORT['untouched_hashes_after'].get(p) != h]
    if REPORT['untouched_changed']:
        REPORT['errors'].append('read-only sources changed on disk: %s' % REPORT['untouched_changed'])
    if REPORT['readback_mismatches']:
        REPORT['errors'].append('%d read-back mismatches' % len(REPORT['readback_mismatches']))


def sync_wave_types(standards):
    """DA_NYCWaves.DefaultZombieTypes and every CustomWaves row's ZombieTypes = the roster standards."""
    info = REPORT['encounters'].setdefault('waves', {})
    waves = load(WAVES)
    want = [pathish(d) for d in standards]
    info['default_before'] = norm(waves.get_editor_property('default_zombie_types'))
    changed = []
    if [pathish(d) for d in (waves.get_editor_property('default_zombie_types') or [])] != want:
        waves.set_editor_property('default_zombie_types', list(standards))
        changed.append('DefaultZombieTypes')
    rows = list(waves.get_editor_property('custom_waves') or [])
    info['rows_before'] = [[pathish(d).rsplit('/', 1)[-1] for d in (r.get_editor_property('zombie_types') or [])]
                           for r in rows]
    rows_changed = 0
    # ZE_WaveConfig.ZombieTypes is DisableEditOnInstance, so set_editor_property refuses it; round-trip the
    # row through export_text / import_text with the ZombieTypes list replaced (every other field kept).
    import re as _re
    types_text = 'ZombieTypes=(%s)' % ','.join('"%s.%s"' % (p, p.rsplit('/', 1)[-1]) for p in want)
    for i, r in enumerate(rows):
        if [pathish(d) for d in (r.get_editor_property('zombie_types') or [])] != want:
            text = r.export_text()
            if 'ZombieTypes=' in text:
                text = _re.sub(r'ZombieTypes=\([^)]*\)', lambda m: types_text, text, count=1)
            else:
                text = text[:-1] + ',' + types_text + ')' if text.endswith(')') else text
            fresh = u.ZE_WaveConfig()
            fresh.import_text(text)
            rows[i] = fresh
            rows_changed += 1
    info['row_text_sample'] = rows[0].export_text()[:600] if rows else None
    if rows_changed:
        waves.set_editor_property('custom_waves', rows)  # struct arrays come back as copies
        changed.append('CustomWaves.ZombieTypes x%d' % rows_changed)
    if changed:
        touch(waves, False)
    info['changes'] = changed
    after = [pathish(d) for d in (waves.get_editor_property('default_zombie_types') or [])]
    rows_after = [[pathish(d) for d in (r.get_editor_property('zombie_types') or [])]
                  for r in (waves.get_editor_property('custom_waves') or [])]
    info['default_after'] = [p.rsplit('/', 1)[-1] for p in after]
    info['rows'] = len(rows_after)
    info['rows_match'] = all(r == want for r in rows_after)
    if after != want or not info['rows_match']:
        REPORT['errors'].append('DA_NYCWaves zombie types did not read back as the roster')


def summary():
    enc = REPORT['encounters'].get('after', {})
    return ('AUTHOR_ZOMBIES_DONE ok=%s standards=%d brute=%s kid=%s failed=%s montages=%d blendspaces=%d '
            'created=%d modified=%d saved=%d warnings=%d errors=%d untouched_changed=%d receipt=%s' % (
                REPORT['ok'], len(enc.get('Standards') or []), (enc.get('Brute') or '').rsplit('/', 1)[-1],
                (enc.get('Kid') or '').rsplit('/', 1)[-1], sorted(REPORT['failed_types']),
                len([m for m in REPORT['montages'].values() if m.get('state') != 'referenced (not edited)']),
                len(REPORT['blendspaces']), len(REPORT['created']), len(REPORT['modified']), len(REPORT['saved']),
                len(REPORT['warnings']), len(REPORT['errors']), len(REPORT['untouched_changed']), RECEIPT))


def write_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        REPORT['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
        RECEIPT.write_text(json.dumps(REPORT, indent=1, default=str))
    except Exception:
        print('AUTHOR_ZOMBIES receipt failed', traceback.format_exc(), flush=True)


def dry_run():
    plan = {'types': [{'name': s['name'], 'identity': s['identity'], 'body': s['body'], 'mesh': s.get('mesh'),
                       'template': s['template'], 'definition': '%s/DA_NYC_%s' % (ROSTER, s['name']),
                       'gait': s['gait'], 'blendspace': '%s/BS_NYC_%s_Gait' % (GAITS, s['name']),
                       'attacks': [montage_path(r) for r in s['attacks']],
                       'hits': [montage_path(r) for r in s['hits']],
                       'deaths': [montage_path(r) for r in s['deaths']],
                       'roar': montage_path(s['roar']) if s.get('roar') else None, 'roar_chance': s['roar_chance'],
                       'pitch': s['voice']['VoicePitch'],
                       'vocals': {k: len(v) for k, v in s['voice'].items() if k.endswith('Vocals')},
                       'max_run': s['max_run'], 'height': s['height'], 'skins': len(s.get('skins', [])),
                       'morphs': len(s.get('morphs', []))} for s in TYPES],
            'brute': {'definition': ROSTER + '/DA_NYC_Brute', 'gait': BRUTE['gait'],
                      'deaths': [montage_path(r) for r in BRUTE['deaths']], 'roar': montage_path(BRUTE['roar'])},
            'kid': {'definition': KID_DA, 'roar': montage_path(KID['roar']), 'pitch': KID['voice']['VoicePitch']},
            'body_copies': BODY_COPIES, 'body_skeletons': BODY_SKELETONS, 'sources': SOURCE_SKELETONS,
            'python_names': {f: candidates(f) for f in NEW_FIELDS}, 'no_lods': NO_LODS}
    if u is None:
        plan['read_only'] = 'computed in Unreal only'
    print('AUTHOR_ZOMBIES_PLAN', json.dumps(plan, indent=1, default=str), flush=True)
    print('AUTHOR_ZOMBIES_DONE dry_run standards=%d' % len(TYPES), flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def run():
    try:
        assert u, 'AuthorZombieDiversity must run inside the Unreal Editor (use --dry-run elsewhere)'
        main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors']
        write_receipt()
        line = summary()
        for w in REPORT['warnings']:
            print('AUTHOR_ZOMBIES warning', w, flush=True)
        for e in REPORT['errors']:
            print('AUTHOR_ZOMBIES error', e, flush=True)
        print(line, flush=True)
        if u:
            u.log_warning(line)
            u.SystemLibrary.quit_editor()


if DRY_RUN:
    dry_run()
else:
    run()
