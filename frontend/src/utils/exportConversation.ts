export interface DetectedKeyword {
  keyword: string;
  sentiment: string;
}

export interface ScoreDetails {
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

export interface ChatMessage {
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

interface ExportReportOptions {
  messages: ChatMessage[];
  liveScore: number;
  previousScore: number;
  scoreDetails: ScoreDetails | null;
  datasetName: string;
  svgElement: SVGSVGElement | null;
}

/**
 * Utility to export complete conversation transcript and plotted SVG chart
 * as a standalone, printable HTML report file.
 */
export function exportConversationReport({
  messages,
  liveScore,
  previousScore,
  scoreDetails,
  datasetName,
  svgElement,
}: ExportReportOptions): void {
  const timestamp = new Date().toLocaleString();
  const fileDate = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);

  // 1. Serialize SVG chart if present
  let chartSvgHtml = "<p>No chart data available</p>";
  if (svgElement) {
    try {
      const clone = svgElement.cloneNode(true) as SVGSVGElement;
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      clone.setAttribute("width", "100%");
      clone.setAttribute("height", "280");
      chartSvgHtml = clone.outerHTML;
    } catch (e) {
      console.error("Failed to serialize SVG chart:", e);
    }
  }

  // 2. Format Turn-by-Turn Rows
  const transcriptRowsHtml = messages
    .map((msg, idx) => {
      const isPos = msg.sentiment_category === "positive";
      const isNeg = msg.sentiment_category === "negative";
      const badgeBg = isPos ? "#ecfdf5" : isNeg ? "#fef2f2" : "#f1f5f9";
      const badgeColor = isPos ? "#059669" : isNeg ? "#dc2626" : "#475569";
      const badgeBorder = isPos ? "#a7f3d0" : isNeg ? "#fecaca" : "#e2e8f0";

      const scoreColor =
        msg.running_score > 0
          ? "#059669"
          : msg.running_score <= -80
          ? "#991b1b"
          : msg.running_score < 0
          ? "#dc2626"
          : "#475569";

      return `
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding: 10px 12px; font-weight: 800; text-align: center; color: #64748b;">T${idx + 1}</td>
          <td style="padding: 10px 12px; font-weight: 700; color: #1e293b;">Caller</td>
          <td style="padding: 10px 12px; color: #334155; line-height: 1.45;">"${msg.isolated_sentence}"</td>
          <td style="padding: 10px 12px; text-align: center;">
            <span style="background-color: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeBorder}; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 800; text-transform: uppercase;">
              ${msg.sentiment_category}
            </span>
          </td>
          <td style="padding: 10px 12px; font-weight: 700; text-transform: capitalize; color: #0f172a;">${msg.emotion || "neutral"}</td>
          <td style="padding: 10px 12px; text-align: center; color: #475569; font-weight: 600;">${(msg.confidence * 100).toFixed(1)}%</td>
          <td style="padding: 10px 12px; text-align: center; color: #475569;">${msg.emotion_weight > 0 ? `+${msg.emotion_weight}` : msg.emotion_weight}</td>
          <td style="padding: 10px 12px; text-align: center; color: #475569;">${msg.effective_emotion_weight > 0 ? `+${msg.effective_emotion_weight.toFixed(1)}` : msg.effective_emotion_weight.toFixed(1)}</td>
          <td style="padding: 10px 12px; text-align: center; font-weight: 800; color: ${scoreColor}; font-size: 14px;">
            ${msg.running_score > 0 ? `+${msg.running_score.toFixed(1)}` : msg.running_score.toFixed(1)}
          </td>
        </tr>
      `;
    })
    .join("");

  // 3. Build Full Report HTML Template
  const reportHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Live Call Sentiment Analysis Report - ${fileDate}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background-color: #f8fafc;
      color: #0f172a;
      margin: 0;
      padding: 24px;
    }
    .container {
      max-width: 1100px;
      margin: 0 auto;
      background-color: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #f1f5f9;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }
    .title {
      font-size: 22px;
      font-weight: 800;
      color: #0f172a;
      margin: 0;
    }
    .subtitle {
      font-size: 13px;
      color: #64748b;
      margin-top: 4px;
    }
    .print-btn {
      background-color: #0f172a;
      color: #ffffff;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 28px;
    }
    .metric-card {
      background-color: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 14px;
    }
    .metric-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      color: #64748b;
    }
    .metric-value {
      font-size: 26px;
      font-weight: 800;
      margin-top: 6px;
    }
    .chart-card {
      background-color: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 28px;
    }
    .chart-title {
      font-size: 16px;
      font-weight: 800;
      margin-bottom: 12px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th {
      background-color: #f1f5f9;
      padding: 10px 12px;
      text-align: left;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      color: #475569;
    }
    @media print {
      .print-btn { display: none; }
      body { background-color: #ffffff; padding: 0; }
      .container { border: none; box-shadow: none; padding: 0; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1 class="title">Live Call Sentiment Analysis Report</h1>
        <p class="subtitle">Dataset Scenario: <strong>${datasetName}</strong> &bull; Generated: ${timestamp}</p>
      </div>
      <button onclick="window.print()" class="print-btn">🖨️ Print / Save PDF</button>
    </div>

    <!-- Metrics Summary -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-title">Final Sentiment Score</div>
        <div class="metric-value" style="color: ${liveScore > 0 ? '#059669' : liveScore <= -80 ? '#991b1b' : liveScore < 0 ? '#dc2626' : '#334155'};">
          ${liveScore > 0 ? `+${liveScore.toFixed(1)}` : liveScore.toFixed(1)}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Call Health Score</div>
        <div class="metric-value" style="color: ${(scoreDetails?.call_health_score ?? liveScore) > 0 ? '#059669' : '#dc2626'};">
          ${(scoreDetails?.call_health_score ?? liveScore) > 0 ? `+${(scoreDetails?.call_health_score ?? liveScore).toFixed(1)}` : (scoreDetails?.call_health_score ?? liveScore).toFixed(1)}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Peak Negativity</div>
        <div class="metric-value" style="color: #dc2626;">
          ${(scoreDetails?.peak_negativity ?? liveScore).toFixed(1)}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Trajectory & Turns</div>
        <div class="metric-value" style="font-size: 18px; color: #0f172a; margin-top: 10px;">
          ${scoreDetails?.sentiment_trend || 'Stable'} &bull; ${messages.length} Turns
        </div>
      </div>
    </div>

    <!-- Plotted Sentiment Trajectory Chart -->
    <div class="chart-card">
      <div class="chart-title">Plotted Caller Sentiment Trajectory Graph</div>
      <div style="width: 100%; overflow: hidden;">
        ${chartSvgHtml}
      </div>
    </div>

    <!-- Turn by Turn Transcript Table -->
    <div>
      <h3 style="font-size: 16px; font-weight: 800; margin-bottom: 12px;">Complete Turn-by-Turn Conversation Transcript</h3>
      <table>
        <thead>
          <tr>
            <th style="text-align: center;">Turn</th>
            <th>Speaker</th>
            <th>Utterance Text</th>
            <th style="text-align: center;">Category</th>
            <th>Emotion</th>
            <th style="text-align: center;">Confidence</th>
            <th style="text-align: center;">Raw Wt</th>
            <th style="text-align: center;">Eff Wt</th>
            <th style="text-align: center;">Score</th>
          </tr>
        </thead>
        <tbody>
          ${transcriptRowsHtml || '<tr><td colspan="9" style="text-align: center; padding: 20px; color: #94a3b8;">No conversation turns recorded yet.</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>`;

  // 4. Trigger File Download
  const blob = new Blob([reportHtml], { type: "text/html;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `live_call_sentiment_report_${fileDate}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Utility to download raw conversation data as JSON
 */
export function exportConversationJSON(messages: ChatMessage[], liveScore: number, datasetName: string): void {
  const fileDate = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const data = {
    dataset: datasetName,
    exported_at: new Date().toISOString(),
    final_sentiment_score: liveScore,
    total_turns: messages.length,
    messages,
  };

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `live_call_sentiment_${fileDate}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
