/* ── Timeline — LLM milestone cards ────────────────────────────────────────
   Fetches /api/timeline/summary (cached on backend).
   Renders a vertical card timeline grouped by milestone.
   ─────────────────────────────────────────────────────────────────────────── */

const TL = (() => {

  const PHASE_COLOR = {
    initiation:  { bg: "#eff6ff", border: "#bfdbfe", text: "#1d4ed8" },
    planning:    { bg: "#f0fdf4", border: "#bbf7d0", text: "#15803d" },
    analysis:    { bg: "#fefce8", border: "#fde68a", text: "#b45309" },
    review:      { bg: "#fdf4ff", border: "#e9d5ff", text: "#7e22ce" },
    approval:    { bg: "#fff7ed", border: "#fed7aa", text: "#c2410c" },
    operations:  { bg: "#f0f9ff", border: "#bae6fd", text: "#0369a1" },
  };

  const PHASE_LABELS = {
    initiation: "Initiation", planning: "Planning",
    analysis: "Analysis",    review: "Review",
    approval: "Approval",    operations: "Operations",
  };

  let allMilestones = [];
  let activePhase   = "all";

  // ── Helpers ────────────────────────────────────────────────────────────
  function avatarInitials(name) {
    if (!name) return "?";
    const clean = name.replace(/^(Dr|Mr|Ms|Mrs|Prof)\.\s*/i, "").trim();
    const parts  = clean.split(/\s+/);
    return parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : clean.slice(0, 2).toUpperCase();
  }

  // Simple deterministic colour from a name string
  function nameColor(name) {
    const palette = ["#6366f1","#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#0ea5e9","#ec4899"];
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
    return palette[Math.abs(h) % palette.length];
  }

  // ── Render one milestone card ──────────────────────────────────────────
  function buildCard(m) {
    const phase  = (m.phase || "").toLowerCase();
    const colors = PHASE_COLOR[phase] || { bg: "#f8fafc", border: "#e2e8f0", text: "#475569" };
    const phaseLabel = PHASE_LABELS[phase] || phase;

    const participants = (m.participants || []).slice(0, 6);
    const docCount     = (m.docs || []).length;

    const avatars = participants.map(p => `
      <span class="tl-avatar" style="background:${nameColor(p)}" title="${p}">
        ${avatarInitials(p)}
      </span>`).join("");

    const extra = m.participants && m.participants.length > 6
      ? `<span class="tl-avatar tl-avatar-more">+${m.participants.length - 6}</span>`
      : "";

    return `
      <div class="tl-card" data-phase="${phase}">
        <div class="tl-marker">
          <div class="tl-dot" style="background:${colors.border}; border-color:${colors.text}"></div>
        </div>
        <div class="tl-card-body">
          <div class="tl-card-head">
            <span class="tl-date">${m.date_range || ""}</span>
            <span class="tl-phase-badge" style="background:${colors.bg};border-color:${colors.border};color:${colors.text}">
              ${phaseLabel}
            </span>
          </div>
          <div class="tl-card-title">${m.title || ""}</div>
          <div class="tl-card-summary">${m.summary || ""}</div>
          <div class="tl-card-footer">
            <div class="tl-avatars">${avatars}${extra}</div>
            ${docCount ? `<span class="tl-doc-count">${docCount} doc${docCount > 1 ? "s" : ""}</span>` : ""}
          </div>
        </div>
      </div>`;
  }

  // ── Render all cards ───────────────────────────────────────────────────
  function render() {
    const filtered = activePhase === "all"
      ? allMilestones
      : allMilestones.filter(m => (m.phase || "").toLowerCase() === activePhase);

    const container = document.getElementById("tlCards");
    if (!container) return;

    if (!filtered.length) {
      container.innerHTML = `<div class="tl-empty">No milestones for this phase.</div>`;
      return;
    }

    container.innerHTML = filtered.map(buildCard).join("");
  }

  // ── Phase filter pills ─────────────────────────────────────────────────
  function bindPills() {
    document.querySelectorAll(".tl-pill").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tl-pill").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        activePhase = btn.dataset.phase;
        render();
      });
    });
  }

  // ── Public init ────────────────────────────────────────────────────────
  async function init() {
    const loading = document.getElementById("tlLoading");
    const board   = document.getElementById("tlBoard");
    if (!loading || !board) return;

    loading.style.display = "flex";
    board.style.display   = "none";

    try {
      const PROJECT = (() => { try { return JSON.parse(sessionStorage.getItem("ti_project") || "null"); } catch { return null; } })();
      // Only scope by project_id for non-live projects; live projects use all pre-indexed docs
      const tlUrl = (PROJECT?.id && !PROJECT?.live)
        ? `/api/timeline/summary?project_id=${encodeURIComponent(PROJECT.id)}`
        : "/api/timeline/summary";
      const res  = await fetch(tlUrl);
      const data = await res.json();
      allMilestones = data.milestones || [];
    } catch (err) {
      loading.innerHTML = `<span style="color:#ef4444">Failed to load timeline: ${err.message}</span>`;
      return;
    }

    loading.style.display = "none";
    board.style.display   = "block";

    bindPills();
    render();
  }

  return { init };
})();
