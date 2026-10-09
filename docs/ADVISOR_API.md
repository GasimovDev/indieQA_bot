# Fix Advisor API setup

The dashboard uses the deterministic local advisor by default. To enable the remote OpenAI-compatible Responses API, configure a key outside Git and restart Streamlit.

Groq is supported directly through its OpenAI-compatible Responses endpoint:

```powershell
$env:GROQ_API_KEY = 'gsk-...'
$env:GROQ_MODEL = 'openai/gpt-oss-20b'
streamlit run dashboard/app.py
```

PowerShell session setup:

```powershell
$env:OPENAI_API_KEY = 'sk-...'
$env:OPENAI_MODEL = 'gpt-4.1-mini'
streamlit run dashboard/app.py
```

For a persistent local Streamlit setup, create `.streamlit/secrets.toml` (it is ignored by Git):

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1-mini"
```

The optional `OPENAI_RESPONSES_URL` setting can point to another Responses-compatible endpoint. `GROQ_RESPONSES_URL`, `ADVISOR_API_KEY`, `ADVISOR_API_URL`, `ADVISOR_MODEL`, and `ADVISOR_TIMEOUT_SECONDS` are also supported.

The terminal smoke-test script uses the same backend selection as the dashboard:

```powershell
python scripts/chatbot_api.py --bug-type "Wall Clip" --question "How can we fix it?"
```

If no key is configured, both the dashboard and script use the local rules advisor. If a configured API request fails, the dashboard reports the API status and answers that question locally instead. Never commit a real key or paste one into source files.
