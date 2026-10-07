import React from 'react';
import { Colors } from '../theme/tokens';
import { Chip } from './Chip';
import type { WorkOrderStatus } from '../api/types';

export interface StatusChipProps {
  status: WorkOrderStatus;
  size?: 'sm' | 'md';
  shadow?: boolean;
}

export const StatusChip: React.FC<StatusChipProps> = ({
  status,
  size = 'md',
  shadow = false,
}) => {
  const getConfig = () => {
    switch (status) {
      case 'OPEN':
        return {
          label: 'ASSIGNED',
          bg: Colors.surface,
          text: Colors.ink,
        };
      case 'IN_PROGRESS':
        return {
          label: 'IN PROGRESS',
          bg: Colors.limeTint,
          text: Colors.ink,
        };
      case 'DONE':
        return {
          label: 'RESOLVED',
          bg: Colors.wine,
          text: Colors.onWine,
        };
      case 'CANCELLED':
        return {
          label: 'CANCELLED',
          bg: Colors.dot,
          text: Colors.muted,
        };
      default:
        return {
          label: status,
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
