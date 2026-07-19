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

  // Orbit angle goes the full circle so particles loop around the moon.
  float theta = currentPhase * 6.28318530718;

  // Orbit radius is always outside the planet.
  float orbitR = aRmax;

  // Flat ring in the XZ plane (group tilt gives it a subtle 3D angle).
  vec3 localPos = vec3(
    orbitR * cos(theta),
    0.0,
    orbitR * sin(theta)
  );

  vec4 modelPosition = modelMatrix * vec4(localPos, 1.0);
  vec4 viewPosition = viewMatrix * modelPosition;
  vec4 projectedPosition = projectionMatrix * viewPosition;

  gl_Position = projectedPosition;

  // Larger favicon dots: less perspective shrink, bigger clamp
  gl_PointSize = (uPointSize * (0.4 + 0.6 * aTrailFade)) * (400.0 / -viewPosition.z);
  gl_PointSize = clamp(gl_PointSize, 2.0, 80.0);

  // Rainbow color based on orbit angle so the ring cycles through all hues.
  float hueNorm = mod(theta / 6.28318530718, 1.0);

  vec3 aColor = vec3(0.5, 0.5, 0.5);
  vec3 bColor = vec3(0.5, 0.5, 0.5);
  vec3 cColor = vec3(1.0, 1.0, 1.0);
  // Shifted offset to land on clearer rainbow primaries
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

  // Hard circular boundary, then soft inner falloff
  if (dist > 0.5) discard;

  // Crisp circular sprite with a soft inner glow
  float alpha = pow(1.0 - (dist * 2.0), 3.2);
  if (alpha < 0.04) discard;

  // Boost brightness so particles pop without post-process bloom
  vec3 brightColor = vColor * 1.8;
  gl_FragColor = vec4(brightColor, alpha * vAlpha * vTrailFade);
}
`;

export function FaviconParticles({
  particleCount = 280,
  planetRadius = 0.28,
  rmaxRange = [0.85, 1.0],
  baseSpeed = 0.06,
  pointSize = 6.0,
  cycleSpeed = 0.008,
  tilt = [0.2, 0.15, 0.05],
  arcBands = 12,
  shellBands = 2,
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
    const TRACERS_PER_PARTICLE = 3;
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
      // Evenly spread around the ring, plus a small jitter, so the rainbow is uniform.
      const basePhase = i / baseParticleCount + (Math.random() - 0.5) * 0.04;
      const pSpeed = baseSpeed * (0.8 + Math.random() * 0.4);

      const basePhi = (i / baseParticleCount) * Math.PI * 2 + (Math.random() - 0.5) * 0.12;

      const shellId = Math.floor(Math.random() * shellBands);
      const baseRmax = THREE.MathUtils.lerp(
        rmaxRange[0],
        rmaxRange[1],
        shellBands > 1 ? shellId / (shellBands - 1) : 0.5
      ) + (Math.random() - 0.5) * (rmaxRange[1] - rmaxRange[0]) * 0.12;

      const baseDirection = Math.random() > 0.5 ? 1 : -1;
      const baseOffset = Math.random() * 100;

      for (let j = 0; j < TRACERS_PER_PARTICLE; j++) {
        const index = i * TRACERS_PER_PARTICLE + j;

        const trailFade = 1.0 - (j / (TRACERS_PER_PARTICLE - 1));
        // Tight delay so trails read as short dashes/dots hugging the moon
        const phaseDelay = j * 0.003;

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
