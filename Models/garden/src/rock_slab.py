def _tri_count(mesh):
    return sum(max(len(p.vertices) - 2, 0) for p in mesh.polygons)


def build(rng, M):
    prefix = 'rock_slab_'

    # ---- 1. Cube, subdivided, with large-scale noise displacement ----
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=5, use_grid_fill=True)

    off1 = Vector((rng.uniform(-30.0, 30.0),
                   rng.uniform(-30.0, 30.0),
                   rng.uniform(-30.0, 30.0)))
    off2 = Vector((rng.uniform(-30.0, 30.0),
                   rng.uniform(-30.0, 30.0),
                   rng.uniform(-30.0, 30.0)))

    rx = rng.uniform(1.40, 1.70)          # wider than tall
    ry = rng.uniform(1.20, 1.50)
    rz = rng.uniform(0.95, 1.15)
    round_t = rng.uniform(0.45, 0.62)     # cube -> sphere blend, keeps blockiness
    freq = rng.uniform(0.38, 0.55)        # low frequency = big broad swells
    amp = rng.uniform(0.26, 0.36)

    for v in bm.verts:
        s = v.co.normalized()
        p = v.co.lerp(s, round_t)
        p = Vector((p.x * rx, p.y * ry, p.z * rz))
        n1 = noise.noise(p * freq + off1)
        n2 = noise.noise(p * 1.6 + off2)
        v.co = p * (1.0 + amp * n1 + 0.10 * n2)

    mesh = bpy.data.meshes.new(prefix + 'boulder_mesh')
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(prefix + 'boulder', mesh)
    bpy.context.collection.objects.link(obj)

    # ---- 2. Aggressive collapse-decimate to BIG flat facets ----
    # (evaluated-depsgraph route: no operator/context dependence)
    target_tris = rng.randint(46, 68)
    cur_tris = max(_tri_count(mesh), 1)
    mod = obj.modifiers.new(name=prefix + 'dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = min(1.0, target_tris / float(cur_tris))

    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    facet_mesh = bpy.data.meshes.new_from_object(ev)
    facet_mesh.name = prefix + 'boulder_facets'
    obj.modifiers.clear()
    old = obj.data
    obj.data = facet_mesh
    bpy.data.meshes.remove(old)

    # ---- 3. Seat on the ground: sink slightly and flatten the base ----
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    zs = [v.co.z for v in bm.verts]
    minz, maxz = min(zs), max(zs)
    sink = (maxz - minz) * rng.uniform(0.10, 0.16)
    dz = -minz - sink
    for v in bm.verts:
        v.co.z += dz
        if v.co.z < 0.0:
            v.co.z = 0.0

    bmesh.ops.dissolve_degenerate(bm, dist=0.02, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()

    # ---- 4. Reassign 2-4 facets to stone_dark (material_index 1) ----
    for f in bm.faces:
        f.material_index = 0
    bm.faces.ensure_lookup_table()
    side = [f for f in bm.faces
            if f.normal.z < 0.85 and f.calc_center_median().z > 0.25]
    if not side:
        side = list(bm.faces)
    rng.shuffle(side)
    for f in side[:rng.randint(2, 4)]:
        f.material_index = 1
        # pull near-coplanar neighbours in so the dark patch is a whole facet
        for e in f.edges:
            for nf in e.link_faces:
                if nf is not f and f.normal.dot(nf.normal) > 0.93:
                    nf.material_index = 1

    bm.to_mesh(obj.data)
    bm.free()

    obj.data.materials.append(M('plaster_rock'))
    obj.data.materials.append(M('stone_dark'))
    for p in obj.data.polygons:
        p.use_smooth = False
