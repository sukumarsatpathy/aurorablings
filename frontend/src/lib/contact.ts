/**
 * Customer contact details used across the storefront.
 * Keep the WhatsApp number in international format without "+" (wa.me needs digits only).
 */
export const WHATSAPP_NUMBER = '917847090866';

/** A wa.me link that opens WhatsApp with `message` already typed in. */
export const whatsappLink = (message: string): string =>
  `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`;

/**
 * Instagram account. Change the handle here only — every page reads from these.
 * (Handle changed from aurora_blings to aurora_blings_.)
 */
export const INSTAGRAM_HANDLE = 'aurora_blings_';
export const INSTAGRAM_URL = `https://www.instagram.com/${INSTAGRAM_HANDLE}`;
