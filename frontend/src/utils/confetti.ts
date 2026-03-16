// src/utils/confetti.ts
// Lightweight CSS confetti — no external deps needed

export function launchConfetti(duration = 2000) {
  const container = document.createElement('div');
  container.style.cssText = `
    position: fixed; inset: 0; pointer-events: none; z-index: 9999; overflow: hidden;
  `;
  document.body.appendChild(container);

  const colors = ['#10b981', '#34d399', '#6ee7b7', '#f59e0b', '#a78bfa', '#f472b6'];
  const count = 80;

  for (let i = 0; i < count; i++) {
    const el = document.createElement('div');
    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = Math.random() * 8 + 4;
    const left = Math.random() * 100;
    const delay = Math.random() * 500;
    const rot = Math.random() * 360;
    const fallDuration = Math.random() * 1500 + 1000;

    el.style.cssText = `
      position: absolute;
      top: -20px;
      left: ${left}%;
      width: ${size}px;
      height: ${size}px;
      background: ${color};
      border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
      transform: rotate(${rot}deg);
      animation: confetti-fall ${fallDuration}ms ease-in ${delay}ms forwards;
      opacity: 0.9;
    `;
    container.appendChild(el);
  }

  // Inject keyframe if not already present
  if (!document.getElementById('confetti-styles')) {
    const style = document.createElement('style');
    style.id = 'confetti-styles';
    style.textContent = `
      @keyframes confetti-fall {
        0%   { transform: translateY(0) rotate(0deg); opacity: 0.9; }
        100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }

  setTimeout(() => container.remove(), duration + 600);
}
