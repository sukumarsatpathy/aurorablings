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
              Due to hygiene reasons and the delicate nature of jewellery, returns are not accepted once the product is delivered.
            </p>
            <p className={bodyTextClass}>However, we do offer replacements under specific conditions (see below).</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>2. Damaged, Defective, or Incorrect Products</h2>
            <p className={bodyTextClass}>If you receive:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>A damaged product</li>
              <li>A defective item</li>
              <li>A wrong product</li>
            </ul>
            <p className={bodyTextClass}>You must notify us within 48 hours of delivery and provide:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Clear unboxing video (mandatory)</li>
              <li>Photos of the product</li>
            </ul>
            <p className={bodyTextClass}>Requests without an unboxing video may not be eligible.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>3. Replacement Policy</h2>
            <p className={bodyTextClass}>Once verified, we will:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Offer a replacement of the same product (subject to availability), OR</li>
              <li>Provide store credit if the product is out of stock</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>4. Refund Policy</h2>
            <p className={bodyTextClass}>Refunds are not applicable in the following cases:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Change of mind</li>
              <li>Minor color/finish variations</li>
              <li>Delays caused by courier partners</li>
            </ul>
            <p className={bodyTextClass}>Refunds will only be processed if:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Replacement is not possible</li>
              <li>The issue is verified by our team</li>
            </ul>
            <p className={bodyTextClass}>Refund Details:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Refunds will be processed within 5-7 business days</li>
              <li>Refunds will be credited to the original payment method</li>
              <li>Shipping charges (if any) are non-refundable</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>5. Cancellation Policy</h2>
            <p className={bodyTextClass}>Orders can be cancelled within 12 hours of placing the order.</p>
            <p className={bodyTextClass}>After this period, cancellation requests may not be accepted.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>6. Shipping Issues</h2>
            <p className={bodyTextClass}>
              While we work with reliable courier partners, delays may occur due to unforeseen circumstances. Aurora Blings will assist
              customers in resolving delivery-related issues.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>7. Contact Us</h2>
            <p className={bodyTextClass}>Aurora Blings</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Puri, Odisha, India</li>
              <li>Email: connect@aurorablings.com</li>
              <li>Phone/WhatsApp: 7847090866</li>
              <li>Instagram: @aurora_blings</li>
            </ul>
            <p className={bodyTextClass}>By placing an order, you agree to this policy.</p>
          </section>
        </div>
      </div>
    </div>
  );
};
