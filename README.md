# linework2026

Real-time Moebius / Geof Darrow–style ink linework in the browser. One HTML file, no build step.

![linework2026 default render](screenshot.png)

## Run it

Open `index.html` in any browser (it pulls Three.js from cdnjs, so it needs internet). Every parameter is a live slider.

Two camera modes, toggled with **F** or the `fly camera` checkbox:

- **orbit** (default) — drag to orbit, shift-drag to pan, wheel to zoom
- **fly** — `WASD` to move, `Q`/`E` down/up, hold `Shift` for 4×, drag to look, wheel to dolly

Switching modes never moves the view: entering flight adopts the orbit camera's exact position and heading, and leaving it drops the orbit target straight ahead at the current radius — verified bit-identical in both directions. Flight speed scales with the scene's bounding sphere so it feels the same in a 16-unit model as in the 170-unit yard, with a `fly speed` slider on top.

## How it works

### Face-ID edge detection — the whole detector

Instead of the usual depth + normal edge detection, every face in the scene is assigned a **random vertex color** ("face ID"). The scene is rendered once with those colors into an offscreen buffer, and a fullscreen shader draws ink wherever neighboring pixels have different colors. Because every face boundary, silhouette, and object-vs-object overlap produces a color step, this single test catches everything the classic depth/normal channels catch — plus all the interior paneling they miss. Depth and normal edge detection were removed entirely; a depth texture is kept only as *data* (distance falloff and sky masking), never as an edge source.

Faces are colored per quad (consecutive triangle pairs share a color) so quads read as single faces instead of showing their diagonals. Color variation is hierarchical — structural hulls get strong random colors, fine panels weak ones — which turns the detection threshold slider into a free level-of-detail dial: raise it and fine paneling melts away, leaving bold structural lines.

### Region grouping — controlling which faces get lines

One color per face means one line per face, which makes any smooth surface a wireframe: a 32-segment sphere is 768 quads and therefore 768 cells of ink. Borrowing the idea behind Blender's IDMapper add-on, adjacent faces are instead flood-filled into **regions** that share a single color. No color step inside a region means no ink inside it, so a smooth sphere collapses to one region and draws only its silhouette while a cube still keeps its six faces.

Two neighbors join when their area-weighted face normals agree to within the **similarity** threshold — 1.0 merges only coplanar faces, lower values tolerate more curvature — and when nothing explicit separates them: an `o`, `g`, or `usemtl` change in a loaded OBJ is always a hard boundary, so parts that merely touch never fuse. The slider is a curvature-based level-of-detail dial that complements the threshold one: threshold drops lines by *contrast*, similarity drops them by *flatness*. At the default 0.5 — 60° of tolerated curvature — the machine yard sheds 50% of its lines (178k → 89k edges), and the LOD garden's high-tessellation sphere, cylinder and torus knot go fully smooth. The slider runs 0.1 (84°, almost everything merges) to 1.0 (coplanar only, 14% shed), so it spans from bold structure to full faceting. Region boundaries drive vector mode too, so both renderers agree.

**A note on assembled models.** Region grouping spans a surface by walking shared edges, so it fails on models built by shoving sealed primitives together. Measured on one such model: 85,828 faces with **zero open edges** — every pipe run is a chain of separate closed tubes, so no region can cross a joint and every joint inks a ring. Two renderer-side workarounds were built, measured and removed: colouring regions by the direction they face (fixed the joints, but surfaces in one object facing the same way lose their mutual boundary — cost the LOD garden 11% of its ink), and screen-space seam suppression (also fixed them, but erased shallow-relief greeble past a narrow threshold and cost `speeder.obj` 22%). Neither earned its keep. **The fix belongs in the model**: a boolean union that fuses the overlapping solids into one continuous closed surface, after which regions span a whole pipe run naturally and it behaves exactly like the yard's cables. Note that merge-by-distance will not do it — that needs open edges, and there are none.

`show face colors` draws the ID buffer itself instead of inking it — what the detector actually sees. It makes the whole system legible at a glance: a flat block of colour is one region, so a smooth sphere reading as a single colour is exactly why it draws only a silhouette, while a faceted one shows its facets. Speckle means surfaces fighting, and buried geometry shows up as parts poking through where they shouldn't. It overrides vector mode rather than silently doing nothing.

Region colors are chosen with neighbor awareness — each is rolled a few times and the roll landing furthest from already-placed neighbors wins — because two near-identical colors across a boundary are an edge the detector would miss. Face colors draw from their own RNG stream, so changing any color option never reshuffles the procedural layout.

### Feature LOD — dropping lines by apparent size

Region grouping is baked and view-independent: it can decide a sphere is smooth, but it can never know the sphere is eight pixels tall. So every shape also gets a characteristic **world size** at build time, and the shaders divide it by distance each frame to get the shape's apparent size as a **fraction of screen height**:

```
frac = worldSize / (dist · 2·tan(fov/2))      →      smoothstep(min, min·2, frac)
```

Screen *fraction* rather than pixels, deliberately: the renderer supersamples, so a pixel threshold would make the interactive 1× frame and the refined 2× frame disagree and detail would visibly shift when progressive refinement lands. Measured, the two agree to 0.2 percentage points of total ink. The fade spans one octave so detail dissolves as you pull back instead of popping, and each edge is gated by the **smaller** of the two shapes it separates, so a shrinking detail disappears entirely rather than leaving an outline around nothing.

There is no principled way to pick the size metric — it depends on how thin shapes like pipes and masts should read — so all of them are baked and switch live from a dropdown, with no rebuild. **Size metric**: `area` (√surface area), `diagonal` (bounding-box diagonal, so long thin strips persist), or `thin` (the middle bbox extent — the smallest is 0 for any flat patch, which would make every panel read as a sliver). **Size of**: `region`, or `object` — one whole `put()` call, which keeps a faceted cylinder's facet lines alive as long as the cylinder is. On the machine yard at the default 0.4%, `region/area` sheds 12% of the ink at normal zoom and 29% pulled back; `region/thin` sheds 78%; `object/*` barely acts until you are far away. `keep outlines` exempts silhouettes — any edge with a large depth step across it — so distant objects never vanish completely.

Both renderers agree: the raster path reads the size from the alpha channel of the ID buffer, which was already RGBA, so it costs no extra pass or target. Vector mode carries a per-edge size instead. Sizes are log-encoded into single bytes, since they end up in an 8-bit channel anyway — all six variants together cost 6 bytes per vertex. Setting `min feature %` to 0 restores the previous image exactly.

### Depth precision, and why it matters more here

Z-fighting is worse in a face-ID renderer than in a shaded one. Two near-coincident surfaces carry *different random colors*, so wherever the depth buffer coin-flips between them the ID buffer fills with color steps, and the detector faithfully inks every one — a field of shimmering noise instead of a barely-visible shading seam. Badly built models hit this constantly.

Depth resolution goes as `z²(far−near) / (2·far·near)`, so the near plane dominates. The camera's planes are therefore derived each frame from the orbit distance and the scene's bounding sphere — `near = orbit.radius × nearFactor`, `far` the exact far side of the bounding sphere — rather than being parked at a fixed 0.1/300 that the camera can never approach. Measured on two coplanar quads at controlled separations, the largest gap that still fights drops from **3×10⁻⁴ to 1×10⁻⁵ world units, about 30×**. The `near plane ×` slider trades further precision against clipping close geometry.

Below the fighting band the artifact disappears again rather than worsening: once a separation is far under the depth resolution, both surfaces round to the same value and the comparison becomes deterministic, so one simply wins. Shimmer is the signature of separations *comparable to* the buffer's resolution, which is why it tracks camera movement — and why raising the near plane fixes it.

`linDepth()` in the ink shader reconstructs world distance from these planes, so they are pushed to the shader every frame; one-sided lines, distance falloff, sky masking and feature LOD all depend on it. Verified stable: a 50× change in the near plane moves total ink by 0.012 percentage points.

### Culling buried faces in assembled models

Models built by stacking primitives — a bust made of 544 boxes and cylinders — hide a surprising amount of geometry inside itself. In one such model **52.9% of all faces sit sealed inside a neighbouring part**. A solid renderer never shows them, but this one draws edges from every face, so wherever a buried part pokes through it contributes ink; densely packed areas like a mouth or a grille turn into scribble.

`cull buried faces` drops them at parse time: a face whose centroid lies strictly inside another part's box is discarded. A part counts as a solid box only when it genuinely is one — at most 12 faces over at most 8 *distinct corner positions*, checked by position rather than index, since exporters routinely split a box's 8 corners into 24 indices for UVs. That restriction keeps concave and hollow parts from swallowing their neighbours. On the bust it removes 52% of triangles and 41% of extracted edges, and cuts the ink in the mouth region by a quarter; on well-built models it is a no-op, verified against the yard, garden, primitives and `speeder.obj`, all byte-identical with it on.

It is off by default: it discards geometry on a heuristic, so it should be opted into per model.

### All detail is geometry

There are no ink textures or drawn details. A procedural greeble system builds everything the lines come from: recursive panel subdivision on every block face, rivets, vent slats, portholes with bolt rings, pipes with flanges and torus elbows, ladders, railings, catenary cables, plated flooring with manholes and grates, antenna masts. All of it is baked into **one merged BufferGeometry — a single draw call** (~89k triangles / ~89k extracted edges at max density and default settings).

### Render pipeline (raster mode)

1. **ID pass** — scene rendered as face colors, with a depth texture attached
2. **Normal pass** — only when hatching is enabled
3. **Ink pass** — fullscreen shader: face-ID edge test (optionally one-sided, drawing only on the nearer surface for half-width lines; optionally coverage AA, averaging the test at 4 sub-pixel offsets), hand-drawn wobble via noise-perturbed sampling UVs, distance-based line thinning that fades distant ink entirely past falloff 1.0, optional screen-space cross-hatching from N·L, paper grain
4. **Blit** — optional FXAA, and filtered downsampling when supersampling is on

Anti-aliasing options stack: one-sided lines, coverage AA, MSAA on the ID buffer, FXAA, and 1–2× supersampling with **progressive refinement** (interactive frames render at 1×; a full supersampled frame snaps in ~250ms after you stop moving). A dirty-flag loop skips rendering entirely when nothing changes.

### Vector line mode

A second, fully separate renderer: at build time every quad boundary is extracted as real line geometry (the duplicated diagonal vertices of each triangle pair identify which edge to drop), then the scene renders as a paper-colored occluder (polygon offset) with the edge lines drawn on top — classic hidden-line rendering, perfectly crisp at any zoom. The lines get their hand-drawn character from a custom shader: world-space noise wobble in the vertex stage (stable while orbiting), per-edge seeds so duplicated shared edges read as natural double-strokes, randomized endpoint overshoot, per-stroke ink variation, and distance-based opacity fade.

### Preview scenes

Four scenes to flip between: **yard** (the procedural greeble city), **garden** (the same solids at three tessellation levels — a direct look at how geometric density becomes line density), **prims** (a minimal debugging scene), and **model**, which renders `speeder.obj` — a real, hand-editable quads-only OBJ file (regenerate it with `make_speeder.py`, or sculpt it in any editor). Drop any `.obj` onto the window, or use the load button, to run your own model through the ink pipeline. Better still, keep models organized in a `Models/` folder — the **models folder…** button turns every subdirectory into its own scene showcasing the OBJs inside it (triangulated models are detected and colored per-triangle automatically). A folder holding more than one `.obj` shows them together in a grid for side-by-side comparison, and also lists each file individually beneath it so any one can be viewed alone.

## Controls

The panel keeps only `show face colors` and `supersample ×` visible; everything else sits behind an **advanced** expander, collapsed by default, so the panel is ~120px tall until you need it.

Under that: detection threshold, per-quad coloring, region grouping and its similarity threshold, feature LOD (minimum feature size, size metric, size unit, outline exemption), near-plane depth precision, the five AA toggles, line width and distance falloff, wobble amplitude/frequency, hatching (thresholds, spacing, angle), ink/paper colors and grain, vector-mode overshoot and ink variation, camera mode and flight speed, and greeble density (rebuilds the scene). `export png` saves the current frame.

The **budget panel** (bottom left) meters each resource against the point where it starts to hurt, rather than just reporting raw counts. Each bar runs empty to *heavy*, staying green through the *comfortable* range, going amber past it and red once the limit is passed:

| meter | comfortable | heavy | |
|---|---|---|---|
| fps | 120 | 60 | |
| shader | 40 | 100 | megapixels shaded × sub-tests per pixel |
| triangles | 500k | 1.5M | |
| edges | 500k | 2M | |
| line verts | 2M | 6M | vector mode only |
| regions | 100k | 300k | |
| gpu mem | 256 MB | 1 GB | attributes + every live render target |
| js heap | 512 MB | 1.5 GB | Chrome only |
| rebuild | 2 s | 5 s | split into weld / group / edge / rest |

**shader** is the one that explains frame time. The ink pass is fullscreen, so cost tracks pixels rather than triangles: supersampling scales the target area and coverage AA runs four sub-tests per pixel. Turning on 2× supersample takes it from 14.3 to 57.3 and drives gpu mem from 133 MB to 534 MB, since the render targets scale with the square of the supersample factor — which is what the 3.08× frame cost measured earlier actually is.

A footer shows geometry draw calls (1 normally, 2 with hatching or in vector mode), canvas megapixels, and the GPU actually in use — worth having because the renderer requests `powerPreference: 'high-performance'`, and on a dual-GPU laptop that line is the only confirmation the request was honoured.

The geometry meters are deliberately generous. All geometry rides in one draw call and the ink pass is fullscreen, so its cost tracks pixels and AA settings rather than triangle count — measured, going from 756 to 55,000 triangles barely moved frame time. **Rebuild is usually the binding constraint**, because vertex welding, region grouping and edge extraction are single-threaded JavaScript at roughly 5–15 µs per triangle. Expect to sit through multi-second rebuilds long before frame rate suffers. The fps meter reads live only while something is changing — the dirty-flag loop idles otherwise, so the last live figure is held and dimmed. Its bar tracks frame *time*, so it fills toward the limit like every other meter here: a full red bar means trouble even though a high fps number would not. The colour carries the meaning, not the fill.

## Tech

Three.js (r160) + WebGL2, custom GLSL throughout. No dependencies beyond Three.js, no build step, no frameworks. Orbit controls and the UI panel are hand-rolled.
