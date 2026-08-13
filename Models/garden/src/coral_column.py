def build(rng, M):
    nseg = 48
    nr = rng.randint(10, 14)
    H = rng.uniform(4.9, 5.4)
    dz = H / nr
    lobes = rng.randint(6, 8)
    twist = rng.uniform(0.5, 1.1) * (1.0 if rng.random() < 0.5 else -1.0)
    r_base = rng.uniform(1.0, 1.2)
    r_top = r_base * rng.uniform(0.45, 0.55)
    amp_p = rng.uniform(0.05, 0.07)
    amp_b = amp_p + rng.uniform(0.03, 0.05)
    bulge = rng.uniform(1.28, 1.38)
    s1 = Vector((rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0)))
    s2 = Vector((rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0)))
    ring_bj = [rng.uniform(0.97, 1.05) for _ in range(nr)]
    ring_pj = [rng.uniform(-0.06, 0.06) for _ in range(nr)]

    verts = []
    faces = []
    fmats = []

    def taper(z):
        t = min(max(z / H, 0.0), 1.0)
        return r_base + (r_top - r_base) * (t ** 1.15)

    def center(z):
        t = z / H
        sway = 0.20 * t
        cx = sway * noise.noise(s1 + Vector((0.0, 0.0, z * 0.5)))
        cy = sway * noise.noise(s1 + Vector((11.3, 5.9, z * 0.5)))
        return cx, cy

    def add_loop(z, rad, amp, pjit):
        i0 = len(verts)
        cx, cy = center(z)
        ph = lobes * twist * (z / H) + pjit
        for k in range(nseg):
            th = math.tau * k / nseg
            r = rad * (1.0 + amp * math.sin(lobes * th + ph))
            r *= 1.0 + 0.04 * noise.noise(
                s2 + Vector((math.cos(th) * 1.7, math.sin(th) * 1.7, z * 0.8)))
            verts.append((cx + r * math.cos(th), cy + r * math.sin(th), z))
        return i0

    def band(a, b, mi):
        for k in range(nseg):
            k2 = (k + 1) % nseg
            faces.append((a + k, a + k2, b + k2, b + k))
            fmats.append(mi)

    # --- column: stacked lobed rings, pinched between, bulged mid ---
    prev = add_loop(0.0, taper(0.0), amp_p, 0.0)
    base_loop = prev
    for i in range(nr):
        mi = 1 if (i + 1) % 4 == 0 else 0
        zm = (i + 0.5) * dz
        zt = (i + 1.0) * dz
        bl = add_loop(zm, taper(zm) * bulge * ring_bj[i], amp_b, ring_pj[i])
        tl = add_loop(zt, taper(zt), amp_p, 0.0)
        band(prev, bl, mi)
        band(bl, tl, mi)
        prev = tl

    # --- bottom cap (flat, on the ground) ---
    ci = len(verts)
    verts.append((0.0, 0.0, 0.0))
    for k in range(nseg):
        k2 = (k + 1) % nseg
        faces.append((ci, base_loop + k2, base_loop + k))
        fmats.append(0)

    # --- rounded top knob, bulging past the last pinch ---
    rk = taper(H) * rng.uniform(1.2, 1.35)
    zc = H + 0.08 + rk * math.sin(0.3)
    kprev = prev
    for phi in (-0.3, 0.12, 0.55, 1.0):
        kl = add_loop(zc + rk * math.sin(phi), rk * math.cos(phi), 0.05,
                      ring_pj[-1] * 0.5)
        band(kprev, kl, 2)
        kprev = kl
    cx, cy = center(H)
    ai = len(verts)
    verts.append((cx, cy, zc + rk * 1.02))
    for k in range(nseg):
        k2 = (k + 1) % nseg
        faces.append((ai, kprev + k, kprev + k2))
        fmats.append(2)

    # --- mesh / object / materials ---
    mesh = bpy.data.meshes.new("coral_column_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    obj = bpy.data.objects.new("coral_column_body", mesh)
    bpy.context.collection.objects.link(obj)
    for name in ("plaster_coral", "flesh_band", "flesh_cap"):
        obj.data.materials.append(M(name))
    for p, mi in zip(mesh.polygons, fmats):
        p.material_index = mi
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.update()
    return obj
