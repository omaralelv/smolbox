import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation} from 'react-router-dom';


const GASTOS_INICIALES = [
    
];

function SolicitudForm() {
    const navigate = useNavigate();

    // 1. DATOS AUTOMÁTICOS (Se llenan solos)
    const datosIniciales = {
        fecha: new Date().toLocaleDateString('es-MX', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            }),
        tienda: "T001",
        gerente: "Karen Ponce Hernández",
        cuentaBancaria: "101328508",
        estadoRegion: "CDMX"
    };

    // 2. ESTADOS PARA LA LISTA DE GASTOS Y FORMULARIO
    const [gastos, setGastos] = useState(() => {
        const guardados = localStorage.getItem('listaGastosSmolbox');
        return guardados ? JSON.parse(guardados) : GASTOS_INICIALES;
    });

    // AÑADIR GASTO A LA LISTA
    useEffect(() => {
  // 1. Intentamos leer si dejamos algún gasto guardado en el navegador
    const gastoGuardado = localStorage.getItem('pendienteGasto');

        if (gastoGuardado) {
            // 2. Convertimos el texto de regreso a un objeto de Javascript
            const nuevoGasto = JSON.parse(gastoGuardado);

            // 3. Lo agregamos al arreglo de la tabla
            setGastos(prevGastos => {
                const listaActualizada = [...prevGastos, nuevoGasto];
                localStorage.setItem('listaGastosSmolbox', JSON.stringify(listaActualizada));
                return listaActualizada;
            });

            // 4. Limpiamos la memoria para que no se vuelva a sumar si el usuario refresca (F5)
            localStorage.removeItem('pendienteGasto');

            console.log("✅ Gasto recuperado de localStorage e inyectado con éxito!");
        }
    }, []);


    // Estado para controlar la visibilidad del bloque de captura manual
    const [mostrarFormGasto, setMostrarFormGasto] = useState(false);
    
    // Estado para los inputs manuales del nuevo gasto
    const [nuevoMonto, setNuevoMonto] = useState('');
    const [nuevoTipo, setNuevoTipo] = useState('');
    const[nuevoFolio, setNuevoFolio] = useState('');

    // Categorías del menú desplegable
    const categoriasGasto = ["Sistemas", "Papelería", "Mantenimiento", "Transporte", "Otros"];

    // 3. FUNCIONES DE LÓGICA
    // QUITAR /  BORRAR DESPUÉS
    const handleAñadirGasto = (e) => {
        e.preventDefault();
        if (!nuevoMonto || isNaN(nuevoMonto) || parseFloat(nuevoMonto) <= 0) {
        alert("Por favor, ingresa un monto válido.");
        return;
        }

        const nuevoGastoItem = {
        id: gastos.length + 1,
        nombre: `Gasto ${gastos.length + 1}`,
        monto: parseFloat(nuevoMonto),
        tipo: nuevoTipo,
        folio: nuevoFolio,
        };

        setGastos([...gastos, nuevoGastoItem]);
        setNuevoMonto(''); // Limpiar input
        setMostrarFormGasto(false); // Ocultar bloque de insercción
    };

    // Calcular el TOTAL dinámicamente basándose en la lista actual
    const calcularTotal = () => {
        return gastos.reduce((sum, item) => sum + item.monto, 0).toFixed(2);
    };

    const handleEnviarSolicitud = () => {
        if (gastos.length === 0) {
            alert("Debes añadir al menos un gasto antes de enviar.");
        return;
        }

        // 1. Recuperamos las solicitudes existentes o iniciamos un arreglo nuevo
        /*const solicitudesGuardadas = JSON.parse(localStorage.getItem('bandejaSolicitudes')) || [
            { id: 'Solicitud 3', tienda: 'T-003', fecha: '12/08/2026', status: 'Aprobada' },
            { id: 'Solicitud 2', tienda: 'T-025', fecha: '10/08/2026', status: 'Pagada' },
            { id: 'Solicitud 1', tienda: 'T-009', fecha: '10/08/2026', status: 'Pagada' }
        ];*/

        // 2. Calculamos el nombre o número de la nueva solicitud
        //const numeroSolicitud = solicitudesGuardadas.length + 1;






// =========================================================================
        // GENERACIÓN DE FOLIO DINÁMICO: TIENDA-DDMMAAAA#
        // =========================================================================

        const codigoTienda = (datosIniciales.tienda || "T001").trim(); 

        // Formateador robusto de fecha
        const formatearFechaDDMMAAAA = (fechaStr) => {
            if (!fechaStr) {
                const hoy = new Date();
                const d = String(hoy.getDate()).padStart(2, '0');
                const m = String(hoy.getMonth() + 1).padStart(2, '0');
                const y = hoy.getFullYear();
                return `${d}${m}${y}`;
            }
            // Quita '/' y '-'
            const limpia = fechaStr.replace(/[-/]/g, '').trim();
            
            // Si viene en formato ISO (YYYY-MM-DD -> YYYYMMDD)
            if (fechaStr.includes('-') && limpia.length === 8) {
                const [y, m, d] = fechaStr.split('-');
                return `${d.padStart(2, '0')}${m.padStart(2, '0')}${y}`;
            }
            
            return limpia;
        };

        const fechaFormateada = formatearFechaDDMMAAAA(datosIniciales.fecha);

        // 1. Obtener historial fresco directamente de localStorage
        const solicitudesGuardadas = JSON.parse(localStorage.getItem('bandejaSolicitudes') || '[]');

        // 2. Filtrar solicitudes que coincidan en TIENDA y FECHA
        const solicitudesMismoDia = solicitudesGuardadas.filter((sol) => {
            const tiendaSol = (sol.tienda || '').trim();
            const fechaSol = (sol.fechaFormateada || formatearFechaDDMMAAAA(sol.fecha) || '').trim();

            const esMismaTienda = tiendaSol === codigoTienda;
            const esMismaFecha = fechaSol === fechaFormateada;

            console.log("Comparando registro previo:", {
                tiendaGuardada: tiendaSol,
                tiendaActual: codigoTienda,
                esMismaTienda,
                fechaGuardada: fechaSol,
                fechaActual: fechaFormateada,
                esMismaFecha
            });

            return esMismaTienda && esMismaFecha;
        });

        console.log("Coincidencias encontradas hoy para esta tienda:", solicitudesMismoDia.length);
        // 5. El consecutivo es el total del mismo día + 1
        const contadorDia = solicitudesMismoDia.length + 1;
        

        // 6. Generar el ID/Folio final (Ej. T001-140820261)
        const numeroSolicitud = `${codigoTienda}-${fechaFormateada}${contadorDia}`;










        const nuevaSolicitud = {
            id: numeroSolicitud,
            folio: numeroSolicitud,
            tienda: codigoTienda,
            status: 'En revisión', // ◄--- Estatus inicial
            fecha: new Date().toLocaleDateString(),
            fechaFormateada: fechaFormateada,
            gastos: gastos, // Todos los gastos cargados
            montoTotal: gastos.reduce((acc, curr) => acc + (parseFloat(curr.monto) || 0), 0)
        };

        // 3. Insertamos la nueva solicitud AL PRINCIPIO de la bandeja
        const listaActualizada = [nuevaSolicitud, ...solicitudesGuardadas];
        localStorage.setItem('bandejaSolicitudes', JSON.stringify(listaActualizada));

        // 4. Limpiamos el borrador de gastos de la pantalla actual
        localStorage.removeItem('listaGastosSmolbox');
        localStorage.removeItem('pendienteGasto');

        alert(`¡Solicitud ${nuevaSolicitud.id} enviada con éxito!`);

        // 5. Redirigimos a la Bandeja / Monitoreo
        navigate('/bandeja');

    };

    return (
        <div style={styles.container}>
        
        {/* TÍTULO Y BOTÓN DE AÑADIR */}
        <div style={styles.titleRow}>
            <h2 style={styles.mainTitle}>Solicitud de Reembolso</h2>
            <button 
            style={styles.añadirBtn} 
            onClick={() => {
                navigate('/gasto/nuevo')
                }
            }
            //onClick={() => setMostrarFormGasto(!mostrarFormGasto)}
            >
            Añadir Gasto
            </button>
        </div>

        {/* BLOQUE DE DATOS AUTOCOMPLETADOS (Campos Fijos) */}
        <div style={styles.gridAuto}>
            <div style={styles.inputGroup}>
            <label style={styles.label}>Fecha</label>
            <div style={styles.disabledInput}>{datosIniciales.fecha}</div>
            </div>
            <div style={styles.inputGroup}>
            <label style={styles.label}>Tienda</label>
            <div style={styles.disabledInput}>{datosIniciales.tienda}</div>
            </div>
            <div style={styles.inputGroup}>
            <label style={styles.label}>Gerente</label>
            <div style={styles.disabledInput}>{datosIniciales.gerente}</div>
            </div>
            <div style={styles.inputGroup}>
            <label style={styles.label}>Cuenta bancaria</label>
            <div style={styles.disabledInput}>{datosIniciales.cuentaBancaria}</div>
            </div>
            <div style={styles.inputGroup}>
            <label style={styles.label}>Estado</label>
            <div style={styles.disabledInput}>{datosIniciales.estadoRegion}</div>
            </div>
        </div>


        {/* TABLA / LISTADO DE GASTOS AGREGADOS */}
        <div style={styles.tableContainer}>
            <div style={styles.tableHeader}>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'center', flex: 1 }}></span>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'right', width: '700px' }}>MONTO</span>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'center', width: '400px', paddingLeft: '100px'}}>TIPO DE GASTO</span>
            <span style={{ flex: 2, textAlign: 'right', paddingLeft: '60px' }}>HERRAMIENTAS</span>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'center', width: '100px' }}></span>
            </div>

            {gastos.map((gasto) => (
            <div key={gasto.id} style={styles.tableRow}>
                <span style={{ fontWeight: 'bold', textAlign: 'left', flex: 1, paddingLeft: '20px' }}>{gasto.nombre}</span>
                <span style={{ textAlign: 'center', width: '200px', paddingLeft: '150px' }}>{gasto.monto.toFixed(2)}</span>
                <span style={{ textAlign: 'center', width: '280px'}}>{gasto.type || gasto.tipo}</span>
                
                <div style={styles.herramientasContainer}>
                    <button style={styles.iconBtn} title="Ver Vale">
                        <img src="/Vale.png" alt="Vale" style={styles.iconImg} />
                    </button>
                
                
                    <button style={styles.iconBtn} title="Ver Factura">
                        <img src="/Factura.png" alt="Factura" style={styles.iconImg} />
                    </button>
                
                
                    <button style={styles.iconBtn} title="Observaciones">
                        <img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} />
                    </button>
                </div>
            </div>
            ))}
        </div>

        {/* FOOTER DE TOTALES */}
        <div style={styles.totalRow}>
            <span style={styles.totalLabel}>TOTAL :</span>
            <span style={styles.totalAmount}>$ {calcularTotal()}</span>
        </div>


        {/* BARRA FIJA INFERIOR (Solo para esta pantalla) */}
        <div style={styles.fixedStickyFooter}>
            <button onClick={handleEnviarSolicitud} style={styles.enviarSolicitudBtnFixed}>
            Enviar Solicitud
            </button>
        </div>

    </div>
    );
    }

    // 🎨 ESTILOS INTEGRADOS CON TU INDEX.CSS
    const styles = {
    container: {
        maxWidth: '1000px',
        margin: '0 auto',
        padding: '20px',
        paddingBottom: '100px',
        textAlign: 'left',
    },
    titleRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '30px',
    },
    mainTitle: {
        margin: 0,
        fontSize: '24px',
    },
    añadirBtn: {
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-WBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        padding: '8px 24px',
        fontSize: '13px',
        fontWeight: '700',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s',
    },
    gridAuto: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '20px',
        marginBottom: '40px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '5px',
    },
    label: {
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        textAlign: 'center',
    },
    disabledInput: {
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '14px',
        textAlign: 'center',
        color: 'var(--text)',
    },
    manualForm: {
        backgroundColor: 'var(--sb-subhead)',
        border: '1px dashed var(--border)',
        borderRadius: '12px',
        padding: '10px',
        marginBottom: '30px',
        boxShadow: 'var(--shadow)',
    },
    subTitle: {
        margin: '0 0 15px 0',
        fontSize: '15px',
        color: 'var(--text-h)',
    },
    manualFormRow: {
        display: 'flex',
        gap: '20px',
        flexWrap: 'wrap',
    },
    manualInput: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '15px',
        width: '180px',
        textAlign: 'center',
        outline: 'none',
    },
    manualSelect: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '15px',
        width: '200px',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        outline: 'none',
    },
    manualFormActions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        marginTop: '15px',
    },
    tableContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginBottom: '20px',
    },
    tableHeader: {
        display: 'flex',
        padding: '0 10px',
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        letterSpacing: '0.5px',
    },
    tableHeaderCell: {
        display: 'inline-block',
    },
    tableRow: {
        display: 'flex',
        alignItems: 'center',
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '9px 10px',
        fontSize: '13px',
    },
    verDetalleLink: {
        width: '100px',
        textAlign: 'right',
        color: 'var(--text-WBtn)',
        fontWeight: 'bold',
        cursor: 'pointer',
        fontSize: '13px',
        paddingRight: '18px',
    },

    herramientasContainer: {
        flex: 2,
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        gap: '20px'
    },
    iconBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: 0,
        display: 'flex',
        alignItems: 'center',
        paddingRight: '5px',
    },
    iconImg: {
        width: '18px',
        height: '18px',
        objectFit: 'contain'
    },

    totalRow: {
        display: 'flex',
        alignItems: 'left',
        gap: '270px',
        paddingLeft: '30px',
        marginBottom: '5px',
    },
    totalLabel: {
        fontWeight: 'bold',
        fontSize: '16px',
        color: 'var(--text-h)',
    },
    totalAmount: {
        fontWeight: 'bold',
        fontSize: '16px',
        color: 'var(--text-h)',
    },

    fixedStickyFooter: {
        position: 'fixed',
        bottom: 0,
        left: 0,
        width: '100%',
        backgroundColor: 'var(--sb-subhead)', /* Usa el fondo blanco de tu index.css */
        boxShadow: '0 -4px 10px rgba(0, 0, 0, 0.05)', /* Una sombra sutil hacia arriba para separarlo del contenido */
        padding: '25px 0',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000, /* Se asegura de quedar por encima de las filas de los gastos */
        borderTop: '1px solid #fff0f0',
    },
    enviarSolicitudBtnFixed: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '10px',
        padding: '10px 25px', /* Un poco más ancho para que destaque en la barra inferior */
        marginBottom: '8px',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s ease',
    }
};

export default SolicitudForm;