# Flat colour, in the reference style

## Context

The renderer draws ink on flat paper. The goal is colour matching the reference
image: **flat fills, no gradients**, a warm dusty palette, distant surfaces washed
toward the sky, and ink as a dark version of the local hue rather than black.
Constraints: **no textures**, **minimum shader overhead**, and — decisive for the
architecture — **a manual face-colour editor must be addable later**.

Rendering is nearly free: the compose step is two lines (`index.html:1947`) and
everything needed is already sampled there — `tID`, `dC`, the sky mask. The real
question was where hue comes from, and the editor requirement settles it.

## Why the display colour needs its own channel

Face-ID colours are all centred on 0.5 (`0.5 + (crng()-0.5)*variation` in
`faceIdColors()`); `variation` only sets spread, and it is deliberately
hierarchical because that is what makes the threshold slider an LOD dial. So the
ID buffer carries no per-object hue, and reusing it for artwork colour would both
tint the scene uniformly and destroy picking — a picked pixel would yield a
colour, not "which thing is this", ambiguously so where variation is low (ground
0.06 means hundreds of regions share a value).

So: **keep the ID buffer for detection, carry display colour separately.** That
keeps detection, display and identity independent, which is what an editor needs.

## Palette — measured from the reference

Sampled by nearest-neighbour downsample and bucketing, so these are true palette
colours rather than blends. A warm analogous set with one cool complement:

| role | hex | share | used for |
|---|---|---|---|
| sky / paper | `#FFD0B0` | 20% | background, ground, receding surfaces |
| cream | `#FFC6A6` | | light surfaces |
| clay | `#DAA291` | 16% | mid-tone bodies |
| rose | `#C5887D` | | mid-tone variant |
| terracotta | `#C66463` | 9% | structure, pipes, columns |
| brick | `#D35D5D` | | brighter structural accent |
| mauve | `#BD808B` | 13% | figures, soft forms |
| plum | `#AA7678` | | shadowed bodies |
| shadow | `#945C61` | | deep shadow, cables |
| steel | `#916678` | | hardware, railings, fittings |
| **blue** | `#517BB8` | **2%** | the single cool accent — sparing |
| teal | `#6FB7C4` | trace | glass, phosphor |
| amber | `#E8A33D` | trace | glow, brass, thread |

The blue is roughly complementary to the terracotta, and its scarcity is what
makes it read as focal. Defaults should respect that ratio — blue and amber stay
rare.

## Implementation

**1. Display colour as its own vertex attribute.** A normalized `Uint8` `aPaint`
(3 bytes/vertex), written per region in `faceIdColors()` alongside the existing
colour and size attributes, merged in `mergeBag()` the same way. No lookup, no
texture, and an editor can later rewrite one region's range and set `needsUpdate`
— instant, versus ~1 s for a full rebuild per click.

**2. Carry it to the compose step.** The ID material becomes MRT, writing ID+size
to attachment 0 and paint to attachment 1 in the same draw. One extra colour
write, **no extra geometry pass**.

*Verified against r160 in the browser, not assumed:*
- `WebGLMultipleRenderTargets(w, h, 2, opts)` is the correct API.
  `WebGLRenderTarget({count: 2})` silently yields 0 textures — that is a newer
  three feature and must not be used here.
- `depthTexture` and `samples: 4` both attach, so the existing ID+depth+MSAA
  setup carries over unchanged.
- MRT **requires GLSL3** (`layout(location=N) out vec4`), so `idMaterial`
  converts to `in`/`out` with named outputs. ~20 lines; the post shader is
  untouched and stays GLSL1.
- Normalized `Uint8` vertex attributes work, so `aPaint` costs 3 bytes/vertex.
- The GPU allows 8 attachments, leaving headroom if picking later wants its own.

**3. Compose** — replace the flat `paper` with the sampled paint, plus two
near-free effects that carry much of the reference's look:
- **aerial fade**: `mix(paint, skyColor, f(dC))` using existing `linDepth`. The
  reference leans on this hard — its background figures dissolve into the peach.
- **tinted ink**: `mix(inkColor, paint*0.35, amount)` so lines read as a dark
  version of the local hue.

**4. Default assignments.** Procedural scenes assign by object type at `put()`
time — ground and plates cream/peach, machine blocks clay/rose/plum per cluster,
panels a tint off their parent, pipes terracotta, tanks mauve, railings and
ladders and masts steel, cables shadow, the hero torus knot the blue accent.
Garden plinths clay with the shape rows cycling the palette; primitives one hue
each. These are permanent defaults — procedural scenes are never persisted.

Imported models key on **material name**, which is where this pays off — the
android model's `usemtl` names are semantic (`duct_metal`, `lamp_glow`,
`crt_phosphor`, `floor_wood_worn`, `jacket_cloth`, `window_glass`...). Keyword
match with a hash-of-name fallback so unknown materials still get a stable,
distinct colour rather than grey:

`wood`->clay · `glass`->blue · `glow`/`ember`->amber · `phosphor`->teal ·
`steel`/`iron`/`fitting`->steel · `cloth`/`velour`/`sofa`->mauve ·
`linen`/`plaster`->cream · `brass`/`thread`->amber · `duct`->terracotta ·
`shadow`->shadow · `sky`/`city`->sky (also the aerial-fade target) ·
`cardboard`->clay · `armor`/`plate`->plum

Respect the reference's ratios: blue and amber must stay rare, or the palette
stops reading as warm-with-an-accent. `.mtl` `Kd` values are currently parsed and
discarded — optionally seed from those instead of the keyword table, though the
android `.mtl`'s greens and greys do not match the reference palette, so the
keyword table is likely the better default.

## Persistence — imported models only

Procedural scenes are palette-driven and never persisted: they regenerate from
`seed`/`density`, so there is nothing to retain and no stability problem to solve.
Only loaded `.obj` models keep colour selections.

**Storage granularity is not selection granularity**, and separating them removes
the rebuild-stability problem entirely:

- **stored per source face** — an index into the file's face list, which nothing
  in the renderer can invalidate
- **selected per region** — a click paints every face the picked region contained

Change `similarity`, `per-quad colors` or `cull buried faces` afterwards and the
regions reshuffle, but not one saved colour moves, because none of them were keyed
on a region. `faceIdColors()` fills `aPaint` per face from the stored override
when there is one and the palette default otherwise, so both paths are the same
code.

**Where it goes:** the existing IndexedDB kv store (`idbSet`/`idbGet`, already
used for the model cache), keyed on the model filename. That needs no new
File System Access permission — the stored directory handle is currently
read-only. A compact record, material-level defaults plus per-face exceptions:

```json
{ "materials": { "duct_metal": "#C66463" },
  "faces": { "1234": "#517BB8", "1235": "#517BB8" } }
```

Plus export/import to a sidecar `<model>.colors.json` for portability and hand
editing.

## Deferred

- **Two-tone shading** — a flat darker step on shadow sides. Needs normals: the
  existing normal pass (~1.15x) or `dFdx/dFdy` on depth (free, faceted). Much of
  the reference is unshaded; add only if the flat version looks too even.
- **Vector mode** — separate path, fills with flat `fillMaterial`. Matching it
  means vertex colours on the fill mesh: cheap, but a second implementation.
- **The editor UI itself** — picking needs no permanent buffer: render an
  index-only frame on demand when the user clicks and read one pixel. Zero cost
  during normal rendering. **Caveat found while testing:** the 7th argument of
  `readRenderTargetPixels` is `activeCubeFaceIndex`, *not* an MRT attachment
  index, so it cannot read attachment 1. Picking must either use
  `gl.readBuffer(gl.COLOR_ATTACHMENT1)` with raw `readPixels`, or render to a
  dedicated single-attachment pick target.

## Verification

- Local `py -m http.server` + Chrome, as in previous sessions.
- **Colour off must be pixel-identical to today** — check first, it is the safety net.
- All four built-in scenes plus the imported model. The yard is the real test:
  its deep object hierarchy will show whether per-object hue reads as deliberate
  or as confetti.
- Confirm edge detection is untouched via `show face colors` — the ID buffer
  should look exactly as it does now.
- Measure frame cost with the `readPixels`-drained timing (median of batches,
  baseline re-measured between configs to cancel GPU clock drift) and confirm the
  shader meter barely moves.
- Sample the rendered frame and compare its dominant colours against the table
  above — the palette should land in the same neighbourhood, with blue and amber
  staying rare.
