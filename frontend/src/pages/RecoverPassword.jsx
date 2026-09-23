import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import Grainient from './Grainient';
import { apiErrorMessage, requestPasswordReset } from '../lib/api';

function RecoverPassword() {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError('');
        setLoading(true);

        try {
            await requestPasswordReset(email);
            navigate('/confirmar-recuperacion', {
                state: { email: email.trim().toLowerCase() },
            });
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={styles.pageWrapper}>
            <div style={styles.backgroundCanvas}>
                <Grainient
                    color1="#ffe6e6"
                    color2="#ffb5b5"
                    color3="#bc8888"
                    timeSpeed={2.15}
                    colorBalance={0}
                    warpStrength={0.65}
                    warpFrequency={8}
                    warpSpeed={1.3}
                    warpAmplitude={15}
                    blendAngle={0}
                    blendSoftness={0.1}
                    rotationAmount={500}
                    noiseScale={1.5}
                    grainAmount={0.05}
                    grainScale={2}
                    grainAnimated={false}
                    contrast={1.5}
                    gamma={1.15}
                    saturation={1.5}
                    centerX={0}
                    centerY={0}
                    zoom={0.8}
                />
            </div>
            <div style={styles.container}>
                <form style={styles.form} onSubmit={handleSubmit}>
                    <img src="/LogotipoNega.png" alt="Logo" style={styles.logo} />
                    <h2 style={styles.title}>Recuperar contraseña</h2>
                    <p style={styles.info}>
                        Te enviaremos un código al correo asociado a tu cuenta.
                    </p>
                    <label style={styles.inputGroup}>
                        <span style={styles.label}>Correo</span>
                        <input
                            type="email"
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                            style={styles.input}
                            autoComplete="email"
                            required
                        />
                    </label>
                    {error && <div style={styles.error}>{error}</div>}
                    <button type="submit" style={styles.button} disabled={loading}>
                        {loading ? 'Enviando...' : 'Enviar código'}
                    </button>
                    <Link to="/login" style={styles.link}>Volver al inicio de sesión</Link>
                </form>
            </div>
        </div>
    );
}

const styles = {
    pageWrapper: {
        position: 'relative',
        width: '100%',
        minHeight: '100vh',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    backgroundCanvas: { position: 'absolute', inset: 0, zIndex: 1 },
    container: { maxWidth: '420px', zIndex: 10, width: '100%', padding: '100px', margin: '60px auto' },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        backgroundColor: '#ffffff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '40px',
        boxShadow: 'var(--shadow)',
    },
    logo: { height: '60px', width: 'auto', objectFit: 'contain', marginBottom: '15px' },
    title: { margin: 0, fontSize: '22px', color: 'var(--text-h)', textAlign: 'left' },
    info: { color: 'var(--text-muted, #5f5f5f)', fontSize: '13px', lineHeight: 1.4, textAlign: 'center' },
    inputGroup: { display: 'flex', flexDirection: 'column', gap: '10px' },
    label: { fontSize: '15px', fontWeight: 'bold', color: 'var(--text-WBtn)' },
    input: { border: '1px solid var(--border)', borderRadius: '8px', backgroundColor: '#ffffff', color: 'var(--text-h)', padding: '8px', fontSize: '14px' },
    error: { color: 'var(--text-denegada, #cc3030)', fontSize: '13px', textAlign: 'center', whiteSpace: 'pre-line' },
    button: { backgroundColor: 'var(--sb-sendBtnBg)', color: 'var(--text-CBtn)', border: 'none', borderRadius: '10px', padding: '10px 25px', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', boxShadow: 'var(--shadow)' },
    link: { color: 'var(--text-h)', fontSize: '13px', textAlign: 'center' },
};

export default RecoverPassword;
