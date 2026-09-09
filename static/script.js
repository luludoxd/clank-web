const apiKey = document.getElementById("apiKey");
const videoUrl = document.getElementById("videoUrl");
const analyzeBtn = document.getElementById("analyzeBtn");
const status = document.getElementById("status");
const summary = document.getElementById("summary");
const resultsPanel = document.getElementById("resultsPanel");
const resultsEl = document.getElementById("results");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
  }[c]));
}

function renderResults(data) {
  document.getElementById("comments").textContent = data.comments.toLocaleString();
  document.getElementById("accounts").textContent = data.accounts.toLocaleString();
  document.getElementById("hits").textContent = data.hits.toLocaleString();

  summary.classList.remove("hidden");
  resultsPanel.classList.remove("hidden");

  if (!data.results.length) {
    resultsEl.innerHTML = "<p class='muted'>No accounts passed the current score threshold.</p>";
    return;
  }

  resultsEl.innerHTML = data.results.map(r => `
    <article class="result">
      <div class="result-top">
        <div>
          <div class="name">${escapeHtml(r.name)}</div>
          <a href="${escapeHtml(r.channel_url)}" target="_blank" rel="noopener">Open YouTube channel</a>
        </div>
        <div class="score">${r.score} / ${r.max_score}</div>
      </div>
      <div class="comment">${escapeHtml(r.comment)}</div>
      <div><strong>Account age:</strong> ${escapeHtml(r.age)}</div>
      <div><strong>Classification:</strong> ${escapeHtml(r.classification)}</div>
      <div class="flags">${(r.flags || []).map(f => `<span>${escapeHtml(f)}</span>`).join("")}</div>
      <ul>${(r.reasons || []).map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
    </article>
  `).join("");
}

analyzeBtn.addEventListener("click", async () => {
  const key = apiKey.value.trim();
  const url = videoUrl.value.trim();

  if (!key || !url) {
    status.textContent = "Please enter both your API key and a YouTube URL.";
    return;
  }

  analyzeBtn.disabled = true;
  status.textContent = "Analyzing... This may take a while because the program checks all available top-level comments.";
  summary.classList.add("hidden");
  resultsPanel.classList.add("hidden");

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({api_key: key, url})
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Analysis failed.");

    renderResults(data);
    status.textContent = "Analysis complete.";
  } catch (err) {
    status.textContent = "Error: " + err.message;
  } finally {
    analyzeBtn.disabled = false;
  }
});

document.getElementById("clearBtn").addEventListener("click", () => {
  resultsEl.innerHTML = "";
  summary.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  status.textContent = "";
});
