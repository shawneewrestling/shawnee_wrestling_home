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
  const SEASONS_INDEX_URL = 'data/seasons/index.json';
  const PLACEHOLDER_PHOTO = 'assets/img/wrestler-silhouette.svg';

  async function loadJson(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error('Failed to load ' + url);
    return r.json();
  }

  function seasonIdFromLocation() {
    try {
      const u = new URL(window.location.href);
      const q = u.searchParams.get('season');
      if (q) return q;
      const h = (u.hash || '').replace(/^#/, '');
      if (h.startsWith('season=')) return h.slice(7);
    } catch (_) {}
    return null;
  }

  function setSeasonInLocation(seasonId, replace) {
    try {
      const u = new URL(window.location.href);
      u.searchParams.set('season', seasonId);
      const method = replace ? 'replaceState' : 'pushState';
      history[method]({}, '', u.pathname + u.search + u.hash);
    } catch (_) {}
  }

  function seasonLabel(id, seasons) {
    const hit = (seasons || []).find((s) => s.id === id);
    return hit?.label || `${String(id).replace(/^(\d{4})-(\d{2})$/, (_, a, b) => a + '-' + (parseInt(a, 10) > 2000 ? String(2000 + parseInt(b, 10)) : b))} Season`;
  }

  async function loadSeasonsIndex() {
    return loadJson(SEASONS_INDEX_URL);
  }

  async function loadSeasonBundle(seasonId) {
    const base = `data/seasons/${seasonId}`;
    const [schedule, results, standings] = await Promise.all([
      loadJson(`${base}/schedule.json`),
      loadJson(`${base}/results.json`),
      loadJson(`${base}/standings.json`),
    ]);
    const duals = results.duals || results.rows || [];
    return {
      seasonId,
      scheduleDoc: schedule,
      resultsDoc: results,
      standingsDoc: standings,
      // Shape expected by renderSchedule / renderResults
      view: {
        schedule: schedule.schedule || [],
        metadata: {
          season: schedule.season || schedule.title,
          title: schedule.title,
          dual_record: schedule.dual_record,
          conference_record: schedule.conference_record,
          status: schedule.status || schedule.season_status,
          season_status: schedule.season_status || schedule.status,
        },
        dual_scores: {
          record: results.shawnee_dual_record || schedule.dual_record,
          conference_record: results.conference_record || schedule.conference_record,
          duals,
        },
        standings: {
          rows: results.rows || duals,
          note: results.note || '',
          shawnee_dual_record: results.shawnee_dual_record || schedule.dual_record,
          conference_record: results.conference_record || schedule.conference_record,
          season: results.title || results.season,
          status: results.status || results.season_status,
        },
      },
    };
  }

  function fillSeasonSelect(selectEl, index, currentId) {
    if (!selectEl) return;
    const seasons = index.seasons || [];
    selectEl.innerHTML = seasons.map((s) =>
      `<option value="${esc(s.id)}"${s.id === currentId ? ' selected' : ''}>${esc(s.label)}</option>`
    ).join('');
  }

  function updateSeasonChrome(seasonId, label) {
    document.querySelectorAll('.site-header .tag').forEach((el) => {
      el.textContent = `Wrestling · ${label}`;
    });
    document.querySelectorAll('.site-footer').forEach((el) => {
      el.textContent = `Shawnee High School Wrestling · ${label}`;
    });
    const sub = document.querySelector('main .page-sub');
    if (!sub) return;
    const page = document.body && document.querySelector('.nav a.active')?.textContent?.trim();
    if (page === 'Schedule / Results') {
      sub.textContent = `Duals, tournaments, and multi-team events for the ${label.replace(/ Season$/, ' season')}.`;
    } else if (page === 'Results') {
      sub.textContent = `Shawnee dual-meet results (including tri/quad splits) · ${label}.`;
    } else if (page === 'Standings') {
      sub.textContent = `${label} wrestling · Olympic Conference`;
    }
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
    if (page === 'Coach Stats') {
      const coachHist = await loadJson(COACH_HISTORY_URL);
      renderCoachStats(coachHist);
      return;
    }

    if (page === 'Standings' || page === 'Schedule / Results' || page === 'Results') {
      const index = await loadSeasonsIndex();
      const seasons = index.seasons || [];
      const defaultId = index.default || (seasons[0] && seasons[0].id) || '2025-26';
      let currentId = seasonIdFromLocation() || defaultId;
      if (!seasons.some((s) => s.id === currentId)) currentId = defaultId;

      const selectEl = document.getElementById('seasonSelect');
      fillSeasonSelect(selectEl, index, currentId);

      async function showSeason(seasonId, { replaceUrl } = {}) {
        currentId = seasonId;
        if (selectEl) selectEl.value = seasonId;
        setSeasonInLocation(seasonId, !!replaceUrl);
        const label = seasonLabel(seasonId, seasons);
        updateSeasonChrome(seasonId, label);
        const bundle = await loadSeasonBundle(seasonId);
        if (page === 'Schedule / Results') renderSchedule(bundle.view);
        else if (page === 'Results') renderResults(bundle.view);
        else if (page === 'Standings') renderConferenceStandings(bundle.standingsDoc);
      }

      if (selectEl) {
        selectEl.addEventListener('change', () => {
          showSeason(selectEl.value, { replaceUrl: false }).catch((e) => {
            console.error(e);
            const main = document.querySelector('main');
            if (main) main.insertAdjacentHTML('afterbegin', `<div class="callout warn">${esc(e.message)}</div>`);
          });
        });
      }
      window.addEventListener('popstate', () => {
        const id = seasonIdFromLocation() || defaultId;
        showSeason(id, { replaceUrl: true }).catch(console.error);
      });

      await showSeason(currentId, { replaceUrl: true });
      return;
    }

    const data = await loadJson(DATA_URL);
    if (page === 'Home') {
      const homeRoster = await loadJson(HOME_ROSTER_URL).catch(() => null);
      renderHome(data, homeRoster);
      return;
    }
    else if (page === 'Stats') {
      const index = await loadJson(PLAYERS_INDEX_URL).catch(() => null);
      renderStats(data, index);
    }
  } catch (e) {
    console.error(e);
    const main = document.querySelector('main');
    if (main) main.insertAdjacentHTML('afterbegin', `<div class="callout warn">${esc(e.message)}</div>`);
  }

  function setHtml(el, html) {
    if (!el) return;
    el.innerHTML = html;
  }

  function seasonIsComplete(data) {
    const m = data.metadata || {};
    const ds = data.dual_scores || {};
    const status = String(m.status || m.season_status || ds.status || '').toLowerCase();
    return status === 'final' || status === 'closed' || status === 'complete' || status === 'completed';
  }

  function parseEventStart(ev) {
    const iso = String(ev.date_iso || ev.date || '').trim();
    if (!iso) return null;
    const day = iso.length >= 10 ? iso.slice(0, 10) : iso;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
    const raw = String(ev.time || ev.time_raw || '').trim();
    let hours = 0, minutes = 0;
    if (raw) {
      const m = raw.match(/^(\d{1,2}):(\d{2})\s*([AaPp][Mm])?$/);
      if (m) {
        hours = parseInt(m[1], 10);
        minutes = parseInt(m[2], 10);
        const ap = (m[3] || '').toUpperCase();
        if (ap === 'PM' && hours < 12) hours += 12;
        if (ap === 'AM' && hours === 12) hours = 0;
      } else {
        const m24 = raw.match(/^(\d{1,2}):(\d{2})$/);
        if (m24) {
          hours = parseInt(m24[1], 10);
          minutes = parseInt(m24[2], 10);
        }
      }
    }
    const dt = new Date(`${day}T00:00:00`);
    if (Number.isNaN(dt.getTime())) return null;
    dt.setHours(hours, minutes, 0, 0);
    return dt;
  }

  function homeDualsForDisplay(data) {
    const duals = (data.dual_scores && data.dual_scores.duals) || [];
    if (seasonIsComplete(data)) return duals.slice();
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - 14);
    const end = new Date();
    end.setHours(23, 59, 59, 999);
    return duals.filter((d) => {
      const iso = String(d.date_iso || d.date || '').slice(0, 10);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return false;
      const dt = new Date(`${iso}T00:00:00`);
      return !Number.isNaN(dt.getTime()) && dt >= start && dt <= end;
    });
  }

  function upcomingEventsFromSchedule(data, now) {
    const stamp = now || new Date();
    const rows = data.schedule || [];
    const seen = new Set();
    const upcoming = [];
    for (const ev of rows) {
      const start = parseEventStart(ev);
      if (!start || start.getTime() < stamp.getTime()) continue;
      const key = String(
        ev.parent_event_id || ev.tournament_key || ev.event_id
        || `${String(ev.date_iso || '').slice(0, 10)}|${ev.event_name || ev.opponent || ''}`
      );
      if (seen.has(key)) continue;
      seen.add(key);
      const title = (ev.multi_meet || !ev.opponent)
        ? (ev.event_name || ev.opponent || 'Event')
        : (ev.opponent || ev.event_name || 'Event');
      const loc = ev.home_away === 'home' ? 'Home'
        : ev.home_away === 'away' ? 'Away'
        : (ev.location || 'Event');
      upcoming.push({
        start,
        title,
        location: loc,
        time: ev.time || '—',
        dateLabel: ev.date || String(ev.date_iso || '').slice(0, 10),
        dateIso: String(ev.date_iso || '').slice(0, 10),
      });
    }
    upcoming.sort((a, b) => a.start - b.start || a.title.localeCompare(b.title));
    return upcoming;
  }

  function pickUpcomingList(upcoming, now) {
    if (!upcoming.length) return [];
    const stamp = now || new Date();
    const weekEnd = new Date(stamp.getTime() + 7 * 24 * 60 * 60 * 1000);
    const inWeek = upcoming.filter((e) => e.start <= weekEnd);
    if (inWeek.length >= 2) return inWeek;
    return upcoming.slice(0, 2);
  }

  function formatCountdown(ms) {
    if (ms <= 0) return '0d 0h 0m';
    const totalMin = Math.floor(ms / 60000);
    const days = Math.floor(totalMin / (60 * 24));
    const hours = Math.floor((totalMin % (60 * 24)) / 60);
    const mins = totalMin % 60;
    return `${days}d ${hours}h ${mins}m`;
  }

  var upcomingTimer = null;

  function renderUpcomingEvents(data) {
    const section = document.getElementById('upcomingSection');
    const countdownEl = document.getElementById('upcomingCountdown');
    const body = document.querySelector('#upcomingTable tbody');
    if (!section || !countdownEl || !body) return;

    if (upcomingTimer) {
      clearInterval(upcomingTimer);
      upcomingTimer = null;
    }

    function paint() {
      const now = new Date();
      const upcoming = upcomingEventsFromSchedule(data, now);
      const list = pickUpcomingList(upcoming, now);
      if (!list.length) {
        section.hidden = true;
        setHtml(countdownEl, '');
        setHtml(body, '');
        if (upcomingTimer) {
          clearInterval(upcomingTimer);
          upcomingTimer = null;
        }
        return;
      }
      section.hidden = false;
      const next = list[0];
      setHtml(countdownEl, `<div class="countdown-label">${esc(next.title)}</div>
        <div class="countdown-value" data-next-start="${esc(next.start.toISOString())}">${esc(formatCountdown(next.start - now))}</div>`);
      setHtml(body, list.map((e) => `
        <tr>
          <td>${esc(e.dateLabel)}</td>
          <td>${esc(e.title)}</td>
          <td>${esc(e.location)}</td>
          <td>${esc(e.time)}</td>
        </tr>`).join(''));
    }

    paint();
    if (!section.hidden) {
      upcomingTimer = setInterval(paint, 30000);
    }
  }

  function renderHome(data, homeRoster) {
    const m = data.metadata || {};
    const ds = data.dual_scores || {};
    const dualRec = m.dual_record || ds.record || '—';
    const confRec = m.conference_record || ds.conference_record || '—';
    setHtml(document.getElementById('homeMeta'), `
      <span><strong>Season</strong> ${esc(m.season)}</span>
      <span><strong>Dual record</strong> ${esc(dualRec)}</span>
      <span><strong>Conference</strong> ${esc(confRec)}</span>
      <span><strong>Roster</strong> ${(data.roster || []).length}</span>
      <span><strong>Events</strong> ${(data.schedule || []).length}</span>
      <span><strong>Updated</strong> ${esc(m.generated_at)}</span>`);
    setHtml(document.getElementById('homeCards'), `
      <div class="stat-card"><div class="label">Dual record</div><div class="value">${esc(dualRec)}</div></div>
      <div class="stat-card"><div class="label">Conference</div><div class="value">${esc(confRec)}</div></div>
      <div class="stat-card"><div class="label">Home / Away</div><div class="value">${esc((m.home_record || ds.home_record || '—') + ' / ' + (m.away_record || ds.away_record || '—'))}</div></div>
      <div class="stat-card"><div class="label">Scored duals</div><div class="value">${(ds.duals || []).length}</div></div>`);

    renderUpcomingEvents(data);
    renderHomeRoster(homeRoster);

    const tb = document.querySelector('#homeDuals tbody');
    const duals = homeDualsForDisplay(data);
    setHtml(tb, duals.map((d) => `
      <tr>
        <td><div class="opp">${logoImg(d.opponent_logo_local, d.opponent_logo, d.opponent)}<span>${esc(d.opponent)}</span></div></td>
        <td>${d.shawnee}-${d.opp}</td>
        <td><span class="badge ${d.result === 'W' ? 'w' : 'l'}">${esc(d.result)}</span></td>
      </tr>`).join(''));
  }

  function renderHomeRoster(homeRoster) {
    const grid = document.getElementById('homeRosterGrid');
    if (!grid) return;
    if (!homeRoster || !(homeRoster.wrestlers || []).length) {
      grid.innerHTML = '<p>Roster gallery unavailable.</p>';
      return;
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
          ${careerLine(r)}
        </div>
      </${tag}>`;
    }).join('');
  }


  function photoSrc(photo) {
    return photo || PLACEHOLDER_PHOTO;
  }

  function careerLine(r) {
    if (!r || !r.show_career) return '';
    if (r.career_wins == null || r.career_losses == null) return '';
    return `<div class="meta career">Career ${esc(`${r.career_wins}-${r.career_losses}`)}</div>`;
  }

  function renderVarsityCards(assign, data) {
    const c = assign.counts || {};
    const meta = document.getElementById('varsityMeta');
    if (meta) meta.innerHTML = `
      <span><strong>Filled</strong> ${c.filled ?? 0} / ${c.weight_classes ?? 14}</span>
      <span><strong>Vacant</strong> ${c.vacant ?? 0}</span>
      <span><strong>Full roster</strong> ${c.full_roster ?? (data.roster || []).length}</span>
      <span><strong>Season</strong> 2025-2026 Season</span>`;
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

  function renderFullRosterSearchable(data, index) {
    // Roster cards: current wrestlers only (current-season weights). Alumni live on player pages.
    const fromIndex = ((index && index.wrestlers) || []).filter((w) => w.status !== 'alumni');
    const rows = (fromIndex.length ? fromIndex : null) || (data.roster || []).map((w) => ({
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
    if (!grid) return;
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
            ${careerLine(r)}
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
    const seasonLabelText = data.metadata?.title || data.metadata?.season || 'Season';
    const statusChip = seasonFinal
      ? `<span><strong>Season</strong> Final · ${esc(seasonLabelText)}</span>`
      : `<span><strong>Season</strong> ${esc(seasonLabelText)}</span>`;
    setHtml(document.getElementById('schedMeta'), `<span><strong>Dual record</strong> ${esc(rec)}</span>
      <span><strong>Conference</strong> ${esc(conf || '—')}</span>
      <span><strong>Listings</strong> ${(data.schedule || []).length}</span>
      ${statusChip}`);
    const body = document.querySelector('#scheduleTable tbody');
    if (!body) return;
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

  function isShawneeVenue(loc) {
    const n = String(loc || '').replace(/\s+/g, ' ').trim().toLowerCase();
    return n === 'shawnee' || n.startsWith('shawnee ');
  }

  function dualSiteLabel(homeAway, location) {
    const venue = String(location || '').replace(/\s+/g, ' ').trim();
    let site = null;
    if (homeAway === 'away') site = 'Away';
    else if (homeAway === 'home') site = 'Home';
    else if (homeAway === 'event') {
      // Infer Home/Away only when a venue is known
      if (venue) site = isShawneeVenue(venue) ? 'Home' : 'Away';
    } else if (homeAway) {
      site = homeAway === 'away' ? 'Away' : 'Home';
    } else if (venue) {
      // Home/away omitted in source: infer only from a known venue
      site = isShawneeVenue(venue) ? 'Home' : 'Away';
    }
    if (!site) return '';
    return venue ? `${site} · ${venue}` : site;
  }

  /** Build dual rows for Results: date, location, logos, cumulative W-L (season-agnostic). */
  function buildResultsDualRows(data) {
    const s = data.standings || {};
    const ds = data.dual_scores || {};
    const venueBy = new Map();
    (data.schedule || []).forEach((e) => {
      if (!e.opponent || !['W', 'L', 'T'].includes(e.result)) return;
      const key = `${e.date_iso || ''}\0${e.opponent}`;
      if (!venueBy.has(key)) {
        venueBy.set(key, {
          location: (e.location || '').replace(/\s+/g, ' ').trim() || null,
          home_away: e.home_away,
        });
      }
    });

    let base;
    if (s.rows && s.rows.length) {
      base = s.rows.map((r, idx) => ({ ...r, _idx: idx }));
    } else {
      base = (ds.duals || []).map((d, idx) => ({
        opponent: d.opponent,
        score: d.score_display || `${d.shawnee}-${d.opp}`,
        result: d.result,
        date_iso: d.date_iso,
        conference_dual: d.conference || d.conference_dual,
        opponent_logo_local: d.opponent_logo_local,
        opponent_logo: d.opponent_logo,
        home_away: d.home_away,
        location: d.location,
        location_display: d.location_display,
        cumulative_record: d.cumulative_record,
        _idx: idx,
      }));
    }

    base.sort((a, b) => String(a.date_iso || '').localeCompare(String(b.date_iso || '')) || (a._idx - b._idx));

    let w = 0, l = 0, t = 0;
    return base.map((r) => {
      const key = `${r.date_iso || ''}\0${r.opponent || ''}`;
      const info = venueBy.get(key) || {};
      const location = r.location || info.location || null;
      const homeAway = r.home_away || info.home_away || null;
      const location_display = (r.location_display != null && r.location_display !== '')
        ? r.location_display
        : dualSiteLabel(homeAway, location);
      if (r.result === 'W') w += 1;
      else if (r.result === 'L') l += 1;
      else if (r.result === 'T') t += 1;
      const cumulative = r.cumulative_record || (`${w}-${l}` + (t ? `-${t}` : ''));
      // Prefer freshly computed running total so UI stays correct even if JSON lags
      const running = `${w}-${l}` + (t ? `-${t}` : '');
      return {
        ...r,
        score: r.score || r.score_display,
        location,
        location_display,
        cumulative_record: running,
      };
    });
  }

  function renderResults(data) {
    const s = data.standings || {};
    const ds = data.dual_scores || {};
    const meta = document.getElementById('resultsMeta');
    const seasonLabel = data.metadata?.title || data.metadata?.season || s.season || 'Season';
    const seasonFinal = (data.metadata?.status || data.metadata?.season_status || s.status) === 'final';
    const rows = buildResultsDualRows(data);
    const finalRec = rows.length ? rows[rows.length - 1].cumulative_record : (s.shawnee_dual_record || ds.record || '—');
    if (meta) meta.innerHTML =
      `<span><strong>Shawnee duals</strong> ${esc(s.shawnee_dual_record || ds.record || finalRec)}</span>
       <span><strong>Conference</strong> ${esc(s.conference_record || ds.conference_record || '—')}</span>
       <span><strong>Season</strong> ${seasonFinal ? `Final · ${esc(seasonLabel)}` : esc(seasonLabel)}</span>`;
    const dualBody = document.querySelector('#resultsDualsTable tbody');
    if (dualBody) dualBody.innerHTML = rows.map((r) => `
      <tr>
        <td>${esc(r.date_iso || r.date || '')}</td>
        <td><div class="opp">${logoImg(r.opponent_logo_local, r.opponent_logo, r.opponent)}<span>${esc(r.opponent)}${r.conference_dual ? ' <em class="conf-tag">conf</em>' : ''}</span></div></td>
        <td>${esc(r.location_display ?? dualSiteLabel(r.home_away, r.location))}</td>
        <td>${esc(r.score)}</td>
        <td><span class="badge ${r.result === 'W' ? 'w' : (r.result === 'L' ? 'l' : 'ev')}">${esc(r.result)}</span></td>
        <td>${esc(r.cumulative_record)}</td>
      </tr>`).join('');
  }

  function fmtPctCell(v) {
    if (v == null || v === '') return '';
    const n = Number(v);
    if (!Number.isFinite(n)) return esc(v);
    return n.toFixed(3).replace(/^0/, '');
  }

  function blankOr(v) {
    if (v == null || v === '') return '<span class="muted-cell">—</span>';
    return esc(v);
  }

  function renderConferenceStandings(doc) {
    const meta = document.getElementById('standingsMeta');
    const seasonTitle = doc.title || doc.season || 'Season';
    if (meta) {
      const final = (doc.status || doc.season_status) === 'final';
      meta.innerHTML =
        `<span><strong>Conference</strong> ${esc(doc.conference || 'Olympic')}</span>
         <span><strong>Season</strong> ${final ? `Final · ${esc(seasonTitle)}` : esc(seasonTitle)}</span>
         <span><strong>As of</strong> ${esc(doc.as_of || doc.generated_at || '—')}</span>`;
    }
    const host = document.getElementById('conferenceStandings');
    if (!host) return;
    const divisions = doc.divisions || [];
    const sample = divisions.flatMap((d) => d.teams || [])[0] || {};
    const cols = doc.columns || [];
    const showDiv = cols.includes('div') || cols.includes('division') || sample.division_record != null;
    const showHome = cols.includes('home') || sample.home_record != null;
    const showAway = cols.includes('away') || sample.away_record != null;
    const showPfPa = cols.includes('pf') || sample.pf != null || sample.pa != null;
    const showPct = cols.includes('pct') || sample.overall_pct != null;

    host.innerHTML = divisions.map((div) => {
      const heading = doc.reconstructed
        ? (div.name === 'Shawnee' ? 'Shawnee' : esc(div.name))
        : `${esc(div.name)} Division`;
      const headCells = ['<th>#</th>', '<th>Team</th>', '<th class="num">Overall</th>'];
      if (showPct) headCells.push('<th class="num">PCT</th>');
      if (showDiv) headCells.push('<th class="num">Div</th>', '<th class="num">Div PCT</th>');
      if (showHome) headCells.push('<th class="num">Home</th>');
      if (showAway) headCells.push('<th class="num">Away</th>');
      if (showPfPa) headCells.push('<th class="num">PF</th>', '<th class="num">PA</th>');

      const rows = (div.teams || []).map((t) => {
        const cls = t.is_shawnee ? ' class="shawnee-row"' : '';
        const cells = [
          `<td class="rank">${esc(t.rank)}</td>`,
          `<td><div class="opp">${logoImg(t.logo_local, t.logo, t.team)}<span>${esc(t.team)}${t.is_shawnee ? ' <em class="conf-tag">us</em>' : ''}</span></div></td>`,
          `<td class="num">${blankOr(t.overall_record)}</td>`,
        ];
        if (showPct) cells.push(`<td class="num">${t.overall_pct == null ? blankOr(null) : esc(fmtPctCell(t.overall_pct))}</td>`);
        if (showDiv) {
          cells.push(`<td class="num">${blankOr(t.division_record)}</td>`);
          cells.push(`<td class="num">${t.division_pct == null ? blankOr(null) : esc(fmtPctCell(t.division_pct))}</td>`);
        }
        if (showHome) cells.push(`<td class="num">${blankOr(t.home_record)}</td>`);
        if (showAway) cells.push(`<td class="num">${blankOr(t.away_record)}</td>`);
        if (showPfPa) {
          cells.push(`<td class="num">${blankOr(t.pf)}</td>`);
          cells.push(`<td class="num">${blankOr(t.pa)}</td>`);
        }
        return `<tr${cls}>${cells.join('')}</tr>`;
      }).join('');
      return `<section class="division-block">
        <h2 class="section-title">${heading}</h2>
        <div class="table-wrap"><table class="standings-table">
          <thead><tr>${headCells.join('')}</tr></thead>
          <tbody>${rows}</tbody>
        </table></div>
      </section>`;
    }).join('') || '<p class="muted">Standings unavailable.</p>';
  }

  function playerPageMap(index) {
    const map = Object.create(null);
    for (const w of (index && index.wrestlers) || []) {
      const href = w.player_page || '';
      if (!href) continue;
      if (w.wrestler_id) map['id:' + String(w.wrestler_id)] = href;
      if (w.name) map['name:' + String(w.name).trim().toLowerCase()] = href;
    }
    return map;
  }

  function renderStats(data, index) {
    const pages = playerPageMap(index);
    const tbody = document.querySelector('#statsTable tbody');
    if (!tbody) return;
    const rows = (data.stats || data.roster || []).slice().sort((a, b) => (b.wins || 0) - (a.wins || 0) || (a.losses || 0) - (b.losses || 0));
    tbody.innerHTML = rows.map((w) => {
      const wins = w.wins || 0, losses = w.losses || 0;
      const pct = (wins + losses) ? ((wins / (wins + losses)) * 100).toFixed(1) + '%' : '—';
      const href = pages['id:' + String(w.wrestler_id || '')] || pages['name:' + String(w.name || '').trim().toLowerCase()] || '';
      const nameCell = href
        ? `<a href="${esc(href)}">${esc(w.name)}</a>`
        : esc(w.name);
      return `<tr>
        <td>${nameCell}</td>
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
    const grid = document.getElementById('awardsGrid');
    if (!filters || !grid) return;
    const kinds = ['all', ...new Set(Object.values(byName).map((c) => c.kind))];
    filters.innerHTML = kinds.map((k) =>
      `<button type="button" data-kind="${esc(k)}" class="${k === 'all' ? 'active' : ''}">${esc(k)}</button>`
    ).join('');

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
