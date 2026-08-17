def build(rng, M):
    A = 32                       # angular columns across the non-notch span
    RINGS = [0.30, 0.55, 0.78, 0.92, 1.0]
    R = len(RINGS)

    Rmax  = rng.uniform(1.15, 1.35)
    t     = rng.uniform(0.13, 0.16)          # pad thickness
    notch = math.radians(rng.uniform(13.0, 19.0))  # half-angle of notch wedge
    dome  = rng.uniform(0.07, 0.13)
    up    = rng.uniform(0.10, 0.16)          # rim upturn
    phase = rng.uniform(0.0, 2.0 * math.pi)  # random facing of the notch
    seedz = rng.uniform(0.0, 100.0)
    wob_a = rng.uniform(0.06, 0.10)          # outline wobble strength
    freq  = rng.uniform(1.2, 2.2)
    tilt  = rng.uniform(0.012, 0.030)        # slight asymmetric lean
    tdir  = rng.uniform(0.0, 2.0 * math.pi)

    def rim_lift(f):
        s = max(0.0, (f - 0.82) / 0.18)
        return up * s * s

    def wob(theta):
        return noise.noise(Vector((math.cos(theta) * freq,
                                   math.sin(theta) * freq, seedz)))

    span = 2.0 * math.pi - 2.0 * notch
    thetas = []
    for i in range(A + 1):
        th = phase + notch + span * i / A
        if 0 < i < A:  # jitter interior columns, keep notch edges clean
            th += rng.uniform(-1.0, 1.0) * 0.25 * span / A
        thetas.append(th)

    bm = bmesh.new()
    top = [[None] * R for _ in range(A + 1)]
    bot = [[None] * R for _ in range(A + 1)]
    tc = bm.verts.new((0.0, 0.0, t + dome))
    bc = bm.verts.new((0.0, 0.0, 0.0))

    for i, th in enumerate(thetas):
        w = wob(th)
        for j, f in enumerate(RINGS):
            r = Rmax * f * (1.0 + wob_a * w * f)
            x = r * math.cos(th)
            y = r * math.sin(th)
            lift = rim_lift(f)
            zn = 0.012 * noise.noise(Vector((x * 1.7, y * 1.7, seedz + 7.0)))
            lean = tilt * f * math.cos(th - tdir)
            zb = max(0.0, 0.85 * lift + 0.6 * lean + zn)
            zt = t + dome * (1.0 - f ** 1.5) + lift + lean + zn
            zt = max(zb + 0.02, zt)
            top[i][j] = bm.verts.new((x, y, zt))
            bot[i][j] = bm.verts.new((x, y, zb))

    for i in range(A):
        bm.faces.new((tc, top[i][0], top[i + 1][0]))
        bm.faces.new((bc, bot[i + 1][0], bot[i][0]))
        for j in range(R - 1):
            bm.faces.new((top[i][j], top[i][j + 1],
                          top[i + 1][j + 1], top[i + 1][j]))
            bm.faces.new((bot[i][j], bot[i + 1][j],
                          bot[i + 1][j + 1], bot[i][j + 1]))
        bm.faces.new((top[i][R - 1], top[i + 1][R - 1],
                      bot[i + 1][R - 1], bot[i][R - 1]))

    for col in (0, A):  # the two cut walls of the notch
        bm.faces.new((tc, top[col][0], bot[col][0], bc))
        for j in range(R - 1):
            bm.faces.new((top[col][j], top[col][j + 1],
                          bot[col][j + 1], bot[col][j]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new("lily_pad_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(M('leaf_pad'))
    for p in mesh.polygons:
        p.use_smooth = True
        p.material_index = 0
    mesh.validate()
    obj = bpy.data.objects.new("lily_pad_pad", mesh)
    bpy.context.collection.objects.link(obj)
    return obj