const bridge = window.AstrBotPluginPage;

// === State ===
const state = {
  currentNovelId: null,
  novelData: null,
  charMap: {},
  isLoading: false,
  allNovels: [],
};

// === Init ===
async function init() {
  await bridge.ready();
  bindGlobalEvents();
  showListView();
}

// === Utility ===
function esc(str) {
  if (str == null) return "";
  const d = document.createElement("div");
  d.textContent = String(str);
  return d.innerHTML;
}

function formatNumber(n) {
  if (n == null) return "0";
  return n.toLocaleString("zh-CN");
}

function formatTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function chapterDisplay(ch) {
  if (ch.label) return ch.label;
  if (ch.is_extra) return `番外·${ch.title}`;
  if (ch.number > 0) return `第${ch.number}章`;
  return ch.title || "（未编号）";
}

function buildCharMap(novelData) {
  const m = {};
  for (const c of (novelData.characters || [])) {
    m[c.id] = c.name;
  }
  return m;
}

function charName(id) {
  return state.charMap[id] || id;
}

function charNames(ids) {
  return (ids || []).map(charName);
}

function statusBadge(status) {
  const cls = { draft: "badge-draft", review: "badge-review", final: "badge-final" }[status] || "badge-default";
  const label = { draft: "草稿", review: "审阅中", final: "定稿" }[status] || status;
  return `<span class="badge ${cls}">${esc(label)}</span>`;
}

function stripContent(novel) {
  // Build a copy of novel data without chapter content for memory efficiency
  // Actually the API already returns content via GET /novels/{id}, we'll use it as-is
}

// === Toast ===
function showToast(message, type = "error") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// === API ===
async function apiGet(path) {
  return bridge.apiGet(path);
}

async function apiPost(path, body) {
  return bridge.apiPost(path, body);
}

async function safeCall(fn) {
  if (state.isLoading) return null;
  state.isLoading = true;
  try {
    return await fn();
  } catch (err) {
    showToast(err.message || "请求失败");
    return null;
  } finally {
    state.isLoading = false;
  }
}

// === View Navigation ===
function showListView() {
  document.getElementById("view-list").classList.remove("hidden");
  document.getElementById("view-detail").classList.add("hidden");
  state.currentNovelId = null;
  state.novelData = null;
  loadNovelList();
}

function showDetailView(novelId) {
  document.getElementById("view-list").classList.add("hidden");
  document.getElementById("view-detail").classList.remove("hidden");
  state.currentNovelId = novelId;
  loadNovelDetail(novelId);
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabName));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${tabName}`));
}

// === Novel List ===
async function loadNovelList() {
  const novels = await safeCall(() => apiGet("novels"));
  if (novels === null) return;
  state.allNovels = novels || [];
  renderNovelList(state.allNovels);
}

function renderNovelList(novels) {
  const grid = document.getElementById("novel-grid");
  const empty = document.getElementById("novel-list-empty");
  if (!novels || novels.length === 0) {
    grid.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  grid.innerHTML = novels.map((n) => `
    <div class="novel-card" data-id="${esc(n.id)}">
      <h3>${esc(n.name)}</h3>
      ${n.synopsis ? `<p class="synopsis">${esc(n.synopsis)}</p>` : ""}
      <div class="stats">
        <span>${esc(String(n.chapter_count || 0))} 章</span>
        <span>${esc(String(n.character_count || 0))} 角色</span>
        <span>${formatTime(n.updated_at)}</span>
      </div>
    </div>
  `).join("");

  grid.querySelectorAll(".novel-card").forEach((card) => {
    card.addEventListener("click", () => showDetailView(card.dataset.id));
  });
}

// === Novel Detail ===
async function loadNovelDetail(novelId) {
  const data = await safeCall(() => apiGet(`novels/${novelId}`));
  if (!data) return;
  state.novelData = data;
  state.charMap = buildCharMap(data);
  document.getElementById("detail-novel-name").textContent = data.name;
  // Reset to overview tab
  switchTab("overview");
  renderOverview();
  renderCharacters();
  renderRelationships();
  renderEvents();
  renderOutlines();
  renderChapters();
  renderWorldSettings();
}

// === Overview Tab ===
function renderOverview() {
  const d = state.novelData;
  const totalWords = (d.chapters || []).reduce((s, ch) => s + (ch.content_length || 0), 0);
  const panel = document.getElementById("panel-overview");

  panel.innerHTML = `
    <div class="synopsis-card">
      <div class="card-header">
        <h3>故事梗概</h3>
        <button class="btn btn-sm btn-secondary" data-action="edit-synopsis">编辑</button>
      </div>
      ${d.synopsis
        ? `<p class="synopsis-text">${esc(d.synopsis)}</p>`
        : `<p class="synopsis-placeholder">暂无梗概，点击编辑添加</p>`}
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">${esc(String((d.characters || []).length))}</div>
        <div class="stat-label">角色</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${esc(String((d.relationships || []).length))}</div>
        <div class="stat-label">关系</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${esc(String((d.events || []).length))}</div>
        <div class="stat-label">事件</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${esc(String((d.outlines || []).length))}</div>
        <div class="stat-label">大纲</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${esc(String((d.chapters || []).length))}</div>
        <div class="stat-label">章节</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${formatNumber(totalWords)}</div>
        <div class="stat-label">总字数</div>
      </div>
    </div>

    <div class="recent-chapters">
      <div class="section-header">
        <h3>最近章节</h3>
      </div>
      ${renderRecentChapters(d.chapters || [])}
    </div>
  `;
}

function renderRecentChapters(chapters) {
  const sorted = [...chapters].sort((a, b) => (b.order || 0) - (a.order || 0)).slice(0, 5);
  if (sorted.length === 0) return `<p class="empty-state" style="padding:16px">暂无章节</p>`;
  return sorted.map((ch) => `
    <div class="recent-chapter-item">
      <span class="ch-label">${esc(chapterDisplay(ch))} ${esc(ch.title)}</span>
      <span class="ch-meta">${formatNumber(ch.content_length || 0)} 字 ${statusBadge(ch.status)}</span>
    </div>
  `).join("");
}

// === Characters Tab ===
function renderCharacters() {
  const chars = state.novelData.characters || [];
  const panel = document.getElementById("panel-characters");

  let html = `
    <div class="tab-toolbar">
      <input type="text" class="input-search" id="search-characters" placeholder="搜索角色..." />
      <button class="btn btn-primary btn-sm" data-action="create" data-type="character">+ 添加角色</button>
    </div>
  `;

  if (chars.length === 0) {
    html += `<div class="empty-state"><p>暂无角色</p></div>`;
  } else {
    html += `<div class="character-grid" id="characters-grid">`;
    html += chars.map((c) => renderCharacterCard(c)).join("");
    html += `</div>`;
  }

  panel.innerHTML = html;
}

function renderCharacterCard(c) {
  const fields = [
    c.personality ? `<p class="char-field"><b>性格：</b>${esc(c.personality)}</p>` : "",
    c.appearance ? `<p class="char-field"><b>外貌：</b>${esc(c.appearance)}</p>` : "",
    c.background ? `<p class="char-field"><b>背景：</b>${esc(c.background)}</p>` : "",
    c.notes ? `<p class="char-field"><b>备注：</b>${esc(c.notes)}</p>` : "",
  ].filter(Boolean).join("");

  return `
    <div class="character-card" data-char-id="${esc(c.id)}">
      <div class="char-name">${esc(c.name)}</div>
      ${fields || `<p class="char-field" style="color:var(--text-muted)">无详细描述</p>`}
      <div class="item-actions">
        <button class="btn btn-sm btn-secondary" data-action="edit" data-type="character" data-id="${esc(c.id)}">编辑</button>
        <button class="btn btn-sm btn-danger-outline" data-action="delete" data-type="character" data-id="${esc(c.id)}">删除</button>
      </div>
    </div>
  `;
}

// === Relationships Tab ===
function renderRelationships() {
  const rels = state.novelData.relationships || [];
  const panel = document.getElementById("panel-relationships");

  let html = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-primary btn-sm" data-action="create" data-type="relationship">+ 添加关系</button>
    </div>
  `;

  if (rels.length === 0) {
    html += `<div class="empty-state"><p>暂无关系</p></div>`;
  } else {
    html += rels.map((r) => `
      <div class="item-card">
        <div class="item-header">
          <div class="relationship-display">
            <span class="char-name">${esc(charName(r.character_a))}</span>
            <span class="relation-type">&larr; ${esc(r.relation_type || "未指定")} &rarr;</span>
            <span class="char-name">${esc(charName(r.character_b))}</span>
          </div>
          <span class="item-id">${esc(r.id)}</span>
        </div>
        ${r.description ? `<div class="item-body"><p>${esc(r.description)}</p></div>` : ""}
        <div class="item-actions">
          <button class="btn btn-sm btn-secondary" data-action="edit" data-type="relationship" data-id="${esc(r.id)}">编辑</button>
          <button class="btn btn-sm btn-danger-outline" data-action="delete" data-type="relationship" data-id="${esc(r.id)}">删除</button>
        </div>
      </div>
    `).join("");
  }

  panel.innerHTML = html;
}

// === Events Tab ===
function renderEvents() {
  const evts = state.novelData.events || [];
  const panel = document.getElementById("panel-events");

  let html = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-primary btn-sm" data-action="create" data-type="event">+ 添加事件</button>
    </div>
  `;

  if (evts.length === 0) {
    html += `<div class="empty-state"><p>暂无事件</p></div>`;
  } else {
    html += evts.map((e) => {
      const names = charNames(e.involved_characters);
      return `
        <div class="item-card">
          <div class="item-header">
            <strong>${esc(e.name)}</strong>
            <span class="item-id">${esc(e.id)}</span>
          </div>
          <div class="item-body">
            ${e.timeline_position ? `<p><b>时间线：</b>${esc(e.timeline_position)}</p>` : ""}
            ${e.description ? `<p><b>描述：</b>${esc(e.description)}</p>` : ""}
            ${names.length > 0 ? `<p><b>涉及角色：</b>${names.map((n) => `<span class="tag">${esc(n)}</span>`).join("")}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="btn btn-sm btn-secondary" data-action="edit" data-type="event" data-id="${esc(e.id)}">编辑</button>
            <button class="btn btn-sm btn-danger-outline" data-action="delete" data-type="event" data-id="${esc(e.id)}">删除</button>
          </div>
        </div>
      `;
    }).join("");
  }

  panel.innerHTML = html;
}

// === Outlines Tab ===
function renderOutlines() {
  const outlines = state.novelData.outlines || [];
  const panel = document.getElementById("panel-outlines");

  let html = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-primary btn-sm" data-action="create" data-type="outline">+ 添加大纲</button>
    </div>
  `;

  if (outlines.length === 0) {
    html += `<div class="empty-state"><p>暂无大纲</p></div>`;
  } else {
    html += `<div class="outline-tree">${renderOutlineTree(outlines)}</div>`;
  }

  panel.innerHTML = html;
}

function renderOutlineTree(outlines, parentId = "") {
  const children = outlines.filter((o) => (o.parent_id || "") === parentId);
  if (children.length === 0) return "";
  return children.sort((a, b) => (a.order || 0) - (b.order || 0)).map((o) => {
    const childHtml = renderOutlineTree(outlines, o.id);
    return `
      <div class="outline-node">
        <div class="outline-card">
          <div class="item-header">
            <span class="outline-title">${esc(o.title)}</span>
            <span class="item-id">${esc(o.id)}</span>
          </div>
          ${o.chapter_plan ? `<p class="outline-meta"><b>章节规划：</b>${esc(o.chapter_plan)}</p>` : ""}
          ${o.plot_direction ? `<p class="outline-meta"><b>情节走向：</b>${esc(o.plot_direction)}</p>` : ""}
          ${o.notes ? `<p class="outline-meta"><b>备注：</b>${esc(o.notes)}</p>` : ""}
          <div class="item-actions">
            <button class="btn btn-sm btn-secondary" data-action="edit" data-type="outline" data-id="${esc(o.id)}">编辑</button>
            <button class="btn btn-sm btn-danger-outline" data-action="delete" data-type="outline" data-id="${esc(o.id)}">删除</button>
          </div>
        </div>
        ${childHtml}
      </div>
    `;
  }).join("");
}

// === Chapters Tab ===
function renderChapters() {
  const chapters = state.novelData.chapters || [];
  const panel = document.getElementById("panel-chapters");

  let html = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-primary btn-sm" data-action="create" data-type="chapter">+ 添加章节</button>
    </div>
  `;

  if (chapters.length === 0) {
    html += `<div class="empty-state"><p>暂无章节</p></div>`;
  } else {
    const sorted = [...chapters].sort((a, b) => (a.order || 0) - (b.order || 0));
    html += sorted.map((ch) => renderChapterCard(ch)).join("");
  }

  panel.innerHTML = html;
}

function renderChapterCard(ch) {
  const display = chapterDisplay(ch);
  return `
    <div class="item-card">
      <div class="item-header">
        <strong>${esc(display)} ${esc(ch.title)}</strong>
        <span class="item-id">${esc(ch.id)}</span>
      </div>
      <div class="chapter-meta-row">
        ${statusBadge(ch.status)}
        <span>${formatNumber(ch.content_length || 0)} 字</span>
        ${ch.is_extra ? `<span class="badge badge-default badge-sm">番外</span>` : ""}
      </div>
      ${ch.summary ? `<p class="chapter-summary">${esc(ch.summary)}</p>` : ""}
      ${ch.content ? `<pre class="chapter-content-preview">${esc(ch.content.substring(0, 500))}${ch.content.length > 500 ? "\n..." : ""}</pre>` : ""}
      <div class="item-actions">
        <button class="btn btn-sm btn-secondary" data-action="edit" data-type="chapter" data-id="${esc(ch.id)}">编辑元数据</button>
        <button class="btn btn-sm btn-outline" data-action="download-chapter" data-id="${esc(ch.id)}">下载</button>
        <button class="btn btn-sm btn-danger-outline" data-action="delete" data-type="chapter" data-id="${esc(ch.id)}">删除</button>
      </div>
    </div>
  `;
}

// === World Settings Tab ===
function renderWorldSettings() {
  const settings = state.novelData.world_settings || [];
  const panel = document.getElementById("panel-world_settings");

  let html = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-primary btn-sm" data-action="create" data-type="world_setting">+ 添加设定</button>
    </div>
  `;

  if (settings.length === 0) {
    html += `<div class="empty-state"><p>暂无世界观设定</p></div>`;
  } else {
    const groups = {};
    for (const s of settings) {
      const cat = s.category || "未分类";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(s);
    }
    for (const [cat, items] of Object.entries(groups)) {
      html += `
        <div class="category-group">
          <div class="category-header">
            <span class="toggle-icon">&#9660;</span>
            <h3>${esc(cat)}</h3>
            <span class="badge badge-default badge-sm">${items.length} 项</span>
          </div>
          <div class="category-items">
            ${items.map((s) => `
              <div class="setting-card">
                <div class="item-header">
                  <span class="setting-name">${esc(s.name)}</span>
                  <span class="item-id">${esc(s.id)}</span>
                </div>
                ${s.description ? `<p class="setting-desc">${esc(s.description)}</p>` : ""}
                <div class="item-actions">
                  <button class="btn btn-sm btn-secondary" data-action="edit" data-type="world_setting" data-id="${esc(s.id)}">编辑</button>
                  <button class="btn btn-sm btn-danger-outline" data-action="delete" data-type="world_setting" data-id="${esc(s.id)}">删除</button>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    }
  }

  panel.innerHTML = html;
}

// === Form Field Definitions ===
const FORM_FIELDS = {
  character: [
    { key: "name", label: "姓名", type: "text", required: true },
    { key: "personality", label: "性格", type: "textarea" },
    { key: "appearance", label: "外貌", type: "textarea" },
    { key: "background", label: "背景", type: "textarea" },
    { key: "notes", label: "备注", type: "textarea" },
  ],
  relationship: [
    { key: "character_a", label: "角色A", type: "select", options: "characters", required: true },
    { key: "character_b", label: "角色B", type: "select", options: "characters", required: true },
    { key: "relation_type", label: "关系类型", type: "text", required: true },
    { key: "description", label: "描述", type: "textarea" },
  ],
  event: [
    { key: "name", label: "事件名", type: "text", required: true },
    { key: "timeline_position", label: "时间线位置", type: "text" },
    { key: "description", label: "描述", type: "textarea" },
    { key: "involved_characters", label: "涉及角色", type: "multiselect", options: "characters" },
  ],
  outline: [
    { key: "title", label: "标题", type: "text", required: true },
    { key: "chapter_plan", label: "章节规划", type: "textarea" },
    { key: "plot_direction", label: "情节走向", type: "textarea" },
    { key: "notes", label: "备注", type: "textarea" },
    { key: "parent_id", label: "父大纲", type: "select", options: "outlines", allowEmpty: true },
  ],
  chapter: [
    { key: "number", label: "章节号", type: "number" },
    { key: "title", label: "标题", type: "text", required: true },
    { key: "status", label: "状态", type: "select", options: "chapterStatuses" },
    { key: "label", label: "自定义标签", type: "text", hint: "设置后覆盖默认\"第N章\"格式" },
    { key: "is_extra", label: "番外", type: "checkbox" },
    { key: "summary", label: "摘要", type: "textarea" },
  ],
  world_setting: [
    { key: "category", label: "分类", type: "text", required: true },
    { key: "name", label: "名称", type: "text", required: true },
    { key: "description", label: "描述", type: "textarea" },
  ],
  novel_meta: [
    { key: "name", label: "小说名称", type: "text", required: true },
    { key: "synopsis", label: "故事梗概", type: "textarea", rows: 6 },
  ],
};

const STATIC_OPTIONS = {
  chapterStatuses: [
    { value: "draft", label: "草稿" },
    { value: "review", label: "审阅中" },
    { value: "final", label: "定稿" },
  ],
};

function getOptionsForField(field) {
  if (field.options === "characters") {
    return (state.novelData.characters || []).map((c) => ({ value: c.id, label: c.name }));
  }
  if (field.options === "outlines") {
    return (state.novelData.outlines || []).map((o) => ({ value: o.id, label: o.title }));
  }
  if (field.options === "chapterStatuses") {
    return STATIC_OPTIONS.chapterStatuses;
  }
  return [];
}

function buildFormHtml(fields, data = {}) {
  return fields.map((f) => {
    const val = data[f.key] !== undefined ? data[f.key] : "";
    const reqMark = f.required ? ' <span style="color:var(--danger)">*</span>' : "";

    if (f.type === "textarea") {
      const displayVal = f.key === "involved_characters" && Array.isArray(val) ? val.join(", ") : val;
      const rows = f.rows || 3;
      return `<label>${f.label}${reqMark}<textarea name="${f.key}" rows="${rows}" ${f.required ? "required" : ""}>${esc(String(displayVal))}</textarea></label>`;
    }

    if (f.type === "select") {
      const options = getOptionsForField(f);
      let optHtml = f.allowEmpty ? `<option value="">（无）</option>` : "";
      optHtml += options.map((o) => `<option value="${esc(o.value)}" ${o.value === val ? "selected" : ""}>${esc(o.label)}</option>`).join("");
      return `<label>${f.label}${reqMark}<select name="${f.key}">${optHtml}</select></label>`;
    }

    if (f.type === "multiselect") {
      const options = getOptionsForField(f);
      const selectedIds = Array.isArray(val) ? val : [];
      const checkboxes = options.map((o) => `
        <label class="checkbox-item">
          <input type="checkbox" name="${f.key}" value="${esc(o.value)}" ${selectedIds.includes(o.value) ? "checked" : ""} />
          ${esc(o.label)}
        </label>
      `).join("");
      return `<label>${f.label}${reqMark}<div class="checkbox-group">${checkboxes}</div></label>`;
    }

    if (f.type === "checkbox") {
      return `<label class="checkbox-item" style="margin-bottom:14px">
        <input type="checkbox" name="${f.key}" ${val ? "checked" : ""} style="width:auto;margin:0" />
        ${f.label}
      </label>`;
    }

    const inputType = f.type === "number" ? "number" : "text";
    const hint = f.hint ? `<span class="field-hint">${esc(f.hint)}</span>` : "";
    return `<label>${f.label}${reqMark}<input type="${inputType}" name="${f.key}" value="${esc(String(val))}" ${f.required ? "required" : ""} />${hint}</label>`;
  }).join("");
}

// === Modal ===
let modalSaveHandler = null;

function showModal(title, formHtml, onSave) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-form").innerHTML = formHtml;
  document.getElementById("modal-overlay").classList.remove("hidden");
  modalSaveHandler = onSave;
}

function hideModal() {
  document.getElementById("modal-overlay").classList.add("hidden");
  modalSaveHandler = null;
}

function showConfirm(message, onOk) {
  document.getElementById("confirm-message").textContent = message;
  document.getElementById("confirm-overlay").classList.remove("hidden");
  document.getElementById("confirm-ok").onclick = () => {
    document.getElementById("confirm-overlay").classList.add("hidden");
    onOk();
  };
}

function collectFormData(formEl, fields) {
  const body = {};
  for (const f of fields) {
    if (f.type === "multiselect") {
      const checked = formEl.querySelectorAll(`input[name="${f.key}"]:checked`);
      body[f.key] = Array.from(checked).map((c) => c.value);
    } else if (f.type === "checkbox") {
      const cb = formEl.querySelector(`input[name="${f.key}"]`);
      body[f.key] = cb ? cb.checked : false;
    } else if (f.type === "number") {
      const input = formEl.querySelector(`[name="${f.key}"]`);
      body[f.key] = input ? (parseInt(input.value, 10) || 0) : 0;
    } else if (f.type === "select") {
      const sel = formEl.querySelector(`[name="${f.key}"]`);
      body[f.key] = sel ? sel.value : "";
    } else {
      const input = formEl.querySelector(`[name="${f.key}"]`);
      body[f.key] = input ? input.value : "";
    }
  }
  return body;
}

// === CRUD Operations ===
function getTypeName(type) {
  const names = { character: "角色", relationship: "关系", event: "事件", outline: "大纲", chapter: "章节", world_setting: "世界观设定" };
  return names[type] || type;
}

function getCollectionKey(type) {
  // API uses plural form
  return type === "world_setting" ? "world_settings" : `${type}s`;
}

function showCreateForm(type) {
  const fields = FORM_FIELDS[type];
  if (!fields) return;
  const formHtml = buildFormHtml(fields);
  showModal(`添加${getTypeName(type)}`, formHtml, async (body) => {
    return safeCall(() => apiPost(`novels/${state.currentNovelId}/${getCollectionKey(type)}`, body));
  });
}

function showEditForm(type, itemId) {
  const fields = FORM_FIELDS[type];
  if (!fields) return;
  const collection = type === "world_setting" ? "world_settings" : `${type}s`;
  const items = state.novelData[collection] || [];
  const item = items.find((i) => i.id === itemId);
  if (!item) return;

  const formHtml = buildFormHtml(fields, item);
  showModal(`编辑${getTypeName(type)}`, formHtml, async (body) => {
    return safeCall(() => apiPost(`novels/${state.currentNovelId}/${getCollectionKey(type)}/${itemId}`, body));
  });
}

function handleDelete(type, itemId) {
  showConfirm(`确定删除该${getTypeName(type)}？此操作不可撤销。`, async () => {
    const result = await safeCall(() =>
      apiPost(`novels/${state.currentNovelId}/${getCollectionKey(type)}/${itemId}`, { _action: "delete" })
    );
    if (result !== null) await loadNovelDetail(state.currentNovelId);
  });
}

function showSynopsisEditForm() {
  const fields = FORM_FIELDS.novel_meta;
  const data = { name: state.novelData.name, synopsis: state.novelData.synopsis };
  const formHtml = buildFormHtml(fields, data);
  showModal("编辑小说信息", formHtml, async (body) => {
    return safeCall(() => apiPost(`novels/${state.currentNovelId}/update`, body));
  });
}

async function handleDownloadChapter(chapterId) {
  await safeCall(() => bridge.download(`novels/${state.currentNovelId}/download`, { chapter: chapterId }, "chapter.txt"));
}

async function handleDownloadNovel() {
  await safeCall(() => bridge.download(`novels/${state.currentNovelId}/download`, {}, `${state.novelData.name}_全本.txt`));
}

async function handleCreateNovel() {
  const formHtml = `<label>小说名称 <span style="color:var(--danger)">*</span><input type="text" name="name" required /></label>`;
  showModal("新建小说", formHtml, async (body) => {
    if (!body.name.trim()) {
      showToast("名称不能为空");
      return null;
    }
    return safeCall(() => apiPost("novels/create", body));
  });
}

async function handleDeleteNovel() {
  showConfirm(`确定删除小说「${state.novelData.name}」？所有数据将被永久删除。`, async () => {
    const result = await safeCall(() => apiPost(`novels/${state.currentNovelId}/delete`, {}));
    if (result !== null) showListView();
  });
}

// === Event Binding ===
function bindGlobalEvents() {
  // Back button
  document.getElementById("btn-back").addEventListener("click", showListView);

  // Create novel
  document.getElementById("btn-create-novel").addEventListener("click", handleCreateNovel);

  // Delete novel
  document.getElementById("btn-delete-novel").addEventListener("click", handleDeleteNovel);

  // Download novel
  document.getElementById("btn-download-novel").addEventListener("click", handleDownloadNovel);

  // Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Modal save
  document.getElementById("modal-save").addEventListener("click", async () => {
    if (!modalSaveHandler) return;
    const formEl = document.getElementById("modal-form");
    // Determine which fields to collect based on the current modal context
    // We pass all named inputs as a simple dict
    const body = {};
    const formData = new FormData(formEl);
    const seen = new Set();
    for (const [key, val] of formData.entries()) {
      if (seen.has(key)) {
        if (!Array.isArray(body[key])) body[key] = [body[key]];
        body[key].push(val);
      } else {
        body[key] = val;
        seen.add(key);
      }
    }
    // Handle checkboxes that aren't in formData (unchecked ones)
    formEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      if (!seen.has(cb.name)) {
        body[cb.name] = false;
      } else if (cb.name === "is_extra") {
        // is_extra is boolean
        body[cb.name] = true;
      }
    });
    // Convert number fields
    if ("number" in body && typeof body.number === "string") {
      body.number = parseInt(body.number, 10) || 0;
    }
    // Convert multiselect arrays
    formEl.querySelectorAll(".checkbox-group").forEach((group) => {
      const name = group.querySelector("input")?.name;
      if (name && body[name] && !Array.isArray(body[name])) {
        body[name] = [body[name]];
      }
    });

    const result = await modalSaveHandler(body);
    if (result !== null && result !== undefined) {
      hideModal();
      if (state.currentNovelId) {
        await loadNovelDetail(state.currentNovelId);
      } else {
        await loadNovelList();
      }
    }
  });

  // Modal cancel
  document.getElementById("modal-cancel").addEventListener("click", hideModal);

  // Confirm cancel
  document.getElementById("confirm-cancel").addEventListener("click", () => {
    document.getElementById("confirm-overlay").classList.add("hidden");
  });

  // Search novels
  document.getElementById("search-novels").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    const filtered = state.allNovels.filter((n) => (n.name || "").toLowerCase().includes(q));
    renderNovelList(filtered);
  });

  // Delegated events on tab panels
  document.querySelector(".tab-panels").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    const type = btn.dataset.type;
    const id = btn.dataset.id;

    switch (action) {
      case "create":
        showCreateForm(type);
        break;
      case "edit":
        showEditForm(type, id);
        break;
      case "delete":
        handleDelete(type, id);
        break;
      case "edit-synopsis":
        showSynopsisEditForm();
        break;
      case "download-chapter":
        handleDownloadChapter(id);
        break;
    }
  });

  // Delegated search for characters
  document.querySelector(".tab-panels").addEventListener("input", (e) => {
    if (e.target.id === "search-characters") {
      const q = e.target.value.toLowerCase();
      const chars = (state.novelData.characters || []).filter((c) => c.name.toLowerCase().includes(q));
      const grid = document.getElementById("characters-grid");
      if (grid) grid.innerHTML = chars.map((c) => renderCharacterCard(c)).join("");
    }
  });

  // Close modals on overlay click
  document.getElementById("modal-overlay").addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") hideModal();
  });
  document.getElementById("confirm-overlay").addEventListener("click", (e) => {
    if (e.target.id === "confirm-overlay") {
      document.getElementById("confirm-overlay").classList.add("hidden");
    }
  });
}

// === Start ===
init();
