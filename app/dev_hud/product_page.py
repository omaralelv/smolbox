PRODUCT_VIEW_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Smolbox Producto Demo</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f9;
      --surface: #ffffff;
      --surface-alt: #eef3f7;
      --ink: #16202a;
      --muted: #607180;
      --line: #d8e2ea;
      --blue: #1d5fd1;
      --green: #0b7a47;
      --amber: #a15c00;
      --red: #b72929;
      --shadow: 0 16px 42px rgba(18, 30, 42, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    button, input, select { font: inherit; }

    .shell {
      max-width: 1360px;
      margin: 0 auto;
      padding: 22px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .brand-mark {
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      border-radius: 8px;
      background: var(--ink);
      color: white;
      font-weight: 800;
    }

    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 24px; line-height: 1.1; }
    h2 { font-size: 18px; line-height: 1.2; }
    h3 { font-size: 14px; line-height: 1.2; }

    .subtle {
      color: var(--muted);
      font-size: 13px;
    }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--ink);
      cursor: pointer;
      font-size: 13px;
      font-weight: 750;
      text-decoration: none;
      white-space: nowrap;
    }

    .btn:hover { background: #f9fbfd; border-color: #aab8c4; }
    .btn:disabled { cursor: not-allowed; opacity: 0.48; }
    .btn.primary { border-color: var(--blue); background: var(--blue); color: white; }
    .btn.success { border-color: var(--green); background: var(--green); color: white; }
    .btn.warning { border-color: #e6c381; background: #fff5dd; color: #5c3600; }
    .btn.danger { border-color: #efb0b0; background: #fff0f0; color: var(--red); }

    .input {
      min-height: 38px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: white;
      color: var(--ink);
      padding: 8px 10px;
      font-size: 13px;
    }

    .layout {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }

    .sidebar {
      position: sticky;
      top: 16px;
      overflow: hidden;
    }

    .sidebar-head {
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }

    .role-list {
      display: grid;
      gap: 4px;
      padding: 8px;
    }

    .role-tab {
      width: 100%;
      justify-content: flex-start;
      border-color: transparent;
      background: transparent;
    }

    .role-tab.active {
      border-color: #b9c7d4;
      background: var(--surface-alt);
    }

    .main {
      display: grid;
      gap: 14px;
    }

    .hero {
      padding: 16px;
    }

    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 14px;
      align-items: start;
    }

    .metric-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }

    .metric {
      min-height: 76px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 12px;
    }

    .metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .metric strong {
      display: block;
      margin-top: 9px;
      font-size: 18px;
      overflow-wrap: anywhere;
    }

    .state {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      width: fit-content;
      padding: 3px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .state.ok { border-color: #b8dfc9; background: #ecfff4; color: var(--green); }
    .state.warn { border-color: #ecd097; background: #fff7e6; color: var(--amber); }
    .state.bad { border-color: #efb4b4; background: #fff0f0; color: var(--red); }

    .workflow {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 8px;
    }

    .step {
      min-height: 70px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: white;
    }

    .step.active {
      border-color: var(--blue);
      box-shadow: inset 0 0 0 1px var(--blue);
    }

    .step strong {
      display: block;
      font-size: 13px;
      margin-bottom: 5px;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.2fr);
      gap: 14px;
    }

    .pane {
      padding: 14px;
    }

    .pane-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 12px;
    }

    .detail-grid {
      display: grid;
      gap: 8px;
    }

    .detail {
      display: grid;
      grid-template-columns: 130px minmax(0, 1fr);
      gap: 8px;
      padding: 9px 0;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
    }

    .detail:last-child { border-bottom: 0; }
    .detail span { color: var(--muted); }
    .detail strong { overflow-wrap: anywhere; }

    .expense-tools {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 8px;
      margin-bottom: 10px;
      align-items: center;
    }

    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
      font-size: 13px;
    }

    th, td {
      padding: 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }

    th {
      background: #f7f9fb;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }

    tr.selected-row {
      background: #edf5ff;
      outline: 2px solid #95bbea;
      outline-offset: -2px;
    }

    .action-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 14px;
      border-top: 1px solid var(--line);
      background: #fbfcfe;
    }

    .notice {
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      color: var(--muted);
      font-size: 13px;
    }

    .activity {
      min-height: 92px;
      max-height: 180px;
      overflow: auto;
      white-space: pre-wrap;
      font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #26333f;
      background: #f8fafc;
      border-top: 1px solid var(--line);
      padding: 12px 14px;
    }

    .empty-state {
      display: grid;
      gap: 14px;
      padding: 34px;
      text-align: center;
      place-items: center;
    }

    @media (max-width: 980px) {
      .topbar, .hero-grid, .layout, .workspace { grid-template-columns: 1fr; }
      .topbar { align-items: flex-start; }
      .toolbar { justify-content: flex-start; }
      .sidebar { position: static; }
      .metric-strip, .workflow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    @media (max-width: 620px) {
      .shell { padding: 12px; }
      .metric-strip, .workflow, .expense-tools { grid-template-columns: 1fr; }
      .detail { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div>
          <h1>Smolbox</h1>
          <p class="subtle">Vista de producto para demostración de flujo</p>
        </div>
      </div>
      <div class="toolbar">
        <select class="input" id="requestSelect" style="width: 280px;"></select>
        <button class="btn" id="refreshBtn">Actualizar</button>
        <button class="btn primary" id="seedBtn">Crear demo</button>
        <button class="btn" id="seedBulkBtn">Demo masivo</button>
        <a class="btn" href="/test-hud">HUD técnico</a>
      </div>
    </header>

    <section class="layout">
      <aside class="panel sidebar">
        <div class="sidebar-head">
          <h2>Rol</h2>
          <p class="subtle">Cambia de ventana como usuario final.</p>
        </div>
        <div class="role-list" id="roleTabs"></div>
      </aside>

      <section class="main">
        <section class="panel hero" id="productApp"></section>
      </section>
    </section>
  </main>

  <script>
    const api = "/api/v1";
    const password = "hud-password";
    let state = null;
    let activeRole = window.localStorage.getItem("smolbox.productView.role") || "store";
    let activeRequestId = window.localStorage.getItem("smolbox.productView.requestId");
    let selectedExpenseId = null;
    let authToken = null;
    let authUser = null;

    const roles = [
      {
        id: "store",
        label: "Tienda",
        title: "Captura de caja chica",
        subtitle: "Solicitud, gastos y comprobantes",
        queueStatuses: ["draft", "correction_required"]
      },
      {
        id: "system",
        label: "Validación",
        title: "Validación automática",
        subtitle: "Comprobantes, CFDI, totales y alertas",
        queueStatuses: ["draft", "submitted", "authorization_review", "authorized", "under_accounting_review"]
      },
      {
        id: "authorizer",
        label: "Autorización",
        title: "Autorización por producto",
        subtitle: "Solo gastos especiales",
        queueStatuses: ["submitted", "authorization_review"]
      },
      {
        id: "accountant",
        label: "Contabilidad",
        title: "Revisión contable",
        subtitle: "Factura, CFDI, formato y póliza",
        queueStatuses: ["submitted", "authorized", "under_accounting_review", "accounting_reviewed"]
      },
      {
        id: "accounting_manager",
        label: "Gerente",
        title: "Aprobación contable",
        subtitle: "Control antes de tesorería",
        queueStatuses: ["accounting_reviewed", "accounting_manager_review"]
      },
      {
        id: "treasury",
        label: "Tesorería",
        title: "Pago",
        subtitle: "Liberación y registro de pago",
        queueStatuses: [
          "accounting_manager_approved",
          "treasury_review",
          "direction_approved",
          "approved_for_payment",
          "paid"
        ]
      },
      {
        id: "director",
        label: "Dirección",
        title: "Aprobación final",
        subtitle: "Autorización antes del pago",
        queueStatuses: ["direction_review"]
      }
    ];

    const reviewStatuses = [
      "authorization_review",
      "under_accounting_review",
      "accounting_manager_review",
      "treasury_review",
      "direction_review"
    ];

    const noPayableRejectionRoles = [
      "authorizer",
      "accountant",
      "accounting_manager",
      "treasury",
      "director"
    ];

    const actions = [
      {
        id: "transition:submitted",
        label: "Enviar solicitud",
        roles: ["store"],
        statuses: ["draft", "correction_required"],
        requiresSubmissionReady: true,
        style: "primary"
      },
      {
        id: "complete-cfdi",
        label: "Completar CFDI",
        roles: ["store", "system"],
        statuses: ["draft", "correction_required"],
        style: "success"
      },
      {
        id: "automated-review",
        label: "Validar automático",
        roles: ["system"],
        statuses: null
      },
      {
        id: "transition:authorization_review",
        label: "Abrir autorización",
        roles: ["authorizer"],
        statuses: ["submitted"],
        requiresAuthorizationPending: true
      },
      {
        id: "authorize-selected",
        label: "Autorizar producto",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        requiresPendingAuthorizationExpense: true,
        style: "success"
      },
      {
        id: "reject-selected",
        label: "Rechazar producto",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        requiresPendingAuthorizationExpense: true,
        style: "warning"
      },
      {
        id: "remove-selected",
        label: "Quitar gasto",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        requiresSelectedRemovable: true,
        style: "warning"
      },
      {
        id: "transition:authorized",
        label: "Enviar a contabilidad",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        style: "success"
      },
      {
        id: "transition:under_accounting_review",
        label: "Tomar revisión contable",
        roles: ["accountant"],
        statuses: ["submitted", "authorized"],
        requiresNoAuthorizationPending: true
      },
      {
        id: "remove-selected",
        label: "Quitar gasto",
        roles: ["accountant", "accounting_manager"],
        statuses: ["under_accounting_review", "accounting_manager_review"],
        requiresSelectedRemovable: true,
        style: "warning"
      },
      {
        id: "observe-selected",
        label: "Observar gasto",
        roles: ["accountant", "accounting_manager", "treasury", "director"],
        statuses: ["under_accounting_review", "accounting_manager_review", "treasury_review", "direction_review"],
        requiresActiveExpense: true
      },
      {
        id: "transition:accounting_reviewed",
        label: "Cerrar contabilidad",
        roles: ["accountant"],
        statuses: ["under_accounting_review"],
        style: "success"
      },
      {
        id: "prepare-sap",
        label: "Preparar póliza SAP",
        roles: ["accountant"],
        statuses: ["accounting_reviewed"],
        style: "success"
      },
      {
        id: "transition:accounting_manager_review",
        label: "Recibir solicitud",
        roles: ["accounting_manager"],
        statuses: ["accounting_reviewed"],
        requiresSap: true
      },
      {
        id: "transition:under_accounting_review",
        label: "Regresar a contabilidad",
        roles: ["accounting_manager"],
        statuses: ["accounting_manager_review"],
        style: "warning"
      },
      {
        id: "transition:accounting_manager_approved",
        label: "Aprobar gerente",
        roles: ["accounting_manager"],
        statuses: ["accounting_manager_review"],
        style: "success"
      },
      {
        id: "transition:treasury_review",
        label: "Tomar tesorería",
        roles: ["treasury"],
        statuses: ["accounting_manager_approved"]
      },
      {
        id: "transition:under_accounting_review",
        label: "Regresar a contabilidad",
        roles: ["treasury"],
        statuses: ["treasury_review"],
        style: "warning"
      },
      {
        id: "transition:direction_review",
        label: "Enviar a dirección",
        roles: ["treasury"],
        statuses: ["treasury_review"]
      },
      {
        id: "transition:under_accounting_review",
        label: "Regresar a contabilidad",
        roles: ["director"],
        statuses: ["direction_review"],
        style: "warning"
      },
      {
        id: "transition:direction_approved",
        label: "Aprobar dirección",
        roles: ["director"],
        statuses: ["direction_review"],
        style: "success"
      },
      {
        id: "transition:approved_for_payment",
        label: "Liberar pago",
        roles: ["treasury"],
        statuses: ["direction_approved"],
        style: "success"
      },
      {
        id: "record-payment",
        label: "Registrar pago",
        roles: ["treasury"],
        statuses: ["approved_for_payment"],
        style: "success"
      },
      {
        id: "transition:closed",
        label: "Cerrar solicitud",
        roles: ["treasury"],
        statuses: ["paid"],
        style: "success"
      },
      {
        id: "transition:rejected",
        label: "Rechazar solicitud sin monto",
        roles: noPayableRejectionRoles,
        statuses: reviewStatuses,
        requiresNoPayable: true,
        style: "danger"
      }
    ];

    const steps = [
      { label: "Tienda", statuses: ["draft", "submitted"] },
      { label: "Autorización", statuses: ["authorization_review", "authorized"] },
      { label: "Contabilidad", statuses: ["under_accounting_review", "accounting_reviewed"] },
      { label: "Gerente", statuses: ["accounting_manager_review", "accounting_manager_approved"] },
      { label: "Tesorería", statuses: ["treasury_review", "approved_for_payment", "paid"] },
      { label: "Dirección", statuses: ["direction_review", "direction_approved"] },
      { label: "Cierre", statuses: ["closed", "rejected"] }
    ];

    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => Array.from(document.querySelectorAll(selector));

    function money(value) {
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(Number(value));
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function writeActivity(label, payload) {
      $("#activity").textContent = `${label}\\n${JSON.stringify(payload, null, 2)}`;
    }

    function writeError(label, error) {
      const detail = error?.payload?.detail;
      const message = detail?.message || detail || error?.payload?.message || error?.message || "Error";
      writeActivity(label, {
        ok: false,
        status: error?.status || null,
        code: detail?.code || error?.payload?.code || null,
        message,
        raw: error?.payload || null
      });
    }

    function selectedRequestQuery() {
      return activeRequestId ? `?request_id=${encodeURIComponent(activeRequestId)}` : "";
    }

    function selectedDevHudPath(path) {
      return `${path}${selectedRequestQuery()}`;
    }

    async function request(path, options = {}) {
      const response = await fetch(`${api}${path}`, options);
      const text = await response.text();
      let payload = text;
      try {
        payload = text ? JSON.parse(text) : {};
      } catch {
        payload = { raw: text };
      }
      if (!response.ok) throw { status: response.status, payload };
      return payload;
    }

    function jsonRequest(path, payload, token = null) {
      return request(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      });
    }

    async function runAction(label, fn) {
      setBusy(true);
      try {
        const payload = await fn();
        writeActivity(label, payload);
        await loadStatus();
      } catch (error) {
        writeError(`${label} falló`, error);
      } finally {
        setBusy(false);
      }
    }

    function setBusy(isBusy) {
      $$("button, select").forEach((element) => {
        element.disabled = isBusy;
      });
    }

    async function loadStatus() {
      state = await request(selectedDevHudPath("/dev-hud/status"));
      if (activeRequestId && !state?.scenario?.exists && (state?.scenarios || []).length) {
        activeRequestId = state.scenarios[0].request_id;
        persistRequestId();
        state = await request(selectedDevHudPath("/dev-hud/status"));
      }
      if (state?.scenario?.request_id) {
        activeRequestId = state.scenario.request_id;
        persistRequestId();
      }
      syncSelectedExpense();
      render();
    }

    function persistRequestId() {
      if (activeRequestId) {
        window.localStorage.setItem("smolbox.productView.requestId", activeRequestId);
      } else {
        window.localStorage.removeItem("smolbox.productView.requestId");
      }
    }

    function persistRole() {
      window.localStorage.setItem("smolbox.productView.role", activeRole);
    }

    function syncSelectedExpense() {
      const expenses = state?.scenario?.expenses || [];
      if (!expenses.length) {
        selectedExpenseId = null;
        return;
      }
      if (expenses.some((expense) => expense.id === selectedExpenseId)) return;
      const activeExpense = expenses.find((expense) => !expense.is_removed && !expense.is_rejected);
      selectedExpenseId = activeExpense?.id || expenses[0].id;
    }

    function render() {
      renderRoleTabs();
      renderRequestSelector();
      renderProduct();
    }

    function renderRoleTabs() {
      $("#roleTabs").innerHTML = roles.map((role) => `
        <button class="btn role-tab ${role.id === activeRole ? "active" : ""}" data-role="${role.id}">
          ${escapeHtml(role.label)}
        </button>
      `).join("");
    }

    function renderRequestSelector() {
      const scenarios = state?.scenarios || [];
      $("#requestSelect").innerHTML = scenarios.length
        ? scenarios.map((scenario) => `
            <option value="${escapeHtml(scenario.request_id)}" ${scenario.request_id === activeRequestId ? "selected" : ""}>
              ${escapeHtml(scenario.store_code)} / ${escapeHtml(scenario.status)} / ${money(scenario.calculated_total)}
            </option>
          `).join("")
        : "<option value=''>Sin solicitudes demo</option>";
    }

    function renderProduct() {
      const scenario = state?.scenario;
      const role = roleConfig(activeRole);
      if (!scenario?.exists) {
        $("#productApp").innerHTML = `
          <div class="empty-state">
            <div>
              <h2>No hay escenario activo</h2>
              <p class="subtle">Crea un demo para abrir la vista de producto.</p>
            </div>
            <button class="btn primary" data-top-action="seed-demo">Crear demo</button>
            <pre class="activity" id="activity">Listo.</pre>
          </div>
        `;
        attachScopedButtons();
        return;
      }

      const summary = scenario.summary || {};
      const queueActive = productQueueActive(role, scenario);
      const roleActions = actionsForRole(role.id);
      $("#productApp").innerHTML = `
        <div class="hero-grid">
          <div>
            <span class="state ${queueActive ? "ok" : "warn"}">${queueActive ? "En bandeja" : "Sin pendiente"}</span>
            <h2 style="margin-top: 10px;">${escapeHtml(role.title)}</h2>
            <p class="subtle">${escapeHtml(role.subtitle)}</p>
          </div>
          <div class="notice">
            ${escapeHtml(userLabel(role.id))}
          </div>
        </div>

        <div class="metric-strip">
          ${metric("Estado", scenario.status)}
          ${metric("Total reportado", money(summary.reported_total))}
          ${metric("Autorización pendiente", summary.missing_authorization_expense_ids?.length || 0)}
          ${metric("Póliza SAP", scenario.sap_policy?.is_prepared ? scenario.sap_policy.reference : "Pendiente")}
        </div>

        <div class="workflow" style="margin-top: 14px;">
          ${steps.map((step) => `
            <div class="step ${step.statuses.includes(scenario.status) ? "active" : ""}">
              <strong>${escapeHtml(step.label)}</strong>
              <span class="subtle">${step.statuses.includes(scenario.status) ? escapeHtml(scenario.status) : "Pendiente"}</span>
            </div>
          `).join("")}
        </div>

        <div class="workspace" style="margin-top: 14px;">
          <section class="panel pane">
            <div class="pane-head">
              <div>
                <h3>Solicitud</h3>
                <p class="subtle">${escapeHtml(scenario.period_name)}</p>
              </div>
              <span class="state">${escapeHtml(scenario.store_code)}</span>
            </div>
            <div class="detail-grid">
              ${detail("Tienda", `${scenario.store_code} / ${scenario.store_name}`)}
              ${detail("Periodo", scenario.period_name)}
              ${detail("Reportado", money(summary.reported_total))}
              ${detail("Calculado", money(summary.calculated_total))}
              ${detail("Diferencia", money(summary.difference))}
              ${detail("CFDI pendientes", summary.missing_cfdi_expense_ids?.length || 0)}
              ${detail("Alertas", summary.issues?.length || 0)}
            </div>
          </section>

          <section class="panel pane">
            <div class="pane-head">
              <div>
                <h3>Gastos</h3>
                <p class="subtle">${scenario.expenses?.length || 0} registro(s)</p>
              </div>
              <span class="state ${hasNoPayableExpenses() ? "bad" : "ok"}">
                ${hasNoPayableExpenses() ? "Sin monto" : "Con monto"}
              </span>
            </div>
            ${expenseSelector(scenario.expenses || [])}
            ${expenseTable(scenario.expenses || [], role.id)}
          </section>
        </div>

        <div class="action-bar">
          ${roleActions.length
            ? roleActions.map((action) => actionButton(role.id, action)).join("")
            : "<span class='subtle'>Sin acciones para este rol y estado.</span>"
          }
        </div>

        <pre class="activity" id="activity">Listo.</pre>
      `;
      attachScopedButtons();
    }

    function metric(label, value) {
      return `
        <div class="metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `;
    }

    function detail(label, value) {
      return `
        <div class="detail">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `;
    }

    function expenseSelector(expenses) {
      if (!expenses.length) return "<div class='notice'>Sin gastos.</div>";
      const selected = selectedExpense();
      return `
        <div class="expense-tools">
          <select class="input" id="selectedExpenseId">
            ${expenses.map((expense) => `
              <option value="${escapeHtml(expense.id)}" ${expense.id === selectedExpenseId ? "selected" : ""}>
                ${escapeHtml(expense.merchant)} / ${money(expense.amount)} / ${escapeHtml(expense.status)}
              </option>
            `).join("")}
          </select>
          <span class="state">${selected ? money(selected.amount) : "-"}</span>
        </div>
      `;
    }

    function expenseTable(expenses, roleId) {
      if (!expenses.length) return "";
      return `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Proveedor</th>
                <th>Monto</th>
                <th>Autorización</th>
                <th>Ticket</th>
                <th>CFDI</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              ${expenses.map((expense) => `
                <tr class="${expense.id === selectedExpenseId ? "selected-row" : ""}">
                  <td>${escapeHtml(expense.merchant)}</td>
                  <td>${money(expense.amount)}</td>
                  <td>${authorizationBadge(expense)}</td>
                  <td>${flagBadge(expense.has_receipt)}</td>
                  <td>${flagBadge(expense.has_current_valid_cfdi)}</td>
                  <td>${expenseStatusBadge(expense)}</td>
                  <td>${expenseActions(expense, roleId)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    function expenseActions(expense, roleId) {
      const active = isActiveExpense(expense);
      const buttons = [];
      if (active && expense.id !== selectedExpenseId && roleId !== "system") {
        buttons.push(rowButton(roleId, "select", expense.id, "Seleccionar", ""));
      }
      if (roleId === "authorizer" && state?.scenario?.status === "authorization_review" && active && expense.requires_authorization) {
        if (!expense.is_authorized) {
          buttons.push(rowButton(roleId, "authorize", expense.id, "Autorizar", "success"));
          buttons.push(rowButton(roleId, "reject", expense.id, "Rechazar", "warning"));
        }
        buttons.push(rowButton(roleId, "remove", expense.id, "Quitar", "warning"));
      }
      if (["accountant", "accounting_manager"].includes(roleId) && ["under_accounting_review", "accounting_manager_review"].includes(state?.scenario?.status) && active) {
        buttons.push(rowButton(roleId, "remove", expense.id, "Quitar", "warning"));
        buttons.push(rowButton(roleId, "observe", expense.id, "Observar", ""));
      }
      return buttons.length ? buttons.join(" ") : "<span class='subtle'>-</span>";
    }

    function rowButton(roleId, actionId, expenseId, label, style) {
      return `
        <button
          class="btn ${escapeHtml(style)} row-action"
          data-role="${escapeHtml(roleId)}"
          data-action="${escapeHtml(actionId)}"
          data-expense-id="${escapeHtml(expenseId)}"
        >
          ${escapeHtml(label)}
        </button>
      `;
    }

    function actionButton(roleId, action) {
      return `
        <button
          class="btn ${escapeHtml(action.style || "")} product-action"
          data-role="${escapeHtml(roleId)}"
          data-action="${escapeHtml(action.id)}"
          ${isActionAvailable(roleId, action) ? "" : "disabled"}
        >
          ${escapeHtml(action.label)}
        </button>
      `;
    }

    function authorizationBadge(expense) {
      if (expense.is_rejected) return "<span class='state bad'>Rechazado</span>";
      if (!expense.requires_authorization) return "<span class='state ok'>No requiere</span>";
      return expense.is_authorized
        ? "<span class='state ok'>Autorizado</span>"
        : "<span class='state warn'>Pendiente</span>";
    }

    function flagBadge(ok) {
      return ok ? "<span class='state ok'>OK</span>" : "<span class='state warn'>Pendiente</span>";
    }

    function expenseStatusBadge(expense) {
      if (expense.is_removed) return "<span class='state bad'>Removido</span>";
      if (expense.is_rejected) return "<span class='state bad'>Rechazado</span>";
      return "<span class='state ok'>Activo</span>";
    }

    function roleConfig(roleId) {
      return roles.find((role) => role.id === roleId) || roles[0];
    }

    function productQueueActive(role, scenario) {
      if (!role.queueStatuses.includes(scenario.status)) return false;
      if (scenario.status !== "submitted") return true;
      const pendingAuthorization = hasAuthorizationPending();
      if (role.id === "authorizer") return pendingAuthorization;
      if (role.id === "accountant") return !pendingAuthorization;
      return true;
    }

    function actionsForRole(roleId) {
      return actions.filter((action) => {
        const visible = action.roles.includes(roleId);
        const statusAllowed = action.statuses === null || action.statuses.includes(state?.scenario?.status);
        return visible && statusAllowed;
      });
    }

    function isActionAvailable(roleId, action) {
      if (!state?.scenario?.exists) return false;
      const roleAllowed = action.roles.includes(roleId);
      const statusAllowed = action.statuses === null || action.statuses.includes(state?.scenario?.status);
      const sapReady = !action.requiresSap || Boolean(state?.scenario?.sap_policy?.is_prepared);
      const submissionReady =
        !action.requiresSubmissionReady || Boolean(state?.scenario?.summary?.ready_for_submission);
      const noPayableReady = !action.requiresNoPayable || hasNoPayableExpenses();
      const authorizationReady = !action.requiresAuthorizationPending || hasAuthorizationPending();
      const noAuthorizationReady = !action.requiresNoAuthorizationPending || !hasAuthorizationPending();
      const pendingExpenseReady = !action.requiresPendingAuthorizationExpense || Boolean(selectedPendingAuthorizationExpense());
      const removableReady = !action.requiresSelectedRemovable || Boolean(selectedRemovableExpense());
      const activeExpenseReady = !action.requiresActiveExpense || Boolean(selectedActiveExpense());
      return (
        roleAllowed &&
        statusAllowed &&
        sapReady &&
        submissionReady &&
        noPayableReady &&
        authorizationReady &&
        noAuthorizationReady &&
        pendingExpenseReady &&
        removableReady &&
        activeExpenseReady
      );
    }

    function selectedExpense() {
      return (state?.scenario?.expenses || []).find((expense) => expense.id === selectedExpenseId) || null;
    }

    function selectedActiveExpense() {
      const expense = selectedExpense();
      return expense && isActiveExpense(expense) ? expense : null;
    }

    function selectedPendingAuthorizationExpense() {
      const expense = selectedActiveExpense();
      if (!expense || !expense.requires_authorization || expense.is_authorized) return null;
      return expense;
    }

    function selectedRemovableExpense() {
      const expense = selectedActiveExpense();
      const status = state?.scenario?.status;
      if (!expense) return null;
      if (["under_accounting_review", "accounting_manager_review"].includes(status)) return expense;
      if (status === "authorization_review" && expense.requires_authorization) return expense;
      return null;
    }

    function isActiveExpense(expense) {
      return !expense.is_removed && !expense.is_rejected;
    }

    function hasAuthorizationPending() {
      return Boolean(state?.scenario?.summary?.missing_authorization_expense_ids?.length);
    }

    function hasNoPayableExpenses() {
      return state?.scenario?.summary?.expense_count === 0;
    }

    function userLabel(roleId) {
      if (roleId === "system") return "Validación automática";
      const user = state?.scenario?.users?.[roleId];
      return user?.email ? `${roleId} / ${user.email}` : roleId;
    }

    async function loginRole(roleId) {
      const email = state?.scenario?.users?.[roleId]?.email;
      if (!email) throw { status: 409, payload: { message: "El rol no tiene usuario demo." } };
      const login = await jsonRequest("/auth/login", { email, password });
      authToken = login.access_token;
      authUser = login.user;
      return login.access_token;
    }

    function scenarioRequestId() {
      const requestId = state?.scenario?.request_id;
      if (!requestId) throw { status: 409, payload: { message: "No hay solicitud activa." } };
      return requestId;
    }

    async function executeProductAction(roleId, actionId) {
      if (actionId === "complete-cfdi") {
        return request(selectedDevHudPath("/dev-hud/complete-cfdi"), { method: "POST" });
      }
      if (actionId === "automated-review") {
        return request(selectedDevHudPath("/dev-hud/automated-review"), { method: "POST" });
      }
      if (actionId === "prepare-sap") {
        return request(selectedDevHudPath("/dev-hud/prepare-sap-policy"), { method: "POST" });
      }
      if (actionId === "record-payment") {
        const token = await loginRole("treasury");
        return jsonRequest(
          `/reimbursement-requests/${scenarioRequestId()}/payments/me`,
          {
            reference: `PRODUCT-PAGO-${Date.now()}`,
            payment_method: "transfer",
            note: "Pago registrado desde vista producto."
          },
          token
        );
      }
      if (actionId === "authorize-selected") {
        const token = await loginRole("authorizer");
        return jsonRequest(`/expenses/${selectedPendingAuthorizationExpense().id}/authorize/me`, {
          note: "Autorizado desde vista producto."
        }, token);
      }
      if (actionId === "reject-selected") {
        const token = await loginRole("authorizer");
        return jsonRequest(`/expenses/${selectedPendingAuthorizationExpense().id}/reject/me`, {
          reason: "Rechazado desde vista producto.",
          adjust_reported_total: true
        }, token);
      }
      if (actionId === "remove-selected") {
        const token = await loginRole(roleId);
        return jsonRequest(`/expenses/${selectedRemovableExpense().id}/remove/me`, {
          reason: "Gasto quitado desde vista producto.",
          adjust_reported_total: true
        }, token);
      }
      if (actionId === "observe-selected") {
        const token = await loginRole(roleId);
        return jsonRequest(`/expenses/${selectedActiveExpense().id}/observation/me`, {
          note: "Observación registrada desde vista producto."
        }, token);
      }
      if (actionId.startsWith("transition:")) {
        const target = actionId.split(":")[1];
        return request(selectedDevHudPath(`/dev-hud/transition/${target}`), { method: "POST" });
      }
      throw { status: 400, payload: { message: `Acción no soportada: ${actionId}` } };
    }

    async function executeRowAction(roleId, actionId, expenseId) {
      if (actionId === "select") {
        selectedExpenseId = expenseId;
        renderProduct();
        return { message: "Gasto seleccionado", expense_id: expenseId };
      }
      selectedExpenseId = expenseId;
      if (actionId === "authorize") return executeProductAction(roleId, "authorize-selected");
      if (actionId === "reject") return executeProductAction(roleId, "reject-selected");
      if (actionId === "remove") return executeProductAction(roleId, "remove-selected");
      if (actionId === "observe") return executeProductAction(roleId, "observe-selected");
      throw { status: 400, payload: { message: `Acción de fila no soportada: ${actionId}` } };
    }

    async function seedDemo() {
      const payload = await jsonRequest("/dev-hud/seed-demo", { reset_existing: true });
      activeRequestId = payload.scenario?.request_id || activeRequestId;
      persistRequestId();
      return payload;
    }

    async function seedBulkDemo() {
      const payload = await jsonRequest("/dev-hud/seed-bulk-demo", {
        reset_existing: true,
        request_count: 16,
        store_count: 5
      });
      activeRequestId = payload.scenario?.request_id || activeRequestId;
      persistRequestId();
      return payload;
    }

    function attachScopedButtons() {
      $$("[data-top-action='seed-demo']").forEach((button) => {
        button.addEventListener("click", () => runAction("Demo creado", seedDemo));
      });
      $$(".product-action").forEach((button) => {
        button.addEventListener("click", () =>
          runAction(button.textContent.trim(), () =>
            executeProductAction(button.dataset.role, button.dataset.action)
          )
        );
      });
      $$(".row-action").forEach((button) => {
        button.addEventListener("click", () =>
          runAction(button.textContent.trim(), () =>
            executeRowAction(button.dataset.role, button.dataset.action, button.dataset.expenseId)
          )
        );
      });
      const selector = $("#selectedExpenseId");
      if (selector) {
        selector.addEventListener("change", (event) => {
          selectedExpenseId = event.target.value;
          renderProduct();
        });
      }
    }

    $("#roleTabs").addEventListener("click", (event) => {
      const button = event.target.closest(".role-tab");
      if (!button) return;
      activeRole = button.dataset.role;
      persistRole();
      render();
    });

    $("#requestSelect").addEventListener("change", (event) => {
      activeRequestId = event.target.value || null;
      persistRequestId();
      runAction("Solicitud seleccionada", async () => ({ request_id: activeRequestId }));
    });

    $("#refreshBtn").addEventListener("click", () => runAction("Actualizado", loadStatus));
    $("#seedBtn").addEventListener("click", () => runAction("Demo creado", seedDemo));
    $("#seedBulkBtn").addEventListener("click", () => runAction("Demo masivo creado", seedBulkDemo));

    loadStatus().catch((error) => {
      $("#productApp").innerHTML = `
        <div class="empty-state">
          <h2>No se pudo cargar la vista</h2>
          <p class="subtle">${escapeHtml(error?.payload?.detail?.message || error?.message || "Error")}</p>
          <pre class="activity" id="activity">Error de carga.</pre>
        </div>
      `;
    });
  </script>
</body>
</html>
"""
