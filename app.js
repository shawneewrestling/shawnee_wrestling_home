/* Shawnee Wrestling site-v2 front end */
(async function () {
  const DATA_URL = 'data/wrestling_data.json';
  const AWARDS_URL = 'data/awards.json';
  const VARSITY_URL = 'data/varsity.json';

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

  function oppCell(m) {
    const name = m.opponent || m.event_name || '—';
    const logo = m.opponent_logo_local || m.opponent_logo;
    const img = logo
      ? `<img src="${esc(logo)}" alt="" loading="lazy" onerror="this.style.display='none'" />`
      : '';
    return `<div class="opp">${img}<span>${esc(name)}</span></div>`;
  }

  function resultBadge(m) {
    if (m.result === 'W') return `<span class="badge w">W ${esc(m.score_display || '')}</span>`;
    if (m.result === 'L') return `<span class="badge l">L ${esc(m.score_display || '')}</span>`;
    if (m.home_away === 'event' || m.event_kind) return `<span class="badge ev">Event</span>`;
    return '—';
  }

  function decadeLabel(season) {
    const y = parseInt(String(season).slice(0, 4), 10);
    if (!y) return 'Unknown';
    const start = Math.floor(y / 10) * 10;
    return `${start}s`;
  }

  const page = document.body && document.querySelector('.nav a.active')?.textContent?.trim();

  try {
    if (page === 'Awards') {
      const awardsData = await loadJson(AWARDS_URL);
      renderAwards(awardsData);
      return;
    }

    if (page === 'Roster') {
      const [data, varsity] = await Promise.all([loadJson(DATA_URL), loadJson(VARSITY_URL)]);
      renderVarsity(varsity, data);
      return;
    }
    const data = await loadJson(DATA_URL);
    if (page === 'Home') renderHome(data);
    else if (page === 'Full Roster') renderRoster(data);
    else if (page === 'Schedule / Results') renderSchedule(data);
    else if (page === 'Standings') renderStandings(data);
    else if (page === 'Stats') renderStats(data);
  } catch (e) {
    console.error(e);
    const main = document.querySelector('main');
    if (main) main.insertAdjacentHTML('afterbegin', `<div class="callout warn">${esc(e.message)}</div>`);
  }

  function renderHome(data) {
    const m = data.metadata || {};
    document.getElementById('homeMeta').innerHTML = `
      <span><strong>Season</strong> ${esc(m.season)}</span>
      <span><strong>Dual record</strong> ${esc(m.dual_record)}</span>
      <span><strong>Roster</strong> ${(data.roster || []).length}</span>
      <span><strong>Events</strong> ${(data.schedule || []).length}</span>
      <span><strong>Updated</strong> ${esc(m.generated_at)}</span>`;
    document.getElementById('homeCards').innerHTML = `
      <div class="stat-card"><div class="label">Dual record</div><div class="value">${esc(m.dual_record || '—')}</div></div>
      <div class="stat-card"><div class="label">Wrestlers</div><div class="value">${(data.roster || []).length}</div></div>
      <div class="stat-card"><div class="label">Schedule events</div><div class="value">${(data.schedule || []).length}</div></div>
      <div class="stat-card"><div class="label">Scored duals</div><div class="value">${(data.dual_scores?.duals || []).length}</div></div>`;
    const tb = document.querySelector('#homeDuals tbody');
    tb.innerHTML = (data.dual_scores?.duals || []).map((d) => `
      <tr><td>${esc(d.opponent)}</td><td>${d.shawnee}-${d.opp}</td>
      <td><span class="badge ${d.result === 'W' ? 'w' : 'l'}">${esc(d.result)}</span></td></tr>`).join('');
  }


  function renderVarsity(varsity, data) {
    const note = document.getElementById('varsityNote');
    if (note) note.textContent = varsity.derivation_note || '';
    const c = varsity.counts || {};
    document.getElementById('varsityMeta').innerHTML = `
      <span><strong>Varsity</strong> ${c.total ?? (varsity.wrestlers||[]).length}</span>
      <span><strong>Full roster</strong> ${c.full_roster ?? (data.roster||[]).length}</span>
      <span><strong>Derivation</strong> ${esc(varsity.derivation || '—')}</span>
      <span><strong>Season</strong> ${esc(varsity.season || '')}</span>`;
    const rows = (varsity.wrestlers || []).slice();
    document.querySelector('#varsityTable tbody').innerHTML = rows.map((w) => `
      <tr>
        <td>${esc(w.weight || '—')}</td>
        <td>${esc(w.name)}</td>
        <td>${esc(w.grade || '—')}</td>
        <td>${esc((w.wins ?? 0) + '-' + (w.losses ?? 0))}</td>
        <td>${w.starter ? '★' : ''}</td>
      </tr>`).join('') || '<tr><td colspan="5">No varsity wrestlers</td></tr>';
  }

  function renderRoster(data) {
    const rows = (data.roster || []).slice().sort((a, b) => {
      const aw = parseInt(a.weight, 10) || 999, bw = parseInt(b.weight, 10) || 999;
      return aw - bw || (a.last_name || '').localeCompare(b.last_name || '');
    });
    document.querySelector('#rosterTable tbody').innerHTML = rows.map((w) => `
      <tr>
        <td>${esc(w.name)}</td>
        <td>${esc(w.weight || '—')}</td>
        <td>${esc(w.grade || '—')}</td>
        <td>${esc((w.wins ?? 0) + '-' + (w.losses ?? 0))}</td>
      </tr>`).join('');
  }

  function renderSchedule(data) {
    const rec = data.metadata?.dual_record || data.dual_scores?.record;
    document.getElementById('schedMeta').innerHTML = `<span><strong>Dual record</strong> ${esc(rec)}</span>
      <span><strong>Events</strong> ${(data.schedule || []).length}</span>`;
    document.querySelector('#scheduleTable tbody').innerHTML = (data.schedule || []).map((m) => `
      <tr>
        <td>${esc(m.date_iso || m.date)}</td>
        <td>${oppCell(m)}</td>
        <td>${esc(m.home_away === 'home' ? 'Home' : m.home_away === 'away' ? 'Away' : (m.location || 'Event'))}</td>
        <td>${esc(m.time || 'TBD')}</td>
        <td>${resultBadge(m)}</td>
      </tr>`).join('');
  }

  function renderStandings(data) {
    const s = data.standings || {};
    document.getElementById('standingsNote').textContent = s.note || '';
    document.getElementById('standingsMeta').innerHTML =
      `<span><strong>Shawnee duals</strong> ${esc(s.shawnee_dual_record)}</span>
       <span><strong>Source</strong> ${esc(s.source)}</span>`;
    document.querySelector('#standingsTable tbody').innerHTML = (s.rows || []).map((r) => `
      <tr>
        <td>${esc(r.opponent)}</td>
        <td>${esc(r.score)}</td>
        <td><span class="badge ${r.result === 'W' ? 'w' : 'l'}">${esc(r.result)}</span></td>
      </tr>`).join('');
  }

  function renderStats(data) {
    const rows = (data.stats || data.roster || []).slice().sort((a, b) => (b.wins || 0) - (a.wins || 0) || (a.losses || 0) - (b.losses || 0));
    document.querySelector('#statsTable tbody').innerHTML = rows.map((w) => {
      const wins = w.wins || 0, losses = w.losses || 0;
      const pct = (wins + losses) ? ((wins / (wins + losses)) * 100).toFixed(1) + '%' : '—';
      return `<tr>
        <td>${esc(w.name)}</td>
        <td>${esc(w.weight || '—')}</td>
        <td>${esc(w.grade || '—')}</td>
        <td>${wins}</td><td>${losses}</td><td>${pct}</td>
        <td>${w.pins == null ? '—' : esc(w.pins)}</td>
      </tr>`;
    }).join('');
  }

  function renderAwards(data) {
    const awards = data.awards || [];
    const meta = data.meta?.njsiaa_placements_2025_26;
    document.getElementById('awardsMeta').innerHTML =
      `<strong>${awards.length}</strong> award rows (${data.seed_count || 0} historical seed + ${data.derived_2025_26_count || 0} auto-derived for 2025-26).
       ${meta ? `<br/><em>NJSIAA 2025-26 placements:</em> ${esc(meta.status)} — ${esc(meta.note)}` : ''}`;

    // Group into cards
    const cards = [];
    const byName = {};
    for (const a of awards) {
      const name = a.award_name || 'Award';
      if (name === 'District Champions' || a.award_category === 'district') {
        const dec = decadeLabel(a.season);
        const key = `District Champions — ${dec}`;
        (byName[key] ||= { title: key, kind: 'district', rows: [] }).rows.push(a);
      } else {
        (byName[name] ||= { title: name, kind: a.award_category || 'other', rows: [] }).rows.push(a);
      }
    }
    const order = Object.keys(byName).sort((a, b) => {
      const da = a.startsWith('District Champions') ? 1 : 0;
      const db = b.startsWith('District Champions') ? 1 : 0;
      if (da !== db) return da - db;
      return a.localeCompare(b);
    });

    const filters = document.getElementById('awardFilters');
    const kinds = ['all', ...new Set(Object.values(byName).map((c) => c.kind))];
    filters.innerHTML = kinds.map((k) =>
      `<button type="button" data-kind="${esc(k)}" class="${k === 'all' ? 'active' : ''}">${esc(k)}</button>`
    ).join('');

    const grid = document.getElementById('awardsGrid');
    function paint(kind) {
      grid.innerHTML = order.filter((t) => kind === 'all' || byName[t].kind === kind).map((t) => {
        const card = byName[t];
        const rows = card.rows.slice().sort((a, b) => String(a.season).localeCompare(String(b.season)) || String(a.wrestler || '').localeCompare(String(b.wrestler || '')));
        const body = rows.map((a) => {
          const left = esc(a.season || '');
          const mid = esc(a.wrestler || a.details || '');
          const right = esc(a.weight || a.placement || a.value || '');
          return `<div class="row"><span>${left}</span><span>${mid}</span><span>${right}</span></div>`;
        }).join('');
        return `<article class="chevron-card" data-kind="${esc(card.kind)}">
          <div class="title">${esc(card.title)}</div>
          <div class="body">${body}</div>
          <div class="s-logo" title="Shawnee">S</div>
        </article>`;
      }).join('');
    }
    paint('all');
    filters.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-kind]');
      if (!btn) return;
      filters.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      paint(btn.dataset.kind);
    });
  }
})();
