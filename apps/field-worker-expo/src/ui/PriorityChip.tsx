import React from 'react';
import { Colors } from '../theme/tokens';
import { Chip } from './Chip';
import type { Priority } from '../api/types';

export interface PriorityChipProps {
  priority: Priority;
  size?: 'sm' | 'md';
  shadow?: boolean;
}

export const PriorityChip: React.FC<PriorityChipProps> = ({
  priority,
  size = 'md',
  shadow = false,
}) => {
  const getConfig = () => {
    switch (priority) {
      case 'P1':
        return {
          label: 'P1 CRITICAL',
          bg: Colors.fire,
          text: Colors.onFire,
        };
      case 'P2':
        return {
          label: 'P2 HIGH',
          bg: Colors.amber,
          text: Colors.ink,
        };
      case 'P3':
      default:
        return {
          label: 'P3 NORMAL',
          bg: Colors.ground,
          text: Colors.ink,
        };
    }
  };

  const config = getConfig();

  return (
    <Chip
      label={config.label}
      backgroundColor={config.bg}
      textColor={config.text}
      size={size}
      shadow={shadow}
    />
  );
};
