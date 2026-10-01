import React, { useState } from 'react';
import { Users, UserPlus, Shield, Search, Eye, Ban, Unlock, MoreHorizontal, Key } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

interface Citizen {
  id: string;
  name: string;
  phone: string;
  email: string;
  status: 'active' | 'suspended' | 'blocked';
  registrationDate: string;
  lastLogin: string;
  reportsSubmitted: number;
  ward: string;
}

interface AdminUser {
  id: string;
  name: string;
  email: string;
  department: string;
  role: 'admin' | 'overseer';
  status: 'active' | 'inactive';
  lastLogin: string;
  permissions: string[];
  phone: string;
}

const mockCitizens: Citizen[] = [
  { id: 'C001', name: 'Rahul Kumar', phone: '+91-9876543210', email: 'rahul@example.com', status: 'active', registrationDate: '2024-01-10', lastLogin: '2 hours ago', reportsSubmitted: 15, ward: 'Ward 1' },
  { id: 'C002', name: 'Priya Singh', phone: '+91-9876543211', email: 'priya@example.com', status: 'active', registrationDate: '2024-01-08', lastLogin: '1 day ago', reportsSubmitted: 8, ward: 'Ward 3' },
  { id: 'C003', name: 'Amit Verma', phone: '+91-9876543212', email: 'amit@example.com', status: 'suspended', registrationDate: '2024-01-05', lastLogin: '3 days ago', reportsSubmitted: 25, ward: 'Ward 2' },
  { id: 'C004', name: 'Sunita Devi', phone: '+91-9876543213', email: 'sunita@example.com', status: 'blocked', registrationDate: '2024-01-03', lastLogin: '1 week ago', reportsSubmitted: 3, ward: 'Ward 4' },
];

const mockAdmins: AdminUser[] = [
  { 
    id: 'A001', 
    name: 'Kumar Singh', 
    email: 'kumar@jharkhand.gov.in', 
    department: 'Road and Transportation', 
    role: 'admin', 
    status: 'active', 
    lastLogin: '1 hour ago', 
    permissions: ['view_issues', 'edit_issues', 'assign_issues'],
    phone: '+91-9876543220'
  },
  { 
    id: 'A002', 
    name: 'Ravi Sharma', 
    email: 'ravi@jharkhand.gov.in', 
    department: 'Electrical', 
    role: 'overseer', 
    status: 'active', 
    lastLogin: '30 minutes ago', 
    permissions: ['view_issues', 'edit_issues', 'assign_issues', 'manage_departments', 'override_decisions'],
    phone: '+91-9876543221'
  },
];

const availablePermissions = [
  'view_issues',
  'edit_issues', 
  'assign_issues',
  'manage_departments',
  'override_decisions',
  'manage_users',
  'system_settings',
  'analytics_access'
];

const UserManagementPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'citizens' | 'admins'>('citizens');
  const [citizenSearch, setCitizenSearch] = useState('');
  const [adminSearch, setAdminSearch] = useState('');
  const [isCreateAdminOpen, setIsCreateAdminOpen] = useState(false);
  const [newAdmin, setNewAdmin] = useState({
    name: '',
    email: '',
    phone: '',
    department: '',
    role: 'admin' as 'admin' | 'overseer',
    permissions: [] as string[]
  });

  const handleCitizenAction = (citizenId: string, action: 'view' | 'suspend' | 'block' | 'activate') => {
    console.log(`Performing ${action} on citizen ${citizenId}`);
  };

  const handleAdminAction = (adminId: string, action: 'view' | 'deactivate' | 'reset_password') => {
    console.log(`Performing ${action} on admin ${adminId}`);
  };

  const handleCreateAdmin = () => {
    console.log('Creating new admin:', newAdmin);
    setIsCreateAdminOpen(false);
    setNewAdmin({
      name: '',
      email: '',
      phone: '',
      department: '',
      role: 'admin',
      permissions: []
    });
  };

  const handlePermissionChange = (permission: string, checked: boolean) => {
    if (checked) {
      setNewAdmin({...newAdmin, permissions: [...newAdmin.permissions, permission]});
    } else {
      setNewAdmin({...newAdmin, permissions: newAdmin.permissions.filter(p => p !== permission)});
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'active': return 'status-resolved';
      case 'suspended': return 'status-progress';
      case 'blocked': return 'status-urgent';
      case 'inactive': return 'bg-gray-100 text-gray-800 px-2 py-1 rounded-full text-xs font-medium';
      default: return 'status-submitted';
    }
  };

  const filteredCitizens = mockCitizens.filter(citizen => 
    citizen.name.toLowerCase().includes(citizenSearch.toLowerCase()) ||
    citizen.email.toLowerCase().includes(citizenSearch.toLowerCase()) ||
    citizen.phone.includes(citizenSearch)
  );

  const filteredAdmins = mockAdmins.filter(admin => 
    admin.name.toLowerCase().includes(adminSearch.toLowerCase()) ||
    admin.email.toLowerCase().includes(adminSearch.toLowerCase()) ||
    admin.department.toLowerCase().includes(adminSearch.toLowerCase())
  );

  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-civic-text-primary mb-2">User Management</h2>
        <p className="text-civic-text-secondary">Manage citizen accounts and administrative users</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-4 mb-6">
        <Button
          variant={activeTab === 'citizens' ? 'default' : 'outline'}
          onClick={() => setActiveTab('citizens')}
          className="flex items-center space-x-2"
        >
          <Users className="h-4 w-4" />
          <span>Citizen Management</span>
        </Button>
        <Button
          variant={activeTab === 'admins' ? 'default' : 'outline'}
          onClick={() => setActiveTab('admins')}
          className="flex items-center space-x-2"
        >
          <Shield className="h-4 w-4" />
          <span>Admin/Overseer Management</span>
        </Button>
      </div>

      {activeTab === 'citizens' && (
        <div className="space-y-6">
          {/* Search and Filters */}
          <div className="civic-card p-4">
            <div className="flex justify-between items-center">
              <div className="flex space-x-4 flex-1">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="Search citizens..."
                    value={citizenSearch}
                    onChange={(e) => setCitizenSearch(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Select defaultValue="all">
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="suspended">Suspended</SelectItem>
                    <SelectItem value="blocked">Blocked</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="text-sm text-gray-600">
                {filteredCitizens.length} citizens found
              </div>
            </div>
          </div>

          {/* Citizens Table */}
          <div className="civic-card">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Registration</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Login</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reports</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredCitizens.map((citizen) => (
                    <tr key={citizen.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium">{citizen.id}</td>
                      <td className="px-6 py-4 text-sm">
                        <div>
                          <div className="font-medium">{citizen.name}</div>
                          <div className="text-gray-500">{citizen.ward}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <div>
                          <div>{citizen.phone}</div>
                          <div className="text-gray-500">{citizen.email}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={getStatusClass(citizen.status)}>
                          {citizen.status.charAt(0).toUpperCase() + citizen.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">{citizen.registrationDate}</td>
                      <td className="px-6 py-4 text-sm">{citizen.lastLogin}</td>
                      <td className="px-6 py-4 text-sm font-medium">{citizen.reportsSubmitted}</td>
                      <td className="px-6 py-4">
                        <div className="flex space-x-2">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleCitizenAction(citizen.id, 'view')}
                            className="text-blue-600"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {citizen.status === 'active' && (
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={() => handleCitizenAction(citizen.id, 'suspend')}
                              className="text-orange-600"
                            >
                              <Ban className="h-4 w-4" />
                            </Button>
                          )}
                          {citizen.status !== 'active' && (
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={() => handleCitizenAction(citizen.id, 'activate')}
                              className="text-green-600"
                            >
                              <Unlock className="h-4 w-4" />
                            </Button>
                          )}
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

      {activeTab === 'admins' && (
        <div className="space-y-6">
          {/* Search and Actions */}
          <div className="civic-card p-4">
            <div className="flex justify-between items-center">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search administrators..."
                  value={adminSearch}
                  onChange={(e) => setAdminSearch(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Dialog open={isCreateAdminOpen} onOpenChange={setIsCreateAdminOpen}>
                <DialogTrigger asChild>
                  <Button className="btn-civic-primary flex items-center space-x-2">
                    <UserPlus className="h-4 w-4" />
                    <span>Create New Admin</span>
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>Create New Administrator</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="name">Full Name</Label>
                        <Input
                          id="name"
                          value={newAdmin.name}
                          onChange={(e) => setNewAdmin({...newAdmin, name: e.target.value})}
                          placeholder="Enter full name"
                        />
                      </div>
                      <div>
                        <Label htmlFor="email">Email</Label>
                        <Input
                          id="email"
                          type="email"
                          value={newAdmin.email}
                          onChange={(e) => setNewAdmin({...newAdmin, email: e.target.value})}
                          placeholder="admin@jharkhand.gov.in"
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="phone">Phone</Label>
                        <Input
                          id="phone"
                          value={newAdmin.phone}
                          onChange={(e) => setNewAdmin({...newAdmin, phone: e.target.value})}
                          placeholder="+91-9876543210"
                        />
                      </div>
                      <div>
                        <Label htmlFor="department">Department</Label>
                        <Select value={newAdmin.department} onValueChange={(value) => setNewAdmin({...newAdmin, department: value})}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select Department" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="roads">Road and Transportation</SelectItem>
                            <SelectItem value="electrical">Electrical</SelectItem>
                            <SelectItem value="sanitation">Sanitation</SelectItem>
                            <SelectItem value="garbage">Garbage Management</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="role">Role</Label>
                      <Select value={newAdmin.role} onValueChange={(value: 'admin' | 'overseer') => setNewAdmin({...newAdmin, role: value})}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="overseer">Overseer</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label>Permissions</Label>
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {availablePermissions.map((permission) => (
                          <div key={permission} className="flex items-center space-x-2">
                            <Checkbox
                              id={permission}
                              checked={newAdmin.permissions.includes(permission)}
                              onCheckedChange={(checked) => handlePermissionChange(permission, checked as boolean)}
                            />
                            <Label htmlFor={permission} className="text-sm">
                              {permission.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </Label>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex justify-end space-x-2 pt-4">
                      <Button variant="outline" onClick={() => setIsCreateAdminOpen(false)}>
                        Cancel
                      </Button>
                      <Button onClick={handleCreateAdmin} disabled={!newAdmin.name || !newAdmin.email || !newAdmin.department}>
                        Create Admin
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Admins Table */}
          <div className="civic-card">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Admin ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Department</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Login</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredAdmins.map((admin) => (
                    <tr key={admin.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium">{admin.id}</td>
                      <td className="px-6 py-4 text-sm font-medium">{admin.name}</td>
                      <td className="px-6 py-4 text-sm">
                        <div>
                          <div>{admin.email}</div>
                          <div className="text-gray-500">{admin.phone}</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">{admin.department}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          admin.role === 'overseer' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                        }`}>
                          {admin.role.charAt(0).toUpperCase() + admin.role.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={getStatusClass(admin.status)}>
                          {admin.status.charAt(0).toUpperCase() + admin.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">{admin.lastLogin}</td>
                      <td className="px-6 py-4">
                        <div className="flex space-x-2">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleAdminAction(admin.id, 'view')}
                            className="text-blue-600"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => handleAdminAction(admin.id, 'reset_password')}
                            className="text-orange-600"
                          >
                            <Key className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="text-gray-600"
                          >
                            <MoreHorizontal className="h-4 w-4" />
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

export default UserManagementPage;