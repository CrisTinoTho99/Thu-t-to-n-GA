/** Leaflet 1.9.4 view only. Route ordering and road requests stay in Python. */
import {BasemapController} from "./basemap.js";
const COLORS = {Warehouse: "#34d399", Pending: "#818cf8", "In Transit": "#fbbf24", Delivering: "#fbbf24", Delivered: "#22d3ee"};
const latLng = point => [point.latitude ?? point.y, point.longitude ?? point.x];
const geoJsonToLeaflet = point => [point[1], point[0]];
const depotLatLng = input => {
  const snapped = input.parking_positions?.[String(input.depot_index)]
    ?? input.phases?.find(phase => phase.kind === "travel")?.geometry?.[0];
  return snapped ? geoJsonToLeaflet(snapped) : latLng(input.locations[input.depot_index]);
};

export function distanceLabel(meters) {
  return meters >= 1000 ? `${(meters / 1000).toFixed(2)} km` : `${meters.toFixed(0)} m`;
}

export class LeafletMap {
  constructor(container, {onSelect, onAdd}) {
    const L = window.L;
    if (!L) throw new Error("Leaflet assets could not load. Reload the application.");
    this.L = L;
    this.onSelect = onSelect;
    this.onAdd = onAdd;
    this.map = L.map(container, {zoomControl: true, scrollWheelZoom: true, maxZoom: 19});
    this.basemap = new BasemapController(this.map, L, {
      select: document.getElementById("basemap-provider"),
      retry: document.getElementById("reload-tiles"),
      status: document.getElementById("basemap-status"),
      notice: document.getElementById("tile-notice"),
    });
    this.layers = L.layerGroup().addTo(this.map);
    this.map.on("click", event => {
      if (this.editor) this.onAdd(event.latlng.lat, event.latlng.lng);
    });
  }

  markerIcon(depot, order, status) {
    const element = document.createElement("span");
    element.className = `geo-marker ${depot ? "geo-warehouse" : "geo-customer"}`;
    element.style.backgroundColor = COLORS[status];
    element.textContent = depot ? "⌂" : String(order ?? "•");
    return this.L.divIcon({className: "geo-icon", html: element, iconSize: [30, 30], iconAnchor: [15, 15], popupAnchor: [0, -18]});
  }

  popup(index, status) {
    const location = this.input.locations[index];
    const wrapper = document.createElement("div");
    wrapper.className = "geo-popup";
    const name = document.createElement("strong"); name.textContent = location.name;
    const coordinates = document.createElement("div"); coordinates.textContent = `Latitude: ${latLng(location)[0].toFixed(6)} · Longitude: ${latLng(location)[1].toFixed(6)}`;
    const order = document.createElement("div"); order.textContent = location.is_depot ? "Kho · xuất phát và quay về" : `Thứ tự giao: ${this.orders.get(index) ?? "chưa tối ưu"}`;
    const state = document.createElement("div"); state.textContent = `Trạng thái: ${status}`;
    wrapper.append(name, coordinates, order, state);
    return wrapper;
  }

  network(input, editor = false) {
    this.input = input; this.editor = editor;
    this.layers.clearLayers();
    this.markers = [];
    this.orders = new Map((input.route ?? []).slice(0, -1).map((index, position) => [index, position]));
    this.points = [];
    if (!editor) {
      for (const phase of input.phases) {
        if (phase.kind === "travel") this.points.push(...phase.geometry.map(geoJsonToLeaflet));
      }
      this.L.polyline(this.points, {
        color: input.source === "approximate" ? "#d97706" : "#6366f1", weight: 5, opacity: .8,
        dashArray: input.source === "approximate" ? "8 7" : null, interactive: false,
      }).addTo(this.layers);
      this.traveled = this.L.polyline([], {color: "#06b6d4", weight: 6, interactive: false}).addTo(this.layers);
    }
    input.locations.forEach((location, index) => {
      const status = location.is_depot ? "Warehouse" : "Pending";
      const marker = this.L.marker(latLng(location), {icon: this.markerIcon(location.is_depot, this.orders.get(index), status), keyboard: true, title: location.name})
        .addTo(this.layers).bindPopup(this.popup(index, status));
      marker.on("click", () => this.onSelect(index));
      this.markers.push(marker);
      this.points.push(latLng(location));
    });
    if (!editor) {
      const icon = document.createElement("div"); icon.className = "geo-truck";
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "-29 -29 58 58");
      svg.setAttribute("width", "58"); svg.setAttribute("height", "58");
      svg.append(document.getElementById("van-body").cloneNode(true));
      // The copied icon must not introduce a second document id.
      svg.firstElementChild.removeAttribute("id");
      icon.append(svg); this.truckBody = svg.firstElementChild;
      this.truck = this.L.marker(depotLatLng(input), {
        icon: this.L.divIcon({className: "geo-truck-icon", html: icon, iconSize: [58, 58], iconAnchor: [29, 29]}),
        interactive: false, zIndexOffset: 1000,
      }).addTo(this.layers);
    }
    this.statuses = "";
    this.fit();
  }

  fit() {
    this.map.invalidateSize();
    if (this.points?.length) this.map.fitBounds(this.points, {padding: [38, 38], maxZoom: 15, animate: false});
    else this.map.setView([10.7769, 106.7009], 13);
  }

  select(index) { this.markers[index]?.openPopup(); }

  update(snapshot, selectedIndex, playbackState) {
    this.truck.setLatLng([snapshot.y, snapshot.x]);
    this.truckBody.setAttribute("transform", `rotate(${-snapshot.heading * 180 / Math.PI})`);
    const path = [depotLatLng(this.input)];
    if (playbackState !== "idle") {
      for (const phase of this.input.phases) {
        if (phase.kind !== "travel") continue;
        if (snapshot.elapsed >= phase.end_time) path.push(...phase.geometry.map(geoJsonToLeaflet));
        else if (snapshot.elapsed >= phase.start_time) {
          const fraction = (snapshot.elapsed - phase.start_time) / (phase.end_time - phase.start_time);
          const cumulative = phase.geometry_cumulative_m;
          const target = fraction * cumulative[cumulative.length - 1];
          for (let i = 0; i < phase.geometry.length && cumulative[i] < target; i += 1) path.push(geoJsonToLeaflet(phase.geometry[i]));
          path.push([snapshot.y, snapshot.x]);
          break;
        } else break;
      }
    }
    this.traveled.setLatLngs(path);
    const signature = snapshot.statuses.join("|");
    if (signature !== this.statuses) {
      this.statuses = signature;
      this.markers.forEach((marker, index) => {
        const location = this.input.locations[index];
        marker.setIcon(this.markerIcon(location.is_depot, this.orders.get(index), snapshot.statuses[index]));
        marker.setPopupContent(this.popup(index, snapshot.statuses[index]));
      });
    }
    this.markers.forEach((marker, index) => marker.getElement()?.classList.toggle("geo-selected", index === selectedIndex));
  }
}
