import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';

function InstagramIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] fill-none stroke-current" aria-hidden="true">
      <rect x="3.5" y="3.5" width="17" height="17" rx="5" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="4" strokeWidth="1.8" />
      <circle cx="17.2" cy="6.8" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] fill-current" aria-hidden="true">
      <path d="M13.5 21v-7.1h2.4l.4-2.9h-2.8V9.1c0-.84.23-1.41 1.43-1.41H16.4V5.1c-.72-.08-1.43-.12-2.16-.11-2.14 0-3.61 1.31-3.61 3.72v2.08H8.25v2.9h2.42V21h2.83Z" />
    </svg>
  );
}

function YoutubeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] fill-current" aria-hidden="true">
      <path d="M21.6 7.2a2.8 2.8 0 0 0-2-2c-1.77-.48-7.6-.48-7.6-.48s-5.83 0-7.6.48a2.8 2.8 0 0 0-2 2A29.4 29.4 0 0 0 2 12a29.4 29.4 0 0 0 .4 4.8 2.8 2.8 0 0 0 2 2c1.77.48 7.6.48 7.6.48s5.83 0 7.6-.48a2.8 2.8 0 0 0 2-2A29.4 29.4 0 0 0 22 12a29.4 29.4 0 0 0-.4-4.8ZM10.2 15.35v-6.7L16 12l-5.8 3.35Z" />
    </svg>
  );
}

const socials = [
  {
    label: 'Instagram',
    href: 'https://www.instagram.com/aurora_blings',
    Icon: InstagramIcon,
  },
  {
    label: 'Facebook',
    href: '#',
    Icon: FacebookIcon,
  },
  {
    label: 'YouTube',
    href: 'https://www.youtube.com/@aurora_blings',
    Icon: YoutubeIcon,
  },
];

export function SocialIcons({ centered = false }) {
  const refs = useRef([]);

  useEffect(() => {
    const cleanups = refs.current.map((element) => {
      if (!element) return null;

      const enter = () => gsap.to(element, { y: -2, scale: 1.04, duration: 0.28, ease: 'power2.out' });
      const leave = () => gsap.to(element, { y: 0, scale: 1, duration: 0.28, ease: 'power2.out' });

      element.addEventListener('mouseenter', enter);
      element.addEventListener('mouseleave', leave);
      element.addEventListener('focus', enter);
      element.addEventListener('blur', leave);

      return () => {
        element.removeEventListener('mouseenter', enter);
        element.removeEventListener('mouseleave', leave);
        element.removeEventListener('focus', enter);
        element.removeEventListener('blur', leave);
      };
    });

    return () => {
      cleanups.forEach((cleanup) => cleanup && cleanup());
    };
  }, []);

  return (
    <div className={`flex flex-wrap gap-3 ${centered ? 'justify-center' : 'justify-start'}`.trim()}>
      {socials.map(({ href, label, Icon }, index) => (
        <a
          key={label}
          ref={(node) => {
            refs.current[index] = node;
          }}
          href={href}
          target={href.startsWith('http') ? '_blank' : undefined}
          rel={href.startsWith('http') ? 'noreferrer' : undefined}
          aria-label={label}
          className="footer-hover-target inline-flex h-11 w-11 items-center justify-center rounded-full border border-[#cfdac7] bg-white/80 text-[#334331] shadow-[0_8px_30px_rgba(81,123,75,0.08)] transition-colors duration-300 hover:border-[#b7c8ad] hover:text-[#517b4b] dark:border-[#3f5140] dark:bg-[#182117]/80 dark:text-[#d6ddd2] dark:hover:border-[#64885e] dark:hover:text-[#9fbd99]"
        >
          <Icon />
        </a>
      ))}
    </div>
  );
}
