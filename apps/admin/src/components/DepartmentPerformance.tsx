import React from 'react';
import { Clock, FileText } from 'lucide-react';

interface DepartmentData {
  name: string;
  avgResponseTime: string;
  pendingCount: number;
}

const departmentData: DepartmentData[] = [
  { name: 'Road and Transportation', avgResponseTime: '3.2 hours', pendingCount: 23 },
  { name: 'Electrical', avgResponseTime: '4.7 hours', pendingCount: 18 },
  { name: 'Sanitation', avgResponseTime: '2.1 hours', pendingCount: 12 },
  { name: 'Garbage Management', avgResponseTime: '5.3 hours', pendingCount: 31 },
];

const DepartmentPerformance: React.FC = () => {
  return (
    <div className="civic-card p-6">
      <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Department Response Times</h3>
      
      <div className="space-y-4">
        {departmentData.map((dept, index) => (
          <div key={index} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
            <div className="flex justify-between items-start mb-2">
              <h4 className="font-medium text-civic-text-primary">{dept.name}</h4>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center space-x-2 text-sm text-civic-text-secondary">
                <Clock className="h-4 w-4" />
                <span>Avg Response: {dept.avgResponseTime}</span>
              </div>
              
              <div className="flex items-center space-x-2 text-sm text-civic-text-secondary">
                <FileText className="h-4 w-4" />
                <span>Pending: {dept.pendingCount} issues</span>
              </div>
            </div>

            {/* Response Time Bar */}
            <div className="mt-3">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    parseFloat(dept.avgResponseTime) < 3 ? 'bg-green-500' :
                    parseFloat(dept.avgResponseTime) < 5 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.min((parseFloat(dept.avgResponseTime) / 6) * 100, 100)}%` }}
                ></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DepartmentPerformance;