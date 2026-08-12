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

    .user-flow {
      display: grid;
      gap: 0;
      border-top: 1px solid var(--line);
    }

    .user-flow-row {
      display: grid;
      grid-template-columns: 150px minmax(180px, 1fr) minmax(240px, 1.5fr);
      gap: 12px;
      align-items: start;
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
    }

    .user-flow-row:last-child {
      border-bottom: 0;
    }

    .role {
      display: grid;
      gap: 5px;
    }

    .role strong {
      font-size: 13px;
      line-height: 1.2;
    }

    .role span,
    .task {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
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
      .user-flow-row,
      .form-grid {
        grid-template-columns: 1fr 1fr;
      }

      .user-flow-row .actions {
        grid-column: 1 / -1;
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
          <h3>Personalizar escenario</h3>
          <div class="form-grid">
            <label class="field">
              <span>Código tienda</span>
              <input class="input" id="scenarioStoreCode" value="HUD-001" />
            </label>
            <label class="field">
              <span>Nombre tienda</span>
              <input class="input" id="scenarioStoreName" value="HUD Tienda Centro" />
            </label>
            <label class="field full">
              <span>Correo tienda</span>
              <input class="input" id="scenarioStoreEmail" value="hud.store@hud.smolbox.example.com" />
            </label>
            <label class="field">
              <span>Periodo</span>
              <input class="input" id="scenarioPeriodName" value="HUD Agosto 2026" />
            </label>
            <label class="field">
              <span>Total reportado</span>
              <input class="input" id="scenarioReportedTotal" value="1500.00" />
            </label>
            <label class="field">
              <span>Inicio</span>
              <input class="input" id="scenarioStartsOn" type="date" value="2026-08-01" />
            </label>
            <label class="field">
              <span>Fin</span>
              <input class="input" id="scenarioEndsOn" type="date" value="2026-08-31" />
            </label>
            <label class="checkline full">
              <input id="scenarioResetExisting" type="checkbox" checked />
              Reemplazar datos HUD existentes
            </label>
          </div>

          <h3>Gastos iniciales</h3>
          <div class="form-grid">
            <label class="field">
              <span>Proveedor 1</span>
              <input class="input" id="scenarioExpense1Merchant" value="HUD Papeleria Uno" />
            </label>
            <label class="field">
              <span>Monto 1</span>
              <input class="input" id="scenarioExpense1Amount" value="1000.00" />
            </label>
            <label class="field">
              <span>Fecha 1</span>
              <input class="input" id="scenarioExpense1Date" type="date" value="2026-08-10" />
            </label>
            <label class="field">
              <span>Categoría 1</span>
              <input class="input" id="scenarioExpense1Category" value="papeleria" />
            </label>
            <label class="field">
              <span>Proveedor 2</span>
              <input class="input" id="scenarioExpense2Merchant" value="HUD Taxi Demo" />
            </label>
            <label class="field">
              <span>Monto 2</span>
              <input class="input" id="scenarioExpense2Amount" value="500.00" />
            </label>
            <label class="field">
              <span>Fecha 2</span>
              <input class="input" id="scenarioExpense2Date" type="date" value="2026-08-11" />
            </label>
            <label class="field">
              <span>Categoría 2</span>
              <input class="input" id="scenarioExpense2Category" value="transporte" />
            </label>
            <label class="checkline full">
              <input id="scenarioExpense2RequiresAuthorization" type="checkbox" checked />
              Gasto 2 requiere autorización previa
            </label>
          </div>
          <div id="scenarioRows"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Flujo usuario final</h2>
              <p class="subtle">Recorrido por rol con acciones equivalentes al proceso real.</p>
            </div>
          </div>
          <div class="user-flow">
            <div class="user-flow-row">
              <div class="role">
                <strong>Tienda</strong>
                <span>Captura caja chica</span>
              </div>
              <div class="task">Crea la solicitud, carga gastos y la envía para revisión.</div>
              <div class="actions">
                <button class="btn primary user-flow-btn" data-action="seed-scenario">Crear solicitud</button>
                <button class="btn user-flow-btn" data-action="transition:submitted">Enviar solicitud</button>
              </div>
            </div>
            <div class="user-flow-row">
              <div class="role">
                <strong>Sistema</strong>
                <span>Validación automática</span>
              </div>
              <div class="task">Revisa comprobantes, CFDI, total, periodo, alertas y datos SAP.</div>
              <div class="actions">
                <button class="btn user-flow-btn" data-action="automated-review">Revisar automáticamente</button>
                <button class="btn success user-flow-btn" data-action="complete-cfdi">Simular CFDI</button>
              </div>
            </div>
            <div class="user-flow-row">
              <div class="role">
                <strong>Autorización</strong>
                <span>Decisión por producto</span>
              </div>
              <div class="task">Aprueba o rechaza solo los gastos que requieren autorización.</div>
              <div class="actions">
                <button class="btn user-flow-btn" data-action="transition:authorization_review">Abrir revisión</button>
                <button class="btn success user-flow-btn" data-action="authorize-expenses">Autorizar producto</button>
                <button class="btn warning user-flow-btn" data-action="reject-product">Rechazar producto</button>
                <button class="btn success user-flow-btn" data-action="transition:authorized">Enviar a contabilidad</button>
              </div>
            </div>
            <div class="user-flow-row">
              <div class="role">
                <strong>Contabilidad</strong>
                <span>Revisión documental</span>
              </div>
              <div class="task">Revisa factura, CFDI, formato, observaciones y prepara póliza SAP.</div>
              <div class="actions">
                <button class="btn user-flow-btn" data-action="transition:under_accounting_review">Tomar revisión</button>
                <button class="btn warning user-flow-btn" data-action="transition:correction_required">Pedir corrección</button>
                <button class="btn success user-flow-btn" data-action="transition:accounting_reviewed">Cerrar revisión</button>
                <button class="btn success user-flow-btn" data-action="prepare-sap-policy">Preparar póliza SAP</button>
              </div>
            </div>
            <div class="user-flow-row">
              <div class="role">
                <strong>Gerente conta</strong>
                <span>Aprobación contable</span>
              </div>
              <div class="task">Recibe solicitud revisada y aprueba antes de tesorería.</div>
              <div class="actions">
                <button class="btn user-flow-btn" data-action="transition:accounting_manager_review">Recibir solicitud</button>
                <button class="btn success user-flow-btn" data-action="transition:accounting_manager_approved">Aprobar gerente</button>
              </div>
            </div>
            <div class="user-flow-row">
              <div class="role">
                <strong>Tesorería</strong>
                <span>Pago y cierre</span>
              </div>
              <div class="task">Revisa pago, envía a dirección, confirma pago y cierra solicitud.</div>
              <div class="actions">
                <button class="btn user-flow-btn" data-action="transition:treasury_review">Revisar pago</button>
                <button class="btn user-flow-btn" data-action="transition:direction_review">Enviar a dirección</button>
                <button class="btn success user-flow-btn" data-action="transition:approved_for_payment">Liberar pago</button>
                <button class="btn success user-flow-btn" data-action="transition:paid">Confirmar pago</button>
                <button class="btn success user-flow-btn" data-action="transition:closed">Cerrar solicitud</button>
              </div>
            </div>
            <div class="user-flow-row">
              <div class="role">
                <strong>Dirección</strong>
                <span>Aprobación final</span>
              </div>
              <div class="task">Aprueba que tesorería realice el pago.</div>
              <div class="actions">
                <button class="btn success user-flow-btn" data-action="transition:direction_approved">Aprobar dirección</button>
              </div>
            </div>
          </div>
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
              <input class="input" id="storeEmail" value="hud.sucursal.norte@hud.smolbox.example.com" />
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
                <option value="authorizer">Autorización</option>
                <option value="accountant">Contador</option>
                <option value="accounting_manager">Gerente Conta</option>
                <option value="treasury">Tesorería</option>
                <option value="director">Dirección</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <label class="field full">
              <span>Correo</span>
              <input class="input" id="userEmail" value="hud.usuario.nuevo@hud.smolbox.example.com" />
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
            <button class="btn flow-btn" data-target="authorization_review">Revisión autorización</button>
            <button class="btn success" id="authorizeExpensesBtn">Autorizar gastos</button>
            <button class="btn warning" id="rejectAuthorizationExpenseBtn">Rechazar producto</button>
            <button class="btn success flow-btn" data-target="authorized">Autorizar solicitud</button>
            <button class="btn flow-btn" data-target="under_accounting_review">Revisión contable</button>
            <button class="btn warning flow-btn" data-target="correction_required">Pedir corrección</button>
            <button class="btn success flow-btn" data-target="accounting_reviewed">Cerrar contabilidad</button>
            <button class="btn success" id="prepareSapPolicyBtn">Preparar póliza SAP</button>
            <button class="btn flow-btn" data-target="accounting_manager_review">Enviar gerente</button>
            <button class="btn success flow-btn" data-target="accounting_manager_approved">Aprobar gerente</button>
            <button class="btn flow-btn" data-target="treasury_review">Revisión tesorería</button>
            <button class="btn flow-btn" data-target="direction_review">Enviar dirección</button>
            <button class="btn success flow-btn" data-target="direction_approved">Aprobar dirección</button>
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
              <button class="btn" id="automatedReviewBtn">Ejecutar automaticos</button>
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
            <label class="checkline full">
              <input id="paymentRequiresAuthorization" type="checkbox" />
              Requiere autorización previa
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
              <h2>Sesión de prueba</h2>
              <p class="subtle">Simula el token que usará el frontend real.</p>
            </div>
          </div>
          <div class="form-grid">
            <label class="field full">
              <span>Rol activo</span>
              <select class="input" id="authRole">
                <option value="store">Tienda</option>
                <option value="authorizer">Autorización</option>
                <option value="accountant">Contabilidad</option>
                <option value="accounting_manager">Gerente conta</option>
                <option value="treasury">Tesorería</option>
                <option value="director">Dirección</option>
                <option value="admin">Admin</option>
              </select>
            </label>
          </div>
          <div class="toolbar">
            <button class="btn primary" id="loginRoleBtn">Iniciar sesión</button>
            <button class="btn" id="meBtn">Ver sesión</button>
          </div>
          <div id="authState"></div>

          <h3 style="margin-top: 16px;">Acciones con token</h3>
          <div class="form-grid">
            <label class="field full">
              <span>Transición</span>
              <select class="input" id="authTransitionTarget">
                <option value="submitted">Enviar solicitud</option>
                <option value="authorization_review">Abrir autorización</option>
                <option value="authorized">Enviar a contabilidad</option>
                <option value="under_accounting_review">Tomar contabilidad</option>
                <option value="accounting_reviewed">Cerrar contabilidad</option>
                <option value="accounting_manager_review">Enviar gerente</option>
                <option value="accounting_manager_approved">Aprobar gerente</option>
                <option value="treasury_review">Revisar tesorería</option>
                <option value="direction_review">Enviar dirección</option>
                <option value="direction_approved">Aprobar dirección</option>
                <option value="approved_for_payment">Liberar pago</option>
                <option value="paid">Confirmar pago</option>
                <option value="closed">Cerrar</option>
              </select>
            </label>
          </div>
          <div class="flow">
            <button class="btn" id="authTransitionBtn">Transición con sesión</button>
            <button class="btn success" id="authAuthorizeBtn">Autorizar producto</button>
            <button class="btn warning" id="authRejectBtn">Rechazar producto</button>
            <button class="btn success" id="authSapBtn">Preparar SAP</button>
            <button class="btn warning" id="outOfPeriodBtn">Probar fuera de periodo</button>
            <button class="btn" id="downloadReceiptBtn">Descargar recibo</button>
            <button class="btn warning" id="missingAttachmentBtn">Probar archivo 404</button>
          </div>
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
    let authToken = null;
    let authUser = null;

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

    function authHeaders(extra = {}) {
      return {
        ...extra,
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {})
      };
    }

    function jsonAuthRequest(path, payload) {
      return request(path, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
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

    async function runExpectedFailure(label, fn, expectedCode) {
      setBusy(true);
      try {
        const payload = await fn();
        writeConsole(`${label} no falló`, payload);
      } catch (error) {
        const code = error?.payload?.detail?.code;
        const ok = !expectedCode || code === expectedCode || error.status === expectedCode;
        writeConsole(ok ? label : `${label} falló distinto`, error);
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
      $$(".flow-btn, #importDryRunBtn, #importRealBtn, #automatedReviewBtn, #completeCfdiBtn, #createPaymentBtn, #authorizeExpensesBtn, #rejectAuthorizationExpenseBtn, #prepareSapPolicyBtn").forEach((button) => {
        button.disabled = !hasScenario;
      });
      $$(".user-flow-btn").forEach((button) => {
        button.disabled = !hasScenario && button.dataset.action !== "seed-scenario";
      });
      $("#assignUserBtn").disabled = !hasStores || !hasUsers;
      $("#loginRoleBtn").disabled = !hasScenario;
      $("#meBtn").disabled = !authToken;
      $$("#authTransitionBtn, #authAuthorizeBtn, #authRejectBtn, #authSapBtn").forEach((button) => {
        button.disabled = !hasScenario || !authToken;
      });
      $$("#outOfPeriodBtn, #downloadReceiptBtn, #missingAttachmentBtn").forEach((button) => {
        button.disabled = !hasScenario;
      });
    }

    function render() {
      renderStats();
      renderScenario();
      renderWorkspaceSelectors();
      renderExpenses();
      renderValidation();
      renderAudit();
      renderAuthState();
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
        row("Póliza SAP", scenario.sap_policy?.is_prepared ? scenario.sap_policy.reference : "Pendiente"),
        row("Usuario tienda", scenario.users.store?.email),
        row("Usuario autorización", scenario.users.authorizer?.email),
        row("Usuario contador", scenario.users.accountant?.email),
        row("Gerente conta", scenario.users.accounting_manager?.email),
        row("Usuario tesorería", scenario.users.treasury?.email),
        row("Dirección", scenario.users.director?.email)
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
              <th>Aut.</th>
              <th>Ticket</th>
              <th>CFDI</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            ${expenses.map((expense) => `
              <tr>
                <td>${expense.merchant}</td>
                <td>${money(expense.amount)}</td>
                <td>${authBadge(expense)}</td>
                <td>${badge(expense.has_receipt)}</td>
                <td>${badge(expense.has_current_valid_cfdi)}</td>
                <td>${expenseStatusBadge(expense)}</td>
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

    function expenseStatusBadge(expense) {
      if (expense.is_rejected) {
        return "<span class='state bad'>Rechazado</span>";
      }
      if (expense.is_removed) {
        return "<span class='state bad'>Removido</span>";
      }
      return "<span class='state ok'>Activo</span>";
    }

    function authBadge(expense) {
      if (expense.is_rejected) {
        return "<span class='state bad'>Rechazado</span>";
      }
      if (!expense.requires_authorization) {
        return "<span class='state ok'>No requiere</span>";
      }
      return expense.is_authorized
        ? "<span class='state ok'>Autorizado</span>"
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
          ${row("Autorización", summary.ready_for_authorization_approval ? "Listo" : "Bloqueado")}
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

    function renderAuthState() {
      const label = authUser
        ? `${authUser.role} / ${authUser.email}`
        : "Sin sesión activa";
      $("#authState").innerHTML = row("Sesión", label);
    }

    function valueOrNull(selector) {
      const value = $(selector).value.trim();
      return value || null;
    }

    function scenarioSeedPayload() {
      return {
        reset_existing: $("#scenarioResetExisting").checked,
        store_code: $("#scenarioStoreCode").value,
        store_name: $("#scenarioStoreName").value,
        contact_email: valueOrNull("#scenarioStoreEmail"),
        period_name: $("#scenarioPeriodName").value,
        starts_on: $("#scenarioStartsOn").value,
        ends_on: $("#scenarioEndsOn").value,
        reported_total: valueOrNull("#scenarioReportedTotal"),
        expenses: [
          {
            merchant: $("#scenarioExpense1Merchant").value,
            amount: $("#scenarioExpense1Amount").value,
            spent_on: $("#scenarioExpense1Date").value,
            category: valueOrNull("#scenarioExpense1Category"),
            supplier_tax_id: "XAXX010101000",
            requires_authorization: false,
            create_receipt: true
          },
          {
            merchant: $("#scenarioExpense2Merchant").value,
            amount: $("#scenarioExpense2Amount").value,
            spent_on: $("#scenarioExpense2Date").value,
            category: valueOrNull("#scenarioExpense2Category"),
            supplier_tax_id: "XEXX010101000",
            requires_authorization: $("#scenarioExpense2RequiresAuthorization").checked,
            create_receipt: true
          }
        ]
      };
    }

    async function importDemo(dryRun) {
      const requestId = state?.scenario?.request_id;
      const form = new FormData();
      const csv = [
        "proveedor,importe,fecha,categoria,descripcion,rfc_proveedor,moneda,requiere_autorizacion",
        "HUD Importado Uno,100.00,2026-08-15,Papeleria,Import demo,XAXX010101000,MXN,no",
        "HUD Importado Dos,200.00,2026-08-16,Transporte,Import demo,XEXX010101000,MXN,si"
      ].join("\\n");
      form.append("dry_run", dryRun ? "true" : "false");
      form.append("file", new Blob([csv], { type: "text/csv" }), "hud-import.csv");
      return request(`/reimbursement-requests/${requestId}/expenses/import`, {
        method: "POST",
        body: form
      });
    }

    function roleEmail(role) {
      const email = state?.scenario?.users?.[role]?.email;
      if (!email) {
        throw { status: 409, payload: { message: "Crea el escenario HUD primero." } };
      }
      return email;
    }

    async function loginSelectedRole() {
      const role = $("#authRole").value;
      const payload = await jsonRequest("/auth/login", {
        email: roleEmail(role),
        password: "hud-password"
      });
      authToken = payload.access_token;
      authUser = payload.user;
      renderAuthState();
      return payload;
    }

    function scenarioRequestId() {
      const requestId = state?.scenario?.request_id;
      if (!requestId) {
        throw { status: 409, payload: { message: "No hay solicitud HUD activa." } };
      }
      return requestId;
    }

    function firstPendingAuthorizationExpense() {
      const expense = (state?.scenario?.expenses || []).find((item) =>
        item.requires_authorization && !item.is_authorized && !item.is_rejected
      );
      if (!expense) {
        throw { status: 409, payload: { message: "No hay producto pendiente de autorización." } };
      }
      return expense;
    }

    function firstReceiptAttachmentId() {
      const expense = (state?.scenario?.expenses || []).find((item) => item.receipt_attachment_id);
      if (!expense) {
        throw { status: 409, payload: { message: "No hay recibo descargable." } };
      }
      return expense.receipt_attachment_id;
    }

    async function authenticatedTransition() {
      return jsonAuthRequest(`/reimbursement-requests/${scenarioRequestId()}/transition/me`, {
        target_status: $("#authTransitionTarget").value,
        note: "Transición desde HUD con token."
      });
    }

    function executeUserFlowAction(action) {
      if (action.startsWith("transition:")) {
        const target = action.split(":")[1];
        return request(`/dev-hud/transition/${target}`, { method: "POST" });
      }
      const actions = {
        "seed-scenario": () => jsonRequest("/dev-hud/seed-demo", scenarioSeedPayload()),
        "automated-review": () => request("/dev-hud/automated-review", { method: "POST" }),
        "complete-cfdi": () => request("/dev-hud/complete-cfdi", { method: "POST" }),
        "authorize-expenses": () => request("/dev-hud/authorize-expenses", { method: "POST" }),
        "reject-product": () => request("/dev-hud/reject-authorization-expense", { method: "POST" }),
        "prepare-sap-policy": () => request("/dev-hud/prepare-sap-policy", { method: "POST" })
      };
      const handler = actions[action];
      if (!handler) {
        throw { status: 400, payload: { message: `Acción no soportada: ${action}` } };
      }
      return handler();
    }

    $("#refreshBtn").addEventListener("click", () => runAction("Estado actualizado", loadStatus));
    $("#seedBtn").addEventListener("click", () => runAction("Escenario creado", () =>
      jsonRequest("/dev-hud/seed-demo", scenarioSeedPayload())
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
    $("#automatedReviewBtn").addEventListener("click", () => runAction("Revision automatica", () =>
      request("/dev-hud/automated-review", { method: "POST" })
    ));
    $("#authorizeExpensesBtn").addEventListener("click", () => runAction("Gastos autorizados", () =>
      request("/dev-hud/authorize-expenses", { method: "POST" })
    ));
    $("#rejectAuthorizationExpenseBtn").addEventListener("click", () => runAction("Producto rechazado", () =>
      request("/dev-hud/reject-authorization-expense", { method: "POST" })
    ));
    $("#prepareSapPolicyBtn").addEventListener("click", () => runAction("Póliza SAP preparada", () =>
      request("/dev-hud/prepare-sap-policy", { method: "POST" })
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
        requires_authorization: $("#paymentRequiresAuthorization").checked,
        keep_reported_total_balanced: $("#paymentBalanced").checked
      })
    ));
    $$(".flow-btn").forEach((button) => {
      button.addEventListener("click", () => runAction(`Transición ${button.dataset.target}`, () =>
        request(`/dev-hud/transition/${button.dataset.target}`, { method: "POST" })
      ));
    });
    $$(".user-flow-btn").forEach((button) => {
      button.addEventListener("click", () =>
        runAction(button.textContent.trim(), () => executeUserFlowAction(button.dataset.action))
      );
    });
    $("#loginRoleBtn").addEventListener("click", () => runAction("Sesión iniciada", loginSelectedRole));
    $("#meBtn").addEventListener("click", () => runAction("Sesión actual", () =>
      request("/auth/me", { headers: authHeaders() })
    ));
    $("#authTransitionBtn").addEventListener("click", () => runAction("Transición autenticada", authenticatedTransition));
    $("#authAuthorizeBtn").addEventListener("click", () => runAction("Producto autorizado con token", () =>
      jsonAuthRequest(`/expenses/${firstPendingAuthorizationExpense().id}/authorize/me`, {
        note: "Autorizado desde HUD con token."
      })
    ));
    $("#authRejectBtn").addEventListener("click", () => runAction("Producto rechazado con token", () =>
      jsonAuthRequest(`/expenses/${firstPendingAuthorizationExpense().id}/reject/me`, {
        reason: "Rechazado desde HUD con token.",
        adjust_reported_total: true
      })
    ));
    $("#authSapBtn").addEventListener("click", () => runAction("SAP preparado con token", () =>
      jsonAuthRequest(`/reimbursement-requests/${scenarioRequestId()}/sap-policy/prepare/me`, {
        reference: "HUD-SAP-TOKEN",
        note: "Preparado desde HUD con token."
      })
    ));
    $("#outOfPeriodBtn").addEventListener("click", () => runExpectedFailure(
      "Gasto fuera de periodo bloqueado",
      () => jsonRequest("/dev-hud/payments", {
        merchant: "HUD Fuera de Periodo",
        amount: "10.00",
        spent_on: "2026-09-30",
        category: "prueba",
        keep_reported_total_balanced: false
      }),
      "PAYMENT_OUTSIDE_PERIOD"
    ));
    $("#downloadReceiptBtn").addEventListener("click", () => runAction("Recibo listo para descargar", async () => {
      const attachmentId = firstReceiptAttachmentId();
      const metadata = await request(`/attachments/${attachmentId}`);
      window.open(`${api}/attachments/${attachmentId}/download`, "_blank");
      return metadata;
    }));
    $("#missingAttachmentBtn").addEventListener("click", () => runExpectedFailure(
      "Archivo inexistente bloqueado",
      () => request("/attachments/00000000-0000-4000-8000-000000000000/download"),
      404
    ));

    loadStatus();
  </script>
</body>
</html>
"""
