import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import Grainient from './Grainient';
import { apiErrorMessage, confirmPasswordReset, requestPasswordReset } from '../lib/api';

function ConfirmPasswordReset() {
    const navigate = useNavigate();
    const location = useLocation();
    const email = location.state?.email || '';
    const [code, setCode] = useState('');
    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const sendCodeAgain = async () => {
        if (!email) {
            navigate('/recuperar-contrasena');
            return;
        }
        setError('');
        setMessage('');
        setLoading(true);
        try {
            await requestPasswordReset(email);
            setMessage('Se envió un código nuevo a tu correo.');
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError('');
        setMessage('');
        if (password !== passwordConfirm) {
            setError('Las contraseñas no coinciden.');
            return;
        }
        setLoading(true);
        try {
            await confirmPasswordReset(email, code, password);
            navigate('/login', {
                replace: true,
                state: { passwordReset: 'Contraseña actualizada. Ya puedes iniciar sesión.' },
            });
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    if (!email) {
        return (
            <div style={styles.simpleMessage}>
                <p>Primero solicita un código de recuperación.</p>
                <Link to="/recuperar-contrasena">Solicitar código</Link>
            </div>
        );
    }

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
                    <h2 style={styles.title}>Cambiar contraseña</h2>
                    <p style={styles.info}>
                        Escribe el código que recibiste en {email} y define una contraseña nueva.
                    </p>
                    <label style={styles.inputGroup}>
                        <span style={styles.label}>Código de 6 dígitos</span>
                        <input
                            type="text"
                            inputMode="numeric"
                            value={code}
                            onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                            style={styles.input}
                            autoComplete="one-time-code"
                            required
                        />
                    </label>
                    <label style={styles.inputGroup}>
                        <span style={styles.label}>Nueva contraseña</span>
                        <input
                            type="password"
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                            style={styles.input}
                            autoComplete="new-password"
                            minLength={8}
                            required
                        />
                    </label>
                    <label style={styles.inputGroup}>
                        <span style={styles.label}>Confirmar contraseña</span>
                        <input
                            type="password"
                            value={passwordConfirm}
                            onChange={(event) => setPasswordConfirm(event.target.value)}
                            style={styles.input}
                            autoComplete="new-password"
                            minLength={8}
                            required
                        />
                    </label>
                    {message && <div style={styles.message}>{message}</div>}
                    {error && <div style={styles.error}>{error}</div>}
                    <button type="submit" style={styles.button} disabled={loading}>
                        {loading ? 'Guardando...' : 'Cambiar contraseña'}
                    </button>
                    <button type="button" style={styles.secondaryButton} onClick={sendCodeAgain} disabled={loading}>
                        Reenviar código
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
    form: { display: 'flex', flexDirection: 'column', gap: '20px', backgroundColor: '#ffffff', border: '1px solid var(--sb-btnBorder)', borderRadius: '10px', padding: '40px', boxShadow: 'var(--shadow)' },
    logo: { height: '60px', width: 'auto', objectFit: 'contain', marginBottom: '15px' },
    title: { margin: 0, fontSize: '22px', color: 'var(--text-h)', textAlign: 'left' },
    info: { color: 'var(--text-muted, #5f5f5f)', fontSize: '13px', lineHeight: 1.4, textAlign: 'center' },
    inputGroup: { display: 'flex', flexDirection: 'column', gap: '10px' },
    label: { fontSize: '15px', fontWeight: 'bold', color: 'var(--text-WBtn)' },
    input: { border: '1px solid var(--border)', borderRadius: '8px', backgroundColor: '#ffffff', color: 'var(--text-h)', padding: '8px', fontSize: '14px' },
    error: { color: 'var(--text-denegada, #cc3030)', fontSize: '13px', textAlign: 'center', whiteSpace: 'pre-line' },
    message: { color: 'var(--text-h)', fontSize: '13px', textAlign: 'center' },
    button: { backgroundColor: 'var(--sb-sendBtnBg)', color: 'var(--text-CBtn)', border: 'none', borderRadius: '10px', padding: '10px 25px', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', boxShadow: 'var(--shadow)' },
    secondaryButton: { backgroundColor: 'transparent', color: 'var(--text-h)', border: '1px solid var(--border)', borderRadius: '10px', padding: '9px 25px', fontSize: '14px', cursor: 'pointer' },
    link: { color: 'var(--text-h)', fontSize: '13px', textAlign: 'center' },
    simpleMessage: { padding: '40px', textAlign: 'center' },
};

export default ConfirmPasswordReset;
