/* ── Team Intelligence · graph.js ───────────────────────────────── */

const GROUP_COLOR = {
  1:  "#6366f1",  // person
  21: "#3b82f6",  // email
  22: "#8b5cf6",  // meeting
  23: "#10b981",  // word/policy/sas
  24: "#f59e0b",  // other docs
  3:  "#64748b",  // topic
  4:  "#94a3b8",  // phase
  5:  "#22c55e",  // team
};

// finer file-type override
const FT_COLOR = {
  email:           "#3b82f6",
  meeting_minutes: "#8b5cf6",
  word_doc:        "#10b981",
  policy_doc:      "#f59e0b",
  sas_script:      "#ef4444",
  excel:           "#22c55e",
  csv:             "#14b8a6",
  log_file:        "#64748b",
  powerpoint:      "#f97316",
};

let graphState = {
  loaded:   false,
  mode:     "people",
  sim:      null,
  svg:      null,
  zoom:     null,
};

// ── Entry point ───────────────────────────────────────────────────
function initGraph() {
  if (graphState.loaded) return;

  bindGraphControls();
  fetchAndRender("people");
}

function bindGraphControls() {
  document.querySelectorAll(".mode-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.mode === graphState.mode && graphState.loaded) return;
      document.querySelectorAll(".mode-pill").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      fetchAndRender(btn.dataset.mode);
    });
  });

  document.getElementById("graphReset").addEventListener("click", resetZoom);
}

// ── Data fetch ────────────────────────────────────────────────────
async function fetchAndRender(mode) {
  graphState.mode   = mode;
  graphState.loaded = false;

  showGraphLoading(true);
  clearSvg();

  try {
    const r    = await fetch(`/api/graph/d3?mode=${mode}`);
    const data = await r.json();
    showGraphLoading(false);
    renderGraph(data.nodes || [], data.links || []);
    graphState.loaded = true;
  } catch (err) {
    showGraphLoading(false);
    showGraphError(err.message);
  }
}

function showGraphLoading(on) {
  document.getElementById("graphLoading").style.display = on ? "flex" : "none";
}

function clearSvg() {
  const svg = document.getElementById("graphSvg");
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}

function showGraphError(msg) {
  const svg = document.getElementById("graphSvg");
  const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
  text.setAttribute("x", "50%");
  text.setAttribute("y", "50%");
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("fill", "#8b949e");
  text.setAttribute("font-size", "14");
  text.textContent = `Graph error: ${msg}`;
  svg.appendChild(text);
}

// ── D3 render ─────────────────────────────────────────────────────
function renderGraph(nodes, links) {
  const container = document.getElementById("graphContainer");
  const W = container.clientWidth;
  const H = container.clientHeight;

  const svg = d3.select("#graphSvg")
    .attr("width",  W)
    .attr("height", H);

  // Arrow markers
  const defs = svg.append("defs");
  const markerColors = ["#58a6ff", "#8b949e"];
  markerColors.forEach((col, i) => {
    defs.append("marker")
      .attr("id",          `arrow-${i}`)
      .attr("viewBox",     "0 -4 8 8")
      .attr("refX",        16)
      .attr("refY",        0)
      .attr("markerWidth", 6)
      .attr("markerHeight",6)
      .attr("orient",      "auto")
      .append("path")
        .attr("d",    "M0,-4L8,0L0,4")
        .attr("fill", col);
  });

  const g = svg.append("g");

  // Zoom
  const zoom = d3.zoom()
    .scaleExtent([.05, 4])
    .on("zoom", e => g.attr("transform", e.transform));
  svg.call(zoom);
  graphState.zoom = zoom;
  graphState.svg  = svg;

  // Build link map for quick lookup
  const linkMap = new Map();
  links.forEach(l => {
    const key = `${l.source}→${l.target}`;
    if (!linkMap.has(key)) linkMap.set(key, l);
  });
  const dedupedLinks = [...linkMap.values()];

  // Simulation
  const sim = d3.forceSimulation(nodes)
    .force("link",   d3.forceLink(dedupedLinks).id(d => d.id).distance(d => linkDist(d)).strength(.4))
    .force("charge", d3.forceManyBody().strength(d => chargeStrength(d)))
    .force("center", d3.forceCenter(W / 2, H / 2))
    .force("collide", d3.forceCollide().radius(d => nodeRadius(d) + 4));

  graphState.sim = sim;

  // Links
  const linkSel = g.append("g").attr("class", "links")
    .selectAll("line")
    .data(dedupedLinks)
    .join("line")
      .attr("stroke",       d => edgeColor(d))
      .attr("stroke-width", d => edgeWidth(d))
      .attr("stroke-opacity", .55)
      .attr("marker-end",   d => isPrimary(d) ? "url(#arrow-0)" : "url(#arrow-1)");

  // Nodes
  const nodeSel = g.append("g").attr("class", "nodes")
    .selectAll("g")
    .data(nodes)
    .join("g")
      .attr("class", "node")
      .call(drag(sim))
      .on("mouseover", onNodeOver)
      .on("mousemove", onNodeMove)
      .on("mouseout",  onNodeOut);

  nodeSel.append("circle")
    .attr("r",    d => nodeRadius(d))
    .attr("fill", d => nodeColor(d))
    .attr("fill-opacity", d => d.type === "topic" || d.type === "phase" ? .7 : .95)
    .attr("stroke",       d => d.type === "person" ? "#fff" : "rgba(255,255,255,.2)")
    .attr("stroke-width", d => d.type === "person" ? 2 : 1);

  // Labels for person + team
  nodeSel.filter(d => d.type === "person" || d.type === "team")
    .append("text")
      .attr("dy",          ".35em")
      .attr("text-anchor", "middle")
      .attr("font-size",   d => d.type === "person" ? 10 : 9)
      .attr("font-weight", d => d.type === "person" ? "600" : "400")
      .attr("fill",        "#e6edf3")
      .attr("pointer-events", "none")
      .text(d => shortLabel(d));

  sim.on("tick", () => {
    linkSel
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    nodeSel.attr("transform", d => `translate(${d.x},${d.y})`);
  });

  // Initial zoom-to-fit after a short warm-up
  setTimeout(() => zoomToFit(svg, g, zoom, W, H), 1800);
}

// ── Styling helpers ───────────────────────────────────────────────
function nodeRadius(d) {
  if (d.type === "person") return 16 + Math.min((d.size || 1) * .4, 8);
  if (d.type === "team")   return 14;
  if (d.type === "topic")  return 7;
  if (d.type === "phase")  return 6;
  return 8 + Math.min((d.size || 1) * .3, 6); // document
}

function nodeColor(d) {
  if (d.type === "person") return "#6366f1";
  if (d.type === "team")   return "#22c55e";
  if (d.type === "topic")  return "#64748b";
  if (d.type === "phase")  return "#94a3b8";
  // document — use file_type from meta
  const ft = d.meta?.file_type;
  return FT_COLOR[ft] || GROUP_COLOR[d.group] || "#58a6ff";
}

function chargeStrength(d) {
  if (d.type === "person") return -200;
  if (d.type === "team")   return -180;
  if (d.type === "topic")  return -60;
  if (d.type === "phase")  return -40;
  return -80;
}

function linkDist(d) {
  const rel = d.rel || "";
  if (rel === "AUTHORED" || rel === "CONTRIBUTED_TO") return 90;
  if (rel === "MANAGES"  || rel === "REPORTS_TO")     return 70;
  if (rel === "MEMBER_OF"|| rel === "LEADS")           return 80;
  if (rel === "TAGGED_WITH" || rel === "IN_PHASE")    return 50;
  return 110;
}

function edgeColor(d) {
  const rel = d.rel || "";
  if (rel === "AUTHORED" || rel === "CONTRIBUTED_TO") return "#3b82f6";
  if (rel === "MANAGES"  || rel === "REPORTS_TO")     return "#22c55e";
  if (rel === "MEMBER_OF"|| rel === "LEADS")           return "#f59e0b";
  if (rel === "REFERENCES"|| rel === "TRIGGERED")      return "#58a6ff";
  if (rel === "SUPERSEDES")                            return "#ef4444";
  if (rel === "APPROVED")                              return "#10b981";
  if (rel === "EXPERT_IN")                             return "#8b5cf6";
  return "#30363d";
}

function edgeWidth(d) {
  const rel = d.rel || "";
  if (rel === "AUTHORED" || rel === "MANAGES" || rel === "LEADS") return 1.5;
  return 1;
}

function isPrimary(d) {
  const rel = d.rel || "";
  return ["AUTHORED","MANAGES","LEADS","REFERENCES","SUPERSEDES","APPROVED"].includes(rel);
}

function shortLabel(d) {
  const lbl = d.label || d.id || "";
  // First name only for persons
  if (d.type === "person") return lbl.split(" ")[0];
  // Team: short name
  if (d.type === "team")   return lbl.replace(/team/i, "").trim().slice(0, 12);
  return lbl.slice(0, 12);
}

// ── Drag ─────────────────────────────────────────────────────────
function drag(sim) {
  return d3.drag()
    .on("start", (e, d) => {
      if (!e.active) sim.alphaTarget(.3).restart();
      d.fx = d.x; d.fy = d.y;
    })
    .on("drag", (e, d) => {
      d.fx = e.x; d.fy = e.y;
    })
    .on("end", (e, d) => {
      if (!e.active) sim.alphaTarget(0);
      d.fx = null; d.fy = null;
    });
}

// ── Tooltip ───────────────────────────────────────────────────────
function onNodeOver(event, d) {
  const tip = document.getElementById("nodeTooltip");
  const meta = d.meta || {};

  let html = `<div class="tooltip-id">${d.label || d.id}</div>`;
  html += `<div class="tooltip-type">${d.type || ""}</div>`;

  const lines = [];
  if (meta.file_type)   lines.push(`Type: ${meta.file_type.replace(/_/g, " ")}`);
  if (meta.event_date)  lines.push(`Date: ${meta.event_date}`);
  if (meta.author)      lines.push(`Author: ${meta.author}`);
  if (meta.title)       lines.push(meta.title);
  if (meta.scope)       lines.push(meta.scope.slice(0, 80) + (meta.scope.length > 80 ? "…" : ""));
  if (d.size != null)   lines.push(`Connections: ${d.size}`);

  if (lines.length) {
    html += `<div class="tooltip-meta">${lines.join("<br>")}</div>`;
  }

  tip.innerHTML = html;
  tip.style.display = "block";
  positionTooltip(event, tip);
}

function onNodeMove(event) {
  const tip = document.getElementById("nodeTooltip");
  positionTooltip(event, tip);
}

function onNodeOut() {
  document.getElementById("nodeTooltip").style.display = "none";
}

function positionTooltip(event, tip) {
  const pad = 14;
  let x = event.clientX + pad;
  let y = event.clientY + pad;
  if (x + 270 > window.innerWidth)  x = event.clientX - 270 - pad;
  if (y + 200 > window.innerHeight) y = event.clientY - 200 - pad;
  tip.style.left = x + "px";
  tip.style.top  = y + "px";
}

// ── Zoom helpers ──────────────────────────────────────────────────
function zoomToFit(svg, g, zoom, W, H) {
  try {
    const box    = g.node().getBBox();
    if (!box.width || !box.height) return;
    const scale  = Math.min(.9, .9 * Math.min(W / box.width, H / box.height));
    const tx     = (W - scale * (box.x * 2 + box.width))  / 2;
    const ty     = (H - scale * (box.y * 2 + box.height)) / 2;
    svg.transition().duration(700)
      .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  } catch { /* bounding box unavailable */ }
}

function resetZoom() {
  if (!graphState.svg || !graphState.zoom) return;
  const container = document.getElementById("graphContainer");
  const W = container.clientWidth;
  const H = container.clientHeight;
  const g = graphState.svg.select("g");
  zoomToFit(graphState.svg, g, graphState.zoom, W, H);
}
