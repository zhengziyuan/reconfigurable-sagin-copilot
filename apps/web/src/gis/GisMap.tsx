import maplibregl, { type Map as MapLibreMap, type Marker, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type { MetricCell, MetricKey, NodeItem, NodeType } from "../types";
import { metricFraction, physicalMetricColor } from "./metricScale";

export type BasemapKind = "street" | "satellite";

interface GisMapProps {
  polygon: [number, number][];
  nodes: NodeItem[];
  selectedIds: Set<string>;
  cells: MetricCell[];
  metric: MetricKey;
  viewMode: "2d" | "3d";
  basemap: BasemapKind;
  placementMode: NodeType | null;
  selectedNodeId: string | null;
  selectedCell: MetricCell | null;
  opacity: number;
  showLinks: boolean;
  showCells: boolean;
  fitRequest: number;
  onSelectNode: (nodeId: string | null) => void;
  onSelectCell: (cell: MetricCell | null) => void;
  onMoveNode: (nodeId: string, position: { lat: number; lon: number }) => void;
  onAddNode: (type: NodeType, position: { lat: number; lon: number }) => void;
}

const candidateTypes = new Set<NodeType>(["ris", "mis", "ma_array", "uav_relay"]);
const sourceIds = ["rsagin-region", "rsagin-cells", "rsagin-links"] as const;
const layerIds = [
  "rsagin-region-fill",
  "rsagin-region-outline",
  "rsagin-cells-fill",
  "rsagin-cells-extrusion",
  "rsagin-cells-line",
  "rsagin-links",
] as const;

export function GisMap(props: GisMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const cameraRef = useRef<{ center: [number, number]; zoom: number; pitch: number; bearing: number } | null>(null);
  const latestPropsRef = useRef(props);
  const [mapState, setMapState] = useState<"loading" | "ready" | "degraded">("loading");
  const center = useMemo(() => polygonCenter(props.polygon), [props.polygon]);

  latestPropsRef.current = props;

  useEffect(() => {
    if (!containerRef.current) return;
    setMapState("loading");
    let fitTimer: number | undefined;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: createBasemapStyle(props.basemap),
      center: cameraRef.current?.center ?? center,
      zoom: cameraRef.current?.zoom ?? 13.4,
      pitch: cameraRef.current?.pitch ?? (props.viewMode === "3d" ? 48 : 0),
      bearing: cameraRef.current?.bearing ?? (props.viewMode === "3d" ? -18 : 0),
      maxPitch: 72,
      cooperativeGestures: false,
      attributionControl: false,
      canvasContextAttributes: { antialias: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true, visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-right");

    map.on("load", () => {
      addOperationalLayers(map, latestPropsRef.current);
      map.resize();
      if (!cameraRef.current) fitScenario(map, latestPropsRef.current.polygon);
      map.jumpTo({ pitch: latestPropsRef.current.viewMode === "3d" ? 48 : 0, bearing: latestPropsRef.current.viewMode === "3d" ? -18 : 0 });
      syncMarkers(map, markersRef, latestPropsRef.current);
      setMapState("ready");
      fitTimer = window.setTimeout(() => {
        map.resize();
        if (!cameraRef.current) fitScenario(map, latestPropsRef.current.polygon);
      }, 180);
    });
    map.on("error", (event) => {
      if (event.error) setMapState((current) => (current === "ready" ? current : "degraded"));
    });
    map.on("click", (event) => {
      const current = latestPropsRef.current;
      if (current.placementMode) {
        current.onAddNode(current.placementMode, { lon: event.lngLat.lng, lat: event.lngLat.lat });
        return;
      }
      const hit = map.queryRenderedFeatures(event.point, { layers: [
        map.getLayer("rsagin-cells-extrusion") && current.viewMode === "3d" ? "rsagin-cells-extrusion" : "rsagin-cells-fill",
      ].filter(Boolean) as string[] })[0];
      if (hit?.properties?.cell_id) {
        const cell = current.cells.find((item) => item.cell_id === hit.properties?.cell_id) ?? null;
        current.onSelectCell(cell);
        current.onSelectNode(null);
      } else {
        current.onSelectCell(null);
        current.onSelectNode(null);
      }
    });
    map.on("mousemove", (event) => {
      const current = latestPropsRef.current;
      if (current.placementMode) {
        map.getCanvas().style.cursor = "crosshair";
        return;
      }
      const interactiveLayer = current.viewMode === "3d" ? "rsagin-cells-extrusion" : "rsagin-cells-fill";
      const hit = map.getLayer(interactiveLayer) && map.queryRenderedFeatures(event.point, { layers: [interactiveLayer] }).length > 0;
      map.getCanvas().style.cursor = hit ? "pointer" : "grab";
    });

    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    return () => {
      if (fitTimer) window.clearTimeout(fitTimer);
      observer.disconnect();
      const mapCenter = map.getCenter();
      cameraRef.current = { center: [mapCenter.lng, mapCenter.lat], zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() };
      clearMarkers(markersRef);
      map.remove();
      mapRef.current = null;
    };
  }, [props.basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource("rsagin-cells")) return;
    updateOperationalSources(map, props);
    syncMarkers(map, markersRef, props);
  }, [props.cells, props.metric, props.nodes, props.selectedCell, props.selectedIds, props.selectedNodeId, props.polygon]);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.getSource("rsagin-region")) fitScenario(map, props.polygon);
  }, [props.polygon, props.fitRequest]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("rsagin-cells-fill")) return;
    applyVisibility(map, props);
  }, [props.opacity, props.showCells, props.showLinks, props.viewMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("rsagin-cells-fill")) return;
    const is3d = props.viewMode === "3d";
    map.easeTo({ pitch: is3d ? 48 : 0, bearing: is3d ? -18 : 0, duration: 500 });
    applyVisibility(map, props);
  }, [props.viewMode]);

  return (
    <div className="gis-map-shell" data-map-state={mapState}>
      <div ref={containerRef} className="gis-map" role="application" aria-label="真实 GIS 空天地网络规划地图" />
      {mapState !== "ready" && (
        <div className="gis-loading-state">
          <span className="gis-loading-pulse" />
          <strong>{mapState === "degraded" ? "底图服务连接较慢" : "正在加载真实 GIS"}</strong>
          <small>性能场与节点图层将继续可用</small>
        </div>
      )}
      <div className="gis-coordinate-chip">EPSG:4326 · {center[1].toFixed(4)}°N, {center[0].toFixed(4)}°E</div>
    </div>
  );
}

function createBasemapStyle(kind: BasemapKind): StyleSpecification {
  const streetTiles = import.meta.env.VITE_GIS_STREET_TILES || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const satelliteTiles = import.meta.env.VITE_GIS_SATELLITE_TILES || "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg";
  const streetAttribution = import.meta.env.VITE_GIS_STREET_ATTRIBUTION || "© OpenStreetMap contributors";
  const satelliteAttribution = import.meta.env.VITE_GIS_SATELLITE_ATTRIBUTION || "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2020)";
  const isSatellite = kind === "satellite";
  return {
    version: 8,
    name: `RSAGIN ${kind}`,
    sources: {
      basemap: {
        type: "raster",
        tiles: [isSatellite ? satelliteTiles : streetTiles],
        tileSize: 256,
        minzoom: 0,
        maxzoom: isSatellite ? 15 : 19,
        attribution: isSatellite ? satelliteAttribution : streetAttribution,
      },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": isSatellite ? "#0f1d22" : "#e9eef0" } },
      {
        id: "basemap",
        type: "raster",
        source: "basemap",
        paint: {
          "raster-opacity": 1,
          "raster-saturation": isSatellite ? -0.18 : -0.34,
          "raster-contrast": isSatellite ? 0.08 : -0.05,
          "raster-brightness-min": isSatellite ? 0.12 : 0.08,
        },
      },
    ],
  };
}

function addOperationalLayers(map: MapLibreMap, props: GisMapProps) {
  const collections = buildCollections(props);
  map.addSource("rsagin-region", { type: "geojson", data: collections.region as never });
  map.addSource("rsagin-cells", { type: "geojson", data: collections.cells as never });
  map.addSource("rsagin-links", { type: "geojson", data: collections.links as never });
  map.addLayer({
    id: "rsagin-region-fill",
    type: "fill",
    source: "rsagin-region",
    paint: { "fill-color": "#00a7a5", "fill-opacity": props.basemap === "satellite" ? 0.08 : 0.045 },
  });
  map.addLayer({
    id: "rsagin-cells-fill",
    type: "fill",
    source: "rsagin-cells",
    layout: { visibility: props.viewMode === "3d" ? "none" : "visible" },
    paint: {
      "fill-color": ["get", "color"],
      "fill-opacity": ["case", ["==", ["get", "selected"], true], 0.94, props.opacity],
    },
  });
  map.addLayer({
    id: "rsagin-cells-extrusion",
    type: "fill-extrusion",
    source: "rsagin-cells",
    layout: { visibility: props.viewMode === "3d" ? "visible" : "none" },
    paint: {
      "fill-extrusion-color": ["get", "color"],
      "fill-extrusion-height": ["get", "height"],
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.78,
      "fill-extrusion-vertical-gradient": true,
    },
  });
  map.addLayer({
    id: "rsagin-cells-line",
    type: "line",
    source: "rsagin-cells",
    paint: {
      "line-color": ["case", ["==", ["get", "selected"], true], "#102d3a", "rgba(255,255,255,0.72)"],
      "line-width": ["case", ["==", ["get", "selected"], true], 2.4, 0.65],
    },
  });
  map.addLayer({
    id: "rsagin-links",
    type: "line",
    source: "rsagin-links",
    paint: {
      "line-color": "#00b8c0",
      "line-width": 2,
      "line-opacity": 0.8,
      "line-dasharray": [3, 2],
    },
  });
  map.addLayer({
    id: "rsagin-region-outline",
    type: "line",
    source: "rsagin-region",
    paint: { "line-color": "#008f8f", "line-width": 3, "line-opacity": 0.95 },
  });
  applyVisibility(map, props);
}

function applyVisibility(map: MapLibreMap, props: GisMapProps) {
  if (map.getLayer("rsagin-cells-fill")) {
    map.setLayoutProperty("rsagin-cells-fill", "visibility", props.showCells && props.viewMode === "2d" ? "visible" : "none");
    map.setPaintProperty("rsagin-cells-fill", "fill-opacity", ["case", ["==", ["get", "selected"], true], 0.94, props.opacity]);
  }
  if (map.getLayer("rsagin-cells-extrusion")) {
    map.setLayoutProperty("rsagin-cells-extrusion", "visibility", props.showCells && props.viewMode === "3d" ? "visible" : "none");
    map.setPaintProperty("rsagin-cells-extrusion", "fill-extrusion-opacity", props.opacity);
  }
  if (map.getLayer("rsagin-cells-line")) map.setLayoutProperty("rsagin-cells-line", "visibility", props.showCells ? "visible" : "none");
  if (map.getLayer("rsagin-links")) map.setLayoutProperty("rsagin-links", "visibility", props.showLinks ? "visible" : "none");
}

function updateOperationalSources(map: MapLibreMap, props: GisMapProps) {
  if (!sourceIds.every((id) => map.getSource(id))) return;
  const collections = buildCollections(props);
  (map.getSource("rsagin-region") as maplibregl.GeoJSONSource).setData(collections.region as never);
  (map.getSource("rsagin-cells") as maplibregl.GeoJSONSource).setData(collections.cells as never);
  (map.getSource("rsagin-links") as maplibregl.GeoJSONSource).setData(collections.links as never);
}

function buildCollections(props: GisMapProps) {
  const ring = closeRing(props.polygon);
  const values = props.cells.map((cell) => cell.value);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const radius = estimateCellRadius(props.cells);
  const region = {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } }],
  };
  const cells = {
    type: "FeatureCollection",
    features: props.cells.map((cell) => {
      const normalized = metricFraction(props.metric, cell.value);
      return {
        type: "Feature",
        properties: {
          cell_id: cell.cell_id,
          color: physicalMetricColor(props.metric, cell.value),
          height: 45 + normalized * 420,
          selected: props.selectedCell?.cell_id === cell.cell_id,
          value: cell.value,
        },
        geometry: { type: "Polygon", coordinates: [hexRing(cell.lon, cell.lat, radius)] },
      };
    }),
  };
  const anchors = props.nodes.filter((node) => ["ground_bs", "ground_station", "satellite_leo"].includes(node.type));
  const selected = props.nodes.filter((node) => props.selectedIds.has(node.id));
  const links = {
    type: "FeatureCollection",
    features: selected.flatMap((node) => anchors.map((anchor) => ({
      type: "Feature",
      properties: { from: anchor.id, to: node.id },
      geometry: {
        type: "LineString",
        coordinates: [[anchor.position.lon, anchor.position.lat], [node.position.lon, node.position.lat]],
      },
    }))),
  };
  return { region, cells, links };
}

function syncMarkers(map: MapLibreMap, markersRef: React.MutableRefObject<Marker[]>, props: GisMapProps) {
  clearMarkers(markersRef);
  markersRef.current = props.nodes.map((node) => {
    const element = document.createElement("button");
    const active = props.selectedIds.has(node.id) || !isCandidate(node);
    element.type = "button";
    element.className = `gis-node-marker gis-node-${node.type}${active ? "" : " is-inactive"}${props.selectedNodeId === node.id ? " is-selected" : ""}`;
    element.setAttribute("aria-label", `${nodeLabel(node.type)} ${node.id}`);
    element.innerHTML = `${nodeSvg(node.type)}<span>${shortNodeLabel(node.type)}</span>`;
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      latestSelection(props, node.id);
    });
    const marker = new maplibregl.Marker({ element, anchor: "center", draggable: true })
      .setLngLat([node.position.lon, node.position.lat])
      .addTo(map);
    marker.on("dragend", () => {
        const position = marker.getLngLat();
        props.onMoveNode(node.id, { lon: position.lng, lat: position.lat });
    });
    return marker;
  });
}

function latestSelection(props: GisMapProps, nodeId: string) {
  props.onSelectNode(nodeId);
  props.onSelectCell(null);
}

function clearMarkers(markersRef: React.MutableRefObject<Marker[]>) {
  markersRef.current.forEach((marker) => marker.remove());
  markersRef.current = [];
}

function fitScenario(map: MapLibreMap, polygon: [number, number][]) {
  if (!polygon.length) return;
  const bounds = polygon.reduce(
    (current, coordinate) => current.extend(coordinate),
    new maplibregl.LngLatBounds(polygon[0], polygon[0]),
  );
  const height = map.getContainer().clientHeight;
  map.fitBounds(bounds, { padding: { top: Math.min(88, height * 0.22), right: 48, bottom: Math.min(50, height * 0.14), left: 48 }, maxZoom: 15.3, duration: 0 });
}

function polygonCenter(polygon: [number, number][]): [number, number] {
  if (!polygon.length) return [120.14, 30.27];
  return [
    polygon.reduce((sum, point) => sum + point[0], 0) / polygon.length,
    polygon.reduce((sum, point) => sum + point[1], 0) / polygon.length,
  ];
}

function closeRing(polygon: [number, number][]) {
  if (!polygon.length) return [];
  const first = polygon[0];
  const last = polygon[polygon.length - 1];
  return first[0] === last[0] && first[1] === last[1] ? polygon : [...polygon, first];
}

function estimateCellRadius(cells: MetricCell[]) {
  if (cells.length < 2) return 90;
  let nearest = Number.POSITIVE_INFINITY;
  const sample = cells.slice(0, Math.min(cells.length, 80));
  for (let first = 0; first < sample.length; first += 1) {
    for (let second = first + 1; second < sample.length; second += 1) {
      const distance = approximateDistance(sample[first].lon, sample[first].lat, sample[second].lon, sample[second].lat);
      if (distance > 2 && distance < nearest) nearest = distance;
    }
  }
  return Math.max(28, Math.min(180, nearest * 0.52));
}

function approximateDistance(lonA: number, latA: number, lonB: number, latB: number) {
  const meanLat = ((latA + latB) / 2) * Math.PI / 180;
  const dx = (lonA - lonB) * 111_320 * Math.cos(meanLat);
  const dy = (latA - latB) * 110_540;
  return Math.hypot(dx, dy);
}

function hexRing(lon: number, lat: number, radiusMeters: number) {
  const result: [number, number][] = [];
  for (let index = 0; index < 6; index += 1) {
    const angle = Math.PI / 3 * index + Math.PI / 6;
    const east = radiusMeters * Math.cos(angle);
    const north = radiusMeters * Math.sin(angle);
    result.push([
      lon + east / (111_320 * Math.cos(lat * Math.PI / 180)),
      lat + north / 110_540,
    ]);
  }
  result.push(result[0]);
  return result;
}

function normalizeMetric(metric: MetricKey, value: number, min: number, max: number) {
  if (max <= min) return 0.5;
  const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)));
  return metric === "localization_peb" || metric === "sla_violation" || metric === "risk" ? 1 - normalized : normalized;
}

function metricColor(metric: MetricKey, normalized: number) {
  const ramps: Record<MetricKey, string[]> = {
    coverage: ["#d9475f", "#f2a83b", "#2bb6aa", "#087f7e"],
    rate: ["#e05259", "#f0a33a", "#42b8bd", "#007c83"],
    localization_peb: ["#d84a62", "#f2a83b", "#63c0b0", "#087f7e"],
    sensing: ["#d34e66", "#e9a33f", "#48a7c6", "#2e64ad"],
    sla_violation: ["#d9475f", "#ee8f3f", "#78bba7", "#18877d"],
    risk: ["#d9475f", "#ee8f3f", "#72b7a8", "#177f79"],
  };
  const ramp = ramps[metric];
  const index = Math.min(ramp.length - 1, Math.floor(normalized * ramp.length));
  return ramp[index];
}

function isCandidate(node: NodeItem) {
  return candidateTypes.has(node.type);
}

function nodeLabel(type: NodeType) {
  const labels: Record<NodeType, string> = {
    satellite_leo: "低轨卫星",
    satellite_geo: "地球同步卫星",
    haps: "高空平台",
    uav_relay: "无人机中继",
    ground_bs: "地面基站",
    ground_station: "地面站",
    ris: "智能反射面",
    mis: "超表面",
    ma_array: "移动天线阵列",
  };
  return labels[type];
}

function shortNodeLabel(type: NodeType) {
  if (type.startsWith("satellite")) return "SAT";
  if (type === "uav_relay" || type === "haps") return "UAV";
  if (type === "ground_bs") return "BS";
  if (type === "ground_station") return "GS";
  if (type === "ma_array") return "MA";
  return type.toUpperCase();
}

function nodeSvg(type: NodeType) {
  if (type.startsWith("satellite")) return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7l5 1 7 7 1 5M7 4l1 5 7 7 5 1M8 8l8 8M3 12l4-4M17 16l4-4"/></svg>';
  if (type === "uav_relay" || type === "haps") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 13h18M7 9l5 4 5-4M8 17l4-4 4 4M12 5v14"/></svg>';
  if (type === "ground_bs" || type === "ground_station") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M8 19h8M8 8c-2 2-2 4 0 6M16 8c2 2 2 4 0 6"/><circle cx="12" cy="7" r="2"/></svg>';
  if (type === "ris") return '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 5v14M14 5v14M5 9h14M5 14h14"/></svg>';
  if (type === "mis") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l9 17H3zM8 16h8M12 8v8"/></svg>';
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 3v6M12 15v6M3 12h6M15 12h6M6 6l4 4M14 14l4 4M18 6l-4 4M10 14l-4 4"/></svg>';
}

export const gisLayerIds = layerIds;
