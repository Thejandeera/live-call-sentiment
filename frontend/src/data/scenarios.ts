import negativeScenario from "./negative.json";
import positiveScenario from "./positive.json";
import mixedScenario from "./mixed_sentiment_100_turns.json";
import negative100Scenario from "./negative_100.json";

export interface ScenarioChunk {
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

function formatNameFromFilename(filename: string): string {
  const base = filename.replace(/\.json$/i, "");
  return base
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getBadgeColor(id: string): string {
  const lower = id.toLowerCase();
  if (lower.includes("pos")) return "#059669";
  if (lower.includes("neg") || lower.includes("catastrophic")) return "#dc2626";
  if (lower.includes("mix")) return "#7c3aed";
  return "#2563eb";
}

/**
 * Dynamically loads all JSON dataset files in frontend/src/data/
 */
export function loadAllScenarioDatasets(): Record<string, ScenarioDataset> {
  const datasets: Record<string, ScenarioDataset> = {};

  // 1. Try Webpack require.context for automatic discovery of ANY newly added .json file
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const context = (require as any).context("./", false, /\.json$/);
    if (context && typeof context.keys === "function") {
      context.keys().forEach((key: string) => {
        const filename = key.replace("./", "");
        const id = filename.replace(/\.json$/i, "");
        const rawModule = context(key);
        const data = Array.isArray(rawModule)
          ? rawModule
          : rawModule && Array.isArray(rawModule.default)
          ? rawModule.default
          : [];

        datasets[id] = {
          id,
          name: formatNameFromFilename(filename),
          filename,
          badgeColor: getBadgeColor(id),
          data: data as ScenarioChunk[],
        };
      });
    }
  } catch (e) {
    // Fallback if require.context is not available
    console.warn("require.context unavailable, falling back to static imports:", e);
  }

  // Fallback defaults if require.context didn't populate
  if (Object.keys(datasets).length === 0) {
    datasets["negative"] = {
      id: "negative",
      name: "Negative (50 Turns)",
      filename: "negative.json",
      badgeColor: "#dc2626",
      data: negativeScenario as ScenarioChunk[],
    };
    datasets["negative_100"] = {
      id: "negative_100",
      name: "Negative 100 (100 Turns)",
      filename: "negative_100.json",
      badgeColor: "#dc2626",
      data: negative100Scenario as ScenarioChunk[],
    };
    datasets["positive"] = {
      id: "positive",
      name: "Positive (50 Turns)",
      filename: "positive.json",
      badgeColor: "#059669",
      data: positiveScenario as ScenarioChunk[],
    };
    datasets["mixed_sentiment_100_turns"] = {
      id: "mixed_sentiment_100_turns",
      name: "Mixed Sentiment 100 Turns (100 Turns)",
      filename: "mixed_sentiment_100_turns.json",
      badgeColor: "#7c3aed",
      data: mixedScenario as ScenarioChunk[],
    };
  }

  return datasets;
}

export const SCENARIO_DATASETS = loadAllScenarioDatasets();
