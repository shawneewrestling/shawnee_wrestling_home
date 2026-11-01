/* Historical roster + stats season dropdown (data/history/*). */
(function () {
  const HISTORY_INDEX_URL = 'data/history/index.json';
  const VARSITY_ASSIGN_URL = 'data/varsity_assignments.json';
  const PLAYERS_INDEX_URL = 'data/players_index.json';
  const DATA_URL = 'data/wrestling_data.json';
  const PLACEHOLDER_PHOTO = 'assets/img/wrestler-silhouette.svg';
  const CURRENT_SEASON = '2025-26';

  const page = document.body && document.querySelector('.nav a.active')?.textContent?.trim();
  if (page !== 'Roster' && page !== 'Stats') return;

  async function loadJson(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error('Failed to load ' + url);
    return r.json();
  }

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function seasonIdFromLocation() {
    try {
      const u = new URL(window.location.href);
      const q = u.searchParams.get('season');
      if (q) return q;
    } catch (_) {}
    return null;
  }

  function setSeasonInLocation(seasonId, replace) {
    try {
      const u = new URL(window.location.href);
      u.searchParams.set('season', seasonId);
      history[replace ? 'replaceState' : 'pushState']({}, '', u.pathname + u.search + u.hash);
    } catch (_) {}
  }

  function seasonLabel(id, seasons) {
    const hit = (seasons || []).find((s) => s.id === id);
    if (hit?.label) return hit.label;
    const m = String(id).match(/^(\d{4})-(\d{2})$/);
    if (m) return `${m[1]}-${parseInt(m[1], 10) + 1} Season`;
    return String(id);
  }

  function updateChrome(label) {
    document.querySelectorAll('.site-header .tag').forEach((el) => {
      el.textContent = `Wrestling · ${label}`;
    });
    document.querySelectorAll('.site-footer').forEach((el) => {
      el.textContent = `Shawnee High School Wrestling · ${label}`;
    });
  }

  function photoSrc(photo) {
    return photo || PLACEHOLDER_PHOTO;
  }

  function careerLine(r) {
    if (!r || !r.show_career) return '';
    if (r.career_wins == null || r.career_losses == null) return '';
    return `<div class="meta career">Career ${esc(`${r.career_wins}-${r.career_losses}`)}</div>`;
  }

  function renderVarsityFromAssign(assign, label) {
    const c = assign.counts || {};
    const meta = document.getElementById('varsityMeta');
    if (meta) {
      meta.innerHTML = `
        <span><strong>Filled</strong> ${c.filled ?? 0} / ${c.weight_classes ?? 14}</span>
        <span><strong>Vacant</strong> ${c.vacant ?? 0}</span>
        <span><strong>Full roster</strong> ${c.full_roster ?? '—'}</span>
        <span><strong>Season</strong> ${esc(label)}</span>`;
    }
    const grid = document.getElementById('varsityGrid');
    if (!grid) return;
    const slots = assign.slots || [];
    grid.innerHTML = slots.map((s) => {
      if (s.vacant) {
        return `<div class="wrestler-tile vacant">
          <div class="photo-wrap">
            <span class="wt-chip">${esc(s.assigned_weight)}</span>
            <img src="${PLACEHOLDER_PHOTO}" alt="" />
          </div>
          <div class="body">
            <div class="name">Vacant</div>
            <div class="meta">NJSIAA ${esc(s.assigned_weight)}</div>
          </div>
        </div>`;
      }
      const href = s.player_page || '#';
      const prest = s.prestige_points ? `<span class="prest-chip">${esc(s.prestige_points)} pts</span>` : '';
      const rec = `${s.wins ?? 0}-${s.losses ?? 0}`;
      return `<a class="wrestler-tile" href="${esc(href)}">
        <div class="photo-wrap">
          <span class="wt-chip">${esc(s.assigned_weight)}</span>
          ${prest}
          <img src="${esc(photoSrc(s.photo))}" alt="${esc(s.name)}" loading="lazy"
               onerror="this.src='${PLACEHOLDER_PHOTO}'" />
        </div>
        <div class="body">
          <div class="name">${esc(s.name)}</div>
          <div class="meta">${esc(s.grade || '')} · ${esc(rec)}</div>
          ${careerLine(s)}
        </div>
      </a>`;
    }).join('') || '<p>No assignments</p>';
  }

  function breakdownHeaders(hasBreakdown) {
    if (!hasBreakdown) {
      return '<tr><th>Name</th><th>Wt</th><th>Grade</th><th>W</th><th>L</th><th>Win%</th><th>Pins</th></tr>';
    }
    return `<tr>
      <th>Name</th><th>Wt</th><th>Grade</th><th>W</th><th>L</th><th>Win%</th>
      <th>Fall</th><th>TF</th><th>MD</th><th>Dec</th>
      <th>L-Fall</th><th>L-TF</th><th>L-MD</th><th>L-Dec</th>
    </tr>`;
  }

  function renderStatsTable(statsDoc, label) {
    const title = document.querySelector('main h1.page-title');
    if (title) title.textContent = `${label.replace(/ Season$/, '')} Season Stats`;
    const sub = document.querySelector('main .page-sub');
    if (sub) {
      sub.textContent = statsDoc.has_breakdown
        ? `Individual W-L breakdown for the ${label}.`
        : `Individual W-L for the ${label}. Pin / tech / major counts populate when available.`;
    }
    const thead = document.querySelector('#statsTable thead');
    const tbody = document.querySelector('#statsTable tbody');
    if (!tbody) return;
    const hasBreakdown = !!statsDoc.has_breakdown;
    if (thead) thead.innerHTML = breakdownHeaders(hasBreakdown);
    const rows = (statsDoc.wrestlers || []).slice().sort(
      (a, b) => (b.wins || b.win || 0) - (a.wins || a.win || 0)
        || (a.losses || a.loss || 0) - (b.losses || b.loss || 0)
    );
    tbody.innerHTML = rows.map((w) => {
      const wins = w.wins ?? w.win ?? 0;
      const losses = w.losses ?? w.loss ?? 0;
      const pct = (wins + losses) ? ((wins / (wins + losses)) * 100).toFixed(1) + '%' : '—';
      const href = w.player_page || '';
      const nameCell = href
        ? `<a href="${esc(href)}">${esc(w.name)}</a>`
        : esc(w.name);
      if (!hasBreakdown) {
        const pins = w.pins ?? w.w_fall;
        return `<tr>
          <td>${nameCell}</td>
          <td>${esc(w.weight || '—')}</td>
          <td>${esc(w.grade || '—')}</td>
          <td>${wins}</td><td>${losses}</td><td>${pct}</td>
          <td>${pins == null ? '—' : esc(pins)}</td>
        </tr>`;
      }
      const cell = (v) => (v == null || v === '' ? '—' : esc(v));
      return `<tr>
        <td>${nameCell}</td>
        <td>${esc(w.weight || primaryWeight(w.weights) || '—')}</td>
        <td>${esc(w.grade || '—')}</td>
        <td>${wins}</td><td>${losses}</td><td>${pct}</td>
        <td>${cell(w.w_fall)}</td><td>${cell(w.w_tech)}</td><td>${cell(w.w_maj)}</td><td>${cell(w.w_dec)}</td>
        <td>${cell(w.l_fall)}</td><td>${cell(w.l_tech)}</td><td>${cell(w.l_maj)}</td><td>${cell(w.l_dec)}</td>
      </tr>`;
    }).join('');
  }

  function primaryWeight(weights) {
    if (!weights) return null;
    const m = String(weights).match(/\d+/);
    return m ? m[0] : null;
  }

  async function loadHistoryIndex() {
    try {
      return await loadJson(HISTORY_INDEX_URL);
    } catch (_) {
      return { default: CURRENT_SEASON, seasons: [{ id: CURRENT_SEASON, label: '2025-2026 Season', roster: true, stats: false }] };
    }
  }

  async function showRosterSeason(seasonId, seasons) {
    const label = seasonLabel(seasonId, seasons);
    updateChrome(label);
    if (seasonId === CURRENT_SEASON) {
      const assign = await loadJson(VARSITY_ASSIGN_URL);
      renderVarsityFromAssign(assign, label);
      return;
    }
    const path = `data/history/${seasonId}_roster.json`;
    const assign = await loadJson(path);
    renderVarsityFromAssign(assign, label);
  }

  async function showStatsSeason(seasonId, seasons) {
    const label = seasonLabel(seasonId, seasons);
    updateChrome(label);
    if (seasonId === CURRENT_SEASON) {
      // Live wrestling_data stats (may lack full breakdown)
      const [data, index] = await Promise.all([
        loadJson(DATA_URL),
        loadJson(PLAYERS_INDEX_URL).catch(() => null),
      ]);
      const pages = Object.create(null);
      for (const w of (index && index.wrestlers) || []) {
        if (w.player_page && w.name) pages[String(w.name).trim().toLowerCase()] = w.player_page;
      }
      const roster = (data.stats || data.roster || []).map((w) => ({
        ...w,
        wins: w.wins || 0,
        losses: w.losses || 0,
        pins: w.pins,
        player_page: pages[String(w.name || '').trim().toLowerCase()] || null,
      }));
      renderStatsTable({ wrestlers: roster, has_breakdown: false }, label);
      return;
    }
    const statsDoc = await loadJson(`data/history/${seasonId}_stats.json`);
    renderStatsTable(statsDoc, label);
  }

  (async function init() {
    const selectEl = document.getElementById('seasonSelect');
    if (!selectEl) return;

    // Prevent app.js default Roster/Stats path from racing: clear loading only via us.
    window.__historyControlsSeason = true;

    const index = await loadHistoryIndex();
    let seasons = index.seasons || [];
    // Ensure current season always listed
    if (!seasons.some((s) => s.id === CURRENT_SEASON)) {
      seasons = [{ id: CURRENT_SEASON, label: '2025-2026 Season', roster: true, stats: true }, ...seasons];
    }
    // Roster/Stats: only seasons that have the matching artifact (current always ok)
    const filtered = seasons.filter((s) => {
      if (s.id === CURRENT_SEASON) return true;
      if (page === 'Roster') return s.roster !== false;
      if (page === 'Stats') return s.stats !== false;
      return true;
    });

    const defaultId = index.default || CURRENT_SEASON;
    let currentId = seasonIdFromLocation() || defaultId;
    if (!filtered.some((s) => s.id === currentId)) currentId = defaultId;

    selectEl.innerHTML = filtered.map((s) =>
      `<option value="${esc(s.id)}"${s.id === currentId ? ' selected' : ''}>${esc(s.label || s.id)}</option>`
    ).join('');

    async function show(id, { replaceUrl } = {}) {
      currentId = id;
      selectEl.value = id;
      setSeasonInLocation(id, !!replaceUrl);
      if (page === 'Roster') await showRosterSeason(id, filtered);
      else await showStatsSeason(id, filtered);
    }

    selectEl.addEventListener('change', () => {
      show(selectEl.value, { replaceUrl: false }).catch((e) => {
        console.error(e);
        const main = document.querySelector('main');
        if (main) main.insertAdjacentHTML('afterbegin', `<div class="callout warn">${esc(e.message)}</div>`);
      });
    });
    window.addEventListener('popstate', () => {
      const id = seasonIdFromLocation() || defaultId;
      show(id, { replaceUrl: true }).catch(console.error);
    });

    await show(currentId, { replaceUrl: true });
  })().catch((e) => {
    console.error(e);
    const main = document.querySelector('main');
    if (main) main.insertAdjacentHTML('afterbegin', `<div class="callout warn">${esc(e.message)}</div>`);
  });
})();
