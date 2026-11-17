/**
 * Clipwise 3D Neon Particle Mesh Wave Engine (Concept 1)
 * High-performance WebGL undulating fluid particle matrix with mouse-reactive wave physics.
 */

(function () {
  const canvas = document.getElementById('bg3d');
  if (!canvas || typeof THREE === 'undefined') return;

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    1,
    3000
  );
  camera.position.set(0, 140, 520);

  const renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // --- High-Resolution Glowing Neon Particle Texture ---
  function createParticleTexture() {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createRadialGradient(
      size / 2, size / 2, 0,
      size / 2, size / 2, size / 2
    );
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    gradient.addColorStop(0.18, 'rgba(168, 85, 247, 0.95)'); // Electric Violet
    gradient.addColorStop(0.45, 'rgba(99, 102, 241, 0.5)'); // Indigo
    gradient.addColorStop(0.7, 'rgba(6, 182, 212, 0.25)'); // Cyan
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);

    return new THREE.CanvasTexture(canvas);
  }

  // --- 3D Neon Particle Wave Matrix ---
  const SEPARATION_X = 16;
  const SEPARATION_Y = 16;
  const AMOUNT_X = 85;
  const AMOUNT_Y = 85;
  const numParticles = AMOUNT_X * AMOUNT_Y;

  const positions = new Float32Array(numParticles * 3);
  const colors = new Float32Array(numParticles * 3);

  const colorViolet = new THREE.Color(0xa855f7); // Violet
  const colorCyan = new THREE.Color(0x06b6d4);   // Cyan
  const colorPink = new THREE.Color(0xec4899);   // Neon Magenta

  let i = 0, j = 0;
  for (let ix = 0; ix < AMOUNT_X; ix++) {
    for (let iy = 0; iy < AMOUNT_Y; iy++) {
      positions[i] = ix * SEPARATION_X - (AMOUNT_X * SEPARATION_X) / 2;
      positions[i + 1] = 0;
      positions[i + 2] = iy * SEPARATION_Y - (AMOUNT_Y * SEPARATION_Y) / 2;

      // Diagonal gradient color flow
      const t = (ix + iy) / (AMOUNT_X + AMOUNT_Y);
      const mixedColor = t < 0.5 
        ? colorViolet.clone().lerp(colorPink, t * 2)
        : colorPink.clone().lerp(colorCyan, (t - 0.5) * 2);

      colors[j] = mixedColor.r;
      colors[j + 1] = mixedColor.g;
      colors[j + 2] = mixedColor.b;

      i += 3;
      j += 3;
    }
  }

  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const particleMaterial = new THREE.PointsMaterial({
    size: 7.5,
    map: createParticleTexture(),
    vertexColors: true,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const particleMesh = new THREE.Points(particleGeometry, particleMaterial);
  particleMesh.position.y = -90;
  particleMesh.rotation.x = 0.25; // Gentle tilt forward for dramatic 3D perspective
  scene.add(particleMesh);

  // --- Volumetric Point Lights ---
  const lightViolet = new THREE.PointLight(0xa855f7, 2.5, 900);
  lightViolet.position.set(0, 200, 300);
  scene.add(lightViolet);

  const lightCyan = new THREE.PointLight(0x06b6d4, 2, 700);
  lightCyan.position.set(-250, -50, 200);
  scene.add(lightCyan);

  // --- Interactive Mouse Parallax & Wave Reactivity ---
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;
  const windowHalfX = window.innerWidth / 2;
  const windowHalfY = window.innerHeight / 2;

  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - windowHalfX) * 0.2;
    mouseY = (e.clientY - windowHalfY) * 0.2;
  }, { passive: true });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  });

  // --- Fluid Animation Loop ---
  let count = 0;

  function animate() {
    requestAnimationFrame(animate);

    count += 0.038;

    // Smooth camera mouse parallax easing
    targetX += (mouseX - targetX) * 0.04;
    targetY += (-mouseY - targetY) * 0.04;
    camera.position.x = targetX;
    camera.position.y = 140 + targetY * 0.5;
    camera.lookAt(0, -20, 0);

    // Dynamic wave elevation physics
    const pos = particleMesh.geometry.attributes.position.array;
    let idx = 0;
    for (let ix = 0; ix < AMOUNT_X; ix++) {
      for (let iy = 0; iy < AMOUNT_Y; iy++) {
        // Compound harmonic wave equations for natural fluid undulation
        pos[idx + 1] =
          Math.sin((ix + count) * 0.32) * 32 +
          Math.cos((iy + count * 0.75) * 0.35) * 32 +
          Math.sin((ix + iy + count * 1.2) * 0.18) * 18;
        idx += 3;
      }
    }
    particleMesh.geometry.attributes.position.needsUpdate = true;
    particleMesh.rotation.y = Math.sin(count * 0.06) * 0.04;

    renderer.render(scene, camera);
  }

  animate();
})();
