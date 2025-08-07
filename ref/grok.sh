source .env

curl https://api.x.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK_API_KEY" \
  -d '{
  "messages": [
    {
      "role": "system",
      "content": "You are a test assistant."
    },
    {
      "role": "user",
      "content": "Testing. Just say hi and hello world and nothing else."
    }
  ],
  "model": "grok-3-latest",
  "stream": false,
  "temperature": 0
}'
{
    "id": "1990daa4-8dc8-8d40-7896-c60e807a691b",
    "object": "chat.completion",
    "created": 1754584012,
    "model": "grok-3",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hi\nHello World",
                "refusal": null
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 28,
        "completion_tokens": 4,
        "total_tokens": 32,
        "prompt_tokens_details": {
            "text_tokens": 28,
            "audio_tokens": 0,
            "image_tokens": 0,
            "cached_tokens": 5
        },
        "completion_tokens_details": {
            "reasoning_tokens": 0,
            "audio_tokens": 0,
            "accepted_prediction_tokens": 0,
            "rejected_prediction_tokens": 0
        },
        "num_sources_used": 0
    },
    "system_fingerprint": "fp_0d42a4eb3d"
}