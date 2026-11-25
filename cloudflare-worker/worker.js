export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("Ifxreelsm_bot Cinema Bridge Online");
    const update = await request.json();
    const msg = update.message;
    if (!msg || !msg.text) return new Response("OK");

    const chatId = String(msg.chat.id);
    const rawText = msg.text.trim();

    if (rawText === "/id") {
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text: `Your Telegram Chat ID is: \`${chatId}\``,
          parse_mode: "Markdown",
        }),
      });
      return new Response("ID Sent");
    }

    if (env.ALLOWED_CHAT_ID && chatId !== String(env.ALLOWED_CHAT_ID)) {
      return new Response("Unauthorized", { status: 403 });
    }

    if (rawText === "/start" || rawText === "/help") {
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text:
            "🎬 *Cinema AI Film & Reels Studio (@Ifxreelsm_bot)*\n\n" +
            "Send any idea, story, or full script from your phone:\n\n" +
            "• `/video How institutional algorithms hunt gold liquidity` *(9:16 Vertical Reel)*\n" +
            "• `/movie The rise of autonomous AI empires` *(16:9 Widescreen Mini-Film with Letterbox & Score)*\n" +
            "• `/video --hindi --brand=IFXTRADES Smart money concept explained`\n" +
            "• `/movie --hindi --brand=VILLAPARTIES Midnight supercar lifestyle`",
          parse_mode: "Markdown",
        }),
      });
      return new Response("Help Sent");
    }

    const isMovie = /^\/movie/i.test(rawText) || /--movie|--cinema|--landscape/i.test(rawText);
    let cleanPrompt = rawText
      .replace(/^\/(video|movie)\s*/i, "")
      .replace(/--landscape/gi, "")
      .trim();

    if (isMovie && !/--movie|--cinema/i.test(cleanPrompt)) {
      cleanPrompt = `--movie ${cleanPrompt}`;
    }

    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: `🎬 *Production Started* (${isMovie ? "16:9 Cinema Film" : "9:16 Vertical Reel"})\n\n📝 *Brief:* ${cleanPrompt.replace(/--movie/gi, "").trim()}\n⚙️ *Pipeline:* AI Director → HD B-Roll/AI Visuals → Neural Voice + Cinema Score → 3D/2D Render\n\nYour mastered MP4 will drop here in ~2–3 minutes.`,
        parse_mode: "Markdown",
      }),
    });

    await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "Ifxreelsm-Cinema-Bridge",
      },
      body: JSON.stringify({
        event_type: "telegram_video_request",
        client_payload: {
          text: cleanPrompt,
          format: isMovie ? "landscape" : "vertical",
          chat_id: chatId,
        },
      }),
    });

    return new Response("Dispatched");
  },
};
