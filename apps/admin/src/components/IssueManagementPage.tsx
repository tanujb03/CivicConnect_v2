import React, { useState } from 'react';
import { Search, Filter, Calendar, MapPin, AlertCircle, Eye, Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import IssueDetailsModal from './IssueDetailsModal';


interface Issue {
  id: string;
  location: string;
  category: string;
  status: 'submitted' | 'progress' | 'resolved' | 'urgent' | 'ignored' | 'disputed';
  assignedTo: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  ward: string;
  timeAgo: string;
  description: string;
  selected?: boolean;
}

const mockIssues: Issue[] = [
  { id: 'CC001', location: 'MG Road Ranchi', category: 'Roads', status: 'progress', assignedTo: 'Road Dept', priority: 'high', ward: 'Ward 1', timeAgo: '2 hours ago', description: 'Large pothole causing traffic issues' },
  { id: 'CC002', location: 'Station Road Jamshedpur', category: 'Electrical', status: 'submitted', assignedTo: 'Electrical', priority: 'medium', ward: 'Ward 3', timeAgo: '4 hours ago', description: 'Street light not working since yesterday' },
  { id: 'CC003', location: 'Civil Lines Dhanbad', category: 'Sanitation', status: 'resolved', assignedTo: 'Sanitation', priority: 'low', ward: 'Ward 2', timeAgo: '1 day ago', description: 'Drainage blockage cleared successfully' },
  { id: 'CC004', location: 'Main Market Bokaro', category: 'Garbage', status: 'urgent', assignedTo: 'Garbage', priority: 'critical', ward: 'Ward 4', timeAgo: '3 hours ago', description: 'Garbage overflow attracting pests' },
  { id: 'CC005', location: 'Park Street Ranchi', category: 'Roads', status: 'progress', assignedTo: 'Road Dept', priority: 'medium', ward: 'Ward 1', timeAgo: '5 hours ago', description: 'Road construction work in progress' },
];

const IssueManagementPage: React.FC = () => {
  const [issues, setIssues] = useState<Issue[]>(mockIssues);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [filters, setFilters] = useState({
    search: '',
    status: 'all',
    department: 'all',
    priority: 'all',
    ward: 'all',
    clustered: false,
  });

  const handleFilterChange = (key: string, value: string | boolean) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleBulkAction = (action: string) => {
    const selectedIssues = issues.filter(issue => issue.selected);
    console.log(`Performing ${action} on`, selectedIssues);
  };

  const handleSelectAll = (checked: boolean) => {
    setIssues(issues.map(issue => ({ ...issue, selected: checked })));
  };

  const handleSelectIssue = (id: string, checked: boolean) => {
    setIssues(issues.map(issue => 
      issue.id === id ? { ...issue, selected: checked } : issue
    ));
  };

  const filteredIssues = issues.filter(issue => {
    if (filters.search && !issue.location.toLowerCase().includes(filters.search.toLowerCase()) && !issue.id.toLowerCase().includes(filters.search.toLowerCase())) return false;
    if (filters.status !== 'all' && issue.status !== filters.status) return false;
    if (filters.priority !== 'all' && issue.priority !== filters.priority) return false;
    if (filters.ward !== 'all' && issue.ward !== filters.ward) return false;
    return true;
  });

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'submitted': return 'status-submitted';
      case 'progress': return 'status-progress';
      case 'resolved': return 'status-resolved';
      case 'urgent': return 'status-urgent';
      case 'ignored': return 'bg-gray-100 text-gray-800 px-2 py-1 rounded-full text-xs font-medium';
      case 'disputed': return 'bg-purple-100 text-purple-800 px-2 py-1 rounded-full text-xs font-medium';
      default: return 'status-submitted';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-600';
      case 'high': return 'text-orange-600';
      case 'medium': return 'text-yellow-600';
      case 'low': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-civic-text-primary mb-2">Issue Management</h2>
        <p className="text-civic-text-secondary">Comprehensive issue tracking and resolution management</p>
      </div>

      {/* Filtering Panel */}
      <div className="civic-card p-4 rounded-lg border mb-6">
        <h3 className="text-lg font-semibold mb-4">Filters</h3>
        <div className="grid grid-cols-7 gap-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search by ID or location..."
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Status Filter */}
          <Select value={filters.status} onValueChange={(value) => handleFilterChange('status', value)}>
            <SelectTrigger>
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="submitted">Submitted</SelectItem>
              <SelectItem value="progress">In Progress</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
              <SelectItem value="ignored">Ignored</SelectItem>
              <SelectItem value="disputed">Disputed</SelectItem>
            </SelectContent>
          </Select>

          {/* Department Filter */}
          <Select value={filters.department} onValueChange={(value) => handleFilterChange('department', value)}>
            <SelectTrigger>
              <SelectValue placeholder="Department" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Departments</SelectItem>
              <SelectItem value="roads">Road and Transportation</SelectItem>
              <SelectItem value="electrical">Electrical</SelectItem>
              <SelectItem value="sanitation">Sanitation</SelectItem>
              <SelectItem value="garbage">Garbage Management</SelectItem>
            </SelectContent>
          </Select>

          {/* Priority Filter */}
          <Select value={filters.priority} onValueChange={(value) => handleFilterChange('priority', value)}>
            <SelectTrigger>
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priority</SelectItem>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
            </SelectContent>
          </Select>

          {/* Ward Filter */}
          <Select value={filters.ward} onValueChange={(value) => handleFilterChange('ward', value)}>
            <SelectTrigger>
              <SelectValue placeholder="Ward" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Wards</SelectItem>
              {Array.from({ length: 10 }, (_, i) => (
                <SelectItem key={i} value={`ward-${i + 1}`}>Ward {i + 1}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Date Range */}
          <div className="flex items-center space-x-2">
            <Calendar className="h-4 w-4 text-gray-400" />
            <span className="text-sm text-gray-600">Date Range</span>
          </div>

          {/* Clustered Reports */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="clustered"
              checked={filters.clustered}
              onCheckedChange={(checked) => handleFilterChange('clustered', checked as boolean)}
            />
            <label htmlFor="clustered" className="text-sm">Clustered Reports</label>
          </div>
        </div>
      </div>

      {/* Bulk Actions */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center space-x-4">
          <Checkbox
            checked={filteredIssues.every(issue => issue.selected)}
            onCheckedChange={handleSelectAll}
          />
          <span className="text-sm text-gray-600">
            {filteredIssues.filter(issue => issue.selected).length} selected
          </span>
          {filteredIssues.some(issue => issue.selected) && (
            <div className="flex space-x-2">
              <Button size="sm" variant="outline" onClick={() => handleBulkAction('reassign')}>
                Bulk Reassign
              </Button>
              <Button size="sm" variant="outline" onClick={() => handleBulkAction('status')}>
                Change Status
              </Button>
            </div>
          )}
        </div>
        <div className="text-sm text-gray-600">
          Showing {filteredIssues.length} of {issues.length} issues
        </div>
      </div>

      {/* Issues Table */}
      <div className="civic-card rounded-lg border">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Checkbox onCheckedChange={(checked) => handleSelectAll(checked as boolean)} />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Priority</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Assigned To</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredIssues.map((issue) => (
                <tr key={issue.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Checkbox
                      checked={issue.selected || false}
                      onCheckedChange={(checked) => handleSelectIssue(issue.id, checked as boolean)}
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-civic-text-primary">
                    {issue.id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">
                    {issue.location}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">
                    {issue.category}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={getStatusClass(issue.status)}>
                      {issue.status.charAt(0).toUpperCase() + issue.status.slice(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`font-medium ${getPriorityColor(issue.priority)}`}>
                      {issue.priority.charAt(0).toUpperCase() + issue.priority.slice(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">
                    {issue.assignedTo}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-civic-text-secondary">
                    {issue.timeAgo}
                  </td>
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
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <div className="text-sm text-gray-600">
            Page 1 of 3 (50 items per page)
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" size="sm" disabled>Previous</Button>
            <Button variant="outline" size="sm">Next</Button>
          </div>
        </div>
      </div>

      {/* Issue Details Modal */}
      {selectedIssue && (
        <IssueDetailsModal
          issue={selectedIssue}
          onClose={() => setSelectedIssue(null)}
        />
      )}
    </div>
  );
};

export default IssueManagementPage;