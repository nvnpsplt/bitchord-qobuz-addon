// BitChord Qobuz Addon Management Frontend

let currentAudio = null;

document.addEventListener("DOMContentLoaded", () => {
  loadStatus();

  // Settings form save
  document.getElementById("configForm").addEventListener("submit", handleSaveConfig);

  // Test login form
  document.getElementById("loginBtn").addEventListener("click", handleLogin);

  // Search form
  document.getElementById("searchBtn").addEventListener("click", handleTestSearch);
  document.getElementById("searchInput").addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleTestSearch();
  });
});

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    // Populate URLs
    const lanUrl = data.network.lan_manifest_url || `${data.network.current_url}/manifest.json`;
    document.getElementById("manifestUrl").textContent = lanUrl;
    document.getElementById("lanRootUrl").textContent = data.network.lan_root_url || data.network.current_url;

    // Populate Fields
    if (data.preferred_format) {
      document.getElementById("formatSelect").value = data.preferred_format;
    }
    if (data.direct_redirect !== undefined) {
      document.getElementById("directRedirectCheck").checked = data.direct_redirect;
    }
    if (data.app_id) {
      document.getElementById("appIdInput").value = data.app_id;
    }

    // Auth Status Badge
    const authBadge = document.getElementById("authStatusBadge");
    if (data.auth && data.auth.authenticated) {
      const user = data.auth.display_name || "User";
      const sub = data.auth.subscription || "Active";
      authBadge.className = "badge-hires";
      authBadge.textContent = `✓ Logged in: ${user} (${sub})`;
    } else if (data.user_token_configured) {
      authBadge.className = "badge-lossless";
      authBadge.textContent = `Token configured (${data.masked_token})`;
    } else {
      authBadge.className = "track-badge";
      authBadge.style.background = "rgba(255, 146, 43, 0.2)";
      authBadge.style.color = "#ff922b";
      authBadge.textContent = "Guest / Previews (Login below for full tracks)";
    }
  } catch (err) {
    console.error("Failed to load status:", err);
  }
}

async function handleSaveConfig(e) {
  e.preventDefault();
  const btn = document.getElementById("saveConfigBtn");
  btn.disabled = true;
  btn.textContent = "Saving...";

  const payload = {
    preferred_format: parseInt(document.getElementById("formatSelect").value, 10),
    user_auth_token: document.getElementById("userTokenInput").value.trim(),
    app_id: document.getElementById("appIdInput").value.trim(),
    app_secret: document.getElementById("appSecretInput").value.trim(),
    direct_redirect: document.getElementById("directRedirectCheck").checked,
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (res.ok) {
      showToast("✓ Settings updated successfully!");
      loadStatus();
    } else {
      showToast(`Error: ${result.error || "Failed to update"}`);
    }
  } catch (err) {
    showToast("Network error saving configuration");
  } finally {
    btn.disabled = false;
    btn.textContent = "Save Configuration";
  }
}

async function handleLogin() {
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  if (!email || !password) {
    showToast("Please enter email and password");
    return;
  }

  const btn = document.getElementById("loginBtn");
  btn.disabled = true;
  btn.textContent = "Authenticating...";

  try {
    const res = await fetch("/api/test-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const result = await res.json();
    if (res.ok && result.user_auth_token) {
      showToast("✓ Qobuz Login Successful!");
      document.getElementById("userTokenInput").value = result.user_auth_token;
      document.getElementById("loginEmail").value = "";
      document.getElementById("loginPassword").value = "";
      loadStatus();
    } else {
      showToast(`Login failed: ${result.error || "Invalid credentials"}`);
    }
  } catch (err) {
    showToast("Login request failed");
  } finally {
    btn.disabled = false;
    btn.textContent = "Login & Fetch Token";
  }
}

async function handleTestSearch() {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) return;

  const btn = document.getElementById("searchBtn");
  btn.disabled = true;
  btn.textContent = "Searching...";

  const trackList = document.getElementById("trackList");
  trackList.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-muted);">Searching Qobuz High-Res catalog for "${query}"...</div>`;

  try {
    const res = await fetch(`/api/test-search?q=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (!data.tracks || data.tracks.length === 0) {
      trackList.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-muted);">No tracks found for "${query}"</div>`;
      return;
    }

    trackList.innerHTML = "";
    data.tracks.forEach((track) => {
      const isHiRes = track.audioQuality === "HI_RES";
      const badgeClass = isHiRes ? "track-badge hires" : "track-badge lossless";
      const sampleRateDisplay = track.sampleRate >= 1000 ? `${track.sampleRate / 1000} kHz` : `${track.sampleRate} Hz`;
      const formatDisplay = `${track.bitDepth}-bit / ${sampleRateDisplay} FLAC`;
      const mins = Math.floor(track.duration / 60);
      const secs = String(track.duration % 60).padStart(2, "0");

      const card = document.createElement("div");
      card.className = "track-card";
      card.innerHTML = `
        <img class="track-artwork" src="${track.artworkURL || '/static/icon.svg'}" alt="Cover" />
        <div class="track-info">
          <div class="track-title">${escapeHtml(track.title)}</div>
          <div class="track-artist">${escapeHtml(track.artist)} • ${escapeHtml(track.album || "")}</div>
          <div class="track-meta">
            <span class="${badgeClass}">${track.audioQuality}</span>
            <span class="track-duration">${formatDisplay} • ${mins}:${secs}</span>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="playTrack('${track.id}', '${escapeJs(track.title)}', '${escapeJs(track.artist)}')">
          ▶ Play Stream
        </button>
      `;
      trackList.appendChild(card);
    });
  } catch (err) {
    trackList.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger);">Search error: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Search";
  }
}

function playTrack(trackId, title, artist) {
  const player = document.getElementById("audioPlayer");
  const container = document.getElementById("playerContainer");
  const playingInfo = document.getElementById("nowPlayingInfo");

  const streamUrl = `/audio/${trackId}.flac`;
  player.src = streamUrl;
  playingInfo.textContent = `Now Playing: ${title} - ${artist} (Original FLAC)`;
  container.classList.add("active");
  player.play().catch((e) => console.log("Audio play prevented:", e));
}

function copyToClipboard(elementId) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast("✓ Copied to clipboard!");
  }).catch(() => {
    showToast("Failed to copy");
  });
}

function showToast(message) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 3000);
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeJs(str) {
  if (!str) return "";
  return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}
