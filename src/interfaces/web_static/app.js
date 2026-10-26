const STEP_DETAILS = {
  pm: {
    title: "Plan del proyecto",
    description: "Define el alcance, la arquitectura y el camino de trabajo.",
    icon: "⌖",
    file: "01_plan_tecnico.md",
    prompt: "Revisa el plan del proyecto: valida que la solución, el alcance y la arquitectura encajen con mi idea. Señala decisiones importantes que debería confirmar.",
  },
  backend: {
    title: "Construcción",
    description: "Prepara la lógica, los datos y los servicios del proyecto.",
    icon: "{ }",
    file: "02_backend_code.md",
    prompt: "Revisa el backend: evalúa si el diseño y los ejemplos de código corresponden al lenguaje y al stack solicitados. Señala decisiones, riesgos y mejoras concretas.",
  },
  frontend: {
    title: "Interfaz",
    description: "Diseña las pantallas y la experiencia de uso.",
    icon: "▧",
    file: "03_frontend_code.md",
    prompt: "Revisa la interfaz: evalúa que la experiencia responda a lo que pedí y que el stack elegido tenga sentido. Señala mejoras concretas de uso y accesibilidad.",
  },
  qa: {
    title: "Pruebas",
    description: "Comprueba los casos importantes y busca puntos débiles.",
    icon: "✓",
    file: "04_qa_report.md",
    prompt: "Profundiza en las pruebas: explica qué casos importantes cubren, qué falta probar y qué problemas deberían resolverse antes de continuar.",
  },
  security: {
    title: "Seguridad",
    description: "Analiza riesgos y recomendaciones para el proyecto.",
    icon: "◈",
    file: "05_security_report.md",
    prompt: "Profundiza en la seguridad: prioriza los riesgos reales del proyecto y explica qué debería hacerse para reducirlos.",
  },
  devops: {
    title: "Preparación",
    description: "Reúne las piezas para ejecutar y mantener el proyecto.",
    icon: "↗",
    file: "06_devops_config.md",
    prompt: "Revisa la preparación del proyecto: verifica que las instrucciones de ejecución, despliegue e infraestructura coincidan con las tecnologías elegidas.",
  },
  tech_writer: {
    title: "Guía de uso",
    description: "Deja los siguientes pasos claros y fáciles de seguir.",
    icon: "≡",
    file: "07_documentation.md",
    prompt: "Revisa la guía del proyecto: identifica los pasos poco claros y propone cómo hacer que otra persona pueda empezar sin ayuda técnica.",
  },
  lead: {
    title: "Revisión final",
    description: "Reúne las distintas perspectivas en una revisión enfocada.",
    icon: "✳",
    file: "00_lead_review.md",
    prompt: "Haz una revisión final equilibrada del proyecto: destaca las decisiones más importantes, los riesgos prioritarios y los siguientes pasos.",
  },
};

const state = {
  settings: null,
  sessions: [],
  activeSession: null,
  activeJob: null,
  selectedStep: null,
  pollToken: 0,
  analysisSessionId: null,
  loadedAnalysisSessionId: null,
};
const GLOBE_FRAMES = [
  [
    "      .-~~~~~-.",
    "    .'  .---.  '.",
    "   /  .#######.  \\",
    "  |  |#########|  |",
    "  |  |#########|  |",
    "   \\  '#######'  /",
    "    '.  '---'  .'",
    "      '-.____.-'",
  ],
  [
    "      .-~~~~~-.",
    "    .' .-----. '.",
    "   /  /######\\  \\",
    "  |  |#########| |",
    "  |  |#########| |",
    "   \\  \\######/  /",
    "    '. '-----' .'",
    "      '-.____.-'",
  ],
  [
    "      .-~~~~~-.",
    "    .'  .---.  '.",
    "   /  .#######.  \\",
    "  |  |#########|  |",
    "  |  |#########|  |",
    "   \\  '#######'  /",
    "    '.  '---'  .'",
    "      '-.____.-'",
  ],
  [
    "      .-~~~~~-.",
    "    .'  .---.  '.",
    "   / .-'#####'-. \\",
    "  | |###########| |",
    "  | |###########| |",
    "   \\ '-.#####.-' /",
    "    '.  '---'  .'",
    "      '-.____.-'",
  ],
];
let globeTimer = null;
let globeFrameIndex = 0;

const $ = (selector) => document.querySelector(selector);
const els = {
  welcomeView: $("#welcome-view"),
  projectView: $("#project-view"),
  homeJobNotice: $("#home-job-notice"),
  homeJobMessage: $("#home-job-message"),
  projectForm: $("#project-form"),
  requirement: $("#requirement"),
  existingProjectForm: $("#existing-project-form"),
  existingProjectFolder: $("#existing-project-folder"),
  existingProjectSubmit: $("#existing-project-submit"),
  existingProjectError: $("#existing-project-error"),
  language: $("#language"),
  startProject: $("#start-project"),
  characterCount: $("#character-count"),
  composerError: $("#composer-error"),
  projectList: $("#project-list"),
  recentSection: $("#recent-section"),
  recentProjects: $("#recent-projects"),
  projectCount: $("#project-count"),
  settingsModal: $("#settings-modal"),
  settingsForm: $("#settings-form"),
  provider: $("#provider"),
  apiKey: $("#api-key"),
  keyOptional: $("#key-optional"),
  keyStatus: $("#key-status"),
  settingsError: $("#settings-error"),
  settingsIndicator: $("#settings-indicator"),
  projectTitle: $("#project-title"),
  projectRequirement: $("#project-requirement"),
  continueProject: $("#continue-project"),
  jobBanner: $("#job-banner"),
  jobTitle: $("#job-title"),
  jobMessage: $("#job-message"),
  jobTime: $("#job-time"),
  projectError: $("#project-error"),
  externalProjectSection: $("#external-project-section"),
  externalAnalysis: $("#external-analysis"),
  externalAnalysisError: $("#external-analysis-error"),
  externalMessages: $("#external-messages"),
  externalQuestionForm: $("#external-question-form"),
  externalQuestion: $("#external-question"),
  externalQuestionSubmit: $("#external-question-submit"),
  workflow: $("#workflow"),
  progressLabel: $("#progress-label"),
  progressChip: $("#progress-chip"),
  workflowSummary: $("#workflow-summary"),
  focusTitle: $("#focus-title"),
  focusDescription: $("#focus-description"),
  reviewContext: $("#review-context"),
  reviewButton: $("#review-button"),
  deliverables: $("#deliverables"),
  deliverablesCount: $("#deliverables-count"),
  documentModal: $("#document-modal"),
  documentTitle: $("#document-title"),
  documentContent: $("#document-content"),
  toastRegion: $("#toast-region"),
};

function escapeText(value) {
  return String(value ?? "");
}

async function startExistingProject(event) {
  event.preventDefault();
  if (state.activeJob) {
    showToast("Espera a que termine el proceso actual antes de abrir otro proyecto.");
    return;
  }
  if (!state.settings?.configured) {
    openSettings();
    return;
  }
  const folder = els.existingProjectFolder.value.trim();
  if (!folder) {
    setError(els.existingProjectError, "Indica la ruta de la carpeta que quieres analizar.");
    els.existingProjectFolder.focus();
    return;
  }
  setError(els.existingProjectError, "");
  els.existingProjectSubmit.disabled = true;
  els.existingProjectSubmit.innerHTML = '<span>Abriendo el proyecto…</span><span class="button-arrow">↗</span>';
  try {
    await startJob("/api/external-projects", {
      folder,
      language: els.language.value,
    }, "analysis", els.existingProjectError);
  } finally {
    els.existingProjectSubmit.disabled = false;
    els.existingProjectSubmit.innerHTML = '<span>Abrir y analizar</span><span class="button-arrow">↗</span>';
  }
}

async function askExternalProject(event) {
  event.preventDefault();
  if (!state.activeSession?.is_external || state.activeJob) return;
  const question = els.externalQuestion.value.trim();
  if (question.length < 2) {
    showToast("Escribe qué quieres hacer con el proyecto.", true);
    els.externalQuestion.focus();
    return;
  }
  els.externalQuestionSubmit.disabled = true;
  try {
    const started = await startJob(
      `/api/sessions/${encodeURIComponent(state.activeSession.id)}/ask`,
      { question },
      "ask",
    );
    if (started) els.externalQuestion.disabled = true;
  } finally {
    els.externalQuestionSubmit.disabled = false;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "No se pudo completar la solicitud.");
  return payload;
}

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " is-error" : ""}`;
  toast.textContent = message;
  els.toastRegion.append(toast);
  window.setTimeout(() => toast.remove(), 4300);
}

function setError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

function openSettings() {
  if (state.settings) els.provider.value = state.settings.provider;
  updateKeyHelp();
  els.settingsError.hidden = true;
  els.settingsModal.hidden = false;
  window.setTimeout(() => els.provider.focus(), 50);
}

function closeSettings() {
  if (state.settings?.configured) els.settingsModal.hidden = true;
}

function updateKeyHelp() {
  const isOllama = els.provider.value === "ollama";
  const sameProvider = els.provider.value === state.settings?.provider;
  const keyAlreadyConfigured = sameProvider && state.settings?.api_key_configured;
  els.keyOptional.textContent = isOllama ? "· opcional para Ollama local" : "· se guarda únicamente en este equipo";
  els.apiKey.required = !isOllama && !keyAlreadyConfigured;
  els.apiKey.placeholder = isOllama
    ? "No se necesita para Ollama local"
    : keyAlreadyConfigured
      ? "Ya hay una clave guardada · déjalo vacío para mantenerla"
      : "Pega tu clave de API aquí";
  els.keyStatus.textContent = keyAlreadyConfigured
    ? "Ya hay una clave guardada. Nunca volveremos a mostrarla."
    : !isOllama && state.settings?.api_key_configured
      ? "La clave guardada es de otro proveedor. Pega aquí la clave correspondiente."
    : isOllama
      ? "Asegúrate de tener Ollama instalado y en ejecución."
      : "";
}

function updateSettingsStatus() {
  const configured = Boolean(state.settings?.configured);
  els.settingsIndicator.classList.toggle("is-ready", configured);
  els.settingsIndicator.setAttribute(
    "aria-label",
    configured ? "Proveedor configurado" : "Configuración pendiente",
  );
  if (!configured) {
    els.settingsModal.hidden = false;
    updateKeyHelp();
  }
}

function setActiveNav(index) {
  document.querySelectorAll(".main-nav a").forEach((link, linkIndex) => {
    link.classList.toggle("is-active", linkIndex === index);
  });
}

function completionCount(session) {
  return Object.values(session?.steps || {}).filter((value) => value === "completed").length;
}

function totalCount(session) {
  return Object.keys(session?.steps || {}).length || 7;
}

function isComplete(session) {
  return completionCount(session) === totalCount(session);
}

function projectTitle(requirement) {
  const trimmed = escapeText(requirement).trim();
  return trimmed.length > 74 ? `${trimmed.slice(0, 71)}…` : trimmed;
}

function formatDate(value) {
  if (!value) return "Proyecto guardado";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Proyecto guardado";
  return new Intl.DateTimeFormat("es", { dateStyle: "medium" }).format(date);
}

function renderProjects() {
  els.projectList.replaceChildren();
  if (!state.sessions.length) {
    const empty = document.createElement("p");
    empty.className = "sidebar-empty";
    empty.textContent = "Tus proyectos aparecerán aquí.";
    els.projectList.append(empty);
  } else {
    for (const session of state.sessions.slice(0, 8)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `sidebar-project${state.activeSession?.id === session.id ? " is-selected" : ""}`;
      button.innerHTML = '<span aria-hidden="true">◈</span>';
      const title = document.createElement("span");
      title.className = "sidebar-project-name";
      title.textContent = projectTitle(session.requirement);
      button.append(title);
      button.addEventListener("click", () => selectProject(session.id));
      els.projectList.append(button);
    }
  }

  els.recentProjects.replaceChildren();
  els.recentSection.hidden = state.sessions.length === 0;
  els.projectCount.textContent = `${state.sessions.length} ${state.sessions.length === 1 ? "proyecto" : "proyectos"}`;
  for (const session of state.sessions.slice(0, 3)) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "recent-card";
    const top = document.createElement("span");
    top.className = "recent-card-top";
    const icon = document.createElement("span");
    icon.className = "recent-icon";
    icon.textContent = "◈";
    const progress = document.createElement("span");
    progress.className = "recent-progress";
    progress.textContent = session.is_external
      ? session.analysis_ready ? "Proyecto analizado" : "Lectura inicial"
      : `${completionCount(session)}/${totalCount(session)} etapas`;
    top.append(icon, progress);
    const title = document.createElement("strong");
    title.textContent = projectTitle(session.requirement);
    const date = document.createElement("span");
    date.className = "recent-date";
    date.textContent = formatDate(session.updated_at || session.created_at);
    const bar = document.createElement("span");
    bar.className = "recent-bar";
    const fill = document.createElement("i");
    const progressBand = session.is_external
      ? session.analysis_ready ? 100 : 0
      : Math.round((completionCount(session) / totalCount(session)) * 10) * 10;
    fill.classList.add(`progress-${progressBand}`);
    bar.append(fill);
    card.append(top, title, date, bar);
    card.addEventListener("click", () => selectProject(session.id));
    els.recentProjects.append(card);
  }
}

function renderNode(key, session, interactive = true) {
  const detail = STEP_DETAILS[key];
  const file = session.files?.find((item) => item.name === detail.file);
  let status = key === "lead"
    ? file?.available ? "completed" : "pending"
    : session.steps?.[key] || "pending";
  if (!interactive && status === "running") status = "pending";
  const button = document.createElement("button");
  button.type = "button";
  button.className = `workflow-node is-${status}${state.selectedStep === key ? " is-selected" : ""}`;
  button.dataset.step = key;
  button.setAttribute("aria-pressed", String(state.selectedStep === key));
  button.setAttribute("aria-label", `${detail.title}: ${detail.description}. Seleccionar para enfocar una revisión.`);
  const icon = document.createElement("span");
  icon.className = "node-icon";
  icon.textContent = detail.icon;
  const copy = document.createElement("span");
  copy.className = "node-copy";
  const title = document.createElement("strong");
  title.textContent = detail.title;
  const description = document.createElement("small");
  description.textContent = detail.description;
  copy.append(title, description);
  const nodeStatus = document.createElement("span");
  nodeStatus.className = "node-state";
  nodeStatus.textContent = status === "completed" ? "LISTO" : status === "running" ? "EN MARCHA" : status === "failed" ? "REVISAR" : "POR EMPEZAR";
  button.append(icon, copy, nodeStatus);
  button.addEventListener("click", () => selectStep(key));
  return button;
}

function addConnector(parent, active = false) {
  const connector = document.createElement("span");
  connector.className = `node-connector${active ? " is-active" : ""}`;
  connector.setAttribute("aria-hidden", "true");
  parent.append(connector);
}

function renderWorkflow(session) {
  els.workflow.replaceChildren();
  const steps = session.steps || {};
  const nodes = [
    ["pm"],
    ["backend", "frontend"],
    ["qa"],
    ["security"],
    ["devops"],
    ["tech_writer"],
    ["lead"],
  ];
  let previousReady = false;
  for (const row of nodes) {
    if (row.length === 2) {
      const branch = document.createElement("div");
      branch.className = "branch-connectors";
      const left = document.createElement("span");
      left.className = "branch-connector-left";
      const right = document.createElement("span");
      right.className = "branch-connector-right";
      branch.append(left, right);
      els.workflow.append(branch);
      const parallel = document.createElement("div");
      parallel.className = "parallel-nodes";
      parallel.append(renderNode(row[0], session), renderNode(row[1], session));
      els.workflow.append(parallel);
      const join = document.createElement("div");
      join.className = "parallel-connectors";
      join.setAttribute("aria-hidden", "true");
      join.innerHTML = "<span></span><span></span>";
      els.workflow.append(join);
      previousReady = steps.backend === "completed" && steps.frontend === "completed";
      continue;
    }
    if (row[0] !== "pm") addConnector(els.workflow, previousReady);
    const node = renderNode(row[0], session);
    els.workflow.append(node);
    previousReady = row[0] === "lead"
      ? session.files?.some((file) => file.name === "00_lead_review.md" && file.available)
      : steps[row[0]] === "completed";
  }

  const done = completionCount(session);
  const total = totalCount(session);
  const working = Object.values(steps).includes("running");
  const failed = Object.values(steps).includes("failed");
  els.progressLabel.textContent = working
    ? "El equipo está trabajando"
    : failed
      ? `${done} de ${total} etapas listas · puedes continuar`
      : isComplete(session)
        ? "Proyecto preparado"
        : done
          ? `${done} de ${total} etapas listas`
          : "Esperando al equipo";
  els.progressChip.classList.toggle("is-working", working);
  const available = session.files?.filter((file) => file.available).length || 0;
  els.workflowSummary.textContent = available
    ? `${available} documentos preparados. Selecciona cualquiera para leerlo.`
    : "Los documentos aparecerán al completar cada etapa.";
}

function renderDeliverables(session) {
  const files = session.files || [];
  const available = files.filter((file) => file.available);
  els.deliverablesCount.textContent = `${available.length} ${available.length === 1 ? "disponible" : "disponibles"}`;
  els.deliverables.replaceChildren();
  for (const file of files) {
    const key = Object.keys(STEP_DETAILS).find((step) => STEP_DETAILS[step].file === file.name);
    const detail = STEP_DETAILS[key] || STEP_DETAILS.lead;
    const card = document.createElement(file.available ? "button" : "div");
    card.className = `deliverable-card${file.available ? "" : " is-pending"}`;
    if (file.available) {
      card.type = "button";
      card.addEventListener("click", () => openDocument(file));
    }
    const top = document.createElement("span");
    top.className = "deliverable-top";
    const icon = document.createElement("span");
    icon.className = "deliverable-icon";
    icon.textContent = detail.icon;
    const status = document.createElement("span");
    status.className = `deliverable-status${file.available ? " is-ready" : ""}`;
    status.textContent = file.available ? "LISTO PARA LEER" : "EN PREPARACIÓN";
    top.append(icon, status);
    const label = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = file.label;
    const hint = document.createElement("small");
    hint.textContent = file.available ? "Abrir documento ↗" : "Aparecerá al completar esta etapa";
    label.append(strong, hint);
    card.append(top, label);
    els.deliverables.append(card);
  }
}

function renderProject(session) {
  if (!session) return;
  state.activeSession = session;
  const existingIndex = state.sessions.findIndex((item) => item.id === session.id);
  if (existingIndex === -1) state.sessions.unshift(session);
  else state.sessions[existingIndex] = session;
  els.welcomeView.hidden = true;
  els.projectView.hidden = false;
  $("#breadcrumb-current").textContent = projectTitle(session.requirement);
  els.projectTitle.textContent = projectTitle(session.requirement);
  els.projectRequirement.textContent = session.requirement;
  const isExternal = session.is_external;
  els.continueProject.hidden = isComplete(session) || isExternal;
  els.continueProject.disabled = Boolean(state.activeJob);
  els.externalProjectSection.hidden = !isExternal;
  $("#team-section").hidden = isExternal;
  $(".focus-panel").hidden = isExternal;
  $("#deliverables-section").hidden = isExternal;
  if (isExternal) {
    renderExternalMessages(session);
    if (state.analysisSessionId !== session.id) {
      state.analysisSessionId = session.id;
      state.loadedAnalysisSessionId = null;
      els.externalAnalysis.textContent = "Preparando una lectura del README, manifiestos y estructura del proyecto…";
      setError(els.externalAnalysisError, "");
    }
    els.externalQuestionSubmit.disabled = Boolean(state.activeJob) || !session.analysis_ready;
    els.externalQuestion.disabled = Boolean(state.activeJob) || !session.analysis_ready;
    if (session.analysis_ready && state.loadedAnalysisSessionId !== session.id) {
      state.loadedAnalysisSessionId = session.id;
      els.externalAnalysis.textContent = "Cargando el análisis inicial…";
      api(`/api/sessions/${encodeURIComponent(session.id)}/files/00_project_analysis.md`)
        .then((payload) => {
          if (state.activeSession?.id === session.id) {
            els.externalAnalysis.textContent = payload.content;
            setError(els.externalAnalysisError, "");
          }
        })
        .catch((error) => setError(els.externalAnalysisError, error.message));
    }
  } else {
    state.analysisSessionId = null;
    state.loadedAnalysisSessionId = null;
  }
  const hasDocuments = session.files?.some((file) => file.available);
  els.reviewButton.disabled = !state.settings?.configured || Boolean(state.activeJob) || !state.selectedStep || !hasDocuments;
  renderWorkflow(session);
  renderDeliverables(session);
  if (session.error) {
    setError(els.projectError, "El trabajo se detuvo antes de terminar. El avance guardado sigue disponible; puedes continuar cuando quieras.");
  } else {
    setError(els.projectError, "");
  }
  renderProjects();
}

function renderExternalMessages(session) {
  els.externalMessages.replaceChildren();
  for (const message of session.conversation || []) {
    const bubble = document.createElement("div");
    bubble.className = `external-message${message.role === "user" ? " is-user" : ""}`;
    bubble.textContent = message.content;
    els.externalMessages.append(bubble);
  }
  els.externalMessages.scrollTop = els.externalMessages.scrollHeight;
}

async function selectProject(sessionId) {
  try {
    const payload = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
    state.selectedStep = null;
    resetFocus();
    renderProject(payload.session);
    setActiveNav(1);
    const job = state.activeJob?.session_id === sessionId ? state.activeJob : null;
    els.jobBanner.hidden = !job;
    if (job) setJobBanner(job);
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    showToast(error.message, true);
  }
}

function showHome() {
  state.activeSession = null;
  state.selectedStep = null;
  setActiveNav(0);
  els.projectView.hidden = true;
  els.welcomeView.hidden = false;
  els.jobBanner.hidden = true;
  els.homeJobNotice.hidden = !state.activeJob;
  if (state.activeJob) {
    const title = state.activeJob.kind === "review"
      ? "una revisión enfocada"
      : state.activeJob.kind === "analysis"
        ? "la lectura inicial de tu proyecto"
        : state.activeJob.kind === "ask"
          ? "tu consulta del proyecto"
          : "tu proyecto";
    els.homeJobMessage.textContent = `El equipo sigue trabajando en ${title}. Tu avance se guarda automáticamente.`;
  }
  setError(els.projectError, "");
  $("#breadcrumb-current").textContent = "Inicio";
  renderProjects();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetFocus() {
  els.focusTitle.textContent = "Pon el foco donde más importa.";
  els.focusDescription.textContent = "Selecciona una etapa del diagrama para preparar una revisión con su contexto ya incluido.";
  els.reviewContext.value = "";
  els.reviewContext.disabled = true;
  els.reviewButton.disabled = true;
  els.reviewContext.placeholder = "Selecciona una etapa para preparar el contexto.";
}

async function selectStep(key) {
  const detail = STEP_DETAILS[key];
  if (!detail || !state.activeSession) return;
  state.selectedStep = key;
  renderWorkflow(state.activeSession);
  els.focusTitle.textContent = `Revisar: ${detail.title}`;
  els.focusDescription.textContent = "El contexto de esta etapa se añadirá a la revisión. Puedes ajustarlo antes de enviarlo.";
  els.reviewContext.disabled = false;
  els.reviewContext.value = detail.prompt;
  const hasDocuments = state.activeSession.files?.some((file) => file.available);
  els.reviewButton.disabled = !state.settings?.configured || Boolean(state.activeJob) || !hasDocuments;
  els.reviewButton.innerHTML = 'Revisar esta área <span aria-hidden="true">↗</span>';
  window.setTimeout(() => els.reviewContext.focus({ preventScroll: true }), 0);
}

async function openDocument(file) {
  try {
    const payload = await api(`/api/sessions/${encodeURIComponent(state.activeSession.id)}/files/${encodeURIComponent(file.name)}`);
    els.documentTitle.textContent = payload.label;
    els.documentContent.textContent = payload.content;
    els.documentModal.hidden = false;
    $("#close-document").focus();
  } catch (error) {
    showToast(error.message, true);
  }
}

function setJobBanner(job) {
  const isReview = job.kind === "review";
  els.jobBanner.hidden = false;
  els.jobBanner.classList.toggle("is-failed", job.status === "failed");
  els.jobBanner.classList.toggle("is-complete", job.status === "completed");
  if (job.status === "running") {
    if (globeTimer === null) {
      globeTimer = window.setInterval(() => {
        globeFrameIndex = (globeFrameIndex + 1) % GLOBE_FRAMES.length;
        $("#globe-frame").textContent = GLOBE_FRAMES[globeFrameIndex].join("\n");
      }, 220);
    }
  } else if (globeTimer !== null) {
    window.clearInterval(globeTimer);
    globeTimer = null;
  }
  $("#globe-frame").textContent = GLOBE_FRAMES[globeFrameIndex].join("\n");
  els.jobTitle.textContent = job.status === "failed"
    ? "El equipo necesita que lo intentemos de nuevo"
    : isReview
      ? "El equipo está revisando el área que elegiste"
      : job.kind === "analysis"
        ? "Ckrafter está leyendo tu proyecto"
        : job.kind === "ask"
          ? "Ckrafter está preparando una respuesta con contexto"
      : "El equipo está dando forma a tu proyecto";
  els.jobMessage.textContent = job.status === "failed"
    ? job.message || "El avance anterior se conserva."
    : job.step
      ? `${STEP_DETAILS[job.step]?.title || "El equipo"} está trabajando en tu proyecto.`
      : "Tu avance se guarda automáticamente. Puedes dejar esta página abierta.";
  if (job.created_at) {
    const seconds = Math.max(0, Math.floor((Date.now() - new Date(job.created_at).getTime()) / 1000));
    els.jobTime.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }
  if (job.status === "failed") els.jobBanner.classList.add("is-failed");
}

async function pollJob(jobId, token) {
  while (token === state.pollToken && state.activeJob?.id === jobId) {
    try {
      const payload = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      const job = payload.job;
      state.activeJob = job;
      if (job.session) {
        const existingIndex = state.sessions.findIndex((item) => item.id === job.session.id);
        if (existingIndex === -1) state.sessions.unshift(job.session);
        else state.sessions[existingIndex] = job.session;
        renderProjects();
        if (state.activeSession?.id === job.session_id) {
          renderProject(job.session);
          if (state.selectedStep) renderWorkflow(job.session);
          setJobBanner(job);
        } else {
          els.homeJobNotice.hidden = els.welcomeView.hidden;
        }
      }
      if (job.status !== "running") {
        const isCurrentProject = state.activeSession?.id === job.session_id;
        state.activeJob = null;
        if (isCurrentProject) {
          setJobBanner(job);
          if (job.status === "completed") {
            els.jobTitle.textContent = job.kind === "review"
              ? "La revisión enfocada está lista"
              : job.kind === "analysis"
                ? "Ya leí el proyecto"
                : job.kind === "ask"
                  ? "La respuesta está lista"
                  : "El proyecto ya tomó forma";
            els.jobMessage.textContent = job.kind === "review"
              ? "Abre el entregable de revisión para ver conclusiones y siguientes pasos."
              : job.kind === "analysis"
                ? "Te compartí lo que entendí. ¿Qué quieres hacer ahora?"
                : job.kind === "ask"
                  ? "La conversación conserva el contexto para tu siguiente instrucción."
                  : "Tus documentos ya están apareciendo en el mapa del equipo.";
            if (job.kind === "review") {
              const reviewFile = state.activeSession.files.find((file) => file.name === STEP_DETAILS.lead.file);
              state.selectedStep = null;
              resetFocus();
              if (reviewFile?.available) openDocument(reviewFile);
            } else if (job.kind === "pipeline") {
              showToast("El equipo terminó el proyecto. Ya puedes explorar los documentos.");
            } else if (job.kind === "ask") {
              els.externalQuestion.value = "";
            }
          } else {
            setError(els.projectError, job.message || "El trabajo se interrumpió. El avance anterior se conserva.");
          }
        } else {
          els.homeJobNotice.hidden = true;
          showToast(job.status === "completed"
            ? "El equipo terminó el trabajo en segundo plano. El proyecto ya está actualizado."
            : "El trabajo se interrumpió. El avance guardado sigue disponible.", job.status === "failed");
        }
        state.pollToken += 1;
        if (state.activeSession) renderProject(state.activeSession);
        renderProjects();
        return;
      }
    } catch (error) {
      els.jobMessage.textContent = "Se perdió la conexión con el proceso. Intentando reconectar…";
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1100));
  }
}

async function startJob(url, body, kind, errorTarget = null) {
  try {
    const payload = await api(url, { method: "POST", body: JSON.stringify(body) });
    const job = { ...payload.job, kind };
    state.activeJob = job;
    state.activeSession = payload.session;
    state.sessions = state.sessions.filter((session) => session.id !== job.session_id);
    state.sessions.unshift(state.activeSession);
    renderProject(state.activeSession);
    setError(els.projectError, "");
    setJobBanner(job);
    const token = ++state.pollToken;
    pollJob(job.id, token);
    return true;
  } catch (error) {
    if (errorTarget) setError(errorTarget, error.message);
    else if (error.message.includes("Configura tu proveedor")) openSettings();
    else showToast(error.message, true);
    return false;
  }
}

async function startProject(event) {
  event.preventDefault();
  if (state.activeJob) {
    showToast("El equipo ya está trabajando en otro proyecto. Espera a que termine para empezar uno nuevo.");
    return;
  }
  const requirement = els.requirement.value.trim();
  if (requirement.length < 2) {
    setError(els.composerError, "Cuéntanos un poco más para preparar el proyecto.");
    els.requirement.focus();
    return;
  }
  if (!state.settings?.configured) {
    openSettings();
    return;
  }
  setError(els.composerError, "");
  els.startProject.disabled = true;
  els.startProject.innerHTML = '<span>Preparando tu espacio…</span><span class="button-arrow">↗</span>';
  try {
    const response = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({ requirement, language: els.language.value }),
    });
    const job = { ...response.job, kind: "pipeline" };
    state.activeJob = job;
    state.activeSession = response.session;
    state.sessions = state.sessions.filter((session) => session.id !== job.session_id);
    state.sessions.unshift(state.activeSession);
    renderProject(state.activeSession);
    setJobBanner(job);
    const token = ++state.pollToken;
    pollJob(job.id, token);
  } catch (error) {
    setError(els.composerError, error.message);
  } finally {
    els.startProject.disabled = false;
    els.startProject.innerHTML = '<span>Preparar mi proyecto</span><span class="button-arrow" aria-hidden="true">↗</span>';
  }
}

async function saveSettings(event) {
  event.preventDefault();
  els.settingsError.hidden = true;
  const saveButton = $("#save-settings");
  saveButton.disabled = true;
  saveButton.textContent = "Guardando en este equipo…";
  try {
    const payload = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        provider: els.provider.value,
        api_key: els.apiKey.value,
      }),
    });
    state.settings = payload.settings;
    els.apiKey.value = "";
    updateSettingsStatus();
    closeSettings();
    showToast("Configuración guardada en este equipo.");
    renderProject(state.activeSession);
  } catch (error) {
    setError(els.settingsError, error.message);
  } finally {
    saveButton.disabled = false;
    saveButton.innerHTML = 'Guardar configuración <span aria-hidden="true">↗</span>';
  }
}

async function runFocusedReview() {
  if (!state.activeSession || !state.selectedStep) return;
  if (state.activeJob) {
    showToast("El equipo ya está trabajando. Cuando termine podrás pedir otra revisión.");
    return;
  }
  const focus = els.reviewContext.value.trim();
  if (!focus) {
    showToast("Escribe qué quieres revisar antes de continuar.", true);
    els.reviewContext.focus();
    return;
  }
  await startJob(
    `/api/sessions/${encodeURIComponent(state.activeSession.id)}/review`,
    { focus },
    "review",
  );
}

async function continueProject() {
  if (!state.activeSession || state.activeJob) return;
  await startJob(
    `/api/sessions/${encodeURIComponent(state.activeSession.id)}/continue`,
    {},
    "pipeline",
  );
}

async function bootstrap() {
  try {
    const payload = await api("/api/bootstrap");
    state.settings = payload.settings;
    state.sessions = payload.sessions;
    updateSettingsStatus();
    renderProjects();
    const running = payload.active_jobs?.[0];
    if (running) {
      await selectProject(running.session_id);
      state.activeJob = running;
      setJobBanner(running);
      const token = ++state.pollToken;
      pollJob(running.id, token);
    }
  } catch (error) {
    showToast(`No se pudo conectar con la aplicación local: ${error.message}`, true);
  }
}

els.projectForm.addEventListener("submit", startProject);
els.existingProjectForm.addEventListener("submit", startExistingProject);
els.externalQuestionForm.addEventListener("submit", askExternalProject);
document.querySelectorAll("[data-project-question]").forEach((button) => {
  button.addEventListener("click", () => {
    els.externalQuestion.value = button.dataset.projectQuestion;
    els.externalQuestion.focus();
  });
});
els.requirement.addEventListener("input", () => {
  els.characterCount.textContent = `${els.requirement.value.length} / 5000`;
  if (!els.composerError.hidden) setError(els.composerError, "");
});
document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    els.requirement.value = button.dataset.example;
    els.requirement.dispatchEvent(new Event("input"));
    els.requirement.focus();
  });
});
els.settingsForm.addEventListener("submit", saveSettings);
els.provider.addEventListener("change", updateKeyHelp);
els.reviewButton.addEventListener("click", runFocusedReview);
els.continueProject.addEventListener("click", continueProject);
$("#back-home").addEventListener("click", showHome);
$("#sidebar-new-project").addEventListener("click", showHome);
$("#return-active-project").addEventListener("click", () => {
  if (state.activeJob) selectProject(state.activeJob.session_id);
});
$("#open-settings").addEventListener("click", openSettings);
$("#top-settings").addEventListener("click", openSettings);
$("#close-settings").addEventListener("click", closeSettings);
$("#close-document").addEventListener("click", () => { els.documentModal.hidden = true; });
els.settingsModal.addEventListener("click", (event) => {
  if (event.target === els.settingsModal) closeSettings();
});
els.documentModal.addEventListener("click", (event) => {
  if (event.target === els.documentModal) els.documentModal.hidden = true;
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSettings();
    els.documentModal.hidden = true;
  }
});
document.querySelectorAll(".main-nav a").forEach((link, index) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    if (index === 0 || !state.activeSession) showHome();
    else {
      setActiveNav(index);
      els.welcomeView.hidden = true;
      els.projectView.hidden = false;
      (index === 1 ? $("#team-section") : $("#deliverables-section"))
        .scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});
window.addEventListener("focus", () => {
  if (!state.activeJob && state.activeSession) {
    api(`/api/sessions/${encodeURIComponent(state.activeSession.id)}`)
      .then((payload) => renderProject(payload.session))
      .catch(() => {});
  }
});

bootstrap();
