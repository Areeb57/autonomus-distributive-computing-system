import React from 'react';

interface ResourceSliderProps {
  id: string;
  title: string;
  value: number;
  unit: string;
  displayValue?: string;
  min: number;
  max: number;
  step?: number;
  subtext?: string;
  onChange: (val: number) => void;
  disabled?: boolean;
}

export const ResourceSlider: React.FC<ResourceSliderProps> = ({
  id,
  title,
  value,
  unit,
  displayValue,
  min,
  max,
  step = 1,
  subtext,
  onChange,
  disabled = false
}) => {
  return (
    <div className="slider-card" style={{ opacity: disabled ? 0.6 : 1 }}>
      <div className="slider-top">
        <label htmlFor={id} className="slider-title">
          {title}
        </label>
        <span className="slider-current-val">
          {displayValue ? displayValue : `${value} ${unit}`}
        </span>
      </div>

      <input
        type="range"
        id={id}
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
      />

      <div className="slider-limits">
        <span>
          Min: {min} {unit}
        </span>
        {subtext && <span>{subtext}</span>}
        <span>
          Max: {max} {unit}
        </span>
      </div>
    </div>
  );
};
