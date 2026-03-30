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
              <li>All products listed are subject to availability.</li>
              <li>We strive to display accurate product details, colors, and images. Slight variations may occur due to lighting or screen settings.</li>
              <li>Prices are subject to change without prior notice.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>3. Orders & Payments</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>Once an order is placed, you will receive a confirmation.</li>
              <li>
                We reserve the right to cancel any order due to product unavailability, payment issues, or suspicious/fraudulent activity.
              </li>
              <li>Payments are processed securely through third-party payment gateways.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>4. Shipping & Delivery</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>Orders will be processed and shipped within the specified timeframe mentioned on the website.</li>
              <li>Delivery timelines may vary based on location and courier services.</li>
              <li>
                Aurora Blings is not responsible for delays caused by courier partners. Please review our{' '}
                <Link to="/shipping-policy/" className="text-primary hover:underline">
                  Shipping Policy
                </Link>{' '}
                for complete details.
              </li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>5. Returns & Refunds</h2>
            <p className={bodyTextClass}>
              Please refer to our{' '}
              <Link to="/return-and-refund-policy/" className="text-primary hover:underline">
                Return & Refund Policy
              </Link>{' '}
              for detailed information. By placing an order, you agree to the terms mentioned in that policy.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>6. Intellectual Property</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>All content on this website, including images, logos, text, and designs, is the property of Aurora Blings.</li>
              <li>Unauthorized use or reproduction is strictly prohibited.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>7. Limitation of Liability</h2>
            <p className={bodyTextClass}>
              Aurora Blings shall not be held liable for any indirect, incidental, or consequential damages arising from the use of our products or website.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>8. User Conduct</h2>
            <p className={bodyTextClass}>You agree not to:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Use the website for any illegal or unauthorized purpose.</li>
              <li>Attempt to harm, disrupt, or misuse the website.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>10. Cookies and Tracking</h2>
            <p className={bodyTextClass}>
              We may use cookies or similar tracking technologies to enhance your browsing experience, understand how you interact with our website, and improve our services.
              By continuing to use this website, you consent to our use of cookies in accordance with our{' '}
              <Link to="/privacy-policy/" className="text-primary hover:underline">
                Privacy Policy
              </Link>
              .
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>11. Termination</h2>
            <p className={bodyTextClass}>
              We reserve the right to terminate or suspend your access to the website and its services at any time, without prior notice, if we believe you have violated
              these Terms and Conditions or engaged in any inappropriate or unlawful activity.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>12. Governing Law</h2>
            <p className={bodyTextClass}>These Terms & Conditions are governed by the laws of India.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>13. Contact Us</h2>
            <p className={bodyTextClass}>For any questions regarding these Terms & Conditions, please contact us:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Email: connect@aurorablings.com</li>
              <li>Instagram: @aurora_blings</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
};
