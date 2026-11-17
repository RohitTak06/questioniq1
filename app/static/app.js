// The Explain drawer. Plain JavaScript, no build step.
// A button with data-explain="<question id>" fetches /api/explain/<id>;
// a button with data-upload="<index>" uses window.UPLOAD_RESULTS[index] instead.

const drawer = document.getElementById("drawer");
const drawerBody = document.getElementById("drawer-body");

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function renderExplanation(item) {
  const parts = [];
  const where = [item.course, item.year, item.exam_type].filter(Boolean).join(" · ");
  const label = item.qno ? `Q${escapeHtml(item.qno)}${item.sub_part ? " (" + escapeHtml(item.sub_part) + ")" : ""}` : "";
  parts.push(`<h3>${label} ${where ? "<span class='muted'>" + escapeHtml(where) + "</span>" : ""}</h3>`);
  parts.push(`<p class="qtext">${escapeHtml(item.text)}</p>`);
  if (!item.predicted) {
    parts.push("<p class='muted'>No prediction for this question.</p>");
    return parts.join("");
  }
  if (item.outside_training_subjects) {
    parts.push("<p class='badge outside'>Outside training subjects: the model learned from CS and AS questions only</p>");
  }
  parts.push(`<p><span class="badge ${item.predicted}">${item.predicted}</span> ${escapeHtml(item.because)}</p>`);
  const p = item.probabilities;
  parts.push(`<div class="probs">${["Easy", "Medium", "Hard"].map(
    (g) => `<span class="${g}" style="width:${(p[g] * 100).toFixed(1)}%" title="${g} ${(p[g] * 100).toFixed(0)}%"></span>`
  ).join("")}</div>`);
  parts.push(`<p class="muted">Easy ${(p.Easy * 100).toFixed(0)}% · Medium ${(p.Medium * 100).toFixed(0)}% · Hard ${(p.Hard * 100).toFixed(0)}%</p>`);
  if (item.owner_label) {
    parts.push(`<p>Your label: <span class="badge ${item.owner_label}">${item.owner_label}</span></p>`);
  }
  const biggest = Math.max(...item.reasons.map((r) => Math.abs(r.shap)), 1e-9);
  parts.push(`<h4>Strongest reasons (SHAP, for ${item.predicted})</h4>`);
  for (const r of item.reasons) {
    const width = (Math.abs(r.shap) / biggest) * 50;
    const side = r.shap > 0 ? "up" : "down";
    parts.push(`<div class="reason"><span>${escapeHtml(r.text)} <span class="muted">${r.shap > 0 ? "towards" : "away"} ${r.shap > 0 ? "+" : ""}${r.shap.toFixed(3)}</span></span>
      <span class="bar"><span class="${side}" style="width:${width}%"></span></span></div>`);
  }
  const topics = (item.topics && item.topics.topics) || [];
  if (topics.length) {
    parts.push("<h4>Topics</h4>");
    for (const t of topics) {
      const words = t.keywords_found.map((w) => `<span class="keyword">${escapeHtml(w.replace("_", " "))}</span>`).join("");
      parts.push(`<p>${escapeHtml(t.name)} <span class="muted">${(t.share * 100).toFixed(0)}%</span><br>${words || "<span class='muted'>no keywords found in the text</span>"}</p>`);
    }
  }
  return parts.join("");
}

function openDrawer(item) {
  drawerBody.innerHTML = renderExplanation(item);
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-explain], [data-upload]");
  if (button) {
    if (button.dataset.upload !== undefined) {
      openDrawer(window.UPLOAD_RESULTS[Number(button.dataset.upload)]);
    } else {
      drawerBody.innerHTML = "<p class='muted'>Loading…</p>";
      drawer.classList.add("open");
      const response = await fetch(`/api/explain/${encodeURIComponent(button.dataset.explain)}`);
      if (response.ok) openDrawer(await response.json());
      else drawerBody.innerHTML = "<p>Could not load this explanation.</p>";
    }
    return;
  }
  if (event.target.closest(".drawer-close")) closeDrawer();
});
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeDrawer(); });
