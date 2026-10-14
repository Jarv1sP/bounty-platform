// Shared recognition is saved by the server; animation follows confirmed state.
(() => {
  const canAnimate = () => document.documentElement.dataset.motion !== 'off' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  const forms = document.querySelectorAll('[data-appreciate-form]');
  forms.forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault();
    if (form.dataset.busy) return;
    form.dataset.busy = 'true';
    const button = form.querySelector('button');
    const message = form.querySelector('.appreciation-message');
    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    message.textContent = '';
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {'Accept': 'application/json'}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('登录可能已失效，请刷新页面后重试。');
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '暂时未能保存，请重试。');
      button.classList.toggle('is-active', result.appreciated);
      button.setAttribute('aria-pressed', String(result.appreciated));
      button.querySelector('.appreciate-heart').textContent = result.appreciated ? '♥' : '♡';
      button.querySelector('[data-appreciate-count]').textContent = result.appreciation_count;
      message.textContent = result.appreciated ? '已标记有帮助' : '已取消标记';
      if (result.appreciated && canAnimate()) {
        button.querySelector('.appreciate-heart').animate([
          {transform:'scale(.8) rotate(-12deg)'},
          {transform:'scale(1.45) rotate(8deg)',offset:.5},
          {transform:'scale(1) rotate(0)'}
        ],{duration:420,easing:'cubic-bezier(.2,.8,.3,1)'});
      }
    } catch (error) {
      message.textContent = error.message;
    } finally {
      button.disabled = false;
      delete form.dataset.busy;
      form.removeAttribute('aria-busy');
    }
  }));
  // A short greeting when the illustration is deliberately approached; no idle loop.
  const studio = document.querySelector('.studio-illustration');
  if (studio) {
    let waving;
    studio.addEventListener('pointerenter', event => {
      if (!canAnimate() || event.pointerType !== 'mouse' || waving?.playState === 'running') return;
      waving = studio.querySelector('.handoff-arm').animate([
        {transform:'rotate(0)'},{transform:'rotate(-7deg)',offset:.4},{transform:'rotate(3deg)',offset:.7},{transform:'rotate(0)'}
      ],{duration:850,easing:'ease-in-out'});
    });
  }
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      if (canAnimate()) entry.target.animate([{opacity:.2,transform:'translateY(15px)'},{opacity:1,transform:'translateY(0)'}],{duration:450,easing:'cubic-bezier(.2,.75,.25,1)'});
      observer.unobserve(entry.target);
    }),{threshold:.1});
    document.querySelectorAll('.achievement-card,.desk-panel').forEach(el => observer.observe(el));
  }
})();
