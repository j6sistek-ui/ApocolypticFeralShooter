"""CleanPowerUps.py - clean the 15 Tripo power-up models for game use (2026-10-31).

  blender -b --python M:/UnrealProjects/AFS/Scripts/Blender/CleanPowerUps.py [-- <out_render_dir>]

Headless and re-runnable: sources are only read, outputs are overwritten. Per model:
  1. import the GLB into an empty scene (read_homefile(use_empty=True), never factory settings);
  2. find connected components (vertices welded by position first, so glTF UV-seam splits do not count as pieces)
     and delete loose strays: a piece is removed only when it is small (< 5 % of the vertices) AND separated from the
     largest piece by a gap (> 1.5 % of the model's size). Attached detail (the eyeball's drip) is kept;
  3. joins every mesh into one, applies transforms, optionally re-orients (PCA up/front for the two models that Tripo
     left lying or tilted), puts the pivot at the bottom centre, scales the largest dimension to the game size;
  4. decimates to about 8k triangles only if over 12k (Collapse; none of the 15 needs it at the time of writing);
  5. keeps the one material and its textures, resizes the textures (1024, or 2048 for the Nuke and the shield), names
     everything PU_<NN>_<Name> and exports SourceAssets/PowerUps/Clean/PU_<NN>_<Name>.glb;
  6. re-imports the exported GLB, renders before/after (Workbench texture, 3/4 view, plus a front check) and writes
     clean_sheet.png and clean.json to the render folder.

Front convention: the readable face (labels, emblems, crosses) faces -Y in Blender, which is glTF/UE forward.
Every source except #3 and #11 already had its front on -Y (checked on the raw _front renders), so they only get the
pivot and scale fix.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

SRC = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/'
DST = SRC + 'Clean/'
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = args[0] if args else 'D:/AFS_Comparisons/PowerUps_20261031/Clean/'
REN = os.path.join(OUT, 'renders')
os.makedirs(DST, exist_ok=True)
os.makedirs(REN, exist_ok=True)

HAND, CRATE = 0.45, 0.60
# (number, source, clean name, size class, texture size, orientation)
# orientation None = keep the source axes (front already -Y); otherwise a dict for align():
#   up: 'pca0' (longest axis) with a hint vector for its sign; front: 'pca2' (thinnest axis) or a hint vector.
MODELS = [
    (1, 'Batch01/ammo_can', 'AmmoCan', HAND, 1024, None),
    (2, 'Batch01/fantasy_prop', 'CurseTower', HAND, 1024, None),
    (3, 'Batch01/fantasy_shield', 'StarShield', HAND, 2048,
     {'up': ('pca0', (0, 1, 1)), 'front': ('pca2', (0, -1, 1)),
      'why': 'Tripo left it lying face-up at a slant; stood upright, star face to -Y, prongs up'}),
    (4, 'Batch01/hourglass_with_clock', 'Hourglass', HAND, 1024, None),
    (5, 'Batch01/loot_crate', 'ArmorBox', CRATE, 1024, None),
    (6, 'Batch01/medkit', 'Medkit', HAND, 1024, None),
    (7, 'Batch01/monster_eyeball', 'ZombieEye', HAND, 1024, None),
    (9, 'Batch01/stone_skull_shield', 'BossTotem', HAND, 1024, None),
    (10, 'Batch01/tactical_vest', 'Vest', CRATE, 1024, None),
    (11, 'Batch02/energy_cell', 'EnergyCell', HAND, 1024,
     {'up': ('pca0', (0, 0, 1)), 'front': ('hint', (math.sin(math.radians(25)), -math.cos(math.radians(25)), 0)),
      'why': 'Tripo left the cell tilted; stood upright on its long axis, threaded cap up, bolt to -Y'}),
    (13, 'Batch02/futuristic_grenade_2', 'ToxicGas', HAND, 1024, None),
    (14, 'Batch02/medical_supply_crate', 'MedCrate', CRATE, 1024, None),
    (15, 'Batch02/rusted_flask', 'GasCan', HAND, 1024, None),
    (16, 'Batch03/futuristic_trap_device', 'SpiderPod', HAND, 1024, None),
    (17, 'Batch04/radiation_grenade', 'Nuke', HAND, 2048, None),
    (18, 'Batch05/ammo_canister', 'MaxAmmo', HAND, 1024, None),
]
FRONT_NOTE = {
    1: '"UNLIMITED AMMO" label already on -Y; kept',
    2: 'skull door and runes already on -Y; kept',
    4: 'pocket-watch face already on -Y; kept',
    5: 'lock emblem and hazard stripe already on -Y; kept',
    6: 'red cross already on -Y; kept',
    7: 'iris already looks to -Y; kept',
    9: 'skull face already on -Y; kept',
    10: 'chest cross already on -Y; kept',
    13: 'green radiation window already on -Y; kept',
    14: 'large white cross already on -Y; kept',
    15: 'clover emblem already on -Y; kept',
    16: 'oval pod, long axis X, open side up; no readable face, source yaw kept',
    17: 'radiation trefoil already on -Y; kept',
}
MAX_TRIS, TARGET_TRIS = 12000, 8000
STRAY_VERT_FRAC, STRAY_GAP_FRAC = 0.05, 0.015


def tris_of(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def vert_bounds(o):
    """Bounds from the mesh vertices (object bound_box goes stale after mesh.transform until a depsgraph update)."""
    a = np.array([v.co[:] for v in o.data.vertices])
    return Vector(a.min(axis=0)), Vector(a.max(axis=0))


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def remove_strays(o):
    """Delete small pieces that float apart from the main body. Returns a list of what went."""
    me = o.data
    co = [v.co.copy() for v in me.vertices]
    par = list(range(len(co)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    seen = {}
    for i, c in enumerate(co):
        k = (round(c.x, 5), round(c.y, 5), round(c.z, 5))
        if k in seen:
            par[find(i)] = find(seen[k])
        else:
            seen[k] = i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            par[a] = b
    comps = {}
    for i in range(len(co)):
        comps.setdefault(find(i), []).append(i)
    pieces = sorted(comps.values(), key=len, reverse=True)
    lo, hi = vert_bounds(o)
    diag = (hi - lo).length
    main = pieces[0]
    kd = KDTree(len(main))
    for j, i in enumerate(main):
        kd.insert(co[i], j)
    kd.balance()
    doomed, removed, kept_small = set(), [], []
    for p in pieces[1:]:
        gap = min(kd.find(co[i])[2] for i in p)
        c = sum((co[i] for i in p), Vector()) / len(p)
        info = {'verts': len(p), 'gap_cm': round(gap * 100, 1), 'centre_m': [round(x, 3) for x in c]}
        if len(p) < STRAY_VERT_FRAC * len(co) and gap > STRAY_GAP_FRAC * diag:
            doomed.update(p)
            removed.append(info)
        else:
            kept_small.append(info)
    if doomed:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in doomed], context='VERTS')
        bm.to_mesh(me)
        bm.free()
        me.update()
    return removed, kept_small, len(pieces)


def axis_with_sign(vec, hint):
    v = Vector(vec).normalized()
    return v if v.dot(Vector(hint)) >= 0 else -v


def align(o, spec):
    """Rotate the (transform-applied) mesh so spec's up goes to +Z and its front to -Y."""
    pts = np.array([v.co[:] for v in o.data.vertices])
    pts = pts - pts.mean(axis=0)
    w, vecs = np.linalg.eigh(np.cov(pts.T))
    order = np.argsort(w)[::-1]
    pca = [vecs[:, order[k]] for k in range(3)]
    kind, hint = spec['up']
    up = axis_with_sign(pca[int(kind[-1])], hint)
    kind, hint = spec['front']
    front = axis_with_sign(pca[int(kind[-1])], hint) if kind.startswith('pca') else Vector(hint)
    front = (front - up * front.dot(up)).normalized()
    right = up.cross(front).normalized()   # with front=-Y, up=+Z this gives +X
    src = Matrix((right, -front, up)).transposed()  # columns: where X, Y, Z of the target come from
    rot = src.inverted().to_4x4()
    o.data.transform(rot)
    o.data.update()
    return [round(x, 3) for x in up], [round(x, 3) for x in front]


def texture_roles(mat):
    """Map image -> role by walking upstream from the Principled BSDF inputs."""
    roles = {}
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return roles

    def walk(sock, role, depth=0):
        for l in sock.links:
            n = l.from_node
            if n.type == 'TEX_IMAGE' and n.image:
                roles.setdefault(n.image.name, role)
            elif depth < 6:
                for s in n.inputs:
                    walk(s, role, depth + 1)
    for name, role in (('Base Color', 'BaseColor'), ('Normal', 'Normal'), ('Metallic', 'ORM'),
                       ('Roughness', 'ORM'), ('Emission Color', 'Emissive'), ('Alpha', 'BaseColor')):
        if name in bsdf.inputs:
            walk(bsdf.inputs[name], role)
    return roles


def setup_render(res=512):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new('w')


def render_views(path_base, views):
    setup_render()
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    lo, hi = bounds(objs)
    centre, radius = (lo + hi) / 2, max((hi - lo).length / 2, 1e-3)
    cd = bpy.data.cameras.new('cam')
    cam = bpy.data.objects.new('cam', cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    dist = radius / math.tan(math.radians(18)) * 1.15
    out = {}
    for tag, (az, el) in views.items():
        a, e = math.radians(az), math.radians(el)
        cam.location = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.render.filepath = '%s_%s.png' % (path_base, tag)
        bpy.ops.render.render(write_still=True)
        out[tag] = bpy.context.scene.render.filepath
    return out


def clean_one(num, rel, name, target, texsize, orient):
    full = 'PU_%02d_%s' % (num, name)
    rec = {'number': num, 'source': rel + '.glb', 'output': DST + full + '.glb'}
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC + rel + '.glb')
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    rec['source_objects'] = len(meshes)
    rec['source_tris'] = sum(tris_of(o.data) for o in meshes)
    lo, hi = bounds(meshes)
    rec['source_size_cm'] = [round(v * 100, 1) for v in hi - lo]
    render_views(os.path.join(REN, '%s_before' % full), {'34': (40, 20)})

    # one mesh, transforms applied (also bakes any parent empties)
    for o in meshes:
        o.hide_set(False)
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.parent and bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for ob in [x for x in bpy.context.scene.objects if x is not o]:
        bpy.data.objects.remove(ob)

    removed, kept_small, npieces = remove_strays(o)
    rec['pieces_found'] = npieces
    rec['removed_pieces'] = removed
    rec['kept_small_pieces'] = kept_small

    if orient:
        up, front = align(o, orient)
        rec['front'] = 're-oriented: %s (source up axis %s, source front %s)' % (orient['why'], up, front)
    else:
        rec['front'] = FRONT_NOTE.get(num, 'kept')

    # pivot at the bottom centre, then scale the largest dimension to the game size
    lo, hi = vert_bounds(o)
    shift = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    o.data.transform(Matrix.Translation(-shift))
    k = target / max(hi - lo)
    o.data.transform(Matrix.Scale(k, 4))
    o.data.update()
    rec['size_class'] = 'crate/vest 60 cm' if target == CRATE else 'hand-size 45 cm'

    tris = tris_of(o.data)
    if tris > MAX_TRIS:
        select_only(o)
        mod = o.modifiers.new('dec', 'DECIMATE')
        mod.ratio = TARGET_TRIS / tris
        bpy.ops.object.modifier_apply(modifier=mod.name)
        rec['decimated_from'] = tris

    # names, material, textures
    o.name = o.data.name = full
    mats = [s.material for s in o.material_slots if s.material]
    rec['materials'] = len(mats)
    texs = {}
    for mi, mat in enumerate(mats):
        mat.name = 'M_%s' % full if mi == 0 else 'M_%s_%d' % (full, mi)
        roles = texture_roles(mat)
        for n in mat.node_tree.nodes:
            if n.type != 'TEX_IMAGE' or not n.image:
                continue
            img = n.image
            src = tuple(img.size)
            if max(src) > texsize:
                img.scale(texsize, texsize)
            role = roles.get(img.name, 'Tex%d' % len(texs))
            img.name = 'T_%s_%s' % (full, role)
            texs[img.name] = {'source_px': list(src)}
    select_only(o)
    bpy.ops.export_scene.gltf(filepath=DST + full + '.glb', export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True, export_animations=False,
                              export_image_format='AUTO')

    # verify the written file, render it
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=DST + full + '.glb')
    meshes = [x for x in bpy.context.scene.objects if x.type == 'MESH']
    lo, hi = bounds(meshes)
    rec['objects'] = len(meshes)
    rec['final_tris'] = sum(tris_of(x.data) for x in meshes)
    rec['size_cm'] = [round(v * 100, 1) for v in hi - lo]
    rec['pivot_check_cm'] = {'min_z': round(lo.z * 100, 2), 'centre_x': round((lo.x + hi.x) * 50, 2),
                             'centre_y': round((lo.y + hi.y) * 50, 2)}
    for img in bpy.data.images:
        if img.size[0]:
            texs.setdefault(img.name, {})['final_px'] = list(img.size)
    rec['textures'] = texs
    rec['file_mb'] = round(os.path.getsize(DST + full + '.glb') / 1e6, 2)
    shots = render_views(os.path.join(REN, '%s_after' % full), {'34': (40, 20), 'front': (0, 5)})
    rec['renders'] = shots
    print('CLEANED', full, rec['final_tris'], rec['size_cm'], 'removed', removed, flush=True)
    return full, rec


def contact_sheet(rows):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('CLEAN_SHEET_SKIPPED no PIL in this Blender python', flush=True)
        return None
    cell, cols = 240, 3
    lab = 34
    cw, ch = cell * 3 + 12, cell + lab + 8
    nrows = (len(rows) + cols - 1) // cols
    head = 40
    sheet = Image.new('RGB', (cw * cols, head + ch * nrows), (34, 34, 38))
    d = ImageDraw.Draw(sheet)
    try:
        big = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 20)
        small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 14)
    except OSError:
        big = small = ImageFont.load_default()
    d.text((10, 8), 'Power-ups cleaned 2026-10-31   each cell: BEFORE 3/4  |  AFTER 3/4  |  AFTER front (-Y)',
           fill=(230, 230, 230), font=big)
    for i, (full, r) in enumerate(rows):
        x, y = (i % cols) * cw, head + (i // cols) * ch
        imgs = [os.path.join(REN, '%s_before_34.png' % full), r['renders']['34'], r['renders']['front']]
        for j, p in enumerate(imgs):
            sheet.paste(Image.open(p).convert('RGB').resize((cell, cell)), (x + j * cell, y + lab))
        d.line((x + cell, y + lab, x + cell, y + lab + cell), fill=(240, 200, 60), width=2)
        d.text((x + 6, y + 4), '%d' % r['number'], fill=(250, 200, 50), font=big)
        rm = sum(p['verts'] for p in r['removed_pieces'])
        d.text((x + 42, y + 9), '%s   %s cm   %d tris%s' % (
            full, ' x '.join('%g' % v for v in r['size_cm']), r['final_tris'],
            ('   removed %d verts' % rm) if rm else ''), fill=(220, 220, 220), font=small)
    path = os.path.join(OUT, 'clean_sheet.png')
    sheet.save(path)
    return path


rows = []
for m in MODELS:
    rows.append(clean_one(*m))
receipt = {
    'script': 'Scripts/Blender/CleanPowerUps.py', 'date': '2026-10-31',
    'rules': {'stray': 'piece < %d %% of verts and > %.1f %% of the model diagonal away from the main body'
              % (STRAY_VERT_FRAC * 100, STRAY_GAP_FRAC * 100),
              'size': 'largest dimension 45 cm hand-size, 60 cm crates (#5, #14) and the vest (#10)',
              'pivot': 'bottom centre (bbox centre in X/Y, min Z = 0)', 'front': '-Y in Blender (glTF/UE forward)',
              'textures': '1024, 2048 for #3 shield and #17 Nuke', 'decimate': 'only if > %d tris, to ~%d'
              % (MAX_TRIS, TARGET_TRIS)},
    'models': {full: r for full, r in rows},
}
json.dump(receipt, open(os.path.join(OUT, 'clean.json'), 'w'), indent=1)
sheet = contact_sheet(rows)
print('CLEAN_POWERUPS_DONE', len(rows), sheet, flush=True)
