def _blade_bm(rng, length, wmax, thick, curl, foldk, nL=14, nW=2):
    """Build one tapered blade as a closed, thick slab in local coords:
    length along +Z, width along X, thickness along Y. Returns a bmesh."""
    bm = bmesh.new()
    off = Vector((rng.uniform(0.0, 40.0),
                  rng.uniform(0.0, 40.0),
                  rng.uniform(0.0, 40.0)))
    bend = rng.uniform(-0.10, 0.10)  # slight in-plane sideways drift

    top = []
    bot = []
    for i in range(nL + 1):
        s = i / nL
        z = length * s
        # width profile: narrow base, belly ~45%, pointed tip
        wp = (0.28 + 0.72 * math.sin(math.pi * (s ** 0.85))) * (1.0 - 0.97 * (s ** 6))
        w = wmax * max(wp, 0.035)
        ycurl = curl * (s ** 2.8)          # out-of-plane tip curl
        rowt = []
        rowb = []
        for j in range(nW + 1):
            u = j / nW - 0.5
            x = u * w + bend * s * s
            yfold = foldk * w * (1.0 - abs(u) * 2.0)   # gentle center-rib fold
            nzy = noise.noise(Vector((x * 1.6, s * 2.3, 0.0)) + off)
            nzx = noise.noise(Vector((s * 1.9, 7.7, 0.0)) + off)
            xw = x + nzx * 0.02
            y = ycurl + yfold + nzy * 0.025
            rowt.append(bm.verts.new((xw, y + thick * 0.5, z)))
            rowb.append(bm.verts.new((xw, y - thick * 0.5, z)))
        top.append(rowt)
        bot.append(rowb)

    for i in range(nL):
        for j in range(nW):
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]))
            bm.faces.new((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]))
        bm.faces.new((top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0]))
        bm.faces.new((top[i][nW], bot[i][nW], bot[i + 1][nW], top[i + 1][nW]))
    for j in range(nW):
        bm.faces.new((top[0][j], bot[0][j], bot[0][j + 1], top[0][j + 1]))
        bm.faces.new((top[nL][j], top[nL][j + 1], bot[nL][j + 1], bot[nL][j]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _link_bm(bm, name, mat):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def _nub_bm(rng):
    """Squat wobbly plaster base, slightly flattened front-to-back (fan is in XZ)."""
    bm = bmesh.new()
    seg = 14
    rs = rng.uniform(0.92, 1.06)
    prof = [(0.0, 0.50), (0.13, 0.545), (0.28, 0.47), (0.42, 0.36), (0.55, 0.225)]
    noff = Vector((rng.uniform(0.0, 40.0),
                   rng.uniform(0.0, 40.0),
                   rng.uniform(0.0, 40.0)))
    rings = []
    for (z, r) in prof:
        ring = []
        for i in range(seg):
            t = 2.0 * math.pi * i / seg
            cx = math.cos(t)
            sy = math.sin(t)
            rr = r * rs * (1.0 + 0.06 * noise.noise(Vector((cx * 1.7, sy * 1.7, z * 2.1)) + noff))
            ring.append(bm.verts.new((cx * rr * 1.12, sy * rr * 0.78, z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        a = rings[k]
        b = rings[k + 1]
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    vb = bm.verts.new((0.0, 0.0, 0.0))
    for i in range(seg):
        bm.faces.new((vb, rings[0][(i + 1) % seg], rings[0][i]))
    vt = bm.verts.new((0.0, 0.0, prof[-1][0] + 0.10))
    for i in range(seg):
        bm.faces.new((vt, rings[-1][i], rings[-1][(i + 1) % seg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build(rng, M):
    n = rng.randint(7, 11)
    half = rng.uniform(0.82, 0.98)          # half-spread of the fan, radians
    Lmax = rng.uniform(3.15, 3.45)          # longest (center) blade length
    base_r = 0.12                            # blade root offset from fan axis
    base_z = 0.45                            # blade roots embedded in the nub

    for k in range(n):
        t = k / (n - 1)
        a = -half + 2.0 * half * t + rng.uniform(-0.025, 0.025)

        # center blades long, outer blades short; clamp horizontal reach
        L = Lmax * (0.55 + 0.45 * math.cos(a)) * rng.uniform(0.94, 1.03)
        sa = abs(math.sin(a))
        if sa > 1e-4:
            L = min(L, (1.62 - base_r) / sa)
        L = max(L, 1.2)

        wmax = min(0.15 + 0.115 * L, 0.55)
        thick = rng.uniform(0.062, 0.095)
        curl = rng.choice([-1.0, 1.0]) * rng.uniform(0.15, 0.38)
        foldk = rng.uniform(0.08, 0.16)

        bm = _blade_bm(rng, L, wmax, thick, curl, foldk)

        # stagger blades front/back so overlapping neighbors don't intersect
        yoff = ((k % 2) * 2 - 1) * (thick * 0.5 + 0.03 + rng.uniform(0.0, 0.02))
        pos = Vector((math.sin(a) * base_r, yoff, base_z + math.cos(a) * base_r))
        mat4 = mathutils.Matrix.Translation(pos) @ mathutils.Matrix.Rotation(a, 4, 'Y')
        bm.transform(mat4)

        # odd blades (1st, 3rd, ...) leaf_blade; even blades shadow_rib
        mat = M('leaf_blade') if (k % 2 == 0) else M('shadow_rib')
        _link_bm(bm, "leaf_fan_blade_%02d" % (k + 1), mat)

    _link_bm(_nub_bm(rng), "leaf_fan_nub", M('plaster_base'))
