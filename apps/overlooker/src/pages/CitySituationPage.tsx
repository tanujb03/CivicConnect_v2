/**
 * O05 — City Situation Analysis
 * Overlooker view: system-wide situational awareness combining
 * geographic, departmental, and temporal data.
 *
 * This is the Overlooker-facing counterpart to Admin A08+A09.
 * Read-only — does not expose admin controls.
 */
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  MapPin, AlertTriangle, TrendingUp, Clock,
  Building2, BarChart3, Layers, RefreshCw,
  Activity, Flame, Droplets, Zap
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend, RadarChart,
  Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

// ─── Mock data ────────────────────────────────────────────────────────────────

const CRITICAL_SITUATIONS = [
  {
    id: 'sit-1',
    type: 'SPATIAL_CLUSTER',
    title: 'Road damage cluster — Ward 12',
    summary: '31 road-damage reports in 7 days within a 800m radius. Infrastructure at risk.',
    severity: 'CRITICAL',
    ward: 'W12',
    cases: 31,
    trend: 'worsening',
  },
  {
    id: 'sit-2',
    type: 'SLA_BREACH_RISK',
    title: 'Water supply SLA at risk — Ward 3',
    summary: '8 water-supply cases approaching 24h SLA deadline with no assigned field worker.',
    severity: 'HIGH',
    ward: 'W3',
    cases: 8,
    trend: 'stable',
  },
  {
    id: 'sit-3',
    type: 'RECURRING_PROBLEM',
    title: 'Sanitation recurring — Ward 18',
    summary: 'Market area sanitation issue has been reported 9 times in 60 days. Root cause unresolved.',
    severity: 'HIGH',
    ward: 'W18',
    cases: 9,
    trend: 'stable',
  },
];

const WARD_HEALTH = [
  { ward: 'W1',  score: 82, cases: 34 },
  { ward: 'W2',  score: 88, cases: 28 },
  { ward: 'W3',  score: 61, cases: 41 },
  { ward: 'W4',  score: 91, cases: 22 },
  { ward: 'W5',  score: 93, cases: 19 },
  { ward: 'W6',  score: 69, cases: 37 },
  { ward: 'W7',  score: 95, cases: 15 },
  { ward: 'W8',  score: 79, cases: 29 },
  { ward: 'W9',  score: 84, cases: 25 },
  { ward: 'W10', score: 93, cases: 18 },
  { ward: 'W11', score: 74, cases: 32 },
  { ward: 'W12', score: 42, cases: 48 },
  { ward: 'W13', score: 90, cases: 20 },
  { ward: 'W14', score: 86, cases: 26 },
  { ward: 'W15', score: 66, cases: 39 },
];

const CITY_TREND = [
  { day: 'Mon', new: 38, resolved: 32, critical: 4 },
  { day: 'Tue', new: 42, resolved: 35, critical: 5 },
  { day: 'Wed', new: 36, resolved: 40, critical: 3 },
  { day: 'Thu', new: 51, resolved: 44, critical: 7 },
  { day: 'Fri', new: 45, resolved: 48, critical: 5 },
  { day: 'Sat', new: 29, resolved: 33, critical: 2 },
  { day: 'Sun', new: 22, resolved: 30, critical: 1 },
];

const DEPT_RADAR = [
  { subject: 'Roads',      SLA: 82, Backlog: 60, Speed: 71 },
  { subject: 'Electrical', SLA: 74, Backlog: 70, Speed: 58 },
  { subject: 'Sanitation', SLA: 91, Backlog: 85, Speed: 88 },
  { subject: 'Water',      SLA: 78, Backlog: 65, Speed: 66 },
  { subject: 'Garbage',    SLA: 88, Backlog: 90, Speed: 92 },
];

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  SPATIAL_CLUSTER:   Flame,
  SLA_BREACH_RISK:   Clock,
  RECURRING_PROBLEM: RefreshCw,
};

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
  HIGH:     'bg-orange-100 text-orange-800 border-orange-200',
  MEDIUM:   'bg-yellow-100 text-yellow-800 border-yellow-200',
};

const TREND_COLORS: Record<string, string> = {
  worsening:  'text-red-600',
  stable:     'text-yellow-600',
  improving:  'text-green-600',
};

function scoreColor(score: number): string {
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-400';
  if (score >= 55) return 'bg-orange-500';
  return 'bg-red-500';
}

// ─── Component ────────────────────────────────────────────────────────────────

const CitySituationPage: React.FC = () => {
  const [selectedTimeRange, setSelectedTimeRange] = useState('7d');

  const cityHealth = Math.round(WARD_HEALTH.reduce((a, w) => a + w.score, 0) / WARD_HEALTH.length);

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Activity className="h-6 w-6 text-primary" />
            City Situation Analysis
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            System-wide situational awareness · Read-only oversight view
          </p>
        </div>
        <div className="flex items-center gap-2">
          {['24h', '7d', '30d'].map(r => (
            <button
              key={r}
              onClick={() => setSelectedTimeRange(r)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedTimeRange === r
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {r}
            </button>
          ))}
          <Button size="sm" variant="outline" className="gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* City Health Score */}
      <Card>
        <CardContent className="pt-5">
          <div className="flex items-center gap-6 flex-wrap">
            <div className="flex flex-col items-center">
              <div className="relative h-20 w-20">
                <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
                  <circle cx="18" cy="18" r="16" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                  <circle
                    cx="18" cy="18" r="16" fill="none"
                    stroke={cityHealth >= 80 ? '#16a34a' : cityHealth >= 65 ? '#eab308' : '#ef4444'}
                    strokeWidth="3"
                    strokeDasharray={`${cityHealth} ${100 - cityHealth}`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-xl font-bold text-foreground">{cityHealth}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-1 text-center">City Health<br />Score</p>
            </div>

            <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              {[
                { label: 'Active Cases',   value: '248', icon: BarChart3, color: 'text-blue-600' },
                { label: 'Critical',       value: '23',  icon: AlertTriangle, color: 'text-red-600' },
                { label: 'Wards Affected', value: '12',  icon: MapPin, color: 'text-orange-600' },
                { label: 'Situations',     value: String(CRITICAL_SITUATIONS.length), icon: Flame, color: 'text-amber-600' },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="py-2">
                  <Icon className={`h-5 w-5 mx-auto mb-1 ${color}`} />
                  <p className={`text-2xl font-bold ${color}`}>{value}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active Situations */}
      <div>
        <h2 className="text-base font-semibold text-foreground mb-3 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          Active Situations ({CRITICAL_SITUATIONS.length})
        </h2>
        <div className="space-y-3">
          {CRITICAL_SITUATIONS.map(sit => {
            const Icon = CATEGORY_ICONS[sit.type] ?? AlertTriangle;
            return (
              <Card key={sit.id} className="border-l-4 border-l-orange-400">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-3">
                    <div className="h-8 w-8 rounded-lg bg-orange-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Icon className="h-4 w-4 text-orange-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-foreground">{sit.title}</p>
                        <Badge className={`text-[10px] border ${SEVERITY_COLORS[sit.severity] ?? 'bg-gray-100 text-gray-700'}`}>
                          {sit.severity}
                        </Badge>
                        <span className="text-xs font-medium text-muted-foreground">{sit.ward}</span>
                        <span className={`text-xs font-medium capitalize ${TREND_COLORS[sit.trend]}`}>↑ {sit.trend}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{sit.summary}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        <span className="font-medium">{sit.cases} cases</span> contributing to this situation
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* City 7-day trend + Dept radar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              City-wide Daily Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={CITY_TREND}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="new"      stroke="#3b82f6" strokeWidth={2} dot={false} name="New" />
                <Line type="monotone" dataKey="resolved" stroke="#16a34a" strokeWidth={2} dot={false} name="Resolved" />
                <Line type="monotone" dataKey="critical" stroke="#ef4444" strokeWidth={2} dot={false} name="Critical" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" />
              Department Performance Radar
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={DEPT_RADAR}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9 }} />
                <Radar name="SLA %"  dataKey="SLA"    stroke="#16a34a" fill="#16a34a" fillOpacity={0.25} />
                <Radar name="Speed"  dataKey="Speed"  stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Ward health grid */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            Ward Health Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-5 sm:grid-cols-8 xl:grid-cols-15 gap-2">
            {WARD_HEALTH.map(w => (
              <div
                key={w.ward}
                title={`${w.ward}: Score ${w.score}, ${w.cases} cases`}
                className="flex flex-col items-center"
              >
                <div className={`w-10 h-10 rounded-lg ${scoreColor(w.score)} flex items-center justify-center`}>
                  <span className="text-white text-xs font-bold">{w.score}</span>
                </div>
                <span className="text-[10px] text-muted-foreground mt-1">{w.ward}</span>
                <span className="text-[10px] text-muted-foreground">{w.cases}c</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 mt-4">
            <span className="text-xs text-muted-foreground">Health:</span>
            {[['bg-green-500', '≥85'], ['bg-yellow-400', '70–84'], ['bg-orange-500', '55–69'], ['bg-red-500', '<55']].map(([cls, label]) => (
              <div key={label} className="flex items-center gap-1">
                <div className={`w-3 h-3 rounded ${cls}`} />
                <span className="text-[10px] text-muted-foreground">{label}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Category breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            Issue Category Breakdown (Top Wards)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={[
                { ward: 'W12', Roads: 21, Sanitation: 12, Electrical: 8,  Water: 4, Garbage: 3 },
                { ward: 'W15', Roads: 14, Sanitation: 10, Electrical: 7,  Water: 5, Garbage: 3 },
                { ward: 'W3',  Roads: 12, Sanitation: 14, Electrical: 5,  Water: 8, Garbage: 2 },
                { ward: 'W6',  Roads: 16, Sanitation: 8,  Electrical: 6,  Water: 4, Garbage: 3 },
                { ward: 'W11', Roads: 10, Sanitation: 9,  Electrical: 7,  Water: 3, Garbage: 3 },
              ]}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="ward" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Roads"      stackId="a" fill="#16a34a" />
              <Bar dataKey="Sanitation" stackId="a" fill="#3b82f6" />
              <Bar dataKey="Electrical" stackId="a" fill="#eab308" />
              <Bar dataKey="Water"      stackId="a" fill="#06b6d4" />
              <Bar dataKey="Garbage"    stackId="a" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
};

export default CitySituationPage;
