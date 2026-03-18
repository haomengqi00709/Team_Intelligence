/* ── Team Intelligence · dashboard.js ───────────────────────────── */

const SESSION = (() => {
  try { return JSON.parse(sessionStorage.getItem("ti_session") || "null"); } catch { return null; }
})();
if (!SESSION) { window.location.href = "/login"; }
else { document.body.style.visibility = "visible"; }
const IS_TEAM = SESSION?.role === "team_member";

// ─────────────────────────────────────────────────────────────────
// ORG DATA  Branch → DG → Director → Manager → (Lead) → Team
// ─────────────────────────────────────────────────────────────────
const ORG = {
  branch: { name: "Transportation of Dangerous Goods", org: "Transport Canada" },

  dgs: [
    {
      id: "michael", name: "Michael", fullName: "Michael Beauchamp", initials: "MB",
      title: "Director General, National Safety Operations",
      desc: "Oversees national carrier inspection programs, risk model modernization, and cross-jurisdictional safety compliance.",
      directors: [
        {
          id: "marc", name: "Marc Tremblay", initials: "MT",
          title: "Director, Transportation Safety Programs",
          desc: "Responsible for program delivery, budget authority, and regulatory alignment across all NOP modernization projects.",
          managers: [
            {
              id: "carolyn", name: "Carolyn Park", initials: "CP",
              title: "Data Management Manager",
              reportsTo: "Marc Tremblay",
              lead: null,
              team: {
                name: "National Oversight Planning Team",
                members: [
                  { name: "Sean Okafor", title: "Senior Program Analyst",              initials: "SO" },
                  { name: "Jason Hao",   title: "Data Analyst",                        initials: "JH" },
                  { name: "Dave",        title: "Regional Inspector, Pacific Region",  initials: "DV" },
                  { name: "Roger",       title: "Senior Analyst, QA",                  initials: "RG" },
                  { name: "Dr. Aris",    title: "External Statistical Consultant",      initials: "DA", type: "contractor" },
                ],
              },
              projects: [
                {
                  id: "nop_risk_model", live: true,
                  name: "NOP Risk Model Modernization",
                  desc: "Modernization of the national occupation risk scoring model for dangerous goods site inspections. Algorithm redesign, SAS implementation, and compliance audit.",
                  status: "active", phase: "Production",
                  docs: 90, updated: "Nov 2024",
                  tags: ["risk-model", "SAS", "compliance", "audit"],
                  snippet: "Comprehensive redesign of the national risk scoring algorithm used to prioritize dangerous goods site inspections across Canada. Rebuilt the statistical weighting methodology, replacing heuristic rules with data-driven risk factors covering carrier history, incident frequency, geographic distribution, and regulatory compliance. Implemented in SAS, the engine produces ranked inspection priority scores per carrier. Key deliverables include revised factor weighting, SAS scoring engine, data pipeline integration with the TC carrier registry, threshold calibration against historical outcomes, and a full QA audit trail. Completed compliance review and sign-off in late 2024. Output feeds directly into regional inspection scheduling across all provinces.",
                },
                {
                  id: "aviation_risk_index", live: false,
                  name: "Aviation Risk Index Update",
                  desc: "Annual refresh of the aviation operator risk index incorporating updated regulatory thresholds from the 2024 policy review.",
                  status: "review", phase: "Review & Sign-off",
                  docs: 34, updated: "Sep 2024",
                  tags: ["aviation", "risk-index", "regulatory"],
                  snippet: "Annual refresh of the aviation operator risk index, incorporating regulatory threshold changes from the 2024 Transport Canada policy review. The index scores commercial aviation operators on safety performance, incident reporting compliance, and maintenance record quality. This cycle recalibrated risk thresholds for new reporting requirements, updated weighting for operator size and route complexity, and reconciled historical scores with the revised methodology. Currently in review and sign-off phase pending Director approval. Outputs inform TC's aviation operator oversight schedule and contribute to the branch-wide risk reporting framework.",
                },
              ],
            },
          ],
        },
      ],
    },

    {
      id: "olaf", name: "Olaf", fullName: "Olaf Lindqvist", initials: "OL",
      title: "Director General, Data & Digital Services",
      desc: "Leads data infrastructure modernization, analytics platform development, and branch-wide data governance initiatives.",
      directors: [
        {
          id: "annemarie", name: "Anne-Marie Côté", initials: "AC",
          title: "Director, Data Infrastructure & Analytics",
          desc: "Owns all data platform, analytics, and visualization work across the branch. Manages two distinct functional teams.",
          managers: [
            {
              id: "priya", name: "Priya Nair", initials: "PN",
              title: "Data Engineering Manager",
              reportsTo: "Anne-Marie Côté",
              lead: null,
              team: {
                name: "Data Infrastructure Team",
                members: [
                  { name: "Isabelle Fontaine", title: "Policy Advisor",       initials: "IF" },
                  { name: "Kenji Watanabe",    title: "Data Pipeline Engineer",initials: "KW" },
                  { name: "Fatima Al-Hassan",  title: "Data Quality Analyst",  initials: "FA" },
                ],
              },
              projects: [
                {
                  id: "motor_carrier", live: false,
                  name: "Motor Carrier Safety Analytics",
                  desc: "Real-time analytics platform for motor carrier safety scores and violation tracking across provincial jurisdictions.",
                  status: "active", phase: "Development",
                  docs: 47, updated: "Oct 2024",
                  tags: ["safety", "analytics", "carriers"],
                  snippet: "Real-time analytics platform tracking motor carrier safety scores and violation records across provincial jurisdictions. Ingests data from provincial registries and TC enforcement records to produce unified carrier profiles including safety score trends, violation breakdowns, inspection history, and peer benchmarks. Supports enforcement officers in identifying high-risk carriers. In active development, the platform includes an automated ingestion pipeline, a scoring engine aligned with federal motor carrier safety regulations, and a regional analyst dashboard. Key technical challenge has been normalizing inconsistent data formats across eight provincial data sources.",
                },
                {
                  id: "data_governance", live: false,
                  name: "Data Governance Framework",
                  desc: "Branch-wide data quality standards, lineage tracking, and governance policies.",
                  status: "planning", phase: "Discovery",
                  docs: 12, updated: "Aug 2024",
                  tags: ["governance", "data-quality", "policy"],
                  snippet: "Branch-wide initiative to establish data quality standards, lineage tracking, and governance policies across all data assets in the Transportation of Dangerous Goods branch. Defines data ownership, quality thresholds, metadata standards, and review processes for all data products produced or consumed by branch teams. Currently mapping existing data flows, identifying quality gaps, and drafting governance policy documents. Expected outputs include a data catalogue, quality scorecard template, lineage documentation standards, and a governance committee charter. Triggered by a 2024 audit finding on traceability of risk-model input data.",
                },
              ],
            },
            {
              id: "david", name: "David Lessard", initials: "DL",
              title: "BI & Visualization Lead",
              reportsTo: "Anne-Marie Côté",
              lead: null,
              team: {
                name: "Reporting & Visualization Team",
                members: [
                  { name: "Sofia Bergmann", title: "BI Developer",      initials: "SB" },
                  { name: "Luc Thibodeau",  title: "Dashboard Analyst",  initials: "LT" },
                ],
              },
              projects: [
                {
                  id: "exec_dashboard", live: false,
                  name: "Executive Performance Dashboard",
                  desc: "Branch-wide KPI dashboard for leadership — safety scores, inspection rates, and program outcomes.",
                  status: "planning", phase: "Discovery",
                  docs: 8, updated: "Jul 2024",
                  tags: ["dashboard", "KPIs", "reporting"],
                  snippet: "Branch-wide KPI dashboard for senior leadership to monitor safety program performance, inspection rates, and program outcomes in near real-time. Consolidates metrics from inspection scheduling, carrier risk scores, incident reporting, and budget tracking systems. Designed for Director General and Director-level audiences with drill-down into regional and program-level breakdowns. Currently in discovery phase: defining KPI definitions with stakeholders, establishing data source connections, and designing visual layout. Will be hosted on the branch analytics platform with a weekly data refresh cycle.",
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

// ── Derived flat views ────────────────────────────────────────────
const ALL_DIRECTORS = ORG.dgs.flatMap(g => g.directors);
const ALL_MANAGERS  = ALL_DIRECTORS.flatMap(d => d.managers);
const ALL_PROJECTS  = ALL_MANAGERS.flatMap(m => m.projects);

// ── Rehydrate user-created projects from sessionStorage ───────────
(function rehydrateCreatedProjects() {
  try {
    const saved = JSON.parse(sessionStorage.getItem("ti_created_projects") || "[]");
    saved.forEach(({ mgrId, project }) => {
      const mgr = ALL_MANAGERS.find(m => m.id === mgrId);
      if (mgr && !mgr.projects.find(p => p.id === project.id)) {
        mgr.projects.push(project);
      }
    });
  } catch (_) {}
})();

// ── Person → org position ──────────────────────────────────────────
const PERSON_ORG = {
  "Michael Beauchamp": { role: "dg",       dgId: "michael" },
  "Marc Tremblay":     { role: "director", dgId: "michael", dirId: "marc" },
  "Carolyn Park":      { role: "manager",  dgId: "michael", dirId: "marc",     mgrId: "carolyn" },
  "Sean Okafor":       { role: "member",   dgId: "michael", dirId: "marc",     mgrId: "carolyn" },
  "Jason Hao":         { role: "member",   dgId: "michael", dirId: "marc",     mgrId: "carolyn" },
  "Olaf Lindqvist":    { role: "dg",       dgId: "olaf" },
  "Anne-Marie Côté":   { role: "director", dgId: "olaf",    dirId: "annemarie" },
  "Priya Nair":        { role: "manager",  dgId: "olaf",    dirId: "annemarie", mgrId: "priya" },
  "David Lessard":     { role: "manager",  dgId: "olaf",    dirId: "annemarie", mgrId: "david" },
  "Isabelle Fontaine": { role: "member",   dgId: "olaf",    dirId: "annemarie", mgrId: "priya" },
};

// ── Navigation state ──────────────────────────────────────────────
// level: "branch" | "dg" | "director" | "team"
const nav = { level: "branch", dgId: null, dirId: null };

// Filter state (status only — no keyword filter)
const filter = { status: "all" };

// Search state
let searchActive = false;

// ── Helpers ───────────────────────────────────────────────────────
const AVATAR_COLORS = ["#6366f1","#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#14b8a6","#f97316"];
function avatarColor(n) {
  let h = 0;
  for (const c of String(n)) h = c.charCodeAt(0) + ((h << 5) - h);
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}
function esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : ""; }

function getDg(id)  { return ORG.dgs.find(g => g.id === id); }
function getDir(dgId, dirId) { return getDg(dgId)?.directors.find(d => d.id === dirId); }
function getMgr(dgId, dirId, mgrId) { return getDir(dgId, dirId)?.managers.find(m => m.id === mgrId); }

function matchesFilter(p) {
  return filter.status === "all" || p.status === filter.status;
}

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  renderHeader();
  buildNavTree();
  bindFilters();
  bindSearch();
  bindSignOut();
  bindCreateProjectModal();
  checkStatus();
  loadIndexStats();

  // If returning from a project page, go straight to My Team
  const returnNav = sessionStorage.getItem("ti_return_nav");
  sessionStorage.removeItem("ti_return_nav");
  if (returnNav === "myteam") {
    goToMyTeam();
  } else {
    navigate("branch", null, null);
  }
});

// ── Header ────────────────────────────────────────────────────────
function renderHeader() {
  document.getElementById("headerAvatar").style.background = SESSION.color;
  document.getElementById("headerAvatar").textContent      = SESSION.initials;
  document.getElementById("headerUserName").textContent    = SESSION.name;
  document.getElementById("headerUserTitle").textContent   = SESSION.title;
  const b = document.getElementById("userAccessBadge");
  b.textContent = IS_TEAM ? "Full Access" : "Branch Viewer";
  b.className   = `user-access-badge role-${SESSION.role}`;

  // Branch label + sidebar stats
  document.getElementById("branchLabel").textContent = ORG.branch.name;
  const _allDirs = ORG.dgs.flatMap(g => g.directors);
  document.getElementById("bcDGs").textContent   = ORG.dgs.length;
  document.getElementById("bcDirs").textContent  = _allDirs.length;
  document.getElementById("bcProjs").textContent = ALL_PROJECTS.length;
}

// ── Nav tree ─────────────────────────────────────────────────────
function buildNavTree() {
  const tree = document.getElementById("navTree");
  tree.innerHTML = "";

  // TDG top-level entry
  const tdgItem = navItem(null, "TDG", () => navigate("branch", null, null));
  tdgItem.dataset.navLevel = "branch";
  tree.appendChild(tdgItem);

  ORG.dgs.forEach(dg => {
    // DG item
    const dgItem = navItem("👤", dg.name, () => navigate("dg", null, null, dg.id));
    dgItem.dataset.navDg = dg.id;
    tree.appendChild(dgItem);

    // Director items (indented)
    dg.directors.forEach(dir => {
      const dirItem = navItem(null, dir.name.split(" ")[0], () => navigate("director", dg.id, null, dir.id), true);
      dirItem.dataset.navDg  = dg.id;
      dirItem.dataset.navDir = dir.id;
      tree.appendChild(dirItem);

      // Manager/team items (more indented)
      dir.managers.forEach(mgr => {
        const teamItem = navItem(null, mgr.team.name, () => navigate("team", dg.id, dir.id, mgr.id), false, true);
        teamItem.dataset.navDg  = dg.id;
        teamItem.dataset.navDir = dir.id;
        teamItem.dataset.navMgr = mgr.id;
        tree.appendChild(teamItem);
      });
    });
  });

  // My Team shortcut
  const divider = document.createElement("div");
  divider.className = "nav-divider";
  tree.appendChild(divider);

  const myTeamBtn = navItem("⭐", "My Team", goToMyTeam);
  myTeamBtn.id = "myTeamBtn";
  tree.appendChild(myTeamBtn);
}

function navItem(icon, label, onClick, indent1 = false, indent2 = false) {
  const btn = document.createElement("button");
  btn.className = `nav-item${indent1 ? " nav-indent-1" : ""}${indent2 ? " nav-indent-2" : ""}`;
  btn.innerHTML = icon
    ? `<span class="nav-icon">${icon}</span>${esc(label)}`
    : `<span class="nav-bullet"></span>${esc(label)}`;
  btn.addEventListener("click", onClick);
  return btn;
}

function updateNavHighlight() {
  document.querySelectorAll(".nav-item").forEach(btn => {
    let active = false;
    if (nav.level === "branch" && btn.dataset.navLevel === "branch") {
      active = true;
    } else if (nav.level === "dg" && btn.dataset.navDg && !btn.dataset.navDir && btn !== document.getElementById("myTeamBtn")) {
      active = btn.dataset.navDg === nav.dgId || (!nav.dgId && !btn.id);
    } else if (nav.level === "director" && btn.dataset.navDir) {
      active = btn.dataset.navDg === nav.dgId && btn.dataset.navDir === nav.dirId && !btn.dataset.navMgr;
    } else if (nav.level === "team" && btn.dataset.navMgr) {
      active = btn.dataset.navDg === nav.dgId && btn.dataset.navDir === nav.dirId && btn.dataset.navMgr === nav.mgrId;
    }
    btn.classList.toggle("active", active);
  });
}

// ── Navigation ────────────────────────────────────────────────────
function navigate(level, dgId, dirId, selectedId) {
  searchActive = false;
  document.getElementById("searchInput").value = "";
  if (level === "branch") {
    nav.level = "branch";
    nav.dgId  = null;
    nav.dirId = null;
    nav.mgrId = null;
  } else if (level === "dg") {
    nav.level = "dg";
    nav.dgId  = selectedId || null;  // null = show all DGs
    nav.dirId = null;
    nav.mgrId = null;
  } else if (level === "director") {
    nav.level = "director";
    nav.dgId  = dgId;
    nav.dirId = selectedId || null;
    nav.mgrId = null;
  } else if (level === "team") {
    nav.level = "team";
    nav.dgId  = dgId;
    nav.dirId = dirId;
    nav.mgrId = selectedId;
  }

  updateNavHighlight();
  renderBreadcrumb();
  renderContent();
}

function goToMyTeam() {
  const pos = PERSON_ORG[SESSION?.name];
  if (!pos) { navigate("dg", null, null); return; }
  if (pos.role === "dg")       navigate("dg", null, null, pos.dgId);
  else if (pos.role === "director") navigate("director", pos.dgId, null, pos.dirId);
  else navigate("team", pos.dgId, pos.dirId, pos.mgrId);

  document.getElementById("myTeamBtn")?.classList.add("active");
}

function openProject(p) {
  sessionStorage.setItem("ti_return_nav", "myteam");
  sessionStorage.setItem("ti_project", JSON.stringify({ id: p.id, name: p.name, live: p.live, fresh: !!p._created }));
  window.location.href = "/";
}

// ── Breadcrumb ────────────────────────────────────────────────────
function renderBreadcrumb() {
  const bc = document.getElementById("breadcrumb");
  bc.innerHTML = "";

  const crumbs = [{ label: "TDG", action: () => navigate("branch", null, null) }];

  if (nav.dgId) {
    const dg = getDg(nav.dgId);
    if (dg) crumbs.push({ label: dg.name, action: () => navigate("dg", null, null, dg.id) });
  } else if (nav.level !== "dg") {
    crumbs.push({ label: "All DGs" });
  }

  if (nav.dirId) {
    const dir = getDir(nav.dgId, nav.dirId);
    if (dir) crumbs.push({ label: dir.name.split(" ")[0], action: () => navigate("director", nav.dgId, null, nav.dirId) });
  }

  if (nav.mgrId) {
    const mgr = getMgr(nav.dgId, nav.dirId, nav.mgrId);
    if (mgr) crumbs.push({ label: mgr.team.name });
  }

  crumbs.forEach((c, i) => {
    if (i > 0) {
      const sep = document.createElement("span");
      sep.className = "bc-sep";
      sep.textContent = "›";
      bc.appendChild(sep);
    }
    const span = document.createElement("span");
    span.className = `bc-item${c.action ? " bc-link" : ""}`;
    span.textContent = c.label;
    if (c.action) span.addEventListener("click", c.action);
    bc.appendChild(span);
  });

  // Update scope badge
  const hints = {
    branch:   ["Branch Level",   "ssb-branch",   "Transportation of Dangerous Goods — top-level branch overview."],
    dg:       ["DG Level",       "ssb-branch",   "High-level portfolio overview across all Director Generals."],
    director: ["Director Level", "ssb-director", "Directors and their teams under the selected DG."],
    team:     ["Team Level",     "ssb-team",     "Team members and projects. Click Open Chat for full document search."],
  };
  const [label, cls, hint] = hints[nav.level] || hints.branch;
  const badge = document.getElementById("searchScopeBadge");
  badge.textContent = label;
  badge.className   = `search-scope-badge ${cls}`;
  document.getElementById("scopeHint").textContent = hint;
}

// ── Content render (level router) ─────────────────────────────────
function renderContent() {
  const root = document.getElementById("dashResults");
  root.innerHTML = "";

  if (nav.level === "branch")        renderBranchLevel(root);
  else if (nav.level === "dg")       renderDgLevel(root);
  else if (nav.level === "director") renderDirectorLevel(root);
  else if (nav.level === "team")     renderTeamLevel(root);
}

// ── Level 0: TDG branch card ──────────────────────────────────────
function renderBranchLevel(root) {
  const totalProjects = ALL_PROJECTS.filter(matchesFilter).length;
  const totalDirs     = ORG.dgs.flatMap(g => g.directors).length;
  const totalTeams    = ORG.dgs.flatMap(g => g.directors.flatMap(d => d.managers)).length;
  const active  = ALL_PROJECTS.filter(p => p.status === "active").length;
  const review  = ALL_PROJECTS.filter(p => p.status === "review").length;
  const plan    = ALL_PROJECTS.filter(p => p.status === "planning").length;

  const card = document.createElement("div");
  card.className = "level-card branch-card";
  card.innerHTML = `
    <div class="lc-header">
      <div class="lc-avatar" style="background:${avatarColor(ORG.branch.name)}">TDG</div>
      <div class="lc-title-block">
        <div class="lc-name">${esc(ORG.branch.name)}</div>
        <div class="lc-title">${esc(ORG.branch.org)}</div>
      </div>
      <span class="lc-role-badge dg-badge">Branch</span>
    </div>
    <div class="lc-desc">National program delivery for the safe transportation of dangerous goods across Canada. Oversees risk model modernization, compliance inspection programs, and data infrastructure.</div>
    <div class="lc-meta-row">
      <span class="lc-meta-chip">${ORG.dgs.length} Director Generals</span>
      <span class="lc-meta-chip">${totalDirs} Directors</span>
      <span class="lc-meta-chip">${totalTeams} Teams</span>
      <span class="lc-meta-chip">${totalProjects} Projects</span>
      <div class="lc-status-row">
        ${active ? `<span class="status-mini active">● ${active} Active</span>` : ""}
        ${review ? `<span class="status-mini review">◐ ${review} Review</span>` : ""}
        ${plan   ? `<span class="status-mini planning">○ ${plan} Planning</span>` : ""}
      </div>
    </div>
    <div class="lc-footer">
      <button class="lc-btn lc-btn-primary js-view-dgs">
        View Leadership
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
      </button>
    </div>
  `;
  card.querySelector(".js-view-dgs").addEventListener("click", () => navigate("dg", null, null));
  root.appendChild(card);
}

// ── Level 1: DG cards ─────────────────────────────────────────────
function renderDgLevel(root) {
  const dgsToShow = nav.dgId ? ORG.dgs.filter(g => g.id === nav.dgId) : ORG.dgs;

  dgsToShow.forEach(dg => {
    const allProj = dg.directors.flatMap(d => d.managers.flatMap(m => m.projects)).filter(matchesFilter);
    const active  = allProj.filter(p => p.status === "active").length;
    const review  = allProj.filter(p => p.status === "review").length;
    const plan    = allProj.filter(p => p.status === "planning").length;
    const nDirs   = dg.directors.length;
    const nTeams  = dg.directors.flatMap(d => d.managers).length;

    const card = document.createElement("div");
    card.className = "level-card dg-card";

    card.innerHTML = `
      <div class="lc-header">
        <div class="lc-avatar" style="background:${avatarColor(dg.fullName)}">${esc(dg.initials)}</div>
        <div class="lc-title-block">
          <div class="lc-name">${esc(dg.fullName)}</div>
          <div class="lc-title">${esc(dg.title)}</div>
        </div>
        <span class="lc-role-badge dg-badge">DG</span>
      </div>
      <div class="lc-desc">${esc(dg.desc)}</div>
      <div class="lc-meta-row">
        <span class="lc-meta-chip">${nDirs} director${nDirs > 1 ? "s" : ""}</span>
        <span class="lc-meta-chip">${nTeams} team${nTeams > 1 ? "s" : ""}</span>
        <span class="lc-meta-chip">${allProj.length} project${allProj.length > 1 ? "s" : ""}</span>
        <div class="lc-status-row">
          ${active  ? `<span class="status-mini active">● ${active} Active</span>` : ""}
          ${review  ? `<span class="status-mini review">◐ ${review} Review</span>` : ""}
          ${plan    ? `<span class="status-mini planning">○ ${plan} Planning</span>` : ""}
        </div>
      </div>
      <div class="lc-footer">
        <button class="lc-btn lc-btn-primary js-open-dir">
          View Directors
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
        </button>
      </div>
    `;

    card.querySelector(".js-open-dir").addEventListener("click", () => navigate("director", dg.id, null));
    root.appendChild(card);
  });
}

// ── Project search (director level) ──────────────────────────────
function allProjectsPayload() {
  return ALL_MANAGERS.flatMap(mgr => {
    const dir = ALL_DIRECTORS.find(d => d.managers.includes(mgr));
    const dg  = ORG.dgs.find(g => g.directors.includes(dir));
    return mgr.projects.map(p => ({
      id:      p.id,
      name:    p.name,
      team:    mgr.team.name,
      manager: mgr.name,
      status:  p.status,
      snippet: p.snippet || p.desc,
    }));
  });
}

async function runProjectSearch(query, resultsEl) {
  resultsEl.innerHTML = `<div class="ps-loading">Searching with AI<span class="ps-dots"><span>.</span><span>.</span><span>.</span></span></div>`;

  try {
    const r = await fetch("/api/projects/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, projects: allProjectsPayload() }),
    });
    const data = await r.json();
    renderSearchResults(data.matches || [], resultsEl);
  } catch {
    resultsEl.innerHTML = `<div class="ps-error">Search unavailable — backend offline.</div>`;
  }
}

function renderSearchResults(matches, resultsEl) {
  resultsEl.innerHTML = "";
  if (!matches.length) {
    resultsEl.innerHTML = `<div class="ps-empty">No related projects found for that query. Try different terms.</div>`;
    return;
  }

  matches.forEach(m => {
    // Find full project + manager context
    let proj = null, mgr = null, dir = null, dg = null;
    for (const g of ORG.dgs) {
      for (const d of g.directors) {
        for (const mg of d.managers) {
          const p = mg.projects.find(p => p.id === m.id);
          if (p) { proj = p; mgr = mg; dir = d; dg = g; }
        }
      }
    }
    if (!proj) return;

    const relevanceClass = { high: "ps-rel-high", medium: "ps-rel-med", low: "ps-rel-low" }[m.relevance] || "ps-rel-low";
    const relevanceLabel = { high: "Strong match", medium: "Related", low: "Possibly related" }[m.relevance] || "Related";

    const card = document.createElement("div");
    card.className = "ps-result-card";
    card.innerHTML = `
      <div class="ps-rel-badge ${relevanceClass}">${relevanceLabel}</div>
      <div class="ps-proj-name">${esc(proj.name)}</div>
      <div class="ps-proj-meta">
        <span class="dpr-status ${proj.status}">${cap(proj.status)}</span>
        <span class="ps-team">${esc(mgr.team.name)}</span>
        <span class="ps-sep">·</span>
        <span class="ps-mgr">Manager: ${esc(mgr.name)}</span>
      </div>
      <div class="ps-reason">${esc(m.reason)}</div>
      <div class="ps-actions">
        <button class="lc-btn lc-btn-ghost js-go-team">View Team</button>
        ${proj.live && IS_TEAM ? `<button class="lc-btn lc-btn-primary js-open-proj">Open Chat</button>` : ""}
      </div>
    `;
    card.querySelector(".js-go-team").addEventListener("click",
      () => navigate("team", dg.id, dir.id, mgr.id));
    card.querySelector(".js-open-proj")?.addEventListener("click",
      () => openProject(proj));
    resultsEl.appendChild(card);
  });
}

// ── Level 2: Director cards ───────────────────────────────────────
function renderDirectorLevel(root) {
  const dg = getDg(nav.dgId);
  if (!dg) return;

  // ── Director cards ──
  dg.directors.forEach(dir => {
    const allProj = dir.managers.flatMap(m => m.projects).filter(matchesFilter);
    const active  = allProj.filter(p => p.status === "active").length;
    const review  = allProj.filter(p => p.status === "review").length;
    const plan    = allProj.filter(p => p.status === "planning").length;

    const card = document.createElement("div");
    card.className = "level-card director-card";

    card.innerHTML = `
      <div class="lc-header">
        <div class="lc-avatar" style="background:${avatarColor(dir.name)}">${esc(dir.initials)}</div>
        <div class="lc-title-block">
          <div class="lc-name">${esc(dir.name)}</div>
          <div class="lc-title">${esc(dir.title)}</div>
        </div>
        <span class="lc-role-badge dir-badge">Director</span>
      </div>
      <div class="lc-desc">${esc(dir.desc)}</div>
      <div class="lc-meta-row">
        <span class="lc-meta-chip">${dir.managers.length} manager${dir.managers.length > 1 ? "s" : ""}</span>
        <span class="lc-meta-chip">${allProj.length} project${allProj.length > 1 ? "s" : ""}</span>
        <div class="lc-status-row">
          ${active ? `<span class="status-mini active">● ${active} Active</span>` : ""}
          ${review ? `<span class="status-mini review">◐ ${review} Review</span>` : ""}
          ${plan   ? `<span class="status-mini planning">○ ${plan} Planning</span>` : ""}
        </div>
      </div>
      ${allProj.length ? `<div class="dir-proj-list" id="dpl-${esc(dir.id)}"></div>` : ""}
      <div class="lc-footer">
        <button class="lc-btn lc-btn-primary js-open-team">
          View Teams
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
        </button>
      </div>
    `;

    // Build expandable project rows as DOM elements
    const projList = card.querySelector(`#dpl-${dir.id}`);
    if (projList) {
      allProj.forEach(p => {
        const mgr = dir.managers.find(m => m.projects.includes(p));
        const row = document.createElement("div");
        row.className = "dir-proj-row";

        // ── Summary line (always visible) ──
        const summary = document.createElement("div");
        summary.className = "dpr-summary";
        summary.innerHTML = `
          <span class="dpr-dot ${p.status}"></span>
          <span class="dir-proj-name">${esc(p.name)}</span>
          <span class="dpr-status ${p.status}">${cap(p.status)}</span>
          <span class="dpr-chip">Manager: ${esc(mgr?.name.split(" ")[0] || "—")}</span>
          ${p.live && IS_TEAM ? `<button class="dpr-open js-proj-open">Open</button>` : ""}
          <svg class="dpr-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6"/></svg>
        `;
        summary.querySelector(".js-proj-open")?.addEventListener("click", e => {
          e.stopPropagation();
          openProject(p);
        });

        // ── Detail panel (shown on expand) ──
        const detail = document.createElement("div");
        detail.className = "dpr-detail";

        const desc = p.snippet || p.desc || "";
        const members = mgr?.team?.members || [];

        detail.innerHTML = `
          ${desc ? `<div class="dpr-detail-desc">${esc(desc)}</div>` : ""}
          <div class="dpr-detail-row">
            <span class="dpr-detail-label">Phase</span>
            <span class="dpr-detail-chip">${esc(p.phase || "—")}</span>
            ${p.docs ? `<span class="dpr-detail-chip">${p.docs} docs</span>` : ""}
            ${(p.tags || []).map(t => `<span class="dpr-detail-chip">${esc(t)}</span>`).join("")}
          </div>
          ${members.length ? `
          <div class="dpr-detail-row">
            <span class="dpr-detail-label">Team</span>
            ${members.map(m => `
              <span class="dpr-member-chip">
                <span class="dpr-member-avatar" style="background:${avatarColor(m.name)}">${esc(m.initials)}</span>
                ${esc(m.name.split(" ")[0])}
              </span>`).join("")}
          </div>` : ""}
        `;

        // Toggle expand on row click
        summary.addEventListener("click", () => {
          row.classList.toggle("expanded");
        });

        row.appendChild(summary);
        row.appendChild(detail);
        projList.appendChild(row);
      });
    }

    card.querySelector(".js-open-team").addEventListener("click", () => navigate("team", dg.id, dir.id));
    root.appendChild(card);
  });
}

// ── Level 3: Team view ────────────────────────────────────────────
function renderTeamLevel(root) {
  const dir = getDir(nav.dgId, nav.dirId);
  if (!dir) return;

  const managersToShow = nav.mgrId
    ? dir.managers.filter(m => m.id === nav.mgrId)
    : dir.managers;

  // Personalization banner if navigated via My Team
  const pos = PERSON_ORG[SESSION?.name];
  if (pos && pos.mgrId && managersToShow.some(m => m.id === pos.mgrId)) {
    const you = managersToShow.find(m => m.id === pos.mgrId);
    if (you) {
      const banner = document.createElement("div");
      banner.className = "my-team-banner";
      const roleLabel = { manager: "You manage this team.", lead: `You are the Project Lead under ${esc(you.name)}.`, member: `You are a member of ${esc(you.team.name)}.` }[pos.role] || "";
      banner.innerHTML = `<div class="mtb-icon">⭐</div><div class="mtb-body"><div class="mtb-title">My Team</div><div class="mtb-sub">${roleLabel}</div></div>`;
      root.appendChild(banner);
    }
  }

  managersToShow.forEach(mgr => {
    root.appendChild(buildTeamBlock(mgr));
  });
}

function buildTeamBlock(mgr) {
  const wrapper = document.createElement("div");
  wrapper.className = "team-block-card";

  // Manager header
  wrapper.innerHTML = `
    <div class="tb-manager-row">
      <div class="tb-label">Manager</div>
      <div class="tb-person-info">
        <div class="lc-avatar" style="background:${avatarColor(mgr.name)};width:32px;height:32px;font-size:11px">${esc(mgr.initials)}</div>
        <div>
          <div class="tb-person-name">${esc(mgr.name)}</div>
          <div class="tb-person-title">${esc(mgr.title)} · reports to ${esc(mgr.reportsTo)}</div>
        </div>
      </div>
    </div>
  `;

  // Project Lead (if exists)
  if (mgr.lead) {
    const leadRow = document.createElement("div");
    leadRow.className = "tb-lead-row";
    leadRow.innerHTML = `
      <div class="tb-label">Project Lead</div>
      <div class="tb-person-info">
        <div class="lc-avatar" style="background:${avatarColor(mgr.lead.name)};width:28px;height:28px;font-size:10px">${esc(mgr.lead.initials)}</div>
        <div>
          <div class="tb-person-name">${esc(mgr.lead.name)}</div>
          <div class="tb-person-title">${esc(mgr.lead.title)} · reports to ${esc(mgr.lead.reportsTo)}</div>
        </div>
      </div>
    `;
    wrapper.appendChild(leadRow);
  }

  // Team members
  if (mgr.team.members?.length) {
    const membersSection = document.createElement("div");
    membersSection.className = "tb-members-section";
    membersSection.innerHTML = `<div class="tb-section-label">Team Members · ${esc(mgr.team.name)}</div>`;
    const grid = document.createElement("div");
    grid.className = "tb-members-grid";
    mgr.team.members.forEach(m => {
      const chip = document.createElement("div");
      chip.className = "tb-member-chip";
      chip.innerHTML = `
        <div class="lc-avatar" style="background:${avatarColor(m.name)};width:28px;height:28px;font-size:10px">${esc(m.initials)}</div>
        <div>
          <div class="tb-person-name">${esc(m.name)}</div>
          <div class="tb-person-title">${esc(m.title)}</div>
        </div>
        ${m.type === "contractor" ? `<span class="tms-ext">Contract</span>` : ""}
      `;
      grid.appendChild(chip);
    });
    membersSection.appendChild(grid);
    wrapper.appendChild(membersSection);
  }

  // Projects
  const projSection = document.createElement("div");
  projSection.className = "tb-projects-section";

  // Section header row with optional "New Project" button
  const pos = PERSON_ORG[SESSION?.name];
  const isMyTeam = pos && pos.mgrId === mgr.id;

  const labelRow = document.createElement("div");
  labelRow.className = "tb-section-label-row";
  const labelSpan = document.createElement("span");
  labelSpan.className = "tb-section-label";
  labelSpan.style.marginBottom = "0";
  labelSpan.textContent = "Projects";
  labelRow.appendChild(labelSpan);

  if (isMyTeam) {
    const createBtn = document.createElement("button");
    createBtn.className = "tb-create-btn";
    createBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> New Project`;
    createBtn.addEventListener("click", () => openCreateProject(mgr));
    labelRow.appendChild(createBtn);
  }
  projSection.appendChild(labelRow);

  const filtered = mgr.projects.filter(matchesFilter);

  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "tb-empty";
    empty.textContent = "No projects match the current filter.";
    projSection.appendChild(empty);
  } else {
    filtered.forEach(p => {
      const row = document.createElement("div");
      row.className = "tb-project-row";

      let actionBtn;
      if (p.live && IS_TEAM) {
        actionBtn = `<button class="lc-btn lc-btn-primary js-open-proj">Open Chat <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></button>`;
      } else if (p._created && IS_TEAM) {
        actionBtn = `<button class="lc-btn lc-btn-primary js-open-proj">Open Chat <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></button>`;
      } else if (IS_TEAM) {
        actionBtn = `<button class="lc-btn lc-btn-ghost" disabled>Indexing…</button>`;
      } else {
        actionBtn = `<span class="tb-restricted">🔒 Restricted</span>`;
      }

      row.innerHTML = `
        <div class="tb-proj-left">
          <span class="pcard-dot ${p.status}"></span>
          <div>
            <div class="tb-proj-name">${esc(p.name)}</div>
            <div class="tb-proj-meta">
              <span class="dpr-status ${p.status}">${cap(p.status)}</span>
              <span class="tb-proj-phase">${esc(p.phase)}</span>
              <span class="tb-proj-docs">${p.docs} docs · ${esc(p.updated)}</span>
            </div>
            <div class="pcard-tags" style="margin-top:5px">${p.tags.map(t => `<span class="pcard-tag">${esc(t)}</span>`).join("")}</div>
          </div>
        </div>
        <div class="tb-proj-right">
          <div class="tb-proj-actions">
            <button class="tb-proj-action-btn danger js-delete-proj">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:3px;vertical-align:-1px"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              Delete
            </button>
            ${actionBtn}
          </div>
        </div>
      `;
      row.querySelector(".js-open-proj")?.addEventListener("click", () => openProject(p));
      row.querySelector(".js-delete-proj")?.addEventListener("click", () => openDeleteProject(p, mgr));
      projSection.appendChild(row);
    });
  }
  wrapper.appendChild(projSection);
  return wrapper;
}

// ── Filters & search ──────────────────────────────────────────────
function bindFilters() {
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      filter.status = chip.dataset.status;
      renderContent();
    });
  });
}

function bindSearch() {
  const input = document.getElementById("searchInput");
  const btn   = document.getElementById("searchAskBtn");

  const go = () => {
    const q = input.value.trim();
    if (!q) { clearSearch(); return; }
    searchActive = true;
    const root = document.getElementById("dashResults");
    root.innerHTML = "";

    const header = document.createElement("div");
    header.className = "ps-search-header";
    header.innerHTML = `
      <span class="ps-search-query">AI Search — "${esc(q)}"</span>
      <button class="lc-btn lc-btn-ghost ps-clear-btn">✕ Clear</button>
    `;
    header.querySelector(".ps-clear-btn").addEventListener("click", () => {
      input.value = ""; clearSearch();
    });
    root.appendChild(header);

    const resultsEl = document.createElement("div");
    resultsEl.className = "ps-results";
    root.appendChild(resultsEl);
    runProjectSearch(q, resultsEl);
  };

  btn.addEventListener("click", go);
  input.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
}

function clearSearch() {
  searchActive = false;
  renderContent();
}

// ── Backend ───────────────────────────────────────────────────────
async function checkStatus() {
  const dot = document.getElementById("statusDot");
  const lbl = document.getElementById("statusLabel");
  try {
    const r = await fetch("/api/health");
    dot.className = r.ok ? "status-dot online" : "status-dot offline";
    lbl.textContent = r.ok ? "System online" : "Backend offline";
  } catch { dot.className = "status-dot offline"; lbl.textContent = "Backend offline"; }
}

async function loadIndexStats() {
  try {
    const r = await fetch("/api/index/stats");
    const d = await r.json();
    if (d.total_chunks) document.getElementById("statChunks").textContent = d.total_chunks;
    if (d.total_docs)   document.getElementById("statDocs").textContent   = d.total_docs;
  } catch { /* ignore */ }
}

function bindSignOut() {
  document.getElementById("signoutBtn")?.addEventListener("click", () => {
    sessionStorage.clear(); window.location.href = "/login";
  });
}

// ── Create Project modal ───────────────────────────────────────────
let _createProjTarget = null;  // the mgr object currently targeted

function openCreateProject(mgr) {
  _createProjTarget = mgr;

  // Label the modal with the team name
  document.getElementById("modalTeamBadge").textContent =
    `Team: ${mgr.team.name}`;

  // Clear form
  document.getElementById("cpName").value = "";
  document.getElementById("cpStatus").value = "planning";
  document.getElementById("cpNameError").classList.add("hidden");

  document.getElementById("createProjModal").classList.remove("hidden");
  document.getElementById("cpName").focus();
}

function closeCreateProject() {
  document.getElementById("createProjModal").classList.add("hidden");
  _createProjTarget = null;
}

async function submitCreateProject() {
  const name = document.getElementById("cpName").value.trim();
  if (!name) { document.getElementById("cpNameError").classList.remove("hidden"); return; }
  document.getElementById("cpNameError").classList.add("hidden");

  const status = document.getElementById("cpStatus").value;

  // Show loading state
  const submitBtn = document.getElementById("createProjSubmit");
  const btnLabel  = document.getElementById("createProjBtnLabel");
  submitBtn.disabled = true;
  btnLabel.textContent = "Generating…";

  // Call LLM to auto-generate description, phase, tags
  let desc = "", phase = "Discovery", tags = [status];
  try {
    const res = await fetch(`/api/project/generate?name=${encodeURIComponent(name)}&status=${encodeURIComponent(status)}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      desc  = data.desc  || "";
      phase = data.phase || "Discovery";
      tags  = data.tags?.length ? data.tags : [status];
    }
  } catch (_) { /* fall through to defaults */ }

  const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "")
    + "_" + Date.now();
  const today = new Date().toLocaleDateString("en-US", { month: "short", year: "numeric" });

  const project = {
    id, name, desc, status, phase, tags,
    docs: 0, updated: today,
    live: false, snippet: desc, _created: true,
  };

  // Save mgrId before closeCreateProject() nullifies _createProjTarget
  const targetMgrId = _createProjTarget.id;
  _createProjTarget.projects.push(project);

  // Find canonical dgId/dirId for navigation
  let targetDgId = null, targetDirId = null;
  for (const dg of ORG.dgs) {
    for (const dir of dg.directors) {
      if (dir.managers.some(m => m.id === targetMgrId)) {
        targetDgId = dg.id; targetDirId = dir.id;
      }
    }
  }

  // Persist to sessionStorage so it survives page refresh
  try {
    const saved = JSON.parse(sessionStorage.getItem("ti_created_projects") || "[]");
    saved.push({ mgrId: targetMgrId, project });
    sessionStorage.setItem("ti_created_projects", JSON.stringify(saved));
  } catch (_) {}

  // Reset button before closing
  submitBtn.disabled = false;
  btnLabel.textContent = "Create Project";

  closeCreateProject();
  navigate("team", targetDgId || nav.dgId, targetDirId || nav.dirId, targetMgrId);
  requestAnimationFrame(() => {
    const results = document.getElementById("dashResults");
    if (results) results.scrollTop = results.scrollHeight;
  });
}

function bindCreateProjectModal() {
  document.getElementById("createProjClose").addEventListener("click", closeCreateProject);
  document.getElementById("createProjCancel").addEventListener("click", closeCreateProject);
  document.getElementById("createProjSubmit").addEventListener("click", submitCreateProject);
  document.getElementById("createProjModal").addEventListener("click", e => {
    if (e.target === document.getElementById("createProjModal")) closeCreateProject();
  });
}

// ── Delete Project modal ───────────────────────────────────────────
let _deleteProjTarget = null;  // { project, mgr }

function openDeleteProject(project, mgr) {
  _deleteProjTarget = { project, mgr };
  document.getElementById("deleteProjNameHint").textContent = project.name;
  document.getElementById("deleteProjInput").value = "";
  document.getElementById("deleteProjError").classList.add("hidden");
  document.getElementById("deleteProjModal").classList.remove("hidden");
  document.getElementById("deleteProjInput").focus();
}

function closeDeleteProject() {
  document.getElementById("deleteProjModal").classList.add("hidden");
  _deleteProjTarget = null;
}

function confirmDeleteProject() {
  if (!_deleteProjTarget) return;
  const { project, mgr } = _deleteProjTarget;
  const typed = document.getElementById("deleteProjInput").value.trim();

  if (typed !== project.name) {
    document.getElementById("deleteProjError").classList.remove("hidden");
    document.getElementById("deleteProjInput").focus();
    return;
  }

  // Remove from manager's projects array
  mgr.projects = mgr.projects.filter(p => p.id !== project.id);

  // Remove from sessionStorage (user-created projects)
  try {
    const saved = JSON.parse(sessionStorage.getItem("ti_created_projects") || "[]");
    const updated = saved.filter(e => e.project.id !== project.id);
    sessionStorage.setItem("ti_created_projects", JSON.stringify(updated));
  } catch (_) {}

  // Remove associated project files from sessionStorage
  try {
    const store = JSON.parse(sessionStorage.getItem("ti_project_files") || "{}");
    delete store[project.id];
    sessionStorage.setItem("ti_project_files", JSON.stringify(store));
  } catch (_) {}

  closeDeleteProject();
  renderContent();
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("deleteProjClose").addEventListener("click", closeDeleteProject);
  document.getElementById("deleteProjCancel").addEventListener("click", closeDeleteProject);
  document.getElementById("deleteProjConfirm").addEventListener("click", confirmDeleteProject);
  document.getElementById("deleteProjModal").addEventListener("click", e => {
    if (e.target === document.getElementById("deleteProjModal")) closeDeleteProject();
  });
  // Allow Enter key to confirm
  document.getElementById("deleteProjInput").addEventListener("keydown", e => {
    if (e.key === "Enter") confirmDeleteProject();
  });
});
