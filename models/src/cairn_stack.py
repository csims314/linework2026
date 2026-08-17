def build(rng, M):
    plaster = M('plaster_stone')
    flesh = M('flesh_band')

    n = rng.randint(4, 6)
    accent = rng.randrange(1, n - 1)          # one MID stone gets the pink band

    # ---- first pass: plan the stack analytically ----
    rs, sqs, pens, rxs, rys = [], [], [], [], []
    for i in range(n):
        t = i / (n - 1)
        r = (1.6 * (1.0 - t) + 0.5 * t) * rng.uniform(0.93, 1.07)
        rs.append(r)
        sqs.append(rng.uniform(0.55, 0.65))
        pens.append(rng.uniform(0.62, 0.78))  # fraction of rz sunk into stone below
        rxs.append(r * rng.uniform(0.92, 1.10))
        rys.append(r * rng.uniform(0.92, 1.10))

    # predicted top: c0 = 0.85*rz0, then each stone adds (2 - pen)*rz
    raw = [rs[i] * sqs[i] for i in range(n)]
    predicted = 1.85 * raw[0]
    for i in range(1, n):
        predicted += (2.0 - pens[i]) * raw[i]
    target = rng.uniform(3.8, 4.2)
    zscale = target / predicted               # squash more/less so stack ~4 tall
    rzs = [raw[i] * zscale for i in range(n)]

    # ---- second pass: build each melted stone ----
    ox, oy = 0.0, 0.0
    prev_top = 0.0
    for i in range(n):
        r, rx, ry, rz = rs[i], rxs[i], rys[i], rzs[i]
        if i == 0:
            cz = rz * 0.85                    # sunk a touch into the ground
        else:
            cz = prev_top + rz - rz * pens[i] # deep sink -> fused, melted stack

        # lateral drift, clamped so the stack still reads balanced
        drift = r * 0.16
        ox = max(-0.55, min(0.55, ox + rng.uniform(-drift, drift)))
        oy = max(-0.55, min(0.55, oy + rng.uniform(-drift, drift)))

        off1 = Vector((rng.uniform(-80.0, 80.0),
                       rng.uniform(-80.0, 80.0),
                       rng.uniform(-80.0, 80.0)))
        off2 = Vector((rng.uniform(-80.0, 80.0),
                       rng.uniform(-80.0, 80.0),
                       rng.uniform(-80.0, 80.0)))
        melt = rng.uniform(0.10, 0.24)        # bottom-heavy droop per stone
        rot = rng.uniform(0.0, 2.0 * math.pi)
        ca, sa = math.cos(rot), math.sin(rot)

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)

        top_z = 0.0
        for v in bm.verts:
            zn = v.co.z                       # -1 .. 1 on the unit sphere
            bulge = 1.0 + melt * (1.0 - zn) * 0.5
            x = v.co.x * rx * bulge
            y = v.co.y * ry * bulge
            z = zn * rz
            xr = x * ca - y * sa
            yr = x * sa + y * ca
            p = Vector((xr, yr, z))
            d = p.normalized()
            f1 = noise.noise(p * (1.1 / r) + off1)
            f2 = noise.noise(p * (3.3 / r) + off2)
            p = p + d * (r * (0.11 * f1 + 0.035 * f2))
            p.x += ox
            p.y += oy
            p.z += cz
            if i == 0 and p.z < 0.0:
                p.z = 0.0                     # bottom stone sits flat on ground
            v.co = p
            if p.z > top_z:
                top_z = p.z
        prev_top = top_z

        name = 'cairn_stack_stone_%d' % i
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True

        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(flesh if i == accent else plaster)
