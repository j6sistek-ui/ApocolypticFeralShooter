"""Create an isolated Vexa material graph and enable its complete UDIM coverage.

Run once after native build, with r.VirtualTextures enabled. Original assets are
hashed before/after; only /Game/HoverPrototype/Appearance copies are converted.
"""
import hashlib,json,traceback
from pathlib import Path
import unreal as u

root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'HoverPrototype/CharacterMaterials'
root.mkdir(parents=True,exist_ok=True)
receipt=root/'setup.json';r={'copies':[],'original_hashes':{},'remapped':[]}
EA=u.EditorAssetLibrary;ML=u.MaterialEditingLibrary
prefix='/Game/HoverPrototype/Appearance/'
content=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
def save(a):EA.save_loaded_asset(a,False)
try:
    d=u.load_asset('/Game/HoverPrototype/DA_HoverPilot');parts=list(d.get_editor_property('body_parts'))
    roots=sorted(set(m.get_path_name().split('.')[0] for part in parts for m in part.get_editor_property('materials')))
    assert not any(p.startswith(prefix) for p in roots),'Already configured; inspect the existing receipt instead of duplicating again.'
    r['original_roots']=roots
    ar=u.AssetRegistryHelpers.get_asset_registry();ar.search_all_assets(True)
    options=u.AssetRegistryDependencyOptions(include_soft_package_references=False,include_hard_package_references=True,include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
    queue=list(roots);seen=set()
    while queue:
        p=queue.pop()
        if p in seen or not p.startswith('/Game/'):continue
        seen.add(p);queue.extend(str(x) for x in ar.get_dependencies(p,options))
    originals=[];copies=[];textures=[];materials=[];mapped={}
    for p in sorted(seen):
        a=u.load_asset(p)
        clone=isinstance(a,(u.MaterialInterface,u.MaterialFunctionInterface))
        if isinstance(a,u.Texture2D):clone='block=1' in u.HoverAuthoring.inspect_texture(a)
        if not clone:continue
        file=content/(p[len('/Game/'):]+'.uasset')
        r['original_hashes'][str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
        dest=prefix+p[len('/Game/'):]
        b=u.load_asset(dest) if EA.does_asset_exist(dest) else EA.duplicate_asset(p,dest)
        assert b,dest
        originals.append(a);copies.append(b);mapped[p]=b
        if isinstance(b,u.Texture2D):textures.append(b)
        if isinstance(b,u.Material):materials.append(b)
        r['copies'].append({'source':p,'copy':dest,'type':a.get_class().get_name()})
    assert textures and materials,'No UDIM texture/material graph found'
    for a in copies:
        count=u.HoverAuthoring.remap_appearance_asset(a,originals,copies)
        assert count>=0,a.get_path_name()
        r['remapped'].append({'asset':a.get_path_name(),'references':count});save(a)
    assert u.HoverAuthoring.convert_appearance_textures(textures,materials)
    r['virtual_textures']=[]
    for t in textures:
        assert t.get_editor_property('virtual_texture_streaming'),t.get_path_name()
        r['virtual_textures'].append({'path':t.get_path_name(),'blocks':u.HoverAuthoring.inspect_texture(t)})
    for a in copies:save(a)
    for file,expected in r['original_hashes'].items():
        assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==expected,'Original changed: '+file
    for part in parts:
        part.set_editor_property('materials',[mapped[m.get_path_name().split('.')[0]] for m in part.get_editor_property('materials')])
    d.set_editor_property('body_parts',parts);save(d)
    r['originals_unchanged']=True;r['ok']=True
except Exception:r['error']=traceback.format_exc()
receipt.write_text(json.dumps(r,indent=2));print('CHARACTER_MATERIALS',r.get('ok'),r.get('error',''),flush=True)
