export const PASSWORD_RULES = [
    '- 8 caracteres.',
    '- Una mayúscula.',
    '- Una minúscula.',
    '- Un número.',
    '- Un carácter especial.',
];

export const PASSWORD_RULES_TEXT = PASSWORD_RULES.join('\n');

export function passwordPolicyMessage(password) {
    const missingRules = [];

    if (!password || password.length < 8) {
        missingRules.push('mínimo 8 caracteres');
    }
    if (!/[A-ZÁÉÍÓÚÑ]/.test(password || '')) {
        missingRules.push('una letra mayúscula');
    }
    if (!/[a-záéíóúñ]/.test(password || '')) {
        missingRules.push('una letra minúscula');
    }
    if (!/\d/.test(password || '')) {
        missingRules.push('un número');
    }
    if (!/[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9]/.test(password || '')) {
        missingRules.push('un carácter especial');
    }

    if (!missingRules.length) return '';
    return `La contraseña debe incluir: ${missingRules.join(', ')}.`;
}

export function passwordPolicyHelpText() {
    return `Tu contraseña debe contener al menos:\n${PASSWORD_RULES_TEXT}`;
}
