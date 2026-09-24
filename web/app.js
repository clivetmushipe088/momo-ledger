// MoMo Ledger dashboard. Talks to the FastAPI app in app/main.py.
"use strict";

// Keep these the same as app/models.py and the CHECKs in app/schema.sql
const TYPES = ["incoming_money", "payment", "transfer", "airtime"];
const STATUSES = ["completed", "pending", "failed", "reversed"];
const PAGE_SIZE = 10;

const $ = (id) => document.getElementById(id);
const state = { page: 1, editing: null, request: 0 };
const charts = {};

// ---------- small helpers ----------

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

const money = (amount) => `${Number(amount).toLocaleString("en-US")} RWF`;
const label = (text) => text.replaceAll("_", " ");

// Hide the middle of phone numbers on screen: 0781234567 -> 0781****67
const maskPhones = (text) => text.replace(/\b(07\d{2})\d{4}(\d{2})\b/g, "$1****$2");

function nowForInput() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); // datetime-local wants local time
  return d.toISOString().slice(0, 16);
}

let toastTimer;
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 3000);
}

// ---------- talking to the API ----------

// The login cookie is sent automatically, so no password or token is kept here.
async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body instanceof FormData) {
    options.body = body; // file upload
  } else if (body) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Can't reach the server. Check that uvicorn is still running.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(errorText(data, response.status));
    error.status = response.status;
    throw error;
  }
  return data;
}

// FastAPI sends {"detail": "text"}, or for bad input {"detail": [{"loc": [...], "msg": "..."}]}
function errorText(data, status) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join("; ");
  return `The server answered ${status}.`;
}

function showError(err) {
  if (err.status === 401) {
    showLogin("Your login has expired. Please log in again.");
    return;
  }
  $("banner").textContent = err.message;
  $("banner").hidden = false;
}

// ---------- logging in and out ----------

function showLogin(message = "") {
  $("login-view").hidden = false;
  $("app-view").hidden = true;
  $("session").hidden = true;
  $("login-error").textContent = message;
}

function showApp(username) {
  $("who").textContent = username;
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  $("session").hidden = false;
  // start clean, in case someone else used this browser before
  $("upload-result").textContent = "";
  $("f-type").value = "";
  $("f-status").value = "";
  state.page = 1;
  refresh();
}

async function onLogin(event) {
  event.preventDefault();
  const form = event.target;
  const account = { username: form.elements.username.value.trim(), password: form.elements.password.value };
  const creatingAccount = event.submitter?.value === "register";
  const buttons = form.querySelectorAll("button");
  buttons.forEach((b) => { b.disabled = true; });
  $("login-error").textContent = "";
  try {
    if (creatingAccount) await api("POST", "/auth/register", account);
    const { username } = await api("POST", "/auth/login", account);
    form.reset();
    showApp(username);
  } catch (err) {
    $("login-error").textContent = err.message;
  } finally {
    buttons.forEach((b) => { b.disabled = false; });
  }
}

async function logOut() {
  await api("POST", "/auth/logout").catch(() => {});
  showLogin();
}

// ---------- loading everything ----------

async function refresh() {
  $("banner").hidden = true;
  try {
    await Promise.all([loadTransactions(), loadReports(), loadUnmatched()]);
  } catch (err) {
    showError(err);
  }
}

async function loadTransactions() {
  // If the filters change twice quickly, the first answer can arrive last.
  // Numbering the requests lets us ignore any answer that isn't the newest.
  const requestNumber = ++state.request;
  const params = new URLSearchParams({ page: state.page, limit: PAGE_SIZE });
  if ($("f-type").value) params.set("type", $("f-type").value);
  if ($("f-status").value) params.set("status", $("f-status").value);
  const data = await api("GET", `/transactions?${params}`);
  if (requestNumber !== state.request) return;

  // e.g. the last row on the last page was deleted: go back one page
  if (data.page > data.pages) {
    state.page = data.pages;
    return loadTransactions();
  }

  $("rows").replaceChildren(...data.transactions.map(rowFor));
  const filtered = $("f-type").value || $("f-status").value;
  $("empty").textContent = filtered
    ? "No transactions match these filters."
    : "No transactions yet. Upload a backup or add one with + New.";
  $("empty").hidden = data.count > 0;
  $("page-label").textContent = `Page ${data.page} of ${data.pages} (${data.count} transactions)`;
  $("prev").disabled = data.page <= 1;
  $("next").disabled = data.page >= data.pages;
}

function rowFor(t) {
  const editButton = el("button", { className: "btn small", type: "button", textContent: "Edit", onclick: () => openEditor(t) });
  const deleteButton = el("button", { className: "btn small danger", type: "button", textContent: "Delete", onclick: () => removeTransaction(t) });
  return el("tr", { title: t.raw_sms ? maskPhones(t.raw_sms) : "Added by hand" },
    el("td", { textContent: t.date }),
    el("td", {}, el("span", { className: `badge ${t.transaction_type}`, textContent: label(t.transaction_type) })),
    el("td", { textContent: maskPhones(t.party) || "—" }),
    el("td", { className: "num", textContent: money(t.amount) }),
    el("td", {}, el("span", { className: `status ${t.status}`, textContent: t.status })),
    el("td", {}, editButton, " ", deleteButton));
}

async function loadUnmatched() {
  const messages = await api("GET", "/unmatched");
  $("unmatched").hidden = messages.length === 0;
  $("unmatched-count").textContent = messages.length;
  $("unmatched-list").replaceChildren(
    ...messages.map((m) => el("li", { textContent: `${m.date || "no date"}: ${maskPhones(m.body)}` })));
}

// ---------- charts ----------

async function loadReports() {
  if (typeof Chart === "undefined") {
    $("charts-note").textContent = "The charts need an internet connection to load Chart.js.";
    $("charts-note").hidden = false;
    return;
  }
  const [months, merchants] = await Promise.all([
    api("GET", "/reports/monthly-flow"),
    api("GET", "/reports/merchants"),
  ]);
  $("charts").hidden = months.length === 0; // nothing to draw until something is uploaded or added

  drawChart("flow-chart", {
    type: "bar",
    data: {
      labels: months.map((m) => m.month),
      datasets: [
        { label: "Money in", data: months.map((m) => m.money_in), backgroundColor: "#2e8b57" },
        { label: "Money out", data: months.map((m) => m.money_out), backgroundColor: "#d9534f" },
      ],
    },
  });
  drawChart("merchant-chart", {
    type: "bar",
    data: {
      labels: merchants.map((m) => m.merchant),
      datasets: [{ label: "Spent (RWF)", data: merchants.map((m) => m.total), backgroundColor: "#2f6fd6" }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } } },
  });
}

// Chart.js needs the old chart removed before drawing a new one on the same canvas
function drawChart(canvasId, config) {
  if (charts[canvasId]) charts[canvasId].destroy();
  config.options = { responsive: true, maintainAspectRatio: false, ...config.options };
  charts[canvasId] = new Chart($(canvasId), config);
}

// ---------- uploading a backup ----------

async function onUpload(event) {
  event.preventDefault();
  const data = new FormData();
  data.append("file", $("upload-file").files[0]);
  $("upload-btn").disabled = true;
  $("upload-result").textContent = "Uploading…";
  try {
    const r = await api("POST", "/upload", data);
    $("upload-result").textContent =
      `Imported: ${r.imported} · Already in your ledger: ${r.duplicates} · ` +
      `Not understood: ${r.unmatched} · Not MoMo messages: ${r.ignored}`;
    event.target.reset();
    state.page = 1;
    refresh();
  } catch (err) {
    $("upload-result").textContent = "";
    showError(err);
    $("upload-btn").disabled = false;
  }
}

// ---------- add, edit, delete ----------

function openEditor(t = null) {
  const form = $("editor-form");
  form.reset();
  state.editing = t;
  $("editor-title").textContent = t ? "Edit transaction" : "New transaction";
  if (t) {
    form.elements.transaction_type.value = t.transaction_type;
    form.elements.amount.value = t.amount;
    form.elements.party.value = t.party;
    form.elements.date.value = t.date.slice(0, 16).replace(" ", "T");
    form.elements.status.value = t.status;
  } else {
    form.elements.date.value = nowForInput();
  }
  $("editor-error").textContent = "";
  $("editor").showModal();
}

async function onSave(event) {
  event.preventDefault();
  const f = event.target.elements;
  const body = {
    transaction_type: f.transaction_type.value,
    amount: Number(f.amount.value),
    party: f.party.value.trim(),
    date: `${f.date.value.replace("T", " ")}:00`,
    status: f.status.value,
  };
  try {
    if (state.editing) await api("PUT", `/transactions/${state.editing.id}`, body);
    else await api("POST", "/transactions", body);
    $("editor").close();
    toast(state.editing ? "Transaction updated" : "Transaction added");
    refresh();
  } catch (err) {
    if (err.status === 401) { $("editor").close(); showError(err); return; }
    $("editor-error").textContent = err.message; // the dialog stays open so nothing typed is lost
  }
}

async function removeTransaction(t) {
  if (!confirm(`Delete the ${money(t.amount)} ${label(t.transaction_type)} from ${t.date}?`)) return;
  try {
    await api("DELETE", `/transactions/${t.id}`);
    toast("Transaction deleted");
    refresh();
  } catch (err) {
    showError(err);
  }
}

// ---------- start up ----------

function fillSelect(select, values) {
  for (const value of values) select.append(el("option", { value, textContent: label(value) }));
}

async function init() {
  fillSelect($("f-type"), TYPES);
  fillSelect($("f-status"), STATUSES);
  fillSelect($("editor-form").elements.transaction_type, TYPES);
  fillSelect($("editor-form").elements.status, STATUSES);
  if (typeof Chart !== "undefined") Chart.defaults.color = getComputedStyle(document.body).color;

  $("login-form").addEventListener("submit", onLogin);
  $("forgot-btn").addEventListener("click", () => {
    $("login-error").textContent = "Password reset isn't available yet. Create a new account with SignUp instead.";
  });
  $("logout-btn").addEventListener("click", logOut);
  $("upload-file").addEventListener("change", () => { $("upload-btn").disabled = !$("upload-file").files.length; });
  $("upload-form").addEventListener("submit", onUpload);
  $("new-btn").addEventListener("click", () => openEditor());
  $("cancel-btn").addEventListener("click", () => $("editor").close());
  $("editor-form").addEventListener("submit", onSave);
  for (const id of ["f-type", "f-status"]) {
    $(id).addEventListener("change", () => { state.page = 1; loadTransactions().catch(showError); });
  }
  $("prev").addEventListener("click", () => { state.page -= 1; loadTransactions().catch(showError); });
  $("next").addEventListener("click", () => { state.page += 1; loadTransactions().catch(showError); });

  // Already logged in from before? The cookie tells the server who we are.
  try {
    const { username } = await api("GET", "/auth/me");
    showApp(username);
  } catch {
    showLogin();
  }
}

init();
