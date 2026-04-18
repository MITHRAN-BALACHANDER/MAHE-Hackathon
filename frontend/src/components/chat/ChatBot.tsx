"use client";

import { ArrowLeft, Bot, Send, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { TelecomMode } from "@/src/types/route";

type Step = {
  id: string;
  question: string;
  options: string[];
  inputPlaceholder?: string;
};

function buildSteps(detectedProvider: string): Step[] {
  const ispOptions =
    detectedProvider && detectedProvider !== "unknown"
      ? [`Continue with ${detectedProvider}`, "Jio", "Airtel", "Vi", "Other"]
      : ["Jio", "Airtel", "Vi", "Any network"];

  return [
    {
      id: "source",
      question: "Where are you starting from?",
      options: [],
      inputPlaceholder: "e.g. Electronic City, Koramangala...",
    },
    {
      id: "destination",
      question: "Where do you want to go?",
      options: [],
      inputPlaceholder: "e.g. Whitefield, MG Road...",
    },
    {
      id: "network_quality",
      question: "How important is network quality on your route?",
      options: ["Not important", "Somewhat important", "Very important"],
    },
    {
      id: "road_quality",
      question: "How important is road quality to you?",
      options: ["Any road is fine", "Prefer decent roads", "Only good roads"],
    },
    {
      id: "isp",
      question: `Which network provider would you like to use?${detectedProvider && detectedProvider !== "unknown" ? ` (Detected: ${detectedProvider})` : ""}`,
      options: ispOptions,
    },
    {
      id: "confirm",
      question: "",
      options: [],
    },
  ];
}

type Message = {
  role: "bot" | "user";
  text: string;
};

type ChatAnswers = {
  source: string;
  destination: string;
  network_quality: string;
  road_quality: string;
  isp: string;
};

function answersToParams(answers: ChatAnswers): {
  source: string;
  destination: string;
  preference: number;
  telecom: TelecomMode;
  summary: string;
} {
  let preference = 50;

  switch (answers.network_quality) {
    case "Not important":
      preference = 20;
      break;
    case "Somewhat important":
      preference = 50;
      break;
    case "Very important":
      preference = 85;
      break;
  }

  // Road quality nudges preference toward speed (lower = faster/better roads)
  switch (answers.road_quality) {
    case "Only good roads":
      preference = Math.max(preference - 15, 5);
      break;
    case "Any road is fine":
      preference = Math.min(preference + 10, 100);
      break;
  }

  let telecom: TelecomMode = "all";
  const ispLower = answers.isp.toLowerCase();
  if (ispLower.includes("jio")) telecom = "jio";
  else if (ispLower.includes("airtel")) telecom = "airtel";
  else if (ispLower.includes("vi")) telecom = "vi";

  const networkLabel =
    preference >= 70 ? "strong network priority" : preference <= 30 ? "speed priority" : "balanced";

  const summary = `Route from ${answers.source} to ${answers.destination} with ${networkLabel}${telecom !== "all" ? ` on ${telecom.charAt(0).toUpperCase() + telecom.slice(1)}` : ""}.`;

  return { source: answers.source, destination: answers.destination, preference, telecom, summary };
}

type Props = {
  onClose: () => void;
  onApply: (source: string, destination: string, preference: number, telecom: TelecomMode) => void;
  detectedNetwork: string;
};

export function ChatBot({ onClose, onApply, detectedNetwork }: Props) {
  const steps = useRef(buildSteps(detectedNetwork)).current;
  const [messages, setMessages] = useState<Message[]>([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Partial<ChatAnswers>>({});
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  useEffect(() => {
    setIsTyping(true);
    const t = setTimeout(() => {
      setMessages([
        {
          role: "bot",
          text: "Hi! I'll help you find the best route. Let me ask a few questions. 🚗",
        },
        { role: "bot", text: steps[0].question },
      ]);
      setIsTyping(false);
    }, 600);
    return () => clearTimeout(t);
  }, [steps]);

  const addBotMessage = useCallback((text: string) => {
    setIsTyping(true);
    setTimeout(() => {
      setMessages((prev) => [...prev, { role: "bot", text }]);
      setIsTyping(false);
    }, 400);
  }, []);

  const advanceStep = useCallback(
    (answer: string) => {
      const currentStep = steps[stepIndex];
      const newAnswers = { ...answers, [currentStep.id]: answer };
      setAnswers(newAnswers);

      setMessages((prev) => [...prev, { role: "user", text: answer }]);

      const nextIndex = stepIndex + 1;

      if (nextIndex >= steps.length - 1) {
        const result = answersToParams(newAnswers as ChatAnswers);
        addBotMessage(result.summary);
        setTimeout(() => {
          addBotMessage(`Click "Analyze & Find Route" to see your suggested route. ✨`);
        }, 800);
        setStepIndex(nextIndex);
      } else {
        addBotMessage(steps[nextIndex].question);
        setStepIndex(nextIndex);
      }
    },
    [stepIndex, answers, steps, addBotMessage],
  );

  const handleSend = useCallback(() => {
    const val = inputValue.trim();
    if (!val) return;
    setInputValue("");
    advanceStep(val);
  }, [inputValue, advanceStep]);

  const isComplete = stepIndex >= steps.length - 1;
  const currentStepData = steps[stepIndex];
  const result = isComplete ? answersToParams(answers as ChatAnswers) : null;

  return (
    <div className="flex flex-col h-full">
      {/* Header with gradient */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-blue-500 to-cyan-500 shrink-0">
        <button
          type="button"
          onClick={onClose}
          className="p-1 hover:bg-white/20 rounded-full cursor-pointer transition-colors"
        >
          <ArrowLeft size={18} className="text-white" />
        </button>
        <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
          <Bot size={16} className="text-white" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Route Assistant</h3>
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-green-300 animate-pulse" />
            <span className="text-[10px] text-white/70">Online</span>
          </div>
        </div>
      </div>

      {/* Messages with light grid background */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 light-grid-bg">
        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.25 }}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "bot" && (
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center mr-2 mt-1 shrink-0">
                  <Sparkles size={12} className="text-white" />
                </div>
              )}
              <div
                className={`max-w-[80%] px-3.5 py-2.5 text-sm ${
                  msg.role === "user"
                    ? "bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-2xl rounded-br-md shadow-md"
                    : "bg-white text-gray-800 rounded-2xl rounded-bl-md shadow-sm border border-gray-100"
                }`}
              >
                {msg.text}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        {isTyping && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2"
          >
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shrink-0">
              <Sparkles size={12} className="text-white" />
            </div>
            <div className="bg-white rounded-2xl rounded-bl-md px-4 py-3 shadow-sm border border-gray-100">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Options / Input */}
      <div className="px-4 py-3 bg-white border-t border-gray-100 shrink-0">
        {isComplete ? (
          <motion.button
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            type="button"
            onClick={() => {
              if (result) onApply(result.source, result.destination, result.preference, result.telecom);
            }}
            className="w-full py-3 bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white text-sm font-semibold rounded-xl cursor-pointer transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2"
          >
            <Sparkles size={16} />
            Analyze & Find Route
          </motion.button>
        ) : (
          <>
            {/* Quick-select options */}
            {currentStepData.options.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {currentStepData.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => advanceStep(opt)}
                    className="px-3 py-1.5 text-xs bg-gradient-to-r from-blue-50 to-cyan-50 hover:from-blue-100 hover:to-cyan-100 text-blue-700 rounded-full cursor-pointer transition-all border border-blue-100 hover:border-blue-200 hover:shadow-sm"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {/* Free text input */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSend();
                }}
                placeholder={currentStepData.inputPlaceholder ?? "Type your answer..."}
                className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-gray-50 px-4 py-2.5 rounded-xl border border-gray-100 focus:border-blue-300 focus:bg-white transition-all"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={!inputValue.trim()}
                className="p-2.5 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-xl cursor-pointer disabled:opacity-30 disabled:cursor-default transition-all hover:shadow-md"
              >
                <Send size={16} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
