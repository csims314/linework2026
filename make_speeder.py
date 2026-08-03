#!/usr/bin/env python3
"""Generate speeder.obj — a quads-only, hand-editable desert speeder.

Structure notes (also written into the OBJ as comments):
- All faces are quads except the octagonal nose/tail cap fans (even
  triangle counts, so the renderer's per-quad pairing stays aligned).
- Sections are easy to tweak: each hull/canopy/pod entry below is one
  cross-section station; move numbers, re-run, or just hand-edit the
  v lines in the OBJ.
"""
import math

verts = []   # (x, y, z)
faces = []   # tuples of 1-based vertex indices (len 3 or 4)
parts = []   # (name, comment, start_face_idx)


def V(x, y, z):
    verts.append((x, y, z))
    return len(verts)


def part(name, comment):
    parts.append((name, comment, len(faces)))


def quad(a, b, c, d):
    faces.append((a, b, c, d))


def tri(a, b, c):
    faces.append((a, b, c))


def octagon_rect(x, w, yb, yt, c):
    """Rounded-rect (chamfered) 8-point section in the (z,y) plane at station x."""
    return [
        V(x, yb + c, -w), V(x, yb, -w + c), V(x, yb, w - c), V(x, yb + c, w),
        V(x, yt - c, w), V(x, yt, w - c), V(x, yt, -w + c), V(x, yt - c, -w),
    ]


def octagon_circle(x, cy, cz, r):
    """8-point circle section in the (y,z) plane at station x."""
    pts = []
    for i in range(8):
        a = i / 8 * 2 * math.pi + math.pi / 8
        pts.append(V(x, cy + r * math.sin(a), cz + r * math.cos(a)))
    return pts


def loft(sections):
    for s1, s2 in zip(sections, sections[1:]):
        n = len(s1)
        for i in range(n):
            quad(s1[i], s1[(i + 1) % n], s2[(i + 1) % n], s2[i])


def cap_fan(section, x, cy, cz=0.0):
    """Octagon cap as an 8-triangle fan (even count keeps quad pairing aligned)."""
    c = V(x, cy, cz)
    n = len(section)
    for i in range(n):
        tri(section[i], section[(i + 1) % n], c)


def slab(corners):
    """8 corners (bottom 4 then top 4, both CCW) -> 6 quads."""
    b0, b1, b2, b3, t0, t1, t2, t3 = corners
    quad(b0, b1, b2, b3)          # bottom
    quad(t3, t2, t1, t0)          # top
    quad(b0, t0, t1, b1)
    quad(b1, t1, t2, b2)
    quad(b2, t2, t3, b3)
    quad(b3, t3, t0, b0)


def box(x0, x1, y0, y1, z0, z1):
    slab([V(x0, y0, z0), V(x1, y0, z0), V(x1, y0, z1), V(x0, y0, z1),
          V(x0, y1, z0), V(x1, y1, z0), V(x1, y1, z1), V(x0, y1, z1)])


# ---------------- hull ----------------
part('hull', 'main fuselage - edit these stations to reshape the body')
hull_stations = [
    (0.0, 0.22, 1.05, 1.45, 0.07),
    (1.2, 0.90, 0.55, 1.95, 0.20),
    (3.0, 1.50, 0.35, 2.40, 0.30),
    (5.5, 1.60, 0.30, 2.50, 0.30),
    (7.5, 1.40, 0.45, 2.30, 0.28),
    (9.2, 1.00, 0.70, 2.05, 0.20),
    (10.0, 0.85, 0.90, 1.85, 0.15),
]
hull = [octagon_rect(*s) for s in hull_stations]
loft(hull)
cap_fan(list(reversed(hull[0])), 0.0, (1.05 + 1.45) / 2)   # nose
cap_fan(hull[-1], 10.0, (0.90 + 1.85) / 2)                 # tail

# ---------------- canopy ----------------
part('canopy', 'cockpit bubble - raise yt values for a taller canopy')
canopy_stations = [
    (2.2, 0.50, 2.32, 2.55, 0.10),
    (2.8, 0.78, 2.36, 3.25, 0.22),
    (4.1, 0.72, 2.36, 3.18, 0.22),
    (4.8, 0.42, 2.36, 2.62, 0.10),
]
canopy = [octagon_rect(*s) for s in canopy_stations]
loft(canopy)
cap_fan(list(reversed(canopy[0])), 2.2, 2.44)
cap_fan(canopy[-1], 4.8, 2.49)

# ---------------- engine pods ----------------
for side in (-1, 1):
    part(f'pod_{"L" if side < 0 else "R"}',
         'engine pod - change r values for fatter/slimmer engines')
    z = 2.15 * side
    stations = [(6.0, 0.30), (6.6, 0.85), (8.7, 0.92), (10.3, 0.60), (10.7, 0.32)]
    pod = [octagon_circle(x, 1.45, z, r) for x, r in stations]
    loft(pod)
    cap_fan(list(reversed(pod[0])), 6.0, 1.45, z)
    cap_fan(pod[-1], 10.7, 1.45, z)
    # pylon connecting pod to hull
    part(f'pylon_{"L" if side < 0 else "R"}', 'strut between hull and pod')
    zi, zo = 1.35 * side, 2.0 * side
    if side > 0:
        slab([V(7.0, 1.2, zi), V(8.4, 1.2, zi), V(8.4, 1.2, zo), V(7.0, 1.2, zo),
              V(7.0, 1.75, zi), V(8.4, 1.75, zi), V(8.4, 1.75, zo), V(7.0, 1.75, zo)])
    else:
        slab([V(7.0, 1.2, zo), V(8.4, 1.2, zo), V(8.4, 1.2, zi), V(7.0, 1.2, zi),
              V(7.0, 1.75, zo), V(8.4, 1.75, zo), V(8.4, 1.75, zi), V(7.0, 1.75, zi)])

# ---------------- tail fin ----------------
part('fin', 'vertical stabilizer - swept back; move top verts to change rake')
slab([V(8.5, 2.30, -0.07), V(10.0, 2.30, -0.07), V(10.0, 2.30, 0.07), V(8.5, 2.30, 0.07),
      V(9.6, 4.60, -0.05), V(10.5, 4.60, -0.05), V(10.5, 4.60, 0.05), V(9.6, 4.60, 0.05)])

# ---------------- skids ----------------
for side in (-1, 1):
    part(f'skid_{"L" if side < 0 else "R"}', 'landing skid + two struts')
    z0, z1 = (1.55 * side, 1.95 * side) if side > 0 else (1.95 * side, 1.55 * side)
    box(2.0, 8.2, 0.0, 0.28, z0, z1)
    for sx in (3.0, 7.0):
        zc = 1.75 * side
        box(sx - 0.12, sx + 0.12, 0.28, 0.9, zc - 0.1, zc + 0.1)

# ---------------- antenna mast ----------------
part('mast', 'small sensor mast on the nose deck')
box(1.35, 1.55, 1.95, 3.1, -0.1, 0.1)
box(1.25, 1.65, 3.1, 3.3, -0.2, 0.2)

# ---------------- write ----------------
qcount = sum(1 for f in faces if len(f) == 4)
tcount = sum(1 for f in faces if len(f) == 3)
lines = [
    '# speeder.obj - desert speeder for the moebius-lines renderer',
    '# Quads-only (plus even-count cap fans) so per-quad face coloring pairs cleanly.',
    '# Edit freely: v lines are positions, f lines are faces (1-based indices).',
    '# Re-generate from make_speeder.py, or sculpt by hand / in Blender.',
    f'# {len(verts)} vertices, {qcount} quads, {tcount} triangles',
    '',
]
part_bounds = [(n, c, s) for n, c, s in parts] + [('_end', '', len(faces))]
for x, y, z in verts:
    lines.append(f'v {x:.4f} {y:.4f} {z:.4f}')
lines.append('')
for (name, comment, start), (_, _, end) in zip(part_bounds, part_bounds[1:]):
    lines.append(f'# {comment}')
    lines.append(f'o {name}')
    for f in faces[start:end]:
        lines.append('f ' + ' '.join(str(i) for i in f))
    lines.append('')

open('/home/claude/moebius/speeder.obj', 'w').write('\n'.join(lines))
print(f'wrote speeder.obj: {len(verts)} verts, {qcount} quads, {tcount} tris')
