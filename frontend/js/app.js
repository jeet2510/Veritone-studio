const state = {
  currentRun: null,
  history: [],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let val = bytes;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx += 1;
  }
  return `${val.toFixed(1)} ${units[idx]}`;
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

function renderRun(run) {
  state.currentRun = run;

  document.getElementById("activeTitle").textContent =
    `Run #${run.id} — ${run.source_name} (${run.created_at})`;
  document.getElementById("kpiScore").textContent =
    `${run.before_score} → ${run.after_score}`;
  document.getElementById("kpiChanges").textContent = run.total_changes;
  document.getElementById("kpiPct").textContent = `${run.change_percentage}%`;
  document.getElementById("kpiWords").textContent = run.word_count;

  document.getElementById("sourcePreview").textContent = run.original_text;
  document.getElementById("humanizedPreview").textContent = run.humanized_text;

  document.getElementById("exportBar").innerHTML = `
    <a href="/api/analyses/${run.id}/download/humanized">Download Humanized (.txt)</a>
    <a href="/api/analyses/${run.id}/download/report">Download Full Report (.json)</a>
  `;

  document.getElementById("changeSummaryLine").textContent =
    `${run.total_changes} edits (${run.change_percentage}% est. word impact) across ${run.changed_sentences} of ${run.total_sentences} sentences.`;

  const tbody = document.getElementById("changesTableBody");
  if (!run.changes || run.changes.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted-sm">No rule-based changes triggered.</td></tr>`;
  } else {
    tbody.innerHTML = run.changes
      .map(
        (c, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${c.sentence_index}</td>
          <td>${escapeHtml(c.change_type)}</td>
          <td>${escapeHtml(c.before)}</td>
          <td>${escapeHtml(c.after)}</td>
        </tr>
      `
      )
      .join("");
  }

  renderMetrics(run);
}

function renderMetrics(run) {
  const before = run.before_metrics || {
    ai_score: run.before_score,
    classification: run.before_label,
    avg_sentence_len: "—",
    sentence_len_stdev: "—",
    cliche_hits: run.cliche_hits || [],
  };
  const after = run.after_metrics || {
    ai_score: run.after_score,
    classification: run.after_label,
    avg_sentence_len: "—",
    sentence_len_stdev: "—",
    cliche_hits: [],
  };

  document.getElementById("metricsCards").innerHTML = `
    <div class="metric-box">
      <h3>Before Humanization</h3>
      <p><strong>AI Score:</strong> ${before.ai_score} / 100</p>
      <p><strong>Classification:</strong> ${escapeHtml(before.classification)}</p>
      <p><strong>Avg Sentence Length:</strong> ${before.avg_sentence_len} words (stdev: ${before.sentence_len_stdev})</p>
      <p><strong>Cliché Hits:</strong> ${before.cliche_hits?.length ? escapeHtml(before.cliche_hits.join(", ")) : "None"}</p>
    </div>
    <div class="metric-box">
      <h3>After Humanization</h3>
      <p><strong>AI Score:</strong> ${after.ai_score} / 100</p>
      <p><strong>Classification:</strong> ${escapeHtml(after.classification)}</p>
      <p><strong>Avg Sentence Length:</strong> ${after.avg_sentence_len} words (stdev: ${after.sentence_len_stdev})</p>
      <p><strong>Cliché Hits:</strong> ${after.cliche_hits?.length ? escapeHtml(after.cliche_hits.join(", ")) : "None"}</p>
    </div>
  `;
}

function renderHistory(rows) {
  state.history = rows;
  document.getElementById("navCount").textContent = rows.length;
  const tbody = document.getElementById("historyTableBody");

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="muted-sm">No runs stored in SQLite yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map(
      (r) => `
      <tr>
        <td>${r.id}</td>
        <td>${escapeHtml(r.created_at)}</td>
        <td>${escapeHtml(r.source_name)} (${escapeHtml(r.source_type)})</td>
        <td>${r.word_count}</td>
        <td>${r.before_score} → ${r.after_score}</td>
        <td>${r.total_changes} (${r.change_percentage}%)</td>
        <td>
          <button class="secondary-btn" onclick="openSavedRun(${r.id})">Open</button>
          <button class="danger-btn" onclick="deleteSavedRun(${r.id})">Delete</button>
        </td>
      </tr>
    `
    )
    .join("");
}

async function openSavedRun(id) {
  const run = await VeriToneAPI.fetchAnalysisById(id);
  renderRun(run);
  switchTab("studio");
}

async function deleteSavedRun(id) {
  await VeriToneAPI.deleteAnalysisById(id);
  const rows = await VeriToneAPI.fetchHistory();
  renderHistory(rows);
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  const fileInput = document.getElementById("fileInput");
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    document.getElementById("fileMeta").textContent = f
      ? `${f.name} (${formatBytes(f.size)})`
      : "No file selected";
  });

  document.getElementById("analyzeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("runBtn");
    const status = document.getElementById("statusBox");
    btn.disabled = true;
    status.textContent = "Streaming upload, analyzing patterns, humanizing, and writing to SQLite...";

    try {
      const formData = new FormData(e.target);
      const run = await VeriToneAPI.runAnalysis(formData);
      renderRun(run);
      const rows = await VeriToneAPI.fetchHistory();
      renderHistory(rows);
      status.textContent = `Completed Run #${run.id} (${run.total_changes} edits, ${run.change_percentage}%).`;
    } catch (err) {
      status.textContent = err.message;
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("refreshHistoryBtn").addEventListener("click", async () => {
    const rows = await VeriToneAPI.fetchHistory();
    renderHistory(rows);
  });

  try {
    const rows = await VeriToneAPI.fetchHistory();
    renderHistory(rows);
    if (rows.length > 0) {
      const latest = await VeriToneAPI.fetchAnalysisById(rows[0].id);
      renderRun(latest);
    }
  } catch (err) {
    document.getElementById("statusBox").textContent = err.message;
  }
});