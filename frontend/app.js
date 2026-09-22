const apiBase = (window.QR_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const $ = (selector) => document.querySelector(selector);
const state = { token: localStorage.getItem("quickqr_token"), email: localStorage.getItem("quickqr_email"), previewUrl: null };

function showToast(message, error = false) {
  const toast = $("#toast"); toast.textContent = message; toast.classList.toggle("error", error); toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer); showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 4200);
}
function authHeaders() { return state.token ? { Authorization: `Bearer ${state.token}` } : {}; }
async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, { ...options, headers: { ...authHeaders(), ...(options.headers || {}) } });
  if (response.status === 401) signOut(false);
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response;
}
function setAuthenticated(authenticated) {
  $("#auth-panel").classList.toggle("hidden", authenticated); $("#studio").classList.toggle("hidden", !authenticated); $("#history").classList.toggle("hidden", !authenticated); $("#logout-button").classList.toggle("hidden", !authenticated);
  if (authenticated) $("#user-email").textContent = state.email;
}
async function getToken(email, password) {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${apiBase}/auth/token`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body });
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || "Sign in failed"); }
  return response.json();
}
async function signIn(event) {
  event.preventDefault(); const email = $("#email").value.trim(); const password = $("#password").value;
  try { const data = await getToken(email, password); state.token = data.access_token; state.email = email; localStorage.setItem("quickqr_token", state.token); localStorage.setItem("quickqr_email", email); setAuthenticated(true); await loadHistory(); showToast("Welcome back."); } catch (error) { showToast(error.message, true); }
}
async function register() {
  const email = $("#email").value.trim(); const password = $("#password").value;
  if (!email || password.length < 10) return showToast("Enter an email and a password with at least 10 characters.", true);
  try { await request("/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) }); const data = await getToken(email, password); state.token = data.access_token; state.email = email; localStorage.setItem("quickqr_token", state.token); localStorage.setItem("quickqr_email", email); setAuthenticated(true); await loadHistory(); showToast("Account created. You’re ready to make QR codes."); } catch (error) { showToast(error.message, true); }
}
function signOut(showMessage = true) { localStorage.removeItem("quickqr_token"); localStorage.removeItem("quickqr_email"); state.token = null; state.email = null; setAuthenticated(false); if (showMessage) showToast("Signed out."); }
async function imageUrl(path) { const response = await request(path); const blob = await response.blob(); return URL.createObjectURL(blob); }
async function generate(event) {
  event.preventDefault(); const payload = { url: $("#url").value.trim(), foreground: $("#foreground").value, background: $("#background").value, size: Number($("#size").value), border: Number($("#border").value), error_correction: $("#correction").value };
  try { const response = await request("/qrcodes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); const item = await response.json(); if (state.previewUrl) URL.revokeObjectURL(state.previewUrl); state.previewUrl = await imageUrl(`/qrcodes/${item.id}/download`); $("#preview-image").src = state.previewUrl; $("#preview-image").classList.remove("hidden"); $("#preview-placeholder").classList.add("hidden"); $("#preview-caption").textContent = "Your code is ready — download it from your library."; await loadHistory(); showToast("QR code generated."); } catch (error) { showToast(error.message, true); }
}
async function download(id) { try { const url = await imageUrl(`/qrcodes/${id}/download`); const link = document.createElement("a"); link.href = url; link.download = `quickqr-${id}.png`; link.click(); URL.revokeObjectURL(url); } catch (error) { showToast(error.message, true); } }
async function deleteCode(id) { if (!window.confirm("Delete this QR code from your history?")) return; try { await request(`/qrcodes/${id}`, { method: "DELETE" }); await loadHistory(); showToast("QR code deleted."); } catch (error) { showToast(error.message, true); } }
async function loadHistory() {
  if (!state.token) return; try { const response = await request("/qrcodes?limit=24"); const data = await response.json(); const grid = $("#history-grid"); grid.innerHTML = ""; $("#empty-history").classList.toggle("hidden", data.items.length > 0); for (const item of data.items) { const card = document.createElement("article"); card.className = "history-card card"; const image = document.createElement("img"); image.alt = `QR code for ${item.url}`; imageUrl(`/qrcodes/${item.id}/download`).then((url) => { image.src = url; }); const details = document.createElement("div"); const title = document.createElement("h3"); title.title = item.url; title.textContent = new URL(item.url).hostname; const time = document.createElement("time"); time.textContent = new Date(item.created_at + "Z").toLocaleDateString(); const actions = document.createElement("div"); actions.className = "card-actions"; const downloadButton = document.createElement("button"); downloadButton.className = "link-button"; downloadButton.type = "button"; downloadButton.textContent = "Download"; downloadButton.onclick = () => download(item.id); const deleteButton = document.createElement("button"); deleteButton.className = "link-button delete"; deleteButton.type = "button"; deleteButton.textContent = "Delete"; deleteButton.onclick = () => deleteCode(item.id); actions.append(downloadButton, deleteButton); details.append(title, time, actions); card.append(image, details); grid.append(card); } } catch (error) { showToast(error.message, true); }
}
async function healthCheck() { try { await request("/health"); $("#api-label").textContent = "API connected"; $(".connection").classList.add("online"); } catch { $("#api-label").textContent = "API unavailable"; } }
function bindColor(input, output) { input.addEventListener("input", () => output.textContent = input.value.toUpperCase()); }
$("#auth-form").addEventListener("submit", signIn); $("#register-button").addEventListener("click", register); $("#logout-button").addEventListener("click", () => signOut()); $("#qr-form").addEventListener("submit", generate); $("#refresh-button").addEventListener("click", loadHistory); $("#border").addEventListener("input", (event) => $("#border-value").textContent = `${event.target.value} modules`); bindColor($("#foreground"), $("#foreground-text")); bindColor($("#background"), $("#background-text")); healthCheck(); if (state.token && state.email) { setAuthenticated(true); loadHistory(); }
