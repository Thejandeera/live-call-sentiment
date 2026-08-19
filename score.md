# Standardized Dual-Horizon Live Sentiment Score Specification (`score.md`)

This document provides a comprehensive technical specification of the standardized live sentiment scoring engine implemented in `service-score/main.py`. It explains the mathematical formulas, confidence weighting, neutral inertia attenuation, continuous logistic saturation functions, mild negative non-relief rules, crisis neutral clamping, sustained duration momentum, dual-horizon long-call metrics, and detailed worked calculation examples.

---

## 1. Overview & Purpose

The **Live Sentiment Score Service** (`service-score`) calculates a real-time Confidence-Weighted Dual-Horizon Sentiment Score $S \in [-100.0, +100.0]$ that tracks the emotional trajectory of live call sessions.

### Key Architectural Concepts:
1. **Confidence-Scaled Learning Rate ($\alpha_{\text{effective}}$)**: Scales the EMA learning rate $\alpha_{\text{effective}} = \alpha_{\text{base}} \times D(S) \times \max(0.40, \text{confidence})$, stepping directly towards the true emotion severity weight $W_{\text{destination}}$. This prevents low-confidence predictions from capping severe scores or causing artificial score reversals.
2. **Support Call Emotion Re-weighting**: Re-weights `curiosity` ($-10.0$, mild inquiry friction) and `surprise` ($0.0$, neutral baseline) to prevent rhetorical panicked customer questions from causing false positive spikes.
3. **Continuous Logistic Saturation Resistance ($D(S)$)**: Smooth continuous friction function $D(S) = \frac{1}{1 + (|S| / 100.0)^2}$ with saturation scale $100.0$.
4. **Mild Negative Non-Relief Rule**: When a call is already in severe crisis ($S_{\text{current}} \le -65.0$), milder negative emotions (e.g. `fear` $-65$, `annoyance` $-70$, `curiosity` $-10$) are clamped with minimal alpha ($\alpha = 0.01$) so they never pull an extreme crisis score upward as if they were positive relief.
5. **Crisis Neutral Clamping**: When $S_{\text{current}} \le -65.0$, factual/neutral statements (e.g. giving account numbers) decay by only $0.5\%$ instead of $4\%$, preserving caller crisis context.
6. **Sustained Duration Compounding**: When severe friction ($S \le -65.0, W \le -50.0$) persists across dozens of turns without resolution ($t > 10$), an incremental duration momentum penalty $- \min(0.60, \frac{t}{100} \times 0.60)$ compounds the score, allowing 100-turn catastrophic calls to smoothly reach $-95.0 \to -99.6$.
7. **Resolution-Restricted Fast Recovery**: Bypasses dampening ($D = 1.0$) only for genuine resolution emotions (`{"gratitude", "relief", "approval", "joy", "optimism", "caring", "admiration"}`).
8. **Dual-Horizon Session Metrics**:
   - **`live_score` ($S_{\text{live}}$)**: Instantaneous turn-by-turn EMA state.
   - **`call_health_score` ($S_{\text{health}}$)**: Cumulative session health score ($70\%$ session average + $30\%$ live score).
   - **`sentiment_trend`**: Rate of score change over recent turns (`"Strong Recovery"`, `"Escalating"`, `"Stable"`).
   - **`peak_negativity`**: Lowest score reached during the session.
9. **Escalation Threshold Breach**: Triggers intervention when either $S_{\text{live}} \le -65.0$ or $S_{\text{health}} \le -65.0$.

---

## 2. API Data Contracts

### 2.1 Request Schema (`ScoreRequest`)
- **Endpoint**: `POST /calculate-score`
- **Content-Type**: `application/json`

```json
{
  "emotion": "disgust",
  "confidence": 0.85,
  "previous_score": -70.0,
  "turn_count": 5,
  "session_avg_score": -65.0,
  "peak_negativity": -75.0,
  "speaker": "caller"
}
```

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `emotion` | `string` | Yes | `""` | The primary emotion string detected (e.g., `"anger"`, `"gratitude"`). |
| `confidence` | `float` | No | `1.0` | RoBERTa confidence score ($0.0 \le C \le 1.0$). |
| `previous_score` | `float` | No | `0.0` | Session score ($S_{\text{current}}$) prior to processing this segment. |
| `turn_count` | `int` | No | `1` | Cumulative number of utterances processed in the current session. |
| `session_avg_score` | `float` | No | `previous_score` | Running average of all session scores. |
| `peak_negativity` | `float` | No | `previous_score` | Lowest score reached in the session so far. |
| `speaker` | `string` | No | `"caller"` | Speaker role (`"caller"` or `"agent"`). |

---

### 2.2 Response Schema (`ScoreResponse`)

```json
{
  "emotion": "disgust",
  "confidence": 0.85,
  "emotion_weight": -95.0,
  "effective_emotion_weight": -80.75,
  "previous_score": -70.0,
  "dampening_factor": 0.6711,
  "dampened_raw_score": -54.19,
  "score": -74.28,
  "call_health_score": -69.33,
  "sentiment_trend": "Escalating",
  "peak_negativity": -74.28,
  "turn_count": 5,
  "session_avg_score": -67.21,
  "escalation_triggered": true
}
```

---

## 3. Contextual Severity Emotion Weights (`EMOTION_WEIGHTS`)

### Positive Hierarchy ($+5.0$ to $+100.0$)
| Emotion | Weight ($W_{\text{raw}}$) | Emotion | Weight ($W_{\text{raw}}$) |
| :--- | :--- | :--- | :--- |
| `gratitude` | $+100.0$ | `excitement` | $+55.0$ |
| `relief` | $+95.0$ | `amusement` | $+35.0$ |
| `approval` | $+85.0$ | `pride` | $+15.0$ |
| `optimism` | $+80.0$ | `love` | $+10.0$ |
| `caring` | $+75.0$ | `desire` | $+5.0$ |
| `joy` | $+70.0$ | | |
| `admiration` | $+65.0$ | | |

### Support Call Inquiry / Neutral Hierarchy
| Emotion | Weight ($W_{\text{raw}}$) | Description |
| :--- | :--- | :--- |
| `surprise` | $0.0$ | Neutral baseline for support questions |
| `curiosity` | $-10.0$ | Mild friction / inquiry sentiment |
| `neutral` / unknown | $0.0$ | Neutral baseline |

### Negative Hierarchy ($-15.0$ to $-100.0$)
| Emotion | Weight ($W_{\text{raw}}$) | Emotion | Weight ($W_{\text{raw}}$) |
| :--- | :--- | :--- | :--- |
| `anger` | $-100.0$ | `annoyance` | $-70.0$ |
| `disgust` | $-95.0$ | `fear` | $-65.0$ |
| `grief` | $-90.0$ | `remorse` | $-55.0$ |
| `sadness` | $-85.0$ | `nervousness` | $-45.0$ |
| `disappointment` | $-80.0$ | `embarrassment` | $-35.0$ |
| `disapproval` | $-75.0$ | `confusion` | $-25.0$ |
| | | `realization` | $-15.0$ |

---

## 4. Execution & Testing

```bash
cd service-score
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```
