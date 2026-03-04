import * as THREE from 'three';
import fs from 'fs';

const fsSource = `
varying vec3 vColor;
varying float vAlpha;

void main() {
  vec2 center = gl_PointCoord - vec2(0.5);
  float distsq = dot(center, center);
  float alpha = exp(-distsq * 15.0); 
  
  if (alpha < 0.01) discard;

  gl_FragColor = vec4(vColor, alpha * vAlpha);
}
`;

const vsSource = `
uniform float uTime;
uniform vec3 uColorNorth;
uniform vec3 uColorEquator;
uniform vec3 uColorSouth;
uniform float uPointSize;

attribute float aPhase;
attribute float aSpeed;
attribute float aPhi;
attribute float aRmax;
attribute float aDirection;
attribute float aOffset;

varying vec3 vColor;
varying float vAlpha;

void main() {
  float cycleTime = mod(uTime, 19.0);
  
  float modePolarBurst = smoothstep(0.0, 1.0, cycleTime) * (1.0 - smoothstep(3.0, 4.0, cycleTime));
  float modeDualStream = smoothstep(3.0, 4.0, cycleTime) * (1.0 - smoothstep(10.0, 11.0, cycleTime));
  float modeRandomEruption = smoothstep(10.0, 11.0, cycleTime) * (1.0 - smoothstep(13.0, 14.0, cycleTime));
  float modeQuiet = smoothstep(13.0, 14.0, cycleTime) * (1.0 - smoothstep(18.0, 19.0, cycleTime));

  float currentPhase = mod(aPhase + (uTime * aSpeed * 0.1) + aOffset, 1.0);
  
  float dir = mix(1.0, aDirection, modeDualStream + modeQuiet); 
  dir = mix(dir, aDirection, modeRandomEruption); 

  float theta = currentPhase * 3.14159265359;
  if (dir < 0.0) {
      theta = (1.0 - currentPhase) * 3.14159265359;
  }

  float randomThetaOffset = fract(sin(aPhi * 12.9898 + aOffset * 78.233) * 43758.5453) * 3.14159265359;
  theta = mix(theta, mix(randomThetaOffset, theta, currentPhase), modeRandomEruption);
  
  float currentRmax = aRmax * (1.0 + 0.1 * sin(uTime * 0.5 + aPhi));

  float r = currentRmax * sin(theta) * sin(theta);
  vec3 localPos = vec3(
    r * sin(theta) * cos(aPhi),
    r * cos(theta),
    r * sin(theta) * sin(aPhi)
  );

  vec4 modelPosition = modelMatrix * vec4(localPos, 1.0);
  vec4 viewPosition = viewMatrix * modelPosition;
  vec4 projectedPosition = projectionMatrix * viewPosition;

  gl_Position = projectedPosition;
  
  gl_PointSize = uPointSize * (300.0 / -viewPosition.z); 
  gl_PointSize = clamp(gl_PointSize, 1.0, 50.0);
  
  vec3 colorMixed = mix(uColorNorth, uColorEquator, smoothstep(0.0, 0.5, currentPhase));
  colorMixed = mix(colorMixed, uColorSouth, smoothstep(0.5, 1.0, currentPhase));
  vColor = colorMixed;

  vAlpha = sin(currentPhase * 3.14159265359);
  
  vAlpha *= mix(1.0, 0.3, modeQuiet);
  
  float eruptionIntensity = fract(sin(aOffset * 100.0) * 1000.0);
  vAlpha *= mix(1.0, eruptionIntensity, modeRandomEruption);
}
`;

const gl = require('gl')(1, 1);
if (!gl) {
  console.log('Failed to init headless webgl');
  process.exit(1);
}

const vs = gl.createShader(gl.VERTEX_SHADER);
gl.shaderSource(vs, vsSource);
gl.compileShader(vs);
if (!gl.getShaderParameter(vs, gl.COMPILE_STATUS)) {
  console.error('Vertex Shader Error:', gl.getShaderInfoLog(vs));
} else {
  console.log('Vertex Shader OK');
}

const fsCompiled = gl.createShader(gl.FRAGMENT_SHADER);
gl.shaderSource(fsCompiled, fsSource);
gl.compileShader(fsCompiled);
if (!gl.getShaderParameter(fsCompiled, gl.COMPILE_STATUS)) {
  console.error('Fragment Shader Error:', gl.getShaderInfoLog(fsCompiled));
} else {
  console.log('Fragment Shader OK');
}

const prog = gl.createProgram();
gl.attachShader(prog, vs);
gl.attachShader(prog, fsCompiled);
gl.linkProgram(prog);
if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
  console.error('Program Link Error:', gl.getProgramInfoLog(prog));
} else {
  console.log('Program Linked OK');
}

