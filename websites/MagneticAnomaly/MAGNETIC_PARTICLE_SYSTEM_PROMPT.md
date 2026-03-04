# Magnetic Pole Particle System — Implementation Prompt

## Role

Act as a Senior WebGL / Three.js Engineer specializing in GPU particle systems and scientific visualization. You are adding a magnetic-field particle effect to an existing React Three Fiber scene. You must write **separate, self-contained component files** that plug into the existing `<SaturnScene>` without modifying the main animation/camera orchestration in `App.jsx`.

---

## Context: Existing Codebase

### Stack
- **React 19** + **Vite 7**
- **@react-three/fiber 9.5** + **@react-three/drei 10.7** + **three 0.183**
- **GSAP 3** with ScrollTrigger (controls camera via `globalCamera` export)
- **Tailwind CSS 3.4**

### Current 3D Scene (`src/App.jsx` → `SaturnScene` component)
The scene contains **4 celestial bodies**, each a `<Sphere>` mesh with texture maps:

| Body | Ref | Radius | Position | Texture |
|---|---|---|---|---|
| **Saturn** | `saturnRef` | 16 | `[-15, 0, -45]` (inside tilted group) | `saturn.jpg` |
| **Enceladus** (hero moon) | `enceladusRef` | 2.5 | `[-40, -5, 405]` | `ceres.jpg` (tinted `#ECECEC`) |
| **Ceres** | `ceresRef` | 3.5 | `[150, 20, -100]` | `ceres.jpg` (tinted `#DDDDDD`) |
| **Makemake** | `makemakeRef` | 5.5 | `[-150, -30, 50]` | `2k_makemake_fictional.jpg` |

Saturn has a tilted axis group: `rotation={[Math.PI / 12, 0, Math.PI / 12]}` and rings via `<SaturnRings>`.

Each body slowly self-rotates via `useFrame`. The camera is driven entirely by GSAP ScrollTrigger orbits in the root `App` component — **do not touch the camera system**.

### Available Textures (`public/textures/`)
- `saturn.jpg`, `ceres.jpg`, `2k_makemake_fictional.jpg`
- `2k_saturn_ring_alpha.png`, `2k_stars_milky_way.jpg`

### File Structure
```
src/
  App.jsx          ← Main scene + all HTML sections (DO NOT restructure)
  App.css
  index.css
  main.jsx
```

---

## What to Build: Magnetic Pole Particle Effects

### Scientific Reference

Earth and planetary bodies with magnetic fields emit charged particles along magnetic field lines. These particles:

1. **Erupt from one magnetic pole** (north or south) in a focused jet/fountain
2. **Arc outward** along dipole field lines — forming toroidal (donut-shaped) paths
3. **Converge back toward the opposite pole**, creating closed-loop trajectories
4. **Accumulate near the surface** in auroral bands around the poles
5. The overall shape is a **dipole magnetic field** — like iron filings around a bar magnet

Key visual characteristics from scientific visualizations:
- Field lines are **curved arcs** connecting pole to pole, not straight lines
- Particles near the poles move **fast and tightly bundled** (high field strength)
- Particles at the equatorial midpoint move **slower and spread wider** (weak field)
- The result is a semi-transparent **envelope/cocoon** of particle streams around the body
- Real aurora appears as glowing rings/ovals around the poles

### Abstract Artistic Interpretation

We want an **abstract, colorful** version of this — not a physics simulation. Think:
- Luminous particle clouds that **breathe and pulse** around each moon
- Streams that burst from poles, arc gracefully outward, and spiral back
- Soft, semi-transparent **nebula-like envelopes** that hug the surface
- Each body gets a **unique color palette** and **timing variation**

---

## Architecture Requirements

### CRITICAL: Separate Files, Independent Execution

Each particle system must be a **standalone React Three Fiber component** in its own file:

```
src/
  particles/
    MagneticParticles.jsx      ← Shared core: the reusable particle system component
    EnceladusParticles.jsx     ← Config + wrapper for Enceladus
    CeresParticles.jsx         ← Config + wrapper for Ceres
    MakemakeParticles.jsx      ← Config + wrapper for Makemake
    SaturnParticles.jsx        ← Config + wrapper for Saturn (special: larger, works with rings)
    index.js                   ← Barrel export
```

These components will be **imported into `SaturnScene`** in App.jsx with minimal edits — just adding `<EnceladusParticles />`, `<CeresParticles />`, etc. as siblings to the existing `<Sphere>` meshes.

### Integration Point (the ONLY edit to App.jsx)

Inside the `SaturnScene` component, add the particle components as children of the same parent groups as the spheres. Example:

```jsx
// Inside SaturnScene, after the Enceladus <Sphere>:
<EnceladusParticles position={[-40, -5, 405]} radius={2.5} />
```

**Do NOT:**
- Modify the camera system (`CameraRig`, `globalCamera`, GSAP ScrollTriggers)
- Modify existing mesh positions, textures, or rotations
- Add new GSAP animations
- Restructure the component hierarchy

---

## Particle System Specification

### Core Engine (`MagneticParticles.jsx`)

Use **instanced buffer geometry** or a **Points** system with a custom shader material for performance. Target: **500–2000 particles per body** (tunable via props).

#### Particle Lifecycle

Each particle follows a **dipole field line path**:

1. **Spawn** — Particle appears at one pole (north or south, chosen randomly or alternating)
2. **Erupt** — Fast outward velocity along the pole axis
3. **Arc** — Curve outward along a dipole field line. Parameterize as:
   ```
   // Dipole field line in spherical coords, parameterized by θ (0 = north pole, π = south pole):
   r(θ) = R_max * sin²(θ)
   
   // In Cartesian (for a pole-aligned body):
   x = r(θ) * sin(θ) * cos(φ)    // φ = azimuthal angle (random per particle)
   y = r(θ) * cos(θ)              // pole axis
   z = r(θ) * sin(θ) * sin(φ)
   ```
   Where `R_max` controls how far the field line extends (1.5× to 3× body radius).
4. **Converge** — Particle curves back toward the opposite pole
5. **Fade & Respawn** — Particle fades out near the destination pole, then respawns at a pole

#### Particle Attributes (per-particle, stored in buffer attributes)

| Attribute | Type | Purpose |
|---|---|---|
| `aPhase` | float | Current progress along the field line (0→1) |
| `aSpeed` | float | Individual speed multiplier (randomized 0.5–1.5) |
| `aPhi` | float | Azimuthal angle — which "longitude" the field line sits at |
| `aRmax` | float | How far this particle's field line extends (randomized within range) |
| `aDirection` | float | +1 = north→south, -1 = south→north |
| `aOffset` | float | Random time offset so particles don't all sync |

#### Shader Material

Use a **custom `ShaderMaterial`** (not standard material) for:

- **Vertex shader**: Compute position from dipole field line math using the attributes above. Add small noise displacement for organic feel.
- **Fragment shader**: 
  - Soft circular point sprite (Gaussian falloff, `gl_PointCoord`)
  - Color interpolated from pole color → midpoint color → opposite pole color
  - Alpha fades in at spawn, peaks at equatorial midpoint, fades out at destination
  - Additive blending (`THREE.AdditiveBlending`) for luminous overlap

#### Animation Modes (time-varying behavior)

The system should cycle between behavioral modes to create visual variety:

| Mode | Duration | Behavior |
|---|---|---|
| **Polar Burst** | 3–5s | Most particles erupt from the north pole in a focused jet |
| **Dual Stream** | 5–8s | Balanced north↔south flow, classic dipole look |
| **Random Eruption** | 2–4s | Particles spawn from random surface points (not just poles), chaotic |
| **Quiet** | 3–6s | Particle count drops to 30%, slow drift, calm breathing |

Transition between modes with a smooth **crossfade** (don't pop). Use a simple state machine driven by elapsed time + random intervals.

---

## Per-Body Configuration

Each wrapper component passes a unique config to `MagneticParticles`:

### Enceladus (Hero Moon — most visible, closest to camera at start)
```js
{
  particleCount: 1200,
  colors: {
    northPole: '#88CCFF',    // Icy blue
    equator: '#FFFFFF',       // Pure white
    southPole: '#AAD4FF',    // Pale blue
  },
  rmaxRange: [3.5, 7.0],     // 1.4× to 2.8× radius
  baseSpeed: 0.3,
  pointSize: 0.08,
  cycleSpeed: 1.0,           // Normal mode cycling
  tilt: [0, 0, 0],           // No axis tilt
}
```

### Ceres
```js
{
  particleCount: 800,
  colors: {
    northPole: '#E58D57',    // Titan Haze (brand accent)
    equator: '#C19A6B',       // Saturn Gold
    southPole: '#FF6B35',    // Deep orange
  },
  rmaxRange: [5.0, 10.0],
  baseSpeed: 0.2,
  pointSize: 0.1,
  cycleSpeed: 0.7,           // Slower mode cycling
  tilt: [0.1, 0, 0.05],     // Slight tilt
}
```

### Makemake
```js
{
  particleCount: 1500,
  colors: {
    northPole: '#C084FC',    // Purple
    equator: '#F0ABFC',       // Pink
    southPole: '#7C3AED',    // Deep violet
  },
  rmaxRange: [7.0, 16.0],    // Larger envelope (big moon)
  baseSpeed: 0.15,
  pointSize: 0.12,
  cycleSpeed: 0.5,           // Slow, meditative cycling
  tilt: [0.2, 0, 0.15],     // Match existing rotation axes
}
```

### Saturn (Special Case)
```js
{
  particleCount: 2000,
  colors: {
    northPole: '#FFEAC2',    // Warm gold
    equator: '#E58D57',       // Titan Haze
    southPole: '#C19A6B',    // Saturn Gold
  },
  rmaxRange: [20, 45],       // Massive envelope, extends near ring plane
  baseSpeed: 0.1,
  pointSize: 0.15,
  cycleSpeed: 0.3,           // Very slow, majestic
  tilt: [Math.PI / 12, 0, Math.PI / 12],  // Match Saturn's axis tilt group
}
```

**Saturn special consideration**: The particle envelope should interact visually with the ring plane. Particles passing through the ring plane could briefly brighten or change color. The tilt must match the existing `<group rotation={[Math.PI / 12, 0, Math.PI / 12]}>`.

---

## Performance Budget

| Metric | Target |
|---|---|
| Total particles (all 4 bodies) | ≤ 5,500 |
| Draw calls added | ≤ 4 (one Points/InstancedMesh per body) |
| GPU: vertex shader | Simple trig (sin²θ dipole), no texture lookups |
| GPU: fragment shader | Point sprite + color lerp + alpha, no texture lookups |
| CPU per frame | Only update `uTime` uniform. All animation in vertex shader. |
| Blending | `AdditiveBlending` + `depthWrite: false` |

**Do NOT use `useFrame` to update individual particle positions on the CPU.** All particle motion must be computed in the vertex shader from `uTime` + per-particle attributes. The only CPU work per frame should be `material.uniforms.uTime.value = clock.elapsedTime`.

---

## Visual Quality Targets

1. **Luminous, not noisy** — Particles should feel like soft, glowing plasma, not confetti. Use additive blending and Gaussian point sprites.
2. **Envelope shape** — From a distance, the particle cloud should form a visible cocoon/magnetosphere shape around each body. Not a random scatter.
3. **Depth** — Particles at different `aPhi` angles create a 3D shell effect, not a flat ring.
4. **Breathing** — Add a slow sinusoidal modulation to `rmaxRange` over time so the envelope gently expands and contracts.
5. **Color harmony** — Each body's palette should complement the existing texture colors and the "Titan Haze" design system.

---

## Deliverables Checklist

- [ ] `src/particles/MagneticParticles.jsx` — Core reusable component with custom shader
- [ ] `src/particles/EnceladusParticles.jsx` — Enceladus config wrapper
- [ ] `src/particles/CeresParticles.jsx` — Ceres config wrapper  
- [ ] `src/particles/MakemakeParticles.jsx` — Makemake config wrapper
- [ ] `src/particles/SaturnParticles.jsx` — Saturn config wrapper (with ring-plane interaction)
- [ ] `src/particles/index.js` — Barrel exports
- [ ] Minimal patch to `App.jsx` `SaturnScene` — import + place the 4 particle components
- [ ] No changes to camera, GSAP, HTML sections, or existing meshes
- [ ] All particle animation runs in GPU shaders (vertex shader dipole math)
- [ ] Performance within budget (≤5,500 particles, ≤4 draw calls, no CPU position updates)
- [ ] Mode cycling (Polar Burst → Dual Stream → Random Eruption → Quiet) with smooth crossfades

---

## Reference: Dipole Field Line Math

For implementing the vertex shader, here is the core dipole parameterization:

```glsl
// θ goes from 0 (north pole) to PI (south pole)
// The particle's progress along the field line maps to θ
float theta = aPhase * PI;  // 0 → PI as particle travels pole to pole

// Dipole field line: r = Rmax * sin²(θ)
float r = aRmax * sin(theta) * sin(theta);

// Convert to Cartesian (Y-up pole axis):
float x = r * sin(theta) * cos(aPhi);
float y = r * cos(theta);                // Pole axis
float z = r * sin(theta) * sin(aPhi);

// Add body center position
vec3 particlePos = uBodyCenter + vec3(x, y, z);
```

For **direction reversal** (south→north): use `theta = (1.0 - aPhase) * PI`.

For **random surface eruption mode**: lerp the spawn point from the pole toward a random theta using a mode-blend uniform.

---

## Execution Directive

Build all files completely. No placeholders, no TODOs. Every shader must compile, every component must render. Test mentally against the existing scene positions and camera paths — the particles must look correct from all the scroll-driven camera angles (close orbit around Enceladus, medium orbit around Ceres, high Saturn overview, close orbit around Makemake).
