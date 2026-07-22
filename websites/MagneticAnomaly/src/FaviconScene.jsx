import React, { Suspense, useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, useTexture, Text } from '@react-three/drei';
import { FaviconParticles } from './FaviconParticles';
import * as THREE from 'three';

function Monogram() {
  const groupRef = useRef();
  const textRef = useRef();

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.15) * 0.05;
    }
  });

  const config = useMemo(() => ({
    font: '/fonts/SpaceGrotesk-Bold.ttf',
    fontSize: 0.78,
    letterSpacing: -0.02,
    lineHeight: 1,
    color: '#F8F9FA',
    anchorX: 'center',
    anchorY: 'middle',
  }), []);

  return (
    <group ref={groupRef} position={[0, 0, 0.75]}>
      <Text
        {...config}
        ref={textRef}
      >
        MA
      </Text>
      {/* Overlay plane: lets nearby particles tint/brighten the monogram.
          Sits slightly in front of the text, uses additive blending and a
          low opacity so colored particles appear to splash across the letters. */}
      <mesh position={[0, 0, 0.02]}>
        <planeGeometry args={[1.35, 0.95]} />
        <meshBasicMaterial
          color="#ffffff"
          transparent
          opacity={0.18}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function TinyMoon() {
  const [ceresMap] = useTexture(['/textures/ceres.jpg']);
  const moonRef = useRef();

  useFrame(() => {
    if (moonRef.current) {
      moonRef.current.rotation.y += 0.001;
    }
  });

  return (
    <group ref={moonRef}>
      {/* Lighting tuned for a small, centered object */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 20]} intensity={1.5} color="#FFEAC2" />
      <directionalLight position={[-10, -5, -10]} intensity={0.4} color="#F8F9FA" />

      <Sphere args={[0.65, 64, 64]}>
        <meshStandardMaterial
          map={ceresMap}
          color="#ECECEC"
          roughness={0.5}
          metalness={0.05}
        />
      </Sphere>

      {/**
       * Favicon-specific particle field: fewer, rounder, bigger, closer, rainbow arcs.
       */}
      <FaviconParticles />
    </group>
  );
}

function Scene() {
  return (
    <>
      <TinyMoon />
      {/* Monogram sits just in front of the moon, behind nearest particles,
          and outside the moon group so it does not rotate with the moon. */}
      <Monogram />
    </>
  );
}

export default function FaviconScene() {
  return (
    <div className="fixed inset-0 bg-[#030305]">
      <Canvas
        camera={{ position: [0, 0.5, 10.0], fov: 45, far: 100 }}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        dpr={[3, 3]}
      >
        <Suspense fallback={null}>
          <Scene />
        </Suspense>
      </Canvas>
    </div>
  );
}
