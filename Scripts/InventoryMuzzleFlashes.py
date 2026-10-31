"""InventoryMuzzleFlashes.py - every muzzle-flash-like FX asset in /Game and what Python can change on it (CPU).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      "-ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/InventoryMuzzleFlashes.py [--dup=SRC:DSTNAME[:r,g,b[:scale]]]"
      -nullrhi -unattended -nosplash -stdout -FullStdOutLogOutput -abslog=<log>

Owner 2026-10-30 23:40, on the blue starburst the rusty M4A1 fires (the Ballista's NS_BallistaMuzzle, which every
rigged gun inherits): "Maybe gun flash is more red/orange, instead of comic book blue. Could also try small explosion
effect instead." UHoverGunRig::MuzzleFlashOverride can now point a rig at any Niagara system; this script finds the
candidates:

  * every NiagaraSystem and (legacy Cascade) ParticleSystem under /Game whose path or name contains
    muzzle / flash / shot / explo / spark, plus the MuzzleFlashFX of every /Game/ZESP/ZE/Data/Weapons/DA_Weapon_*
    definition (Niagara or Cascade), described by UHoverAuthoring.describe_flash_asset: exposed USER parameters
    (name / type / value: the only knobs a component or a Python helper can set without the Niagara editor), emitter
    names, renderers (a light renderer is what whites the character out), loop / lifetime / colour / size constants
    read from the module stacks, and an estimated duration (loop delay + loop duration x count + longest lifetime;
    -1 = loops forever, -2 = nothing readable).
  * a warm / cool verdict per asset from its colour constants and user colours (R vs B), so "warm as-is" candidates
    fall out without opening the editor.

--dup=SRC:DSTNAME[:r,g,b[:scale]] duplicates SRC (a /Game Niagara system) to /Game/HoverPrototype/Effects/DSTNAME
with EditorAssetLibrary.duplicate_asset and, ONLY through exposed user parameters (UHoverAuthoring.set_niagara_user_color
/ _float on names containing color / tint / scale / size), sets the colour and scale; it reports which parameters it
could set. Emitter internals (module inputs) are never edited here: a flash whose colour lives only in its emitter
stack is reported as "Niagara editor only".

Receipt: D:/AFS_Comparisons/Flash_20261031/inventory.json. Saves nothing unless --dup is given (then only the copy).
"""
import json
import re
import sys
import time
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/Flash_20261031')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'inventory.json'
ARGS = sys.argv[1:]
EA = u.EditorAssetLibrary
NAME_RE = re.compile(r'muzzle|flash|shot|explo|spark', re.I)
# Wider net, flagged 'scan-ext': vendor packs name muzzle flashes after the gun ("..._Fire", "..._Burst").
EXT_RE = re.compile(r'fire|gun|burst|blast|impact|hit', re.I)
WEAPON_DIR = '/Game/ZESP/ZE/Data/Weapons'
PROTO = '/Game/HoverPrototype/Effects'
# Candidate rules: a one-shot flash should be gone within half a second; "small explosion" gets a little more.
FLASH_MAX_S = 0.5
EXPLOSION_MAX_S = 1.0

R = {'ok': False, 'errors': [], 'notes': [], 'assets': {}, 'weapon_definitions': {}, 'candidates': {},
     'duplicate': None, 'counts': {}}


def log(*a):
    line = 'FLASHINV ' + ' '.join(str(x) for x in a)
    print(line, flush=True)
    u.log(line)


def save():
    RECEIPT.write_text(json.dumps(R, indent=1, default=str))


def pkg_of(asset_data):
    return str(asset_data.package_name)


def describe(obj):
    txt = u.HoverAuthoring.describe_flash_asset(obj)
    return json.loads(txt) if txt else None


def warm_verdict(desc):
    """'warm' / 'cool' / 'white' / 'unknown' from every colour constant and user colour with a value."""
    colours = []
    for p in desc.get('user_parameters', []):
        if p.get('type') == 'LinearColor' and isinstance(p.get('value'), list):
            colours.append(p['value'])
    for e in desc.get('emitters', []):
        if not e.get('enabled', True):
            continue
        for c in e.get('constants', []):
            if c.get('type') == 'LinearColor' and isinstance(c.get('value'), list):
                colours.append(c['value'])
        for r in e.get('renderers', []):
            if r.get('class') == 'NiagaraLightRendererProperties' and isinstance(r.get('color_add'), list):
                colours.append(r['color_add'] + [1.0])
    if not colours:
        return 'unknown', colours
    # Weight by brightness so a dim grey tint does not outvote the bright core.
    rs = sum(c[0] * max(1e-3, sum(c[:3])) for c in colours)
    bs = sum(c[2] * max(1e-3, sum(c[:3])) for c in colours)
    if rs > bs * 1.3:
        return 'warm', colours
    if bs > rs * 1.3:
        return 'cool', colours
    return 'white', colours


def colour_control(desc):
    """How the colour can be changed without the Niagara editor."""
    users = [p['name'] for p in desc.get('user_parameters', [])
             if p.get('type') == 'LinearColor' or re.search(r'colou?r|tint', p.get('name', ''), re.I)]
    scales = [p['name'] for p in desc.get('user_parameters', [])
              if p.get('type') in ('float', 'Vector2f', 'Vector') and re.search(r'scale|size', p.get('name', ''), re.I)]
    if users:
        return {'colour': 'user parameter(s) %s: set on the spawned component or baked into a duplicate with '
                          'UHoverAuthoring.set_niagara_user_color' % users, 'user_colour_params': users,
                'user_scale_params': scales}
    const_colours = [c['name'] for e in desc.get('emitters', []) for c in e.get('constants', [])
                     if c.get('type') == 'LinearColor']
    if const_colours:
        return {'colour': 'Niagara editor only (module-stack constants %s; a C++ rapid-iteration edit like '
                          'UHoverAuthoring::ConfigurePrototypeEffect would reach them, out of scope here)'
                          % const_colours[:4], 'user_colour_params': [], 'user_scale_params': scales,
                'stack_colour_constants': const_colours}
    return {'colour': 'Niagara editor only (colour is in the material / curve data, no readable constant)',
            'user_colour_params': [], 'user_scale_params': scales}


def inventory_asset(path, source):
    if path in R['assets']:
        R['assets'][path]['sources'].append(source)
        return R['assets'][path]
    row = {'path': path, 'sources': [source], 'ok': False}
    R['assets'][path] = row
    try:
        obj = EA.load_asset(path)
        if not obj:
            row['error'] = 'load failed'
            return row
        row['class'] = obj.get_class().get_name()
        desc = describe(obj)
        if not desc:
            row['error'] = 'describe_flash_asset returned nothing (not Niagara / Cascade?)'
            return row
        verdict, colours = warm_verdict(desc)
        emitters = desc.get('emitters', [])
        row.update({
            'ok': True,
            'duration_s': desc.get('duration_s'), 'duration_known': desc.get('duration_known'),
            'warmth': verdict, 'colours_seen': colours[:8],
            'user_parameters': desc.get('user_parameters', []),
            'emitters': [{'name': e.get('name'), 'enabled': e.get('enabled'), 'sim_target': e.get('sim_target'),
                          'local_space': e.get('local_space'),
                          'renderers': [r.get('class') for r in e.get('renderers', [])],
                          'loop_behavior': e.get('loop_behavior'), 'loop_duration_s': e.get('loop_duration_s'),
                          'lifetime_max_s': e.get('lifetime_max_s'), 'duration_s': e.get('duration_s'),
                          'emitter_duration_s': e.get('emitter_duration_s'), 'emitter_loops': e.get('emitter_loops'),
                          'modules': [m.get('class') for m in e.get('modules', [])]} for e in emitters],
            'constants': {e.get('name'): e.get('constants', []) for e in emitters},
            # Loop Behavior / Duration are static switches in UE 5.8 (not rapid-iteration constants), so the system
            # duration is unknown (-2) and the longest InitializeParticle lifetime is the lower bound. In game it
            # hardly matters: AHoverPilot destroys the flash component after Tier.MuzzleFlashSeconds (0.10 s).
            'particle_lifetime_max_s': max([c['value'] for e in emitters if e.get('enabled', True)
                                            for c in e.get('constants', [])
                                            if 'InitializeParticle.Lifetime' in c.get('name', '')
                                            and isinstance(c.get('value'), (int, float))] or [None]),
            'on_screen_s_in_game': 0.10,
            'has_light_renderer': any(r.get('class') == 'NiagaraLightRendererProperties'
                                      for e in emitters if e.get('enabled', True) for r in e.get('renderers', [])),
            'gpu_emitters': [e.get('name') for e in emitters if e.get('sim_target') == 'GPU'],
            'colour_control': colour_control(desc),
        })
        log(path, row['class'], 'dur=%s' % row['duration_s'], row['warmth'],
            'light' if row['has_light_renderer'] else 'nolight', 'users=%d' % len(row['user_parameters']))
    except Exception:
        row['error'] = traceback.format_exc()
        R['errors'].append('%s: %s' % (path, row['error'][-400:]))
    return row


def soft_path(value):
    """Asset path of a soft-object property value (object, SoftObjectPath or None)."""
    if value is None:
        return None
    if hasattr(value, 'get_path_name'):
        return value.get_path_name().split('.')[0]
    t = str(value).strip("'\"")
    return t.split('.')[0] if t.startswith('/') else (t or None)


def weapon_definitions():
    ar = u.AssetRegistryHelpers.get_asset_registry()
    rows = ar.get_assets_by_path(WEAPON_DIR, True)
    for ad in rows:
        name = str(ad.asset_name)
        if not name.startswith('DA_Weapon_'):
            continue
        path = pkg_of(ad)
        info = R['weapon_definitions'][name] = {'path': path}
        try:
            d = EA.load_asset(path)
            fx = d.get_editor_property('muzzle_flash_fx')
            et = fx.get_editor_property('effect_type')
            info['effect_type'] = getattr(et, 'name', str(et).split('.')[-1])
            info['scale'] = fx.get_editor_property('scale')
            nia = cas = None
            try:
                nia = soft_path(fx.get_editor_property('niagara_fx'))
                cas = soft_path(fx.get_editor_property('cascade_fx'))
            except Exception as e:
                info['soft_read_error'] = str(e)
            if nia is None and cas is None:
                # Soft pointers may not resolve through the property API; the text export always names them.
                props = u.HoverAuthoring.describe_object_properties(d)
                txt = props.get('MuzzleFlashFX', '') if hasattr(props, 'get') else str(props)
                info['export'] = txt[:400]
                m = re.search(r"NiagaraFX=\"?[^'\"]*'([^'\"]+)'", txt)
                nia = m.group(1).split('.')[0] if m else None
                m = re.search(r"CascadeFX=\"?[^'\"]*'([^'\"]+)'", txt)
                cas = m.group(1).split('.')[0] if m else None
            info['niagara_fx'] = nia
            info['cascade_fx'] = cas
            used = nia if info['effect_type'] == 'NIAGARA' else cas
            info['active_fx'] = used
            for p in (nia, cas):
                if p and EA.does_asset_exist(p):
                    inventory_asset(p, 'weapon:' + name)
                elif p:
                    info.setdefault('missing', []).append(p)
        except Exception:
            info['error'] = traceback.format_exc()[-600:]
            R['errors'].append('%s: %s' % (name, info['error'][-300:]))


def scan_fx():
    ar = u.AssetRegistryHelpers.get_asset_registry()
    classes = (('/Script/Niagara', 'NiagaraSystem'), ('/Script/Engine', 'ParticleSystem'))
    n_all = 0
    for pkg, cls in classes:
        try:
            rows = ar.get_assets_by_class(u.TopLevelAssetPath(pkg, cls), False)
        except Exception as e:
            R['errors'].append('get_assets_by_class %s: %s' % (cls, e))
            rows = []
        R['counts'][cls + '_total'] = len(rows)
        for ad in rows:
            path = pkg_of(ad)
            if not path.startswith('/Game/'):
                continue
            n_all += 1
            R.setdefault('all_game_fx', []).append(path)
            if NAME_RE.search(path):
                inventory_asset(path, 'scan:' + cls)
            elif EXT_RE.search(path.rsplit('/', 1)[-1]):
                inventory_asset(path, 'scan-ext:' + cls)
    R['counts']['game_fx_total'] = n_all
    R['all_game_fx'] = sorted(R.get('all_game_fx', []))
    # The named project effects always go in, matched or not.
    for name in ('NS_BallistaMuzzle', 'NS_BallistaMuzzle_Pulse', 'NS_RifleMuzzle', 'NS_RifleMuzzle_Compact'):
        p = PROTO + '/' + name
        if EA.does_asset_exist(p):
            inventory_asset(p, 'named')
        else:
            R['notes'].append('named effect missing: ' + p)
    p = '/Game/ZESP/ZE/FX/Expo/NS_Explosion'
    if EA.does_asset_exist(p):
        inventory_asset(p, 'named:explosion')
    else:
        R['notes'].append('NS_Explosion missing at ' + p)


def pick_candidates():
    ok = [a for a in R['assets'].values() if a.get('ok')]
    short = lambda a, lim: a['duration_s'] is not None and 0 <= a['duration_s'] <= lim
    c = R['candidates']
    c['a_warm_as_is'] = sorted([a['path'] for a in ok if a['warmth'] == 'warm' and a['class'] == 'NiagaraSystem'
                                and (short(a, FLASH_MAX_S) or a['duration_s'] == -2)],
                               key=lambda p: (0 if 'uzzle' in p or 'lash' in p else 1, p))
    c['a_warm_cascade_legacy'] = [a['path'] for a in ok if a['warmth'] == 'warm' and a['class'] == 'ParticleSystem']
    c['b_rifle_muzzle'] = [a['path'] for a in ok if a['path'] in (PROTO + '/NS_RifleMuzzle_Compact',
                                                                     PROTO + '/NS_RifleMuzzle')]
    ex = R['assets'].get('/Game/ZESP/ZE/FX/Expo/NS_Explosion')
    c['c_small_explosion'] = {
        'path': ex['path'] if ex else None, 'duration_s': ex.get('duration_s') if ex else None,
        'short_enough': bool(ex and short(ex, EXPLOSION_MAX_S)),
        'warmth': ex.get('warmth') if ex else None,
        'colour_control': ex.get('colour_control') if ex else None}
    c['cool_or_white'] = [a['path'] for a in ok if a['warmth'] in ('cool', 'white')]
    c['unknown_colour'] = [a['path'] for a in ok if a['warmth'] == 'unknown']
    c['with_light_renderer'] = [a['path'] for a in ok if a.get('has_light_renderer')]
    c['with_user_colour_param'] = [a['path'] for a in ok if a['colour_control'].get('user_colour_params')]
    c['looping'] = [a['path'] for a in ok if a['duration_s'] == -1]


def duplicate(spec):
    """--dup=SRC:DSTNAME[:r,g,b[:scale]]"""
    parts = spec.split(':')
    src, dst = parts[0], PROTO + '/' + parts[1]
    colour = [float(x) for x in parts[2].split(',')] if len(parts) > 2 and parts[2] else None
    scale = float(parts[3]) if len(parts) > 3 and parts[3] else None
    info = R['duplicate'] = {'source': src, 'target': dst, 'colour': colour, 'scale': scale, 'set': [], 'unset': []}
    if not EA.does_asset_exist(src):
        info['error'] = 'source missing'
        return
    if EA.does_asset_exist(dst):
        info['state'] = 'existing'
        obj = EA.load_asset(dst)
    else:
        obj = EA.duplicate_asset(src, dst)
        info['state'] = 'created' if obj else 'duplicate_asset failed'
    if not obj:
        return
    desc = describe(obj) or {}
    for p in desc.get('user_parameters', []):
        name = p.get('name', '')
        if colour and p.get('type') == 'LinearColor' and re.search(r'colou?r|tint', name, re.I):
            ok = u.HoverAuthoring.set_niagara_user_color(obj, name, u.LinearColor(*(colour + [1.0])[:4]))
            (info['set'] if ok else info['unset']).append(name)
        elif scale is not None and p.get('type') == 'float' and re.search(r'scale|size', name, re.I):
            ok = u.HoverAuthoring.set_niagara_user_float(obj, name, scale)
            (info['set'] if ok else info['unset']).append(name)
    if not desc.get('user_parameters'):
        info['note'] = 'no exposed user parameters: the copy is identical to the source; colour / size need the Niagara editor'
    info['saved'] = EA.save_loaded_asset(obj, False)
    info['after'] = inventory_asset(dst, 'duplicate') if info['saved'] else None


def main():
    t0 = time.monotonic()
    try:
        scan_fx()
        weapon_definitions()
        pick_candidates()
        for a in ARGS:
            if a.startswith('--dup='):
                duplicate(a[len('--dup='):])
        R['counts']['inventoried'] = len(R['assets'])
        R['counts']['described_ok'] = sum(1 for a in R['assets'].values() if a.get('ok'))
        R['ok'] = not R['errors'] and R['counts']['described_ok'] > 0
    except Exception:
        R['errors'].append(traceback.format_exc())
    R['seconds'] = round(time.monotonic() - t0, 1)
    save()
    log('RESULT ok=%s assets=%d ok=%d errors=%d receipt=%s' % (R['ok'], len(R['assets']),
                                                               R['counts'].get('described_ok', 0), len(R['errors']),
                                                               RECEIPT))
    print('FLASHINV_CANDIDATES', json.dumps(R['candidates'], default=str)[:3000], flush=True)


main()
u.SystemLibrary.quit_editor()
