import React, { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, useTexture } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { MagneticParticles } from './particles/MagneticParticles';

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

      <Sphere args={[1, 64, 64]}>
        <meshStandardMaterial
          map={ceresMap}
          color="#ECECEC"
          roughness={0.5}
          metalness={0.05}
        />
      </Sphere>

      {/**
       * Handful of particles using the same shader as the main site.
       * particleCount=36 becomes 18 base particles * 6 trail segments = 108 vertices.
       * Smaller scale makes the same point sprites read as bigger relative to the moon.
       */}
      <MagneticParticles
        particleCount={36}
        planetRadius={1.0}
        rmaxRange={[2.2, 3.8]}
        baseSpeed={0.25}
        pointSize={10.0}
        cycleSpeed={0.04}
        arcBands={3}
        shellBands={2}
        tilt={[0.15, 0.1, 0]}
      />
    </group>
  );
}

export default function FaviconScene() {
  return (
    <div className="fixed inset-0 bg-[#030305]">
      <Canvas
        camera={{ position: [0, 0, 6], fov: 45, far: 100 }}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        dpr={[2, 2]}
      >
        <EffectComposer disableNormalPass>
          <Bloom
            luminanceThreshold={0.25}
            mipmapBlur={true}
            intensity={1.5}
          />
        </EffectComposer>
        <Suspense fallback={null}>
          <TinyMoon />
        </Suspense>
      </Canvas>
    </div>
  );
}
