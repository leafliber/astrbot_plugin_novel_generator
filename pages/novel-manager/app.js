const bridge = window.AstrBotPluginPage;

let currentNovelId = null;
let currentNovelData = null;
let isLoading = false;

async function init() {
  await bridge.ready();
  loadNovelList();
  bindEvents();
}

function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

function bindEvents() {
  document.getElementById("back-btn").addEventListener("click", () => {
    document.getElementById("novel-detail-section").style.display = "none";
    document.getElementById("novel-list-section").style.display = "block";
    loadNovelList();
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

function setLoading(loading) {
  isLoading = loading;
  document.querySelectorAll(".add-btn, .edit-btn, .delete-btn").forEach((btn) => {
    btn.disabled = loading;
  });
}

function showError(message) {
  const existing = document.querySelector(".error-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "error-toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

async function safeApiCall(fn) {
  if (isLoading) return;
  setLoading(true);
  try {
    return await fn();
  } catch (err) {
    showError(`请求失败：${err.message || "未知错误"}`);
    return null;
  } finally {
    setLoading(false);
  }
}

async function loadNovelList() {
  const novels = await safeApiCall(() => bridge.apiGet("novels"));
  if (novels === null) return;
  const container = document.getElementById("novel-list");
  if (!novels || novels.length === 0) {
    container.innerHTML = '<p class="empty">暂无小说</p>';
    return;
  }
  container.innerHTML = novels
    .map(
      (n) => `
      <div class="novel-card" data-id="${escapeHtml(n.id)}">
        <h3>${escapeHtml(n.name)}</h3>
        <p>章节：${escapeHtml(String(n.chapter_count))} | 角色：${escapeHtml(String(n.character_count))}</p>
        <p class="meta">更新：${escapeHtml(n.updated_at)}</p>
      </div>`
    )
    .join("");
  container.querySelectorAll(".novel-card").forEach((card) => {
    card.addEventListener("click", () => {
      loadNovelDetail(card.dataset.id);
    });
  });
}

async function loadNovelDetail(novelId) {
  const data = await safeApiCall(() => bridge.apiGet(`novels/${novelId}`));
  if (!data) return;
  currentNovelId = novelId;
  currentNovelData = data;
  document.getElementById("novel-title").textContent = currentNovelData.name;
  document.getElementById("novel-list-section").style.display = "none";
  document.getElementById("novel-detail-section").style.display = "block";
  renderCharacters();
  renderRelationships();
  renderEvents();
  renderOutlines();
  renderChapters();
}

function renderCharacters() {
  const panel = document.getElementById("tab-characters");
  const chars = currentNovelData.characters || [];
  let html = '<button class="add-btn" data-type="character">+ 添加角色</button>';
  if (chars.length === 0) {
    html += '<p class="empty">暂无角色</p>';
  } else {
    html += chars
      .map(
        (c) => `
        <div class="item-card">
          <div class="item-header">
            <strong>${escapeHtml(c.name)}</strong>
            <span class="item-id">ID: ${escapeHtml(c.id)}</span>
          </div>
          <div class="item-body">
            ${c.personality ? `<p><b>性格：</b>${escapeHtml(c.personality)}</p>` : ""}
            ${c.appearance ? `<p><b>外貌：</b>${escapeHtml(c.appearance)}</p>` : ""}
            ${c.background ? `<p><b>背景：</b>${escapeHtml(c.background)}</p>` : ""}
            ${c.notes ? `<p><b>备注：</b>${escapeHtml(c.notes)}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="character" data-id="${escapeHtml(c.id)}">编辑</button>
            <button class="delete-btn" data-type="character" data-id="${escapeHtml(c.id)}">删除</button>
          </div>
        </div>`
      )
      .join("");
  }
  panel.innerHTML = html;
  bindCrudEvents(panel, "character");
}

function renderRelationships() {
  const panel = document.getElementById("tab-relationships");
  const rels = currentNovelData.relationships || [];
  let html = '<button class="add-btn" data-type="relationship">+ 添加关系</button>';
  if (rels.length === 0) {
    html += '<p class="empty">暂无关系</p>';
  } else {
    html += rels
      .map(
        (r) => `
        <div class="item-card">
          <div class="item-header">
            <strong>${escapeHtml(r.character_a)} ↔ ${escapeHtml(r.character_b)}</strong>
            <span class="item-id">ID: ${escapeHtml(r.id)}</span>
          </div>
          <div class="item-body">
            <p><b>类型：</b>${escapeHtml(r.relation_type || "未指定")}</p>
            ${r.description ? `<p><b>描述：</b>${escapeHtml(r.description)}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="relationship" data-id="${escapeHtml(r.id)}">编辑</button>
            <button class="delete-btn" data-type="relationship" data-id="${escapeHtml(r.id)}">删除</button>
          </div>
        </div>`
      )
      .join("");
  }
  panel.innerHTML = html;
  bindCrudEvents(panel, "relationship");
}

function renderEvents() {
  const panel = document.getElementById("tab-events");
  const evts = currentNovelData.events || [];
  let html = '<button class="add-btn" data-type="event">+ 添加事件</button>';
  if (evts.length === 0) {
    html += '<p class="empty">暂无事件</p>';
  } else {
    html += evts
      .map(
        (e) => `
        <div class="item-card">
          <div class="item-header">
            <strong>${escapeHtml(e.name)}</strong>
            <span class="item-id">ID: ${escapeHtml(e.id)}</span>
          </div>
          <div class="item-body">
            <p><b>时间线：</b>${escapeHtml(e.timeline_position || "未指定")}</p>
            ${e.description ? `<p><b>描述：</b>${escapeHtml(e.description)}</p>` : ""}
            ${e.involved_characters && e.involved_characters.length > 0 ? `<p><b>涉及角色：</b>${escapeHtml(e.involved_characters.join(", "))}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="event" data-id="${escapeHtml(e.id)}">编辑</button>
            <button class="delete-btn" data-type="event" data-id="${escapeHtml(e.id)}">删除</button>
          </div>
        </div>`
      )
      .join("");
  }
  panel.innerHTML = html;
  bindCrudEvents(panel, "event");
}

function renderOutlines() {
  const panel = document.getElementById("tab-outlines");
  const outs = currentNovelData.outlines || [];
  let html = '<button class="add-btn" data-type="outline">+ 添加大纲</button>';
  if (outs.length === 0) {
    html += '<p class="empty">暂无大纲</p>';
  } else {
    html += outs
      .map(
        (o) => `
        <div class="item-card">
          <div class="item-header">
            <strong>${escapeHtml(o.title)}</strong>
            <span class="item-id">ID: ${escapeHtml(o.id)}</span>
          </div>
          <div class="item-body">
            ${o.chapter_plan ? `<p><b>章节规划：</b>${escapeHtml(o.chapter_plan)}</p>` : ""}
            ${o.plot_direction ? `<p><b>情节走向：</b>${escapeHtml(o.plot_direction)}</p>` : ""}
            ${o.notes ? `<p><b>备注：</b>${escapeHtml(o.notes)}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="outline" data-id="${escapeHtml(o.id)}">编辑</button>
            <button class="delete-btn" data-type="outline" data-id="${escapeHtml(o.id)}">删除</button>
          </div>
        </div>`
      )
      .join("");
  }
  panel.innerHTML = html;
  bindCrudEvents(panel, "outline");
}

function renderChapters() {
  const panel = document.getElementById("tab-chapters");
  const chs = currentNovelData.chapters || [];
  let html = '<button class="add-btn" data-type="chapter">+ 添加章节</button>';
  if (chs.length === 0) {
    html += '<p class="empty">暂无章节</p>';
  } else {
    html += chs
      .map(
        (ch) => `
        <div class="item-card">
          <div class="item-header">
            <strong>第${escapeHtml(String(ch.number))}章 ${escapeHtml(ch.title)}</strong>
            <span class="item-id">ID: ${escapeHtml(ch.id)}</span>
          </div>
          <div class="item-body">
            <pre class="chapter-content">${escapeHtml(ch.content || "（空）")}</pre>
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="chapter" data-id="${escapeHtml(ch.id)}">编辑</button>
            <button class="delete-btn" data-type="chapter" data-id="${escapeHtml(ch.id)}">删除</button>
          </div>
        </div>`
      )
      .join("");
  }
  panel.innerHTML = html;
  bindCrudEvents(panel, "chapter");
}

const FIELDS = {
  character: [
    { key: "name", label: "姓名", type: "text" },
    { key: "personality", label: "性格", type: "textarea" },
    { key: "appearance", label: "外貌", type: "textarea" },
    { key: "background", label: "背景", type: "textarea" },
    { key: "notes", label: "备注", type: "textarea" },
  ],
  relationship: [
    { key: "character_a", label: "角色A", type: "text" },
    { key: "character_b", label: "角色B", type: "text" },
    { key: "relation_type", label: "关系类型", type: "text" },
    { key: "description", label: "描述", type: "textarea" },
  ],
  event: [
    { key: "name", label: "事件名", type: "text" },
    { key: "timeline_position", label: "时间线位置", type: "text" },
    { key: "description", label: "描述", type: "textarea" },
    { key: "involved_characters", label: "涉及角色(逗号分隔)", type: "text" },
  ],
  outline: [
    { key: "title", label: "标题", type: "text" },
    { key: "chapter_plan", label: "章节规划", type: "textarea" },
    { key: "plot_direction", label: "情节走向", type: "textarea" },
    { key: "notes", label: "备注", type: "textarea" },
  ],
  chapter: [
    { key: "number", label: "章节号", type: "number" },
    { key: "title", label: "标题", type: "text" },
    { key: "content", label: "正文", type: "textarea" },
  ],
};

function buildForm(type, data = {}) {
  const fields = FIELDS[type] || [];
  return fields
    .map((f) => {
      const val = data[f.key] !== undefined ? data[f.key] : "";
      const displayVal = f.key === "involved_characters" && Array.isArray(val) ? val.join(", ") : val;
      const safeVal = escapeHtml(String(displayVal));
      if (f.type === "textarea") {
        return `<label>${f.label}<textarea name="${f.key}">${safeVal}</textarea></label>`;
      }
      return `<label>${f.label}<input type="${f.type}" name="${f.key}" value="${safeVal}" /></label>`;
    })
    .join("");
}

function showFormModal(title, formHtml, onSave) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal">
      <h3>${escapeHtml(title)}</h3>
      <form id="modal-form">${formHtml}</form>
      <div class="modal-actions">
        <button id="modal-save">保存</button>
        <button id="modal-cancel">取消</button>
      </div>
    </div>`;
  document.body.appendChild(modal);
  modal.querySelector("#modal-cancel").addEventListener("click", () => modal.remove());
  modal.querySelector("#modal-save").addEventListener("click", async () => {
    const form = modal.querySelector("#modal-form");
    const formData = new FormData(form);
    const body = {};
    formData.forEach((v, k) => {
      if (k === "involved_characters") {
        body[k] = v.split(",").map((s) => s.trim()).filter(Boolean);
      } else if (k === "number") {
        body[k] = parseInt(v, 10) || 0;
      } else {
        body[k] = v;
      }
    });
    const result = await safeApiCall(() => onSave(body));
    if (result !== null) {
      modal.remove();
      await loadNovelDetail(currentNovelId);
    }
  });
}

function bindCrudEvents(panel, type) {
  panel.querySelectorAll(".add-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      showFormModal(`添加${getTypeName(type)}`, buildForm(type), async (body) => {
        return bridge.apiPost(`novels/${currentNovelId}/${type}s`, body);
      });
    });
  });
  panel.querySelectorAll(".edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const itemId = btn.dataset.id;
      const items = currentNovelData[`${type}s`] || [];
      const item = items.find((i) => i.id === itemId);
      if (!item) return;
      showFormModal(`编辑${getTypeName(type)}`, buildForm(type, item), async (body) => {
        return bridge.apiPost(`novels/${currentNovelId}/${type}s/${itemId}`, body);
      });
    });
  });
  panel.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("确定删除？")) return;
      const result = await safeApiCall(() =>
        bridge.apiPost(`novels/${currentNovelId}/${type}s/${btn.dataset.id}`, { _action: "delete" })
      );
      if (result !== null) {
        await loadNovelDetail(currentNovelId);
      }
    });
  });
}

function getTypeName(type) {
  const names = { character: "角色", relationship: "关系", event: "事件", outline: "大纲", chapter: "章节" };
  return names[type] || type;
}

init();
