import { useState } from 'react';

import {
    apiErrorMessage,
    completeNewPasswordLogin,
    currentStoredRole,
    login,
} from '../lib/api';

import Grainient from './Grainient';


function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
    const [cognitoChallenge, setCognitoChallenge] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const redirectByRole = (response) => {
        const rolBackend = response?.context?.currentRole || response?.user?.role || response?.role || currentStoredRole() || '';
        const rolActual = String(rolBackend).toLowerCase().trim();

        if (rolActual === 'supervisor') {
            window.location.href = '/autorizacion';
        } else {
            window.location.href = '/bandeja';
        }
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (cognitoChallenge) {
                if (newPassword !== newPasswordConfirm) {
                    setError('Las contraseñas no coinciden.');
                    return;
                }
                const response = await completeNewPasswordLogin(
                    cognitoChallenge.email,
                    newPassword,
                    cognitoChallenge.session,
                );
                redirectByRole(response);
                return;
            }

            const response = await login(email, password);
            if (response?.challengeName === 'NEW_PASSWORD_REQUIRED') {
                setCognitoChallenge(response);
                setPassword('');
                setError('');
                return;
            }
            redirectByRole(response);
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={styles.pageWrapper}>
            {/* FONDO ANIMADO GRAINIENT */}
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
                <img 
                    src="/LogotipoNega.png" 
                    alt="Logo" 
                    style={styles.logo} 
                />
                <h2 style={styles.title}>
                    {cognitoChallenge ? 'Crear nueva contraseña' : 'Iniciar sesión'}
                </h2>
                {cognitoChallenge && (
                    <div style={styles.info}>
                        Tu usuario requiere una nueva contraseña para continuar.
                    </div>
                )}
                <div style={styles.inputGroup}>
                    <label style={styles.label}>Correo</label>
                    <input
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        style={styles.input}
                        disabled={Boolean(cognitoChallenge)}
                        required
                    />
                </div>
                {cognitoChallenge ? (
                    <>
                        <div style={styles.inputGroup}>
                            <label style={styles.label}>Nueva contraseña</label>
                            <input
                                type="password"
                                value={newPassword}
                                onChange={(event) => setNewPassword(event.target.value)}
                                style={styles.input}
                                required
                            />
                        </div>
                        <div style={styles.inputGroup}>
                            <label style={styles.label}>Confirmar contraseña</label>
                            <input
                                type="password"
                                value={newPasswordConfirm}
                                onChange={(event) => setNewPasswordConfirm(event.target.value)}
                                style={styles.input}
                                required
                            />
                        </div>
                    </>
                ) : (
                    <div style={styles.inputGroup}>
                        <label style={styles.label}>Contraseña</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                            style={styles.input}
                            required
                        />
                    </div>
                )}
                {error && <div style={styles.error}>{error}</div>}
                <button type="submit" style={styles.button} disabled={loading}>
                    {loading
                        ? 'Procesando...'
                        : cognitoChallenge
                            ? 'Guardar contraseña'
                            : 'Entrar'}
                </button>
            </form>
        </div>



        </div>
    );
}



const styles = {
    // Wrapper de pantalla completa
    pageWrapper: {
        position: 'relative',
        width: '100%',
        minHeight: '100vh',
        
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    // El canvas de Grainient cubre todo el fondo
    backgroundCanvas: {
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 1, // Fondo
    },

    logo: {
        height: '60px',          
        width: 'auto',
        alignSelf: 'left',     
        objectFit: 'contain',
        marginBottom: '15px',
    },


    container: {
        maxWidth: '420px',
        zIndex: 10, // Encima del canvas
        width: '100%',
        padding: '100px',margin: '60px auto',
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        backgroundColor:'#ffffff',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '40px',
        boxShadow: 'var(--shadow)',
    },
    title: {
        margin: 0,
        fontSize: '22px',
        color: 'var(--text-h)',
        textAlign: 'left',
        paddingLeft: '10px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
    },
    label: {
        fontSize: '15px',
        fontWeight: 'bold',
        color: 'var(--text-WBtn)',
        textAlign: 'left',
        paddingLeft: '10px',
    },
    input: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        backgroundColor: '#ffffff',
        color: 'var(--text-h)',
        padding: '8px',
        fontSize: '14px',
        outline: 'none',
    },
    error: {
        color: 'var(--text-denegada, #cc3030)',
        fontSize: '13px',
        textAlign: 'center',
    },
    info: {
        color: 'var(--text-muted, #5f5f5f)',
        fontSize: '13px',
        lineHeight: 1.4,
        textAlign: 'center',
    },
    button: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '10px',
        padding: '10px 25px',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
    },
};

export default Login;
