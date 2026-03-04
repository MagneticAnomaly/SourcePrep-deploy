import React, { useRef, useMemo, useEffect } from 'react';
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
  // Base phase progression
  float currentPhase = mod(aPhase + (uTime * aSpeed) + aOffset, 1.0);
  
  float dir = aDirection;

  // Phase mapping (0 to PI)
  float theta = currentPhase * 3.14159265359;
  if (dir < 0.0) {
      theta = (1.0 - currentPhase) * 3.14159265359;
  }

  // Parametric arc equations:
  // 1. Horizontally, we want the particles to reach aRmax at the equator.
  float radius_xz = aRmax * sin(theta);
  
  // 2. Vertically, we want the particles to start at exactly the planet's poles
  // and stretch high up into space (2x height of planet or more) before coming down.
  float stretch = max(aRmax * 1.5, uPlanetRadius * 3.0); // Ensure they are always at least 3x the planet radius tall
  float y = uPlanetRadius * cos(theta) + stretch * sin(theta) * cos(theta);

  vec3 localPos = vec3(
    radius_xz * cos(aPhi),
    y,
    radius_xz * sin(aPhi)
  );

  // Apply tilt (via the object transform passed by React Three Fiber)
  vec4 modelPosition = modelMatrix * vec4(localPos, 1.0);
  vec4 viewPosition = viewMatrix * modelPosition;
  vec4 projectedPosition = projectionMatrix * viewPosition;

  gl_Position = projectedPosition;
  
  // Point size (Perspective)
  // Clamp the point size to be visible but not massive.
  // Scale the point size down based on its position in the tail using aTrailFade.
  gl_PointSize = (uPointSize * (0.3 + 0.7 * aTrailFade)) * (300.0 / -viewPosition.z); 
  gl_PointSize = clamp(gl_PointSize, 1.0, 50.0);
  
  // Rainbow Color based on normalized arc size (aRmax)
  float arcNorm = clamp((aRmax - uRmaxRangeMap.x) / (uRmaxRangeMap.y - uRmaxRangeMap.x), 0.0, 1.0);
  
  // High fidelity procedural rainbow palette
  vec3 aColor = vec3(0.5, 0.5, 0.5);
  vec3 bColor = vec3(0.5, 0.5, 0.5);
  vec3 cColor = vec3(1.0, 1.0, 1.0);
  vec3 dColor = vec3(0.00, 0.33, 0.67);
  vColor = aColor + bColor * cos(6.28318530718 * (cColor * arcNorm + dColor));

  // Fully visible at all times, but pass the tail fade to the fragment shader
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
  // Gaussian point sprite (tighter, less blurry dropoff)
  vec2 center = gl_PointCoord - vec2(0.5);
  float distsq = dot(center, center);
  float alpha = exp(-distsq * 7.0); // Tighter Gaussian falloff for crisper dots
  
  // Discard corners
  if (alpha < 0.01) discard;

  // Enhance glow with vTrailFade, making the tail far more transparent
  gl_FragColor = vec4(vColor, alpha * vAlpha * vTrailFade);
}
`;

export function MagneticParticles({
    particleCount = 1000,
    planetRadius = 1.0,
    rmaxRange = [2, 5],
    baseSpeed = 0.5,
    pointSize = 6.0, // Base point size, reduced for crisper look
    cycleSpeed = 1.0,
    tilt = [0, 0, 0],
    position = [0, 0, 0],
    arcBands = 8,
    shellBands = 3
}) {
    const pointsRef = useRef();
    const materialRef = useRef();

    const uniforms = useMemo(() => ({
        uTime: { value: 0 },
        uPointSize: { value: pointSize },
        uPlanetRadius: { value: planetRadius },
        uRmaxRangeMap: { value: new THREE.Vector2(rmaxRange[0], rmaxRange[1]) }
    }), [pointSize, planetRadius, rmaxRange]);

    const geometry = useMemo(() => {
        const geo = new THREE.BufferGeometry();

        // Settings for tracer tails
        // Half the total unique objects but multiply them into 6-segment trails
        const TRACERS_PER_PARTICLE = 6;
        const totalVertices = Math.floor(particleCount / 2) * TRACERS_PER_PARTICLE;

        const positions = new Float32Array(totalVertices * 3);
        const phases = new Float32Array(totalVertices);
        const speeds = new Float32Array(totalVertices);
        const phis = new Float32Array(totalVertices);
        const rmaxs = new Float32Array(totalVertices);
        const directions = new Float32Array(totalVertices);
        const offsets = new Float32Array(totalVertices);
        const trailFades = new Float32Array(totalVertices);

        // Calculate for half the particles since they each have 6 vertices now
        const baseParticleCount = Math.floor(particleCount / 2);

        for (let i = 0; i < baseParticleCount; i++) {
            const basePhase = Math.random();
            const pSpeed = baseSpeed * (0.8 + Math.random() * 0.4);

            // Quantize phi to form distinct longitudinal bands, but add randomized spray
            const bandId = Math.floor(Math.random() * arcBands);
            const basePhi = (bandId / arcBands) * Math.PI * 2 + (Math.random() - 0.5) * 0.35;

            // Quantize rmax to form distinct radial shells, but with random spread
            const shellId = Math.floor(Math.random() * shellBands);
            const baseRmax = THREE.MathUtils.lerp(rmaxRange[0], rmaxRange[1], shellBands > 1 ? shellId / (shellBands - 1) : 0.5) + (Math.random() - 0.5) * (rmaxRange[1] - rmaxRange[0]) * 0.2;

            const baseDirection = Math.random() > 0.5 ? 1 : -1;
            const baseOffset = Math.random() * 100;

            // Generate the head and its trailing dots
            for (let j = 0; j < TRACERS_PER_PARTICLE; j++) {
                const index = i * TRACERS_PER_PARTICLE + j;

                // j=0 is the head, j=5 is the tip of the tail
                const trailFade = 1.0 - (j / (TRACERS_PER_PARTICLE - 1));
                // Delay phase for trailing particles
                const phaseDelay = j * 0.015;

                phases[index] = basePhase;
                speeds[index] = pSpeed;
                phis[index] = basePhi;
                rmaxs[index] = baseRmax;
                directions[index] = baseDirection;
                offsets[index] = baseOffset - phaseDelay;
                trailFades[index] = trailFade;

                positions[index * 3] = position[0];
                positions[index * 3 + 1] = position[1];
                positions[index * 3 + 2] = position[2];
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
    }, [particleCount, rmaxRange, baseSpeed, position, arcBands, shellBands]);


    useFrame((state) => {
        if (materialRef.current) {
            materialRef.current.uniforms.uTime.value = state.clock.elapsedTime * cycleSpeed;
        }
    });

    return (
        <points ref={pointsRef} position={position} rotation={tilt} frustumCulled={false}>
            <primitive object={geometry} attach="geometry" />
            <shaderMaterial
                ref={materialRef}
                attach="material"
                vertexShader={vertexShader}
                fragmentShader={fragmentShader}
                uniforms={uniforms}
                transparent={true}
                blending={THREE.AdditiveBlending}
                depthWrite={false}
                depthTest={true}
            />
        </points>
    );
}
