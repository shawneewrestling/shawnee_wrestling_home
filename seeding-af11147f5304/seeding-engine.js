/**
 * NJSIAA region/state seeding engine (client-side).
 * Round-robin / cycle elimination + pre-seed ordering helpers.
 * Browser and Node (unit tests) both load this file.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SeedingEngine = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** @typedef {{id:string, winnerId:string, loserId:string, date?:string, seq?:number, source?:string}} Bout */
  /** @typedef {{id:string, name:string, school?:string, districtPlace?:number|null, isChamp?:boolean, twPoints?:number, priorCode?:string|null, priorRank?:number, winsOverSeeded?:number, winsOverPrior?:number}} Wrestler */

  /**
   * Normalize bouts: ensure winner/loser ids, assign seq by date then input order.
   * @param {Bout[]} bouts
   * @returns {Bout[]}
   */
  function normalizeBouts(bouts) {
    return (bouts || []).map(function (b, i) {
      return {
        id: b.id || "b" + i,
        winnerId: String(b.winnerId),
        loserId: String(b.loserId),
        date: b.date || "",
        seq: typeof b.seq === "number" ? b.seq : i,
        source: b.source || "",
      };
    });
  }

  /**
   * Find all simple directed cycles of length >= 3 among wrestler ids
   * using only the directed edges winner -> loser (A beat B means A > B).
   * Returns cycles as arrays of wrestler ids (closing back to start not repeated).
   * @param {string[]} wrestlerIds
   * @param {Bout[]} bouts  (already filtered to this field; may include multiples)
   * @returns {string[][]}
   */
  function findCycles(wrestlerIds, bouts) {
    var idSet = {};
    wrestlerIds.forEach(function (id) {
      idSet[id] = true;
    });
    // adjacency: winner -> set of losers (presence of at least one win)
    var adj = {};
    wrestlerIds.forEach(function (id) {
      adj[id] = {};
    });
    bouts.forEach(function (b) {
      if (!idSet[b.winnerId] || !idSet[b.loserId]) return;
      if (b.winnerId === b.loserId) return;
      adj[b.winnerId][b.loserId] = true;
    });

    var cycles = [];
    var seenKey = {};

    function keyFor(cycle) {
      // canonical rotation starting at min id, direction as discovered
      var min = 0;
      for (var i = 1; i < cycle.length; i++) {
        if (cycle[i] < cycle[min]) min = i;
      }
      var rot = cycle.slice(min).concat(cycle.slice(0, min));
      return rot.join(">");
    }

    function dfs(start, node, path, pathSet) {
      var neighbors = Object.keys(adj[node] || {});
      for (var i = 0; i < neighbors.length; i++) {
        var nxt = neighbors[i];
        if (!idSet[nxt]) continue;
        if (nxt === start && path.length >= 3) {
          var cyc = path.slice();
          var k = keyFor(cyc);
          if (!seenKey[k]) {
            seenKey[k] = true;
            cycles.push(cyc);
          }
          continue;
        }
        if (pathSet[nxt]) continue;
        // only explore nodes >= start lexicographically as first to reduce dupes? keep full for correctness on overlapping
        if (path.length >= wrestlerIds.length) continue;
        path.push(nxt);
        pathSet[nxt] = true;
        dfs(start, nxt, path, pathSet);
        path.pop();
        delete pathSet[nxt];
      }
    }

    // Limit combinatorial explosion: for typical seeding fields (12–32) OK.
    wrestlerIds.forEach(function (start) {
      var path = [start];
      var pathSet = {};
      pathSet[start] = true;
      dfs(start, start, path, pathSet);
    });

    return cycles;
  }

  /**
   * Strongly connected components via Kosaraju — any bout between two wrestlers
   * in the same SCC of size >= 3 sits on some cycle. Used for the "any length"
   * grouping Jeff described; cycle listing still comes from findCycles.
   * @param {string[]} wrestlerIds
   * @param {Bout[]} bouts
   * @returns {string[][]} components with length >= 2 (pairs in mutual/cycle graph)
   */
  function stronglyConnectedGroups(wrestlerIds, bouts) {
    var idSet = {};
    wrestlerIds.forEach(function (id) {
      idSet[id] = true;
    });
    var adj = {};
    var radj = {};
    wrestlerIds.forEach(function (id) {
      adj[id] = [];
      radj[id] = [];
    });
    bouts.forEach(function (b) {
      if (!idSet[b.winnerId] || !idSet[b.loserId] || b.winnerId === b.loserId)
        return;
      adj[b.winnerId].push(b.loserId);
      radj[b.loserId].push(b.winnerId);
    });

    var order = [];
    var seen = {};
    function dfs1(u) {
      seen[u] = true;
      (adj[u] || []).forEach(function (v) {
        if (!seen[v]) dfs1(v);
      });
      order.push(u);
    }
    wrestlerIds.forEach(function (u) {
      if (!seen[u]) dfs1(u);
    });

    var compId = {};
    var comps = [];
    function dfs2(u, acc) {
      compId[u] = comps.length;
      acc.push(u);
      (radj[u] || []).forEach(function (v) {
        if (compId[v] === undefined) dfs2(v, acc);
      });
    }
    for (var i = order.length - 1; i >= 0; i--) {
      var u = order[i];
      if (compId[u] === undefined) {
        var acc = [];
        dfs2(u, acc);
        comps.push(acc);
      }
    }
    return comps.filter(function (c) {
      return c.length >= 2;
    });
  }

  /**
   * Apply NJSIAA round-robin elimination rules:
   * - Cycles of length 3+
   * - A single loss may satisfy many round robins
   * - Multiple losses to same opponent: eliminate only one
   * - Multiple results between two wrestlers that are part of a round robin:
   *   eliminate the earliest result in that pair series
   *
   * Returns { remainingBouts, struckBouts, loops }
   * struckBouts grouped conceptually by loop in `loops`.
   *
   * @param {string[]} wrestlerIds
   * @param {Bout[]} bouts
   */
  function eliminateRoundRobins(wrestlerIds, bouts) {
    var normalized = normalizeBouts(bouts).slice().sort(function (a, b) {
      // earliest first for elimination preference
      if (a.date && b.date && a.date !== b.date) return a.date < b.date ? -1 : 1;
      return a.seq - b.seq;
    });

    var cycles = findCycles(wrestlerIds, normalized);
    // Keep only cycles length >= 3
    cycles = cycles.filter(function (c) {
      return c.length >= 3;
    });

    // Pair key helper
    function pairKey(a, b) {
      return a < b ? a + "|" + b : b + "|" + a;
    }

    // For each unordered pair, list bouts chronologically
    var pairBouts = {};
    normalized.forEach(function (b) {
      var k = pairKey(b.winnerId, b.loserId);
      if (!pairBouts[k]) pairBouts[k] = [];
      pairBouts[k].push(b);
    });

    // Which pairs appear on at least one cycle of length >= 3?
    var pairOnCycle = {};
    var loops = cycles.map(function (cyc) {
      var edges = [];
      for (var i = 0; i < cyc.length; i++) {
        var a = cyc[i];
        var b = cyc[(i + 1) % cyc.length];
        // directed a->b exists in graph (a beat b)
        edges.push({ from: a, to: b, pair: pairKey(a, b) });
        pairOnCycle[pairKey(a, b)] = true;
      }
      return { wrestlers: cyc.slice(), edges: edges, struck: [] };
    });

    // For each pair on a cycle, mark exactly one bout to strike:
    // the earliest result in the series (rule ii), and only one even if
    // multiple losses to same opponent (rule i).
    var struckMeta = {}; // id -> { bout, reason, loops }
    Object.keys(pairOnCycle).forEach(function (k) {
      var list = pairBouts[k] || [];
      if (!list.length) return;
      // earliest already sorted
      var victim = list[0];
      var pairParts = k.split("|");
      var multi = list.length > 1;
      var reason =
        "Round-robin loop (3+): eliminate " +
        (multi
          ? "earliest result of this pair (only one loss per repeated pair)"
          : "this bout (pair sits on a cycle of 3+)");
      struckMeta[victim.id] = {
        bout: victim,
        reason: reason,
        pair: k,
        loopCount: 0,
        rule: multi ? "earliest_of_pair_in_loop" : "bout_on_loop",
      };
    });

    // Attach struck bouts to every loop that uses that pair; annotate loop membership
    loops.forEach(function (loop) {
      loop.edges.forEach(function (e) {
        var list = pairBouts[e.pair] || [];
        if (!list.length) return;
        var victim = list[0];
        if (struckMeta[victim.id]) {
          loop.struck.push(victim);
          struckMeta[victim.id].loopCount++;
          if (!struckMeta[victim.id].sampleLoop) {
            struckMeta[victim.id].sampleLoop = loop.wrestlers.slice();
          }
        }
      });
      // unique struck by id
      var seen = {};
      loop.struck = loop.struck.filter(function (b) {
        if (seen[b.id]) return false;
        seen[b.id] = true;
        return true;
      });
    });

    var remaining = normalized.filter(function (b) {
      return !struckMeta[b.id];
    });
    var struck = normalized
      .filter(function (b) {
        return !!struckMeta[b.id];
      })
      .map(function (b) {
        var m = struckMeta[b.id];
        var loopNote = m.sampleLoop
          ? " Loop: " + m.sampleLoop.join(" → ") + " → " + m.sampleLoop[0] + "."
          : "";
        return Object.assign({}, b, {
          eliminated: true,
          rule: m.rule,
          reason: m.reason + loopNote,
          pair: m.pair,
        });
      });

    return {
      remainingBouts: remaining,
      struckBouts: struck,
      loops: loops,
      cycles: cycles,
      sccGroups: stronglyConnectedGroups(wrestlerIds, normalized).filter(function (c) {
        return c.length >= 3;
      }),
    };
  }

  /**
   * Head-to-head record between two wrestlers using remaining (non-struck) bouts.
   * Returns { aWins, bWins, laterWinnerId|null, bouts }
   */
  function headToHead(aId, bId, remainingBouts) {
    var aWins = 0;
    var bWins = 0;
    var relevant = remainingBouts
      .filter(function (b) {
        return (
          (b.winnerId === aId && b.loserId === bId) ||
          (b.winnerId === bId && b.loserId === aId)
        );
      })
      .slice()
      .sort(function (x, y) {
        if (x.date && y.date && x.date !== y.date)
          return x.date < y.date ? -1 : 1;
        return x.seq - y.seq;
      });
    relevant.forEach(function (b) {
      if (b.winnerId === aId) aWins++;
      else bWins++;
    });
    var laterWinnerId = relevant.length
      ? relevant[relevant.length - 1].winnerId
      : null;
    return { aWins: aWins, bWins: bWins, laterWinnerId: laterWinnerId, bouts: relevant };
  }

  /**
   * Apply H2H movement: start with best pre-seed, work down; best challenge first.
   * Majority of victories moves challenger ahead; split -> later win.
   * Vote cases (extenuating / true ties with no H2H clarity) are flagged —
   * both outcomes returned.
   *
   * @param {Wrestler[]} preSeeded  already sorted best->worst pre-seed
   * @param {Bout[]} remainingBouts
   * @returns {{ order: Wrestler[], movements: any[], votePoints: any[] }}
   */
  function applyHeadToHeadMovement(preSeeded, remainingBouts) {
    var order = preSeeded.slice();
    var movements = [];
    var votePoints = [];

    // Process from best seed downward; for each higher seed, consider challenges
    // from lower seeds who have H2H against them, best (highest) challenger first.
    var i = 0;
    while (i < order.length) {
      var higher = order[i];
      var challenges = [];
      for (var j = i + 1; j < order.length; j++) {
        var lower = order[j];
        var h2h = headToHead(higher.id, lower.id, remainingBouts);
        if (h2h.aWins + h2h.bWins === 0) continue;
        challenges.push({ idx: j, wrestler: lower, h2h: h2h });
      }
      // best challenge first = closest to top = lowest idx among challengers
      challenges.sort(function (a, b) {
        return a.idx - b.idx;
      });

      var moved = false;
      for (var c = 0; c < challenges.length; c++) {
        var ch = challenges[c];
        var h = ch.h2h;
        var lowerWins = h.bWins;
        var higherWins = h.aWins;
        if (lowerWins > higherWins) {
          // challenger moves ahead of higher
          order.splice(ch.idx, 1);
          order.splice(i, 0, ch.wrestler);
          movements.push({
            type: "move",
            challenger: ch.wrestler.id,
            over: higher.id,
            reason: "majority",
            record: lowerWins + "-" + higherWins,
          });
          moved = true;
          break; // restart from this position
        } else if (lowerWins === higherWins && h.laterWinnerId === ch.wrestler.id) {
          order.splice(ch.idx, 1);
          order.splice(i, 0, ch.wrestler);
          movements.push({
            type: "move",
            challenger: ch.wrestler.id,
            over: higher.id,
            reason: "later_win_split",
            record: lowerWins + "-" + higherWins,
          });
          moved = true;
          break;
        } else if (lowerWins === higherWins && h.laterWinnerId === higher.id) {
          movements.push({
            type: "hold",
            challenger: ch.wrestler.id,
            over: higher.id,
            reason: "later_win_split_holds",
            record: lowerWins + "-" + higherWins,
          });
        } else if (lowerWins < higherWins) {
          movements.push({
            type: "hold",
            challenger: ch.wrestler.id,
            over: higher.id,
            reason: "majority_holds",
            record: lowerWins + "-" + higherWins,
          });
        } else {
          // no decisive H2H — flag vote; show both outcomes
          var alt = order.slice();
          // outcome A: challenger moves ahead
          alt.splice(ch.idx, 1);
          alt.splice(i, 0, ch.wrestler);
          votePoints.push({
            higherId: higher.id,
            challengerId: ch.wrestler.id,
            record: lowerWins + "-" + higherWins,
            outcomeStay: order.map(function (w) {
              return w.id;
            }),
            outcomeMove: alt.map(function (w) {
              return w.id;
            }),
            note: "Extenuating / vote — both outcomes shown; default keeps pre-seed",
          });
        }
      }
      if (moved) {
        // don't increment i; re-evaluate new occupant
        continue;
      }
      i++;
    }

    return { order: order, movements: movements, votePoints: votePoints };
  }

  /**
   * Region rule: force district champs into top 8 (place at 8, or 7&8, etc.).
   * @param {Wrestler[]} seeded
   * @returns {Wrestler[]}
   */
  function forceChampsTop8(seeded) {
    var list = seeded.slice();
    var champsOutside = [];
    for (var i = 8; i < list.length; i++) {
      if (list[i].isChamp || list[i].districtPlace === 1) {
        champsOutside.push(list[i]);
      }
    }
    if (!champsOutside.length) return list;
    // Remove them from current positions (from end so indices stable)
    champsOutside.forEach(function (ch) {
      var idx = list.indexOf(ch);
      if (idx >= 0) list.splice(idx, 1);
    });
    // Place into slots 8,7,6... (1-based seeds) i.e. indices 7,6,5...
    // "placed at the 8th seed" — if multiple, use 7th and 8th, etc.
    var slots = [];
    for (var s = 0; s < champsOutside.length; s++) {
      slots.push(7 - s); // 7,6,5...
    }
    slots.reverse(); // fill from highest seed number downward: first champ to lowest reserved slot
    // Actually: first displaced champ goes to 8, second to 7, etc.
    for (var k = 0; k < champsOutside.length; k++) {
      var insertAt = 7 - k;
      if (insertAt < 0) insertAt = 0;
      list.splice(insertAt, 0, champsOutside[k]);
    }
    return list;
  }

  /**
   * Pair the eight 2nd/3rd place finishers: best vs lowest, etc.
   * Returns array of { higherSeed, lowerSeed } among non-champs in seeds 1-12.
   * @param {Wrestler[]} seeded  after champ top-8 enforcement
   */
  function pairSecondThird(seeded) {
    var nonChamps = seeded.filter(function (w) {
      return !(w.isChamp || w.districtPlace === 1);
    });
    // Among the field, the 2nd/3rd are the non-champs; take up to 8
    var pool = nonChamps.slice(0, 8);
    var pairs = [];
    var n = pool.length;
    for (var i = 0; i < Math.floor(n / 2); i++) {
      pairs.push({
        higher: pool[i],
        lower: pool[n - 1 - i],
        label: "best/lowest 2nd-3rd pairing",
      });
    }
    return pairs;
  }

  /**
   * Compare own-merit codes using code_rank map (higher rank number = better
   * in our data: S1 Place = 125). "This level or better":
   * region level => region place or state; state level => state only.
   */
  function meritRank(code, codeRank, level) {
    if (!code) return -1;
    var r = codeRank[code];
    if (typeof r !== "number") return -1;
    var isState = /^S\d|swb/i.test(code);
    var isRegion = /^R\d|RWB|2v3/i.test(code);
    if (level === "state") {
      return isState ? r : -1; // only state-level merit counts at state
    }
    // region: region or better (state)
    if (isState || isRegion) return r;
    return -1;
  }

  /**
   * Sort wrestlers by pre-seed criteria (before H2H):
   * 1) own merit at this level or better
   * 2) wins over seeded wrestlers (desc)
   * 3) wins over prior participants (desc)
   * 4) TW points (desc)
   */
  function preSeedSort(wrestlers, codeRank, level) {
    return wrestlers.slice().sort(function (a, b) {
      var ma = typeof a.priorRank === "number" ? a.priorRank : meritRank(a.priorCode, codeRank, level);
      var mb = typeof b.priorRank === "number" ? b.priorRank : meritRank(b.priorCode, codeRank, level);
      if (mb !== ma) return mb - ma;
      var sa = a.winsOverSeeded || 0;
      var sb = b.winsOverSeeded || 0;
      if (sb !== sa) return sb - sa;
      var pa = a.winsOverPrior || 0;
      var pb = b.winsOverPrior || 0;
      if (pb !== pa) return pb - pa;
      return (b.twPoints || 0) - (a.twPoints || 0);
    });
  }

  /**
   * Full pipeline.
   */
  function runSeeding(opts) {
    var level = opts.level || "region"; // 'region' | 'state'
    var wrestlers = (opts.wrestlers || []).map(function (w, i) {
      return Object.assign(
        {
          id: w.id || "w" + i,
          name: w.name || "Wrestler " + i,
          school: w.school || "",
          districtPlace: w.districtPlace != null ? w.districtPlace : null,
          isChamp: !!(w.isChamp || w.districtPlace === 1),
          twPoints: w.twPoints || 0,
          priorCode: w.priorCode || null,
          priorRank: w.priorRank,
          winsOverSeeded: w.winsOverSeeded || 0,
          winsOverPrior: w.winsOverPrior || 0,
        },
        w
      );
    });
    var bouts = normalizeBouts(opts.bouts || []);
    var codeRank = opts.codeRank || {};
    var boutDataIncomplete = !!opts.boutDataIncomplete || bouts.length === 0;

    var ids = wrestlers.map(function (w) {
      return w.id;
    });
    var elim = eliminateRoundRobins(ids, bouts);
    var pre = preSeedSort(wrestlers, codeRank, level);
    var h2h = applyHeadToHeadMovement(pre, elim.remainingBouts);
    var after = h2h.order;
    var pairs = [];
    if (level === "region") {
      after = forceChampsTop8(after);
      pairs = pairSecondThird(after);
    }

    // Annotate final order with why each wrestler sits where (pre-seed + movements)
    var preIndex = {};
    pre.forEach(function (w, i) {
      preIndex[w.id] = i;
    });
    var moveByChallenger = {};
    h2h.movements.forEach(function (m) {
      if (m.type === "move") moveByChallenger[m.challenger] = m;
    });
    var nameById = {};
    wrestlers.forEach(function (w) {
      nameById[w.id] = w.name || w.id;
    });
    var seedTrail = after.map(function (w, i) {
      var prePos = preIndex[w.id];
      var m = moveByChallenger[w.id];
      var why;
      if (m) {
        why =
          "Moved ahead of " +
          (nameById[m.over] || m.over) +
          " via H2H (" +
          m.reason +
          ", " +
          m.record +
          "); pre-seed was #" +
          (prePos + 1);
      } else if (typeof prePos === "number" && prePos === i) {
        why = "Holds pre-seed #" + (i + 1) + " (merit/TW order; no H2H challenge prevailed)";
      } else if (typeof prePos === "number") {
        why =
          "Pre-seed #" +
          (prePos + 1) +
          " → final #" +
          (i + 1) +
          " after H2H reshuffle / champ top-8 rule";
      } else {
        why = "Final #" + (i + 1);
      }
      return { id: w.id, final: i + 1, preSeed: typeof prePos === "number" ? prePos + 1 : null, why: why };
    });

    return {
      preSeed: pre,
      finalSeed: after,
      movements: h2h.movements,
      votePoints: h2h.votePoints,
      loops: elim.loops,
      struckBouts: elim.struckBouts,
      remainingBouts: elim.remainingBouts,
      sccGroups: elim.sccGroups || [],
      pairs: pairs,
      boutDataIncomplete: boutDataIncomplete,
      level: level,
      seedTrail: seedTrail,
      criteriaOrder: [
        "1. Own merit in previous tournament (this level or better)",
        "2. Wins over seeded wrestlers this season (distinct preferred)",
        "3. Wins over prior-year participants this season",
        "4. Trackwrestling points tiebreak",
        "5. Eliminate round-robin loops of 3+ (one bout per pair; earliest if series)",
        "6. H2H from best pre-seed down: majority wins; split → later win",
      ],
    };
  }


  /**
   * Seasons strictly before `season`, newest first, up to `count` (default 4).
   * "2025-26" → ["2024-25","2023-24","2022-23","2021-22"]
   */
  function priorSeasonWindow(season, count) {
    count = typeof count === "number" ? count : 4;
    var m = String(season || "").match(/^(\d{4})-(\d{2})$/);
    if (!m) return [];
    var start = parseInt(m[1], 10);
    var out = [];
    for (var i = 1; i <= count; i++) {
      var y = start - i;
      var yy = String((y + 1) % 100).padStart(2, "0");
      out.push(y + "-" + yy);
    }
    return out;
  }

  /**
   * Best prior-tournament code within the window (highest code_rank).
   * seasonsMap: { "2024-25": {code,weight,...} } or compact [code,weight,grade,school]
   */
  function bestPriorInWindow(seasonsMap, season, codeRank, windowSize) {
    var window = priorSeasonWindow(season, windowSize || 4);
    var bestCode = null;
    var bestRank = -1;
    var bestSeason = null;
    var finishes = [];
    window.forEach(function (s) {
      var info = seasonsMap && seasonsMap[s];
      if (!info) return;
      var code = Array.isArray(info) ? info[0] : info.code;
      if (!code) return;
      var rank = typeof codeRank[code] === "number" ? codeRank[code] : -1;
      finishes.push({ season: s, code: code, rank: rank });
      if (rank > bestRank) {
        bestRank = rank;
        bestCode = code;
        bestSeason = s;
      }
    });
    return {
      priorCode: bestCode,
      priorRank: bestRank,
      priorSeason: bestSeason,
      window: window,
      finishes: finishes,
    };
  }

  return {
    normalizeBouts: normalizeBouts,
    findCycles: findCycles,
    stronglyConnectedGroups: stronglyConnectedGroups,
    eliminateRoundRobins: eliminateRoundRobins,
    headToHead: headToHead,
    applyHeadToHeadMovement: applyHeadToHeadMovement,
    forceChampsTop8: forceChampsTop8,
    pairSecondThird: pairSecondThird,
    meritRank: meritRank,
    preSeedSort: preSeedSort,
    runSeeding: runSeeding,
    priorSeasonWindow: priorSeasonWindow,
    bestPriorInWindow: bestPriorInWindow,
  };
});
