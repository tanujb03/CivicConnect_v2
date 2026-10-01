import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import IssueCard, { Issue } from '@/components/common/IssueCard';
import { 
  Search, 
  Filter, 
  X, 
  TrendingUp, 
  MessageSquare, 
  Users, 
  Eye,
  MapPin,
  Calendar,
  Activity
} from 'lucide-react';

// Mock community data - same issues as citizen portal but read-only
const communityIssues: Issue[] = [
  {
    id: '1',
    title: 'Street food vendors blocking sidewalk',
    description: 'Multiple food vendors have set up permanent stalls on the main sidewalk, forcing pedestrians to walk on the road.',
    status: 'submitted',
    priority: 'medium',
    category: 'Roads & Transportation',
    location: 'Main Bazaar, Commercial Street',
    ward: 'Ward 6',

    reportedAt: new Date('2024-01-18'),
    imageUrl: 'https://erepublic.brightspotcdn.com/dims4/default/b2142c5/2147483647/strip/true/crop/1512x788+0+22/resize/840x438!/quality/90/?url=http%3A%2F%2Ferepublic-brightspot.s3.us-west-2.amazonaws.com%2F44%2F48%2F997684134acbad8e4cca16fb14a9%2F1708-amtrak-371a.jpg',
    upvotes: 156,
    reportedBy: ''
  },
  {
    id: '2',
    title: 'Children playing in construction site - safety hazard',
    description: 'An abandoned construction site has become a playground for children. No safety barriers present.',
    status: 'urgent',
    priority: 'critical',
    category: 'Public Safety',
    location: 'New Colony, Near Park',
    ward: 'Ward 8',

    reportedAt: new Date('2024-01-17'),
    imageUrl: 'https://cdn.prod.website-files.com/64ee6c6f0da86184dbf899fb/65a93dc100e30b8e35d6075f_iStock-1422796768.jpg',
    upvotes: 89,
    reportedBy: ''
  },
  {
    id: '3',
    title: 'Public toilet maintenance required urgently',
    description: 'Public toilet facility is in extremely poor condition and unusable. Community requests immediate action.',
    status: 'in-progress',
    priority: 'high',
    category: 'Sanitation',
    location: 'Bus Stand, Platform 2',
    ward: 'Ward 4',

    reportedAt: new Date('2024-01-15'),
    imageUrl: 'https://currentaffairs.khanglobalstudies.com/wp-content/uploads/2025/01/Quick_Guide_to_Cleaning_Public_Toilets_Effectively.jpg',
    upvotes: 234,
    reportedBy: ''
  },
  {
    id: '4',
    title: 'Stray dogs creating nuisance and safety concerns',
    description: 'Pack of stray dogs in residential area causing fear among residents, especially children and elderly.',
    status: 'disputed',
    priority: 'medium',
    category: 'Public Safety',
    location: 'Residential Complex, Block C',
    ward: 'Ward 2',

    reportedAt: new Date('2024-01-12'),
    imageUrl: 'data:image/jpeg;base64,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',
    upvotes: 67,
    reportedBy: ''
  },
  {
    id: '5',
    title: 'Community park lights not working after sunset',
    description: 'Park becomes unsafe after dark as lighting system has been non-functional for weeks.',
    status: 'overdue',
    priority: 'medium',
    category: 'Electrical',
    location: 'Community Park, Sector 3',
    ward: 'Ward 9',

    reportedAt: new Date('2024-01-05'),
    
    imageUrl: 'https://static.toiimg.com/thumb/msid-99369090,width-400,height-225,resizemode-72/99369090.jpg',
    upvotes: 123,
    reportedBy: ''
  },
  {
    id: '6',
    title: 'Water quality issues in municipal supply',
    description: 'Community reporting foul smell and taste in municipal water supply for the past week.',
    status: 'resolved',
    priority: 'high',
    category: 'Water Supply',
    location: 'Entire Ward Area',
    ward: 'Ward 7',
    reportedAt: new Date('2024-01-01'),
    imageUrl: 'data:image/jpeg;base64,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',
    upvotes: 445,
    reportedBy: ''
  }
];

const CommunityPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [sortBy, setSortBy] = useState('popular');
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  const clearFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setCategoryFilter('all');
    setSortBy('popular');
  };

  const filteredIssues = communityIssues
    .filter(issue => {
      const matchesSearch = issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           issue.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           issue.location.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = statusFilter === 'all' || issue.status === statusFilter;
      const matchesCategory = categoryFilter === 'all' || issue.category === categoryFilter;
      return matchesSearch && matchesStatus && matchesCategory;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'popular':
          return (b.upvotes || 0) - (a.upvotes || 0);
        case 'recent':
          return b.reportedAt.getTime() - a.reportedAt.getTime();
        default:
          return 0;
      }
    });

  const communityStats = {
    totalIssues: communityIssues.length,
    activeUsers: 1247,
    resolvedThisWeek: 23,
    avgResponseTime: '4.2 days'
  };

  const activeFiltersCount = [statusFilter, categoryFilter]
    .filter(filter => filter !== 'all').length + (searchQuery ? 1 : 0);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] p-6 text-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Community Portal</h1>
            <p className="text-white/80">Citizen-reported issues and community engagement</p>
          </div>
          <Badge className="bg-white/20 text-white border-white/30">
            <Eye className="w-3 h-3 mr-1" />
            View Only
          </Badge>
        </div>

        {/* Community Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{communityStats.totalIssues}</div>
            <div className="text-xs text-white/80">Total Issues</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{communityStats.activeUsers}</div>
            <div className="text-xs text-white/80">Active Citizens</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{communityStats.resolvedThisWeek}</div>
            <div className="text-xs text-white/80">Resolved This Week</div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <div className="text-xl font-bold">{communityStats.avgResponseTime}</div>
            <div className="text-xs text-white/80">Avg Response</div>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Search and Filters */}
        <Card className="civic-card">
          <CardContent className="p-4">
            {/* Search Bar */}
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
              <Input
                placeholder="Search community issues..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Filters */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="submitted">Submitted</SelectItem>
                  <SelectItem value="in-progress">In Progress</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                  <SelectItem value="overdue">Overdue</SelectItem>
                  <SelectItem value="disputed">Disputed</SelectItem>
                </SelectContent>
              </Select>

              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="Roads & Transportation">Roads & Transportation</SelectItem>
                  <SelectItem value="Electrical">Electrical</SelectItem>
                  <SelectItem value="Sanitation">Sanitation</SelectItem>
                  <SelectItem value="Public Safety">Public Safety</SelectItem>
                  <SelectItem value="Water Supply">Water Supply</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger>
                  <SelectValue placeholder="Sort By" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="popular">Most Popular</SelectItem>
                  <SelectItem value="recent">Most Recent</SelectItem>
                </SelectContent>
              </Select>

              <Button 
                variant="outline" 
                onClick={clearFilters}
                disabled={activeFiltersCount === 0}
              >
                <X className="w-4 h-4 mr-1" />
                Clear ({activeFiltersCount})
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Trending Issues */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <span>Trending This Week</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {communityIssues
                .sort((a, b) => (b.upvotes || 0) - (a.upvotes || 0))
                .slice(0, 3)
                .map((issue, index) => (
                  <div 
                    key={issue.id}
                    className="flex items-center space-x-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
                    onClick={() => setSelectedIssue(issue)}
                  >
                    <div className="text-2xl font-bold text-primary">#{index + 1}</div>
                    <div className="flex-1">
                      <h3 className="font-medium line-clamp-1">{issue.title}</h3>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground mt-1">
                        <div className="flex items-center space-x-1">
                          <TrendingUp className="w-3 h-3" />
                          <span>{issue.upvotes} upvotes</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <MapPin className="w-3 h-3" />
                          <span>{issue.ward}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        {/* Community Engagement */}
        <Card className="civic-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Activity className="w-5 h-5 text-primary" />
              <span>Community Activity</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm">36 new issues reported today</span>
                </div>
                <span className="text-xs text-muted-foreground">2 hours ago</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  <span className="text-sm">120+ users responded to water quality concerns</span>
                </div>
                <span className="text-xs text-muted-foreground">4 hours ago</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                  <span className="text-sm">13 Reports resolved in past 24 hours.</span>
                </div>
                <span className="text-xs text-muted-foreground">6 hours ago</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results Summary */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {filteredIssues.length} Community Issue{filteredIssues.length !== 1 ? 's' : ''}
          </h2>
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Read-only view</span>
          </div>
        </div>

        {/* Issues Grid - No action buttons for community view */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredIssues.map((issue) => (
            <IssueCard
              key={issue.id}
              issue={issue}
              onClick={() => setSelectedIssue(issue)}
              showActions={false} // Community view is read-only
            />
          ))}
        </div>

        {filteredIssues.length === 0 && (
          <Card className="civic-card">
            <CardContent className="p-8 text-center">
              <Users className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No Community Issues Found</h3>
              <p className="text-muted-foreground">
                Try adjusting your search criteria or filters to find relevant community issues.
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Issue Detail Modal - Read-only */}
      {selectedIssue && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-2xl overflow-hidden">
            <div className="p-6 border-b border-border">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Community Issue Details</h2>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setSelectedIssue(null)}
                >
                  ✕
                </Button>
              </div>
            </div>
            
            <div className="p-6 max-h-96 overflow-y-auto space-y-6">
              {/* Issue Image */}
              {selectedIssue.imageUrl && (
                <div className="aspect-video overflow-hidden rounded-lg">
                  <img 
                    src={selectedIssue.imageUrl} 
                    alt={selectedIssue.title}
                    className="w-full h-full object-cover"
                  />
                </div>
              )}

              {/* Issue Info */}
              <div>
                <h3 className="text-xl font-semibold mb-2">{selectedIssue.title}</h3>
                <p className="text-muted-foreground mb-4">{selectedIssue.description}</p>
                
                <div className="grid grid-cols-2 gap-4 text-sm">
                  
                  <div>
                    <span className="font-medium">Date:</span>
                    <div className="mt-1 text-muted-foreground">
                      {selectedIssue.reportedAt.toLocaleDateString()}
                    </div>
                  </div>
                  <div>
                    <span className="font-medium">Location:</span>
                    <div className="mt-1 text-muted-foreground">{selectedIssue.location}</div>
                  </div>
                  <div>
                    <span className="font-medium">Category:</span>
                    <div className="mt-1 text-muted-foreground">{selectedIssue.category}</div>
                  </div>
                </div>
              </div>

              {/* Community Engagement Stats */}
              <div className="bg-muted/50 p-4 rounded-lg">
                <h4 className="font-medium mb-3">Community Engagement</h4>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-1">
                      <TrendingUp className="w-4 h-4 text-primary" />
                      <span className="text-sm">{selectedIssue.upvotes} upvotes</span>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-muted-foreground">
                    <Eye className="w-3 h-3 mr-1" />
                    View Only
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CommunityPage;
