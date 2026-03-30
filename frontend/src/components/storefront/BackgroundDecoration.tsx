import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';

export const BackgroundDecoration: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const orbs = containerRef.current.querySelectorAll('.floating-orb');
    
    orbs.forEach((orb) => {
      // Random initial position
      gsap.set(orb, {
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
      });

      // Animate movement
      gsap.to(orb, {
        x: `+=${Math.random() * 200 - 100}`,
        y: `+=${Math.random() * 200 - 100}`,
        duration: 10 + Math.random() * 20,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });

      // Animate scale
      gsap.to(orb, {
        scale: 1.5 + Math.random(),
        duration: 5 + Math.random() * 10,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });
    });
  }, []);

  return (
    <div ref={containerRef} className="fixed inset-0 pointer-events-none z-[-1] overflow-hidden bg-white">
      <div className="floating-orb w-[600px] h-[600px] -top-20 -left-20 opacity-[0.07]" />
      <div className="floating-orb w-[500px] h-[500px] top-1/2 left-3/4 opacity-[0.05]" />
      <div className="floating-orb w-[700px] h-[700px] -bottom-40 left-1/4 opacity-[0.06]" />
      
      {/* Subtle Grid Pattern Overlay */}
      <div 
        className="absolute inset-0 opacity-[0.03]" 
        style={{ 
          backgroundImage: `linear-gradient(#517b4b 1px, transparent 1px), linear-gradient(90deg, #517b4b 1px, transparent 1px)`,
          backgroundSize: '40px 40px'
        }} 
      />
    </div>
  );
};
