import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const vertexShader = `
precision highp float;
uniform float uTime;
uniform float uPointSize;
uniform float uPlanetRadius;
uniform vec2 uRmaxRangeMap;

attribute float aPhase;
attribute float aSpeed;
attribute float aPhi;
attribute float aRmax;
attribute float aDirection;
attribute float aOffset;
attribute float aTrailFade;

varying vec3 vColor;
varying float vAlpha;
varying float vTrailFade;

void main() {
  float currentPhase = mod(aPhase + (uTime * aSpeed) + aOffset, 1.0);

  float dir = aDirection;
  // Phase maps 0..1 to a half-arc: particles leave one pole, arc over, return to the other.
  float theta = currentPhase * 3.14159265359;
  if (dir < 0.0) {
      theta = (1.0 - currentPhase) * 3.14159265359;
  }

  // Horizontal reach at the equator.
  float radius_xz = aRmax * sin(theta);

  // Tall arcs that shoot high above/below the poles.
  float stretch = uPlanetRadius * 3.0;
  float y = uPlanetRadius * cos(theta) + stretch * sin(theta) * cos(theta);

  // Ensure arcs never dip inside the planet body.
  radius_xz = max(radius_xz, uPlanetRadius * 1.25);

  vec3 localPos = vec3(
    radius_xz * cos(aPhi),
    y,
    radius_xz * sin(aPhi)
  );

  vec4 modelPosition = modelMatrix * vec4(localPos, 1.0);
  vec4 viewPosition = viewMatrix * modelPosition;
  vec4 projectedPosition = projectionMatrix * viewPosition;

  gl_Position = projectedPosition;

  // Big head; tail shrinks very steeply so each stream reads as a few bold dots.
  float sizeFade = pow(aTrailFade, 5.0);
  gl_PointSize = (uPointSize * (0.03 + 0.97 * sizeFade)) * (400.0 / -viewPosition.z);
  gl_PointSize = clamp(gl_PointSize, 1.0, 200.0);

  // Rainbow color based on arc longitude (aPhi) so different arcs show different hues.
  float hueNorm = mod(aPhi / 6.28318530718, 1.0);

  vec3 aColor = vec3(0.5, 0.5, 0.5);
  vec3 bColor = vec3(0.5, 0.5, 0.5);
  vec3 cColor = vec3(1.0, 1.0, 1.0);
  // Offset to favor clear rainbow primaries
  vec3 dColor = vec3(0.20, 0.53, 0.87);
  vColor = aColor + bColor * cos(6.28318530718 * (cColor * hueNorm + dColor));

  vAlpha = 1.0;
  vTrailFade = aTrailFade;
}
`;

const fragmentShader = `
precision highp float;
varying vec3 vColor;
varying float vAlpha;
varying float vTrailFade;

void main() {
  vec2 center = gl_PointCoord - vec2(0.5);
  float dist = length(center);

  // Near-hard circular disc with only a 1-pixel-ish anti-aliased edge.
  if (dist > 0.5) discard;
  float edge = smoothstep(0.5, 0.48, dist);
  float alpha = edge;
  if (alpha < 0.02) discard;

  // Bright, saturated color.
  vec3 brightColor = vColor * 1.8;
  gl_FragColor = vec4(brightColor, alpha * vAlpha * vTrailFade);
}
`;

export function FaviconParticles({
  particleCount = 16,
  planetRadius = 0.65,
  rmaxRange = [1.05, 1.35],
  baseSpeed = 0.08,
  pointSize = 70.0,
  cycleSpeed = 0.018,
  tilt = [0.12, 0.0, 0.05],
  arcBands = 6,
  shellBands = 3,
}) {
  const materialRef = useRef();

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uPointSize: { value: pointSize },
    uPlanetRadius: { value: planetRadius },
    uRmaxRangeMap: { value: new THREE.Vector2(rmaxRange[0], rmaxRange[1]) },
  }), [pointSize, planetRadius, rmaxRange]);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const TRACERS_PER_PARTICLE = 8;
    const totalVertices = Math.floor(particleCount / 2) * TRACERS_PER_PARTICLE;

    const positions = new Float32Array(totalVertices * 3);
    const phases = new Float32Array(totalVertices);
    const speeds = new Float32Array(totalVertices);
    const phis = new Float32Array(totalVertices);
    const rmaxs = new Float32Array(totalVertices);
    const directions = new Float32Array(totalVertices);
    const offsets = new Float32Array(totalVertices);
    const trailFades = new Float32Array(totalVertices);

    const baseParticleCount = Math.floor(particleCount / 2);

    for (let i = 0; i < baseParticleCount; i++) {
      const basePhase = Math.random();
      const pSpeed = baseSpeed * (0.8 + Math.random() * 0.4);

      // Quantize phi into longitudinal bands so we get distinct arcing streams.
      const bandId = Math.floor(Math.random() * arcBands);
      const basePhi = (bandId / arcBands) * Math.PI * 2 + (Math.random() - 0.5) * 0.35;

      const shellId = Math.floor(Math.random() * shellBands);
      const baseRmax = THREE.MathUtils.lerp(
        rmaxRange[0],
        rmaxRange[1],
        shellBands > 1 ? shellId / (shellBands - 1) : 0.5
      ) + (Math.random() - 0.5) * (rmaxRange[1] - rmaxRange[0]) * 0.18;

      const baseDirection = Math.random() > 0.5 ? 1 : -1;
      const baseOffset = Math.random() * 100;

      for (let j = 0; j < TRACERS_PER_PARTICLE; j++) {
        const index = i * TRACERS_PER_PARTICLE + j;

        const trailFade = 1.0 - (j / (TRACERS_PER_PARTICLE - 1));
        // Longer delay so each particle has a visible trailing tail along the arc.
        const phaseDelay = j * 0.05;

        phases[index] = basePhase;
        speeds[index] = pSpeed;
        phis[index] = basePhi;
        rmaxs[index] = baseRmax;
        directions[index] = baseDirection;
        offsets[index] = baseOffset - phaseDelay;
        trailFades[index] = trailFade;

        positions[index * 3] = 0;
        positions[index * 3 + 1] = 0;
        positions[index * 3 + 2] = 0;
      }
    }

    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
    geo.setAttribute('aSpeed', new THREE.BufferAttribute(speeds, 1));
    geo.setAttribute('aPhi', new THREE.BufferAttribute(phis, 1));
    geo.setAttribute('aRmax', new THREE.BufferAttribute(rmaxs, 1));
    geo.setAttribute('aDirection', new THREE.BufferAttribute(directions, 1));
    geo.setAttribute('aOffset', new THREE.BufferAttribute(offsets, 1));
    geo.setAttribute('aTrailFade', new THREE.BufferAttribute(trailFades, 1));

    return geo;
  }, [particleCount, rmaxRange, baseSpeed, arcBands, shellBands]);

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime * cycleSpeed;
    }
  });

  return (
    <points rotation={tilt} frustumCulled={false}>
      <primitive object={geometry} attach="geometry" />
      <shaderMaterial
        ref={materialRef}
        attach="material"
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent={true}
        blending={THREE.NormalBlending}
        depthWrite={false}
        depthTest={true}
      />
    </points>
  );
}
