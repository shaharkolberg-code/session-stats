// Netlify Function: sorts a batch of chat messages into categories with Claude.
// The browser sends at most MAX_MESSAGES messages per call; the API key stays on the server.
//
// Environment variables (Netlify → Site configuration → Environment variables):
//   ANTHROPIC_API_KEY  required. Your Claude API key.
//   APP_PASSWORD       optional but recommended. If set, the page must send it, so strangers
//                      who find your site URL cannot spend your API credits.
import Anthropic from "@anthropic-ai/sdk";

const MODEL = "claude-opus-5-5";
const MAX_MESSAGES = 40;
const MAX_CHARS = 2000; // per message; longer messages are cut before sending
const CATEGORIES = ["exam", "material", "scheduled", "task", "money", "place", "other"];

const SYSTEM = `You sort WhatsApp messages for a university student so they can find what matters.
Messages may be in Hebrew, English, or a mix.

For every message, pick one or more categories:
- exam: an exam, test, quiz, moed (מועד), grade, or studying for one.
- material: study material: summaries, notes, slides, lecture recordings, homework, assignments, past exams, solutions.
- scheduled: a meeting, appointment, call, class, event, party, meal or any plan at a specific time.
- task: something someone needs to do: a request, a deadline, a submission, a reminder.
- money: payments, prices, splitting costs, transfers, debts.
- place: an address or location to go to.
- other: small talk, reactions, greetings, anything not above. Use "other" only on its own.

If the message refers to a specific day for an exam, plan, deadline or event, resolve it to an absolute date
(YYYY-MM-DD) using the message's own timestamp for words like "tomorrow", "מחר", "Thursday", "יום שלישי".
Give the time as HH:MM (24h) if one is stated, otherwise "". If no specific day is meant, date is "".
Give a short calendar title (max 60 characters) in the message's language, e.g. "Calculus 2 midterm, room 204".
If the message has no date, title is "".`;

const SCHEMA = {
  type: "object",
  properties: {
    items: {
      type: "array",
      items: {
        type: "object",
        properties: {
          i: { type: "integer" },
          categories: { type: "array", items: { type: "string", enum: CATEGORIES } },
          date: { type: "string" },
          time: { type: "string" },
          title: { type: "string" },
        },
        required: ["i", "categories", "date", "time", "title"],
        additionalProperties: false,
      },
    },
  },
  required: ["items"],
  additionalProperties: false,
};

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export default async (req) => {
  const hasKey = !!process.env.ANTHROPIC_API_KEY;
  const password = process.env.APP_PASSWORD || "";

  if (req.method === "GET") {
    return json(200, {
      ok: hasKey,
      needsPassword: !!password,
      reason: hasKey ? "" : "ANTHROPIC_API_KEY is not set on the Netlify site.",
    });
  }
  if (req.method !== "POST") return json(405, { error: "Use POST." });
  if (!hasKey) return json(500, { error: "ANTHROPIC_API_KEY is not set on the Netlify site." });
  if (password && req.headers.get("x-app-password") !== password) {
    return json(401, { error: "Wrong or missing app password." });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json(400, { error: "Body must be JSON." });
  }
  const messages = Array.isArray(body?.messages) ? body.messages : [];
  if (!messages.length) return json(400, { error: "No messages sent." });
  if (messages.length > MAX_MESSAGES) return json(400, { error: `Send at most ${MAX_MESSAGES} messages per request.` });

  const lines = messages.map((m) => ({
    i: Number(m.i),
    chat: String(m.chat ?? "").slice(0, 100),
    sender: String(m.sender ?? "").slice(0, 100),
    sent: String(m.ts ?? "").slice(0, 40),
    text: String(m.text ?? "").slice(0, MAX_CHARS),
  }));

  const client = new Anthropic();
  try {
    const response = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 8000,
      system: SYSTEM,
      output_config: {
        effort: "low",
        format: { type: "json_schema", schema: SCHEMA },
      },
      // If a message trips a safety filter, the API retries on a fallback model automatically.
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      messages: [
        {
          role: "user",
          content: `Sort these messages. Return one item per message, using its "i".\n\n${JSON.stringify(lines)}`,
        },
      ],
    });

    if (response.stop_reason === "refusal") {
      return json(422, { error: "Claude declined to sort this batch.", items: [] });
    }
    if (response.stop_reason === "max_tokens") {
      return json(502, { error: "The answer was cut off. Try a smaller batch." });
    }
    const text = response.content
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("");
    const parsed = JSON.parse(text);
    const valid = new Set(lines.map((l) => l.i));
    const items = (parsed.items || [])
      .filter((it) => valid.has(it.i))
      .map((it) => ({
        i: it.i,
        categories: (it.categories || []).filter((c) => CATEGORIES.includes(c)),
        date: /^\d{4}-\d{2}-\d{2}$/.test(it.date) ? it.date : "",
        time: /^\d{1,2}:\d{2}$/.test(it.time) ? it.time : "",
        title: String(it.title || "").slice(0, 80),
      }));
    return json(200, { items });
  } catch (err) {
    if (err instanceof Anthropic.AuthenticationError) return json(500, { error: "The API key on the Netlify site was rejected." });
    if (err instanceof Anthropic.RateLimitError) return json(429, { error: "Rate limited by the Claude API. Wait a minute and try again." });
    if (err instanceof Anthropic.APIError) return json(502, { error: `Claude API error ${err.status ?? ""}: ${err.message}` });
    if (err instanceof SyntaxError) return json(502, { error: "Could not read Claude's answer." });
    return json(500, { error: "Unexpected server error." });
  }
};

export const config = { path: "/api/classify" };
