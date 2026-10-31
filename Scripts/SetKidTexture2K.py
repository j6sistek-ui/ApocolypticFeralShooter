"""Raise the Kid zombie's runtime texture cap from 1K to 2K (owner decision 2026-10-29: 2K minimum).

Run via Unreal -ExecutePythonScript with -RenderOffscreen. Changes exactly three texture assets'
MaxTextureSize (1024 -> 2048); source data stays 4096. Writes a receipt under Saved/HoverPrototype/.
"""
import hashlib, json, traceback
from pathlib import Path
import unreal as u

root = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'HoverPrototype' / 'KidTexture2K'
root.mkdir(parents=True, exist_ok=True)
content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
ASSETS = ['/Game/HoverPrototype/ZombieEngine/Variants/Kid/T_Kid_0_BaseColor',
          '/Game/HoverPrototype/ZombieEngine/Variants/Kid/T_Kid_0_Normal',
          '/Game/HoverPrototype/ZombieEngine/Variants/Kid/T_Kid_0_RM']
TARGET = 2048
r = {'target': TARGET, 'assets': {}, 'errors': []}
EA = u.EditorAssetLibrary
try:
    for p in ASSETS:
        f = content / (p[len('/Game/'):] + '.uasset')
        before_hash = hashlib.sha256(f.read_bytes()).hexdigest()
        t = u.load_asset(p)
        assert isinstance(t, u.Texture2D), p
        before = int(t.get_editor_property('max_texture_size'))
        info_before = u.HoverAuthoring.inspect_texture(t)
        if before != TARGET:
            t.set_editor_property('max_texture_size', TARGET)
            EA.save_loaded_asset(t, False)
        after = int(t.get_editor_property('max_texture_size'))
        r['assets'][p] = {'max_before': before, 'max_after': after, 'source': [t.blueprint_get_size_x(), t.blueprint_get_size_y()],
                          'file_hash_before': before_hash, 'file_hash_after': hashlib.sha256(f.read_bytes()).hexdigest(),
                          'inspect_before': info_before, 'inspect_after': u.HoverAuthoring.inspect_texture(t)}
except Exception:
    r['errors'].append(traceback.format_exc())
(root / 'receipt.json').write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
u.log_warning('SetKidTexture2K: ' + json.dumps({k: (v['max_before'], v['max_after']) for k, v in r['assets'].items()}) + (' ERRORS' if r['errors'] else ''))
