import React, { useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { gsap, shouldAnimate } from '@/animations/gsapConfig';

interface VariantSelectorProps {
  label: string;
  options: string[];
  selectedOption: string;
  onSelect: (option: string) => void;
  type?: 'text' | 'color';
}

export const VariantSelector: React.FC<VariantSelectorProps> = ({ 
  label, 
  options, 
  selectedOption, 
  onSelect,
  type = 'text'
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !shouldAnimate()) {
      return;
    }

    gsap.fromTo(
      containerRef.current,
      { autoAlpha: 0.92, y: 4 },
      { autoAlpha: 1, y: 0, duration: 0.28, ease: 'power2.out' }
    );
  }, [selectedOption]);

  return (
    <div ref={containerRef} className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{label}</span>
        <span className="text-xs text-primary font-medium">{selectedOption}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            onClick={() => onSelect(option)}
            className={cn(
              "transition-all duration-200 will-change-transform hover:-translate-y-0.5",
              type === 'text' 
                ? "px-4 py-2 text-sm border-2 rounded-xl" 
                : "w-8 h-8 rounded-full border-2 p-0.5",
              selectedOption === option
                ? "border-primary bg-primary/5 text-primary"
                : "border-border hover:border-primary/50 text-muted-foreground"
            )}
          >
            {type === 'text' ? (
              option
            ) : (
              <span 
                className="block w-full h-full rounded-full" 
                style={{ backgroundColor: option.toLowerCase() }} 
              />
            )}
          </button>
        ))}
      </div>
    </div>
  );
};
