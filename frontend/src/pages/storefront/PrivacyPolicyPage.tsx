import React from 'react';
import { Link } from 'react-router-dom';

const sectionTitleClass = 'text-xl md:text-2xl font-semibold text-foreground';
const bodyTextClass = 'mt-3 text-sm md:text-base leading-7 text-muted-foreground';

export const PrivacyPolicyPage: React.FC = () => {
  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">Privacy Policy</span>
          </div>
          <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight text-foreground">Privacy Policy</h1>
          <p className={bodyTextClass}>Last Updated: April 2026</p>
        </div>

        <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-6 md:p-10 space-y-9">
          <section>
            <h2 className={sectionTitleClass}>1. Introduction</h2>
            <p className={bodyTextClass}>Aurora Blings ("we", "our", "us") operates the website www.aurorablings.com.</p>
            <p className={bodyTextClass}>
              This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you visit our website
              or make a purchase.
            </p>
            <p className={bodyTextClass}>By using our website, you consent to the practices described in this Privacy Policy.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>2. Information We Collect</h2>
            <p className={bodyTextClass}>a. Personal Information</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Name</li>
              <li>Email address</li>
              <li>Phone number</li>
              <li>Shipping &amp; billing address</li>
            </ul>
            <p className={bodyTextClass}>b. Order Information</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Products purchased</li>
              <li>Payment status</li>
              <li>Transaction details</li>
            </ul>
            <p className={bodyTextClass}>c. Account Information</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Username &amp; password</li>
              <li>Login activity</li>
            </ul>
            <p className={bodyTextClass}>d. Technical Data</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>IP address</li>
              <li>Browser type</li>
              <li>Device information</li>
              <li>Website usage data</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>3. How We Use Your Information</h2>
            <p className={bodyTextClass}>We use your data to:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Process and fulfill orders</li>
              <li>Deliver products and services</li>
              <li>Communicate order updates</li>
              <li>Provide customer support</li>
              <li>Improve website functionality</li>
              <li>Prevent fraud and unauthorized activities</li>
              <li>Send promotional messages (if opted in)</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>4. Payment Security</h2>
            <p className={bodyTextClass}>
              All payments are processed through secure third-party payment gateways (such as PhonePe, Razorpay, or Cashfree).
            </p>
            <p className={bodyTextClass}>Aurora Blings does NOT store your card, UPI, or banking details.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>5. Sharing of Information</h2>
            <p className={bodyTextClass}>We may share your data with:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Courier partners (for delivery)</li>
              <li>Payment gateways (for processing payments)</li>
              <li>Service providers (hosting, analytics, etc.)</li>
            </ul>
            <p className={bodyTextClass}>We do not sell your personal data to third parties.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>6. Cookies &amp; Tracking</h2>
            <p className={bodyTextClass}>We use cookies to:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Enhance user experience</li>
              <li>Analyze traffic</li>
              <li>Improve services</li>
            </ul>
            <p className={bodyTextClass}>You can disable cookies via browser settings.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>7. Data Security</h2>
            <p className={bodyTextClass}>We implement appropriate security measures to protect your personal information.</p>
            <p className={bodyTextClass}>However, no method of transmission over the internet is 100% secure.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>8. Data Retention</h2>
            <p className={bodyTextClass}>We retain your information only as long as necessary for:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Order processing</li>
              <li>Legal compliance</li>
              <li>Business operations</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>9. Your Rights</h2>
            <p className={bodyTextClass}>As a user, you have the right to:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Access your data</li>
              <li>Request correction</li>
              <li>Request deletion</li>
              <li>Opt-out of marketing communications</li>
            </ul>
            <p className={bodyTextClass}>To exercise these rights, contact us.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>10. Children's Privacy</h2>
            <p className={bodyTextClass}>Our website is not intended for children under 18.</p>
            <p className={bodyTextClass}>We do not knowingly collect data from minors.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>11. Third-Party Links</h2>
            <p className={bodyTextClass}>Our website may contain links to external websites.</p>
            <p className={bodyTextClass}>We are not responsible for their privacy practices.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>12. Changes to Policy</h2>
            <p className={bodyTextClass}>We may update this Privacy Policy at any time.</p>
            <p className={bodyTextClass}>Changes will be posted on this page with updated date.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>13. Legal Compliance</h2>
            <p className={bodyTextClass}>
              This Privacy Policy complies with applicable Indian laws including the Information Technology Act, 2000 and relevant
              rules.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>14. Data Storage</h2>
            <p className={bodyTextClass}>Your data may be stored and processed in India or in locations where our service providers operate.</p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>15. Contact Us</h2>
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
