import React from 'react';

/**
 * Props: value (string), onChange (fn), label (string)
 */
const ColorPicker = ({ value, onChange, label }) => {
  return (
    <div className="flex flex-col gap-2">
      {label && <label className="text-sm font-medium text-gray-700">{label}</label>}
      <div className="flex items-center gap-3">
        <input 
          type="color" 
          value={value || '#f5f0eb'} 
          onChange={(e) => onChange(e.target.value)}
          className="w-10 h-10 border-none p-0 cursor-pointer bg-transparent"
        />
        <span className="text-sm font-mono text-gray-500 uppercase">{value}</span>
      </div>
    </div>
  );
};

export default ColorPicker;
