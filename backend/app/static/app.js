const DEFAULT_NOTEBOOK_ID = "nb-1";
const SETTINGS_STORAGE_KEY = "llmSettings";
const DEFAULT_SETTINGS = {
  temperature: null,
  maxTokens: null,
  retrievalTopK: null,
};
const state = {
  projects: [],
  activeProjectId: DEFAULT_NOTEBOOK_ID,
  projectMessages: {},
  sources: [],
  messages: [],
  indexedAt: null,
  searchResults: [],
  summaryText: "",
  mindmapRoot: null,
  slides: [],
  transcriptSegments: [],
  transcriptText: "",
  settings: { ...DEFAULT_SETTINGS },
  settingsDefaults: {
    maxTokens: null,
    retrievalTopK: null,
  },
};

const el = (id) => document.getElementById(id);

const sourcesList = el("sources-list");
const indexStatus = el("index-status");
const indexProgress = el("index-progress");
const toggleSourcesBtn = el("toggle-sources");
const searchResults = el("search-results");
const summaryOutput = el("summary-output");
const transcriptOutput = el("transcript-output");
const mindmapOutput = el("mindmap-output");
const slidesOutput = el("slides-output");
const chatMessages = el("chat-messages");
const projectSelect = el("project-select");
const projectNewBtn = el("project-new");
const projectDeleteBtn = el("project-delete");
const projectImportBtn = el("project-import");
const projectImportInput = el("project-import-input");
const projectExportBtn = el("project-export");
const audioForm = el("audio-form");
const audioInput = el("audio-input");
const chatUseSourcesToggle = el("chat-use-sources");
const temperatureInput = el("temperature-input");
const maxTokensInput = el("max-tokens-input");
const retrievalTopkInput = el("retrieval-topk-input");
const settingsResetBtn = el("settings-reset");

const getNotebookId = () => state.activeProjectId || DEFAULT_NOTEBOOK_ID;

const buildContext = () =>
  state.sources
    .filter((s) => s.status === "success")
    .map((s) => `Title: ${s.title}\nContent: ${(s.text || "").slice(0, 30000)}`)
    .join("\n\n");

const renderProjects = () => {
  if (!projectSelect) return;
  projectSelect.innerHTML = "";
  state.projects.forEach((project) => {
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = project.name;
    projectSelect.appendChild(option);
  });
  projectSelect.value = getNotebookId();
  if (projectDeleteBtn) {
    const isDefault = getNotebookId() === DEFAULT_NOTEBOOK_ID;
    projectDeleteBtn.disabled = isDefault || state.projects.length <= 1;
  }
};

const clearOutputs = () => {
  searchResults.innerHTML = "";
  summaryOutput.textContent = "";
  transcriptOutput.textContent = "";
  mindmapOutput.textContent = "";
  slidesOutput.textContent = "";
};

const setActiveProject = (projectId, { skipLoad } = {}) => {
  const currentId = getNotebookId();
  if (currentId) {
    state.projectMessages[currentId] = state.messages;
  }
  state.activeProjectId = projectId || DEFAULT_NOTEBOOK_ID;
  state.messages = state.projectMessages[getNotebookId()] || [];
  state.sources = [];
  state.indexedAt = null;
  state.searchResults = [];
  state.summaryText = "";
  state.mindmapRoot = null;
  state.slides = [];
  state.transcriptSegments = [];
  state.transcriptText = "";
  indexStatus.textContent = "";
  finishIndexProgress(false);
  renderSources();
  renderChat();
  clearOutputs();
  renderProjects();
  if (!skipLoad) {
    loadSources();
  }
  localStorage.setItem("activeProjectId", getNotebookId());
};

const loadProjects = async () => {
  try {
    const res = await fetch("/api/projects", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Failed to load projects");
    state.projects = data.projects || [];
    const stored = localStorage.getItem("activeProjectId");
    const defaultId = data.defaultId || DEFAULT_NOTEBOOK_ID;
    if (!state.projects.length) {
      state.projects = [{ id: defaultId, name: "Default" }];
    }
    let nextId = stored && state.projects.some((p) => p.id === stored) ? stored : defaultId;
    if (!state.projects.find((p) => p.id === nextId) && state.projects.length) {
      nextId = state.projects[0].id;
    }
    setActiveProject(nextId, { skipLoad: true });
    loadSources();
  } catch (err) {
    state.projects = [{ id: DEFAULT_NOTEBOOK_ID, name: "Default" }];
    setActiveProject(DEFAULT_NOTEBOOK_ID, { skipLoad: true });
    loadSources();
  }
};

const loadSettings = () => {
  const stored = localStorage.getItem(SETTINGS_STORAGE_KEY);
  if (!stored) return;
  try {
    const parsed = JSON.parse(stored);
    if (parsed && typeof parsed === "object") {
      const parsedTemperature = Number(parsed.temperature);
      const parsedMaxTokens = Number.parseInt(parsed.maxTokens, 10);
      const parsedTopK = Number.parseInt(parsed.retrievalTopK, 10);
      state.settings = {
        ...DEFAULT_SETTINGS,
        temperature: Number.isFinite(parsedTemperature) ? parsedTemperature : null,
        maxTokens: Number.isFinite(parsedMaxTokens) ? parsedMaxTokens : null,
        retrievalTopK: Number.isFinite(parsedTopK) ? parsedTopK : null,
      };
    }
  } catch (err) {
    state.settings = { ...DEFAULT_SETTINGS };
  }
};

const saveSettings = () => {
  localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(state.settings));
};

const parseNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const parseInteger = (value) => {
  const num = Number.parseInt(value, 10);
  return Number.isFinite(num) ? num : null;
};

const buildLlmPayload = () => {
  const payload = {};
  const temperature = Number.isFinite(state.settings.temperature)
    ? state.settings.temperature
    : parseNumber(state.settings.temperature);
  if (Number.isFinite(temperature)) {
    payload.temperature = temperature;
  }
  const maxTokens = Number.isFinite(state.settings.maxTokens)
    ? state.settings.maxTokens
    : parseInteger(state.settings.maxTokens);
  if (Number.isFinite(maxTokens)) {
    payload.maxTokens = maxTokens;
  }
  return payload;
};

const renderSettings = () => {
  if (!temperatureInput && !maxTokensInput && !retrievalTopkInput) return;
  if (temperatureInput) {
    temperatureInput.value = Number.isFinite(state.settings.temperature)
      ? state.settings.temperature
      : "";
    temperatureInput.placeholder = "default";
  }
  if (maxTokensInput) {
    maxTokensInput.value = Number.isFinite(state.settings.maxTokens)
      ? state.settings.maxTokens
      : "";
    maxTokensInput.placeholder = state.settingsDefaults.maxTokens
      ? String(state.settingsDefaults.maxTokens)
      : "default";
  }
  if (retrievalTopkInput) {
    retrievalTopkInput.value = Number.isFinite(state.settings.retrievalTopK)
      ? state.settings.retrievalTopK
      : "";
    retrievalTopkInput.placeholder = state.settingsDefaults.retrievalTopK
      ? String(state.settingsDefaults.retrievalTopK)
      : "default";
  }
};

const fetchSettingsDefaults = async () => {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Failed to load settings");
    state.settingsDefaults = {
      maxTokens: Number.isFinite(data?.llm?.maxTokens) ? data.llm.maxTokens : null,
      retrievalTopK: Number.isFinite(data?.retrieval?.topK) ? data.retrieval.topK : null,
    };
  } catch (err) {
    state.settingsDefaults = {
      maxTokens: null,
      retrievalTopK: null,
    };
  } finally {
    renderSettings();
  }
};

const handleSettingsInput = () => {
  if (temperatureInput) {
    state.settings.temperature = parseNumber(temperatureInput.value);
  }
  if (maxTokensInput) {
    state.settings.maxTokens = parseInteger(maxTokensInput.value);
  }
  if (retrievalTopkInput) {
    state.settings.retrievalTopK = parseInteger(retrievalTopkInput.value);
  }
  saveSettings();
};

const handleSettingsReset = () => {
  state.settings.temperature = null;
  state.settings.maxTokens = null;
  state.settings.retrievalTopK = null;
  saveSettings();
  renderSettings();
};


const handleProjectCreate = async () => {
  const name = window.prompt("Project name?");
  if (name === null) return;
  try {
    const res = await fetch("/api/projects/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Failed to create project");
    const project = data.project;
    if (project) {
      state.projects.push(project);
      setActiveProject(project.id);
    }
  } catch (err) {
    alert(err.message);
  }
};

const handleProjectDelete = async () => {
  const projectId = getNotebookId();
  if (projectId === DEFAULT_NOTEBOOK_ID) {
    alert("Default project cannot be deleted.");
    return;
  }
  if (!window.confirm("Delete this project and all its sources?")) return;
  try {
    const res = await fetch("/api/projects/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Failed to delete project");
    state.projects = state.projects.filter((p) => p.id !== projectId);
    const fallbackId = state.projects.length ? state.projects[0].id : DEFAULT_NOTEBOOK_ID;
    setActiveProject(fallbackId);
  } catch (err) {
    alert(err.message);
  }
};

const handleProjectImport = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", "merge");
    const res = await fetch("/api/projects/import", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Import failed");
    await loadProjects();
    alert(`Imported ${data.projects} project(s).`);
  } catch (err) {
    alert(err.message);
  } finally {
    event.target.value = "";
  }
};

const handleProjectExport = async () => {
  try {
    const res = await fetch("/api/projects/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId: getNotebookId() }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || data.error || "Export failed");
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = /filename="([^"]+)"/.exec(disposition);
    const filename = match ? match[1] : `project-${getNotebookId()}.zip`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    alert(err.message);
  }
};


const renderSources = () => {
  sourcesList.innerHTML = "";
  if (state.sources.length === 0) {
    sourcesList.innerHTML = `<div class="list-item">No sources yet.</div>`;
    return;
  }
  state.sources.forEach((source) => {
    const item = document.createElement("div");
    item.className = "list-item";
    item.innerHTML = `
      <strong>${source.title || source.url}</strong><br />
      <small>${source.url}</small><br />
      <small>Status: ${source.status}</small>
      <div class="actions">
        <button data-id="${source.id}">Remove</button>
      </div>
    `;
    item.querySelector("button").addEventListener("click", () => removeSource(source.id));
    sourcesList.appendChild(item);
  });
};

const renderMarkdown = (input) => {
  const text = String(input ?? "");
  const lines = text.split(/\r?\n/);
  const html = [];
  let inCode = false;
  let listType = null;
  let paragraph = [];

  const inlineFormat = (value) => {
    let output = escapeHtml(value);
    output = output.replace(/`([^`]+)`/g, "<code>$1</code>");
    output = output.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    output = output.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    output = output.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    output = output.replace(/_([^_]+)_/g, "<em>$1</em>");
    output = output.replace(/\n/g, "<br />");
    output = output.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    return output;
  };

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${inlineFormat(paragraph.join("\n"))}</p>`);
    paragraph = [];
  };

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  lines.forEach((rawLine) => {
    const line = rawLine.replace(/\s+$/, "");
    if (line.trim().startsWith("```")) {
      flushParagraph();
      closeList();
      if (!inCode) {
        html.push("<pre><code>");
        inCode = true;
      } else {
        html.push("</code></pre>");
        inCode = false;
      }
      return;
    }

    if (inCode) {
      html.push(escapeHtml(rawLine));
      return;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      closeList();
      return;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      closeList();
      const level = headingMatch[1].length;
      html.push(`<h${level}>${inlineFormat(headingMatch[2])}</h${level}>`);
      return;
    }

    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    const unorderedMatch = trimmed.match(/^[-*•]\s+(.*)$/);
    if (orderedMatch || unorderedMatch) {
      flushParagraph();
      const type = orderedMatch ? "ol" : "ul";
      if (listType && listType !== type) {
        closeList();
      }
      if (!listType) {
        html.push(`<${type}>`);
        listType = type;
      }
      const itemText = orderedMatch ? orderedMatch[2] : unorderedMatch[1];
      html.push(`<li>${inlineFormat(itemText)}</li>`);
      return;
    }

    paragraph.push(trimmed);
  });

  if (inCode) {
    html.push("</code></pre>");
  }
  flushParagraph();
  closeList();
  return html.join("\n");
};

const renderChat = () => {
  chatMessages.innerHTML = "";
  state.messages.forEach((message) => {
    const item = document.createElement("div");
    item.className = `chat-message ${message.role}`;
    item.innerHTML = renderMarkdown(message.content);
    chatMessages.appendChild(item);
  });
  chatMessages.scrollTop = chatMessages.scrollHeight;
};

const toggleSources = () => {
  document.body.classList.toggle("sources-hidden");
  if (toggleSourcesBtn) {
    const hidden = document.body.classList.contains("sources-hidden");
    toggleSourcesBtn.textContent = hidden ? "Show Sources" : "Hide Sources";
  }
};

let indexTimer = null;
let indexPercent = 0;
let isIndexing = false;
let indexPending = false;
let autoIndexTimer = null;

const startIndexProgress = () => {
  clearInterval(indexTimer);
  indexPercent = 8;
  if (indexProgress) {
    indexProgress.style.width = `${indexPercent}%`;
  }
  indexTimer = setInterval(() => {
    if (indexPercent < 90) {
      indexPercent += Math.random() * 4 + 2;
      if (indexPercent > 90) indexPercent = 90;
      if (indexProgress) {
        indexProgress.style.width = `${indexPercent}%`;
      }
    }
  }, 300);
};

const finishIndexProgress = (success) => {
  clearInterval(indexTimer);
  if (!indexProgress) return;
  if (success) {
    indexProgress.style.width = "100%";
    setTimeout(() => {
      indexProgress.style.width = "0%";
    }, 1200);
  } else {
    indexProgress.style.width = "0%";
  }
};

const scheduleAutoIndex = () => {
  clearTimeout(autoIndexTimer);
  autoIndexTimer = setTimeout(() => {
    handleIndex();
  }, 800);
};

const handleUrlSubmit = async (event) => {
  event.preventDefault();
  const url = el("url-input").value.trim();
  if (!url) return;
  const tempId = `source-${Date.now()}`;
  state.sources.push({ id: tempId, url, status: "loading", addedAt: Date.now() });
  renderSources();

  try {
    const res = await fetch("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, notebookId: getNotebookId() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Scrape failed");
    const serverId = data.id || tempId;
    state.sources = state.sources.map((s) =>
      s.id === tempId
        ? {
            ...s,
            id: serverId,
            status: "success",
            title: data.title,
            content: data.content,
            text: data.text,
            url: data.url,
          }
        : s
    );
    state.indexedAt = null;
    finishIndexProgress(false);
    renderSources();
  } catch (err) {
    state.sources = state.sources.map((s) =>
      s.id === tempId ? { ...s, status: "error", error: err.message } : s
    );
    state.indexedAt = null;
    finishIndexProgress(false);
    renderSources();
    alert(err.message);
  }
};

const handleFileSubmit = async (event) => {
  event.preventDefault();
  const fileInput = el("file-input");
  const file = fileInput.files[0];
  if (!file) return;

  const tempId = `file-${Date.now()}`;
  state.sources.push({
    id: tempId,
    url: file.name,
    title: file.name,
    status: "loading",
    addedAt: Date.now(),
  });
  renderSources();

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("notebookId", getNotebookId());
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Upload failed");
    const serverId = data.id || tempId;
    state.sources = state.sources.map((s) =>
      s.id === tempId
        ? {
            ...s,
            id: serverId,
            status: "success",
            title: data.title || file.name,
            content: data.content,
            text: data.text,
          }
        : s
    );
    state.indexedAt = null;
    finishIndexProgress(false);
    renderSources();
    scheduleAutoIndex();
  } catch (err) {
    state.sources = state.sources.map((s) =>
      s.id === tempId ? { ...s, status: "error", error: err.message } : s
    );
    state.indexedAt = null;
    finishIndexProgress(false);
    renderSources();
    alert(err.message);
  } finally {
    fileInput.value = "";
  }
};

const handleAudioSubmit = async (event) => {
  event.preventDefault();
  const file = audioInput.files[0];
  if (!file) return;
  if (transcriptOutput) {
    transcriptOutput.textContent = "Распознавание...";
  }

  const tempId = `audio-${Date.now()}`;
  state.sources.push({
    id: tempId,
    url: file.name,
    title: file.name,
    status: "loading",
    addedAt: Date.now(),
  });
  renderSources();

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("notebookId", getNotebookId());
    const res = await fetch("/api/stt", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Transcription failed");
    const source = data.source || {};
    state.sources = state.sources.map((s) =>
      s.id === tempId
        ? {
            ...s,
            id: source.id || tempId,
            status: "success",
            title: source.title || file.name,
            content: source.content || data.text,
            text: source.text || data.text,
          }
        : s
    );
    state.transcriptSegments = Array.isArray(data.segments) ? data.segments : [];
    state.transcriptText = data.text || "";
    renderTranscript(state.transcriptSegments, state.transcriptText);
    state.indexedAt = null;
    finishIndexProgress(false);
    renderSources();
    scheduleAutoIndex();
  } catch (err) {
    state.sources = state.sources.map((s) =>
      s.id === tempId ? { ...s, status: "error", error: err.message } : s
    );
    state.transcriptSegments = [];
    state.transcriptText = "";
    if (transcriptOutput) {
      transcriptOutput.textContent = "";
    }
    state.indexedAt = null;
    finishIndexProgress(false);
    renderSources();
    alert(err.message);
  } finally {
    audioInput.value = "";
  }
};

const handleIndex = async () => {
  if (state.sources.filter((s) => s.status === "success").length === 0) {
    alert("Add at least one source before indexing.");
    return;
  }
  if (isIndexing) {
    indexPending = true;
    return;
  }
  isIndexing = true;
  indexStatus.textContent = "Indexing...";
  startIndexProgress();
  try {
    const res = await fetch("/api/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notebookId: getNotebookId() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Index failed");
    state.indexedAt = Date.now();
    indexStatus.textContent = `Indexed ${data.chunks} chunks (dim ${data.dimension}).`;
    finishIndexProgress(true);
  } catch (err) {
    indexStatus.textContent = "";
    finishIndexProgress(false);
    alert(err.message);
  } finally {
    isIndexing = false;
    if (indexPending) {
      indexPending = false;
      handleIndex();
    }
  }
};

const handleSearch = async () => {
  const query = el("search-query").value.trim();
  const topK = Number(el("search-topk").value || 5);
  if (!query) return;
  if (!state.indexedAt) {
    alert("Index is not ready. Click Reindex first.");
    return;
  }
  searchResults.innerHTML = "Searching...";
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notebookId: getNotebookId(), query, topK }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Search failed");
    renderSearchResults(data.results || []);
  } catch (err) {
    state.searchResults = [];
    searchResults.innerHTML = "";
    alert(err.message);
  }
};

const renderSearchResults = (results) => {
  state.searchResults = results || [];
  searchResults.innerHTML = "";
  if (!state.searchResults.length) {
    searchResults.innerHTML = `<div class="list-item">No results.</div>`;
    return;
  }
  state.searchResults.forEach((result) => {
    const title = result.source?.title || result.source?.url || "Untitled";
    const sourceUrl = result.source?.url || "";
    const item = document.createElement("div");
    item.className = "list-item";
    const score =
      typeof result.score === "number" ? result.score.toFixed(4) : String(result.score ?? "");
    item.innerHTML = `
      <strong>${title}</strong>
      <small>Score: ${score}</small>
      <p>${escapeHtml(result.text)}</p>
    `;
    if (sourceUrl) {
      const link = document.createElement("small");
      link.textContent = sourceUrl;
      item.appendChild(link);
    }
    searchResults.appendChild(item);
  });
};

const formatTimestamp = (value) => {
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return "00:00";
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const base = `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${base}`;
  }
  return base;
};

const renderTranscript = (segments, text) => {
  if (!transcriptOutput) return;
  transcriptOutput.innerHTML = "";
  const items = Array.isArray(segments) ? segments : [];
  if (!items.length) {
    transcriptOutput.textContent = text || "Нет транскрипции.";
    return;
  }
  items.forEach((segment) => {
    const line = document.createElement("div");
    line.className = "transcript-line";
    const time = document.createElement("span");
    time.className = "transcript-time";
    time.textContent = `${formatTimestamp(segment.start)} - ${formatTimestamp(segment.end)}`;
    const body = document.createElement("span");
    body.className = "transcript-text";
    body.textContent = segment.text || "";
    line.appendChild(time);
    line.appendChild(body);
    transcriptOutput.appendChild(line);
  });
};

const handleSummary = async () => {
  summaryOutput.textContent = "Generating...";
  try {
    const context = buildContext();
    const payload = { context, ...buildLlmPayload() };
    const res = await fetch("/api/summary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Summary failed");
    renderSummary(data.summary || "");
  } catch (err) {
    state.summaryText = "";
    summaryOutput.textContent = "";
    alert(err.message);
  }
};

const handleMindmap = async () => {
  mindmapOutput.textContent = "Generating...";
  try {
    const payload = {
      notebookId: getNotebookId(),
      sources: state.sources,
      ...buildLlmPayload(),
    };
    const res = await fetch("/api/gpt/mindmap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Mindmap failed");
    renderMindmap(data.root);
  } catch (err) {
    state.mindmapRoot = null;
    mindmapOutput.textContent = "";
    alert(err.message);
  }
};

const handleSlides = async () => {
  slidesOutput.textContent = "";
  try {
    const payload = {
      notebookId: getNotebookId(),
      sources: state.sources,
      ...buildLlmPayload(),
    };
    const res = await fetch("/api/gemini/slides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Slides failed");
    renderSlides(data.slides || []);
  } catch (err) {
    state.slides = [];
    slidesOutput.textContent = "";
    alert(err.message);
  }
};


const handleChat = async (event) => {
  event.preventDefault();
  const input = el("chat-input");
  const content = input.value.trim();
  if (!content) return;
  const message = { role: "user", content };
  state.messages.push(message);
  renderChat();
  input.value = "";

  const useSources = chatUseSourcesToggle ? chatUseSourcesToggle.checked : true;
  const context = useSources ? buildContext() : "";
  try {
    const payload = {
      messages: state.messages,
      context,
      notebookId: getNotebookId(),
      useSources,
      ...buildLlmPayload(),
    };
    const retrievalTopK = Number.isFinite(state.settings.retrievalTopK)
      ? state.settings.retrievalTopK
      : parseInteger(state.settings.retrievalTopK);
    if (Number.isFinite(retrievalTopK)) {
      payload.topK = retrievalTopK;
    }
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok || !res.body) {
      throw new Error("Chat failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let assistantText = "";
    const assistant = { role: "assistant", content: "" };
    state.messages.push(assistant);
    renderChat();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      assistantText += decoder.decode(value);
      assistant.content = assistantText;
      renderChat();
    }
  } catch (err) {
    alert(err.message);
  }
};

const handleChatKeydown = (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    el("chat-form").requestSubmit();
  }
};

const handleClear = async () => {
  await fetch("/api/sources/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notebookId: getNotebookId() }),
  }).catch(() => {});

  state.sources = [];
  state.messages = [];
  state.projectMessages[getNotebookId()] = [];
  state.indexedAt = null;
  state.searchResults = [];
  state.summaryText = "";
  state.mindmapRoot = null;
  state.slides = [];
  state.transcriptSegments = [];
  state.transcriptText = "";
  finishIndexProgress(false);
  renderSources();
  renderChat();
  searchResults.innerHTML = "";
  summaryOutput.textContent = "";
  transcriptOutput.textContent = "";
  mindmapOutput.textContent = "";
  slidesOutput.textContent = "";
  indexStatus.textContent = "";
};

const removeSource = async (sourceId) => {
  await fetch("/api/sources/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notebookId: getNotebookId(), sourceId }),
  }).catch(() => {});
  state.sources = state.sources.filter((s) => s.id !== sourceId);
  state.indexedAt = null;
  finishIndexProgress(false);
  renderSources();
};

const loadSources = async () => {
  try {
    const res = await fetch("/api/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notebookId: getNotebookId() }),
    });
    const data = await res.json();
    if (res.ok && data.sources) {
      state.sources = data.sources;
      renderSources();
    }
  } catch (err) {
    renderSources();
  }
};

const renderSummary = (text) => {
  state.summaryText = text || "";
  if (!text) {
    summaryOutput.textContent = "";
    return;
  }
  const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
  const fragments = [];
  let listOpen = false;
  lines.forEach((line) => {
    const isBullet = line.startsWith("-") || line.startsWith("*") || line.startsWith("•");
    if (isBullet) {
      if (!listOpen) {
        fragments.push("<ul>");
        listOpen = true;
      }
      fragments.push(`<li>${escapeHtml(line.replace(/^[-*•]\s*/, ""))}</li>`);
    } else {
      if (listOpen) {
        fragments.push("</ul>");
        listOpen = false;
      }
      fragments.push(`<p>${escapeHtml(line)}</p>`);
    }
  });
  if (listOpen) fragments.push("</ul>");
  summaryOutput.innerHTML = fragments.join("");
};

const renderMindmap = (root) => {
  state.mindmapRoot = root || null;
  mindmapOutput.innerHTML = "";
  if (!root) return;
  const buildNode = (node) => {
    const li = document.createElement("li");
    li.textContent = node.title || "Untitled";
    if (node.children && node.children.length) {
      const ul = document.createElement("ul");
      node.children.forEach((child) => ul.appendChild(buildNode(child)));
      li.appendChild(ul);
    }
    return li;
  };
  const tree = document.createElement("ul");
  tree.appendChild(buildNode(root));
  mindmapOutput.appendChild(tree);
};

const renderSlides = (slides) => {
  state.slides = slides || [];
  slidesOutput.innerHTML = "";
  if (!state.slides.length) {
    slidesOutput.innerHTML = `<div class="list-item">No slides yet.</div>`;
    return;
  }
  state.slides.forEach((slide) => {
    const card = document.createElement("div");
    card.className = "slide-card";
    const title = document.createElement("h4");
    title.textContent = slide.title || "Untitled";
    card.appendChild(title);
    const list = document.createElement("ul");
    (slide.bullets || []).forEach((bullet) => {
      const li = document.createElement("li");
      li.textContent = bullet;
      list.appendChild(li);
    });
    card.appendChild(list);
    slidesOutput.appendChild(card);
  });
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const normalizeText = (value) => String(value ?? "").trim();

const buildMindmapLines = (node, depth = 0) => {
  if (!node) return [];
  const prefix = `${"  ".repeat(depth)}- `;
  const lines = [`${prefix}${normalizeText(node.title || "Untitled")}`];
  (node.children || []).forEach((child) => {
    lines.push(...buildMindmapLines(child, depth + 1));
  });
  return lines;
};

const buildChatMarkdown = () => {
  if (!state.messages.length) return "";
  return state.messages
    .map((message) => {
      const role = message.role === "assistant" ? "Assistant" : "User";
      const content = normalizeText(message.content);
      return `### ${role}\n${content}`;
    })
    .join("\n\n")
    .trim();
};

const buildSearchMarkdown = () => {
  if (!state.searchResults.length) return "";
  return state.searchResults
    .map((result) => {
      const title = normalizeText(result.source?.title || result.source?.url || "Untitled");
      const url = normalizeText(result.source?.url || "");
      const score =
        typeof result.score === "number" ? result.score.toFixed(4) : normalizeText(result.score);
      const text = normalizeText(result.text);
      const meta = [`Score: ${score}`, url ? `Source: ${url}` : ""].filter(Boolean).join("\n");
      return [`### ${title}`, meta, text].filter(Boolean).join("\n");
    })
    .join("\n\n")
    .trim();
};

const buildSlidesMarkdown = () => {
  if (!state.slides.length) return "";
  return state.slides
    .map((slide, index) => {
      const title = normalizeText(slide.title || `Slide ${index + 1}`);
      const bullets = (slide.bullets || []).map((bullet) => `- ${normalizeText(bullet)}`).join("\n");
      return [`## ${title}`, bullets].filter(Boolean).join("\n");
    })
    .join("\n\n")
    .trim();
};

const buildTranscriptMarkdown = () => {
  if (state.transcriptSegments.length) {
    return state.transcriptSegments
      .map((segment) => {
        const start = formatTimestamp(segment.start);
        const end = formatTimestamp(segment.end);
        const text = normalizeText(segment.text);
        return `[${start} - ${end}] ${text}`;
      })
      .join("\n")
      .trim();
  }
  return normalizeText(state.transcriptText);
};

const buildMarkdown = (type) => {
  switch (type) {
    case "chat":
      return buildChatMarkdown();
    case "search":
      return buildSearchMarkdown();
    case "summary":
      return normalizeText(state.summaryText);
    case "transcript":
      return buildTranscriptMarkdown();
    case "mindmap":
      return buildMindmapLines(state.mindmapRoot).join("\n").trim();
    case "slides":
      return buildSlidesMarkdown();
    default:
      return "";
  }
};

const copyFallback = (text) => {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
};

const flashCopyState = (button) => {
  if (!button) return;
  const label = button.textContent;
  button.textContent = "Copied";
  button.disabled = true;
  setTimeout(() => {
    button.textContent = label;
    button.disabled = false;
  }, 1200);
};

const handleCopy = async (type, button) => {
  const text = buildMarkdown(type);
  if (!text) {
    alert("Nothing to copy yet.");
    return;
  }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      copyFallback(text);
    }
    flashCopyState(button);
  } catch (err) {
    alert("Copy failed.");
  }
};

el("url-form").addEventListener("submit", handleUrlSubmit);
el("file-form").addEventListener("submit", handleFileSubmit);
if (audioForm) {
  audioForm.addEventListener("submit", handleAudioSubmit);
}
el("index-btn").addEventListener("click", handleIndex);
el("search-btn").addEventListener("click", handleSearch);
document.querySelectorAll(".summary-btn").forEach((button) => {
  button.addEventListener("click", handleSummary);
});
el("mindmap-btn").addEventListener("click", handleMindmap);
el("slides-btn").addEventListener("click", handleSlides);
el("chat-form").addEventListener("submit", handleChat);
el("chat-input").addEventListener("keydown", handleChatKeydown);
el("clear-btn").addEventListener("click", handleClear);
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", () => handleCopy(button.dataset.copy, button));
});
if (toggleSourcesBtn) {
  toggleSourcesBtn.addEventListener("click", toggleSources);
}
if (projectSelect) {
  projectSelect.addEventListener("change", (event) => {
    setActiveProject(event.target.value);
  });
}
if (projectNewBtn) {
  projectNewBtn.addEventListener("click", handleProjectCreate);
}
if (projectDeleteBtn) {
  projectDeleteBtn.addEventListener("click", handleProjectDelete);
}
if (projectImportBtn && projectImportInput) {
  projectImportBtn.addEventListener("click", () => projectImportInput.click());
  projectImportInput.addEventListener("change", handleProjectImport);
}
if (projectExportBtn) {
  projectExportBtn.addEventListener("click", handleProjectExport);
}
if (temperatureInput) {
  temperatureInput.addEventListener("input", handleSettingsInput);
}
if (maxTokensInput) {
  maxTokensInput.addEventListener("input", handleSettingsInput);
}
if (retrievalTopkInput) {
  retrievalTopkInput.addEventListener("input", handleSettingsInput);
}
if (settingsResetBtn) {
  settingsResetBtn.addEventListener("click", handleSettingsReset);
}

renderSources();
renderChat();
loadSettings();
renderSettings();
fetchSettingsDefaults();
loadProjects();
