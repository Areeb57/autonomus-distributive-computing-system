import React from 'react';
import { Check } from 'lucide-react';

export interface StepItem {
  id: number;
  title: string;
  subtitle?: string;
}

interface StepperProps {
  steps: StepItem[];
  currentStep: number;
  onStepClick?: (stepId: number) => void;
}

export const Stepper: React.FC<StepperProps> = ({
  steps,
  currentStep,
  onStepClick,
}) => {
  return (
    <div className="stepper-nav" style={{ padding: '0 8px' }}>
      {steps.map((step, idx) => {
        const isCompleted = currentStep > step.id;
        const isActive = currentStep === step.id;

        return (
          <React.Fragment key={step.id}>
            <div
              className={`stepper-step ${isActive ? 'active' : ''} ${
                isCompleted ? 'completed' : ''
              }`}
              onClick={() => {
                if (isCompleted && onStepClick) {
                  onStepClick(step.id);
                }
              }}
              style={{ cursor: isCompleted ? 'pointer' : 'default' }}
            >
              <div className="stepper-circle">
                {isCompleted ? <Check size={18} strokeWidth={2.5} /> : step.id}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span
                  style={{
                    fontSize: '0.88rem',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive
                      ? 'var(--text-primary)'
                      : isCompleted
                      ? 'var(--status-online)'
                      : 'var(--text-muted)',
                  }}
                >
                  {step.title}
                </span>
                {step.subtitle && (
                  <span
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    {step.subtitle}
                  </span>
                )}
              </div>
            </div>

            {idx < steps.length - 1 && (
              <div
                className={`stepper-line ${isCompleted ? 'completed' : ''}`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
