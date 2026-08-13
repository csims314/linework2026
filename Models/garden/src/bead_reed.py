def _make_obj(name, bm, mat):
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


def _add_bead(bm, rng, pos, rad, squash, ox, oy):
    ret = bmesh.ops.create_uvsphere(
        bm, u_segments=12, v_segments=6, radius=rad,
        matrix=mathutils.Matrix.Translation(pos))
    for v in ret['verts']:
        d = v.co - pos
        n = noise.noise(v.co * 2.3 + Vector((ox, oy, 4.2)))
        v.co = pos + d * (1.0 + 0.05 * n)
        v.co.z = pos.z + (v.co.z - pos.z) * squash
    return ret['verts']


def build(rng, M):
    H = rng.uniform(4.1, 4.6)
    az = rng.uniform(0.0, 2.0 * math.pi)
    lean = rng.uniform(0.35, 0.7)
    lx, ly = math.cos(az) * lean, math.sin(az) * lean
    ox = rng.uniform(0.0, 50.0)
    oy = rng.uniform(50.0, 100.0)
    bow = rng.uniform(1.5, 1.9)

    def center(t):
        c = t ** bow
        nx = noise.noise(Vector((t * 1.7 + ox, 0.0, 7.7)))
        ny = noise.noise(Vector((0.0, t * 1.7 + oy, 3.3)))
        x = lx * c + 0.10 * nx * t
        y = ly * c + 0.10 * ny * t
        return Vector((x, y, t * H))

    def tangent(t):
        dt = 0.01
        a = max(0.0, t - dt)
        b = min(1.0, t + dt)
        return (center(b) - center(a)).normalized()

    # ---- stalk tube (one bmesh shared with the lower beads) ----
    bm = bmesh.new()
    NSEG = 8
    NRING = 16
    rings = []
    ref = Vector((1.0, 0.0, 0.0))
    for i in range(NRING + 1):
        t = i / NRING
        cpos = center(t)
        tn = tangent(t)
        # stable frame for a near-vertical curve: project global X
        # onto the plane perpendicular to the tangent (no twist/flip)
        bx = (ref - tn * tn.dot(ref)).normalized()
        by = tn.cross(bx).normalized()
        r = 0.075 * (1.0 - 0.3 * t)
        r *= 1.0 + 0.10 * noise.noise(Vector((t * 3.1 + ox, 5.5, 9.1)))
        ring = []
        for j in range(NSEG):
            a = 2.0 * math.pi * j / NSEG
            ring.append(bm.verts.new(
                cpos + bx * (r * math.cos(a)) + by * (r * math.sin(a))))
        rings.append(ring)
    for i in range(NRING):
        for j in range(NSEG):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % NSEG],
                          rings[i + 1][(j + 1) % NSEG], rings[i + 1][j]))
    for ring, cp in ((rings[0], center(0.0)), (rings[-1], center(1.0))):
        cv = bm.verts.new(cp)
        for j in range(NSEG):
            bm.faces.new((ring[j], ring[(j + 1) % NSEG], cv))

    # ---- lower beads threaded on the stalk ----
    n_lower = rng.randint(4, 5)
    t0, t1 = 0.28, 0.86
    for k in range(n_lower):
        base = t0 + (t1 - t0) * k / (n_lower - 1)
        t = min(0.92, max(0.20, base + rng.uniform(-0.03, 0.03)))
        rad = rng.uniform(0.18, 0.28)
        squash = rng.uniform(0.82, 0.95)
        _add_bead(bm, rng, center(t), rad, squash, ox, oy)

    # keep the planted base exactly on the ground
    for v in bm.verts:
        if v.co.z < 0.0:
            v.co.z = 0.0
    _make_obj('bead_reed_body', bm, M('cable_stalk'))

    # ---- glowing head bead ----
    bm2 = bmesh.new()
    hrad = rng.uniform(0.30, 0.36)
    hpos = center(1.0) + tangent(1.0) * (hrad * 0.35)
    _add_bead(bm2, rng, hpos, hrad, rng.uniform(0.9, 1.0), ox, oy)
    _make_obj('bead_reed_head', bm2, M('lamp_node'))
