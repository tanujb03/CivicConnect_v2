import React, { useState } from 'react';
import { X, MapPin, Camera, MessageSquare, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface Issue {
  id: string;
  location: string;
  category: string;
  status: string;
  assignedTo: string;
  priority: string;
  ward: string;
  timeAgo: string;
  description: string;
}

interface IssueDetailsModalProps {
  issue: Issue;
  onClose: () => void;
}

const statusTimeline = [
  { status: 'Submitted', timestamp: '2024-01-15 10:30 AM', user: 'Citizen John Doe' },
  { status: 'Assigned', timestamp: '2024-01-15 11:45 AM', user: 'Admin Kumar' },
  { status: 'In Progress', timestamp: '2024-01-15 02:15 PM', user: 'Road Dept' },
];

const IssueDetailsModal: React.FC<IssueDetailsModalProps> = ({ issue, onClose }) => {
  const [newNote, setNewNote] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState(issue.assignedTo);
  const [selectedStatus, setSelectedStatus] = useState(issue.status);

  const handleSave = () => {
    console.log('Saving changes...', {
      department: selectedDepartment,
      status: selectedStatus,
      note: newNote
    });
    onClose();
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex justify-between items-center">
            <DialogTitle className="text-xl font-bold">Issue Details - {issue.id}</DialogTitle>
            <div className="flex items-center space-x-2">
              <span className={`px-3 py-1 rounded-full text-sm font-medium status-${issue.status}`}>
                {issue.status.charAt(0).toUpperCase() + issue.status.slice(1)}
              </span>
              <Button variant="ghost" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Images Section */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3 flex items-center">
                <Camera className="h-4 w-4 mr-2" />
                Issue Images
              </h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-gray-200 h-24 rounded-lg flex items-center justify-center">
                  <Camera className="h-6 w-6 text-gray-400" />
                </div>
                <div className="bg-gray-200 h-24 rounded-lg flex items-center justify-center">
                  <Camera className="h-6 w-6 text-gray-400" />
                </div>
              </div>
            </div>

            {/* Location Map */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3 flex items-center">
                <MapPin className="h-4 w-4 mr-2" />
                Location
              </h3>
              <div className="bg-gray-100 h-32 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <MapPin className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-sm text-gray-600">{issue.location}</p>
                </div>
              </div>
            </div>

            {/* Details */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3">Issue Details</h3>
              <div className="space-y-2 text-sm">
                <div><strong>Category:</strong> {issue.category}</div>
                <div><strong>Priority:</strong> {issue.priority}</div>
                <div><strong>Ward:</strong> {issue.ward}</div>
                <div><strong>Submitted:</strong> {issue.timeAgo}</div>
                <div className="mt-3">
                  <strong>Description:</strong>
                  <p className="mt-1 text-gray-600">{issue.description}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Status Timeline */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3">Status Timeline</h3>
              <div className="space-y-3">
                {statusTimeline.map((timeline, index) => (
                  <div key={index} className="flex items-start space-x-3">
                    <div className="w-2 h-2 bg-green-500 rounded-full mt-2"></div>
                    <div className="flex-1">
                      <p className="font-medium text-sm">{timeline.status}</p>
                      <p className="text-xs text-gray-500">{timeline.timestamp}</p>
                      <p className="text-xs text-gray-600">by {timeline.user}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Department Assignment */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3">Department Assignment</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium">Current Department</label>
                  <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Road Dept">Road and Transportation</SelectItem>
                      <SelectItem value="Electrical">Electrical</SelectItem>
                      <SelectItem value="Sanitation">Sanitation</SelectItem>
                      <SelectItem value="Garbage">Garbage Management</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium">Status</label>
                  <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="submitted">Submitted</SelectItem>
                      <SelectItem value="progress">In Progress</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                      <SelectItem value="urgent">Urgent</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Internal Notes */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3 flex items-center">
                <MessageSquare className="h-4 w-4 mr-2" />
                Internal Notes
              </h3>
              <div className="space-y-3">
                <div className="bg-gray-50 p-3 rounded-lg text-sm">
                  <p className="font-medium">Admin Kumar</p>
                  <p className="text-gray-600">Assigned to road department for immediate attention.</p>
                  <p className="text-xs text-gray-500 mt-1">2 hours ago</p>
                </div>
                <Textarea
                  placeholder="Add internal note..."
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  rows={3}
                />
              </div>
            </div>

            {/* Resolution Images */}
            <div className="civic-card p-4">
              <h3 className="font-semibold mb-3">Resolution Images</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-gray-100 h-20 rounded-lg flex items-center justify-center border-dashed border-2 border-gray-300">
                  <Camera className="h-5 w-5 text-gray-400" />
                </div>
                <div className="bg-gray-100 h-20 rounded-lg flex items-center justify-center border-dashed border-2 border-gray-300">
                  <Camera className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between pt-4 border-t">
          <Button variant="destructive" className="flex items-center space-x-2">
            <Trash2 className="h-4 w-4" />
            <span>Delete Issue</span>
          </Button>
          <div className="space-x-2">
            <Button variant="outline" onClick={onClose}>Close</Button>
            <Button onClick={handleSave} className="btn-civic-primary flex items-center space-x-2">
              <Save className="h-4 w-4" />
              <span>Save Changes</span>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default IssueDetailsModal;