PFX = 'tube_cluster_'


def _new_obj(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    bpy.context.collection.objects.link(ob)
    return ob


def _bridge(bm, ra, rb):
    n = len(ra)
    for j in range(n):
        k = (j + 1) % n
        bm.faces.new((ra[j], ra[k], rb[k], rb[j]))


def build(rng, M):
    off = Vector((rng.uniform(-50.0, 50.0),
                  rng.uniform(-50.0, 50.0),
                  rng.uniform(-50.0, 50.0)))

    # ---- lumpy squashed-sphere base ----
    base_r = rng.uniform(0.95, 1.12)
    ay = base_r * rng.uniform(0.82, 1.0)
    zs = rng.uniform(0.30, 0.38)
    zc = rng.uniform(0.13, 0.19)

    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    for v in bm.verts:
        n = v.co.normalized()
        d = noise.noise(v.co * 1.9 + off)
        v.co += n * (d * 0.20)
    for v in bm.verts:
        v.co.x *= base_r
        v.co.y *= ay
        v.co.z = v.co.z * zs + zc
        if v.co.z < 0.0:
            v.co.z = 0.0
    bm.normal_update()
    _new_obj(PFX + 'base', bm, M('moss_base'))

    # ---- tube placement (rejection-sampled, non-overlapping) ----
    want = rng.randint(6, 12)
    placed = []
    tries = 0
    while len(placed) < want and tries < 400:
        tries += 1
        ang = rng.uniform(0.0, 2.0 * math.pi)
        rad = (rng.random() ** 0.6) * 0.72
        x = math.cos(ang) * rad * base_r
        y = math.sin(ang) * rad * ay
        r = rng.uniform(0.09, 0.23)
        if all((x - px) ** 2 + (y - py) ** 2 > (r + pr + 0.05) ** 2
               for px, py, pr in placed):
            placed.append((x, y, r))

    # ---- hollow tubes: outer wall up, rim, inner wall down, floor cap ----
    NSEG = 12
    bt = bmesh.new()
    for (x, y, r) in placed:
        h = rng.uniform(0.32, 1.0)
        d2 = (x / base_r) ** 2 + (y / ay) ** 2
        surfz = zc + zs * math.sqrt(max(0.0, 1.0 - min(1.0, d2)))
        zb = max(0.05, surfz - 0.18)
        tilt = rng.uniform(0.03, 0.40)
        taz = math.atan2(y, x) + rng.uniform(-1.3, 1.3)
        axis = Vector((math.sin(tilt) * math.cos(taz),
                       math.sin(tilt) * math.sin(taz),
                       math.cos(tilt)))
        u = axis.cross(Vector((0.0, 0.0, 1.0)))
        if u.length < 1e-5:
            u = Vector((1.0, 0.0, 0.0))
        u.normalize()
        w = axis.cross(u)
        base = Vector((x, y, zb))

        # lathe profile: (t along axis, radius) — up the outside,
        # over the lip, down the inside
        prof = [(0.0, r * rng.uniform(1.22, 1.4)),
                (h * 0.5, r * rng.uniform(0.9, 1.0)),
                (h, r * rng.uniform(1.02, 1.12)),
                (h * 0.97, r * 0.70),
                (h * rng.uniform(0.3, 0.5), r * 0.60)]
        rings = []
        for (t, rr) in prof:
            c = base + axis * t
            wob = 0.05 * t
            c = c + u * (wob * noise.noise(c * 2.3 + off)) \
                  + w * (wob * noise.noise(c * 2.3 - off))
            ring = []
            for j in range(NSEG):
                a = 2.0 * math.pi * j / NSEG
                dv = u * math.cos(a) + w * math.sin(a)
                rj = rr * (1.0 + 0.09 * noise.noise(c * 3.1 + dv * 1.7 + off))
                p = c + dv * rj
                if p.z < 0.01:
                    p.z = 0.01
                ring.append(bt.verts.new(p))
            rings.append(ring)
        for i in range(len(rings) - 1):
            _bridge(bt, rings[i], rings[i + 1])
        # inner floor cap
        cc = base + axis * (prof[-1][0] - 0.03)
        if cc.z < 0.01:
            cc = Vector((cc.x, cc.y, 0.01))
        vc = bt.verts.new(cc)
        last = rings[-1]
        for j in range(NSEG):
            k = (j + 1) % NSEG
            bt.faces.new((last[j], last[k], vc))
    bt.normal_update()
    _new_obj(PFX + 'tubes', bt, M('pipe_tube'))
