import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  User, 
  MapPin, 
  Shield, 
  Bell, 
  Settings, 
  HelpCircle, 
  LogOut,
  Camera,
  Mail,
  Phone,
  Building,
  Calendar,
  Download,
  Moon,
  Globe,
  Database,
  BarChart3,
  FileText,
  MessageSquare
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useNavigate } from 'react-router-dom';

const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState({
    name: 'Rajesh Kumar Singh',
    designation: 'Senior Overlooker',
    jurisdiction: 'Ranchi Municipal Corporation',
    department: 'All Departments',
    email: 'rajesh.singh@ranchi.gov.in',
    phone: '+91 9876543210',
    office: 'Municipal Office, Block A, Room 204',
    joinDate: '2019-03-15'
  });

  const [notifications, setNotifications] = useState({
    realTimeAlerts: true,
    dailySummary: true,
    weeklyReports: false,
    smsAlerts: true,
    pushNotifications: true
  });

  const [preferences, setPreferences] = useState({
    theme: 'light',
    language: 'en',
    mapView: 'satellite',
    dashboardLayout: 'compact'
  });

  const { toast } = useToast();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('civic_auth_token');
    localStorage.removeItem('civic_user_role');
    localStorage.removeItem('civic_user_name');
    localStorage.removeItem('civic_user_jurisdiction');
    
    toast({
      title: "Logged Out",
      description: "You have been successfully logged out.",
    });
    
    navigate('/login');
  };

  const handleSaveProfile = () => {
    toast({
      title: "Profile Updated",
      description: "Your profile information has been saved successfully.",
    });
  };

  const handleExportData = (type: string) => {
    toast({
      title: "Export Started",
      description: `Your ${type} export will be ready shortly. You'll receive an email notification.`,
    });
  };

  const activityStats = {
    issuesReviewed: 1247,
    escalationsRaised: 89,
    flaggedIssues: 45,
    analyticsViewed: 234
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] text-white">
        <div className="flex items-center space-x-4">
          <div className="relative">
            <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center">
              <User className="w-8 h-8 text-white" />
            </div>
            <Button 
              size="sm" 
              className="absolute -bottom-1 -right-1 w-8 h-8 p-0 bg-white text-primary hover:bg-white/90"
            >
              <Camera className="w-4 h-4" />
            </Button>
          </div>
          <div>
            <h1 className="text-2xl font-bold">{profile.name}</h1>
            <p className="text-white/80">{profile.designation}</p>
            <div className="flex items-center space-x-2 mt-1">
              <MapPin className="w-4 h-4" />
              <span className="text-sm">{profile.jurisdiction}</span>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{activityStats.issuesReviewed}</div>
            <div className="text-xs text-white/80">Issues Reviewed</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{activityStats.escalationsRaised}</div>
            <div className="text-xs text-white/80">Escalations</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{activityStats.flaggedIssues}</div>
            <div className="text-xs text-white/80">Flagged Issues</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{activityStats.analyticsViewed}</div>
            <div className="text-xs text-white/80">Reports Generated</div>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* Profile Information */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <User className="w-5 h-5 text-primary" />
              <span>Profile Information</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  value={profile.name}
                  onChange={(e) => setProfile({...profile, name: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="designation">Designation</Label>
                <Input
                  id="designation"
                  value={profile.designation}
                  onChange={(e) => setProfile({...profile, designation: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    value={profile.email}
                    onChange={(e) => setProfile({...profile, email: e.target.value})}
                    className="pl-10"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="phone"
                    value={profile.phone}
                    onChange={(e) => setProfile({...profile, phone: e.target.value})}
                    className="pl-10"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="office">Office Address</Label>
                <div className="relative">
                  <Building className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="office"
                    value={profile.office}
                    onChange={(e) => setProfile({...profile, office: e.target.value})}
                    className="pl-10"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Join Date</Label>
                <div className="flex items-center space-x-2 text-muted-foreground">
                  <Calendar className="w-4 h-4" />
                  <span>{new Date(profile.joinDate).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleSaveProfile} className="civic-button-primary">
                Save Changes
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Jurisdiction & Authority */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Shield className="w-5 h-5 text-primary" />
              <span>Jurisdiction & Authority</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Jurisdiction Area</Label>
                <div className="mt-1">
                  <Badge variant="secondary" className="mr-2">Ranchi Municipal Corporation</Badge>
                  <Badge variant="outline">Ward 1-15</Badge>
                </div>
              </div>
              <div>
                <Label>Department Oversight</Label>
                <div className="mt-1">
                  <Badge className="mr-1 mb-1">Roads and Transportation</Badge>
                </div>
              </div>
              <div>
                <Label>Access Level</Label>
                <div className="mt-1">
                  <Badge variant="destructive">Senior Overlooker</Badge>
                </div>
              </div>
              <div>
                <Label>Authority Scope</Label>
                <div className="mt-1">
                  <Badge variant="secondary">Major Upvote</Badge>
                  <Badge variant="secondary" className="ml-1">Flag Authority</Badge>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Notification Settings */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Bell className="w-5 h-5 text-primary" />
              <span>Notification Settings</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Real-time Alerts</Label>
                  <p className="text-sm text-muted-foreground">Get notified instantly for critical issues</p>
                </div>
                <Switch
                  checked={notifications.realTimeAlerts}
                  onCheckedChange={(checked) => 
                    setNotifications({...notifications, realTimeAlerts: checked})
                  }
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <Label>Daily Summary Emails</Label>
                  <p className="text-sm text-muted-foreground">Receive daily activity summaries</p>
                </div>
                <Switch
                  checked={notifications.dailySummary}
                  onCheckedChange={(checked) => 
                    setNotifications({...notifications, dailySummary: checked})
                  }
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <Label>Weekly Reports</Label>
                  <p className="text-sm text-muted-foreground">Comprehensive weekly analytics reports</p>
                </div>
                <Switch
                  checked={notifications.weeklyReports}
                  onCheckedChange={(checked) => 
                    setNotifications({...notifications, weeklyReports: checked})
                  }
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <Label>SMS Alerts</Label>
                  <p className="text-sm text-muted-foreground">Critical alerts via SMS</p>
                </div>
                <Switch
                  checked={notifications.smsAlerts}
                  onCheckedChange={(checked) => 
                    setNotifications({...notifications, smsAlerts: checked})
                  }
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Display Preferences */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Settings className="w-5 h-5 text-primary" />
              <span>Display Preferences</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Theme</Label>
                <Select value={preferences.theme} onValueChange={(value) => 
                  setPreferences({...preferences, theme: value})
                }>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">Light Mode</SelectItem>
                    <SelectItem value="dark">Dark Mode</SelectItem>
                    <SelectItem value="auto">Auto (System)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Language</Label>
                <Select value={preferences.language} onValueChange={(value) => 
                  setPreferences({...preferences, language: value})
                }>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="hi">हिंदी</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Map View</Label>
                <Select value={preferences.mapView} onValueChange={(value) => 
                  setPreferences({...preferences, mapView: value})
                }>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="street">Street View</SelectItem>
                    <SelectItem value="satellite">Satellite</SelectItem>
                    <SelectItem value="terrain">Terrain</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Dashboard Layout</Label>
                <Select value={preferences.dashboardLayout} onValueChange={(value) => 
                  setPreferences({...preferences, dashboardLayout: value})
                }>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="compact">Compact</SelectItem>
                    <SelectItem value="detailed">Detailed</SelectItem>
                    <SelectItem value="minimal">Minimal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Export Data */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Download className="w-5 h-5 text-primary" />
              <span>Data Export & Reports</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Button 
                variant="outline" 
                className="justify-start h-auto p-4"
                onClick={() => handleExportData('Activity Report')}
              >
                <BarChart3 className="w-5 h-5 mr-3 text-primary" />
                <div className="text-left">
                  <div className="font-medium">Activity Report</div>
                  <div className="text-sm text-muted-foreground">Your oversight activities (PDF)</div>
                </div>
              </Button>
              
              <Button 
                variant="outline" 
                className="justify-start h-auto p-4"
                onClick={() => handleExportData('Analytics Data')}
              >
                <Database className="w-5 h-5 mr-3 text-primary" />
                <div className="text-left">
                  <div className="font-medium">Analytics Data</div>
                  <div className="text-sm text-muted-foreground">Performance metrics (Excel)</div>
                </div>
              </Button>
              
              <Button 
                variant="outline" 
                className="justify-start h-auto p-4"
                onClick={() => handleExportData('Issue Summary')}
              >
                <FileText className="w-5 h-5 mr-3 text-primary" />
                <div className="text-left">
                  <div className="font-medium">Issue Summary</div>
                  <div className="text-sm text-muted-foreground">Issues you've reviewed (PDF)</div>
                </div>
              </Button>
              
              <Button 
                variant="outline" 
                className="justify-start h-auto p-4"
                onClick={() => handleExportData('Communication Log')}
              >
                <MessageSquare className="w-5 h-5 mr-3 text-primary" />
                <div className="text-left">
                  <div className="font-medium">Communication Log</div>
                  <div className="text-sm text-muted-foreground">All escalations & flags (CSV)</div>
                </div>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Help & Support */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <HelpCircle className="w-5 h-5 text-primary" />
              <span>Help & Support</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Button variant="ghost" className="justify-start w-full">
                <FileText className="w-4 h-4 mr-3" />
                User Guidelines & Best Practices
              </Button>
              <Button variant="ghost" className="justify-start w-full">
                <MessageSquare className="w-4 h-4 mr-3" />
                Contact Technical Support
              </Button>
              <Button variant="ghost" className="justify-start w-full">
                <Globe className="w-4 h-4 mr-3" />
                Documentation & Tutorials
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* System Information */}
        <Card className="civic-card">
          <CardContent className="p-4">
            <div className="text-center text-sm text-muted-foreground space-y-1">
              <p>CivicConnect Overlooker Portal v2.0.1</p>
              <p>Last login: {new Date().toLocaleString()}</p>
              <p>Session expires in 4 hours 23 minutes</p>
            </div>
          </CardContent>
        </Card>

        {/* Logout */}
        <Card className="civic-card border-red-200">
          <CardContent className="p-4">
            <Button 
              variant="destructive" 
              className="w-full"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ProfilePage;