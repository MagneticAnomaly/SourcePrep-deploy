import React, { useRef, useState, useLayoutEffect, useEffect, useCallback, Suspense, memo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, Ring, Icosahedron, Stars, useTexture } from '@react-three/drei';
import * as THREE from 'three';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { MagneticParticles, EnceladusParticles, CeresParticles, MakemakeParticles, SaturnParticles } from './particles';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { Terminal, Smartphone, Lock, Activity, Shield, ArrowRight, XSquare, MessageSquare, ExternalLink } from 'lucide-react';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger);

// Fix for mobile scroll sticking issues when using fixed pinning
ScrollTrigger.config({ ignoreMobileResize: true });
ScrollTrigger.normalizeScroll(true);

/** ====== WEBGL BACKGROUND ====== */
function AsteroidField({ count = 150 }) {
  const meshRef = useRef();
  const dummy = new THREE.Object3D();
  const particles = React.useMemo(() => {
    const temp = [];
    for (let i = 0; i < count; i++) {
      const x = (Math.random() - 0.5) * 800;
      const y = (Math.random() - 0.5) * 400;
      const z = (Math.random() - 0.5) * 800;
      const scale = Math.random() * 0.8 + 0.1;
      temp.push({ x, y, z, scale });
    }
    return temp;
  }, [count]);

  useFrame(() => {
    particles.forEach((particle, i) => {
      dummy.position.set(particle.x, particle.y, particle.z);
      dummy.scale.set(particle.scale, particle.scale, particle.scale);
      dummy.rotation.x += 0.001;
      dummy.rotation.y += 0.002;
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
    });
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[null, null, count]}>
      <icosahedronGeometry args={[1, 0]} />
      <meshStandardMaterial color="#8B949E" wireframe transparent opacity={0.3} />
    </instancedMesh>
  );
}

function SaturnRings({ ringMap }) {
  const meshRef = useRef();

  useEffect(() => {
    if (meshRef.current) {
      const geometry = meshRef.current.geometry;
      const pos = geometry.attributes.position;
      const v3 = new THREE.Vector3();
      const uvs = [];
      for (let i = 0; i < pos.count; i++) {
        v3.fromBufferAttribute(pos, i);
        // Radius of this vertex (distance from center)
        const radius = v3.length();
        // Map radius from innerRadius(18) to outerRadius(42)  => U coordinate from 0 to 1
        const u = (radius - 18) / (42 - 18);
        uvs.push(u, 0); // V doesn't matter
      }
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    }
  }, []);

  return (
    <Ring ref={meshRef} args={[18, 42, 128]} rotation={[-Math.PI / 2, 0, 0]}>
      <meshStandardMaterial
        map={ringMap}
        color="#FFFFFF"
        transparent
        opacity={0.95}
        depthWrite={false}
        side={THREE.DoubleSide}
        roughness={0.4}
      />
    </Ring>
  );
}

function SaturnScene() {
  const groupRef = useRef();
  const saturnRef = useRef();
  const enceladusRef = useRef();
  const ceresRef = useRef();
  const makemakeRef = useRef();

  // Load standard solar system textures
  const [saturnMap, ceresMap, makemakeMap, ringMap, milkyWayMap] = useTexture([
    '/textures/saturn.jpg',
    '/textures/ceres.jpg',
    '/textures/2k_makemake_fictional.jpg',
    '/textures/2k_saturn_ring_alpha.png',
    '/textures/2k_stars_milky_way.jpg'
  ]);

  useFrame((state) => {
    if (saturnRef.current) {
      saturnRef.current.rotation.y += 0.0005; // Only rotate around Y axis (day/night)
    }
    if (enceladusRef.current) {
      enceladusRef.current.rotation.y -= 0.0025;
    }
    if (ceresRef.current) {
      ceresRef.current.rotation.y += 0.0025;
    }
    if (makemakeRef.current) {
      makemakeRef.current.rotation.y += 0.001;
      makemakeRef.current.rotation.x += 0.0005;
    }
  });

  return (
    <group ref={groupRef} position={[0, 0, 0]}>
      {/* Normalized ambient light to balance textures */}
      <ambientLight intensity={0.4} />
      {/* Front lighting 180 degrees from dark side, balanced */}
      <directionalLight position={[10, 10, 40]} intensity={1.8} color="#FFEAC2" />
      <directionalLight position={[-20, -5, -10]} intensity={0.5} color="#F8F9FA" />

      {/* Saturn Group */}
      <group position={[-15, 0, -45]}>
        {/* Tilted Axis Group for alignment */}
        <group rotation={[Math.PI / 12, 0, Math.PI / 12]}>
          <group ref={saturnRef}>
            <Sphere args={[16, 64, 64]}>
              <meshStandardMaterial
                map={saturnMap}
                roughness={0.9}
                metalness={0.1}
              />
            </Sphere>
            <SaturnParticles />
          </group>

          <SaturnRings ringMap={ringMap} />
        </group>
      </group>

      {/* Hero Moon (Enceladus) */}
      <group ref={enceladusRef} position={[-40, -5, 405]}>
        <Sphere args={[2.5, 32, 32]}>
          <meshStandardMaterial
            map={ceresMap}
            color="#ECECEC"
            roughness={0.4}
            metalness={0.0}
          />
        </Sphere>
        <EnceladusParticles />
      </group>

      {/* Ceres */}
      <group ref={ceresRef} position={[150, 20, -100]}>
        <Sphere args={[3.5, 32, 32]}>
          <meshStandardMaterial
            map={ceresMap}
            color="#DDDDDD"
            roughness={0.2}
            metalness={0.1}
          />
        </Sphere>
        <CeresParticles />
      </group>

      {/* Makemake */}
      <group ref={makemakeRef} position={[-150, -30, 50]}>
        <Sphere args={[5.5, 32, 32]}>
          <meshStandardMaterial
            map={makemakeMap}
            roughness={0.9}
            metalness={0.0}
          />
        </Sphere>
        <MakemakeParticles />
      </group>

      <AsteroidField count={1500} />

      {/* Milky Way Skybox */}
      <Sphere args={[2500, 64, 64]}>
        <meshBasicMaterial
          map={milkyWayMap}
          side={THREE.BackSide}
          color="#333333"
        />
      </Sphere>
    </group>
  );
}

const HERO_START_ANGLE = Math.PI * 0.45; // Just a tiny bit off-center
const HERO_END_ANGLE = Math.PI * 0.6; // Rotate the opposite direction
const HERO_RADIUS = 15;
const HERO_CENTER = new THREE.Vector3(-40, -5, 405);

export const globalCamera = {
  pos: new THREE.Vector3(
    HERO_CENTER.x + Math.cos(HERO_START_ANGLE) * HERO_RADIUS,
    HERO_CENTER.y,
    HERO_CENTER.z + Math.sin(HERO_START_ANGLE) * HERO_RADIUS
  ),
  lookAt: HERO_CENTER.clone()
};

function CameraRig() {
  const currentPos = useRef(globalCamera.pos.clone());
  const currentLookAt = useRef(globalCamera.lookAt.clone());

  useFrame((state) => {
    // 1. Base Target
    const targetPos = globalCamera.pos.clone();
    const targetLookAt = globalCamera.lookAt.clone();

    // 2. Very subtle ambient vertical bob
    const time = state.clock.getElapsedTime();
    targetPos.y += Math.sin(time * 0.5) * 2;

    // 3. Mouse parallax (applied gently on top of the orbit)
    const parallaxOffset = new THREE.Vector3(state.pointer.x * 2, state.pointer.y * 2, 0);
    targetPos.add(parallaxOffset);

    // 4. Smooth damp the actual camera position towards the calculated point
    if (state.clock.elapsedTime < 0.2) {
      currentPos.current.copy(targetPos);
      currentLookAt.current.copy(targetLookAt);
    } else {
      currentPos.current.lerp(targetPos, 0.03);
      currentLookAt.current.lerp(targetLookAt, 0.03);
    }

    state.camera.position.copy(currentPos.current);
    state.camera.lookAt(currentLookAt.current);
  });
  return null;
}

/** ====== COMPONENTS ====== */

function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navTransition = scrolled ? 'delay-[0ms]' : 'delay-[500ms]';
  const contentTransition = scrolled ? 'delay-[500ms]' : 'delay-[0ms]';

  return (
    <>
      <nav className={`fixed top-0 w-full z-50 transition-all duration-500 ${navTransition} ${scrolled ? 'bg-[#030305]/80 backdrop-blur-[7px] pt-[max(1rem,env(safe-area-inset-top))] pb-4' : 'bg-transparent pt-[max(2rem,env(safe-area-inset-top))] pb-8'}`}>
        <div className="max-w-7xl mx-auto px-6 relative flex items-center h-8">
          <h1 className={`absolute whitespace-nowrap w-max top-1/2 -translate-y-1/2 font-sans font-bold text-[1rem] sm:text-xl tracking-widest text-ice transition-all duration-500 ${contentTransition} ${scrolled ? 'left-6 -translate-x-0' : 'left-1/2 -translate-x-1/2'}`}>MAGNETIC ANOMALY</h1>

          {/* <div className={`hidden md:flex items-center space-x-8 absolute right-6 transition-all duration-500 ${contentTransition} ${scrolled ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>
            <a href="#gap-to-payloads" className="font-mono text-sm text-telemetry hover:text-titan transition-colors">PORTFOLIO</a>
            <a href="#manifesto" className="font-mono text-sm text-telemetry hover:text-titan transition-colors">MANIFESTO</a>
            <a href="#commlink" className="font-mono text-sm text-telemetry hover:text-titan transition-colors">CONTACT</a>
          </div> */}

          {/* <div className={`md:hidden absolute right-6 transition-all duration-500 ${contentTransition} ${scrolled ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>
            <button onClick={() => setMenuOpen(true)} className="text-ice p-1 focus:outline-none">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
            </button>
          </div> */}
        </div>
      </nav>

      {/* Mobile Menu Overlay */}
      {/* <div className={`fixed inset-0 z-[60] bg-[#030305]/80 backdrop-blur-[7px] transition-all duration-500 flex flex-col items-center justify-center ${menuOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>
        <button onClick={() => setMenuOpen(false)} className="absolute top-6 right-6 text-ice p-2 focus:outline-none">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
        <div className="flex flex-col items-center space-y-12">
          <a href="#gap-to-payloads" onClick={() => setMenuOpen(false)} className="font-sans font-bold text-2xl tracking-widest text-titan hover:text-ice transition-colors">PORTFOLIO</a>
          <a href="#manifesto" onClick={() => setMenuOpen(false)} className="font-sans font-bold text-2xl tracking-widest text-titan hover:text-ice transition-colors">MANIFESTO</a>
          <a href="#commlink" onClick={() => setMenuOpen(false)} className="font-sans font-bold text-2xl tracking-widest text-titan hover:text-ice transition-colors">CONTACT</a>
        </div>
      </div> */}
    </>
  );
}

function Hero({ ready }) {
  const container = useRef();

  // Hide hero text on mount so it doesn't paint before the WebGL scene is ready.
  // Using gsap.set inside useGSAP runs in useLayoutEffect — applies before first paint.
  useGSAP(() => {
    gsap.set(".hero-anim", { autoAlpha: 0, y: 40 });
  }, { scope: container });

  // Animate hero text in only after the scene has rendered its first frame.
  useGSAP(() => {
    if (!ready) return;
    gsap.to(".hero-anim", {
      autoAlpha: 1,
      y: 0,
      duration: 1.5,
      stagger: 0.2,
      ease: "power3.out",
    });
  }, { scope: container, dependencies: [ready] });

  return (
    <section id="hero" ref={container} className="relative w-full h-[100dvh] flex items-center justify-center px-6">
      <div className="text-center w-full z-10 max-w-4xl mx-auto md:mt-20 mt-0">
        <div className="hero-anim inline-block mb-6 px-4 py-1.5 opacity-0 pointer-events-none" style={{ height: '2rem' }}></div>
        <h2 className="hero-anim font-serif text-6xl md:text-8xl italic text-ice mb-8 leading-tight max-md:text-[3.5em] max-md:leading-[1.1] max-md:px-[0.3em] max-md:mt-[0.6em] drop-shadow-[1px_2px_30px_rgba(0,0,0,0.4)]">We Make Things That Don't Exist Yet.</h2>
        <div className="hero-anim relative w-screen ml-[calc(50%-50vw)] flex items-center justify-center my-6" style={{ height: '2.5rem' }}>
          <div className="subtitle-mask-hero absolute w-screen h-full bg-[#030305]/95 backdrop-blur-sm border-y border-white/5 flex items-center justify-center translate-z-0"
            style={{ clipPath: 'polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)' }}>
            <p className="absolute w-screen text-center font-mono text-[#8B949E] max-md:text-[3.2vw] md:text-xl" style={{ textShadow: '0 0 10px rgba(255,255,255,0.1)' }}>
              App Design for Humans made by Human & Computers
            </p>
          </div>
        </div>

        {/* <a href="#gap-to-payloads" className="hero-anim mt-12 cursor-pointer flex items-center justify-center space-x-3 group mx-auto w-fit no-underline">
          <div className="w-12 h-12 rounded-full border border-titan flex items-center justify-center group-hover:bg-titan transition-all duration-300">
            <ArrowRight className="text-titan group-hover:text-void w-5 h-5 transition-colors" />
          </div>
          <span className="font-mono text-sm tracking-widest text-titan uppercase">Explore Portfolio</span>
        </a> */}
      </div>
    </section>
  );
}

function Payloads() {
  const container = useRef();

  return (
    <>
      <div id="gap-to-payloads" className="h-[150vh] pointer-events-none" />
      <section id="payloads" ref={container} className="w-full min-h-[100dvh] flex flex-col justify-center pt-8 pb-12 md:py-12 relative z-10 max-md:h-[100dvh] max-md:justify-start max-md:pt-28 max-md:pb-2">

        {/* Header matching Navbar width */}
        <div className="max-w-7xl w-full px-6 mx-auto mb-6 md:mb-12 lg:mb-20 max-md:mb-4 max-md:shrink-0">
          <h3 className="font-mono text-sm tracking-[0.2em] text-titan mb-4 uppercase max-md:mb-0 hidden md:block">// OUR WORK</h3>
          <h2 className="font-sans font-bold text-4xl md:text-5xl uppercase tracking-wider text-ice hidden md:block">Portfolio</h2>
          <h3 className="font-mono text-sm tracking-[0.2em] text-titan mb-0 uppercase md:hidden">// PORTFOLIO</h3>
        </div>

        {/* Portfolio Cards matching wider layout */}
        <div className="max-w-[1400px] w-full px-0 sm:px-4 md:px-8 mx-auto max-md:flex-1 max-md:flex max-md:flex-col max-md:min-h-0">
          <div className="overflow-hidden w-full relative max-md:h-full max-md:flex-1">
            <div className="payloads-track relative w-full h-[550px] md:h-[700px] max-md:h-full">

              {/* APP 01 - SourcePrep */}
              <div className="app-panel-1 absolute inset-0 w-full h-full flex flex-col justify-center px-2 sm:px-4 md:px-8 max-md:justify-start max-md:pb-2">
                <div className="payload-card w-full relative glass-panel rounded-[2.5rem] p-2 md:p-3 overflow-hidden transition-all duration-700 hover:border-titan/50 hover:shadow-[0_0_40px_rgba(229,141,87,0.15)] md:bg-void/80 min-h-[500px] md:min-h-[650px] max-md:h-full max-md:rounded-[2rem] max-md:flex max-md:flex-col">
                  <div className="absolute inset-0 bg-gradient-to-br from-titan/5 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-500" />
                  <div className="relative z-10 w-full h-full p-4 md:p-14 flex flex-col lg:flex-row gap-4 md:gap-8 lg:gap-12 items-center max-md:items-start max-md:min-h-0">

                    {/* Text Column */}
                    <div className="w-full lg:w-5/12 max-md:shrink-0">
                      <div className="flex flex-row items-center justify-between mb-6 gap-4">
                        <div className="flex items-center space-x-4">
                          <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                            <img src="/SourcePrep-Logo2.png" alt="SourcePrep Icon" className="w-full h-full object-cover" />
                          </div>
                          <div>
                            <span className="font-mono text-xs text-telemetry tracking-widest block">[ DESKTOP / APP ]</span>
                            <h4 className="font-sans text-2xl md:text-3xl font-bold text-ice">SourcePrep</h4>
                          </div>
                        </div>
                        <a href="https://sourceprep.io" target="_blank" rel="noreferrer" className="md:hidden flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-titan text-ice hover:text-void border border-white/10 hover:border-titan transition-all">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>

                      <p className="font-mono text-[11px] md:text-sm text-telemetry max-md:text-[#A1AAB5] mb-4 md:mb-6 leading-relaxed">
                        <strong className="text-ice">The Context Engine for AI-Assisted Software Engineering.</strong><br /><br />
                        SourcePrep bridges the gap between massive, complex codebases and LLMs by providing precise, graph-augmented context. It uses advanced AST parsing to trace dependencies, effectively fighting Context Bloat and reducing token costs.
                      </p>

                      <div className="space-y-1.5 md:space-y-2 mb-4 md:mb-8 font-mono text-[10px] md:text-xs text-telemetry max-md:text-[#A1AAB5]">
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Native Semantic Search (Local ONNX)</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Code Graph & Trace Expansion</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Smart Token Compression (20:1 ratio)</p>
                      </div>

                      <a href="https://sourceprep.io" target="_blank" rel="noreferrer" className="hidden md:inline-block font-mono text-xs bg-white/5 hover:bg-titan hover:text-void text-ice border border-white/10 hover:border-titan px-8 py-4 rounded-full transition-all uppercase tracking-wider">
                        View Website
                      </a>
                    </div>

                    {/* Mockup Column (Desktop) */}
                    <div className="w-full lg:w-7/12 scale-100 sm:scale-75 md:scale-100 origin-top relative flex items-center justify-center max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:-ml-2">
                      <div className="w-[110%] aspect-[1078/799] bg-void border border-white/10 rounded-xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] relative overflow-hidden flex flex-col lg:translate-x-6">
                        <div className="h-6 border-b border-white/10 bg-white/5 flex items-center px-2 space-x-1.5 z-10 relative">
                          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
                          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
                          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
                          <span className="ml-4 font-mono text-[10px] text-white/30 tracking-widest">prep-dashboard</span>
                        </div>
                        {/* Inner Scroll Container */}
                        <div className="flex-1 relative overflow-hidden bg-gradient-to-br from-void to-white/5">
                          <div className="mockup-inner-1 flex w-[200%] h-full">
                            <div className="w-1/2 h-full flex items-center justify-center bg-void">
                              <img src="/SourcePrep-ss1.png" alt="SourcePrep Screen 1" className="w-full h-full object-cover" />
                            </div>
                            <div className="w-1/2 h-full flex items-center justify-center bg-void">
                              <img src="/SourcePrep-ss2.png" alt="SourcePrep Screen 2" className="w-full h-full object-cover" />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                  </div>
                </div>
              </div>

              {/* APP 02 - HomeColab */}
              <div className="app-panel-2 absolute inset-0 w-full h-full flex flex-col justify-center px-2 sm:px-4 md:px-8 max-md:justify-start max-md:pb-2">
                <div className="payload-card w-full relative glass-panel rounded-[2.5rem] p-2 md:p-3 overflow-hidden transition-all duration-700 hover:border-titan/50 hover:shadow-[0_0_40px_rgba(229,141,87,0.15)] md:bg-void/80 min-h-[500px] md:min-h-[650px] max-md:h-full max-md:rounded-[2rem] max-md:flex max-md:flex-col">
                  <div className="relative z-10 w-full h-full p-4 md:p-14 flex flex-col lg:flex-row gap-4 md:gap-8 lg:gap-12 items-center max-md:items-start max-md:min-h-0">

                    {/* Text Column */}
                    <div className="w-full lg:w-5/12 max-md:shrink-0">
                      <div className="flex flex-row items-center justify-between mb-6 gap-4">
                        <div className="flex items-center space-x-4">
                          <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                            <img src="/HomeColab-logo.png" alt="HomeColab Icon" className="w-full h-full object-cover" />
                          </div>
                          <div>
                            <span className="font-mono text-xs text-telemetry tracking-widest block">[ iOS / MOBILE ]</span>
                            <h4 className="font-sans text-2xl md:text-3xl font-bold text-ice">HomeColab</h4>
                          </div>
                        </div>
                        <a href="https://homecolab.app" target="_blank" rel="noreferrer" className="md:hidden flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-titan text-ice hover:text-void border border-white/10 hover:border-titan transition-all">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>

                      <p className="font-mono text-[11px] md:text-sm text-telemetry max-md:text-[#A1AAB5] mb-4 md:mb-6 leading-relaxed">
                        <strong className="text-ice">Find a Home... Together.</strong><br /><br />
                        HomeColab is the ultimate shared workspace for homebuyers and a silent intelligence engine for real estate agents. It replaces messy group texts and notification noise with a structured, intent-driven experience.
                      </p>

                      <div className="space-y-1.5 md:space-y-2 mb-4 md:mb-8 font-mono text-[10px] md:text-xs text-telemetry max-md:text-[#A1AAB5]">
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Universal Link Unfurling</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Partner Alignment & Heat Scores</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Smart Agent Briefings</p>
                      </div>

                      <a href="https://homecolab.app" target="_blank" rel="noreferrer" className="hidden md:inline-block font-mono text-xs bg-white/5 hover:bg-titan hover:text-void text-ice border border-white/10 hover:border-titan px-8 py-4 rounded-full transition-all uppercase tracking-wider">
                        View Website
                      </a>
                    </div>

                    {/* Mockup Column (Dual iOS) */}
                    <div className="w-full lg:w-7/12 h-[340px] md:h-[600px] scale-[0.65] sm:scale-90 md:scale-100 origin-top relative flex items-center justify-center gap-6 md:gap-10 pb-[1em] md:pb-[4em] max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:h-auto">
                      {/* Phone 1 */}
                      <div className="w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col z-20">
                        <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
                        <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
                          <div className="mockup-inner-2 flex flex-col h-[200%] w-full">
                            <div className="h-1/2 w-full flex items-center justify-center bg-void">
                              <img src="https://homecolab.app/screenshots/SS_01_the_list_.png" alt="HomeColab Screen 1" className="w-full h-full object-cover" />
                            </div>
                            <div className="h-1/2 w-full flex items-center justify-center bg-void">
                              <img src="https://homecolab.app/screenshots/SS_09_Rank-Compare2.png" alt="HomeColab Screen 3" className="w-full h-full object-cover" />
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Phone 2 (Slightly staggered on desktop) */}
                      <div className="w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col md:translate-y-16 z-10">
                        <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
                        <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
                          <div className="mockup-inner-2 flex flex-col h-[200%] w-full">
                            <div className="h-1/2 w-full flex items-center justify-center bg-void">
                              <img src="https://homecolab.app/screenshots/SS_02_webview-details.png" alt="HomeColab Screen 2" className="w-full h-full object-cover" />
                            </div>
                            <div className="h-1/2 w-full flex flex-col items-center justify-center bg-void">
                              <img src="https://homecolab.app/screenshots/SS_10_Rank-OurFavs.png" alt="HomeColab Screen 4" className="w-full h-full object-cover" />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                  </div>
                </div>
              </div>

              {/* APP 03 - DinnerVision */}
              <div className="app-panel-3 absolute inset-0 w-full h-full flex flex-col justify-center px-2 sm:px-4 md:px-8 max-md:justify-start max-md:pb-2">
                <div className="payload-card w-full relative glass-panel rounded-[2.5rem] p-2 md:p-3 overflow-hidden transition-all duration-700 hover:border-titan/50 hover:shadow-[0_0_40px_rgba(229,141,87,0.15)] md:bg-void/80 min-h-[500px] md:min-h-[650px] max-md:h-full max-md:rounded-[2rem] max-md:flex max-md:flex-col">
                  <div className="relative z-10 w-full h-full p-4 md:p-14 flex flex-col lg:flex-row gap-4 md:gap-8 lg:gap-12 items-center max-md:items-start max-md:min-h-0">

                    {/* Text Column */}
                    <div className="w-full lg:w-5/12 max-md:shrink-0">
                      <div className="flex flex-row items-center justify-between mb-6 gap-4">
                        <div className="flex items-center space-x-4">
                          <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                            <img src="/DinnerVision_v2.png" alt="DinnerVision Icon" className="w-full h-full object-cover" />
                          </div>
                          <div>
                            <span className="font-mono text-xs text-telemetry tracking-widest block">[ iOS / MOBILE ]</span>
                            <h4 className="font-sans text-2xl md:text-3xl font-bold text-ice">DinnerVision</h4>
                          </div>
                        </div>
                        <a href="https://dinner.vision" target="_blank" rel="noreferrer" className="md:hidden flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-titan text-ice hover:text-void border border-white/10 hover:border-titan transition-all">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>

                      <p className="font-mono text-[11px] md:text-sm text-telemetry max-md:text-[#A1AAB5] mb-4 md:mb-6 leading-relaxed">
                        <strong className="text-ice">Turn what you have into what you can cook.</strong><br /><br />
                        An intelligent mobile app designed to eliminate decision fatigue. Harnessing the power of computer vision, it instantly transforms the random ingredients in your fridge into delicious, actionable meal ideas.
                      </p>

                      <div className="space-y-1.5 md:space-y-2 mb-4 md:mb-8 font-mono text-[10px] md:text-xs text-telemetry max-md:text-[#A1AAB5]">
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Camera-First Ingredient Detection</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Smart Pantry Assumptions</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Custom Recipe Generation</p>
                      </div>

                      <a href="https://dinner.vision" target="_blank" rel="noreferrer" className="hidden md:inline-block font-mono text-xs bg-white/5 hover:bg-titan hover:text-void text-ice border border-white/10 hover:border-titan px-8 py-4 rounded-full transition-all uppercase tracking-wider">
                        View Website
                      </a>
                    </div>

                    {/* Mockup Column (Dual iOS) */}
                    <div className="w-full lg:w-7/12 h-[340px] md:h-[600px] scale-[0.65] sm:scale-90 md:scale-100 origin-top relative flex items-center justify-center gap-6 md:gap-10 pb-[1em] md:pb-[4em] max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:h-auto">
                      {/* Phone 1 */}
                      <div className="w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col z-20">
                        <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
                        <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
                          <div className="mockup-inner-3 flex flex-col h-[200%] w-full">
                            <div className="h-1/2 w-full bg-gradient-to-t from-void to-[#201005] flex items-center justify-center p-4">
                              <p className="font-mono flex-col flex text-center text-[10px] text-[#E58D57]"><span className="text-[20px] mb-2 drop-shadow-md">📸</span> SCAN</p>
                            </div>
                            <div className="h-1/2 w-full bg-[#050508] border-t border-white/5 flex items-center justify-center p-4">
                              <p className="font-mono text-[10px] text-telemetry">RECIPE</p>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Phone 2 (Slightly staggered on desktop) */}
                      <div className="w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col md:translate-y-16 z-10">
                        <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
                        <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
                          <div className="mockup-inner-3 flex flex-col h-[200%] w-full">
                            <div className="h-1/2 w-full bg-gradient-to-b from-void to-[#111118] flex items-center justify-center p-4">
                              <p className="font-mono text-[10px] text-telemetry">AI MATCH</p>
                            </div>
                            <div className="h-1/2 w-full bg-[#030305] border-t border-white/5 flex flex-col items-center justify-center p-4">
                              <p className="font-mono text-[10px] text-signal mb-3">COOK MODE</p>
                              <div className="w-full h-8 rounded-md bg-signal/10 border border-signal/20" />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                  </div>
                </div>
              </div>

              {/* APP 04 - DebateHaus */}
              <div className="app-panel-4 absolute inset-0 w-full h-full flex flex-col justify-center px-2 sm:px-4 md:px-8 max-md:justify-start max-md:pb-2">
                <div className="payload-card w-full relative glass-panel rounded-[2.5rem] p-2 md:p-3 overflow-hidden transition-all duration-700 hover:border-titan/50 hover:shadow-[0_0_40px_rgba(229,141,87,0.15)] md:bg-void/80 min-h-[500px] md:min-h-[650px] max-md:h-full max-md:rounded-[2rem] max-md:flex max-md:flex-col">
                  <div className="relative z-10 w-full h-full p-4 md:p-14 flex flex-col lg:flex-row gap-4 md:gap-8 lg:gap-12 items-center max-md:items-start max-md:min-h-0">

                    {/* Text Column */}
                    <div className="w-full lg:w-5/12 max-md:shrink-0">
                      <div className="flex flex-row items-center justify-between mb-6 gap-4">
                        <div className="flex items-center space-x-4">
                          <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                            <img src="/DebateHaus_LogoColor.png" alt="DebateHaus Icon" className="w-full h-full object-cover" />
                          </div>
                          <div>
                            <span className="font-mono text-xs text-telemetry tracking-widest block">[ iOS / MOBILE ]</span>
                            <h4 className="font-sans text-2xl md:text-3xl font-bold text-ice">DebateHaus</h4>
                          </div>
                        </div>
                        <a href="https://debate.haus" target="_blank" rel="noreferrer" className="md:hidden flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-titan text-ice hover:text-void border border-white/10 hover:border-titan transition-all">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>

                      <p className="font-mono text-[11px] md:text-sm text-telemetry max-md:text-[#A1AAB5] mb-4 md:mb-6 leading-relaxed">
                        <strong className="text-ice">Elevating the Digital Public Square.</strong><br /><br />
                        A video-first platform engineered to elevate the quality of online conversation. Moving beyond toxic comment threads, DebateHaus offers a structured, purpose-built format for civil, good-faith debate between creators, intellectuals, and institutions.
                      </p>

                      <div className="space-y-1.5 md:space-y-2 mb-4 md:mb-8 font-mono text-[10px] md:text-xs text-telemetry max-md:text-[#A1AAB5]">
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Structured Pre-Debate Negotiation</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Private Video Recording Environment</p>
                        <p className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> Co-Creator Publishing & Engagement</p>
                      </div>

                      <a href="https://debate.haus" target="_blank" rel="noreferrer" className="hidden md:inline-block font-mono text-xs bg-white/5 hover:bg-titan hover:text-void text-ice border border-white/10 hover:border-titan px-8 py-4 rounded-full transition-all uppercase tracking-wider">
                        View Website
                      </a>
                    </div>

                    {/* Mockup Column (Dual iOS) */}
                    <div className="w-full lg:w-7/12 h-[340px] md:h-[600px] scale-[0.65] sm:scale-90 md:scale-100 origin-top relative flex items-center justify-center gap-6 md:gap-10 pb-[1em] md:pb-[4em] max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:h-auto">
                      {/* Phone 1 */}
                      <div className="w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col z-20">
                        <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
                        <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
                          <div className="mockup-inner-4 flex flex-col h-[200%] w-full">
                            <div className="h-1/2 w-full bg-gradient-to-t from-void to-[#101030] flex items-center justify-center p-4">
                              <p className="font-mono flex-col flex text-center text-[10px] text-[#8B949E]"><span className="text-[20px] mb-2 drop-shadow-md">🎙️</span> INVITE</p>
                            </div>
                            <div className="h-1/2 w-full bg-[#050508] border-t border-white/5 flex items-center justify-center p-4">
                              <p className="font-mono text-[10px] text-telemetry">RECORDING</p>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Phone 2 (Slightly staggered on desktop) */}
                      <div className="w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col md:translate-y-16 z-10">
                        <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
                        <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
                          <div className="mockup-inner-4 flex flex-col h-[200%] w-full">
                            <div className="h-1/2 w-full bg-gradient-to-b from-void to-[#111118] flex items-center justify-center p-4">
                              <p className="font-mono text-[10px] text-telemetry">TERMS</p>
                            </div>
                            <div className="h-1/2 w-full bg-[#030305] border-t border-white/5 flex flex-col items-center justify-center p-4">
                              <p className="font-mono text-[10px] text-ice mb-3">PUBLISHED</p>
                              <div className="w-full h-12 rounded-lg bg-gradient-to-r from-void to-white/5 border border-white/5" />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function Manifesto() {
  const container = useRef();

  useGSAP(() => {
    gsap.from(".manifesto-neutral", {
      scrollTrigger: { trigger: container.current, start: "top 70%" },
      y: 20, opacity: 0, duration: 1
    });
    gsap.from(".manifesto-drama", {
      scrollTrigger: { trigger: container.current, start: "top 60%" },
      y: 40, opacity: 0, duration: 1.5, ease: "power3.out"
    });
  }, { scope: container });

  return (
    <>
      <div id="gap-to-manifesto" className="h-[150vh] pointer-events-none" />
      <section id="manifesto" ref={container} className="w-full h-[100dvh] relative z-10 flex flex-col items-center justify-center px-6 pointer-events-none">
        <div className="text-center w-full max-w-5xl mx-auto">
          <div className="manifesto-neutral relative w-screen ml-[calc(50%-50vw)] flex items-center justify-center mb-[5em] md:mb-[10em]" style={{ height: '2.5rem' }}>
            <div className="subtitle-mask-manifesto absolute w-screen h-full bg-[#030305]/95 backdrop-blur-sm border-y border-white/5 flex items-center justify-center translate-z-0"
              style={{ clipPath: 'polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)' }}>
              <p className="absolute w-screen text-center font-mono text-[#8B949E] max-md:text-[3.2vw] md:text-base tracking-widest uppercase" style={{ textShadow: '0 0 10px rgba(255,255,255,0.1)' }}>
                {/* We don't make games but we game design */}
                <span className="md:hidden">Making apps for us to experience the world</span>
                <span className="hidden md:inline">Making apps for humans to experience the world better</span>
              </p>
            </div>
          </div>
          <h2 className="manifesto-drama font-serif text-5xl md:text-7xl lg:text-8xl italic text-white leading-tight max-md:text-[3.5em] max-md:leading-[1.1] max-sm:px-0 max-md:px-[0.25em] max-md:mt-[0.6em] mb-[2.25em] drop-shadow-[1px_2px_10px_rgba(0,0,0,0.8)] md:drop-shadow-[1px_2px_30px_rgba(0,0,0,0.4)]">
            {/* App Design is a Puzzle & Strategy Game. */}
            Building the best things that can be imagined.
          </h2>
        </div>
      </section>
    </>
  );
}

function CommLink() {
  const [formState, setFormState] = useState('idle'); // idle | sending | sent | error

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormState('sending');

    const formData = new FormData(e.target);

    try {
      const res = await fetch('https://formspree.io/f/xpwdgvkn', {
        method: 'POST',
        body: formData,
        headers: { 'Accept': 'application/json' },
      });
      if (res.ok) {
        setFormState('sent');
        e.target.reset();
        setTimeout(() => setFormState('idle'), 5000);
      } else {
        setFormState('error');
        setTimeout(() => setFormState('idle'), 4000);
      }
    } catch {
      setFormState('error');
      setTimeout(() => setFormState('idle'), 4000);
    }
  };

  return (
    <>
      <div id="gap-to-commlink" className="h-[150vh] pointer-events-none" />
      <section id="commlink" className="w-full py-32 px-6 relative z-10">
        <div className="max-w-7xl mx-auto glass-panel rounded-[3rem] p-8 md:p-16">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">

            {/* FAQ */}
            <div>
              <div className="mb-12">
                <h3 className="font-mono text-sm tracking-[0.2em] text-titan mb-4">// CONTACT US</h3>
                <h2 className="font-sans font-bold text-3xl md:text-4xl uppercase tracking-wider">Support & Inquiries</h2>
              </div>

              <div className="space-y-6 font-mono text-sm">
                <div className="border border-white/10 rounded-xl p-6 bg-white/5 hover:bg-white/10 transition-colors">
                  <p className="text-titan mb-2 flex items-center"><MessageSquare className="w-4 h-4 mr-2" />&gt; QUERY: How do I restore purchases?</p>
                  <p className="text-telemetry pl-6">Access the settings menu within any app and tap 'Restore Purchases'. Standard App Store authentication is required.</p>
                </div>
                <div className="border border-white/10 rounded-xl p-6 bg-white/5 hover:bg-white/10 transition-colors">
                  <p className="text-titan mb-2 flex items-center"><MessageSquare className="w-4 h-4 mr-2" />&gt; QUERY: Can I access the beta?</p>
                  <p className="text-telemetry pl-6">Beta access is currently restricted. Join our waitlist below.</p>
                </div>
                <div className="border border-white/10 rounded-xl p-6 bg-white/5 hover:bg-white/10 transition-colors">
                  <p className="text-titan mb-2 flex items-center"><MessageSquare className="w-4 h-4 mr-2" />&gt; QUERY: Who builds these tools?</p>
                  <p className="text-telemetry pl-6">Magnetic Anomaly LLC is based in Brooklyn, NY.</p>
                </div>
              </div>
            </div>

            {/* Form */}
            <div className="bg-[#030305] border border-white/5 rounded-[2rem] p-8 font-mono">
              <h4 className="text-ice mb-8 pb-4 border-b border-white/10">Secure Contact Form</h4>
              <form className="space-y-6" onSubmit={handleSubmit}>
                <div>
                  <label className="block text-xs text-telemetry mb-2 tracking-widest uppercase">Email Address</label>
                  <input name="email" type="email" required className="w-full bg-void border border-white/10 rounded-xl p-4 text-ice focus:border-titan focus:outline-none focus:ring-1 focus:ring-titan transition-all" placeholder="Enter email..." />
                </div>
                <div>
                  <label className="block text-xs text-telemetry mb-2 tracking-widest uppercase">Subject</label>
                  <input name="subject" type="text" required className="w-full bg-void border border-white/10 rounded-xl p-4 text-ice focus:border-titan focus:outline-none focus:ring-1 focus:ring-titan transition-all" placeholder="How can we help?" />
                </div>
                <div>
                  <label className="block text-xs text-telemetry mb-2 tracking-widest uppercase">Message</label>
                  <textarea name="message" rows="4" required className="w-full bg-void border border-white/10 rounded-xl p-4 text-ice focus:border-titan focus:outline-none focus:ring-1 focus:ring-titan transition-all resize-none" placeholder="Type message..."></textarea>
                </div>
                <button
                  type="submit"
                  disabled={formState === 'sending'}
                  className={`w-full font-bold py-4 rounded-xl transition-all uppercase tracking-widest text-sm flex justify-center items-center group ${formState === 'sent'
                    ? 'bg-signal text-void'
                    : formState === 'error'
                      ? 'bg-red-500 text-white'
                      : 'bg-titan hover:bg-titan/80 text-void'
                    } ${formState === 'sending' ? 'opacity-70 cursor-wait' : ''}`}
                >
                  {formState === 'idle' && <>Send Message <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" /></>}
                  {formState === 'sending' && 'Encrypting...'}
                  {formState === 'sent' && 'Transmission Received.'}
                  {formState === 'error' && 'Transmission Failed. Retry.'}
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function SystemIndex() {
  const apps = [
    { name: 'SourcePrep', icon: '/SourcePrep-Logo2.png', url: 'https://sourceprep.io', tagline: 'The Context Engine for AI-Assisted Software Engineering.' },
    { name: 'HomeColab', icon: '/HomeColab-logo.png', url: 'https://homecolab.app', tagline: 'Find a Home... Together.' },
    { name: 'DinnerVision', icon: '/DinnerVision_v2.png', url: 'https://dinner.vision', tagline: 'Turn what you have into what you can cook.' },
    { name: 'DebateHaus', icon: '/DebateHaus_LogoColor.png', url: 'https://debate.haus', tagline: 'Elevating the Digital Public Square.' },
  ];

  return (
    <div id="gap-to-footer" className="min-h-[100vh] flex flex-col justify-center items-center px-6 relative z-10 w-full pb-24 md:pb-32">
      <div className="max-w-3xl w-full mt-32 md:mt-64 relative z-20">
        <div className="flex flex-col space-y-3">
          {apps.map((app) => (
            <div key={app.name} className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-6 rounded-2xl border border-white/5 bg-[#030305]/80 backdrop-blur-[7px] transition-colors duration-300 hover:border-white/10 gap-6 sm:gap-4">
              <div className="flex items-center space-x-6">
                <div className="w-16 h-16 sm:w-14 sm:h-14 rounded-xl overflow-hidden bg-void border border-white/10 flex-shrink-0">
                  <img src={app.icon} alt={app.name} className="w-full h-full object-cover" />
                </div>
                <div>
                  <h4 className="text-ice font-bold text-lg font-sans tracking-wide mb-1">{app.name}</h4>
                  <p className="text-telemetry/80 font-mono text-sm">{app.tagline}</p>
                </div>
              </div>
              <a href={app.url} target="_blank" rel="noreferrer" className="w-full sm:w-auto mt-2 sm:mt-0 px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-titan font-mono text-xs tracking-widest uppercase inline-flex items-center justify-center transition-all group shrink-0">
                Visit Website
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <footer className="relative z-10 border-t border-white/5 bg-[#030305]/80 backdrop-blur-[7px] pt-16 pb-8 px-6 font-mono text-xs text-telemetry">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8 mb-16 pt-12">
        <div>
          <h2 className="font-sans font-bold text-lg text-ice tracking-widest mb-4">MAGNETIC ANOMALY</h2>
          <p className="mb-2">ENTITY: MAGNETIC ANOMALY LLC.</p>
          <p>ORIGIN: CLINTON HILL, BROOKLYN</p>
          <p>COORDS: 40.6895° N, 73.9646° W</p>
        </div>
        <div className="md:text-right flex flex-col md:items-end justify-between">
          <div className="space-x-4">
            <a href="#" className="hover:text-ice transition-colors">Privacy Policy</a>
            <span className="text-white/20">|</span>
            <a href="#" className="hover:text-ice transition-colors">Terms of Service</a>
          </div>
        </div>
      </div>
      <div className="max-w-7xl mx-auto text-center border-t border-white/5 pt-8 opacity-50">
        &copy; {new Date().getFullYear()} Magnetic Anomaly LLC. All rights reserved.
      </div>
    </footer>
  );
}

// Lives inside Canvas + Suspense. Fires onReady on the first useFrame tick —
// guaranteeing textures have loaded (Suspense resolved), the WebGL pipeline
// is alive, and shaders compiled. One extra rAF gives the post-process Bloom
// pass time to render its first pass before we fade the veil.
function FirstFrameSignal({ onReady }) {
  const firedRef = useRef(false);
  useFrame(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    requestAnimationFrame(() => requestAnimationFrame(() => onReady()));
  });
  return null;
}

// Pure presentational component — opacity driven by `ready` prop. No useProgress.
// Has its own safety timeout so a missing onReady can't strand the user.
function LoadingVeil({ ready }) {
  const [safetyHide, setSafetyHide] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSafetyHide(true), 5000);
    return () => clearTimeout(t);
  }, []);

  const hidden = ready || safetyHide;

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none fixed inset-0 z-[9998] bg-void transition-opacity duration-700 ease-out ${hidden ? 'opacity-0' : 'opacity-100'}`}
    />
  );
}

// Memoized so App re-renders (when sceneReady flips) don't propagate into the
// Canvas tree. SaturnParticles passes array literals like rmaxRange={[20,45]}
// on every render, which invalidates MagneticParticles' useMemo deps and
// rebuilds the entire BufferGeometry — that was freezing the particle
// animation. onReady is stable (useCallback), so memo holds.
const SceneContents = memo(function SceneContents({ onReady }) {
  return (
    <>
      <EffectComposer disableNormalPass>
        <Bloom
          luminanceThreshold={0.2}
          mipmapBlur={true}
          intensity={2.0}
        />
      </EffectComposer>
      <Suspense fallback={null}>
        <SaturnScene />
        <FirstFrameSignal onReady={onReady} />
      </Suspense>
      <CameraRig />
    </>
  );
});

export default function App() {
  const appContainer = useRef();
  const [sceneReady, setSceneReady] = useState(false);
  const handleReady = useCallback(() => setSceneReady(true), []);

  // Safety: unblock Hero entrance even if FirstFrameSignal never fires
  // (e.g. WebGL unavailable). Veil has its own independent timeout.
  useEffect(() => {
    if (sceneReady) return;
    const t = setTimeout(() => setSceneReady(true), 5000);
    return () => clearTimeout(t);
  }, [sceneReady]);

  useGSAP(() => {
    // CONSTANTS FOR ORBITS (Hardcoded to match 3D Mesh positions)
    const saturnLookAt = new THREE.Vector3(-15, 0, -45);
    const saturnHighRadius = 120;
    const saturnHighY = 35;

    const enceladusLookAt = new THREE.Vector3(-40, -5, 405);
    const enceladusRadius = 15;

    const ceresLookAt = new THREE.Vector3(150, 20, -100);
    const ceresRadius = 50;

    const makemakeLookAt = new THREE.Vector3(-150, -30, 50);
    const makemakeRadius = 60;

    const HERO_START_ANGLE = Math.PI * 0.45;
    const HERO_END_ANGLE = Math.PI * 0.6;

    // --- 1. HERO (ORBIT ENCELADUS) ---
    const enceladusOrbit = { angle: HERO_START_ANGLE };

    const heroTl = gsap.timeline();
    heroTl.to(enceladusOrbit, { angle: HERO_END_ANGLE, ease: "none", duration: 1 }, 0);
    // 0: Start Hidden Left
    // 0.2 -> 0.4: Reveal Across Full Width
    heroTl.to(".subtitle-mask-hero", { clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)", ease: "power2.inOut", duration: 0.2 }, 0.2);
    // 0.8 -> 1.0: Hide Right
    heroTl.to(".subtitle-mask-hero", { clipPath: "polygon(100% 0%, 100% 0%, 100% 100%, 100% 100%)", ease: "power2.inOut", duration: 0.2 }, 0.8);

    ScrollTrigger.create({
      trigger: "#hero",
      start: "top top",
      end: "+=1500",
      pin: true,
      anticipatePin: 1,
      animation: heroTl,
      scrub: true,
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.x = enceladusLookAt.x + Math.cos(enceladusOrbit.angle) * enceladusRadius;
        globalCamera.pos.z = enceladusLookAt.z + Math.sin(enceladusOrbit.angle) * enceladusRadius;
        globalCamera.pos.y = enceladusLookAt.y;
        globalCamera.lookAt.copy(enceladusLookAt);
      }
    });

    // --- 2. TRAVEL (ENCELADUS TO CERES) ---
    const travel1Pos = {
      x: enceladusLookAt.x + Math.cos(HERO_END_ANGLE) * enceladusRadius,
      y: enceladusLookAt.y,
      z: enceladusLookAt.z + Math.sin(HERO_END_ANGLE) * enceladusRadius
    };
    const travel1LookAt = { x: enceladusLookAt.x, y: enceladusLookAt.y, z: enceladusLookAt.z };
    ScrollTrigger.create({
      trigger: "#gap-to-payloads", start: "top bottom", endTrigger: "#payloads", end: "top 20%", scrub: 1,
      animation: gsap.timeline()
        .to(travel1Pos, { x: ceresLookAt.x - ceresRadius, y: ceresLookAt.y, z: ceresLookAt.z, ease: "expo.inOut" }, 0)
        .to(travel1LookAt, { x: ceresLookAt.x, y: ceresLookAt.y, z: ceresLookAt.z, ease: "expo.inOut" }, 0),
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.copy(travel1Pos);
        globalCamera.lookAt.copy(travel1LookAt);
      }
    });

    // --- 3. PAYLOADS (ORBIT CERES) & HORIZONTAL SCROLL & INNER SCROLL ---
    const ceresOrbit = { angle: Math.PI }; // Start Left

    const payloadTl = gsap.timeline();
    // Total duration: 16 virtual units
    // 0 -> 16: Camera pans 180 degrees (PI to 0)
    payloadTl.to(ceresOrbit, { angle: 0, ease: "none", duration: 16 }, 0);

    // Initial State: hide off-screen panels to prevent backdrop-filter blur compositing
    gsap.set(".app-panel-2, .app-panel-3, .app-panel-4", { x: "105vw", visibility: "hidden" });

    // PANEL 1 (SourcePrep) Animation (0 -> 4)
    payloadTl.to(".mockup-inner-1", { xPercent: -50, ease: "power2.inOut", duration: 1.5 }, 0.5);
    // Swipe to Panel 2
    payloadTl.set(".app-panel-2", { visibility: "visible" }, 2.4);
    payloadTl.to(".app-panel-1", { x: "-105vw", ease: "power2.inOut", duration: 1.5 }, 2.5);
    payloadTl.to(".app-panel-2", { x: 0, ease: "power2.inOut", duration: 1.5 }, 2.5);
    payloadTl.set(".app-panel-1", { visibility: "hidden" }, 4.0);

    // PANEL 2 (HomeColab) Animation (4 -> 8)
    payloadTl.to(".mockup-inner-2", { yPercent: -50, ease: "power2.inOut", duration: 1.5 }, 4.5);
    // Swipe to Panel 3
    payloadTl.set(".app-panel-3", { visibility: "visible" }, 6.4);
    payloadTl.to(".app-panel-2", { x: "-105vw", ease: "power2.inOut", duration: 1.5 }, 6.5);
    payloadTl.to(".app-panel-3", { x: 0, ease: "power2.inOut", duration: 1.5 }, 6.5);
    payloadTl.set(".app-panel-2", { visibility: "hidden" }, 8.0);

    // PANEL 3 (DinnerVision) Animation (8 -> 12)
    payloadTl.to(".mockup-inner-3", { yPercent: -50, ease: "power2.inOut", duration: 1.5 }, 8.5);
    // Swipe to Panel 4
    payloadTl.set(".app-panel-4", { visibility: "visible" }, 10.4);
    payloadTl.to(".app-panel-3", { x: "-105vw", ease: "power2.inOut", duration: 1.5 }, 10.5);
    payloadTl.to(".app-panel-4", { x: 0, ease: "power2.inOut", duration: 1.5 }, 10.5);
    payloadTl.set(".app-panel-3", { visibility: "hidden" }, 12.0);

    // PANEL 4 (DebateHaus) Animation (12 -> 16)
    payloadTl.to(".mockup-inner-4", { yPercent: -50, ease: "power2.inOut", duration: 1.5 }, 12.5);
    // 14 -> 16: Wait and finish

    ScrollTrigger.create({
      trigger: "#payloads",
      start: "top top",
      end: "+=12000", // Double the previous duration
      pin: true,
      anticipatePin: 1,
      animation: payloadTl,
      scrub: 1,
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.x = ceresLookAt.x + Math.cos(ceresOrbit.angle) * ceresRadius;
        globalCamera.pos.z = ceresLookAt.z + Math.sin(ceresOrbit.angle) * ceresRadius;
        globalCamera.pos.y = ceresLookAt.y;
        globalCamera.lookAt.copy(ceresLookAt);
      }
    });

    // Independent entrace for payload cards (No Scrub, just entrance stagger)
    // Removed to fix a bug where cards get stuck at opacity: 0
    // gs ap.from(".payload-card", { ... });

    // --- 4. TRAVEL (CERES TO SATURN HIGH VIEW) ---
    const travel2Pos = { x: ceresLookAt.x, y: ceresLookAt.y, z: ceresLookAt.z + ceresRadius };
    const travel2LookAt = { x: ceresLookAt.x, y: ceresLookAt.y, z: ceresLookAt.z };
    ScrollTrigger.create({
      trigger: "#gap-to-manifesto", start: "top bottom", endTrigger: "#manifesto", end: "center center", scrub: 1,
      animation: gsap.timeline()
        .to(travel2Pos, { x: saturnLookAt.x, y: saturnHighY, z: saturnLookAt.z + saturnHighRadius, ease: "expo.inOut" }, 0)
        .to(travel2LookAt, { x: saturnLookAt.x, y: saturnLookAt.y, z: saturnLookAt.z, ease: "expo.inOut" }, 0),
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.copy(travel2Pos);
        globalCamera.lookAt.copy(travel2LookAt);
      }
    });

    // --- 5. MANIFESTO (ORBIT SATURN HIGH VIEW) ---
    const saturnHighOrbit = { angle: Math.PI / 2 }; // Start Front

    const manifestoTl = gsap.timeline();
    manifestoTl.to(saturnHighOrbit, { angle: 0, ease: "none", duration: 1 }, 0);
    // 0: Start Hidden Left
    // 0.2 -> 0.4: Reveal Across Full Width
    manifestoTl.to(".subtitle-mask-manifesto", { clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)", ease: "power2.inOut", duration: 0.2 }, 0.2);
    // 0.8 -> 1.0: Hide Right
    manifestoTl.to(".subtitle-mask-manifesto", { clipPath: "polygon(100% 0%, 100% 0%, 100% 100%, 100% 100%)", ease: "power2.inOut", duration: 0.2 }, 0.8);

    ScrollTrigger.create({
      trigger: "#manifesto",
      start: "center center",
      end: "+=1500",
      pin: true,
      anticipatePin: 1,
      animation: manifestoTl,
      scrub: true,
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.x = saturnLookAt.x + Math.cos(saturnHighOrbit.angle) * saturnHighRadius;
        globalCamera.pos.z = saturnLookAt.z + Math.sin(saturnHighOrbit.angle) * saturnHighRadius;
        globalCamera.pos.y = saturnHighY;
        globalCamera.lookAt.copy(saturnLookAt);
      }
    });

    // --- 6. TRAVEL (SATURN HIGH VIEW TO MAKEMAKE) ---
    const travel3Pos = { x: saturnLookAt.x + saturnHighRadius, y: saturnHighY, z: saturnLookAt.z };
    const travel3LookAt = { x: saturnLookAt.x, y: saturnLookAt.y, z: saturnLookAt.z };
    ScrollTrigger.create({
      trigger: "#gap-to-commlink", start: "top bottom", endTrigger: "#commlink", end: "center center", scrub: 1,
      animation: gsap.timeline()
        .to(travel3Pos, { x: makemakeLookAt.x + makemakeRadius, y: makemakeLookAt.y, z: makemakeLookAt.z, ease: "expo.inOut" }, 0)
        .to(travel3LookAt, { x: makemakeLookAt.x, y: makemakeLookAt.y, z: makemakeLookAt.z, ease: "expo.inOut" }, 0),
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.copy(travel3Pos);
        globalCamera.lookAt.copy(travel3LookAt);
      }
    });

    // --- 7. COMMLINK (ORBIT MAKEMAKE) ---
    const makemakeOrbit = { angle: 0 }; // Start aligned to the right
    ScrollTrigger.create({
      trigger: "#commlink",
      start: "center center",
      end: "+=1500",
      pin: true,
      anticipatePin: 1,
      animation: gsap.to(makemakeOrbit, { angle: -Math.PI / 2, ease: "none" }),
      scrub: true,
      onUpdate: (self) => {
        if (!self.isActive) return;
        globalCamera.pos.x = makemakeLookAt.x + Math.cos(makemakeOrbit.angle) * makemakeRadius;
        globalCamera.pos.z = makemakeLookAt.z + Math.sin(makemakeOrbit.angle) * makemakeRadius;
        globalCamera.pos.y = makemakeLookAt.y;
        globalCamera.lookAt.copy(makemakeLookAt);
      }
    });

    // --- 8. FOOTER SLOW REVEAL ---
    gsap.from("footer", {
      yPercent: 100,
      ease: "none",
      scrollTrigger: {
        trigger: "#gap-to-footer",
        start: "top bottom",
        end: "bottom bottom",
        scrub: 1
      }
    });

  }, { scope: appContainer });

  return (
    <div ref={appContainer} className="relative w-full overflow-x-hidden selection:bg-titan/30 selection:text-titan">
      {/* WebGL Canvas sits behind everything */}
      <div className="fixed inset-0 z-0 bg-void pointer-events-none">
        <Canvas
          camera={{ position: [0, 0, 15], fov: 45, far: 5000 }}
          gl={{ antialias: false, powerPreference: "high-performance" }}
          dpr={[1, 1.5]}
        >
          <SceneContents onReady={handleReady} />
        </Canvas>
      </div>

      <LoadingVeil ready={sceneReady} />

      <Navbar />
      <Hero ready={sceneReady} />
      <Payloads />
      <Manifesto />
      <CommLink />
      <SystemIndex />
      <Footer />
    </div>
  );
}
