"use client";

import React, { useState, useMemo, useCallback, useEffect, KeyboardEvent, useRef } from "react";
import "./live.css";
import negativeScenario from "@/data/negative.json";
import positiveScenario from "@/data/positive.json";
import {
  Broadcast,
  MagnifyingGlass,
  User,
  ArrowsClockwise,
  Spinner,
  PaperPlaneRight,
  TrendUp,
  TrendDown,
  Minus,
  WarningOctagon,
  Heartbeat,
  Scales,
  Play,
  Pause,
  ListNumbers,
  Flame,
  FastForward
} from "@phosphor-icons/react";

interface DetectedKeyword {
  keyword: string;
  sentiment: string;
}

interface ScoreDetails {
  emotion: string;
  confidence: number;
  emotion_weight: number;
  effective_emotion_weight?: number;
  previous_score: number;
  dampening_factor: number;
  dampened_raw_score: number;
  score: number;
  call_health_score?: number;
  sentiment_trend?: string;
  peak_negativity?: number;
  turn_count?: number;
  session_avg_score?: number;
  escalation_triggered: boolean;
}

interface ChatMessage {
  id: string;
  speaker: "caller";
  isolated_sentence: string;
  phrase: string;
  detected_keywords: DetectedKeyword[];
  emotion: string;
  sentiment_category: "positive" | "negative" | "neutral";
  confidence: number;
  emotion_weight: number;
  effective_emotion_weight: number;
  sentence_score: number;
  running_score: number;
}

interface ChartPoint {
  turnIndex: number;
  label: string;
  score: number;
  emotion: string;
  confidence: number;
  sentiment_category: "positive" | "negative" | "neutral";
  emotion_weight: number;
  effective_emotion_weight: number;
  speaker?: "caller";
  sentence?: string;
}

interface ScenarioChunk {
  turn: number;
  speaker: "caller";
  text: string;
  expectedMood: string;
}

export interface ScenarioDataset {
  id: string;
  name: string;
  filename: string;
  badgeColor: string;
  data: ScenarioChunk[];
}

export const SCENARIO_DATASETS: Record<string, ScenarioDataset> = {
  negative: {
    id: "negative",
    name: "Catastrophic Escalation Test",
    filename: "negative.json",
    badgeColor: "#dc2626",
    data: negativeScenario as ScenarioChunk[],
  },
  positive: {
    id: "positive",
    name: "High Resolution & Praise Test",
    filename: "positive.json",
    badgeColor: "#059669",
    data: positiveScenario as ScenarioChunk[],
  },
};

const EMOTION_WEIGHT_MAP: Record<string, number> = {
  gratitude: 100.0,
  relief: 95.0,
  approval: 85.0,
  optimism: 80.0,
  caring: 75.0,
  joy: 70.0,
  admiration: 65.0,
  excitement: 55.0,
  surprise: 0.0,
  amusement: 35.0,
  curiosity: -10.0,
  pride: 15.0,
  love: 10.0,
  desire: 5.0,
  anger: -100.0,
  disgust: -95.0,
  grief: -90.0,
  sadness: -85.0,
  disappointment: -80.0,
  disapproval: -75.0,
  annoyance: -70.0,
  fear: -65.0,
  remorse: -55.0,
  nervousness: -45.0,
  embarrassment: -35.0,
  confusion: -25.0,
  realization: -15.0,
  neutral: 0.0,
};

function getEmotionWeight(emotion: string): number {
  const clean = (emotion || "").trim().toLowerCase();
  return EMOTION_WEIGHT_MAP[clean] ?? 0.0;
}

// Interactive SVG Line Chart Component
function SentimentLineChart({ points }: { points: ChartPoint[] }) {
  const [hoveredPoint, setHoveredPoint] = useState<ChartPoint | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  const width = 680;
  const height = 300;
  const padLeft = 50;
  const padRight = 30;
  const padTop = 25;
  const padBottom = 35;

  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const getY = (score: number) => {
    const clamped = Math.max(-100, Math.min(100, score));
    return padTop + ((100 - clamped) / 200) * plotH;
  };

  const getX = (index: number, total: number) => {
    if (total <= 1) return padLeft + plotW / 2;
    return padLeft + (index / (total - 1)) * plotW;
  };

  const totalPoints = points.length;

  const pathCoords = useMemo(() => {
    return points.map((pt, i) => ({
      x: getX(i, totalPoints),
      y: getY(pt.score),
      pt
    }));
  }, [points, totalPoints]);

  const lineD = useMemo(() => {
    if (pathCoords.length === 0) return "";
    return pathCoords.reduce((acc, curr, idx) => {
      if (idx === 0) return `M ${curr.x} ${curr.y}`;
      const prev = pathCoords[idx - 1];
      const cx1 = prev.x + (curr.x - prev.x) / 2;
      const cy1 = prev.y;
      const cx2 = prev.x + (curr.x - prev.x) / 2;
      const cy2 = curr.y;
      return `${acc} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${curr.x} ${curr.y}`;
    }, "");
  }, [pathCoords]);

  const yZero = getY(0);
  const yEscalation = getY(-65);
  const yMinus80 = getY(-80);

  return (
    <div className="chart-wrapper">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart-svg"
        preserveAspectRatio="xMidYMid meet"
        onMouseLeave={() => {
          setHoveredPoint(null);
          setTooltipPos(null);
        }}
      >
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="40%" stopColor="#8b5cf6" />
            <stop offset="70%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#dc2626" />
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Positive & Negative Background zones */}
        <rect
          x={padLeft}
          y={padTop}
          width={plotW}
          height={yZero - padTop}
          fill="rgba(16, 185, 129, 0.03)"
        />
        <rect
          x={padLeft}
          y={yZero}
          width={plotW}
          height={padTop + plotH - yZero}
          fill="rgba(239, 68, 68, 0.04)"
        />

        {/* Extreme Negative Zone (-80 to -100) */}
        <rect
          x={padLeft}
          y={yMinus80}
          width={plotW}
          height={padTop + plotH - yMinus80}
          fill="rgba(185, 28, 28, 0.08)"
        />

        {/* Grid lines & Y-Axis labels */}
        {[-100, -80, -50, 0, 50, 100].map((val) => {
          const yPos = getY(val);
          const isZero = val === 0;
          const isExtreme = val === -80;
          return (
            <g key={val}>
              <line
                x1={padLeft}
                y1={yPos}
                x2={width - padRight}
                y2={yPos}
                stroke={isZero ? "#94a3b8" : isExtreme ? "#f87171" : "#e2e8f0"}
                strokeWidth={isZero ? 1.5 : isExtreme ? 1 : 1}
                strokeDasharray={isZero ? "none" : isExtreme ? "2 2" : "3 3"}
              />
              <text
                x={padLeft - 8}
                y={yPos + 4}
                textAnchor="end"
                fontSize="10"
                fontWeight={isZero || isExtreme ? "700" : "500"}
                fill={val > 0 ? "#10b981" : val <= -80 ? "#b91c1c" : val < 0 ? "#ef4444" : "#64748b"}
              >
                {val > 0 ? `+${val}` : val}
              </text>
            </g>
          );
        })}

        {/* Critical Escalation Line (-65) */}
        <line
          x1={padLeft}
          y1={yEscalation}
          x2={width - padRight}
          y2={yEscalation}
          stroke="#dc2626"
          strokeWidth="1.2"
          strokeDasharray="4 4"
        />
        <text
          x={width - padRight}
          y={yEscalation - 4}
          textAnchor="end"
          fontSize="9"
          fontWeight="700"
          fill="#dc2626"
        >
          Escalation Alert (-65)
        </text>

        {/* Severe Negative Line (-80) */}
        <text
          x={width - padRight}
          y={yMinus80 - 4}
          textAnchor="end"
          fontSize="9"
          fontWeight="700"
          fill="#991b1b"
        >
          Severe Friction (-80)
        </text>

        {/* Line Path */}
        {lineD && (
          <path
            d={lineD}
            fill="none"
            stroke="url(#lineGrad)"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* Data points & Interactive trigger targets */}
        {pathCoords.map((coord, idx) => {
          const isLatest = idx === pathCoords.length - 1;
          const pointColor =
            coord.pt.score > 0
              ? "#10b981"
              : coord.pt.score <= -80
              ? "#991b1b"
              : coord.pt.score < 0
              ? "#ef4444"
              : "#64748b";

          return (
            <g key={idx}>
              {isLatest && (
                <circle
                  cx={coord.x}
                  cy={coord.y}
                  r="9"
                  fill={pointColor}
                  opacity="0.3"
                  className="animate-ping"
                />
              )}
              <circle
                cx={coord.x}
                cy={coord.y}
                r={isLatest ? 5.5 : Math.max(3, 5 - Math.floor(totalPoints / 25))}
                fill="#ffffff"
                stroke={pointColor}
                strokeWidth={isLatest ? 3 : 2}
                filter="url(#glow)"
              />
              <circle
                cx={coord.x}
                cy={coord.y}
                r="16"
                fill="transparent"
                style={{ cursor: "pointer" }}
                onMouseEnter={() => {
                  setHoveredPoint(coord.pt);
                  setTooltipPos({ x: coord.x, y: coord.y });
                }}
              />
              {(totalPoints <= 15 || idx % Math.ceil(totalPoints / 10) === 0 || isLatest) && (
                <text
                  x={coord.x}
                  y={height - 10}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight={isLatest ? "700" : "500"}
                  fill={isLatest ? "#0f172a" : "#94a3b8"}
                >
                  {coord.pt.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Floating Interactive Tooltip */}
      {hoveredPoint && tooltipPos && (
        <div
          className="chart-tooltip"
          style={{
            left: `${(tooltipPos.x / width) * 100}%`,
            top: `${(tooltipPos.y / height) * 100}%`,
            transform:
              tooltipPos.x > width * 0.75
                ? "translate(-105%, -50%)"
                : tooltipPos.x < width * 0.25
                ? "translate(5%, -50%)"
                : "translate(-50%, -120%)",
          }}
        >
          <div className="tooltip-header">
            <span className="tooltip-turn">
              {hoveredPoint.label} (Caller)
            </span>
            <span
              className={`badge-pill ${
                hoveredPoint.sentiment_category === "positive"
                  ? "badge-pill-pos"
                  : hoveredPoint.sentiment_category === "negative"
                  ? "badge-pill-neg"
                  : "badge-pill-neu"
              }`}
            >
              {hoveredPoint.sentiment_category.toUpperCase()}
            </span>
          </div>

          <div className="tooltip-score-row">
            <span className="tooltip-label">Caller Sentiment Score:</span>
            <span
              className="tooltip-val-score"
              style={{
                color:
                  hoveredPoint.score > 0
                    ? "#10b981"
                    : hoveredPoint.score <= -80
                    ? "#b91c1c"
                    : hoveredPoint.score < 0
                    ? "#ef4444"
                    : "#64748b",
              }}
            >
              {hoveredPoint.score > 0 ? `+${hoveredPoint.score.toFixed(1)}` : hoveredPoint.score.toFixed(1)}
            </span>
          </div>

          <div className="tooltip-metric-grid">
            <div>
              <span className="tooltip-metric-name">Emotion:</span>{" "}
              <strong style={{ textTransform: "capitalize" }}>{hoveredPoint.emotion || "neutral"}</strong>
            </div>
            <div>
              <span className="tooltip-metric-name">Confidence:</span>{" "}
              <strong>{(hoveredPoint.confidence * 100).toFixed(1)}%</strong>
            </div>
            <div>
              <span className="tooltip-metric-name">Raw Weight:</span>{" "}
              <strong>{hoveredPoint.emotion_weight > 0 ? `+${hoveredPoint.emotion_weight}` : hoveredPoint.emotion_weight}</strong>
            </div>
            <div>
              <span className="tooltip-metric-name">Eff. Weight:</span>{" "}
              <strong>
                {hoveredPoint.effective_emotion_weight > 0
                  ? `+${hoveredPoint.effective_emotion_weight.toFixed(1)}`
                  : hoveredPoint.effective_emotion_weight.toFixed(1)}
              </strong>
            </div>
          </div>

          {hoveredPoint.sentence && (
            <div className="tooltip-sentence">&ldquo;{hoveredPoint.sentence}&rdquo;</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function LiveMonitor() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [transcript, setTranscript] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [liveScore, setLiveScore] = useState<number>(0);
  const [previousScore, setPreviousScore] = useState<number>(0);
  const [scoreDetails, setScoreDetails] = useState<ScoreDetails | null>(null);

  const [inputText, setInputText] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Dataset Selection state
  const [selectedDatasetKey, setSelectedDatasetKey] = useState<string>("negative");
  const activeDataset = SCENARIO_DATASETS[selectedDatasetKey] || SCENARIO_DATASETS.negative;
  const activeScenario = activeDataset.data;

  // Script Scenario Pipeline index state
  const [scenarioIndex, setScenarioIndex] = useState<number>(0);
  const [showScenarioDrawer, setShowScenarioDrawer] = useState<boolean>(false);

  // Auto-run pipeline state (Automatically send one by one when response is received)
  const [isAutoRunning, setIsAutoRunning] = useState<boolean>(false);
  const [autoDelay, setAutoDelay] = useState<number>(500); // ms delay after backend response before sending next turn

  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Restore session from sessionStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const savedLiveScore = sessionStorage.getItem("live_sentiment_score");
        if (savedLiveScore !== null) {
          const parsed = parseFloat(savedLiveScore);
          if (!isNaN(parsed)) setLiveScore(parsed);
        }

        const savedPrevScore = sessionStorage.getItem("previous_sentiment_score");
        if (savedPrevScore !== null) {
          const parsed = parseFloat(savedPrevScore);
          if (!isNaN(parsed)) setPreviousScore(parsed);
        }

        const savedAll = sessionStorage.getItem("all_chat_messages");
        if (savedAll) {
          const parsedAll: ChatMessage[] = JSON.parse(savedAll);
          setMessages(parsedAll);
          setTranscript(parsedAll.map((m) => m.isolated_sentence).join(" "));
          setScenarioIndex(parsedAll.length);
        }

        const savedDetails = sessionStorage.getItem("latest_score_details");
        if (savedDetails) {
          setScoreDetails(JSON.parse(savedDetails));
        }

        const savedDataset = sessionStorage.getItem("selected_dataset_key");
        if (savedDataset && SCENARIO_DATASETS[savedDataset]) {
          setSelectedDatasetKey(savedDataset);
        }
      } catch (e) {
        console.error("Failed to load conversation history from sessionStorage:", e);
      }
    }
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleResetCall = useCallback(() => {
    setIsAutoRunning(false);
    setMessages([]);
    setTranscript("");
    setLiveScore(0);
    setPreviousScore(0);
    setScoreDetails(null);
    setError(null);
    setScenarioIndex(0);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("all_chat_messages");
      sessionStorage.removeItem("last_6_chat_messages");
      sessionStorage.removeItem("live_sentiment_score");
      sessionStorage.removeItem("previous_sentiment_score");
      sessionStorage.removeItem("latest_score_details");
    }
  }, []);

  const handleDatasetChange = useCallback((newKey: string) => {
    setIsAutoRunning(false);
    setSelectedDatasetKey(newKey);
    setScenarioIndex(0);
    if (typeof window !== "undefined") {
      sessionStorage.setItem("selected_dataset_key", newKey);
    }
  }, []);

  // Message sender function exclusively for Caller (returns boolean success)
  const sendCallerUtterance = useCallback(
    async (textToSend: string): Promise<boolean> => {
      if (!textToSend.trim() || isLoading) return false;
      setIsLoading(true);
      setError(null);

      try {
        const res = await fetch("http://localhost:8000/api/v1/process-message", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: textToSend,
            speaker: "caller",
            previous_score: liveScore,
            turn_count: messages.length + 1,
            session_avg_score: scoreDetails?.session_avg_score ?? liveScore,
            peak_negativity: scoreDetails?.peak_negativity ?? liveScore,
            recent_scores: messages.slice(-5).map((m) => m.running_score),
          }),
        });

        const data = await res.json();
        if (data.status === "success") {
          const issues = data.detected_issues || [];
          if (issues.length > 0) {
            const issue = issues[0];
            const newScore =
              typeof issue.final_score === "number"
                ? issue.final_score
                : typeof issue.score === "number"
                ? issue.score
                : liveScore;

            const rawWeight =
              typeof issue.emotion_weight === "number"
                ? issue.emotion_weight
                : getEmotionWeight(issue.emotion);

            const conf = issue.confidence || 0.0;
            const effWeight =
              typeof issue.effective_emotion_weight === "number"
                ? issue.effective_emotion_weight
                : rawWeight * conf;

            const details: ScoreDetails = issue.score_details || {
              emotion: issue.emotion || "neutral",
              confidence: conf,
              emotion_weight: rawWeight,
              effective_emotion_weight: effWeight,
              previous_score: liveScore,
              dampening_factor: 1.0,
              dampened_raw_score: effWeight,
              score: newScore,
              call_health_score: newScore,
              sentiment_trend: "Stable",
              peak_negativity: newScore,
              turn_count: messages.length + 1,
              session_avg_score: newScore,
              escalation_triggered: newScore <= -65.0,
            };

            const newMsg: ChatMessage = {
              id: `msg-${Date.now()}`,
              speaker: "caller",
              isolated_sentence: textToSend,
              phrase: issue.detected_keywords?.[0]?.keyword || "N/A",
              detected_keywords: issue.detected_keywords || [],
              emotion: issue.emotion || "neutral",
              sentiment_category:
                issue.sentiment_category === "positive" ||
                issue.sentiment_category === "negative" ||
                issue.sentiment_category === "neutral"
                  ? issue.sentiment_category
                  : "neutral",
              confidence: conf,
              emotion_weight: rawWeight,
              effective_emotion_weight: effWeight,
              sentence_score: rawWeight,
              running_score: newScore,
            };

            const updatedMessages = [...messages, newMsg];
            setMessages(updatedMessages);
            setPreviousScore(liveScore);
            setLiveScore(newScore);
            setScoreDetails(details);

            if (typeof window !== "undefined") {
              sessionStorage.setItem("all_chat_messages", JSON.stringify(updatedMessages));
              sessionStorage.setItem("previous_sentiment_score", liveScore.toString());
              sessionStorage.setItem("live_sentiment_score", newScore.toString());
              sessionStorage.setItem("latest_score_details", JSON.stringify(details));
            }
            return true;
          }
        } else {
          setError(data.detail || "Error processing message");
          return false;
        }
      } catch (err) {
        setError("Failed to connect to API Gateway at http://localhost:8000. Is the backend running?");
        return false;
      } finally {
        setIsLoading(false);
      }
      return false;
    },
    [isLoading, liveScore, messages, scoreDetails]
  );

  // Auto-run sequential runner: automatically triggers the next chunk as soon as previous response finishes
  useEffect(() => {
    let timer: NodeJS.Timeout;

    if (isAutoRunning && !isLoading) {
      if (scenarioIndex < activeScenario.length) {
        timer = setTimeout(() => {
          const chunk = activeScenario[scenarioIndex];
          setScenarioIndex((prev) => prev + 1);
          sendCallerUtterance(chunk.text).then((success) => {
            if (!success) {
              setIsAutoRunning(false);
            }
          });
        }, autoDelay);
      } else {
        setIsAutoRunning(false);
      }
    }

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isAutoRunning, isLoading, scenarioIndex, autoDelay, activeScenario, sendCallerUtterance]);

  const toggleAutoRun = useCallback(() => {
    if (isAutoRunning) {
      setIsAutoRunning(false);
    } else {
      if (scenarioIndex >= activeScenario.length) {
        setScenarioIndex(0);
      }
      setIsAutoRunning(true);
    }
  }, [isAutoRunning, scenarioIndex, activeScenario.length]);

  const handleSendTextMessage = useCallback(() => {
    if (!inputText.trim()) return;
    const text = inputText.trim();
    setInputText("");
    sendCallerUtterance(text);
  }, [inputText, sendCallerUtterance]);

  // Execute next chunk from active test scenario manually (one by one)
  const handleSendNextScenarioChunk = useCallback(() => {
    if (scenarioIndex >= activeScenario.length) return;
    const chunk = activeScenario[scenarioIndex];
    sendCallerUtterance(chunk.text);
    setScenarioIndex((prev) => prev + 1);
  }, [activeScenario, scenarioIndex, sendCallerUtterance]);

  // Execute any specific chunk directly from the list drawer
  const handleSendSpecificChunk = useCallback(
    (chunk: ScenarioChunk, idx: number) => {
      sendCallerUtterance(chunk.text);
      setScenarioIndex(idx + 1);
    },
    [sendCallerUtterance]
  );

  // Construct chart points progression
  const chartPoints: ChartPoint[] = useMemo(() => {
    const initialPoint: ChartPoint = {
      turnIndex: 0,
      label: "Start",
      score: 0.0,
      emotion: "neutral",
      confidence: 1.0,
      sentiment_category: "neutral",
      emotion_weight: 0.0,
      effective_emotion_weight: 0.0,
      sentence: "Initial baseline",
    };

    if (messages.length === 0) {
      return [initialPoint];
    }

    const pts: ChartPoint[] = [initialPoint];
    messages.forEach((msg, idx) => {
      pts.push({
        turnIndex: idx + 1,
        label: `T${idx + 1}`,
        score: msg.running_score,
        emotion: msg.emotion,
        confidence: msg.confidence,
        sentiment_category: msg.sentiment_category,
        emotion_weight: msg.emotion_weight,
        effective_emotion_weight: msg.effective_emotion_weight,
        speaker: "caller",
        sentence: msg.isolated_sentence,
      });
    });

    return pts;
  }, [messages]);

  // Latest message metadata
  const latestMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const currentEmotion = latestMessage?.emotion || scoreDetails?.emotion || "neutral";
  const currentConfidence = latestMessage?.confidence ?? scoreDetails?.confidence ?? 0.0;
  const currentCategory = latestMessage?.sentiment_category || (liveScore > 5 ? "positive" : liveScore < -5 ? "negative" : "neutral");
  const currentRawWeight = latestMessage?.emotion_weight ?? (scoreDetails?.emotion_weight ?? getEmotionWeight(currentEmotion));
  const currentEffWeight = latestMessage?.effective_emotion_weight ?? (scoreDetails?.effective_emotion_weight ?? currentRawWeight * currentConfidence);

  const filteredMessages = useMemo(() => {
    if (!searchQuery.trim()) return messages;
    const q = searchQuery.toLowerCase();
    return messages.filter(
      (msg) =>
        msg.isolated_sentence.toLowerCase().includes(q) ||
        msg.emotion.toLowerCase().includes(q) ||
        msg.sentiment_category.toLowerCase().includes(q)
    );
  }, [messages, searchQuery]);

  return (
    <div className="live-page-root">
      {/* Top Navbar */}
      <header className="live-header">
        <div className="live-title-group">
          <div className="live-logo-icon">
            <Broadcast size={20} weight="bold" />
          </div>
          <div>
            <h1 className="live-title">Live Call Sentiment Monitor</h1>
            <p className="live-subtitle">Caller Sentiment &bull; ModernBERT GoEmotions</p>
          </div>
        </div>

        {/* Center: Dynamic Scenario Dataset Pipeline Launcher */}
        <div className="scenario-pipeline-bar">
          {/* Dataset JSON File Selector Dropdown */}
          <select
            value={selectedDatasetKey}
            onChange={(e) => handleDatasetChange(e.target.value)}
            className="scenario-select"
            title="Select Scenario Dataset JSON File"
          >
            {Object.entries(SCENARIO_DATASETS).map(([key, dataset]) => (
              <option key={key} value={key}>
                📄 {dataset.filename} — {dataset.name}
              </option>
            ))}
          </select>

          <div className="scenario-info-tag">
            <Flame size={16} weight="fill" color={activeDataset.badgeColor} />
            <span className="scenario-name">{activeDataset.name}</span>
            <span className="scenario-progress-pill">
              Chunk {Math.min(scenarioIndex + 1, activeScenario.length)} / {activeScenario.length}
            </span>
          </div>

          {/* Manual Send Next Button (Send one by one manually) */}
          <button
            onClick={handleSendNextScenarioChunk}
            disabled={isLoading || isAutoRunning || scenarioIndex >= activeScenario.length}
            className="scenario-next-btn"
            title={`Send next single caller utterance from ${activeDataset.filename} manually`}
            style={
              activeDataset.id === "positive"
                ? { background: "linear-gradient(135deg, #059669 0%, #047857 100%)", boxShadow: "0 1px 2px rgba(5, 150, 105, 0.2)" }
                : undefined
            }
          >
            {isLoading && !isAutoRunning ? (
              <Spinner size={14} className="animate-spin" />
            ) : (
              <Play size={14} weight="fill" />
            )}
            <span>
              {scenarioIndex >= activeScenario.length
                ? "Scenario Finished"
                : `Inject Turn #${scenarioIndex + 1}`}
            </span>
          </button>

          {/* Auto-Run Button (Automatically sends one by one upon receiving backend response) */}
          <button
            onClick={toggleAutoRun}
            disabled={isLoading && !isAutoRunning}
            className={`scenario-auto-btn ${isAutoRunning ? "running" : ""}`}
            title={`Automatically send each turn from ${activeDataset.filename} one by one`}
          >
            {isAutoRunning ? (
              <>
                <Pause size={14} weight="fill" />
                <span>Pause Auto-Run</span>
              </>
            ) : (
              <>
                <FastForward size={14} weight="fill" />
                <span>Auto-Run All {activeScenario.length}</span>
              </>
            )}
          </button>

          {/* Auto-Run Speed Selector */}
          <select
            value={autoDelay}
            onChange={(e) => setAutoDelay(Number(e.target.value))}
            className="speed-select"
            title="Delay between responses in auto-run mode"
          >
            <option value={100}>Instant (100ms)</option>
            <option value={300}>Fast (300ms)</option>
            <option value={500}>Normal (500ms)</option>
            <option value={1000}>Slow (1s)</option>
            <option value={2000}>Relaxed (2s)</option>
          </select>

          {/* Interactive Chunk List Drawer Toggle */}
          <button
            onClick={() => setShowScenarioDrawer(!showScenarioDrawer)}
            className={`scenario-list-toggle ${showScenarioDrawer ? "active" : ""}`}
            title="Open/Close Interactive Script List"
          >
            <ListNumbers size={16} weight="bold" />
            <span>Chunks ({activeScenario.length})</span>
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          {liveScore <= -65 && (
            <div className="escalation-alert-badge">
              <WarningOctagon size={16} weight="fill" />
              <span>{liveScore <= -80 ? "SEVERE FRICTION (<= -80)" : "CRITICAL ESCALATION (<= -65)"}</span>
            </div>
          )}
          <button
            onClick={handleResetCall}
            className="reset-btn"
            title="Reset Session, Clear Chat & Restart Script"
          >
            <ArrowsClockwise size={16} weight="bold" />
            <span>Reset</span>
          </button>
        </div>
      </header>

      {/* Main Grid View */}
      <main className="live-main-grid">
        {/* Left Column: Live Conversation Feed */}
        <section className="left-chat-section">
          <div className="chat-header-bar">
            <div className="chat-search-wrap">
              <MagnifyingGlass size={15} className="chat-search-icon" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search caller transcript..."
                className="chat-search-input"
              />
            </div>

            <div className="caller-active-badge">
              <User size={14} weight="bold" />
              <span>Caller Transcripts Feed {isAutoRunning ? "(Auto-Running)" : ""}</span>
            </div>
          </div>

          {/* Conversation Transcript Feed */}
          <div className="chat-feed-area">
            {error && <div className="chat-error-banner">{error}</div>}

            {messages.length === 0 && !isLoading && (
              <div className="empty-chat-state">
                <div className="empty-chat-icon">
                  <Flame size={28} color={activeDataset.badgeColor} />
                </div>
                <h3 className="empty-chat-title">Ready for {activeDataset.name}</h3>
                <p className="empty-chat-desc">
                  Dataset: <strong>{activeDataset.filename}</strong> &bull; Click <strong>&ldquo;Inject Turn #1&rdquo;</strong> to send manually, or <strong>&ldquo;Auto-Run All 50&rdquo;</strong> to auto-play.
                </p>
              </div>
            )}

            {filteredMessages.map((msg, idx) => {
              const isPos = msg.sentiment_category === "positive";
              const isNeg = msg.sentiment_category === "negative";

              return (
                <div
                  key={msg.id || idx}
                  className="chat-row chat-row-caller"
                >
                  <div className="chat-avatar avatar-caller">
                    <User size={15} weight="bold" />
                  </div>

                  <div className="chat-bubble-container">
                    <div className="chat-bubble-meta">
                      <span className="chat-speaker-label">
                        Caller &bull; Turn #{idx + 1}
                      </span>
                      <span
                        className={`badge-pill ${
                          isPos
                            ? "badge-pill-pos"
                            : isNeg
                            ? "badge-pill-neg"
                            : "badge-pill-neu"
                        }`}
                      >
                        {msg.sentiment_category.toUpperCase()}
                      </span>
                    </div>

                    <div className="chat-bubble-content bubble-caller">
                      {msg.isolated_sentence}
                    </div>

                    {/* Detailed Metadata Pill Bar */}
                    <div className="chat-bubble-analytics">
                      <span className="analytics-pill">
                        Emotion: <strong>{msg.emotion}</strong> ({(msg.confidence * 100).toFixed(0)}%)
                      </span>
                      <span className="analytics-pill">
                        Weight: <strong>{msg.emotion_weight > 0 ? `+${msg.emotion_weight}` : msg.emotion_weight}</strong>
                      </span>
                      <span className="analytics-pill">
                        Eff: <strong>{msg.effective_emotion_weight > 0 ? `+${msg.effective_emotion_weight.toFixed(1)}` : msg.effective_emotion_weight.toFixed(1)}</strong>
                      </span>
                      <span
                        className="analytics-pill"
                        style={{
                          color:
                            msg.running_score > 0
                              ? "#059669"
                              : msg.running_score <= -80
                              ? "#991b1b"
                              : msg.running_score < 0
                              ? "#dc2626"
                              : "#475569",
                          fontWeight: 700,
                        }}
                      >
                        Score: {msg.running_score > 0 ? `+${msg.running_score.toFixed(1)}` : msg.running_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={chatBottomRef} />
          </div>

          {/* Bottom Chat Input Bar */}
          <div className="chat-input-bar">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
                if (e.key === "Enter") handleSendTextMessage();
              }}
              placeholder="Send custom caller transcript... (Press Enter)"
              className="chat-text-input"
            />
            <button
              onClick={handleSendTextMessage}
              disabled={isLoading || !inputText.trim()}
              className="chat-send-btn send-caller"
            >
              {isLoading ? (
                <Spinner size={16} className="animate-spin" />
              ) : (
                <PaperPlaneRight size={16} weight="bold" />
              )}
              <span>Send</span>
            </button>
          </div>
        </section>

        {/* Right Column: Clean Live Analytics & Line Chart */}
        <section className="right-analytics-section">
          {/* Key Metrics Grid */}
          <div className="metrics-summary-grid">
            {/* Metric 1: Current Live Sentiment Score */}
            <div className="metric-card">
              <div className="metric-card-header">
                <span className="metric-title">Caller Sentiment Score</span>
                <span
                  className={`badge-pill ${
                    liveScore > 0
                      ? "badge-pill-pos"
                      : liveScore <= -80
                      ? "badge-pill-extreme"
                      : liveScore < 0
                      ? "badge-pill-neg"
                      : "badge-pill-neu"
                  }`}
                >
                  {liveScore <= -80 ? "SEVERE NEGATIVE" : liveScore < 0 ? "NEGATIVE" : liveScore > 0 ? "POSITIVE" : "NEUTRAL"}
                </span>
              </div>
              <div
                className="big-metric-score"
                style={{
                  color:
                    liveScore > 0
                      ? "#059669"
                      : liveScore <= -80
                      ? "#991b1b"
                      : liveScore < 0
                      ? "#dc2626"
                      : "#334155",
                }}
              >
                {liveScore > 0 ? `+${liveScore.toFixed(1)}` : liveScore.toFixed(1)}
              </div>
              <div className="metric-subtext">
                Previous Score:{" "}
                <strong>
                  {previousScore > 0 ? `+${previousScore.toFixed(1)}` : previousScore.toFixed(1)}
                </strong>{" "}
                &bull; Range: [-100, +100]
              </div>
            </div>

            {/* Metric 2: Triggered Emotion & Confidence */}
            <div className="metric-card">
              <div className="metric-card-header">
                <span className="metric-title">Triggered Emotion</span>
                <span className="confidence-tag">
                  {(currentConfidence * 100).toFixed(1)}% Confidence
                </span>
              </div>
              <div className="big-metric-emotion">
                {currentEmotion.toUpperCase()}
              </div>
              <div className="metric-subtext">
                Model: <strong>ModernBERT GoEmotions</strong> &bull; Class:{" "}
                <span
                  style={{
                    fontWeight: 700,
                    color:
                      currentCategory === "positive"
                        ? "#059669"
                        : currentCategory === "negative"
                        ? "#dc2626"
                        : "#64748b",
                  }}
                >
                  {currentCategory.toUpperCase()}
                </span>
              </div>
            </div>

            {/* Metric 3: Applied Emotion Weights */}
            <div className="metric-card">
              <div className="metric-card-header">
                <span className="metric-title">Emotion Weights</span>
                <Scales size={16} style={{ color: "#64748b" }} />
              </div>
              <div className="weight-display-row">
                <div className="weight-box">
                  <span className="weight-lbl">Raw Weight</span>
                  <span
                    className="weight-val"
                    style={{
                      color:
                        currentRawWeight > 0
                          ? "#059669"
                          : currentRawWeight < 0
                          ? "#dc2626"
                          : "#334155",
                    }}
                  >
                    {currentRawWeight > 0 ? `+${currentRawWeight.toFixed(0)}` : currentRawWeight.toFixed(0)}
                  </span>
                </div>
                <div className="weight-divider">&rarr;</div>
                <div className="weight-box">
                  <span className="weight-lbl">Effective Weight</span>
                  <span
                    className="weight-val"
                    style={{
                      color:
                        currentEffWeight > 0
                          ? "#059669"
                          : currentEffWeight < 0
                          ? "#dc2626"
                          : "#334155",
                    }}
                  >
                    {currentEffWeight > 0 ? `+${currentEffWeight.toFixed(1)}` : currentEffWeight.toFixed(1)}
                  </span>
                </div>
              </div>
              <div className="metric-subtext" style={{ textAlign: "center" }}>
                Effective Weight = Raw Weight &times; Confidence
              </div>
            </div>

            {/* Metric 4: Health & Session Trajectory */}
            <div className="metric-card">
              <div className="metric-card-header">
                <span className="metric-title">Call Health &amp; Trend</span>
                <Heartbeat size={16} style={{ color: "#ff5722" }} />
              </div>
              <div className="health-trend-row">
                <div>
                  <span className="health-lbl">Call Health</span>
                  <div
                    className="health-val"
                    style={{
                      color:
                        (scoreDetails?.call_health_score ?? liveScore) > 0
                          ? "#059669"
                          : "#dc2626",
                    }}
                  >
                    {(scoreDetails?.call_health_score ?? liveScore) > 0
                      ? `+${(scoreDetails?.call_health_score ?? liveScore).toFixed(1)}`
                      : (scoreDetails?.call_health_score ?? liveScore).toFixed(1)}
                  </div>
                </div>
                <div>
                  <span className="health-lbl">Trajectory</span>
                  <div className="trend-badge">
                    {scoreDetails?.sentiment_trend === "Strong Recovery" ? (
                      <TrendUp size={14} color="#059669" weight="bold" />
                    ) : scoreDetails?.sentiment_trend === "Escalating" ? (
                      <TrendDown size={14} color="#dc2626" weight="bold" />
                    ) : (
                      <Minus size={14} color="#64748b" weight="bold" />
                    )}
                    <span>{scoreDetails?.sentiment_trend || "Stable"}</span>
                  </div>
                </div>
              </div>
              <div className="metric-subtext">
                Peak Negativity:{" "}
                <strong style={{ color: "#dc2626" }}>
                  {(scoreDetails?.peak_negativity ?? liveScore).toFixed(1)}
                </strong>
              </div>
            </div>
          </div>

          {/* Real-time Sentiment Score Line Chart */}
          <div className="chart-card">
            <div className="chart-card-header">
              <div>
                <h2 className="chart-card-title">Caller Sentiment Trajectory</h2>
                <p className="chart-card-subtitle">
                  Historical progression for {activeDataset.filename} across turns
                </p>
              </div>
              <div className="chart-legend">
                <span className="legend-item">
                  <span className="legend-dot" style={{ backgroundColor: "#10b981" }}></span>
                  Positive (&gt; 0)
                </span>
                <span className="legend-item">
                  <span className="legend-dot" style={{ backgroundColor: "#ef4444" }}></span>
                  Negative (&lt; 0)
                </span>
                <span className="legend-item">
                  <span className="legend-dot" style={{ backgroundColor: "#dc2626", border: "1px dashed #dc2626" }}></span>
                  Escalation (&le; -65)
                </span>
                <span className="legend-item">
                  <span className="legend-dot" style={{ backgroundColor: "#991b1b" }}></span>
                  Severe (&le; -80)
                </span>
              </div>
            </div>

            <SentimentLineChart points={chartPoints} />
          </div>

          {/* Interactive Scenario Script Drawer */}
          {showScenarioDrawer && (
            <div className="scenario-drawer-panel">
              <div className="scenario-drawer-header">
                <div>
                  <h3 className="scenario-drawer-title">
                    {activeDataset.name} ({activeDataset.filename})
                  </h3>
                  <p className="scenario-drawer-sub">
                    Click any caller chunk below to inject it directly into the live sentiment pipeline
                  </p>
                </div>
                <button
                  onClick={() => setShowScenarioDrawer(false)}
                  className="scenario-close-btn"
                >
                  &times;
                </button>
              </div>

              <div className="scenario-chunks-grid">
                {activeScenario.map((chunk, idx) => {
                  const isSent = idx < scenarioIndex;
                  const isNext = idx === scenarioIndex;
                  return (
                    <div
                      key={chunk.turn}
                      className={`scenario-chunk-item ${isSent ? "chunk-sent" : ""} ${isNext ? "chunk-next" : ""}`}
                    >
                      <div className="chunk-meta">
                        <span className="chunk-role-badge role-caller">
                          CALLER &bull; Turn #{chunk.turn}
                        </span>
                        <span className="chunk-mood-tag">{chunk.expectedMood}</span>
                        <button
                          onClick={() => handleSendSpecificChunk(chunk, idx)}
                          disabled={isLoading}
                          className="chunk-fire-btn"
                        >
                          <Play size={12} weight="fill" />
                          <span>{isSent ? "Re-send" : "Inject"}</span>
                        </button>
                      </div>
                      <p className="chunk-text">&ldquo;{chunk.text}&rdquo;</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
