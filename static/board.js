// The server renders every task and link. This file only moves the viewport.
(() => {
  const viewport = document.querySelector('.wall-viewport');
  if (!viewport) return;
  const canvas = viewport.querySelector('.wall-canvas');
  const zones = [...canvas.querySelectorAll('.wall-zone')];
  const toolbar = document.querySelector('.wall-toolbar');
  const prev = toolbar.querySelector('[data-wall-prev]');
  const next = toolbar.querySelector('[data-wall-next]');
  let zone = 0, width = 0, animation, drag, suppressClick = false;
  const allowsMotion = () => document.documentElement.dataset.motion !== 'off' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  viewport.classList.add('wall-ready');
  toolbar.hidden = false;
  function controls() {
    prev.disabled = zone === 0;
    next.disabled = zone === zones.length - 1;
    toolbar.querySelector('[data-wall-position]').textContent = `${zone + 1} / ${zones.length} 区`;
    toolbar.querySelector('[data-wall-count]').textContent = `${canvas.querySelectorAll('[data-task]').length} 个任务`;
    canvas.dataset.zone = String(zone);
    zones.forEach((element, index) => { element.inert = index !== zone; });
  }
  function move(target, play = true) {
    const from = getComputedStyle(canvas).transform;
    const oldX = -zone * width;
    zone = Math.max(0, Math.min(zones.length - 1, target));
    const x = -zone * width;
    animation?.cancel();
    canvas.style.transform = `translate3d(${x}px,0,0)`;
    controls();
    if (play && allowsMotion()) {
      animation = canvas.animate([
        {transform: from === 'none' ? `translate3d(${oldX}px,0,0)` : from},
        {transform: `translate3d(${oldX + (x-oldX)*.25 + width*.04}px,18px,0) scale(.92) rotate(-.4deg)`, offset: .28},
        {transform: `translate3d(${x + width*.04}px,12px,0) scale(.92)`, offset: .72},
        {transform: `translate3d(${x}px,0,0)`}
      ], {duration: 850, easing: 'cubic-bezier(.22,.7,.24,1)'});
    }
  }
  function layout() {
    width = viewport.clientWidth;
    canvas.style.setProperty('--zone-width', `${width}px`);
    canvas.style.width = `${width * zones.length}px`;
    viewport.style.height = `${Math.max(...zones.map(element => element.offsetHeight)) + 12}px`;
    move(zone, false);
  }
  layout();
  new ResizeObserver(layout).observe(viewport);
  prev.addEventListener('click', () => move(zone - 1));
  next.addEventListener('click', () => move(zone + 1));
  viewport.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault(); viewport.focus({preventScroll:true});
      move(zone + (event.key === 'ArrowLeft' ? -1 : 1));
    }
  });
  viewport.addEventListener('pointerdown', event => {
    if (event.button !== 0 || zones.length < 2) return;
    animation?.cancel();
    canvas.style.transform = `translate3d(${-zone*width}px,0,0)`;
    drag = {id:event.pointerId, x:event.clientX, y:event.clientY, base:-zone*width, moved:false};
  });
  viewport.addEventListener('pointermove', event => {
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.x;
    if (!drag.moved && Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(event.clientY-drag.y)) {
      drag.moved = true; viewport.setPointerCapture(event.pointerId); viewport.classList.add('dragging');
    }
    if (drag.moved) canvas.style.transform = `translate3d(${Math.max(-(zones.length-1)*width,Math.min(0,drag.base+dx))}px,0,0)`;
  });
  viewport.addEventListener('pointerup', event => {
    if (!drag) return;
    if (drag.moved) {
      suppressClick = true;
      const dx = event.clientX-drag.x;
      move(zone + (Math.abs(dx)>width*.18 ? (dx<0 ? 1 : -1) : 0));
      setTimeout(() => { suppressClick=false; },0);
    }
    if (viewport.hasPointerCapture(drag.id)) viewport.releasePointerCapture(drag.id);
    drag=null; viewport.classList.remove('dragging');
  });
  viewport.addEventListener('pointercancel', () => { drag=null; viewport.classList.remove('dragging'); move(zone,false); });
  viewport.addEventListener('click', event => { if (suppressClick) {event.preventDefault();event.stopPropagation();} },true);
  // Prevent the browser's native link-drag gesture from competing with wall movement.
  viewport.addEventListener('dragstart', event => event.preventDefault());
})();
