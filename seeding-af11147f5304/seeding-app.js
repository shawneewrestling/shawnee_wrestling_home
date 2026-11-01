/* global SeedingEngine */
(function () {
  "use strict";

  const WEIGHTS = [106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285];
  const SEASONS = ["2025-26", "2024-25", "2023-24"];

  const els = {};
  let advancement = null;
  let lastResult = null;

  function $(id) { return document.getElementById(id); }

  function initDom() {
    ["level", "season", "weight", "status", "wrestlerPaste", "boutPaste",
      "preSeedBody", "finalSeedBody", "loopsBox", "votesBox", "pairsBox",
      "movementsBox", "runBtn", "loadSampleBtn", "clearBoutsBtn", "incompleteFlag"
    ].forEach(function (id) { els[id] = $(id); });

    SEASONS.forEach(function (s) {
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      els.season.appendChild(o);
    });
    WEIGHTS.forEach(function (w) {
      const o = document.createElement("option");
      o.value = String(w); o.textContent = String(w);
      els.weight.appendChild(o);
    });

    els.runBtn.addEventListener("click", run);
    els.loadSampleBtn.addEventListener("click", loadSample);
    els.clearBoutsBtn.addEventListener("click", function () {
      els.boutPaste.value = "";
    });
  }

  function setStatus(msg, isWarn) {
    els.status.textContent = msg || "";
    els.status.className = "seed-banner" + (isWarn ? " warn" : "");
    els.status.hidden = !msg;
  }

  async function loadData() {
    setStatus("Loading advancement data…");
    try {
      const res = await fetch("data/opponent_advancement.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      advancement = await res.json();
      setStatus("Advancement loaded (" + Object.keys(advancement.athletes || {}).length + " athletes). Bout data is incomplete — paste bouts or enter wrestlers manually.");
    } catch (e) {
      advancement = { athletes: {}, code_rank: {}, by_name: {} };
      setStatus("Could not load advancement JSON (" + e.message + "). Manual entry still works.", true);
    }
  }

  /** Parse wrestlers paste:
   * name | school | districtPlace | priorCode | twPoints | winsOverSeeded | winsOverPrior
   * or JSON array
   */
  function parseWrestlers(text) {
    text = (text || "").trim();
    if (!text) return [];
    if (text[0] === "[" || text[0] === "{") {
      const data = JSON.parse(text);
      const arr = Array.isArray(data) ? data : data.wrestlers;
      return arr.map(function (w, i) {
        return normalizeWrestler(w, i);
      });
    }
    return text.split(/\n+/).map(function (line, i) {
      if (!line.trim() || line.trim().startsWith("#")) return null;
      const p = line.split("|").map(function (s) { return s.trim(); });
      return normalizeWrestler({
        name: p[0],
        school: p[1] || "",
        districtPlace: p[2] ? Number(p[2]) : null,
        priorCode: p[3] || null,
        twPoints: p[4] ? Number(p[4]) : 0,
        winsOverSeeded: p[5] ? Number(p[5]) : 0,
        winsOverPrior: p[6] ? Number(p[6]) : 0,
      }, i);
    }).filter(Boolean);
  }

  function normalizeWrestler(w, i) {
    const id = w.id || slugId(w.name, w.school, i);
    const priorCode = w.priorCode || lookupPriorCode(w.name, w.school, els.season.value);
    const codeRank = (advancement && advancement.code_rank) || {};
    const priorRank = typeof w.priorRank === "number"
      ? w.priorRank
      : (priorCode && codeRank[priorCode]) || -1;
    const districtPlace = w.districtPlace != null && w.districtPlace !== ""
      ? Number(w.districtPlace)
      : null;
    return {
      id: id,
      name: w.name || ("Wrestler " + i),
      school: w.school || "",
      districtPlace: districtPlace,
      isChamp: !!(w.isChamp || districtPlace === 1),
      priorCode: priorCode,
      priorRank: priorRank,
      twPoints: Number(w.twPoints) || 0,
      winsOverSeeded: Number(w.winsOverSeeded) || 0,
      winsOverPrior: Number(w.winsOverPrior) || 0,
    };
  }

  function slugId(name, school, i) {
    const base = String(name || "w" + i).toLowerCase().replace(/[^a-z0-9]+/g, "");
    const sch = String(school || "").toLowerCase().replace(/[^a-z0-9]+/g, "").slice(0, 12);
    return base + (sch ? "_" + sch : "") || ("w" + i);
  }

  function lookupPriorCode(name, school, season) {
    if (!advancement || !advancement.by_name) return null;
    const key = String(name || "").toLowerCase().trim();
    const ids = advancement.by_name[key] || [];
    // Prefer school match
    let best = null;
    ids.forEach(function (aid) {
      const a = advancement.athletes[aid];
      if (!a) return;
      const schoolOk = !school || (a.schools || []).some(function (s) {
        return s.toLowerCase() === String(school).toLowerCase();
      }) || (a.school || "").toLowerCase() === String(school).toLowerCase();
      if (!schoolOk && school) return;
      // most recent season before current? use selected season's prior window:
      // for seeding season S, look at finishes in seasons before S — career best at level handled in engine
      const seasons = a.seasons || {};
      // Prefer career_best; also expose season code for selected prior year
      best = a.career_best || best;
      // If the athlete has a finish in the immediately prior season, note it
      const priorSeason = priorSeasonOf(season);
      if (priorSeason && seasons[priorSeason] && seasons[priorSeason].code) {
        best = seasons[priorSeason].code;
      }
    });
    return best;
  }

  function priorSeasonOf(season) {
    const map = { "2025-26": "2024-25", "2024-25": "2023-24", "2023-24": "2022-23" };
    return map[season] || null;
  }

  /** Bout paste: winner | loser | date(YYYY-MM-DD)
   * or JSON
   */
  function parseBouts(text, wrestlers) {
    text = (text || "").trim();
    if (!text) return [];
    const byName = {};
    wrestlers.forEach(function (w) {
      byName[w.name.toLowerCase()] = w.id;
      byName[w.id.toLowerCase()] = w.id;
    });
    function resolve(x) {
      const k = String(x).toLowerCase().trim();
      return byName[k] || slugId(x, "", 0);
    }
    if (text[0] === "[" || text[0] === "{") {
      const data = JSON.parse(text);
      const arr = Array.isArray(data) ? data : data.bouts;
      return arr.map(function (b, i) {
        return {
          id: b.id || "b" + i,
          winnerId: resolve(b.winnerId || b.winner),
          loserId: resolve(b.loserId || b.loser),
          date: b.date || "",
          seq: typeof b.seq === "number" ? b.seq : i,
        };
      });
    }
    return text.split(/\n+/).map(function (line, i) {
      if (!line.trim() || line.trim().startsWith("#")) return null;
      const p = line.split("|").map(function (s) { return s.trim(); });
      return {
        id: "b" + i,
        winnerId: resolve(p[0]),
        loserId: resolve(p[1]),
        date: p[2] || "",
        seq: i,
      };
    }).filter(Boolean);
  }

  function loadSample() {
    els.wrestlerPaste.value = [
      "# name | school | districtPlace | priorCode | twPoints | winsOverSeeded | winsOverPrior",
      "Alex Champ | Shawnee | 1 | R1place | 120 | 2 | 3",
      "Blake Second | Cherokee | 2 | R3place | 100 | 1 | 2",
      "Chris Third | Lenape | 3 | D1 | 90 | 0 | 1",
      "Drew Champ2 | Seneca | 1 | R2place | 110 | 1 | 1",
      "Evan Second2 | Shawnee | 2 | Quarters Dis | 80 | 0 | 0",
      "Frank Third2 | Cherokee | 3 | | 70 | 0 | 0",
      "Gabe Champ3 | Lenape | 1 | swb1 | 130 | 3 | 2",
      "Hank Second3 | Seneca | 2 | R4place | 95 | 0 | 1",
      "Ian Third3 | Shawnee | 3 | | 60 | 0 | 0",
      "Jake Champ4 | Cherokee | 1 | RWB1 | 85 | 0 | 0",
      "Kyle Second4 | Lenape | 2 | | 55 | 0 | 0",
      "Leo Third4 | Seneca | 3 | | 50 | 0 | 0",
    ].join("\n");
    els.boutPaste.value = [
      "# winner | loser | date",
      "Blake Second | Chris Third | 2025-12-10",
      "Chris Third | Evan Second2 | 2025-12-20",
      "Evan Second2 | Blake Second | 2026-01-05",
      "Gabe Champ3 | Alex Champ | 2026-01-12",
      "Hank Second3 | Gabe Champ3 | 2026-01-18",
    ].join("\n");
    setStatus("Sample field loaded (includes a 3-cycle among Blake/Chris/Evan). Click Run seeding.");
  }

  function run() {
    let wrestlers;
    let bouts;
    try {
      wrestlers = parseWrestlers(els.wrestlerPaste.value);
      bouts = parseBouts(els.boutPaste.value, wrestlers);
    } catch (e) {
      setStatus("Parse error: " + e.message, true);
      return;
    }
    if (!wrestlers.length) {
      setStatus("Add at least one wrestler (paste or sample).", true);
      return;
    }
    const incomplete = bouts.length === 0;
    els.incompleteFlag.hidden = !incomplete;
    lastResult = SeedingEngine.runSeeding({
      level: els.level.value,
      wrestlers: wrestlers,
      bouts: bouts,
      codeRank: (advancement && advancement.code_rank) || {},
      boutDataIncomplete: incomplete,
    });
    render(lastResult);
    setStatus(
      (incomplete ? "Bout data incomplete — H2H/cycles limited. " : "") +
      "Pre-seeded " + lastResult.preSeed.length +
      "; final order ready. Struck bouts: " + lastResult.struckBouts.length +
      "; vote points: " + lastResult.votePoints.length + ".",
      incomplete
    );
  }

  function render(r) {
    renderSeedTable(els.preSeedBody, r.preSeed, null);
    renderSeedTable(els.finalSeedBody, r.finalSeed, r);
    renderLoops(r);
    renderVotes(r);
    renderPairs(r);
    renderMovements(r);
  }

  function renderSeedTable(tbody, list, result) {
    tbody.innerHTML = "";
    list.forEach(function (w, i) {
      const tr = document.createElement("tr");
      if (w.isChamp) tr.className = "champ";
      const vote = result && (result.votePoints || []).some(function (v) {
        return v.challengerId === w.id || v.higherId === w.id;
      });
      tr.innerHTML =
        "<td>" + (i + 1) + "</td>" +
        "<td>" + escapeHtml(w.name) +
          (w.isChamp ? '<span class="tag-pill">D1</span>' : "") +
          (vote ? '<span class="tag-pill vote">vote</span>' : "") +
        "</td>" +
        "<td>" + escapeHtml(w.school || "") + "</td>" +
        "<td>" + (w.districtPlace != null ? w.districtPlace : "") + "</td>" +
        "<td>" + escapeHtml(w.priorCode || "—") + "</td>" +
        "<td>" + (w.priorRank > 0 ? w.priorRank : "—") + "</td>" +
        "<td>" + (w.twPoints || 0) + "</td>";
      tbody.appendChild(tr);
    });
  }

  function renderLoops(r) {
    const box = els.loopsBox;
    box.innerHTML = "";
    if (!r.loops.length) {
      box.innerHTML = '<p class="muted">No round-robin cycles of length 3+ among entered bouts.</p>';
      return;
    }
    r.loops.forEach(function (loop, i) {
      const div = document.createElement("div");
      div.className = "loop-block";
      const path = loop.wrestlers.join(" → ") + " → " + loop.wrestlers[0];
      const struck = (loop.struck || []).map(function (b) {
        return b.winnerId + " over " + b.loserId + (b.date ? " (" + b.date + ")" : "");
      }).join("; ") || "—";
      div.innerHTML =
        "<strong>Loop " + (i + 1) + " (" + loop.wrestlers.length + ")</strong>: " +
        escapeHtml(path) +
        "<br><span class='tag-pill struck'>struck</span> " + escapeHtml(struck);
      box.appendChild(div);
    });
  }

  function renderVotes(r) {
    const box = els.votesBox;
    box.innerHTML = "";
    if (!r.votePoints.length) {
      box.innerHTML = '<p class="muted">No vote / extenuating points flagged.</p>';
      return;
    }
    r.votePoints.forEach(function (v) {
      const div = document.createElement("div");
      div.className = "vote-card";
      div.innerHTML =
        "<strong>Vote:</strong> " + escapeHtml(v.challengerId) + " vs " + escapeHtml(v.higherId) +
        " (" + escapeHtml(v.record) + ")<br>" +
        "<em>Stay:</em> " + escapeHtml(v.outcomeStay.join(", ")) + "<br>" +
        "<em>Move challenger up:</em> " + escapeHtml(v.outcomeMove.join(", ")) + "<br>" +
        "<span class='muted'>" + escapeHtml(v.note) + "</span>";
      box.appendChild(div);
    });
  }

  function renderPairs(r) {
    const box = els.pairsBox;
    box.innerHTML = "";
    if (r.level !== "region") {
      box.innerHTML = '<p class="muted">2nd/3rd pairings apply to region only.</p>';
      return;
    }
    if (!r.pairs.length) {
      box.innerHTML = '<p class="muted">No pairings (need non-champ 2nd/3rd place wrestlers).</p>';
      return;
    }
    const ul = document.createElement("ul");
    r.pairs.forEach(function (p) {
      const li = document.createElement("li");
      li.textContent = p.higher.name + " vs " + p.lower.name;
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  function renderMovements(r) {
    const box = els.movementsBox;
    box.innerHTML = "";
    if (!r.movements.length) {
      box.innerHTML = '<p class="muted">No head-to-head movements applied.</p>';
      return;
    }
    const ul = document.createElement("ul");
    r.movements.forEach(function (m) {
      const li = document.createElement("li");
      li.textContent = m.type.toUpperCase() + ": " + m.challenger + " vs " + m.over +
        " — " + m.reason + " (" + m.record + ")";
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  initDom();
  loadData();
})();
