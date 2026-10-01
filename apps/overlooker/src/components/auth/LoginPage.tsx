import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue, SelectLabel } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Eye, EyeOff, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '@/hooks/use-toast';

const LoginPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    jurisdiction: '',
    department: ''
  });
  
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Simulate login process
    setTimeout(() => {
      if (formData.username && formData.password && formData.jurisdiction) {
        localStorage.setItem('civic_auth_token', 'demo-token-123');
        localStorage.setItem('civic_user_role', 'overlooker');
        localStorage.setItem('civic_user_name', formData.username);
        localStorage.setItem('civic_user_jurisdiction', formData.jurisdiction);
        
        if (rememberMe) {
          localStorage.setItem('civic_remember_user', 'true');
        }
        
        toast({
          title: "Login Successful",
          description: `Welcome back, ${formData.username}!`,
        });
        
        navigate('/');
      } else {
        toast({
          title: "Login Failed",
          description: "Please fill in all required fields.",
          variant: "destructive",
        });
      }
      setIsLoading(false);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#1A531A] to-[#7CAE0C] flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Logo and Branding - Kept centered as per the image */}
        <div className="text-center text-white space-y-2">
          <div className="flex items-center justify-center space-x-2 mb-4">
            <img src="/images/CivicConnect_logo.jpg" alt="CivicConnect Logo" className="w-16 h-16" />
            <h1 className="text-2xl font-bold">CivicConnect</h1>
          </div>
          <h2 className="text-xl font-semibold">Overlooker Portal</h2>
          <p className="text-white/80">Government of Jharkhand</p>
        </div>

        {/* Login Form */}
        <Card className="civic-card-elevated border-0 shadow-2xl">
          <CardHeader className="text-left">
            <CardTitle className="text-2xl text-primary">Sign In</CardTitle>
            <CardDescription>
              Access your oversight dashboard
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  type="text"
                  placeholder="Enter your username"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  required
                  className="border-card-border focus:border-primary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required
                    className="border-card-border focus:border-primary pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-primary"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
 
              <div className="space-y-2">
                <Label htmlFor="department-jurisdiction">Department/Jurisdiction</Label>
                <Select onValueChange={(value) => setFormData({...formData, jurisdiction: value, department: value})} required>
                  <SelectTrigger className="border-card-border focus:border-primary">
                    <SelectValue placeholder="Select a department or jurisdiction" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectLabel>Jurisdiction</SelectLabel>
                      <SelectItem value="ranchi">Ranchi Municipal Corporation</SelectItem>
                      <SelectItem value="jamshedpur">Jamshedpur Notified Area Committee</SelectItem>
                      <SelectItem value="dhanbad">Dhanbad Municipal Corporation</SelectItem>
                      <SelectItem value="bokaro">Bokaro Steel City</SelectItem>
                      <SelectItem value="deoghar">Deoghar Municipality</SelectItem>
                    </SelectGroup>
                    <SelectGroup>
                      <SelectLabel>Department (Optional)</SelectLabel>
                      <SelectItem value="all">All Departments</SelectItem>
                      <SelectItem value="roads">Roads & Transportation</SelectItem>
                      <SelectItem value="electrical">Electrical Department</SelectItem>
                      <SelectItem value="sanitation">Sanitation Department</SelectItem>
                      <SelectItem value="garbage">Garbage Management</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="remember"
                  checked={rememberMe}
                  onCheckedChange={(checked) => setRememberMe(checked as boolean)}
                />
                <Label htmlFor="remember" className="text-sm text-muted-foreground">
                  Remember me for 30 days
                </Label>
              </div>

              <Button 
                type="submit" 
                className="w-full civic-button-primary text-lg py-6"
                disabled={isLoading}
              >
                {isLoading ? "Signing in..." : "Sign In"}
              </Button>

              <div className="text-left">
                <button
                  type="button"
                  className="text-sm text-primary hover:underline"
                  onClick={() => toast({
                    title: "Password Reset",
                    description: "Please contact your system administrator for password reset.",
                  })}
                >
                  Forgot your password?
                </button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-white/60 text-xs">
          <p>CivicConnect v2.0 | Government of Jharkhand</p>
          <p className="flex items-center justify-center mt-1">
            <MapPin className="w-3 h-3 mr-1" />
            Powered by Digital India Initiative
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;