const fetchOpts = { credentials: "same-origin" };

function setupPasswordToggle(inputId, btnId) {
  const input = document.getElementById(inputId);
  const btn = document.getElementById(btnId);
  if (!input || !btn) return;
  btn.addEventListener("click", () => {
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.textContent = showing ? "👁" : "🙈";
    btn.setAttribute(
      "aria-label",
      showing ? "Mostrar contraseña" : "Ocultar contraseña",
    );
  });
}

setupPasswordToggle("admin-new-pass", "toggle-admin-new-pass");

const ModalUtil = {
  show(title, message, isConfirm = false) {
    return new Promise((resolve) => {
      document.getElementById("modal-title").textContent = title;
      document.getElementById("modal-msg").textContent = message;
      const btnCancel = document.getElementById("modal-btn-cancel");
      const btnConfirm = document.getElementById("modal-btn-confirm");
      const overlay = document.getElementById("modal-overlay");
      btnCancel.classList.toggle("hidden", !isConfirm);
      btnConfirm.onclick = () => {
        overlay.classList.add("hidden");
        resolve(true);
      };
      btnCancel.onclick = () => {
        overlay.classList.add("hidden");
        resolve(false);
      };
      overlay.classList.remove("hidden");
    });
  },
};

window.alert = (msg) => ModalUtil.show("Notificación", msg);

document.getElementById("btn-logout").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST", ...fetchOpts });
  window.location.href = "/";
});

// Student search functionality
const studentSearch = document.getElementById("input-student-search");
const studentDropdown = document.getElementById("student-dropdown");
const studentIdInput = document.getElementById("input-student-id");
let searchTimeout;

const courseSearch = document.getElementById("input-course-search");
const courseDropdown = document.getElementById("course-dropdown");
const courseHiddenId = document.getElementById("input-course-id");
let coursesEmitList = [];
let courseSearchTimeout;

async function searchStudents(query) {
  try {
    const response = await fetch(
      `/api/students?q=${encodeURIComponent(query)}`,
      fetchOpts,
    );
    const data = await response.json();
    if (!response.ok)
      throw new Error(data.error || "Error al buscar estudiantes");
    return data.students || [];
  } catch (error) {
    console.error("Error searching students:", error);
    return [];
  }
}

function renderStudentDropdown(students) {
  studentDropdown.innerHTML = "";
  if (students.length === 0) {
    const noResults = document.createElement("div");
    noResults.className = "p-3 text-gray-500 text-sm";
    noResults.textContent = "No se encontraron estudiantes";
    studentDropdown.appendChild(noResults);
  } else {
    students.forEach((student) => {
      const item = document.createElement("div");
      item.className =
        "p-3 hover:bg-gray-100 cursor-pointer border-b border-gray-100 last:border-b-0";
      item.onclick = () => selectStudent(student);

      const nameDiv = document.createElement("div");
      nameDiv.className = "font-medium text-gray-900";
      nameDiv.textContent = student.name;

      const dniDiv = document.createElement("div");
      dniDiv.className = "text-xs text-gray-500";
      dniDiv.textContent = `DNI: ${student.dni}`;

      item.appendChild(nameDiv);
      item.appendChild(dniDiv);
      studentDropdown.appendChild(item);
    });
  }
  studentDropdown.classList.remove("hidden");
}

function selectStudent(student) {
  studentSearch.value = student.name;
  studentIdInput.value = student.id;
  studentDropdown.classList.add("hidden");
  studentSearch.classList.remove("border-red-300");
  studentSearch.classList.add("border-green-300");
}

studentSearch.addEventListener("input", (e) => {
  const query = e.target.value.trim();
  clearTimeout(searchTimeout);
  if (query.length < 2) {
    studentDropdown.classList.add("hidden");
    studentIdInput.value = "";
    studentSearch.classList.remove("border-green-300", "border-red-300");
    studentSearch.classList.add("border-gray-300");
    return;
  }
  searchTimeout = setTimeout(async () => {
    const students = await searchStudents(query);
    renderStudentDropdown(students);
  }, 300);
});

studentSearch.addEventListener("focus", () => {
  if (studentSearch.value.trim().length >= 2) {
    searchStudents(studentSearch.value.trim()).then(renderStudentDropdown);
  }
});

function renderCourseEmitDropdown(matches) {
  if (!courseDropdown) return;
  courseDropdown.innerHTML = "";
  if (!matches || matches.length === 0) {
    const noResults = document.createElement("div");
    noResults.className = "p-3 text-gray-500 text-sm";
    noResults.textContent =
      coursesEmitList.length === 0
        ? "No hay cursos activos. Agréguelos en Catálogos."
        : "No hay coincidencias. Siga escribiendo o elija de la lista.";
    courseDropdown.appendChild(noResults);
    courseDropdown.classList.remove("hidden");
    return;
  }
  matches.forEach((c) => {
    const item = document.createElement("div");
    item.className =
      "p-3 hover:bg-gray-100 cursor-pointer border-b border-gray-100 last:border-b-0 text-sm";
    item.textContent = c.name;
    item.onclick = () => selectCourseEmit(c);
    courseDropdown.appendChild(item);
  });
  courseDropdown.classList.remove("hidden");
}

function selectCourseEmit(c) {
  if (courseHiddenId) courseHiddenId.value = String(c.id);
  if (courseSearch) courseSearch.value = c.name;
  if (courseDropdown) courseDropdown.classList.add("hidden");
  if (courseSearch) {
    courseSearch.classList.remove("border-red-300");
    courseSearch.classList.add("border-green-300");
  }
  const ta = document.getElementById("input-body");
  if (ta && ta.value.includes("[[CURSO]]")) {
    const nm = String(c.name || "");
    ta.value = ta.value.split("[[CURSO]]").join(nm);
  }
}

function filterCoursesEmitQuery(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return [...coursesEmitList];
  return coursesEmitList.filter((c) => (c.name || "").toLowerCase().includes(q));
}

if (courseSearch && courseDropdown && courseHiddenId) {
  courseSearch.addEventListener("input", () => {
    courseHiddenId.value = "";
    courseSearch.classList.remove("border-green-300");
    const query = courseSearch.value.trim();
    clearTimeout(courseSearchTimeout);
    if (query.length === 0) {
      courseDropdown.classList.add("hidden");
      return;
    }
    courseSearchTimeout = setTimeout(() => {
      renderCourseEmitDropdown(filterCoursesEmitQuery(query));
    }, 200);
  });
  courseSearch.addEventListener("focus", () => {
    const query = courseSearch.value.trim();
    renderCourseEmitDropdown(
      query.length > 0 ? filterCoursesEmitQuery(query) : [...coursesEmitList],
    );
  });
}

function insertBodyMarker(marker) {
  const ta = document.getElementById("input-body");
  if (!ta) return;
  const start = ta.selectionStart ?? ta.value.length;
  const end = ta.selectionEnd ?? ta.value.length;
  const before = ta.value.slice(0, start);
  const after = ta.value.slice(end);
  ta.value = before + marker + after;
  const pos = start + marker.length;
  ta.selectionStart = ta.selectionEnd = pos;
  ta.focus();
}

function insertCursoIntoBody() {
  const hid = document.getElementById("input-course-id");
  const label = courseSearch?.value?.trim();
  if (hid?.value && label) {
    insertBodyMarker(label);
    return;
  }
  insertBodyMarker("[[CURSO]]");
}

document.getElementById("btn-insert-curso-marker")?.addEventListener("click", () => {
  insertCursoIntoBody();
});

document.addEventListener("click", (e) => {
  if (
    studentSearch &&
    studentDropdown &&
    !studentSearch.contains(e.target) &&
    !studentDropdown.contains(e.target)
  ) {
    studentDropdown.classList.add("hidden");
  }
  if (
    courseSearch &&
    courseDropdown &&
    !courseSearch.contains(e.target) &&
    !courseDropdown.contains(e.target)
  ) {
    courseDropdown.classList.add("hidden");
  }
});

const navBtns = document.querySelectorAll(".nav-btn");
const interfaces = document.querySelectorAll(".interface");
const typeSelect = document.getElementById("input-type");
const centroSelect = document.getElementById("input-centro-id");
const firmaDoctorSelect = document.getElementById("input-firma-doctor-id");

navBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetId = btn.dataset.target;
    interfaces.forEach((i) => {
      i.classList.remove("active", "hidden");
      if (i.id !== targetId) i.classList.add("hidden");
    });
    document.getElementById(targetId).classList.add("active");
    navBtns.forEach((b) => {
      b.classList.remove("bg-blue-600", "text-white");
      b.classList.add("bg-gray-200", "text-gray-700");
    });
    btn.classList.remove("bg-gray-200", "text-gray-700");
    btn.classList.add("bg-blue-600", "text-white");

    if (targetId === "manage" || targetId === "dashboard") {
      loadCertificatesData();
      loadStatistics();
      loadDashboardInsights();
    }
    if (targetId === "create") {
      loadCoursesIntoSelect().catch(() => {});
      loadTypesIntoSelect().catch(() => {});
      loadCentrosIntoSelect().catch(() => {});
      loadFirmaDoctoresIntoSelect().catch(() => {});
      loadBodyTextPresetsForEmitForm(null).catch(() => {});
    }
    if (targetId === "catalogs") loadCatalogs();
  });
});

function setMsg(el, ok, text) {
  el.classList.remove("hidden");
  el.className = `text-sm font-medium ${ok ? "text-emerald-700" : "text-red-700"}`;
  el.textContent = text;
}

async function fetchJson(url, opts = {}) {
  const r = await fetch(url, { ...fetchOpts, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Error del servidor");
  return data;
}

const dashboardState = {
  generated: 0,
  verifications: 0,
  valid: 0,
  invalid: 0,
  avgGen: 0,
  avgVer: 0,
};

const dashboardCharts = {
  drill: null,
};
let selectedDashboardMetric = null;
const dashboardInsights = {
  monthly: [],
  status: { total: 0, active: 0, revoked: 0 },
  topCourses: [],
  topTypes: [],
};

function toFiniteNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function setBarWidth(id, pct, className) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  if (className) el.className = `h-full rounded-full ${className}`;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function pctChange(current, previous) {
  if (!previous) return current > 0 ? 100 : 0;
  return ((current - previous) / previous) * 100;
}

function renderChartKpis(items) {
  const wrap = document.getElementById("dashboard-chart-kpis");
  if (!wrap) return;
  wrap.replaceChildren();
  (items || []).forEach((txt) => {
    const item = document.createElement("div");
    item.className = "p-3 rounded-lg bg-gray-50 border border-gray-100 text-xs text-gray-700";
    item.textContent = txt;
    wrap.appendChild(item);
  });
}

function getDrillChartConfig(metricKey) {
  const validRate =
    dashboardState.verifications > 0
      ? (dashboardState.valid / dashboardState.verifications) * 100
      : 0;
  const invalidRate = Math.max(0, 100 - validRate);
  const monthly = dashboardInsights.monthly || [];
  const monthLabels = monthly.map((m) => m.label);
  const emittedSeries = monthly.map((m) => toFiniteNumber(m.emitted));
  const activeSeries = monthly.map((m) => toFiniteNumber(m.active));
  const revokedSeries = monthly.map((m) => toFiniteNumber(m.revoked));
  const avgGenSeries = monthly.map((m) => toFiniteNumber(m.avgGen));
  const avgVerSeries = monthly.map((m) => toFiniteNumber(m.avgVer));
  const lastEmitted = emittedSeries.length ? emittedSeries[emittedSeries.length - 1] : 0;
  const prevEmitted = emittedSeries.length > 1 ? emittedSeries[emittedSeries.length - 2] : 0;
  const trend = pctChange(lastEmitted, prevEmitted);

  if (metricKey === "generated") {
    return {
      title: "Certificados emitidos",
      subtitle: "Comparativa mensual de emisión y estado (últimos meses).",
      kpis: [
        `Total histórico: ${dashboardState.generated}`,
        `Último periodo: ${lastEmitted}`,
        `Variación vs anterior: ${trend >= 0 ? "+" : ""}${trend.toFixed(1)}%`,
      ],
      chart: {
        type: "bar",
        data: {
          labels: monthLabels.length ? monthLabels : ["Sin datos"],
          datasets: [
            {
              label: "Emitidos",
              data: monthLabels.length ? emittedSeries : [0],
              backgroundColor: "#3b82f6",
              borderRadius: 8,
            },
            {
              label: "Activos",
              data: monthLabels.length ? activeSeries : [0],
              backgroundColor: "#10b981",
              borderRadius: 8,
            },
            {
              label: "Revocados",
              data: monthLabels.length ? revokedSeries : [0],
              backgroundColor: "#ef4444",
              borderRadius: 8,
            },
          ],
        },
      },
    };
  }
  if (metricKey === "verifications") {
    return {
      title: "Total verificaciones",
      subtitle: "Volumen y calidad de verificaciones en una sola vista.",
      kpis: [
        `Verificaciones totales: ${dashboardState.verifications}`,
        `Correctas: ${dashboardState.valid}`,
        `Incorrectas: ${dashboardState.invalid}`,
      ],
      chart: {
        type: "bar",
        data: {
          labels: ["Totales", "Correctas", "Incorrectas"],
          datasets: [
            {
              label: "Cantidad",
              data: [dashboardState.verifications, dashboardState.valid, dashboardState.invalid],
              backgroundColor: ["#8b5cf6", "#10b981", "#ef4444"],
              borderRadius: 8,
            },
            {
              type: "line",
              label: "Porcentaje",
              data: [100, validRate, invalidRate],
              borderColor: "#334155",
              backgroundColor: "#334155",
              yAxisID: "y1",
              tension: 0.3,
            },
          ],
        },
      },
    };
  }
  if (metricKey === "valid") {
    return {
      title: "Validaciones correctas",
      subtitle: `Comparativa entre calidad de verificación y estado del inventario.`,
      kpis: [
        `Tasa de acierto: ${validRate.toFixed(1)}%`,
        `Certificados activos: ${dashboardInsights.status.active || 0}`,
        `Certificados revocados: ${dashboardInsights.status.revoked || 0}`,
      ],
      chart: {
        type: "polarArea",
        data: {
          labels: ["Correctas", "Incorrectas", "Activos", "Revocados"],
          datasets: [
            {
              data: [
                dashboardState.valid,
                dashboardState.invalid,
                toFiniteNumber(dashboardInsights.status.active),
                toFiniteNumber(dashboardInsights.status.revoked),
              ],
              backgroundColor: ["#10b981", "#ef4444", "#22c55e", "#f97316"],
              borderWidth: 0,
            },
          ],
        },
      },
    };
  }
  if (metricKey === "avgGen") {
    return {
      title: "Tiempo de generación de certificados",
      subtitle: "Evolución mensual de tiempos promedio vs metas sugeridas.",
      kpis: [
        `Promedio actual TGC: ${dashboardState.avgGen.toFixed(4)} s`,
        `Promedio actual TV: ${dashboardState.avgVer.toFixed(4)} s`,
        "Meta sugerida TGC <= 2.00 s / TV <= 1.50 s",
      ],
      chart: {
        type: "line",
        data: {
          labels: monthLabels.length ? monthLabels : ["Sin datos"],
          datasets: [
            {
              label: "TGC promedio",
              data: monthLabels.length ? avgGenSeries : [dashboardState.avgGen],
              borderColor: "#3b82f6",
              backgroundColor: "rgba(59,130,246,0.15)",
              fill: true,
              tension: 0.35,
            },
            {
              label: "TV promedio",
              data: monthLabels.length ? avgVerSeries : [dashboardState.avgVer],
              borderColor: "#8b5cf6",
              backgroundColor: "rgba(139,92,246,0.10)",
              fill: true,
              tension: 0.35,
            },
            {
              label: "Meta TGC (2.00 s)",
              data: (monthLabels.length ? monthLabels : ["Sin datos"]).map(() => 2),
              borderColor: "#94a3b8",
              borderDash: [6, 6],
              pointRadius: 0,
            },
            {
              label: "Meta TV (1.50 s)",
              data: (monthLabels.length ? monthLabels : ["Sin datos"]).map(() => 1.5),
              borderColor: "#cbd5e1",
              borderDash: [4, 4],
              pointRadius: 0,
            },
          ],
        },
      },
    };
  }
  const topCourses = (dashboardInsights.topCourses || []).slice(0, 4);
  const topTypes = (dashboardInsights.topTypes || []).slice(0, 4);
  const labels = [
    ...topCourses.map((x) => `Curso: ${x.name}`),
    ...topTypes.map((x) => `Tipo: ${x.name}`),
  ];
  const values = [
    ...topCourses.map((x) => toFiniteNumber(x.count)),
    ...topTypes.map((x) => toFiniteNumber(x.count)),
  ];
  return {
    title: "Tiempo de verificación de certificados (TV)",
    subtitle: "Contexto operativo: carga por cursos y tipos más usados.",
    kpis: [
      `TV global: ${dashboardState.avgVer.toFixed(4)} s`,
      topCourses[0] ? `Curso líder: ${topCourses[0].name} (${topCourses[0].count})` : "Sin cursos suficientes",
      topTypes[0] ? `Tipo líder: ${topTypes[0].name} (${topTypes[0].count})` : "Sin tipos suficientes",
    ],
    chart: {
      type: "bar",
      data: {
        labels: labels.length ? labels : ["Sin datos"],
        datasets: [
          {
            label: "Certificados",
            data: labels.length ? values : [0],
            backgroundColor: labels.map((_, idx) => (idx < topCourses.length ? "#3b82f6" : "#8b5cf6")),
            borderRadius: 8,
          },
        ],
      },
    },
  };
}

function setDashboardCardActive(metricKey) {
  document.querySelectorAll(".dashboard-chart-card").forEach((card) => {
    const isActive = card.dataset.chartKey === metricKey;
    card.classList.toggle("ring-2", isActive);
    card.classList.toggle("ring-blue-300", isActive);
  });
}

function renderDrillChart(metricKey) {
  if (typeof Chart === "undefined") return;
  const canvas = document.getElementById("dashboard-drill-chart");
  const panel = document.getElementById("dashboard-chart-panel");
  if (!canvas || !panel) return;
  const config = getDrillChartConfig(metricKey);
  setText("dashboard-chart-title", config.title);
  setText("dashboard-chart-subtitle", config.subtitle);
  renderChartKpis(config.kpis || []);
  panel.classList.remove("hidden");
  setDashboardCardActive(metricKey);

  if (dashboardCharts.drill) {
    dashboardCharts.drill.destroy();
  }
  dashboardCharts.drill = new Chart(canvas, {
    type: config.chart.type,
    data: config.chart.data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: config.chart.type === "doughnut" ? "bottom" : "top" },
      },
      scales:
        config.chart.type === "bar"
          ? (() => {
              const hasPctAxis = (config.chart.data.datasets || []).some(
                (d) => d.yAxisID === "y1",
              );
              if (!hasPctAxis) {
                return { y: { beginAtZero: true, ticks: { precision: 0 } } };
              }
              return {
                y: { beginAtZero: true, ticks: { precision: 0 } },
                y1: {
                  beginAtZero: true,
                  position: "right",
                  grid: { drawOnChartArea: false },
                  ticks: { callback: (v) => `${v}%` },
                },
              };
            })()
          : config.chart.type === "line"
            ? { y: { beginAtZero: true } }
          : undefined,
    },
  });
}

function setupDashboardCardInteractions() {
  document.querySelectorAll(".dashboard-chart-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectedDashboardMetric = card.dataset.chartKey || "generated";
      renderDrillChart(selectedDashboardMetric);
    });
  });
  const btnHide = document.getElementById("dashboard-chart-hide");
  const panel = document.getElementById("dashboard-chart-panel");
  if (btnHide && panel) {
    btnHide.addEventListener("click", () => {
      panel.classList.add("hidden");
      setDashboardCardActive("");
      renderChartKpis([]);
      selectedDashboardMetric = null;
    });
  }
}

function refreshDashboardVisuals() {
  const maxTop = Math.max(
    dashboardState.generated,
    dashboardState.verifications,
    dashboardState.valid,
    1,
  );
  const validRate =
    dashboardState.verifications > 0
      ? (dashboardState.valid / dashboardState.verifications) * 100
      : 0;

  setText("dash-generated", dashboardState.generated);
  setText("dash-verifications", dashboardState.verifications);
  setText("dash-valid", dashboardState.valid);
  setText("rep-avg-gen", `${dashboardState.avgGen.toFixed(4)} s`);
  setText("rep-avg-ver", `${dashboardState.avgVer.toFixed(4)} s`);

  setBarWidth("chart-generated-bar", (dashboardState.generated / maxTop) * 100);
  setBarWidth(
    "chart-verifications-bar",
    (dashboardState.verifications / maxTop) * 100,
  );
  setBarWidth("chart-valid-bar", validRate);
  setText(
    "chart-generated-note",
    `${dashboardState.generated} registros emitidos hasta ahora`,
  );
  setText(
    "chart-verifications-note",
    `${dashboardState.verifications} verificaciones acumuladas`,
  );
  setText("chart-valid-note", `Tasa de acierto: ${validRate.toFixed(1)}%`);

  const genPct = Math.min((dashboardState.avgGen / 2) * 100, 100);
  const verPct = Math.min((dashboardState.avgVer / 1.5) * 100, 100);
  const genColor =
    dashboardState.avgGen <= 1 ? "bg-emerald-500" : dashboardState.avgGen <= 2 ? "bg-amber-500" : "bg-red-500";
  const verColor =
    dashboardState.avgVer <= 0.8 ? "bg-emerald-500" : dashboardState.avgVer <= 1.5 ? "bg-amber-500" : "bg-red-500";
  setBarWidth("chart-avg-gen-bar", genPct, genColor);
  setBarWidth("chart-avg-ver-bar", verPct, verColor);
  setText("chart-avg-gen-note", `Meta sugerida: <= 2.00 s (actual ${dashboardState.avgGen.toFixed(4)} s)`);
  setText("chart-avg-ver-note", `Meta sugerida: <= 1.50 s (actual ${dashboardState.avgVer.toFixed(4)} s)`);

  if (selectedDashboardMetric) {
    renderDrillChart(selectedDashboardMetric);
  }
}

async function loadCoursesIntoSelect() {
  const searchEl = document.getElementById("input-course-search");
  const hiddenEl = document.getElementById("input-course-id");
  const dropdownEl = document.getElementById("course-dropdown");
  if (!searchEl || !hiddenEl) return;
  hiddenEl.value = "";
  searchEl.value = "";
  searchEl.classList.remove("border-green-300", "border-red-300");
  searchEl.classList.add("border-gray-300");
  if (dropdownEl) {
    dropdownEl.classList.add("hidden");
    dropdownEl.innerHTML = "";
  }
  searchEl.placeholder = "Cargando cursos…";
  try {
    const data = await fetchJson("/api/admin/courses");
    coursesEmitList = (data.courses || [])
      .filter((c) => c.active)
      .map((c) => ({ id: c.id, name: String(c.name || "") }));
  } catch {
    coursesEmitList = [];
  }
  searchEl.placeholder = coursesEmitList.length
    ? "Escriba para buscar y elija un curso de la lista…"
    : "No hay cursos activos. Agréguelos en Catálogos.";
}

async function loadTypesIntoSelect() {
  if (!typeSelect) return;
  typeSelect.innerHTML = `<option value="">Cargando tipos...</option>`;
  const data = await fetchJson("/api/admin/credential-types");
  const rows = (data.types || []).filter((t) => t.active);
  typeSelect.innerHTML = `<option value="">Seleccione un tipo...</option>`;
  rows.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = String(t.id);
    opt.textContent = t.name;
    typeSelect.appendChild(opt);
  });
}

async function loadCentrosIntoSelect() {
  if (!centroSelect) return;
  centroSelect.innerHTML = `<option value="">Cargando centros...</option>`;
  const data = await fetchJson("/api/admin/centros-educativos");
  const rows = (data.centers || []).filter((c) => c.active);
  centroSelect.innerHTML = `<option value="">Seleccione un centro...</option>`;
  rows.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = String(c.id);
    opt.textContent = c.name;
    centroSelect.appendChild(opt);
  });
}

async function loadFirmaDoctoresIntoSelect() {
  if (!firmaDoctorSelect) return;
  firmaDoctorSelect.innerHTML = `<option value="">Cargando directores...</option>`;
  const data = await fetchJson("/api/admin/firma-doctores");
  const rows = (data.doctors || []).filter((d) => d.active);
  firmaDoctorSelect.innerHTML = `<option value="">Seleccione director...</option>`;
  rows.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = String(d.id);
    opt.textContent = d.nombres || `ID ${d.id}`;
    firmaDoctorSelect.appendChild(opt);
  });
}

async function loadBodyTextPresetsForEmitForm(presetsFromCatalog) {
  const sel = document.getElementById("select-body-preset");
  if (!sel) return;
  let list = presetsFromCatalog;
  if (list == null) {
    try {
      const data = await fetchJson("/api/admin/body-text-presets");
      list = data.presets || [];
    } catch {
      sel.innerHTML = '<option value="">— Textos guardados no disponibles —</option>';
      return;
    }
  }
  const active = (list || []).filter((p) => p.active);
  window.__bodyPresetTextById = {};
  active.forEach((p) => {
    window.__bodyPresetTextById[p.id] = p.text || "";
  });
  const prev = sel.value;
  sel.innerHTML = '<option value="">— Escribir manualmente —</option>';
  active.forEach((p) => {
    const o = document.createElement("option");
    o.value = String(p.id);
    o.textContent = p.name;
    sel.appendChild(o);
  });
  if (prev && window.__bodyPresetTextById[Number(prev)] !== undefined) {
    sel.value = prev;
  }
}

async function loadCatalogs() {
  const coursesBody = document.getElementById("table-courses");
  const typesBody = document.getElementById("table-ctypes");
  const centrosBody = document.getElementById("table-centros");
  if (!coursesBody || !typesBody) {
    await loadCoursesIntoSelect().catch(() => {});
    await loadTypesIntoSelect().catch(() => {});
    await loadCentrosIntoSelect().catch(() => {});
    await loadFirmaDoctoresIntoSelect().catch(() => {});
    await loadBodyTextPresetsForEmitForm(null).catch(() => {});
    return;
  }
  const courses = (await fetchJson("/api/admin/courses")).courses || [];
  const types = (await fetchJson("/api/admin/credential-types")).types || [];
  let bodyPresets = [];
  try {
    bodyPresets = (await fetchJson("/api/admin/body-text-presets")).presets || [];
  } catch {
    bodyPresets = [];
  }
  const centros = (await fetchJson("/api/admin/centros-educativos")).centers || [];
  const doctors = (await fetchJson("/api/admin/firma-doctores")).doctors || [];

  coursesBody.replaceChildren();
  courses.forEach((c) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="px-4 py-3 text-sm font-semibold">${c.name}</td>
      <td class="px-4 py-3 text-center text-sm">${c.active ? "Sí" : "No"}</td>
      <td class="px-4 py-3 text-center text-sm"></td>
    `;
    const actionsTd = tr.lastElementChild;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = c.active
      ? "px-3 py-1 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-700"
      : "px-3 py-1 rounded-lg font-semibold text-white bg-green-600 hover:bg-green-700";
    btn.textContent = c.active ? "Deshabilitar" : "Habilitar";
    btn.addEventListener("click", () =>
      changeCatalogStatus({
        kind: "course",
        id: c.id,
        name: c.name,
        currentActive: c.active,
      }),
    );
    actionsTd.appendChild(btn);
    coursesBody.appendChild(tr);
  });

  typesBody.replaceChildren();
  types.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="px-4 py-3 text-sm font-semibold">${t.name}</td>
      <td class="px-4 py-3 text-center text-sm">${t.active ? "Sí" : "No"}</td>
      <td class="px-4 py-3 text-center text-sm"></td>
    `;
    const actionsTd = tr.lastElementChild;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = t.active
      ? "px-3 py-1 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-700"
      : "px-3 py-1 rounded-lg font-semibold text-white bg-green-600 hover:bg-green-700";
    btn.textContent = t.active ? "Deshabilitar" : "Habilitar";
    btn.addEventListener("click", () =>
      changeCatalogStatus({
        kind: "type",
        id: t.id,
        name: t.name,
        currentActive: t.active,
      }),
    );
    actionsTd.appendChild(btn);
    typesBody.appendChild(tr);
  });

  const presetsBody = document.getElementById("table-body-text-presets");
  if (presetsBody) {
    presetsBody.replaceChildren();
    bodyPresets.forEach((p) => {
      const tr = document.createElement("tr");
      const tdName = document.createElement("td");
      tdName.className = "px-4 py-3 text-sm font-semibold";
      tdName.textContent = p.name || "";
      const tdPrev = document.createElement("td");
      tdPrev.className = "px-4 py-3 text-xs text-gray-600";
      const full = p.text || "";
      tdPrev.textContent = full.length > 80 ? `${full.slice(0, 80)}…` : full;
      const tdAct = document.createElement("td");
      tdAct.className = "px-4 py-3 text-center text-sm";
      tdAct.textContent = p.active ? "Sí" : "No";
      const actionsTd = document.createElement("td");
      actionsTd.className = "px-4 py-3 text-center text-sm";
      tr.appendChild(tdName);
      tr.appendChild(tdPrev);
      tr.appendChild(tdAct);
      tr.appendChild(actionsTd);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = p.active
        ? "px-3 py-1 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-700"
        : "px-3 py-1 rounded-lg font-semibold text-white bg-green-600 hover:bg-green-700";
      btn.textContent = p.active ? "Deshabilitar" : "Habilitar";
      btn.addEventListener("click", () =>
        changeCatalogStatus({
          kind: "body_preset",
          id: p.id,
          name: p.name,
          currentActive: p.active,
        }),
      );
      actionsTd.appendChild(btn);
      presetsBody.appendChild(tr);
    });
  }


  await loadBodyTextPresetsForEmitForm(bodyPresets);

  if (centrosBody) {
    centrosBody.replaceChildren();
    centros.forEach((c) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-4 py-3 text-sm font-semibold">${c.name}</td>
        <td class="px-4 py-3 text-center text-sm">${c.hasLogoDerecho ? "Sí" : "No"}</td>
        <td class="px-4 py-3 text-center text-sm">${c.active ? "Sí" : "No"}</td>
        <td class="px-4 py-3 text-center text-sm"></td>
      `;
      const actionsTd = tr.lastElementChild;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = c.active
        ? "px-3 py-1 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-700"
        : "px-3 py-1 rounded-lg font-semibold text-white bg-green-600 hover:bg-green-700";
      btn.textContent = c.active ? "Deshabilitar" : "Habilitar";
      btn.addEventListener("click", () =>
        changeCatalogStatus({
          kind: "centro",
          id: c.id,
          name: c.name,
          currentActive: c.active,
        }),
      );
      actionsTd.appendChild(btn);
      centrosBody.appendChild(tr);
    });
  }

  const doctorsBody = document.getElementById("table-firma-doctores");
  if (doctorsBody) {
    doctorsBody.replaceChildren();
    doctors.forEach((d) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-4 py-3 text-sm font-semibold">${d.nombres || ""}</td>
        <td class="px-4 py-3 text-center text-sm">${d.genero || ""}</td>
        <td class="px-4 py-3 text-center text-sm">${d.hasFirma ? "Sí" : "No"}</td>
        <td class="px-4 py-3 text-center text-sm">${d.active ? "Sí" : "No"}</td>
        <td class="px-4 py-3 text-center text-sm"></td>
      `;
      const actionsTd = tr.lastElementChild;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = d.active
        ? "px-3 py-1 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-700"
        : "px-3 py-1 rounded-lg font-semibold text-white bg-green-600 hover:bg-green-700";
      btn.textContent = d.active ? "Deshabilitar" : "Habilitar";
      btn.addEventListener("click", () =>
        changeCatalogStatus({
          kind: "doctor",
          id: d.id,
          name: d.nombres || String(d.id),
          currentActive: d.active,
        }),
      );
      actionsTd.appendChild(btn);
      doctorsBody.appendChild(tr);
    });
  }

  await loadCoursesIntoSelect();
  await loadTypesIntoSelect();
  await loadCentrosIntoSelect();
  await loadFirmaDoctoresIntoSelect();
}

async function changeCatalogStatus({ kind, id, name, currentActive }) {
  const nextActive = !currentActive;
  const entityLabel =
    kind === "course"
      ? "curso"
      : kind === "centro"
        ? "centro educativo"
        : kind === "doctor"
          ? "director"
          : kind === "body_preset"
            ? "texto guardado"
            : "tipo de credencial";
  const actionLabel = nextActive ? "habilitar" : "deshabilitar";
  const endpoint =
    kind === "course"
      ? `/api/admin/courses/${id}/active`
      : kind === "centro"
        ? `/api/admin/centros-educativos/${id}/active`
        : kind === "doctor"
          ? `/api/admin/firma-doctores/${id}/active`
          : kind === "body_preset"
            ? `/api/admin/body-text-presets/${id}/active`
            : `/api/admin/credential-types/${id}/active`;
  const msgEl = document.getElementById(
    kind === "course"
      ? "courses-msg"
      : kind === "centro"
        ? "centros-msg"
        : kind === "doctor"
          ? "firma-doctor-msg"
          : kind === "body_preset"
            ? "body-presets-msg"
            : "ctypes-msg",
  );

  const accepted = await ModalUtil.show(
    "Confirmar cambio",
    `¿Desea ${actionLabel} "${name}"?`,
    true,
  );
  if (!accepted) return;

  if (msgEl) msgEl.classList.add("hidden");
  try {
    await fetchJson(endpoint, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: nextActive }),
    });
    if (msgEl) {
      setMsg(
        msgEl,
        true,
        `Estado del ${entityLabel} actualizado a ${nextActive ? "Sí" : "No"}.`,
      );
    }
    await loadCatalogs();
  } catch (err) {
    if (msgEl) {
      setMsg(msgEl, false, err.message || "No se pudo actualizar el estado.");
    }
  }
}

function showCreateResultSuccess(resDiv, certId, timeSec, pdfOk, mailSent) {
  resDiv.replaceChildren();
  const p = document.createElement("p");
  p.className = "mb-2";
  p.append("Certificado ", document.createElement("strong"));
  p.querySelector("strong").textContent = certId;
  p.append(" firmado y registrado.");
  resDiv.appendChild(p);
  const sub = document.createElement("div");
  sub.className = "text-sm font-semibold text-emerald-900 space-y-2";
  sub.appendChild(document.createElement("p")).textContent =
    `TGC: ${Number(timeSec).toFixed(4)} s`;
  if (pdfOk) {
    const a = document.createElement("a");
    a.href = `/api/certificates/${encodeURIComponent(certId)}/pdf`;
    a.className = "inline-block mt-2 text-blue-700 underline font-bold";
    a.textContent = "Descargar PDF del diploma";
    a.setAttribute("download", "");
    sub.appendChild(a);
  } else {
    const w = document.createElement("p");
    w.className = "text-amber-800";
    w.textContent =
      "El PDF no se pudo generar; revise la consola del servidor.";
    sub.appendChild(w);
  }

  const mailP = document.createElement("p");
  if (mailSent) {
    mailP.className = "text-emerald-700 mt-2";
    mailP.innerHTML =
      '<i class="fas fa-envelope"></i> Correo de notificación enviado al alumno.';
  } else {
    mailP.className = "text-amber-700 mt-2";
    mailP.innerHTML =
      '<i class="fas fa-exclamation-triangle"></i> El correo no se pudo enviar (verifique configuración SMTP).';
  }
  sub.appendChild(mailP);

  resDiv.appendChild(sub);
}

function showCreateResultError(resDiv, message) {
  resDiv.replaceChildren();
  const s = document.createElement("strong");
  s.textContent = "Error: ";
  resDiv.appendChild(s);
  resDiv.appendChild(document.createTextNode(message));
}

document.getElementById("form-create").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btnSpinner = document.getElementById("spinner-create");
  const btnText = document.getElementById("text-create");
  const resDiv = document.getElementById("result-create");
  const btnSubmit = document.getElementById("btn-create");
  btnSpinner.classList.remove("hidden");
  btnText.classList.add("hidden");
  btnSubmit.disabled = true;

  const bodyTxt = document.getElementById("input-body").value.trim();
  const studentId = document.getElementById("input-student-id").value;
  const studentName = document
    .getElementById("input-student-search")
    .value.trim();

  if (!studentId || !studentName) {
    const resDiv = document.getElementById("result-create");
    resDiv.classList.remove("hidden", "bg-emerald-100", "text-emerald-800");
    resDiv.classList.add("bg-red-100", "text-red-800");
    showCreateResultError(resDiv, "Debe seleccionar un estudiante de la lista");
    btnSpinner.classList.add("hidden");
    btnText.classList.remove("hidden");
    btnSubmit.disabled = false;
    return;
  }

  const courseId = document.getElementById("input-course-id").value;
  if (!courseId) {
    const resDiv = document.getElementById("result-create");
    resDiv.classList.remove("hidden", "bg-emerald-100", "text-emerald-800");
    resDiv.classList.add("bg-red-100", "text-red-800");
    showCreateResultError(
      resDiv,
      "Debe seleccionar un curso de la lista (escriba para filtrar y pulse una opción).",
    );
    btnSpinner.classList.add("hidden");
    btnText.classList.remove("hidden");
    btnSubmit.disabled = false;
    const cs = document.getElementById("input-course-search");
    if (cs) cs.classList.add("border-red-300");
    return;
  }

  const payload = {
    name: studentName,
    date: document.getElementById("input-date").value,
    recipient_user_id: studentId,
  };
  payload.course_id = document.getElementById("input-course-id").value;
  payload.type_id = document.getElementById("input-type").value;
  payload.centro_educativo_id = document.getElementById("input-centro-id").value;
  payload.firma_doctor_id = document.getElementById("input-firma-doctor-id").value;
  if (bodyTxt) payload.body_text = bodyTxt;
  const presetSel = document.getElementById("select-body-preset");
  if (presetSel && presetSel.value) {
    payload.body_text_catalog_id = presetSel.value;
  }

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      ...fetchOpts,
      body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));
    resDiv.classList.remove(
      "hidden",
      "bg-emerald-100",
      "text-emerald-800",
      "bg-red-100",
      "text-red-800",
    );
    if (!response.ok) {
      resDiv.classList.add("bg-red-100", "text-red-800");
      showCreateResultError(resDiv, result.error || "Error del servidor");
      return;
    }
    resDiv.classList.add("bg-emerald-100", "text-emerald-800");
    const pdfOk = Boolean(result.cert?.hasPdf);
    const mailSent = Boolean(result.cert?.mailSent);
    showCreateResultSuccess(
      resDiv,
      result.cert.id,
      result.time,
      pdfOk,
      mailSent,
    );
    e.target.reset();
    document.getElementById("input-student-search").value = "";
    document.getElementById("input-student-id").value = "";
    document
      .getElementById("input-student-search")
      .classList.remove("border-green-300", "border-red-300");
    document
      .getElementById("input-student-search")
      .classList.add("border-gray-300");
    loadCoursesIntoSelect().catch(() => {});
  } catch (err) {
    console.error(err);
    resDiv.classList.remove("hidden");
    resDiv.classList.add("bg-red-100", "text-red-800");
    showCreateResultError(resDiv, "No se pudo conectar al servidor.");
  } finally {
    btnSpinner.classList.add("hidden");
    btnText.classList.remove("hidden");
    btnSubmit.disabled = false;
  }
});

function appendCertRow(tbody, cert) {
  const isActive = cert.status === "Activo";
  const tr = document.createElement("tr");
  const tdId = document.createElement("td");
  tdId.className = "px-6 py-4";
  const d1 = document.createElement("div");
  d1.className = "text-sm font-bold text-gray-900";
  d1.textContent = cert.id;
  tdId.appendChild(d1);

  const tdData = document.createElement("td");
  tdData.className = "px-6 py-4";
  const n = document.createElement("div");
  n.className = "text-sm text-gray-900";
  n.textContent = cert.name;
  const c = document.createElement("div");
  c.className = "text-xs text-gray-500";
  c.textContent = cert.course;
  tdData.appendChild(n);
  tdData.appendChild(c);

  const tdMetrics = document.createElement("td");
  tdMetrics.className = "px-6 py-4 text-center";
  const tgcDiv = document.createElement("div");
  tgcDiv.className = "text-xs text-blue-600 font-semibold";
  tgcDiv.textContent = `TGC: ${Number(cert.tgc || 0).toFixed(4)}s`;
  const tvDiv = document.createElement("div");
  tvDiv.className = "text-xs text-purple-600 font-semibold";
  tvDiv.textContent = `TV: ${Number(cert.tv || 0).toFixed(4)}s`;
  const valDiv = document.createElement("div");
  valDiv.className = `text-[10px] uppercase font-bold ${cert.isValid ? "text-emerald-600" : "text-gray-400"}`;
  valDiv.textContent = cert.isValid ? "Validado" : "Pendiente/Inval";
  tdMetrics.appendChild(tgcDiv);
  tdMetrics.appendChild(tvDiv);
  tdMetrics.appendChild(valDiv);

  const tdPdf = document.createElement("td");
  tdPdf.className = "px-6 py-4 text-center";
  if (cert.hasPdf) {
    const a = document.createElement("a");
    a.href = `/api/certificates/${encodeURIComponent(cert.id)}/pdf`;
    a.className = "text-blue-600 font-bold underline text-sm";
    a.textContent = "Descargar";
    a.setAttribute("download", "");
    tdPdf.appendChild(a);
  } else {
    const sp = document.createElement("span");
    sp.className = "text-xs text-gray-400";
    sp.textContent = "—";
    tdPdf.appendChild(sp);
  }

  const tdState = document.createElement("td");
  tdState.className = "px-6 py-4 text-center";
  const span = document.createElement("span");
  span.className = `px-3 py-1 inline-flex text-xs font-bold rounded-full ${
    isActive ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
  }`;
  span.textContent = cert.status;
  tdState.appendChild(span);

  const tdAct = document.createElement("td");
  tdAct.className = "px-6 py-4 text-right";
  const b = document.createElement("button");
  b.type = "button";
  b.className = `font-bold text-sm ${isActive ? "text-rose-600" : "text-emerald-600"}`;
  b.textContent = isActive ? "Revocar" : "Activar";
  b.addEventListener("click", () => toggleStatus(cert.id));
  tdAct.appendChild(b);

  tr.appendChild(tdId);
  tr.appendChild(tdData);
  tr.appendChild(tdMetrics);
  tr.appendChild(tdPdf);
  tr.appendChild(tdState);
  tr.appendChild(tdAct);
  tbody.appendChild(tr);
}

// --- Certificados: búsqueda, paginación y renderizado ---
let certPage = 1;
let certPageSize = 5;
let certSearch = "";
let certTotalPages = 1;

async function loadCertificatesData() {
  const tbody = document.getElementById("table-body-certs");
  const emptyMsg = document.getElementById("empty-certs");
  const search = certSearch;
  const page = certPage;
  const page_size = certPageSize;
  try {
    const url = `/api/certificates?q=${encodeURIComponent(search)}&page=${page}&page_size=${page_size}`;
    const response = await fetch(url, fetchOpts);
    if (response.status === 401 || response.status === 403) {
      window.location.href = "/";
      return;
    }
    if (!response.ok) throw new Error();
    const data = await response.json();
    const certs = data.certificates || [];
    certTotalPages = data.total_pages || 1;
    tbody.replaceChildren();
    dashboardState.generated = toFiniteNumber(data.total || 0);
    refreshDashboardVisuals();
    if (certs.length === 0) {
      emptyMsg.classList.remove("hidden");
    } else {
      emptyMsg.classList.add("hidden");
      certs.forEach((cert) => appendCertRow(tbody, cert));
    }
    renderCertPagination();
  } catch {
    tbody.innerHTML =
      '<tr><td colspan="5" class="p-4 text-center text-red-500 font-bold">Error al cargar certificados.</td></tr>';
    emptyMsg.classList.add("hidden");
    renderCertPagination();
  }
}

function renderCertPagination() {
  const pag = document.getElementById("cert-pagination");
  pag.innerHTML = "";
  if (certTotalPages <= 1) return;
  const prev = document.createElement("button");
  prev.textContent = "←";
  prev.className = "px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 font-bold";
  prev.disabled = certPage <= 1;
  prev.onclick = () => {
    if (certPage > 1) {
      certPage--;
      loadCertificatesData();
    }
  };
  pag.appendChild(prev);
  // Page numbers (show max 5)
  let start = Math.max(1, certPage - 2);
  let end = Math.min(certTotalPages, start + 4);
  if (end - start < 4) start = Math.max(1, end - 4);
  for (let i = start; i <= end; i++) {
    const btn = document.createElement("button");
    btn.textContent = i;
    btn.className = `px-3 py-1 rounded font-bold ${i === certPage ? "bg-blue-600 text-white" : "bg-gray-200 hover:bg-gray-300"}`;
    btn.disabled = i === certPage;
    btn.onclick = () => {
      certPage = i;
      loadCertificatesData();
    };
    pag.appendChild(btn);
  }
  const next = document.createElement("button");
  next.textContent = "→";
  next.className = "px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 font-bold";
  next.disabled = certPage >= certTotalPages;
  next.onclick = () => {
    if (certPage < certTotalPages) {
      certPage++;
      loadCertificatesData();
    }
  };
  pag.appendChild(next);
}

document.getElementById("cert-search").addEventListener("input", (e) => {
  certSearch = e.target.value.trim();
  certPage = 1;
  loadCertificatesData();
});
document.getElementById("cert-page-size").addEventListener("change", (e) => {
  certPageSize = parseInt(e.target.value, 10) || 5;
  certPage = 1;
  loadCertificatesData();
});

document
  .getElementById("form-new-admin")
  .addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("admin-msg");
    msg.classList.add("hidden");
    const r = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      ...fetchOpts,
      body: JSON.stringify({
        username: document.getElementById("admin-new-user").value.trim(),
        email: document.getElementById("admin-new-email").value.trim(),
        password: document.getElementById("admin-new-pass").value,
      }),
    });
    const data = await r.json().catch(() => ({}));
    msg.classList.remove("hidden");
    if (!r.ok) {
      msg.className = "mt-4 text-sm font-medium text-red-700";
      msg.textContent = data.error || "Error";
      return;
    }
    msg.className = "mt-4 text-sm font-medium text-emerald-700";
    msg.textContent = data.mailSent
      ? "Administrador creado y credenciales enviadas por correo."
      : "Administrador creado. No se pudo enviar el correo de credenciales.";
    e.target.reset();
  });

function loadStatistics() {
  fetch("/api/stats", fetchOpts)
    .then((r) => (r.ok ? r.json() : {}))
    .then((stats) => {
      dashboardState.verifications = toFiniteNumber(stats.verCount || 0);
      dashboardState.valid = toFiniteNumber(stats.validCount || 0);
      dashboardState.invalid = toFiniteNumber(stats.invalidCount || 0);
      dashboardState.avgGen = toFiniteNumber(stats.avgGenTime || 0);
      dashboardState.avgVer = toFiniteNumber(stats.avgVerTime || 0);
      if (!dashboardState.generated) {
        dashboardState.generated = toFiniteNumber(stats.genCount || 0);
      }
      refreshDashboardVisuals();
    })
    .catch(() => {});
}

function loadDashboardInsights() {
  fetch("/api/dashboard/insights", fetchOpts)
    .then((r) => (r.ok ? r.json() : {}))
    .then((data) => {
      dashboardInsights.monthly = Array.isArray(data.monthly) ? data.monthly : [];
      dashboardInsights.status = data.status || { total: 0, active: 0, revoked: 0 };
      dashboardInsights.topCourses = Array.isArray(data.topCourses) ? data.topCourses : [];
      dashboardInsights.topTypes = Array.isArray(data.topTypes) ? data.topTypes : [];
      if (selectedDashboardMetric) {
        renderDrillChart(selectedDashboardMetric);
      }
    })
    .catch(() => {});
}

document.addEventListener("DOMContentLoaded", () => {
  setupDashboardCardInteractions();
  refreshDashboardVisuals();
  loadCertificatesData();
  loadStatistics();
  loadDashboardInsights();
  loadCatalogs().catch(() => {});
});

// --- Catálogos: alta de cursos y tipos ---
const courseForm = document.getElementById("form-new-course");
if (courseForm) {
  courseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("courses-msg");
    msg.classList.add("hidden");
    try {
      await fetchJson("/api/admin/courses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: document.getElementById("course-name").value.trim(),
        }),
      });
      setMsg(msg, true, "Curso agregado correctamente.");
      e.target.reset();
      await loadCatalogs();
    } catch (err) {
      setMsg(msg, false, err.message || "Error");
    }
  });
}

const ctypeForm = document.getElementById("form-new-ctype");
if (ctypeForm) {
  ctypeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("ctypes-msg");
    msg.classList.add("hidden");
    try {
      await fetchJson("/api/admin/credential-types", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: document.getElementById("ctype-name").value.trim(),
        }),
      });
      setMsg(msg, true, "Tipo de credencial agregado correctamente.");
      e.target.reset();
      await loadCatalogs();
    } catch (err) {
      setMsg(msg, false, err.message || "Error");
    }
  });
}

const bodyPresetForm = document.getElementById("form-new-body-preset");
if (bodyPresetForm) {
  bodyPresetForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("body-presets-msg");
    msg.classList.add("hidden");
    const name = document.getElementById("body-preset-name").value.trim();
    const text = document.getElementById("body-preset-text").value.trim();
    try {
      await fetchJson("/api/admin/body-text-presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, text }),
      });
      setMsg(msg, true, "Texto guardado correctamente.");
      e.target.reset();
      await loadCatalogs();
    } catch (err) {
      setMsg(msg, false, err.message || "Error");
    }
  });
}

const selectBodyPreset = document.getElementById("select-body-preset");
if (selectBodyPreset) {
  selectBodyPreset.addEventListener("change", () => {
    const id = selectBodyPreset.value;
    const ta = document.getElementById("input-body");
    if (!ta || !id) return;
    const m = window.__bodyPresetTextById || {};
    if (m[Number(id)] !== undefined) ta.value = m[Number(id)];
  });
}

const centroForm = document.getElementById("form-new-centro");
if (centroForm) {
  centroForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("centros-msg");
    msg.classList.add("hidden");
    const payload = {
      name: document.getElementById("centro-name").value.trim(),
      estado: document.getElementById("centro-estado").value,
    };
    const fileDer = document.getElementById("centro-logo-derecho");
    const fileD = fileDer && fileDer.files && fileDer.files[0];
    if (fileD) {
      if (fileD.size > 5 * 1024 * 1024) {
        setMsg(msg, false, "El logo derecho no puede superar 5 MB.");
        return;
      }
      const b64d = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => {
          const s = String(r.result || "");
          const i = s.indexOf(",");
          resolve(i >= 0 ? s.slice(i + 1) : s);
        };
        r.onerror = () => reject(new Error("No se pudo leer el archivo"));
        r.readAsDataURL(fileD);
      });
      payload.logo_derecho_base64 = b64d;
    }
    try {
      await fetchJson("/api/admin/centros-educativos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMsg(msg, true, "Centro educativo agregado correctamente.");
      e.target.reset();
      document.getElementById("centro-estado").value = "Activo";
      const ld = document.getElementById("centro-logo-derecho");
      if (ld) ld.value = "";
      await loadCatalogs();
    } catch (err) {
      setMsg(msg, false, err.message || "Error");
    }
  });
}

const firmaDoctorForm = document.getElementById("form-new-firma-doctor");
if (firmaDoctorForm) {
  firmaDoctorForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("firma-doctor-msg");
    msg.classList.add("hidden");
    const payload = {
      nombres: document.getElementById("firma-doctor-nombres").value.trim(),
      genero: document.getElementById("firma-doctor-genero").value,
      estado: document.getElementById("firma-doctor-estado").value,
    };
    if (!payload.genero) {
      setMsg(msg, false, "Seleccione el género.");
      msg.classList.remove("hidden");
      return;
    }
    const fin = document.getElementById("firma-doctor-archivo");
    const f = fin && fin.files && fin.files[0];
    if (f) {
      if (f.size > 5 * 1024 * 1024) {
        setMsg(msg, false, "La imagen no puede superar 5 MB.");
        msg.classList.remove("hidden");
        return;
      }
      const b64 = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => {
          const s = String(r.result || "");
          const i = s.indexOf(",");
          resolve(i >= 0 ? s.slice(i + 1) : s);
        };
        r.onerror = () => reject(new Error("No se pudo leer el archivo"));
        r.readAsDataURL(f);
      });
      payload.firma_base64 = b64;
    }
    try {
      await fetchJson("/api/admin/firma-doctores", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMsg(msg, true, "Director registrado correctamente.");
      msg.classList.remove("hidden");
      e.target.reset();
      document.getElementById("firma-doctor-estado").value = "Activo";
      await loadCatalogs();
    } catch (err) {
      setMsg(msg, false, err.message || "Error");
      msg.classList.remove("hidden");
    }
  });
}
