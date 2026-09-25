import { useState, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import Grainient from './Grainient';
import { apiErrorMessage, confirmPasswordReset, requestPasswordReset } from '../lib/api';

function ConfirmPasswordReset() {
    const navigate = useNavigate();
    const location = useLocation();
    const email = location.state?.email || '';
    //const [code, setCode] = useState('');
    const [otp, setOtp] = useState(['', '', '', '', '', '']);
    const inputsRef = useRef([]);

    const [password, setPassword] = useState('');
    const [passwordConfirm, setPasswordConfirm] = useState('');
    const [showPassword, setShowPassword] = useState(false); // Estado para visibilidad
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);



    // Maneja la escritura individual y pegado de código
    const handleOtpChange = (value, index) => {
        const cleanValue = value.replace(/\D/g, '');
        if (!cleanValue && value !== '') return;

        const newOtp = [...otp];

        // Manejo si el usuario pega un código completo (ej. 6 dígitos juntos)
        if (cleanValue.length > 1) {
            const pastedDigits = cleanValue.slice(0, 6).split('');
            for (let i = 0; i < 6; i++) {
                newOtp[i] = pastedDigits[i] || '';
            }
            setOtp(newOtp);
            const focusIndex = Math.min(pastedDigits.length, 5);
            inputsRef.current[focusIndex]?.focus();
            return;
        }

        newOtp[index] = cleanValue;
        setOtp(newOtp);

        // Avanzar automáticamente al siguiente campo
        if (cleanValue && index < 5) {
            inputsRef.current[index + 1]?.focus();
        }
    };

    // Maneja borrado con Backspace y navegación por teclado
    const handleKeyDown = (event, index) => {
        if (event.key === 'Backspace') {
            if (!otp[index] && index > 0) {
                inputsRef.current[index - 1]?.focus();
            }
        } else if (event.key === 'ArrowLeft' && index > 0) {
            inputsRef.current[index - 1]?.focus();
        } else if (event.key === 'ArrowRight' && index < 5) {
            inputsRef.current[index + 1]?.focus();
        }
    };


    
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

/*const handleSubmit = async (event) => {
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
    };*/

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError('');
        setMessage('');

        const fullCode = otp.join('');
        if (fullCode.length < 6) {
            setError('Ingresa el código completo de 6 dígitos.');
            return;
        }

        if (password !== passwordConfirm) {
            setError('Las contraseñas no coinciden.');
            return;
        }

        setLoading(true);
        try {
            await confirmPasswordReset(email, fullCode, password);
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
                    <Link to="/login" style={{...styles.link, textAlign: 'left'}}>🡨 Volver a Inicio de Sesión</Link>
                    <h2 style={styles.title}>Cambiar Contraseña</h2>
                    <p style={styles.info}>
                        Escribe el código que recibiste en {email} y define una contraseña nueva.
                    </p>
                    <label style={styles.inputGroup}>
                        <span style={styles.label}>Código de 6 dígitos</span>
                        


                        <div style={styles.otpContainer}>
                            {otp.map((digit, index) => (
                                <input
                                    key={index}
                                    ref={(el) => (inputsRef.current[index] = el)}
                                    type="text"
                                    inputMode="numeric"
                                    maxLength={6}
                                    value={digit}
                                    onChange={(e) => handleOtpChange(e.target.value, index)}
                                    onKeyDown={(e) => handleKeyDown(e, index)}
                                    style={styles.otpInput}
                                    autoComplete="one-time-code"
                                    required
                                />
                            ))}
                        </div>




                    </label>
                    <label style={styles.inputGroup}>
                        <span style={styles.label}>Nueva contraseña</span>
                        <input
                            type={showPassword ? 'text' : 'password'}
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
                            type={showPassword ? 'text' : 'password'}
                            value={passwordConfirm}
                            onChange={(event) => setPasswordConfirm(event.target.value)}
                            style={styles.input}
                            autoComplete="new-password"
                            minLength={8}
                            required
                        />
                    </label>

                    {/* CHECKBOX MOSTRAR CONTRASEÑA */}
                    <label style={styles.checkboxLabel}>
                        <input
                            type="checkbox"
                            checked={showPassword}
                            onChange={(e) => setShowPassword(e.target.checked)}
                            style={{
                                ...styles.checkbox,
                                backgroundColor: showPassword ? 'var(--sb-btnBorder)' : '#ffffff',
                                borderColor: showPassword ? 'var(--sb-btnBorder)' : 'var(--border)',
                                boxShadow: showPassword ? 'inset 0 0 0 3px #ffffff' : 'none',
                            }}
                        />
                        <span>Mostrar contraseña</span>
                    </label>

                    {message && <div style={styles.message}>{message}</div>}
                    {error && <div style={styles.error}>{error}</div>}
                    <button type="submit" style={styles.button} disabled={loading}>
                        {loading ? 'Guardando...' : 'Cambiar contraseña'}
                    </button>
                    <button type="button" style={styles.secondaryButton} onClick={sendCodeAgain} disabled={loading}>
                        Reenviar código
                    </button>
                </form>
            </div>
        </div>
    );
}

const styles = {
    pageWrapper: {
        position: 'relative',
        width: '100%',
        height: '100svh',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxSizing: 'border-box',
    },
    backgroundCanvas: { position: 'absolute', inset: 0, zIndex: 1 },
    container: { zIndex: 10, width: 'min(420px, calc(100% - 32px))', padding: '20px 0px', boxSizing: 'border-box' },
    form: { display: 'flex', flexDirection: 'column', gap: '15px', backgroundColor: '#ffffff', border: '1px solid var(--sb-btnBorder)', borderRadius: '10px', padding: '30px', boxShadow: 'var(--shadow)' },
    logo: { height: '60px', width: 'auto', objectFit: 'contain', marginBottom: '15px' },
    title: { margin: 0, fontSize: '22px', color: 'var(--text-h)', textAlign: 'left' },
    info: { color: 'var(--text-muted, #5f5f5f)', fontSize: '13px', lineHeight: 1.4, textAlign: 'left' },
    inputGroup: { display: 'flex', flexDirection: 'column', gap: '10px' },
    label: { fontSize: '15px', fontWeight: 'bold', color: 'var(--text-WBtn)' },
    input: { border: '1px solid var(--border)', borderRadius: '8px', backgroundColor: '#ffffff', color: 'var(--text-h)', padding: '10px', fontSize: '14px', textAlign: 'center'},
    error: { color: 'var(--text-denegada, #cc3030)', fontSize: '13px', textAlign: 'center', whiteSpace: 'pre-line' },
    message: { color: 'var(--text-h)', fontSize: '13px', textAlign: 'center' },
    button: { backgroundColor: 'var(--sb-sendBtnBg)', color: 'var(--text-CBtn)', border: 'none', borderRadius: '10px', padding: '10px 25px', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', boxShadow: 'var(--shadow)' },
    secondaryButton: { backgroundColor: 'transparent', color: 'var(--text-h)', border: '1px solid var(--border)', borderRadius: '10px', padding: '9px 25px', fontSize: '14px', cursor: 'pointer' },
    link: { 
        color: 'var(--sb-btnBorder)',
        fontSize: '13px',
        fontWeight:'400',
        textAlign: 'center', 
        textDecoration: 'none',
    },

    // ESTILOS PARA LOS CUADRITOS OTP
    otpContainer: {
        display: 'flex',
        justifyContent: 'space-between',
        gap: '0px',
    },
    otpInput: {
        width: '40px',
        height: '35px',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        backgroundColor: '#ffffff',
        color: 'var(--text-h)',
        fontSize: '18px',
        fontWeight: 'bold',
        textAlign: 'center',
        outline: 'none',
    },


    // ESTILOS DE LA CHECKBOX
    checkboxLabel: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '13px',
        color: 'var(--text-muted)',
        cursor: 'pointer',
        userSelect: 'none',
        marginTop: '-5px',
    },
    checkbox: {
        appearance: 'none',
        WebkitAppearance: 'none',
        width: '16px',
        height: '16px',
        border: '1px solid var(--border)',
        borderRadius: '100px',
        backgroundColor: '#ffffff',
        cursor: 'pointer',
        outline: 'none',
        display: 'grid',
        placeContent: 'center',
        transition: 'all 0.2s ease-in-out',
        accentColor: 'var(--sb-btnBorder)', // Mantiene la consistencia con el color de marca
    },

    simpleMessage: { padding: '40px', textAlign: 'center' },
};

export default ConfirmPasswordReset;
