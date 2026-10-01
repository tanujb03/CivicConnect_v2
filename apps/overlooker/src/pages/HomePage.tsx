import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  MapPin, 
  AlertTriangle, 
  Clock, 
  MessageSquare, 
  BarChart3,
  Filter,
  Calendar,
  TrendingUp,
  Users,
  Zap,
  Bell
} from 'lucide-react';
import StatusBadge from '@/components/common/StatusBadge';
import { cn } from '@/lib/utils';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

// Fix for default icon issues with Webpack/Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Mock data for demonstration
const mockIssues = [
  { id: '1', lat: 23.3441, lng: 85.3096, status: 'urgent', category: 'roads', title: 'Major pothole on Main Street' },
  { id: '2', lat: 23.3551, lng: 85.3296, status: 'overdue', category: 'electrical', title: 'Street light not working' },
  { id: '3', lat: 23.3341, lng: 85.3196, status: 'resolved', category: 'sanitation', title: 'Drainage cleaning completed' },
  { id: '4', lat: 23.3641, lng: 85.3396, status: 'disputed', category: 'garbage', title: 'Garbage collection irregular' },
  { id: '5', lat: 23.3241, lng: 85.2996, status: 'ignored', category: 'roads', title: 'Traffic signal malfunction' },
];

const mockUpdates = 
  [
  {
    id: '1',
    type: 'citywide',
    icon: '📢',
    title: 'Trash pickup delayed today due to holiday',
    time: '2 hours ago',
    priority: 'medium'
  },
  {
    id: '2', 
    type: 'local',
    icon: '💧',
    title: '50 citizens reported water logging in your area',
    time: '3 hours ago',
    priority: 'high'
  },
  {
    id: '3',
    type: 'alert',
    icon: '⚠️',
    title: 'Traffic light outage at Central Crossing',
    time: '4 hours ago',
    priority: 'urgent'
  },
  {
    id: '4',
    type: 'update',
    icon: '🔧',
    title: 'Water main repair completed in Ward 12',
    time: '6 hours ago',
    priority: 'low'
  },
  {
    id: '5',
    type: 'weekly',
    icon: '📊',
    title: '89% issue resolution rate this week (+5%)',
    time: '1 day ago',
    priority: 'low'
  },
  {
    id: '6',
    type: 'citywide',
    icon: '🌳',
    title: 'Tree plantation drive scheduled this weekend',
    time: '1 day ago',
    priority: 'medium'
  },
  {
    id: '7',
    type: 'alert',
    icon: '🔥',
    title: 'Small fire reported near Market Street, under control',
    time: '18 hours ago',
    priority: 'high'
  },
  {
    id: '8',
    type: 'local',
    icon: '🚧',
    title: 'Road maintenance on Park Avenue, expect delays',
    time: '12 hours ago',
    priority: 'medium'
  },
  {
    id: '9',
    type: 'update',
    icon: '🏥',
    title: 'New health center inaugurated in Ward 7',
    time: '2 days ago',
    priority: 'low'
  },
  {
    id: '10',
    type: 'weekly',
    icon: '📈',
    title: 'Citizen satisfaction index rises by 12%',
    time: '3 days ago',
    priority: 'low'
  },
  {
    id: '11',
    type: 'citywide',
    icon: '🚌',
    title: 'Additional buses deployed during morning rush hours',
    time: '5 hours ago',
    priority: 'medium'
  },
  {
    id: '12',
    type: 'alert',
    icon: '🌩️',
    title: 'Severe thunderstorm warning issued for the evening',
    time: '30 minutes ago',
    priority: 'urgent'
  },
  {
    id: '13',
    type: 'local',
    icon: '🛒',
    title: 'Weekly farmers market opens at Riverside Ground',
    time: '7 hours ago',
    priority: 'low'
  },
];


const HomePage: React.FC = () => {
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [showSpecialReports, setShowSpecialReports] = useState(false);
  const [activeReportTab, setActiveReportTab] = useState('ignored');

  useEffect(() => {
    const interval = setInterval(() => {
      console.log('Checking for updates...');
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const getIssueColor = (status: string) => {
    switch (status) {
      case 'urgent': return 'bg-red-500';
      case 'overdue': return 'bg-orange-500';
      case 'disputed': return 'bg-blue-500';
      case 'resolved': return 'bg-green-500';
      case 'ignored': return 'bg-gray-500';
      default: return 'bg-primary';
    }
  };

  const getUpdateTypeColor = (type: string) => {
    switch (type) {
      case 'alert': return 'border-l-red-500 bg-red-50';
      case 'citywide': return 'border-l-blue-500 bg-blue-50';
      case 'local': return 'border-l-orange-500 bg-orange-50';
      case 'update': return 'border-l-green-500 bg-green-50';
      case 'weekly': return 'border-l-purple-500 bg-purple-50';
      default: return 'border-l-gray-500 bg-gray-50';
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] p-6 text-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Good Morning, Overlooker</h1>
            <p className="text-white/80">Ranchi Municipal Corporation</p>
          </div>
          <div className="flex items-center space-x-2">
            <Badge className="bg-white/20 text-white border-white/30">
              Ward 1-15
            </Badge>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white/10 rounded-lg p-3 text-center transition-transform duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
            <div className="text-2xl font-bold">127</div>
            <div className="text-sm text-white/80">Active Issues</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center transition-transform duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
            <div className="text-2xl font-bold">23</div>
            <div className="text-sm text-white/80">Urgent</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center transition-transform duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
            <div className="text-2xl font-bold">89%</div>
            <div className="text-sm text-white/80">Resolved</div>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* Interactive Map Section */}
        <Card className="civic-card">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center space-x-2">
                <MapPin className="w-5 h-5 text-primary" />
                <span>Jurisdiction Map</span>
              </CardTitle>
              <Button variant="outline" size="sm" className="civic-button-secondary">
                <Filter className="w-4 h-4 mr-2" />
                Filter
              </Button>
            </div>
          </CardHeader>
          <CardContent>
  <MapContainer 
    center={[23.3441, 85.3096]} 
    zoom={13} 
    scrollWheelZoom={false} 
    className="h-64 rounded-lg z-[0]"
  >
    <TileLayer
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    />
    {mockIssues.map(issue => (
      <Marker key={issue.id} position={[issue.lat, issue.lng]}>
        <Popup>
          <b>{issue.title}</b><br />{issue.status}
        </Popup>
      </Marker>
    ))}
  </MapContainer>
</CardContent>
        </Card>

        {/* Special Report Button */}
        <Card 
          className="civic-card hover:shadow-lg cursor-pointer transition-all duration-300 group"
          onClick={() => setShowSpecialReports(true)}
        >
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 bg-civic-gradient rounded-full flex items-center justify-center">
                  <BarChart3 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-primary">Special Reports</h3>
                  <p className="text-muted-foreground">View ignored, overdue & disputed issues</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Real-time Updates */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Zap className="w-5 h-5 text-primary" />
              <span>Live Updates</span>
              <Badge variant="secondary" className="ml-2">Real-time</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {mockUpdates.map((update) => (
                <div 
                  key={update.id}
                  className={cn(
                    "p-3 rounded-lg border-l-4 transition-colors hover:bg-gray-50",
                    getUpdateTypeColor(update.type)
                  )}
                >
                  <div className="flex items-start space-x-3">
                    <span className="text-lg">{update.icon}</span>
                    <div className="flex-1">
                      <p className="font-medium text-sm">{update.title}</p>
                      <p className="text-xs text-muted-foreground mt-1">{update.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Special Reports Modal */}
      {showSpecialReports && (
        <div className="fixed inset-0 bg-black/50 z-1000 flex items-end sm:items-center justify-center p-4">
          <div className="w-full max-w-4xl max-h-[90vh] bg-white rounded-t-2xl sm:rounded-2xl animate-slide-up">
            <div className="p-6 border-b border-border">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Special Reports</h2>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setShowSpecialReports(false)}
                >
                  ✕
                </Button>
              </div>
              
              {/* Tabs */}
              <div className="flex space-x-1 mt-4 bg-muted p-1 rounded-lg">
                {[
                  { id: 'ignored', label: '🚫 Ignored', count: 12 },
                  { id: 'overdue', label: '⏰ Overdue', count: 23 },
                  { id: 'disputed', label: '🔄 Disputed', count: 8 },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveReportTab(tab.id)}
                    className={cn(
                      "flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors",
                      activeReportTab === tab.id
                        ? "bg-white text-primary shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>
            </div>
            
            <div className="p-6 max-h-96 overflow-y-auto">
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((item) => (
                  <div key={item} className="flex items-center space-x-4 p-4 border border-border rounded-lg">
                    <div className="w-16 h-16 bg-muted rounded-lg flex items-center justify-center">
                      <MapPin className="w-6 h-6 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium">Sample {activeReportTab} issue #{item}</h3>
                      <p className="text-sm text-muted-foreground">Description of the issue...</p>
                      <div className="flex items-center space-x-2 mt-1">
                        <StatusBadge status={activeReportTab as any} size="sm" />
                        <span className="text-xs text-muted-foreground">
                          {activeReportTab === 'ignored' ? '6+ months old' : 
                           activeReportTab === 'overdue' ? '15 days overdue' : 
                           '3 disputes'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HomePage;