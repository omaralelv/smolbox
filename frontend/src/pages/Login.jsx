import { useState } from 'react';

import { apiErrorMessage, login } from '../lib/api';

function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError('');
        setLoading(true);

        try {
            await login(email, password);
            window.location.href = '/bandeja';
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={styles.container}>
            <form style={styles.form} onSubmit={handleSubmit}>
                <h2 style={styles.title}>Iniciar sesión</h2>
                <div style={styles.inputGroup}>
                    <label style={styles.label}>Correo</label>
                    <input
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        style={styles.input}
                        required
                    />
                </div>
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
                {error && <div style={styles.error}>{error}</div>}
                <button type="submit" style={styles.button} disabled={loading}>
                    {loading ? 'Entrando...' : 'Entrar'}
                </button>
            </form>
        </div>
    );
}

const styles = {
    container: {
        maxWidth: '420px',
        margin: '40px auto',
        padding: '20px',
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: '18px',
        backgroundColor: '#ffffff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '28px',
        boxShadow: 'var(--shadow)',
    },
    title: {
        margin: 0,
        fontSize: '24px',
        color: 'var(--text-h)',
        textAlign: 'center',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
    },
    label: {
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
    },
    input: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '15px',
        outline: 'none',
    },
    error: {
        color: 'var(--text-denegada, #cc3030)',
        fontSize: '13px',
        textAlign: 'center',
    },
    button: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '10px',
        padding: '11px 25px',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
    },
};

export default Login;
