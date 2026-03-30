import React from 'react';
import { Link } from 'react-router-dom';

const sectionTitleClass = 'text-xl md:text-2xl font-semibold text-foreground';
const bodyTextClass = 'mt-3 text-sm md:text-base leading-7 text-muted-foreground';

export const ReturnRefundPolicyPage: React.FC = () => {
  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">Return & Refund Policy</span>
          </div>
          <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight text-foreground">Return & Refund Policy</h1>
          <p className="mt-3 text-muted-foreground max-w-3xl">
            Thank you for shopping with Aurora Blings. We strive to provide you with high-quality jewellery and a great shopping experience.
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-6 md:p-10 space-y-9">
          <section>
            <h2 className={sectionTitleClass}>1. Returns</h2>
            <p className={bodyTextClass}>
              Due to hygiene reasons and the delicate nature of jewellery, we do not accept returns on any products once delivered.
            </p>
            <p className={bodyTextClass}>However, we do offer replacements under certain conditions (see below).</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>2. Damaged or Incorrect Products</h2>
            <p className={bodyTextClass}>If you receive:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>A damaged product</li>
              <li>A defective item</li>
              <li>A wrong product</li>
            </ul>
            <p className={bodyTextClass}>Please contact us within 48 hours of delivery.</p>
            <p className={bodyTextClass}>You must share:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Clear unboxing video (mandatory)</li>
              <li>Photos of the product</li>
            </ul>
            <p className={bodyTextClass}>Without an unboxing video, we may not be able to process your request.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>3. Replacement Policy</h2>
            <p className={bodyTextClass}>Once verified, we will:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Offer a replacement of the same product (if available)</li>
              <li>OR provide store credit (if the product is out of stock)</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>4. Refunds</h2>
            <p className={bodyTextClass}>We do not offer refunds in the following cases:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Change of mind</li>
              <li>Minor color/finish variations (due to lighting/photography)</li>
              <li>Delays caused by courier partners</li>
            </ul>
            <p className={bodyTextClass}>Refunds will only be processed if:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Replacement is not possible</li>
              <li>The issue is verified from our side</li>
              <li>The original shipping cost, if applicable, is not refundable under any circumstances</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>5. Cancellation Policy</h2>
            <p className={bodyTextClass}>Orders can be cancelled within 12 hours of placing the order.</p>
            <p className={bodyTextClass}>After that, cancellations may not be possible.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>6. Shipping Issues</h2>
            <p className={bodyTextClass}>We are not responsible for:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Delays caused by courier companies</li>
              <li>Incorrect address provided by the customer</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>7. Contact Us</h2>
            <p className={bodyTextClass}>For any issues, contact us at:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Email: connect@aurorablings.com</li>
              <li>Instagram: @aurora_blings</li>
            </ul>
            <p className={bodyTextClass}>By placing an order with Aurora Blings, you agree to this Return & Refund Policy.</p>
          </section>
        </div>
      </div>
    </div>
  );
};
