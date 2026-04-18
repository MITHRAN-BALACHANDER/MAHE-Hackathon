"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register } from "@/src/services/auth";
import { useAuth } from "@/src/hooks/useAuth";
import Link from "next/link";
import { Eye, EyeOff, Lock, Mail, Signal, User, TowerControl, Shield, Zap } from "lucide-react";

const FEATURES = [
  {
    icon: Signal,
    title: "Signal-Aware Routing",
    desc: "Score routes by predicted cellular signal, not just ETA.",
  },
  {
    icon: TowerControl,
    title: "Real Tower Data",
    desc: "847+ cell towers from OpenCelliD across 20 Bangalore zones.",
  },
  {
    icon: Shield,
    title: "Dead Zone Alerts",
    desc: "Get warned before entering weak signal areas.",
  },
  {
    icon: Zap,
    title: "AI Personalization",
    desc: "Thompson Sampling RL learns your preferences in 3-5 trips.",
  },
];

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { setToken } = useAuth();

  const passwordStrength = (() => {
    if (password.length === 0) return { level: 0, label: "", color: "" };
    if (password.length < 6) return { level: 1, label: "Weak", color: "bg-red-400" };
    if (password.length < 10) return { level: 2, label: "Medium", color: "bg-yellow-400" };
    const hasUpper = /[A-Z]/.test(password);
    const hasDigit = /[0-9]/.test(password);
    const hasSpecial = /[^A-Za-z0-9]/.test(password);
    if (hasUpper && hasDigit && hasSpecial) return { level: 4, label: "Strong", color: "bg-green-500" };
    if ((hasUpper && hasDigit) || (hasUpper && hasSpecial) || (hasDigit && hasSpecial))
      return { level: 3, label: "Good", color: "bg-blue-400" };
    return { level: 2, label: "Medium", color: "bg-yellow-400" };
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const data = await register(username, password, email);
      setToken(data.access_token || data.token);
      // Mark as first visit so onboarding tour triggers
      localStorage.setItem("signalroute_first_visit", "true");
      router.push("/");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to register";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left Panel - Product Showcase */}
      <div className="hidden lg:flex lg:w-[55%] auth-gradient-bg relative overflow-hidden flex-col justify-center items-center px-16">
        <div className="absolute top-20 left-16 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-32 right-20 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: "2s" }} />
        <div className="absolute top-1/2 left-1/3 w-48 h-48 bg-purple-500/10 rounded-full blur-2xl animate-float" style={{ animationDelay: "4s" }} />

        <div className="relative z-10 max-w-lg">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-400 to-cyan-400 flex items-center justify-center animate-pulse-glow">
              <Signal className="text-white" size={24} />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight" style={{ fontFamily: "var(--font-sora)" }}>
                SignalRoute
              </h1>
              <p className="text-blue-200 text-sm">Cellular Network-Aware Routing</p>
            </div>
          </div>

          <h2 className="text-2xl font-semibold text-white/90 mb-3 leading-snug">
            Join the future of
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-300">
              connected navigation.
            </span>
          </h2>

          <p className="text-blue-200/80 text-sm mb-10 leading-relaxed">
            Create your account and let our AI learn your connectivity preferences.
            After 3 trips, SignalRoute knows exactly how to route you.
          </p>

          <div className="grid grid-cols-2 gap-4">
            {FEATURES.map((feat, i) => (
              <div key={feat.title} className="stat-card animate-slide-up" style={{ animationDelay: `${i * 0.1}s` }}>
                <feat.icon className="text-cyan-400 mb-2" size={20} />
                <h3 className="text-white text-sm font-semibold mb-1">{feat.title}</h3>
                <p className="text-blue-200/60 text-xs leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Panel - Register Form */}
      <div className="flex-1 flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50/30 px-6">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Signal className="text-white" size={20} />
            </div>
            <span className="text-2xl font-bold text-gray-900" style={{ fontFamily: "var(--font-sora)" }}>SignalRoute</span>
          </div>

          <div className="glass-card rounded-3xl p-8 sm:p-10">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-gray-900" style={{ fontFamily: "var(--font-sora)" }}>
                Create account
              </h2>
              <p className="text-sm text-gray-500 mt-1">Start your 30-day free trial. Cancel anytime.</p>
            </div>

            {/* Tabs */}
            <div className="flex bg-gray-100 rounded-xl p-1 mb-8">
              <Link
                href="/login"
                className="flex-1 text-center py-2.5 text-sm font-medium text-gray-500 hover:text-gray-700 rounded-lg transition-colors"
              >
                Sign In
              </Link>
              <div className="flex-1 text-center py-2.5 text-sm font-semibold bg-white rounded-lg text-gray-900 shadow-sm cursor-default">
                Sign Up
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-xl px-4 py-3 animate-slide-up">
                  {error}
                </div>
              )}

              {/* Full Name */}
              <div>
                <label htmlFor="reg-username" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Full Name
                </label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="reg-username"
                    type="text"
                    required
                    className="glass-input w-full rounded-xl pl-12 pr-4 py-3 text-sm text-gray-900 placeholder-gray-400 outline-none"
                    placeholder="Enter your full name"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label htmlFor="reg-email" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="reg-email"
                    type="email"
                    required
                    className="glass-input w-full rounded-xl pl-12 pr-4 py-3 text-sm text-gray-900 placeholder-gray-400 outline-none"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label htmlFor="reg-password" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="reg-password"
                    type={showPassword ? "text" : "password"}
                    required
                    className="glass-input w-full rounded-xl pl-12 pr-12 py-3 text-sm text-gray-900 placeholder-gray-400 outline-none"
                    placeholder="Must be at least 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {/* Password strength bar */}
                {password.length > 0 && (
                  <div className="mt-2">
                    <div className="flex gap-1 mb-1">
                      {[1, 2, 3, 4].map((i) => (
                        <div
                          key={i}
                          className={`h-1 flex-1 rounded-full transition-colors ${
                            i <= passwordStrength.level ? passwordStrength.color : "bg-gray-200"
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-xs text-gray-400">{passwordStrength.label}</p>
                  </div>
                )}
              </div>

              {/* Terms */}
              <p className="text-xs text-gray-400">
                By proceeding, you agree to the{" "}
                <span className="text-blue-500 hover:underline cursor-pointer">Terms and Conditions</span>
              </p>

              {/* Submit */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white text-sm font-semibold rounded-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Creating account...
                  </span>
                ) : (
                  "Create Account"
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-4 my-6">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-gray-400">or</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>

            {/* Google */}
            <button
              type="button"
              className="w-full py-3 bg-white border border-gray-200 text-sm font-medium text-gray-700 rounded-xl hover:bg-gray-50 transition-colors flex items-center justify-center gap-3 cursor-pointer"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              Sign Up with Google
            </button>

            <p className="text-center text-xs text-gray-400 mt-6">
              © 2026 SignalRoute AI. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
