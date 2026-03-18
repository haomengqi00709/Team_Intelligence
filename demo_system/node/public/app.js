/* ── Team Intelligence · app.js ──────────────────────────────────── */

// ── Auth guard ────────────────────────────────────────────────────
const SESSION = (() => {
  try { return JSON.parse(sessionStorage.getItem("ti_session") || "null"); } catch { return null; }
})();

const PROJECT = (() => {
  try { return JSON.parse(sessionStorage.getItem("ti_project") || "null"); } catch { return null; }
})();

if (!SESSION) { window.location.href = "/login"; }
else if (!PROJECT) { window.location.href = "/dashboard"; }
else { document.body.style.visibility = "visible"; }

const IS_TEAM = SESSION?.role === "team_member";

// ── Sample questions by role ──────────────────────────────────────
const SAMPLE_QUESTIONS_TEAM = [
  "Why was the geographic weight changed from 5% to 15%?",
  "What did Jason contribute technically to this project?",
  "Are there any conflicts or contradictions between documents?",
  "What should a new person read first to understand this project?",
  "Show the full compliance audit chain for the risk model.",
  "What is the role of ERAP in the streamlining filter?",
  "Who manages Jason and what is his scope?",
];

const SAMPLE_QUESTIONS_BRANCH = [
  "What is the NOP Risk Model Modernization project about?",
  "Who is responsible for the NOP project and how can I contact them?",
  "What branch or team owns the risk model work?",
  "Which projects are currently active under this branch?",
  "Who leads the data technical team?",
];

const SAMPLE_QUESTIONS = IS_TEAM ? SAMPLE_QUESTIONS_TEAM : SAMPLE_QUESTIONS_BRANCH;

const FILE_TYPE_COLORS = {
  email:          "var(--c-email)",
  meeting_minutes:"var(--c-meeting)",
  word_doc:       "var(--c-word)",
  policy_doc:     "var(--c-policy)",
  sas_script:     "var(--c-sas)",
  excel:          "var(--c-excel)",
  csv:            "var(--c-csv)",
  log_file:       "var(--c-log)",
  powerpoint:     "var(--c-ppt)",
  org_chart:      "var(--c-org)",
};

const QUERY_TYPE_LABELS = {
  causal_trace:        "Causal Analysis",
  contributor_profile: "Contributor Profile",
  conflict_detect:     "Conflict Detection",
  audit_chain:         "Audit Chain",
  onboarding:          "Onboarding Guide",
  org_lookup:          "Org Lookup",
  general:             "General",
};

const AVATAR_COLORS = [
  "#6366f1","#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#14b8a6","#f97316",
];

// ── State ─────────────────────────────────────────────────────────
let currentSources = [];
let allFileDocs    = [];   // populated by loadFileList, used by "/" picker
let fvDocCache     = {};   // docId → fetched doc data
let activeFileRow  = null; // currently highlighted row
let chatHistory    = [];   // [{role, content}] — kept in memory until refresh
const HISTORY_TURNS = 4;   // how many past exchanges to include as context

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  renderHeaderUser();
  renderBreadcrumb();
  applyRoleRestrictions();
  buildSampleList();
  loadFileList();
  checkBackendStatus();
  loadIndexStats();
  bindNav();
  bindInput();
  bindSignOut();
  bindBackBtn();
  bindFileViewer();
  bindAddFiles();
  bindNewVersion();
  if (PROJECT?.fresh) showFreshProjectStart();
  handlePrefillQuery();
});

function bindNewVersion() {
  const btn = document.getElementById("newVersionBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    showToast("Version management coming soon — this will let you snapshot the current project state and start a new iteration.");
  });
}

function showToast(msg) {
  let toast = document.getElementById("nvToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "nvToast";
    toast.className = "nv-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("show"), 3500);
}

function showFreshProjectStart() {
  const welcome = document.querySelector(".welcome-state");
  if (!welcome) return;

  welcome.innerHTML = `
    <div class="fresh-icon">
      <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
    </div>
    <p class="fresh-title">${esc(PROJECT.name)}</p>
    <p class="fresh-sub">This project was just created. Upload your files to start chatting with your documents.</p>
    <button class="fresh-upload-btn" id="freshUploadBtn">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
      Add Files
    </button>
    <p class="fresh-hint">Word, PDF, Excel, emails, meeting notes, SAS scripts and more</p>
  `;

  document.getElementById("freshUploadBtn").addEventListener("click", () => {
    document.getElementById("fileUploadInput").click();
  });
}

function renderHeaderUser() {
  if (!SESSION) return;
  document.getElementById("headerAvatar").style.background = SESSION.color;
  document.getElementById("headerAvatar").textContent      = SESSION.initials;
  document.getElementById("headerUserName").textContent    = SESSION.name;
  document.getElementById("headerUserTitle").textContent   = SESSION.title;

  const badge = document.getElementById("userAccessBadge");
  badge.textContent  = IS_TEAM ? "Full Access" : "Branch Viewer";
  badge.className    = `user-access-badge role-${SESSION.role}`;
}

function renderBreadcrumb() {
  if (PROJECT?.name) {
    document.getElementById("projectBreadcrumb").textContent =
      `Data Technical Branch  ›  ${PROJECT.name}`;
  }
}

function bindBackBtn() {
  document.getElementById("backBtn")?.addEventListener("click", () => {
    window.location.href = "/dashboard";
  });
}

function handlePrefillQuery() {
  const q = sessionStorage.getItem("ti_prefill_query");
  if (q) {
    sessionStorage.removeItem("ti_prefill_query");
    // Small delay so DOM is ready
    setTimeout(() => submitQuery(q), 300);
  }
}

function applyRoleRestrictions() {
  if (IS_TEAM) return;

  // Hide Timeline tab for branch viewers
  document.querySelector('[data-tab="graph"]').style.display = "none";

  // Add role banner below input
  const hint = document.querySelector(".input-hint");
  if (hint) {
    hint.innerHTML = `<span style="color:#f59e0b">⚠ Branch Viewer</span> — Answers are limited to project-level summaries and contact information. Internal documents are restricted.`;
  }
}

function bindSignOut() {
  document.getElementById("signoutBtn")?.addEventListener("click", () => {
    sessionStorage.removeItem("ti_session");
    window.location.href = "/login";
  });
}

// ── Navigation ────────────────────────────────────────────────────
function bindNav() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      tabs.forEach(t => t.classList.remove("active"));
      btn.classList.add("active");

      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      document.getElementById(`tab-${target}`).classList.add("active");

      if (target === "graph") {
        PROJECT?.live ? TL.init() : showProjectTabEmpty("tlContainer",
          "Timeline builds from your project files.",
          "Upload documents, meeting notes, or emails to generate a milestone timeline.");
      }
      if (target === "team") {
        PROJECT?.live ? loadTeam() : showProjectTabEmpty("teamContainer",
          "Team insights come from your project files.",
          "Upload files to discover contributors, roles, and activity across your project.");
      }
    });
  });
}

function showProjectTabEmpty(containerId, title, sub) {
  const el = document.getElementById(containerId);
  if (!el || el.dataset.emptyShown) return;
  el.dataset.emptyShown = "1";
  el.innerHTML = `
    <div class="project-tab-empty">
      <div class="pte-icon">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <p class="pte-title">${title}</p>
      <p class="pte-sub">${sub}</p>
      <button class="pte-btn" id="pteUploadBtn_${containerId}">
        Add Files
      </button>
    </div>
  `;
  document.getElementById(`pteUploadBtn_${containerId}`)?.addEventListener("click", () => {
    // Switch back to chat tab and trigger upload
    document.querySelector('[data-tab="chat"]')?.click();
    document.getElementById("fileUploadInput")?.click();
  });
}

// ── Sample questions (collapsible) ────────────────────────────────
function buildSampleList() {
  const toggle = document.getElementById("demoToggle");
  const list   = document.getElementById("sampleList");

  // Start collapsed
  list.style.display = "none";

  toggle.addEventListener("click", () => {
    const open = list.style.display !== "none";
    list.style.display = open ? "none" : "block";
    toggle.classList.toggle("open", !open);
  });

  SAMPLE_QUESTIONS.forEach(q => {
    const li = document.createElement("li");
    li.className = "sample-item";
    li.textContent = q;
    li.addEventListener("click", () => submitQuery(q));
    list.appendChild(li);
  });
}

// ── File upload ───────────────────────────────────────────────────
function bindAddFiles() {
  const btn   = document.getElementById("addFilesBtn");
  const input = document.getElementById("fileUploadInput");
  if (!btn || !input) return;
  btn.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    if (input.files.length) {
      Array.from(input.files).forEach(handleUpload);
      input.value = "";
    }
  });
}

async function handleUpload(file) {
  const pending = document.getElementById("uploadPending");

  // Show a pending row immediately
  const row = document.createElement("div");
  row.className = "file-row pending";
  row.innerHTML = `
    <span class="file-row-spinner"></span>
    <span class="file-row-name">${esc(file.name)}</span>
    <span class="file-row-status">Processing…</span>
  `;
  pending.appendChild(row);

  try {
    const form = new FormData();
    form.append("file", file);
    const uploadUrl = PROJECT?.id
      ? `/api/upload?project_id=${encodeURIComponent(PROJECT.id)}`
      : "/api/upload";
    const res  = await fetch(uploadUrl, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    pollUploadStatus(data.doc_id, row);
  } catch (err) {
    row.classList.add("upload-error");
    row.querySelector(".file-row-status").textContent = "Failed";
    row.title = err.message;
  }
}

function pollUploadStatus(docId, row) {
  const interval = setInterval(async () => {
    try {
      const res  = await fetch(`/api/upload/status/${encodeURIComponent(docId)}`);
      const data = await res.json();
      if (data.status === "ready") {
        clearInterval(interval);
        row.remove();
        if (!PROJECT?.live) addProjectDocId(docId); // track for non-live projects
        loadFileList();
      } else if (data.status === "error") {
        clearInterval(interval);
        row.classList.add("upload-error");
        row.querySelector(".file-row-status").textContent = "Error";
        row.title = data.message || "Processing failed";
      }
    } catch (_) { /* keep polling */ }
  }, 2000);
}

// ── Per-project file tracking ──────────────────────────────────────
function getProjectDocIds() {
  if (!PROJECT?.id) return null; // null = no filter
  try {
    const store = JSON.parse(sessionStorage.getItem("ti_project_files") || "{}");
    return store[PROJECT.id] || [];
  } catch { return []; }
}

function addProjectDocId(docId) {
  if (!PROJECT?.id) return;
  try {
    const store = JSON.parse(sessionStorage.getItem("ti_project_files") || "{}");
    if (!store[PROJECT.id]) store[PROJECT.id] = [];
    if (!store[PROJECT.id].includes(docId)) store[PROJECT.id].push(docId);
    sessionStorage.setItem("ti_project_files", JSON.stringify(store));
  } catch {}
}

// ── File list ─────────────────────────────────────────────────────
const FOLDER_LABELS = {
  work: "Work Documents", meetings: "Meetings",
  documents: "Documents", email: "Emails",
  spreadsheets: "Spreadsheets", presentations: "Presentations",
  sas_code: "SAS Scripts", logs: "Logs", other: "Other",
  pdf: "PDFs",
};
const FOLDER_ICONS = {
  work: "📄", meetings: "📋",
  documents: "📄", email: "✉️",
  spreadsheets: "📊", presentations: "📑",
  sas_code: "💻", logs: "🗒️", other: "📁",
  pdf: "📕",
};

// Folder display order (pre-loaded first, then upload types)
const FOLDER_ORDER = ["meetings", "work", "documents", "email", "spreadsheets", "presentations", "sas_code", "logs", "other"];

async function loadFileList() {
  const container = document.getElementById("fileList");
  try {
    const r    = await fetch("/api/docs");
    const data = await r.json();

    // All successfully parsed docs (any folder)
    let docs = (data.docs || []).filter(d => d.parse_status === "success");

    // For non-live projects, show only files uploaded to this project
    if (!PROJECT?.live) {
      const allowed = getProjectDocIds();
      docs = docs.filter(d => allowed.includes(d.doc_id));
    }

    allFileDocs = docs;
    container.innerHTML = "";

    if (!docs.length) {
      container.innerHTML = `<div class="file-list-empty">${
        PROJECT?.live ? "No files indexed yet." : "No files yet — add files above."
      }</div>`;
      return;
    }

    // Group by source_folder
    const groups = {};
    docs.forEach(d => { (groups[d.source_folder] ??= []).push(d); });

    // Render in defined order, then any remaining folders alphabetically
    const ordered = [...FOLDER_ORDER, ...Object.keys(groups).filter(f => !FOLDER_ORDER.includes(f)).sort()];
    ordered.forEach(folder => {
      if (!groups[folder]?.length) return;
      container.appendChild(buildFolderGroup(folder, groups[folder]));
    });
  } catch {
    container.innerHTML = `<div class="file-list-empty">Could not load files.</div>`;
  }
}

function buildFolderGroup(folder, docs) {
  const group = document.createElement("div");
  group.className = "file-group";

  const header = document.createElement("button");
  header.className = "file-group-header open";
  header.innerHTML = `
    <svg class="fg-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
    <span>${FOLDER_ICONS[folder] || "📁"} ${FOLDER_LABELS[folder] || folder}</span>
    <span class="fg-count">${docs.length}</span>
  `;

  const list = document.createElement("div");
  list.className = "file-group-list";

  header.addEventListener("click", () => {
    const open = header.classList.toggle("open");
    list.style.display = open ? "block" : "none";
  });

  docs.forEach(doc => list.appendChild(buildFileRow(doc)));
  group.append(header, list);
  return group;
}

function buildFileRow(doc) {
  const color = FILE_TYPE_COLORS[doc.file_type] || "#94a3b8";
  const row = document.createElement("div");
  row.className = "file-row";
  row.innerHTML = `
    <span class="file-type-dot" style="background:${color}"></span>
    <span class="file-row-name">${esc(doc.doc_id)}</span>
  `;
  row.addEventListener("click", () => {
    if (activeFileRow) activeFileRow.classList.remove("active");
    activeFileRow = row;
    row.classList.add("active");
    openFileViewer(doc);
  });
  return row;
}

// ── File viewer ───────────────────────────────────────────────────
async function openFileViewer(doc) {
  const viewer  = document.getElementById("fileViewer");
  const divider = document.getElementById("fvDivider");
  const title   = document.getElementById("fvTitle");
  const typeDot = document.getElementById("fvTypeDot");
  const meta    = document.getElementById("fvMeta");
  const body    = document.getElementById("fvBody");

  const color = FILE_TYPE_COLORS[doc.file_type] || "#94a3b8";
  const label = (doc.file_type || "").replace(/_/g, " ");

  viewer.classList.remove("hidden");
  divider.classList.remove("hidden");
  title.textContent        = doc.doc_id;
  typeDot.style.background = color;
  body.textContent         = "Loading…";
  meta.innerHTML           = "";

  document.getElementById("fvRefBtn").onclick = () => referenceFile(doc.doc_id);

  if (!fvDocCache[doc.doc_id]) {
    try {
      const r = await fetch(`/api/docs/${encodeURIComponent(doc.doc_id)}`);
      fvDocCache[doc.doc_id] = await r.json();
    } catch {
      body.textContent = "Could not load file.";
      return;
    }
  }

  const d = fvDocCache[doc.doc_id];
  meta.innerHTML = `
    <span class="fv-chip" style="color:${color};border-color:${color}25;background:${color}12">${esc(label)}</span>
    ${d.event_date   ? `<span class="fv-chip">${esc(d.event_date)}</span>`    : ""}
    ${d.author       ? `<span class="fv-chip">${esc(d.author)}</span>`        : ""}
    ${doc.word_count ? `<span class="fv-chip">${doc.word_count} words</span>` : ""}
  `;
  body.textContent = d.raw_text || "(no content)";
}

function referenceFile(docId) {
  const input = document.getElementById("queryInput");
  const ref   = `[file: ${docId}] `;
  const pos   = input.selectionStart;
  input.value = input.value.slice(0, pos) + ref + input.value.slice(pos);
  input.focus();
  input.setSelectionRange(pos + ref.length, pos + ref.length);
}

function bindFileViewer() {
  // Close button
  document.getElementById("fvCloseBtn").addEventListener("click", () => {
    document.getElementById("fileViewer").classList.add("hidden");
    document.getElementById("fvDivider").classList.add("hidden");
    if (activeFileRow) { activeFileRow.classList.remove("active"); activeFileRow = null; }
  });

  // Drag-to-resize
  const divider = document.getElementById("fvDivider");
  const viewer  = document.getElementById("fileViewer");
  const panel   = document.querySelector(".chat-panel");
  let dragging  = false;

  divider.addEventListener("mousedown", () => {
    dragging = true;
    document.body.style.cssText += ";cursor:col-resize;user-select:none";
    divider.classList.add("dragging");
  });
  document.addEventListener("mousemove", e => {
    if (!dragging) return;
    const rect  = panel.getBoundingClientRect();
    const width = Math.max(240, Math.min(rect.width * 0.75, e.clientX - rect.left));
    viewer.style.width = width + "px";
  });
  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    divider.classList.remove("dragging");
  });
}

// ── Backend status ────────────────────────────────────────────────
async function checkBackendStatus() {
  const dot   = document.getElementById("statusDot");
  const label = document.getElementById("statusLabel");
  try {
    const r = await fetch("/api/health");
    if (r.ok) {
      dot.className   = "status-dot online";
      label.textContent = "System online";
    } else {
      throw new Error("non-ok");
    }
  } catch {
    dot.className   = "status-dot offline";
    label.textContent = "Backend offline";
  }
}

// ── Index stats ───────────────────────────────────────────────────
async function loadIndexStats() {
  try {
    const r    = await fetch("/api/index/stats");
    const data = await r.json();
    document.getElementById("statChunks").textContent = data.total_chunks ?? "—";
    document.getElementById("statDocs").textContent   = data.total_docs   ?? "—";
  } catch { /* ignore */ }
}

// ── Chat input ────────────────────────────────────────────────────
let pickerActive   = false;
let pickerSelected = 0;

function bindInput() {
  const input = document.getElementById("queryInput");
  const btn   = document.getElementById("sendBtn");

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
    handleSlashTrigger(input);
  });

  input.addEventListener("keydown", e => {
    if (pickerActive && handlePickerKey(e, input)) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      triggerSend();
    }
  });

  // Dismiss picker on outside click
  document.addEventListener("click", e => {
    if (!e.target.closest("#filePicker") && !e.target.closest("#queryInput")) {
      hideFilePicker();
    }
  });

  btn.addEventListener("click", triggerSend);
}

// ── Slash-command file picker ─────────────────────────────────────
function handleSlashTrigger(input) {
  const val    = input.value;
  const cursor = input.selectionStart;
  const before = val.slice(0, cursor);
  const slash  = before.lastIndexOf("/");

  if (slash === -1) { hideFilePicker(); return; }

  const afterSlash = before.slice(slash + 1);
  if (afterSlash.includes(" ")) { hideFilePicker(); return; }

  const query   = afterSlash.toLowerCase();
  const matches = allFileDocs
    .filter(d => !query || d.doc_id.toLowerCase().includes(query))
    .slice(0, 8);

  if (!matches.length) { hideFilePicker(); return; }

  let picker = document.getElementById("filePicker");
  if (!picker) {
    picker = document.createElement("div");
    picker.id = "filePicker";
    picker.className = "file-picker";
    document.querySelector(".chat-input-wrap").appendChild(picker);
  }

  pickerActive   = true;
  pickerSelected = 0;

  picker.innerHTML = matches.map((d, i) => {
    const color = FILE_TYPE_COLORS[d.file_type] || "#94a3b8";
    return `<div class="fp-item${i === 0 ? " selected" : ""}" data-id="${esc(d.doc_id)}" data-idx="${i}">
      <span class="fp-item-dot" style="background:${color}"></span>
      <span class="fp-item-name">${esc(d.doc_id)}</span>
      <span class="fp-item-type">${esc((d.file_type || "").replace(/_/g, " "))}</span>
    </div>`;
  }).join("");

  picker.style.display = "block";
  picker.querySelectorAll(".fp-item").forEach(item => {
    item.addEventListener("mousedown", e => {
      e.preventDefault();
      const slashPos = input.value.slice(0, input.selectionStart).lastIndexOf("/");
      selectPickerItem(item.dataset.id, slashPos, input);
    });
  });
}

function hideFilePicker() {
  pickerActive = false;
  const p = document.getElementById("filePicker");
  if (p) p.style.display = "none";
}

function handlePickerKey(e, input) {
  const picker = document.getElementById("filePicker");
  const items  = picker?.querySelectorAll(".fp-item");
  if (!items?.length) return false;

  if (e.key === "ArrowDown") {
    e.preventDefault();
    pickerSelected = Math.min(pickerSelected + 1, items.length - 1);
    items.forEach((it, i) => it.classList.toggle("selected", i === pickerSelected));
    return true;
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    pickerSelected = Math.max(pickerSelected - 1, 0);
    items.forEach((it, i) => it.classList.toggle("selected", i === pickerSelected));
    return true;
  }
  if (e.key === "Enter" || e.key === "Tab") {
    e.preventDefault();
    const sel = items[pickerSelected];
    if (sel) {
      const slashPos = input.value.slice(0, input.selectionStart).lastIndexOf("/");
      selectPickerItem(sel.dataset.id, slashPos, input);
    }
    return true;
  }
  if (e.key === "Escape") { hideFilePicker(); return true; }
  return false;
}

function selectPickerItem(docId, slashPos, input) {
  const after   = input.value.slice(input.selectionStart);
  const ref     = `[file: ${docId}] `;
  input.value   = input.value.slice(0, slashPos) + ref + after;
  const newPos  = slashPos + ref.length;
  input.focus();
  input.setSelectionRange(newPos, newPos);
  hideFilePicker();
}

function triggerSend() {
  const input = document.getElementById("queryInput");
  const q = input.value.trim();
  if (!q) return;
  input.value = "";
  input.style.height = "auto";
  submitQuery(q);
}

// ── Query pipeline ────────────────────────────────────────────────
async function submitQuery(query) {
  clearWelcome();
  appendMessage("user", query);
  const loadEl = appendLoading();
  setInputEnabled(false);

  try {
    // Build query with conversation context prepended
    const contextBlock = buildContextBlock();
    const baseQuery = contextBlock ? `${contextBlock}\nCurrent question: ${query}` : query;
    const scopedQuery = IS_TEAM
      ? baseQuery
      : `[BRANCH VIEWER — provide only project-level summary and responsible contact names, no internal document details] ${baseQuery}`;

    const params = new URLSearchParams({ q: scopedQuery, n: 10 });
    // Only scope by project_id for non-live projects; live projects search all pre-indexed docs
    if (PROJECT?.id && !PROJECT?.live) params.set("project_id", PROJECT.id);
    const r    = await fetch(`/api/query?${params}`, { method: "POST" });
    const data = await r.json();

    // Store this exchange in history
    chatHistory.push({ role: "user",      content: query });
    chatHistory.push({ role: "assistant", content: data.answer || "" });
    // Trim to last N turns (each turn = 2 entries)
    if (chatHistory.length > HISTORY_TURNS * 2) {
      chatHistory = chatHistory.slice(-HISTORY_TURNS * 2);
    }

    loadEl.remove();
    appendAssistantMessage(data);
    renderSources(data.all_sources || []);
  } catch (err) {
    loadEl.remove();
    appendMessage("assistant", `Error: ${err.message}`);
  } finally {
    setInputEnabled(true);
  }
}

function buildContextBlock() {
  if (!chatHistory.length) return "";
  const lines = chatHistory.map(m =>
    m.role === "user"
      ? `User: ${m.content}`
      : `Assistant: ${m.content.slice(0, 400)}${m.content.length > 400 ? "…" : ""}`
  );
  return `[Conversation so far:\n${lines.join("\n")}\n]`;
}

// ── Message rendering ─────────────────────────────────────────────
function clearWelcome() {
  const welcome = document.querySelector(".welcome-state");
  if (welcome) welcome.remove();
}

function appendMessage(role, text) {
  const wrap = document.getElementById("chatMessages");
  const div  = document.createElement("div");
  div.className = `message message--${role}`;

  const bubble = document.createElement("div");
  bubble.className = `bubble bubble--${role}`;
  bubble.textContent = text;

  div.appendChild(bubble);
  wrap.appendChild(div);
  scrollToBottom();
  return div;
}

function appendLoading() {
  const wrap = document.getElementById("chatMessages");
  const div  = document.createElement("div");
  div.className = "message message--assistant message--loading";

  div.innerHTML = `<div class="bubble bubble--assistant">
    <div class="dot-anim">
      <span></span><span></span><span></span>
    </div>
    <span>Analyzing documents…</span>
  </div>`;

  wrap.appendChild(div);
  scrollToBottom();
  return div;
}

function appendAssistantMessage(data) {
  const wrap = document.getElementById("chatMessages");
  const div  = document.createElement("div");
  div.className = "message message--assistant";

  // Meta row
  const meta = document.createElement("div");
  meta.className = "message-meta";

  const qtype = data.query_type || "general";
  const badge = document.createElement("span");
  badge.className = `query-type-badge badge-${qtype}`;
  badge.textContent = QUERY_TYPE_LABELS[qtype] || qtype;
  meta.appendChild(badge);

  if (typeof data.retrieval_count === "number") {
    const rc = document.createElement("span");
    rc.textContent = `${data.retrieval_count} sources`;
    meta.appendChild(rc);
  }

  div.appendChild(meta);

  // Bubble
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble--assistant";
  bubble.innerHTML = renderAnswer(data.answer || "");

  div.appendChild(bubble);
  wrap.appendChild(div);
  scrollToBottom();
}

function renderAnswer(text) {
  // Escape HTML, then linkify [Source: X] citations
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped.replace(
    /\[Source:\s*([^\]]+)\]/g,
    (_, id) => `<span class="cite-ref" title="${id.trim()}">[${id.trim()}]</span>`
  );
}

function scrollToBottom() {
  const wrap = document.getElementById("chatMessages");
  wrap.scrollTop = wrap.scrollHeight;
}

function setInputEnabled(on) {
  document.getElementById("queryInput").disabled = !on;
  document.getElementById("sendBtn").disabled    = !on;
}

// ── Sources panel ─────────────────────────────────────────────────
function renderSources(sources) {
  currentSources = sources;
  const list  = document.getElementById("sourcesList");
  const count = document.getElementById("sourcesCount");

  list.innerHTML = "";

  if (!sources.length) {
    list.innerHTML = `<div class="sources-empty">No sources returned.</div>`;
    count.textContent = "";
    return;
  }

  const cited   = sources.filter(s => s.cited);
  const uncited = sources.filter(s => !s.cited);

  count.textContent = `${cited.length} cited`;

  [...cited, ...uncited].forEach(src => {
    list.appendChild(buildSourceCard(src));
  });
}

function buildSourceCard(src) {
  const color   = FILE_TYPE_COLORS[src.file_type] || "var(--c-log)";
  const card    = document.createElement("div");
  const restricted = !IS_TEAM && src.file_type !== "org_chart";
  card.className = `source-card${src.cited ? "" : " is-uncited"}${restricted ? " is-restricted" : ""}`;
  card.style.borderLeftColor = color;

  const typeName = (src.file_type || "").replace(/_/g, " ");

  card.innerHTML = `
    <div class="source-card-top">
      <div class="source-doc-id">${esc(src.doc_id)}</div>
      ${src.cited ? `<span class="source-cited-badge">Cited</span>` : ""}
    </div>
    <div class="source-meta">
      ${src.file_type ? `<span class="source-chip type-chip" style="color:${color};border-color:${color}20;background:${color}12">${esc(typeName)}</span>` : ""}
      ${src.event_date ? `<span class="source-chip">${esc(src.event_date)}</span>` : ""}
      ${src.author ? `<span class="source-chip">${esc(src.author)}</span>` : ""}
    </div>
    ${src.excerpt ? `<div class="source-excerpt">${esc(src.excerpt)}</div>` : ""}
  `;
  return card;
}

// ── Team tab ──────────────────────────────────────────────────────
let teamLoaded = false;

async function loadTeam() {
  if (teamLoaded) return;
  const container = document.getElementById("teamContainer");

  try {
    const summaryUrl = (PROJECT?.id && !PROJECT?.live)
      ? `/api/team/summary?project_id=${encodeURIComponent(PROJECT.id)}`
      : "/api/team/summary";
    const [orgRes, summaryRes] = await Promise.all([
      fetch("/api/graph/org"),
      fetch(summaryUrl),
    ]);
    const [orgData, summaryData] = await Promise.all([orgRes.json(), summaryRes.json()]);

    teamLoaded = true;
    container.innerHTML = "";
    renderTeamView(container, orgData, summaryData.members || []);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--text-muted);padding:40px">Could not load team data: ${err.message}</p>`;
  }
}

function renderTeamView(container, data, summaryMembers) {
  const teams  = data.teams  || {};
  const people = data.people || {};

  // ── Project Roles intro section ──────────────────────────────────
  if (summaryMembers && summaryMembers.length) {
    const intro = document.createElement("div");
    intro.className = "team-intro";

    const hdr = document.createElement("div");
    hdr.className = "team-intro-header";
    hdr.innerHTML = `
      <div class="team-intro-title">Project Contributions</div>
      <div class="team-intro-sub">Who did what on the NOP Risk Score Model Modernization</div>`;
    intro.appendChild(hdr);

    // Sort: core first, then supporting, then external
    const order = { core: 0, supporting: 1, external: 2 };
    const sorted = [...summaryMembers].sort((a, b) =>
      (order[a.involvement] ?? 3) - (order[b.involvement] ?? 3));

    const grid = document.createElement("div");
    grid.className = "team-intro-grid";
    sorted.forEach(m => grid.appendChild(buildRoleCard(m)));
    intro.appendChild(grid);
    container.appendChild(intro);

    // Divider
    const sep = document.createElement("div");
    sep.className = "team-intro-sep";
    container.appendChild(sep);
  }

  // ── Org structure (existing) ──────────────────────────────────────
  const teamMap = {};
  Object.entries(teams).forEach(([tid, team]) => {
    teamMap[tid] = { ...team, memberData: {} };
    (team.members || []).forEach(name => {
      if (people[name]) teamMap[tid].memberData[name] = people[name];
    });
  });

  const allTeamMembers = new Set(Object.values(teams).flatMap(t => t.members || []));
  const unaffiliated   = Object.entries(people).filter(([name]) => !allTeamMembers.has(name));

  Object.entries(teamMap).forEach(([tid, team]) => {
    container.appendChild(buildTeamBlock(team, tid));
  });

  if (unaffiliated.length) {
    const title = document.createElement("div");
    title.className = "team-section-title";
    title.textContent = "Individual Contributors";
    container.appendChild(title);

    const grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px";
    unaffiliated.forEach(([name, pdata]) => {
      grid.appendChild(buildPersonCard(name, pdata));
    });
    container.appendChild(grid);
  }
}

function buildRoleCard(m) {
  const INVOLVEMENT_STYLE = {
    core:       { bg: "#eff6ff", border: "#bfdbfe", text: "#1d4ed8", label: "Core" },
    supporting: { bg: "#f0fdf4", border: "#bbf7d0", text: "#15803d", label: "Supporting" },
    external:   { bg: "#f8fafc", border: "#e2e8f0", text: "#64748b", label: "External" },
  };
  const inv    = (m.involvement || "supporting").toLowerCase();
  const style  = INVOLVEMENT_STYLE[inv] || INVOLVEMENT_STYLE.supporting;
  const initials = m.name.replace(/^(Dr|Mr|Ms|Mrs|Prof)\.\s*/i, "")
    .trim().split(/\s+/).filter(Boolean)
    .map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const color = AVATAR_COLORS[m.name.charCodeAt(0) % AVATAR_COLORS.length];
  const contribs = (m.key_contributions || []).slice(0, 4)
    .map(c => `<span class="role-contrib">${esc(c)}</span>`).join("");

  const card = document.createElement("div");
  card.className = "role-card";
  card.innerHTML = `
    <div class="role-card-top">
      <div class="person-avatar" style="background:${color}">${initials}</div>
      <div class="role-card-name-wrap">
        <div class="role-card-name">${esc(m.name)}</div>
        <span class="role-inv-badge" style="background:${style.bg};border-color:${style.border};color:${style.text}">${style.label}</span>
      </div>
    </div>
    <div class="role-card-desc">${esc(m.project_role || "")}</div>
    ${contribs ? `<div class="role-contribs">${contribs}</div>` : ""}
  `;
  return card;
}

function buildTeamBlock(team, tid) {
  const icons = { nop_project: "🏗️", data_technical: "📊" };
  const icon  = icons[tid] || "👥";

  const block = document.createElement("div");
  block.className = "team-block";

  block.innerHTML = `
    <div class="team-block-header">
      <div class="team-icon" style="background:var(--primary-light)">${icon}</div>
      <div class="team-block-meta">
        <div class="team-block-name">${esc(team.name || tid)}</div>
        <div class="team-block-goal">${esc(team.goal || "")}</div>
      </div>
      ${team.lead ? `<div class="team-lead-badge">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        Lead: ${esc(team.lead)}
      </div>` : ""}
    </div>
    <div class="team-members-grid" id="members-${tid}"></div>
  `;

  const grid = block.querySelector(`#members-${tid}`);
  Object.entries(team.memberData || {}).forEach(([name, pdata]) => {
    grid.appendChild(buildPersonCard(name, pdata));
  });

  return block;
}

function buildPersonCard(name, pdata) {
  const card = document.createElement("div");
  card.className = "person-card";

  const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const color    = AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];

  const empType = (pdata.employment_type || "").toLowerCase();
  const empClass = empType.includes("staff") ? "emp-staff"
                 : empType.includes("contractor") ? "emp-contractor"
                 : "emp-consultant";

  const skills = (pdata.skills || []).slice(0, 6);
  const skillsHtml = skills.map(s => `<span class="skill-tag">${esc(s)}</span>`).join("");

  card.innerHTML = `
    <div class="person-card-top">
      <div class="person-avatar" style="background:${color}">${initials}</div>
      <div>
        <div class="person-name">${esc(name)}</div>
        <div class="person-title">${esc(pdata.title || "")}</div>
      </div>
      ${pdata.employment_type ? `<span class="person-emp-badge ${empClass}">${esc(pdata.employment_type)}</span>` : ""}
    </div>
    ${pdata.scope ? `<div class="person-scope">${esc(pdata.scope)}</div>` : ""}
    ${skills.length ? `<div class="person-skills">${skillsHtml}</div>` : ""}
    ${pdata.reports_to ? `
      <div class="person-reports">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        Reports to ${esc(pdata.reports_to)}
      </div>` : ""}
  `;
  return card;
}

// ── Helpers ───────────────────────────────────────────────────────
function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
