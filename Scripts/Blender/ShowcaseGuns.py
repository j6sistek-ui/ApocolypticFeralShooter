"""ShowcaseGuns.py - phone-friendly showcase videos + stills of the four rigged AFS guns.

Blender 5.2 headless, re-runnable, never saves over the rigged .blend files (the gun file is
opened, dressed in memory, rendered, and discarded; a debug copy goes to the scratch dir only).

  blender.exe -b --python ShowcaseGuns.py -- --gun M4A1            # video + hero + reload still
  blender.exe -b --python ShowcaseGuns.py -- --gun EM_21 --stage video|stills|all
  blender.exe -b --python ShowcaseGuns.py -- --gun EM_08 --frames 1,80,200   # test PNG frames only
  blender.exe -b --python ShowcaseGuns.py -- --stage stitch        # Guns_showcase_all.mp4
  blender.exe -b --python ShowcaseGuns.py -- --stage qc            # extract QC frames from MP4s

Guns: M4A1, EM_11, EM_21, EM_08.
Timeline (30 fps): 2 s turntable (rest), 0.6 s camera move, Fire x3 at 1x with 0.4 s gaps,
Fire 0.3x slow-mo replay, Reload 1x, Chamber 1x, 1 s rest. The clips are 60 fps actions played
through NLA strips (scale 0.5 = real time at 30 fps). Captions are camera-parented text objects.
HARD RULES (this machine): never read_factory_settings / --factory-startup (wipes extension
wheels); clear save handlers before any save (the comfyui add-on crashes headless saves).
"""
import bpy, sys, os, re, json, math, time
from mathutils import Vector, Matrix

SA = r"M:\UnrealProjects\AFS\SourceAssets"
OUT = r"D:\AFS_Comparisons\Showcase_20261029"
SCRATCH = (r"C:\Users\j6sis\AppData\Local\Temp\claude\M--AFS-Relocation-Backup-20261025-Saved-From-C"
           r"\c549ba76-f9d4-4652-b871-26d23d5e3882\scratchpad\showcase")
FPS = 30
CLIP_FPS = 60

GUNS = {
    "M4A1": dict(
        label="M4A1", blend=SA + r"\M4A1_Modular\Rigged\M4A1_rig.blend", prefix="A_M4A1_",
        tex_dir=SA + r"\M4A1_Modular\Textures_unpacked\Textures", kind="box",
        rig_json=SA + r"\M4A1_Modular\Rigged\m4a1_rig.json",
        focus_bones=["magazine", "bolt_carrier", "charging_handle", "trigger"], reload_bone="magazine",
        chamber_note=""),
    "EM_11": dict(
        label="EM_11 Carbine", blend=SA + r"\EM_Apocalyptic_Guns\Rigged\EM_11\EM11_rig.blend", prefix="A_EM11_",
        tex_dir=SA + r"\EM_Apocalyptic_Guns\Textures_2K\EM_11", kind="box",
        focus_bones=["magazine", "bolt_carrier", "trigger"], reload_bone="magazine", chamber_note=""),
    "EM_21": dict(
        label="EM_21 SMG", blend=SA + r"\EM_Apocalyptic_Guns\Rigged\EM_21\EM_21_rig.blend", prefix="A_EM21_",
        tex_dir=SA + r"\EM_Apocalyptic_Guns\Textures_2K\EM_21", kind="box",
        focus_bones=["magazine", "charging_handle", "trigger"], reload_bone="magazine", chamber_note=""),
    "EM_08": dict(
        label="EM_08 Revolver", blend=SA + r"\EM_Apocalyptic_Guns\Rigged\EM_08\SK_EM08_rig.blend", prefix="A_EM08_",
        tex_dir=SA + r"\EM_Apocalyptic_Guns\Textures_2K\EM_08", kind="revolver",
        focus_bones=["cylinder", "hammer", "trigger"], reload_bone="cylinder",
        chamber_note="cock + decock"),
}
ORDER = ["M4A1", "EM_11", "EM_21", "EM_08"]

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print("[SHOWCASE]", s, flush=True)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = dict(gun=None, stage="all", frames=None)
    i = 0
    while i < len(a):
        if a[i] == "--gun":
            out["gun"] = a[i + 1]; i += 2
        elif a[i] == "--stage":
            out["stage"] = a[i + 1]; i += 2
        elif a[i] == "--frames":
            out["frames"] = [int(x) for x in a[i + 1].split(",")]; i += 2
        else:
            i += 1
    return out


def clear_save_handlers():
    for h in (bpy.app.handlers.save_pre, bpy.app.handlers.save_post):
        h.clear()


# ------------------------------------------------------------------ materials
def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    return m, nt, out


def img(path, noncolor):
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        im.colorspace_settings.name = "Non-Color"
    return im


def pbr_material(name, maps):
    """maps: dict BaseColor/Normal/Roughness/Metallic -> path (any may be missing)."""
    m, nt, out = new_mat(name)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    y = 300
    for key, sock, nc in (("BaseColor", "Base Color", False), ("Metallic", "Metallic", True),
                          ("Roughness", "Roughness", True), ("Normal", None, True)):
        p = maps.get(key)
        if not p:
            continue
        t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-400, y); y -= 280
        t.image = img(p, nc)
        if key == "Normal":
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (0, -400)
            nt.links.new(t.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        else:
            nt.links.new(t.outputs["Color"], bsdf.inputs[sock])
    return m


def gunmetal(name):
    m, nt, out = new_mat(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.035, 0.037, 0.04, 1)
    b.inputs["Metallic"].default_value = 0.85
    b.inputs["Roughness"].default_value = 0.42
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return m


def glass_mat():
    m, nt, out = new_mat("SC_Glass")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.02, 0.03, 0.035, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.04
    b.inputs["Alpha"].default_value = 0.45
    for k in ("Coat Weight",):
        if k in b.inputs:
            b.inputs[k].default_value = 0.0
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        pass
    return m


def reddot_mat():
    m, nt, out = new_mat("SC_RedDot")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1.0, 0.02, 0.01, 1)
    e.inputs["Strength"].default_value = 12.0
    nt.links.new(e.outputs["Emission"], out.inputs["Surface"])
    return m


def tokens(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    t = [x for x in re.split(r"[^a-z0-9]+", s.lower()) if x]
    stop = {"m4a1", "ar", "15", "for", "the", "and", "basecolor", "normal", "roughness", "metallic", "tga", "png",
            "grp", "m4", "a2", "style", "mm"}
    return set(x for x in t if x not in stop)


def texture_sets(folder):
    sets = {}
    for f in os.listdir(folder):
        mm = re.match(r"(.+)_(BaseColor|Normal|Roughness|Metallic)\.(tga|png)$", f, re.I)
        if mm:
            sets.setdefault(mm.group(1), {})[mm.group(2)] = os.path.join(folder, f)
    return sets


def m4a1_materials(mesh_objs, cfg):
    sets = texture_sets(cfg["tex_dir"])
    rig = json.load(open(cfg["rig_json"]))
    vendor = {}
    for part, slot in rig.get("part_to_slot", {}).items():
        vendor.setdefault(slot, []).append(part)
    slots = []
    for o in mesh_objs:
        for s in o.material_slots:
            if s.material and s.material.name not in slots:
                slots.append(s.material.name)
    special = {"Glass": glass_mat, "RedDot": reddot_mat}
    cands = []
    for sl in slots:
        if sl in special:
            continue
        corpus = tokens(sl)
        for p in vendor.get(sl, []):
            corpus |= tokens(p)
        for sn in sets:
            st = tokens(sn)
            sc = len(corpus & st)
            if sc:
                cands.append((sc, sl, sn))
    cands.sort(key=lambda c: -c[0])
    assign, used = {}, set()
    for sc, sl, sn in cands:
        if sl in assign or sn in used:
            continue
        assign[sl] = (sn, sc); used.add(sn)
    newmats, unmatched = {}, []
    for sl in slots:
        if sl in special:
            newmats[sl] = special[sl]()
            log("slot", sl, "-> procedural", sl)
        elif sl in assign:
            sn, sc = assign[sl]
            newmats[sl] = pbr_material("SC_" + sl, sets[sn])
            log("slot", sl, "-> texture set '%s' (score %d, maps %s)" % (sn, sc, sorted(sets[sn])))
        else:
            newmats[sl] = gunmetal("SC_" + sl + "_gunmetal")
            unmatched.append(sl)
            log("slot", sl, "-> UNMATCHED, dark gunmetal")
    unused = [s for s in sets if s not in used]
    log("M4A1 unmatched slots:", unmatched, "unused texture sets:", unused)
    for o in mesh_objs:
        for s in o.material_slots:
            if s.material and s.material.name in newmats:
                s.material = newmats[s.material.name]
    return unmatched


def em_materials(mesh_objs, cfg, gun):
    sets = texture_sets(cfg["tex_dir"])
    assert len(sets) == 1, sets
    sn, maps = next(iter(sets.items()))
    m = pbr_material("SC_" + gun, maps)
    log(gun, "material from", sn, sorted(maps))
    for o in mesh_objs:
        for s in o.material_slots:
            s.material = m
    return []


# ------------------------------------------------------------------ geometry helpers
def world_verts(objs, deps):
    import numpy as np
    pts = []
    for o in objs:
        oe = o.evaluated_get(deps)
        me = oe.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(n, 3)
        M = np.array(o.matrix_world)
        co = co @ M[:3, :3].T + M[:3, 3]
        pts.append(co)
        oe.to_mesh_clear()
    return np.concatenate(pts)


def bounds(pts):
    return Vector(pts.min(axis=0)), Vector(pts.max(axis=0))


def corners(lo, hi):
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


def cam_dir(az_deg, el_deg):
    a, e = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


def fit_distance(points, target, d, lens=50.0, sensor=36.0, aspect=16 / 9, margin=1.12):
    th = (sensor / 2) / lens
    tv = th / aspect
    f = -d
    r = f.cross(Vector((0, 0, 1))).normalized()
    u = r.cross(f).normalized()
    D = 0.05
    for p in points:
        q = p - target
        x, y, z = q.dot(r), q.dot(u), q.dot(d)
        D = max(D, z + abs(x) * margin / th, z + abs(y) * margin / tv)
    return D


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ scene dressing
def bg_gradient_nodes(nt, loc=(-600, 0)):
    """window-space vertical gradient (dark grey studio) -> returns colour output socket"""
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = loc
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (loc[0] + 200, loc[1])
    nt.links.new(tc.outputs["Window"], sep.inputs["Vector"])
    # radial-ish: mix vertical ramp with a horizontal falloff
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (loc[0] + 400, loc[1])
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.006, 0.0065, 0.007, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.05, 0.052, 0.056, 1)
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def make_world():
    w = bpy.data.worlds.new("SC_World")
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (800, 0)
    grad = bg_gradient_nodes(nt, (-800, 300))
    bg_cam = nt.nodes.new("ShaderNodeBackground"); bg_cam.location = (200, 300)
    nt.links.new(grad, bg_cam.inputs["Color"])
    # lighting env: soft studio dome, brighter overhead (gives metal something to reflect)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-800, -200)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-600, -200)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-400, -200)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.022, 1)
    ramp.color_ramp.elements[1].position = 0.95
    ramp.color_ramp.elements[1].color = (0.55, 0.56, 0.6, 1)
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-600, -400)
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    bg_env = nt.nodes.new("ShaderNodeBackground"); bg_env.location = (200, -200)
    bg_env.inputs["Strength"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], bg_env.inputs["Color"])
    lp = nt.nodes.new("ShaderNodeLightPath"); lp.location = (200, 600)
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.location = (500, 0)
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_env.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    bpy.context.scene.world = w


def make_floor(z, size, gain):
    """shadow-catcher look: floor colour = background gradient * received-light ratio (clamped)."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    fl = bpy.context.active_object
    fl.name = "SC_Floor"
    m, nt, out = new_mat("SC_FloorShadow")
    grad = bg_gradient_nodes(nt, (-900, 300))
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse"); diff.location = (-900, -200)
    diff.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB"); s2r.location = (-700, -200)
    nt.links.new(diff.outputs["BSDF"], s2r.inputs["Shader"])
    bw = nt.nodes.new("ShaderNodeRGBToBW"); bw.location = (-500, -200)
    nt.links.new(s2r.outputs["Color"], bw.inputs["Color"])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.use_clamp = True
    mul.location = (-300, -200); mul.inputs[1].default_value = gain
    nt.links.new(bw.outputs["Val"], mul.inputs[0])
    shade = nt.nodes.new("ShaderNodeMapRange"); shade.location = (-100, -200)
    shade.inputs["To Min"].default_value = 0.35
    shade.inputs["To Max"].default_value = 1.0
    nt.links.new(mul.outputs["Value"], shade.inputs["Value"])
    mixc = nt.nodes.new("ShaderNodeMixRGB"); mixc.blend_type = "MULTIPLY"; mixc.location = (100, 0)
    mixc.inputs["Fac"].default_value = 1.0
    nt.links.new(grad, mixc.inputs["Color1"])
    nt.links.new(shade.outputs["Result"], mixc.inputs["Color2"])
    em = nt.nodes.new("ShaderNodeEmission"); em.location = (300, 0)
    nt.links.new(mixc.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    fl.data.materials.append(m)
    try:
        fl.visible_shadow = False
    except Exception:
        pass
    return fl


def make_lights(target, scale, az_cam, side_sign):
    # key: soft sun from camera side, upper front
    kd = cam_dir(az_cam + 35 * side_sign, 52)
    sun = bpy.data.lights.new("SC_Key", "SUN"); sun.energy = 3.2; sun.angle = math.radians(9)
    try:
        sun.use_shadow = True
    except Exception:
        pass
    ko = bpy.data.objects.new("SC_Key", sun); bpy.context.scene.collection.objects.link(ko)
    ko.rotation_mode = "QUATERNION"; ko.rotation_quaternion = (-kd).to_track_quat("-Z", "Y")
    # rim: area light behind/above the gun, opposite the camera
    rd = cam_dir(az_cam + 180 - 25 * side_sign, 35)
    ar = bpy.data.lights.new("SC_Rim", "AREA"); ar.shape = "DISK"; ar.size = 1.2 * max(scale, 0.4)
    dist = 2.2 * max(scale, 0.4)
    ar.energy = 260.0 * (dist / 2.2) ** 2
    ro = bpy.data.objects.new("SC_Rim", ar); bpy.context.scene.collection.objects.link(ro)
    ro.location = target + rd * dist
    ro.rotation_mode = "QUATERNION"; ro.rotation_quaternion = (-rd).to_track_quat("-Z", "Y")
    # small fill from the camera side, low
    fd = cam_dir(az_cam - 40 * side_sign, 5)
    fa = bpy.data.lights.new("SC_Fill", "AREA"); fa.size = 1.0 * max(scale, 0.4)
    fdist = 2.0 * max(scale, 0.4)
    fa.energy = 60.0 * (fdist / 2.0) ** 2
    try:
        fa.use_shadow = False
    except Exception:
        pass
    fo = bpy.data.objects.new("SC_Fill", fa); bpy.context.scene.collection.objects.link(fo)
    fo.location = target + fd * fdist
    fo.rotation_mode = "QUATERNION"; fo.rotation_quaternion = (-fd).to_track_quat("-Z", "Y")


def make_camera():
    cd = bpy.data.cameras.new("SC_Cam"); cd.lens = 50; cd.sensor_width = 36; cd.sensor_fit = "HORIZONTAL"
    cd.clip_start = 0.004; cd.clip_end = 100
    co = bpy.data.objects.new("SC_Cam", cd); bpy.context.scene.collection.objects.link(co)
    co.rotation_mode = "QUATERNION"
    bpy.context.scene.camera = co
    return co


def make_caption(cam, text, name):
    zt = 0.1
    w = zt * 18 / 50
    h = w * 9 / 16
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.size = 2 * h * 0.062
    cu.align_x = "LEFT"; cu.align_y = "TOP"
    try:
        cu.font = bpy.data.fonts.load(r"C:\Windows\Fonts\segoeuib.ttf", check_existing=True)
    except Exception:
        pass
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = cam
    ob.location = (-w + 0.035 * 2 * w, h - 0.05 * 2 * h, -zt)
    m, nt, out = new_mat(name + "_mat")
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (1, 1, 1, 1)
    e.inputs["Strength"].default_value = 3.0
    nt.links.new(e.outputs["Emission"], out.inputs["Surface"])
    cu.materials.append(m)
    try:
        ob.visible_shadow = False
    except Exception:
        pass
    # dark shadow copy for legibility
    cu2 = cu.copy(); cu2.materials.clear()
    m2, nt2, out2 = new_mat(name + "_shadow")
    e2 = nt2.nodes.new("ShaderNodeEmission"); e2.inputs["Color"].default_value = (0, 0, 0, 1)
    nt2.links.new(e2.outputs["Emission"], out2.inputs["Surface"])
    cu2.materials.append(m2)
    ob2 = bpy.data.objects.new(name + "_shadow", cu2)
    bpy.context.scene.collection.objects.link(ob2)
    ob2.parent = cam
    ob2.location = (ob.location.x + cu.size * 0.06, ob.location.y - cu.size * 0.06, -zt - 0.0005)
    try:
        ob2.visible_shadow = False
    except Exception:
        pass
    # translucent dark plate behind the text so it reads over the gun on a phone
    bpy.context.view_layer.update()
    tw, th = ob.dimensions.x, cu.size * 0.95
    pad = cu.size * 0.35
    x0, y0 = ob.location.x - pad, ob.location.y + pad * 0.6
    x1, y1 = ob.location.x + tw + pad, ob.location.y - th - pad * 0.6
    me = bpy.data.meshes.new(name + "_plate")
    me.from_pydata([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [], [(0, 3, 2, 1)])
    m3, nt3, out3 = new_mat(name + "_platemat")
    tr = nt3.nodes.new("ShaderNodeBsdfTransparent")
    e3 = nt3.nodes.new("ShaderNodeEmission"); e3.inputs["Color"].default_value = (0, 0, 0, 1)
    mx = nt3.nodes.new("ShaderNodeMixShader"); mx.inputs["Fac"].default_value = 0.72
    nt3.links.new(tr.outputs[0], mx.inputs[1]); nt3.links.new(e3.outputs[0], mx.inputs[2])
    nt3.links.new(mx.outputs[0], out3.inputs["Surface"])
    try:
        m3.surface_render_method = "BLENDED"
    except Exception:
        pass
    me.materials.append(m3)
    ob3 = bpy.data.objects.new(name + "_plate", me)
    bpy.context.scene.collection.objects.link(ob3)
    ob3.parent = cam
    ob3.location = (0, 0, -zt - 0.001)
    try:
        ob3.visible_shadow = False
    except Exception:
        pass
    return [ob, ob2, ob3]


def key_visibility(objs, f0, f1, total):
    for ob in objs:
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=0)
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=f0)
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=f1)


# ------------------------------------------------------------------ main per gun
def setup_render(sc, res=(1280, 720), samples=32):
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    ee = sc.eevee
    ee.taa_render_samples = samples
    for k, v in (("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8),
                 ("use_raytracing", True), ("use_fast_gi", True)):
        try:
            setattr(ee, k, v)
        except Exception as e:
            log("eevee setting", k, "failed", e)
    try:
        ee.ray_tracing_method = "SCREEN"
    except Exception:
        pass
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.render.film_transparent = False


def set_output_video(sc, path):
    sc.render.image_settings.media_type = "VIDEO"
    sc.render.image_settings.file_format = "FFMPEG"
    ff = sc.render.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = "HIGH"
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = 15
    ff.audio_codec = "NONE"
    sc.render.filepath = path


def set_output_png(sc, path):
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.filepath = path


def build(gun, cfg):
    pass  # handlers are only cleared around the debug save (main)
    bpy.ops.wm.open_mainfile(filepath=cfg["blend"], load_ui=False)
    pass
    sc = bpy.context.scene
    sc.render.fps = FPS; sc.render.fps_base = 1.0
    arm = [o for o in sc.objects if o.type == "ARMATURE"][0]
    meshes = [o for o in sc.objects if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
    for o in list(sc.objects):
        if o.type in ("CAMERA", "LIGHT") or (o.type == "MESH" and o not in meshes) or o.type == "FONT":
            bpy.data.objects.remove(o)
    log(gun, "armature", arm.name, "meshes", [m.name for m in meshes])
    unmatched = m4a1_materials(meshes, cfg) if gun == "M4A1" else em_materials(meshes, cfg, gun)

    # actions -> NLA timeline
    acts = {}
    for clip in ("Idle", "Fire", "DryFire", "Reload", "Chamber"):
        a = bpy.data.actions.get(cfg["prefix"] + clip)
        assert a, cfg["prefix"] + clip
        acts[clip] = a
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    clipsec = {k: (a.frame_range[1] - a.frame_range[0]) / CLIP_FPS for k, a in acts.items()}
    log(gun, "clip seconds", {k: round(v, 3) for k, v in clipsec.items()})
    track = ad.nla_tracks.new(); track.name = "Showcase"
    segs = []  # (caption, f0, f1)

    def place(clip, t_start, speed=1.0):
        a = acts[clip]
        f0 = int(round(1 + t_start * FPS))
        st = track.strips.new("%s_%d" % (clip, f0), f0, a)
        try:
            if a.slots and st.action_slot is None:
                st.action_slot = a.slots[0]
        except Exception:
            pass
        st.scale = (FPS / CLIP_FPS) / speed
        st.extrapolation = "HOLD" if len(track.strips) == 1 else "HOLD_FORWARD"
        st.blend_type = "REPLACE"
        return f0, st.frame_end

    lab = cfg["label"]
    t = 2.6
    fire_f0 = None
    fires = []
    for i in range(3):
        f0, f1 = place("Fire", t)
        fires.append((f0, f1))
        t += clipsec["Fire"] + 0.4
    segs.append(("%s - Fire x3 (%.2f s)" % (lab, clipsec["Fire"]), fires[0][0], int(round(1 + (t - 0.3) * FPS))))
    push0 = t - 0.3                 # camera pushes in to the firing parts during the gap
    t += 0.35
    push1 = t
    f0, f1 = place("Fire", t, speed=0.3)
    slowmo = (f0, f1)
    sm_end = t + clipsec["Fire"] / 0.3 + 0.45
    pull1 = sm_end + 0.5            # camera pulls back to the action framing
    segs.append(("%s - Fire, 0.3x slow motion" % lab, int(round(1 + (push0) * FPS)), int(round(1 + (pull1 + 0.05) * FPS)) - 3))  # runs until the Reload caption
    t = pull1 + 0.05
    cam_keys = dict(push0=1 + push0 * FPS, push1=1 + push1 * FPS, pull0=1 + sm_end * FPS, pull1=1 + pull1 * FPS)
    rf0, rf1 = place("Reload", t)
    t_reload = t
    t += clipsec["Reload"] + 0.5
    segs.append(("%s - Reload (%.1f s)" % (lab, clipsec["Reload"]), rf0 - 3, int(round(1 + (t - 0.1) * FPS))))
    cf0, cf1 = place("Chamber", t)
    cap = "%s - Chamber (%.1f s)" % (lab, clipsec["Chamber"])
    if cfg["chamber_note"]:
        cap = "%s - Chamber: %s (%.1f s)" % (lab, cfg["chamber_note"], clipsec["Chamber"])
    t += clipsec["Chamber"]
    segs.append((cap, cf0 - 3, int(round(1 + (t + 0.3) * FPS))))
    t_end = t + 1.2
    last = int(round(1 + t_end * FPS))
    segs.insert(0, ("%s - Rest pose" % lab, 0, int(round(1 + 2.55 * FPS))))
    segs.append(("%s - Rest" % lab, int(round(1 + (t + 0.3) * FPS)), last + 1))
    sc.frame_start, sc.frame_end = 1, last
    log(gun, "timeline frames", last, "=", round(last / FPS, 2), "s; strips",
        [(s.name, round(s.frame_start, 2), round(s.frame_end, 2)) for s in track.strips])

    deps = bpy.context.evaluated_depsgraph_get()
    sc.frame_set(1)
    deps = bpy.context.evaluated_depsgraph_get()
    rest_pts = world_verts(meshes, deps)
    rlo, rhi = bounds(rest_pts)
    length = (rhi - rlo).x
    log(gun, "rest bounds", tuple(round(v, 3) for v in rlo), tuple(round(v, 3) for v in rhi), "length", round(length, 3))

    # lowest point over the whole timeline (sampled) -> floor; also reload-still frame
    zmin = rlo.z
    rb = cfg["reload_bone"]
    pb = arm.pose.bones[rb]
    rest_head = arm.matrix_world @ pb.head
    disp = []
    for f in range(1, last + 1, 2):
        sc.frame_set(f)
        if rf0 <= f <= rf1 + 1:
            disp.append((f, ((arm.matrix_world @ pb.head) - rest_head).length))
        if f % 6 == 1 or (rf0 <= f <= rf1):
            deps = bpy.context.evaluated_depsgraph_get()
            p = world_verts(meshes, deps)
            zmin = min(zmin, float(p[:, 2].min()))
    for f in range(rf0, int(rf1) + 2):
        sc.frame_set(f)
        disp = [d for d in disp if d[0] != f] + [(f, ((arm.matrix_world @ pb.head) - rest_head).length)]
    disp.sort()
    dmax = max(d for _, d in disp)
    if cfg["kind"] == "revolver":
        plate = [f for f, d in disp if d >= 0.95 * dmax]
        reload_still = plate[len(plate) // 2]
    else:
        thr = min(0.5 * dmax, 0.10)
        reload_still = [f for f, d in disp if d >= thr][0]
    log(gun, "reload bone", rb, "max disp %.3f m" % dmax, "reload still frame", reload_still,
        "(clip frame %.1f)" % ((reload_still - rf0) * CLIP_FPS / FPS))
    floor_z = min(zmin, rlo.z) - 0.01
    log(gun, "floor z", round(floor_z, 3), "(lowest point over timeline %.3f)" % zmin)

    # framing
    side = 1 if cfg["kind"] == "revolver" else -1     # revolver from gun's left (+Y), others from right (-Y)
    az = 70.0 if side > 0 else -70.0
    el = 14.0
    tgt_full = (rlo + rhi) / 2
    scale = max(length, 0.25)
    sc.frame_set(1)
    if length > 0.5:
        cx = sum((arm.matrix_world @ arm.pose.bones[b].head).x for b in cfg["focus_bones"] if b in arm.pose.bones)
        cx /= len([b for b in cfg["focus_bones"] if b in arm.pose.bones])
        sel = rest_pts[(rest_pts[:, 0] > cx - 0.28) & (rest_pts[:, 0] < cx + 0.28)]
        alo, ahi = bounds(sel)
    else:
        alo, ahi = rlo, rhi
    tgt_act = (alo + ahi) / 2
    tgt_act.z -= 0.04 * (ahi - alo).z     # a little extra room below for the mag drop
    d_act = cam_dir(az, el)
    D_act = fit_distance(corners(alo, ahi), tgt_act, d_act, margin=1.18)
    turn_az = [az - 75 + 75 * smooth(i / 60.0) for i in range(61)]
    D_turn = max(fit_distance(corners(rlo, rhi), tgt_full, cam_dir(a, el + 4), margin=1.1) for a in turn_az[::5])
    log(gun, "D_turn %.3f D_act %.3f target_act" % (D_turn, D_act), tuple(round(v, 3) for v in tgt_act))

    # close-up for the slow-mo Fire: bones (other than root/body) that move during Fire
    sc.frame_set(1)
    rest_m = {b.name: (arm.matrix_world @ b.matrix).copy() for b in arm.pose.bones}
    moving = {}
    for f in range(slowmo[0], int(slowmo[1]) + 1):
        sc.frame_set(f)
        for b in arm.pose.bones:
            if b.name in ("root", "body"):
                continue
            M = arm.matrix_world @ b.matrix
            # own motion only: compare with where the bone would be if it just rode on its parent
            # (so the revolver's body recoil does not flag every socket)
            if b.parent:
                P = arm.matrix_world @ b.parent.matrix
                ride = P @ (rest_m[b.parent.name].inverted() @ rest_m[b.name])
            else:
                ride = rest_m[b.name]
            dt = (M.translation - ride.translation).length
            da = (M.to_quaternion().rotation_difference(ride.to_quaternion())).angle
            if dt > 0.003 or da > math.radians(2):
                moving.setdefault(b.name, []).append(M.translation.copy())
    sc.frame_set(1)
    own = list(moving)
    pts_m = [rest_m[n].translation for n in own] + [p for n in own for p in moving[n]]
    cc = sum(pts_m, Vector()) / len(pts_m)
    spread = max((p - cc).length for p in pts_m)
    hw = max(0.07 if length < 0.5 else 0.10, spread + 0.05)
    selc = rest_pts[(abs(rest_pts[:, 0] - cc.x) < hw) & (abs(rest_pts[:, 2] - cc.z) < hw * 0.6)]
    clo, chi = bounds(selc)
    tgt_cu = (clo + chi) / 2
    D_cu = fit_distance(corners(clo, chi), tgt_cu, d_act, margin=1.35)
    log(gun, "fire moving bones", sorted(moving), "close-up on", own, "centre", tuple(round(v, 3) for v in cc),
        "half-width %.3f D_cu %.3f" % (hw, D_cu))

    make_world()
    make_floor(floor_z, max(30.0, 40 * scale), gain=1.0)
    make_lights(tgt_full, scale, az, side)
    cam = make_camera()

    def cam_at(f, target, D, a, e):
        d = cam_dir(a, e)
        cam.location = target + d * D
        cam.rotation_quaternion = (-d).to_track_quat("-Z", "Y")
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)

    f_move0, f_move1 = 61, 61 + 18
    for f in range(1, last + 1):
        if f <= f_move0:
            cam_at(f, tgt_full, D_turn, az - 75 + 75 * smooth((f - 1) / 60.0), el + 4)
        elif f <= f_move1:
            s = smooth((f - f_move0) / (f_move1 - f_move0))
            cam_at(f, tgt_full.lerp(tgt_act, s), D_turn + (D_act - D_turn) * s, az, el + 4 * (1 - s))
        else:
            # very slow drift so the frame never feels frozen, plus the slow-mo close-up
            s = (f - f_move1) / max(1, last - f_move1)
            tg, D, a_ = tgt_act, D_act * (1 - 0.04 * s), az + 3 * s * side * -1
            k = cam_keys
            if k["push0"] <= f <= k["pull1"]:
                if f < k["push1"]:
                    c = smooth((f - k["push0"]) / (k["push1"] - k["push0"]))
                elif f <= k["pull0"]:
                    c = 1.0
                else:
                    c = 1 - smooth((f - k["pull0"]) / (k["pull1"] - k["pull0"]))
                tg = tgt_act.lerp(tgt_cu, c)
                D = D + (D_cu - D) * c
            cam_at(f, tg, D, a_, el)

    for i, (txt, f0, f1) in enumerate(segs):
        objs = make_caption(cam, txt, "SC_Cap%02d" % i)
        key_visibility(objs, max(0, f0), f1, last)
    log(gun, "captions", [(s[0], s[1], s[2]) for s in segs])

    info = dict(gun=gun, frames=last, seconds=last / FPS, reload_still=reload_still, fires=fires,
                reload=(rf0, rf1), chamber=(cf0, cf1), unmatched=unmatched, floor_z=floor_z,
                tgt_full=tuple(tgt_full), D_full=fit_distance(corners(rlo, rhi), tgt_full, cam_dir(az, el), margin=1.08),
                az=az, el=el, side=side, segs=segs, slowmo=slowmo)
    return sc, arm, meshes, cam, info


def render_video(sc, gun, info):
    setup_render(sc, (1280, 720), 32)
    path = os.path.join(OUT, gun + "_showcase.mp4")
    if os.path.exists(path):
        os.remove(path)
    set_output_video(sc, path)
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    log(gun, "video", path, "%.1f MB" % (os.path.getsize(path) / 1e6), "render %.0f s" % (time.time() - t0))


def render_frames(sc, gun, frames):
    setup_render(sc, (1280, 720), 32)
    for f in frames:
        sc.frame_set(f)
        set_output_png(sc, os.path.join(SCRATCH, "test_%s_f%04d.png" % (gun, f)))
        bpy.ops.render.render(write_still=True)
        log("test frame", sc.render.filepath)


def render_stills(sc, gun, info, arm, meshes, cam):
    setup_render(sc, (1920, 1080), 96)
    for o in sc.objects:
        if o.name.startswith("SC_Cap"):
            o.animation_data_clear(); o.hide_render = True
    cam.animation_data_clear()
    sc.frame_set(1)
    # hero: rest pose, full gun, slightly lower and wider angle than the video
    deps = bpy.context.evaluated_depsgraph_get()
    pts = world_verts(meshes, deps)
    lo, hi = bounds(pts)
    tgt = (lo + hi) / 2
    a, e = info["az"] - 12 * info["side"] * -1, 10.0
    d = cam_dir(a, e)
    D = fit_distance(corners(lo, hi), tgt, d, margin=1.08)
    cam.location = tgt + d * D; cam.rotation_quaternion = (-d).to_track_quat("-Z", "Y")
    set_output_png(sc, os.path.join(OUT, gun + "_hero.png"))
    bpy.ops.render.render(write_still=True)
    log(gun, "hero", sc.render.filepath)
    # mid-reload
    f = info["reload_still"]
    sc.frame_set(f)
    deps = bpy.context.evaluated_depsgraph_get()
    pts = world_verts(meshes, deps)
    lo2, hi2 = bounds(pts)
    tgt = (lo2 + hi2) / 2
    d = cam_dir(info["az"], 14.0)
    D = fit_distance(corners(lo2, hi2), tgt, d, margin=1.08)
    cam.location = tgt + d * D; cam.rotation_quaternion = (-d).to_track_quat("-Z", "Y")
    set_output_png(sc, os.path.join(OUT, gun + "_reload.png"))
    bpy.ops.render.render(write_still=True)
    log(gun, "reload still frame", f, sc.render.filepath)


def stitch():
    bpy.ops.wm.read_homefile(use_empty=True)
    pass
    sc = bpy.context.scene
    sc.render.fps = FPS; sc.render.fps_base = 1.0
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1280, 720, 100
    se = sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    f = 1
    gap = int(0.5 * FPS)
    for i, g in enumerate(ORDER):
        p = os.path.join(OUT, g + "_showcase.mp4")
        s = strips.new_movie(name=g, filepath=p, channel=1, frame_start=f)
        log("stitch", g, "start", f, "len", s.frame_final_duration)
        f = s.frame_final_end + (gap if i < len(ORDER) - 1 else 0)
    sc.frame_start, sc.frame_end = 1, f - 1
    sc.render.use_sequencer = True
    try:
        sc.view_settings.view_transform = "Standard"
    except Exception:
        pass
    path = os.path.join(OUT, "Guns_showcase_all.mp4")
    if os.path.exists(path):
        os.remove(path)
    set_output_video(sc, path)
    bpy.ops.render.render(animation=True)
    log("stitched", path, "%.1f MB" % (os.path.getsize(path) / 1e6), "frames", sc.frame_end)


def qc():
    import imageio_ffmpeg, subprocess
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    qd = os.path.join(SCRATCH, "qc")
    os.makedirs(qd, exist_ok=True)
    for g in ORDER + ["Guns_showcase_all"]:
        p = os.path.join(OUT, (g + "_showcase.mp4") if g in GUNS else g + ".mp4")
        if not os.path.exists(p):
            continue
        r = subprocess.run([exe, "-hide_banner", "-i", p], capture_output=True, text=True)
        dur = re.search(r"Duration: ([0-9:.]+)", r.stderr)
        log("QC", os.path.basename(p), "duration", dur.group(1) if dur else "?",
            "%.2f MB" % (os.path.getsize(p) / 1e6), re.search(r"Video: [^\n]+", r.stderr).group(0)[:90])
        info_p = os.path.join(SCRATCH, g + "_info.json")
        times = []
        if os.path.exists(info_p):
            inf = json.load(open(info_p))
            fr = [30, inf["fires"][0][0] + 1, inf["slowmo"][0] + 5, inf["reload_still"], inf["chamber"][0] + 8]
            times = [(x - 1) / FPS for x in fr]
        else:
            times = [5.0, 17.0, 29.0, 41.0]
        for i, tt in enumerate(times):
            o = os.path.join(qd, "%s_qc%d_%.2fs.png" % (g, i, tt))
            subprocess.run([exe, "-y", "-loglevel", "error", "-ss", "%.3f" % tt, "-i", p, "-frames:v", "1", o])
            log("QC frame", o)


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SCRATCH, exist_ok=True)
    if a["stage"] == "stitch":
        stitch(); return
    if a["stage"] == "qc":
        qc(); return
    guns = [a["gun"]] if a["gun"] else ORDER
    for g in guns:
        cfg = GUNS[g]
        sc, arm, meshes, cam, info = build(g, cfg)
        json.dump(info, open(os.path.join(SCRATCH, g + "_info.json"), "w"), indent=1, default=str)
        if a["frames"]:
            render_frames(sc, g, a["frames"]); continue
        saved = (list(bpy.app.handlers.save_pre), list(bpy.app.handlers.save_post))
        clear_save_handlers()
        try:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCRATCH, g + "_showcase_debug.blend"), copy=True)
        except Exception as e:
            log("debug save failed", e)
        bpy.app.handlers.save_pre.extend(saved[0]); bpy.app.handlers.save_post.extend(saved[1])
        if a["stage"] in ("all", "video"):
            render_video(sc, g, info)
        if a["stage"] in ("all", "stills"):
            render_stills(sc, g, info, arm, meshes, cam)
        with open(os.path.join(SCRATCH, g + "_log.txt"), "w") as fh:
            fh.write("\n".join(LOG))


main()
