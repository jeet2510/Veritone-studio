const state = { user: null, currentRun: null, history: [], authMode: "login" };

const escapeHtml = (value) => String(value ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const number = (value) => Number(value || 0).toLocaleString();
const score = (value) => Number(value || 0).toFixed(1);

function showAuthMode(mode) {
  state.authMode = mode;
  document.querySelectorAll(".auth-switch-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.authMode === mode);
  });
  document.getElementById("authSubmit").innerHTML = `${mode === "login" ? "Sign in" : "Create account"} <span aria-hidden="true">→</span>`;
  document.getElementById("authPassword").autocomplete = mode === "login" ? "current-password" : "new-password";
  document.getElementById("passwordHint").hidden = mode !== "register";
  document.getElementById("authStatus").textContent = "";
}

function showWorkspace(user) {
  state.user = user;
  document.getElementById("authScreen").hidden = true;
  document.getElementById("studioApp").hidden = false;
  window.scrollTo(0, 0);
  document.getElementById("accountName").textContent = user.username;
  document.getElementById("accountRole").textContent = user.role.toUpperCase();
  document.getElementById("adminNav").hidden = user.role !== "admin";
  document.getElementById("footerMode").textContent = "HEURISTIC ANALYSIS AVAILABLE · GEMINI OPTIONAL";
  loadHistory().then((rows) => {
    if (rows.length) return VeriToneAPI.fetchAnalysisById(rows[0].id).then(renderRun);
    return undefined;
  }).catch((error) => setStatus(error.message, "error"));
}

function setStatus(message, kind = "") {
  const status = document.getElementById("statusBox");
  status.textContent = message;
  status.dataset.state = kind;
}

function switchTab(tabName) {
  if (tabName === "admin" && state.user?.role !== "admin") return;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
  if (tabName === "history") loadHistory().catch((error) => setStatus(error.message, "error"));
  if (tabName === "admin") loadAdmin().catch((error) => window.alert(error.message));
}

function renderRun(run) {
  state.currentRun = run;
  document.getElementById("activeTitle").textContent = `Run #${run.id} · ${run.source_name}`;
  document.getElementById("runCountLabel").textContent = `RUN ${String(run.id).padStart(4, "0")}`;
  document.getElementById("kpiScore").textContent = `${score(run.before_score)} → ${score(run.after_score)}`;
  document.getElementById("kpiChanges").textContent = number(run.total_changes);
  document.getElementById("kpiPct").textContent = `${score(run.change_percentage)}%`;
  document.getElementById("kpiWords").textContent = number(run.word_count);
  document.getElementById("sourcePreview").textContent = run.original_text;
  document.getElementById("humanizedPreview").textContent = run.humanized_text;
  document.getElementById("sourceScore").textContent = `${score(run.before_score)} / 100`;
  document.getElementById("outputScore").textContent = `${score(run.after_score)} / 100`;
  document.getElementById("exportBar").innerHTML = `
    <a href="/api/analyses/${run.id}/download/humanized">Export .txt ↓</a>
    <a href="/api/analyses/${run.id}/download/report">Full report .json ↓</a>`;
  document.getElementById("changeSummaryLine").textContent =
    `${number(run.total_changes)} edits · ${score(run.change_percentage)}% estimated word impact · ${number(run.changed_sentences)} of ${number(run.total_sentences)} sentences changed.`;
  document.getElementById("engineNote").textContent = run.engine_mode === "gemini"
    ? "Gemini-assisted analysis · contextual pattern scores are estimates, not evidence of authorship."
    : "Heuristic-only analysis · linguistic signals are estimates, not evidence of authorship.";

  const changes = run.changes || [];
  document.getElementById("changesTableBody").innerHTML = changes.length
    ? changes.map((change, index) => `<tr><td>${index + 1}</td><td>${change.sentence_index}</td><td>${escapeHtml(change.change_type.replaceAll("_", " "))}</td><td>${escapeHtml(change.before)}</td><td>${escapeHtml(change.after)}</td></tr>`).join("")
    : '<tr><td colspan="5" class="empty-cell">No changes were recorded for this run.</td></tr>';
  renderMetrics(run);
}

function metricColumn(title, metrics, fallbackScore) {
  const report = metrics || {};
  const hits = report.cliche_hits || [];
  const flagged = report.flagged_sentences || [];
  return `<section class="metric-column"><h2>${title}</h2>
    <div class="metric-line"><span>Pattern score</span><strong>${score(report.ai_score ?? fallbackScore)} / 100</strong></div>
    <div class="metric-line"><span>Average sentence length</span><strong>${score(report.avg_sentence_len)} words</strong></div>
    <div class="metric-line"><span>Sentence length deviation</span><strong>${score(report.sentence_len_stdev)} words</strong></div>
    <div class="metric-line"><span>Burstiness</span><strong>${score(report.burstiness)}</strong></div>
    <div class="metric-line"><span>Lexical diversity</span><strong>${score(report.lexical_diversity)}</strong></div>
    <div class="metric-diagnostics"><strong>Cliché diagnostics · ${hits.length}</strong><p>${hits.length ? escapeHtml(hits.join(", ")) : "No cliché phrases detected."}</p></div>
    <div class="metric-diagnostics"><strong>Flagged sentences · ${flagged.length}</strong><p>${flagged.length ? flagged.map(escapeHtml).join("<br />") : "No sentences flagged."}</p></div>
    ${report.contextual_note ? `<div class="metric-diagnostics"><strong>Contextual note</strong><p>${escapeHtml(report.contextual_note)}</p></div>` : ""}
  </section>`;
}

function renderMetrics(run) {
  document.getElementById("metricsCards").innerHTML =
    metricColumn("Before revision", run.before_metrics, run.before_score) +
    metricColumn("After revision", run.after_metrics, run.after_score);
}

async function loadHistory() {
  const rows = await VeriToneAPI.fetchHistory();
  state.history = rows;
  document.getElementById("navCount").textContent = rows.length;
  const body = document.getElementById("historyTableBody");
  body.innerHTML = rows.length ? rows.map((row) => `<tr>
    <td>#${row.id}</td><td>${escapeHtml(row.created_at)}</td>
    <td>${escapeHtml(row.source_name)} <span class="muted">· ${escapeHtml(row.source_type)}</span></td>
    <td>${number(row.word_count)}</td><td>${score(row.before_score)} → ${score(row.after_score)}</td>
    <td>${row.total_changes} · ${score(row.change_percentage)}%</td>
    <td><div class="table-actions"><button class="button button-outline table-action" data-open-run="${row.id}">Open</button><button class="button button-outline table-action danger-action" data-delete-run="${row.id}">Delete</button><a class="button button-outline table-action" href="/api/analyses/${row.id}/download/humanized">TXT</a><a class="button button-outline table-action" href="/api/analyses/${row.id}/download/report">JSON</a></div></td>
  </tr>`).join("") : '<tr><td colspan="7" class="empty-cell">No saved runs yet. Your analyses will appear here.</td></tr>';
  return rows;
}

async function loadAdmin() {
  const [overview, users, runs] = await Promise.all([
    VeriToneAPI.adminOverview(), VeriToneAPI.adminUsers(), VeriToneAPI.adminAnalyses(),
  ]);
  document.getElementById("adminKpis").innerHTML = [
    ["Total users", number(overview.total_users)], ["Platform runs", number(overview.total_runs)],
    ["Words processed", number(overview.total_words)], ["Average score shift", `${overview.average_score_shift >= 0 ? "+" : ""}${score(overview.average_score_shift)}`],
  ].map(([label, value]) => `<div class="admin-kpi"><span>${label}</span><strong>${value}</strong></div>`).join("");
  document.getElementById("usersTableBody").innerHTML = users.map((user) => `<tr>
    <td>${escapeHtml(user.username)}${user.id === state.user.id ? " · you" : ""}</td>
    <td>${escapeHtml(user.created_at)}</td><td>${number(user.run_count)}</td><td>${number(user.word_count)}</td>
    <td><select aria-label="Role for ${escapeHtml(user.username)}" data-user-role="${user.id}" ${user.id === state.user.id ? "disabled" : ""}><option value="user" ${user.role === "user" ? "selected" : ""}>user</option><option value="admin" ${user.role === "admin" ? "selected" : ""}>admin</option></select></td>
    <td><select aria-label="Status for ${escapeHtml(user.username)}" data-user-active="${user.id}" ${user.id === state.user.id ? "disabled" : ""}><option value="true" ${user.is_active ? "selected" : ""}>Active</option><option value="false" ${!user.is_active ? "selected" : ""}>Disabled</option></select></td>
  </tr>`).join("") || '<tr><td colspan="6" class="empty-cell">No accounts found.</td></tr>';
  document.getElementById("auditTableBody").innerHTML = runs.map((run) => `<tr>
    <td>#${run.id}</td><td>${escapeHtml(run.created_at)}</td><td>${escapeHtml(run.username || "Unknown")}</td>
    <td>${escapeHtml(run.source_name)}</td><td>${number(run.word_count)}</td>
    <td>${score(run.before_score)} → ${score(run.after_score)}</td>
    <td><button class="button button-outline table-action" data-open-admin-run="${run.id}">Open</button></td>
  </tr>`).join("") || '<tr><td colspan="7" class="empty-cell">No platform runs yet.</td></tr>';
}

async function openRun(id, isAdmin = false) {
  const run = isAdmin ? await VeriToneAPI.adminAnalysis(id) : await VeriToneAPI.fetchAnalysisById(id);
  renderRun(run);
  switchTab("studio");
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      showAuthMode(button.dataset.authMode);
      if (button.classList.contains("button")) document.getElementById("authCard").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  document.getElementById("authForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const credentials = { username: form.get("username"), password: form.get("password") };
    const submit = document.getElementById("authSubmit");
    submit.disabled = true;
    document.getElementById("authStatus").textContent = "";
    try {
      const result = state.authMode === "login"
        ? await VeriToneAPI.login(credentials) : await VeriToneAPI.register(credentials);
      showWorkspace(result.user);
    } catch (error) {
      document.getElementById("authStatus").textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });

  document.getElementById("logoutBtn").addEventListener("click", async () => {
    await VeriToneAPI.logout();
    window.location.reload();
  });

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      switchTab(button.dataset.tab);
    });
  });

  const fileInput = document.getElementById("fileInput");
  const dropzone = document.getElementById("dropzone");
  const updateFileMeta = () => {
    const file = fileInput.files[0];
    document.getElementById("fileMeta").textContent = file ? `${file.name} · ${(file.size / (1024 * 1024)).toFixed(2)} MB` : "No file selected";
  };
  fileInput.addEventListener("change", updateFileMeta);
  ["dragenter", "dragover"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => {
    event.preventDefault(); dropzone.classList.add("drag-over");
  }));
  ["dragleave", "drop"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => {
    event.preventDefault(); dropzone.classList.remove("drag-over");
  }));
  dropzone.addEventListener("drop", (event) => {
    if (event.dataTransfer.files.length) {
      fileInput.files = event.dataTransfer.files;
      updateFileMeta();
    }
  });

  document.getElementById("analyzeForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = document.getElementById("runBtn");
    submit.disabled = true;
    setStatus("Reading the draft and preparing your report…");
    try {
      const result = await VeriToneAPI.runAnalysis(new FormData(event.currentTarget));
      renderRun(result);
      await loadHistory();
      setStatus(`Run #${result.id} complete · ${result.total_changes} edits recorded.`, "success");
      switchTab("studio");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });

  document.getElementById("refreshHistoryBtn").addEventListener("click", () => {
    loadHistory().catch((error) => setStatus(error.message, "error"));
  });

  document.addEventListener("click", async (event) => {
    const open = event.target.closest("[data-open-run]");
    const adminOpen = event.target.closest("[data-open-admin-run]");
    const remove = event.target.closest("[data-delete-run]");
    try {
      if (open) await openRun(open.dataset.openRun);
      if (adminOpen) await openRun(adminOpen.dataset.openAdminRun, true);
      if (remove && window.confirm("Delete this saved analysis? This cannot be undone.")) {
        await VeriToneAPI.deleteAnalysisById(remove.dataset.deleteRun);
        await loadHistory();
      }
    } catch (error) {
      setStatus(error.message, "error");
    }
  });

  document.addEventListener("change", async (event) => {
    const roleControl = event.target.closest("[data-user-role]");
    const activeControl = event.target.closest("[data-user-active]");
    if (!roleControl && !activeControl) return;
    const userId = (roleControl || activeControl).dataset.userRole || (roleControl || activeControl).dataset.userActive;
    try {
      const changes = roleControl ? { role: roleControl.value } : { is_active: activeControl.value === "true" };
      await VeriToneAPI.adminUpdateUser(userId, changes);
      await loadAdmin();
    } catch (error) {
      window.alert(error.message);
      await loadAdmin();
    }
  });

  try {
    const result = await VeriToneAPI.session();
    if (result.user) showWorkspace(result.user);
    else showAuthMode("login");
  } catch (error) {
    document.getElementById("authStatus").textContent = error.message;
  }
});