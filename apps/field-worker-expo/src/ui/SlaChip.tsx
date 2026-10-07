import React from 'react';
import { Colors } from '../theme/tokens';
import { Chip } from './Chip';

export interface SlaChipProps {
  deadline: string; // ISO 8601
  size?: 'sm' | 'md';
  shadow?: boolean;
}

export const SlaChip: React.FC<SlaChipProps> = ({
  deadline,
  size = 'md',
  shadow = false,
}) => {
  const getSlaDetails = () => {
    try {
      const now = new Date().getTime();
      const target = new Date(deadline).getTime();
      const diffMs = target - now;

      if (isNaN(diffMs)) {
        return { label: 'SLA: --', bg: Colors.ground, text: Colors.ink };
      }

      if (diffMs <= 0) {
        const overdueHours = Math.abs(Math.round(diffMs / (1000 * 60 * 60)));
        return {
          label: overdueHours > 0 ? `BREACHED (${overdueHours}H)` : 'BREACHED',
          bg: Colors.fire,
          text: Colors.onFire,
        };
      }

      const totalHours = Math.floor(diffMs / (1000 * 60 * 60));
      const totalMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      if (totalHours < 2) {
        const text = totalHours > 0 ? `${totalHours}H ${totalMinutes}M` : `${totalMinutes}M`;
        return {
          label: `SLA: ${text}`,
          bg: Colors.amber,
          text: Colors.ink,
        };
      }

      return {
        label: `SLA: ${totalHours}H`,
        bg: Colors.ground,
        text: Colors.ink,
      };
    } catch {
      return { label: 'SLA: --', bg: Colors.ground, text: Colors.ink };
    }
  };

  const { label, bg, text } = getSlaDetails();

  return (
    <Chip
      label={label}
      backgroundColor={bg}
      textColor={text}
      size={size}
      shadow={shadow}
    />
  );
};
