import bpy, bmesh, math, random, mathutils
from mathutils import Vector, noise

_GD = r"C:\Users\chris\AppData\Local\Temp\claude\C--Users-chris-OneDrive-Documents-Moebius-linework2026\7150ab6a-8f5d-4283-98fc-5fbf8bd96b16\scratchpad\garden"
_OUT = r"C:\Users\chris\OneDrive\Documents\Moebius\linework2026\Models\garden"


def _clear_tmp():
    old = bpy.data.scenes.get("GEN_TMP")
    if old:
        for o in list(old.objects):
            d = o.data
            bpy.data.objects.remove(o)
            if d and getattr(d, "users", 1) == 0:
                bpy.data.meshes.remove(d)
        bpy.data.scenes.remove(old)


def _build_one(asset, seed):
    prev = bpy.context.window.scene.name
    _clear_tmp()
    scn = bpy.data.scenes.new("GEN_TMP")
    bpy.context.window.scene = scn

    def M(name):
        m = bpy.data.materials.get(name)
        return m if m else bpy.data.materials.new(name)

    ns = {"bpy": bpy, "bmesh": bmesh, "math": math, "random": random,
          "mathutils": mathutils, "Vector": Vector, "noise": noise}
    src = open(_GD + "\\" + asset + ".py").read()
    exec(compile(src, asset, "exec"), ns)
    ns["build"](random.Random(seed), M)

    objs = [o for o in scn.objects if o.type == 'MESH']
    for o in scn.objects:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.wm.obj_export(
        filepath=_OUT + "\\" + asset + ".obj",
        export_selected_objects=True,
        export_triangulated_mesh=True,
        export_materials=True,
        forward_axis='NEGATIVE_Z', up_axis='Y')
    tris = sum(max(0, len(p.vertices) - 2) for o in objs for p in o.data.polygons)

    bpy.context.window.scene = bpy.data.scenes[prev]
    _clear_tmp()
    return len(objs), tris
