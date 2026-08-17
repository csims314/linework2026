def _puff_shrub_spike_dir(rng):
    # Rejection-sample a unit direction, biased to not point below horizontal.
    while True:
        v = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-0.05, 1.0)))
        L = v.length
        if 0.15 < L <= 1.0:
            return v / L


def build(rng, M):
    bm = bmesh.new()

    # Base icosphere: subdiv 4 -> 1280 tris, dense enough for bristly displacement.
    r = rng.uniform(0.68, 0.76)
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=r)

    # Seeded noise-domain offsets so each build differs but stays deterministic.
    off = Vector((rng.uniform(-40.0, 40.0), rng.uniform(-40.0, 40.0), rng.uniform(-40.0, 40.0)))
    off2 = Vector((rng.uniform(-40.0, 40.0), rng.uniform(-40.0, 40.0), rng.uniform(-40.0, 40.0)))
    freq = rng.uniform(3.2, 4.4)
    squash = rng.uniform(0.70, 0.82)

    # High-frequency ridged (abs) noise pushed along normals: up to 40% of radius.
    for v in bm.verts:
        p = v.co.copy()
        d = p.normalized()
        n1 = noise.noise(p * freq + off)
        n2 = noise.noise(p * (freq * 2.3) + off2)
        disp = 0.40 * r * (0.70 * abs(n1) + 0.30 * abs(n2))
        v.co = p + d * disp
        v.co.z *= squash  # slight vertical squash (spikes squash with it -> cohesive tuft)

    # 5-8 longer single spikes: thin 5-segment cones, bases buried in the puff.
    n_spikes = rng.randint(5, 8)
    for _ in range(n_spikes):
        dirv = _puff_shrub_spike_dir(rng)
        length = rng.uniform(0.55, 0.95)
        base_r = rng.uniform(0.045, 0.085)
        pos = dirv * (r * 0.55)
        pos = Vector((pos.x, pos.y, pos.z * squash)) + dirv * (length * 0.5)
        quat = dirv.to_track_quat('Z', 'Y')
        mat = mathutils.Matrix.Translation(pos) @ quat.to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=5,
                              radius1=base_r, radius2=0.0, depth=length, matrix=mat)

    # Sit exactly on the ground: nothing below z=0.
    minz = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= minz

    me = bpy.data.meshes.new('puff_shrub')
    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new('puff_shrub_main', me)
    bpy.context.collection.objects.link(obj)

    me.materials.append(M('shadow_puff'))
    for poly in me.polygons:
        poly.material_index = 0
