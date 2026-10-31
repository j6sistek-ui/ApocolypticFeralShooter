"""Headless survey of the 30 EM Apocalyptic Guns Vol 23 FBX files.

Usage: blender -b --factory-startup --python SurveyEMGuns.py
Writes em_guns_survey.json and em_guns_islands_sheet.png beside the pack.
Per gun: tris, node transform, raw and world bounds, orientation, loose islands
(raw and welded), and the largest islands below the bore line (magazine candidates).
"""
import bpy, os, glob, json, math
import numpy as np
from mathutils import Matrix

PACK = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns"
ROOT = os.path.join(PACK, "FBX", "EM_Apocalyptic_Guns_FBX")
OUT_JSON = os.path.join(PACK, "em_guns_survey.json")
OUT_SHEET = os.path.join(PACK, "em_guns_uv_islands_sheet.png")
TILE_W, TILE_H, COLS = 768, 432, 5


def islands(nv, edges, key=None):
    """Connected components over edges; key maps verts to welded ids."""
    if key is not None:
        nv2 = int(key.max()) + 1
        edges = key[edges]
    else:
        nv2 = nv
    lab = np.arange(nv2)
    a, b = edges[:, 0], edges[:, 1]
    while True:
        m = np.minimum(lab[a], lab[b])
        old = lab.copy()
        np.minimum.at(lab, a, m)
        np.minimum.at(lab, b, m)
        lab = lab[lab]
        lab = lab[lab]
        if np.array_equal(lab, old):
            break
    if key is not None:
        lab = lab[key]
    _, comp = np.unique(lab, return_inverse=True)
    return comp.reshape(-1)


# Verified by eye from the file-orientation renders (SurveyEMGunsFileAxes.py): every gun
# has Z up and the barrel on world X after the importer's node transform; these point -X.
MUZZLE_MINUS_X = {"EM_13", "EM_14", "EM_15", "EM_16", "EM_17", "EM_18", "EM_19", "EM_20",
                  "EM_21", "EM_22", "EM_25"}


def gun_frame_verified(co, gun):
    ext = co.max(0) - co.min(0)
    return 0, 2, 1, (-1 if gun in MUZZLE_MINUS_X else 1), ext


def gun_frame(co):
    """Heuristic only (kept for the record): longest axis = barrel, taller end = stock."""
    ext = co.max(0) - co.min(0)
    order = list(np.argsort(-ext))
    longest = int(order[0])
    if longest != 2:
        u_ax, v_ax = longest, 2
    else:
        u_ax, v_ax = 2, int(order[1])
    w_ax = 3 - u_ax - v_ax
    lo, hi = co[:, u_ax].min(), co[:, u_ax].max()
    t = (co[:, u_ax] - lo) / max(hi - lo, 1e-9)

    def vext(mask):
        s = co[mask, v_ax]
        return (s.max() - s.min()) if s.size else 0

    # The stock / grip end is taller than the muzzle end.
    u_sign = 1 if vext(t < .12) >= vext(t > .88) else -1
    return u_ax, v_ax, w_ax, u_sign, ext


def survey(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    o = meshes[0]
    me = o.data
    nv = len(me.vertices)
    raw = np.empty(nv * 3)
    me.vertices.foreach_get('co', raw)
    raw = raw.reshape(-1, 3)
    mw = np.array(o.matrix_world)
    co = (raw @ mw[:3, :3].T + mw[:3, 3]) * 100.0  # world cm, as Unreal imports a cm-unit FBX
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ed)
    ed = ed.reshape(-1, 2)
    lt = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get('loop_total', lt)
    tris = int((lt - 2).sum())
    ls = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get('loop_start', ls)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get('vertex_index', lv)
    poly_v0 = lv[ls]

    comp_raw = islands(nv, ed)
    q = np.round(co / 0.001).astype(np.int64)  # weld at 0.01 mm
    _, key = np.unique(q, axis=0, return_inverse=True)
    comp = islands(nv, ed, key.reshape(-1))
    n_isl = int(comp.max() + 1)

    gun = os.path.basename(os.path.dirname(path))[:5]
    h = gun_frame(co)
    heuristic = "XYZ"[h[0]] + ("+" if h[3] > 0 else "-")
    u_ax, v_ax, w_ax, u_sign, ext = gun_frame_verified(co, gun)
    U = co[:, u_ax] * u_sign
    V = co[:, v_ax]
    W = co[:, w_ax]
    gu0, gu1, gv0, gv1 = U.min(), U.max(), V.min(), V.max()
    nu = (U - gu0) / (gu1 - gu0)
    nvv = (V - gv0) / (gv1 - gv0)
    front = nu > .75
    bore = float(np.median(nvv[front])) if front.any() else .7

    ptris = np.bincount(comp[poly_v0], weights=(lt - 2), minlength=n_isl)
    isl = []
    for i in np.argsort(-ptris)[:300]:
        m = comp == i
        if not m.any():
            continue
        sz = np.array([np.ptp(U[m]), np.ptp(V[m]), np.ptp(W[m])])
        isl.append(dict(id=int(i), tris=int(ptris[i]),
                        u=[round(float(nu[m].min()), 3), round(float(nu[m].max()), 3)],
                        v=[round(float(nvv[m].min()), 3), round(float(nvv[m].max()), 3)],
                        size_cm=[round(float(x), 2) for x in sz], vol_cm3=round(float(np.prod(sz)), 1)))
    main = isl[0]
    cands = [d for d in isl[1:] if d['v'][1] <= bore + .08 and d['v'][0] < bore - .25
             and .12 < (d['u'][0] + d['u'][1]) / 2 < .9 and d['size_cm'][1] > 3]
    cands.sort(key=lambda d: -d['vol_cm3'])
    rot = [round(math.degrees(a), 1) for a in o.rotation_euler]
    res = dict(
        gun=os.path.basename(os.path.dirname(path))[:5], file=os.path.relpath(path, PACK), object=o.name,
        materials=[s.material.name if s.material else None for s in o.material_slots],
        mesh_objects=len(meshes), verts=nv, tris=tris,
        node_rotation_deg=rot, node_scale=[round(s, 4) for s in o.scale],
        raw_bounds_units=[round(float(x), 2) for x in np.ptp(raw, 0)],
        world_bounds_cm=[round(float(x), 1) for x in ext],
        length_cm=round(float(gu1 - gu0), 1), height_cm=round(float(gv1 - gv0), 1),
        width_cm=round(float(np.ptp(W)), 1),
        length_cm_if_raw_x2p54=round(float(np.ptp(raw, 0).max() * 2.54), 1),
        axes=dict(barrel="XYZ"[u_ax] + ("+" if u_sign > 0 else "-"), up="XYZ"[v_ax], lateral="XYZ"[w_ax]),
        muzzle_heuristic=heuristic,
        node_transform_nonstandard=bool(abs(rot[0] - 90) > .5 or abs(rot[1]) > .5 or abs(rot[2]) > .5
                                        or abs(o.scale[0] - .01) > 1e-4),
        islands_raw=int(comp_raw.max() + 1), islands_welded=n_isl,
        main_island_tri_share=round(main['tris'] / max(tris, 1), 3),
        bore_line_v=round(bore, 3), top_islands=isl[:8], mag_candidates=cands[:3])
    res.update(uv_survey(o, nu, nvv, bore))
    return res, o, comp, (u_ax, v_ax, w_ax, u_sign)


def uv_survey(o, nu, nvv, bore):
    """UV islands (faces joined across edges whose UVs match). A magazine that owns its UV
    islands can be cut along those seams with no texture damage."""
    import bmesh
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    nf = len(bm.faces)
    par = list(range(nf))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    eps = 1e-5
    for f in bm.faces:
        for l in f.loops:
            r = l.link_loop_radial_next
            if r is l or r.face.index < f.index:
                continue
            a0, a1 = l[uvl].uv, l.link_loop_next[uvl].uv
            b0, b1 = r.link_loop_next[uvl].uv, r[uvl].uv
            if (a0 - b0).length < eps and (a1 - b1).length < eps:
                ra, rb = find(f.index), find(r.face.index)
                if ra != rb:
                    par[ra] = rb
    roots = np.array([find(i) for i in range(nf)])
    _, fis = np.unique(roots, return_inverse=True)
    fis = fis.reshape(-1)
    n = int(fis.max() + 1)
    fv = [[v.index for v in f.verts] for f in bm.faces]
    fu = np.array([nu[i].mean() for i in fv])
    fvv = np.array([nvv[i].mean() for i in fv])
    fa = np.array([f.calc_area() for f in bm.faces]) * (o.scale[0] * 100) ** 2  # raw units -> cm2
    bm.free()
    out = []
    for k in range(n):
        m = fis == k
        out.append(dict(uv_island=k, faces=int(m.sum()), area_cm2=round(float(fa[m].sum()), 1),
                        u=[round(float(fu[m].min()), 3), round(float(fu[m].max()), 3)],
                        v=[round(float(fvv[m].min()), 3), round(float(fvv[m].max()), 3)]))
    cands = [d for d in out if d['v'][1] <= bore + .03 and d['v'][0] < bore - .25
             and .12 < (d['u'][0] + d['u'][1]) / 2 < .9]
    cands.sort(key=lambda d: -d['area_cm2'])
    # Auto-pick the pipeline would use: the biggest candidate plus any island that overlaps
    # it along the barrel by half (mirrored left/right halves, base plate, follower).
    pick = []
    if cands and cands[0]['faces'] >= 60:
        c0 = cands[0]
        for d in cands + [x for x in out if x not in cands]:
            ov = min(d['u'][1], c0['u'][1]) - max(d['u'][0], c0['u'][0])
            span = d['u'][1] - d['u'][0]
            if (d is c0 or (span > 0 and ov / span > .5 and d['v'][1] <= bore + .03
                            and d['v'][0] < c0['v'][1] and d['faces'] >= 8)):
                pick.append(d['uv_island'])
    return dict(uv_islands=n, uv_mag_candidates=cands[:4], uv_mag_autopick=pick, _face_uv_island=fis)


def render_tile(o, comp, frame, label, outpng, baked=False, pal=None):
    u_ax, v_ax, w_ax, u_sign = frame
    for ob in [x for x in bpy.context.scene.objects if x.type in ('CAMERA', 'FONT')]:
        bpy.data.objects.remove(ob)
    R = np.zeros((3, 3))
    R[0, u_ax] = u_sign
    R[2, v_ax] = 1
    R[1] = np.cross(R[2], R[0])
    M = Matrix([list(r) + [0] for r in R] + [[0, 0, 0, 1]])
    S = Matrix.Diagonal((100, 100, 100, 1))
    if not baked:
        o.data.transform(S @ o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.data.transform(M)
    o.data.update()
    me = o.data
    rng = np.random.default_rng(7)
    if pal is None:
        pal = rng.uniform(.15, 1, (int(comp.max()) + 1, 3))
    attr = me.color_attributes.new("isl%d" % len(me.color_attributes), 'FLOAT_COLOR', 'CORNER')
    lt = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get('loop_total', lt)
    per_loop = np.repeat(comp, lt)
    col = np.concatenate([pal[per_loop], np.ones((len(per_loop), 1))], 1).astype(np.float32)
    attr.data.foreach_set('color', col.ravel())
    me.color_attributes.active_color = attr
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'VERTEX'
    sh.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = TILE_W, TILE_H
    if not sc.world:
        sc.world = bpy.data.worlds.new("w")
    cof = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', cof)
    cof = cof.reshape(-1, 3)
    lo, hi = cof.min(0), cof.max(0)
    c = (lo + hi) / 2
    e = hi - lo
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    s = max(e[0], e[2] * TILE_W / TILE_H) * 1.15
    cam.data.ortho_scale = s
    cam.location = (c[0], lo[1] - 50, c[2] + s * .03)
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_end = 10000
    sc.camera = cam
    txt = bpy.data.curves.new("t", 'FONT')
    txt.body = label
    t = bpy.data.objects.new("t", txt)
    sc.collection.objects.link(t)
    t.rotation_euler = (math.radians(90), 0, 0)
    t.scale = (s * .04,) * 3
    t.location = (c[0] - s / 2 + s * .02, lo[1] - 10, cam.location[2] + s * TILE_H / TILE_W / 2 - s * .06)
    sc.render.filepath = outpng
    bpy.ops.render.render(write_still=True)


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "EM_*", "*.fbx")))
    tmp = os.path.join(PACK, "_survey_tiles")
    os.makedirs(tmp, exist_ok=True)
    out = []
    for f in files:
        r, o, comp, frame = survey(f)
        print("SURVEY", r['gun'], r['tris'], r['length_cm'], r['islands_welded'], r['axes'], len(r['mag_candidates']))
        tile = os.path.join(tmp, r['gun'] + ".png")
        fis = r.pop('_face_uv_island')
        lab = "%s  mesh islands %d  UV islands %d  %d cm" % (r['gun'], r['islands_welded'], r['uv_islands'], round(r['length_cm']))
        render_tile(o, fis, frame, lab, tile)
        r['island_tile'] = os.path.relpath(tile, PACK)
        mask = np.isin(fis, r['uv_mag_autopick']).astype(np.int64)
        tile2 = os.path.join(tmp, r['gun'] + "_magpick.png")
        render_tile(o, mask, frame, "%s  auto-picked magazine UV islands: %d" % (r['gun'], len(r['uv_mag_autopick'])),
                    tile2, baked=True, pal=np.array([(.6, .6, .6), (.9, .12, .1)]))
        r['magpick_tile'] = os.path.relpath(tile2, PACK)
        out.append(r)
    with open(OUT_JSON, 'w') as fh:
        json.dump(dict(pack="EM Apocalyptic Guns Vol 23", source="FBX",
                       units_note="FBX header UnitScaleFactor=1.0 (cm), Maya, Y-up; world_bounds_cm is what "
                                  "Unreal imports at scale 1.0 with node transforms applied",
                       guns=out), fh, indent=1)
    sheet_of(out, 'island_tile', OUT_SHEET)
    sheet_of(out, 'magpick_tile', os.path.join(PACK, "em_guns_mag_autopick_sheet.png"))
    print("WROTE", OUT_JSON, OUT_SHEET)


def sheet_of(out, field, path):
    rows = math.ceil(len(out) / COLS)
    sheet = np.zeros((rows * TILE_H, COLS * TILE_W, 4), np.float32)
    for k, r in enumerate(out):
        img = bpy.data.images.load(os.path.join(PACK, r[field]))
        px = np.array(img.pixels[:], np.float32).reshape(TILE_H, TILE_W, 4)
        rr, cc = k // COLS, k % COLS
        y0 = (rows - 1 - rr) * TILE_H
        sheet[y0:y0 + TILE_H, cc * TILE_W:(cc + 1) * TILE_W] = px
    im = bpy.data.images.new("sheet", COLS * TILE_W, rows * TILE_H, alpha=True)
    im.pixels.foreach_set(sheet.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()


main()
