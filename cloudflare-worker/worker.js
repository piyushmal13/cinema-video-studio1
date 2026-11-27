const CONTEXT_TTL_SECONDS = 30 * 24 * 60 * 60;
const MAX_CONTEXT_PROMPTS = 4;
const MAX_PROMPT_LENGTH = 3500;

async function sendMessage(env, chatId, text) {
  if (!env.TELEGRAM_BOT_TOKEN) {
    throw new Error("TELEGRAM_BOT_TOKEN is not configured.");
  }
  const response = await fetch(
    `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    }
  );
  if (!response.ok) {
    throw new Error(`Telegram sendMessage failed with status ${response.status}.`);
  }
}


function getReferenceAttachment(message) {
  const photo = Array.isArray(message.photo) && message.photo.length
    ? message.photo[message.photo.length - 1]
    : null;
  const candidate = photo
    ? { file_id: photo.file_id, file_unique_id: photo.file_unique_id, kind: "image", mime_type: "image/jpeg", file_size: photo.file_size }
    : message.video
      ? { ...message.video, kind: "video", mime_type: message.video.mime_type || "video/mp4" }
      : message.document && /^(image\/|video\/)/i.test(message.document.mime_type || "")
        ? { ...message.document, kind: (message.document.mime_type || "").startsWith("image/") ? "image" : "video" }
        : null;
  if (!candidate || !candidate.file_id) return null;
  const mime = String(candidate.mime_type || "").toLowerCase();
  if (!["image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"].includes(mime)) {
    return { error: "Unsupported reference format. Send JPG, PNG, WEBP or MP4." };
  }
  if (Number(candidate.file_size || 0) > 20 * 1024 * 1024) {
    return { error: "Reference file is larger than Telegram's 20 MB download limit for this workflow." };
  }
  return {
    file_id: candidate.file_id,
    file_unique_id: candidate.file_unique_id || "",
    kind: candidate.kind,
    mime_type: mime,
    file_name: candidate.file_name || "",
    file_size: Number(candidate.file_size || 0),
  };
}

function stripCommand(text) {
  return text.replace(/^\/(?:video|movie|cinema|reel)(?:@\w+)?\s*/i, "").trim();
}

function isFollowUp(text) {
  return /^(?:(?:and|also|now)\s+)?(?:make it|change it|keep it|add to it|remove from it|make that|change that|same(?: story| style| format)?|continue|revise|shorter|longer|more\b|less\b|use the same)\b/i.test(
    text.trim()
  ) || /\b(?:the previous video|that video|the last one|same story)\b/i.test(text);
}

function getHistory(value) {
  if (!value) {
    return [];
  }
  const parsed = JSON.parse(value);
  return Array.isArray(parsed.prompts)
    ? parsed.prompts
        .map((item) =>
          typeof item === "string"
            ? {
                text: item,
                format: /\/(?:movie|cinema)|--(?:movie|cinema|landscape)|\b(?:landscape|widescreen|16\s*:\s*9)\b/i.test(
                  item
                )
                  ? "landscape"
                  : "vertical",
              }
            : item
        )
        .filter(
          (item) =>
            item &&
            typeof item.text === "string" &&
            ["vertical", "landscape"].includes(item.format)
        )
        .slice(-MAX_CONTEXT_PROMPTS)
    : [];
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Ifxreelsm_bot Cinema Bridge Online");
    }

    const update = await request.json();
    const message = update.message;
    if (!message) {
      return new Response("OK");
    }

    const chatId = String(message.chat.id);
    if (env.ALLOWED_CHAT_ID && chatId !== String(env.ALLOWED_CHAT_ID)) {
      return new Response("Unauthorized", { status: 403 });
    }

    const text = (message.text || message.caption || "").trim();
    const reference = getReferenceAttachment(message);
    if (reference?.error) {
      await sendMessage(env, chatId, reference.error);
      return new Response("Unsupported reference attachment", { status: 415 });
    }
    if (!text && !reference) {
      await sendMessage(env, chatId, "Send a video idea, or attach a reference photo/video with a caption describing what to create.");
      return new Response("Text or reference required", { status: 400 });
    }

    if (/^\/(?:id|start|help)(?:@\w+)?$/i.test(text)) {
      if (/^\/id(?:@\w+)?$/i.test(text)) {
        await sendMessage(env, chatId, `Your Telegram Chat ID is: ${chatId}`);
      } else {
        await sendMessage(
          env,
          chatId,
          "Cinema AI Film Studio\n\n" +
            "Send any topic, story, or full script. The director understands natural requests for video shape, runtime, language, narration voice, brand, color, tone, and audience.\n\n" +
            "Examples:\n" +
            "/video A 45-second vertical explainer about how solar panels work, warm documentary tone\n" +
            "/movie A 90-second widescreen Hindi film about India's space program\n" +
            "/video --female --brand=IFXTRADES --color=#D4AF37 Explain compound interest\n\n" +
            "Send a short follow-up such as 'make it more emotional' to refine the last request. Use /forget to clear saved context."
        );
      }
      return new Response("Command handled");
    }

    if (/^\/forget(?:@\w+)?$/i.test(text)) {
      if (env.PROMPT_CONTEXT_KV) {
        await env.PROMPT_CONTEXT_KV.delete(`chat:${chatId}`);
      }
      await sendMessage(
        env,
        chatId,
        env.PROMPT_CONTEXT_KV
          ? "Saved prompt context cleared."
          : "Prompt memory is not configured; no saved context was available."
      );
      return new Response("Context cleared");
    }

    const prompt = stripCommand(text) || (
      reference?.kind === "image"
        ? "Create an original video using the attached reference image as a visual asset. Understand its subject and composition, preserve important details, and build a relevant story around it."
        : "Create an original video guided by the attached reference footage. Analyze its editing rhythm, shot structure, framing and visual mood; do not copy its footage or audio."
    );
    const requestId = crypto.randomUUID();
    if (!prompt) {
      await sendMessage(env, chatId, "Add a topic, story, or script after the command.");
      return new Response("Prompt required", { status: 400 });
    }
    if (prompt.length > MAX_PROMPT_LENGTH) {
      await sendMessage(env, chatId, "Prompts must be 4,000 characters or fewer.");
      return new Response("Prompt too long", { status: 413 });
    }
    if (!env.GITHUB_REPO || !env.GITHUB_PAT) {
      await sendMessage(env, chatId, "The video pipeline is not configured yet. Please contact the bot owner.");
      return new Response("GitHub dispatch is not configured", { status: 503 });
    }

    let previousPrompts = [];
    let contextNotice = "";
    if (env.PROMPT_CONTEXT_KV) {
      try {
        const saved = await env.PROMPT_CONTEXT_KV.get(`chat:${chatId}`);
        previousPrompts = getHistory(saved);
      } catch (error) {
        console.error("Could not read Telegram prompt context.", error);
        contextNotice = "\nSaved context could not be read; this request is standalone.";
      }
    }
    const useContext = isFollowUp(prompt) && previousPrompts.length > 0;
    const promptContext = useContext
      ? previousPrompts.map((item) => item.text).join("\n")
      : "";
    const asksLandscape = /^\/(?:movie|cinema)\b/i.test(text) ||
      /--(?:movie|cinema|landscape)\b|\b(?:landscape|widescreen|horizontal|16\s*:\s*9)\b/i.test(prompt);
    const asksVertical = /^\/reel(?:@\w+)?\b/i.test(text) ||
      /--(?:portrait|vertical|reel)\b|\b(?:portrait|vertical|9\s*:\s*16|reel|shorts?)\b/i.test(prompt);
    const format = asksLandscape
      ? "landscape"
      : asksVertical
        ? "vertical"
        : useContext
          ? previousPrompts[previousPrompts.length - 1].format
          : "vertical";

    const response = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_PAT}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "Ifxreelsm-Cinema-Bridge",
        },
        body: JSON.stringify({
          event_type: "telegram_video_request",
          client_payload: {
            text: prompt,
            format,
            chat_id: chatId,
            prompt_context: promptContext,
            request_id: requestId,
            reference_file_id: reference?.file_id || "",
            reference_file_unique_id: reference?.file_unique_id || "",
            reference_kind: reference?.kind || "",
            reference_mime_type: reference?.mime_type || "",
            reference_file_name: reference?.file_name || "",
          },
        }),
      }
    );
    if (!response.ok) {
      await sendMessage(
        env,
        chatId,
        `The render could not be queued (GitHub returned ${response.status}). Please try again later.`
      );
      return new Response("GitHub dispatch failed", { status: 502 });
    }

    if (env.PROMPT_CONTEXT_KV) {
      const nextPrompts = useContext
        ? [...previousPrompts, { text: prompt, format }].slice(-MAX_CONTEXT_PROMPTS)
        : [{ text: prompt, format }];
      try {
        await env.PROMPT_CONTEXT_KV.put(
          `chat:${chatId}`,
          JSON.stringify({ prompts: nextPrompts, updatedAt: new Date().toISOString() }),
          { expirationTtl: CONTEXT_TTL_SECONDS }
        );
      } catch (error) {
        console.error("Could not save Telegram prompt context.", error);
        contextNotice = "\nThis video was queued, but its context could not be saved.";
      }
    } else {
      contextNotice = "\nContext memory is not configured, so follow-ups will be standalone.";
    }

    await sendMessage(
      env,
      chatId,
      `Production queued (${format === "landscape" ? "16:9 widescreen" : "9:16 vertical"}).\n\n` +
        `Brief: ${prompt.slice(0, 600)}${prompt.length > 600 ? "..." : ""}\n\n` +
        (reference ? "The reference attachment will guide the visual style and image treatment. " : "") +
        "The render includes narrated voice, word-timed captions, a free generated score, and scene transition sounds. " +
        "The finished MP4 will be sent here when the GitHub Actions render completes." +
        contextNotice
    );
    return new Response("Dispatched");
  },
};
