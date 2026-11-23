"use strict";

const POLL_MS = 2000;
const REQUEST_TIMEOUT_MS = 5000;
const MAX_POINTS = 180;
let pollInFlight = false;
let selectedSession = null;
let latencyUnit = "ticks";
let transferUnit = "application bytes";
const history = [];

const byId = (id) => document.getElementById(id);

function setText(id, value) {
  byId(id).textContent = value == null ? "—" : String(value);
}

function formatNumber(value, digits = 2) {
  return value == null || !Number.isFinite(Number(value))
    ? "—"
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatScaled(value, scale, suffix, digits = 3) {
  return value == null ? "—" : `${formatNumber(Number(value) / scale, digits)} ${suffix}`;
}

async function getJson(path) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    window.clearTimeout(timer);
  }
}

function replaceChildrenWithText(container, text) {
  const item = document.createElement("li");
  item.textContent = text;
  container.replaceChildren(item);
}

function renderArtifacts(values) {
  const container = byId("artifacts");
  const fragment = document.createDocumentFragment();
  const entries = Object.entries(values || {}).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = "Status";
    detail.textContent = "No artifact identity";
    row.append(term, detail);
    fragment.append(row);
  }
  for (const [name, digest] of entries) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = name;
    detail.textContent = digest;
    detail.className = "digest";
    row.append(term, detail);
    fragment.append(row);
  }
  container.replaceChildren(fragment);
}

function renderErrors(detail) {
  setText("error-count", detail.error_count ?? 0);
  const container = byId("errors");
  const errors = Array.isArray(detail.recent_errors) ? detail.recent_errors : [];
  if (!errors.length) {
    replaceChildrenWithText(container, "No errors");
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const error of errors) {
    const item = document.createElement("li");
    const code = typeof error.code === "string" ? error.code : "unknown";
    const detailText = typeof error.detail === "string" ? error.detail : "No detail";
    item.textContent = `${code}: ${detailText}`;
    fragment.append(item);
  }
  container.replaceChildren(fragment);
}

function updateBadges(health) {
  const collector = byId("collector-badge");
  collector.textContent = String(health.collector_state || "unknown").toUpperCase();
  collector.className = health.collector_state === "connected"
    ? "badge badge-connected" : "badge badge-waiting";
  const phase = byId("phase-badge");
  phase.textContent = health.phase || "NO EVIDENCE";
}

function pushHistory(detail) {
  const timestamp = detail.updated_at;
  if (timestamp == null) return;
  const point = {
    timestamp,
    latency: detail.mean_latency_ticks,
    fps: detail.fps,
    fullBytes: detail.full_payload_wire_bytes,
    compactBytes: detail.compact_result_wire_bytes,
    reduction: detail.uplink_reduction_percent,
    powerW: detail.latest_power_uW == null ? null : detail.latest_power_uW / 1_000_000,
    energyJ: detail.monitored_energy_uJ == null ? null : detail.monitored_energy_uJ / 1_000_000,
    temperatureC: detail.latest_temperature_mC == null ? null : detail.latest_temperature_mC / 1000,
  };
  if (history.length && history[history.length - 1].timestamp === timestamp) {
    history[history.length - 1] = point;
  } else {
    history.push(point);
    if (history.length > MAX_POINTS) history.shift();
  }
}

function available(values) {
  return values.some((value) => value != null && Number.isFinite(Number(value)));
}

function chartLayout(title, rightTitle = null, unavailable = false) {
  const layout = {
    margin: { l: 52, r: rightTitle ? 52 : 20, t: 12, b: 44 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(6,18,28,0.32)",
    font: { color: "#c9d7df", size: 11 },
    xaxis: { gridcolor: "rgba(148,180,198,0.12)", title: "latest updates" },
    yaxis: { gridcolor: "rgba(148,180,198,0.12)", title },
    showlegend: true,
    legend: { orientation: "h", y: 1.13 },
  };
  if (rightTitle) layout.yaxis2 = { overlaying: "y", side: "right", title: rightTitle };
  if (unavailable) layout.annotations = [{
    text: "Unavailable", x: 0.5, y: 0.5, xref: "paper", yref: "paper",
    showarrow: false, font: { color: "#8ca1ad", size: 15 },
  }];
  return layout;
}

function renderCharts() {
  const x = history.map((point) => point.timestamp);
  const config = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["sendDataToCloud"] };
  const chart = (id, traces, leftTitle, rightTitle = null) => {
    const hasData = traces.some((trace) => available(trace.y));
    Plotly.react(id, hasData ? traces : [], chartLayout(leftTitle, rightTitle, !hasData), config);
  };
  chart("latency-chart", [
    { x, y: history.map((p) => p.latency), name: latencyUnit, type: "scatter", mode: "lines+markers" },
    { x, y: history.map((p) => p.fps), name: "FPS", type: "scatter", mode: "lines+markers", yaxis: "y2" },
  ], latencyUnit, "FPS");
  chart("bytes-chart", [
    { x, y: history.map((p) => p.fullBytes), name: "full", type: "scatter", mode: "lines+markers" },
    { x, y: history.map((p) => p.compactBytes), name: "compact", type: "scatter", mode: "lines+markers" },
    { x, y: history.map((p) => p.reduction), name: "reduction %", type: "scatter", mode: "lines+markers", yaxis: "y2" },
  ], transferUnit, "%");
  chart("power-chart", [
    { x, y: history.map((p) => p.powerW), name: "W", type: "scatter", mode: "lines+markers" },
    { x, y: history.map((p) => p.energyJ), name: "J", type: "scatter", mode: "lines+markers", yaxis: "y2" },
  ], "monitored W", "monitored J");
  chart("temperature-chart", [
    { x, y: history.map((p) => p.temperatureC), name: "°C", type: "scatter", mode: "lines+markers" },
  ], "°C");
}

function renderDetail(detail) {
  latencyUnit = "ticks";
  transferUnit = "application bytes";
  setText("latency-label", "Mean board latency");
  setText("latency-unit", "PS timer ticks; DMA + PL");
  setText("sample-label", "Inference count");
  setText("model", detail.model);
  setText("endpoint", detail.board_ip && detail.tcp_port ? `${detail.board_ip}:${detail.tcp_port}` : null);
  setText("firmware", detail.firmware_sha256);
  setText("session-id", detail.session_id);
  setText("latest-update", detail.updated_at ? `Updated ${detail.updated_at}` : "No collected evidence");
  setText("sample-count", formatNumber(detail.sample_count, 0));
  setText("latency", formatNumber(detail.mean_latency_ticks));
  setText("fps", formatNumber(detail.fps));
  setText("reduction", detail.uplink_reduction_percent == null ? "—" : `${formatNumber(detail.uplink_reduction_percent)} %`);
  setText("power", formatScaled(detail.latest_power_uW, 1_000_000, "W"));
  setText("energy", formatScaled(detail.monitored_energy_uJ, 1_000_000, "J"));
  setText("temperature", formatScaled(detail.latest_temperature_mC, 1000, "°C", 2));
  setText("full-bytes", formatNumber(detail.full_payload_wire_bytes, 0));
  setText("compact-bytes", formatNumber(detail.compact_result_wire_bytes, 0));
  setText("completed-frames", formatNumber(detail.completed_frames, 0));
  renderArtifacts(detail.artifact_hashes);
  renderErrors(detail);
  pushHistory(detail);
  renderCharts();
}

function showStale(message) {
  byId("stale-badge").classList.remove("is-hidden");
  setText("poll-message", `Evidence may be stale: ${message}`);
}

function renderMeasurements(report) {
  setText("measurement-status", report.status || "NOT RUN");
  setText("measurement-source", `${report.source || "No evidence"} · ${report.measurement_id || ""}`);
  const rows = document.createDocumentFragment();
  const appendRow = (experiment, mode, values, saving = null) => {
    const row = document.createElement("tr");
    const fields = [experiment.trial ?? 1, experiment.camera_streams,
      experiment.load_mode || "fixed", experiment.offered_fps_per_stream ?? "unpaced", mode,
      `${values.frames_received ?? "—"} / ${values.frames_sent ?? "—"}`,
      formatNumber(values.bytes_received_per_frame), formatNumber(values.socket_received_bytes, 0),
      formatNumber(values.source_payload_mbit_s, 4), formatNumber(values.bandwidth_mbit_s, 4),
      formatNumber(values.fps), formatNumber(values.e2e_ms_p95 ?? values.command_response_latency_p95_ms),
      values.missing_responses, saving == null ? "—" : `${formatNumber(saving)} %`];
    for (const value of fields) {
      const cell = document.createElement("td");
      cell.textContent = value == null ? "—" : String(value);
      row.append(cell);
    }
    rows.append(row);
  };
  const experiments = report.experiments || (report.modes ? [{camera_streams: 1, modes: report.modes, comparison: report.comparison}] : []);
  for (const experiment of experiments) {
    for (const [mode, values] of Object.entries(experiment.modes || {})) {
      const saving = experiment.comparison?.per_frame_bytes_saved_percent;
      appendRow(experiment, mode, values, saving);
    }
  }
  if (report.active_stage && report.live) appendRow(report.live, `${report.live.mode} (live)`, report.live);
  byId("measurement-rows").replaceChildren(rows);
  setText("measurement-limits", (report.limits || []).join(" ") || "No completed timed measurements.");
}

function renderLiveMeasurement(report) {
  if (report.source !== "E07_PHYSICAL" || !report.live) return false;
  const live = report.live;
  const identity = report.identity || {};
  latencyUnit = "response ms";
  transferUnit = "response Mbit/s";
  setText("latency-label", "Mean response latency");
  setText("latency-unit", "PC clock; input + edge + response");
  setText("sample-label", "Verified replay responses");
  setText("model", identity.model);
  setText("endpoint", identity.board_ip ? `${identity.board_ip}:${identity.tcp_port}` : null);
  setText("firmware", identity.firmware_sha256);
  setText("session-id", report.session_id);
  renderArtifacts(identity.artifact_hashes);
  setText("latest-update", `Updated ${live.updated_at} · trial ${live.trial} · ${live.mode} · ${live.load_mode}`);
  setText("sample-count", formatNumber(live.frames_received, 0));
  setText("completed-frames", formatNumber(live.frames_received, 0));
  setText("fps", formatNumber(live.fps));
  setText("latency", formatNumber(live.e2e_ms_mean, 3));
  setText("power", formatScaled(live.telemetry?.power_uW, 1e6, "W"));
  setText("energy", formatScaled(live.monitored_system_energy_J, 1, "J"));
  setText("temperature", formatScaled(live.telemetry?.temperature_mC, 1000, "°C", 2));
  const latest = (report.experiments || []).at(-1);
  setText("full-bytes", formatNumber(latest?.modes?.full?.socket_received_bytes ??
    (live.mode === "full" ? live.socket_received_bytes : null), 0));
  setText("compact-bytes", formatNumber(latest?.modes?.compact?.socket_received_bytes ??
    (live.mode === "compact" ? live.socket_received_bytes : null), 0));
  const saving = latest?.comparison?.per_frame_bytes_saved_percent;
  setText("reduction", saving == null ? "—" : `${formatNumber(saving, 4)} %`);
  renderErrors({error_count: report.failure ? 1 : 0,
    recent_errors: report.failure ? [{code: report.status, detail: report.failure}] : []});
  history.length = 0;
  for (const point of report.live_history?.length ? report.live_history : [live]) {
    history.push({timestamp: point.updated_at, latency: point.e2e_ms_mean, fps: point.fps,
      fullBytes: point.mode === "full" ? point.bandwidth_mbit_s : null,
      compactBytes: point.mode === "compact" ? point.bandwidth_mbit_s : null,
      reduction: null, powerW: point.telemetry?.power_uW == null ? null : point.telemetry.power_uW / 1e6,
      energyJ: point.monitored_system_energy_J,
      temperatureC: point.telemetry?.temperature_mC == null ? null : point.telemetry.temperature_mC / 1000});
  }
  renderCharts();
  setText("poll-message", `${report.status} · ${live.camera_streams} multiplexed streams · ${live.mode} · ${live.load_mode}`);
  return true;
}

async function poll() {
  if (pollInFlight) return;
  pollInFlight = true;
  try {
    const [health, listing, measurements] = await Promise.all([
      getJson("/api/health"), getJson("/api/sessions"), getJson("/api/measurements/latest")]);
    renderMeasurements(measurements);
    updateBadges(health);
    const sessions = Array.isArray(listing.sessions) ? listing.sessions : [];
    if (renderLiveMeasurement(measurements)) {
      // All E07 metric cards and charts use the same atomic report snapshot.
    } else if (!sessions.length) {
      setText("poll-message", "Waiting for a board session…");
      renderCharts();
    } else {
      const nextSession = sessions[0].session_id;
      if (selectedSession !== nextSession) {
        selectedSession = nextSession;
        history.length = 0;
      }
      const detail = await getJson(`/api/sessions/${encodeURIComponent(selectedSession)}`);
      renderDetail(detail);
      setText("poll-message", "Local evidence view synchronized");
    }
    const age = Date.now() - Date.parse(measurements.live?.updated_at);
    if (measurements.status === "RUNNING" && Number.isFinite(age) && age > 10000) {
      showStale("no measurement progress for more than 10 seconds; inspect collector / transaction timeout");
    } else {
      byId("stale-badge").classList.add("is-hidden");
    }
  } catch (error) {
    showStale(error instanceof Error ? error.message : "poll failed");
  } finally {
    pollInFlight = false;
  }
}

poll();
window.setInterval(poll, POLL_MS);
