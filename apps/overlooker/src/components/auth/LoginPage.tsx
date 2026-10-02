import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue, SelectLabel } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Eye, EyeOff, MapPin, Shield, Sparkles, Lock, User } from 'lucide-react';
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
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
         style={{ background: 'linear-gradient(145deg, #051a08 0%, #0d4a1a 30%, #1a6b2e 60%, #2a8a42 100%)' }}>
      
      {/* Animated background orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-16 left-16 w-80 h-80 rounded-full animate-float"
             style={{ background: 'radial-gradient(circle, rgba(39,169,74,0.1) 0%, transparent 70%)' }} />
        <div className="absolute bottom-16 right-16 w-96 h-96 rounded-full animate-float"
             style={{ background: 'radial-gradient(circle, rgba(108,199,122,0.08) 0%, transparent 70%)', animationDelay: '2s', animationDuration: '8s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full animate-float"
             style={{ background: 'radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%)', animationDelay: '4s' }} />
        
        {/* Grid */}
        <div className="absolute inset-0 opacity-[0.03]"
             style={{
               backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                                 linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
               backgroundSize: '60px 60px',
             }} />
      </div>

      <div className="w-full max-w-md space-y-6 relative z-10">
        {/* Logo and Branding */}
        <div className="text-center text-white space-y-3 page-enter">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-full px-4 py-1.5 border border-white/10 mb-3">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-xs text-white/60 font-medium">Government Oversight Portal</span>
          </div>
          <div className="flex items-center justify-center space-x-3 mb-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center border border-white/15"
                 style={{ background: 'linear-gradient(145deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05))', backdropFilter: 'blur(10px)' }}>
              <img src="/images/CivicConnect_logo.jpg" alt="CivicConnect Logo" className="w-10 h-10 rounded-xl" />
            </div>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight" style={{ textShadow: '0 2px 10px rgba(0,0,0,0.2)' }}>CivicConnect</h1>
          <h2 className="text-lg font-semibold text-white/80">Overlooker Portal</h2>
          <p className="text-white/40 text-sm">Government of Jharkhand</p>
        </div>

        {/* Login Form */}
        <Card className="bg-white/95 backdrop-blur-xl border-0 rounded-3xl page-enter" style={{ animationDelay: '0.1s', boxShadow: '0 30px 80px rgba(0,0,0,0.3)' }}>
          <CardHeader className="text-left pb-2">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                   style={{ background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)' }}>
                <Lock className="w-4 h-4 text-white" />
              </div>
              <CardTitle className="text-xl font-bold text-gray-900">Sign In</CardTitle>
            </div>
            <CardDescription className="text-gray-500">
              Access your oversight dashboard
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="username" className="text-sm font-semibold text-gray-700">Username</Label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="username"
                    type="text"
                    placeholder="Enter your username"
                    value={formData.username}
                    onChange={(e) => setFormData({...formData, username: e.target.value})}
                    required
                    className="pl-10 h-11 rounded-xl border-gray-200 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-400 transition-all"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-sm font-semibold text-gray-700">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required
                    className="pl-10 pr-10 h-11 rounded-xl border-gray-200 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-400 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-emerald-600 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
 
              <div className="space-y-1.5">
                <Label htmlFor="department-jurisdiction" className="text-sm font-semibold text-gray-700">Department/Jurisdiction</Label>
                <Select onValueChange={(value) => setFormData({...formData, jurisdiction: value, department: value})} required>
                  <SelectTrigger className="h-11 rounded-xl border-gray-200 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all">
                    <SelectValue placeholder="Select department or jurisdiction" />
                  </SelectTrigger>
                  <SelectContent className="rounded-xl border-gray-200 shadow-lg">
                    <SelectGroup>
                      <SelectLabel className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Jurisdiction</SelectLabel>
                      <SelectItem value="ranchi" className="rounded-lg">Ranchi Municipal Corporation</SelectItem>
                      <SelectItem value="jamshedpur" className="rounded-lg">Jamshedpur Notified Area Committee</SelectItem>
                      <SelectItem value="dhanbad" className="rounded-lg">Dhanbad Municipal Corporation</SelectItem>
                      <SelectItem value="bokaro" className="rounded-lg">Bokaro Steel City</SelectItem>
                      <SelectItem value="deoghar" className="rounded-lg">Deoghar Municipality</SelectItem>
                    </SelectGroup>
                    <SelectGroup>
                      <SelectLabel className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Department (Optional)</SelectLabel>
                      <SelectItem value="all" className="rounded-lg">All Departments</SelectItem>
                      <SelectItem value="roads" className="rounded-lg">Roads & Transportation</SelectItem>
                      <SelectItem value="electrical" className="rounded-lg">Electrical Department</SelectItem>
                      <SelectItem value="sanitation" className="rounded-lg">Sanitation Department</SelectItem>
                      <SelectItem value="garbage" className="rounded-lg">Garbage Management</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="remember"
                  checked={rememberMe}
                  onCheckedChange={(checked) => setRememberMe(checked as boolean)}
                  className="border-gray-300 data-[state=checked]:bg-emerald-600 data-[state=checked]:border-emerald-600"
                />
                <Label htmlFor="remember" className="text-sm text-gray-500 font-normal cursor-pointer">
                  Remember me for 30 days
                </Label>
              </div>

              <Button 
                type="submit" 
                className="w-full h-12 rounded-xl text-white font-bold text-[15px] transition-all duration-300"
                style={{ 
                  background: 'linear-gradient(145deg, #0d4a1a, #1a7a2e)',
                  boxShadow: '0 4px 20px rgba(22, 163, 74, 0.3)',
                }}
                disabled={isLoading}
              >
                {isLoading ? "Signing in..." : "Sign In"}
              </Button>

              <div className="text-left">
                <button
                  type="button"
                  className="text-sm text-emerald-600 hover:text-emerald-700 font-medium transition-colors"
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
        <div className="text-center page-enter" style={{ animationDelay: '0.2s' }}>
          <p className="text-white/30 text-xs font-medium">CivicConnect v2.0 | Government of Jharkhand</p>
          <p className="flex items-center justify-center mt-1 text-white/20 text-xs">
            <Sparkles className="w-3 h-3 mr-1" />
            Powered by Digital India Initiative
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;