import React, { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { Mail, MapPin, MessageCircle, MoveUpRight } from 'lucide-react';
import { FooterColumn } from './FooterColumn';
import { SocialIcons } from './SocialIcons';
import newsletterService from '@/services/api/newsletter';

gsap.registerPlugin(ScrollTrigger);

const quickLinks = [
  { label: 'Our Story', href: '/about-us/' },
  { label: 'Shop', href: '/shop' },
  { label: 'Contact Us', href: '/contact-us/' },
  { label: 'My Account', href: '/login' },
];

const policyLinks = [
  { label: 'Terms & Conditions', href: '/terms-and-conditions/' },
  { label: 'Return & Refund Policy', href: '/return-and-refund-policy/' },
  { label: 'Privacy Policy', href: '/privacy-policy/' },
  { label: 'Shipping Policy', href: '/shipping-policy' },
];

const paymentBadges = ['Visa', 'Mastercard', 'UPI'];

export function LuxuryFooter() {
  const rootRef = useRef(null);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [newsletterState, setNewsletterState] = useState({ type: 'idle', message: '' });
  const [isSubmittingNewsletter, setIsSubmittingNewsletter] = useState(false);

  useEffect(() => {
    if (!rootRef.current) return undefined;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = gsap.context(() => {
      if (!reduceMotion) {
        gsap.fromTo(
          '.footer-reveal',
          { opacity: 0, y: 28 },
          {
            opacity: 1,
            y: 0,
            duration: 0.7,
            stagger: 0.1,
            ease: 'power2.out',
            scrollTrigger: {
              trigger: rootRef.current,
              start: 'top bottom-=120',
              once: true,
            },
          },
        );
      } else {
        gsap.set('.footer-reveal', { opacity: 1, y: 0 });
      }

      const hoverTargets = gsap.utils.toArray('.footer-hover-target');
      const listeners = hoverTargets.map((target) => {
        const enter = () => gsap.to(target, { scale: 1.015, y: -1, duration: 0.24, ease: 'power2.out' });
        const leave = () => gsap.to(target, { scale: 1, y: 0, duration: 0.24, ease: 'power2.out' });

        target.addEventListener('mouseenter', enter);
        target.addEventListener('mouseleave', leave);
        target.addEventListener('focus', enter);
        target.addEventListener('blur', leave);

        return () => {
          target.removeEventListener('mouseenter', enter);
          target.removeEventListener('mouseleave', leave);
          target.removeEventListener('focus', enter);
          target.removeEventListener('blur', leave);
        };
      });

      return () => {
        listeners.forEach((cleanup) => cleanup());
      };
    }, rootRef);

    const onScroll = () => setShowScrollTop(window.scrollY > 640);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', onScroll);
      ctx.revert();
    };
  }, []);

  const openCookieSettings = () => {
    window.dispatchEvent(new Event('aurora:open-cookie-settings'));
  };

  const handleNewsletterSubmit = async (event) => {
    event.preventDefault();

    const email = newsletterEmail.trim().toLowerCase();
    if (!email) {
      setNewsletterState({ type: 'error', message: 'Please enter your email address.' });
      return;
    }

    setIsSubmittingNewsletter(true);
    setNewsletterState({ type: 'idle', message: '' });

    try {
      const response = await newsletterService.subscribe({ email, source: 'footer' });
      setNewsletterEmail('');
      setNewsletterState({
        type: 'success',
        message: response?.message || 'You have been subscribed successfully.',
      });
    } catch (error) {
      const message =
        error?.response?.data?.message ||
        error?.response?.data?.errors?.email?.[0] ||
        'Something went wrong. Please try again.';

      setNewsletterState({ type: 'error', message });
    } finally {
      setIsSubmittingNewsletter(false);
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <>
      <footer
        ref={rootRef}
        className="relative mt-20 overflow-hidden border-t border-[#d8e2d0] bg-[#f5f8f2] text-[#1f2937] dark:border-[#2c372b] dark:bg-[#121811] dark:text-[#e7ece4]"
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#84a07c] to-transparent opacity-80" />

        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 lg:py-16">
          <div className="grid grid-cols-1 gap-10 md:grid-cols-2 xl:grid-cols-4 xl:gap-12">
            <section className="footer-reveal flex flex-col items-center text-center md:items-start md:text-left">
              <div className="inline-flex items-center gap-3">
                <span className="h-2.5 w-2.5 rounded-full bg-[#517b4b]" />
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#517b4b] dark:text-[#9fbd99]">
                  Aurora Blings
                </p>
              </div>

              <p className="mt-4 max-w-md text-sm leading-7 text-[#55616f] dark:text-[#c7d0c3]">
                Jewellery that feels personal, elegant, and made to shine with you. Carefully curated imitation jewellery for your everyday elegance.
              </p>
              <div className="mt-6">
                <SocialIcons centered />
              </div>
            </section>

            <FooterColumn title="Quick Links" links={quickLinks} align="left" />

            <FooterColumn
              title="Policies"
              links={[...policyLinks, { label: 'Cookie Settings', type: 'button', onClick: openCookieSettings }]}
              align="left"
            />

            <section className="footer-reveal flex flex-col items-center text-center md:items-start md:text-left">
              <h3 className="text-xs font-semibold uppercase tracking-[0.28em] text-[#517b4b] dark:text-[#9fbd99]">
                Contact
              </h3>

              <address className="mt-5 not-italic">
                <ul className="space-y-4 text-sm leading-6 text-[#4b5a49] dark:text-[#d6ddd2]">
                  <li className="flex items-start justify-center gap-3 md:justify-start">
                    <MapPin size={17} className="mt-1 shrink-0 text-[#517b4b] dark:text-[#9fbd99]" />
                    <span>Gangamata Bagicha, Near Nabakalebara Road, Puri 752002</span>
                  </li>
                  <li className="flex items-center justify-center gap-3 md:justify-start">
                    <MessageCircle size={17} className="shrink-0 text-[#517b4b] dark:text-[#9fbd99]" />
                    <a href="tel:+917847090866" className="footer-hover-target transition-colors duration-300 hover:text-[#517b4b] dark:hover:text-[#9fbd99]">
                      +91 7847090866
                    </a>
                  </li>
                  <li className="flex items-center justify-center gap-3 md:justify-start">
                    <Mail size={17} className="shrink-0 text-[#517b4b] dark:text-[#9fbd99]" />
                    <a href="mailto:connect@aurora.blings.com" className="footer-hover-target transition-colors duration-300 hover:text-[#517b4b] dark:hover:text-[#9fbd99]">
                      connect@aurora.blings.com
                    </a>
                  </li>
                </ul>
              </address>

              <div className="mt-6 w-full rounded-3xl border border-[#dde6d7] bg-white/70 p-5 text-left shadow-[0_18px_60px_rgba(81,123,75,0.08)] backdrop-blur-sm dark:border-[#334132] dark:bg-[#171f16]/80">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#517b4b] dark:text-[#9fbd99]">
                  Trust Note
                </p>
                <p className="mt-2 text-sm leading-6 text-[#55616f] dark:text-[#c7d0c3]">
                  This is imitation jewellery. No precious metals or stones unless specified.
                </p>
              </div>
            </section>
          </div>

          <section className="footer-reveal mt-12 rounded-[2rem] border border-[#dce5d7] bg-white/70 p-6 shadow-[0_24px_80px_rgba(81,123,75,0.08)] backdrop-blur-sm dark:border-[#324030] dark:bg-[#171f16]/80 sm:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-xl text-center lg:text-left">
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#517b4b] dark:text-[#9fbd99]">
                  Stay Close
                </p>
                <h3 className="mt-3 text-2xl font-semibold text-[#1f2937] dark:text-white">
                  Get exclusive offers &amp; new arrivals ✨
                </h3>
                <p className="mt-2 text-sm leading-6 text-[#5f6b65] dark:text-[#c7d0c3]">
                  Join our inner circle for styling drops, festive edits, and limited curation updates.
                </p>
              </div>

              <form onSubmit={handleNewsletterSubmit} className="w-full max-w-xl">
                <label htmlFor="footer-email" className="sr-only">
                  Enter your email
                </label>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <input
                    id="footer-email"
                    type="email"
                    placeholder="Enter your email"
                    value={newsletterEmail}
                    onChange={(event) => setNewsletterEmail(event.target.value)}
                    className="h-13 min-w-0 flex-1 rounded-full border border-[#d6e0cf] bg-[#f5f8f2] px-5 text-sm text-[#1f2937] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] outline-none transition-all duration-300 placeholder:text-[#7c8777] focus:border-[#517b4b] focus:ring-4 focus:ring-[#517b4b]/10 dark:border-[#3a4938] dark:bg-[#10160f] dark:text-white dark:placeholder:text-[#8f998b]"
                    aria-label="Enter your email"
                    disabled={isSubmittingNewsletter}
                    autoComplete="email"
                  />
                  <button
                    type="submit"
                    disabled={isSubmittingNewsletter}
                    className="footer-hover-target inline-flex h-13 items-center justify-center gap-2 rounded-full bg-[#517b4b] px-6 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(81,123,75,0.24)] transition-colors duration-300 hover:bg-[#476c42] focus:outline-none focus:ring-4 focus:ring-[#517b4b]/20"
                  >
                    {isSubmittingNewsletter ? 'Submitting...' : 'Get Updates'}
                    <MoveUpRight size={16} />
                  </button>
                </div>
                <p
                  className={`mt-3 text-sm ${
                    newsletterState.type === 'error'
                      ? 'text-[#9a4337] dark:text-[#f1a494]'
                      : 'text-[#5f6b65] dark:text-[#c7d0c3]'
                  }`}
                  aria-live="polite"
                >
                  {newsletterState.message || 'Get exclusive offers & new arrivals ✨'}
                </p>
              </form>
            </div>
          </section>

          <div className="footer-reveal mt-12 flex flex-col gap-6 border-t border-[#dce5d7] pt-6 dark:border-[#2f3b2e]">
            <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
              <div className="text-center md:text-left">
                <p className="text-sm font-medium text-[#1f2937] dark:text-white">
                  © 2026 Aurora Blings. All rights reserved.
                </p>
                <p className="mt-1 text-sm text-[#62705f] dark:text-[#b5beb2]">Curated with care in India ✨</p>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-2 md:justify-end">
                {paymentBadges.map((badge) => (
                  <span
                    key={badge}
                    className="rounded-full border border-[#d3ddcc] bg-white/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#41503f] dark:border-[#394838] dark:bg-[#171f16] dark:text-[#d6ddd2]"
                  >
                    {badge}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </footer>

      <button
        type="button"
        aria-label="Scroll to top"
        onClick={scrollToTop}
        className={`fixed bottom-6 right-4 z-40 inline-flex h-12 w-12 items-center justify-center rounded-full border border-[#d6dfcf] bg-white/90 text-[#2f402c] shadow-[0_16px_45px_rgba(31,41,55,0.14)] backdrop-blur-sm transition-all duration-300 hover:border-[#517b4b]/40 hover:text-[#517b4b] focus:outline-none focus:ring-4 focus:ring-[#517b4b]/15 dark:border-[#364435] dark:bg-[#171f16]/90 dark:text-[#d6ddd2] ${showScrollTop ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-4 opacity-0'}`.trim()}
      >
        <span className="text-lg leading-none">↑</span>
      </button>
    </>
  );
}
