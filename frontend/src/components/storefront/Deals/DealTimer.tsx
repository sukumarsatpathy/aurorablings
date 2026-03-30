import React, { useState, useEffect } from 'react';

interface DealTimerProps {
  endDate?: string;
}

export const DealTimer: React.FC<DealTimerProps> = ({ endDate }) => {
  const [timeLeft, setTimeLeft] = useState<{
    days: number;
    hours: number;
    minutes: number;
    seconds: number;
  } | null>(null);

  useEffect(() => {
    // Determine the target end time (defaults to end of current day if no endDate provided)
    let targetTime: number;
    if (endDate) {
      targetTime = new Date(endDate).getTime();
    } else {
      const eod = new Date();
      eod.setHours(23, 59, 59, 999);
      targetTime = eod.getTime();
    }

    const updateTimer = () => {
      const now = new Date().getTime();
      const distance = targetTime - now;

      if (distance <= 0) {
        setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0 });
      } else {
        setTimeLeft({
          days: Math.floor(distance / (1000 * 60 * 60 * 24)),
          hours: Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)),
          minutes: Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)),
          seconds: Math.floor((distance % (1000 * 60)) / 1000),
        });
      }
    };

    updateTimer(); // Initial call
    const timer = setInterval(updateTimer, 1000);
    return () => clearInterval(timer);
  }, [endDate]);

  if (!timeLeft) return null;

  return (
    <div className="flex items-center gap-4 px-5 py-2.5 bg-gray-100 border border-gray-200 rounded-full shadow-sm select-none transition-all duration-300">
      {/* Days Part */}
      <div className="flex items-center gap-2 pr-4 border-r border-gray-300/50">
        <span className="text-xl font-black text-gray-950 tracking-tight">
          {timeLeft.days}
        </span>
        <span className="text-sm font-bold text-gray-500 uppercase tracking-wider">
          Days
        </span>
      </div>
      
      {/* Time Part */}
      <div className="flex items-center gap-2 text-xl font-black text-[#517b4b] tabular-nums tracking-normal">
        <span>{timeLeft.hours.toString().padStart(2, '0')}</span>
        <span className="text-gray-300 font-medium pb-1">:</span>
        <span>{timeLeft.minutes.toString().padStart(2, '0')}</span>
        <span className="text-gray-300 font-medium pb-1">:</span>
        <span>{timeLeft.seconds.toString().padStart(2, '0')}</span>
      </div>
    </div>
  );
};
