import React, { useState } from 'react';
import { AlertTriangle, RotateCcw, Eye, MessageSquare, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';

interface IgnoredIssue {
  id: string;
  location: string;
  category: string;
  reason: string;
  ignoredBy: string;
  ignoredDate: string;
  originalSubmission: string;
}

interface DisputedIssue {
  id: string;
  location: string;
  category: string;
  reassignmentCount: number;
  currentDepartment: string;
  previousDepartments: string[];
  disputeReason: string;
  citizenComplaint: string;
}

interface OverdueIssue {
  id: string;
  location: string;
  category: string;
  daysOverdue: number;
  assignedTo: string;
  lastUpdate: string;
  status: 'submitted' | 'progress';
}

const ignoredIssues: IgnoredIssue[] = [
  { id: 'CC101', location: 'Main Road Ranchi', category: 'Roads', reason: 'Duplicate', ignoredBy: 'Admin Kumar', ignoredDate: '2024-01-14', originalSubmission: '2024-01-12' },
  { id: 'CC102', location: 'Park Street', category: 'Sanitation', reason: 'Spam', ignoredBy: 'Admin Singh', ignoredDate: '2024-01-13', originalSubmission: '2024-01-11' },
  { id: 'CC103', location: 'Market Area', category: 'Garbage', reason: 'Irrelevant', ignoredBy: 'Admin Verma', ignoredDate: '2024-01-12', originalSubmission: '2024-01-10' },
];

const disputedIssues: DisputedIssue[] = [
  { 
    id: 'CC201', 
    location: 'Central Avenue', 
    category: 'Mixed', 
    reassignmentCount: 4, 
    currentDepartment: 'Electrical', 
    previousDepartments: ['Roads', 'Sanitation', 'Garbage'], 
    disputeReason: 'Overlapping jurisdiction',
    citizenComplaint: 'Issue has been passed between departments for 2 weeks without resolution'
  },
  { 
    id: 'CC202', 
    location: 'Industrial Area', 
    category: 'Infrastructure', 
    reassignmentCount: 3, 
    currentDepartment: 'Roads', 
    previousDepartments: ['Electrical', 'Sanitation'], 
    disputeReason: 'Unclear responsibility',
    citizenComplaint: 'Each department claims it is not their responsibility'
  },
];

const overdueIssues: OverdueIssue[] = [
  { id: 'OD301', location: 'City Bypass', category: 'Roads', daysOverdue: 25, assignedTo: 'Roads Dept.', lastUpdate: '2024-01-01', status: 'progress' },
  { id: 'OD302', location: 'Sector 5, Housing Society', category: 'Water', daysOverdue: 18, assignedTo: 'Water Works', lastUpdate: '2024-01-05', status: 'submitted' },
  { id: 'OD303', location: 'Old Market Road', category: 'Lighting', daysOverdue: 35, assignedTo: 'Electrical Dept.', lastUpdate: '2023-12-28', status: 'progress' },
];

interface SpecialBoardsPageProps {
  userRole: 'admin' | 'overseer';
}

const SpecialBoardsPage: React.FC<SpecialBoardsPageProps> = ({ userRole }) => {
  const [selectedIgnored, setSelectedIgnored] = useState<string[]>([]);
  const [reactivationReason, setReactivationReason] = useState('');
  const [activeTab, setActiveTab] = useState<'ignored' | 'disputed' | 'overdue'>('ignored');

  const handleSelectIgnored = (id: string, checked: boolean) => {
    if (checked) {
      setSelectedIgnored([...selectedIgnored, id]);
    } else {
      setSelectedIgnored(selectedIgnored.filter(selectedId => selectedId !== id));
    }
  };

  const handleBulkReactivate = () => {
    console.log('Reactivating issues:', selectedIgnored, 'Reason:', reactivationReason);
    setSelectedIgnored([]);
    setReactivationReason('');
  };

  const handleDisputeResolution = (issueId: string, action: 'escalate' | 'assign' | 'merge') => {
    console.log(`Resolving dispute ${issueId} with action: ${action}`);
  };

  const handleOverdueAction = (issueId: string, action: 'escalate' | 'remind') => {
    console.log(`Overdue issue ${issueId} action: ${action}`);
  };

  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-civic-text-primary mb-2">Special Boards</h2>
        <p className="text-civic-text-secondary">Manage ignored, disputed, and overdue issues requiring special attention</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-4 mb-6">
        <Button
          variant={activeTab === 'ignored' ? 'default' : 'outline'}
          onClick={() => setActiveTab('ignored')}
          className="flex items-center space-x-2"
        >
          <XCircle className="h-4 w-4" />
          <span>Ignored Issues</span>
        </Button>
        <Button
          variant={activeTab === 'disputed' ? 'default' : 'outline'}
          onClick={() => setActiveTab('disputed')}
          className="flex items-center space-x-2"
        >
          <AlertTriangle className="h-4 w-4" />
          <span>Disputed Issues</span>
        </Button>
        <Button
          variant={activeTab === 'overdue' ? 'default' : 'outline'}
          onClick={() => setActiveTab('overdue')}
          className="flex items-center space-x-2"
        >
          <Clock className="h-4 w-4" />
          <span>Overdue Issues</span>
        </Button>
      </div>

      {activeTab === 'ignored' && (
        <div className="space-y-6">
          {/* Statistics Card */}
          <div className="civic-card p-6">
            <h3 className="text-lg font-semibold mb-4">Ignored Issues Statistics</h3>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-civic-text-primary">{ignoredIssues.length}</p>
                <p className="text-sm text-civic-text-secondary">Total Ignored</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-orange-600">15%</p>
                <p className="text-sm text-civic-text-secondary">Ignored Ratio</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-600">23</p>
                <p className="text-sm text-civic-text-secondary">Spam Reports</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-600">12</p>
                <p className="text-sm text-civic-text-secondary">Duplicates</p>
              </div>
            </div>
          </div>

          {/* Bulk Actions */}
          {selectedIgnored.length > 0 && (
            <div className="civic-card p-4">
              <div className="flex justify-between items-end">
                <div className="flex-1 mr-4">
                  <label className="block text-sm font-medium mb-2">Reactivation Reason</label>
                  <Textarea
                    placeholder="Explain why these issues should be reactivated..."
                    value={reactivationReason}
                    onChange={(e) => setReactivationReason(e.target.value)}
                    rows={2}
                  />
                </div>
                <Button
                  onClick={handleBulkReactivate}
                  disabled={!reactivationReason.trim()}
                  className="btn-civic-success"
                >
                  Reactivate {selectedIgnored.length} Issues
                </Button>
              </div>
            </div>
          )}

          {/* Ignored Issues Table */}
          <div className="civic-card">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold">Ignored Issues</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left">
                      <Checkbox
                        checked={selectedIgnored.length === ignoredIssues.length}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedIgnored(ignoredIssues.map(issue => issue.id));
                          } else {
                            setSelectedIgnored([]);
                          }
                        }}
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ignored By</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {ignoredIssues.map((issue) => (
                    <tr key={issue.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Checkbox
                          checked={selectedIgnored.includes(issue.id)}
                          onCheckedChange={(checked) => handleSelectIgnored(issue.id, checked as boolean)}
                        />
                      </td>
                      <td className="px-6 py-4 text-sm font-medium">{issue.id}</td>
                      <td className="px-6 py-4 text-sm">{issue.location}</td>
                      <td className="px-6 py-4 text-sm">{issue.category}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">
                          {issue.reason}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">{issue.ignoredBy}</td>
                      <td className="px-6 py-4 text-sm">{issue.ignoredDate}</td>
                      <td className="px-6 py-4">
                        <div className="flex space-x-2">
                          <Button variant="ghost" size="sm" className="text-blue-600">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-green-600">
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'disputed' && (
        <div className="space-y-6">
          {/* Disputed Issues Table */}
          <div className="civic-card">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold">Cross-Department Disputes</h3>
            </div>
            <div className="space-y-4 p-6">
              {disputedIssues.map((issue) => (
                <div key={issue.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h4 className="font-semibold text-lg">{issue.id} - {issue.location}</h4>
                      <p className="text-sm text-gray-600">Category: {issue.category}</p>
                    </div>
                    <span className="px-3 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-800">
                      {issue.reassignmentCount} Reassignments
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <h5 className="font-medium mb-2">Assignment History</h5>
                      <div className="space-y-1">
                        {issue.previousDepartments.map((dept, index) => (
                          <div key={index} className="text-sm text-gray-600">
                            {index + 1}. {dept}
                          </div>
                        ))}
                        <div className="text-sm font-medium text-civic-primary">
                          Current: {issue.currentDepartment}
                        </div>
                      </div>
                    </div>
                    <div>
                      <h5 className="font-medium mb-2">Dispute Details</h5>
                      <p className="text-sm text-gray-600 mb-2">{issue.disputeReason}</p>
                      <div className="bg-yellow-50 p-2 rounded text-sm">
                        <strong>Citizen:</strong> {issue.citizenComplaint}
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-between items-center pt-4 border-t">
                    <div className="text-sm text-gray-500">
                      Requires {userRole === 'overseer' ? 'overseer' : 'senior admin'} intervention
                    </div>
                    <div className="space-x-2">
                      {userRole === 'overseer' && (
                        <>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleDisputeResolution(issue.id, 'assign')}
                          >
                            Force Assign
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleDisputeResolution(issue.id, 'escalate')}
                          >
                            Escalate
                          </Button>
                        </>
                      )}
                      <Button 
                        size="sm" 
                        className="btn-civic-primary"
                        onClick={() => handleDisputeResolution(issue.id, 'merge')}
                      >
                        <MessageSquare className="h-4 w-4 mr-1" />
                        Mediate
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Overseer Special Powers */}
          {userRole === 'overseer' && (
            <div className="civic-card p-6 bg-blue-50 border-blue-200">
              <h3 className="text-lg font-semibold text-blue-800 mb-4">Overseer Special Powers</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Button className="w-full" variant="outline">
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Re-raise Resolved Issues
                  </Button>
                  <Button className="w-full" variant="outline">
                    <AlertTriangle className="h-4 w-4 mr-2" />
                    Assign Major Upvote Badge
                  </Button>
                </div>
                <div className="space-y-2">
                  <Button className="w-full" variant="outline">
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Force Department Override
                  </Button>
                  <Button className="w-full btn-civic-danger">
                    <AlertTriangle className="h-4 w-4 mr-2" />
                    Emergency Escalation
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'overdue' && (
        <div className="space-y-6">
          {/* Overdue Issues Table */}
          <div className="civic-card">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold">Overdue Issues</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Days Overdue</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Assigned To</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Update</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {overdueIssues.map((issue) => (
                    <tr key={issue.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium">{issue.id}</td>
                      <td className="px-6 py-4 text-sm">{issue.location}</td>
                      <td className="px-6 py-4 text-sm">{issue.category}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-orange-100 text-orange-800">
                          {issue.daysOverdue} days
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">{issue.assignedTo}</td>
                      <td className="px-6 py-4 text-sm">{issue.lastUpdate}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${issue.status === 'submitted' ? 'bg-blue-100 text-blue-800' : 'bg-yellow-100 text-yellow-800'}`}>
                          {issue.status.charAt(0).toUpperCase() + issue.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex space-x-2">
                          <Button variant="ghost" size="sm" className="text-blue-600" onClick={() => handleOverdueAction(issue.id, 'remind')}>
                            <MessageSquare className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-red-600" onClick={() => handleOverdueAction(issue.id, 'escalate')}>
                            <AlertTriangle className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SpecialBoardsPage;