import React from 'react';
import { Link } from 'react-router-dom';

const sectionTitleClass = 'text-xl md:text-2xl font-semibold text-foreground';
const bodyTextClass = 'mt-3 text-sm md:text-base leading-7 text-muted-foreground';

export const TermsAndConditionsPage: React.FC = () => {
  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">Terms & Conditions</span>
          </div>
          <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight text-foreground">Terms & Conditions</h1>
          <p className="mt-3 text-muted-foreground max-w-3xl">
            Welcome to Aurora Blings. By accessing our website and placing an order, you agree to the following terms.
          </p>
          <p className={bodyTextClass}>Last Updated: April 2026</p>
        </div>

        <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-6 md:p-10 space-y-9">
          <section>
            <h2 className={sectionTitleClass}>1. General</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>By using this website, you confirm that you are at least 18 years old or using it under parental supervision.</li>
              <li>We reserve the right to update or modify these terms at any time without prior notice.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>2. Products & Pricing</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>All products are subject to availability.</li>
              <li>Slight variations in color/design may occur.</li>
              <li>Prices may change without prior notice.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>3. Orders & Payments</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>Order confirmation will be sent after successful placement.</li>
              <li>We reserve the right to cancel/refuse any order.</li>
              <li>Payments are processed securely via trusted payment gateways.</li>
              <li>Aurora Blings does not store payment details.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>4. Shipping & Delivery</h2>
            <p className={bodyTextClass}>Orders are processed and shipped as per timelines mentioned on the website.</p>
            <p className={bodyTextClass}>
              While we work with reliable courier partners, delays may occur. Aurora Blings will assist customers in resolving
              delivery-related issues.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>5. Returns & Refunds</h2>
            <p className={bodyTextClass}>
              Please refer to our{' '}
              <Link to="/return-and-refund-policy/" className="text-primary hover:underline">
                Return & Refund Policy
              </Link>{' '}
              .
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>6. Intellectual Property</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>All content (images, logos, designs) is owned by Aurora Blings.</li>
              <li>Unauthorized use is strictly prohibited.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>7. Limitation of Liability</h2>
            <p className={bodyTextClass}>
              Aurora Blings shall not be liable for indirect or consequential damages arising from website or product usage.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>8. User Responsibilities</h2>
            <p className={bodyTextClass}>You agree not to:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Use the website for illegal purposes.</li>
              <li>Attempt to harm or disrupt the platform.</li>
            </ul>
            <p className={bodyTextClass}>You are responsible for maintaining the confidentiality of your account credentials.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>9. Cookies</h2>
            <p className={bodyTextClass}>We use cookies to enhance user experience. Continued use implies consent.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>10. Termination</h2>
            <p className={bodyTextClass}>
              We may suspend or terminate access if terms are violated.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>11. Force Majeure</h2>
            <p className={bodyTextClass}>
              Aurora Blings shall not be liable for delays caused by events beyond our control, including natural disasters, strikes,
              or government restrictions.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>12. Governing Law</h2>
            <p className={bodyTextClass}>These terms are governed by the laws of India.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>13. Contact Us</h2>
            <p className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              Aurora Blings By Bimba Dhar Dash<br/>
              Puri, Odisha, India<br/>
              Email: connect@aurorablings.com<br/>
              Phone/WhatsApp: 7847090866<br/>
              Instagram: @aurora_blings
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};
