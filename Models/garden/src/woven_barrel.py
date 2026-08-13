# woven_barrel — procedural asset builder for Blender 4.4
# Assumes in scope: bpy, bmesh, math, random, mathutils, Vector, noise


def _wb_link_mesh(name, verts, faces, mat, recalc=True, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    me.materials.append(mat)
    return ob


def _wb_rib(name, R, r, rz, zc, phase, wob, seed, maj, minr, cx, cy, mat):
    """Horizontal torus rib. R: major radius, r: minor (horizontal) radius,
    rz: vertical minor radius (squashed), zc: center height.
    Radial-only noise wobble so z extent stays exactly [zc-rz, zc+rz]."""
    verts = []
    faces = []
    for j in range(maj):
        th = 2.0 * math.pi * j / maj + phase
        c = math.cos(th)
        s = math.sin(th)
        nv = noise.noise(Vector((c * 1.7 + seed, s * 1.7 + seed * 0.37, zc * 0.9)))
        Rj = R * (1.0 + wob * nv)
        for k in range(minr):
            ph = 2.0 * math.pi * k / minr
            rad = Rj + r * math.cos(ph)
            verts.append((cx + rad * c, cy + rad * s, zc + rz * math.sin(ph)))
    for j in range(maj):
        j2 = (j + 1) % maj
        for k in range(minr):
            k2 = (k + 1) % minr
            faces.append((j * minr + k, j2 * minr + k, j2 * minr + k2, j * minr + k2))
    return _wb_link_mesh(name, verts, faces, mat)


def _wb_disc(name, R, z, segs, wob, seed, mat):
    """Flat triangle-fan disc at height z, facing +Z. Slight radius wobble."""
    verts = [(0.0, 0.0, z)]
    faces = []
    for j in range(segs):
        th = 2.0 * math.pi * j / segs
        c = math.cos(th)
        s = math.sin(th)
        nv = noise.noise(Vector((c * 1.5 + seed, s * 1.5 - seed, z)))
        rr = R * (1.0 + wob * nv)
        verts.append((rr * c, rr * s, z))
    for j in range(segs):
        faces.append((0, 1 + j, 1 + ((j + 1) % segs)))
    # fan is already CCW viewed from +Z -> normals up; skip recalc (open sheet)
    return _wb_link_mesh(name, verts, faces, mat, recalc=False)


def build(rng, M):
    lin = M('linen_weave')
    met = M('metal_hoop')

    n = rng.randint(6, 8)          # number of rib rings
    maj = 24 if n <= 7 else 20     # major segments (silhouette smoothness)
    minr = 10                      # minor segments per rib
    squash = 0.8                   # vertical squash of rib cross-section
    H = rng.uniform(2.8, 3.2)      # target overall height
    Rmax = rng.uniform(1.12, 1.24) # widest major radius (belly)

    # --- minor radii: alternate fat / thin, metal hoops slightly slimmer ---
    rbase = H / (2.0 * squash * n)
    metal = [((i % 3) == 1) for i in range(n)]
    rs = []
    for i in range(n):
        f = 1.16 if (i % 2) == 0 else 0.86
        f *= rng.uniform(0.96, 1.04)
        if metal[i]:
            f *= 0.90
        rs.append(rbase * f)

    # --- stack ribs (small overlaps so no gaps), then rescale to height H ---
    def stack(radii):
        zs = []
        z = radii[0] * squash          # bottom rib rests exactly on z=0
        zs.append(z)
        for i in range(1, len(radii)):
            hz0 = radii[i - 1] * squash
            hz1 = radii[i] * squash
            ov = 0.22 * min(hz0, hz1)
            z = z + hz0 + hz1 - ov
            zs.append(z)
        return zs

    zs = stack(rs)
    top = zs[-1] + rs[-1] * squash
    scale = H / top
    rs = [r * scale for r in rs]
    zs = [z * scale for z in zs]
    top = H

    # keep overall width ~3: belly radius + fattest rib + hoop bump <= ~1.5
    Rmax = min(Rmax, 1.50 - max(rs) - 0.03)

    # --- build ribs with a gentle barrel bulge profile ---
    seed = rng.uniform(0.0, 50.0)
    for i in range(n):
        t = zs[i] / top
        R = Rmax * (0.80 + 0.20 * math.sin(math.pi * t))
        R *= rng.uniform(0.985, 1.015)
        if metal[i]:
            R += 0.02  # hoops sit slightly proud of the weave
        mat = met if metal[i] else lin
        _wb_rib(
            'woven_barrel_rib_%02d' % i,
            R, rs[i], rs[i] * squash, zs[i],
            rng.uniform(0.0, 2.0 * math.pi),
            0.028, seed + i * 3.1,
            maj, minr,
            rng.uniform(-0.025, 0.025), rng.uniform(-0.025, 0.025),
            mat,
        )

    # --- recessed flat lid: disc buried into the inner wall of the top rib ---
    r_top = rs[-1]
    hz_top = r_top * squash
    t_top = zs[-1] / top
    R_top = Rmax * (0.80 + 0.20 * math.sin(math.pi * t_top))
    lid_z = zs[-1] + 0.12 * hz_top          # well below rim top (recess ~0.9*hz)
    lid_R = R_top - 0.35 * r_top            # edge buried inside torus body
    _wb_disc('woven_barrel_lid', lid_R, lid_z, maj, 0.012, seed + 71.3, lin)

    # --- floor disc closing the bottom hole ---
    r_bot = rs[0]
    t_bot = zs[0] / top
    R_bot = Rmax * (0.80 + 0.20 * math.sin(math.pi * t_bot))
    bot_z = zs[0] + 0.25 * (r_bot * squash)
    _wb_disc('woven_barrel_base', R_bot - 0.35 * r_bot, bot_z, maj, 0.012,
             seed - 33.7, lin)
