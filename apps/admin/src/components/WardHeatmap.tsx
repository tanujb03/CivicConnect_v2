import React from 'react';

interface WardData {
  ward: string;
  issueCount: number;
  density: 'high' | 'medium' | 'low';
}

const wardData: WardData[] = [
  { ward: 'Ward 1', issueCount: 67, density: 'high' },
  { ward: 'Ward 2', issueCount: 34, density: 'medium' },
  { ward: 'Ward 3', issueCount: 12, density: 'low' },
  { ward: 'Ward 4', issueCount: 56, density: 'high' },
  { ward: 'Ward 5', issueCount: 28, density: 'medium' },
  { ward: 'Ward 6', issueCount: 8, density: 'low' },
  { ward: 'Ward 7', issueCount: 45, density: 'medium' },
  { ward: 'Ward 8', issueCount: 73, density: 'high' },
  { ward: 'Ward 9', issueCount: 19, density: 'low' },
];

const WardHeatmap: React.FC = () => {
  const getDensityClass = (density: string) => {
    switch (density) {
      case 'high': return 'density-high';
      case 'medium': return 'density-medium';
      case 'low': return 'density-low';
      default: return 'density-low';
    }
  };

  const getDensityLabel = (density: string) => {
    switch (density) {
      case 'high': return 'High density (>50)';
      case 'medium': return 'Medium density (20-50)';
      case 'low': return 'Low density (<20)';
      default: return '';
    }
  };

  return (
    <div className="civic-card p-6">
      <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Ward-wise Issue Heatmap</h3>
      
      <div className="grid grid-cols-3 gap-4">
        {wardData.map((ward) => (
          <div
            key={ward.ward}
            className={`p-4 rounded-lg border-2 transition-all hover:shadow-md cursor-pointer ${getDensityClass(ward.density)}`}
          >
            <h4 className="font-semibold text-lg">{ward.ward}</h4>
            <p className="text-2xl font-bold mt-1">{ward.issueCount}</p>
            <p className="text-sm mt-1 capitalize">
              {getDensityLabel(ward.density)}
            </p>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex justify-center space-x-6 mt-6 text-sm">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded bg-red-200 border border-red-300"></div>
          <span>High (&gt;50)</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded bg-yellow-200 border border-yellow-300"></div>
          <span>Medium (20-50)</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded bg-green-200 border border-green-300"></div>
          <span>Low (&lt;20)</span>
        </div>
      </div>
    </div>
  );
};

export default WardHeatmap;