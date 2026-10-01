import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import 'leaflet/dist/leaflet.css';

import AdminLayout from "./components/AdminLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./components/LoginPage";

// A01 – Login is above
// A02 – Operations Dashboard
import Dashboard from "./pages/Dashboard";
// A03 – Case Management Workbench
import CaseManagement from "./components/IssueManagementPage";
// A04 – Case Detail / Evidence
import CaseDetailPage from "./pages/CaseDetailPage";
// A05 – AI Triage Panel
import AITriagePage from "./pages/AITriagePage";
// A06 – Department Coordination
import DepartmentCoordinationPage from "./components/DepartmentCoordinationPage";
// A07 – Department Performance
import DepartmentPerformancePage from "./pages/DepartmentPerformancePage";
// A08 – City Map
import CityMapPage from "./pages/CityMapPage";
// A09 – Ward Heatmap
import WardHeatmapPage from "./pages/WardHeatmapPage";
// A10 – Analytics
import AnalyticsPage from "./pages/AnalyticsPage";
// A11 – Special Boards / Incident Mode
import SpecialBoardsPage from "./components/SpecialBoardsPage";
// A12 – User Management
import UserManagementPage from "./components/UserManagementPage";
// A13 – System Settings
import SystemSettingsPage from "./components/SystemSettingsPage";

import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error: unknown) => {
        const err = error as { status?: number };
        if (err?.status === 401 || err?.status === 403) return false;
        return failureCount < 2;
      },
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          {/* A01 – Login */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected admin shell */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            {/* A02 */}
            <Route path="dashboard" element={<Dashboard />} />
            {/* A03 */}
            <Route path="cases" element={<CaseManagement />} />
            {/* A04 */}
            <Route path="cases/:caseId" element={<CaseDetailPage />} />
            {/* A05 */}
            <Route path="cases/:caseId/triage" element={<AITriagePage />} />
            {/* A06 */}
            <Route path="departments" element={<DepartmentCoordinationPage />} />
            {/* A07 */}
            <Route path="departments/performance" element={<DepartmentPerformancePage />} />
            {/* A08 */}
            <Route path="map" element={<CityMapPage />} />
            {/* A09 */}
            <Route path="ward-heatmap" element={<WardHeatmapPage />} />
            {/* A10 */}
            <Route path="analytics" element={<AnalyticsPage />} />
            {/* A11 */}
            <Route path="incidents" element={<SpecialBoardsPage userRole="admin" />} />
            {/* A12 */}
            <Route path="users" element={<UserManagementPage />} />
            {/* A13 */}
            <Route path="settings" element={<SystemSettingsPage />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
