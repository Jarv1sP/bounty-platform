/* 页面级交互：发现页的任务墙翻页和推荐卡，发布页的实时预览。手感工具来自 ui.js 的 window.bounty。 */
(() => {
  const feel = window.bounty || {play() { return null; }, sfx() {}, motionOn: () => false, A: 'ease', B: 'ease', C: 'ease'};

  /* ---------- 任务墙：一页 12 张，翻页时整块滑过去 ---------- */
  const canvas = document.querySelector('.wall-canvas');
  if (canvas) {
    const zones = [...canvas.querySelectorAll('.wall-zone')];
    const position = document.querySelector('[data-wall-position]');
    let current = 0;
    const go = step => {
      const target = (current + step + zones.length) % zones.length;
      if (target === current) return;
      zones[current].hidden = true;
      zones[target].hidden = false;
      current = target;
      canvas.dataset.zone = String(current);
      if (position) position.textContent = String(current + 1);
      feel.play(canvas, [{transform: `translateX(${step > 0 ? 40 : -40}px)`, opacity: 0}, {transform: 'none', opacity: 1}], {duration: 260, easing: feel.C});
      feel.sfx('tap');
      const top = canvas.closest('.browse')?.getBoundingClientRect().top;
      if (top < 0) canvas.closest('.browse').scrollIntoView({behavior: feel.motionOn() ? 'smooth' : 'auto'});
    };
    document.querySelector('[data-wall-next]')?.addEventListener('click', () => go(1));
    document.querySelector('[data-wall-prev]')?.addEventListener('click', () => go(-1));
  }

  /* ---------- 推荐卡：不感兴趣时先甩出去再提交 ---------- */
  document.querySelectorAll('.pick-x').forEach(form => form.addEventListener('submit', event => {
    const card = form.closest('.pick');
    const motion = feel.play(card, [{transform: 'none', opacity: 1}, {transform: 'translateY(16px) rotate(4deg) scale(.94)', opacity: 0}], {duration: 220, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards'});
    if (!motion) return;
    event.preventDefault();
    motion.finished.then(() => HTMLFormElement.prototype.submit.call(form));
  }));
  document.querySelectorAll('[data-shuffle]').forEach(link => link.addEventListener('click', () => {
    document.querySelectorAll('.pick').forEach((card, i) => feel.play(card, [{transform: 'none'}, {transform: 'translateY(8px) scale(.97)', opacity: .4}], {duration: 160, delay: i * 30, fill: 'forwards'}));
  }));

  /* ---------- 发布页：边填边看「发现」里的样子 ---------- */
  const editor = document.querySelector('[data-editor]');
  if (editor) {
    const out = name => document.querySelectorAll(`[data-out="${name}"]`);
    const template = document.querySelector('template[data-medal-template]');
    const medal = key => template.content.querySelector(`[data-key="${key}"]`).innerHTML;
    const names = {'light-normal': '点', 'standard-normal': '线', 'major-normal': '面', 'light-urgent': '点·急', 'standard-urgent': '线·急', 'major-urgent': '面·急'};
    const xp = {light: 10, standard: 30, major: 80};
    const effort = {light: '半天内', standard: '一两天', major: '一周左右'};
    const tagsInput = editor.querySelector('[name=tags]');
    let lastKey = '';
    const escape = text => text.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const update = () => {
      const value = name => editor.querySelector(`[name=${name}]:checked`)?.value || editor.querySelector(`[name=${name}]`)?.value || '';
      const importance = value('importance') || 'standard';
      const urgency = value('urgency') || 'normal';
      const key = `${importance}-${urgency}`;
      out('title').forEach(el => { el.textContent = value('title') || '任务标题'; });
      out('description').forEach(el => { el.textContent = value('description') || '任务说明会显示在这里。'; });
      const tags = (tagsInput.value || '').split(/[,，、;；\s]+/).map(t => t.replace(/^#/, '')).filter(Boolean).slice(0, 3);
      out('tags').forEach(el => { el.innerHTML = tags.map(t => `<span class="tag">${escape(t)}</span>`).join(''); });
      out('effort').forEach(el => { el.textContent = effort[importance]; });
      out('xp').forEach(el => { el.textContent = `+${urgency === 'urgent' ? xp[importance] * 1.5 : xp[importance]}`; });
      out('medal').forEach(el => { el.textContent = `完成的人得到「${names[key]}」`; });
      if (key !== lastKey) {
        document.querySelector('[data-preview-medal]').innerHTML = medal(key);
        const big = document.querySelector('[data-preview-medal-big]');
        big.innerHTML = medal(key);
        const svg = big.querySelector('svg');
        if (lastKey && feel.motionOn()) { svg.classList.add('anim'); feel.sfx('tap'); }
        lastKey = key;
      }
    };
    editor.addEventListener('input', update);
    editor.addEventListener('change', update);
    update();
    document.querySelectorAll('[data-tag-suggest] [data-tag]').forEach(button => button.addEventListener('click', () => {
      const tags = tagsInput.value.split(/[,，、;；\s]+/).filter(Boolean);
      if (!tags.includes(button.dataset.tag) && tags.length < 5) tags.push(button.dataset.tag);
      tagsInput.value = tags.join(' ') + ' ';
      tagsInput.focus();
      feel.play(button, [{transform: 'scale(.9)'}, {transform: 'scale(1)'}], {duration: 200, easing: feel.B});
      update();
    }));
  }
})();
