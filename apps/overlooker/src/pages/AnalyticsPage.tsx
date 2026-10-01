import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  BarChart3, 
  TrendingUp, 
  TrendingDown, 
  Users, 
  Clock, 
  CheckCircle, 
  AlertTriangle,
  Download,
  Calendar,
  Target,
  MapPin,
  Zap
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ 
  title, 
  value, 
  change, 
  changeLabel, 
  icon: Icon, 
  color = 'text-primary' 
}) => {
  const isPositive = change && change > 0;
  const isNegative = change && change < 0;

  return (
    <Card className="civic-card">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold text-foreground">{value}</p>
            {change !== undefined && (
              <div className={cn(
                "flex items-center space-x-1 text-sm",
                isPositive ? "text-green-600" : isNegative ? "text-red-600" : "text-muted-foreground"
              )}>
                {isPositive && <TrendingUp className="w-3 h-3" />}
                {isNegative && <TrendingDown className="w-3 h-3" />}
                <span>{Math.abs(change)}% {changeLabel || (isPositive ? 'increase' : 'decrease')}</span>
              </div>
            )}
          </div>
          <div className={cn("p-3 rounded-full bg-muted", color)}>
            <Icon className="w-6 h-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const AnalyticsPage: React.FC = () => {
  const [timeRange, setTimeRange] = useState('30d');

  // Mock analytics data
  const kpiData = [
    { title: 'Total Issues', value: 1247, change: 12, icon: BarChart3 },
    { title: 'Avg Resolution Time', value: '4.2 days', change: -15, changeLabel: 'improvement', icon: Clock },
    { title: 'Pending Issues', value: 127, change: -8, changeLabel: 'decrease', icon: AlertTriangle },
    { title: 'Citizen Satisfaction', value: '89%', change: 5, icon: Users },
    { title: 'Response Rate', value: '94%', change: 3, icon: CheckCircle },
    { title: 'Escalation Rate', value: '12%', change: -2, changeLabel: 'decrease', icon: TrendingUp },
  ];

  const department = {
    name: 'Roads & Transportation',
    pending: 45,
    avgTime: '5.2 days',
    satisfaction: '87%',
  };

  const trendData = [
    { month: 'Jan', submitted: 89, resolved: 75, satisfaction: 87 },
    { month: 'Feb', submitted: 95, resolved: 82, satisfaction: 89 },
    { month: 'Mar', submitted: 102, resolved: 89, satisfaction: 91 },
    { month: 'Apr', submitted: 87, resolved: 93, satisfaction: 88 },
    { month: 'May', submitted: 112, resolved: 98, satisfaction: 92 },
    { month: 'Jun', submitted: 98, resolved: 105, satisfaction: 89 },
  ];

  const priorityBreakdown = [
    { priority: 'Critical', count: 23, percentage: 18, color: 'bg-red-500' },
    { priority: 'High', count: 45, percentage: 35, color: 'bg-orange-500' },
    { priority: 'Medium', count: 38, percentage: 30, color: 'bg-yellow-500' },
    { priority: 'Low', count: 21, percentage: 17, color: 'bg-green-500' },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] p-6 text-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Analytics Dashboard</h1>
            <p className="text-white/80">Comprehensive performance insights</p>
          </div>
          <div className="flex items-center space-x-2">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-32 bg-white/10 border-white/20 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="90d">Last 3 months</SelectItem>
                <SelectItem value="1y">Last year</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="secondary" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {kpiData.map((kpi, index) => (
            <MetricCard
              key={index}
              title={kpi.title}
              value={kpi.value}
              change={kpi.change}
              changeLabel={kpi.changeLabel}
              icon={kpi.icon}
            />
          ))}
        </div>

        {/* Issue Volume Trends */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              <span>Issue Volume Trends</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-end justify-between space-x-2">
              {trendData.map((data, index) => (
                <div key={index} className="flex-1 flex flex-col items-center">
                  <div className="w-full space-y-1 mb-2">
                    <div 
                      className="bg-red-500 rounded-t"
                      style={{ height: `${(data.submitted / 120) * 150}px` }}
                      title={`Submitted: ${data.submitted}`}
                    />
                    <div 
                      className="bg-green-500 rounded-t"
                      style={{ height: `${(data.resolved / 120) * 150}px` }}
                      title={`Resolved: ${data.resolved}`}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">{data.month}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-center space-x-6 mt-4 text-xs">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-red-500 rounded"></div>
                <span>Submitted</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded"></div>
                <span>Resolved</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Department Performance (Single Department) */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Target className="w-5 h-5 text-primary" />
              <span>Department Performance</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-4 border border-border rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium">{department.name}</h3>
                <Badge variant="outline">{department.pending} pending</Badge>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Avg Resolution:</span>
                  <div className="font-medium">{department.avgTime}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Satisfaction:</span>
                  <div className="font-medium">{department.satisfaction}</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Priority Distribution */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 text-primary" />
              <span>Priority Distribution</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {priorityBreakdown.map((item, index) => (
                <div key={index}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{item.priority}</span>
                    <span className="text-sm text-muted-foreground">
                      {item.count} ({item.percentage}%)
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div
                      className={cn("h-2 rounded-full", item.color)}
                      style={{ width: `${item.percentage}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Geographic Heat Map */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <MapPin className="w-5 h-5 text-primary" />
              <span>Geographic Distribution</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((ward, index) => {
                const colors = [
                  "bg-red-100 text-red-800",
                  "bg-orange-100 text-orange-800",
                  "bg-green-100 text-green-800",
                  "bg-orange-100 text-orange-800",
                  "bg-red-100 text-red-800",
                  "bg-orange-100 text-orange-800",
                  "bg-green-100 text-green-800",
                  "bg-green-100 text-green-800",
                  "bg-red-100 text-red-800"
                ];

                const issues = [45, 32, 8, 15, 52, 19, 9, 6, 40];

                return (
                  <div
                    key={ward}
                    className={cn(
                      "p-4 rounded-lg text-center cursor-pointer transition-colors",
                      colors[index]
                    )}
                  >
                    <div className="text-lg font-bold">Ward {ward}</div>
                    <div className="text-sm">{issues[index]} issues</div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Response Time Analytics */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Clock className="w-5 h-5 text-primary" />
              <span>Response Time Metrics</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-primary">4.2</div>
                  <div className="text-sm text-muted-foreground">Average Days</div>
                  <div className="text-xs text-green-600 mt-1">↓ 15% from last month</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-primary">94%</div>
                  <div className="text-sm text-muted-foreground">Within SLA</div>
                  <div className="text-xs text-green-600 mt-1">↑ 3% from last month</div>
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>10% slower than City Average</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Needs Improvement</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Export Options */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Download className="w-5 h-5 text-primary" />
              <span>Export Reports</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Button variant="outline" className="justify-start">
                <BarChart3 className="w-4 h-4 mr-2" />
                Performance Summary (PDF)
              </Button>
              <Button variant="outline" className="justify-start">
                <Calendar className="w-4 h-4 mr-2" />
                Monthly Report (Excel)
              </Button>
              <Button variant="outline" className="justify-start">
                <Zap className="w-4 h-4 mr-2" />
                Real-time Data (CSV)
              </Button>
              <Button variant="outline" className="justify-start">
                <Target className="w-4 h-4 mr-2" />
                Department Analysis (PDF)
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AnalyticsPage;