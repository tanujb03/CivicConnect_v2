import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import StatusBadge from './StatusBadge';
import { MapPin, Calendar, TrendingUp, Flag } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Issue {
  id: string;
  title: string;
  description: string;
  status: 'incoming' | 'ongoing' | 'resolved';
  priority: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  location: string;
  ward: string;
  reportedBy: string;
  reportedAt: Date;
  imageUrl?: string;
  daysRemaining?: number;
  isOverdue?: boolean;
  upvotes?: number;
  comments?: number;
}

interface IssueCardProps {
  issue: Issue;
  onClick?: () => void;
  showActions?: boolean;
  onMajorUpvote?: (issueId: string, isCurrentlyUpvoted: boolean) => void;
  onFlag?: (issueId: string, isCurrentlyFlagged: boolean) => void;
  className?: string;
}

const IssueCard: React.FC<IssueCardProps> = ({ 
  issue, 
  onClick, 
  showActions = false, 
  onMajorUpvote, 
  onFlag,
  className 
}) => {
  const priorityColors = {
    low: 'bg-green-100 text-green-800',
    medium: 'bg-yellow-100 text-yellow-800',
    high: 'bg-orange-100 text-orange-800',
    critical: 'bg-red-100 text-red-800',
  };

  const [isMajorUpvoted, setIsMajorUpvoted] = useState(false);
  const [isFlagged, setIsFlagged] = useState(false);

  const formatDate = (date: Date) => {
    return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(
      Math.ceil((date.getTime() - Date.now()) / (1000 * 60 * 60 * 24)), 
      'day'
    );
  };

  const handleMajorUpvoteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const newState = !isMajorUpvoted;
    setIsMajorUpvoted(newState);
    if (newState) {
      onMajorUpvote?.(issue.id, newState);
    }
  };

  const handleFlagClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const newState = !isFlagged;
    setIsFlagged(newState);
    if (newState) {
      onFlag?.(issue.id, newState);
    }
  };

  return (
    <Card 
      className={cn(
        "civic-card hover:shadow-lg transition-all duration-300 cursor-pointer group",
        className
      )}
      onClick={onClick}
    >
      <CardContent className="p-0">
        {/* Image Section */}
        <div className="relative h-40 overflow-hidden rounded-t-xl">
          {issue.imageUrl ? (
            <img 
              src={issue.imageUrl} 
              alt={issue.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-civic-green-subtle to-muted flex items-center justify-center">
              <MapPin className="w-12 h-12 text-civic-green opacity-50" />
            </div>
          )}
          
          {/* Status and Priority Overlays */}
          <div className="absolute top-3 left-3">
            <StatusBadge status={issue.status} size="sm" />
          </div>
          <div className="absolute top-3 right-3">
            <Badge className={cn("text-xs font-medium", priorityColors[issue.priority])}>
              {issue.priority.toUpperCase()}
            </Badge>
          </div>

          {/* Overdue Indicator */}
          {issue.isOverdue && (
            <div className="absolute bottom-3 right-3 bg-red-500 text-white px-2 py-1 rounded-full text-xs font-bold animate-pulse">
              OVERDUE
            </div>
          )}
        </div>

        {/* Content Section */}
        <div className="p-4 space-y-3">
          <div>
            <h3 className="font-semibold text-card-foreground line-clamp-2 group-hover:text-primary transition-colors">
              {issue.title}
            </h3>
            <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
              {issue.description}
            </p>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center space-x-1">
              <MapPin className="w-3 h-3" />
              <span className="truncate">{issue.location}</span>
            </div>
            {issue.daysRemaining !== undefined && (
              <div className="flex items-center space-x-1">
                <Calendar className="w-3 h-3" />
                <span className={issue.isOverdue ? "text-red-600 font-medium" : ""}>
                  {issue.isOverdue ? `${Math.abs(issue.daysRemaining)} days overdue` : `${issue.daysRemaining} days left`}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between text-xs">
            {/* The reporter info has been removed from here */}
            <div className="text-muted-foreground">
              {formatDate(issue.reportedAt)}
            </div>
          </div>

          {/* Action Buttons for Overlooker */}
          {showActions && (
            <div className="flex items-center justify-between pt-2 border-t border-border">
              {/* Major Upvote Button */}
              <button
                onClick={handleMajorUpvoteClick}
                className={cn(
                  "flex items-center space-x-1 px-3 py-1.5 rounded-full transition-colors text-xs font-medium",
                  isMajorUpvoted 
                    ? "bg-orange-500 text-white hover:bg-orange-600"
                    : "bg-orange-100 text-orange-800 hover:bg-orange-200"
                )}
              >
                <TrendingUp className="w-3 h-3" />
                <span>Major Upvote</span>
              </button>
              
              {/* Flag Issue Button */}
              <button
                onClick={handleFlagClick}
                className={cn(
                  "flex items-center space-x-1 px-3 py-1.5 rounded-full transition-colors text-xs font-medium",
                  isFlagged 
                    ? "bg-red-500 text-white hover:bg-red-600" // Darker filled color when flagged
                    : "bg-red-100 text-red-800 hover:bg-red-200" // Original color when not flagged
                )}
              >
                <Flag className="w-3 h-3" />
                <span>Flag Issue</span>
              </button>
            </div>
          )}

          {/* Engagement Stats */}
          {issue.upvotes && (
            <div className="flex items-center justify-between pt-2 border-t border-border text-xs text-muted-foreground">
              <div className="flex items-center space-x-1">
                <TrendingUp className="w-3 h-3" />
                <span>{issue.upvotes} upvotes</span>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default IssueCard;