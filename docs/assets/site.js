// Progressive enhancement: research content and all result rows exist in HTML.
(() => {
  const toast = (message) => {
    const status = document.querySelector('#status');
    if (!status) return;
    status.textContent = message;
    status.classList.add('visible');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => status.classList.remove('visible'), 3500);
  };

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast('Copied to clipboard');
    } catch {
      // Select actual text so the requested manual copy action is possible.
      const area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('aria-label', 'Text to copy');
      area.style.cssText = 'position:fixed;left:20px;bottom:20px;width:calc(100% - 40px);height:120px;z-index:60';
      document.body.append(area);
      area.focus();
      area.select();
      toast('Press Ctrl+C or ⌘C to copy; Escape to close');
      area.addEventListener('keydown', (event) => { if (event.key === 'Escape') area.remove(); });
      area.addEventListener('blur', () => area.remove());
    }
  }

  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', () => copy(document.getElementById(button.dataset.copyTarget).textContent));
  });

  const menu = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#site-nav');
  if (menu && nav) {
    menu.hidden = false;
    nav.dataset.menuOpen = 'false';
    const close = () => { nav.dataset.menuOpen = 'false'; menu.setAttribute('aria-expanded', 'false'); };
    menu.addEventListener('click', () => {
      const open = menu.getAttribute('aria-expanded') !== 'true';
      nav.dataset.menuOpen = String(open);
      menu.setAttribute('aria-expanded', String(open));
    });
    nav.querySelectorAll('a').forEach((a) => a.addEventListener('click', close));
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { close(); menu.focus(); } });
  }

  const form = document.querySelector('#result-filters');
  if (!form) return;
  const rows = [...document.querySelectorAll('[data-result-row]')];
  // Expand metrics into a full-width table row. Native details remain available
  // in the source HTML for readers without JavaScript.
  rows.forEach((row, index) => {
    const details = row.querySelector('.metric-detail');
    const panel = details.querySelector('.metric-popover');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'detail-toggle';
    button.setAttribute('aria-expanded', 'false');
    panel.id = `comparison-metrics-${index}`;
    button.setAttribute('aria-controls', panel.id);
    button.textContent = '12 metrics ＋';
    const expanded = document.createElement('tr');
    expanded.className = 'expanded-result';
    expanded.hidden = true;
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.append(panel);
    expanded.append(cell);
    row.after(expanded);
    details.replaceWith(button);
    row.closeDetail = () => {
      expanded.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      button.textContent = '12 metrics ＋';
    };
    button.addEventListener('click', () => {
      const open = expanded.hidden;
      expanded.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
      button.textContent = open ? 'Hide metrics −' : '12 metrics ＋';
    });
  });
  const fields = ['model', 'method', 'domain'];
  const params = new URLSearchParams(location.search);
  fields.forEach((name) => {
    const field = form.elements.namedItem(name);
    if ([...field.options].some((o) => o.value === params.get(name))) field.value = params.get(name);
  });

  function filter(updateUrl = true) {
    let count = 0;
    const query = new URLSearchParams();
    fields.forEach((name) => {
      const value = form.elements.namedItem(name).value;
      if (value) query.set(name, value);
    });
    rows.forEach((row) => {
      row.hidden = fields.some((name) => query.has(name) && row.dataset[name] !== query.get(name));
      if (!row.hidden) count += 1;
      else row.closeDetail();
    });
    document.querySelector('#result-count').textContent = `${count} comparison${count === 1 ? '' : 's'} · 12 metrics each`;
    const url = new URL(location.href);
    url.search = query.toString();
    document.querySelector('#share-results').href = url.href;
    if (updateUrl) history.replaceState(null, '', url);
  }
  form.hidden = false;
  form.addEventListener('submit', (event) => event.preventDefault());
  form.addEventListener('change', () => filter());
  form.addEventListener('reset', () => setTimeout(() => filter(), 0));
  document.querySelector('#share-results').addEventListener('click', (event) => {
    event.preventDefault();
    copy(event.currentTarget.href);
  });
  filter(false);
})();
