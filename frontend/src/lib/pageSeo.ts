/**
 * Title and description for each storefront page, so search results and
 * browser tabs say what the page is rather than "Aurora Blings" everywhere.
 *
 * Product pages set their own (from the product) in ProductDetailPage, and the
 * shop page adds the selected category in ProductListingPage.
 */
export interface PageSeo {
  title: string;
  description: string;
}

const BRAND = 'Aurora Blings';

export const SITE_DESCRIPTION =
  'Shop hand-picked imitation jewellery from Aurora Blings, Puri — enamel bangles and everyday pieces. Free delivery on orders above ₹799 and easy 7-day returns.';

const PAGES: Record<string, PageSeo> = {
  '/': {
    title: `${BRAND} | Imitation Jewellery & Bangles Online`,
    description: SITE_DESCRIPTION,
  },
  '/products/': {
    title: `Shop Jewellery | ${BRAND}`,
    description: 'Browse imitation jewellery from Aurora Blings — enamel bangle sets and new arrivals. Free delivery on orders above ₹799.',
  },
  '/about-us/': {
    title: `Our Story | ${BRAND}`,
    description: 'How Aurora Blings began, and how we choose every piece we sell.',
  },
  '/contact-us/': {
    title: `Contact Us | ${BRAND}`,
    description: 'Questions about a piece or an order? Reach Aurora Blings on WhatsApp, phone or email, or visit us in Puri.',
  },
  '/cart': { title: `Your Cart | ${BRAND}`, description: SITE_DESCRIPTION },
  '/checkout': { title: `Checkout | ${BRAND}`, description: SITE_DESCRIPTION },
  '/order/thank-you': { title: `Thank You | ${BRAND}`, description: SITE_DESCRIPTION },
  '/terms-and-conditions/': { title: `Terms & Conditions | ${BRAND}`, description: `Terms for shopping with ${BRAND}.` },
  '/return-and-refund-policy/': {
    title: `Returns & Refunds | ${BRAND}`,
    description: 'Easy 7-day returns and exchanges — how to return an Aurora Blings order and when refunds arrive.',
  },
  '/privacy-policy/': { title: `Privacy Policy | ${BRAND}`, description: `How ${BRAND} collects and protects your information.` },
  '/shipping-policy/': {
    title: `Shipping Policy | ${BRAND}`,
    description: 'Delivery times, charges and tracking for Aurora Blings orders. Free delivery on orders above ₹799.',
  },
};

export const pageSeoFor = (pathname: string): PageSeo | null => PAGES[pathname] ?? null;
