Chat-AI source update: online web search + NVIDIA default

Files in this archive are source replacements:
- assistant/support_ui.py
- assistant/cloud.py
- desktop_ui.py
- config.json
- work.js (Cloudflare Worker source)

Behavior changes:
- Cloudflare AI uses Worker-side Brave Search when Tìm web is enabled, including turns with attached document context.
- Other online API providers receive web page/source context from the existing desktop web-search module.
- New installs default to NVIDIA AI. Existing saved provider selections are preserved.

Deployment requirement:
Set BRAVE_SEARCH_API_KEY as a secret in the Cloudflare Worker environment, then deploy the updated work.js. The search feature reports a setup error if this secret is missing or invalid.
