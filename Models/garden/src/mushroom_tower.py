def _finish(name, verts, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def _lathe(name, prof, segs, mat, wob=0.0, nscale=0.8, soff=0.0):
    # prof: list of (radius, z, cx, cy); radius <= 1e-4 makes a pole point
    verts = []
    rows = []
    for (r, z, cx, cy) in prof:
        if r <= 1e-4:
            rows.append(len(verts))
            verts.append((cx, cy, z))
        else:
            ring = []
            for i in range(segs):
                a = 2.0 * math.pi * i / segs
                x, y = math.cos(a), math.sin(a)
                nv = noise.noise(Vector((x * nscale + soff, y * nscale + soff, z * 0.55 + soff * 0.7)))
                rr = r * (1.0 + wob * nv)
                ring.append(len(verts))
                verts.append((cx + x * rr, cy + y * rr, z))
            rows.append(ring)
    faces = []
    for k in range(len(rows) - 1):
        A, B = rows[k], rows[k + 1]
        if isinstance(A, int) and isinstance(B, list):
            for i in range(segs):
                faces.append((A, B[(i + 1) % segs], B[i]))
        elif isinstance(A, list) and isinstance(B, int):
            for i in range(segs):
                faces.append((A[i], A[(i + 1) % segs], B))
        elif isinstance(A, list) and isinstance(B, list):
            for i in range(segs):
                j = (i + 1) % segs
                faces.append((A[i], A[j], B[j], B[i]))
    return _finish(name, verts, faces, mat)


def _cap_top(R, H, phi):
    # dome arc from rim (phi=0) to apex (phi=pi/2)
    r = 1.03 * R * (math.cos(phi) ** 0.88)
    z = H * (math.sin(phi) ** 1.08) + 0.05 * H
    return r, z


def build(rng, M):
    P = 'mushroom_tower_'
    segs = 24

    htot = rng.uniform(8.6, 9.3)
    ncaps = 3 if rng.random() < 0.6 else 2
    Rbig = rng.uniform(2.35, 2.6)
    if ncaps == 3:
        fr = (0.46, 0.72, 0.92)
        rf = (1.0, 0.66, 0.45)
    else:
        fr = (0.54, 0.92)
        rf = (1.0, 0.55)
    caps = []
    for f, rr in zip(fr, rf):
        R = Rbig * rr * rng.uniform(0.94, 1.06)
        H = R * rng.uniform(0.44, 0.54)
        droop = R * rng.uniform(0.20, 0.28)
        caps.append((htot * f, R, H, droop))
    ztop = caps[-1][0] + 0.35

    lx = rng.uniform(-0.45, 0.45)
    ly = rng.uniform(-0.45, 0.45)

    def cline(z):
        t = max(0.0, min(1.0, z / ztop))
        s = t ** 1.6
        return lx * s, ly * s

    # ---------- stem ----------
    rbase = rng.uniform(1.05, 1.25)
    rtop = rng.uniform(0.36, 0.46)
    bulge_ph = rng.uniform(0.0, 6.28)
    cx0, cy0 = cline(0.0)
    prof = [(0.0, 0.0, cx0, cy0)]
    nz = 16
    for i in range(nz + 1):
        t = i / nz
        z = t * ztop
        r = rtop + (rbase - rtop) * (1.0 - t) ** 1.8
        r *= 1.0 + 0.07 * math.sin(z * 1.9 + bulge_ph)
        cx, cy = cline(z)
        prof.append((r, z, cx, cy))
    tx, ty = cline(ztop)
    prof.append((0.0, ztop + 0.12, tx, ty))
    _lathe(P + 'stem', prof, segs, M('plaster_stem'),
           wob=rng.uniform(0.05, 0.09), nscale=0.9, soff=rng.uniform(0.0, 50.0))

    # ---------- caps ----------
    cap_data = []
    for ci, (zc, R, H, droop) in enumerate(caps):
        ccx, ccy = cline(zc)
        ccx += rng.uniform(-0.12, 0.12)
        ccy += rng.uniform(-0.12, 0.12)
        prof = [(0.0, zc + 0.30 * H, ccx, ccy)]
        und = ((0.26 * R, 0.20 * H), (0.52 * R, 0.05 * H),
               (0.78 * R, -0.40 * droop), (0.93 * R, -0.78 * droop),
               (1.0 * R, -droop), (1.045 * R, -0.45 * droop), (1.055 * R, 0.04 * H))
        for r, dz in und:
            prof.append((r, zc + dz, ccx, ccy))
        ntop = 8
        for i in range(1, ntop + 1):
            phi = (i / ntop) * (math.pi / 2.0)
            r, dz = _cap_top(R, H, phi)
            prof.append((r, zc + dz, ccx, ccy))
        _lathe(P + 'cap%d' % ci, prof, segs, M('flesh_cap'),
               wob=rng.uniform(0.045, 0.075), nscale=0.7, soff=rng.uniform(0.0, 50.0))
        cap_data.append((zc, R, H, ccx, ccy))

    # ---------- ragged frill under the lowest cap ----------
    zc0, R0, H0, d0 = caps[0]
    fcx, fcy = cap_data[0][3], cap_data[0][4]
    fsegs = 26
    fverts = []
    ffaces = []
    topz = zc0 - 0.10 * d0
    ring_specs = []
    top_ring = []
    mid_ring = []
    bot_ring = []
    for i in range(fsegs):
        a = 2.0 * math.pi * i / fsegs
        x, y = math.cos(a), math.sin(a)
        rj = rng.uniform(0.95, 1.05)
        top_ring.append((fcx + x * 0.60 * R0 * rj, fcy + y * 0.60 * R0 * rj,
                         topz + rng.uniform(-0.05, 0.05)))
        rj = rng.uniform(0.93, 1.07)
        mid_ring.append((fcx + x * 0.70 * R0 * rj, fcy + y * 0.70 * R0 * rj,
                         topz - rng.uniform(0.35, 0.55)))
        if i % 2 == 0:
            hang = rng.uniform(0.55, 1.05)
        else:
            hang = rng.uniform(0.05, 0.30)
        rj = rng.uniform(0.9, 1.1)
        bot_ring.append((fcx + x * 0.76 * R0 * rj, fcy + y * 0.76 * R0 * rj,
                         topz - 0.45 - hang))
    for ring in (top_ring, mid_ring, bot_ring):
        base = len(fverts)
        fverts.extend(ring)
        ring_specs.append(base)
    for k in range(2):
        A = ring_specs[k]
        B = ring_specs[k + 1]
        for i in range(fsegs):
            j = (i + 1) % fsegs
            ffaces.append((A + i, A + j, B + j, B + i))
    _finish(P + 'frill', fverts, ffaces, M('moss_frill'))

    # ---------- dot-discs on the upper caps ----------
    ndots = 15 + int(rng.random() * 10.999)
    upper = cap_data[1:] if len(cap_data) > 1 else cap_data
    bm = bmesh.new()
    for _ in range(ndots):
        zc, R, H, ccx, ccy = upper[min(len(upper) - 1, int(rng.random() * len(upper)))]
        phi = rng.uniform(0.28, 1.25)
        a = rng.uniform(0.0, 2.0 * math.pi)
        r, dz = _cap_top(R, H, phi)
        # profile derivative -> outward surface normal in the (radial, z) plane
        drad = -1.03 * R * 0.88 * (math.cos(phi) ** -0.12) * math.sin(phi)
        dvert = H * 1.08 * (math.sin(phi) ** 0.08) * math.cos(phi)
        nr, nz2 = dvert, -drad
        n3 = Vector((nr * math.cos(a), nr * math.sin(a), nz2)).normalized()
        pos = Vector((ccx + r * math.cos(a), ccy + r * math.sin(a), zc + dz)) + n3 * 0.015
        s = R * rng.uniform(0.07, 0.12)
        quat = Vector((0.0, 0.0, 1.0)).rotation_difference(n3)
        mtx = (mathutils.Matrix.Translation(pos)
               @ quat.to_matrix().to_4x4()
               @ mathutils.Matrix.Diagonal((s, s, s * 0.38, 1.0)))
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=4, radius=1.0, matrix=mtx)
    dmesh = bpy.data.meshes.new(P + 'dots')
    bm.to_mesh(dmesh)
    bm.free()
    dobj = bpy.data.objects.new(P + 'dots', dmesh)
    bpy.context.collection.objects.link(dobj)
    dobj.data.materials.append(M('flesh_dot'))
