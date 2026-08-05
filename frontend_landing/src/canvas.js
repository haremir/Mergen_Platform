// NOTHING TECH STYLE DOT-MATRIX CANVAS BACKGROUND WITH REACTIVE GLYPH MATRIX LIGHTS

export function initMatrixCanvas() {
  const canvas = document.getElementById('matrix-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  const spacing = 32; // Dot grid spacing
  const dotRadius = 1.2;
  const mouse = { x: -1000, y: -1000, radius: 180 };

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });

  window.addEventListener('mouseleave', () => {
    mouse.x = -1000;
    mouse.y = -1000;
  });

  function draw() {
    ctx.clearRect(0, 0, width, height);

    const cols = Math.ceil(width / spacing);
    const rows = Math.ceil(height / spacing);

    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const x = i * spacing + 16;
        const y = j * spacing + 16;

        const dx = mouse.x - x;
        const dy = mouse.y - y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        let currentRadius = dotRadius;
        let opacity = 0.12;
        let color = '255, 255, 255';

        if (dist < mouse.radius) {
          const factor = 1 - dist / mouse.radius;
          currentRadius = dotRadius + factor * 2.5;
          opacity = 0.12 + factor * 0.75;
          color = '0, 210, 255'; // Cyan glow near mouse cursor
        }

        ctx.beginPath();
        ctx.arc(x, y, currentRadius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${color}, ${opacity})`;
        ctx.fill();
      }
    }

    requestAnimationFrame(draw);
  }

  draw();
}
