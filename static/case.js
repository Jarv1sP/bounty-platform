/* 勋章柜（成就页）
   - 进场：每格的勋章按顺序落下来，总数从 0 数上去。
   - 拿起来看：点一格，背景从那一格铺开成深色展台，勋章转着飞到中央、落定时闪一下；
     能拖着转（甩一下有惯性，停在正面或背面），点一下翻面，背面刻着最近一句夸奖。左右键换下一枚，Esc 放回去。
   - 颁奖（ui.js）开始时先把这批勋章从柜子里"拿出来"，收下时再一枚枚飞回各自的格子。
   不开动效时所有过程直接跳到结果；不开 JS 时每格是一个 <details>，展开看每一次获得。 */
(() => {
  const feel = window.bounty || {play() { return null; }, sfx() {}, toast() {}, countTo(el, to) { el.textContent = to; return Promise.resolve(); }, motionOn: () => false, B: 'ease', C: 'ease', D: 'ease'};
  const panel = document.querySelector('.case');
  const source = document.getElementById('case-data');
  if (!panel || !source) return;
  // 逐帧截图用（和 ui.js 一样）：只放慢计时器和逐帧补间；元素动画由截图脚本自己放慢
  const SLOW = Number(window.__bountyTimeScale) || 1;
  const data = JSON.parse(source.textContent);
  // 顺序跟柜子里一样（先冷色一行再暖色一行）；JSON 里的键是按字母排的，不能直接用
  const keys = [...panel.querySelectorAll('[data-collection-key]')].map(tile => tile.dataset.collectionKey);
  const template = document.querySelector('template[data-medal-template]');
  const medalSvg = (key, ghost) => template.content.querySelector(`[data-key="${ghost ? 'ghost-' : ''}${key}"]`).innerHTML;
  const tileOf = key => panel.querySelector(`[data-collection-key="${key}"]`);
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const totalEl = panel.querySelector('[data-case-total]');
  const kindsEl = panel.querySelector('[data-case-kinds]');
  const shown = Object.fromEntries(keys.map(key => [key, data[key].count]));

  if (totalEl && !document.querySelector('[data-honor-reveal]')) feel.countTo(totalEl, Number(totalEl.textContent), {from: 0, duration: 700});

  /* ---------- 柜子里每一格的样子跟着 shown 走 ---------- */
  function paintTile(key) {
    const tile = tileOf(key);
    const n = shown[key];
    const stage = tile.querySelector('.tile-stage');
    if (tile.classList.contains('locked') !== !n) stage.querySelector('.medal').outerHTML = medalSvg(key, !n);
    tile.classList.toggle('locked', !n);
    tile.dataset.count = String(n);
    stage.dataset.stack = String(Math.min(n, 3));
    tile.querySelector('[data-count-text]').textContent = n;
    const info = data[key];
    tile.querySelector('.tile-sub').textContent = n ? `+${info.each * n} 经验` : info.can_get ? `${info.can_get} 个任务能拿` : '还没拿到';
  }
  function paintHead() {
    if (totalEl) totalEl.textContent = keys.reduce((sum, key) => sum + shown[key], 0);
    if (kindsEl) kindsEl.textContent = keys.filter(key => shown[key]).length;
  }

  // 颁奖开始：这一批先从柜子里拿出来（对话框已经盖住页面，看不到这一步）
  document.addEventListener('bounty:reveal-start', ({detail}) => {
    detail.awards.forEach(award => { shown[award.medal_key] = Math.max(0, shown[award.medal_key] - 1); });
    keys.forEach(paintTile);
    paintHead();
  });
  // 收下：一枚枚从屏幕中央飞回自己的格子，落下时格子回弹、数字跳一下
  document.addEventListener('bounty:collected', ({detail}) => {
    const groups = {};
    detail.awards.forEach(award => { groups[award.medal_key] = (groups[award.medal_key] || 0) + 1; });
    Object.entries(groups).forEach(([key, n], i) => {
      const land = () => {
        const tile = tileOf(key);
        const before = shown[key];
        shown[key] = data[key].count;
        paintTile(key);
        tile.classList.add('collection-new');
        const count = tile.querySelector('[data-count-text]');
        feel.countTo(count, shown[key], {from: before, duration: 360});
        feel.play(tile.querySelector('.tile-stage'), [{transform: 'scale(1.18,.86)'}, {transform: 'scale(.96,1.04)', offset: .45}, {transform: 'none'}], {duration: 420, easing: feel.B});
        feel.sfx('medal', {pitch: 1 + i * 0.12});
        if (totalEl) feel.countTo(totalEl, keys.reduce((sum, k) => sum + shown[k], 0), {duration: 300});
        if (kindsEl) kindsEl.textContent = keys.filter(k => shown[k]).length;
      };
      if (!feel.motionOn()) { land(); return; }
      setTimeout(() => flyHome(key, n).then(land), (120 + i * 240) * SLOW);
    });
  });
  function flyHome(key, n) {
    const target = tileOf(key).querySelector('.tile-stage').getBoundingClientRect();
    const size = 150;
    const flyer = document.createElement('div');
    flyer.style.cssText = `position:fixed;left:${innerWidth / 2 - size / 2}px;top:${innerHeight / 2 - size / 2}px;width:${size}px;height:${size}px;z-index:80;pointer-events:none`;
    flyer.innerHTML = medalSvg(key, false);
    flyer.firstElementChild.style.cssText = 'width:100%;height:100%;filter:drop-shadow(0 12px 18px rgba(0,0,0,.35))';
    document.body.append(flyer);
    const dx = target.left + target.width / 2 - innerWidth / 2;
    const dy = target.top + target.height / 2 - innerHeight / 2;
    const s = target.width / size;
    // 走一条弧线：先往上抛一点再落进格子
    const motion = flyer.animate([
      {transform: 'translate(0,0) scale(1)'},
      {transform: `translate(${dx * 0.45}px,${dy * 0.45 - 80}px) scale(${(1 + s) / 2}) rotate(-16deg)`, offset: .45},
      {transform: `translate(${dx}px,${dy}px) scale(${s})`},
    ], {duration: 560 + Math.min(n, 3) * 40, easing: 'cubic-bezier(.45,0,.2,1)', fill: 'forwards'});
    return motion.finished.then(() => flyer.remove(), () => flyer.remove());
  }

  /* ---------- 拿起来看 ---------- */
  const dialog = document.querySelector('.inspect');
  if (!dialog) return;
  const bg = dialog.querySelector('.inspect-bg');
  const fly = dialog.querySelector('[data-coin-fly]');
  const coin = dialog.querySelector('[data-coin]');
  const front = dialog.querySelector('[data-coin-front]');
  const back = dialog.querySelector('[data-coin-back]');
  const burst = dialog.querySelector('[data-inspect-burst]');
  const info = dialog.querySelector('[data-inspect-info]');
  const position = dialog.querySelector('[data-inspect-pos]');
  const tools = dialog.querySelector('.inspect-tools');
  // 勋章的厚度：十三片同色的薄片叠在正反面之间，侧过来时能看到边
  dialog.querySelector('[data-coin-edge]').innerHTML = Array.from({length: 13}, (_, i) => `<i style="--z:${i - 6}px"></i>`).join('');
  coin.tabIndex = 0;
  coin.setAttribute('role', 'button');
  coin.setAttribute('aria-label', '翻面');
  // 浅色勋章的背面用墨色字
  const INK_ON = new Set(['#F2B700', '#F39800', '#00AEE0']);
  let current = null;
  let ry = 0;
  let tween = 0;
  let timers = [];
  let closing = false;    // 正在放回去
  let stepping = false;   // 正在换下一枚（换的过程中再点左右键不叠加）
  const later = (fn, ms) => timers.push(setTimeout(fn, ms * SLOW));
  const outCubic = k => 1 - Math.pow(1 - k, 3);
  const outBack = k => 1 + 2.4 * Math.pow(k - 1, 3) + 1.4 * Math.pow(k - 1, 2);
  const mine = () => dialog.getAnimations({subtree: true}).filter(a => !(window.CSSAnimation && a instanceof CSSAnimation) && !(window.CSSTransition && a instanceof CSSTransition));

  let face = 0;
  function setRy(value, audible = false) {
    ry = value;
    coin.style.transform = `rotateY(${value}deg)`;
    const now = Math.round(value / 180);
    if (now !== face) { face = now; if (audible) feel.sfx('tick', {pitch: now % 2 ? 1.3 : 1}); }
  }
  function tweenRy(to, ms, ease = outCubic, audible = false) {
    const id = ++tween;
    if (!feel.motionOn()) { setRy(to); return Promise.resolve(); }
    const from = ry;
    const start = performance.now();
    return new Promise(resolve => {
      const step = now => {
        if (id !== tween) return resolve();
        const k = Math.min(1, (now - start) / (ms * SLOW));
        setRy(from + (to - from) * ease(k), audible);
        if (k < 1) requestAnimationFrame(step); else resolve();
      };
      requestAnimationFrame(step);
    });
  }

  function fill(key) {
    const d = data[key];
    const got = d.count > 0;
    current = key;
    dialog.style.setProperty('--hue', got ? d.hue : '#5A5E6E');
    dialog.style.setProperty('--edge', got ? `color-mix(in srgb, ${d.hue} 58%, #000)` : '#34374A');
    dialog.style.setProperty('--on', got && INK_ON.has(d.hue) ? '#1B1D2A' : '#fff');
    front.innerHTML = medalSvg(key, !got);
    back.classList.toggle('empty', !got);
    back.innerHTML = got
      ? `<span class="cb-n">NO.${String(d.count).padStart(2, '0')}</span><q>${esc(d.back.quote)}</q><small>${esc(d.back.by)}${d.back.praised ? '' : ' 验收'} · ${esc(d.back.on)}</small>`
      : '<b class="cb-q">?</b><small>还没拿到</small>';
    info.innerHTML = got ? `
      <span class="inspect-kicker">${esc(d.kind)}</span>
      <h2 id="inspect-name">${esc(d.name)}${d.plate ? '<span class="award-tier">在名牌上</span>' : ''}</h2>
      <div class="inspect-nums">
        <div><b class="num">×<span data-n>${d.count}</span></b><small>拿到过</small></div>
        <div><b class="num">+${d.xp}</b><small>经验 · 每枚 ${d.each}</small></div>
        <div><b class="num">${esc(d.first)}</b><small>第一次拿到</small></div>
      </div>
      <h3>每一次</h3>
      <ol class="tickets">${d.history.map(h => `<li class="ticket"><span class="stamp-date" style="--c:${d.hue}">${esc(h.on)}</span><b><a href="${esc(h.task)}">${esc(h.title)}</a></b><span>${esc(h.by)} 验收${h.praise ? ` · <q>${esc(h.praise)}</q>` : ''}${h.claps ? ` · ${h.claps} 次鼓掌` : ''}</span></li>`).join('')}</ol>
      <div class="inspect-actions"><a class="btn btn-line btn-sm" href="${esc(d.find)}">再找一个「${esc(d.name)}」任务</a></div>`
      : `
      <span class="inspect-kicker">${esc(d.kind)}</span>
      <h2 id="inspect-name">${esc(d.name)}</h2>
      <p class="inspect-lock">还没拿到。完成一个<b>${esc(d.kind)}</b>的任务，验收通过后它会寄到你的信箱。${d.can_get ? `现在有 <b>${d.can_get}</b> 个任务能拿到它。` : '现在还没有这类任务，留意新发布的。'}</p>
      <div class="inspect-actions"><a class="btn btn-sm" href="${esc(d.find)}">去找这类任务</a></div>`;
    position.textContent = `${keys.indexOf(key) + 1} / ${keys.length}`;
    panel.querySelectorAll('.tile.picked').forEach(tile => tile.classList.remove('picked'));
    tileOf(key).classList.add('picked');
  }

  // 展台的打光对准勋章
  function aim() {
    const box = fly.getBoundingClientRect();
    dialog.style.setProperty('--cx', `${box.left + box.width / 2}px`);
    dialog.style.setProperty('--cy', `${box.top + box.height / 2}px`);
  }
  addEventListener('resize', () => { if (dialog.open) aim(); });
  dialog.querySelector('.inspect-in').addEventListener('scroll', () => aim(), {passive: true});

  // 落定的一下：扫光 + 碎片 + 铃声；越多枚越热闹
  function hit(d) {
    coin.classList.remove('shine');
    void coin.offsetWidth;
    coin.classList.add('shine');
    const colors = [d.hue, '#fff', '#F2B700', d.hue, '#00AEE0', '#fff', '#E54465', d.hue];
    const pieces = Math.min(8 + d.count * 2, 18);
    const reach = fly.offsetWidth * 0.62;
    burst.innerHTML = Array.from({length: pieces}, (_, i) => {
      const angle = (i / pieces) * Math.PI * 2 + (i % 2) * 0.28;
      const distance = reach + (i % 3) * 34;
      return `<i style="--x:${Math.round(Math.cos(angle) * distance)}px;--y:${Math.round(Math.sin(angle) * distance)}px;--s:${8 + (i % 3) * 6}px;--c:${colors[i % colors.length]};--r:${i % 3 === 1 ? '3px' : '50%'};--rot:${i * 37}deg;--delay:${i * 16}ms"></i>`;
    }).join('');
    fly.classList.remove('go');
    void fly.offsetWidth;
    fly.classList.add('go');
    feel.sfx('medal', {pitch: 1 + Math.min(d.count, 6) * 0.03});
  }

  function enterInfo(delay) {
    const d = data[current];
    const n = info.querySelector('[data-n]');
    if (!feel.motionOn()) return;
    feel.play(info, [{opacity: 0, transform: 'translateX(36px)'}, {opacity: 1, transform: 'none'}], {duration: 460, delay, easing: feel.C, fill: 'backwards'});
    feel.play(info.querySelector('h2'), [{transform: 'scaleX(.25)', opacity: 0}, {transform: 'none', opacity: 1}], {duration: 340, delay: delay + 120, easing: feel.B, fill: 'backwards'});
    info.querySelectorAll('.ticket').forEach((ticket, i) => {
      if (i < 8) feel.play(ticket, [{opacity: 0, transform: 'translateY(14px) rotate(-1deg)'}, {opacity: 1, transform: 'none'}], {duration: 380, delay: delay + 300 + i * 60, easing: feel.C, fill: 'backwards'});
    });
    if (n && d.count > 1) {
      n.textContent = '0';
      later(() => feel.countTo(n, d.count, {from: 0, duration: 520, onTick: k => feel.sfx('tick', {pitch: 1 + k * 0.5})}), delay + 260);
    }
  }

  function open(key) {
    if (dialog.open) return;
    fill(key);
    face = 0;
    setRy(0);
    dialog.showModal();
    aim();
    const got = data[key].count > 0;
    if (!feel.motionOn()) return;
    const from = tileOf(key).querySelector('.tile-stage').getBoundingClientRect();
    const to = fly.getBoundingClientRect();
    const cx = from.left + from.width / 2;
    const cy = from.top + from.height / 2;
    feel.play(bg, [{clipPath: `circle(0px at ${cx}px ${cy}px)`}, {clipPath: `circle(150% at ${cx}px ${cy}px)`}], {duration: 600, easing: feel.C});
    feel.play(fly, [
      {transform: `translate(${cx - to.left - to.width / 2}px,${cy - to.top - to.height / 2}px) scale(${from.width / to.width})`},
      {transform: 'translate(0,0) scale(1.08)', offset: .7},
      {transform: 'none'},
    ], {duration: 720, easing: feel.C});
    [tools, dialog.querySelector('.inspect-close')].forEach(el => feel.play(el, [{opacity: 0}, {opacity: 1}], {duration: 300, delay: 500, fill: 'backwards'}));
    // 拿到过的转两圈亮相；没拿到的只晃半圈
    setRy(got ? -720 : -180);
    tweenRy(0, got ? 1150 : 700);
    if (got) later(() => hit(data[key]), 620);
    else feel.sfx('tap');
    enterInfo(240);
  }

  // 任何时候都能放回去，包括亮相和换下一枚的半路
  async function close() {
    if (!dialog.open || closing) return;
    closing = true;
    timers.forEach(clearTimeout);
    timers = [];
    const tile = tileOf(current);
    if (feel.motionOn()) {
      const to = tile.querySelector('.tile-stage').getBoundingClientRect();
      const from = fly.getBoundingClientRect();
      const cx = to.left + to.width / 2;
      const cy = to.top + to.height / 2;
      tweenRy(Math.round(ry / 360) * 360, 420);
      feel.play(info, [{opacity: 1}, {opacity: 0, transform: 'translateX(24px)'}], {duration: 180, fill: 'forwards'});
      feel.play(tools, [{opacity: 1}, {opacity: 0}], {duration: 150, fill: 'forwards'});
      feel.play(bg, [{clipPath: `circle(150% at ${cx}px ${cy}px)`}, {clipPath: `circle(0px at ${cx}px ${cy}px)`}], {duration: 480, easing: 'cubic-bezier(.55,0,.75,.2)', fill: 'forwards'});
      await feel.play(fly, [{transform: 'none'}, {transform: `translate(${cx - from.left - from.width / 2}px,${cy - from.top - from.height / 2}px) scale(${to.width / from.width})`}],
        {duration: 460, easing: 'cubic-bezier(.5,0,.2,1)', fill: 'forwards'}).finished.catch(() => {});
    }
    tween++;
    dialog.close();
    mine().forEach(animation => animation.cancel());
    fly.classList.remove('go');
    tile.classList.remove('picked');
    // 放回格子里：轻轻压一下
    feel.play(tile.querySelector('.tile-stage'), [{transform: 'scale(1.1,.9)'}, {transform: 'none'}], {duration: 300, easing: feel.B});
    feel.sfx('tap');
    closing = stepping = false;
  }

  async function step(dir) {
    if (stepping || closing) return;
    const key = keys[(keys.indexOf(current) + dir + keys.length) % keys.length];
    timers.forEach(clearTimeout);
    timers = [];
    if (!feel.motionOn()) { fill(key); setRy(0); return; }
    stepping = true;
    tween++;
    const out = feel.play(fly, [{transform: 'none', opacity: 1}, {transform: `translateX(${-dir * 90}px) scale(.82)`, opacity: 0}], {duration: 170, easing: feel.D, fill: 'forwards'});
    feel.play(info, [{opacity: 1}, {opacity: 0}], {duration: 150, fill: 'forwards'});
    await out.finished.catch(() => {});
    if (closing || !dialog.open) return;
    mine().forEach(animation => animation.cancel());
    fill(key);
    face = 0;
    const got = data[key].count > 0;
    feel.play(fly, [{transform: `translateX(${dir * 90}px) scale(.82)`, opacity: 0}, {transform: 'none', opacity: 1}], {duration: 420, easing: feel.C});
    setRy(dir * -360);
    tweenRy(0, 760);
    if (got) later(() => hit(data[key]), 380); else feel.sfx('tap');
    enterInfo(60);
    stepping = false;
  }

  function flip() {
    const target = Math.round(ry / 180) * 180 + 180;
    tweenRy(target, 640, outBack, true);
    feel.sfx('tap');
  }

  /* 拖着转：跟手转，松手按甩出去的速度再转一段，最后停在正面或背面 */
  let drag = null;
  coin.addEventListener('pointerdown', event => {
    if (event.button !== 0 || closing) return;
    tween++;
    drag = {x: event.clientX, start: ry, last: event.clientX, t: performance.now(), v: 0, moved: 0};
    coin.setPointerCapture(event.pointerId);
    coin.classList.add('dragging');
  });
  coin.addEventListener('pointermove', event => {
    if (!drag) return;
    const now = performance.now();
    const dx = event.clientX - drag.x;
    drag.moved = Math.max(drag.moved, Math.abs(dx));
    drag.v = (event.clientX - drag.last) / Math.max(1, now - drag.t) * 0.6;
    drag.last = event.clientX;
    drag.t = now;
    setRy(drag.start + dx * 0.6, true);
  });
  const release = () => {
    if (!drag) return;
    const {moved, v} = drag;
    drag = null;
    coin.classList.remove('dragging');
    if (moved < 5) { flip(); return; }
    const target = Math.round((ry + v * 280) / 180) * 180;
    tweenRy(target, Math.min(1300, 480 + Math.abs(target - ry) * 1.1), outBack, true);
  };
  coin.addEventListener('pointerup', release);
  coin.addEventListener('pointercancel', release);
  coin.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); flip(); }
  });

  panel.querySelectorAll('.tile summary').forEach(summary => summary.addEventListener('click', event => {
    event.preventDefault();
    open(summary.closest('.tile').dataset.collectionKey);
  }));
  dialog.querySelector('[data-inspect-close]').addEventListener('click', close);
  dialog.querySelectorAll('[data-inspect-step]').forEach(button => button.addEventListener('click', () => step(Number(button.dataset.inspectStep))));
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') step(-1);
    if (event.key === 'ArrowRight') step(1);
  });
  // 点空白处放回去
  dialog.addEventListener('click', event => {
    if (event.target === dialog || event.target.classList.contains('inspect-in') || event.target.classList.contains('inspect-stage')) close();
  });
})();
