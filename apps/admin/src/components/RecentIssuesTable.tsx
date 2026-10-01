import React, { useState } from 'react';
import { Eye, Edit, ArrowUpDown, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Issue {
  id: string;
  location: string;
  category: string;
  status: 'submitted' | 'progress' | 'resolved' | 'urgent';
  assignedTo: string;
  timeAgo: string;
}

const issuesData: Issue[] = [
  { id: 'CC001', location: 'MG Road Ranchi', category: 'Roads', status: 'progress', assignedTo: 'Road Dept', timeAgo: '2 hours ago' },
  { id: 'CC002', location: 'Station Road Jamshedpur', category: 'Electrical', status: 'submitted', assignedTo: 'Electrical', timeAgo: '4 hours ago' },
  { id: 'CC003', location: 'Civil Lines Dhanbad', category: 'Sanitation', status: 'resolved', assignedTo: 'Sanitation', timeAgo: '1 day ago' },
  { id: 'CC004', location: 'Main Market Bokaro', category: 'Garbage', status: 'urgent', assignedTo: 'Garbage', timeAgo: '3 hours ago' },
  { id: 'CC005', location: 'Park Street Ranchi', category: 'Roads', status: 'progress', assignedTo: 'Road Dept', timeAgo: '5 hours ago' },
  { id: 'CC006', location: 'Central Avenue Jamshedpur', category: 'Electrical', status: 'submitted', assignedTo: 'Electrical', timeAgo: '6 hours ago' },
  { id: 'CC007', location: 'Ring Road Dhanbad', category: 'Roads', status: 'resolved', assignedTo: 'Road Dept', timeAgo: '2 days ago' },
  { id: 'CC008', location: 'Market Street Bokaro', category: 'Sanitation', status: 'urgent', assignedTo: 'Sanitation', timeAgo: '1 hour ago' },
  { id: 'CC009', location: 'Gandhi Chowk Ranchi', category: 'Garbage', status: 'progress', assignedTo: 'Garbage', timeAgo: '8 hours ago' },
  { id: 'CC010', location: 'Railway Station Road', category: 'Electrical', status: 'submitted', assignedTo: 'Electrical', timeAgo: '12 hours ago' },
];

const RecentIssuesTable: React.FC = () => {
  const [sortField, setSortField] = useState<keyof Issue>('id');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  const handleSort = (field: keyof Issue) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedIssues = [...issuesData].sort((a, b) => {
    const aValue = a[sortField];
    const bValue = b[sortField];

    if (sortDirection === 'asc') {
      return aValue > bValue ? 1 : -1;
    } else {
      return aValue < bValue ? 1 : -1;
    }
  });

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'submitted': return 'status-submitted';
      case 'progress': return 'status-progress';
      case 'resolved': return 'status-resolved';
      case 'urgent': return 'status-urgent';
      default: return 'status-submitted';
    }
  };

  return (
    <div className="civic-card rounded-lg border border-gray-200 mb-8">
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-civic-text-primary">Recent Issues</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {['id','location','category','status'].map((field) => (
                <th key={field} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort(field as keyof Issue)}
                    className="flex items-center space-x-1 hover:text-gray-700"
                  >
                    <span>{field.charAt(0).toUpperCase() + field.slice(1)}</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </button>
                </th>
              ))}
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Assigned To</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedIssues.map((issue) => (
              <tr key={issue.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-civic-text-primary">{issue.id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">{issue.location}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">{issue.category}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`${getStatusClass(issue.status)}`}>
                    {issue.status.charAt(0).toUpperCase() + issue.status.slice(1)}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">{issue.assignedTo}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">{issue.timeAgo}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <div className="flex space-x-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-blue-600 hover:text-blue-700"
                      onClick={() => setSelectedIssue(issue)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-green-600 hover:text-green-700">
                      <Edit className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal for viewing details */}
      {selectedIssue && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md relative">
            <button
              onClick={() => setSelectedIssue(null)}
              className="absolute top-3 right-3 text-gray-500 hover:text-gray-700"
            >
              <X className="h-5 w-5" />
            </button>
            <h2 className="text-xl font-semibold mb-4">Issue Details</h2>
            <p><strong>ID:</strong> {selectedIssue.id}</p>
            <p><strong>Location:</strong> {selectedIssue.location}</p>
            <p><strong>Category:</strong> {selectedIssue.category}</p>
            <p><strong>Status:</strong> {selectedIssue.status}</p>
            <p><strong>Assigned To:</strong> {selectedIssue.assignedTo}</p>
            <p><strong>Reported:</strong> {selectedIssue.timeAgo}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default RecentIssuesTable;
