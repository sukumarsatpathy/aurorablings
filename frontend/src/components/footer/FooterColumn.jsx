import React from 'react';

const baseLinkClass =
  'group relative inline-flex w-fit items-center text-sm leading-6 text-[#4b5a49] transition-colors duration-300 hover:text-[#517b4b] dark:text-[#d6ddd2] dark:hover:text-[#9fbd99]';

export function FooterColumn({ title, links = [], align = 'left', className = '' }) {
  const alignmentClass = align === 'center' ? 'items-center text-center' : 'items-start text-left';

  return (
    <div className={`footer-reveal flex flex-col ${alignmentClass} ${className}`.trim()}>
      <h3 className="text-xs font-semibold uppercase tracking-[0.28em] text-[#517b4b] dark:text-[#9fbd99]">
        {title}
      </h3>

      <nav className={`mt-5 flex flex-col gap-3 ${alignmentClass}`.trim()} aria-label={title}>
        {links.map((link) => {
          const content = (
            <>
              <span>{link.label}</span>
              <span className="absolute -bottom-0.5 left-0 h-px w-full origin-left scale-x-0 bg-current transition-transform duration-300 group-hover:scale-x-100" />
            </>
          );

          if (link.type === 'button') {
            return (
              <button
                key={link.label}
                type="button"
                onClick={link.onClick}
                className={`${baseLinkClass} footer-hover-target cursor-pointer border-0 bg-transparent p-0`.trim()}
              >
                {content}
              </button>
            );
          }

          if (link.external) {
            return (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className={`${baseLinkClass} footer-hover-target`.trim()}
              >
                {content}
              </a>
            );
          }

          return (
            <a key={link.label} href={link.href} className={`${baseLinkClass} footer-hover-target`.trim()}>
              {content}
            </a>
          );
        })}
      </nav>
    </div>
  );
}
