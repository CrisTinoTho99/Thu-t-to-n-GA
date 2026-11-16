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

async function mount({checkpoint = null, local = null, schedule = fixture, editor = null} = {}) {
  const dom = new JSDOM(html, {url: "http://localhost:8501/component/simulation/index.html", pretendToBeVisual: true, runScripts: "outside-only"});
  const window = dom.window;
  let leafletMap = null;
  if (editor || schedule.coordinate_mode === "geographic") {
    window.SVGSVGElement.prototype.createSVGRect = () => ({});
    const container = window.document.getElementById("leaflet-map");
    Object.defineProperty(container, "clientWidth", {value: 900});
    Object.defineProperty(container, "clientHeight", {value: 500});
    container.getBoundingClientRect = () => ({left: 0, top: 0, width: 900, height: 500});
    window.eval(readFileSync(new URL("vendor/leaflet/leaflet.js", frontend), "utf8"));
    const createMap = window.L.map;
    window.L.map = (...args) => { leafletMap = createMap(...args); return leafletMap; };
  }
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
  function renderEditor(input) {
    window.dispatchEvent(new window.MessageEvent("message", {source: window,
      data: {type: "streamlit:render", args: {editor: input}}}));
  }
  if (editor) renderEditor(editor); else render(schedule, checkpoint);
  const byId = id => window.document.getElementById(id);
  return {
    byId, window, messages, callbacks, render, renderEditor, leaflet: () => leafletMap,
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

test("browser history restoration reconnects playback without duplicate loops", async () => {
  const app = await mount();
  try {
    app.byId("play").click();
    app.advance(1000);
    for (const [restoredAt, nextFrame] of [[1000, 2000], [2000, 3000]]) {
      const frozenPosition = app.byId("position").textContent;
      app.window.dispatchEvent(new app.window.Event("pagehide"));
      assert.equal(app.callbacks.size, 0);
      const restored = new app.window.Event("pageshow");
      Object.defineProperty(restored, "persisted", {value: true});
      app.window.dispatchEvent(restored);
      assert.equal(app.byId("vehicle-status").textContent, "Paused");
      assert.equal(app.byId("position").textContent, frozenPosition);
      assert.equal(app.callbacks.size, 0, "history restore must not autoplay");
      app.byId("play").click();
      assert.equal(app.callbacks.size, 1);
      app.advance(nextFrame);
      assert.notEqual(app.byId("position").textContent, frozenPosition);
      assert.equal(app.callbacks.size, 1);
    }
  } finally { app.close(); }
});


function roadFixture() {
  const schedule = structuredClone(fixture);
  schedule.coordinate_mode = "geographic";
  schedule.route_key = "geographic-bent-route";
  schedule.objective = "distance";
  schedule.source = "osrm";
  schedule.demo_time_scale = 60;
  schedule.estimated_travel_seconds = 720;
  schedule.estimated_service_seconds = 240;
  schedule.estimated_journey_seconds = 960;
  for (const location of schedule.locations) {
    location.x = location.longitude = 106 + location.x / 100;
    location.y = location.latitude = 10 + location.y / 100;
  }
  for (const phase of schedule.phases) {
    if (phase.kind !== "travel") continue;
    const from = schedule.locations[phase.start_index], to = schedule.locations[phase.end_index];
    phase.geometry = [[from.x, from.y], [from.x, from.y + .01], [to.x, to.y]];
    phase.geometry_cumulative_m = [0, 1, 2];
  }
  return schedule;
}

test("real vendored Leaflet draws road bends, truck, safe popups and reversible deliveries", async () => {
  const schedule = roadFixture();
  schedule.locations[0].name = '<img src=x onerror="alert(1)">';
  const app = await mount({schedule});
  try {
    assert.equal(app.byId("error").hidden, true, app.byId("error").textContent);
    assert.equal(app.byId("leaflet-map").hidden, false);
    assert.equal(app.byId("map").hasAttribute("hidden"), true);
    assert.match(app.byId("leaflet-map").textContent, /OpenStreetMap/);
    assert.equal(app.byId("fit").textContent, "Vừa khung bản đồ");
    app.byId("play").click(); app.advance(1500);
    const truck = [...Object.values(app.leaflet()._layers)].find(layer => layer.options?.zIndexOffset === 1000);
    assert.ok(truck, "real Leaflet vehicle marker exists");
    assert.equal(truck.getLatLng().lng, 106, "vehicle follows road bend rather than direct line");
    assert.equal(truck.getLatLng().lat, 10.01);
    assert.match(app.byId("position").textContent, /lat 10.010000/);
    const customer = [...Object.values(app.leaflet()._layers)].find(layer => layer.options?.title === schedule.locations[0].name);
    customer.openPopup();
    assert.equal(app.byId("leaflet-map").querySelector(".geo-popup img"), null);
    assert.match(customer.getPopup().getContent().textContent, /Latitude.*Longitude/);
    app.input("seek", 1000, "input"); app.input("seek", 1000);
    assert.equal(app.latest().state, "completed");
    assert.equal(truck.getLatLng().lng, 106); assert.equal(truck.getLatLng().lat, 10);
    assert.equal(app.byId("delivered-count").textContent, "2 / 2");
    app.input("seek", 250, "input"); app.input("seek", 250);
    assert.equal(app.byId("delivered-count").textContent, "0 / 2");
    assert.match(customer.getPopup().getContent().textContent, /Delivering/);
    app.byId("restart").click();
    assert.equal(app.latest().state, "idle");
  } finally { app.close(); }
});

test("real Leaflet editor emits one bounded GPS click and keeps dataset identity", async () => {
  const editor = {locations: roadFixture().locations, dataset_fingerprint: "editable-data"};
  const app = await mount({editor});
  try {
    assert.equal(app.byId("error").hidden, true, app.byId("error").textContent);
    assert.ok(app.byId("workspace").classList.contains("editor-mode"));
    app.leaflet().fire("click", {latlng: {lat: 10.7769, lng: 106.7009}});
    assert.deepEqual({...app.latest(), event_id: "id"}, {kind: "add_point", latitude: 10.7769, longitude: 106.7009, dataset_fingerprint: "editable-data", event_id: "id"});
    const firstEvent = app.latest().event_id;
    app.renderEditor(editor);
    assert.equal(app.latest().event_id, firstEvent, "rerender does not duplicate a click");
    app.leaflet().fire("click", {latlng: {lat: 10.78, lng: 106.71}});
    assert.notEqual(app.latest().event_id, firstEvent);
    assert.equal(app.callbacks.size, 0, "point editing does not start animation");
  } finally { app.close(); }
});

test("road progress starts at snapped depot without an off-road connector", async () => {
  const schedule = roadFixture();
  const snapped = [106.005, 10.002];
  schedule.parking_positions = {[schedule.depot_index]: snapped};
  const travels = schedule.phases.filter(phase => phase.kind === "travel");
  travels[0].geometry[0] = snapped;
  travels.at(-1).geometry[travels.at(-1).geometry.length - 1] = snapped;
  const app = await mount({schedule});
  try {
    assert.equal(app.byId("error").hidden, true, app.byId("error").textContent);
    const layers = Object.values(app.leaflet()._layers);
    const progress = layers.find(layer => layer.options?.color === "#06b6d4");
    const truck = layers.find(layer => layer.options?.zIndexOffset === 1000);
    assert.deepEqual([truck.getLatLng().lng, truck.getLatLng().lat], snapped);
    assert.deepEqual([progress.getLatLngs()[0].lng, progress.getLatLngs()[0].lat], snapped);
    app.byId("play").click(); app.advance(500);
    assert.deepEqual([progress.getLatLngs()[0].lng, progress.getLatLngs()[0].lat], snapped);
    assert.ok(progress.getLatLngs().every(point => point.lng !== 106 || point.lat !== 10), "cyan path never connects to the unsnapped GPS depot");
    app.input("seek", 1000, "input"); app.input("seek", 1000);
    assert.deepEqual([truck.getLatLng().lng, truck.getLatLng().lat], snapped);
  } finally { app.close(); }
});

test("Leaflet editor and playback hide the Euclidean SVG across mode changes", async () => {
  const road = roadFixture();
  const editor = {locations: road.locations, dataset_fingerprint: "map-visibility"};
  const app = await mount({editor});
  try {
    const stylesheet = app.window.document.createElement("style");
    stylesheet.textContent = readFileSync(new URL("styles.css", frontend), "utf8");
    app.window.document.head.append(stylesheet);
    const assertGeographic = () => {
      assert.equal(app.byId("map").hasAttribute("hidden"), true, "SVG has a real hidden attribute");
      assert.equal(app.window.getComputedStyle(app.byId("map")).display, "none", "Euclidean grid takes no layout space");
      assert.equal(app.byId("leaflet-map").hidden, false);
      assert.notEqual(app.window.getComputedStyle(app.byId("leaflet-map")).display, "none");
    };
    assertGeographic();
    app.render(road);
    assertGeographic();
    app.render({...fixture, route_key: "euclidean-after-map"});
    assert.equal(app.byId("map").hasAttribute("hidden"), false);
    assert.equal(app.window.getComputedStyle(app.byId("map")).display, "block");
    assert.equal(app.byId("leaflet-map").hidden, true);
    app.renderEditor(editor);
    assertGeographic();
    assert.equal(app.byId("error").hidden, true, app.byId("error").textContent);
  } finally { app.close(); }
});

test("real Leaflet recovers a failed basemap without rebuilding the route or publishing controls", async () => {
  const road = roadFixture();
  const app = await mount({schedule: road});
  try {
    assert.equal(app.byId("basemap-tools").hidden, false);
    const layers = () => Object.values(app.leaflet()._layers);
    const first = layers().find(layer => layer._url?.includes("tile.openstreetmap.org"));
    assert.ok(first);
    first.fire("loading"); first.fire("tileerror"); first.fire("load");
    const fallback = layers().find(layer => layer._url?.includes("tile.openstreetmap.de"));
    assert.ok(fallback);
    assert.ok(!layers().includes(first));
    assert.equal(app.byId("basemap-provider").value, "osm_de");
    fallback.fire("tileload"); fallback.fire("load");
    assert.equal(app.byId("basemap-status").dataset.state, "ready");
    assert.equal(app.byId("tile-notice").hidden, true);
    const truck = layers().find(layer => layer.options?.zIndexOffset === 1000);
    const before = app.messages.filter(message => message.type === "streamlit:setComponentValue").length;
    app.byId("reload-tiles").click();
    assert.ok(layers().includes(truck), "retry only replaces the tile layer");
    assert.equal(app.messages.filter(message => message.type === "streamlit:setComponentValue").length, before);
    app.byId("play").click(); app.advance(500);
    assert.equal(app.latest().state, "playing");
    assert.ok(layers().includes(truck));
    app.render({...fixture, route_key: "euclid-after-tile-failure"});
    assert.equal(app.byId("basemap-tools").hidden, true);
  } finally { app.close(); }
});
