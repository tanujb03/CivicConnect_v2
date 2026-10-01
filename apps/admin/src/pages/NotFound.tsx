import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Home, ArrowLeft } from 'lucide-react';

const NotFound: React.FC = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-civic-bg flex items-center justify-center">
      <div className="text-center max-w-sm">
        <p className="text-8xl font-black text-gray-200">404</p>
        <h1 className="text-2xl font-bold text-gray-800 mt-4">Page not found</h1>
        <p className="text-gray-500 mt-2 text-sm">The page you're looking for doesn't exist in the admin portal.</p>
        <div className="flex gap-3 justify-center mt-6">
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" /> Go back
          </Button>
          <Button className="bg-green-600 hover:bg-green-700 text-white" onClick={() => navigate('/dashboard')}>
            <Home className="h-4 w-4 mr-2" /> Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
