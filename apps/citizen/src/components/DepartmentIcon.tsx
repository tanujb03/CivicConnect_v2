import React from 'react';
import { Car, Trash2, Droplet, Lightbulb } from 'lucide-react';

interface DepartmentIconProps {
  category: 'roads' | 'sanitation' | 'water' | 'lighting';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeMap = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12'
};

const colorMap = {
  roads: 'text-blue-600 bg-blue-100',
  sanitation: 'text-green-600 bg-green-100',
  water: 'text-cyan-600 bg-cyan-100',
  lighting: 'text-yellow-600 bg-yellow-100'
};

export const DepartmentIcon: React.FC<DepartmentIconProps> = ({ 
  category, 
  size = 'md', 
  className = '' 
}) => {
  const IconComponent = {
    roads: Car,
    sanitation: Trash2,
    water: Droplet,
    lighting: Lightbulb
  }[category];

  return (
    <div className={`
      ${sizeMap[size]} 
      ${colorMap[category]} 
      rounded-full flex items-center justify-center p-2
      ${className}
    `}>
      <IconComponent className={sizeMap[size]} />
    </div>
  );
};