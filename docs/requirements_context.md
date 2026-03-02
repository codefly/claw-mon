## Requirements

I want a web application I can use to drill into my usage of openclaw. 
Speifically I want to see how much model usage I'm doing, and I want to be able to understand the types of tasks I'm doing that actually burn tokens.

I want to be able to look by agent, by model, by day, by conversation etc.

I'm thinking in order to get the context about what the conversation is about, we may need to run the logs through an LLM to get that context and enrich the data.

## OpenClaw Token Usage Data Specification

Data Source

• Root Directory: ~/.openclaw/agents/
• File Pattern: ~/.openclaw/agents/<agent_id>/sessions/<session_id>.jsonl

Data Structure

The session files are JSONL (one JSON object per line). Usage data is reported every time an agent generates a response.

Target Object Logic

To calculate usage, the application must parse each .jsonl file and filter for lines where:

1. .type == "message"
2. .message.role == "assistant"

Field Mapping

| Metric        | JSON Path                  | Type    | Note                                   |
| ------------- | -------------------------- | ------- | -------------------------------------- |
| Agent Name    | N/A                        | String  | Derived from the parent directory name |
| Session ID    | N/A                        | String  | Derived from the filename              |
| Timestamp     | .timestamp                 | String  | ISO 8601 UTC                           |
| Model ID      | .message.model             | String  | e.g., claude-sonnet-4-6                |
| Provider      | .message.provider          | String  | e.g., anthropic                        |
| Input Tokens  | .message.usage.input       | Integer |                                        |
| Output Tokens | .message.usage.output      | Integer |                                        |
| Cache Read    | .message.usage.cacheRead   | Integer | Specific to Anthropic                  |
| Cache Write   | .message.usage.cacheWrite  | Integer | Specific to Anthropic                  |
| Total Tokens  | .message.usage.totalTokens | Integer | Aggregate of the above                 |
| USD Cost      | .message.usage.cost.total  | Float   | Pre-calculated by OpenClaw             |

Sample JSON Object

{
  "type": "message",
  "timestamp": "2026-03-02T22:23:08.995Z",
  "message": {
    "role": "assistant",
    "model": "claude-sonnet-4-6",
    "provider": "anthropic",
    "usage": {
      "input": 147608,
      "output": 240,
      "cacheRead": 50000,
      "cacheWrite": 1200,
      "totalTokens": 147848,
      "cost": { "total": 0.0448824 }
    }
  }
}

Parsing Requirements

• Recursion: The monitor must walk the ~/.openclaw/agents/ tree to find all active sessions.
• Incremental Loading: Files are appended to in real-time. The monitor should track file offsets to avoid re-parsing the entire history on every refresh.
• Grouping: Data should be aggregatable by Day (via timestamp), Agent ID, and Model.

───