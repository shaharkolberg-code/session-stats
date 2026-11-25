# Chat Sorter

Sorts exported WhatsApp chats into **exams, study material, scheduled plans, to-dos, money, links, files and places**, and puts dated items on a timeline.

- **Keyword sorting** (English and Hebrew) runs in the browser. Nothing is uploaded.
- **Sort with AI**: Claude re-sorts the messages and works out dates like "next Thursday". It runs through a Netlify Function, so your API key never reaches the browser.
- **Calendar**: download upcoming items as an `.ics` file, or add single items with an "Add to Google Calendar" link.
- **Saved chats**: uploaded chats and AI results are kept in the browser (IndexedDB) until you press "Forget saved chats".

## Getting chats out of WhatsApp

WhatsApp has no API for personal chats, so you export them yourself:

- **Android:** chat → ⋮ → More → Export chat → Without media
- **iPhone:** chat → tap the chat name → Export Chat → Without Media

Upload the `.txt` or `.zip` file in the app. You can upload several chats at once.

## Deploy to Netlify

1. In Netlify, choose **Add new site → Import an existing project** and pick this repository.
   The `netlify.toml` at the repo root already sets everything up (base `chat-sorter`, publish `public`, functions `netlify/functions`), so leave the build settings empty.
2. Under **Site configuration → Environment variables**, add:
   - `ANTHROPIC_API_KEY`: your key from https://console.anthropic.com
   - `APP_PASSWORD`: any password. **Recommended.** Without it, anyone who finds your site URL can spend your API credits.
3. Deploy. Open the site: the "Sort with AI" panel should say **Connected**.

The site works without the API key too. AI sorting just stays off.

## Cost

AI sorting sends messages in batches of 30 to `claude-opus-5-5` at low effort. You choose the date range before running (default: last 90 days). Messages that were already sorted are skipped, because results are saved in the browser.

If a batch trips a safety filter, the function uses the API's server-side fallback (`fallbacks: "default"`), which retries the batch on another model.

## Files

| Path | What it is |
|---|---|
| `public/index.html` | The whole app (HTML, CSS, JS). Loads JSZip from cdnjs to read `.zip` exports. |
| `netlify/functions/classify.mjs` | `GET /api/classify` reports whether AI is set up; `POST /api/classify` sorts up to 40 messages. |
| `package.json` | Pins `@anthropic-ai/sdk` for the function. |

## Run locally

```bash
npm install -g netlify-cli
cd chat-sorter && npm install
ANTHROPIC_API_KEY=sk-ant-... netlify dev
```
