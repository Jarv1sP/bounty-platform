// Presentation effects never decide whether a task action succeeded.
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let userQuiet = false;
try { userQuiet = localStorage.getItem('bounty-motion') === 'off'; } catch {}
const motionAllowed = () => !reducedMotion.matches && !userQuiet;
const motionToggle = document.querySelector('[data-motion-toggle]');
function updateMotion() {
  document.documentElement.dataset.motion = motionAllowed() ? 'on' : 'off';
  if (motionToggle) {
    motionToggle.hidden = false;
    motionToggle.setAttribute('aria-pressed', String(userQuiet || reducedMotion.matches));
    motionToggle.textContent = reducedMotion.matches ? '动效：随系统关闭' : `动效：${userQuiet ? '关' : '开'}`;
    motionToggle.disabled = reducedMotion.matches;
  }
  if (!motionAllowed()) {
    document.getAnimations().forEach(animation => animation.cancel());
    document.querySelectorAll('[data-tilt]').forEach(card => {
      card.style.removeProperty('--tilt-x'); card.style.removeProperty('--tilt-y');
    });
  }
}
updateMotion();
reducedMotion.addEventListener('change', updateMotion);
motionToggle?.addEventListener('click', () => {
  userQuiet = !userQuiet;
  try { localStorage.setItem('bounty-motion', userQuiet ? 'off' : 'on'); } catch {}
  updateMotion();
});
function animate(element, frames, options = {}) {
  if (element && motionAllowed()) return element.animate(frames, {duration: 420, easing: 'cubic-bezier(.22,.8,.25,1)', ...options});
}

// A short paper arrival, followed by pointer-controlled depth (no idle loop).
document.querySelectorAll('[data-tilt]').forEach((card, index) => {
  animate(card, [{opacity: 0, transform: 'translateY(18px) rotate(-2deg)'}, {opacity: 1, transform: 'none'}], {delay: Math.min(index, 5) * 50});
  let frame = 0;
  card.addEventListener('pointermove', event => {
    if (!motionAllowed() || event.pointerType !== 'mouse') return;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const box = card.getBoundingClientRect();
      card.style.setProperty('--tilt-x', `${-((event.clientY - box.top) / box.height - .5) * 5}deg`);
      card.style.setProperty('--tilt-y', `${((event.clientX - box.left) / box.width - .5) * 5}deg`);
    });
  });
  const reset = () => {
    cancelAnimationFrame(frame);
    card.style.removeProperty('--tilt-x'); card.style.removeProperty('--tilt-y');
  };
  card.addEventListener('pointerleave', reset);
  card.addEventListener('blur', reset);
});

const importance = document.querySelector('#importance');
const urgency = document.querySelector('#urgency');
if (importance && urgency) {
  const preview = (play = true) => {
    const key = `${importance.value}-${urgency.value}`;
    document.querySelectorAll('[data-medal]').forEach(el => {
      el.hidden = el.dataset.medal !== key;
      if (!el.hidden && play) animate(el.querySelector('.medal'), [
        {transform: 'translateY(-12px) rotate(-12deg) scale(.8)'},
        {transform: 'translateY(3px) rotate(5deg) scale(1.05)', offset: .7},
        {transform: 'none'}
      ]);
    });
  };
  importance.addEventListener('change', () => preview());
  urgency.addEventListener('change', () => preview());
  preview(false);
}

// Submit immediately. Pending state is not a success animation and adds no artificial delay.
document.querySelectorAll('form[method="post"]:not([data-appreciate-form])').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.pending) { event.preventDefault(); return; }
    form.dataset.pending = 'true';
    form.setAttribute('aria-busy', 'true');
    form.classList.add('is-sending');
    form.querySelectorAll('button:not([type="button"])').forEach(button => {
      button.disabled = true;
      button.dataset.originalLabel = button.innerHTML;
      button.textContent = '正在保存…';
    });
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[data-pending]').forEach(form => {
    delete form.dataset.pending;
    form.removeAttribute('aria-busy'); form.classList.remove('is-sending');
    form.querySelectorAll('button[data-original-label]').forEach(button => {
      button.disabled = false; button.innerHTML = button.dataset.originalLabel;
      delete button.dataset.originalLabel;
    });
  });
});

const receipt = document.querySelector('[data-confirmed-action]');
if (receipt) {
  const stamp = receipt.querySelector('.receipt-stamp');
  const isDelivery = receipt.dataset.confirmedAction === 'submit';
  const effect = animate(stamp, isDelivery ? [
    {opacity: 0, transform: 'translateX(-65px) rotate(-15deg)'},
    {opacity: 1, transform: 'translateX(5px) rotate(3deg)', offset: .7},
    {opacity: 1, transform: 'rotate(-4deg)'}
  ] : [
    {opacity: 0, transform: 'scale(1.2) rotate(-8deg)'},
    {opacity: 1, transform: 'scale(.94) rotate(-4deg)', offset: .62},
    {opacity: 1, transform: 'scale(1) rotate(-4deg)'}
  ], {duration: 360});
  const skip = receipt.querySelector('[data-skip-receipt]');
  if (effect) {
    skip.hidden = false;
    effect.finished.then(() => { skip.hidden = true; }).catch(() => { skip.hidden = true; });
    skip.addEventListener('click', () => { effect.cancel(); skip.hidden = true; });
  }
}

// Native details remains usable with keyboard and without JavaScript.
document.querySelectorAll('.honor-card').forEach(card => {
  card.addEventListener('toggle', () => {
    const face = card.open ? card.querySelector('.honor-back') : card.querySelector('.honor-front');
    animate(face, [{opacity: .3, transform: 'perspective(650px) rotateY(-65deg)'}, {opacity: 1, transform: 'perspective(650px) rotateY(0)'}]);
  });
});

const reveal = document.querySelector('[data-honor-reveal]');
const dialog = document.querySelector('.award-dialog');
if (reveal && dialog && typeof dialog.showModal === 'function') {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  let previousFocus;
  let newKeys = [];
  const finish = () => {
    dialog.getAnimations({subtree: true}).forEach(animation => animation.cancel());
    document.querySelectorAll('.collection-new').forEach(card => card.classList.remove('collection-new'));
    newKeys.forEach(key => {
      const card = document.querySelector(`[data-collection-key="${key}"]`);
      card?.classList.add('collection-new');
    });
    if (previousFocus?.isConnected && previousFocus !== document.body) previousFocus.focus({preventScroll: true});
    else document.querySelector('[data-collection-key] summary')?.focus({preventScroll: true});
  };
  dialog.querySelectorAll('[data-close-awards]').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('close', finish);
  async function loadAwards() {
    try {
      const response = await fetch(reveal.dataset.honorReveal, {
        method: 'POST', body: new URLSearchParams({csrf}), headers: {'Accept': 'application/json'}
      });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const {awards} = await response.json();
      if (!awards?.length) return;
      const area = dialog.querySelector('.award-items');
      document.querySelector('#award-title').textContent = `集章册新增 ${awards.length} 枚`;
      for (const award of awards) {
        const template = reveal.querySelector(`[data-medal-template="${award.medal_key}"]`);
        if (!template) continue;
        const item = document.createElement('a');
        item.className = 'award-item'; item.href = `/tasks/${Number(award.task_id)}`;
        item.append(template.content.cloneNode(true));
        const label = document.createElement('small'); label.textContent = award.title;
        item.append(label); area.append(item); newKeys.push(award.medal_key);
      }
      previousFocus = document.activeElement;
      dialog.showModal();
      animate(dialog, [{opacity: 0, transform: 'translateY(24px) scale(.9)'}, {opacity: 1, transform: 'none'}]);
      dialog.querySelectorAll('.award-item .medal').forEach((medal, index) => {
        animate(medal, [{transform: 'translateY(-14px) rotate(-8deg) scale(.9)', opacity: 0},
          {transform: 'translateY(8px) rotate(8deg) scale(1.08)', opacity: 1, offset: .7},
          {transform: 'none', opacity: 1}], {duration: 420, delay: Math.min(index, 5) * 80});
      });
    } catch { /* Honors remain visible; network errors never block the collection. */ }
  }
  loadAwards();
}
