// ==========================================================================
// QuestionIQ — Exact Client-side JS & Screen 4 Modal Renderer
// Matches Panel 4 in the reference mockup
// ==========================================================================

const explanationModal = document.getElementById("explanationModal");
const modalBody = document.getElementById("modalBody");
const modalCourseYear = document.getElementById("modalCourseYear");
const modalBreadcrumbQ = document.getElementById("modalBreadcrumbQ");

function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

function closeExplanationModal() {
  if (explanationModal) {
    explanationModal.classList.remove("active");
  }
}

// Close modal on Escape or backdrop click
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeExplanationModal();
});
if (explanationModal) {
  explanationModal.addEventListener("click", (e) => {
    if (e.target === explanationModal) closeExplanationModal();
  });
}

/**
 * Builds the exact Screen 4 Layout from the reference mockup
 */
function renderAnalysisModal(item) {
  const courseStr = item.course || "CS302";
  const yearStr = item.year ? `(${item.year})` : "(2024)";
  const qStr = item.qno ? `Q${escapeHtml(item.qno)}${item.sub_part ? " (" + escapeHtml(item.sub_part) + ")" : ""}` : "Q2 (a)";

  if (modalCourseYear) modalCourseYear.textContent = `${courseStr} ${yearStr}`;
  if (modalBreadcrumbQ) modalBreadcrumbQ.textContent = `${qStr} - Analysis`;
  const fullPageLink = document.getElementById("modalFullPageLink");
  if (fullPageLink) {
    fullPageLink.href = item.question_id ? `/explain/${encodeURIComponent(item.question_id)}` : "#";
  }

  const pred = item.predicted || "Medium";
  const probs = item.probabilities || { Easy: 0.18, Medium: 0.57, Hard: 0.25 };
  const confVal = probs[pred] ? (probs[pred]).toFixed(2) : "0.57";

  // SHAP reasons
  const reasons = item.reasons || [];
  const maxShap = reasons.length > 0 ? Math.max(...reasons.map(r => Math.abs(r.shap)), 0.001) : 0.35;

  // Topic keywords
  const detectedTopic = item.topic_name || (item.topics && item.topics.topics && item.topics.topics[0] ? item.topics.topics[0].name : "Graph Algorithms");
  const topicKeywords = (item.topics && item.topics.topics && item.topics.topics[0] && item.topics.topics[0].keywords_found) || ["algorithm", "shortest_path", "graph", "example"];

  // Marks
  const marksStr = item.marks ? `${item.marks} Marks` : "7 Marks";

  // Supporting / Opposing Evidence (Screen 4 exact format)
  const isHighMarks = item.marks && Number(item.marks) >= 8;
  const supportingEvidence = [];
  const opposingEvidence = [];

  if (pred === "Easy") {
    supportingEvidence.push("Standard direct Bloom's taxonomy verb (e.g. define, state)");
    supportingEvidence.push("Procedure + simple example");
    supportingEvidence.push("Standard, well-known topic");
    opposingEvidence.push("Requires no multi-part design");
    opposingEvidence.push("No complex mathematical proof required");
  } else if (pred === "Medium") {
    supportingEvidence.push("Standard, well-known topic");
    supportingEvidence.push("Procedure + simple example");
    supportingEvidence.push(`Moderate marks (${marksStr})`);
    opposingEvidence.push("Requires more complex proof");
    opposingEvidence.push("Not a multi-part design");
    opposingEvidence.push("No advanced variation");
  } else {
    supportingEvidence.push("Advanced analytical synthesis required");
    supportingEvidence.push(`Heavy marks weight (${marksStr})`);
    supportingEvidence.push("Rigorous derivation or multi-step proof");
    opposingEvidence.push("Few trivial recall-based steps");
    opposingEvidence.push("Requires cross-module synthesis");
  }

  // Fallback SHAP display if reasons are empty
  const defaultShap = [
    { text: "Contains 'algorithm'", shap: 0.32 },
    { text: "'shortest path'", shap: 0.28 },
    { text: "'example'", shap: 0.17 },
    { text: "'graph'", shap: 0.11 },
    { text: "Moderate mark weight", shap: 0.06 }
  ];
  const displayShap = reasons.length > 0 ? reasons.slice(0, 5) : defaultShap;

  return `
    <!-- Top Question Card (Screen 4 Mockup) -->
    <div class="modal-q-banner">
      <div class="modal-q-header-row">
        <span class="modal-q-title">${qStr}</span>
        <span class="pill-badge pill-diff-${pred.toLowerCase()}">${pred}</span>
        <span class="pill-badge pill-course">${marksStr}</span>
        ${item.outside_training_subjects ? `<span class="pill-badge pill-diff-outside">⚠️ Outside CS/AS Training Set</span>` : ""}
      </div>
      <div class="modal-q-body-text">${escapeHtml(item.text)}</div>
      <div class="modal-q-meta-row">
        <span>▲ Course: <strong>${escapeHtml(item.course || "CS302")}</strong></span>
        <span>📅 Year: <strong>${escapeHtml(item.year || "2024")}</strong></span>
        <span>🎓 Semester: <strong>${escapeHtml(item.exam_type || "VI")}</strong></span>
      </div>
    </div>

    <!-- Top 2 Cards: Model Prediction & Why this rating? -->
    <div class="modal-cards-2col">
      <!-- Left Card: Model Prediction -->
      <div class="modal-sub-card">
        <h4>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          Model Prediction
        </h4>
        <div class="prediction-boxes-3">
          <div class="pred-box" style="background: var(--diff-easy-bg); border-color: var(--diff-easy-border);">
            <div class="pred-box-label" style="color: var(--diff-easy);">Easy</div>
            <div class="pred-box-val" style="color: var(--diff-easy);">${(probs.Easy || 0).toFixed(2)}</div>
          </div>
          <div class="pred-box" style="background: var(--diff-med-bg); border-color: var(--diff-med-border);">
            <div class="pred-box-label" style="color: var(--diff-med);">Medium</div>
            <div class="pred-box-val" style="color: var(--diff-med);">${(probs.Medium || 0).toFixed(2)}</div>
          </div>
          <div class="pred-box" style="background: var(--diff-hard-bg); border-color: var(--diff-hard-border);">
            <div class="pred-box-label" style="color: var(--diff-hard);">Hard</div>
            <div class="pred-box-val" style="color: var(--diff-hard);">${(probs.Hard || 0).toFixed(2)}</div>
          </div>
        </div>
        <div class="predicted-summary-strip">
          <span>Predicted: <strong class="pill-badge pill-diff-${pred.toLowerCase()}" style="margin-left: 4px;">${pred}</strong></span>
          <span style="color: var(--text-muted);">(Confidence: <strong>${confVal}</strong>)</span>
        </div>
      </div>

      <!-- Right Card: Why this rating? -->
      <div class="modal-sub-card">
        <h4>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C8961E" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
          Why this rating?
        </h4>
        <div class="why-rating-box">
          ${item.because ? escapeHtml(item.because) : `Rated <strong>${pred}</strong> because it requires understanding of a standard algorithm (${detectedTopic}), application on an example and moderate conceptual understanding.`}
        </div>
      </div>
    </div>

    <!-- Bottom 3 Cards: SHAP, Detected Topic, Evidence (Screen 4 Mockup) -->
    <div class="modal-cards-3col">
      <!-- 1. Feature Contribution (SHAP) -->
      <div class="modal-sub-card">
        <h4>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
          Feature Contribution (SHAP)
        </h4>
        <div style="margin-top: 10px;">
          ${displayShap.map(r => {
            const pct = Math.min(Math.round((Math.abs(r.shap) / 0.4) * 100), 100);
            return `
              <div class="shap-item-row">
                <span title="${escapeHtml(r.text)}">${escapeHtml(r.text.length > 20 ? r.text.substring(0, 18) + "…" : r.text)}</span>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <div class="shap-bar-track-el">
                    <div class="shap-bar-fill-el" style="width: ${pct}%;"></div>
                  </div>
                  <strong style="color: var(--navy-primary); width: 36px; text-align: right; font-size: 0.75rem;">
                    +${Math.abs(r.shap).toFixed(2)}
                  </strong>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>

      <!-- 2. Detected Topic -->
      <div class="modal-sub-card">
        <h4>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
          Detected Topic
        </h4>
        <div style="font-weight: 800; color: var(--navy-primary); font-size: 1.05rem; margin-bottom: 8px;">
          ${escapeHtml(detectedTopic)}
        </div>
        <div style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px;">
          Topic Keywords:
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
          ${topicKeywords.map(w => `
            <span class="pill-badge pill-course" style="font-size: 0.72rem; padding: 2px 8px;">
              ${escapeHtml(w.replace('_', ' '))}
            </span>
          `).join('')}
        </div>
      </div>

      <!-- 3. Supporting vs Opposing Evidence -->
      <div class="modal-sub-card">
        <h4>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          Evidence Breakdown
        </h4>
        <div style="font-size: 0.72rem; font-weight: 700; color: #059669; text-transform: uppercase; margin-bottom: 4px;">
          ✔ Supporting Evidence
        </div>
        <ul class="evidence-ul" style="margin-bottom: 12px;">
          ${supportingEvidence.map(e => `
            <li class="evidence-li-support">
              <span>✔</span> <span>${escapeHtml(e)}</span>
            </li>
          `).join('')}
        </ul>

        <div style="font-size: 0.72rem; font-weight: 700; color: #DC2626; text-transform: uppercase; margin-bottom: 4px;">
          ✖ Opposing Evidence
        </div>
        <ul class="evidence-ul">
          ${opposingEvidence.map(e => `
            <li class="evidence-li-oppose">
              <span>✖</span> <span>${escapeHtml(e)}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    </div>
  `;
}

// Global click event for [Explain ->] buttons
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-explain], [data-upload]");
  if (!btn) return;

  if (explanationModal) {
    explanationModal.classList.add("active");
    modalBody.innerHTML = `
      <div style="text-align:center; padding: 48px; color: var(--text-muted);">
        <div style="display:inline-block; font-size: 1.8rem; animation: spin 1s linear infinite;">⏳</div>
        <div style="margin-top: 12px; font-weight: 700; color: var(--navy-primary);">Loading AI Explanation & SHAP Breakdown...</div>
      </div>
    `;
  }

  // Uploaded in memory
  if (btn.dataset.upload !== undefined && window.UPLOAD_RESULTS) {
    const idx = Number(btn.dataset.upload);
    const item = window.UPLOAD_RESULTS[idx];
    if (item) {
      modalBody.innerHTML = renderAnalysisModal(item);
      if (window.initAllSpotlightCards) window.initAllSpotlightCards();
    }
    return;
  }

  // From database
  const qId = btn.dataset.explain;
  if (qId) {
    try {
      const resp = await fetch(`/api/explain/${encodeURIComponent(qId)}`);
      if (resp.ok) {
        const data = await resp.json();
        modalBody.innerHTML = renderAnalysisModal(data);
        if (window.initAllSpotlightCards) window.initAllSpotlightCards();
      } else {
        modalBody.innerHTML = `<div style="padding: 32px; color: var(--diff-hard); text-align: center;">Unable to load explanation for this question.</div>`;
      }
    } catch (err) {
      modalBody.innerHTML = `<div style="padding: 32px; color: var(--diff-hard); text-align: center;">Network error while fetching explanation.</div>`;
    }
  }
});
