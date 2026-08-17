def _mam_off(rng):
    return Vector((rng.uniform(-50.0, 50.0), rng.uniform(-50.0, 50.0), rng.uniform(-50.0, 50.0)))


def _mam_noise(p, off, freq):
    return noise.noise(Vector((p.x * freq + off.x, p.y * freq + off.y, p.z * freq + off.z)))


def build(rng, M):
    PFX = 'moss_arch_mound_'
    R, H = 3.0, 2.5
    seg, rings = 64, 22
    sx = rng.uniform(0.96, 1.08)
    sy = rng.uniform(0.88, 1.0)
    o1 = _mam_off(rng)
    o2 = _mam_off(rng)

    # ---- lumpy dome (closed: top pole, wall rings, flat bottom cap) ----
    bm = bmesh.new()
    top = bm.verts.new((0.0, 0.0, H))
    rows = []
    for i in range(1, rings + 1):
        phi = (i / rings) * (math.pi / 2.0)
        r = R * math.sin(phi)
        z = H * math.cos(phi)
        row = []
        for j in range(seg):
            th = 2.0 * math.pi * j / seg
            row.append(bm.verts.new((r * math.cos(th) * sx, r * math.sin(th) * sy, z)))
        rows.append(row)
    for j in range(seg):
        bm.faces.new((top, rows[0][j], rows[0][(j + 1) % seg]))
    for i in range(rings - 1):
        a, b = rows[i], rows[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((a[j], b[j], b[k], a[k]))
    bot = bm.verts.new((0.0, 0.0, 0.0))
    bottom_ring = rows[-1]
    for j in range(seg):
        k = (j + 1) % seg
        bm.faces.new((bot, bottom_ring[k], bottom_ring[j]))

    bottom_set = set(bottom_ring)
    amp = 0.30
    for v in bm.verts:
        if v is bot:
            continue
        p = v.co.copy()
        d = _mam_noise(p, o1, 0.55) + 0.45 * _mam_noise(p, o2, 1.4)
        dirv = Vector((p.x, p.y, max(p.z, 0.001) * 1.2))
        if dirv.length < 1e-6:
            dirv = Vector((0.0, 0.0, 1.0))
        dirv.normalize()
        v.co = p + dirv * (d * amp)
        if v in bottom_set:
            v.co.z = 0.0
        elif v.co.z < 0.0:
            v.co.z = 0.0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(PFX + 'dome')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(PFX + 'mound', me)
    bpy.context.collection.objects.link(ob)

    # ---- arch tunnel cutter (rect sides + semicircular crown, runs along Y) ----
    w2 = 0.75
    spring = 0.80
    L = 4.6
    zlow = -0.4
    ang = rng.uniform(-0.15, 0.15)
    dx = rng.uniform(-0.2, 0.2)
    prof = [(w2, zlow)]
    narc = 12
    for k2 in range(narc + 1):
        t = math.pi * k2 / narc
        prof.append((w2 * math.cos(t), spring + 0.72 * math.sin(t)))
    prof.append((-w2, zlow))
    ca, sa = math.cos(ang), math.sin(ang)
    cb = bmesh.new()

    def mkvert(x, y, z):
        X = x + dx
        return cb.verts.new((X * ca - y * sa, X * sa + y * ca, z))

    front = [mkvert(x, -L, z) for (x, z) in prof]
    back = [mkvert(x, L, z) for (x, z) in prof]
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        cb.faces.new((front[i], front[j], back[j], back[i]))
    cfv = mkvert(0.0, -L, 0.35)
    cbv = mkvert(0.0, L, 0.35)
    for i in range(n):
        j = (i + 1) % n
        cb.faces.new((cfv, front[j], front[i]))
        cb.faces.new((cbv, back[i], back[j]))
    bmesh.ops.recalc_face_normals(cb, faces=cb.faces)
    cme = bpy.data.meshes.new(PFX + 'cutter')
    cb.to_mesh(cme)
    cb.free()
    cob = bpy.data.objects.new(PFX + 'cutter', cme)
    bpy.context.collection.objects.link(cob)

    # ---- boolean difference, applied via depsgraph (no context-dependent ops) ----
    mod = ob.modifiers.new('cut', 'BOOLEAN')
    mod.object = cob
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    deps = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    me2.name = PFX + 'mound'
    ob.modifiers.clear()
    ob.data = me2
    bpy.data.meshes.remove(me)
    bpy.data.objects.remove(cob)
    bpy.data.meshes.remove(cme)

    # ---- clean ngons, clamp, assign materials by face normal ----
    bm = bmesh.new()
    bm.from_mesh(me2)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons)
    for v in bm.verts:
        if v.co.z < 0.0:
            v.co.z = 0.0
    bm.normal_update()
    for f in bm.faces:
        f.material_index = 0 if f.normal.z > 0.4 else 1
    # despeckle: flip isolated faces so material boundaries ink as clean blobs
    for _p in range(3):
        flips = []
        for f in bm.faces:
            nb = [lf.material_index for e in f.edges for lf in e.link_faces if lf is not f]
            if len(nb) >= 2:
                other = 1 - f.material_index
                if all(m == other for m in nb):
                    flips.append(f)
        if not flips:
            break
        for f in flips:
            f.material_index = 1 - f.material_index
    bm.to_mesh(me2)
    bm.free()
    me2.materials.append(M('moss_top'))
    me2.materials.append(M('plaster_base'))

    # ---- moss tuft bumps: squashed noisy little domes rayed onto the top ----
    tb = bmesh.new()
    want = rng.randint(6, 10)
    placed = []
    tries = 0
    while len(placed) < want and tries < 90:
        tries += 1
        th = rng.uniform(0.0, 2.0 * math.pi)
        rr = R * math.sqrt(rng.uniform(0.01, 0.5))
        x = rr * math.cos(th) * sx
        y = rr * math.sin(th) * sy
        rad = rng.uniform(0.2, 0.42)
        too_close = False
        for (px, py, pr) in placed:
            if (px - x) ** 2 + (py - y) ** 2 < (pr + rad) ** 2 * 0.6:
                too_close = True
                break
        if too_close:
            continue
        hit, loc, nrm, _fi = ob.ray_cast(Vector((x, y, 10.0)), Vector((0.0, 0.0, -1.0)))
        if (not hit) or nrm.z < 0.55 or loc.z < 0.7:
            continue
        zs = rng.uniform(0.55, 0.8)
        ret = bmesh.ops.create_uvsphere(tb, u_segments=8, v_segments=5, radius=rad)
        wob_off = rng.uniform(0.0, 40.0)
        for v in ret['verts']:
            c = v.co.copy()
            w = 1.0 + 0.28 * noise.noise(Vector((c.x * 3.0 + wob_off, c.y * 3.0, c.z * 3.0 + wob_off)))
            v.co = Vector((loc.x + c.x * w, loc.y + c.y * w, loc.z + c.z * zs * w - rad * 0.35))
        placed.append((x, y, rad))
    if placed:
        bmesh.ops.recalc_face_normals(tb, faces=tb.faces)
        for f in tb.faces:
            f.material_index = 0
        tme = bpy.data.meshes.new(PFX + 'tufts')
        tb.to_mesh(tme)
        tme.materials.append(M('moss_top'))
        tob = bpy.data.objects.new(PFX + 'tufts', tme)
        bpy.context.collection.objects.link(tob)
    tb.free()
