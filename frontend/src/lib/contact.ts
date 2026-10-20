/**
 * Customer contact details used across the storefront.
 * Keep the WhatsApp number in international format without "+" (wa.me needs digits only).
 */
export const WHATSAPP_NUMBER = '917847090866';

/** A wa.me link that opens WhatsApp with `message` already typed in. */
export const whatsappLink = (message: string): string =>
  `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`;
