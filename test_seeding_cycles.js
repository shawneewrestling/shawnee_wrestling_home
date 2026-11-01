/**
 * Unit tests for NJSIAA round-robin / cycle elimination (seeding-engine.js).
 * Run: node test_seeding_cycles.js
 */
const path = require("path");
const assert = require("assert");
const fs = require("fs");

// Discover seeding-* dir
const repoRoot = __dirname;
const seedingDir = fs.readdirSync(repoRoot).find((d) => /^seeding-[0-9a-f]+$/.test(d));
assert.ok(seedingDir, "seeding-* directory must exist");
const Eng = require(path.join(repoRoot, seedingDir, "seeding-engine.js"));

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
    console.log("ok -", name);
  } catch (e) {
    console.error("FAIL -", name);
    console.error(e && e.stack ? e.stack : e);
    process.exitCode = 1;
  }
}

test("3-cycle A>B>C>A strikes one bout per pair (earliest)", () => {
  const ids = ["A", "B", "C"];
  const bouts = [
    { id: "1", winnerId: "A", loserId: "B", date: "2025-12-01", seq: 0 },
    { id: "2", winnerId: "B", loserId: "C", date: "2025-12-02", seq: 1 },
    { id: "3", winnerId: "C", loserId: "A", date: "2025-12-03", seq: 2 },
  ];
  const r = Eng.eliminateRoundRobins(ids, bouts);
  assert.strictEqual(r.cycles.length >= 1, true);
  assert.ok(r.cycles.some((c) => c.length === 3));
  // one bout per pair on cycle => all 3 struck (each pair has one bout)
  assert.strictEqual(r.struckBouts.length, 3);
  assert.strictEqual(r.remainingBouts.length, 0);
  assert.ok(r.loops.length >= 1);
  assert.ok(r.loops[0].struck.length >= 1);
});

test("4-cycle A>B>C>D>A strikes earliest per pair", () => {
  const ids = ["A", "B", "C", "D"];
  const bouts = [
    { id: "ab", winnerId: "A", loserId: "B", date: "2025-01-01", seq: 0 },
    { id: "bc", winnerId: "B", loserId: "C", date: "2025-01-02", seq: 1 },
    { id: "cd", winnerId: "C", loserId: "D", date: "2025-01-03", seq: 2 },
    { id: "da", winnerId: "D", loserId: "A", date: "2025-01-04", seq: 3 },
  ];
  const r = Eng.eliminateRoundRobins(ids, bouts);
  assert.ok(r.cycles.some((c) => c.length === 4));
  assert.strictEqual(r.struckBouts.length, 4);
});

test("multiple losses to same opponent: only one eliminated", () => {
  // A>B, A>B (again), B>C, C>A  => cycle A-B-C. Pair A-B has two bouts; only earliest struck.
  const ids = ["A", "B", "C"];
  const bouts = [
    { id: "ab1", winnerId: "A", loserId: "B", date: "2025-01-01", seq: 0 },
    { id: "ab2", winnerId: "A", loserId: "B", date: "2025-02-01", seq: 1 },
    { id: "bc", winnerId: "B", loserId: "C", date: "2025-01-15", seq: 2 },
    { id: "ca", winnerId: "C", loserId: "A", date: "2025-01-20", seq: 3 },
  ];
  const r = Eng.eliminateRoundRobins(ids, bouts);
  const struckIds = r.struckBouts.map((b) => b.id).sort();
  assert.ok(struckIds.includes("ab1"), "earliest A>B struck");
  assert.ok(!struckIds.includes("ab2"), "later A>B NOT struck");
  assert.ok(struckIds.includes("bc"));
  assert.ok(struckIds.includes("ca"));
  // remaining should include ab2
  assert.ok(r.remainingBouts.some((b) => b.id === "ab2"));
});

test("A>B>A>B series in a larger robin: earliest of the pair eliminated", () => {
  // A>B, B>A, B>C, C>A — pairs on cycle; for A-B eliminate earliest (A>B)
  const ids = ["A", "B", "C"];
  const bouts = [
    { id: "ab", winnerId: "A", loserId: "B", date: "2025-01-01", seq: 0 },
    { id: "ba", winnerId: "B", loserId: "A", date: "2025-02-01", seq: 1 },
    { id: "bc", winnerId: "B", loserId: "C", date: "2025-01-10", seq: 2 },
    { id: "ca", winnerId: "C", loserId: "A", date: "2025-01-12", seq: 3 },
  ];
  const r = Eng.eliminateRoundRobins(ids, bouts);
  const struckIds = r.struckBouts.map((b) => b.id);
  assert.ok(struckIds.includes("ab"), "earliest A-B result struck");
  assert.ok(!struckIds.includes("ba"), "later A-B result kept");
});

test("no cycle: nothing struck", () => {
  const ids = ["A", "B", "C"];
  const bouts = [
    { id: "1", winnerId: "A", loserId: "B", seq: 0 },
    { id: "2", winnerId: "A", loserId: "C", seq: 1 },
    { id: "3", winnerId: "B", loserId: "C", seq: 2 },
  ];
  const r = Eng.eliminateRoundRobins(ids, bouts);
  assert.strictEqual(r.struckBouts.length, 0);
  assert.strictEqual(r.remainingBouts.length, 3);
});

test("H2H majority moves challenger ahead", () => {
  const pre = [
    { id: "H", name: "Higher" },
    { id: "L", name: "Lower" },
  ];
  const bouts = [
    { id: "1", winnerId: "L", loserId: "H", date: "2025-01-01", seq: 0 },
  ];
  const r = Eng.applyHeadToHeadMovement(pre, bouts);
  assert.strictEqual(r.order[0].id, "L");
  assert.ok(r.movements.some((m) => m.type === "move" && m.reason === "majority"));
});

test("H2H split goes to later win", () => {
  const pre = [
    { id: "H", name: "Higher" },
    { id: "L", name: "Lower" },
  ];
  const bouts = [
    { id: "1", winnerId: "H", loserId: "L", date: "2025-01-01", seq: 0 },
    { id: "2", winnerId: "L", loserId: "H", date: "2025-02-01", seq: 1 },
  ];
  const r = Eng.applyHeadToHeadMovement(pre, bouts);
  assert.strictEqual(r.order[0].id, "L");
  assert.ok(r.movements.some((m) => m.reason === "later_win_split"));
});

test("forceChampsTop8 pulls champ from seed 9 to 8", () => {
  const list = [];
  for (let i = 1; i <= 12; i++) {
    list.push({
      id: "w" + i,
      name: "W" + i,
      isChamp: i === 10,
      districtPlace: i === 10 ? 1 : 2,
    });
  }
  const out = Eng.forceChampsTop8(list);
  const idx = out.findIndex((w) => w.id === "w10");
  assert.ok(idx >= 0 && idx <= 7, "champ should be in top 8, got idx " + idx);
});

test("long cycle 6 wrestlers detected and struck", () => {
  const ids = ["A", "B", "C", "D", "E", "F"];
  const edges = [
    ["A", "B"],
    ["B", "C"],
    ["C", "D"],
    ["D", "E"],
    ["E", "F"],
    ["F", "A"],
  ];
  const bouts = edges.map((e, i) => ({
    id: "e" + i,
    winnerId: e[0],
    loserId: e[1],
    date: "2025-03-0" + (i + 1),
    seq: i,
  }));
  const r = Eng.eliminateRoundRobins(ids, bouts);
  assert.ok(r.cycles.some((c) => c.length === 6));
  assert.strictEqual(r.struckBouts.length, 6);
});

console.log("\n" + passed + " tests passed");
