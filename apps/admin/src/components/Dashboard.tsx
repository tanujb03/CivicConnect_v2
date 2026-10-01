import React from 'react';
import { ArrowUpRight, ArrowDownRight, Users, FileText, Clock, AlertCircle, TrendingUp, RotateCcw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import CityMap from './CityMap';
import WardHeatmap from './WardHeatmap';
import DepartmentPerformance from './DepartmentPerformance';
import RecentIssuesTable from './RecentIssuesTable';

const statsData = [
  {
    title: 'Total Active Citizens',
    value: '12,847',
    change: '+8.2%',
    trend: 'up',
    icon: Users,
  },
  {
    title: 'Reports This Month',
    value: '1,234',
    change: '+15.3%',
    trend: 'up',
    icon: FileText,
  },
  {
    title: 'Average Resolution Time',
    value: '4.2 days',
    change: '-12.5%',
    trend: 'down',
    icon: Clock,
  },
  {
    title: 'Critical Issues Pending',
    value: '23',
    change: '+5',
    trend: 'up',
    icon: AlertCircle,
  },
  {
    title: 'Escalated Issues Count',
    value: '45',
    change: '-8',
    trend: 'down',
    icon: TrendingUp,
  },
  {
    title: 'Cross-department Reassignments',
    value: '67',
    change: '+12',
    trend: 'up',
    icon: RotateCcw,
  },
];

const trendingIssuesData = [
  { name: 'Potholes', value: 145 },
  { name: 'Street Lights', value: 89 },
  { name: 'Garbage', value: 76 },
  { name: 'Water Supply', value: 54 },
  { name: 'Drainage', value: 43 },
];

const resolutionTrendsData = [
  { month: 'Jan', resolved: 120, pending: 45 },
  { month: 'Feb', resolved: 135, pending: 38 },
  { month: 'Mar', resolved: 150, pending: 42 },
  { month: 'Apr', resolved: 142, pending: 35 },
  { month: 'May', resolved: 165, pending: 28 },
  { month: 'Jun', resolved: 178, pending: 23 },
];

const departmentWorkloadData = [
  { department: 'Roads', resolved: 89, pending: 23 },
  { department: 'Electrical', resolved: 76, pending: 18 },
  { department: 'Sanitation', resolved: 54, pending: 12 },
  { department: 'Garbage', resolved: 67, pending: 15 },
];

const Dashboard: React.FC = () => {
  return (
    <div className="ml-64 p-6 bg-civic-bg min-h-screen">
      {/* Stats Cards */}
      <div className="grid grid-cols-6 gap-6 mb-8">
        {statsData.map((stat, index) => {
          const Icon = stat.icon;
          const isPositive = stat.trend === 'up' && stat.change.startsWith('+');
          const isNegative = stat.trend === 'up' && !stat.change.startsWith('-');
          
          return (
            <div key={index} className="civic-card p-6">
              <div className="flex items-center justify-between mb-4">
                <Icon className="h-8 w-8 text-civic-primary" />
                {stat.trend === 'up' ? (
                  <ArrowUpRight className={`h-5 w-5 ${isPositive ? 'trend-up' : 'trend-down'}`} />
                ) : (
                  <ArrowDownRight className="h-5 w-5 trend-up" />
                )}
              </div>
              <div className="space-y-1">
                <h3 className="text-2xl font-bold text-civic-text-primary">{stat.value}</h3>
                <p className="text-sm text-civic-text-secondary">{stat.title}</p>
                <p className={`text-xs font-medium ${isPositive || stat.trend === 'down' ? 'trend-up' : 'trend-down'}`}>
                  {stat.change}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Interactive City Map */}
      <CityMap />

      {/* Main Content Grid */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {/* Ward-wise Heatmap */}
        <div className="col-span-2">
          <WardHeatmap />
        </div>

        {/* Department Performance */}
        <div className="col-span-1">
          <DepartmentPerformance />
        </div>
      </div>

      {/* Recent Issues Table */}
      <RecentIssuesTable />

      {/* Analytics Charts Row */}
      <div className="grid grid-cols-3 gap-6">
        {/* Trending Issues Chart */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Trending Issues</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={trendingIssuesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="hsl(var(--civic-primary))" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Resolution Trends Chart */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Resolution Trends</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={resolutionTrendsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="resolved" stroke="hsl(var(--civic-success))" strokeWidth={2} />
              <Line type="monotone" dataKey="pending" stroke="hsl(var(--civic-danger))" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Department Workload Chart */}
        <div className="civic-card p-6">
          <h3 className="text-lg font-semibold text-civic-text-primary mb-4">Department Workload</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={departmentWorkloadData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="department" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="pending" stackId="a" fill="hsl(var(--civic-danger))" />
              <Bar dataKey="resolved" stackId="a" fill="hsl(var(--civic-success))" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;