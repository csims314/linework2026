# linework2026

Real-time Moebius / Geof Darrow–style ink linework in the browser. One HTML file, no build step.

![A loaded hoverbike .obj — emissive power cell, panel linework, cast shadows, character for scale](screenshot.png)

## Run it

Serve the folder and open it — e.g. `npx serve` or `python -m http.server`, then browse to `index.html`. A server is needed because the models are fetched from `models/`, and browsers block `fetch` on `file://`. Three.js comes from cdnjs, so it needs internet too. Every parameter is a live slider.

Opening the file directly still works, with one extra click: the **models folder…** button reads `models/` through the File System Access API instead, and the library is cached afterwards so later loads are instant.

Two camera modes, toggled with **F** or the `fly camera` checkbox:

- **orbit** (default) — drag to orbit, shift-drag to pan, wheel to zoom
- **fly** — `WASD` to move, `Q`/`E` down/up, hold `Shift` for 4×, drag to look, wheel to dolly

Switching modes never moves the view: entering flight adopts the orbit camera's exact position and heading, and leaving it drops the orbit target straight ahead at the current radius — verified bit-identical in both directions. Flight speed scales with the scene's bounding sphere so it feels the same around one model as across the whole showcase grid, with a `fly speed` slider on top.

## How it works

### Face-ID edge detection — the whole detector

Instead of the usual depth + normal edge detection, every face in the scene is assigned a **random vertex color** ("face ID"). The scene is rendered once with those colors into an offscreen buffer, and a fullscreen shader draws ink wherever neighboring pixels have different colors. Because every face boundary, silhouette, and object-vs-object overlap produces a color step, this single test catches everything the classic depth/normal channels catch — plus all the interior paneling they miss. Depth and normal edge detection were removed entirely; a depth texture is kept only as *data* (distance falloff and sky masking), never as an edge source.

Faces are colored per quad (consecutive triangle pairs share a color) so quads read as single faces instead of showing their diagonals. Color variation is hierarchical — structural hulls get strong random colors, fine panels weak ones — which turns the detection threshold slider into a free level-of-detail dial: raise it and fine paneling melts away, leaving bold structural lines.

The test itself is three lines of GLSL. A pixel is compared against its `+x` and `+y` neighbors in the nearest-filtered ID buffer, and the RGB distance is ramped through `smoothstep(threshold, threshold·1.8, diff)` — that ramp is the only place a "how different is different enough" decision is made. Each boundary is evaluated **from both sides' perspectives** and the results unioned, because the per-pixel gates that can suppress a line (feature LOD, soft-root contact, keep-outlines) belong to a *surface*, not to a pixel pair; evaluating from one side only would let a skyline die on the sky side's meaningless LOD data.

The ID buffer carries more than color. Its alpha holds the log-encoded feature size (see below), and the low bits of the color bytes are flags the detector and the shadow pass read: red bit 0 marks soft-root contact geometry, green bit 0 marks a surface eligible for self-overlap contours, blue bit 0 marks unlit surfaces (no terminator), blue bit 1 marks geometry that casts no shadow. Because they ride in the bottom bit of a byte, they cost nothing — a one-step color difference is far below any usable threshold.

One thing the ID buffer genuinely cannot see is a surface folding over itself: a cylinder's own overlap is one region against itself, same color both sides. That case — and only that case — is caught from the normal buffer, as a contour where the angle between neighboring normals exceeds the contour threshold.

### Region grouping — controlling which faces get lines

One color per face means one line per face, which makes any smooth surface a wireframe: a 32-segment sphere is 768 quads and therefore 768 cells of ink. Borrowing the idea behind Blender's IDMapper add-on, adjacent faces are instead flood-filled into **regions** that share a single color. No color step inside a region means no ink inside it, so a smooth sphere collapses to one region and draws only its silhouette while a cube still keeps its six faces.

Two neighbors join when their area-weighted face normals agree to within the **similarity** threshold — 1.0 merges only coplanar faces, lower values tolerate more curvature — and when nothing explicit separates them: an `o`, `g`, or `usemtl` change in a loaded OBJ is always a hard boundary, so parts that merely touch never fuse. The slider is a curvature-based level-of-detail dial that complements the threshold one: threshold drops lines by *contrast*, similarity drops them by *flatness*. At the default 0.5 — 60° of tolerated curvature — a dense model sheds around half its lines, and smoothly tessellated shapes like the coral column and lily pad go fully smooth. The slider runs 0.1 (84°, almost everything merges) to 1.0 (coplanar only, 14% shed), so it spans from bold structure to full faceting.

**A note on assembled models.** Region grouping spans a surface by walking shared edges, so it fails on models built by shoving sealed primitives together. Measured on one such model: 85,828 faces with **zero open edges** — every pipe run is a chain of separate closed tubes, so no region can cross a joint and every joint inks a ring. Two renderer-side workarounds were built, measured and removed: colouring regions by the direction they face (fixed the joints, but surfaces in one object facing the same way lose their mutual boundary — cost the garden models 11% of their ink), and screen-space seam suppression (also fixed them, but erased shallow surface relief past a narrow threshold and cost `speeder.obj` 22%). Neither earned its keep. **The fix belongs in the model**: a boolean union that fuses the overlapping solids into one continuous closed surface, after which regions span a whole pipe run naturally. Note that merge-by-distance will not do it — that needs open edges, and there are none.

`show face colors` draws the ID buffer itself instead of inking it — what the detector actually sees. It makes the whole system legible at a glance: a flat block of colour is one region, so a smooth sphere reading as a single colour is exactly why it draws only a silhouette, while a faceted one shows its facets. Speckle means surfaces fighting, and buried geometry shows up as parts poking through where they shouldn't.

Region colors are chosen with neighbor awareness — each is rolled a few times and the roll landing furthest from already-placed neighbors wins — because two near-identical colors across a boundary are an edge the detector would miss. Face colors draw from their own RNG stream, so changing any color option never reshuffles the procedural layout.

### Feature LOD — dropping lines by apparent size

Region grouping is baked and view-independent: it can decide a sphere is smooth, but it can never know the sphere is eight pixels tall. So every shape also gets a characteristic **world size** at build time, and the shaders divide it by distance each frame to get the shape's apparent size as a **fraction of screen height**:

```
frac = worldSize / (dist · 2·tan(fov/2))      →      smoothstep(min, min·2, frac)
```

Screen *fraction* rather than pixels, deliberately: the renderer supersamples, so a pixel threshold would make the interactive 1× frame and the refined 2× frame disagree and detail would visibly shift when progressive refinement lands. Measured, the two agree to 0.2 percentage points of total ink. The fade spans one octave so detail dissolves as you pull back instead of popping, and each edge is gated by the **smaller** of the two shapes it separates, so a shrinking detail disappears entirely rather than leaving an outline around nothing.

There is no principled way to pick the size metric — it depends on how thin shapes like pipes and masts should read — so all of them are baked and switch live from a dropdown, with no rebuild. **Size metric**: `area` (√surface area), `diagonal` (bounding-box diagonal, so long thin strips persist), or `thin` (the middle bbox extent — the smallest is 0 for any flat patch, which would make every panel read as a sliver). **Size of**: `region`, or `object` — one whole placed model, which keeps a faceted shape's facet lines alive as long as the shape itself is. On the showcase at the default 0.4%, `region/area` sheds around a tenth of the ink at normal zoom and far more pulled back; `region/thin` sheds most of it; `object/*` barely acts until you are far away. `keep outlines` exempts silhouettes — any edge with a large depth step across it — so distant objects never vanish completely.

The size rides in the alpha channel of the ID buffer, which was already RGBA, so it costs no extra pass or target. Sizes are log-encoded into single bytes, since they end up in an 8-bit channel anyway — all six variants together cost 6 bytes per vertex. Setting `min feature %` to 0 restores the previous image exactly.

### Depth precision, and why it matters more here

Z-fighting is worse in a face-ID renderer than in a shaded one. Two near-coincident surfaces carry *different random colors*, so wherever the depth buffer coin-flips between them the ID buffer fills with color steps, and the detector faithfully inks every one — a field of shimmering noise instead of a barely-visible shading seam. Badly built models hit this constantly.

Depth resolution goes as `z²(far−near) / (2·far·near)`, so the near plane dominates. The camera's planes are therefore derived each frame from the orbit distance and the scene's bounding sphere — `near = orbit.radius × nearFactor`, `far` the exact far side of the bounding sphere — rather than being parked at a fixed 0.1/300 that the camera can never approach. Measured on two coplanar quads at controlled separations, the largest gap that still fights drops from **3×10⁻⁴ to 1×10⁻⁵ world units, about 30×**. The `near plane ×` slider trades further precision against clipping close geometry.

Below the fighting band the artifact disappears again rather than worsening: once a separation is far under the depth resolution, both surfaces round to the same value and the comparison becomes deterministic, so one simply wins. Shimmer is the signature of separations *comparable to* the buffer's resolution, which is why it tracks camera movement — and why raising the near plane fixes it.

`linDepth()` in the ink shader reconstructs world distance from these planes, so they are pushed to the shader every frame; one-sided lines, distance falloff, sky masking and feature LOD all depend on it. Verified stable: a 50× change in the near plane moves total ink by 0.012 percentage points.

### Culling buried faces in assembled models

Models built by stacking primitives — a bust made of 544 boxes and cylinders — hide a surprising amount of geometry inside itself. In one such model **52.9% of all faces sit sealed inside a neighbouring part**. A solid renderer never shows them, but this one draws edges from every face, so wherever a buried part pokes through it contributes ink; densely packed areas like a mouth or a grille turn into scribble.

`cull buried faces` drops them at parse time: a face whose centroid lies strictly inside another part's box is discarded. A part counts as a solid box only when it genuinely is one — at most 12 faces over at most 8 *distinct corner positions*, checked by position rather than index, since exporters routinely split a box's 8 corners into 24 indices for UVs. That restriction keeps concave and hollow parts from swallowing their neighbours. On the bust it removes 52% of triangles and 41% of boundary edges, and cuts the ink in the mouth region by a quarter; on well-built models it is a no-op, verified against the garden pieces and `speeder.obj`, all byte-identical with it on.

It is off by default: it discards geometry on a heuristic, so it should be opted into per model.

### One line pass — skeleton, then nib

Ink used to be drawn wherever it was convenient: geometry edges in the compose shader, glass edges beside them, shadow outlines somewhere else again, each with its own width and antialiasing rule. They drifted. Now **every line in the image is drawn by one detector in one pass**, in two stages, and the compose shader draws no lines at all — it only reads the result. Line families cannot disagree because there is nowhere else to draw one.

**Stage A — the skeleton.** Find every boundary at 1-pixel precision and record only its *strength*, never a width. One shader collects all of them into `rtSkel`: face-ID boundaries and contours, shadow-region boundaries, ground-speckle rims, sun-disc and cloud rims in the sky, and glass front/back edges into their own channels (R = main ink, G/B = glass, A = speckle fill). Because the detector uses forward `+x`/`+y` differences, the mark lands on the left/bottom pixel of each boundary rather than centered on it — stage B fixes that, and the fix is where the antialiasing comes from.

**Stage B — the round nib.** Dilate the skeleton with a disc of per-pixel radius, which makes width exact in *every* direction for *every* family, with round joins and caps for free. Two details do the real work:

- Every nib tap is offset by **−0.5 texels** and reads `rtSkel` bilinearly. That recenters the skeleton onto the true boundary and spreads it across the texel pair, turning a 1px binary mark into the two-sided half-intensity 2px profile a 1px ideal line actually rasterizes as. Along diagonal stairs the resulting 0.25/0.75 corner pixels are exactly the gradient SMAA needs to reconstruct shallow runs. Coverage antialiasing is therefore not a separate supersampling of the detector — it falls out of the recentering, which is why the detector runs **once** per pixel instead of four times.
- The nib radius comes from the **neighborhood-minimum depth**, not the center pixel's: a line's width belongs to the nearer of the two surfaces it separates, so a silhouette against a distant background stays a foreground-weight line, and sky pixels land at the far end of the distance dial automatically.

At the default line width the nib radius is 0 and the whole loop collapses to that single recentering tap. Wider nibs are gated by a quarter-res **max-downsample** of the skeleton (`rtSkelLo`): most pixels have no boundary within reach and skip the 25- or 121-tap loop entirely.

The shadow mask gets the same treatment one stage earlier. Deriving "is this pixel in shadow" was the most expensive helper in the shader and was being re-derived up to seven times per pixel across the skeleton's probes and the compose branches, so it is now **materialized once** into `rtSMask` (R = the binary shadow region, G = the antialiased fill term) by its own fullscreen pass. The hand-drawn wobble is applied there, once, and every consumer reads at unwobbled coordinates — probing at the wobbled position would have applied it twice.

`regions` in the debug bar draws the complete "coloring book" the detector runs on — the ID buffer plus shadow regions, speckles and sky, every boundary in that view being a place a line gets drawn. It is compiled from the *same shader source* as the line pass under a different define, so it cannot drift from what the detector actually sees.

### Cast shadows — stencil shadow volumes

Shadow maps were tried first and removed. In a renderer whose whole subject is a crisp ink line, a filtered depth map's shadow edge is the one soft, resolution-bound, acne-prone thing in the frame — and worse, the shadow's *outline* is inked here, so map artifacts become drawn lines. Cast shadows are instead **per-triangle depth-fail stencil volumes** (Carmack's reverse), which are pixel-exact by construction: the shadow boundary lands on a pixel edge, at any zoom, with no bias, no resolution setting and no filtering.

**Per-triangle volumes, so kitbash geometry just works.** The textbook implementation extrudes the light-facing silhouette of a closed manifold — which this scene is not, and cannot be: models are stacks of interpenetrating primitives, one of them 85,828 faces with zero open edges. So every light-facing triangle emits *its own* closed volume: 6 vertices (3 on the surface, 3 flagged for extrusion) and 24 indices — near cap, reversed far cap, and an outward-wound side quad per edge. On a shared interior edge, the two triangles' side quads are coincident with opposite windings and **cancel exactly** in the stencil count, so the interior contributes nothing and the silhouette emerges from the arithmetic instead of being searched for. No watertight requirement, no adjacency table, no silhouette rebuild when the light moves. Positions are welded at 1e-5 first, so duplicated vertices from an exporter still produce cancelling quads.

**Extrusion happens in the vertex shader.** Each vertex carries the triangle's flat normal in an int8-normalized `vec4` with the extrude flag in `w` (~1° of accuracy is plenty for a facing test). Light-facing triangles keep their near cap on the surface and send flagged vertices to the ideal point `vec4(lightDir, 0)`; back-facing triangles extrude *all* their vertices and collapse to zero area, so a single draw handles both. Sending vertices to infinity requires the far plane to be there too, so the projection matrix is patched in place with the epsilon trick (`e[10] = ε−1`) before the volume passes and restored with `updateProjectionMatrix()` after — a `w = 0` vertex then rasterizes at depth ~1−ε instead of clipping.

**Self-shadow acne is solved by exact equality, not by bias.** The depth prepass and the volume's non-extruded branch use the *identical* transform expression, `projectionMatrix * (modelViewMatrix * position)`, and the weld preserves the first occurrence's exact floats — so a near cap rasterizes bit-identically to the surface it sits on. With a strict `LESS` depth test those fragments z-fail on *both* volume passes, and the increment and decrement cancel. There is no bias slider because there is nothing to bias.

The frame sequence, into a target with a packed depth24/stencil8 buffer:

1. **depth prepass** — the opaque scene, color writes off, same double-sided rasterization as the ID pass
2. **back faces**, increment stencil on z-fail
3. **front faces**, decrement stencil on z-fail — both with wrapping ops, because nested volumes routinely exceed a count of 1
4. **extract** — a fullscreen quad gated by `stencil != 0` writes 1 into the color attachment

`autoClear` is off across the four passes or the stencil would be wiped between them. The output is a binary screen-space mask (`.r`, 1 = shadowed) and it is the one and only cast-shadow source in the renderer. It is linear-filtered on purpose: the one-texel bilinear ramp at its edge is what downstream sampling re-hardens into an antialiased boundary.

Volume geometry is rebuilt lazily and only when stencil shadows actually render; actor volumes share the source mesh's `matrixWorld` **by reference**, so animated casters cost nothing per frame. The mask itself is view-dependent and so is regenerated every frame — which the dirty-flag loop makes cheap, since it only renders when something changed. Triangles flagged no-cast in the ID color emit no volume at all, and the translucent glass layer casts nothing.

**Downstream, the mask is just another region.** The shading pass reads it with a 4-tap rotated-grid average for a soft fill edge, and the line detector edge-detects it exactly like the face-ID buffer — which is why a cast shadow gets an ink outline in the same pen as everything else, tunable with the `shadow lines` slider. Optional silhouette smoothing (`shadow smooth`) runs the mask through blur → re-threshold → blur at half res: the edge becomes the 50% level-set of a smooth field, so features smaller than the radius melt away and corners round into painted lobes, and doing it twice approximates curvature flow. The kernel is depth-aware so the radius is a constant in *world* units rather than pixels, and the pass is fully deterministic — no noise anywhere on it.

### All detail is geometry

There are no ink textures and no drawn details: every line in the image comes from a real face boundary in a real model. Nothing is generated procedurally — all geometry is `.obj` files loaded from `models/`, and the only shape built in code is the ground sheet they stand on (plus a placeholder box figure for the player controller). However many models a scene places, they are baked into **one merged BufferGeometry — a single draw call**, so the whole 18-model showcase renders like one object.

### Render pipeline

1. **ID pass** — the opaque scene as face colors, into an MRT (IDs + a paint attachment) with a depth texture
2. **Glass passes** — the translucent layer twice: nearest surface, and nearest *back* face so interior edges can draw through it
3. **Shadow volumes** — depth prepass + two stencil passes + extract, producing the screen-space shadow mask (only when cast shadows are on)
4. **Normal pass** — view-space normals, when shading, contours or feature LOD need them
5. **Shadow melt** — optional silhouette smoothing of the mask, at half res
6. **Glow** — emissive pixels and the sun disc, blurred at quarter res
7. **Mask pass** — the shadow test materialized once into `rtSMask`, wobble applied here
8. **Line pass** — stage A skeleton → quarter-res max-downsample → stage B nib; all ink in the frame
9. **Compose** — reads the line buffer, adds shading, pigment, paper grain
10. **Blit** — optional FXAA/SMAA, and filtered downsampling when supersampling is on

Anti-aliasing stacks: coverage from the nib's recentering, post AA (FXAA or SMAA), and 1–2× supersampling with **progressive refinement** (interactive frames render at 1×; a full supersampled frame snaps in ~250ms after you stop moving). A dirty-flag loop skips rendering entirely when nothing changes.

### The model library

Everything the renderer draws lives in `models/`, listed in `models/manifest.json`:

```json
{ "file": "mushroom_tower.obj", "name": "mushroom tower", "organic": true }
```

`organic` picks the shade class (PN-quadratic shade normals plus the organic blur — true for plants, terrain and rocks, false for machinery), and an optional `scale` nudges one piece bigger or smaller than its neighbours. Drop a `.obj` in the folder, add a line, and it appears in every scene list.

**showcase** is the front page: one of every model, laid out in a grid on open ground. Each is normalized so its longest axis measures the same — the library runs from a palm-sized lily pad to a 16-unit speeder, and at true scale the small pieces would be specks. Every model also gets its own scene below the showcase, centred and alone, and the camera frames itself from what the model actually measures once placed, so a wide flat slab and a tall thin column both fill the frame.

Drop any `.obj` onto the window, or use **load obj…**, to run your own model through the ink pipeline without adding it to the library. **models folder…** points the whole library somewhere else — a manifest inside that folder is honoured if present, otherwise every `.obj` found is loaded and classified by filename. `speeder.obj` is hand-editable quads-only geometry you can regenerate with `make_speeder.py`, and doubles as the rideable craft in player mode.

## Controls

The panel keeps only `show face colors` and `supersample ×` visible; everything else sits behind an **advanced** expander, collapsed by default, so the panel is ~120px tall until you need it.

A **debug bar** blits any intermediate buffer straight to the screen instead of composing ink — `depth`, `regions` (the detector's coloring book), `skel` and `lines` (the two line-pass stages), `stencil` and `smask` (the raw shadow mask and the materialized one), `melt`, `glow`, `shade n`, `field`, `classes`, `ink`. Every view renders after all the pre-passes, so each is current.

Under that: detection threshold, per-quad coloring, region grouping and its similarity threshold, feature LOD (minimum feature size, size metric, size unit, outline exemption), near-plane depth precision, the AA toggles, line width and distance falloff, wobble amplitude/frequency, shading (style, thresholds, noise) and cast shadows, ink/paper colors and grain, and camera mode and flight speed. `recolor` rerolls the face-ID seed — it repaints the same models rather than moving them — and `export png` saves the current frame.

The **budget panel** (bottom left) meters each resource against the point where it starts to hurt, rather than just reporting raw counts. Each bar runs empty to *heavy*, staying green through the *comfortable* range, going amber past it and red once the limit is passed:

| meter | comfortable | heavy | |
|---|---|---|---|
| fps | 120 | 60 | |
| shader | 40 | 100 | megapixels shaded × sub-tests per pixel |
| triangles | 500k | 1.5M | |
| edges | 500k | 2M | |
| regions | 100k | 300k | |
| gpu mem | 256 MB | 1 GB | attributes + every live render target |
| js heap | 512 MB | 1.5 GB | Chrome only |
| rebuild | 2 s | 5 s | split into weld / group / edge / rest |

**shader** is the one that explains frame time. The ink pass is fullscreen, so cost tracks pixels rather than triangles: supersampling scales the target area and coverage AA runs four sub-tests per pixel. Turning on 2× supersample takes it from 14.3 to 57.3 and drives gpu mem from 133 MB to 534 MB, since the render targets scale with the square of the supersample factor — which is what the 3.08× frame cost measured earlier actually is.

A footer shows geometry draw calls (1 normally, 2 with shading on, plus the glass layers), canvas megapixels, and the GPU actually in use — worth having because the renderer requests `powerPreference: 'high-performance'`, and on a dual-GPU laptop that line is the only confirmation the request was honoured.

The geometry meters are deliberately generous. All geometry rides in one draw call and the ink pass is fullscreen, so its cost tracks pixels and AA settings rather than triangle count — measured, going from 756 to 55,000 triangles barely moved frame time. **Rebuild is usually the binding constraint**, because vertex welding, region grouping and edge counting are single-threaded JavaScript at roughly 5–15 µs per triangle. Expect to sit through multi-second rebuilds long before frame rate suffers. The fps meter reads live only while something is changing — the dirty-flag loop idles otherwise, so the last live figure is held and dimmed. Its bar tracks frame *time*, so it fills toward the limit like every other meter here: a full red bar means trouble even though a high fps number would not. The colour carries the meaning, not the fill.

## Tech

Three.js (r160) + WebGL2, custom GLSL throughout. No dependencies beyond Three.js, no build step, no frameworks. Orbit controls and the UI panel are hand-rolled.
