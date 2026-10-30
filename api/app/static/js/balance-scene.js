import * as THREE from 'three';
import { pointerTilt, damp } from './balance-math.js';

export function initBalanceScene(container) {
  if (!container) return { destroy() {} };
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (_) {
    return { destroy() {} };
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  camera.position.set(0, 4.6, 14.5);
  camera.lookAt(0, 3.1, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.setClearColor(0x000000, 0);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.domElement.setAttribute('aria-hidden', 'true');
  container.appendChild(renderer.domElement);

  const metal = new THREE.MeshStandardMaterial({ color: 0xc87b24, metalness: 0.82, roughness: 0.28 });
  const lightMetal = new THREE.MeshStandardMaterial({ color: 0xeaae35, metalness: 0.72, roughness: 0.3 });
  const darkMetal = new THREE.MeshStandardMaterial({ color: 0x71330f, metalness: 0.78, roughness: 0.34 });
  const ink = new THREE.MeshStandardMaterial({ color: 0x251c17, metalness: 0.35, roughness: 0.46 });
  const orange = new THREE.MeshStandardMaterial({ color: 0xb85516, metalness: 0.45, roughness: 0.36 });
  const resources = new Set();
  const track = object => {
    object.traverse(child => {
      if (child.geometry) resources.add(child.geometry);
      if (child.material) resources.add(child.material);
    });
    return object;
  };
  const mesh = (geometry, material, parent, position = [0, 0, 0]) => {
    const item = new THREE.Mesh(geometry, material);
    item.position.set(...position);
    item.castShadow = true;
    item.receiveShadow = true;
    parent.add(item);
    resources.add(geometry);
    return item;
  };
  const cylinder = (parent, radius, height, position, material = metal) =>
    mesh(new THREE.CylinderGeometry(radius, radius, height, 32), material, parent, position);

  const instrument = new THREE.Group();
  instrument.position.y = -1.15;
  scene.add(instrument);
  const baseProfile = [
    [0, 0], [2.1, 0], [2.15, .16], [1.95, .28], [1.8, .34], [1.75, .48],
    [1.45, .58], [1.35, .76], [1.05, .88], [.92, 1.04], [.58, 1.15], [.5, 1.25], [0, 1.25],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  mesh(new THREE.LatheGeometry(baseProfile, 64), darkMetal, instrument);
  const columnProfile = [
    [0, 0], [.48, 0], [.5, .18], [.34, .34], [.3, 1.2], [.42, 1.38], [.46, 1.55],
    [.32, 1.72], [.26, 3.35], [.38, 3.55], [.38, 3.75], [0, 3.75],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  mesh(new THREE.LatheGeometry(columnProfile, 48), metal, instrument, [0, 1.05, 0]);
  cylinder(instrument, .62, .16, [0, 1.2, 0], lightMetal);
  cylinder(instrument, .5, .14, [0, 4.63, 0], lightMetal);
  mesh(new THREE.ConeGeometry(.16, .65, 32), lightMetal, instrument, [0, 5.75, 0]);

  const beamPivot = new THREE.Group();
  beamPivot.position.set(0, 5.05, 0);
  instrument.add(beamPivot);
  const beamCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-3.65, -.12, 0), new THREE.Vector3(-2.3, .14, 0),
    new THREE.Vector3(-1.05, .34, 0), new THREE.Vector3(0, .2, 0),
    new THREE.Vector3(1.05, .34, 0), new THREE.Vector3(2.3, .14, 0), new THREE.Vector3(3.65, -.12, 0),
  ]);
  mesh(new THREE.TubeGeometry(beamCurve, 80, .115, 12, false), metal, beamPivot);
  const hub = cylinder(beamPivot, .36, .32, [0, .12, 0], darkMetal);
  hub.rotation.x = Math.PI / 2;
  const hubFace = cylinder(beamPivot, .23, .35, [0, .12, 0], lightMetal);
  hubFace.rotation.x = Math.PI / 2;

  function makeHanger(side) {
    const hanger = new THREE.Group();
    hanger.position.set(side * 3.55, -.1, 0);
    beamPivot.add(hanger);
    for (const z of [-.72, .72]) {
      const curve = new THREE.LineCurve3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -2.25, z));
      mesh(new THREE.TubeGeometry(curve, 1, .025, 8, false), darkMetal, hanger);
      for (let index = 0; index < 13; index += 1) {
        const ring = mesh(new THREE.TorusGeometry(.055, .012, 5, 10), lightMetal, hanger, [0, -.12 - index * .165, z * index / 13]);
        ring.rotation.y = index % 2 ? Math.PI / 2 : 0;
      }
    }
    const panProfile = [[0, 0], [1.18, 0], [1.16, .12], [.96, .32], [.62, .48], [0, .56]]
      .map(([x, y]) => new THREE.Vector2(x, y));
    const pan = mesh(new THREE.LatheGeometry(panProfile, 48), side < 0 ? orange : lightMetal, hanger, [0, -2.68, 0]);
    pan.material.side = THREE.DoubleSide;
    const rim = mesh(new THREE.TorusGeometry(1.18, .045, 10, 48), darkMetal, hanger, [0, -2.68, 0]);
    rim.rotation.x = Math.PI / 2;
    return hanger;
  }
  const leftHanger = makeHanger(-1);
  const rightHanger = makeHanger(1);

  for (let index = 0; index < 3; index += 1) {
    const coin = cylinder(leftHanger, .37, .09, [-.42 + index * .39, -2.02 + index * .04, .05 * index], lightMetal);
    coin.rotation.x = Math.PI / 2.7;
    const inset = mesh(new THREE.TorusGeometry(.25, .018, 6, 24), darkMetal, coin, [0, .055, 0]);
    inset.rotation.x = Math.PI / 2;
  }
  const tag = mesh(new THREE.BoxGeometry(.68, .08, .46), orange, leftHanger, [.4, -1.96, -.35]);
  tag.rotation.y = -.35;
  mesh(new THREE.TorusGeometry(.07, .018, 6, 16), lightMetal, tag, [-.23, .07, 0]);

  const chip = mesh(new THREE.BoxGeometry(1.05, .18, .9), ink, rightHanger, [0, -2.0, 0]);
  for (const side of [-1, 1]) {
    for (let index = -2; index <= 2; index += 1) {
      mesh(new THREE.BoxGeometry(.16, .06, .045), lightMetal, chip, [index * .18, 0, side * .49]);
      mesh(new THREE.BoxGeometry(.045, .06, .16), lightMetal, chip, [side * .57, 0, index * .15]);
    }
  }
  const nodePositions = [[-.27, .15, -.2], [.27, .15, -.2], [0, .15, .24]];
  nodePositions.forEach(position => mesh(new THREE.SphereGeometry(.09, 16, 12), lightMetal, chip, position));
  for (const [a, b] of [[0, 2], [1, 2]]) {
    const curve = new THREE.LineCurve3(new THREE.Vector3(...nodePositions[a]), new THREE.Vector3(...nodePositions[b]));
    mesh(new THREE.TubeGeometry(curve, 1, .025, 6, false), lightMetal, chip);
  }

  const floor = mesh(new THREE.CircleGeometry(4.2, 64), new THREE.ShadowMaterial({ color: 0x3c210e, opacity: .16 }), scene, [0, -1.13, 0]);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(new THREE.HemisphereLight(0xfff5df, 0x6b3519, 2.2));
  const key = new THREE.DirectionalLight(0xffe6b0, 4.2);
  key.position.set(-4, 9, 7);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xb85516, 2.2);
  rim.position.set(5, 4, -5);
  scene.add(rim);
  track(instrument);

  let target = { beam: 0, pitch: 0 };
  let current = { beam: 0, pitch: 0 };
  let frame = 0;
  let previous = performance.now();
  let destroyed = false;
  const onPointer = event => {
    if (reducedMotion.matches || event.pointerType === 'touch') return;
    target = pointerTilt(event.clientX, event.clientY, window.innerWidth, window.innerHeight);
  };
  const reset = () => { target = { beam: 0, pitch: 0 }; };
  const resize = () => {
    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
  };
  const animate = now => {
    if (destroyed) return;
    const delta = Math.min(.05, (now - previous) / 1000);
    previous = now;
    current.beam = damp(current.beam, target.beam, 5.5, delta);
    current.pitch = damp(current.pitch, target.pitch, 4, delta);
    beamPivot.rotation.z = current.beam;
    leftHanger.rotation.z = -current.beam;
    rightHanger.rotation.z = -current.beam;
    instrument.rotation.x = current.pitch;
    renderer.render(scene, camera);
    if (!document.hidden && !reducedMotion.matches) frame = requestAnimationFrame(animate);
  };
  const start = () => {
    cancelAnimationFrame(frame);
    previous = performance.now();
    if (reducedMotion.matches) {
      current = { beam: 0, pitch: 0 };
      beamPivot.rotation.z = 0;
      leftHanger.rotation.z = 0;
      rightHanger.rotation.z = 0;
      renderer.render(scene, camera);
    } else if (!document.hidden) {
      frame = requestAnimationFrame(animate);
    }
  };
  const onVisibility = () => { if (document.hidden) cancelAnimationFrame(frame); else start(); };
  window.addEventListener('pointermove', onPointer, { passive: true });
  window.addEventListener('blur', reset);
  document.addEventListener('mouseleave', reset);
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('resize', resize);
  reducedMotion.addEventListener('change', start);
  resize();
  start();
  const fallback = container.querySelector('img');
  if (fallback) fallback.hidden = true;

  return {
    destroy() {
      destroyed = true;
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', onPointer);
      window.removeEventListener('blur', reset);
      document.removeEventListener('mouseleave', reset);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('resize', resize);
      reducedMotion.removeEventListener('change', start);
      resources.forEach(resource => resource.dispose?.());
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
