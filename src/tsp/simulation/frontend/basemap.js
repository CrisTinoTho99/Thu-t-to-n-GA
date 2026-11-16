/** Viewport-only raster tiles. No prefetch, tile proxy or background retry loop. */
export const BASEMAPS = Object.freeze({
  osm: {
    label: "OpenStreetMap Standard",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    maxNativeZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
  },
  osm_de: {
    label: "OpenStreetMap DE · dự phòng",
    url: "https://tile.openstreetmap.de/{z}/{x}/{y}.png",
    maxNativeZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors · <a href="https://tile.openstreetmap.de/" target="_blank" rel="noopener">OSM DE</a> · <a href="https://creativecommons.org/licenses/by-sa/2.0/" target="_blank" rel="noopener">CC BY-SA</a>',
  },
});

export class BasemapController {
  constructor(map, L, {select, retry, status, notice}, now = () => Date.now()) {
    Object.assign(this, {map, L, select, retry, status, notice, now});
    this.lastManual = -Infinity;
    this.fallbackUsed = false;
    this.onSelect = () => this.manual(select.value);
    this.onRetry = () => this.manual(this.provider);
    if (select) {
      select.replaceChildren();
      for (const [key, provider] of Object.entries(BASEMAPS)) {
        const option = document.createElement("option");
        option.value = key; option.textContent = provider.label; select.append(option);
      }
      select.addEventListener("change", this.onSelect);
    }
    retry?.addEventListener("click", this.onRetry);
    map.on("unload", () => this.dispose());
    this.use("osm");
  }

  show(state, message, detail = "") {
    this.state = state;
    this.message = message;
    this.detail = detail;
    if (this.status) {
      this.status.dataset.state = state;
      this.status.textContent = message;
    }
    if (this.notice) {
      this.notice.hidden = !detail || Boolean(this.map.getContainer?.().hidden);
      this.notice.textContent = detail;
    }
  }

  refreshStatus() { this.show(this.state, this.message, this.detail); }

  manual(provider) {
    if (!Object.hasOwn(BASEMAPS, provider)) throw new Error("Unknown basemap provider.");
    // A repeated click cannot create a fast request loop. HTTP tile caching remains enabled.
    if (this.now() - this.lastManual < 2000) {
      if (this.select) this.select.value = this.provider;
      return;
    }
    this.lastManual = this.now();
    this.fallbackUsed = false;
    this.use(provider);
  }

  use(provider) {
    if (!Object.hasOwn(BASEMAPS, provider)) throw new Error("Unknown basemap provider.");
    if (this.layer) { this.layer.off(); this.map.removeLayer(this.layer); }
    this.provider = provider;
    if (this.select) this.select.value = provider;
    const source = BASEMAPS[provider];
    const layer = this.L.tileLayer(source.url, {
      maxZoom: 19, maxNativeZoom: source.maxNativeZoom,
      updateWhenIdle: true, updateWhenZooming: false, keepBuffer: 0,
      referrerPolicy: "strict-origin-when-cross-origin",
      attribution: source.attribution,
    });
    this.layer = layer;
    let loaded = 0, failed = 0;
    const current = () => this.layer === layer;
    const loading = () => this.show("loading", `Đang tải nền ${source.label}…`);
    layer.on("loading", () => { if (current()) { loaded = failed = 0; loading(); } });
    layer.on("tileload", () => { if (current()) loaded += 1; });
    layer.on("tileerror", () => { if (current()) failed += 1; });
    layer.on("load", () => {
      if (!current()) return;
      if (loaded === 0 && failed > 0 && provider === "osm" && !this.fallbackUsed) {
        // Switch once after the whole viewport fails, never once per failed tile.
        this.fallbackUsed = true;
        this.use("osm_de");
        return;
      }
      if (loaded === 0 && failed > 0) {
        this.show("error", "Không tải được nền bản đồ",
          "Không kết nối được máy chủ nền bản đồ. Kiểm tra Internet/DNS, chọn nguồn khác hoặc nhấn Tải lại nền. Điểm và tuyến hiện có vẫn hoạt động.");
      } else if (failed > 0) {
        this.show("partial", `Nền ${source.label} tải chưa đầy đủ`,
          "Một số ô bản đồ chưa tải được. Nhấn Tải lại nền hoặc đổi nguồn nền; không cần tối ưu lại tuyến.");
      } else if (loaded > 0) {
        this.show("ready", this.fallbackUsed
          ? "Nền sẵn sàng · dùng OSM DE do nguồn chính lỗi"
          : `Nền sẵn sàng · ${source.label}`);
      }
    });
    loading();
    layer.addTo(this.map);
  }

  dispose() {
    this.select?.removeEventListener("change", this.onSelect);
    this.retry?.removeEventListener("click", this.onRetry);
    this.layer?.off();
  }
}
