def build(rng, M):
    # ---------------- parameters ----------------
    N = rng.randint(16, 20)            # rings along arc
    S = rng.randint(14, 16)            # segments per ring
    L = rng.uniform(4.2, 4.6)          # half-span (footprint incl. flared caps ~10)
    H = rng.uniform(3.7, 4.3)          # apex height ~4
    asym = rng.uniform(0.08, 0.20) * (1.0 if rng.random() < 0.5 else -1.0)
    ybow = rng.uniform(-0.5, 0.5)      # sideways bow
    ytilt = rng.uniform(-0.6, 0.6)     # end-to-end lateral drift
    noff = Vector((rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0)))
    woff = Vector((rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0)))

    # ---------------- path helpers ----------------
    def fmap(t):
        # asymmetric monotonic remap, fixed at 0 and 1
        return t + asym * math.sin(math.pi * t)

    def path(t):
        f = min(1.0, max(0.0, fmap(t)))
        a = math.pi * (1.0 - f)                 # a: pi -> 0
        p = Vector((L * math.cos(a),
                    ybow * math.sin(math.pi * f) + ytilt * (f - 0.5),
                    H * math.sin(a)))
        # organic wobble on the path, faded to zero at the planted ends
        fade = math.sin(math.pi * f) ** 0.7 if 0.0 < f < 1.0 else 0.0
        w = Vector((noise.noise(noff + p * 0.45),
                    noise.noise(noff + p * 0.45 + Vector((7.7, 3.1, 9.2))),
                    noise.noise(noff + p * 0.45 + Vector((2.2, 8.8, 4.4)))))
        return p + w * 0.35 * fade

    def radius(t):
        base = 0.6 - 0.15 * math.sin(math.pi * t)   # 0.6 ends -> 0.45 apex
        e = min(t, 1.0 - t)
        flare = max(0.0, (0.09 - e) / 0.09)         # slight flare at planted ends
        return base * (1.0 + 0.28 * flare ** 1.6)

    def frame(t):
        eps = 1e-3
        T = path(min(1.0, t + eps)) - path(max(0.0, t - eps))
        if T.length < 1e-9:
            T = Vector((0.0, 0.0, 1.0))
        T.normalize()
        U = T.cross(Vector((0.0, 1.0, 0.0)))
        if U.length < 1e-5:
            U = Vector((1.0, 0.0, 0.0))
        U.normalize()
        V = T.cross(U)
        V.normalize()
        return U, V

    # ---------------- main tube loft ----------------
    bm = bmesh.new()
    rings = []
    ring_ts = []
    for i in range(N):
        t = i / (N - 1)
        c = path(t)
        if i == 0 or i == N - 1:
            c.z = 0.0
        U, V = frame(t)
        r0 = radius(t)
        ring = []
        for j in range(S):
            ang = 2.0 * math.pi * j / S
            d = U * math.cos(ang) + V * math.sin(ang)
            rr = r0 * (1.0 + 0.13 * noise.noise(woff + (c + d * r0) * 1.6))
            pos = c + d * rr
            if i == 0 or i == N - 1:
                pos = Vector((pos.x, pos.y, 0.0))   # cap ring exactly on ground
            else:
                pos = Vector((pos.x, pos.y, max(pos.z, 0.0)))
            ring.append(bm.verts.new(pos))
        rings.append(ring)
        ring_ts.append(t)

    loft_faces = []
    for i in range(N - 1):
        tm = 0.5 * (ring_ts[i] + ring_ts[i + 1])
        for j in range(S):
            f = bm.faces.new((rings[i][j], rings[i][(j + 1) % S],
                              rings[i + 1][(j + 1) % S], rings[i + 1][j]))
            loft_faces.append((f, tm))

    # ground-level end caps (fans)
    for i in (0, N - 1):
        cen = Vector((0.0, 0.0, 0.0))
        for v in rings[i]:
            cen += v.co
        cen /= S
        cv = bm.verts.new(Vector((cen.x, cen.y, 0.0)))
        for j in range(S):
            bm.faces.new((cv, rings[i][j], rings[i][(j + 1) % S]))

    # ---------------- stub branchlets ----------------
    nst = rng.randint(3, 5)
    stub_ts = []
    tries = 0
    while len(stub_ts) < nst and tries < 300:
        tries += 1
        tt = rng.uniform(0.15, 0.85)
        if all(abs(tt - o) > 0.09 for o in stub_ts):
            stub_ts.append(tt)

    SR = 8
    for tt in stub_ts:
        c = path(tt)
        U, V = frame(tt)
        rt = radius(tt)
        ang = rng.uniform(0.0, 2.0 * math.pi)
        d = U * math.cos(ang) + V * math.sin(ang)
        d = (d + Vector((0.0, 0.0, rng.uniform(0.45, 1.1)))).normalized()
        while d.z < 0.15:               # never let a stub aim into the ground
            d = (d + Vector((0.0, 0.0, 0.3))).normalized()
        curl = Vector((rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(0.1, 0.45)))
        Ls = rng.uniform(0.6, 1.1)
        Ut = d.cross(Vector((0.0, 0.0, 1.0)))
        if Ut.length < 1e-5:
            Ut = d.cross(Vector((0.0, 1.0, 0.0)))
        Ut.normalize()
        Vt = d.cross(Ut)
        Vt.normalize()
        bc = c + d * (rt * 0.5)                     # base buried in the tube
        srings = []
        NR = 4
        for k in range(NR):
            s = k / float(NR)                        # 0 .. 0.75; tip vertex finishes it
            ck = bc + d * (Ls * s) + curl * (s * s)
            rk = (0.38 * rt) * (1.0 - s) + 0.05
            rk *= 1.0 + 0.18 * noise.noise(woff + ck * 2.3)
            ring = []
            for j in range(SR):
                aj = 2.0 * math.pi * j / SR
                pos = ck + (Ut * math.cos(aj) + Vt * math.sin(aj)) * rk
                ring.append(bm.verts.new(Vector((pos.x, pos.y, max(pos.z, 0.0)))))
            srings.append(ring)
        for k in range(NR - 1):
            for j in range(SR):
                bm.faces.new((srings[k][j], srings[k][(j + 1) % SR],
                              srings[k + 1][(j + 1) % SR], srings[k + 1][j]))
        # base cap
        bcv = bm.verts.new(bc - d * 0.02)
        for j in range(SR):
            bm.faces.new((bcv, srings[0][j], srings[0][(j + 1) % SR]))
        # tip cap
        tip = bc + d * (Ls * 1.05) + curl
        tv = bm.verts.new(Vector((tip.x, tip.y, max(tip.z, 0.02))))
        for j in range(SR):
            bm.faces.new((tv, srings[NR - 1][j], srings[NR - 1][(j + 1) % SR]))

    # ---------------- normals + materials ----------------
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    for f in bm.faces:
        f.material_index = 0
    for f, tm in loft_faces:
        if 0.25 <= tm <= 0.75 and f.normal.z > 0.55:
            f.material_index = 1

    me = bpy.data.meshes.new('root_arc_mesh')
    bm.to_mesh(me)
    bm.free()
    me.update()
    obj = bpy.data.objects.new('root_arc_main', me)
    bpy.context.collection.objects.link(obj)
    me.materials.append(M('wood_root'))
    me.materials.append(M('moss_patch'))
