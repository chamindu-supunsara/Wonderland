import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';

// Keep native form elements and their accessibility/validation behavior.
export const PRIME_FORM_UI = [ButtonModule, InputTextModule, TextareaModule] as const;
