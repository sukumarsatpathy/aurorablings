import React from 'react';
import { useLocation } from 'react-router-dom';
import { whatsappLink } from '@/lib/contact';
import { cn } from '@/lib/utils';

/** WhatsApp's glyph; lucide has no brand icons. */
export const WhatsAppIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.65.07-.3-.15-1.26-.46-2.4-1.48-.89-.79-1.49-1.77-1.66-2.07-.17-.3-.02-.46.13-.61.14-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.02-1.04 2.48s1.07 2.88 1.21 3.08c.15.2 2.1 3.2 5.08 4.49.71.31 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.76-.72 2.01-1.41.25-.69.25-1.29.17-1.41-.07-.12-.27-.2-.57-.35ZM12.05 21.5h-.01a9.45 9.45 0 0 1-4.82-1.32l-.35-.21-3.58.94.96-3.49-.23-.36a9.44 9.44 0 0 1-1.45-5.03c0-5.22 4.25-9.47 9.48-9.47 2.53 0 4.91.99 6.7 2.78a9.41 9.41 0 0 1 2.77 6.7c0 5.22-4.25 9.47-9.47 9.47Zm8.06-17.53A11.33 11.33 0 0 0 12.05.63C5.77.63.65 5.74.65 12.03c0 2.01.52 3.97 1.52 5.7L.55 23.63l6.04-1.58a11.37 11.37 0 0 0 5.45 1.39h.01c6.28 0 11.4-5.11 11.4-11.4 0-3.05-1.19-5.91-3.34-8.07Z" />
  </svg>
);

/** Pages with their own sticky mobile action bar; lift the button above it there. */
const HAS_MOBILE_ACTION_BAR = [/^\/product\//, /^\/cart\/?$/];
/** Pages where the button would distract from finishing an action. */
const HIDDEN_ON = [/^\/checkout/];

/**
 * Floating "Chat on WhatsApp" button for the storefront.
 * On a product page the message carries the page link, so the reply can be about that piece.
 */
export const WhatsAppButton: React.FC = () => {
  const { pathname } = useLocation();
  if (HIDDEN_ON.some((re) => re.test(pathname))) return null;

  const onProduct = pathname.startsWith('/product/');
  const message = onProduct
    ? `Hi Aurora Blings! I have a question about this piece: ${window.location.origin}${pathname}`
    : 'Hi Aurora Blings! I have a question.';
  const liftOnMobile = HAS_MOBILE_ACTION_BAR.some((re) => re.test(pathname));

  return (
    <a
      href={whatsappLink(message)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Chat with us on WhatsApp"
      className={cn(
        'group fixed left-4 z-40 flex items-center gap-2 rounded-full bg-[#25D366] p-3 text-white shadow-[0_10px_30px_rgba(37,211,102,0.35)] transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#25D366] focus-visible:ring-offset-2 md:bottom-6 md:left-6',
        liftOnMobile ? 'bottom-24' : 'bottom-5',
      )}
    >
      <WhatsAppIcon className="h-6 w-6" />
      <span className="hidden pr-1 text-sm font-semibold md:inline">Chat with us</span>
    </a>
  );
};

export default WhatsAppButton;
