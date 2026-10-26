const PAGE_SIZE = 8;

const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#device-query");
const searchButton = document.querySelector("#search-button");
const countLabel = document.querySelector("#results-count");
const messageState = document.querySelector("#message-state");
const resultGrid = document.querySelector("#resource-grid");
const kindFilter = document.querySelector("#kind-filter");
const languageFilter = document.querySelector("#language-filter");
const sortFilter = document.querySelector("#sort-filter");
const pagination = document.querySelector("#pagination");
const previousPage = document.querySelector("#previous-page");
const nextPage = document.querySelector("#next-page");
const pageLabel = document.querySelector("#page-label");
const quickLinks = document.querySelector("#quick-links");
const externalSearches = document.querySelector("#external-searches");

let searchResults = [];
let currentPage = 1;
let currentQuery = "";

const kindLabels = {
  guide: "Guia de reparacion",
  wiki: "Manual / referencia",
  question: "Pregunta de la comunidad",
  answer: "Respuesta de la comunidad",
  teardown: "Desmontaje",
  device: "Dispositivo",
};

function setMessage(title, description, isError = false) {
  messageState.hidden = false;
  messageState.classList.toggle("is-error", isError);
  messageState.querySelector("h3").textContent = title;
  messageState.querySelector("p").textContent = description;
  resultGrid.replaceChildren();
  pagination.hidden = true;
}

function formatDate(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp * 1000);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("es", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function createCard(resource) {
  const card = document.createElement("article");
  card.className = "resource-card";

  const imageArea = document.createElement("div");
  imageArea.className = "card-image";
  if (resource.image) {
    const image = document.createElement("img");
    image.src = resource.image;
    image.alt = "";
    image.loading = "lazy";
    imageArea.append(image);
  } else {
    const placeholder = document.createElement("span");
    placeholder.className = "card-image-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    placeholder.textContent = "+";
    imageArea.append(placeholder);
  }

  const content = document.createElement("div");
  content.className = "card-content";

  const metadata = document.createElement("div");
  metadata.className = "card-meta";
  const badge = document.createElement("span");
  badge.className = `kind-badge kind-${resource.kind}`;
  badge.textContent = kindLabels[resource.kind] || "Recurso";
  metadata.append(badge);
  const dateText = formatDate(resource.modified);
  if (dateText) {
    const date = document.createElement("time");
    date.className = "card-date";
    date.dateTime = new Date(resource.modified * 1000).toISOString();
    date.textContent = dateText;
    metadata.append(date);
  }

  const title = document.createElement("h3");
  title.textContent = resource.title;
  const summary = document.createElement("p");
  summary.className = "card-summary";
  summary.textContent = resource.summary || "Abre el recurso para consultar los detalles y pasos de reparacion.";

  const footer = document.createElement("div");
  footer.className = "card-footer";
  const origin = document.createElement("span");
  origin.className = "card-origin";
  const languageName = resource.language
    ? new Intl.DisplayNames(["es"], { type: "language" }).of(resource.language)
    : "Idioma no indicado";
  origin.textContent = `iFixit · ${languageName || resource.language}`;
  const link = document.createElement("a");
  link.className = "card-link";
  link.href = resource.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Ver recurso ↗";

  footer.append(origin, link);
  content.append(metadata, title, summary, footer);
  card.append(imageArea, content);
  return card;
}

function populateFilter(select, values, defaultLabel) {
  const previousValue = select.value;
  select.replaceChildren(new Option(defaultLabel, "all"));
  for (const value of values) {
    const option = new Option(value.label, value.value);
    select.add(option);
  }
  select.disabled = values.length === 0;
  if (values.some((value) => value.value === previousValue)) {
    select.value = previousValue;
  }
}

function updateFilters() {
  const kinds = [...new Set(searchResults.map((resource) => resource.kind))]
    .sort()
    .map((kind) => ({ value: kind, label: kindLabels[kind] || "Recurso" }));
  const languages = [...new Set(searchResults.map((resource) => resource.language).filter(Boolean))]
    .sort()
    .map((language) => {
      const label = new Intl.DisplayNames(["es"], { type: "language" }).of(language);
      return { value: language, label: label || language };
    });
  populateFilter(kindFilter, kinds, "Todos los recursos");
  populateFilter(languageFilter, languages, "Cualquier idioma");
  sortFilter.disabled = searchResults.length === 0;
}

function filteredResults() {
  const filtered = searchResults.filter((resource) => {
    const matchesKind = kindFilter.value === "all" || resource.kind === kindFilter.value;
    const matchesLanguage = languageFilter.value === "all" || resource.language === languageFilter.value;
    return matchesKind && matchesLanguage;
  });

  if (sortFilter.value === "recent") {
    filtered.sort((a, b) => (b.modified || 0) - (a.modified || 0));
  } else if (sortFilter.value === "title") {
    filtered.sort((a, b) => a.title.localeCompare(b.title, "es"));
  }
  return filtered;
}

function renderResults() {
  const filtered = filteredResults();
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  currentPage = Math.min(currentPage, totalPages);
  const start = (currentPage - 1) * PAGE_SIZE;
  const pageResults = filtered.slice(start, start + PAGE_SIZE);

  countLabel.textContent = filtered.length === searchResults.length
    ? `${searchResults.length} recursos encontrados`
    : `${filtered.length} de ${searchResults.length} recursos`;
  messageState.hidden = pageResults.length > 0;
  if (pageResults.length === 0) {
    setMessage("No encontramos recursos con esos filtros.", "Prueba con otro tipo de recurso, idioma o nombre de dispositivo.");
    return;
  }
  messageState.hidden = true;
  resultGrid.replaceChildren(...pageResults.map(createCard));
  pagination.hidden = filtered.length <= PAGE_SIZE;
  pageLabel.textContent = `Pagina ${currentPage} de ${totalPages}`;
  previousPage.disabled = currentPage === 1;
  nextPage.disabled = currentPage === totalPages;
}

function addExternalSearchLinks(query) {
  const encoded = encodeURIComponent(query);
  const destinations = [
    ["Manuales del fabricante", `https://www.google.com/search?q=${encoded}+manual+servicio+fabricante`],
    ["Videos de reparacion", `https://www.youtube.com/results?search_query=${encoded}+repair`],
    ["Guias en la web", `https://www.google.com/search?q=${encoded}+repair+manual+guide`],
  ];
  externalSearches.replaceChildren();
  for (const [label, href] of destinations) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = label;
    externalSearches.append(link);
  }
  quickLinks.hidden = false;
}

async function search(query) {
  currentQuery = query.trim();
  if (currentQuery.length < 2) {
    setMessage("Escribe un poco mas.", "La busqueda necesita al menos 2 caracteres.", true);
    return;
  }
  queryInput.value = currentQuery;
  searchButton.disabled = true;
  searchButton.textContent = "Buscando...";
  countLabel.textContent = "Consultando recursos";
  setMessage("Buscando recursos...", "Estamos consultando la biblioteca publica de iFixit.");
  quickLinks.hidden = true;

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(currentQuery)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "No se pudo completar la busqueda.");

    searchResults = payload.results;
    currentPage = 1;
    kindFilter.value = "all";
    languageFilter.value = "all";
    sortFilter.value = "relevance";
    updateFilters();
    addExternalSearchLinks(currentQuery);
    if (searchResults.length === 0) {
      countLabel.textContent = "Sin resultados";
      setMessage("Aun no encontramos una guia exacta.", "Prueba otro modelo o amplia la busqueda con los enlaces de manuales y videos.");
      return;
    }
    renderResults();
  } catch (error) {
    countLabel.textContent = "No se pudo buscar";
    setMessage("La busqueda no esta disponible ahora.", error.message, true);
  } finally {
    searchButton.disabled = false;
    searchButton.innerHTML = 'Buscar recursos <span>→</span>';
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  search(queryInput.value);
});

document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => search(button.dataset.query));
});

for (const filter of [kindFilter, languageFilter, sortFilter]) {
  filter.addEventListener("change", () => {
    currentPage = 1;
    renderResults();
  });
}

previousPage.addEventListener("click", () => {
  currentPage = Math.max(1, currentPage - 1);
  renderResults();
});
nextPage.addEventListener("click", () => {
  currentPage += 1;
  renderResults();
});
