import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import IssueCard, { Issue } from '@/components/common/IssueCard';
import StatusBadge from '@/components/common/StatusBadge';
import { Search, Filter, X, MapPin, TrendingUp, Flag } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { motion, AnimatePresence } from 'framer-motion';

const mockIssues: Issue[] = [
  { id: '1', title: 'Broken footpath near school', description: 'The footpath is broken and unsafe for children.', status: 'submitted', priority: 'high', category: 'Roads & Transportation', location: 'Model Colony', ward: 'Ward 2', reportedBy: 'Rahul Patil', reportedAt: new Date('2024-02-01'), imageUrl: 'https://images.hindustantimes.com/img/2022/06/01/550x309/7f54f51c-e1d6-11ec-a220-69841afa1483_1654107309215.jpg', daysRemaining: 3, isOverdue: false, upvotes: 12, comments: 4 },
  { id: '2', title: 'Garbage not collected in sector 8', description: 'Dustbins overflowing for last 3 days.', status: 'submitted', priority: 'medium', category: 'Sanitation', location: 'Sector 8', ward: 'Ward 5', reportedBy: 'Anjali Mehta', reportedAt: new Date('2024-02-02'), imageUrl: 'https://images.hindustantimes.com/rf/image_size_630x354/HT/p2/2018/09/21/Pictures/_615a211a-bdca-11e8-95ec-91800d079bb4.jpg', daysRemaining: 5, isOverdue: false, upvotes: 6, comments: 1 },
  { id: '3', title: 'Street dog nuisance reported', description: 'Pack of street dogs causing disturbance.', status: 'submitted', priority: 'low', category: 'Animal Control', location: 'Laxmi Nagar', ward: 'Ward 3', reportedBy: 'Sunita Devi', reportedAt: new Date('2024-02-03'), imageUrl: 'https://www.punjabtodaynews.com/wp-content/uploads/2025/08/Stray-dogs-story.jpg', daysRemaining: 7, isOverdue: false, upvotes: 3, comments: 0 },
  { id: '4', title: 'Park lights not working', description: 'Public park lights not functioning at night.', status: 'submitted', priority: 'medium', category: 'Electrical', location: 'Green Park', ward: 'Ward 4', reportedBy: 'Amit Sharma', reportedAt: new Date('2024-02-04'), imageUrl: '/images/streetlight-issue.jpg', daysRemaining: 4, isOverdue: false, upvotes: 5, comments: 2 },
  { id: '5', title: 'Potholes near hospital gate', description: 'Ambulances struggling due to potholes.', status: 'submitted', priority: 'critical', category: 'Roads & Transportation', location: 'Civil Hospital', ward: 'Ward 1', reportedBy: 'Meena Sharma', reportedAt: new Date('2024-02-05'), imageUrl: 'https://thepatriot.in/wp-content/uploads/2025/05/potholes.jpg', daysRemaining: -1, isOverdue: true, upvotes: 8, comments: 3 },
  { id: '6', title: 'Illegal construction complaint', description: 'Unauthorized building in sector 5.', status: 'submitted', priority: 'high', category: 'Urban Development', location: 'Sector 5', ward: 'Ward 6', reportedBy: 'Deepak Gupta', reportedAt: new Date('2024-02-06'), imageUrl: 'https://www.mumbailive.com/images/news/images_1522061450034_illegal_construction.jpg?fm=webp&w=1368', daysRemaining: 6, isOverdue: false, upvotes: 7, comments: 1 },

  { id: '7', title: 'Street lights repair ongoing', description: 'Electrical department is fixing street lights.', status: 'in-progress', priority: 'high', category: 'Electrical', location: 'Green Park', ward: 'Ward 3', reportedBy: 'Sunil Kumar', reportedAt: new Date('2024-02-03'), imageUrl: '/images/streetlight-issue.jpg', daysRemaining: 2, isOverdue: false, upvotes: 10, comments: 2 },
  { id: '8', title: 'Road resurfacing work in progress', description: 'Road near central market is being resurfaced.', status: 'in-progress', priority: 'medium', category: 'Roads & Transportation', location: 'Central Market', ward: 'Ward 1', reportedBy: 'Meena Sharma', reportedAt: new Date('2024-02-01'), imageUrl: 'https://assets.telegraphindia.com/telegraph/c75de910-8e88-4bb4-9a19-6fc4cff66c99.jpg', daysRemaining: 5, isOverdue: false, upvotes: 5, comments: 1 },
  { id: '9', title: 'Garbage collection ongoing', description: 'Municipal team is clearing garbage in Ward 5.', status: 'in-progress', priority: 'medium', category: 'Sanitation', location: 'Ward 5', ward: 'Ward 5', reportedBy: 'Priya Singh', reportedAt: new Date('2024-02-02'), imageUrl: 'https://assets.kpmg.com/is/image/kpmg/garbage-collection:cq5dam.web.1200.630', daysRemaining: 1, isOverdue: false, upvotes: 4, comments: 0 },
  { id: '10', title: 'Water pipeline repair', description: 'Repair work for broken pipeline is ongoing.', status: 'in-progress', priority: 'high', category: 'Sanitation', location: 'Sector 2', ward: 'Ward 2', reportedBy: 'Amit Sharma', reportedAt: new Date('2024-02-05'), imageUrl: 'https://images.indianexpress.com/2019/10/water-pipeline.jpg', daysRemaining: 3, isOverdue: false, upvotes: 6, comments: 1 },
  { id: '11', title: 'Traffic signal maintenance', description: 'Traffic lights being repaired.', status: 'in-progress', priority: 'medium', category: 'Roads & Transportation', location: 'Main Street', ward: 'Ward 1', reportedBy: 'Rahul Patil', reportedAt: new Date('2024-02-06'), imageUrl: 'https://www.shutterstock.com/image-photo/man-uniform-on-aerial-platform-260nw-2153500591.jpg', daysRemaining: 4, isOverdue: false, upvotes: 7, comments: 2 },
  { id: '12', title: 'Bridge safety check ongoing', description: 'Bridge structural inspection in progress.', status: 'in-progress', priority: 'high', category: 'Infrastructure', location: 'River Bridge', ward: 'Ward 7', reportedBy: 'Sunita Devi', reportedAt: new Date('2024-02-04'), imageUrl: 'https://img.roadsbridges.com/files/base/ebm/roadsbridges/image/2022/06/1654617960892-nit_20200923_174852246_ios.png?auto=format,compress&fit=fill&fill=blur&q=45&w=640&width=640', daysRemaining: 2, isOverdue: false, upvotes: 5, comments: 1 },

  { id: '13', title: 'Sewage blockage cleared', description: 'Sewage blockage near Ward 5 cleared by sanitation team.', status: 'resolved', priority: 'medium', category: 'Sanitation', location: 'Ward 5', ward: 'Ward 5', reportedBy: 'Amit Sharma', reportedAt: new Date('2024-01-28'), imageUrl: 'https://cdn.prod.website-files.com/62cd333e227dcd4826dc0859/62f64185750575fe1a1542fb_Engineer%20cleaning%20outdoor%20%20(1).jpg', daysRemaining: 0, isOverdue: false, upvotes: 15, comments: 3 },
  { id: '14', title: 'Water supply restored', description: 'Water supply restored in Sector 2 after pipe repair.', status: 'resolved', priority: 'low', category: 'Sanitation', location: 'Sector 2', ward: 'Ward 2', reportedBy: 'Priya Singh', reportedAt: new Date('2024-01-30'), imageUrl: 'https://constructionreviewonline.com/wp-content/uploads/2018/07/water-project.jpg', daysRemaining: 0, isOverdue: false, upvotes: 8, comments: 1 },
  { id: '15', title: 'Street lights fixed', description: 'All street lights in Ward 3 restored.', status: 'resolved', priority: 'medium', category: 'Electrical', location: 'Ward 3', ward: 'Ward 3', reportedBy: 'Sunil Kumar', reportedAt: new Date('2024-01-25'), imageUrl: '/images/streetlight-issue.jpg', daysRemaining: 0, isOverdue: false, upvotes: 10, comments: 2 },
  { id: '16', title: 'Road potholes repaired', description: 'Main road potholes repaired successfully.', status: 'resolved', priority: 'high', category: 'Roads & Transportation', location: 'Central Market', ward: 'Ward 1', reportedBy: 'Meena Sharma', reportedAt: new Date('2024-01-27'), imageUrl: 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTX4MbUs__L56LvB6vq7KzdxkysMhPcj_M12w&s', daysRemaining: 0, isOverdue: false, upvotes: 12, comments: 3 },
  { id: '17', title: 'Park cleaned', description: 'Public park in Sector 6 cleaned.', status: 'resolved', priority: 'low', category: 'Sanitation', location: 'Sector 6', ward: 'Ward 6', reportedBy: 'Deepak Gupta', reportedAt: new Date('2024-01-29'), imageUrl: 'https://qns.com/wp-content/uploads/2022/06/52138679498_edbe89e44b_4k-scaled.jpg?quality=51&w=1200', daysRemaining: 0, isOverdue: false, upvotes: 5, comments: 1 },
  { id: '18', title: 'Bridge inspection completed', description: 'Bridge structural inspection completed successfully.', status: 'resolved', priority: 'medium', category: 'Infrastructure', location: 'River Bridge', ward: 'Ward 7', reportedBy: 'Sunita Devi', reportedAt: new Date('2024-01-26'), imageUrl: 'https://www.flyability.com/hs-fs/hubfs/bridge-inspections-flyability-6.jpg?width=720&height=448&name=bridge-inspections-flyability-6.jpg', daysRemaining: 0, isOverdue: false, upvotes: 6, comments: 2 },
];

const IssuesPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [wardFilter, setWardFilter] = useState('all');
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'incoming' | 'ongoing' | 'resolved'>('all');
  const { toast } = useToast();

  const clearFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setPriorityFilter('all');
    setCategoryFilter('all');
    setWardFilter('all');
  };

  const filteredIssues = mockIssues.filter(issue => {
    const matchesSearch =
      issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.location.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === 'all' || issue.status === statusFilter;
    const matchesPriority = priorityFilter === 'all' || issue.priority === priorityFilter;
    const matchesCategory = categoryFilter === 'all' || issue.category === categoryFilter;
    const matchesWard = wardFilter === 'all' || issue.ward === wardFilter;

    const matchesTab =
      activeTab === 'all'
        ? true
        : activeTab === 'incoming'
        ? issue.status === 'submitted'
        : activeTab === 'ongoing'
        ? issue.status === 'in-progress'
        : activeTab === 'resolved'
        ? issue.status === 'resolved'
        : true;

    return matchesSearch && matchesStatus && matchesPriority && matchesCategory && matchesWard && matchesTab;
  });

  const handleMajorUpvote = (issueId: string) => {
    toast({
      title: 'Major Upvote Applied',
      description: 'Issue has been escalated with high priority. Admin has been notified.',
    });
  };

  const handleFlag = (issueId: string) => {
    toast({
      title: 'Issue Flagged',
      description: 'Issue has been flagged as spam/fake. Notification sent.',
      variant: 'destructive',
    });
  };

  const activeFiltersCount = [statusFilter, priorityFilter, wardFilter].filter(f => f !== 'all').length;

  return (
    <div className="min-h-screen bg-background">
      {/* Top Heading Bar */}
      <div className="bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] p-6 text-white">
        <h1 className="text-2xl font-bold mb-2">Issue Management</h1>
        <h3 className="text-white/100">Roads and Transportation Department</h3>
        <p className="text-white/60">Monitor and manage civic issues in your jurisdiction</p>
      </div>

      {/* Top Navigation Bar (left-aligned tabs) */}
      <div className="bg-white border-b">
        <nav className="max-w-7xl px-4">
          <div className="flex items-center space-x-4 py-3">
            <button
              onClick={() => setActiveTab('all')}
              className={`text-sm font-medium px-3 py-2 rounded ${activeTab === 'all' ? 'text-primary border-b-2 border-primary' : 'text-muted-foreground hover:bg-gray-50'}`}
            >
              All
            </button>
            <button
              onClick={() => setActiveTab('incoming')}
              className={`text-sm font-medium px-3 py-2 rounded ${activeTab === 'incoming' ? 'text-primary border-b-2 border-primary' : 'text-muted-foreground hover:bg-gray-50'}`}
            >
              Incoming
            </button>
            <button
              onClick={() => setActiveTab('ongoing')}
              className={`text-sm font-medium px-3 py-2 rounded ${activeTab === 'ongoing' ? 'text-primary border-b-2 border-primary' : 'text-muted-foreground hover:bg-gray-50'}`}
            >
              Ongoing
            </button>
            <button
              onClick={() => setActiveTab('resolved')}
              className={`text-sm font-medium px-3 py-2 rounded ${activeTab === 'resolved' ? 'text-primary border-b-2 border-primary' : 'text-muted-foreground hover:bg-gray-50'}`}
            >
              Resolved
            </button>
          </div>
        </nav>
      </div>

      {/* Page Content */}
      <div className="p-4 space-y-4">
        <Card className="civic-card">
          <CardContent className="p-4">
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
              <Input
                placeholder="Search issues by title, description, or location..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v)}>
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
                  <SelectItem value="ignored">Ignored</SelectItem>
                </SelectContent>
              </Select>

              <Select value={priorityFilter} onValueChange={(v) => setPriorityFilter(v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Priority" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Priority</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>

              <Select value={wardFilter} onValueChange={(v) => setWardFilter(v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Ward" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Wards</SelectItem>
                    <SelectItem value="Ward 1">Ward 1</SelectItem>
                    <SelectItem value="Ward 2">Ward 2</SelectItem>
                    <SelectItem value="Ward 3">Ward 3</SelectItem>
                    <SelectItem value="Ward 4">Ward 4</SelectItem>
                    <SelectItem value="Ward 5">Ward 5</SelectItem>
                    <SelectItem value="Ward 6">Ward 6</SelectItem>
                    <SelectItem value="Ward 7">Ward 7</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {activeFiltersCount > 0 && (
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Filter className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {activeFiltersCount} filter{activeFiltersCount !== 1 ? 's' : ''} active
                  </span>
                </div>
                <Button variant="ghost" size="sm" onClick={clearFilters} className="text-primary hover:text-primary/80">
                  <X className="w-4 h-4 mr-1" />
                  Clear All
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {filteredIssues.length} Issue{filteredIssues.length !== 1 ? 's' : ''} Found
          </h2>
          <Badge variant="secondary">
            {filteredIssues.filter(i => i.status === 'urgent' || i.isOverdue).length} Need Attention
          </Badge>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.28 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          >
            {filteredIssues.map(issue => (
              <IssueCard
                key={issue.id}
                issue={issue}
                onClick={() => setSelectedIssue(issue)}
                showActions={true}
                onMajorUpvote={() => {
                  handleMajorUpvote(issue.id);
                  setSelectedIssue(null);
                }}
                onFlag={() => {
                  handleFlag(issue.id);
                  setSelectedIssue(null);
                }}
              />
            ))}
          </motion.div>
        </AnimatePresence>

        {filteredIssues.length === 0 && (
          <Card className="civic-card">
            <CardContent className="p-8 text-center">
              <MapPin className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No Issues Found</h3>
              <p className="text-muted-foreground">
                Try adjusting your search criteria or filters to find relevant issues.
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {selectedIssue && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-2xl overflow-hidden">
            <div className="p-6 border-b border-border">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Issue Details</h2>
                <Button variant="ghost" size="sm" onClick={() => setSelectedIssue(null)}>✕</Button>
              </div>
            </div>

            <div className="p-6 max-h-96 overflow-y-auto space-y-6">
              {selectedIssue.imageUrl && (
                <div className="aspect-video overflow-hidden rounded-lg">
                  <img src={selectedIssue.imageUrl} alt={selectedIssue.title} className="w-full h-full object-cover" />
                </div>
              )}

              <div>
                <h3 className="text-xl font-semibold mb-2">{selectedIssue.title}</h3>
                <p className="text-muted-foreground mb-4">{selectedIssue.description}</p>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Status:</span>
                    <div className="mt-1"><StatusBadge status={selectedIssue.status} /></div>
                  </div>
                  <div>
                    <span className="font-medium">Priority:</span>
                    <div className="mt-1">
                      <Badge className={
                        selectedIssue.priority === 'critical' ? 'bg-red-100 text-red-800' :
                        selectedIssue.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                        selectedIssue.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-green-100 text-green-800'
                      }>
                        {selectedIssue.priority?.toUpperCase?.() ?? selectedIssue.priority}
                      </Badge>
                    </div>
                  </div>
                  <div>
                    <span className="font-medium">Category:</span>
                    <div className="mt-1 text-muted-foreground">{selectedIssue.category}</div>
                  </div>
                  <div>
                    <span className="font-medium">Location:</span>
                    <div className="mt-1 text-muted-foreground">{selectedIssue.location}</div>
                  </div>
                  <div>
                    <span className="font-medium">Reported By:</span>
                    <div className="mt-1 text-muted-foreground">{selectedIssue.reportedBy}</div>
                  </div>
                  <div>
                    <span className="font-medium">Date:</span>
                    <div className="mt-1 text-muted-foreground">{selectedIssue.reportedAt.toLocaleDateString()}</div>
                  </div>
                </div>
              </div>

              <div className="flex space-x-3 pt-4 border-t border-border">
                <Button
                  className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
                  onClick={() => {
                    handleMajorUpvote(selectedIssue.id);
                    setSelectedIssue(null);
                  }}
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Major Upvote
                </Button>
                <Button
                  variant="destructive"
                  className="flex-1"
                  onClick={() => {
                    handleFlag(selectedIssue.id);
                    setSelectedIssue(null);
                  }}
                >
                  <Flag className="w-4 h-4 mr-2" />
                  Flag Issue
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IssuesPage;