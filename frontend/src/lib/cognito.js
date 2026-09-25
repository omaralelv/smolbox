const COGNITO_REGION = import.meta.env.VITE_COGNITO_REGION || 'us-east-1';
const COGNITO_APP_CLIENT_ID = import.meta.env.VITE_COGNITO_APP_CLIENT_ID || '';

function cognitoEndpoint() {
    return `https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`;
}

export function isCognitoLoginEnabled() {
    return import.meta.env.VITE_COGNITO_ENABLED === 'true';
}

export async function cognitoLogin(email, password) {
    ensureCognitoConfig();
    const response = await cognitoRequest('AWSCognitoIdentityProviderService.InitiateAuth', {
        AuthFlow: 'USER_PASSWORD_AUTH',
        ClientId: COGNITO_APP_CLIENT_ID,
        AuthParameters: {
            USERNAME: email.trim().toLowerCase(),
            PASSWORD: password,
        },
    });

    if (response.ChallengeName === 'NEW_PASSWORD_REQUIRED') {
        return {
            challengeName: response.ChallengeName,
            session: response.Session,
            email: email.trim().toLowerCase(),
        };
    }

    return tokensFromAuthenticationResult(response.AuthenticationResult);
}

export async function completeCognitoNewPassword(email, newPassword, session) {
    ensureCognitoConfig();
    const response = await cognitoRequest(
        'AWSCognitoIdentityProviderService.RespondToAuthChallenge',
        {
            ChallengeName: 'NEW_PASSWORD_REQUIRED',
            ClientId: COGNITO_APP_CLIENT_ID,
            Session: session,
            ChallengeResponses: {
                USERNAME: email.trim().toLowerCase(),
                NEW_PASSWORD: newPassword,
            },
        },
    );

    return tokensFromAuthenticationResult(response.AuthenticationResult);
}

export async function refreshCognitoSession(refreshToken) {
    ensureCognitoConfig();
    if (!refreshToken) {
        throw new Error('Tu sesión expiró. Vuelve a iniciar sesión.');
    }

    const response = await cognitoRequest('AWSCognitoIdentityProviderService.InitiateAuth', {
        AuthFlow: 'REFRESH_TOKEN_AUTH',
        ClientId: COGNITO_APP_CLIENT_ID,
        AuthParameters: {
            REFRESH_TOKEN: refreshToken,
        },
    });

    return tokensFromAuthenticationResult(response.AuthenticationResult);
}

export async function forgotCognitoPassword(email) {
    ensureCognitoConfig();
    return cognitoRequest('AWSCognitoIdentityProviderService.ForgotPassword', {
        ClientId: COGNITO_APP_CLIENT_ID,
        Username: normalizeUsername(email),
    });
}

export async function confirmCognitoPassword(email, confirmationCode, newPassword) {
    ensureCognitoConfig();
    return cognitoRequest('AWSCognitoIdentityProviderService.ConfirmForgotPassword', {
        ClientId: COGNITO_APP_CLIENT_ID,
        Username: normalizeUsername(email),
        ConfirmationCode: confirmationCode.trim(),
        Password: newPassword,
    });
}

async function cognitoRequest(target, body) {
    const response = await fetch(cognitoEndpoint(), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-amz-json-1.1',
            'X-Amz-Target': target,
        },
        body: JSON.stringify(body),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(cognitoErrorMessage(data));
    }
    return data;
}

function tokensFromAuthenticationResult(result) {
    if (!result?.IdToken) {
        throw new Error('Cognito no devolvió una sesión válida.');
    }
    return {
        accessToken: result.AccessToken,
        idToken: result.IdToken,
        refreshToken: result.RefreshToken,
        expiresIn: result.ExpiresIn,
    };
}

function ensureCognitoConfig() {
    if (!COGNITO_APP_CLIENT_ID) {
        throw new Error('Falta configurar VITE_COGNITO_APP_CLIENT_ID.');
    }
}

function normalizeUsername(email) {
    return email.trim().toLowerCase();
}

function cognitoErrorMessage(data) {
    const type = String(data.__type || data.code || '');
    const message = String(data.message || '');

    if (type.includes('NotAuthorizedException')) {
        return 'Correo o contraseña incorrectos.';
    }
    if (type.includes('UserNotFoundException')) {
        return 'El usuario no existe o no está registrado para entrar.';
    }
    if (type.includes('UserNotConfirmedException')) {
        return 'El usuario todavía no está confirmado.';
    }
    if (type.includes('PasswordResetRequiredException')) {
        return 'El usuario necesita restablecer su contraseña.';
    }
    if (type.includes('InvalidPasswordException')) {
        return 'La contraseña no cumple la política de seguridad configurada.';
    }
    if (type.includes('CodeMismatchException')) {
        return 'El código no es válido. Verifica el correo o solicita uno nuevo.';
    }
    if (type.includes('ExpiredCodeException')) {
        return 'El código expiró. Solicita un código nuevo.';
    }
    if (type.includes('LimitExceededException') || type.includes('TooManyRequestsException')) {
        return 'Se alcanzó el límite de intentos. Espera unos minutos y vuelve a intentarlo.';
    }
    if (type.includes('UserLambdaValidationException')) {
        return message || 'Cognito rechazó la solicitud de recuperación.';
    }
    if (type.includes('InvalidParameterException')) {
        return message || 'La configuración de Cognito no acepta esta solicitud.';
    }
    if (message) {
        return message;
    }
    return 'No se pudo iniciar sesión con Cognito.';
}
