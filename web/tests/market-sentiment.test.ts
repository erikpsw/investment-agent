import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  formatSentimentDelta,
  gaugeArcAngle,
  getRegimeMeta,
  resonanceBadgeMeta,
} from "../src/lib/sentiment";

test("maps 0-100 sentiment score to -90..+90 gauge angles", () => {
  assert.equal(gaugeArcAngle(0), -90);
  assert.equal(gaugeArcAngle(50), 0);
  assert.equal(gaugeArcAngle(100), 90);
  assert.equal(gaugeArcAngle(-15), -90);
  assert.equal(gaugeArcAngle(150), 90);
});

test("resolves regime metadata with fallback to neutral", () => {
  assert.equal(getRegimeMeta("extreme_fear").label, "极度恐慌");
  assert.equal(getRegimeMeta("extreme_greed").label, "极度贪婪");
  assert.equal(getRegimeMeta("unknown").label, "中性震荡");
});

test("formats signed sentiment deltas and missing values", () => {
  assert.equal(formatSentimentDelta(3.45), "+3.5");
  assert.equal(formatSentimentDelta(-2.1), "-2.1");
  assert.equal(formatSentimentDelta(null), "--");
});

test("returns expected tone for resonance signals", () => {
  assert.equal(resonanceBadgeMeta("bottom").tone, "bottom");
  assert.equal(resonanceBadgeMeta("right_turn").tone, "right_turn");
  assert.equal(resonanceBadgeMeta("top").tone, "top");
  assert.equal(resonanceBadgeMeta("watch_bottom").tone, "watch");
  assert.equal(resonanceBadgeMeta("none").tone, "neutral");
});

test("dashboard page mounts MarketSentimentPanel", async () => {
  const page = await readFile(
    new URL("../src/app/dashboard/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(page, /MarketSentimentPanel/);
});
