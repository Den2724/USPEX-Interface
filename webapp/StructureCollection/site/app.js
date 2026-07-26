const listEl = document.getElementById("crystal-list");
const searchEl = document.getElementById("search");
const titleEl = document.getElementById("viewer-title");
const metaEl = document.getElementById("meta");
const viewerEmptyEl = document.getElementById("viewer-empty");
const countEl = document.getElementById("crystal-count");
const cellPrimitiveBtn = document.getElementById("cell-primitive");
const cellConventionalBtn = document.getElementById("cell-conventional");
const fullscreenBtn = document.getElementById("fullscreen-view");
const labelsBtn = document.getElementById("toggle-labels");
const viewerWrapEl = document.getElementById("viewer-wrap");
const libraryBodyEl = document.getElementById("library-body");
const listColumnEl = document.getElementById("list-column");
const splitterEl = document.getElementById("splitter");

const styleButtons = {
  ballstick: document.getElementById("style-sphere"),
  stick: document.getElementById("style-stick"),
  surface: document.getElementById("style-surface"),
};

let viewer = null;
let allCrystals = [];
let activeItem = null;
let currentStyle = "ballstick";
let currentCell = "primitive";
let currentFile = null;
let labelsEnabled = false;

function normalizeName(filename) {
  return filename.replace(/\.cif$/i, "").replace(/_/g, " ");
}

function createListItem(filename) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = "crystal-item";
  item.dataset.filename = filename;

  const name = document.createElement("span");
  name.textContent = normalizeName(filename);
  const file = document.createElement("small");
  file.textContent = filename;

  item.appendChild(name);
  item.appendChild(file);

  item.addEventListener("click", () => selectCrystal(filename, item));

  return item;
}

function renderList(files) {
  listEl.innerHTML = "";
  files.forEach((file) => listEl.appendChild(createListItem(file)));
}

function updateActive(item) {
  if (activeItem) {
    activeItem.classList.remove("active");
  }
  activeItem = item;
  if (activeItem) {
    activeItem.classList.add("active");
  }
}

function updateStyleButtons() {
  Object.entries(styleButtons).forEach(([style, button]) => {
    button.classList.toggle("is-active", currentStyle === style);
  });
}

function updateCellButtons() {
  cellPrimitiveBtn.classList.toggle("is-active", currentCell === "primitive");
  cellConventionalBtn.classList.toggle("is-active", currentCell === "conventional");
}

function updateLabelsButton() {
  labelsBtn.classList.toggle("is-active", labelsEnabled);
}

function applyLabels() {
  if (!viewer) return;
  viewer.removeAllLabels();
  if (!labelsEnabled) return;
  const atoms = viewer.selectedAtoms({});
  atoms.forEach((atom) => {
    viewer.addLabel(atom.elem, {
      position: atom,
      fontSize: 12,
      fontColor: "#1a1a1a",
      backgroundColor: "rgba(255,255,255,0.65)",
    });
  });
}

function setViewerStyle() {
  if (!viewer) return;
  viewer.setStyle({}, {});
  viewer.removeAllSurfaces();

  if (currentStyle === "surface") {
    viewer.setStyle({}, { stick: { radius: 0.2 } });
    viewer.addSurface($3Dmol.SurfaceType.VDW, { opacity: 0.65, color: "#e0643a" });
  } else if (currentStyle === "stick") {
    viewer.setStyle({}, { stick: { radius: 0.25, colorscheme: "Jmol" } });
  } else if (currentStyle === "ballstick") {
    viewer.setStyle({}, { stick: { radius: 0.22, colorscheme: "Jmol" }, sphere: { scale: 0.28, colorscheme: "Jmol" } });
  } else {
    viewer.setStyle({}, { line: { colorscheme: "Jmol" } });
  }

  applyLabels();
  viewer.zoomTo();
  viewer.render();
}

function setupViewer() {
  if (viewer) return viewer;
  viewer = $3Dmol.createViewer("viewer", {
    backgroundColor: "#fdfbf8",
    antialias: true,
  });
  return viewer;
}

async function fetchCif(filename) {
  const primitivePath = `../${encodeURIComponent(filename)}`;
  const conventionalPath = `../conventional/${encodeURIComponent(filename)}`;
  const preferred = currentCell === "conventional" ? conventionalPath : primitivePath;

  let response = await fetch(preferred);
  let usedCell = currentCell;

  if (!response.ok && currentCell === "conventional") {
    response = await fetch(primitivePath);
    usedCell = "primitive";
  }

  if (!response.ok) {
    throw new Error(`Failed to load ${filename}`);
  }

  return { text: await response.text(), usedCell };
}

async function loadCrystal(filename) {
  titleEl.textContent = normalizeName(filename);
  viewerEmptyEl.style.display = "none";
  metaEl.textContent = `Loading ${filename}...`;

  try {
    const { text, usedCell } = await fetchCif(filename);
    setupViewer();
    viewer.clear();
    viewer.removeAllSurfaces();
    viewer.removeAllLabels();
    viewer.addModel(text, "cif");
    viewer.addUnitCell(viewer.getModel(), { color: "#b7b0a8", radius: 0.08 });
    setViewerStyle();

    const label = usedCell === "conventional" ? "Conventional" : "Primitive";
    const fallback = usedCell !== currentCell ? " (fallback)" : "";
    metaEl.textContent = `File: ${filename} | ${label}${fallback}`;
  } catch (err) {
    metaEl.textContent = `Failed to load ${filename}.`;
  }
}

async function selectCrystal(filename, item) {
  updateActive(item);
  currentFile = filename;
  await loadCrystal(filename);
}

function toggleStyle(style) {
  if (currentStyle === style) {
    currentStyle = null;
  } else {
    currentStyle = style;
  }
  updateStyleButtons();
  if (viewer) {
    setViewerStyle();
  }
}

function setCellMode(mode) {
  if (currentCell === mode) return;
  currentCell = mode;
  updateCellButtons();
  if (currentFile) {
    loadCrystal(currentFile);
  }
}

function toggleLabels() {
  labelsEnabled = !labelsEnabled;
  updateLabelsButton();
  if (viewer) {
    applyLabels();
    viewer.render();
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    viewerWrapEl.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}

function bindSplitter() {
  let dragging = false;

  splitterEl.addEventListener("mousedown", (event) => {
    dragging = true;
    document.body.style.cursor = "col-resize";
    event.preventDefault();
  });

  document.addEventListener("mouseup", () => {
    dragging = false;
    document.body.style.cursor = "";
  });

  document.addEventListener("mousemove", (event) => {
    if (!dragging) return;
    const rect = libraryBodyEl.getBoundingClientRect();
    const minWidth = 200;
    const maxWidth = rect.width * 0.55;
    let newWidth = event.clientX - rect.left;
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    listColumnEl.style.width = `${newWidth}px`;
  });
}

function bindControls() {
  styleButtons.ballstick.addEventListener("click", () => toggleStyle("ballstick"));
  styleButtons.stick.addEventListener("click", () => toggleStyle("stick"));
  styleButtons.surface.addEventListener("click", () => toggleStyle("surface"));

  document.getElementById("reset-view").addEventListener("click", () => {
    if (!viewer) return;
    viewer.zoomTo();
    viewer.render();
  });

  fullscreenBtn.addEventListener("click", toggleFullscreen);
  labelsBtn.addEventListener("click", toggleLabels);

  cellPrimitiveBtn.addEventListener("click", () => setCellMode("primitive"));
  cellConventionalBtn.addEventListener("click", () => setCellMode("conventional"));
}

function bindSearch() {
  searchEl.addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    const filtered = allCrystals.filter((file) => file.toLowerCase().includes(query));
    renderList(filtered);
  });
}

async function init() {
  try {
    const response = await fetch("crystals.json");
    allCrystals = await response.json();
    countEl.textContent = allCrystals.length.toString();
    renderList(allCrystals);
  } catch (err) {
    listEl.textContent = "Failed to load crystal list.";
  }

  updateStyleButtons();
  updateCellButtons();
  updateLabelsButton();
  bindSearch();
  bindControls();
  bindSplitter();
}

init();


