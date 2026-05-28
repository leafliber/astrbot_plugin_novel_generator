const bridge = window.AstrBotPluginPage;
const PLUGIN_NAME = "astrbot_plugin_novel_generator";

let currentNovelId = null;
let currentNovelData = null;

async function init() {
  await bridge.ready();
  loadNovelList();
  bindEvents();
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

async function loadNovelList() {
  const novels = await bridge.apiGet("novels");
  const container = document.getElementById("novel-list");
  if (!novels || novels.length === 0) {
    container.innerHTML = '<p class="empty">暂无小说</p>';
    return;
  }
  container.innerHTML = novels
    .map(
      (n) => `
      <div class="novel-card" data-id="${n.id}">
        <h3>${n.name}</h3>
        <p>章节：${n.chapter_count} | 角色：${n.character_count}</p>
        <p class="meta">更新：${n.updated_at}</p>
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
  currentNovelId = novelId;
  currentNovelData = await bridge.apiGet(`novels/${novelId}`);
  if (!currentNovelData) return;
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
            <strong>${c.name}</strong>
            <span class="item-id">ID: ${c.id}</span>
          </div>
          <div class="item-body">
            ${c.personality ? `<p><b>性格：</b>${c.personality}</p>` : ""}
            ${c.appearance ? `<p><b>外貌：</b>${c.appearance}</p>` : ""}
            ${c.background ? `<p><b>背景：</b>${c.background}</p>` : ""}
            ${c.notes ? `<p><b>备注：</b>${c.notes}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="character" data-id="${c.id}">编辑</button>
            <button class="delete-btn" data-type="character" data-id="${c.id}">删除</button>
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
            <strong>${r.character_a} ↔ ${r.character_b}</strong>
            <span class="item-id">ID: ${r.id}</span>
          </div>
          <div class="item-body">
            <p><b>类型：</b>${r.relation_type || "未指定"}</p>
            ${r.description ? `<p><b>描述：</b>${r.description}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="relationship" data-id="${r.id}">编辑</button>
            <button class="delete-btn" data-type="relationship" data-id="${r.id}">删除</button>
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
            <strong>${e.name}</strong>
            <span class="item-id">ID: ${e.id}</span>
          </div>
          <div class="item-body">
            <p><b>时间线：</b>${e.timeline_position || "未指定"}</p>
            ${e.description ? `<p><b>描述：</b>${e.description}</p>` : ""}
            ${e.involved_characters && e.involved_characters.length > 0 ? `<p><b>涉及角色：</b>${e.involved_characters.join(", ")}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="event" data-id="${e.id}">编辑</button>
            <button class="delete-btn" data-type="event" data-id="${e.id}">删除</button>
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
            <strong>${o.title}</strong>
            <span class="item-id">ID: ${o.id}</span>
          </div>
          <div class="item-body">
            ${o.chapter_plan ? `<p><b>章节规划：</b>${o.chapter_plan}</p>` : ""}
            ${o.plot_direction ? `<p><b>情节走向：</b>${o.plot_direction}</p>` : ""}
            ${o.notes ? `<p><b>备注：</b>${o.notes}</p>` : ""}
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="outline" data-id="${o.id}">编辑</button>
            <button class="delete-btn" data-type="outline" data-id="${o.id}">删除</button>
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
            <strong>第${ch.number}章 ${ch.title}</strong>
            <span class="item-id">ID: ${ch.id}</span>
          </div>
          <div class="item-body">
            <pre class="chapter-content">${ch.content || "（空）"}</pre>
          </div>
          <div class="item-actions">
            <button class="edit-btn" data-type="chapter" data-id="${ch.id}">编辑</button>
            <button class="delete-btn" data-type="chapter" data-id="${ch.id}">删除</button>
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
      if (f.type === "textarea") {
        return `<label>${f.label}<textarea name="${f.key}">${displayVal}</textarea></label>`;
      }
      return `<label>${f.label}<input type="${f.type}" name="${f.key}" value="${displayVal}" /></label>`;
    })
    .join("");
}

function showFormModal(title, formHtml, onSave) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal">
      <h3>${title}</h3>
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
    await onSave(body);
    modal.remove();
    await loadNovelDetail(currentNovelId);
  });
}

function bindCrudEvents(panel, type) {
  panel.querySelectorAll(".add-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      showFormModal(`添加${getTypeName(type)}`, buildForm(type), async (body) => {
        await bridge.apiPost(`novels/${currentNovelId}/${type}s`, body);
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
        await bridge.apiPost(`novels/${currentNovelId}/${type}s/${itemId}`, body);
      });
    });
  });
  panel.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("确定删除？")) return;
      await bridge.apiPost(`novels/${currentNovelId}/${type}s/${btn.dataset.id}`, { _action: "delete" });
      await loadNovelDetail(currentNovelId);
    });
  });
}

function getTypeName(type) {
  const names = { character: "角色", relationship: "关系", event: "事件", outline: "大纲", chapter: "章节" };
  return names[type] || type;
}

init();
