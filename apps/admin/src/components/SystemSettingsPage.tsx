import React, { useState } from 'react';
import { Settings, Building2, Tag, Clock, Bell, Palette, Save, Plus, Trash2, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface Department {
  id: string;
  name: string;
  description: string;
  head: string;
  contact: string;
  isActive: boolean;
}

interface IssueCategory {
  id: string;
  name: string;
  description: string;
  defaultDepartment: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  slaHours: number;
}

interface SLATarget {
  category: string;
  responseTime: number;
  resolutionTime: number;
  escalationTime: number;
}

const mockDepartments: Department[] = [
  { id: 'roads', name: 'Road and Transportation', description: 'Handles road maintenance and traffic issues', head: 'Rajesh Kumar', contact: '+91-9876543210', isActive: true },
  { id: 'electrical', name: 'Electrical', description: 'Manages street lights and electrical infrastructure', head: 'Priya Singh', contact: '+91-9876543211', isActive: true },
  { id: 'sanitation', name: 'Sanitation', description: 'Handles sanitation and cleanliness issues', head: 'Amit Verma', contact: '+91-9876543212', isActive: true },
  { id: 'garbage', name: 'Garbage Management', description: 'Manages waste collection and disposal', head: 'Sunita Devi', contact: '+91-9876543213', isActive: true },
];

const mockCategories: IssueCategory[] = [
  { id: 'pothole', name: 'Potholes', description: 'Road surface damage requiring repair', defaultDepartment: 'roads', priority: 'high', slaHours: 48 },
  { id: 'streetlight', name: 'Street Lights', description: 'Non-functional or damaged street lighting', defaultDepartment: 'electrical', priority: 'medium', slaHours: 24 },
  { id: 'garbage', name: 'Garbage Collection', description: 'Missed garbage collection or overflow', defaultDepartment: 'garbage', priority: 'high', slaHours: 12 },
  { id: 'drainage', name: 'Drainage Issues', description: 'Blocked drains and water logging', defaultDepartment: 'sanitation', priority: 'critical', slaHours: 6 },
];

const mockSLATargets: SLATarget[] = [
  { category: 'Critical', responseTime: 2, resolutionTime: 6, escalationTime: 4 },
  { category: 'High', responseTime: 4, resolutionTime: 24, escalationTime: 12 },
  { category: 'Medium', responseTime: 8, resolutionTime: 72, escalationTime: 48 },
  { category: 'Low', responseTime: 24, resolutionTime: 168, escalationTime: 120 },
];

const SystemSettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'departments' | 'categories' | 'sla' | 'notifications' | 'branding'>('departments');
  const [departments, setDepartments] = useState<Department[]>(mockDepartments);
  const [categories, setCategories] = useState<IssueCategory[]>(mockCategories);
  const [slaTargets, setSlaTargets] = useState<SLATarget[]>(mockSLATargets);
  const [isEditing, setIsEditing] = useState<string | null>(null);

  const [systemSettings, setSystemSettings] = useState({
    notifications: {
      emailEnabled: true,
      smsEnabled: true,
      pushEnabled: true,
      escalationEmails: true,
    },
    branding: {
      systemName: 'CivicConnect',
      tagline: 'Admin Portal - Jharkhand',
      primaryColor: '#16a34a',
      logoUrl: '',
    }
  });

  const handleSaveChanges = () => {
    console.log('Saving system settings...');
    // API call would go here
  };

  const handleDepartmentEdit = (deptId: string) => {
    setIsEditing(deptId);
  };

  const handleDepartmentSave = (deptId: string) => {
    setIsEditing(null);
    console.log('Saving department:', deptId);
  };

  const handleAddDepartment = () => {
    const newDept: Department = {
      id: `dept-${Date.now()}`,
      name: 'New Department',
      description: '',
      head: '',
      contact: '',
      isActive: true
    };
    setDepartments([...departments, newDept]);
    setIsEditing(newDept.id);
  };

  const handleDeleteDepartment = (deptId: string) => {
    setDepartments(departments.filter(dept => dept.id !== deptId));
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'departments':
        return (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold">Department Management</h3>
              <Button onClick={handleAddDepartment} className="btn-civic-primary flex items-center space-x-2">
                <Plus className="h-4 w-4" />
                <span>Add Department</span>
              </Button>
            </div>

            <div className="space-y-4">
              {departments.map((dept) => (
                <div key={dept.id} className="civic-card p-4">
                  {isEditing === dept.id ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Department Name</Label>
                          <Input defaultValue={dept.name} />
                        </div>
                        <div>
                          <Label>Department Head</Label>
                          <Input defaultValue={dept.head} />
                        </div>
                      </div>
                      <div>
                        <Label>Description</Label>
                        <Textarea defaultValue={dept.description} rows={2} />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Contact</Label>
                          <Input defaultValue={dept.contact} />
                        </div>
                        <div className="flex items-center space-x-2">
                          <Switch checked={dept.isActive} />
                          <Label>Active</Label>
                        </div>
                      </div>
                      <div className="flex space-x-2">
                        <Button size="sm" onClick={() => handleDepartmentSave(dept.id)}>Save</Button>
                        <Button size="sm" variant="outline" onClick={() => setIsEditing(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h4 className="font-semibold text-lg">{dept.name}</h4>
                          <span className={`px-2 py-1 text-xs rounded-full ${dept.isActive ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                            {dept.isActive ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mb-2">{dept.description}</p>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div><strong>Head:</strong> {dept.head}</div>
                          <div><strong>Contact:</strong> {dept.contact}</div>
                        </div>
                      </div>
                      <div className="flex space-x-2">
                        <Button variant="ghost" size="sm" onClick={() => handleDepartmentEdit(dept.id)}>
                          <Edit3 className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteDepartment(dept.id)} className="text-red-600">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );

      case 'categories':
        return (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold">Issue Categories Configuration</h3>
              <Button className="btn-civic-primary flex items-center space-x-2">
                <Plus className="h-4 w-4" />
                <span>Add Category</span>
              </Button>
            </div>

            <div className="grid gap-4">
              {categories.map((category) => (
                <div key={category.id} className="civic-card p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h4 className="font-semibold">{category.name}</h4>
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          category.priority === 'critical' ? 'bg-red-100 text-red-800' :
                          category.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                          category.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-green-100 text-green-800'
                        }`}>
                          {category.priority}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{category.description}</p>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div><strong>Department:</strong> {category.defaultDepartment}</div>
                        <div><strong>SLA:</strong> {category.slaHours} hours</div>
                        <div><strong>Priority:</strong> {category.priority}</div>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <Button variant="ghost" size="sm">
                        <Edit3 className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" className="text-red-600">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'sla':
        return (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold">SLA Targets Configuration</h3>
            
            <div className="civic-card">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority Level</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Response Time (hrs)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resolution Time (hrs)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Escalation Time (hrs)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {slaTargets.map((sla, index) => (
                      <tr key={index}>
                        <td className="px-6 py-4 font-medium">{sla.category}</td>
                        <td className="px-6 py-4">
                          <Input type="number" defaultValue={sla.responseTime} className="w-20" />
                        </td>
                        <td className="px-6 py-4">
                          <Input type="number" defaultValue={sla.resolutionTime} className="w-20" />
                        </td>
                        <td className="px-6 py-4">
                          <Input type="number" defaultValue={sla.escalationTime} className="w-20" />
                        </td>
                        <td className="px-6 py-4">
                          <Button variant="ghost" size="sm">
                            <Edit3 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );

      case 'notifications':
        return (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold">Notification Templates & Settings</h3>
            
            <div className="grid grid-cols-2 gap-6">
              <div className="civic-card p-6">
                <h4 className="font-semibold mb-4">Notification Channels</h4>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Email Notifications</Label>
                      <p className="text-sm text-gray-600">Send email updates to citizens and staff</p>
                    </div>
                    <Switch 
                      checked={systemSettings.notifications.emailEnabled}
                      onCheckedChange={(checked) => setSystemSettings({
                        ...systemSettings,
                        notifications: { ...systemSettings.notifications, emailEnabled: checked }
                      })}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>SMS Notifications</Label>
                      <p className="text-sm text-gray-600">Send SMS alerts for urgent issues</p>
                    </div>
                    <Switch 
                      checked={systemSettings.notifications.smsEnabled}
                      onCheckedChange={(checked) => setSystemSettings({
                        ...systemSettings,
                        notifications: { ...systemSettings.notifications, smsEnabled: checked }
                      })}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Push Notifications</Label>
                      <p className="text-sm text-gray-600">Send app push notifications</p>
                    </div>
                    <Switch 
                      checked={systemSettings.notifications.pushEnabled}
                      onCheckedChange={(checked) => setSystemSettings({
                        ...systemSettings,
                        notifications: { ...systemSettings.notifications, pushEnabled: checked }
                      })}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Escalation Emails</Label>
                      <p className="text-sm text-gray-600">Auto-escalate overdue issues</p>
                    </div>
                    <Switch 
                      checked={systemSettings.notifications.escalationEmails}
                      onCheckedChange={(checked) => setSystemSettings({
                        ...systemSettings,
                        notifications: { ...systemSettings.notifications, escalationEmails: checked }
                      })}
                    />
                  </div>
                </div>
              </div>

              <div className="civic-card p-6">
                <h4 className="font-semibold mb-4">Email Templates</h4>
                <div className="space-y-3">
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select template to edit" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="issue-submitted">Issue Submitted</SelectItem>
                      <SelectItem value="issue-assigned">Issue Assigned</SelectItem>
                      <SelectItem value="issue-resolved">Issue Resolved</SelectItem>
                      <SelectItem value="escalation">Escalation Alert</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <div>
                    <Label>Subject Line</Label>
                    <Input placeholder="Email subject template" />
                  </div>
                  
                  <div>
                    <Label>Message Template</Label>
                    <Textarea 
                      placeholder="Dear {{citizen_name}}, your issue {{issue_id}} has been..."
                      rows={6}
                    />
                  </div>
                  
                  <Button size="sm" className="btn-civic-primary">Save Template</Button>
                </div>
              </div>
            </div>
          </div>
        );

      case 'branding':
        return (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold">System Branding & Appearance</h3>
            
            <div className="civic-card p-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <Label>System Name</Label>
                    <Input 
                      value={systemSettings.branding.systemName}
                      onChange={(e) => setSystemSettings({
                        ...systemSettings,
                        branding: { ...systemSettings.branding, systemName: e.target.value }
                      })}
                    />
                  </div>
                  
                  <div>
                    <Label>Tagline</Label>
                    <Input 
                      value={systemSettings.branding.tagline}
                      onChange={(e) => setSystemSettings({
                        ...systemSettings,
                        branding: { ...systemSettings.branding, tagline: e.target.value }
                      })}
                    />
                  </div>
                  
                  <div>
                    <Label>Primary Color</Label>
                    <div className="flex space-x-2">
                      <Input 
                        type="color" 
                        value={systemSettings.branding.primaryColor}
                        onChange={(e) => setSystemSettings({
                          ...systemSettings,
                          branding: { ...systemSettings.branding, primaryColor: e.target.value }
                        })}
                        className="w-16 h-10"
                      />
                      <Input 
                        value={systemSettings.branding.primaryColor}
                        onChange={(e) => setSystemSettings({
                          ...systemSettings,
                          branding: { ...systemSettings.branding, primaryColor: e.target.value }
                        })}
                        className="flex-1"
                      />
                    </div>
                  </div>
                  
                  <div>
                    <Label>Logo URL</Label>
                    <Input 
                      placeholder="https://example.com/logo.png"
                      value={systemSettings.branding.logoUrl}
                      onChange={(e) => setSystemSettings({
                        ...systemSettings,
                        branding: { ...systemSettings.branding, logoUrl: e.target.value }
                      })}
                    />
                  </div>
                </div>

                <div className="space-y-4">
                  <h4 className="font-semibold">Preview</h4>
                  <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                    <div style={{ color: systemSettings.branding.primaryColor }}>
                      <h2 className="text-2xl font-bold">{systemSettings.branding.systemName}</h2>
                      <p className="text-sm">{systemSettings.branding.tagline}</p>
                    </div>
                    
                    <div className="mt-4">
                      <div 
                        className="w-full h-8 rounded"
                        style={{ backgroundColor: systemSettings.branding.primaryColor }}
                      ></div>
                      <p className="text-xs text-gray-600 mt-1">Primary color usage example</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-civic-text-primary mb-2">System Settings</h2>
        <p className="text-civic-text-secondary">Configure system-wide settings and preferences</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-4 mb-6 overflow-x-auto">
        {[
          { id: 'departments', label: 'Departments', icon: Building2 },
          { id: 'categories', label: 'Issue Categories', icon: Tag },
          { id: 'sla', label: 'SLA Targets', icon: Clock },
          { id: 'notifications', label: 'Notifications', icon: Bell },
          { id: 'branding', label: 'Branding', icon: Palette },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? 'default' : 'outline'}
              onClick={() => setActiveTab(tab.id as any)}
              className="flex items-center space-x-2 whitespace-nowrap"
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </Button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="civic-card p-6">
        {renderTabContent()}
      </div>

      {/* Save Button */}
      <div className="fixed bottom-6 right-6">
        <Button onClick={handleSaveChanges} className="btn-civic-primary flex items-center space-x-2 shadow-lg">
          <Save className="h-4 w-4" />
          <span>Save All Changes</span>
        </Button>
      </div>
    </div>
  );
};

export default SystemSettingsPage;