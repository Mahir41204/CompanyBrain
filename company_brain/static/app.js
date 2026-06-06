const state = {
  dashboard: null,
  peopleRisk: null,
  graph: null,
  people: null,
  processes: null,
  coverage: null,
  risks: null,
  evidence: null,
  sources: null,
  selectedNode: null,
  graphFilter: "all",
  timeFilter: "Today",
  highlightEdges: [],
  simulation: null
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function pct(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function percentNumber(value) {
  return Math.round(Number(value || 0) * 100);
}

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value || 0);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;"
  }[char]));
}

function setOnline(ok, text) {
  $("connectionStatus").textContent = text;
  document.querySelector(".status-dot").classList.toggle("online", ok);
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  $(`${view}View`).classList.add("active");
  document.querySelector(`[data-view="${view}"]`).classList.add("active");
}

function severityClass(value) {
  const normalized = String(value || "medium").toLowerCase();
  if (["critical", "high", "expired", "error"].includes(normalized)) return "high";
  if (["medium", "stale", "syncing", "aging"].includes(normalized)) return "medium";
  return "low";
}

function renderKpis(id, items) {
  $(id).innerHTML = items.map((item) => `
    <article class="kpi">
      <div class="label">${escapeHtml(item.label)}</div>
      <div class="kpi-value">${escapeHtml(item.value)}</div>
      <div class="delta ${item.cls || ""}">${escapeHtml(item.detail || "")}</div>
    </article>
  `).join("");
}

function chips(rows, label = "name") {
  const list = rows || [];
  return list.length ? `
    <div class="chip-row">
      ${list.map((row) => `<span class="pill">${escapeHtml(row[label] || row.name || row.id || row)}</span>`).join("")}
    </div>
  ` : `<div class="row-meta">None mapped</div>`;
}

function entityChips(rows) {
  const list = rows || [];
  return list.length ? list.map((row) => `<span class="pill">${escapeHtml(row.name || row.id || row)}</span>`).join("") : `<span class="row-meta">None mapped</span>`;
}

function riskText(value) {
  const text = String(value || "unknown");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function renderRows(id, rows, renderer) {
  const list = rows || [];
  $(id).innerHTML = list.length ? list.map((row) => `<div class="row">${renderer(row)}</div>`).join("") : `<div class="row-meta">No items</div>`;
}

async function loadOverview() {
  state.dashboard = await api("/brain/dashboard");
  renderOverview();
}

async function loadPeopleRisk(target = null) {
  const selectedTarget = target || $("peopleRiskTarget")?.value || "";
  const suffix = selectedTarget ? `?target=${encodeURIComponent(selectedTarget)}` : "";
  state.peopleRisk = await api(`/brain/people-risk${suffix}`);
  renderPeopleRisk();
}

function renderPeopleRisk() {
  const data = state.peopleRisk;
  if (!data) return;
  const selected = data.selected_person;
  const simulation = data.departure_simulation;
  const targetName = selected?.name || data.positioning.buyer_question.replace("What breaks if ", "").replace(" leaves?", "");
  const options = data.top_people.map((row) => `<option value="${escapeHtml(row.name)}">${escapeHtml(row.name)} - ${escapeHtml(row.role)}</option>`).join("");
  if ($("peopleRiskTarget").innerHTML !== options) {
    $("peopleRiskTarget").innerHTML = options;
  }
  if (targetName) $("peopleRiskTarget").value = targetName;

  $("peopleRiskQuestion").textContent = data.positioning.buyer_question;
  $("peopleRiskNarrative").textContent = selected
    ? `${selected.role} controls ${selected.controlled_processes.length} critical workflows with ${selected.evidence_count} source-backed proof points. ${selected.backup_status}.`
    : data.positioning.why_now;

  const mitigated = simulation.mitigated_resilience?.after ?? simulation.resilience.after;
  $("departureSnapshot").innerHTML = `
    <div class="snapshot-item danger">
      <span>Departure risk</span>
      <strong>${riskText(simulation.risk)}</strong>
    </div>
    <div class="snapshot-item">
      <span>Monthly exposure</span>
      <strong>${money(simulation.monthly_cost.monthly_estimate)}</strong>
    </div>
    <div class="snapshot-item">
      <span>Affected processes</span>
      <strong>${simulation.affected.processes.length}</strong>
    </div>
    <div class="snapshot-item">
      <span>Resilience lift</span>
      <strong>+${Math.max(0, mitigated - simulation.resilience.after)}</strong>
    </div>
  `;

  renderRows("peopleRiskControlPlan", data.control_plan, (row) => `
    <div class="row-title"><span>${escapeHtml(row.action)}</span><span class="pill ${severityClass(row.priority)}">${escapeHtml(row.priority)}</span></div>
    <div class="row-meta">${escapeHtml(row.target)} - ${escapeHtml(row.reason)}</div>
  `);

  $("peopleRiskEvidenceLabel").textContent = `${data.proof_points.length} sources`;
  $("peopleRiskProof").innerHTML = data.proof_points.length ? data.proof_points.map((item) => `
    <article class="evidence-card">
      <strong>${escapeHtml(item.source_type)} - ${escapeHtml(item.source_ref)}</strong>
      <div class="row-meta">confidence ${percentNumber(item.confidence)}%</div>
      <div>${escapeHtml(item.text)}</div>
    </article>
  `).join("") : `<div class="row-meta">No evidence attached</div>`;
  if (state.dashboard) renderOverview();
}

function renderOverview() {
  const data = state.dashboard;
  const kpis = data.kpis;
  const peopleRisk = state.peopleRisk;
  const departure = peopleRisk?.departure_simulation;
  $("overviewSubtitle").textContent = `Live graph: ${kpis.nodes} nodes, ${kpis.relations} relations, ${peopleRisk?.summary.high_risk_people || 0} high-risk people`;
  renderKpis("overviewKpis", [
    {
      label: "Departure Risk",
      value: departure ? riskText(departure.risk) : `${kpis.knowledge_risk_score.value}/100`,
      detail: peopleRisk?.positioning.buyer_question || kpis.knowledge_risk_score.trend_note,
      cls: departure?.risk === "critical" || departure?.risk === "high" ? "bad" : "warn"
    },
    { label: "Monthly Exposure", value: departure ? money(departure.monthly_cost.monthly_estimate) : "Pending", detail: "Scenario estimate", cls: "warn" },
    { label: "Affected Workflows", value: departure ? departure.affected.processes.length : 0, detail: "Graph-derived blast radius" },
    { label: "High-Risk People", value: peopleRisk?.summary.high_risk_people || 0, detail: `${peopleRisk?.summary.people_mapped || 0} people mapped` },
    { label: "Evidence Confidence", value: departure ? pct(departure.confidence.overall) : pct(kpis.average_confidence), detail: "Dependency confidence" }
  ]);

  renderTrend(data.coverage_trend);
  renderDrilldown(data.coverage_drilldown);
  renderConfidence(kpis.average_confidence, data);
  renderRows("topRisks", data.organizational_health.top_risks, (row) => `
    <div class="row-title"><span>${escapeHtml(row.title)}</span><span class="pill ${severityClass(row.severity)}">${escapeHtml(row.severity)}</span></div>
    <div class="row-meta">${escapeHtml(row.detail)}</div>
  `);
  renderRows("topBottlenecks", data.top_bottlenecks, (row) => `
    <div class="row-title"><span>${escapeHtml(row.entity.name)}</span><span class="pill ${severityClass(row.criticality >= 75 ? "high" : "medium")}">${row.criticality}</span></div>
    <div class="row-meta">${row.dependency_count} mapped dependencies - ${escapeHtml(row.entity.type)}</div>
  `);
  renderRows("recommendedActions", data.recommended_actions, (row) => `
    <div class="row-title"><span>${escapeHtml(row.action)}</span><span class="pill ${severityClass(row.priority)}">${escapeHtml(row.priority)}</span></div>
    <div class="row-meta">${escapeHtml(row.target)} - ${escapeHtml(row.reason)}</div>
  `);
  renderGaps(data.gaps);
}

function renderTrend(trend) {
  if (!trend || !trend.available) {
    $("coverageTrendLabel").textContent = trend?.message || "Insufficient historical data.";
    $("coverageTrend").innerHTML = `<div class="row-meta">Insufficient historical data.</div>`;
    return;
  }
  const rows = trend.points || [];
  const max = Math.max(...rows.map((row) => row.value), 100);
  const points = rows.map((row, index) => {
    const x = 30 + index * (420 / Math.max(rows.length - 1, 1));
    const y = 125 - (row.value / max) * 100;
    return { ...row, x, y };
  });
  $("coverageTrendLabel").textContent = trend.message;
  $("coverageTrend").innerHTML = `
    <svg viewBox="0 0 500 150" aria-label="Coverage trend chart">
      <polyline points="${points.map((p) => `${p.x},${p.y}`).join(" ")}" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
      ${points.map((p) => `
        <circle cx="${p.x}" cy="${p.y}" r="5" fill="var(--accent)"></circle>
        <text x="${p.x}" y="${p.y - 12}" text-anchor="middle" font-size="12" fill="var(--ink)" font-weight="700">${p.value}%</text>
        <text x="${p.x}" y="145" text-anchor="middle" font-size="11" fill="var(--muted)">${p.label}</text>
      `).join("")}
    </svg>
  `;
}

function renderDrilldown(rows) {
  $("coverageDrilldown").innerHTML = (rows || []).map((row) => `
    <div class="drill">
      <div class="row-title"><span>${escapeHtml(row.label)}</span><span>${row.percent}%</span></div>
      <div class="row-meta">${row.value} of ${row.total}</div>
      <div class="bar"><span style="width:${row.percent}%"></span></div>
    </div>
  `).join("");
}

function renderConfidence(confidence, data) {
  const angle = Math.round(confidence * 360);
  $("confidenceRing").style.setProperty("--angle", `${angle}deg`);
  $("confidenceRing").innerHTML = `<span>${percentNumber(confidence)}%</span>`;
  $("healthSummary").innerHTML = [
    ["Average graph confidence", `${percentNumber(confidence)}%`],
    ["Open conflicts", data.kpis.conflicts],
    ["Recommended actions", data.recommended_actions.length]
  ].map(([label, value]) => `<div class="row"><div class="row-title"><span>${label}</span><span>${value}</span></div></div>`).join("");
}

function renderGaps(rows) {
  $("gapTable").innerHTML = (rows || []).map((gap) => `
    <div class="gap-row">
      <strong>${escapeHtml(gap.title)}</strong>
      <span class="pill ${severityClass(gap.estimated_risk)}">${escapeHtml(gap.estimated_risk)}</span>
      <span>${escapeHtml((gap.affected_teams || []).join(", ") || "No team mapped")}</span>
      <span>${escapeHtml((gap.affected_processes || []).join(", ") || "No process mapped")}</span>
      <span>${gap.impact_score}/100 - ${escapeHtml(gap.recommended_action)}</span>
    </div>
  `).join("");
}

async function loadGraph() {
  state.graph = await api("/brain/graph/view");
  state.selectedNode = state.graph.nodes[0] || null;
  renderGraph();
}

function renderGraph() {
  renderGraphFilters();
  renderTimeTravel();
  renderGraphSvg();
  renderInspector(state.selectedNode);
}

function renderGraphFilters() {
  const filters = ["all", "people", "process", "policy", "tool", "conflict", "high-risk"];
  $("graphFilters").innerHTML = filters.map((filter) => `
    <button class="filter-chip ${state.graphFilter === filter ? "active" : ""}" data-filter="${filter}">${filter}</button>
  `).join("");
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.graphFilter = button.dataset.filter;
      renderGraph();
    });
  });
}

function renderTimeTravel() {
  $("timeTravel").innerHTML = state.graph.timeline.map((item) => `
    <button class="time-chip ${state.timeFilter === item.label ? "active" : ""}" data-time="${item.label}">${item.label}</button>
  `).join("");
  document.querySelectorAll("[data-time]").forEach((button) => {
    button.addEventListener("click", () => {
      state.timeFilter = button.dataset.time;
      renderGraphSvg();
    });
  });
}

function visibleNodes() {
  const query = $("graphSearch").value.trim().toLowerCase();
  return state.graph.nodes.filter((node) => {
    const typeMatch =
      state.graphFilter === "all" ||
      node.type === state.graphFilter ||
      (state.graphFilter === "people" && ["person", "team"].includes(node.type)) ||
      (state.graphFilter === "conflict" && node.has_conflict) ||
      (state.graphFilter === "high-risk" && node.criticality_label === "high");
    const queryMatch = !query || `${node.name} ${node.id} ${node.type}`.toLowerCase().includes(query);
    return typeMatch && queryMatch;
  });
}

function nodeColor(node) {
  if (node.has_conflict) return "var(--red)";
  if (node.criticality_label === "high") return "var(--amber)";
  if (node.type === "policy") return "#d85a30";
  if (node.type === "tool") return "#b36d12";
  if (["person", "team"].includes(node.type)) return "var(--green)";
  if (node.type === "skill") return "var(--blue)";
  return "var(--accent)";
}

function renderGraphSvg() {
  const nodes = visibleNodes();
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = state.graph.edges.filter((edge) => nodeIds.has(edge.source_id) && nodeIds.has(edge.target_id));
  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const highlight = new Set(state.highlightEdges || []);
  $("graphSvg").innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 Z" fill="#a8a39a"></path>
      </marker>
    </defs>
    ${edges.map((edge) => {
      const source = byId[edge.source_id];
      const target = byId[edge.target_id];
      if (!source || !target) return "";
      const isHot = highlight.has(edge.id);
      const width = Math.max(1, edge.strength / 32);
      return `
        <line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" stroke="${isHot ? "var(--red)" : "#a8a39a"}" stroke-width="${isHot ? width + 1.5 : width}" opacity="${Math.max(0.25, edge.strength / 100)}" marker-end="url(#arrow)"></line>
        <text class="edge-label" x="${(source.x + target.x) / 2}" y="${(source.y + target.y) / 2 - 4}" text-anchor="middle">${edge.relation} (${edge.strength}%)</text>
      `;
    }).join("")}
    ${nodes.map((node) => `
      <g class="graph-node" data-node="${node.id}" opacity="${Math.max(0.45, node.confidence)}">
        <circle cx="${node.x}" cy="${node.y}" r="${node.criticality_label === "high" ? 28 : 23}" fill="${nodeColor(node)}" stroke="${node.criticality_label === "high" ? "var(--red)" : "white"}" stroke-width="${node.criticality_label === "high" ? 4 : 2}"></circle>
        <text x="${node.x}" y="${node.y + 4}" text-anchor="middle" fill="white">${escapeHtml(node.name).slice(0, 14)}</text>
      </g>
    `).join("")}
  `;
  document.querySelectorAll("[data-node]").forEach((nodeEl) => {
    nodeEl.addEventListener("click", () => {
      state.selectedNode = state.graph.nodes.find((node) => node.id === nodeEl.dataset.node);
      renderInspector(state.selectedNode);
    });
  });
}

function renderInspector(node) {
  if (!node) {
    $("nodeInspector").innerHTML = `<div class="row-meta">No node selected</div>`;
    $("evidenceViewer").innerHTML = "";
    return;
  }
  $("selectedNodeType").textContent = node.type;
  $("nodeInspector").innerHTML = `
    <div class="row">
      <div class="row-title"><span>${escapeHtml(node.name)}</span><span class="pill ${severityClass(node.criticality_label)}">${node.criticality_label}</span></div>
      <div class="row-meta">${node.type} - confidence ${percentNumber(node.confidence)}% - criticality ${node.criticality}/100</div>
      <div class="bar"><span style="width:${percentNumber(node.confidence)}%;background:var(--green)"></span></div>
    </div>
    <div class="row">
      <div class="row-title"><span>Relationship count</span><span>${node.degree}</span></div>
      <div class="row-meta">${node.has_conflict ? "Policy conflict present" : "No conflict flag"}</div>
    </div>
  `;
  const evidence = node.evidence || [];
  $("evidenceCount").textContent = `${evidence.length} sources`;
  $("evidenceViewer").innerHTML = evidence.length ? evidence.map((item) => `
    <article class="evidence-card">
      <strong>${escapeHtml(item.source_type)} - ${escapeHtml(item.source_ref)}</strong>
      <div class="row-meta">${escapeHtml(item.timestamp)} - confidence ${percentNumber(item.confidence)}%</div>
      <div>${escapeHtml(item.text).slice(0, 260)}</div>
    </article>
  `).join("") : `<div class="row-meta">No evidence attached</div>`;
}

function findNode(value) {
  const q = value.trim().toLowerCase();
  return state.graph.nodes.find((node) => node.id.toLowerCase() === q || node.name.toLowerCase().includes(q));
}

async function runPathSearch() {
  const source = findNode($("pathFrom").value);
  const target = findNode($("pathTo").value);
  if (!source || !target) return;
  const result = await api(`/brain/graph/path?from=${encodeURIComponent(source.id)}&to=${encodeURIComponent(target.id)}`);
  state.highlightEdges = result.path ? result.path.edges.map((edge) => edge.id) : [];
  renderGraphSvg();
}

async function loadPeople() {
  state.people = await api("/brain/people");
  renderPeople();
}

function renderPeople() {
  const data = state.people;
  const riskRows = Object.fromEntries((state.peopleRisk?.top_people || []).map((row) => [row.id, row]));
  renderKpis("peopleKpis", [
    { label: "People", value: data.summary.people, detail: "Mapped individuals" },
    { label: "Teams", value: data.summary.teams, detail: "Mapped teams" },
    { label: "Top Concentration", value: data.summary.top_concentration?.tribal_knowledge_score || 0, detail: data.summary.top_concentration?.name || "No data" },
    { label: "Rows", value: data.people_and_teams.length, detail: "Ownership candidates" }
  ]);
  $("peopleList").innerHTML = data.people_and_teams.map((row) => `
    <article class="data-card">
      <div class="row-title"><h3>${escapeHtml(row.name)}</h3><span class="pill ${severityClass(row.risk_label)}">${row.tribal_knowledge_score}/100</span></div>
      <div class="row-meta">${row.type} - confidence ${percentNumber(row.confidence)}% - ${row.evidence.length} evidence items${riskRows[row.id] ? ` - ${escapeHtml(riskRows[row.id].backup_status)}` : ""}</div>
      <div class="row-meta">Owns</div>${chips(row.owns)}
      <div class="row-meta">Approvals</div>${chips(row.approvals)}
      <div class="row-meta">Escalations</div>${chips(row.escalations)}
    </article>
  `).join("");
}

async function loadProcesses() {
  state.processes = await api("/brain/processes");
  renderProcesses();
}

function renderProcesses() {
  const data = state.processes;
  renderKpis("processKpis", [
    { label: "Processes", value: data.summary.count, detail: "Documented in memory graph" },
    { label: "Owners Known", value: data.summary.with_owner, detail: "Owner or approver mapped" },
    { label: "Steps Known", value: data.summary.with_steps, detail: "Extracted steps" },
    { label: "With Evidence", value: data.summary.with_evidence, detail: "Source-backed processes" }
  ]);
  $("processList").innerHTML = data.processes.map((row) => `
    <article class="data-card">
      <div class="row-title"><h3>${escapeHtml(row.name)}</h3><span class="pill ${severityClass(row.risk_score >= 70 ? "high" : row.risk_score >= 45 ? "medium" : "low")}">${row.risk_score}/100</span></div>
      <div class="row-meta">Owner: ${escapeHtml(row.owner?.name || "Unknown")} - confidence ${percentNumber(row.confidence)}% - ${row.evidence.length} evidence items</div>
      <div class="row-meta">Steps</div>${chips(row.steps)}
      <div class="row-meta">Tools</div>${chips(row.tools)}
      <div class="row-meta">Policies</div>${chips(row.policies)}
      <div class="row-meta">Exceptions</div>${chips(row.exceptions)}
    </article>
  `).join("");
}

async function loadCoverage() {
  state.coverage = await api("/brain/coverage/view");
  renderCoverage();
}

function renderCoverage() {
  const summary = state.coverage.summary;
  renderKpis("coverageKpis", [
    { label: "Skills", value: summary.total_skills, detail: `${summary.high_confidence_skills} high confidence` },
    { label: "Processes", value: summary.processes_documented, detail: "Documented" },
    { label: "Policies", value: summary.policies_mapped, detail: "Mapped" },
    { label: "Evidence", value: summary.evidence_items, detail: "Source records" }
  ]);
  $("coverageTable").innerHTML = state.coverage.processes.map((row) => `
    <div class="gap-row">
      <strong>${escapeHtml(row.name)}</strong>
      <span class="pill ${row.owner_known ? "fresh" : "high"}">${row.owner_known ? "owner" : "missing owner"}</span>
      <span>${row.dependencies_mapped ? "dependencies mapped" : "dependencies missing"}</span>
      <span>${row.evidence_count} evidence items</span>
      <span>${percentNumber(row.confidence)}%</span>
    </div>
  `).join("");
}

async function loadRisks() {
  state.risks = await api("/brain/risks");
  renderRisks();
}

function renderRisks() {
  const risk = state.risks.knowledge_risk_score;
  renderKpis("riskKpis", [
    { label: "Risk Score", value: `${risk.value}/100`, detail: risk.trend_note, cls: risk.value >= 75 ? "bad" : "warn" },
    { label: "Gaps", value: state.risks.gaps.length, detail: "Prioritized" },
    { label: "Conflicts", value: state.risks.top_policy_conflicts.length, detail: "Policy conflicts" },
    { label: "Actions", value: state.risks.recommended_actions.length, detail: "Recommended" }
  ]);
  renderRows("riskGaps", state.risks.gaps, (row) => `
    <div class="row-title"><span>${escapeHtml(row.title)}</span><span class="pill ${severityClass(row.estimated_risk)}">${escapeHtml(row.estimated_risk)}</span></div>
    <div class="row-meta">${row.impact_score}/100 - ${escapeHtml(row.recommended_action)}</div>
  `);
  renderRows("riskActions", state.risks.recommended_actions, (row) => `
    <div class="row-title"><span>${escapeHtml(row.action)}</span><span class="pill ${severityClass(row.priority)}">${escapeHtml(row.priority)}</span></div>
    <div class="row-meta">${escapeHtml(row.target)} - ${escapeHtml(row.reason)}</div>
  `);
}

async function loadEvidence() {
  const query = $("evidenceSearch")?.value.trim() || "";
  state.evidence = await api(`/brain/evidence${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  renderEvidence();
}

function renderEvidence() {
  const data = state.evidence;
  renderKpis("evidenceKpis", [
    { label: "Evidence", value: data.summary.count, detail: "Source records" },
    { label: "Confidence", value: pct(data.summary.average_confidence), detail: "Average evidence confidence" },
    { label: "Source Types", value: Object.keys(data.summary.sources).length, detail: "Distinct sources" },
    { label: "Insights", value: data.evidence.reduce((sum, row) => sum + row.insights.length, 0), detail: "LLM discovery outputs" }
  ]);
  $("evidenceList").innerHTML = data.evidence.map((row) => `
    <article class="data-card">
      <div class="row-title"><h3>${escapeHtml(row.source_ref)}</h3><span class="pill">${escapeHtml(row.source_type)}</span></div>
      <div class="row-meta">${escapeHtml(row.timestamp)} - confidence ${percentNumber(row.confidence)}% - ${row.entities.length} entities - ${row.relationships.length} relationships</div>
      <p>${escapeHtml(row.text)}</p>
      <div class="row-meta">Extracted entities</div>${chips(row.entities)}
      <div class="row-meta">Insights: ${row.insights.length}</div>
    </article>
  `).join("");
}

async function loadSources() {
  state.sources = await api("/brain/sources");
  renderSources();
}

function renderSources() {
  const data = state.sources;
  renderKpis("sourceKpis", [
    { label: "Connected", value: data.summary.connected, detail: "Active source connections" },
    { label: "Documents", value: data.summary.documents_processed, detail: "Processed by connectors" },
    { label: "Extracted", value: data.summary.knowledge_extracted, detail: "Entities and relationships" },
    { label: "Sources", value: data.sources.length, detail: "Tracked source systems" }
  ]);
  renderRows("sourceList", data.sources, (row) => `
    <div class="row-title"><span>${escapeHtml(row.source_type || row.id)}</span><span class="pill ${severityClass(row.status)}">${escapeHtml(row.status)}</span></div>
    <div class="row-meta">Last sync: ${escapeHtml(row.last_sync_at || "Never")} - docs ${row.documents_processed || 0} - extracted ${row.knowledge_extracted || 0}</div>
    <div class="row-meta">${row.auth_configured ? "Auth configured" : "Auth not configured"}${row.last_error ? ` - ${escapeHtml(row.last_error)}` : ""}</div>
  `);
}

async function loadSimulation(payload = null) {
  const body = payload || {
    type: $("scenarioType").value || "person_departure",
    target: $("scenarioTarget").value || "Sarah Kim",
    mitigations: selectedMitigations()
  };
  state.simulation = await api("/brain/simulation/run", {
    method: "POST",
    body: JSON.stringify(body)
  });
  renderSimulation();
}

function selectedMitigations() {
  return [...document.querySelectorAll("#mitigationList input:checked")].map((input) => input.value);
}

function renderSimulation() {
  const sim = state.simulation;
  renderScenarioControls(sim.library);
  $("scenarioType").value = sim.scenario.type;
  $("scenarioTarget").value = sim.scenario.target;
  const result = sim.result;
  const raw = result.raw;
  $("scenarioStatus").textContent = raw.risk;
  $("resiliencePanel").innerHTML = `
    ${scoreBar("Before", result.resilience.before)}
    ${scoreBar("After", result.resilience.after)}
    <div class="row-meta">Change: ${result.resilience.delta >= 0 ? "+" : ""}${result.resilience.delta} points - ${raw.blast_radius.transitive_affected} transitive dependencies</div>
  `;
  $("simulationConfidence").innerHTML = `
    ${scoreBar("Overall", percentNumber(result.confidence.overall))}
    <div class="row"><div class="row-title"><span>Evidence used</span><span>${result.confidence.evidence_used}</span></div></div>
    <div class="row"><div class="row-title"><span>Dependency strength</span><span>${result.confidence.dependency_strength}%</span></div></div>
    <div class="row-meta">${escapeHtml(result.confidence.why)}</div>
  `;
  renderBlastRadius(raw);
  renderFailurePaths(raw);
  $("costBreakdown").innerHTML = `
    <div class="kpi-value">${money(result.impact_cost_breakdown.monthly_estimate)}/mo</div>
    <div class="row-meta">${escapeHtml(result.impact_cost_breakdown.explanation)}</div>
    <div class="stack">
      <div class="row"><div class="row-title"><span>Ticket volume basis</span><span>${result.impact_cost_breakdown.ticket_volume_basis}</span></div></div>
      <div class="row"><div class="row-title"><span>CSAT drop</span><span>${result.impact_cost_breakdown.csat_drop_points} pts</span></div></div>
      <div class="row"><div class="row-title"><span>Historical churn component</span><span>${money(result.impact_cost_breakdown.historical_churn_component)}</span></div></div>
      <div class="row"><div class="row-title"><span>Productivity loss</span><span>${money(result.impact_cost_breakdown.productivity_loss_component)}</span></div></div>
    </div>
  `;
  $("simulationTimeline").innerHTML = result.timeline.map((item) => `
    <div class="time-card">
      <strong>${escapeHtml(item.time)}</strong>
      <div class="row-meta">${escapeHtml(item.severity)}</div>
      <div>${escapeHtml(item.event)}</div>
    </div>
  `).join("");
  $("simulationRecommendations").innerHTML = Object.entries(result.recommendations).map(([priority, rows]) => `
    <div class="rec-column ${priority}">
      <h3>${priority}</h3>
      <div class="stack">${rows.map((row) => `
        <div class="row">
          <div class="row-title"><span>${escapeHtml(row.action)}</span></div>
          <div class="row-meta">${escapeHtml(row.target)} - ${escapeHtml(row.reason)}</div>
        </div>
      `).join("") || `<div class="row-meta">No items</div>`}</div>
    </div>
  `).join("");
  renderComparison(sim);
}

function renderBlastRadius(raw) {
  $("blastRadius").innerHTML = `
    <div class="blast-grid">
      <div><span>Processes</span><strong>${raw.affected_processes?.length || 0}</strong></div>
      <div><span>Teams</span><strong>${raw.affected_teams?.length || 0}</strong></div>
      <div><span>Policies</span><strong>${raw.affected_policies?.length || 0}</strong></div>
      <div><span>Tools</span><strong>${raw.affected_tools?.length || 0}</strong></div>
    </div>
    <div class="row-meta">Direct neighbors: ${raw.blast_radius?.direct_neighbors || 0} - transitive affected: ${raw.blast_radius?.transitive_affected || 0}</div>
    <div class="chip-row">${entityChips(raw.affected_processes)}</div>
    <div class="chip-row">${entityChips(raw.affected_teams)}</div>
    <div class="chip-row">${entityChips(raw.affected_policies)}</div>
  `;
}

function renderFailurePaths(raw) {
  const paths = raw.propagation?.paths || [];
  $("failurePaths").innerHTML = paths.length ? paths.slice(0, 5).map((path) => {
    const chain = path.steps.map((step) => `${escapeHtml(step.relation)} -> ${escapeHtml(step.entity.name)}`).join(" / ");
    const confidence = Math.round(Math.min(...path.steps.map((step) => Number(step.confidence || 0.5))) * 100);
    return `
      <div class="row">
        <div class="row-title"><span>Depth ${path.depth}</span><span class="pill ${severityClass(confidence < 75 ? "medium" : "low")}">${confidence}%</span></div>
        <div class="row-meta">${chain}</div>
      </div>
    `;
  }).join("") : `<div class="row-meta">No propagation path found for this target.</div>`;
}

function scoreBar(label, value) {
  return `
    <div class="score-row">
      <strong>${label}</strong>
      <div class="bar"><span style="width:${Math.max(0, Math.min(100, value))}%;background:${value >= 70 ? "var(--green)" : value >= 45 ? "var(--amber)" : "var(--red)"}"></span></div>
      <span>${value}/100</span>
    </div>
  `;
}

function renderComparison(sim) {
  if (!sim.comparison) {
    $("scenarioComparison").innerHTML = `<div class="row-meta">Run mitigation comparison to populate Scenario B.</div>`;
    return;
  }
  $("scenarioComparison").innerHTML = `
    <div class="score-row"><strong>A</strong><div class="bar"><span style="width:${sim.result.resilience.after}%"></span></div><span>${sim.result.resilience.after}</span></div>
    <div class="score-row"><strong>B</strong><div class="bar"><span style="width:${sim.comparison.resilience.after}%;background:var(--green)"></span></div><span>${sim.comparison.resilience.after}</span></div>
    <div class="row-meta">Scenario B includes mitigation testing.</div>
  `;
}

function renderScenarioControls(library) {
  if ($("scenarioType").children.length) return;
  $("scenarioType").innerHTML = library.map((item) => `<option value="${escapeHtml(item.type)}">${escapeHtml(item.label)}</option>`).join("");
  $("scenarioLibrary").innerHTML = library.map((item) => `
    <button data-scenario="${escapeHtml(item.type)}" data-target="${escapeHtml(item.default_target)}">${escapeHtml(item.label)} - ${escapeHtml(item.default_target)}</button>
  `).join("");
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.addEventListener("click", () => {
      $("scenarioType").value = button.dataset.scenario;
      $("scenarioTarget").value = button.dataset.target;
      loadSimulation();
    });
  });
}

async function compareMitigation() {
  const base = {
    type: $("scenarioType").value,
    target: $("scenarioTarget").value,
    mitigations: selectedMitigations()
  };
  await loadSimulation({
    ...base,
    compare_to: {
      ...base,
      mitigations: [...new Set([...base.mitigations, "assign backup owner", "document process"])]
    }
  });
}

async function syncNotion() {
  $("notionSyncStatus").textContent = "Syncing";
  const pageIds = $("notionPageIds").value.split(",").map((item) => item.trim()).filter(Boolean);
  const apiKey = $("notionApiKey").value.trim();
  try {
    const payload = { page_ids: pageIds };
    if (apiKey) payload.api_key = apiKey;
    await api("/brain/connectors/notion/sync", { method: "POST", body: JSON.stringify(payload) });
    $("notionSyncStatus").textContent = "Synced";
    await refreshCustomerScreens();
  } catch (error) {
    $("notionSyncStatus").textContent = error.message;
  }
}

async function ingestManual() {
  $("manualIngestStatus").textContent = "Ingesting";
  try {
    await api("/brain/ingest", {
      method: "POST",
      body: JSON.stringify({
        records: {
          source: $("manualSource").value.trim() || "customer_note",
          content: $("manualContent").value,
          metadata: {
            source_type: "manual",
            id: `manual-${Date.now()}`,
            timestamp: new Date().toISOString()
          }
        }
      })
    });
    $("manualIngestStatus").textContent = "Ingested";
    await refreshCustomerScreens();
  } catch (error) {
    $("manualIngestStatus").textContent = error.message;
  }
}

async function refreshCustomerScreens() {
  await Promise.all([
    loadPeopleRisk(),
    loadOverview(),
    loadGraph(),
    loadPeople(),
    loadProcesses(),
    loadCoverage(),
    loadRisks(),
    loadEvidence(),
    loadSources()
  ]);
}

async function safeLoad(loader) {
  try {
    await loader();
  } catch (error) {
    setOnline(false, error.message);
  }
}

async function boot() {
  setOnline(false, "Loading");
  await Promise.all([
    safeLoad(loadPeopleRisk),
    safeLoad(loadOverview),
    safeLoad(loadGraph),
    safeLoad(loadPeople),
    safeLoad(loadProcesses),
    safeLoad(loadCoverage),
    safeLoad(loadRisks),
    safeLoad(loadEvidence),
    safeLoad(loadSources),
    safeLoad(() => loadSimulation({ type: "person_departure", target: "Sarah Kim", mitigations: [] }))
  ]);
  setOnline(true, "Live");
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});
$("refreshOverview").addEventListener("click", async () => {
  await loadPeopleRisk();
  await loadOverview();
});
$("runPeopleRisk").addEventListener("click", async () => {
  await loadPeopleRisk($("peopleRiskTarget").value);
  $("scenarioType").value = "person_departure";
  $("scenarioTarget").value = $("peopleRiskTarget").value;
  await loadSimulation({ type: "person_departure", target: $("peopleRiskTarget").value, mitigations: [] });
});
$("openRiskGraph").addEventListener("click", () => {
  const target = $("peopleRiskTarget").value;
  switchView("graph");
  if ($("graphSearch")) {
    $("graphSearch").value = target;
    if (state.graph) renderGraphSvg();
  }
});
$("refreshGraph").addEventListener("click", loadGraph);
$("refreshPeople").addEventListener("click", loadPeople);
$("refreshProcesses").addEventListener("click", loadProcesses);
$("refreshCoverage").addEventListener("click", loadCoverage);
$("refreshRisks").addEventListener("click", loadRisks);
$("refreshEvidence").addEventListener("click", loadEvidence);
$("refreshSources").addEventListener("click", loadSources);
$("graphSearch").addEventListener("input", renderGraphSvg);
$("runPathSearch").addEventListener("click", runPathSearch);
$("runSimulation").addEventListener("click", () => loadSimulation());
$("compareMitigation").addEventListener("click", compareMitigation);
$("syncNotion").addEventListener("click", syncNotion);
$("ingestManual").addEventListener("click", ingestManual);

boot();
