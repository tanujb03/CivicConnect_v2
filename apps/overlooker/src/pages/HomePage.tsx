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
  Bell,
  ChevronRight,
  X,
  Sparkles
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

const mockUpdates = [
  { id: '1', type: 'citywide', icon: '📢', title: 'Trash pickup delayed today due to holiday', time: '2 hours ago', priority: 'medium' },
  { id: '2', type: 'local', icon: '💧', title: '50 citizens reported water logging in your area', time: '3 hours ago', priority: 'high' },
  { id: '3', type: 'alert', icon: '⚠️', title: 'Traffic light outage at Central Crossing', time: '4 hours ago', priority: 'urgent' },
  { id: '4', type: 'update', icon: '🔧', title: 'Water main repair completed in Ward 12', time: '6 hours ago', priority: 'low' },
  { id: '5', type: 'weekly', icon: '📊', title: '89% issue resolution rate this week (+5%)', time: '1 day ago', priority: 'low' },
  { id: '6', type: 'citywide', icon: '🌳', title: 'Tree plantation drive scheduled this weekend', time: '1 day ago', priority: 'medium' },
  { id: '7', type: 'alert', icon: '🔥', title: 'Small fire reported near Market Street, under control', time: '18 hours ago', priority: 'high' },
  { id: '8', type: 'local', icon: '🚧', title: 'Road maintenance on Park Avenue, expect delays', time: '12 hours ago', priority: 'medium' },
  { id: '9', type: 'update', icon: '🏥', title: 'New health center inaugurated in Ward 7', time: '2 days ago', priority: 'low' },
  { id: '10', type: 'weekly', icon: '📈', title: 'Citizen satisfaction index rises by 12%', time: '3 days ago', priority: 'low' },
  { id: '11', type: 'citywide', icon: '🚌', title: 'Additional buses deployed during morning rush hours', time: '5 hours ago', priority: 'medium' },
  { id: '12', type: 'alert', icon: '🌩️', title: 'Severe thunderstorm warning issued for the evening', time: '30 minutes ago', priority: 'urgent' },
  { id: '13', type: 'local', icon: '🛒', title: 'Weekly farmers market opens at Riverside Ground', time: '7 hours ago', priority: 'low' },
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

  const getUpdateTypeColor = (type: string) => {
    switch (type) {
      case 'alert': return 'border-l-red-400 bg-red-50/50';
      case 'citywide': return 'border-l-blue-400 bg-blue-50/50';
      case 'local': return 'border-l-amber-400 bg-amber-50/50';
      case 'update': return 'border-l-emerald-400 bg-emerald-50/50';
      case 'weekly': return 'border-l-purple-400 bg-purple-50/50';
      default: return 'border-l-gray-400 bg-gray-50/50';
    }
  };

  const statCards = [
    { value: '127', label: 'Active Issues', color: 'text-white' },
    { value: '23', label: 'Urgent', color: 'text-red-300' },
    { value: '89%', label: 'Resolved', color: 'text-emerald-300' },
  ];

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(180deg, hsl(140,25%,99%) 0%, hsl(140,20%,96%) 100%)' }}>
      {/* ─── Premium Header ──────────────────────────────────────── */}
      <div className="civic-gradient-bg px-5 pt-6 pb-7 text-white">
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-[11px] text-white/40 font-medium tracking-wider uppercase">CivicConnect</p>
            <h1 className="text-2xl font-extrabold tracking-tight mt-0.5">Good Morning, Overlooker</h1>
            <p className="text-white/50 text-sm mt-0.5">Ranchi Municipal Corporation</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-white/10 text-white/80 border-white/15 backdrop-blur-sm rounded-lg px-3 py-1 text-xs font-medium">
              Ward 1-15
            </Badge>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-3">
          {statCards.map((stat, i) => (
            <div
              key={i}
              className="bg-white/10 backdrop-blur-sm rounded-2xl p-3.5 text-center border border-white/10 hover:bg-white/15 transition-all duration-300 cursor-default group"
            >
              <div className={`text-2xl font-extrabold tracking-tight ${stat.color}`}>{stat.value}</div>
              <div className="text-[10px] text-white/50 font-medium mt-0.5 uppercase tracking-wider">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="px-5 pt-5 space-y-5">
        {/* ─── Map Section ──────────────────────────────────────── */}
        <Card className="civic-card overflow-hidden">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-[15px]">
                <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
                  <MapPin className="w-4 h-4 text-emerald-600" />
                </div>
                Jurisdiction Map
              </CardTitle>
              <Button variant="outline" size="sm" className="rounded-xl border-emerald-200 text-emerald-700 hover:bg-emerald-50 text-xs font-semibold h-8">
                <Filter className="w-3.5 h-3.5 mr-1.5" />
                Filter
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <MapContainer 
              center={[23.3441, 85.3096]} 
              zoom={13} 
              scrollWheelZoom={false} 
              className="h-56 z-[0]"
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

        {/* ─── Special Report CTA ───────────────────────────────── */}
        <Card 
          className="civic-card hover-lift cursor-pointer group"
          onClick={() => setShowSpecialReports(true)}
        >
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"
                     style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)', boxShadow: '0 4px 15px rgba(22,163,74,0.25)' }}>
                  <BarChart3 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-[15px] text-gray-900">Special Reports</h3>
                  <p className="text-sm text-gray-500 mt-0.5">View ignored, overdue & disputed issues</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-emerald-500 group-hover:translate-x-1 transition-all duration-300" />
            </div>
          </CardContent>
        </Card>

        {/* ─── Live Updates ─────────────────────────────────────── */}
        <Card className="civic-card">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-[15px]">
              <div className="w-7 h-7 rounded-lg bg-amber-50 flex items-center justify-center">
                <Zap className="w-4 h-4 text-amber-600" />
              </div>
              Live Updates
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-md text-[10px] font-semibold border border-emerald-100 ml-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Real-time
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5 max-h-[320px] overflow-y-auto pr-1 scrollbar-hide">
              {mockUpdates.map((update, i) => (
                <div 
                  key={update.id}
                  className={cn(
                    "p-3 rounded-xl border-l-4 transition-all duration-300 hover:shadow-sm cursor-pointer group",
                    getUpdateTypeColor(update.type)
                  )}
                  style={{ animationDelay: `${i * 0.03}s` }}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-lg shrink-0 mt-0.5">{update.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-gray-800 group-hover:text-gray-900 transition-colors leading-snug">{update.title}</p>
                      <p className="text-xs text-gray-400 mt-1 font-medium">{update.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ─── Special Reports Modal ──────────────────────────────── */}
      {showSpecialReports && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[1000] flex items-end sm:items-center justify-center p-4">
          <div className="w-full max-w-4xl max-h-[90vh] bg-white rounded-t-3xl sm:rounded-3xl animate-slide-up shadow-2xl">
            <div className="p-6 border-b border-gray-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                       style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)' }}>
                    <BarChart3 className="w-4 h-4 text-white" />
                  </div>
                  <h2 className="text-xl font-bold text-gray-900">Special Reports</h2>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setShowSpecialReports(false)}
                  className="rounded-xl hover:bg-gray-100 w-8 h-8 p-0"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              
              {/* Tabs */}
              <div className="flex gap-1 mt-4 bg-gray-100/70 p-1 rounded-xl">
                {[
                  { id: 'ignored', label: '🚫 Ignored', count: 12 },
                  { id: 'overdue', label: '⏰ Overdue', count: 23 },
                  { id: 'disputed', label: '🔄 Disputed', count: 8 },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveReportTab(tab.id)}
                    className={cn(
                      "flex-1 py-2.5 px-3 rounded-lg text-sm font-semibold transition-all duration-300",
                      activeReportTab === tab.id
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    )}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>
            </div>
            
            <div className="p-6 max-h-96 overflow-y-auto">
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((item) => (
                  <div key={item} className="flex items-center gap-4 p-4 border border-gray-100 rounded-2xl hover:border-emerald-100 hover:shadow-sm transition-all duration-300 cursor-pointer group">
                    <div className="w-14 h-14 bg-gray-50 rounded-xl flex items-center justify-center group-hover:bg-emerald-50 transition-colors">
                      <MapPin className="w-5 h-5 text-gray-400 group-hover:text-emerald-500 transition-colors" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900">Sample {activeReportTab} issue #{item}</h3>
                      <p className="text-sm text-gray-500 mt-0.5">Description of the issue...</p>
                      <div className="flex items-center gap-2 mt-2">
                        <StatusBadge status={activeReportTab as any} size="sm" />
                        <span className="text-xs text-gray-400 font-medium">
                          {activeReportTab === 'ignored' ? '6+ months old' : 
                           activeReportTab === 'overdue' ? '15 days overdue' : 
                           '3 disputes'}
                        </span>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-emerald-400 transition-colors" />
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