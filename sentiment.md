# Emotion Matrix Sentiment Analysis & Scoring Architecture

This document provides a comprehensive specification of the sentiment calculation logic, microservice request workflow, data structures, and mathematical formulas utilized in the Emotion Matrix platform.

---

## 1. Architectural Overview

The Emotion Matrix platform uses a microservices architecture to process real-time audio streams and chat text. 

- **Keyword Impact Removal**: Admin-configured keywords are used **strictly for phrase detection and UI text highlighting** (e.g., highlighting target phrases in red or green). Keyword impact weight modifiers have been removed to preserve pure model output integrity.
- **RoBERTa-Driven Sentiment**: Sentiment classification is performed by a fine-tuned RoBERTa Transformer model (`SamLowe/roberta-base-go_emotions`), outputting an emotion label and a model confidence score $C_i \in [0.0, 1.0]$.
- **Role-Based Chat Alignment**: Messages are styled according to speaker role:
  - **Agent Messages**: Positioned on the **RIGHT side** of the chat container.
  - **Caller Messages**: Positioned on the **LEFT side** of the chat container.

---

## 2. Sentiment Score Calculation & Formulas

### 2.1 Sentence-Level Score ($S_i$)

Each input sentence $i$ processed by the system receives a `sentiment_category` (`positive`, `negative`, or `neutral`) and a RoBERTa model `confidence` score $C_i$.

The individual **Sentence Sentiment Score** $S_i$ (ranging from $-100$ to $+100$) is computed as follows:

$$S_i = \begin{cases} +(C_i \times 100), & \text{if Category} = \text{positive} \\[6pt] -(C_i \times 100), & \text{if Category} = \text{negative} \\[6pt] 0, & \text{if Category} = \text{neutral} \end{cases}$$

#### Examples:
1. **Positive Sentence**: *"Thank you for your fantastic support!"*
   - RoBERTa Emotion: `gratitude` $\rightarrow$ Category: `positive`
   - Confidence $C = 0.9421$
   - $S_i = +(0.9421 \times 100) = +94.21 \approx +94$

2. **Negative Sentence**: *"I am extremely frustrated with this delay."*
   - RoBERTa Emotion: `annoyance` $\rightarrow$ Category: `negative`
   - Confidence $C = 0.8850$
   - $S_i = -(0.8850 \times 100) = -88.50 \approx -88$

3. **Neutral Sentence**: *"My account number is 48291."*
   - RoBERTa Emotion: `neutral` $\rightarrow$ Category: `neutral`
   - Confidence $C = 0.9100$
   - $S_i = 0$

---

### 2.2 Session Cumulative Aggregate Score ($S_{\text{aggregate}}$)

The Frontend maintains state for all sentences processed during an active monitoring session. As new sentences arrive from either the Agent or the Caller, the **Cumulative Aggregate Score** updates dynamically:

$$S_{\text{aggregate}} = \operatorname{round}\left( \frac{1}{N} \sum_{i=1}^{N} S_i \right)$$

where:
- $N$ is the total count of analyzed sentences in the conversation so far.
- $\sum_{i=1}^{N} S_i$ is the running sum of all sentence scores $S_i$.

#### Properties of Aggregate Calculation:
- **Range**: $-100\% \le S_{\text{aggregate}} \le +100\%$
- **Gauge Positioning**: The UI linear score gauge pointer position (in percentage $[5\%, 95\%]$) is derived via:
  $$\text{Pointer Position (\%)} = \min\left(95, \max\left(5, \frac{S_{\text{aggregate}} + 100}{200} \times 100\right)\right)$$

---

## 3. End-to-End Request Flow

![End-to-End Request Flow](resources/flow-diagram.png)

---

## 4. Phase Inputs & Outputs

### Phase 1: Client Request to API Gateway
- **Endpoint**: `POST /api/v1/process-message`
- **Input**:
```json
{
  "text": "I want to cancel my account immediately.",
  "speaker": "caller"
}
```

### Phase 2: Keyword Detection (`service-phrase`)
- **Endpoint**: `POST http://localhost:8002/extract-keywords`
- **Input**:
```json
{
  "text": "I want to cancel my account immediately."
}
```
- **Output**:
```json
{
  "matches": [
    {
      "keyword": "cancel account",
      "sentiment": "negative"
    }
  ]
}
```

### Phase 3: Sentiment & Emotion Analysis (`service-sentiment`)
- **Endpoint**: `POST http://localhost:8003/analyze-sentiment-batch`
- **Input**:
```json
{
  "items": [
    {
      "isolated_sentence": "I want to cancel my account immediately."
    }
  ]
}
```
- **Output**:
```json
{
  "results": [
    {
      "emotion": "annoyance",
      "sentiment_category": "negative",
      "confidence": 0.8742
    }
  ]
}
```

### Phase 4: Gateway Consolidated Response to Frontend
- **Output**:
```json
{
  "status": "success",
  "processing_time_ms": 14.52,
  "detected_issues": [
    {
      "isolated_sentence": "I want to cancel my account immediately.",
      "speaker": "caller",
      "phrase": "cancel account",
      "detected_keywords": [
        {
          "keyword": "cancel account",
          "sentiment": "negative"
        }
      ],
      "emotion": "annoyance",
      "sentiment_category": "negative",
      "confidence": 0.8742
    }
  ]
}
```

### Phase 5: Frontend Score Calculation & UI Rendering
1. **Sentence Score Calculation**:
   - $S_1 = -(0.8742 \times 100) = -87.42 \approx -87$
2. **Cumulative Average Score Update**:
   - New average score $S_{\text{aggregate}}$ is recomputed across all conversation messages.
3. **UI Layout Alignment**:
   - Speaker is `"caller"` $\rightarrow$ Rendered on **LEFT side** with `.chat-msg-caller` and `.bubble-caller`.
   - Admin keyword `"cancel account"` highlighted with red badge styling `.kw-highlight-red`.
