"""Calibrate local locomotion clips and repair virtual-texture fallback overrides."""
import unreal as u,json,math,statistics,traceback,hashlib
from pathlib import Path
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'HoverPrototype/CharacterMaterials'
receipt=json.loads((out/'setup.json').read_text());r={'rates':[],'fallbacks':[]}
EA=u.EditorAssetLibrary;ML=u.MaterialEditingLibrary
try:
    copies=[u.load_asset(x['copy']) for x in receipt['copies']]
    materials=[x for x in copies if isinstance(x,u.Material)]
    fallbacks={}
    for mi in copies:
        if not isinstance(mi,u.MaterialInstanceConstant):continue
        base=mi
        while isinstance(base,u.MaterialInstanceConstant):base=base.get_editor_property('parent')
        for name in ML.get_texture_parameter_names(mi):
            actual=ML.get_material_instance_texture_parameter_value(mi,name)
            expected=ML.get_material_default_texture_parameter_value(base,name)
            if isinstance(expected,u.Texture2D) and expected.get_editor_property('virtual_texture_streaming') and isinstance(actual,u.Texture2D) and not actual.get_editor_property('virtual_texture_streaming'):
                fallbacks[actual.get_path_name().split('.')[0]]=actual
    originals=[];targets=[]
    for path,original in fallbacks.items():
        dest='/Game/HoverPrototype/Appearance/Fallbacks/'+original.get_name()
        target=u.load_asset(dest) if EA.does_asset_exist(dest) else EA.duplicate_asset(path,dest)
        originals.append(original);targets.append(target);r['fallbacks'].append({'source':path,'copy':dest})
    if targets:
        for a in copies:
            assert u.HoverAuthoring.remap_appearance_asset(a,originals,targets)>=0
            EA.save_loaded_asset(a,False)
        assert u.HoverAuthoring.convert_appearance_textures(targets,materials)
        for a in copies+targets:EA.save_loaded_asset(a,False)
    for path,sha in receipt['original_hashes'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
    d=u.load_asset('/Game/HoverPrototype/DA_HoverPilot');bs=d.get_editor_property('locomotion')
    mesh=d.get_editor_property('body_parts')[0].get_editor_property('mesh')
    options=u.AnimPoseEvaluationOptions();options.optional_skeletal_mesh=mesh;options.should_retarget=True
    samples=list(bs.get_editor_property('sample_data'));cache={}
    for sample in samples:
        sequence=sample.get_editor_property('animation');value=sample.get_editor_property('sample_value')
        if value.y<1:continue
        name=sequence.get_path_name()
        if name not in cache:
            length=sequence.get_play_length();n=max(30,round(length*60));dt=length/n;points={b:[] for b in ['foot_l','foot_r']}
            for i in range(n+1):
                pose=u.AnimPoseExtensions.get_anim_pose_at_time(sequence,min(i*dt,length-.0001),options)
                root=pose.get_bone_pose('root',u.AnimPoseSpaces.WORLD).translation
                for b in points:points[b].append(pose.get_bone_pose(b,u.AnimPoseSpaces.WORLD).translation-root)
            speeds=[];angle=math.radians(value.x)
            for rows in points.values():
                low=min(v.z for v in rows)
                for a,b in zip(rows,rows[1:]):
                    if max(a.z,b.z)>low+2 or abs(b.z-a.z)/dt>30:continue
                    speed=-((b.y-a.y)*math.cos(angle)-(b.x-a.x)*math.sin(angle))/dt
                    if speed>30:speeds.append(speed)
            assert len(speeds)>=3,(name,len(speeds))
            cache[name]=statistics.median(speeds)
        nominal=cache[name];rate=max(.65,min(1.65,value.y/nominal))
        sample.set_editor_property('rate_scale',rate)
        r['rates'].append({'clip':name,'speed':value.y,'direction':value.x,'measured_stride_cm_s':nominal,'rate':rate})
    bs.set_editor_property('sample_data',samples);EA.save_loaded_asset(bs,False)
    for key in ['turn_left','turn_right']:
        sequence=d.get_editor_property(key)
        sequence.set_editor_property('root_motion_root_lock',u.RootMotionRootLock.REF_POSE);EA.save_loaded_asset(sequence,False)
    r['ok']=True
except Exception:r['error']=traceback.format_exc()
(out/'refinement.json').write_text(json.dumps(r,indent=2));print('CHARACTER_REFINEMENT',r.get('ok'),r.get('error',''),flush=True)
