/** Run real frontend handlers against a DOM with deterministic animation time.
 * This verifies behavior and messaging, not browser layout or measured FPS.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {JSDOM} from "jsdom";

const frontend = new URL("../../src/tsp/simulation/frontend/", import.meta.url);
const html = readFileSync(new URL("index.html", frontend), "utf8");
const fixture = JSON.parse(readFileSync(new URL("../fixtures/simulation_cases.json", import.meta.url), "utf8")).schedule;
let counter = 0;

async function mount({checkpoint = null, local = null, schedule = fixture} = {}) {
  const dom = new JSDOM(html, {url: "http://localhost:8501/component/simulation/index.html", pretendToBeVisual: true});
  const window = dom.window;
  const messages = [];
  const callbacks = new Map();
  let time = 0, nextId = 0;
  const originals = new Map();
  const globals = {
    window, document: window.document, sessionStorage: window.sessionStorage,
    performance: {now: () => time},
    requestAnimationFrame: callback => { callbacks.set(++nextId, callback); return nextId; },
    cancelAnimationFrame: id => callbacks.delete(id),
    ResizeObserver: class {observe() {} disconnect() {}},
  };
  for (const [key, value] of Object.entries(globals)) {
    originals.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, {value, writable: true, configurable: true});
  }
  window.postMessage = message => messages.push(message);
  const map = window.document.getElementById("map");
  map.getBoundingClientRect = () => ({left: 0, top: 0, width: 900, height: 500});
  let captures = 0;
  map.setPointerCapture = () => { captures += 1; };
  if (local) window.sessionStorage.setItem("tsp.delivery.latest-checkpoint.v1", JSON.stringify(local));
  await import(new URL(`app.js?domtest=${++counter}`, frontend));
  function render(input, saved = null) {
    window.dispatchEvent(new window.MessageEvent("message", {source: window,
      data: {type: "streamlit:render", args: {schedule: input, checkpoint: saved}}}));
  }
  render(schedule, checkpoint);
  const byId = id => window.document.getElementById(id);
  return {
    byId, window, messages, callbacks, render,
    captures: () => captures,
    advance(ms) {
      time = ms;
      const pending = [...callbacks.values()]; callbacks.clear();
      for (const callback of pending) callback(time);
    },
    latest: () => messages.filter(m => m.type === "streamlit:setComponentValue").at(-1)?.value,
    input(id, value, type = "change") {
      byId(id).value = String(value);
      byId(id).dispatchEvent(new window.Event(type, {bubbles: true}));
    },
    close() {
      window.dispatchEvent(new window.Event("pagehide"));
      dom.window.close();
      for (const [key, descriptor] of originals) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    },
  };
}

test("actual bridge, van, controls, events, seek and completion share a clock", async () => {
  const app = await mount();
  try {
    assert.ok(app.messages.some(m => m.type === "streamlit:componentReady" && m.apiVersion === 1));
    assert.equal(app.byId("workspace").hidden, false);
    assert.equal(app.byId("vehicle-status").textContent, "Idle");
    assert.equal(app.byId("markers").children.length, 3);
    assert.ok(app.byId("van-body").querySelector("path"));
    app.byId("play").click();
    assert.equal(app.latest().state, "playing");
    assert.equal(app.callbacks.size, 1);
    app.advance(1500);
    assert.equal(app.byId("distance-traveled").textContent, "1.50");
    assert.match(app.byId("position").textContent, /x 1.50/);
    app.byId("pause").click();
    assert.equal(app.latest().state, "paused");
    assert.equal(app.callbacks.size, 0);
    app.advance(10000);
    assert.equal(app.byId("distance-traveled").textContent, "1.50");
    app.byId("play").click();
    app.advance(11500); // resumes from 1.5 sim seconds, arrives at customer A
    assert.equal(app.byId("vehicle-status").textContent, "Delivering");
    assert.equal(app.byId("delivered-count").textContent, "0 / 2");
    app.input("speed", 2);
    assert.equal(app.latest().time, 3);
    app.advance(12500); // 2 sim seconds of service
    assert.equal(app.byId("delivered-count").textContent, "1 / 2");
    app.byId("stop").click();
    assert.equal(app.latest().state, "stopped");
    const atStop = app.byId("position").textContent;
    app.advance(15000);
    assert.equal(app.byId("position").textContent, atStop);
    app.input("seek", 437.5, "input"); // input[type=range] step rounds normally; cursor is ~7s
    app.input("seek", app.byId("seek").value);
    assert.equal(app.latest().state, "paused");
    assert.match(app.byId("van-body").getAttribute("transform"), /rotate\(-90\)/);
    app.input("seek", 1000, "input"); app.input("seek", 1000);
    assert.equal(app.latest().state, "completed");
    assert.equal(app.byId("distance-traveled").textContent, "12.00");
    assert.equal(app.byId("distance-remaining").textContent, "0.00");
    assert.equal(app.byId("complete-banner").hidden, false);
    assert.equal(app.byId("timeline").children.length, fixture.events.length);
    app.input("seek", 250, "input"); app.input("seek", 250);
    assert.equal(app.byId("delivered-count").textContent, "0 / 2");
    assert.equal(app.byId("timeline").children.length, 3);
    app.input("seek", 1000, "input"); app.input("seek", 1000);
    assert.equal(app.byId("timeline").children.length, fixture.events.length);
    app.byId("restart").click();
    assert.equal(app.latest().state, "idle");
    assert.equal(app.byId("delivered-count").textContent, "0 / 2");
    assert.equal(app.byId("event-count").textContent, "0 events");
  } finally { app.close(); }
});

test("echo keeps one animation, new route resets, labels are safe, markers remain clickable", async () => {
  const schedule = structuredClone(fixture);
  schedule.locations[0].name = '<img src=x onerror="alert(1)">';
  const app = await mount({schedule});
  try {
    app.byId("play").click(); app.advance(2000);
    app.render(schedule, app.latest());
    assert.equal(app.byId("distance-traveled").textContent, "2.00");
    assert.equal(app.callbacks.size, 1);
    app.byId("markers").children[0].dispatchEvent(new app.window.Event("click", {bubbles: true}));
    assert.equal(app.byId("selected-name").textContent, schedule.locations[0].name);
    assert.equal(app.byId("selected-name").querySelector("img"), null);
    app.byId("manifest").children[2].click();
    assert.equal(app.byId("selected-name").textContent, schedule.locations[2].name);
    const map = app.byId("map");
    map.dispatchEvent(new app.window.MouseEvent("pointerdown", {bubbles: true, button: 0, clientX: 20, clientY: 20}));
    assert.equal(app.captures(), 0, "marker presses are not retargeted by premature pointer capture");
    map.dispatchEvent(new app.window.MouseEvent("pointermove", {bubbles: true, clientX: 40, clientY: 50}));
    assert.equal(app.captures(), 1);
    assert.notEqual(map.getAttribute("viewBox"), "0 0 900 500");
    app.byId("fit").click();
    assert.equal(map.getAttribute("viewBox"), "0 0 900 500");
    const changed = {...schedule, route_key: "different-result", algorithm: "Another algorithm"};
    app.render(changed, app.latest());
    assert.equal(app.byId("vehicle-status").textContent, "Idle");
    assert.equal(app.byId("distance-traveled").textContent, "0.00");
    assert.equal(app.callbacks.size, 0);
  } finally { app.close(); }
});

test("a remount restores the freshest stored cursor paused and hidden tab freezes playback", async () => {
  const local = {route_key: fixture.route_key, time: 7, speed: 2, state: "playing", started: true, sequence: 2};
  const app = await mount({local, checkpoint: {...local, time: 1}});
  try {
    assert.equal(app.byId("vehicle-status").textContent, "Paused");
    assert.equal(app.byId("distance-traveled").textContent, "5.00");
    app.byId("play").click();
    app.advance(1000);
    Object.defineProperty(app.window.document, "hidden", {configurable: true, value: true});
    app.window.document.dispatchEvent(new app.window.Event("visibilitychange"));
    assert.equal(app.latest().state, "paused");
    assert.equal(app.callbacks.size, 0);
    const count = app.messages.length;
    app.advance(5000);
    assert.equal(app.messages.length, count);
  } finally { app.close(); }
});
