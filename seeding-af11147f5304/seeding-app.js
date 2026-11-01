/* global SeedingEngine */
(function () {
  "use strict";

  const WEIGHTS = [106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285];
  const SEASONS = ["2025-26", "2024-25", "2023-24", "2026-27"];
  const LS_KEY = "shawnee_seeding_group_v1";

  const els = {};
  /** @type {{meta:any, athletes:any[], byId:Object}} */
  let pool = { meta: null, athletes: [], byId: {} };
  /** @type {any[]} */
  let group = [];
  /** @type {any[]} */
  let bouts = [];
  let lastResult = null;
  let searchTimer = null;
  const checkedIds = {};

  function $(id) { return document.getElementById(id); }

  function initDom() {
    [
      "level", "season", "weight", "groupName", "status", "incompleteFlag",
      "poolSearch", "filterWeightOnly", "poolResults",
      "selectVisibleBtn", "selectAllWeightBtn", "clearSelBtn", "addSelectedBtn",
      "manualName", "manualSchool", "manualPrior", "manualTw", "addManualBtn",
      "groupCount", "groupBody", "prestigeNote",
      "boutWinner", "boutLoser", "boutDate", "addBoutBtn", "boutBody",
      "wrestlerPaste", "boutPaste", "applyWrestlerPaste", "applyBoutPaste",
      "preSeedBody", "finalSeedBody", "struckBox", "loopsBox", "votesBox",
      "pairsBox", "movementsBox", "criteriaBox",
      "runBtn", "loadSampleBtn", "saveLocalBtn", "loadLocalBtn",
      "exportBtn", "importFile", "clearGroupBtn",
    ].forEach(function (id) { els[id] = $(id); });

    SEASONS.forEach(function (s) {
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      els.season.appendChild(o);
    });
    const wall = document.createElement("option");
    wall.value = ""; wall.textContent = "All";
    els.weight.appendChild(wall);
    WEIGHTS.forEach(function (w) {
      const o = document.createElement("option");
      o.value = String(w); o.textContent = String(w);
      els.weight.appendChild(o);
    });
    els.weight.value = "150";

    els.runBtn.addEventListener("click", run);
    els.loadSampleBtn.addEventListener("click", loadSample);
    els.saveLocalBtn.addEventListener("click", saveLocal);
    els.loadLocalBtn.addEventListener("click", loadLocal);
    els.exportBtn.addEventListener("click", exportJson);
    els.importFile.addEventListener("change", importJson);
    els.clearGroupBtn.addEventListener("click", function () {
      group = []; bouts = []; renderGroup(); renderBouts(); setStatus("Group cleared.");
    });
    els.poolSearch.addEventListener("input", function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(renderPoolResults, 120);
    });
    els.filterWeightOnly.addEventListener("change", renderPoolResults);
    els.weight.addEventListener("change", renderPoolResults);
    els.season.addEventListener("change", function () {
      // refresh prestige for pool-sourced members
      group.forEach(function (w) {
        if (w.fromPool && w._seasons) applyPrestige(w);
      });
      renderGroup();
      updatePrestigeNote();
    });
    els.selectVisibleBtn.addEventListener("click", selectVisible);
    if (els.selectAllWeightBtn) els.selectAllWeightBtn.addEventListener("click", selectAllAtWeight);
    els.clearSelBtn.addEventListener("click", function () {
      Object.keys(checkedIds).forEach(function (k) { delete checkedIds[k]; });
      renderPoolResults();
    });
    els.addSelectedBtn.addEventListener("click", addSelected);
    els.addManualBtn.addEventListener("click", addManual);
    els.addBoutBtn.addEventListener("click", addBoutFromForm);
    els.applyWrestlerPaste.addEventListener("click", applyWrestlerPaste);
    els.applyBoutPaste.addEventListener("click", applyBoutPaste);
  }

  function setStatus(msg, isWarn) {
    els.status.textContent = msg || "";
    els.status.className = "seed-banner" + (isWarn ? " warn" : "");
    els.status.hidden = !msg;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function slugId(name, school, i) {
    const base = String(name || "w" + i).toLowerCase().replace(/[^a-z0-9]+/g, "");
    const sch = String(school || "").toLowerCase().replace(/[^a-z0-9]+/g, "").slice(0, 12);
    return base + (sch ? "_" + sch : "") || ("w" + i);
  }

  async function loadPool() {
    setStatus("Loading statewide pool…");
    try {
      const res = await fetch("data/pool_index.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      pool.meta = data.meta || {};
      pool.athletes = data.athletes || [];
      pool.byId = {};
      pool.athletes.forEach(function (a) { pool.byId[a.id] = a; });
      setStatus(
        "Pool ready: " + pool.athletes.length + " wrestlers. Search and multi-select to build a group."
      );
      updatePrestigeNote();
      renderPoolResults();
    } catch (e) {
      pool = { meta: { code_rank: {} }, athletes: [], byId: {} };
      setStatus("Could not load pool index (" + e.message + "). Manual entry still works.", true);
    }
  }

  function codeRank() {
    return (pool.meta && pool.meta.code_rank) || {};
  }

  function updatePrestigeNote() {
    const win = SeedingEngine.priorSeasonWindow(els.season.value, 4);
    els.prestigeNote.textContent =
      "Prestige window for " + els.season.value + ": " + win.join(", ") +
      " (best finish in window).";
  }

  function expandAthlete(a) {
    // compact keys → seasons map objects
    const seasons = {};
    const se = a.se || a.seasons || {};
    Object.keys(se).forEach(function (s) {
      const v = se[s];
      if (Array.isArray(v)) {
        seasons[s] = { code: v[0], weight: v[1], grade: v[2], school: v[3] };
      } else {
        seasons[s] = v;
      }
    });
    return {
      id: a.id,
      name: a.n || a.name,
      school: a.sch || a.school || "",
      schools: a.schs || a.schools || [],
      career_best: a.cb || a.career_best || "",
      weights: a.w || a.weights || [],
      seasons: seasons,
    };
  }

  function applyPrestige(w) {
    const best = SeedingEngine.bestPriorInWindow(w._seasons || {}, els.season.value, codeRank(), 4);
    if (!w.priorCodeLocked) {
      w.priorCode = best.priorCode;
      w.priorRank = best.priorRank;
      w.priorSeason = best.priorSeason;
      w.priorFinishes = best.finishes;
    } else {
      w.priorRank = codeRank()[w.priorCode] || w.priorRank || -1;
    }
    return w;
  }

  function renderPoolResults() {
    const q = String(els.poolSearch.value || "").trim().toLowerCase();
    const wFilter = els.filterWeightOnly.checked ? Number(els.weight.value) : 0;
    const box = els.poolResults;
    box.innerHTML = "";
    if (!q && !wFilter) {
      box.innerHTML = '<p class="muted">Type a name/school' +
        (els.filterWeightOnly.checked ? " or uncheck weight limit to browse." : ".") + "</p>";
      return;
    }
    let hits = [];
    for (let i = 0; i < pool.athletes.length; i++) {
      const raw = pool.athletes[i];
      const name = (raw.n || "").toLowerCase();
      const schs = (raw.schs || []).join(" ").toLowerCase() + " " + (raw.sch || "").toLowerCase();
      if (q && name.indexOf(q) < 0 && schs.indexOf(q) < 0) continue;
      if (wFilter && !(raw.w || []).includes(wFilter)) continue;
      hits.push(raw);
      if (hits.length >= 80) break;
    }
    if (!hits.length) {
      box.innerHTML = '<p class="muted">No matches.</p>';
      return;
    }
    const table = document.createElement("table");
    table.className = "seed-table pool-table";
    table.innerHTML =
      "<thead><tr><th></th><th>Name</th><th>School</th><th>Weights</th><th>Career best</th></tr></thead>";
    const tb = document.createElement("tbody");
    hits.forEach(function (raw) {
      const tr = document.createElement("tr");
      const id = raw.id;
      const inGroup = group.some(function (g) { return g.id === id; });
      tr.innerHTML =
        '<td><input type="checkbox" data-id="' + escapeHtml(id) + '"' +
          (checkedIds[id] ? " checked" : "") +
          (inGroup ? " disabled" : "") + " /></td>" +
        "<td>" + escapeHtml(raw.n) + (inGroup ? ' <span class="tag-pill">in group</span>' : "") + "</td>" +
        "<td>" + escapeHtml(raw.sch || "") + "</td>" +
        "<td>" + escapeHtml((raw.w || []).join(", ")) + "</td>" +
        "<td>" + escapeHtml(raw.cb || "—") + "</td>";
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    box.appendChild(table);
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = "Showing " + hits.length + (hits.length >= 80 ? "+ (refine search)" : "") + " matches.";
    box.appendChild(note);

    box.querySelectorAll('input[type=checkbox][data-id]').forEach(function (cb) {
      cb.addEventListener("change", function () {
        if (cb.checked) checkedIds[cb.getAttribute("data-id")] = true;
        else delete checkedIds[cb.getAttribute("data-id")];
      });
    });
  }

  function selectVisible() {
    els.poolResults.querySelectorAll('input[type=checkbox][data-id]:not(:disabled)').forEach(function (cb) {
      cb.checked = true;
      checkedIds[cb.getAttribute("data-id")] = true;
    });
  }

  function selectAllAtWeight() {
    const wFilter = Number(els.weight.value);
    if (!wFilter) {
      setStatus("Pick a weight first to select all at that weight.", true);
      return;
    }
    const q = String(els.poolSearch.value || "").trim().toLowerCase();
    let n = 0;
    for (let i = 0; i < pool.athletes.length; i++) {
      const raw = pool.athletes[i];
      if (!(raw.w || []).includes(wFilter)) continue;
      if (q) {
        const name = (raw.n || "").toLowerCase();
        const schs = (raw.schs || []).join(" ").toLowerCase() + " " + (raw.sch || "").toLowerCase();
        if (name.indexOf(q) < 0 && schs.indexOf(q) < 0) continue;
      }
      if (group.some(function (g) { return g.id === raw.id; })) continue;
      checkedIds[raw.id] = true;
      n++;
      if (n >= 40) break;
    }
    renderPoolResults();
    setStatus("Checked " + n + " wrestler(s) at " + wFilter + " (cap 40). Click Add selected.");
  }

  function addSelected() {
    const ids = Object.keys(checkedIds);
    if (!ids.length) {
      setStatus("Check one or more wrestlers first.", true);
      return;
    }
    let added = 0;
    ids.forEach(function (id) {
      if (group.some(function (g) { return g.id === id; })) return;
      const raw = pool.byId[id];
      if (!raw) return;
      const ex = expandAthlete(raw);
      const w = {
        id: ex.id,
        name: ex.name,
        school: ex.school,
        districtPlace: null,
        isChamp: false,
        priorCode: null,
        priorRank: -1,
        twPoints: 0,
        winsOverSeeded: 0,
        winsOverPrior: 0,
        record: "",
        fromPool: true,
        priorCodeLocked: false,
        _seasons: ex.seasons,
      };
      applyPrestige(w);
      group.push(w);
      added++;
    });
    Object.keys(checkedIds).forEach(function (k) { delete checkedIds[k]; });
    renderGroup();
    renderPoolResults();
    setStatus("Added " + added + " wrestler(s) to the group.");
  }

  function addManual() {
    const name = String(els.manualName.value || "").trim();
    if (!name) {
      setStatus("Enter a name for the manual wrestler.", true);
      return;
    }
    const school = String(els.manualSchool.value || "").trim();
    const prior = String(els.manualPrior.value || "").trim() || null;
    const tw = Number(els.manualTw.value) || 0;
    const id = slugId(name, school, group.length) + "_manual" + Date.now().toString(36);
    const w = {
      id: id,
      name: name,
      school: school,
      districtPlace: null,
      isChamp: false,
      priorCode: prior,
      priorRank: prior ? (codeRank()[prior] || -1) : -1,
      twPoints: tw,
      winsOverSeeded: 0,
      winsOverPrior: 0,
      record: "",
      fromPool: false,
      priorCodeLocked: !!prior,
      _seasons: {},
    };
    group.push(w);
    els.manualName.value = "";
    els.manualSchool.value = "";
    els.manualPrior.value = "";
    els.manualTw.value = "";
    renderGroup();
    setStatus("Added manual wrestler " + name + ".");
  }

  function renderGroup() {
    els.groupCount.textContent = String(group.length);
    const tb = els.groupBody;
    tb.innerHTML = "";
    group.forEach(function (w, idx) {
      const tr = document.createElement("tr");
      if (w.isChamp || w.districtPlace === 1) tr.className = "champ";
      tr.innerHTML =
        "<td>" + (idx + 1) + "</td>" +
        "<td>" + escapeHtml(w.name) +
          (w.fromPool ? "" : ' <span class="tag-pill">manual</span>') +
        "</td>" +
        "<td>" + escapeHtml(w.school || "") + "</td>" +
        '<td><input class="cell-in" data-f="districtPlace" data-i="' + idx + '" type="number" min="1" max="4" value="' +
          (w.districtPlace != null ? w.districtPlace : "") + '" style="width:3.2rem" /></td>' +
        '<td><input class="cell-in" data-f="priorCode" data-i="' + idx + '" type="text" value="' +
          escapeHtml(w.priorCode || "") + '" style="width:6.5rem" /></td>' +
        "<td>" + (w.priorRank > 0 ? w.priorRank : "—") + "</td>" +
        '<td><input class="cell-in" data-f="twPoints" data-i="' + idx + '" type="number" value="' +
          (w.twPoints || 0) + '" style="width:4.5rem" /></td>' +
        '<td><input class="cell-in" data-f="winsOverSeeded" data-i="' + idx + '" type="number" value="' +
          (w.winsOverSeeded || 0) + '" style="width:3.5rem" /></td>' +
        '<td><input class="cell-in" data-f="winsOverPrior" data-i="' + idx + '" type="number" value="' +
          (w.winsOverPrior || 0) + '" style="width:3.5rem" /></td>' +
        '<td><input class="cell-in" data-f="record" data-i="' + idx + '" type="text" value="' +
          escapeHtml(w.record || "") + '" style="width:4.5rem" placeholder="12-3" /></td>' +
        '<td><button type="button" class="linkish" data-rm="' + idx + '">Remove</button></td>';
      tb.appendChild(tr);
    });
    tb.querySelectorAll("input.cell-in").forEach(function (inp) {
      inp.addEventListener("change", function () {
        const i = Number(inp.getAttribute("data-i"));
        const f = inp.getAttribute("data-f");
        let v = inp.value;
        if (["districtPlace", "twPoints", "winsOverSeeded", "winsOverPrior"].indexOf(f) >= 0) {
          v = v === "" ? (f === "districtPlace" ? null : 0) : Number(v);
        }
        group[i][f] = v;
        if (f === "districtPlace") {
          group[i].isChamp = v === 1;
        }
        if (f === "priorCode") {
          group[i].priorCodeLocked = true;
          group[i].priorRank = codeRank()[v] || -1;
          renderGroup();
        }
      });
    });
    tb.querySelectorAll("button[data-rm]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const i = Number(btn.getAttribute("data-rm"));
        const removed = group.splice(i, 1)[0];
        bouts = bouts.filter(function (b) {
          return b.winnerId !== removed.id && b.loserId !== removed.id;
        });
        renderGroup();
        renderBouts();
      });
    });
    fillBoutSelects();
  }

  function fillBoutSelects() {
    function fill(sel) {
      const cur = sel.value;
      sel.innerHTML = "";
      const opt0 = document.createElement("option");
      opt0.value = ""; opt0.textContent = "— pick —";
      sel.appendChild(opt0);
      group.forEach(function (w) {
        const o = document.createElement("option");
        o.value = w.id;
        o.textContent = w.name + (w.school ? " (" + w.school + ")" : "");
        sel.appendChild(o);
      });
      if (cur) sel.value = cur;
    }
    fill(els.boutWinner);
    fill(els.boutLoser);
  }

  function addBoutFromForm() {
    const w = els.boutWinner.value;
    const l = els.boutLoser.value;
    if (!w || !l || w === l) {
      setStatus("Pick two different group members for the bout.", true);
      return;
    }
    bouts.push({
      id: "b" + Date.now().toString(36) + bouts.length,
      winnerId: w,
      loserId: l,
      date: els.boutDate.value || "",
      seq: bouts.length,
    });
    renderBouts();
  }

  function nameOf(id) {
    const w = group.find(function (g) { return g.id === id; });
    return w ? w.name : id;
  }

  function renderBouts() {
    const tb = els.boutBody;
    tb.innerHTML = "";
    bouts.forEach(function (b, i) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + escapeHtml(nameOf(b.winnerId)) + "</td>" +
        "<td>" + escapeHtml(nameOf(b.loserId)) + "</td>" +
        "<td>" + escapeHtml(b.date || "") + "</td>" +
        '<td><button type="button" class="linkish" data-brm="' + i + '">Remove</button></td>';
      tb.appendChild(tr);
    });
    tb.querySelectorAll("button[data-brm]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        bouts.splice(Number(btn.getAttribute("data-brm")), 1);
        renderBouts();
      });
    });
  }

  function serializeGroup() {
    return {
      version: 1,
      groupName: els.groupName.value || "",
      level: els.level.value,
      season: els.season.value,
      weight: els.weight.value,
      wrestlers: group.map(function (w) {
        return {
          id: w.id,
          name: w.name,
          school: w.school,
          districtPlace: w.districtPlace,
          isChamp: w.isChamp,
          priorCode: w.priorCode,
          priorRank: w.priorRank,
          priorSeason: w.priorSeason,
          twPoints: w.twPoints,
          winsOverSeeded: w.winsOverSeeded,
          winsOverPrior: w.winsOverPrior,
          record: w.record,
          fromPool: w.fromPool,
          priorCodeLocked: w.priorCodeLocked,
          _seasons: w._seasons || {},
        };
      }),
      bouts: bouts,
    };
  }

  function loadSerialized(data) {
    if (!data || !Array.isArray(data.wrestlers)) throw new Error("Invalid group JSON");
    if (data.level) els.level.value = data.level;
    if (data.season) els.season.value = data.season;
    if (data.weight != null) els.weight.value = String(data.weight);
    if (data.groupName) els.groupName.value = data.groupName;
    group = data.wrestlers.map(function (w) {
      const x = Object.assign({}, w);
      if (x.fromPool && (!x.priorCode || !x.priorCodeLocked)) applyPrestige(x);
      else if (x.priorCode) x.priorRank = codeRank()[x.priorCode] || x.priorRank || -1;
      return x;
    });
    bouts = (data.bouts || []).map(function (b, i) {
      return {
        id: b.id || "b" + i,
        winnerId: b.winnerId,
        loserId: b.loserId,
        date: b.date || "",
        seq: typeof b.seq === "number" ? b.seq : i,
      };
    });
    renderGroup();
    renderBouts();
    updatePrestigeNote();
  }

  function saveLocal() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(serializeGroup()));
      setStatus("Saved group to this browser (localStorage).");
    } catch (e) {
      setStatus("Save failed: " + e.message, true);
    }
  }

  function loadLocal() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) {
        setStatus("No saved group in this browser.", true);
        return;
      }
      loadSerialized(JSON.parse(raw));
      setStatus("Loaded saved group (" + group.length + " wrestlers).");
    } catch (e) {
      setStatus("Load failed: " + e.message, true);
    }
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(serializeGroup(), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (els.groupName.value || "seeding-group").replace(/\s+/g, "-") + ".json";
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus("Exported group JSON.");
  }

  function importJson(ev) {
    const file = ev.target.files && ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function () {
      try {
        loadSerialized(JSON.parse(String(reader.result)));
        setStatus("Imported " + group.length + " wrestlers from " + file.name + ".");
      } catch (e) {
        setStatus("Import failed: " + e.message, true);
      }
      ev.target.value = "";
    };
    reader.readAsText(file);
  }

  function applyWrestlerPaste() {
    try {
      const list = parseWrestlers(els.wrestlerPaste.value);
      list.forEach(function (w) {
        if (group.some(function (g) { return g.id === w.id; })) return;
        // try pool enrich
        const hit = pool.athletes.find(function (a) {
          return (a.n || "").toLowerCase() === w.name.toLowerCase() &&
            (!w.school || (a.sch || "").toLowerCase() === w.school.toLowerCase());
        });
        if (hit) {
          const ex = expandAthlete(hit);
          w.id = ex.id;
          w.fromPool = true;
          w._seasons = ex.seasons;
          if (!w.priorCode) applyPrestige(w);
          else {
            w.priorCodeLocked = true;
            w.priorRank = codeRank()[w.priorCode] || -1;
          }
        }
        group.push(w);
      });
      renderGroup();
      setStatus("Applied wrestler paste (" + list.length + ").");
    } catch (e) {
      setStatus("Wrestler paste error: " + e.message, true);
    }
  }

  function applyBoutPaste() {
    try {
      const more = parseBouts(els.boutPaste.value, group);
      bouts = bouts.concat(more);
      renderBouts();
      setStatus("Applied bout paste (" + more.length + ").");
    } catch (e) {
      setStatus("Bout paste error: " + e.message, true);
    }
  }

  function parseWrestlers(text) {
    text = (text || "").trim();
    if (!text) return [];
    if (text[0] === "[" || text[0] === "{") {
      const data = JSON.parse(text);
      const arr = Array.isArray(data) ? data : data.wrestlers;
      return arr.map(function (w, i) { return normalizeWrestler(w, i); });
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
    const priorCode = w.priorCode || null;
    const priorRank = typeof w.priorRank === "number"
      ? w.priorRank
      : (priorCode && codeRank()[priorCode]) || -1;
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
      record: w.record || "",
      fromPool: !!w.fromPool,
      priorCodeLocked: !!w.priorCode,
      _seasons: w._seasons || {},
    };
  }

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
        id: "bp" + Date.now().toString(36) + i,
        winnerId: resolve(p[0]),
        loserId: resolve(p[1]),
        date: p[2] || "",
        seq: i,
      };
    }).filter(Boolean);
  }

  function loadSample() {
    els.groupName.value = "Sample Region field";
    els.level.value = "region";
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
    group = [];
    bouts = [];
    applyWrestlerPaste();
    applyBoutPaste();
    setStatus("Sample field loaded (includes a 3-cycle among Blake/Chris/Evan). Click Evaluate group.");
  }

  function run() {
    if (!group.length) {
      setStatus("Add at least one wrestler to the group.", true);
      return;
    }
    const incomplete = bouts.length === 0;
    els.incompleteFlag.hidden = !incomplete;
    // sync champ flag
    group.forEach(function (w) {
      w.isChamp = !!(w.isChamp || w.districtPlace === 1);
      if (w.priorCode && !(w.priorRank > 0)) {
        w.priorRank = codeRank()[w.priorCode] || -1;
      }
    });
    lastResult = SeedingEngine.runSeeding({
      level: els.level.value,
      wrestlers: group,
      bouts: bouts,
      codeRank: codeRank(),
      boutDataIncomplete: incomplete,
    });
    render(lastResult);
    setStatus(
      (incomplete ? "Bout data incomplete — H2H/cycles limited. " : "") +
      "Pre-seeded " + lastResult.preSeed.length +
      "; final order ready. Struck bouts: " + lastResult.struckBouts.length +
      "; movements: " + lastResult.movements.length +
      "; vote points: " + lastResult.votePoints.length + ".",
      incomplete
    );
  }

  function render(r) {
    if (els.criteriaBox) {
      els.criteriaBox.innerHTML = (r.criteriaOrder || []).map(escapeHtml).join("<br>");
    }
    renderSeedTable(els.preSeedBody, r.preSeed, null);
    renderFinalTable(els.finalSeedBody, r);
    renderStruck(r);
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
      tr.innerHTML =
        "<td>" + (i + 1) + "</td>" +
        "<td>" + escapeHtml(w.name) +
          (w.isChamp ? '<span class="tag-pill">D1</span>' : "") +
        "</td>" +
        "<td>" + escapeHtml(w.school || "") + "</td>" +
        "<td>" + (w.districtPlace != null ? w.districtPlace : "") + "</td>" +
        "<td>" + escapeHtml(w.priorCode || "—") + "</td>" +
        "<td>" + (w.priorRank > 0 ? w.priorRank : "—") + "</td>" +
        "<td>" + (w.twPoints || 0) + "</td>";
      tbody.appendChild(tr);
    });
  }

  function renderFinalTable(tbody, r) {
    tbody.innerHTML = "";
    const trailById = {};
    (r.seedTrail || []).forEach(function (t) { trailById[t.id] = t; });
    r.finalSeed.forEach(function (w, i) {
      const tr = document.createElement("tr");
      if (w.isChamp) tr.className = "champ";
      const why = (trailById[w.id] && trailById[w.id].why) || "";
      const vote = (r.votePoints || []).some(function (v) {
        return v.challengerId === w.id || v.higherId === w.id;
      });
      tr.innerHTML =
        "<td>" + (i + 1) + "</td>" +
        "<td>" + escapeHtml(w.name) +
          (w.isChamp ? '<span class="tag-pill">D1</span>' : "") +
          (vote ? '<span class="tag-pill vote">vote</span>' : "") +
        "</td>" +
        "<td>" + escapeHtml(w.school || "") + "</td>" +
        '<td class="why-cell">' + escapeHtml(why) + "</td>" +
        "<td>" + escapeHtml(w.priorCode || "—") + "</td>" +
        "<td>" + (w.twPoints || 0) + "</td>";
      tbody.appendChild(tr);
    });
  }

  function renderStruck(r) {
    const box = els.struckBox;
    box.innerHTML = "";
    if (!r.struckBouts.length) {
      box.innerHTML = '<p class="muted">No bouts eliminated.</p>';
      return;
    }
    r.struckBouts.forEach(function (b) {
      const div = document.createElement("div");
      div.className = "loop-block";
      div.innerHTML =
        '<span class="tag-pill struck">struck</span> ' +
        escapeHtml(nameOf(b.winnerId)) + " over " + escapeHtml(nameOf(b.loserId)) +
        (b.date ? " (" + escapeHtml(b.date) + ")" : "") +
        "<br><em>" + escapeHtml(b.reason || b.rule || "loop") + "</em>";
      box.appendChild(div);
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
      const names = loop.wrestlers.map(nameOf);
      const path = names.join(" → ") + " → " + names[0];
      div.innerHTML =
        "<strong>Loop " + (i + 1) + " (" + loop.wrestlers.length + ")</strong>: " +
        escapeHtml(path);
      box.appendChild(div);
    });
    if (r.sccGroups && r.sccGroups.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "SCC groups ≥3: " + r.sccGroups.map(function (g) {
        return "[" + g.map(nameOf).join(", ") + "]";
      }).join("; ");
      box.appendChild(p);
    }
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
        "<strong>Vote:</strong> " + escapeHtml(nameOf(v.challengerId)) + " vs " + escapeHtml(nameOf(v.higherId)) +
        " (" + escapeHtml(v.record) + ")<br>" +
        "<em>Stay:</em> " + escapeHtml(v.outcomeStay.map(nameOf).join(", ")) + "<br>" +
        "<em>Move challenger up:</em> " + escapeHtml(v.outcomeMove.map(nameOf).join(", ")) + "<br>" +
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
      li.textContent =
        m.type.toUpperCase() + ": " + nameOf(m.challenger) + " vs " + nameOf(m.over) +
        " — " + m.reason + " (" + m.record + ")";
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  initDom();
  loadPool();
})();
