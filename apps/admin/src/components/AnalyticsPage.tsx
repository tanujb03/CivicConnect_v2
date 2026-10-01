import React from 'react';
import { Users, Clock, Activity, HardDrive } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const userMetrics = [
  { label: 'Daily Active Users', value: '2,847', icon: Users },
  { label: 'Weekly Active Users', value: '8,234', icon: Activity },
  { label: 'App Engagement Rate', value: '73.5%', icon: Activity },
  { label: 'Average Session Duration', value: '4.2 min', icon: Clock },
];

const systemMetrics = [
  { label: 'Server Uptime', value: '99.8%', color: 'text-green-600' },
  { label: 'Average API Response', value: '120ms', color: 'text-blue-600' },
  { label: 'Storage Usage', value: '2.3GB / 10GB', color: 'text-orange-600' },
  { label: 'Peak Concurrent Users', value: '456', color: 'text-purple-600' },
];

const globalTrendsData = [
  { month: 'Jan', resolved: 450, pending: 120 },
  { month: 'Feb', resolved: 520, pending: 98 },
  { month: 'Mar', resolved: 480, pending: 110 },
  { month: 'Apr', resolved: 590, pending: 85 },
  { month: 'May', resolved: 630, pending: 72 },
  { month: 'Jun', resolved: 710, pending: 65 },
];

const AnalyticsPage: React.FC = () => {
  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-civic-text-primary mb-2">Analytics & Reports</h2>
        <p className="text-civic-text-secondary">Comprehensive system analytics and performance metrics</p>
      </div>

      {/* User Analytics Section */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* User Metrics */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4">User Metrics</h3>
          <div className="grid grid-cols-2 gap-4">
            {userMetrics.map((metric, index) => {
              const Icon = metric.icon;
              return (
                <div key={index} className="text-center p-4 border border-gray-200 rounded-lg">
                  <Icon className="h-8 w-8 text-civic-primary mx-auto mb-2" />
                  <p className="text-2xl font-bold text-civic-text-primary">{metric.value}</p>
                  <p className="text-sm text-civic-text-secondary">{metric.label}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* System Performance */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4">System Performance</h3>
          <div className="space-y-4">
            {systemMetrics.map((metric, index) => (
              <div key={index} className="flex justify-between items-center p-3 border border-gray-200 rounded-lg">
                <span className="text-civic-text-secondary">{metric.label}</span>
                <span className={`font-semibold ${metric.color}`}>{metric.value}</span>
              </div>
            ))}
            
            {/* Storage Usage Progress Bar */}
            <div className="mt-4">
              <div className="flex justify-between text-sm mb-1">
                <span>Storage Usage</span>
                <span>23% used</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-orange-500 h-2 rounded-full" style={{ width: '23%' }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Global Issue Analytics */}
      <div className="civic-card p-6">
        <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Global Issue Resolution Trends</h3>
        <div style={{ width: '100%', height: 300 }}>
          <ResponsiveContainer>
            <AreaChart data={globalTrendsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="resolved"
                stackId="1"
                stroke="hsl(var(--civic-success))"
                fill="hsl(var(--civic-success))"
                fillOpacity={0.6}
              />
              <Area
                type="monotone"
                dataKey="pending"
                stackId="1"
                stroke="hsl(var(--civic-danger))"
                fill="hsl(var(--civic-danger))"
                fillOpacity={0.6}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsPage;