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
    select,
    textarea {
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

    .session-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 10px;
    }

	    .session-actions .notice {
	      grid-column: 1 / -1;
	    }

	    .scenario-list {
	      display: grid;
	      gap: 10px;
	    }

	    .scenario-card {
	      width: 100%;
	      display: grid;
	      grid-template-columns: minmax(180px, 1.5fr) repeat(3, minmax(90px, 0.7fr));
	      align-items: center;
	      gap: 12px;
	      padding: 12px;
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      background: var(--panel);
	      color: var(--ink);
	      cursor: pointer;
	      text-align: left;
	    }

	    .scenario-card:hover {
	      border-color: #94a3b8;
	      background: #f8fafc;
	    }

	    .scenario-card.active {
	      border-color: var(--blue);
	      background: #eef5ff;
	      box-shadow: inset 3px 0 0 var(--blue);
	    }

	    .scenario-card strong,
	    .scenario-card span {
	      overflow-wrap: anywhere;
	    }

	    .scenario-card small {
	      display: block;
	      margin-top: 4px;
	      color: var(--muted);
	      font-size: 12px;
	    }

	    .scenario-card .metric-mini {
	      display: grid;
	      gap: 4px;
	    }

	    .scenario-card .metric-mini span {
	      color: var(--muted);
	      font-size: 11px;
	      font-weight: 760;
	      text-transform: uppercase;
	    }

	    .scenario-card .metric-mini strong {
	      font-size: 13px;
	    }

	    .product-tabs {
	      display: flex;
	      flex-wrap: wrap;
	      gap: 8px;
	      margin-bottom: 14px;
	    }

	    .product-tab {
	      min-height: 36px;
	      padding: 7px 11px;
	      border: 1px solid var(--line);
	      border-radius: 7px;
	      background: var(--panel);
	      color: var(--muted);
	      cursor: pointer;
	      font-size: 13px;
	      font-weight: 760;
	    }

	    .product-tab.active {
	      border-color: var(--blue);
	      background: #e8f0ff;
	      color: var(--blue);
	    }

	    .product-window {
	      overflow: hidden;
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      background: #fbfcfd;
	    }

	    .product-shell {
	      display: grid;
	      grid-template-columns: 190px minmax(0, 1fr);
	      min-height: 520px;
	    }

	    .product-sidebar {
	      padding: 16px;
	      border-right: 1px solid var(--line);
	      background: #eef3f7;
	    }

	    .product-logo {
	      display: block;
	      margin-bottom: 18px;
	      color: var(--ink);
	      font-size: 15px;
	      font-weight: 780;
	    }

	    .product-nav {
	      display: grid;
	      gap: 8px;
	    }

	    .product-nav-item {
	      padding: 9px 10px;
	      border-radius: 7px;
	      color: var(--muted);
	      font-size: 13px;
	      font-weight: 720;
	    }

	    .product-nav-item.active {
	      background: var(--panel);
	      color: var(--ink);
	    }

	    .product-main {
	      display: grid;
	      grid-template-rows: auto auto 1fr auto;
	      min-width: 0;
	      padding: 18px;
	      gap: 14px;
	    }

	    .product-titlebar,
	    .product-actions-bar {
	      display: flex;
	      align-items: flex-start;
	      justify-content: space-between;
	      gap: 12px;
	    }

	    .product-titlebar h3 {
	      font-size: 20px;
	      line-height: 1.2;
	    }

	    .metric-strip {
	      display: grid;
	      grid-template-columns: repeat(4, minmax(0, 1fr));
	      gap: 10px;
	    }

	    .metric {
	      min-height: 74px;
	      padding: 10px;
	      border: 1px solid var(--line);
	      border-radius: 7px;
	      background: var(--panel);
	    }

	    .metric span {
	      display: block;
	      color: var(--muted);
	      font-size: 12px;
	      font-weight: 720;
	      text-transform: uppercase;
	    }

	    .metric strong {
	      display: block;
	      margin-top: 8px;
	      overflow-wrap: anywhere;
	      font-size: 18px;
	      line-height: 1.1;
	    }

	    .product-workspace {
	      display: grid;
	      grid-template-columns: minmax(220px, 0.8fr) minmax(320px, 1.2fr);
	      gap: 14px;
	      min-width: 0;
	    }

	    .product-pane {
	      min-width: 0;
	      padding: 12px;
	      border: 1px solid var(--line);
	      border-radius: 7px;
	      background: var(--panel);
	    }

	    .product-pane-head {
	      display: flex;
	      align-items: center;
	      justify-content: space-between;
	      gap: 10px;
	      margin-bottom: 10px;
	    }

	    .request-tile {
	      display: grid;
	      gap: 7px;
	      padding: 11px;
	      border: 1px solid var(--line);
	      border-radius: 7px;
	      background: #f8fafc;
	    }

	    .request-tile.active {
	      border-color: #94b5ef;
	      background: #eef5ff;
	    }

	    .product-detail-grid {
	      display: grid;
	      grid-template-columns: repeat(2, minmax(0, 1fr));
	      gap: 10px;
	    }

	    .detail-cell {
	      min-width: 0;
	      padding: 10px;
	      border-bottom: 1px solid var(--line);
	    }

	    .detail-cell span {
	      display: block;
	      color: var(--muted);
	      font-size: 12px;
	      font-weight: 720;
	      text-transform: uppercase;
	    }

	    .detail-cell strong {
	      display: block;
	      margin-top: 6px;
	      overflow-wrap: anywhere;
	      font-size: 13px;
	    }

	    .product-expenses {
	      grid-column: 1 / -1;
	    }

	    .product-actions-bar {
	      align-items: center;
	      padding-top: 4px;
	      border-top: 1px solid var(--line);
	    }

	    .product-action-list {
	      display: flex;
	      flex-wrap: wrap;
	      gap: 8px;
	      justify-content: flex-end;
	    }

	    .expense-action-list {
	      display: flex;
	      flex-wrap: wrap;
	      gap: 6px;
	    }

	    .expense-action-list .btn {
	      min-height: 30px;
	      padding: 5px 8px;
	      font-size: 12px;
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

    .textarea {
      min-height: 86px;
      resize: vertical;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      line-height: 1.45;
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

    .rule-list {
      display: grid;
      gap: 12px;
    }

    .rule-card {
      display: grid;
      gap: 10px;
      padding: 12px 0;
      border-top: 1px solid var(--line);
    }

    .rule-card:first-child {
      border-top: 0;
      padding-top: 0;
    }

    @media (max-width: 1080px) {
      .stats {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }

	      .layout,
	      .split,
	      .scenario-card,
	      .product-shell,
	      .product-workspace {
	        grid-template-columns: 1fr;
	      }

	      .product-sidebar {
	        border-right: 0;
	        border-bottom: 1px solid var(--line);
	      }

	      .product-nav {
	        grid-template-columns: repeat(4, minmax(0, 1fr));
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
	      .form-grid,
	      .metric-strip,
	      .product-detail-grid,
	      .product-nav {
	        grid-template-columns: 1fr 1fr;
	      }

	      .scenario-card {
	        grid-template-columns: 1fr;
	      }

	      .product-titlebar,
	      .product-actions-bar {
	        align-items: flex-start;
	        flex-direction: column;
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
              <h2>1. Escenario HUD</h2>
              <p class="subtle">Datos aislados con prefijo HUD.</p>
            </div>
	            <div class="toolbar">
	              <button class="btn" id="refreshBtn">Actualizar</button>
	              <button class="btn primary" id="seedBtn">Crear escenario</button>
	              <button class="btn success" id="seedBulkBtn">Crear demo masivo</button>
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
              <input id="scenarioResetExisting" type="checkbox" />
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
		              <h2>2. Solicitudes HUD</h2>
		              <p class="subtle">Selecciona una solicitud para probar su flujo.</p>
		            </div>
		          </div>
		          <div class="scenario-list" id="scenarioList"></div>
		        </section>

		        <section class="card panel">
		          <div class="panel-head">
		            <div>
		              <h2>3. Vista producto</h2>
		              <p class="subtle">Ventanas por rol para probar como usuario final.</p>
		            </div>
		          </div>
	          <div class="product-tabs" id="productTabs"></div>
	          <div class="product-window" id="productPreview"></div>
	        </section>

		        <section class="card panel">
		          <div class="panel-head">
		            <div>
		              <h2>4. Flujo usuario final</h2>
		              <p class="subtle">Recorrido por rol con acciones equivalentes al proceso real.</p>
		            </div>
		          </div>
          <div class="user-flow">
            <div class="user-flow-row">
              <div class="role">
                <strong>Tienda</strong>
                <span>Captura caja chica</span>
              </div>
              <div class="task">Crea la solicitud, carga gastos, comprobantes y CFDI, y la envía para revisión.</div>
              <div class="actions">
                <button class="btn primary user-flow-btn" data-action="seed-scenario">Crear solicitud</button>
                <button class="btn success user-flow-btn" data-action="complete-cfdi">Completar CFDI</button>
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
                <button class="btn danger user-flow-btn" data-action="transition:rejected">Rechazar solicitud sin monto</button>
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
                <button class="btn success user-flow-btn" data-action="record-payment">Registrar pago</button>
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
              <h2>Herramientas de datos</h2>
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
              <h2>Flujo técnico rápido</h2>
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
            <button class="btn success" id="recordPaymentBtn">Registrar pago</button>
            <button class="btn success flow-btn" data-target="closed">Cerrar</button>
          </div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Datos de la solicitud</h2>
              <p class="subtle">Filas actuales de la solicitud demo.</p>
            </div>
            <div class="toolbar">
              <button class="btn warning" id="importDryRunBtn">CSV dry run</button>
              <button class="btn" id="importRealBtn">Importar CSV</button>
              <button class="btn" id="automatedReviewBtn">Ejecutar automaticos</button>
              <button class="btn success" id="completeCfdiBtn">Completar CFDI demo</button>
              <button class="btn warning" id="outOfPeriodBtn">Probar fuera de periodo</button>
              <button class="btn warning" id="missingAttachmentBtn">Probar archivo 404</button>
            </div>
          </div>
          <div id="expenses"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Agregar gasto de prueba</h2>
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
            <button class="btn primary" id="createPaymentBtn">Agregar gasto</button>
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
              <h2>Sesión técnica</h2>
              <p class="subtle">Acciones visibles según rol y estado actual.</p>
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
            <button class="btn primary" id="loginRoleBtn">Iniciar o cambiar sesión</button>
            <button class="btn" id="meBtn">Ver sesión</button>
            <button class="btn" id="logoutBtn">Cerrar sesión</button>
          </div>
          <div id="authState"></div>

          <h3 style="margin-top: 16px;">Acciones disponibles</h3>
          <div id="authActions" class="session-actions"></div>
        </section>

        <section class="card panel">
          <div class="panel-head">
            <div>
              <h2>Reglas de negocio</h2>
              <p class="subtle">Configuración técnica editable por admin para validaciones del flujo.</p>
            </div>
          </div>
          <div id="businessRules" class="rule-list"></div>
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
	    let activeProductRole = "store";
	    let activeRequestId = window.localStorage.getItem("smolbox.devHud.activeRequestId");

	    const $ = (selector) => document.querySelector(selector);
	    const $$ = (selector) => Array.from(document.querySelectorAll(selector));
	    const productRoles = [
	      {
	        id: "store",
	        label: "Tienda",
	        title: "Caja chica",
	        subtitle: "Captura de gastos y envio",
	        queueStatuses: ["draft", "correction_required"],
	        nav: ["Bandeja", "Captura", "Comprobantes", "Historial"]
	      },
	      {
	        id: "system",
	        label: "Validación",
	        title: "Revisión automática",
	        subtitle: "CFDI, comprobantes, totales y alertas",
	        queueStatuses: ["draft", "submitted", "authorization_review", "authorized", "under_accounting_review"],
	        nav: ["Resumen", "Alertas", "CFDI", "OCR"]
	      },
	      {
	        id: "authorizer",
	        label: "Autorización",
	        title: "Autorización por producto",
	        subtitle: "Decisión sobre gastos especiales",
	        queueStatuses: ["submitted", "authorization_review"],
	        nav: ["Bandeja", "Gastos", "Decisiones", "Historial"]
	      },
	      {
	        id: "accountant",
	        label: "Contabilidad",
	        title: "Revisión contable",
	        subtitle: "Factura, CFDI, formato y póliza",
	        queueStatuses: ["authorized", "under_accounting_review", "accounting_reviewed"],
	        nav: ["Bandeja", "Documentos", "Póliza SAP", "Historial"]
	      },
	      {
	        id: "accounting_manager",
	        label: "Gerente",
	        title: "Aprobación contable",
	        subtitle: "Control antes de tesorería",
	        queueStatuses: ["accounting_reviewed", "accounting_manager_review"],
	        nav: ["Bandeja", "Solicitud", "Riesgos", "Historial"]
	      },
	      {
	        id: "treasury",
	        label: "Tesorería",
	        title: "Pago",
	        subtitle: "Liberación, dirección y registro de pago",
	        queueStatuses: [
	          "accounting_manager_approved",
	          "treasury_review",
	          "direction_approved",
	          "approved_for_payment",
	          "paid"
	        ],
	        nav: ["Bandeja", "Pago", "Comprobante", "Historial"]
	      },
	      {
	        id: "director",
	        label: "Dirección",
	        title: "Aprobación final",
	        subtitle: "Autorización antes del pago",
	        queueStatuses: ["direction_review"],
	        nav: ["Bandeja", "Solicitud", "Aprobación", "Historial"]
	      }
	    ];
	    const allHumanRoles = [
      "store",
      "authorizer",
      "accountant",
      "accounting_manager",
      "treasury",
      "director",
      "admin"
    ];
    const roleActions = [
      {
        id: "transition:submitted",
        label: "Enviar solicitud",
        roles: ["store"],
        statuses: ["draft", "correction_required"],
        style: "primary"
      },
      {
        id: "transition:authorization_review",
        label: "Abrir autorización",
        roles: ["authorizer"],
        statuses: ["submitted"]
      },
      {
        id: "authorize-expense",
        label: "Autorizar producto",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        style: "success"
      },
      {
        id: "reject-expense",
        label: "Rechazar producto",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        style: "warning"
      },
      {
        id: "transition:rejected",
        label: "Rechazar solicitud sin monto",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        style: "danger",
        requiresNoPayable: true
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
        statuses: ["authorized"]
      },
      {
        id: "transition:correction_required",
        label: "Pedir corrección",
        roles: ["authorizer"],
        statuses: ["authorization_review"],
        style: "warning"
      },
      {
        id: "transition:correction_required",
        label: "Pedir corrección",
        roles: ["accountant"],
        statuses: ["under_accounting_review"],
        style: "warning"
      },
      {
        id: "remove-expense",
        label: "Quitar gasto",
        roles: ["accountant"],
        statuses: ["under_accounting_review"],
        style: "warning"
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
        id: "transition:correction_required",
        label: "Pedir corrección",
        roles: ["accounting_manager"],
        statuses: ["accounting_manager_review"],
        style: "warning"
      },
      {
        id: "remove-expense",
        label: "Quitar gasto",
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
        id: "transition:correction_required",
        label: "Pedir corrección",
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
        id: "transition:correction_required",
        label: "Pedir corrección",
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
        id: "view-queue",
        label: "Ver mi cola",
        roles: allHumanRoles,
        statuses: null
      },
      {
        id: "download-receipt",
        label: "Descargar recibo",
        roles: allHumanRoles,
        statuses: null,
        requiresReceipt: true
      }
    ];

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

	    function specificErrorPayload(error) {
	      const payload = error?.payload || {};
	      const detail = payload.detail;
	      const detailIsObject = detail && typeof detail === "object" && !Array.isArray(detail);
	      const code = detailIsObject && detail.code
	        ? detail.code
	        : payload.code || `HTTP_${error?.status || "ERROR"}`;
	      const message = detailIsObject && detail.message
	        ? detail.message
	        : typeof detail === "string"
	          ? detail
	          : payload.message || error?.message || "Error inesperado";
	      const errors = detailIsObject && detail.errors
	        ? detail.errors
	        : Array.isArray(detail)
	          ? detail.map((item) => ({
	              field: (item.loc || []).join("."),
	              message: item.msg,
	              type: item.type
	            }))
	          : undefined;

	      return {
	        ok: false,
	        status: error?.status || null,
	        code,
	        message,
	        ...(errors ? { errors } : {}),
	        raw: payload
	      };
	    }

	    function writeErrorConsole(label, error) {
	      writeConsole(label, specificErrorPayload(error));
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

    function jsonAuthPatchRequest(path, payload) {
      return request(path, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });
    }

	    function escapeHtml(value) {
	      return String(value ?? "")
	        .replace(/&/g, "&amp;")
	        .replace(/</g, "&lt;")
	        .replace(/>/g, "&gt;")
	        .replace(/"/g, "&quot;")
	        .replace(/'/g, "&#039;");
	    }

	    function selectedRequestQuery() {
	      return activeRequestId ? `?request_id=${encodeURIComponent(activeRequestId)}` : "";
	    }

	    function selectedDevHudPath(path) {
	      return `${path}${selectedRequestQuery()}`;
	    }

	    function persistActiveRequestId() {
	      if (activeRequestId) {
	        window.localStorage.setItem("smolbox.devHud.activeRequestId", activeRequestId);
	      } else {
	        window.localStorage.removeItem("smolbox.devHud.activeRequestId");
	      }
	    }

	    function syncActiveRequestFromState() {
	      if (state?.scenario?.request_id) {
	        activeRequestId = state.scenario.request_id;
	      } else if (!(state?.scenarios || []).length) {
	        activeRequestId = null;
	      }
	      persistActiveRequestId();
	    }

	    async function loadStatus() {
	      try {
	        state = await request(selectedDevHudPath("/dev-hud/status"));
	        if (activeRequestId && !state?.scenario?.exists && (state?.scenarios || []).length) {
	          activeRequestId = state.scenarios[0].request_id;
	          persistActiveRequestId();
	          state = await request(selectedDevHudPath("/dev-hud/status"));
	        }
	        syncActiveRequestFromState();
	        render();
	      } catch (error) {
	        writeErrorConsole("No se pudo cargar el estado", error);
	      }
	    }

    async function runAction(label, fn) {
      setBusy(true);
      try {
        const payload = await fn();
        writeConsole(label, payload);
        await loadStatus();
	      } catch (error) {
	        writeErrorConsole(`${label} falló`, error);
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
	        writeErrorConsole(ok ? label : `${label} falló distinto`, error);
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
      const hasSession = Boolean(authToken);
      const canEditRules = Boolean(authToken && authUser?.role === "admin");
      const isEditable = isEditableScenarioStatus();
      $$(
        ".flow-btn, #importDryRunBtn, #importRealBtn, #automatedReviewBtn, #completeCfdiBtn, " +
        "#createPaymentBtn, #authorizeExpensesBtn, #rejectAuthorizationExpenseBtn, " +
        "#prepareSapPolicyBtn, #recordPaymentBtn"
      ).forEach((button) => {
        button.disabled = !hasScenario;
      });
      $$("#importDryRunBtn, #importRealBtn, #completeCfdiBtn, #createPaymentBtn").forEach((button) => {
        button.disabled = !hasScenario || !isEditable;
      });
      $("#recordPaymentBtn").disabled = !hasScenario || state?.scenario?.status !== "approved_for_payment";
	      $$(".user-flow-btn").forEach((button) => {
	        button.disabled = !isUserFlowActionAvailable(button.dataset.action);
	      });
	      $$(".product-action-btn").forEach((button) => {
	        button.disabled = !isProductActionAvailable(
	          button.dataset.productRole,
	          button.dataset.productAction
	        );
	      });
	      $("#assignUserBtn").disabled = !hasStores || !hasUsers;
      $("#loginRoleBtn").disabled = !hasScenario;
      $("#meBtn").disabled = !authToken;
      $("#logoutBtn").disabled = !authToken;
      $$(".auth-action-btn").forEach((button) => {
        button.disabled = !hasScenario || !hasSession;
      });
      $$("#outOfPeriodBtn, #missingAttachmentBtn").forEach((button) => {
        button.disabled = !hasScenario;
      });
      $$(".business-rule-save").forEach((button) => {
        button.disabled = !canEditRules;
      });
    }

    function isEditableScenarioStatus() {
      return ["draft", "correction_required"].includes(state?.scenario?.status);
    }

    function isUserFlowActionAvailable(action) {
      const hasScenario = Boolean(state?.scenario?.exists);
      if (action === "seed-scenario") return true;
      if (!hasScenario) return false;
      if (action === "complete-cfdi") return isEditableScenarioStatus();
      if (action === "record-payment") return state?.scenario?.status === "approved_for_payment";
      if (action === "transition:rejected") {
        return (
          state?.scenario?.status === "authorization_review" &&
          state?.scenario?.summary?.expense_count === 0
        );
      }
      return true;
    }

    function isProductActionAvailable(role, actionId) {
      const hasScenario = Boolean(state?.scenario?.exists);
      if (actionId === "seed-scenario") return true;
      if (!hasScenario) return false;
      if (actionId === "complete-cfdi") return isEditableScenarioStatus();
      if (actionId === "record-payment") return state?.scenario?.status === "approved_for_payment";
      const action = roleActions.find((item) => item.id === actionId);
      if (!action) return true;
      return isRoleActionAvailableFor(role, action);
    }

    function isRoleActionAvailableFor(role, action) {
      const status = state?.scenario?.status;
      if (!status) return false;
      const roleAllowed = role === "admin" || action.roles.includes(role);
      const statusAllowed = action.statuses === null || action.statuses.includes(status);
      const sapReady = !action.requiresSap || Boolean(state?.scenario?.sap_policy?.is_prepared);
      const receiptReady = !action.requiresReceipt || hasReceiptAttachment();
      const noPayableReady = !action.requiresNoPayable || state?.scenario?.summary?.expense_count === 0;
      return roleAllowed && statusAllowed && sapReady && receiptReady && noPayableReady;
    }

    function render() {
	      renderStats();
	      renderScenario();
	      renderScenarioList();
	      renderProductPreview();
	      renderWorkspaceSelectors();
      renderExpenses();
      renderValidation();
      renderAudit();
      renderAuthState();
      renderRoleActions();
      renderBusinessRules();
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

	    function renderScenarioList() {
	      const scenarios = state?.scenarios || [];
	      if (!scenarios.length) {
	        $("#scenarioList").innerHTML = `
	          <div class="notice">No hay solicitudes HUD creadas.</div>
	        `;
	        return;
	      }
	      $("#scenarioList").innerHTML = scenarios.map((scenario) => `
	        <button
	          class="scenario-card ${scenario.request_id === activeRequestId ? "active" : ""}"
	          data-request-id="${escapeHtml(scenario.request_id)}"
	        >
	          <span>
	            <strong>${escapeHtml(scenario.store_code)} / ${escapeHtml(scenario.period_name)}</strong>
	            <small>${escapeHtml(scenario.store_name)}</small>
	          </span>
	          <span class="metric-mini">
	            <span>Estado</span>
	            <strong>${escapeHtml(scenario.status)}</strong>
	          </span>
	          <span class="metric-mini">
	            <span>Total</span>
	            <strong>${money(scenario.calculated_total)}</strong>
	          </span>
	          <span class="metric-mini">
	            <span>Alertas</span>
	            <strong>${scenario.issue_count || 0}</strong>
	          </span>
	        </button>
	      `).join("");
	    }

	    function renderProductPreview() {
	      renderProductTabs();
	      const scenario = state?.scenario;
	      const config = productRoleConfig(activeProductRole);
	      if (!scenario?.exists) {
	        $("#productPreview").innerHTML = `
	          <div class="product-shell">
	            ${productSidebar(config)}
	            <div class="product-main">
	              <div class="product-titlebar">
	                <div>
	                  <h3>${escapeHtml(config.title)}</h3>
	                  <p class="subtle">${escapeHtml(config.subtitle)}</p>
	                </div>
	                <span class="state warn">Sin solicitud</span>
	              </div>
	              <div class="notice">Crea un escenario para ver la ventana con datos.</div>
	              <div></div>
	              <div class="product-actions-bar">
	                <p class="subtle">Ambiente HUD</p>
	                <div class="product-action-list">
	                  ${productActionButton("store", "seed-scenario", "Crear solicitud", "primary")}
	                </div>
	              </div>
	            </div>
	          </div>
	        `;
	        return;
	      }

	      const summary = scenario.summary || {};
	      const queueActive = config.queueStatuses.includes(scenario.status);
	      const actions = productActionsForRole(config.id);
	      $("#productPreview").innerHTML = `
	        <div class="product-shell">
	          ${productSidebar(config)}
	          <div class="product-main">
	            <div class="product-titlebar">
	              <div>
	                <h3>${escapeHtml(config.title)}</h3>
	                <p class="subtle">${escapeHtml(config.subtitle)}</p>
	              </div>
	              <span class="state ${queueActive ? "ok" : "warn"}">
	                ${queueActive ? "En bandeja" : "Sin pendiente"}
	              </span>
	            </div>

	            <div class="metric-strip">
	              <div class="metric">
	                <span>Estado</span>
	                <strong>${escapeHtml(scenario.status)}</strong>
	              </div>
	              <div class="metric">
	                <span>Total</span>
	                <strong>${money(summary.reported_total)}</strong>
	              </div>
	              <div class="metric">
	                <span>Validación</span>
	                <strong>${summary.issues?.length ? `${summary.issues.length} alerta(s)` : "Sin alertas"}</strong>
	              </div>
	              <div class="metric">
	                <span>Póliza SAP</span>
	                <strong>${scenario.sap_policy?.is_prepared ? "Preparada" : "Pendiente"}</strong>
	              </div>
	            </div>

	            <div class="product-workspace">
	              <section class="product-pane">
	                <div class="product-pane-head">
	                  <h3>Bandeja</h3>
	                  <span class="state ${queueActive ? "ok" : "warn"}">${queueActive ? "1" : "0"}</span>
	                </div>
	                ${productRequestTile(scenario, queueActive)}
	              </section>
	              <section class="product-pane">
	                <div class="product-pane-head">
	                  <h3>Solicitud</h3>
	                  <span class="state">${escapeHtml(scenario.store_code)}</span>
	                </div>
	                ${productDetailGrid(scenario)}
	              </section>
	              <section class="product-pane product-expenses">
	                <div class="product-pane-head">
	                  <h3>Gastos</h3>
	                  <span class="subtle">${scenario.expenses?.length || 0} registro(s)</span>
	                </div>
		                ${productExpensesTable(scenario.expenses || [], config.id)}
	              </section>
	            </div>

	            <div class="product-actions-bar">
	              <p class="subtle">${escapeHtml(productRoleUserLabel(config.id))}</p>
	              <div class="product-action-list">
	                ${actions.length
	                  ? actions.map((action) =>
	                      productActionButton(config.id, action.id, action.label, action.style || "")
	                    ).join("")
	                  : "<span class='subtle'>Sin acciones para este estado.</span>"
	                }
	              </div>
	            </div>
	          </div>
	        </div>
	      `;
	    }

	    function renderProductTabs() {
	      $("#productTabs").innerHTML = productRoles.map((role) => `
	        <button class="product-tab ${role.id === activeProductRole ? "active" : ""}" data-product-role="${role.id}">
	          ${escapeHtml(role.label)}
	        </button>
	      `).join("");
	    }

	    function productRoleConfig(roleId) {
	      return productRoles.find((role) => role.id === roleId) || productRoles[0];
	    }

	    function productSidebar(config) {
	      return `
	        <aside class="product-sidebar">
	          <strong class="product-logo">Smolbox</strong>
	          <nav class="product-nav">
	            ${config.nav.map((item, index) => `
	              <span class="product-nav-item ${index === 0 ? "active" : ""}">${escapeHtml(item)}</span>
	            `).join("")}
	          </nav>
	        </aside>
	      `;
	    }

	    function productRequestTile(scenario, queueActive) {
	      const summary = scenario.summary || {};
	      return `
	        <div class="request-tile ${queueActive ? "active" : ""}">
	          <strong>${escapeHtml(scenario.period_name)}</strong>
	          <span class="subtle">${escapeHtml(scenario.store_name)} / ${money(summary.calculated_total)}</span>
	          <span class="state ${queueActive ? "ok" : "warn"}">${escapeHtml(scenario.status)}</span>
	        </div>
	      `;
	    }

	    function productDetailGrid(scenario) {
	      const summary = scenario.summary || {};
	      return `
	        <div class="product-detail-grid">
	          ${detailCell("Tienda", `${scenario.store_code} / ${scenario.store_name}`)}
	          ${detailCell("Periodo", scenario.period_name)}
	          ${detailCell("Reportado", money(summary.reported_total))}
	          ${detailCell("Calculado", money(summary.calculated_total))}
	          ${detailCell("Diferencia", money(summary.difference))}
	          ${detailCell("CFDI pendientes", summary.missing_cfdi_expense_ids?.length || 0)}
	          ${detailCell("Autorización pendiente", summary.missing_authorization_expense_ids?.length || 0)}
	          ${detailCell("Póliza SAP", scenario.sap_policy?.is_prepared ? scenario.sap_policy.reference : "Pendiente")}
	        </div>
	      `;
	    }

	    function detailCell(label, value) {
	      return `
	        <div class="detail-cell">
	          <span>${escapeHtml(label)}</span>
	          <strong>${escapeHtml(value)}</strong>
	        </div>
	      `;
	    }

	    function productExpensesTable(expenses, role) {
	      if (!expenses.length) {
	        return "<p class='subtle'>Sin gastos.</p>";
	      }
	      return `
	        <table class="table">
	          <thead>
	            <tr>
	              <th>Proveedor</th>
	              <th>Monto</th>
	              <th>Aut.</th>
	              <th>Ticket</th>
	              <th>CFDI</th>
	              <th>Estado</th>
		              <th>Acciones</th>
	            </tr>
	          </thead>
	          <tbody>
	            ${expenses.map((expense) => `
	              <tr>
	                <td>${escapeHtml(expense.merchant)}</td>
	                <td>${money(expense.amount)}</td>
	                <td>${authBadge(expense)}</td>
	                <td>${badge(expense.has_receipt)}</td>
	                <td>${badge(expense.has_current_valid_cfdi)}</td>
	                <td>${expenseStatusBadge(expense)}</td>
		                <td>${productExpenseActions(expense, role)}</td>
	              </tr>
	            `).join("")}
	          </tbody>
	        </table>
	      `;
	    }

	    function productExpenseActions(expense, role) {
	      const actions = [];
	      if (
	        role === "authorizer" &&
	        state?.scenario?.status === "authorization_review" &&
	        expense.requires_authorization &&
	        !expense.is_authorized &&
	        !expense.is_rejected &&
	        !expense.is_removed
	      ) {
	        actions.push(expenseActionButton(role, "authorize", expense.id, "Autorizar", "success"));
	        actions.push(expenseActionButton(role, "reject", expense.id, "Rechazar", "warning"));
	      }
	      if (
	        ["accountant", "accounting_manager"].includes(role) &&
	        ["under_accounting_review", "accounting_manager_review"].includes(state?.scenario?.status) &&
	        !expense.is_removed &&
	        !expense.is_rejected
	      ) {
	        actions.push(expenseActionButton(role, "remove", expense.id, "Quitar", "warning"));
	        actions.push(expenseActionButton(role, "observe", expense.id, "Observar", ""));
	      }
	      if (expense.receipt_attachment_id && role !== "system") {
	        actions.push(expenseActionButton(role, "download-receipt", expense.id, "Recibo", ""));
	      }
	      if (!actions.length) {
	        return "<span class='subtle'>-</span>";
	      }
	      return `<div class="expense-action-list">${actions.join("")}</div>`;
	    }

	    function expenseActionButton(role, actionId, expenseId, label, style) {
	      return `
	        <button
	          class="btn ${escapeHtml(style)} expense-action-btn"
	          data-product-role="${escapeHtml(role)}"
	          data-expense-action="${escapeHtml(actionId)}"
	          data-expense-id="${escapeHtml(expenseId)}"
	        >
	          ${escapeHtml(label)}
	        </button>
	      `;
	    }

	    function productActionsForRole(role) {
	      if (role === "system") {
	        return [
	          {
	            id: "automated-review",
	            label: "Revisar automáticamente",
	            style: ""
	          },
	          {
	            id: "complete-cfdi",
	            label: "Completar CFDI",
	            style: "success"
	          }
	        ].filter((action) => isProductActionAvailable(role, action.id));
	      }
	      const actions = roleActions.filter((action) => isRoleActionAvailableFor(role, action));
	      if (role === "store" && isProductActionAvailable(role, "complete-cfdi")) {
	        actions.splice(1, 0, {
	          id: "complete-cfdi",
	          label: "Completar CFDI",
	          style: "success"
	        });
	      }
	      return actions;
	    }

	    function productActionButton(role, actionId, label, style) {
	      const disabled = isProductActionAvailable(role, actionId) ? "" : "disabled";
	      return `
	        <button
	          class="btn ${escapeHtml(style)} product-action-btn"
	          data-product-role="${escapeHtml(role)}"
	          data-product-action="${escapeHtml(actionId)}"
	          ${disabled}
	        >
	          ${escapeHtml(label)}
	        </button>
	      `;
	    }

	    function productRoleUserLabel(role) {
	      if (role === "system") return "Validación automática";
	      const email = state?.scenario?.users?.[role]?.email;
	      return email ? `${role} / ${email}` : role;
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
        ? `${authUser.role} / ${authUser.email} / ${state?.scenario?.status || "sin estado"}`
        : "Sin sesión activa";
      $("#authState").innerHTML = row("Sesión", label);
    }

    function renderRoleActions() {
      if (!authToken || !authUser) {
        $("#authActions").innerHTML = `
          <div class="notice">Inicia sesión para ver acciones por rol.</div>
        `;
        return;
      }

      const actions = availableRoleActions();
      if (!actions.length) {
        $("#authActions").innerHTML = `
          <div class="notice">
            Sin acciones disponibles para ${escapeHtml(authUser.role)}
            en estado ${escapeHtml(state?.scenario?.status || "-")}.
          </div>
        `;
        return;
      }

      $("#authActions").innerHTML = actions.map((action) => `
        <button class="btn ${action.style || ""} auth-action-btn" data-auth-action="${action.id}">
          ${escapeHtml(action.label)}
        </button>
      `).join("");
    }

    function availableRoleActions() {
      const status = state?.scenario?.status;
      if (!status) return [];
      return roleActions.filter((action) => {
        const roleAllowed = authUser?.role === "admin" || action.roles.includes(authUser?.role);
        const statusAllowed = action.statuses === null || action.statuses.includes(status);
        const sapReady = !action.requiresSap || Boolean(state?.scenario?.sap_policy?.is_prepared);
        const receiptReady = !action.requiresReceipt || hasReceiptAttachment();
        const noPayableReady = !action.requiresNoPayable || state?.scenario?.summary?.expense_count === 0;
        return roleAllowed && statusAllowed && sapReady && receiptReady && noPayableReady;
      });
    }

    function hasReceiptAttachment() {
      return (state?.scenario?.expenses || []).some((item) =>
        item.receipt_attachment_id && !item.is_removed && !item.is_rejected
      );
    }

    function renderBusinessRules() {
      const rules = state?.business_rules || [];
      if (!rules.length) {
        $("#businessRules").innerHTML = "<p class='subtle'>Sin reglas configuradas.</p>";
        return;
      }
      const canEdit = authUser?.role === "admin";

      $("#businessRules").innerHTML = rules.map((rule) => `
        <article class="rule-card">
          <div>
            <h3>${escapeHtml(rule.name)}</h3>
            <p class="subtle mono">${escapeHtml(rule.code)}</p>
          </div>
          ${canEdit ? editableBusinessRule(rule) : readonlyBusinessRule(rule)}
        </article>
      `).join("");
    }

    function editableBusinessRule(rule) {
      return `
        <label class="field">
          <span>Descripción</span>
          <textarea class="input textarea" data-rule-description="${escapeHtml(rule.code)}">${escapeHtml(rule.description)}</textarea>
        </label>
        <label class="field">
          <span>Valor JSON</span>
          <textarea class="input textarea" data-rule-value="${escapeHtml(rule.code)}">${escapeHtml(JSON.stringify(rule.value || {}, null, 2))}</textarea>
        </label>
        <label class="checkline">
          <input data-rule-active="${escapeHtml(rule.code)}" type="checkbox" ${rule.is_active ? "checked" : ""} />
          Regla activa
        </label>
        <div class="toolbar">
          <button class="btn primary business-rule-save" data-rule-code="${escapeHtml(rule.code)}">
            Guardar regla
          </button>
        </div>
      `;
    }

    function readonlyBusinessRule(rule) {
      return `
        ${row("Estado", rule.is_active ? "Activa" : "Inactiva")}
        ${row("Valor", escapeHtml(JSON.stringify(rule.value || {}, null, 2)))}
      `;
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

		    async function seedScenario() {
		      const payload = await jsonRequest("/dev-hud/seed-demo", scenarioSeedPayload());
		      activeRequestId = payload.scenario?.request_id || activeRequestId;
		      persistActiveRequestId();
		      return payload;
		    }

		    async function seedBulkScenario() {
		      const payload = await jsonRequest("/dev-hud/seed-bulk-demo", {
		        reset_existing: true,
		        request_count: 24,
		        store_count: 8
		      });
		      activeRequestId = payload.scenario?.request_id || activeRequestId;
		      persistActiveRequestId();
		      return payload;
		    }

	    async function resetHudData() {
	      const payload = await request("/dev-hud/reset-demo", { method: "POST" });
	      activeRequestId = null;
	      persistActiveRequestId();
	      return payload;
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

	    async function loginProductRole(role) {
	      const payload = await jsonRequest("/auth/login", {
	        email: roleEmail(role),
	        password: "hud-password"
	      });
	      authToken = payload.access_token;
	      authUser = payload.user;
	      $("#authRole").value = role;
	      renderAuthState();
	      renderRoleActions();
	      return payload;
	    }

    async function logoutRole() {
      const previousUser = authUser;
      authToken = null;
      authUser = null;
      render();
      return { message: "Sesión cerrada", previous_user: previousUser };
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

    function firstActiveExpense() {
      const expense = (state?.scenario?.expenses || []).find((item) =>
        !item.is_removed && !item.is_rejected
      );
      if (!expense) {
        throw { status: 409, payload: { message: "No hay gasto activo disponible." } };
      }
      return expense;
    }

	    function firstReceiptAttachmentId() {
	      const expense = (state?.scenario?.expenses || []).find((item) =>
	        item.receipt_attachment_id && !item.is_removed && !item.is_rejected
	      );
      if (!expense) {
        throw { status: 409, payload: { message: "No hay recibo descargable." } };
      }
	      return expense.receipt_attachment_id;
	    }

	    function expenseById(expenseId) {
	      const expense = (state?.scenario?.expenses || []).find((item) => item.id === expenseId);
	      if (!expense) {
	        throw {
	          status: 404,
	          payload: {
	            detail: {
	              code: "HUD_EXPENSE_NOT_FOUND",
	              message: "No se encontro el gasto seleccionado."
	            }
	          }
	        };
	      }
	      return expense;
	    }

    function businessRulePayload(ruleCode) {
      const description = $(`[data-rule-description="${ruleCode}"]`).value.trim();
      const rawValue = $(`[data-rule-value="${ruleCode}"]`).value.trim();
      let parsedValue = {};
      try {
        parsedValue = rawValue ? JSON.parse(rawValue) : {};
      } catch {
        throw { status: 400, payload: { message: "El valor de la regla debe ser JSON válido." } };
      }
      return {
        description,
        value: parsedValue,
        is_active: $(`[data-rule-active="${ruleCode}"]`).checked
      };
    }

    async function transitionWithToken(targetStatus) {
      return jsonAuthRequest(`/reimbursement-requests/${scenarioRequestId()}/transition/me`, {
        target_status: targetStatus,
        note: "Transición desde HUD con token."
      });
    }

    async function removeExpenseWithToken() {
      return jsonAuthRequest(`/expenses/${firstActiveExpense().id}/remove/me`, {
        reason: "Gasto quitado desde HUD con token.",
        adjust_reported_total: true
      });
    }

    async function registerPaymentWithToken() {
      return jsonAuthRequest(`/reimbursement-requests/${scenarioRequestId()}/payments/me`, {
        reference: `HUD-PAGO-${Date.now()}`,
        payment_method: "transfer",
        note: "Pago registrado desde HUD con token."
      });
    }

    async function registerPaymentAsDemoTreasury() {
      const login = await jsonRequest("/auth/login", {
        email: roleEmail("treasury"),
        password: "hud-password"
      });
      return request(`/reimbursement-requests/${scenarioRequestId()}/payments/me`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${login.access_token}`
        },
        body: JSON.stringify({
          reference: `HUD-PAGO-${Date.now()}`,
          payment_method: "transfer",
          note: "Pago registrado desde flujo usuario final HUD."
        })
      });
    }

	    async function downloadReceiptWithToken() {
	      return downloadAttachmentWithToken(firstReceiptAttachmentId());
	    }

	    async function downloadReceiptByExpenseWithToken(expenseId) {
	      const expense = expenseById(expenseId);
	      if (!expense.receipt_attachment_id) {
	        throw {
	          status: 409,
	          payload: {
	            detail: {
	              code: "HUD_RECEIPT_NOT_FOUND",
	              message: "El gasto seleccionado no tiene recibo."
	            }
	          }
	        };
	      }
	      return downloadAttachmentWithToken(expense.receipt_attachment_id);
	    }

	    async function downloadAttachmentWithToken(attachmentId) {
	      const response = await fetch(`${api}/attachments/${attachmentId}/download/me`, {
	        headers: authHeaders()
	      });
      if (!response.ok) {
        const text = await response.text();
        let payload = text;
        try {
          payload = text ? JSON.parse(text) : {};
        } catch {
          payload = { raw: text };
        }
        throw { status: response.status, payload };
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 30000);
	      return {
	        attachment_id: attachmentId,
	        content_type: blob.type,
	        size_bytes: blob.size
	      };
	    }

    async function viewWorkQueueWithToken() {
      return request("/work-queue/me", { headers: authHeaders() });
    }

    function executeAuthAction(actionId) {
      if (actionId.startsWith("transition:")) {
        return transitionWithToken(actionId.split(":")[1]);
      }
      const actions = {
        "authorize-expense": () => jsonAuthRequest(
          `/expenses/${firstPendingAuthorizationExpense().id}/authorize/me`,
          { note: "Autorizado desde HUD con token." }
        ),
        "reject-expense": () => jsonAuthRequest(
          `/expenses/${firstPendingAuthorizationExpense().id}/reject/me`,
          {
            reason: "Rechazado desde HUD con token.",
            adjust_reported_total: true
          }
        ),
        "remove-expense": removeExpenseWithToken,
        "prepare-sap": () => jsonAuthRequest(
          `/reimbursement-requests/${scenarioRequestId()}/sap-policy/prepare/me`,
          {
            reference: "HUD-SAP-TOKEN",
            note: "Preparado desde HUD con token."
          }
        ),
        "record-payment": registerPaymentWithToken,
        "download-receipt": downloadReceiptWithToken,
        "view-queue": viewWorkQueueWithToken
      };
      const handler = actions[actionId];
      if (!handler) {
        throw { status: 400, payload: { message: `Acción no soportada: ${actionId}` } };
      }
      return handler();
    }

	    function executeUserFlowAction(action) {
	      if (action.startsWith("transition:")) {
	        const target = action.split(":")[1];
	        return request(selectedDevHudPath(`/dev-hud/transition/${target}`), { method: "POST" });
      }
      const actions = {
        "seed-scenario": seedScenario,
        "automated-review": () => request(selectedDevHudPath("/dev-hud/automated-review"), { method: "POST" }),
        "complete-cfdi": () => request(selectedDevHudPath("/dev-hud/complete-cfdi"), { method: "POST" }),
        "authorize-expenses": () => request(selectedDevHudPath("/dev-hud/authorize-expenses"), { method: "POST" }),
        "reject-product": () => request(selectedDevHudPath("/dev-hud/reject-authorization-expense"), { method: "POST" }),
        "prepare-sap-policy": () => request(selectedDevHudPath("/dev-hud/prepare-sap-policy"), { method: "POST" }),
        "record-payment": registerPaymentAsDemoTreasury
      };
      const handler = actions[action];
      if (!handler) {
        throw { status: 400, payload: { message: `Acción no soportada: ${action}` } };
	      }
	      return handler();
	    }

		    async function executeProductAction(role, actionId) {
		      if (["seed-scenario", "complete-cfdi", "automated-review"].includes(actionId)) {
		        return executeUserFlowAction(actionId);
		      }
		      await loginProductRole(role);
		      return executeAuthAction(actionId);
		    }

		    async function executeExpenseAction(role, actionId, expenseId) {
		      await loginProductRole(role);
		      const actions = {
		        authorize: () => jsonAuthRequest(`/expenses/${expenseId}/authorize/me`, {
		          note: "Autorizado por fila desde HUD."
		        }),
		        reject: () => jsonAuthRequest(`/expenses/${expenseId}/reject/me`, {
		          reason: "Rechazado por fila desde HUD.",
		          adjust_reported_total: true
		        }),
		        remove: () => jsonAuthRequest(`/expenses/${expenseId}/remove/me`, {
		          reason: "Gasto quitado por fila desde HUD.",
		          adjust_reported_total: true
		        }),
		        observe: () => jsonAuthRequest(`/expenses/${expenseId}/observation/me`, {
		          note: "Observacion registrada por fila desde HUD."
		        }),
		        "download-receipt": () => downloadReceiptByExpenseWithToken(expenseId)
		      };
		      const handler = actions[actionId];
		      if (!handler) {
		        throw { status: 400, payload: { message: `Acción de gasto no soportada: ${actionId}` } };
		      }
		      return handler();
		    }

		    $("#refreshBtn").addEventListener("click", () => runAction("Estado actualizado", loadStatus));
		    $("#seedBtn").addEventListener("click", () => runAction("Escenario creado", seedScenario));
		    $("#seedBulkBtn").addEventListener("click", () => runAction("Demo masivo creado", seedBulkScenario));
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
	      runAction("HUD limpiado", resetHudData);
	    });
	    $("#completeCfdiBtn").addEventListener("click", () => runAction("CFDI demo completado", () =>
	      request(selectedDevHudPath("/dev-hud/complete-cfdi"), { method: "POST" })
	    ));
	    $("#automatedReviewBtn").addEventListener("click", () => runAction("Revision automatica", () =>
	      request(selectedDevHudPath("/dev-hud/automated-review"), { method: "POST" })
	    ));
	    $("#authorizeExpensesBtn").addEventListener("click", () => runAction("Gastos autorizados", () =>
	      request(selectedDevHudPath("/dev-hud/authorize-expenses"), { method: "POST" })
	    ));
	    $("#rejectAuthorizationExpenseBtn").addEventListener("click", () => runAction("Producto rechazado", () =>
	      request(selectedDevHudPath("/dev-hud/reject-authorization-expense"), { method: "POST" })
	    ));
	    $("#prepareSapPolicyBtn").addEventListener("click", () => runAction("Póliza SAP preparada", () =>
	      request(selectedDevHudPath("/dev-hud/prepare-sap-policy"), { method: "POST" })
	    ));
    $("#importDryRunBtn").addEventListener("click", () => runAction("CSV dry run", () =>
      importDemo(true)
    ));
    $("#importRealBtn").addEventListener("click", () => runAction("CSV importado", () =>
      importDemo(false)
    ));
	    $("#createPaymentBtn").addEventListener("click", () => runAction("Gasto creado", () =>
	      jsonRequest(selectedDevHudPath("/dev-hud/payments"), {
	        merchant: $("#paymentMerchant").value,
	        amount: $("#paymentAmount").value,
        spent_on: $("#paymentDate").value,
        category: $("#paymentCategory").value || null,
        requires_authorization: $("#paymentRequiresAuthorization").checked,
        keep_reported_total_balanced: $("#paymentBalanced").checked
      })
    ));
    $("#recordPaymentBtn").addEventListener("click", () => runAction("Pago registrado", registerPaymentAsDemoTreasury));
	    $$(".flow-btn").forEach((button) => {
	      button.addEventListener("click", () => runAction(`Transición ${button.dataset.target}`, () =>
	        request(selectedDevHudPath(`/dev-hud/transition/${button.dataset.target}`), { method: "POST" })
	      ));
	    });
	    $$(".user-flow-btn").forEach((button) => {
	      button.addEventListener("click", () =>
	        runAction(button.textContent.trim(), () => executeUserFlowAction(button.dataset.action))
	      );
	    });
	    $("#scenarioList").addEventListener("click", (event) => {
	      const button = event.target.closest(".scenario-card");
	      if (!button) return;
	      activeRequestId = button.dataset.requestId;
	      persistActiveRequestId();
	      runAction("Solicitud seleccionada", async () => ({ request_id: activeRequestId }));
	    });
	    $("#productTabs").addEventListener("click", (event) => {
	      const button = event.target.closest(".product-tab");
	      if (!button) return;
	      activeProductRole = button.dataset.productRole;
	      renderProductPreview();
	      applyButtonState();
	    });
		    $("#productPreview").addEventListener("click", (event) => {
		      const expenseButton = event.target.closest(".expense-action-btn");
		      if (expenseButton) {
		        runAction(expenseButton.textContent.trim(), () =>
		          executeExpenseAction(
		            expenseButton.dataset.productRole,
		            expenseButton.dataset.expenseAction,
		            expenseButton.dataset.expenseId
		          )
		        );
		        return;
		      }
		      const button = event.target.closest(".product-action-btn");
		      if (!button) return;
		      runAction(button.textContent.trim(), () =>
	        executeProductAction(button.dataset.productRole, button.dataset.productAction)
	      );
	    });
    $("#loginRoleBtn").addEventListener("click", () => runAction("Sesión iniciada", loginSelectedRole));
    $("#meBtn").addEventListener("click", () => runAction("Sesión actual", () =>
      request("/auth/me", { headers: authHeaders() })
    ));
    $("#logoutBtn").addEventListener("click", () => runAction("Sesión cerrada", logoutRole));
    $("#authActions").addEventListener("click", (event) => {
      const button = event.target.closest(".auth-action-btn");
      if (!button) return;
      runAction(button.textContent.trim(), () => executeAuthAction(button.dataset.authAction));
    });
    $("#outOfPeriodBtn").addEventListener("click", () => runExpectedFailure(
	      "Gasto fuera de periodo bloqueado",
	      () => jsonRequest(selectedDevHudPath("/dev-hud/payments"), {
	        merchant: "HUD Fuera de Periodo",
        amount: "10.00",
        spent_on: "2026-09-30",
        category: "prueba",
        keep_reported_total_balanced: false
      }),
      "PAYMENT_OUTSIDE_PERIOD"
    ));
    $("#missingAttachmentBtn").addEventListener("click", () => runExpectedFailure(
      "Archivo inexistente bloqueado",
      () => request("/attachments/00000000-0000-4000-8000-000000000000/download"),
      404
    ));
    $("#businessRules").addEventListener("click", (event) => {
      const button = event.target.closest(".business-rule-save");
      if (!button) return;
      const ruleCode = button.dataset.ruleCode;
      runAction(`Regla ${ruleCode} guardada`, () =>
        jsonAuthPatchRequest(`/business-rules/${ruleCode}`, businessRulePayload(ruleCode))
      );
    });

    loadStatus();
  </script>
</body>
</html>
"""
