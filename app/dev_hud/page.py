TEST_HUD_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Smolbox Dev HUD</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --panel-2: #eef3f7;
      --ink: #17202a;
      --muted: #5f6f7c;
      --line: #d8e0e7;
      --blue: #1d5fd1;
      --green: #0f7b45;
      --yellow: #a26100;
      --red: #bd2d2d;
      --shadow: 0 10px 30px rgba(23, 32, 42, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    button,
    input,
    select {
      font: inherit;
    }

    .shell {
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    h1,
    h2,
    h3,
    p {
      margin: 0;
    }

    h1 {
      font-size: 28px;
      line-height: 1.1;
      font-weight: 760;
    }

    h2 {
      font-size: 16px;
      line-height: 1.2;
      font-weight: 740;
    }

    h3 {
      font-size: 14px;
      line-height: 1.25;
      font-weight: 720;
    }

    .subtle {
      color: var(--muted);
      font-size: 13px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .grid {
      display: grid;
      gap: 14px;
    }

    .stats {
      grid-template-columns: repeat(7, minmax(0, 1fr));
      margin-bottom: 14px;
    }

    .layout {
      grid-template-columns: 1.15fr 0.85fr;
      align-items: start;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }

    .stat {
      min-height: 92px;
      padding: 14px;
    }

    .stat strong {
      display: block;
      margin-top: 10px;
      font-size: 26px;
      line-height: 1;
    }

    .panel {
      padding: 16px;
    }

    .panel-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
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
      background: var(--panel);
      color: var(--ink);
      cursor: pointer;
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }

    .btn:hover {
      border-color: #a9b8c5;
      background: #f8fafc;
    }

    .btn:disabled {
      cursor: not-allowed;
      opacity: 0.52;
    }

    .btn.primary {
      border-color: var(--blue);
      background: var(--blue);
      color: white;
    }

    .btn.success {
      border-color: var(--green);
      background: var(--green);
      color: white;
    }

    .btn.warning {
      border-color: #e8c989;
      background: #fff5db;
      color: #5d3b00;
    }

    .btn.danger {
      border-color: #f1b1b1;
      background: #fff1f1;
      color: var(--red);
    }

    .stack {
      display: grid;
      gap: 12px;
    }

    .row {
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 10px;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
    }

    .row:last-child {
      border-bottom: 0;
    }

    .mono {
      overflow-wrap: anywhere;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }

    .flow {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }

    .field {
      display: grid;
      gap: 5px;
    }

    .field span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 720;
      text-transform: uppercase;
    }

    .field.full {
      grid-column: 1 / -1;
    }

    .input {
      width: 100%;
      min-height: 38px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      color: var(--ink);
      font-size: 13px;
    }

    .checkline {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }

    .table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    .table th,
    .table td {
      padding: 9px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }

    .table th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      text-transform: uppercase;
    }

    .state {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--panel-2);
      color: var(--ink);
      font-size: 12px;
      font-weight: 760;
      white-space: nowrap;
    }

    .state.ok {
      background: #dff5e8;
      color: var(--green);
    }

    .state.warn {
      background: #fff2cc;
      color: var(--yellow);
    }

    .state.bad {
      background: #ffe1e1;
      color: var(--red);
    }

    .console {
      min-height: 220px;
      max-height: 420px;
      overflow: auto;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #111827;
      color: #d1fae5;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
    }

    .split {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    .notice {
      padding: 12px;
      border: 1px solid #f0d28a;
      border-radius: 8px;
      background: #fff8e6;
      color: #563a00;
      font-size: 13px;
      font-weight: 650;
    }

    @media (max-width: 1080px) {
      .stats {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }

      .layout,
      .split {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 720px) {
      .shell {
        padding: 14px;
      }

      .topbar {
        align-items: flex-start;
        flex-direction: column;
      }

      .stats,
      .flow,
      .form-grid {
        grid-template-columns: 1fr 1fr;
      }

      .row {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>Smolbox Dev HUD</h1>
        <p class="subtle">Panel local para probar caja chica, evidencia, CFDI y flujo.</p>
      </div>
      <span class="badge">Solo desarrollo</span>
    </header>

    <section class="grid stats" id="stats"></section>

    <section class="grid layout">
      <div class="stack">
        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Escenario HUD</h2>
              <p class="subtle">Datos aislados con prefijo HUD.</p>
            </div>
            <div class="toolbar">
              <button class="btn" id="refreshBtn">Actualizar</button>
              <button class="btn primary" id="seedBtn">Crear escenario</button>
              <button class="btn danger" id="resetBtn">Limpiar HUD</button>
            </div>
          </div>
          <div id="scenarioRows"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Crear y asignar</h2>
              <p class="subtle">Herramientas locales para tiendas y usuarios HUD.</p>
            </div>
          </div>

          <h3>Tienda</h3>
          <div class="form-grid">
            <label class="field">
              <span>Código</span>
              <input class="input" id="storeCode" value="HUD-002" />
            </label>
            <label class="field">
              <span>Nombre</span>
              <input class="input" id="storeName" value="HUD Sucursal Norte" />
            </label>
            <label class="field full">
              <span>Correo tienda</span>
              <input class="input" id="storeEmail" value="hud.sucursal.norte@hud.smolbox.local" />
            </label>
          </div>
          <div class="toolbar">
            <button class="btn primary" id="createStoreBtn">Crear tienda</button>
          </div>

          <h3 style="margin-top: 16px;">Usuario</h3>
          <div class="form-grid">
            <label class="field">
              <span>Nombre</span>
              <input class="input" id="userName" value="HUD Usuario Nuevo" />
            </label>
            <label class="field">
              <span>Rol</span>
              <select class="input" id="userRole">
                <option value="store">Tienda</option>
                <option value="accountant">Contador</option>
                <option value="treasury">Tesorería</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <label class="field full">
              <span>Correo</span>
              <input class="input" id="userEmail" value="hud.usuario.nuevo@hud.smolbox.local" />
            </label>
          </div>
          <div class="toolbar">
            <button class="btn primary" id="createUserBtn">Crear usuario</button>
          </div>

          <h3 style="margin-top: 16px;">Asignación</h3>
          <div class="form-grid">
            <label class="field">
              <span>Tienda</span>
              <select class="input" id="assignStoreId"></select>
            </label>
            <label class="field">
              <span>Usuario</span>
              <select class="input" id="assignUserId"></select>
            </label>
          </div>
          <div class="toolbar">
            <button class="btn" id="assignUserBtn">Asignar usuario</button>
          </div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Flujo</h2>
              <p class="subtle">Transiciones con usuarios demo por rol.</p>
            </div>
          </div>
          <div class="flow">
            <button class="btn primary flow-btn" data-target="submitted">Enviar tienda</button>
            <button class="btn flow-btn" data-target="under_accounting_review">Revisión contable</button>
            <button class="btn warning flow-btn" data-target="correction_required">Pedir corrección</button>
            <button class="btn success flow-btn" data-target="accounting_approved">Aprobar contabilidad</button>
            <button class="btn flow-btn" data-target="treasury_review">Revisión tesorería</button>
            <button class="btn success flow-btn" data-target="approved_for_payment">Aprobar pago</button>
            <button class="btn success flow-btn" data-target="paid">Marcar pagado</button>
            <button class="btn success flow-btn" data-target="closed">Cerrar</button>
          </div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Gastos</h2>
              <p class="subtle">Filas actuales de la solicitud demo.</p>
            </div>
            <div class="toolbar">
              <button class="btn warning" id="importDryRunBtn">CSV dry run</button>
              <button class="btn" id="importRealBtn">Importar CSV</button>
              <button class="btn success" id="completeCfdiBtn">Completar CFDI demo</button>
            </div>
          </div>
          <div id="expenses"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Crear pago/gasto</h2>
              <p class="subtle">Agrega un movimiento a la solicitud HUD en borrador.</p>
            </div>
          </div>
          <div class="form-grid">
            <label class="field">
              <span>Proveedor</span>
              <input class="input" id="paymentMerchant" value="HUD Proveedor Pago" />
            </label>
            <label class="field">
              <span>Monto</span>
              <input class="input" id="paymentAmount" value="250.00" />
            </label>
            <label class="field">
              <span>Fecha</span>
              <input class="input" id="paymentDate" type="date" value="2026-08-17" />
            </label>
            <label class="field">
              <span>Categoría</span>
              <input class="input" id="paymentCategory" value="hud_pago" />
            </label>
            <label class="checkline full">
              <input id="paymentBalanced" type="checkbox" checked />
              Ajustar total reportado para mantener balance
            </label>
          </div>
          <div class="toolbar">
            <button class="btn primary" id="createPaymentBtn">Crear pago/gasto</button>
          </div>
        </section>
      </div>

      <aside class="stack">
        <section class="notice">
          Ambiente local. No uses este HUD como interfaz final ni lo expongas en produccion.
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Validación</h2>
              <p class="subtle">Resumen calculado por el backend.</p>
            </div>
          </div>
          <div id="validation"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Auditoría</h2>
              <p class="subtle">Últimos eventos del escenario.</p>
            </div>
          </div>
          <div id="audit"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Respuesta</h2>
              <p class="subtle">Resultado de la última acción.</p>
            </div>
          </div>
          <pre class="console" id="console">Listo.</pre>
        </section>
      </aside>
    </section>
  </main>

  <script>
    const api = "/api/v1";
    let state = null;
    let busy = false;

    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => Array.from(document.querySelectorAll(selector));

    function money(value) {
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat("es-MX", {
        style: "currency",
        currency: "MXN"
      }).format(Number(value));
    }

    function writeConsole(label, payload) {
      $("#console").textContent = `${label}\\n${JSON.stringify(payload, null, 2)}`;
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
      if (!response.ok) {
        throw { status: response.status, payload };
      }
      return payload;
    }

    function jsonRequest(path, payload) {
      return request(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    async function loadStatus() {
      try {
        state = await request("/dev-hud/status");
        render();
      } catch (error) {
        writeConsole("No se pudo cargar el estado", error);
      }
    }

    async function runAction(label, fn) {
      setBusy(true);
      try {
        const payload = await fn();
        writeConsole(label, payload);
        await loadStatus();
      } catch (error) {
        writeConsole(`${label} falló`, error);
      } finally {
        setBusy(false);
        applyButtonState();
      }
    }

    function setBusy(isBusy) {
      busy = isBusy;
      $$("button").forEach((button) => {
        button.disabled = isBusy;
      });
    }

    function applyButtonState() {
      if (busy) return;
      const hasScenario = Boolean(state?.scenario?.exists);
      const hasStores = Boolean(state?.workspace?.stores?.length);
      const hasUsers = Boolean(state?.workspace?.users?.length);
      $$(".flow-btn, #importDryRunBtn, #importRealBtn, #completeCfdiBtn, #createPaymentBtn").forEach((button) => {
        button.disabled = !hasScenario;
      });
      $("#assignUserBtn").disabled = !hasStores || !hasUsers;
    }

    function render() {
      renderStats();
      renderScenario();
      renderWorkspaceSelectors();
      renderExpenses();
      renderValidation();
      renderAudit();
      applyButtonState();
    }

    function renderStats() {
      const counts = state?.counts || {};
      const stats = [
        ["API", state?.api_status || "n/a"],
        ["DB", state?.database || "n/a"],
        ["Tiendas", counts.stores ?? 0],
        ["Usuarios", counts.users ?? 0],
        ["Solicitudes", counts.reimbursement_requests ?? 0],
        ["Gastos", counts.expenses ?? 0],
        ["Adjuntos", counts.attachments ?? 0]
      ];
      $("#stats").innerHTML = stats.map(([label, value]) => `
        <article class="card stat">
          <span class="subtle">${label}</span>
          <strong>${value}</strong>
        </article>
      `).join("");
    }

    function row(label, value) {
      return `<div class="row"><strong>${label}</strong><span class="mono">${value ?? "-"}</span></div>`;
    }

    function renderScenario() {
      const scenario = state?.scenario;
      if (!scenario?.exists) {
        $("#scenarioRows").innerHTML = row("Estado", "Sin escenario HUD");
        return;
      }
      $("#scenarioRows").innerHTML = [
        row("Solicitud", scenario.request_id),
        row("Estado", `<span class="state">${scenario.status}</span>`),
        row("Tienda", `${scenario.store_code} / ${scenario.store_name}`),
        row("Periodo", scenario.period_name),
        row("Usuario tienda", scenario.users.store?.email),
        row("Usuario contador", scenario.users.accountant?.email),
        row("Usuario tesorería", scenario.users.treasury?.email)
      ].join("");
    }

    function renderWorkspaceSelectors() {
      const stores = state?.workspace?.stores || [];
      const users = state?.workspace?.users || [];
      const selectedStore = $("#assignStoreId").value || state?.scenario?.store_id || "";
      const selectedUser = $("#assignUserId").value || state?.scenario?.users?.store?.id || "";

      $("#assignStoreId").innerHTML = stores.map((store) => `
        <option value="${store.id}" ${store.id === selectedStore ? "selected" : ""}>
          ${store.code} / ${store.name}
        </option>
      `).join("");
      $("#assignUserId").innerHTML = users.map((user) => `
        <option value="${user.id}" ${user.id === selectedUser ? "selected" : ""}>
          ${user.role} / ${user.email}
        </option>
      `).join("");
    }

    function renderExpenses() {
      const expenses = state?.scenario?.expenses || [];
      if (!expenses.length) {
        $("#expenses").innerHTML = "<p class='subtle'>Sin gastos.</p>";
        return;
      }
      $("#expenses").innerHTML = `
        <table class="table">
          <thead>
            <tr>
              <th>Proveedor</th>
              <th>Monto</th>
              <th>Ticket</th>
              <th>CFDI</th>
            </tr>
          </thead>
          <tbody>
            ${expenses.map((expense) => `
              <tr>
                <td>${expense.merchant}</td>
                <td>${money(expense.amount)}</td>
                <td>${badge(expense.has_receipt)}</td>
                <td>${badge(expense.has_current_valid_cfdi)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function badge(ok) {
      return ok
        ? "<span class='state ok'>OK</span>"
        : "<span class='state warn'>Pendiente</span>";
    }

    function renderValidation() {
      const summary = state?.scenario?.summary;
      if (!summary) {
        $("#validation").innerHTML = "<p class='subtle'>Sin resumen.</p>";
        return;
      }
      const issues = summary.issues?.length
        ? summary.issues.map((issue) => `<tr><td>${issue.code}</td><td>${issue.severity}</td></tr>`).join("")
        : "<tr><td colspan='2'>Sin errores</td></tr>";
      $("#validation").innerHTML = `
        <div class="split">
          ${row("Reportado", money(summary.reported_total))}
          ${row("Calculado", money(summary.calculated_total))}
          ${row("Diferencia", money(summary.difference))}
          ${row("Enviar", summary.ready_for_submission ? "Listo" : "Bloqueado")}
          ${row("Contabilidad", summary.ready_for_accounting_approval ? "Listo" : "Bloqueado")}
        </div>
        <table class="table">
          <thead><tr><th>Issue</th><th>Severidad</th></tr></thead>
          <tbody>${issues}</tbody>
        </table>
      `;
    }

    function renderAudit() {
      const events = state?.scenario?.audit_events || [];
      if (!events.length) {
        $("#audit").innerHTML = "<p class='subtle'>Sin eventos.</p>";
        return;
      }
      $("#audit").innerHTML = `
        <table class="table">
          <thead><tr><th>Acción</th><th>Estado</th></tr></thead>
          <tbody>
            ${events.map((event) => `
              <tr>
                <td>${event.action}</td>
                <td>${event.to_status || "-"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    async function importDemo(dryRun) {
      const requestId = state?.scenario?.request_id;
      const form = new FormData();
      const csv = [
        "proveedor,importe,fecha,categoria,descripcion,rfc_proveedor,moneda",
        "HUD Importado Uno,100.00,2026-08-15,Papeleria,Import demo,XAXX010101000,MXN",
        "HUD Importado Dos,200.00,2026-08-16,Transporte,Import demo,XEXX010101000,MXN"
      ].join("\\n");
      form.append("dry_run", dryRun ? "true" : "false");
      form.append("file", new Blob([csv], { type: "text/csv" }), "hud-import.csv");
      return request(`/reimbursement-requests/${requestId}/expenses/import`, {
        method: "POST",
        body: form
      });
    }

    $("#refreshBtn").addEventListener("click", () => runAction("Estado actualizado", loadStatus));
    $("#seedBtn").addEventListener("click", () => runAction("Escenario creado", () =>
      request("/dev-hud/seed-demo", { method: "POST" })
    ));
    $("#createStoreBtn").addEventListener("click", () => runAction("Tienda creada", () =>
      jsonRequest("/dev-hud/stores", {
        code: $("#storeCode").value,
        name: $("#storeName").value,
        contact_email: $("#storeEmail").value || null
      })
    ));
    $("#createUserBtn").addEventListener("click", () => runAction("Usuario creado", () =>
      jsonRequest("/dev-hud/users", {
        email: $("#userEmail").value,
        full_name: $("#userName").value,
        role: $("#userRole").value
      })
    ));
    $("#assignUserBtn").addEventListener("click", () => runAction("Usuario asignado", () =>
      jsonRequest("/dev-hud/assign-user", {
        store_id: $("#assignStoreId").value,
        user_id: $("#assignUserId").value
      })
    ));
    $("#resetBtn").addEventListener("click", () => {
      if (!confirm("Limpiar solo datos HUD?")) return;
      runAction("HUD limpiado", () => request("/dev-hud/reset-demo", { method: "POST" }));
    });
    $("#completeCfdiBtn").addEventListener("click", () => runAction("CFDI demo completado", () =>
      request("/dev-hud/complete-cfdi", { method: "POST" })
    ));
    $("#importDryRunBtn").addEventListener("click", () => runAction("CSV dry run", () =>
      importDemo(true)
    ));
    $("#importRealBtn").addEventListener("click", () => runAction("CSV importado", () =>
      importDemo(false)
    ));
    $("#createPaymentBtn").addEventListener("click", () => runAction("Pago/gasto creado", () =>
      jsonRequest("/dev-hud/payments", {
        merchant: $("#paymentMerchant").value,
        amount: $("#paymentAmount").value,
        spent_on: $("#paymentDate").value,
        category: $("#paymentCategory").value || null,
        keep_reported_total_balanced: $("#paymentBalanced").checked
      })
    ));
    $$(".flow-btn").forEach((button) => {
      button.addEventListener("click", () => runAction(`Transición ${button.dataset.target}`, () =>
        request(`/dev-hud/transition/${button.dataset.target}`, { method: "POST" })
      ));
    });

    loadStatus();
  </script>
</body>
</html>
"""
