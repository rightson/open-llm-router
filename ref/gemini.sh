source .env
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent" \
  -H 'Content-Type: application/json' \
  -H "X-goog-api-key: $GEMINI_API_KEY" \
  -X POST \
  -d '{
    "contents": [
      {
        "parts": [
          {
            "text": "Explain how AI works in a few words"
          }
        ]
      }
    ]
  }'
[{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "AI"
          }
        ],
        "role": "model"
      }
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 8,
    "totalTokenCount": 8,
    "promptTokensDetails": [
      {
        "modality": "TEXT",
        "tokenCount": 8
      }
    ]
  },
  "modelVersion": "gemini-2.0-flash",
  "responseId": "md2UaLXRCaKTmNAPrsSpgAo"
}
,
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": " learns patterns from data to make predictions or decisions.\n"
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP"
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 8,
    "candidatesTokenCount": 12,
    "totalTokenCount": 20,
    "promptTokensDetails": [
      {
        "modality": "TEXT",
        "tokenCount": 8
      }
    ],
    "candidatesTokensDetails": [
      {
        "modality": "TEXT",
        "tokenCount": 12
      }
    ]
  },
  "modelVersion": "gemini-2.0-flash",
  "responseId": "md2UaLXRCaKTmNAPrsSpgAo"
}
]