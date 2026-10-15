/* 积木：在 16×16 的板子上用点、线、面拼东西，随便拼，不花任何东西。
   - 点零件盒里的零件拿在手上，再点板子放下去（可以连着放）；Esc 或再点一次零件就放下手里的。
   - 点板子上的零件选中它，拖着走；R 转、D 复制、[ ] 调前后、Delete 删、方向键挪一格、Ctrl+Z 撤销。
   - 没解锁的零件和颜色点了会说怎么解锁：都是靠勋章。
   手感：放下时零件从小弹到位，越小的零件音越高；转的时候转一下再停；删掉时缩没。 */
(() => {
  const feel = window.bounty || {play() { return null; }, sfx() {}, toast() {}, motionOn: () => false, B: 'ease', C: 'ease', D: 'ease'};
  const root = document.querySelector('[data-blocks]');
  if (!root) return;
  const NS = 'http://www.w3.org/2000/svg';
  const data = JSON.parse(document.getElementById('blocks-data').textContent);
  const SIZE = Number(root.dataset.size) || 16;
  const MAX = Number(root.dataset.max) || 160;
  const board = root.querySelector('[data-board]');
  const layer = board.querySelector('[data-parts]');
  const ghost = board.querySelector('[data-ghost]');
  const selectBox = board.querySelector('[data-select-box]');
  const bgRect = board.querySelector('[data-bg-rect]');
  const countEl = root.querySelector('[data-count]');
  const emptyHint = root.querySelector('[data-empty]');
  const nameInput = root.querySelector('[data-name]');
  const showButton = root.querySelector('[data-show-build]');
  const medalTemplate = document.querySelector('template[data-medal-template]');
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const csrf = () => document.querySelector('meta[name=csrf-token]')?.content || '';

  let parts = data.build ? data.build.parts.map(part => [...part]) : [];
  let bg = data.build?.bg || 'paper';
  let buildId = data.build?.id || null;
  let hand = null;          // 拿在手上的零件
  let handRot = 0;
  let color = Object.keys(data.colors).find(key => data.colors[key].open) || 'ink';
  let selected = -1;
  let drag = null;
  let dirty = false;
  const undos = [];        // 撤销用

  const footprint = (id, r) => { const {w, h} = data.parts[id]; return r % 2 ? [h, w] : [w, h]; };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  function shape(id) {
    if (data.parts[id].shape) return data.parts[id].shape;
    // 勋章零件：用页面上的勋章图形
    return medalTemplate.content.querySelector(`[data-key="${id.slice(6)}"]`).innerHTML.replace('<svg ', '<svg x="-15" y="-15" width="30" height="30" ');
  }
  function partNode([id, c, x, y, r]) {
    const [fw, fh] = footprint(id, r);
    const outer = document.createElementNS(NS, 'g');
    outer.setAttribute('transform', `translate(${(x + fw / 2) * 10} ${(y + fh / 2) * 10}) rotate(${r * 90})`);
    outer.setAttribute('color', data.colors[c].hex);
    outer.setAttribute('fill', 'currentColor');
    const inner = document.createElementNS(NS, 'g');
    inner.setAttribute('class', 'pop');
    inner.innerHTML = shape(id);
    outer.append(inner);
    return outer;
  }
  function render() {
    layer.replaceChildren(...parts.map(partNode));
    bgRect.setAttribute('fill', data.backgrounds[bg]);
    board.classList.toggle('dark', ['ink', 'blue', 'red', 'green'].includes(bg));
    countEl.textContent = parts.length;
    emptyHint.hidden = parts.length > 0 || !!hand;
    paintSelection();
    root.querySelectorAll('.bg-btn').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.bg === bg)));
  }
  function paintSelection() {
    const on = selected >= 0 && parts[selected];
    root.querySelectorAll('[data-tool]').forEach(button => {
      const needsPart = ['rotate', 'paint', 'copy', 'front', 'back', 'delete'].includes(button.dataset.tool);
      button.disabled = needsPart ? !on && !(button.dataset.tool === 'rotate' && hand) : button.dataset.tool === 'undo' ? !undos.length : !parts.length;
    });
    if (!on) { selectBox.setAttribute('width', 0); selectBox.setAttribute('height', 0); return; }
    const [id, , x, y, r] = parts[selected];
    const [fw, fh] = footprint(id, r);
    selectBox.setAttribute('x', x * 10 - 1.5); selectBox.setAttribute('y', y * 10 - 1.5);
    selectBox.setAttribute('width', fw * 10 + 3); selectBox.setAttribute('height', fh * 10 + 3);
  }
  function remember() {
    undos.push(JSON.stringify({parts, bg}));
    if (undos.length > 100) undos.shift();
    dirty = true;
  }
  function pop(index, from = 'scale(.4)') {
    const node = layer.children[index]?.firstChild;
    feel.play(node, [{transform: from}, {transform: 'scale(1.12)', offset: .6}, {transform: 'none'}], {duration: 280, easing: feel.B});
  }
  function click(id) {
    // 越小的零件音越高，像积木"咔哒"一声
    const {w, h} = data.parts[id];
    feel.sfx('tick', {pitch: 1.7 - Math.min(w * h, 16) / 16 * 0.8});
  }
  function point(event) {
    const p = board.createSVGPoint();
    p.x = event.clientX;
    p.y = event.clientY;
    const local = p.matrixTransform(board.getScreenCTM().inverse());
    return [local.x / 10, local.y / 10];
  }
  function hit(px, py) {
    for (let i = parts.length - 1; i >= 0; i--) {
      const [id, , x, y, r] = parts[i];
      const [fw, fh] = footprint(id, r);
      if (px >= x && px <= x + fw && py >= y && py <= y + fh) return i;
    }
    return -1;
  }
  function spot(id, r, px, py) {
    const [fw, fh] = footprint(id, r);
    return [clamp(Math.round(px - fw / 2), 0, SIZE - fw), clamp(Math.round(py - fh / 2), 0, SIZE - fh)];
  }

  /* ---------- 零件盒、颜色、底色 ---------- */
  function locked(button, item) {
    feel.play(button, [{transform: 'translateX(-4px)'}, {transform: 'translateX(3px)'}, {transform: 'none'}], {duration: 220});
    feel.toast(`<span>「${esc(item.name)}」还没解锁：${esc(item.need)}</span>`, 'locked');
    feel.sfx('return');
  }
  root.querySelectorAll('[data-part]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.part;
    if (!data.parts[id].open) return locked(button, data.parts[id]);
    hand = hand === id ? null : id;
    handRot = 0;
    selected = -1;
    root.querySelectorAll('[data-part]').forEach(other => other.setAttribute('aria-pressed', String(other.dataset.part === hand)));
    feel.play(button, [{transform: 'scale(.9)'}, {transform: 'none'}], {duration: 200, easing: feel.B});
    if (hand) click(hand);
    board.classList.toggle('holding', !!hand);
    ghost.replaceChildren();
    render();
  }));
  function setColor(key, button) {
    if (!data.colors[key].open) return locked(button, data.colors[key]);
    color = key;
    root.querySelectorAll('[data-color]').forEach(other => other.setAttribute('aria-checked', String(other.dataset.color === key)));
    root.querySelectorAll('.part-icon g').forEach(g => g.setAttribute('color', data.colors[key].hex));
    feel.play(button, [{transform: 'scale(.8)'}, {transform: 'scale(1.15)', offset: .6}, {transform: 'none'}], {duration: 260, easing: feel.B});
    feel.sfx('tap');
    if (selected >= 0) { remember(); parts[selected][1] = key; render(); pop(selected, 'scale(.9)'); }
  }
  root.querySelectorAll('[data-color]').forEach(button => button.addEventListener('click', () => setColor(button.dataset.color, button)));
  root.querySelectorAll('[data-bg]').forEach(button => button.addEventListener('click', () => {
    remember();
    bg = button.dataset.bg;
    render();
    feel.play(bgRect, [{opacity: .4}, {opacity: 1}], {duration: 260});
    feel.sfx('tap');
  }));

  /* ---------- 板子：放、选、拖 ---------- */
  board.addEventListener('pointerdown', event => {
    const [px, py] = point(event);
    if (hand) {
      if (parts.length >= MAX) { feel.toast(`<span>一件作品最多 ${MAX} 个零件</span>`); return; }
      const [x, y] = spot(hand, handRot, px, py);
      remember();
      parts.push([hand, color, x, y, handRot]);
      render();
      pop(parts.length - 1);
      click(hand);
      return;
    }
    const index = hit(px, py);
    selected = index;
    if (index >= 0) {
      event.preventDefault();
      board.setPointerCapture(event.pointerId);
      drag = {index, dx: px - parts[index][2], dy: py - parts[index][3], moved: false};
      feel.sfx('tap');
    }
    paintSelection();
  });
  board.addEventListener('pointermove', event => {
    const [px, py] = point(event);
    if (hand) {
      const [x, y] = spot(hand, handRot, px, py);
      ghost.replaceChildren(partNode([hand, color, x, y, handRot]));
      return;
    }
    if (!drag) return;
    const part = parts[drag.index];
    const [fw, fh] = footprint(part[0], part[4]);
    const x = clamp(Math.round(px - drag.dx), 0, SIZE - fw);
    const y = clamp(Math.round(py - drag.dy), 0, SIZE - fh);
    if (x === part[2] && y === part[3]) return;
    if (!drag.moved) { remember(); drag.moved = true; }
    part[2] = x;
    part[3] = y;
    render();
    feel.sfx('tick', {pitch: 0.8});
  });
  const stop = () => { drag = null; };
  board.addEventListener('pointerup', stop);
  board.addEventListener('pointercancel', stop);
  board.addEventListener('pointerleave', () => ghost.replaceChildren());

  /* ---------- 工具 ---------- */
  const tools = {
    rotate() {
      if (selected < 0) { handRot = (handRot + 1) % 4; feel.sfx('tap'); return; }
      remember();
      const part = parts[selected];
      part[4] = (part[4] + 1) % 4;
      const [fw, fh] = footprint(part[0], part[4]);
      part[2] = clamp(part[2], 0, SIZE - fw);
      part[3] = clamp(part[3], 0, SIZE - fh);
      render();
      pop(selected, 'rotate(-90deg)');
      feel.sfx('tap');
    },
    paint() { if (selected >= 0) setColor(color, root.querySelector(`[data-color="${color}"]`)); },
    copy() {
      if (selected < 0 || parts.length >= MAX) return;
      remember();
      const [id, c, x, y, r] = parts[selected];
      const [fw, fh] = footprint(id, r);
      parts.push([id, c, clamp(x + 1, 0, SIZE - fw), clamp(y + 1, 0, SIZE - fh), r]);
      selected = parts.length - 1;
      render();
      pop(selected);
      click(id);
    },
    front() { if (selected < 0) return; remember(); parts.push(parts.splice(selected, 1)[0]); selected = parts.length - 1; render(); feel.sfx('tap'); },
    back() { if (selected < 0) return; remember(); parts.unshift(parts.splice(selected, 1)[0]); selected = 0; render(); feel.sfx('tap'); },
    delete() {
      if (selected < 0) return;
      remember();
      const node = layer.children[selected]?.firstChild;
      const index = selected;
      selected = -1;
      const done = () => { parts.splice(index, 1); render(); };
      const motion = feel.play(node, [{transform: 'none', opacity: 1}, {transform: 'scale(0)', opacity: 0}], {duration: 160, easing: feel.D, fill: 'forwards'});
      if (motion) motion.finished.then(done); else done();
      feel.sfx('return');
    },
    undo() {
      const last = undos.pop();
      if (!last) return;
      ({parts, bg} = JSON.parse(last));
      selected = -1;
      render();
      feel.sfx('tap');
    },
    clear() {
      if (!parts.length || !confirm('把板子上的零件全部清掉？可以撤销。')) return;
      remember();
      parts = [];
      selected = -1;
      render();
      feel.sfx('return');
    },
  };
  root.querySelectorAll('[data-tool]').forEach(button => button.addEventListener('click', () => tools[button.dataset.tool]()));
  document.addEventListener('keydown', event => {
    if (event.target.closest('input,textarea')) return;
    const key = event.key;
    if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === 'z') { event.preventDefault(); return tools.undo(); }
    if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === 's') { event.preventDefault(); return save(); }
    if (key === 'Escape') { hand = null; selected = -1; ghost.replaceChildren(); board.classList.remove('holding'); root.querySelectorAll('[data-part]').forEach(b => b.setAttribute('aria-pressed', 'false')); render(); return; }
    if (key === 'r' || key === 'R') return tools.rotate();
    if (key === 'd' || key === 'D') return tools.copy();
    if (key === '[') return tools.back();
    if (key === ']') return tools.front();
    if (key === 'Delete' || key === 'Backspace') { event.preventDefault(); return tools.delete(); }
    const step = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[key];
    if (step && selected >= 0) {
      event.preventDefault();
      const part = parts[selected];
      const [fw, fh] = footprint(part[0], part[4]);
      remember();
      part[2] = clamp(part[2] + step[0], 0, SIZE - fw);
      part[3] = clamp(part[3] + step[1], 0, SIZE - fh);
      render();
      feel.sfx('tick', {pitch: 0.8});
    }
  });

  /* ---------- 保存、挂到名牌上 ---------- */
  async function send(url, body) {
    const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf(), Accept: 'application/json'},
      body: JSON.stringify(body || {})});
    const result = await response.json().catch(() => ({error: '出了点问题，稍后再试'}));
    if (!response.ok) throw new Error(result.error || '出了点问题，稍后再试');
    return result;
  }
  async function save() {
    try {
      const result = await send(root.dataset.save, {id: buildId, name: nameInput.value, bg, parts});
      const fresh = !buildId;
      buildId = result.id;
      dirty = false;
      if (fresh) {
        showButton.dataset.url = `/play/blocks/${buildId}/show`;
        showButton.hidden = false;
      }
      feel.toast(`<span>「${esc(nameInput.value || '我的作品')}」存好了</span>`);
      feel.sfx('claim');
      feel.play(board, [{transform: 'scale(.985)'}, {transform: 'none'}], {duration: 220, easing: feel.B});
      if (fresh) setTimeout(() => location.assign(result.url), feel.motionOn() ? 700 : 0);   // 作品列表里出现新的这件
    } catch (error) {
      feel.toast(`<span>${esc(error.message)}</span>`);
    }
  }
  root.querySelector('[data-save-build]').addEventListener('click', save);
  showButton.addEventListener('click', async () => {
    if (dirty) await save();
    try {
      const result = await send(showButton.dataset.url);
      showButton.classList.toggle('on', result.shown);
      showButton.setAttribute('aria-pressed', String(result.shown));
      showButton.querySelector('span').textContent = result.shown ? '在名牌上' : '挂到名牌上';
      feel.toast(`<span>${result.shown ? '挂到名牌上了，队友在名牌墙和积木墙上都能看到' : '从名牌上取下来了'}</span>`);
      feel.sfx(result.shown ? 'stamp' : 'tap');
    } catch (error) {
      feel.toast(`<span>${esc(error.message)}</span>`);
    }
  });
  nameInput.addEventListener('input', () => { dirty = true; });
  root.querySelector('[data-delete-build]')?.addEventListener('submit', event => {
    if (!confirm('删掉这件作品？删了就找不回来了。')) event.preventDefault();
    else dirty = false;
  });
  addEventListener('beforeunload', event => { if (dirty && parts.length) { event.preventDefault(); event.returnValue = ''; } });

  root.querySelector(`[data-color="${color}"]`)?.setAttribute('aria-checked', 'true');
  root.querySelectorAll('[data-color]').forEach(other => other.setAttribute('aria-checked', String(other.dataset.color === color)));
  render();
  // 打开一件作品时，零件从下往上一个个落回板子上
  if (feel.motionOn()) [...layer.children].forEach((node, i) => feel.play(node.firstChild, [{transform: 'translateY(-14px) scale(.6)', opacity: 0}, {transform: 'none', opacity: 1}],
    {duration: 360, delay: Math.min(i, 40) * 18, easing: feel.B, fill: 'backwards'}));
})();
