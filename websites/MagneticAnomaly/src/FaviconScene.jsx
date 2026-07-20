import React, { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, useTexture } from '@react-three/drei';
import { FaviconParticles } from './FaviconParticles';

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

      <Sphere args={[0.45, 64, 64]}>
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

export default function FaviconScene() {
  return (
    <div className="fixed inset-0 bg-[#030305]">
      <Canvas
        camera={{ position: [0, 0.2, 11.0], fov: 45, far: 100 }}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        dpr={[2, 2]}
      >
        <Suspense fallback={null}>
          <TinyMoon />
        </Suspense>
      </Canvas>
    </div>
  );
}
