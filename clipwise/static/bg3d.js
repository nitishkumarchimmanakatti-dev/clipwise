/**
 * Clipwise 3D Motion Background Engine using Three.js
 * Creates an undulating 3D particle wave terrain with floating geometric nodes
 * and mouse-responsive 3D camera parallax.
 */

(function () {
  const canvas = document.getElementById('bg3d-canvas');
  if (!canvas) return;

  // 1. Scene & Camera Setup
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x07080d, 0.0018);

  const camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    1,
    2000
  );
  camera.position.set(0, 180, 480);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  // 2. Undulating 3D Particle Wave Field
  const SEPARATION = 40;
  const AMOUNTX = 75;
  const AMOUNTY = 75;
  const numParticles = AMOUNTX * AMOUNTY;

  const positions = new Float32Array(numParticles * 3);
  const colors = new Float32Array(numParticles * 3);

  // Gradient colors: violet (0.39, 0.40, 0.95) to cyan/pink
  const color1 = new THREE.Color(0x6366f1); // Indigo
  const color2 = new THREE.Color(0xa855f7); // Purple
  const color3 = new THREE.Color(0x06b6d4); // Cyan

  let i = 0;
  for (let ix = 0; ix < AMOUNTX; ix++) {
    for (let iy = 0; iy < AMOUNTY; iy++) {
      const x = ix * SEPARATION - (AMOUNTX * SEPARATION) / 2;
      const z = iy * SEPARATION - (AMOUNTY * SEPARATION) / 2;

      positions[i] = x;
      positions[i + 1] = 0;
      positions[i + 2] = z;

      // Color interpolation across the field
      const ratio = (ix + iy) / (AMOUNTX + AMOUNTY);
      const c = color1.clone().lerp(ratio > 0.5 ? color2 : color3, ratio);

      colors[i] = c.r;
      colors[i + 1] = c.g;
      colors[i + 2] = c.b;

      i += 3;
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // Circular soft particle texture
  function createParticleTexture() {
    const pCanvas = document.createElement('canvas');
    pCanvas.width = 64;
    pCanvas.height = 64;
    const ctx = pCanvas.getContext('2d');
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.3, 'rgba(200, 220, 255, 0.7)');
    grad.addColorStop(0.7, 'rgba(99, 102, 241, 0.25)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(pCanvas);
  }

  const material = new THREE.PointsMaterial({
    size: 6.5,
    vertexColors: true,
    map: createParticleTexture(),
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const particles = new THREE.Points(geometry, material);
  particles.position.y = -60;
  scene.add(particles);

  // 3. Floating 3D Geometric Polygonal Meshes
  const floatingGroup = new THREE.Group();
  scene.add(floatingGroup);

  const shapes = [];
  const geomTypes = [
    new THREE.IcosahedronGeometry(35, 0),
    new THREE.OctahedronGeometry(28, 0),
    new THREE.TetrahedronGeometry(30, 0),
    new THREE.TorusGeometry(32, 6, 12, 32),
  ];

  const wireMaterial = new THREE.MeshBasicMaterial({
    color: 0x818cf8,
    wireframe: true,
    transparent: true,
    opacity: 0.25,
  });

  for (let k = 0; k < 9; k++) {
    const geom = geomTypes[k % geomTypes.length];
    const mesh = new THREE.Mesh(geom, wireMaterial.clone());

    mesh.position.x = (Math.random() - 0.5) * 1400;
    mesh.position.y = Math.random() * 300 + 40;
    mesh.position.z = (Math.random() - 0.5) * 800;

    mesh.scale.setScalar(0.7 + Math.random() * 0.8);

    mesh.userData = {
      rotX: (Math.random() - 0.5) * 0.015,
      rotY: (Math.random() - 0.5) * 0.015,
      floatSpeed: 0.001 + Math.random() * 0.002,
      baseY: mesh.position.y,
      offset: Math.random() * Math.PI * 2,
    };

    floatingGroup.add(mesh);
    shapes.push(mesh);
  }

  // 4. Mouse Tracking & Parallax
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;

  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - window.innerWidth / 2) * 0.4;
    mouseY = (e.clientY - window.innerHeight / 2) * 0.3;
  });

  // 5. Animation Loop
  let count = 0;

  function animate() {
    requestAnimationFrame(animate);

    count += 0.035;

    // Smooth camera parallax
    targetX += (mouseX - targetX) * 0.03;
    targetY += (mouseY - targetY) * 0.03;

    camera.position.x = targetX * 0.8;
    camera.position.y = 180 - targetY * 0.5;
    camera.lookAt(0, 20, 0);

    // Wave motion calculation for 3D particles
    const pos = particles.geometry.attributes.position.array;
    let idx = 0;

    for (let ix = 0; ix < AMOUNTX; ix++) {
      for (let iy = 0; iy < AMOUNTY; iy++) {
        pos[idx + 1] =
          Math.sin((ix + count) * 0.25) * 35 +
          Math.sin((iy + count) * 0.4) * 35 +
          Math.cos((ix + iy + count) * 0.2) * 20;
        idx += 3;
      }
    }
    particles.geometry.attributes.position.needsUpdate = true;

    // Rotate floating shapes
    shapes.forEach((s) => {
      s.rotation.x += s.userData.rotX;
      s.rotation.y += s.userData.rotY;
      s.position.y =
        s.userData.baseY + Math.sin(count * 0.5 + s.userData.offset) * 25;
    });

    renderer.render(scene, camera);
  }

  animate();

  // 6. Responsive Window Resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  // 7. Interactive 3D Card Tilt for UI Elements
  function enable3DCardTilt(selector) {
    document.querySelectorAll(selector).forEach((card) => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateX = ((y - centerY) / centerY) * -7;
        const rotateY = ((x - centerX) / centerX) * 7;

        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
      });

      card.addEventListener('mouseleave', () => {
        card.style.transform =
          'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
      });
    });
  }

  // Apply tilt to generator card
  enable3DCardTilt('.generator-card');
})();
