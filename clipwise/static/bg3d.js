/**
 * Clipwise Interactive 3D WebGL Background Engine
 * Combines undulating neon particle mesh waves with floating 3D vertical glass reels and mouse parallax.
 */

(function () {
  const canvas = document.getElementById('bg3d');
  if (!canvas || typeof THREE === 'undefined') return;

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(
    65,
    window.innerWidth / window.innerHeight,
    1,
    2000
  );
  camera.position.set(0, 80, 420);

  const renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // --- 1. Soft Circular Neon Particle Texture Generator ---
  function createParticleTexture() {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createRadialGradient(
      size / 2, size / 2, 0,
      size / 2, size / 2, size / 2
    );
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    gradient.addColorStop(0.2, 'rgba(168, 85, 247, 0.9)'); // violet
    gradient.addColorStop(0.6, 'rgba(99, 102, 241, 0.4)'); // indigo
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);

    const texture = new THREE.CanvasTexture(canvas);
    return texture;
  }

  // --- 2. 3D Neon Particle Mesh Wave ---
  const SEPARATION_X = 18;
  const SEPARATION_Y = 18;
  const AMOUNT_X = 65;
  const AMOUNT_Y = 65;
  const numParticles = AMOUNT_X * AMOUNT_Y;

  const positions = new Float32Array(numParticles * 3);
  const colors = new Float32Array(numParticles * 3);

  const color1 = new THREE.Color(0x6366f1); // Indigo
  const color2 = new THREE.Color(0xec4899); // Neon Pink
  const color3 = new THREE.Color(0x06b6d4); // Cyan

  let i = 0, j = 0;
  for (let ix = 0; ix < AMOUNT_X; ix++) {
    for (let iy = 0; iy < AMOUNT_Y; iy++) {
      positions[i] = ix * SEPARATION_X - (AMOUNT_X * SEPARATION_X) / 2; // x
      positions[i + 1] = 0; // y (dynamic in animate)
      positions[i + 2] = iy * SEPARATION_Y - (AMOUNT_Y * SEPARATION_Y) / 2; // z

      // Blend gradient colors along wave diagonal
      const t = (ix + iy) / (AMOUNT_X + AMOUNT_Y);
      const mixedColor = t < 0.5 
        ? color1.clone().lerp(color2, t * 2) 
        : color2.clone().lerp(color3, (t - 0.5) * 2);

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
    size: 6.5,
    map: createParticleTexture(),
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const particleSystem = new THREE.Points(particleGeometry, particleMaterial);
  particleSystem.position.y = -120;
  scene.add(particleSystem);

  // --- 3. Floating 3D Translucent 9:16 Glass Reels ---
  const glassCardsGroup = new THREE.Group();
  scene.add(glassCardsGroup);

  const cardGeometry = new THREE.PlaneGeometry(36, 64);
  const cardBorderGeo = new THREE.EdgesGeometry(cardGeometry);

  const cardConfigs = [
    { x: -280, y: 70, z: -100, rotY: 0.35, rotX: 0.1, speed: 0.8 },
    { x: 300, y: 90, z: -80, rotY: -0.4, rotX: -0.05, speed: 1.1 },
    { x: -340, y: -40, z: 20, rotY: 0.45, rotX: -0.15, speed: 0.9 },
    { x: 330, y: -20, z: 40, rotY: -0.3, rotX: 0.12, speed: 1.2 },
    { x: -180, y: 160, z: -160, rotY: 0.2, rotX: 0.2, speed: 0.7 },
    { x: 210, y: 170, z: -140, rotY: -0.25, rotX: -0.1, speed: 1.0 },
  ];

  const cards = [];

  cardConfigs.forEach((cfg) => {
    // Glass plane
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0x1a1e38,
      transparent: true,
      opacity: 0.22,
      roughness: 0.1,
      metalness: 0.1,
      clearcoat: 1.0,
      side: THREE.DoubleSide,
    });
    const cardMesh = new THREE.Mesh(cardGeometry, glassMat);

    // Neon glowing border
    const borderMat = new THREE.LineBasicMaterial({
      color: 0xa855f7,
      transparent: true,
      opacity: 0.45,
    });
    const borderLines = new THREE.LineSegments(cardBorderGeo, borderMat);
    cardMesh.add(borderLines);

    cardMesh.position.set(cfg.x, cfg.y, cfg.z);
    cardMesh.rotation.set(cfg.rotX, cfg.rotY, 0);

    glassCardsGroup.add(cardMesh);
    cards.push({ mesh: cardMesh, initialY: cfg.y, cfg: cfg });
  });

  // --- 4. Volumetric Ambient Lights ---
  const light1 = new THREE.PointLight(0xa855f7, 2, 600);
  light1.position.set(200, 200, 200);
  scene.add(light1);

  const light2 = new THREE.PointLight(0x06b6d4, 1.8, 600);
  light2.position.set(-200, -100, 150);
  scene.add(light2);

  // --- 5. Interactive Mouse Parallax ---
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;
  const windowHalfX = window.innerWidth / 2;
  const windowHalfY = window.innerHeight / 2;

  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - windowHalfX) * 0.15;
    mouseY = (e.clientY - windowHalfY) * 0.15;
  }, { passive: true });

  // Handle window resize smoothly
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  });

  // --- 6. Render Animation Loop ---
  let count = 0;

  function animate() {
    requestAnimationFrame(animate);

    count += 0.035;

    // Smooth camera mouse parallax easing
    targetX += (mouseX - targetX) * 0.05;
    targetY += (-mouseY - targetY) * 0.05;
    camera.position.x = targetX;
    camera.position.y = 80 + targetY * 0.6;
    camera.lookAt(0, 0, 0);

    // Undulate the 3D particle mesh wave
    const pos = particleSystem.geometry.attributes.position.array;
    let idx = 0;
    for (let ix = 0; ix < AMOUNT_X; ix++) {
      for (let iy = 0; iy < AMOUNT_Y; iy++) {
        // Multi-frequency wave formula
        pos[idx + 1] =
          Math.sin((ix + count) * 0.35) * 28 +
          Math.cos((iy + count * 0.8) * 0.4) * 28 +
          Math.sin((ix + iy + count) * 0.2) * 15;
        idx += 3;
      }
    }
    particleSystem.geometry.attributes.position.needsUpdate = true;
    particleSystem.rotation.y = Math.sin(count * 0.08) * 0.06;

    // Gently float and orbit the 3D 9:16 glass cards
    cards.forEach((c) => {
      c.mesh.position.y = c.initialY + Math.sin(count * c.cfg.speed) * 12;
      c.mesh.rotation.y = c.cfg.rotY + Math.sin(count * 0.4 * c.cfg.speed) * 0.08;
      c.mesh.rotation.z = Math.cos(count * 0.3 * c.cfg.speed) * 0.04;
    });

    renderer.render(scene, camera);
  }

  animate();
})();
