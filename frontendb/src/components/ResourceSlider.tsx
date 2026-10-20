import React, { useEffect, useRef, useState } from 'react';

interface ResourceSliderProps {
  id: string;
  title: string;
  value: number;
  unit: string;
  displayValue?: string;
  min: number;
  max: number;
  step?: number;
  /** Increment accepted by the numeric input; defaults to the slider increment. */
  inputStep?: number;
  subtext?: string;
  onChange: (val: number) => void;
  disabled?: boolean;
}

function decimalPlaces(value: number): number {
  const text = String(value);
  return text.includes('.') ? text.split('.')[1].length : 0;
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
  inputStep = step,
  subtext,
  onChange,
  disabled = false
}) => {
  const [manualValue, setManualValue] = useState(String(value));
  const [editing, setEditing] = useState(false);
  const cancelBlurCommit = useRef(false);

  useEffect(() => {
    if (!editing) setManualValue(String(value));
  }, [value, min, max, editing]);

  const commitManualValue = () => {
    if (cancelBlurCommit.current) {
      cancelBlurCommit.current = false;
      setManualValue(String(value));
      setEditing(false);
      return;
    }
    const parsed = manualValue.trim() === '' ? Number.NaN : Number(manualValue);
    if (!Number.isFinite(parsed)) {
      setManualValue(String(value));
      setEditing(false);
      return;
    }

    const safeMin = Math.min(min, max);
    const safeMax = Math.max(min, max);
    const clamped = Math.min(safeMax, Math.max(safeMin, parsed));
    const safeStep = inputStep > 0 ? inputStep : 1;
    const snapped = safeMin + Math.round((clamped - safeMin) / safeStep) * safeStep;
    const precision = Math.min(6, Math.max(decimalPlaces(inputStep), decimalPlaces(safeMin), decimalPlaces(safeMax)));
    const result = Number(Math.min(safeMax, Math.max(safeMin, snapped)).toFixed(precision));

    setManualValue(String(result));
    setEditing(false);
    onChange(result);
  };

  const inputStyle: React.CSSProperties = {
    width: 88,
    minWidth: 72,
    boxSizing: 'border-box',
    padding: '5px 7px',
    border: '1px solid var(--border-subtle)',
    borderRadius: 6,
    background: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    font: 'inherit',
    fontSize: 12,
  };

  return (
    <div className="slider-card" style={{ opacity: disabled ? 0.6 : 1 }}>
      <div className="slider-top" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <label htmlFor={id} className="slider-title">
          {title}
        </label>
        <div style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: 7 }}>
          <span className="slider-current-val">
            {displayValue ? displayValue : `${value} ${unit}`}
          </span>
          <label htmlFor={`${id}-manual`} style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
            Manual
          </label>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <input
              id={`${id}-manual`}
              type="number"
              aria-label={`${title} manual value in ${unit}`}
              min={Math.min(min, max)}
              max={Math.max(min, max)}
              step={inputStep}
              value={manualValue}
              onFocus={() => setEditing(true)}
              onChange={(event) => setManualValue(event.target.value)}
              onBlur={commitManualValue}
              onKeyDown={(event) => {
                if (event.key === 'Enter') (event.currentTarget as HTMLInputElement).blur();
                if (event.key === 'Escape') {
                  event.preventDefault();
                  cancelBlurCommit.current = true;
                  setManualValue(String(value));
                  setEditing(false);
                  (event.currentTarget as HTMLInputElement).blur();
                }
              }}
              disabled={disabled}
              style={inputStyle}
            />
            <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>{unit}</span>
          </div>
        </div>
      </div>

      <input
        type="range"
        id={id}
        min={min}
        max={max}
        step={step}
        value={Math.min(Math.max(value, Math.min(min, max)), Math.max(min, max))}
        onChange={(event) => onChange(Number(event.target.value))}
        disabled={disabled || max <= min}
      />

      <div className="slider-limits">
        <span>Min: {min} {unit}</span>
        {subtext && <span>{subtext}</span>}
        <span>Max: {max} {unit}</span>
      </div>
    </div>
  );
};
