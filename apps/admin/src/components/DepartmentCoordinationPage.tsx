import React, { useState } from 'react';
import { Building2, Clock, Users, Phone, Mail, AlertCircle, CheckCircle, ArrowLeftRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

interface Department {
  id: string;
  name: string;
  icon: any;
  workload: number;
  maxCapacity: number;
  avgResponseTime: string;
  pendingIssues: number;
  staffAvailable: number;
  totalStaff: number;
  contact: {
    phone: string;
    email: string;
    head: string;
  };
}

const departments: Department[] = [
  {
    id: 'roads',
    name: 'Road and Transportation',
    icon: Building2,
    workload: 75,
    maxCapacity: 100,
    avgResponseTime: '3.2 hours',
    pendingIssues: 23,
    staffAvailable: 12,
    totalStaff: 15,
    contact: { phone: '+91-9876543210', email: 'roads@jharkhand.gov.in', head: 'Rajesh Kumar' }
  },
  {
    id: 'electrical',
    name: 'Electrical',
    icon: Building2,
    workload: 60,
    maxCapacity: 80,
    avgResponseTime: '4.7 hours',
    pendingIssues: 18,
    staffAvailable: 8,
    totalStaff: 10,
    contact: { phone: '+91-9876543211', email: 'electrical@jharkhand.gov.in', head: 'Priya Singh' }
  },
  {
    id: 'sanitation',
    name: 'Sanitation',
    icon: Building2,
    workload: 45,
    maxCapacity: 70,
    avgResponseTime: '2.1 hours',
    pendingIssues: 12,
    staffAvailable: 15,
    totalStaff: 18,
    contact: { phone: '+91-9876543212', email: 'sanitation@jharkhand.gov.in', head: 'Amit Verma' }
  },
  {
    id: 'garbage',
    name: 'Garbage Management',
    icon: Building2,
    workload: 90,
    maxCapacity: 100,
    avgResponseTime: '5.3 hours',
    pendingIssues: 31,
    staffAvailable: 6,
    totalStaff: 12,
    contact: { phone: '+91-9876543213', email: 'garbage@jharkhand.gov.in', head: 'Sunita Devi' }
  }
];

interface TransferRequest {
  issueId: string;
  fromDepartment: string;
  toDepartment: string;
  reason: string;
  comments: string;
  status: 'pending' | 'accepted' | 'rejected';
  timestamp: string;
}

const mockTransfers: TransferRequest[] = [
  {
    issueId: 'CC001',
    fromDepartment: 'Roads',
    toDepartment: 'Electrical',
    reason: 'Street light maintenance required',
    comments: 'Issue involves both road work and electrical systems',
    status: 'pending',
    timestamp: '2 hours ago'
  },
  {
    issueId: 'CC002',
    fromDepartment: 'Electrical',
    toDepartment: 'Sanitation',
    reason: 'Drainage blockage affecting electrical systems',
    comments: 'Primary issue is drainage, electrical is secondary',
    status: 'accepted',
    timestamp: '4 hours ago'
  }
];

const DepartmentCoordinationPage: React.FC = () => {
  const [transferForm, setTransferForm] = useState({
    issueId: '',
    fromDepartment: '',
    toDepartment: '',
    reason: '',
    comments: ''
  });

  const getWorkloadColor = (workload: number, maxCapacity: number) => {
    const percentage = (workload / maxCapacity) * 100;
    if (percentage > 90) return 'text-red-600';
    if (percentage > 70) return 'text-orange-600';
    return 'text-green-600';
  };

  const getWorkloadBarColor = (workload: number, maxCapacity: number) => {
    const percentage = (workload / maxCapacity) * 100;
    if (percentage > 90) return 'bg-red-500';
    if (percentage > 70) return 'bg-orange-500';
    return 'bg-green-500';
  };

  const handleTransferSubmit = () => {
    console.log('Submitting transfer request:', transferForm);
    // Reset form
    setTransferForm({
      issueId: '',
      fromDepartment: '',
      toDepartment: '',
      reason: '',
      comments: ''
    });
  };

  const handleTransferAction = (transferId: string, action: 'accept' | 'reject') => {
    console.log(`${action} transfer request ${transferId}`);
  };

  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-civic-text-primary mb-2">Department Coordination</h2>
        <p className="text-civic-text-secondary">Manage inter-department collaboration and task reassignment</p>
      </div>

      {/* Department Overview Dashboard */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {departments.map((dept) => {
          const Icon = dept.icon;
          const workloadPercentage = (dept.workload / dept.maxCapacity) * 100;
          
          return (
            <div key={dept.id} className="civic-card p-6">
              <div className="flex items-center justify-between mb-4">
                <Icon className="h-8 w-8 text-civic-primary" />
                <span className={`text-sm font-medium ${getWorkloadColor(dept.workload, dept.maxCapacity)}`}>
                  {Math.round(workloadPercentage)}% Load
                </span>
              </div>
              
              <h3 className="font-semibold text-civic-text-primary mb-3">{dept.name}</h3>
              
              {/* Workload Meter */}
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span>Workload</span>
                  <span>{dept.workload}/{dept.maxCapacity}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full ${getWorkloadBarColor(dept.workload, dept.maxCapacity)}`}
                    style={{ width: `${workloadPercentage}%` }}
                  ></div>
                </div>
              </div>

              {/* Metrics */}
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center">
                    <Clock className="h-4 w-4 mr-1" />
                    Response Time
                  </span>
                  <span className="font-medium">{dept.avgResponseTime}</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="flex items-center">
                    <AlertCircle className="h-4 w-4 mr-1" />
                    Pending
                  </span>
                  <span className="font-medium">{dept.pendingIssues}</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="flex items-center">
                    <Users className="h-4 w-4 mr-1" />
                    Staff Available
                  </span>
                  <span className="font-medium">{dept.staffAvailable}/{dept.totalStaff}</span>
                </div>
              </div>

              {/* Contact Information */}
              <div className="mt-4 pt-4 border-t border-gray-200 space-y-1 text-xs">
                <div className="flex items-center">
                  <Phone className="h-3 w-3 mr-1" />
                  <span>{dept.contact.phone}</span>
                </div>
                <div className="flex items-center">
                  <Mail className="h-3 w-3 mr-1" />
                  <span>{dept.contact.email}</span>
                </div>
                <div className="font-medium">Head: {dept.contact.head}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Task Reassignment Interface */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* New Transfer Request */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4 flex items-center">
            <ArrowLeftRight className="h-5 w-5 mr-2" />
            Create Transfer Request
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Issue ID</label>
              <Select value={transferForm.issueId} onValueChange={(value) => setTransferForm({...transferForm, issueId: value})}>
                <SelectTrigger>
                  <SelectValue placeholder="Select Issue ID" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CC001">CC001 - MG Road Pothole</SelectItem>
                  <SelectItem value="CC002">CC002 - Station Road Light</SelectItem>
                  <SelectItem value="CC003">CC003 - Park Street Drainage</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">From Department</label>
                <Select value={transferForm.fromDepartment} onValueChange={(value) => setTransferForm({...transferForm, fromDepartment: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="From" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map(dept => (
                      <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">To Department</label>
                <Select value={transferForm.toDepartment} onValueChange={(value) => setTransferForm({...transferForm, toDepartment: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="To" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map(dept => (
                      <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Transfer Reason (Required)</label>
              <Select value={transferForm.reason} onValueChange={(value) => setTransferForm({...transferForm, reason: value})}>
                <SelectTrigger>
                  <SelectValue placeholder="Select Reason" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="jurisdiction">Wrong Jurisdiction</SelectItem>
                  <SelectItem value="expertise">Requires Different Expertise</SelectItem>
                  <SelectItem value="capacity">Department at Capacity</SelectItem>
                  <SelectItem value="collaboration">Multi-department Issue</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Comments</label>
              <Textarea
                placeholder="Additional details about the transfer..."
                value={transferForm.comments}
                onChange={(e) => setTransferForm({...transferForm, comments: e.target.value})}
                rows={3}
              />
            </div>

            <Button 
              onClick={handleTransferSubmit}
              disabled={!transferForm.issueId || !transferForm.fromDepartment || !transferForm.toDepartment || !transferForm.reason}
              className="w-full btn-civic-primary"
            >
              Submit Transfer Request
            </Button>
          </div>
        </div>

        {/* Pending Transfers */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Pending Transfer Requests</h3>
          
          <div className="space-y-4">
            {mockTransfers.map((transfer, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="font-medium">{transfer.issueId}</h4>
                    <p className="text-sm text-gray-600">
                      {transfer.fromDepartment} → {transfer.toDepartment}
                    </p>
                  </div>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    transfer.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                    transfer.status === 'accepted' ? 'bg-green-100 text-green-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {transfer.status.charAt(0).toUpperCase() + transfer.status.slice(1)}
                  </span>
                </div>
                
                <p className="text-sm mb-2"><strong>Reason:</strong> {transfer.reason}</p>
                <p className="text-sm text-gray-600 mb-3">{transfer.comments}</p>
                
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-500">{transfer.timestamp}</span>
                  {transfer.status === 'pending' && (
                    <div className="space-x-2">
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => handleTransferAction(transfer.issueId, 'reject')}
                        className="text-red-600 hover:text-red-700"
                      >
                        Reject
                      </Button>
                      <Button 
                        size="sm" 
                        onClick={() => handleTransferAction(transfer.issueId, 'accept')}
                        className="btn-civic-success"
                      >
                        <CheckCircle className="h-4 w-4 mr-1" />
                        Accept
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit Trail */}
      <div className="civic-card p-6">
        <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Transfer Audit Trail</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left">Issue ID</th>
                <th className="px-4 py-2 text-left">From</th>
                <th className="px-4 py-2 text-left">To</th>
                <th className="px-4 py-2 text-left">Reason</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-left">Approved By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              <tr>
                <td className="px-4 py-2 font-medium">CC001</td>
                <td className="px-4 py-2">Roads</td>
                <td className="px-4 py-2">Electrical</td>
                <td className="px-4 py-2">Street light maintenance</td>
                <td className="px-4 py-2">
                  <span className="status-progress">Approved</span>
                </td>
                <td className="px-4 py-2">2024-01-15</td>
                <td className="px-4 py-2">Admin Kumar</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">CC002</td>
                <td className="px-4 py-2">Electrical</td>
                <td className="px-4 py-2">Sanitation</td>
                <td className="px-4 py-2">Drainage issue</td>
                <td className="px-4 py-2">
                  <span className="status-resolved">Completed</span>
                </td>
                <td className="px-4 py-2">2024-01-14</td>
                <td className="px-4 py-2">Admin Singh</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DepartmentCoordinationPage;