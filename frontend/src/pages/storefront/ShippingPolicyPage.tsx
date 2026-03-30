import React from 'react';
import { Link } from 'react-router-dom';

const sectionTitleClass = 'text-xl md:text-2xl font-semibold text-foreground';
const bodyTextClass = 'mt-3 text-sm md:text-base leading-7 text-muted-foreground';

export const ShippingPolicyPage: React.FC = () => {
  return (
    <div className="pt-32 pb-24">
      <div className="container mx-auto px-4">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-white/70 backdrop-blur-sm px-4 py-2">
            <Link to="/" className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground hover:text-primary transition-colors">
              Home
            </Link>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-foreground">Shipping Policy</span>
          </div>
          <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight text-foreground">Shipping Policy</h1>
          <p className="mt-3 text-muted-foreground max-w-3xl">
            Thank you for shopping with Aurora Blings. We are committed to delivering your order safely and on time.
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-white/85 backdrop-blur-sm p-6 md:p-10 space-y-9">
          <section>
            <h2 className={sectionTitleClass}>1. Order Processing Time</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>All orders are processed within 1-3 business days after confirmation.</li>
              <li>Orders placed on weekends or holidays will be processed on the next working day.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>2. Shipping Time</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>Estimated delivery time: 3-7 business days depending on your location in India.</li>
              <li>Delivery timelines may vary due to external factors such as courier delays, weather, or high demand.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>3. Shipping Charges</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>Shipping charges will be calculated at checkout.</li>
              <li>We may offer free shipping on selected orders or promotions.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>4. Order Tracking</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>Once your order is shipped, you will receive a tracking ID via SMS/Email/WhatsApp.</li>
              <li>You can use this to track your shipment in real time.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>5. Delivery Issues</h2>
            <p className={bodyTextClass}>Aurora Blings is not responsible for:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Delays caused by courier partners</li>
              <li>Incorrect or incomplete shipping address provided by the customer</li>
              <li>Failed delivery attempts due to unavailability</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>6. Lost or Damaged Packages</h2>
            <ul className={`${bodyTextClass} list-disc pl-5 space-y-2`}>
              <li>If your order is lost or arrives damaged, please contact us within 48 hours of delivery.</li>
              <li>You must provide an unboxing video as proof for any damage claims.</li>
            </ul>
          </section>

          <section>
            <h2 className={sectionTitleClass}>7. Contact Us</h2>
            <p className={bodyTextClass}>For any shipping-related queries, please contact us:</p>
            <ul className="mt-3 text-sm md:text-base leading-7 text-muted-foreground list-disc pl-5 space-y-2">
              <li>Email: connect@aurorablings.com</li>
              <li>Instagram: @aurora_blings</li>
            </ul>
            <p className={bodyTextClass}>Thank you for choosing Aurora Blings.</p>
          </section>
        </div>
      </div>
    </div>
  );
};
