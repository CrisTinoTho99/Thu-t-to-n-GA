/** Offline SVG renderer and the small Streamlit v1 message bridge. */
import {Playback} from "./engine.js";

const $ = id => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
const STORAGE_KEY = "tsp.delivery.latest-checkpoint.v1";
const COLORS = {Warehouse: "#34d399", Pending: "#818cf8", "In Transit": "#fbbf24", Delivering: "#fbbf24", Delivered: "#22d3ee"};
const STATE_LABELS = {idle: "Idle", playing: "Moving", paused: "Paused", stopped: "Stopped", completed: "Completed"};
const PHASE_LABELS = {moving: "On route", delivering: "Delivering", at_depot: "At warehouse"};
let schedule = null;
let playback = null;
let animation = null;
let lastPaint = -Infinity;
let lastStorage = -Infinity;
let lastEventSignature = "";
let lastStatusSignature = "";
let selectedIndex = null;
let markers = [];
let manifestRows = [];
let base = null;
let view = {x: 0, y: 0, width: 900, height: 500};
let drag = null;
let dragged = false;
let frameHeight = 0;
let disposed = false;
let disabled = false;

let parentOrigin = "*";
try {
  const source = new URLSearchParams(window.location.search).get("streamlitUrl");
  if (source) parentOrigin = new URL(source).origin;
} catch { /* A sandboxed component can still use the standard v1 bridge. */ }

function message(type, payload = {}) {
  window.parent.postMessage({isStreamlitMessage: true, type, ...payload}, parentOrigin);
}

function resizeFrame() {
  const height = Math.ceil($("simulation").getBoundingClientRect().height) + 4;
  if (height > 0 && height !== frameHeight) {
    frameHeight = height;
    message("streamlit:setFrameHeight", {height});
  }
}

function savedCheckpoint(routeKey, backend) {
  let local = null;
  try {
    const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "null");
    if (parsed?.route_key === routeKey) local = parsed;
  } catch { /* Storage can be disabled; backend checkpoints still work. */ }
  const remote = backend?.route_key === routeKey ? backend : null;
  if (!local) return remote;
  if (!remote) return local;
  if ((local.sequence ?? 0) !== (remote.sequence ?? 0)) return local.sequence > remote.sequence ? local : remote;
  // A playing browser cursor advances between explicit backend checkpoints.
  return (local.time ?? 0) >= (remote.time ?? 0) ? local : remote;
}

function storeCheckpoint() {
  if (!playback) return;
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(playback.checkpoint())); } catch { /* Optional persistence. */ }
}

function publishCheckpoint() {
  if (!playback) return;
  storeCheckpoint();
  message("streamlit:setComponentValue", {dataType: "json", value: playback.checkpoint()});
}

function svgElement(tag, attributes = {}, text = null) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== null) element.textContent = String(text);
  return element;
}

function setText(id, value) {
  const element = $(id);
  const text = String(value);
  if (element.textContent !== text) element.textContent = text;
}

function number(value, digits = 2) { return Number(value).toLocaleString("en-US", {minimumFractionDigits: digits, maximumFractionDigits: digits}); }
function seconds(value) { return `${number(value, 1)} s`; }

function mapPoint(point) {
  return {x: 450 + (point.x - base.centerX) * base.scale, y: 250 - (point.y - base.centerY) * base.scale};
}

function updateView() {
  $("map").setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`);
}

function fitView() {
  view = {x: 0, y: 0, width: 900, height: 500};
  updateView();
}

function drawNetwork() {
  const locations = schedule.locations;
  const xs = locations.map(point => point.x);
  const ys = locations.map(point => point.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = Math.max(1, maxX - minX), height = Math.max(1, maxY - minY);
  base = {centerX: minX + (maxX - minX) / 2, centerY: minY + (maxY - minY) / 2, scale: Math.min(720 / width, 345 / height)};
  fitView();
  const routePoints = schedule.route.map(index => mapPoint(locations[index]));
  $("route-line").setAttribute("points", routePoints.map(point => `${point.x},${point.y}`).join(" "));
  $("markers").replaceChildren();
  $("manifest").replaceChildren();
  markers = [];
  manifestRows = [];
  const order = new Map(schedule.route.slice(0, -1).map((index, position) => [index, position]));
  for (const [index, location] of locations.entries()) {
    const point = mapPoint(location);
    const depot = index === schedule.depot_index;
    const group = svgElement("g", {class: "stop-marker", transform: `translate(${point.x} ${point.y})`, tabindex: 0, role: "button", "aria-label": `${location.name}, ${depot ? "warehouse" : `visit ${order.get(index)}`}`});
    const halo = svgElement("circle", {class: "location-halo", r: depot ? 19 : 15, fill: "none", stroke: "#fbbf24", "stroke-width": 2, opacity: 0});
    group.append(halo);
    let shape;
    if (depot) {
      shape = svgElement("path", {d: "M-13 -3 L0 -14 L13 -3 L13 11 L-13 11 Z", fill: "#34d399", stroke: "#bbf7d0", "stroke-width": 1.5});
      group.append(shape, svgElement("path", {d: "M-6 11 V0 H6 V11 M-3 0 V11 M3 0 V11", fill: "none", stroke: "#0d4034", "stroke-width": 1.5}));
    } else {
      shape = svgElement("circle", {r: 8, fill: "#818cf8", stroke: "#c7d2fe", "stroke-width": 1.5});
      group.append(shape);
    }
    group.append(svgElement("text", {class: "marker-label", x: 0, y: depot ? -24 : -18, "text-anchor": "middle", fill: depot ? "#6ee7b7" : "#c7d2fe", "font-size": 12, "font-weight": 650}, depot ? "WAREHOUSE" : String(order.get(index))));
    group.append(svgElement("title", {}, `${location.name}\nID: ${location.id}\n(${number(location.x)}, ${number(location.y)})`));
    const choose = () => { selectedIndex = index; render(playback.snapshot()); };
    group.addEventListener("click", () => { if (!dragged) choose(); });
    group.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } });
    $("markers").append(group);
    markers.push({group, halo, shape, depot});
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-label", `Inspect ${location.name}`);
    row.addEventListener("click", choose);
    row.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); }
    });
    const visit = document.createElement("td"); visit.textContent = depot ? "Depot" : String(order.get(index));
    const name = document.createElement("td"); name.textContent = `${location.id} · ${location.name}`;
    const coords = document.createElement("td"); coords.textContent = `(${number(location.x)}, ${number(location.y)})`;
    const status = document.createElement("td"); status.textContent = depot ? "Warehouse" : "Pending";
    row.append(visit, name, coords, status);
    $("manifest").append(row);
    manifestRows.push(status);
  }
  selectedIndex = schedule.depot_index;
  setText("manifest-count", `${locations.length - 1} customers + warehouse`);
  setText("route-summary", `${schedule.algorithm} · ${number(schedule.total_distance)} coordinate units · ${number(schedule.base_speed)} units / sim second`);
}

function completedPoints(snapshot) {
  const points = [mapPoint(schedule.locations[schedule.depot_index])];
  if (playback.state === "idle") return points;
  for (const phase of schedule.phases) {
    if (phase.kind !== "travel") continue;
    if (snapshot.elapsed >= phase.end_time) points.push(mapPoint(schedule.locations[phase.end_index]));
    else if (snapshot.elapsed >= phase.start_time) {
      points.push(mapPoint(snapshot));
      break;
    } else break;
  }
  return points;
}

function eventDescription(event) {
  const location = schedule.locations[event.index]?.name ?? "location";
  return {
    started: "Simulation started",
    departed: event.index === schedule.depot_index ? "Vehicle departed warehouse" : `Vehicle departed ${location}`,
    arrived: `Vehicle arrived at ${location}`,
    delivered: `Delivery completed at ${location}`,
    returned: "Vehicle returned to warehouse",
    completed: "Delivery completed · all stops served",
  }[event.type] ?? event.type;
}

function drawEvents(snapshot) {
  const signature = snapshot.visible_events.join("|");
  if (signature === lastEventSignature) return;
  lastEventSignature = signature;
  const visible = new Set(snapshot.visible_events);
  const fragment = document.createDocumentFragment();
  let count = 0;
  for (const event of schedule.events) {
    if (!visible.has(event.id)) continue;
    const item = document.createElement("li"); item.className = `event-${event.type}`;
    const dot = document.createElement("span"); dot.className = "event-dot";
    const time = document.createElement("time"); time.textContent = seconds(event.time);
    const text = document.createElement("span"); text.textContent = eventDescription(event);
    item.append(dot, time, text);
    fragment.append(item);
    count += 1;
  }
  if (count === 0) {
    const empty = document.createElement("li"); empty.className = "empty-event"; empty.textContent = "Press Play to depart the warehouse."; fragment.append(empty);
  }
  $("timeline").replaceChildren(fragment);
  $("timeline").scrollTop = $("timeline").scrollHeight;
  setText("event-count", `${count} events`);
}

function render(snapshot) {
  if (!playback || !schedule || !base) return;
  const point = mapPoint(snapshot);
  $("vehicle").setAttribute("transform", `translate(${point.x} ${point.y})`);
  $("van-body").setAttribute("transform", `rotate(${-snapshot.heading * 180 / Math.PI})`);
  $("vehicle").style.pointerEvents = "none";
  $("traveled-line").setAttribute("points", completedPoints(snapshot).map(p => `${p.x},${p.y}`).join(" "));
  const status = playback.state === "playing" && snapshot.phase === "delivering" ? "Delivering" : STATE_LABELS[playback.state];
  setText("vehicle-status", status);
  setText("phase-badge", PHASE_LABELS[snapshot.phase]);
  setText("destination", snapshot.destination_index !== null ? schedule.locations[snapshot.destination_index].name : (playback.state === "completed" ? "Returned to warehouse" : "Ready at warehouse"));
  setText("position", `x ${number(snapshot.x)} · y ${number(snapshot.y)}`);
  setText("delivered-count", `${snapshot.delivered_count} / ${schedule.locations.length - 1}`);
  setText("remaining-count", `${snapshot.remaining_count} remaining`);
  setText("distance-traveled", number(snapshot.distance_traveled));
  setText("distance-remaining", number(snapshot.remaining_distance));
  setText("elapsed", seconds(snapshot.elapsed));
  setText("time-remaining", seconds(snapshot.remaining_time));
  setText("playback-remaining", seconds(snapshot.remaining_time / playback.speed));
  setText("distance-progress", `${number(snapshot.distance_progress_percent, 1)}%`);
  $("distance-bar").style.width = `${snapshot.distance_progress_percent}%`;
  setText("time-progress", `${number(snapshot.progress_percent, 1)}%`);
  setText("time-range", `${number(snapshot.elapsed, 1)} / ${number(schedule.total_duration, 1)} sim seconds`);
  $("seek").value = String(Math.round(snapshot.progress_percent * 10));
  $("seek").setAttribute("aria-valuetext", `${number(snapshot.elapsed, 1)} of ${number(schedule.total_duration, 1)} simulation seconds`);
  $("speed").value = String(playback.speed);
  $("play").textContent = playback.state === "paused" || playback.state === "stopped" ? "▶ Resume" : "▶ Play";
  $("play").disabled = disabled || ["playing", "completed"].includes(playback.state);
  $("pause").disabled = disabled || playback.state !== "playing";
  $("stop").disabled = disabled || ["idle", "stopped", "completed"].includes(playback.state);
  $("restart").disabled = disabled || playback.state === "idle";
  $("speed").disabled = disabled;
  $("seek").disabled = disabled;
  $("complete-banner").hidden = playback.state !== "completed";
  const statusesSignature = snapshot.statuses.join("|");
  if (statusesSignature !== lastStatusSignature) {
    lastStatusSignature = statusesSignature;
    for (const [index, marker] of markers.entries()) {
      const value = snapshot.statuses[index];
      marker.shape.setAttribute("fill", COLORS[value]);
      marker.halo.setAttribute("opacity", value === "In Transit" || value === "Delivering" ? "1" : "0");
      manifestRows[index].textContent = value;
      manifestRows[index].style.color = COLORS[value];
    }
  }
  for (const [index, marker] of markers.entries()) marker.group.classList.toggle("selected", index === selectedIndex);
  if (selectedIndex !== null) {
    const location = schedule.locations[selectedIndex];
    const visit = schedule.route.slice(0, -1).indexOf(selectedIndex);
    setText("selected-name", location.name);
    setText("selected-details", `${location.id} · (${number(location.x)}, ${number(location.y)}) · ${selectedIndex === schedule.depot_index ? "Warehouse" : `Visit ${visit}`}`);
    setText("selected-status", snapshot.statuses[selectedIndex]);
    $("selected-status").style.color = COLORS[snapshot.statuses[selectedIndex]];
  }
  drawEvents(snapshot);
}

function cancelAnimation() {
  if (animation !== null) cancelAnimationFrame(animation);
  animation = null;
}

function animate(now) {
  animation = null;
  if (disposed || !playback || playback.state !== "playing") return;
  if (now - lastPaint >= 1000 / 30) {
    lastPaint = now;
    const snapshot = playback.tick(now);
    render(snapshot);
    if (now - lastStorage >= 1000) { storeCheckpoint(); lastStorage = now; }
    if (playback.state === "completed") { publishCheckpoint(); return; }
  }
  animation = requestAnimationFrame(animate);
}

function beginAnimation() {
  if (!disposed && playback?.state === "playing" && animation === null) {
    lastPaint = -Infinity;
    animation = requestAnimationFrame(animate);
  }
}

function action(method, ...args) {
  if (!playback || disabled) return;
  const snapshot = playback[method](...args);
  if (playback.state !== "playing") cancelAnimation();
  render(snapshot);
  publishCheckpoint();
  beginAnimation();
}

$("play").addEventListener("click", () => action("play"));
$("pause").addEventListener("click", () => action("pause"));
$("stop").addEventListener("click", () => action("stop"));
$("restart").addEventListener("click", () => action("restart"));
$("speed").addEventListener("change", () => action("setSpeed", Number($("speed").value)));
$("seek").addEventListener("input", () => {
  if (!playback || disabled) return;
  cancelAnimation();
  render(playback.seek(Number($("seek").value) / 1000 * schedule.total_duration));
  storeCheckpoint();
});
$("seek").addEventListener("change", () => publishCheckpoint());
$("fit").addEventListener("click", fitView);
$("locations-panel").addEventListener("toggle", resizeFrame);

$("map").addEventListener("wheel", event => {
  if (!base) return;
  event.preventDefault();
  const rect = $("map").getBoundingClientRect();
  const fractionX = (event.clientX - rect.left) / rect.width;
  const fractionY = (event.clientY - rect.top) / rect.height;
  const width = Math.max(225, Math.min(1350, view.width * (event.deltaY > 0 ? 1.12 : 1 / 1.12)));
  const height = width * 500 / 900;
  view.x += fractionX * (view.width - width);
  view.y += fractionY * (view.height - height);
  view.width = width; view.height = height;
  updateView();
}, {passive: false});

$("map").addEventListener("pointerdown", event => {
  if (event.button !== 0) return;
  dragged = false;
  drag = {x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y};
});
$("map").addEventListener("pointermove", event => {
  if (!drag) return;
  const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) < 4 && !dragged) return;
  if (!dragged) $("map").setPointerCapture(event.pointerId);
  dragged = true;
  $("map").classList.add("dragging");
  const rect = $("map").getBoundingClientRect();
  // SVG's meet scaling can leave horizontal/vertical margins; pan uses the
  // uniform unit scale, preserving the physical x/y ratio.
  const unitsPerPixel = Math.max(view.width / rect.width, view.height / rect.height);
  view.x = drag.viewX - dx * unitsPerPixel;
  view.y = drag.viewY - dy * unitsPerPixel;
  updateView();
});
for (const type of ["pointerup", "pointercancel"]) $("map").addEventListener(type, () => { drag = null; $("map").classList.remove("dragging"); });

function receiveRender(event) {
  if (event.source !== window.parent || !event.data || event.data.type !== "streamlit:render") return;
  const args = event.data.args ?? {};
  disabled = Boolean(event.data.disabled);
  if (!args.schedule?.route_key) return;
  try {
    if (!schedule || schedule.route_key !== args.schedule.route_key) {
      cancelAnimation();
      const firstMount = schedule === null;
      if (!firstMount) { try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* Optional storage. */ } }
      schedule = args.schedule;
      playback = new Playback(schedule, firstMount ? savedCheckpoint(schedule.route_key, args.checkpoint) : null);
      lastEventSignature = "uninitialized";
      lastStatusSignature = "";
      lastStorage = -Infinity;
      drawNetwork();
      $("loading").hidden = true;
      $("workspace").hidden = false;
      $("error").hidden = true;
      storeCheckpoint();
    }
    // Streamlit echoes checkpoint messages by rerunning Python. A matching
    // route keeps the in-memory clock; it must not restore a stale echo.
    render(playback.snapshot());
    resizeFrame();
  } catch (error) {
    cancelAnimation();
    $("loading").hidden = true;
    $("workspace").hidden = true;
    $("error").hidden = false;
    $("error").textContent = `Unable to prepare simulation: ${error.message}`;
    resizeFrame();
  }
}

function visibilityChanged() {
  if (document.hidden && playback?.state === "playing") action("pause");
}

function dispose() {
  if (disposed) return;
  if (playback?.state === "playing") playback.pause();
  storeCheckpoint();
  disposed = true;
  cancelAnimation();
  resizeObserver.disconnect();
  window.removeEventListener("message", receiveRender);
  document.removeEventListener("visibilitychange", visibilityChanged);
}

window.addEventListener("message", receiveRender);
document.addEventListener("visibilitychange", visibilityChanged);
window.addEventListener("pagehide", dispose, {once: true});
const resizeObserver = new ResizeObserver(resizeFrame);
resizeObserver.observe($("simulation"));
message("streamlit:componentReady", {apiVersion: 1});
resizeFrame();
