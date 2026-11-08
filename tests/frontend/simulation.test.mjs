// Run with: node --test tests/frontend/simulation.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Playback, snapshotAt } from "../../src/tsp/simulation/frontend/engine.js";

const fixture = JSON.parse(readFileSync(new URL("../fixtures/simulation_cases.json", import.meta.url), "utf8"));
const schedule = fixture.schedule;

function near(actual, expected, label = "number") {
  assert.ok(Number.isFinite(actual), `${label} is finite`);
  assert.ok(Math.abs(actual - expected) <= 1e-9 * Math.max(1, Math.abs(expected)), `${label}: ${actual} ≈ ${expected}`);
}

function expectedSnapshot(actual, expected) {
  for (const [key, value] of Object.entries(expected)) {
    if (typeof value === "number") near(actual[key], value, key);
    else assert.deepEqual(actual[key], value, key);
  }
  assert.ok(Number.isFinite(actual.heading));
}

function fakeClock(input = schedule, checkpoint = null) {
  let now = 0;
  const player = new Playback(input, checkpoint, () => now);
  return { player, advance(milliseconds) { now = milliseconds; return player.tick(now); } };
}

for (const row of fixture.snapshots) {
  test(`shared independent snapshot ${row.state}@${row.time}`, () => {
    const frame = snapshotAt(schedule, row.time, row.state);
    expectedSnapshot(frame, row.expected);
  });
}

test("Play/Pause/Resume uses an injected monotonic clock", () => {
  const clock = fakeClock();
  clock.player.play();
  let frame = clock.advance(1500);
  near(frame.x, 1.5);
  clock.player.pause();
  frame = clock.advance(10000);
  near(frame.x, 1.5);
  assert.equal(clock.player.state, "paused");
  clock.player.play();
  frame = clock.advance(11000);
  near(frame.x, 2.5);
  assert.equal(clock.player.state, "playing");
});

test("Stop freezes position and Resume continues without teleporting", () => {
  const clock = fakeClock();
  clock.player.play();
  clock.advance(2000);
  clock.player.stop();
  const saved = clock.player.snapshot();
  assert.equal(clock.player.state, "stopped");
  assert.deepEqual(clock.advance(10000), saved);
  clock.player.play();
  near(clock.advance(11000).elapsed, 3);
});

test("2x halves playback duration including service phases", () => {
  const slow = fakeClock();
  slow.player.play();
  assert.equal(slow.advance(8000).phase, "moving");
  assert.equal(slow.player.state, "playing");
  slow.advance(16000);
  assert.equal(slow.player.state, "completed");
  const fast = fakeClock();
  fast.player.setSpeed(2);
  fast.player.play();
  const end = fast.advance(8000);
  assert.equal(fast.player.state, "completed");
  near(end.elapsed, 16);
  near(end.x, 0);
  near(end.y, 0);
});

test("Changing speed rebases the clock and preserves current position", () => {
  const clock = fakeClock();
  clock.player.play();
  const before = clock.advance(2000);
  clock.player.setSpeed(2);
  assert.deepEqual(clock.player.snapshot(), before);
  const after = clock.advance(3000);
  near(after.elapsed, 4);
  near(after.x, 3);  // now serving the first customer
  near(after.distance_traveled, 3);
});

test("Seek pauses and recomputes deliveries/events reversibly", () => {
  const clock = fakeClock();
  clock.player.play();
  clock.player.seek(13.5);
  assert.equal(clock.player.state, "paused");
  assert.equal(clock.player.snapshot().delivered_count, 2);
  clock.player.seek(4);
  const earlier = clock.player.snapshot();
  assert.equal(earlier.delivered_count, 0);
  assert.equal(earlier.phase, "delivering");
  assert.deepEqual(clock.advance(10000), earlier);
  clock.player.seek(16);
  assert.equal(clock.player.state, "completed");
  const completedIds = clock.player.snapshot().visible_events;
  assert.equal(completedIds.length, new Set(completedIds).size);
  clock.player.seek(4);
  clock.player.seek(16);
  assert.deepEqual(clock.player.snapshot().visible_events, completedIds);
});

test("Completed only after returning; Restart restores all idle state", () => {
  const clock = fakeClock();
  clock.player.play();
  const returning = clock.advance(11000);
  assert.equal(returning.delivered_count, 2);
  assert.equal(returning.phase, "moving");
  assert.equal(clock.player.state, "playing");
  clock.advance(16000);
  assert.equal(clock.player.state, "completed");
  clock.player.play();
  assert.equal(clock.player.state, "completed");
  clock.player.restart();
  const reset = clock.player.snapshot();
  assert.equal(clock.player.state, "idle");
  near(reset.x, 0);
  near(reset.y, 0);
  near(reset.elapsed, 0);
  assert.equal(reset.delivered_count, 0);
  assert.deepEqual(reset.visible_events, []);
});

test("Checkpoint restores paused and mismatched route identity resets", () => {
  const clock = fakeClock();
  clock.player.play();
  clock.advance(6500);
  clock.player.setSpeed(2);
  const checkpoint = clock.player.checkpoint();
  assert.equal(checkpoint.route_key, schedule.route_key);
  near(checkpoint.time, 6.5);
  const restored = fakeClock(schedule, checkpoint);
  assert.equal(restored.player.state, "paused");
  near(restored.player.snapshot().elapsed, 6.5);
  assert.equal(restored.player.speed, 2);
  assert.deepEqual(restored.advance(90000), restored.player.snapshot());
  const anotherRoute = { ...schedule, route_key: "another-optimization-run" };
  const other = fakeClock(anotherRoute, checkpoint);
  assert.equal(other.player.state, "idle");
  near(other.player.snapshot().elapsed, 0);
});

test("Zero-duration schedules are idle until Play and then complete safely", () => {
  const zero = structuredClone(schedule);
  zero.route_key = "zero-fixture";
  zero.total_distance = zero.total_duration = zero.service_seconds = 0;
  for (const location of zero.locations) location.x = location.y = 0;
  for (const phase of zero.phases) phase.start_time = phase.end_time = phase.distance_start = phase.distance_end = phase.heading = 0;
  for (const stop of zero.stops) stop.arrival_time = stop.delivery_time = 0;
  for (const event of zero.events) event.time = 0;
  const clock = fakeClock(zero);
  assert.equal(clock.player.state, "idle");
  assert.equal(clock.player.snapshot().delivered_count, 0);
  assert.equal(clock.player.snapshot().progress_percent, 0);
  clock.player.play();
  const frame = clock.advance(0);
  assert.equal(clock.player.state, "completed");
  assert.equal(frame.delivered_count, 2);
  assert.equal(frame.progress_percent, 100);
  for (const value of [frame.x, frame.y, frame.heading, frame.distance_traveled, frame.remaining_distance]) assert.ok(Number.isFinite(value));
});

test("Invalid speeds and times are rejected without corrupting playback", () => {
  const clock = fakeClock();
  for (const value of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) assert.throws(() => clock.player.setSpeed(value));
  for (const value of [Number.NaN, Number.POSITIVE_INFINITY]) assert.throws(() => clock.player.seek(value));
  assert.equal(clock.player.state, "idle");
  near(clock.player.snapshot().elapsed, 0);
});
