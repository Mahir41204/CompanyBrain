const state = {
  skills: [],
  selectedSkillId: null
};

const byId = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || response.statusText);
  }
  return data;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function short(text, length = 130) {
  if (!text) return "";
  return text.length > length ? `${text.slice(0, length - 3)}...` : text;
}

function setStatus(text, ok = true) {
  const status = byId("apiStatus");
  status.textContent = text;
  status.style.background = ok ? "var(--soft)" : "#f8dfdc";
  status.style.color = ok ? "var(--accent)" : "var(--accent-2)";
}

function switchView(id) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-button").forEach((button) => button.classList.remove("active"));
  byId(id).classList.add("active");
  document.querySelector(`[data-view="${id}"]`).classList.add("active");
}

async function loadSkills() {
  const result = await api("/brain/skills");
  state.skills = result.skills;
  const list = byId("skillList");
  list.innerHTML = "";

  result.skills.forEach((skill) => {
    const row = document.createElement("button");
    row.className = "row";
    row.innerHTML = `
      <div class="row-title">
        <strong>${skill.skill_id}</strong>
        <span class="pill">${Number(skill.confidence_score).toFixed(2)}</span>
      </div>
      <p>${short(skill.description)}</p>
    `;
    row.addEventListener("click", () => selectSkill(skill.skill_id));
    list.appendChild(row);
  });

  if (!state.selectedSkillId && result.skills.length) {
    await selectSkill(result.skills[0].skill_id);
  }
}

async function selectSkill(skillId) {
  const skill = await api(`/brain/skills/${encodeURIComponent(skillId)}`);
  state.selectedSkillId = skillId;
  byId("selectedDomain").textContent = skill.domain || "operations";
  byId("selectedTitle").textContent = skill.skill_id;
  byId("selectedConfidence").textContent = Number(skill.confidence_score || 0).toFixed(2);
  byId("skillDefinition").textContent = pretty(skill);
}

async function runSelectedSkill() {
  if (!state.selectedSkillId) return;
  const context = JSON.parse(byId("executionContext").value);
  const result = await api(`/brain/execute/${encodeURIComponent(state.selectedSkillId)}`, {
    method: "POST",
    body: JSON.stringify(context)
  });
  byId("executionResult").textContent = pretty(result);
}

async function loadCandidates() {
  const result = await api("/brain/candidates");
  const list = byId("candidateList");
  list.innerHTML = "";

  result.candidates.forEach((candidate) => {
    const skill = candidate.proposed_skill || {};
    const row = document.createElement("article");
    row.className = "row";
    row.innerHTML = `
      <div class="row-title">
        <strong>${candidate.candidate_id}</strong>
        <span class="pill">${candidate.status}</span>
      </div>
      <p>${short(skill.description, 180)}</p>
      <pre>${pretty(skill)}</pre>
      <div class="actions">
        <button class="primary" data-action="approve">Approve</button>
        <button class="danger" data-action="reject">Reject</button>
      </div>
    `;
    row.querySelector('[data-action="approve"]').addEventListener("click", () => reviewCandidate(candidate.candidate_id, "approve"));
    row.querySelector('[data-action="reject"]').addEventListener("click", () => reviewCandidate(candidate.candidate_id, "reject"));
    list.appendChild(row);
  });

  if (!result.candidates.length) {
    list.innerHTML = '<div class="row"><strong>No candidates</strong><p>The review queue is clear.</p></div>';
  }
}

async function reviewCandidate(candidateId, action) {
  await api(`/brain/candidates/${encodeURIComponent(candidateId)}/${action}`, {
    method: "POST",
    body: "{}"
  });
  await Promise.all([loadCandidates(), loadSkills(), loadCoverage()]);
}

async function ingestRecord() {
  const payload = {
    source: byId("ingestSource").value,
    content: byId("ingestContent").value,
    metadata: {
      owner: byId("ingestOwner").value
    }
  };
  const result = await api("/brain/ingest", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  byId("ingestResult").textContent = pretty(result);
  await loadCandidates();
}

async function loadCoverage() {
  const coverage = await api("/brain/coverage");
  byId("coverageMetrics").innerHTML = `
    <div class="metric"><span>Total Skills</span><strong>${coverage.total_skills}</strong></div>
    <div class="metric"><span>High Confidence</span><strong>${coverage.high_confidence_skills}</strong></div>
    <div class="metric"><span>Average Confidence</span><strong>${Number(coverage.average_confidence).toFixed(2)}</strong></div>
    <div class="metric"><span>Covered Estimate</span><strong>${Math.round(coverage.operations_covered_estimate * 100)}%</strong></div>
  `;
  byId("coverageGaps").innerHTML = coverage.top_review_gaps.map((gap) => `
    <article class="row">
      <div class="row-title">
        <strong>${gap.candidate_id}</strong>
        <span class="pill">${gap.domain}</span>
      </div>
      <p>${short(gap.description, 220)}</p>
    </article>
  `).join("") || '<div class="row"><strong>No review gaps</strong><p>The pending queue is empty.</p></div>';
}

async function loadMemory() {
  const graph = await api("/brain/graph");
  byId("memoryMetrics").innerHTML = `
    <div class="metric"><span>Entities</span><strong>${graph.entities.length}</strong></div>
    <div class="metric"><span>Edges</span><strong>${graph.edges.length}</strong></div>
    <div class="metric"><span>Evidence</span><strong>${graph.evidence.length}</strong></div>
  `;
}

async function explainMemory() {
  const query = encodeURIComponent(byId("memoryQuery").value);
  const result = await api(`/brain/graph/explain?q=${query}`);
  byId("memoryResult").textContent = pretty(result);
}

async function boot() {
  try {
    await api("/health");
    setStatus("Online");
    await Promise.all([loadSkills(), loadCandidates(), loadCoverage(), loadMemory()]);
  } catch (error) {
    setStatus(error.message, false);
  }
}

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});
byId("refreshSkills").addEventListener("click", loadSkills);
byId("runSkill").addEventListener("click", runSelectedSkill);
byId("refreshCandidates").addEventListener("click", loadCandidates);
byId("submitIngest").addEventListener("click", ingestRecord);
byId("refreshCoverage").addEventListener("click", loadCoverage);
byId("refreshMemory").addEventListener("click", loadMemory);
byId("explainMemory").addEventListener("click", explainMemory);

boot();
