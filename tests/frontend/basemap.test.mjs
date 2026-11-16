import test from "node:test";
import assert from "node:assert/strict";
import {BasemapController, BASEMAPS} from "../../src/tsp/simulation/frontend/basemap.js";

function harness() {
  const created = [], removed = [];
  const map = {on() {}, removeLayer(layer) { removed.push(layer); }, getContainer() { return {hidden: false}; }};
  const L = {tileLayer(url, options) {
    const listeners = new Map();
    const layer = {
      url, options,
      on(event, action) { listeners.set(event, action); return this; },
      off() { listeners.clear(); return this; },
      addTo() { return this; },
      fire(event) { listeners.get(event)?.(); },
    };
    created.push(layer); return layer;
  }};
  const status = {dataset: {}, textContent: ""};
  const notice = {hidden: true, textContent: ""};
  let now = 1000;
  const controller = new BasemapController(map, L, {status, notice}, () => now);
  return {controller, created, removed, status, notice, advance(ms) { now += ms; }};
}

test("all viewport tiles failing changes to the free OSM fallback once", () => {
  const h = harness();
  const first = h.created[0];
  first.fire("loading");
  for (let i = 0; i < 12; i++) first.fire("tileerror");
  assert.equal(h.created.length, 1, "no request loop per failed tile");
  first.fire("load");
  assert.equal(h.created.length, 2);
  assert.equal(h.controller.provider, "osm_de");
  const fallback = h.created[1];
  fallback.fire("loading"); fallback.fire("tileerror"); fallback.fire("load");
  assert.equal(h.created.length, 2, "both sources failing never loops");
  assert.equal(h.status.dataset.state, "error");
  assert.equal(h.notice.hidden, false);
  assert.match(h.notice.textContent, /Internet\/DNS/);
});

test("recovered tiles clear the warning and stale provider events cannot overwrite state", () => {
  const h = harness();
  const first = h.created[0];
  first.fire("tileerror"); first.fire("load");
  const fallback = h.created[1];
  fallback.fire("tileload"); fallback.fire("load");
  assert.equal(h.status.dataset.state, "ready");
  assert.match(h.status.textContent, /OSM DE do nguồn chính lỗi/);
  assert.equal(h.notice.hidden, true);
  first.fire("tileerror"); first.fire("load");
  assert.equal(h.status.dataset.state, "ready");
  assert.equal(h.created.length, 2);
});

test("partial loading stays on its source and succeeds after one manual retry", () => {
  const h = harness();
  const first = h.created[0];
  first.fire("tileload"); first.fire("tileerror"); first.fire("load");
  assert.equal(h.controller.provider, "osm");
  assert.equal(h.status.dataset.state, "partial");
  h.controller.manual("osm");
  h.controller.manual("osm");
  assert.equal(h.created.length, 2, "rapid manual retry is bounded");
  const retry = h.created[1];
  retry.fire("tileload"); retry.fire("load");
  assert.equal(h.status.dataset.state, "ready");
  assert.equal(h.notice.hidden, true);
  h.advance(2000); h.controller.manual("osm_de");
  assert.equal(h.controller.provider, "osm_de");
  assert.equal(h.created.length, 3);
});

test("tile options retain attribution, browser caching, referrer and viewport limits", () => {
  const h = harness();
  for (const source of Object.keys(BASEMAPS)) {
    h.advance(2000); h.controller.manual(source);
    const layer = h.created.at(-1);
    assert.ok(layer.url.startsWith("https://tile.openstreetmap."));
    assert.ok(!layer.url.includes("key="));
    assert.match(layer.options.attribution, /openstreetmap.org\/copyright/);
    assert.equal(layer.options.referrerPolicy, "strict-origin-when-cross-origin");
    assert.equal(layer.options.keepBuffer, 0);
    assert.equal(layer.options.updateWhenIdle, true);
    assert.equal(layer.options.updateWhenZooming, false);
  }
  assert.throws(() => h.controller.manual("unknown"), /Unknown/);
});
