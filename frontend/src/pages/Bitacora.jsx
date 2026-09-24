const auditItems = [
    {
        title: 'Quién cargó',
        description: 'Usuario que creó la solicitud o añadió documentos al gasto.',
    },
    {
        title: 'Quién validó',
        description: 'Usuario que revisó la información capturada y la evidencia cargada.',
    },
    {
        title: 'Quién autorizó o rechazó',
        description: 'Responsable que tomó la decisión y resultado de la revisión.',
    },
    {
        title: 'Quién editó monto, folio o documentos',
        description: 'Cambios importantes hechos después de la carga inicial.',
    },
    {
        title: 'Fecha y motivo',
        description: 'Momento del movimiento y explicación relacionada con la acción.',
    },
];

function Bitacora() {
    return (
        <main style={styles.container}>
            <section style={styles.header}>
                <span style={styles.kicker}>Auditoría visible</span>
                <h1 style={styles.title}>Bitácora de actividad</h1>
                <p style={styles.description}>
                    Ya hay historial interno, pero convendría mostrar mejor quién hizo cada
                    movimiento relevante dentro de una solicitud.
                </p>
            </section>

            <section style={styles.panel}>
                <div style={styles.panelHeader}>
                    <h2 style={styles.sectionTitle}>Información a mostrar</h2>
                    <p style={styles.sectionText}>
                        La bitácora debe ayudar a revisar el flujo completo sin depender de
                        validaciones ocultas o consultas técnicas.
                    </p>
                </div>

                <div style={styles.grid}>
                    {auditItems.map((item) => (
                        <article key={item.title} style={styles.card}>
                            <div style={styles.dot} />
                            <div>
                                <h3 style={styles.cardTitle}>{item.title}</h3>
                                <p style={styles.cardText}>{item.description}</p>
                            </div>
                        </article>
                    ))}
                </div>
            </section>
        </main>
    );
}

const styles = {
    container: {
        maxWidth: '1180px',
        margin: '0 auto',
        padding: '34px 28px 56px',
        color: '#252525',
    },
    header: {
        marginBottom: '24px',
        borderBottom: '1px solid var(--border, #f3c6cc)',
        paddingBottom: '20px',
    },
    kicker: {
        display: 'inline-block',
        color: 'var(--sb-primary, #e96f7d)',
        fontSize: '13px',
        fontWeight: 800,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        marginBottom: '10px',
    },
    title: {
        margin: 0,
        fontSize: '30px',
        lineHeight: 1.2,
        fontWeight: 800,
    },
    description: {
        maxWidth: '760px',
        margin: '12px 0 0',
        color: '#5f5f5f',
        fontSize: '16px',
        lineHeight: 1.55,
    },
    panel: {
        border: '1px solid var(--border, #f3c6cc)',
        borderRadius: '8px',
        background: '#fff',
        boxShadow: '0 10px 28px rgba(230, 112, 126, 0.08)',
        overflow: 'hidden',
    },
    panelHeader: {
        padding: '24px 26px 10px',
    },
    sectionTitle: {
        margin: 0,
        fontSize: '20px',
        fontWeight: 800,
    },
    sectionText: {
        margin: '8px 0 0',
        color: '#666',
        fontSize: '14px',
        lineHeight: 1.5,
    },
    grid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '14px',
        padding: '18px 26px 26px',
    },
    card: {
        display: 'flex',
        gap: '12px',
        minHeight: '108px',
        border: '1px solid #f5cbd1',
        borderRadius: '8px',
        padding: '16px',
        background: '#fffafa',
    },
    dot: {
        flex: '0 0 auto',
        width: '10px',
        height: '10px',
        borderRadius: '50%',
        marginTop: '6px',
        background: 'var(--sb-primary, #e96f7d)',
        boxShadow: '0 0 0 5px rgba(233, 111, 125, 0.12)',
    },
    cardTitle: {
        margin: 0,
        fontSize: '15px',
        fontWeight: 800,
        color: '#202020',
    },
    cardText: {
        margin: '7px 0 0',
        color: '#666',
        fontSize: '14px',
        lineHeight: 1.45,
    },
};

export default Bitacora;
