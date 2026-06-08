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

function fmt(n) {
  return (n ?? 0).toLocaleString("zh-CN");
}

function fmtTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function chDisplay(ch) {
  if (ch.label) return ch.label;
  if (ch.is_extra) return `番外·${ch.title}`;
  if (ch.number > 0) return `第${ch.number}章`;
  return ch.title || "（未编号）";
}

function buildCharMap(data) {
  const m = {};
  for (const c of (data.characters || [])) m[c.id] = c.name;
  return m;
}

function cName(id) {
  return state.charMap[id] || id;
}

function cNames(ids) {
  return (ids || []).map(cName);
}

function statusBadge(s) {
  const cls = { draft: "badge-draft", review: "badge-review", final: "badge-final" }[s] || "badge-default";
  const lbl = { draft: "草稿", review: "审阅中", final: "定稿" }[s] || s;
  return `<span class="badge ${cls}">${esc(lbl)}</span>`;
}

// === Toast ===
function toast(msg, type = "error") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// === API ===
async function safe(fn) {
  if (state.isLoading) return null;
  state.isLoading = true;
  try {
    return await fn();
  } catch (e) {
    toast(e.message || "请求失败");
    return null;
  } finally {
    state.isLoading = false;
  }
}

// === Navigation ===
function showListView() {
  document.getElementById("view-list").classList.remove("hidden");
  document.getElementById("view-detail").classList.add("hidden");
  state.currentNovelId = null;
  state.novelData = null;
  loadNovelList();
}

function showDetail(id) {
  document.getElementById("view-list").classList.add("hidden");
  document.getElementById("view-detail").classList.remove("hidden");
  state.currentNovelId = id;
  loadDetail(id);
}

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
}

// === Novel List ===
async function loadNovelList() {
  const novels = await safe(() => bridge.apiGet("novels"));
  if (novels === null) return;
  state.allNovels = novels || [];
  renderList(state.allNovels);
}

function renderList(novels) {
  const grid = document.getElementById("novel-grid");
  const empty = document.getElementById("novel-list-empty");
  if (!novels || !novels.length) {
    grid.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  grid.innerHTML = novels.map((n) => `
    <div class="novel-card" data-id="${esc(n.id)}">
      <div class="novel-name">${esc(n.name)}</div>
      ${n.synopsis ? `<p class="synopsis">${esc(n.synopsis)}</p>` : ""}
      <div class="meta-row">
        <span>${n.chapter_count || 0} 章</span>
        <span>${n.character_count || 0} 角色</span>
        <span>${fmtTime(n.updated_at)}</span>
      </div>
    </div>
  `).join("");
  grid.querySelectorAll(".novel-card").forEach((c) => {
    c.addEventListener("click", () => showDetail(c.dataset.id));
  });
}

// === Novel Detail ===
async function loadDetail(id) {
  const data = await safe(() => bridge.apiGet(`novels/${id}`));
  if (!data) return;
  state.novelData = data;
  state.charMap = buildCharMap(data);
  document.getElementById("detail-novel-name").textContent = data.name;
  switchTab("overview");
  renderOverview();
  renderCharacters();
  renderRelationships();
  renderEvents();
  renderOutlines();
  renderChapters();
  renderWorldSettings();
}

// === Overview ===
function renderOverview() {
  const d = state.novelData;
  const words = (d.chapters || []).reduce((s, ch) => s + (ch.content_length || 0), 0);
  const panel = document.getElementById("panel-overview");

  panel.innerHTML = `
    <div class="synopsis-block">
      <div class="block-header">
        <span class="block-title">故事梗概</span>
        <button class="btn btn-ghost btn-sm" data-action="edit-synopsis">编辑</button>
      </div>
      ${d.synopsis
        ? `<p class="synopsis-text">${esc(d.synopsis)}</p>`
        : `<p class="synopsis-placeholder">暂无梗概，点击编辑添加</p>`}
    </div>

    <div class="stat-grid">
      <div class="stat-card"><div class="stat-value">${(d.characters || []).length}</div><div class="stat-label">角色</div></div>
      <div class="stat-card"><div class="stat-value">${(d.relationships || []).length}</div><div class="stat-label">关系</div></div>
      <div class="stat-card"><div class="stat-value">${(d.events || []).length}</div><div class="stat-label">事件</div></div>
      <div class="stat-card"><div class="stat-value">${(d.outlines || []).length}</div><div class="stat-label">大纲</div></div>
      <div class="stat-card"><div class="stat-value">${(d.chapters || []).length}</div><div class="stat-label">章节</div></div>
      <div class="stat-card"><div class="stat-value">${fmt(words)}</div><div class="stat-label">总字数</div></div>
    </div>

    <div class="section-block">
      <div class="section-title">最近章节</div>
      <div class="recent-block">
        ${renderRecent(d.chapters || [])}
      </div>
    </div>
  `;
}

function renderRecent(chapters) {
  const sorted = [...chapters].sort((a, b) => (b.order || 0) - (a.order || 0)).slice(0, 5);
  if (!sorted.length) return `<p style="padding:12px 0;color:var(--ink-muted);text-align:center">暂无章节</p>`;
  return sorted.map((ch) => `
    <div class="recent-item">
      <span class="ch-label">${esc(chDisplay(ch))} ${esc(ch.title)}</span>
      <span class="ch-meta">${fmt(ch.content_length)} 字 ${statusBadge(ch.status)}</span>
    </div>
  `).join("");
}

// === Characters ===
function renderCharacters() {
  const chars = state.novelData.characters || [];
  const panel = document.getElementById("panel-characters");
  let h = `
    <div class="tab-toolbar">
      <div class="search-wrap">
        <svg class="search-icon" viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/></svg>
        <input type="text" class="input-search" id="search-characters" placeholder="搜索角色..." />
      </div>
      <button class="btn btn-accent btn-sm" data-action="create" data-type="character">添加角色</button>
    </div>`;
  if (!chars.length) {
    h += `<div class="empty-state"><div class="empty-decor">~</div><p>暂无角色</p></div>`;
  } else {
    h += `<div class="character-grid" id="characters-grid">${chars.map(charCard).join("")}</div>`;
  }
  panel.innerHTML = h;
}

function charCard(c) {
  const fields = [
    c.personality ? `<p class="char-field"><b>性格：</b>${esc(c.personality)}</p>` : "",
    c.appearance ? `<p class="char-field"><b>外貌：</b>${esc(c.appearance)}</p>` : "",
    c.background ? `<p class="char-field"><b>背景：</b>${esc(c.background)}</p>` : "",
    c.notes ? `<p class="char-field"><b>备注：</b>${esc(c.notes)}</p>` : "",
  ].filter(Boolean).join("");
  return `
    <div class="character-card" data-char-id="${esc(c.id)}">
      <div class="char-name">${esc(c.name)}</div>
      ${fields || `<p class="char-field" style="color:var(--ink-muted)">无详细描述</p>`}
      <div class="item-actions">
        <button class="btn btn-ghost btn-sm" data-action="edit" data-type="character" data-id="${esc(c.id)}">编辑</button>
        <button class="btn btn-danger-ghost btn-sm" data-action="delete" data-type="character" data-id="${esc(c.id)}">删除</button>
      </div>
    </div>`;
}

// === Relationships ===
function renderRelationships() {
  const rels = state.novelData.relationships || [];
  const panel = document.getElementById("panel-relationships");
  let h = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-accent btn-sm" data-action="create" data-type="relationship">添加关系</button>
    </div>`;
  if (!rels.length) {
    h += `<div class="empty-state"><div class="empty-decor">~</div><p>暂无关系</p></div>`;
  } else {
    h += rels.map((r) => `
      <div class="item-card">
        <div class="relationship-line">
          <span class="char-name">${esc(cName(r.character_a))}</span>
          <span class="relation-arrow">${esc(r.relation_type || "—")}</span>
          <span class="char-name">${esc(cName(r.character_b))}</span>
        </div>
        ${r.description ? `<div class="item-body"><p>${esc(r.description)}</p></div>` : ""}
        <div class="item-actions">
          <button class="btn btn-ghost btn-sm" data-action="edit" data-type="relationship" data-id="${esc(r.id)}">编辑</button>
          <button class="btn btn-danger-ghost btn-sm" data-action="delete" data-type="relationship" data-id="${esc(r.id)}">删除</button>
        </div>
      </div>`).join("");
  }
  panel.innerHTML = h;
}

// === Events ===
function renderEvents() {
  const evts = state.novelData.events || [];
  const panel = document.getElementById("panel-events");
  let h = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-accent btn-sm" data-action="create" data-type="event">添加事件</button>
    </div>`;
  if (!evts.length) {
    h += `<div class="empty-state"><div class="empty-decor">~</div><p>暂无事件</p></div>`;
  } else {
    h += evts.map((e) => {
      const names = cNames(e.involved_characters);
      return `
        <div class="item-card">
          <div class="item-header">
            <strong>${esc(e.name)}</strong>
            <span class="item-id">${esc(e.id)}</span>
          </div>
          <div class="item-body">
            ${e.timeline_position ? `<p><b>时间线：</b>${esc(e.timeline_position)}</p>` : ""}
            ${e.description ? `<p><b>描述：</b>${esc(e.description)}</p>` : ""}
            ${names.length ? `<p><b>涉及角色：</b>${names.map((n) => `<span class="tag">${esc(n)}</span>`).join("")}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="btn btn-ghost btn-sm" data-action="edit" data-type="event" data-id="${esc(e.id)}">编辑</button>
            <button class="btn btn-danger-ghost btn-sm" data-action="delete" data-type="event" data-id="${esc(e.id)}">删除</button>
          </div>
        </div>`;
    }).join("");
  }
  panel.innerHTML = h;
}

// === Outlines ===
function renderOutlines() {
  const outlines = state.novelData.outlines || [];
  const panel = document.getElementById("panel-outlines");
  let h = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-accent btn-sm" data-action="create" data-type="outline">添加大纲</button>
    </div>`;
  if (!outlines.length) {
    h += `<div class="empty-state"><div class="empty-decor">~</div><p>暂无大纲</p></div>`;
  } else {
    h += `<div class="outline-tree">${outlineTree(outlines)}</div>`;
  }
  panel.innerHTML = h;
}

function outlineTree(all, pid = "") {
  const children = all.filter((o) => (o.parent_id || "") === pid);
  if (!children.length) return "";
  return children.sort((a, b) => (a.order || 0) - (b.order || 0)).map((o) => `
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
          <button class="btn btn-ghost btn-sm" data-action="edit" data-type="outline" data-id="${esc(o.id)}">编辑</button>
          <button class="btn btn-danger-ghost btn-sm" data-action="delete" data-type="outline" data-id="${esc(o.id)}">删除</button>
        </div>
      </div>
      ${outlineTree(all, o.id)}
    </div>`).join("");
}

// === Chapters ===
function renderChapters() {
  const chapters = state.novelData.chapters || [];
  const panel = document.getElementById("panel-chapters");
  let h = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-accent btn-sm" data-action="create" data-type="chapter">添加章节</button>
    </div>`;
  if (!chapters.length) {
    h += `<div class="empty-state"><div class="empty-decor">~</div><p>暂无章节</p></div>`;
  } else {
    const sorted = [...chapters].sort((a, b) => (a.order || 0) - (b.order || 0));
    h += sorted.map(chCard).join("");
  }
  panel.innerHTML = h;
}

function chCard(ch) {
  const disp = chDisplay(ch);
  return `
    <div class="item-card">
      <div class="item-header">
        <strong>${esc(disp)} ${esc(ch.title)}</strong>
        <span class="item-id">${esc(ch.id)}</span>
      </div>
      <div class="chapter-meta-row">
        ${statusBadge(ch.status)}
        <span>${fmt(ch.content_length)} 字</span>
        ${ch.is_extra ? `<span class="badge badge-default badge-sm">番外</span>` : ""}
      </div>
      ${ch.summary ? `<p class="chapter-summary">${esc(ch.summary)}</p>` : ""}
      ${ch.content ? `<pre class="chapter-content-preview">${esc(ch.content.substring(0, 500))}${ch.content.length > 500 ? "\n..." : ""}</pre>` : ""}
      <div class="item-actions">
        <button class="btn btn-ghost btn-sm" data-action="edit" data-type="chapter" data-id="${esc(ch.id)}">编辑元数据</button>
        <button class="btn btn-outline btn-sm" data-action="download-chapter" data-id="${esc(ch.id)}">
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"/></svg>
          下载
        </button>
        <button class="btn btn-danger-ghost btn-sm" data-action="delete" data-type="chapter" data-id="${esc(ch.id)}">删除</button>
      </div>
    </div>`;
}

// === World Settings ===
function renderWorldSettings() {
  const settings = state.novelData.world_settings || [];
  const panel = document.getElementById("panel-world_settings");
  let h = `
    <div class="tab-toolbar">
      <span></span>
      <button class="btn btn-accent btn-sm" data-action="create" data-type="world_setting">添加设定</button>
    </div>`;
  if (!settings.length) {
    h += `<div class="empty-state"><div class="empty-decor">~</div><p>暂无世界观设定</p></div>`;
  } else {
    const groups = {};
    for (const s of settings) {
      const cat = s.category || "未分类";
      (groups[cat] ??= []).push(s);
    }
    for (const [cat, items] of Object.entries(groups)) {
      h += `
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
                  <button class="btn btn-ghost btn-sm" data-action="edit" data-type="world_setting" data-id="${esc(s.id)}">编辑</button>
                  <button class="btn btn-danger-ghost btn-sm" data-action="delete" data-type="world_setting" data-id="${esc(s.id)}">删除</button>
                </div>
              </div>`).join("")}
          </div>
        </div>`;
    }
  }
  panel.innerHTML = h;
}

// === Form Definitions ===
const FIELDS = {
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

const STATIC_OPTS = {
  chapterStatuses: [
    { value: "draft", label: "草稿" },
    { value: "review", label: "审阅中" },
    { value: "final", label: "定稿" },
  ],
};

function fieldOpts(f) {
  if (f.options === "characters") return (state.novelData.characters || []).map((c) => ({ v: c.id, l: c.name }));
  if (f.options === "outlines") return (state.novelData.outlines || []).map((o) => ({ v: o.id, l: o.title }));
  if (f.options === "chapterStatuses") return STATIC_OPTS.chapterStatuses;
  return [];
}

function buildForm(fields, data = {}) {
  return fields.map((f) => {
    const val = data[f.key] !== undefined ? data[f.key] : "";
    const req = f.required ? ' <span style="color:var(--danger)">*</span>' : "";

    if (f.type === "textarea") {
      const dv = f.key === "involved_characters" && Array.isArray(val) ? val.join(", ") : val;
      return `<label>${f.label}${req}<textarea name="${f.key}" rows="${f.rows || 3}" ${f.required ? "required" : ""}>${esc(String(dv))}</textarea></label>`;
    }
    if (f.type === "select") {
      const opts = fieldOpts(f);
      let oh = f.allowEmpty ? `<option value="">（无）</option>` : "";
      oh += opts.map((o) => `<option value="${esc(o.v)}" ${o.v === val ? "selected" : ""}>${esc(o.l)}</option>`).join("");
      return `<label>${f.label}${req}<select name="${f.key}">${oh}</select></label>`;
    }
    if (f.type === "multiselect") {
      const opts = fieldOpts(f);
      const sel = Array.isArray(val) ? val : [];
      const cbs = opts.map((o) => `
        <label class="checkbox-item">
          <input type="checkbox" name="${f.key}" value="${esc(o.v)}" ${sel.includes(o.v) ? "checked" : ""} />
          ${esc(o.l)}
        </label>`).join("");
      return `<label>${f.label}${req}<div class="checkbox-group">${cbs}</div></label>`;
    }
    if (f.type === "checkbox") {
      return `<label class="checkbox-item" style="margin-bottom:18px">
        <input type="checkbox" name="${f.key}" ${val ? "checked" : ""} style="width:auto;margin:0" />
        ${f.label}
      </label>`;
    }
    const it = f.type === "number" ? "number" : "text";
    const hint = f.hint ? `<span class="field-hint">${esc(f.hint)}</span>` : "";
    return `<label>${f.label}${req}<input type="${it}" name="${f.key}" value="${esc(String(val))}" ${f.required ? "required" : ""} />${hint}</label>`;
  }).join("");
}

// === Modal ===
let _onSave = null;

function showModal(title, formHtml, onSave) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-form").innerHTML = formHtml;
  document.getElementById("modal-overlay").classList.remove("hidden");
  _onSave = onSave;
}

function hideModal() {
  document.getElementById("modal-overlay").classList.add("hidden");
  _onSave = null;
}

function showConfirm(msg, onOk) {
  document.getElementById("confirm-message").textContent = msg;
  document.getElementById("confirm-overlay").classList.remove("hidden");
  document.getElementById("confirm-ok").onclick = () => {
    document.getElementById("confirm-overlay").classList.add("hidden");
    onOk();
  };
}

// === CRUD ===
const TYPE_NAMES = { character: "角色", relationship: "关系", event: "事件", outline: "大纲", chapter: "章节", world_setting: "世界观设定" };

function collKey(t) {
  return t === "world_setting" ? "world_settings" : `${t}s`;
}

function createForm(type) {
  const fields = FIELDS[type];
  if (!fields) return;
  showModal(`添加${TYPE_NAMES[type]}`, buildForm(fields), async (body) => {
    return safe(() => bridge.apiPost(`novels/${state.currentNovelId}/${collKey(type)}`, body));
  });
}

function editForm(type, id) {
  const fields = FIELDS[type];
  if (!fields) return;
  const coll = collKey(type);
  const item = (state.novelData[coll] || []).find((i) => i.id === id);
  if (!item) return;
  showModal(`编辑${TYPE_NAMES[type]}`, buildForm(fields, item), async (body) => {
    return safe(() => bridge.apiPost(`novels/${state.currentNovelId}/${collKey(type)}/${id}`, body));
  });
}

function handleDelete(type, id) {
  showConfirm(`确定删除该${TYPE_NAMES[type]}？此操作不可撤销。`, async () => {
    const r = await safe(() => bridge.apiPost(`novels/${state.currentNovelId}/${collKey(type)}/${id}`, { _action: "delete" }));
    if (r !== null) await loadDetail(state.currentNovelId);
  });
}

function editSynopsis() {
  const data = { name: state.novelData.name, synopsis: state.novelData.synopsis };
  showModal("编辑小说信息", buildForm(FIELDS.novel_meta, data), async (body) => {
    return safe(() => bridge.apiPost(`novels/${state.currentNovelId}/update`, body));
  });
}

async function downloadChapter(id) {
  await safe(() => bridge.download(`novels/${state.currentNovelId}/download`, { chapter: id }, "chapter.txt"));
}

async function downloadNovel() {
  await safe(() => bridge.download(`novels/${state.currentNovelId}/download`, {}, `${state.novelData.name}_全本.txt`));
}

async function createNovel() {
  const fh = `<label>小说名称 <span style="color:var(--danger)">*</span><input type="text" name="name" required /></label>`;
  showModal("新建小说", fh, async (body) => {
    if (!body.name.trim()) { toast("名称不能为空"); return null; }
    return safe(() => bridge.apiPost("novels/create", body));
  });
}

async function deleteNovel() {
  showConfirm(`确定删除小说「${state.novelData.name}」？所有数据将被永久删除。`, async () => {
    const r = await safe(() => bridge.apiPost(`novels/${state.currentNovelId}/delete`, {}));
    if (r !== null) showListView();
  });
}

// === Event Binding ===
function bindGlobalEvents() {
  document.getElementById("btn-back").addEventListener("click", showListView);
  document.getElementById("btn-create-novel").addEventListener("click", createNovel);
  document.getElementById("btn-delete-novel").addEventListener("click", deleteNovel);
  document.getElementById("btn-download-novel").addEventListener("click", downloadNovel);

  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
  });

  // Modal save
  document.getElementById("modal-save").addEventListener("click", async () => {
    if (!_onSave) return;
    const formEl = document.getElementById("modal-form");
    const body = {};
    const fd = new FormData(formEl);
    const seen = new Set();
    for (const [k, v] of fd.entries()) {
      if (seen.has(k)) {
        if (!Array.isArray(body[k])) body[k] = [body[k]];
        body[k].push(v);
      } else {
        body[k] = v;
        seen.add(k);
      }
    }
    // Unchecked checkboxes
    formEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      if (!seen.has(cb.name)) body[cb.name] = false;
      else if (cb.name === "is_extra") body[cb.name] = true;
    });
    if ("number" in body && typeof body.number === "string") body.number = parseInt(body.number, 10) || 0;
    formEl.querySelectorAll(".checkbox-group").forEach((g) => {
      const n = g.querySelector("input")?.name;
      if (n && body[n] && !Array.isArray(body[n])) body[n] = [body[n]];
    });

    const result = await _onSave(body);
    if (result !== null && result !== undefined) {
      hideModal();
      if (state.currentNovelId) await loadDetail(state.currentNovelId);
      else await loadNovelList();
    }
  });

  document.getElementById("modal-cancel").addEventListener("click", hideModal);
  document.getElementById("confirm-cancel").addEventListener("click", () => {
    document.getElementById("confirm-overlay").classList.add("hidden");
  });

  // Novel search
  document.getElementById("search-novels").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    renderList(state.allNovels.filter((n) => (n.name || "").toLowerCase().includes(q)));
  });

  // Delegated panel actions
  document.querySelector(".tab-panels").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const { action, type, id } = btn.dataset;
    if (action === "create") createForm(type);
    else if (action === "edit") editForm(type, id);
    else if (action === "delete") handleDelete(type, id);
    else if (action === "edit-synopsis") editSynopsis();
    else if (action === "download-chapter") downloadChapter(id);
  });

  // Character search
  document.querySelector(".tab-panels").addEventListener("input", (e) => {
    if (e.target.id === "search-characters") {
      const q = e.target.value.toLowerCase();
      const chars = (state.novelData.characters || []).filter((c) => c.name.toLowerCase().includes(q));
      const grid = document.getElementById("characters-grid");
      if (grid) grid.innerHTML = chars.map(charCard).join("");
    }
  });

  // Overlay dismiss
  document.getElementById("modal-overlay").addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") hideModal();
  });
  document.getElementById("confirm-overlay").addEventListener("click", (e) => {
    if (e.target.id === "confirm-overlay") {
      document.getElementById("confirm-overlay").classList.add("hidden");
    }
  });
}

init();
