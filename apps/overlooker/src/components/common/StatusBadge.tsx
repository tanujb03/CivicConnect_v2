import React from 'react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { 
  Clock, 
  CheckCircle, 
  AlertTriangle, 
  MessageSquare, 
  Ban,
  Flame,
  Calendar
} from 'lucide-react';

export type IssueStatus = 
  | 'submitted' 
  | 'in-progress' 
  | 'resolved' 
  | 'urgent' 
  | 'overdue' 
  | 'disputed' 
  | 'ignored';

interface StatusBadgeProps {
  status: IssueStatus;
  className?: string;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const statusConfig = {
  submitted: {
    label: 'Submitted',
    icon: Calendar,
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  'in-progress': {
    label: 'In Progress',
    icon: Clock,
    className: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  resolved: {
    label: 'Resolved',
    icon: CheckCircle,
    className: 'civic-status-resolved',
  },
  urgent: {
    label: 'Urgent',
    icon: Flame,
    className: 'civic-status-urgent animate-pulse',
  },
  overdue: {
    label: 'Overdue',
    icon: AlertTriangle,
    className: 'civic-status-overdue',
  },
  disputed: {
    label: 'Disputed',
    icon: MessageSquare,
    className: 'civic-status-disputed',
  },
  ignored: {
    label: 'Ignored',
    icon: Ban,
    className: 'civic-status-ignored',
  },
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ 
  status, 
  className, 
  showIcon = true, 
  size = 'md' 
}) => {
  const config = statusConfig[status];
  const Icon = config.icon;
  
  const sizeClasses = {
    sm: 'text-xs px-2 py-1',
    md: 'text-sm px-2.5 py-1.5',
    lg: 'text-base px-3 py-2',
  };

  return (
    <Badge 
      className={cn(
        'inline-flex items-center font-medium rounded-full border',
        config.className,
        sizeClasses[size],
        className
      )}
    >
      {showIcon && <Icon className={cn(
        "mr-1.5",
        size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-5 h-5' : 'w-4 h-4'
      )} />}
      {config.label}
    </Badge>
  );
};

export default StatusBadge;