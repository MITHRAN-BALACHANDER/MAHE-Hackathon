"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register } from "@/src/services/auth";
import { useAuth } from "@/src/hooks/useAuth";
import Link from "next/link";
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  Signal,
  User,
  TowerControl,
  Shield,
  Zap,
  Compass,
  MapPin,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const FEATURES = [
  {
    icon: Compass,
    title: "Intelligent Routing",
    desc: "Experience navigation scored by true connectivity and time.",
  },
  {
    icon: TowerControl,
    title: "Precision Data",
    desc: "Powered by comprehensive cell tower analytics.",
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
    if (password.length < 6)
      return { level: 1, label: "Weak", color: "bg-[#c0392b]" };
    if (password.length < 10)
      return { level: 2, label: "Medium", color: "bg-[#d35400]" };
    const hasUpper = /[A-Z]/.test(password);
    const hasDigit = /[0-9]/.test(password);
    const hasSpecial = /[^A-Za-z0-9]/.test(password);
    if (hasUpper && hasDigit && hasSpecial)
      return { level: 4, label: "Strong", color: "bg-[#27ae60]" };
    if (
      (hasUpper && hasDigit) ||
      (hasUpper && hasSpecial) ||
      (hasDigit && hasSpecial)
    )
      return { level: 3, label: "Good", color: "bg-[#2980b9]" };
    return { level: 2, label: "Medium", color: "bg-[#d35400]" };
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const data = await register(username, password, email);
      setToken(data.access_token || data.token);
      localStorage.setItem("signalroute_first_visit", "true");
      router.push("/");
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to sign up. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: "easeOut" as const },
    },
  };

  return (
    <div className="flex justify-center min-h-screen bg-[#f4f1ea] selection:bg-[#2c3e50] selection:text-[#f4f1ea] font-sans">
      {/* Left Panel - Classic Aesthetic */}
      <motion.div
        initial={{ opacity: 0, x: -50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 1, ease: "easeOut" }}
        className="hidden lg:flex lg:w-[50%] relative overflow-hidden flex-col justify-center items-center px-16 bg-[#1a2530]"
      >
        <div className="absolute inset-0 opacity-[0.03] bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-white via-transparent to-transparent pointer-events-none" />
        <div className="absolute top-0 left-0 w-full h-full bg-[url('https://www.transparenttextures.com/patterns/stardust.png')] opacity-20 pointer-events-none" />

        <motion.div
          initial="hidden"
          animate="visible"
          variants={containerVariants}
          className="relative z-10 max-w-lg text-[#f4f1ea]"
        >
          <motion.div
            variants={itemVariants}
            className="flex items-center gap-4 mb-6"
          >
            <div className="w-14 h-14 rounded-full border border-[#d4af37]/30 flex items-center justify-center bg-[#2c3e50] shadow-[0_0_15px_rgba(212,175,55,0.1)]">
              <MapPin className="text-[#d4af37]" strokeWidth={1.5} size={28} />
            </div>
            <div>
              <h1 className="text-4xl font-serif tracking-wide">SignalRoute</h1>
              <p className="text-[#aeb6bf] text-sm uppercase tracking-widest mt-1 font-medium">
                Modern Cartography
              </p>
            </div>
          </motion.div>

          <motion.h2
            variants={itemVariants}
            className="text-3xl font-serif text-white/95 mb-4 leading-tight"
          >
            Embark on a new era of
            <br />
            <span className="text-[#d4af37] italic">connected travel.</span>
          </motion.h2>

          <motion.p
            variants={itemVariants}
            className="text-[#aeb6bf] text-base mb-8 leading-relaxed max-w-md font-light"
          >
            Create your account to teach our systems your distinct connectivity
            contours. Within journeys, we align the map to your needs.
          </motion.p>

          <motion.div
            variants={containerVariants}
            className="grid grid-cols-2 gap-x-8 gap-y-8"
          >
            {FEATURES.map((feat, i) => (
              <motion.div
                key={feat.title}
                variants={itemVariants}
                className="group cursor-default"
              >
                <feat.icon
                  className="text-[#d4af37] mb-3 opacity-80 group-hover:opacity-100 transition-opacity duration-500"
                  strokeWidth={1.5}
                  size={24}
                />
                <h3 className="text-[#f4f1ea] text-sm uppercase tracking-wider font-semibold mb-2">
                  {feat.title}
                </h3>
                <p className="text-[#8e98a3] text-xs leading-relaxed font-light">
                  {feat.desc}
                </p>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </motion.div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-4 relative py-6">
        <div className="absolute inset-0 bg-[#f4f1ea] opacity-50 pointer-events-none" />

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md relative z-10"
        >
          {/* Mobile Header */}
          <div className="lg:hidden flex flex-col items-center gap-3 mb-6 justify-center">
            <div className="w-12 h-12 rounded-full border border-[#d4af37]/40 flex items-center justify-center bg-[#1a2530]">
              <MapPin className="text-[#d4af37]" strokeWidth={1.5} size={24} />
            </div>
            <span className="text-3xl font-serif text-[#1a2530]">
              SignalRoute
            </span>
          </div>

          <div className="bg-white/80 backdrop-blur-xl border border-[#e5e0d8] shadow-2xl shadow-[#1a2530]/5 rounded-2xl p-6 sm:p-8">
            <div className="text-center mb-6">
              <h2 className="text-3xl font-serif text-[#1a2530] tracking-tight">
                Create Account
              </h2>
              <p className="text-sm text-[#7f8c8d] mt-2 font-light">
                Begin your seamless journey today.
              </p>
            </div>

            {/* Elegant Tabs */}
            <div className="flex mb-6 border-b border-[#e5e0d8]">
              <Link
                href="/login"
                className="flex-1 text-center pb-3 text-sm font-medium text-[#95a5a6] hover:text-[#1a2530] transition-colors"
              >
                Sign In
              </Link>
              <div className="flex-1 text-center pb-3 text-sm font-semibold text-[#1a2530] border-b-2 border-[#1a2530] cursor-default">
                Create Account
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="bg-[#c0392b]/10 border border-[#c0392b]/20 text-[#c0392b] text-sm rounded-lg px-4 py-3"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Username */}
              <div className="space-y-1">
                <label
                  htmlFor="reg-username"
                  className="block text-xs uppercase tracking-wider font-semibold text-[#34495e]"
                >
                  Full Name
                </label>
                <div className="relative group">
                  <User
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-[#bdc3c7] transition-colors group-focus-within:text-[#1a2530]"
                    size={18}
                    strokeWidth={1.5}
                  />
                  <input
                    id="reg-username"
                    type="text"
                    required
                    className="w-full bg-transparent border-b border-[#bdc3c7] pl-12 pr-4 py-3 text-sm text-[#2c3e50] placeholder-[#bdc3c7] outline-none focus:border-[#1a2530] transition-colors"
                    placeholder="Your name"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
              </div>

              {/* Email */}
              <div className="space-y-1">
                <label
                  htmlFor="reg-email"
                  className="block text-xs uppercase tracking-wider font-semibold text-[#34495e]"
                >
                  Email
                </label>
                <div className="relative group">
                  <Mail
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-[#bdc3c7] transition-colors group-focus-within:text-[#1a2530]"
                    size={18}
                    strokeWidth={1.5}
                  />
                  <input
                    id="reg-email"
                    type="email"
                    required
                    className="w-full bg-transparent border-b border-[#bdc3c7] pl-12 pr-4 py-3 text-sm text-[#2c3e50] placeholder-[#bdc3c7] outline-none focus:border-[#1a2530] transition-colors"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1">
                <label
                  htmlFor="reg-password"
                  className="block text-xs uppercase tracking-wider font-semibold text-[#34495e]"
                >
                  Password
                </label>
                <div className="relative group">
                  <Lock
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-[#bdc3c7] transition-colors group-focus-within:text-[#1a2530]"
                    size={18}
                    strokeWidth={1.5}
                  />
                  <input
                    id="reg-password"
                    type={showPassword ? "text" : "password"}
                    required
                    className="w-full bg-transparent border-b border-[#bdc3c7] pl-12 pr-12 py-3 text-sm text-[#2c3e50] placeholder-[#bdc3c7] outline-none focus:border-[#1a2530] transition-colors"
                    placeholder="Minimum 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-0 top-1/2 -translate-y-1/2 text-[#bdc3c7] hover:text-[#1a2530] p-3 transition-colors cursor-pointer"
                  >
                    {showPassword ? (
                      <EyeOff size={18} strokeWidth={1.5} />
                    ) : (
                      <Eye size={18} strokeWidth={1.5} />
                    )}
                  </button>
                </div>
                {/* Password strength bar */}
                {password.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-3"
                  >
                    <div className="flex gap-1.5 mb-1.5">
                      {[1, 2, 3, 4].map((i) => (
                        <div
                          key={i}
                          className={`h-1 flex-1 rounded-none transition-colors duration-300 ${
                            i <= passwordStrength.level
                              ? passwordStrength.color
                              : "bg-[#e5e0d8]"
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-[10px] uppercase tracking-widest text-[#95a5a6] font-semibold">
                      {passwordStrength.label}
                    </p>
                  </motion.div>
                )}
              </div>

              {/* Terms */}
              <p className="text-xs text-[#95a5a6] font-light mt-2">
                By participating, you assent to our{" "}
                <span className="text-[#34495e] hover:text-[#1a2530] border-b border-[#34495e] hover:border-[#1a2530] cursor-pointer transition-colors">
                  Terms of Service
                </span>
                .
              </p>

              {/* Submit */}
              <motion.button
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                type="submit"
                disabled={isLoading}
                className="w-full py-3 mt-4 bg-[#1a2530] hover:bg-[#2c3e50] text-[#f4f1ea] text-sm font-semibold uppercase tracking-wider rounded-none transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-3">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{
                        repeat: Infinity,
                        duration: 1,
                        ease: "linear",
                      }}
                      className="w-4 h-4 border-2 border-[#f4f1ea]/30 border-t-[#f4f1ea] rounded-full"
                    />
                    Registering
                  </span>
                ) : (
                  "Create Account"
                )}
              </motion.button>
            </form>

            <div className="flex items-center gap-4 my-5">
              <div className="flex-1 h-px bg-[#e5e0d8]" />
              <span className="text-xs uppercase tracking-widest text-[#95a5a6] font-medium">
                Or
              </span>
              <div className="flex-1 h-px bg-[#e5e0d8]" />
            </div>

            <button
              type="button"
              className="w-full py-3 bg-transparent border border-[#bdc3c7] text-sm font-semibold uppercase tracking-wider text-[#34495e] hover:bg-[#f4f1ea]/50 hover:border-[#1a2530] transition-all duration-300 flex items-center justify-center gap-3 cursor-pointer"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
              Continue with Google
            </button>

           
          </div>
        </motion.div>
      </div>
    </div>
  );
}
