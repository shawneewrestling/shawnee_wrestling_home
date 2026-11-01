/* Shawnee Wrestling site-v2 front end */
(async function () {
  const DATA_URL = 'data/wrestling_data.json';
  const AWARDS_URL = 'data/awards.json';
  const VARSITY_URL = 'data/varsity.json';
  const VARSITY_ASSIGN_URL = 'data/varsity_assignments.json';
  const PLAYERS_INDEX_URL = 'data/players_index.json';
  const STANDINGS_URL = 'data/standings.json';
  const COACH_HISTORY_URL = 'data/coaching_history.json';
  const HOME_ROSTER_URL = 'data/home_roster.json';
  const PLACEHOLDER_PHOTO = 'assets/img/wrestler-silhouette.svg';

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
    if (m.result === 'T') return `<span class="badge ev">T ${esc(m.score_display || '')}</span>`;
    if (m.status === 'final' || m.completed || m.result_label === 'Final') {
      if (m.results_unavailable) {
        return `<span class="badge final" title="${esc(m.result_note || 'Bout cards unavailable')}">Final</span>`;
      }
      return `<span class="badge final">Final</span>`;
    }
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
      const [data, assign] = await Promise.all([loadJson(DATA_URL), loadJson(VARSITY_ASSIGN_URL)]);
      renderVarsityCards(assign, data);
      return;
    }
    if (page === 'Full Roster') {
      const [data, index] = await Promise.all([loadJson(DATA_URL), loadJson(PLAYERS_INDEX_URL).catch(() => null)]);
      renderFullRosterSearchable(data, index);
      return;
    }
    if (page === 'Standings') {
      const standings = await loadJson(STANDINGS_URL);
      renderConferenceStandings(standings);
      return;
    }
    if (page === 'Coach Stats') {
      const coachHist = await loadJson(COACH_HISTORY_URL);
      renderCoachStats(coachHist);
      return;
    }
    const data = await loadJson(DATA_URL);
    if (page === 'Home') {
      const homeRoster = await loadJson(HOME_ROSTER_URL).catch(() => null);
      renderHome(data, homeRoster);
      return;
    }
    else if (page === 'Schedule / Results') renderSchedule(data);
    else if (page === 'Results') renderResults(data);
    else if (page === 'Stats') renderStats(data);
  } catch (e) {
    console.error(e);
    const main = document.querySelector('main');
    if (main) main.insertAdjacentHTML('afterbegin', `<div class="callout warn">${esc(e.message)}</div>`);
  }

  function renderHome(data, homeRoster) {
    const m = data.metadata || {};
    const ds = data.dual_scores || {};
    const dualRec = m.dual_record || ds.record || '—';
    const confRec = m.conference_record || ds.conference_record || '—';
    document.getElementById('homeMeta').innerHTML = `
      <span><strong>Season</strong> ${esc(m.season)}</span>
      <span><strong>Dual record</strong> ${esc(dualRec)}</span>
      <span><strong>Conference</strong> ${esc(confRec)}</span>
      <span><strong>Roster</strong> ${(data.roster || []).length}</span>
      <span><strong>Events</strong> ${(data.schedule || []).length}</span>
      <span><strong>Updated</strong> ${esc(m.generated_at)}</span>`;
    document.getElementById('homeCards').innerHTML = `
      <div class="stat-card"><div class="label">Dual record</div><div class="value">${esc(dualRec)}</div></div>
      <div class="stat-card"><div class="label">Conference</div><div class="value">${esc(confRec)}</div></div>
      <div class="stat-card"><div class="label">Home / Away</div><div class="value">${esc((m.home_record || ds.home_record || '—') + ' / ' + (m.away_record || ds.away_record || '—'))}</div></div>
      <div class="stat-card"><div class="label">Scored duals</div><div class="value">${(ds.duals || []).length}</div></div>`;

    renderHomeRoster(homeRoster);

    const tb = document.querySelector('#homeDuals tbody');
    // Ledger: every dual, including splits from tri/quad meets
    const duals = data.dual_scores?.duals || [];
    tb.innerHTML = duals.map((d) => `
      <tr>
        <td><div class="opp">${logoImg(d.opponent_logo_local, d.opponent_logo, d.opponent)}<span>${esc(d.opponent)}</span></div></td>
        <td>${d.shawnee}-${d.opp}</td>
        <td><span class="badge ${d.result === 'W' ? 'w' : 'l'}">${esc(d.result)}</span></td>
      </tr>`).join('');
  }

  function renderHomeRoster(homeRoster) {
    const grid = document.getElementById('homeRosterGrid');
    if (!grid) return;
    if (!homeRoster || !(homeRoster.wrestlers || []).length) {
      grid.innerHTML = '<p>Roster gallery unavailable.</p>';
      return;
    }
    const note = document.getElementById('homeRosterNote');
    const c = homeRoster.counts || {};
    if (note) {
      note.textContent = `Team-site gallery (${c.wp_gallery ?? (homeRoster.wrestlers || []).length}) matched to 2025-26 season data where names align (${c.matched ?? 0} matched).`;
    }
    grid.innerHTML = (homeRoster.wrestlers || []).map((r) => {
      const href = r.player_page || '';
      const tag = href ? 'a' : 'div';
      const hrefAttr = href ? ` href="${esc(href)}"` : '';
      const wt = r.display_weight || (r.weights_wrestled && r.weights_wrestled[0]) || '';
      const wtChip = wt ? `<span class="wt-chip">${esc(wt)}</span>` : '';
      const metaParts = [];
      if (r.grade) metaParts.push(esc(r.grade));
      if (r.wins != null && r.losses != null) metaParts.push(esc(`${r.wins}-${r.losses}`));
      else if ((r.weights_wrestled || []).length) metaParts.push(esc((r.weights_wrestled || []).join('/')));
      const meta = metaParts.length ? `<div class="meta">${metaParts.join(' · ')}</div>` : '';
      return `<${tag} class="wrestler-tile"${hrefAttr}>
        <div class="photo-wrap">
          ${wtChip}
          <img src="${esc(photoSrc(r.photo))}" alt="${esc(r.name)}" loading="lazy"
               onerror="this.src='${PLACEHOLDER_PHOTO}'" />
        </div>
        <div class="body">
          <div class="name">${esc(r.name)}</div>
          ${meta}
        </div>
      </${tag}>`;
    }).join('');

    const box = document.getElementById('homeRosterUnmatched');
    if (box && homeRoster.match_report) {
      const mr = homeRoster.match_report;
      const uwp = mr.unmatched_wp || [];
      const utw = mr.unmatched_tw || [];
      if (uwp.length || utw.length) {
        box.hidden = false;
        const parts = [];
        if (uwp.length) parts.push(`<strong>On team-site gallery only:</strong> ${uwp.map(esc).join(', ')}`);
        if (utw.length) parts.push(`<strong>On 2025-26 season roster only (${utw.length}):</strong> ${utw.map(esc).join(', ')}`);
        box.innerHTML = parts.join('<br/>');
      }
    }
  }


  function photoSrc(photo) {
    return photo || PLACEHOLDER_PHOTO;
  }

  function renderVarsityCards(assign, data) {
    const note = document.getElementById('varsityNote');
    if (note) note.textContent = assign.derivation_note || '';
    const c = assign.counts || {};
    const meta = document.getElementById('varsityMeta');
    if (meta) meta.innerHTML = `
      <span><strong>Filled</strong> ${c.filled ?? 0} / ${c.weight_classes ?? 14}</span>
      <span><strong>Vacant</strong> ${c.vacant ?? 0}</span>
      <span><strong>Full roster</strong> ${c.full_roster ?? (data.roster || []).length}</span>
      <span><strong>Season</strong> 2025-2026 Season</span>`;
    const grid = document.getElementById('varsityGrid');
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
        </div>
      </a>`;
    }).join('') || '<p>No assignments</p>';
  }

  function renderFullRosterSearchable(data, index) {
    const fromIndex = (index && index.wrestlers) || null;
    const rows = fromIndex || (data.roster || []).map((w) => ({
      wrestler_id: w.wrestler_id,
      name: w.name,
      grade: w.grade,
      roster_weight: w.weight,
      wins: w.wins || 0,
      losses: w.losses || 0,
      photo: w.photo,
      player_page: null,
      prestige_points: 0,
      weights_wrestled: w.weights_wrestled || (w.weight ? [String(w.weight)] : []),
      search_text: [w.name, w.grade, w.weight].filter(Boolean).join(' ').toLowerCase(),
    }));
    rows.sort((a, b) => {
      const aw = parseInt((a.weights_wrestled || [])[0] || a.roster_weight || a.assigned_weight, 10) || 999;
      const bw = parseInt((b.weights_wrestled || [])[0] || b.roster_weight || b.assigned_weight, 10) || 999;
      return aw - bw || String(a.name || '').localeCompare(String(b.name || ''));
    });

    const weightSel = document.getElementById('rosterWeight');
    const weightSet = new Set();
    rows.forEach((r) => {
      (r.weights_wrestled || []).forEach((w) => weightSet.add(String(w)));
      if (r.roster_weight) weightSet.add(String(r.roster_weight));
      if (r.assigned_weight) weightSet.add(String(r.assigned_weight));
    });
    const weights = [...weightSet].filter(Boolean).sort((a, b) => (parseInt(a, 10) || 0) - (parseInt(b, 10) || 0));
    if (weightSel && weightSel.options.length <= 1) {
      weights.forEach((wt) => {
        const opt = document.createElement('option');
        opt.value = wt;
        opt.textContent = wt;
        weightSel.appendChild(opt);
      });
    }

    const grid = document.getElementById('rosterGrid');
    const countEl = document.getElementById('rosterCount');
    const qEl = document.getElementById('rosterSearch');
    const gEl = document.getElementById('rosterGrade');

    function rowWeights(r) {
      const ww = (r.weights_wrestled || []).map(String);
      if (ww.length) return ww;
      const single = r.roster_weight || r.assigned_weight;
      return single ? [String(single)] : [];
    }

    function paint() {
      const q = (qEl && qEl.value || '').trim().toLowerCase();
      const g = gEl && gEl.value || '';
      const wt = weightSel && weightSel.value || '';
      const filtered = rows.filter((r) => {
        if (g && r.grade !== g) return false;
        const ww = rowWeights(r);
        if (wt && !ww.includes(wt) && String(r.roster_weight || '') !== wt && String(r.assigned_weight || '') !== wt) return false;
        const hay = (r.search_text || '') + ' ' + (r.name || '').toLowerCase() + ' ' + ww.join(' ');
        if (q && !hay.includes(q)) return false;
        return true;
      });
      if (countEl) countEl.textContent = `${filtered.length} wrestler${filtered.length === 1 ? '' : 's'}`;
      grid.innerHTML = filtered.map((r) => {
        const href = r.player_page || '#';
        const tag = href === '#' ? 'div' : 'a';
        const hrefAttr = href === '#' ? '' : ` href="${esc(href)}"`;
        const prest = r.prestige_points ? `<span class="prest-chip">${esc(r.prestige_points)} pts</span>` : '';
        const ww = rowWeights(r);
        const wtLabel = ww.length ? ww.join('/') : '';
        const wtChip = wtLabel ? `<span class="wt-chip">${esc(wtLabel)}</span>` : '';
        const metaParts = [];
        if (r.grade) metaParts.push(esc(r.grade));
        if (r.wins != null && r.losses != null) metaParts.push(esc(`${r.wins ?? 0}-${r.losses ?? 0}`));
        const meta = metaParts.length ? `<div class="meta">${metaParts.join(' · ')}</div>` : '';
        return `<${tag} class="wrestler-tile"${hrefAttr}>
          <div class="photo-wrap">
            ${wtChip}
            ${prest}
            <img src="${esc(photoSrc(r.photo))}" alt="${esc(r.name)}" loading="lazy"
                 onerror="this.src='${PLACEHOLDER_PHOTO}'" />
          </div>
          <div class="body">
            <div class="name">${esc(r.name)}</div>
            ${meta}
          </div>
        </${tag}>`;
      }).join('') || '<p>No matches</p>';
    }

    ['input', 'change'].forEach((ev) => {
      qEl && qEl.addEventListener(ev, paint);
      gEl && gEl.addEventListener(ev, paint);
      weightSel && weightSel.addEventListener(ev, paint);
    });
    paint();
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
    const conf = data.metadata?.conference_record || data.dual_scores?.conference_record;
    const seasonFinal = (data.metadata?.status || data.metadata?.season_status) === 'final';
    const statusChip = seasonFinal
      ? `<span><strong>Season</strong> Final · 2025-2026 Season</span>`
      : `<span><strong>Season</strong> 2025-2026 Season</span>`;
    document.getElementById('schedMeta').innerHTML = `<span><strong>Dual record</strong> ${esc(rec)}</span>
      <span><strong>Conference</strong> ${esc(conf || '—')}</span>
      <span><strong>Listings</strong> ${(data.schedule || []).length}</span>
      ${statusChip}`;
    const body = document.querySelector('#scheduleTable tbody');
    body.innerHTML = (data.schedule || []).map((m) => {
      const expand = m.expandable ? `<button type="button" class="expand-btn" data-eid="${esc(m.tournament_key || m.event_id)}" aria-expanded="false">Details</button>` : '';
      const timeLabel = m.time || ((m.status === 'final' || m.completed || seasonFinal) ? '—' : 'TBD');
      const main = `<tr class="sched-row" data-eid="${esc(m.event_id || '')}">
        <td>${esc(m.date_iso || m.date)}</td>
        <td>${oppCell(m)}</td>
        <td>${esc(m.home_away === 'home' ? 'Home' : m.home_away === 'away' ? 'Away' : (m.location || 'Event'))}</td>
        <td>${esc(timeLabel)} ${expand}</td>
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

  function renderResults(data) {
    const s = data.standings || {};
    const noteEl = document.getElementById('resultsNote');
    if (noteEl) noteEl.textContent = s.note || '';
    const ds = data.dual_scores || {};
    const meta = document.getElementById('resultsMeta');
    const seasonFinal = (data.metadata?.status || data.metadata?.season_status || s.status) === 'final';
    if (meta) meta.innerHTML =
      `<span><strong>Shawnee duals</strong> ${esc(s.shawnee_dual_record || ds.record)}</span>
       <span><strong>Conference</strong> ${esc(s.conference_record || ds.conference_record || '—')}</span>
       <span><strong>Season</strong> ${seasonFinal ? 'Final · 2025-2026 Season' : '2025-2026 Season'}</span>`;
    const rows = (s.rows && s.rows.length) ? s.rows : (ds.duals || []).map((d) => ({
      opponent: d.opponent, score: d.score_display || `${d.shawnee}-${d.opp}`, result: d.result,
      opponent_logo_local: d.opponent_logo_local, opponent_logo: d.opponent_logo,
      conference_dual: d.conference,
    }));
    const dualBody = document.querySelector('#resultsDualsTable tbody');
    if (dualBody) dualBody.innerHTML = rows.map((r) => `
      <tr>
        <td><div class="opp">${logoImg(r.opponent_logo_local, r.opponent_logo, r.opponent)}<span>${esc(r.opponent)}${r.conference_dual ? ' <em class="conf-tag">conf</em>' : ''}</span></div></td>
        <td>${esc(r.score)}</td>
        <td><span class="badge ${r.result === 'W' ? 'w' : 'l'}">${esc(r.result)}</span></td>
      </tr>`).join('');

    // Tournament bout cards (same payload schedule expand uses)
    const host = document.getElementById('resultsTournaments');
    if (host) {
      const trMap = data.tournament_results || {};
      const events = (data.schedule || []).filter((m) => m.expandable || m.tournament_key || m.event_kind === 'tournament' || m.event_kind === 'I' || m.display_as_event || m.results_unavailable);
      const seen = new Set();
      const blocks = [];
      for (const m of events) {
        const key = m.tournament_key || m.event_id;
        if (!key || seen.has(key)) continue;
        seen.add(key);
        const tr = trMap[key];
        const title = esc(m.event_name || m.opponent || key);
        const date = esc(m.date || '');
        if (tr && (tr.wrestlers || []).length) {
          const panel = tournamentPanel({ ...m, tournament_key: key, expandable: true }, data);
          const match = panel.match(/<div class="tournament-panel">[\s\S]*<\/div>/);
          const cards = match ? match[0] : panel;
          blocks.push(`<section class="results-tournament-block"><h3>${title} <span class="muted">${date}</span></h3>${cards}</section>`);
        } else {
          blocks.push(`<section class="results-tournament-block"><h3>${title} <span class="muted">${date}</span></h3><p class="muted">${seasonFinal ? 'Bout cards unavailable for this event.' : 'Bout cards not yet available.'}</p></section>`);
        }
      }
      host.innerHTML = blocks.length ? blocks.join('') : `<p class="muted">${seasonFinal ? 'No tournament bout cards on file.' : 'No tournament results yet.'}</p>`;
    }
  }

  function renderConferenceStandings(doc) {
    const noteEl = document.getElementById('standingsNote');
    const gaps = (doc.gaps || []).filter((g) => typeof g === 'string' || g.type === 'validation');
    const gapText = gaps.map((g) => typeof g === 'string' ? g : (g.issues || []).join('; ')).filter(Boolean).join(' · ');
    if (noteEl) {
      noteEl.textContent = gapText || '';
      noteEl.style.display = gapText ? '' : 'none';
    }
    const meta = document.getElementById('standingsMeta');
    if (meta) {
      const final = (doc.status || doc.season_status) === 'final';
      meta.innerHTML =
        `<span><strong>Conference</strong> ${esc(doc.conference || 'Olympic')}</span>
         <span><strong>Season</strong> ${final ? 'Final · 2025-2026 Season' : esc(doc.title || doc.season || '2025-2026 Season')}</span>
         <span><strong>Source</strong> ${esc(doc.source || '—')}</span>
         <span><strong>As of</strong> ${esc(doc.as_of || '—')}</span>`;
    }
    const host = document.getElementById('conferenceStandings');
    if (!host) return;
    const divisions = doc.divisions || [];
    host.innerHTML = divisions.map((div) => {
      const rows = (div.teams || []).map((t) => {
        const cls = t.is_shawnee ? ' class="shawnee-row"' : '';
        return `<tr${cls}>
          <td class="rank">${esc(t.rank)}</td>
          <td><div class="opp">${logoImg(t.logo_local, t.logo, t.team)}<span>${esc(t.team)}${t.is_shawnee ? ' <em class="conf-tag">us</em>' : ''}</span></div></td>
          <td>${esc(t.division_record)}</td>
          <td>${esc(t.overall_record)}</td>
        </tr>`;
      }).join('');
      return `<section class="division-block">
        <h2 class="section-title">${esc(div.name)} Division</h2>
        <div class="table-wrap"><table class="standings-table">
          <thead><tr><th>#</th><th>Team</th><th>Division</th><th>Overall</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>
      </section>`;
    }).join('') || '<p class="muted">Standings unavailable.</p>';
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
    // Match live banners: stacked varsity words, optional decade / division subtitle.
    let main = String(title || 'Award');
    let sub = '';
    // Preserve NCAA division tag as subtitle before stripping other parens
    const ncaaDiv = main.match(/\((D1\/D2\/D3\/J)\)/i);
    const m = main.match(/^(.*?)\s*[—–]\s*(.+)$/); // em/en dash only (keep hyphens in All-American)
    if (m) { main = m[1].trim(); sub = m[2].trim(); }
    main = main.replace(/\s*\(.*?\)\s*/g, ' ').replace(/\s+/g, ' ').trim();
    if (ncaaDiv && !sub) sub = '(' + ncaaDiv[1].toUpperCase() + ')';
    const up = main.toUpperCase();
    let lines;
    if (/TEAM CHAMPIONSHIP$/.test(up) && up.includes(' ')) {
      const i = up.lastIndexOf(' TEAM CHAMPIONSHIP');
      lines = [up.slice(0, i).trim(), 'TEAM CHAMPIONSHIP'];
    } else if (/\bCHAMPIONS$/.test(up) && up.includes(' ')) {
      const i = up.lastIndexOf(' CHAMPIONS');
      lines = [up.slice(0, i).trim(), 'CHAMPIONS'];
    } else if (/\bCHAMPIONSHIP$/.test(up) && up.includes(' ')) {
      const i = up.lastIndexOf(' CHAMPIONSHIP');
      lines = [up.slice(0, i).trim(), 'CHAMPIONSHIP'];
    } else if (up === 'NCAA ALL-AMERICAN') {
      lines = ['NCAA', 'ALL-AMERICAN'];
    } else if (up === 'STATE PLACE WINNER') {
      lines = ['STATE', 'PLACE WINNER'];
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
      // Live Career Wins / Pins: value | name | years (single-row columns)
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
    // State Place Winner: place | name | year weight (match original card)
    if ((a.award_name || '') === 'State Place Winner' ||
        (kind === 'state' && a.placement && a.placement !== '1st' && (a.award_name || '').toLowerCase().includes('place'))) {
      const yr = a.season || '';
      const wt = a.weight || '';
      const right = [yr, wt].filter(Boolean).join(' ');
      return {
        left: a.placement || '',
        mid: name,
        right,
        rowClass: 'row state-place',
      };
    }
    // district / region / default: year | wrestler | weight/placement
    return {
      left: a.season || '',
      mid: name,
      right: a.weight || a.placement || (a.value != null ? String(a.value) : ''),
      rowClass: 'row',
    };
  }

  function isStatePlaceWinnerCard(card) {
    return (card.title || '') === 'State Place Winner' ||
      /^State Place/i.test(card.title || '');
  }

  function placeSortKey(p) {
    const m = String(p || '').match(/(\d+)/);
    return m ? Number(m[1]) : 99;
  }

  function weightSortKey(w) {
    const s = String(w || '').trim().toUpperCase();
    if (!s) return 997;
    if (s === 'HWT' || s === 'HW' || s === 'HEAVY' || s === 'HEAVYWEIGHT' || s === 'HEAVY WEIGHT') return 285;
    const m = s.match(/(\d+)/);
    if (!m) return 998;
    return Number(m[1]);
  }

  function isStateChampionCard(card) {
    return (card.title || '') === 'State Champions' ||
      ((card.kind === 'state' || card.rows[0]?.award_category === 'state') &&
        /^State Champions$/i.test(card.title || ''));
  }

  function isNcaaCard(card) {
    return (card.kind === 'college') || /^NCAA/i.test(card.title || '');
  }

  function isTeamCard(card) {
    return card.kind === 'team' || (card.rows[0] && card.rows[0].award_category === 'team');
  }

  function renderTeamBody(card, rows) {
    // Team acknowledgements: years only (or a single note). No blank "Team title" / "1st" columns.
    // Layout matches originals: decade columns for multi-decade lists; stacked years when few.
    const noteOnly = rows.every((a) => !a.season && (a.details || a.value != null));
    if (noteOnly || /dual record/i.test(card.title || '')) {
      const text = rows.map((a) => a.details || a.value || a.season || '').filter(Boolean).join(' · ');
      return `<div class="team-note">${esc(text)}</div>`;
    }
    const years = rows.map((a) => String(a.season || '').slice(0, 4)).filter((y) => /^\d{4}$/.test(y));
    years.sort();
    if (years.length <= 4) {
      // Sectional (and short lists): stacked years like the original sectional banner
      return `<div class="years-stack">${years.map((y) => `<div>${esc(y)}</div>`).join('')}</div>`;
    }
    // District (and longer lists): one column per decade, years packed — no empty placeholder cells
    const byDecade = {};
    for (const y of years) {
      const dec = Math.floor(Number(y) / 10) * 10;
      (byDecade[dec] ||= []).push(y);
    }
    const decades = Object.keys(byDecade).map(Number).sort((a, b) => a - b);
    const cols = decades.map((dec) => {
      const cells = byDecade[dec].map((y) => `<div class="yr">${esc(y)}</div>`).join('');
      return `<div class="decade-col" data-decade="${dec}s">${cells}</div>`;
    }).join('');
    return `<div class="decade-cols" style="--cols:${decades.length}">${cols}</div>`;
  }


  function renderNcaaBody(rows) {
    // Prestigious centered entries: year · NAME · place · school
    return rows.map((a) => `
      <div class="prestige-entry">
        <div class="year">${esc(a.season || '')}</div>
        <div class="name">${esc(a.wrestler || '')}</div>
        <div class="place">${esc(a.placement || '')}</div>
        ${a.details ? `<div class="school">${esc(a.details)}</div>` : ''}
      </div>`).join('');
  }

  function renderStateChampBody(rows) {
    // Featured champion plaque: large name, year, note
    return rows.map((a) => `
      <div class="prestige-entry state-champ">
        <div class="name">${esc((a.wrestler || '').toUpperCase())}</div>
        <div class="year">${esc(a.season || '')}</div>
        ${a.details ? `<div class="school">${esc(a.details)}</div>` : ''}
      </div>`).join('');
  }

  function fmtPct(p) {
    if (p == null || Number.isNaN(Number(p))) return '—';
    return Number(p).toFixed(1) + '%';
  }

  function titleMarks(ch) {
    const bits = [];
    if (ch.league) bits.push('<span class="title-chip league" title="League champions">League</span>');
    if (ch.districts) bits.push('<span class="title-chip district" title="District team champions">District</span>');
    if (ch.sectional) bits.push('<span class="title-chip sectional" title="Sectional team champions">Sectional</span>');
    return bits.length ? bits.join(' ') : '<span class="muted">—</span>';
  }

  function renderCoachStats(doc) {
    const team = doc.team_all_time || {};
    const coaches = doc.coaches || [];
    const seasons = doc.seasons || [];
    const meta = document.getElementById('coachMeta');
    if (meta) {
      meta.innerHTML = `
        <span><strong>All-time duals</strong> ${esc(team.record || '—')}</span>
        <span><strong>Winning %</strong> ${esc(fmtPct(team.win_pct))}</span>
        <span><strong>Seasons</strong> ${seasons.length}</span>
        <span><strong>Coaches</strong> ${coaches.length}</span>`;
    }
    const cards = document.getElementById('coachCards');
    if (cards) {
      cards.innerHTML = coaches.map((c) => {
        const t = c.titles || {};
        const years = c.first_season === c.last_season
          ? c.first_season
          : `${c.first_season} – ${c.last_season}`;
        return `<div class="stat-card coach-card">
          <div class="coach-card-name">${esc(c.name)}</div>
          <div class="label">${esc(years)} · ${c.seasons} season${c.seasons === 1 ? '' : 's'}</div>
          <div class="value">${esc(c.record)}</div>
          <div class="coach-card-pct">${esc(fmtPct(c.win_pct))}</div>
          <div class="coach-card-titles">
            <span><strong>${t.league || 0}</strong> League</span>
            <span><strong>${t.districts || 0}</strong> District</span>
            <span><strong>${t.sectional || 0}</strong> Sectional</span>
          </div>
        </div>`;
      }).join('');
    }
    const wrap = document.getElementById('coachSeasonTables');
    if (!wrap) return;
    // Group consecutive seasons by coach (already chronological)
    const groups = [];
    for (const s of seasons) {
      if (!groups.length || groups[groups.length - 1].coach !== s.coach) {
        groups.push({ coach: s.coach, rows: [s] });
      } else {
        groups[groups.length - 1].rows.push(s);
      }
    }
    wrap.innerHTML = groups.map((g) => {
      const summary = coaches.find((c) => c.name === g.coach);
      const head = summary
        ? `${esc(g.coach)} · ${esc(summary.record)} · ${esc(fmtPct(summary.win_pct))}`
        : esc(g.coach);
      const body = g.rows.map((s) => {
        const ch = s.championships || {};
        return `<tr>
          <td>${esc(s.season)}</td>
          <td>${esc(s.record)}</td>
          <td>${esc(fmtPct(s.win_pct))}</td>
          <td>${esc(s.team_cumulative.record)}</td>
          <td>${esc(s.coach_cumulative.record)}</td>
          <td>${esc(fmtPct(s.coach_cumulative.win_pct))}</td>
          <td class="titles-cell">${titleMarks(ch)}</td>
        </tr>`;
      }).join('');
      return `<section class="coach-season-block">
        <h3 class="section-title">${head}</h3>
        <div class="table-wrap"><table class="coach-history-table">
          <thead><tr>
            <th>Season</th><th>Record</th><th>Win%</th>
            <th>Team cum.</th><th>Coach cum.</th><th>Coach %</th><th>Titles</th>
          </tr></thead>
          <tbody>${body}</tbody>
        </table></div>
      </section>`;
    }).join('');
  }

  function renderAwards(data) {
    const awards = data.awards || [];
    const meta = data.meta?.njsiaa_placements_2025_26;
    document.getElementById('awardsMeta').innerHTML =
      `<strong>${awards.length}</strong> award rows (${data.seed_count || 0} historical seed + ${data.derived_2025_26_count || 0} auto-derived for 2025-26).
       ${meta ? `<br/><em>NJSIAA 2025-2026 placements:</em> ${esc(meta.status)} — ${esc(meta.note)}` : ''}`;

    // Group into cards
    const byName = {};
    const SKIP_AWARDS = new Set(['Season Win Leaders', 'Season 20+ Wins', 'Varsity Dual Record']);
    for (const a of awards) {
      const name = a.award_name || 'Award';
      if (SKIP_AWARDS.has(name)) continue;
      if (name === 'District Champions' || a.award_category === 'district') {
        const dec = decadeLabel(a.season);
        const key = `District Champions — ${dec}`;
        (byName[key] ||= { title: key, kind: 'district', rows: [] }).rows.push(a);
      } else {
        (byName[name] ||= { title: name, kind: a.award_category || 'other', rows: [] }).rows.push(a);
      }
    }
    // AWARDS_CHEVRON_CHROME_LOCKED — config-driven rows from awards.json card_rows
    // (fallback: flattened card_order). District Champions expands to decade cards.
    // Do not invent new award entries here.
    const configuredRows = (data.card_rows && data.card_rows.length)
      ? data.card_rows.map((r) => r.slice())
      : (data.card_order || []).map((k) => [k]);
    const configuredOrder = configuredRows.flat();
    function titleMatchesKey(title, key) {
      if (title === key || title.startsWith(key)) return true;
      if (key.startsWith('NCAA') && title.startsWith('NCAA')) return true;
      return false;
    }
    function cardOrderRank(title) {
      for (let i = 0; i < configuredOrder.length; i++) {
        if (titleMatchesKey(title, configuredOrder[i])) return i;
      }
      return 1000;
    }
    const usedTitles = new Set();
    const rowTitleLists = configuredRows.map((keys) => {
      const titles = [];
      for (const key of keys) {
        const matches = Object.keys(byName).filter((t) => titleMatchesKey(t, key) && !usedTitles.has(t));
        matches.sort((a, b) => {
          if (a.startsWith('District Champions') && b.startsWith('District Champions')) {
            return a.localeCompare(b);
          }
          return a.localeCompare(b);
        });
        for (const t of matches) {
          usedTitles.add(t);
          titles.push(t);
        }
      }
      return titles;
    }).filter((titles) => titles.length);
    // Leftovers (should be empty when card_rows covers all rendered cards)
    const leftovers = Object.keys(byName).filter((t) => !usedTitles.has(t)).sort((a, b) => {
      const ra = cardOrderRank(a), rb = cardOrderRank(b);
      if (ra !== rb) return ra - rb;
      return a.localeCompare(b);
    });
    if (leftovers.length) rowTitleLists.push(leftovers);
    const order = rowTitleLists.flat();

    const filters = document.getElementById('awardFilters');
    const kinds = ['all', ...new Set(Object.values(byName).map((c) => c.kind))];
    filters.innerHTML = kinds.map((k) =>
      `<button type="button" data-kind="${esc(k)}" class="${k === 'all' ? 'active' : ''}">${esc(k)}</button>`
    ).join('');

    const grid = document.getElementById('awardsGrid');
    function renderCardHtml(t) {
      const card = byName[t];
      const rows = card.rows.slice().sort((a, b) => {
        if (card.kind === 'leaderboard') {
          const av = Number(a.value), bv = Number(b.value);
          if (!Number.isNaN(av) && !Number.isNaN(bv) && bv !== av) return bv - av;
        }
        if (isStatePlaceWinnerCard(card)) {
          const pd = placeSortKey(a.placement) - placeSortKey(b.placement);
          if (pd) return pd;
        }
        // District / Region Champions: year asc, then weight asc (HWT/285 last) — matches auto_awards.py
        if (card.kind === 'district' || card.kind === 'region') {
          const sy = String(a.season || '').localeCompare(String(b.season || ''));
          if (sy) return sy;
          const dw = weightSortKey(a.weight) - weightSortKey(b.weight);
          if (dw) return dw;
          return String(a.wrestler || '').localeCompare(String(b.wrestler || ''));
        }
        return String(a.season || '').localeCompare(String(b.season || ''))
          || String(a.wrestler || '').localeCompare(String(b.wrestler || ''));
      });

      const prestigeNcaa = isNcaaCard(card);
      const prestigeState = isStateChampionCard(card);
      const team = isTeamCard(card);
      const statePlace = isStatePlaceWinnerCard(card);
      let body;
      let extraClass = '';
      // AWARDS_CHEVRON_CHROME_LOCKED: Region-and-below share .tier-uniform width;
      // NCAA + State Champions + State Place keep default 252px tier.
      const uniformTier = !prestigeNcaa && !prestigeState && !statePlace;
      if (team) {
        body = renderTeamBody(card, rows);
        extraClass = ' team';
      } else if (prestigeNcaa) {
        body = renderNcaaBody(rows);
        extraClass = ' prestige ncaa';
      } else if (prestigeState) {
        body = renderStateChampBody(rows);
        extraClass = ' prestige state-champ';
      } else {
        let prevSeason = null;
        const placeCard = isStatePlaceWinnerCard(card);
        body = rows.map((a) => {
          const cells = awardRowCells(a, card.kind);
          let left = cells.left;
          // Blank repeated seasons for district/region only — never for State Place Winner
          // (place is left col; year must stay visible per entry, e.g. Luke Sherlock 2024).
          if (!placeCard && (card.kind === 'district' || card.kind === 'region') && left && left === prevSeason) {
            left = '';
          } else if (cells.left) {
            prevSeason = cells.left;
          }
          return `<div class="${cells.rowClass}"><span>${esc(left)}</span><span>${esc(cells.mid)}</span><span>${esc(cells.right)}</span></div>`;
        }).join('');
      }
      if (uniformTier) extraClass += ' tier-uniform';
      return `<article class="chevron-card${extraClass}" data-kind="${esc(card.kind)}">
          <div class="chevron-card-inner">
            <div class="title">${formatChevronTitle(card.title)}</div>
            <div class="body">${body}</div>
            <!-- AWARDS_CHEVRON_CHROME_LOCKED: identical tip + S on every card -->
            <div class="foot"><img class="s-logo" src="assets/img/shawnee-s.png" alt="Shawnee S" width="58" height="58" /></div>
          </div>
        </article>`;
    }
    function paint(kind) {
      if (kind !== 'all') {
        grid.innerHTML = `<div class="awards-row">${order.filter((t) => byName[t].kind === kind).map(renderCardHtml).join('')}</div>`;
        return;
      }
      grid.innerHTML = rowTitleLists.map((titles) =>
        `<div class="awards-row">${titles.map(renderCardHtml).join('')}</div>`
      ).join('');
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
