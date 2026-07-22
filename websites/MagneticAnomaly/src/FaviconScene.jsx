import React, { Suspense, useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, useTexture, Text } from '@react-three/drei';
import { FaviconParticles } from './FaviconParticles';
import * as THREE from 'three';

function Monogram() {
  const groupRef = useRef();
  const mRef = useRef();
  const aRef = useRef();

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.15) * 0.05;
    }
  });

  useEffect(() => {
    [mRef, aRef].forEach((ref) => {
      const mesh = ref.current;
      if (mesh) {
        mesh.renderOrder = -10;
        const material = mesh.material;
        if (material) {
          material.transparent = false;
          material.opacity = 1.0;
          material.depthWrite = true;
          material.blending = THREE.NormalBlending;
          material.smoothness = 0.65;
          material.thickness = 0.025;
          material.needsUpdate = true;
        }
      }
    });
  }, []);

  const mConfig = useMemo(() => ({
    font: '/fonts/SpaceGrotesk-Bold.ttf',
    fontSize: 0.735,
    letterSpacing: -0.02,
    lineHeight: 1,
    color: '#F8F9FA',
    anchorX: 'right',
    anchorY: 'middle',
  }), []);

  const aConfig = useMemo(() => ({
    font: '/fonts/SpaceGrotesk-Bold.ttf',
    fontSize: 0.735,
    letterSpacing: -0.02,
    lineHeight: 1,
    color: '#F8F9FA',
    anchorX: 'left',
    anchorY: 'middle',
  }), []);

  return (
    <group ref={groupRef} position={[0, 0, 0.75]}>
      <Text {...mConfig} ref={mRef} position={[-0.01, 0, 0]}>
        M
      </Text>
      <Text {...aConfig} ref={aRef} position={[0.015, 0, 0]}>
        A
      </Text>
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

      <FaviconParticles />
    </group>
  );
}

function Scene() {
  return (
    <>
      <TinyMoon />
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
