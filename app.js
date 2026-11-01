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

  function logoImg(local, remote, alt) {
    const logo = local || remote;
    if (!logo) return '';
    return `<img src="${esc(logo)}" alt="${esc(alt || '')}" loading="lazy" onerror="this.style.display='none'" />`;
  }

  function oppCell(m) {
    const name = m.opponent || m.event_name || '—';
    const note = m.split_note ? `<small class="split-note">${esc(m.split_note)}</small>` : '';
    const img = logoImg(m.opponent_logo_local, m.opponent_logo, name);
    return `<div class="opp">${img}<span>${esc(name)}${note}</span></div>`;
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
    const duals = (data.dual_scores?.duals || []).filter((d) => !d.split);
    tb.innerHTML = duals.map((d) => `
      <tr>
        <td><div class="opp">${logoImg(d.opponent_logo_local, d.opponent_logo, d.opponent)}<span>${esc(d.opponent)}</span></div></td>
        <td>${d.shawnee}-${d.opp}</td>
        <td><span class="badge ${d.result === 'W' ? 'w' : 'l'}">${esc(d.result)}</span></td>
      </tr>`).join('');
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

  function boutLine(b) {
    const res = b.result === 'W' ? 'W' : b.result === 'L' ? 'L' : '—';
    const oppSchool = b.opponent_team ? ` (${b.opponent_team})` : '';
    const rnd = b.round ? `${b.round} · ` : '';
    return `<li><strong>${esc(res)}</strong> ${esc(rnd)}${esc(b.opponent_wrestler || '—')}${esc(oppSchool)} · ${esc(b.score || b.win_type || '')}</li>`;
  }

  function tournamentPanel(m, data) {
    const key = m.tournament_key || m.event_id;
    const tr = (data.tournament_results || {})[key];
    if (!tr || !(tr.wrestlers || []).length) return '';
    let wrestlers = tr.wrestlers || [];
    if (m.filter_opponent) {
      const want = String(m.filter_opponent).toLowerCase();
      wrestlers = wrestlers.map((w) => {
        const bouts = (w.bouts || []).filter((b) => String(b.opponent_team || '').toLowerCase().includes(want.split('(')[0].trim()) || want.includes(String(b.opponent_team || '').toLowerCase().slice(0, 8)));
        // softer match: resolve by slug-ish containment
        const bouts2 = (w.bouts || []).filter((b) => {
          const ot = String(b.opponent_team || '').toLowerCase();
          return ot && (want.includes(ot.slice(0, 6)) || ot.includes(want.slice(0, 6)));
        });
        return { ...w, bouts: bouts2.length ? bouts2 : bouts };
      }).filter((w) => (w.bouts || []).length);
    }
    if (!wrestlers.length) return '';
    const cards = wrestlers.map((w) => {
      const place = w.placement ? `<span class="place">${esc(w.placement)}</span>` : '';
      return `<details class="wrestler-card">
        <summary><span class="wt">${esc(w.weight || '—')}</span> <span class="nm">${esc(w.wrestler)}</span> <span class="rec">${esc(w.record)}</span> ${place}</summary>
        <ul class="bouts">${(w.bouts || []).map(boutLine).join('') || '<li>No bouts</li>'}</ul>
      </details>`;
    }).join('');
    return `<tr class="expand-row"><td colspan="5"><div class="tournament-panel">${cards}</div></td></tr>`;
  }

  function renderSchedule(data) {
    const rec = data.metadata?.dual_record || data.dual_scores?.record;
    document.getElementById('schedMeta').innerHTML = `<span><strong>Dual record</strong> ${esc(rec)}</span>
      <span><strong>Listings</strong> ${(data.schedule || []).length}</span>`;
    const body = document.querySelector('#scheduleTable tbody');
    body.innerHTML = (data.schedule || []).map((m) => {
      const expand = m.expandable ? `<button type="button" class="expand-btn" data-eid="${esc(m.tournament_key || m.event_id)}" aria-expanded="false">Details</button>` : '';
      const main = `<tr class="sched-row" data-eid="${esc(m.event_id || '')}">
        <td>${esc(m.date_iso || m.date)}</td>
        <td>${oppCell(m)}</td>
        <td>${esc(m.home_away === 'home' ? 'Home' : m.home_away === 'away' ? 'Away' : (m.location || 'Event'))}</td>
        <td>${esc(m.time || 'TBD')} ${expand}</td>
        <td>${resultBadge(m)}</td>
      </tr>`;
      // Pre-render collapsed panel as hidden sibling; toggled by button
      const panel = m.expandable ? tournamentPanel(m, data).replace('class="expand-row"', 'class="expand-row hidden"') : '';
      return main + panel;
    }).join('');
    body.querySelectorAll('.expand-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const tr = btn.closest('tr');
        const panel = tr && tr.nextElementSibling;
        if (!panel || !panel.classList.contains('expand-row')) return;
        const open = panel.classList.toggle('hidden') === false;
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        btn.textContent = open ? 'Hide' : 'Details';
      });
    });
  }

  function renderStandings(data) {
    const s = data.standings || {};
    document.getElementById('standingsNote').textContent = s.note || '';
    document.getElementById('standingsMeta').innerHTML =
      `<span><strong>Shawnee duals</strong> ${esc(s.shawnee_dual_record)}</span>
       <span><strong>Source</strong> ${esc(s.source)}</span>`;
    document.querySelector('#standingsTable tbody').innerHTML = (s.rows || []).map((r) => `
      <tr>
        <td><div class="opp">${logoImg(r.opponent_logo_local, r.opponent_logo, r.opponent)}<span>${esc(r.opponent)}</span></div></td>
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

  function formatChevronTitle(title) {
    // Match live banners: stacked varsity words, optional decade subtitle.
    let main = String(title || 'Award');
    let sub = '';
    const m = main.match(/^(.*?)\s*[—–]\s*(.+)$/); // em/en dash only (keep hyphens in All-American)
    if (m) { main = m[1].trim(); sub = m[2].trim(); }
    main = main.replace(/\s*\(.*?\)\s*/g, ' ').replace(/\s+/g, ' ').trim();
    const up = main.toUpperCase();
    let lines;
    if (/\bCHAMPIONS$/.test(up) && up.includes(' ')) {
      const i = up.lastIndexOf(' CHAMPIONS');
      lines = [up.slice(0, i).trim(), 'CHAMPIONS'];
    } else if (/\bCHAMPIONSHIP$/.test(up) && up.includes(' ')) {
      const i = up.lastIndexOf(' CHAMPIONSHIP');
      lines = [up.slice(0, i).trim(), 'CHAMPIONSHIP'];
    } else if (up === 'NCAA ALL-AMERICAN') {
      lines = ['NCAA', 'ALL-AMERICAN'];
    } else if (up.length > 14 && up.includes(' ')) {
      const parts = up.split(' ');
      const mid = Math.ceil(parts.length / 2);
      lines = [parts.slice(0, mid).join(' '), parts.slice(mid).join(' ')];
    } else {
      lines = [up];
    }
    const lineHtml = lines.map((l) => esc(l)).join('<br />');
    const subHtml = sub ? `<span class="sub">${esc(sub.toUpperCase())}</span>` : '';
    return lineHtml + subHtml;
  }

  function awardRowCells(a, kind) {
    const name = a.wrestler || a.details || '';
    if (kind === 'leaderboard' || a.award_category === 'leaderboard') {
      // Live Career Wins / Pins: value | name | years
      return {
        left: a.value != null ? String(a.value) : '',
        mid: name,
        right: a.years_active || a.details || a.season || '',
        rowClass: 'row leaderboard',
      };
    }
    if (kind === 'season_milestone' || a.award_category === 'season_milestone') {
      return {
        left: a.value != null ? String(a.value) : (a.season || ''),
        mid: name,
        right: a.weight || a.details || '',
        rowClass: 'row',
      };
    }
    if (kind === 'team' || a.award_category === 'team') {
      return {
        left: a.season || '',
        mid: a.details || name || 'Team title',
        right: a.placement || '',
        rowClass: 'row',
      };
    }
    // district / region / state / college / default: year | wrestler | weight/placement
    return {
      left: a.season || '',
      mid: name,
      right: a.weight || a.placement || (a.value != null ? String(a.value) : ''),
      rowClass: 'row',
    };
  }

  function renderAwards(data) {
    const awards = data.awards || [];
    const meta = data.meta?.njsiaa_placements_2025_26;
    document.getElementById('awardsMeta').innerHTML =
      `<strong>${awards.length}</strong> award rows (${data.seed_count || 0} historical seed + ${data.derived_2025_26_count || 0} auto-derived for 2025-26).
       ${meta ? `<br/><em>NJSIAA 2025-26 placements:</em> ${esc(meta.status)} — ${esc(meta.note)}` : ''}`;

    // Group into cards
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
        const rows = card.rows.slice().sort((a, b) => {
          if (card.kind === 'leaderboard') {
            const av = Number(a.value), bv = Number(b.value);
            if (!Number.isNaN(av) && !Number.isNaN(bv) && bv !== av) return bv - av;
          }
          return String(a.season || '').localeCompare(String(b.season || ''))
            || String(a.wrestler || '').localeCompare(String(b.wrestler || ''));
        });
        let prevSeason = null;
        const body = rows.map((a) => {
          const cells = awardRowCells(a, card.kind);
          // Live district/region banners omit repeated year labels
          let left = cells.left;
          if ((card.kind === 'district' || card.kind === 'region' || card.kind === 'state') && left && left === prevSeason) {
            left = '';
          } else if (cells.left) {
            prevSeason = cells.left;
          }
          return `<div class="${cells.rowClass}"><span>${esc(left)}</span><span>${esc(cells.mid)}</span><span>${esc(cells.right)}</span></div>`;
        }).join('');
        return `<article class="chevron-card" data-kind="${esc(card.kind)}">
          <div class="chevron-card-inner">
            <div class="title">${formatChevronTitle(card.title)}</div>
            <div class="body">${body}</div>
            <div class="foot"><img class="s-logo" src="assets/img/shawnee-s.png" alt="Shawnee S" width="58" height="58" /></div>
          </div>
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
