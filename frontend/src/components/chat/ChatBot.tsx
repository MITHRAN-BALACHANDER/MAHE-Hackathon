"use client";

import { ArrowLeft, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
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
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    setMessages([
      {
        role: "bot",
        text: "Hi! I'll help you find the best route. Let me ask a few questions.",
      },
      { role: "bot", text: steps[0].question },
    ]);
  }, [steps]);

  const advanceStep = useCallback(
    (answer: string) => {
      const currentStep = steps[stepIndex];
      const newAnswers = { ...answers, [currentStep.id]: answer };
      setAnswers(newAnswers);

      setMessages((prev) => [...prev, { role: "user", text: answer }]);

      const nextIndex = stepIndex + 1;

      if (nextIndex >= steps.length - 1) {
        const result = answersToParams(newAnswers as ChatAnswers);
        setMessages((prev) => [
          ...prev,
          { role: "bot", text: result.summary },
          {
            role: "bot",
            text: `Click "Analyze & Find Route" to see your suggested route.`,
          },
        ]);
        setStepIndex(nextIndex);
      } else {
        setMessages((prev) => [...prev, { role: "bot", text: steps[nextIndex].question }]);
        setStepIndex(nextIndex);
      }
    },
    [stepIndex, answers, steps],
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
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 shrink-0">
        <button
          type="button"
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full cursor-pointer"
        >
          <ArrowLeft size={18} className="text-gray-600" />
        </button>
        <h3 className="text-sm font-semibold text-gray-800">Route Assistant</h3>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm ${
                msg.role === "user"
                  ? "bg-blue-500 text-white rounded-br-md"
                  : "bg-gray-100 text-gray-800 rounded-bl-md"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
      </div>

      {/* Options / Input */}
      <div className="px-4 py-3 border-t border-gray-100 shrink-0">
        {isComplete ? (
          <button
            type="button"
            onClick={() => {
              if (result) onApply(result.source, result.destination, result.preference, result.telecom);
            }}
            className="w-full py-2.5 bg-blue-500 hover:bg-blue-600 text-white text-sm font-semibold rounded-xl cursor-pointer transition-colors"
          >
            Analyze & Find Route
          </button>
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
                    className="px-3 py-1.5 text-xs bg-gray-100 hover:bg-blue-50 hover:text-blue-600 text-gray-700 rounded-full cursor-pointer transition-colors"
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
                className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-gray-50 px-3 py-2 rounded-xl"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={!inputValue.trim()}
                className="p-2 text-blue-500 hover:bg-blue-50 rounded-full cursor-pointer disabled:opacity-30 disabled:cursor-default transition-colors"
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
