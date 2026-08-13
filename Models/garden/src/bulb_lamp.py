def _cr(p0, p1, p2, p3, t):
    # Catmull-Rom interpolation of 2D (r, z) tuples
    t2 = t * t
    t3 = t2 * t
    out = []
    for a, b, c, d in ((p0[0], p1[0], p2[0], p3[0]), (p0[1], p1[1], p2[1], p3[1])):
        out.append(0.5 * ((2.0 * b) + (-a + c) * t +
                          (2.0 * a - 5.0 * b + 4.0 * c - d) * t2 +
                          (-a + 3.0 * b - 3.0 * c + d) * t3))
    return (out[0], out[1])


def _finish(name, verts, faces, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def _bm_finish(name, bm, mat):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def build(rng, M):
    TAU = 2.0 * math.pi
    S = 26                                # radial segments of the lathe
    zs = rng.uniform(0.92, 1.06)          # height scale
    rs = rng.uniform(0.94, 1.05)          # girth scale
    lx = rng.uniform(-0.10, 0.10)         # lean of the whole gourd
    ly = rng.uniform(-0.10, 0.10)
    nx = rng.uniform(0.0, 100.0)          # noise domain offsets
    ny = rng.uniform(0.0, 100.0)
    nz = rng.uniform(0.0, 100.0)
    lobn = rng.choice([3, 4, 5])          # gentle gourd lobes
    lobp = rng.uniform(0.0, TAU)
    loba = rng.uniform(0.008, 0.020)
    Ztop = 4.0 * zs                       # top of the neck

    def lean(z):
        f = (z / Ztop) ** 2
        return (lx * f, ly * f)

    def wob(th, z):
        n = noise.noise(Vector((math.cos(th) * 0.9 + nx,
                                math.sin(th) * 0.9 + ny,
                                z * 0.55 + nz)))
        return 1.0 + 0.035 * n + loba * math.cos(lobn * th + lobp)

    # ---- teardrop body (lathe) --------------------------------------
    ctrl = [(0.28, 0.14), (0.62, 0.18), (1.12, 0.32), (1.56, 0.58),
            (1.80, 1.05), (1.78, 1.55), (1.55, 2.15), (1.18, 2.75),
            (0.82, 3.25), (0.55, 3.62), (0.36, 3.88), (0.28, 4.00)]
    ctrl = [(r * rs, z * zs) for (r, z) in ctrl]
    prof = []
    n = len(ctrl)
    for i in range(n - 1):
        p0 = ctrl[max(i - 1, 0)]
        p1 = ctrl[i]
        p2 = ctrl[i + 1]
        p3 = ctrl[min(i + 2, n - 1)]
        for s in range(2):
            prof.append(_cr(p0, p1, p2, p3, s / 2.0))
    prof.append(ctrl[-1])

    verts = []
    faces = []
    for (r, z) in prof:
        cx, cy = lean(z)
        for j in range(S):
            th = TAU * j / S
            w = wob(th, z)
            verts.append((cx + r * w * math.cos(th),
                          cy + r * w * math.sin(th), z))
    nr = len(prof)
    for i in range(nr - 1):
        for j in range(S):
            a = i * S + j
            b = i * S + (j + 1) % S
            c = (i + 1) * S + (j + 1) % S
            d = (i + 1) * S + j
            faces.append((a, b, c, d))
    # bottom cap
    cb = len(verts)
    verts.append((0.0, 0.0, max(prof[0][1] - 0.05 * zs, 0.02)))
    for j in range(S):
        faces.append((cb, (j + 1) % S, j))
    # top cap
    ct = len(verts)
    cx, cy = lean(Ztop)
    verts.append((cx, cy, Ztop + 0.03 * zs))
    base = (nr - 1) * S
    for j in range(S):
        faces.append((ct, base + j, base + (j + 1) % S))
    _finish('bulb_lamp_body', verts, faces, M('plaster_gourd'))

    # ---- stubby feet ------------------------------------------------
    bm = bmesh.new()
    nfeet = rng.choice([3, 4])
    a0 = rng.uniform(0.0, TAU)
    for k in range(nfeet):
        a = a0 + TAU * k / nfeet + rng.uniform(-0.12, 0.12)
        jit = rng.uniform(0.9, 1.1)
        h = 0.58 * zs * rng.uniform(0.9, 1.08)
        r1 = 0.30 * rs * jit
        r2 = 0.20 * rs * jit
        fr = 0.95 * rs
        sh = 0.10 * rs                      # shear: bottom out, top in
        ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True,
                                    segments=9, radius1=r1, radius2=r2,
                                    depth=h)
        ca = math.cos(a)
        sa = math.sin(a)
        for v in ret['verts']:
            if v.co.z > 0.0:
                v.co.x -= sh * ca
                v.co.y -= sh * sa
            v.co.z = max(v.co.z + h * 0.5, 0.0)
            v.co.x += fr * ca
            v.co.y += fr * sa
    _bm_finish('bulb_lamp_feet', bm, M('plaster_gourd'))

    # ---- collar ring under the tip ---------------------------------
    maj = 0.34 * rs
    minr = 0.09 * rs
    zc = Ztop + 0.05 * zs
    ccx, ccy = lean(zc)
    Mm = 20
    mn = 8
    cverts = []
    cfaces = []
    for i in range(Mm):
        phi = TAU * i / Mm
        mw = 1.0 + 0.02 * noise.noise(Vector((math.cos(phi) + nx,
                                              math.sin(phi) + ny, zc + nz)))
        for j in range(mn):
            th = TAU * j / mn
            rr = maj * mw + minr * math.cos(th)
            cverts.append((ccx + rr * math.cos(phi),
                           ccy + rr * math.sin(phi),
                           zc + minr * 0.8 * math.sin(th)))
    for i in range(Mm):
        for j in range(mn):
            a = i * mn + j
            b = i * mn + (j + 1) % mn
            c = ((i + 1) % Mm) * mn + (j + 1) % mn
            d = ((i + 1) % Mm) * mn + j
            cfaces.append((a, b, c, d))
    _finish('bulb_lamp_collar', cverts, cfaces, M('metal_ring'))

    # ---- glowing tip sphere ----------------------------------------
    bm = bmesh.new()
    tr = 0.31 * rs
    ret = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10,
                                    radius=tr)
    tz = Ztop + 0.26 * zs
    tcx, tcy = lean(tz)
    for v in ret['verts']:
        v.co.z = v.co.z * 0.92 + tz
        v.co.x += tcx
        v.co.y += tcy
    _bm_finish('bulb_lamp_tip', bm, M('lamp_tip'))
