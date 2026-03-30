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
          <p className="mt-3 text-muted-foreground max-w-4xl">
            This Privacy Policy describes how AURORA BLINGS collects, uses, and discloses your personal information when you use our website and services.
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-6 md:p-10 space-y-9">
          <section>
            <p className={bodyTextClass}>
              This Privacy Policy describes how AURORA BLINGS (the "WEBSITE", "WE", "US", or "OUR") collects, uses, and discloses your personal information when you
              visit, use our services, or make a purchase from www.aurorablings.com (the "Website") or otherwise communicate with US regarding the Website (collectively,
              the "Services"). For purposes of this Privacy Policy, "you" and "your" means you as the user of the Services, whether you are a customer, website visitor,
              or another individual whose information we have collected pursuant to this Privacy Policy.
            </p>
            <p className={bodyTextClass}>
              Please read this Privacy Policy carefully. By using and accessing any of the Services, you agree to the collection, use, and disclosure of your information
              as described in this Privacy Policy. If you do not agree to this Privacy Policy, please do not use or access any of the Services.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Changes to This Privacy Policy</h2>
            <p className={bodyTextClass}>
              We may update this Privacy Policy from time to time, including to reflect changes to our practices or for other operational, legal, or regulatory reasons.
              We will post the revised Privacy Policy on the Website, update the "Last updated" date and take any other steps required by applicable law.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>How We Collect and Use Your Personal Information</h2>
            <p className={bodyTextClass}>
              To provide the Services, we collect personal information about you from a variety of sources, as set out below. The information that we collect and use
              varies depending on how you interact with us.
            </p>
            <p className={bodyTextClass}>
              In addition to the specific uses set out below, we may use information we collect about you to communicate with you, provide or improve the Services, comply
              with any applicable legal obligations, enforce any applicable terms of service, and to protect or defend the Services, our rights, and the rights of our
              users or others.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>What Personal Information We Collect</h2>
            <p className={bodyTextClass}>
              The types of personal information we obtain about you depends on how you interact with our Website and use our Services. When we use the term "personal
              information", we are referring to information that identifies, relates to, describes or can be associated with you.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Information We Collect Directly from You</h2>
            <p className={bodyTextClass}>Information that you directly submit to us through our Services may include:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Contact details including your name, address, phone number, and email.</li>
              <li>Order information including your name, billing address, shipping address, payment confirmation, email address, and phone number.</li>
              <li>Account information including your username, password, security questions and other information used for account security purposes.</li>
              <li>Customer support information including the information you choose to include in communications with us.</li>
            </ul>
            <p className={bodyTextClass}>
              Some features of the Services may require you to directly provide us with certain information about yourself. You may elect not to provide this information,
              but doing so may prevent you from using or accessing these features.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Information We Collect about Your Usage</h2>
            <p className={bodyTextClass}>
              We may also automatically collect certain information about your interaction with the Services ("Usage Data"). To do this, we may use cookies, pixels and
              similar technologies ("Cookies"). Usage Data may include information about how you access and use our Website and your account, including device information,
              browser information, information about your network connection, your IP address and other information regarding your interaction with the Services.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Information We Obtain from Third Parties</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>
                Our payment processors, who collect payment information (e.g., bank account, credit or debit card information, billing address) to process your payment.
              </li>
              <li>
                When you visit our Website, open or click on emails we send you, or interact with our Services or advertisements, we or third parties we work with may
                automatically collect certain information using tracking technologies.
              </li>
            </ul>
            <p className={bodyTextClass}>
              Any information we obtain from third parties will be treated in accordance with this Privacy Policy. Also see the section below, Third Party Websites and
              Links.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>How We Use Your Personal Information</h2>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Providing Products and Services, including order management, shipping, returns, and account management.</li>
              <li>Marketing and Advertising, including promotional communications and tailored advertisements.</li>
              <li>Security and Fraud Prevention, including detecting and preventing malicious or illegal activity.</li>
              <li>Communicating with You and Service Improvement, including support and service enhancement.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Cookies</h2>
            <p className={bodyTextClass}>
              Like many websites, we may use cookies to enhance your browsing experience and analyze website traffic. We may also permit third parties and service providers
              to use Cookies on our Website to better tailor services, products and advertising.
            </p>
            <p className={bodyTextClass}>
              Most browsers automatically accept Cookies by default, but you can choose to remove or reject Cookies through your browser controls. Removing or blocking
              Cookies may negatively impact your user experience and service functionality.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>How We Disclose Personal Information</h2>
            <p className={bodyTextClass}>In certain circumstances, we may disclose your personal information to third parties for lawful and operational purposes, such as:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>With vendors or third parties who perform services on our behalf.</li>
              <li>With business and marketing partners to provide services and advertising.</li>
              <li>With your consent or at your direction.</li>
              <li>With affiliates in our corporate group.</li>
              <li>For legal compliance, rights protection, or in business transactions.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Categories of Information and Recipients</h2>
            <p className={bodyTextClass}>We may disclose the following categories of information:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Identifiers such as contact and account details.</li>
              <li>Commercial information such as order and shopping information.</li>
              <li>Internet activity data, including usage data.</li>
              <li>Geolocation data inferred from IP or technical measures.</li>
            </ul>
            <p className={bodyTextClass}>Recipients may include service providers, business/marketing partners, and affiliates.</p>
            <p className={bodyTextClass}>
              We do not use or disclose sensitive personal information without your consent or for the purposes of inferring characteristics about you.
            </p>
            <p className={bodyTextClass}>
              We may "sell" or "share" personal information in the future, as permitted by applicable law, for advertising and marketing activities.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Third Party Websites and Links</h2>
            <p className={bodyTextClass}>
              Our Website may provide links to websites or platforms operated by third parties. We are not responsible for the privacy or security of such sites. Please
              review third-party policies before sharing information.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Children's Data</h2>
            <p className={bodyTextClass}>
              The Services are not intended for children, and we do not knowingly collect personal information from children. If you believe a child has shared data with
              us, please contact us to request deletion.
            </p>
            <p className={bodyTextClass}>
              As of the Effective Date of this Privacy Policy, we do not have actual knowledge that we "share" or "sell" personal information of individuals under 16 years
              of age.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Security and Retention of Your Information</h2>
            <p className={bodyTextClass}>
              No security measures are perfect or impenetrable, and we cannot guarantee perfect security. We recommend that you do not use insecure channels to communicate
              sensitive information.
            </p>
            <p className={bodyTextClass}>
              Retention periods vary based on the nature of information and legal or operational requirements, including account maintenance, service delivery, legal
              compliance, dispute resolution, and enforcement of policies.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Your Rights</h2>
            <p className={bodyTextClass}>Depending on your location and applicable law, you may have rights such as:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Right to Access / Know</li>
              <li>Right to Delete</li>
              <li>Right to Correct</li>
              <li>Right of Portability</li>
              <li>Restriction of Processing</li>
              <li>Withdrawal of Consent</li>
              <li>Right to Appeal</li>
              <li>Managing Communication Preferences</li>
            </ul>
            <p className={bodyTextClass}>
              We may need to verify your identity before fulfilling a request. You may also appoint an authorized agent as permitted by applicable law.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Complaints</h2>
            <p className={bodyTextClass}>
              If you have complaints about how we process your personal information, please contact us. If you are not satisfied with our response, you may have the right to
              escalate to your local data protection authority.
            </p>
          </section>

          <section>
            <h2 className={sectionTitleClass}>Contact Us</h2>
            <p className={bodyTextClass}>
              For questions about this Privacy Policy or to exercise your rights, contact us at Email: connect@aurorablings.com, Instagram: @aurora_blings
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};
