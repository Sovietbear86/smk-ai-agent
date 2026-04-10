(function () {
  const DEFAULT_CONFIG = {
    apiUrl: "http://127.0.0.1:8000/chat",
    title: "SMK Performance Lab",
    subtitle: "Подбор настройки, запись на диностенд",
    primaryColor: "#111111",
    accentColor: "#e53935",
    position: "right",
    welcomeMessage:
      "Здравствуйте! Я помогу подобрать настройку, ответить по диностенду и записать вас на удобное время.",
    placeholder: "Введите сообщение...",
    sessionStorageKey: "smk_chat_session_id",
  };

  const userConfig = window.SMKChatWidgetConfig || {};
  const config = { ...DEFAULT_CONFIG, ...userConfig };

  function uuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function getSessionId() {
    let sessionId = localStorage.getItem(config.sessionStorageKey);
    if (!sessionId) {
      sessionId = uuid();
      localStorage.setItem(config.sessionStorageKey, sessionId);
    }
    return sessionId;
  }

  const sessionId = getSessionId();

  const style = document.createElement("style");
  style.innerHTML = `
    .smk-chat-launcher {
      position: fixed;
      bottom: 20px;
      ${config.position === "left" ? "left: 20px;" : "right: 20px;"}
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: ${config.accentColor};
      color: white;
      border: none;
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
      cursor: pointer;
      z-index: 999999;
      font-size: 24px;
    }

    .smk-chat-widget {
      position: fixed;
      bottom: 95px;
      ${config.position === "left" ? "left: 20px;" : "right: 20px;"}
      width: 360px;
      max-width: calc(100vw - 24px);
      height: 600px;
      max-height: calc(100vh - 120px);
      background: #fff;
      border-radius: 18px;
      box-shadow: 0 14px 50px rgba(0,0,0,0.2);
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 999999;
      border: 1px solid #e5e7eb;
      font-family: Inter, Arial, sans-serif;
    }

    .smk-chat-header {
      background: ${config.primaryColor};
      color: #fff;
      padding: 16px;
    }

    .smk-chat-title {
      font-size: 16px;
      font-weight: 700;
      margin: 0;
    }

    .smk-chat-subtitle {
      font-size: 12px;
      opacity: 0.85;
      margin-top: 4px;
    }

    .smk-chat-messages {
      flex: 1;
      padding: 14px;
      overflow-y: auto;
      background: #f7f7f8;
    }

    .smk-chat-row {
      display: flex;
      margin-bottom: 12px;
    }

    .smk-chat-row.user {
      justify-content: flex-end;
    }

    .smk-chat-row.assistant {
      justify-content: flex-start;
    }

    .smk-chat-bubble {
      max-width: 82%;
      padding: 10px 12px;
      border-radius: 14px;
      font-size: 14px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-wrap: break-word;
    }

    .smk-chat-row.user .smk-chat-bubble {
      background: ${config.accentColor};
      color: #fff;
      border-bottom-right-radius: 6px;
    }

    .smk-chat-row.assistant .smk-chat-bubble {
      background: #fff;
      color: #111827;
      border: 1px solid #e5e7eb;
      border-bottom-left-radius: 6px;
    }

    .smk-chat-quick-replies {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 8px 0 14px 0;
    }

    .smk-chat-chip {
      border: 1px solid #d1d5db;
      background: #fff;
      color: #111827;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      cursor: pointer;
    }

    .smk-chat-chip:hover {
      border-color: ${config.accentColor};
      color: ${config.accentColor};
    }

    .smk-chat-slots {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 12px;
    }

    .smk-chat-slot {
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid #d1d5db;
      background: #fff;
      cursor: pointer;
      font-size: 14px;
      text-align: left;
    }

    .smk-chat-slot:hover {
      border-color: ${config.accentColor};
    }

    .smk-chat-input-wrap {
      border-top: 1px solid #e5e7eb;
      padding: 12px;
      background: #fff;
      display: flex;
      gap: 8px;
    }

    .smk-chat-input {
      flex: 1;
      border: 1px solid #d1d5db;
      border-radius: 12px;
      padding: 12px;
      font-size: 14px;
      outline: none;
    }

    .smk-chat-input:focus {
      border-color: ${config.accentColor};
    }

    .smk-chat-send {
      border: none;
      background: ${config.accentColor};
      color: #fff;
      border-radius: 12px;
      padding: 0 16px;
      cursor: pointer;
      font-weight: 600;
    }

    .smk-chat-typing {
      font-size: 12px;
      color: #6b7280;
      padding: 4px 2px 10px 2px;
    }

    @media (max-width: 480px) {
      .smk-chat-widget {
        width: calc(100vw - 16px);
        right: 8px !important;
        left: 8px !important;
        bottom: 80px;
        height: calc(100vh - 100px);
      }

      .smk-chat-launcher {
        right: 16px !important;
        left: auto !important;
        bottom: 16px;
      }
    }
  `;
  document.head.appendChild(style);

  const launcher = document.createElement("button");
  launcher.className = "smk-chat-launcher";
  launcher.innerHTML = "💬";

  const widget = document.createElement("div");
  widget.className = "smk-chat-widget";
  widget.innerHTML = `
    <div class="smk-chat-header">
      <div class="smk-chat-title">${config.title}</div>
      <div class="smk-chat-subtitle">${config.subtitle}</div>
    </div>
    <div class="smk-chat-messages" id="smk-chat-messages"></div>
    <div class="smk-chat-input-wrap">
      <input class="smk-chat-input" id="smk-chat-input" type="text" placeholder="${config.placeholder}" />
      <button class="smk-chat-send" id="smk-chat-send">→</button>
    </div>
  `;

  document.body.appendChild(launcher);
  document.body.appendChild(widget);

  const messagesEl = widget.querySelector("#smk-chat-messages");
  const inputEl = widget.querySelector("#smk-chat-input");
  const sendBtn = widget.querySelector("#smk-chat-send");

  let isOpen = false;
  let isSending = false;
  let initialized = false;

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, text) {
    const row = document.createElement("div");
    row.className = `smk-chat-row ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "smk-chat-bubble";
    bubble.textContent = text;

    row.appendChild(bubble);
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function addTyping() {
    const el = document.createElement("div");
    el.className = "smk-chat-typing";
    el.id = "smk-chat-typing";
    el.textContent = "Печатает...";
    messagesEl.appendChild(el);
    scrollToBottom();
  }

  function removeTyping() {
    const el = document.getElementById("smk-chat-typing");
    if (el) el.remove();
  }

  function clearInteractiveBlocks() {
    const blocks = messagesEl.querySelectorAll(".smk-chat-quick-replies, .smk-chat-slots");
    blocks.forEach((b) => b.remove());
  }

  function renderQuickReplies(items) {
    if (!Array.isArray(items) || !items.length) return;

    const wrap = document.createElement("div");
    wrap.className = "smk-chat-quick-replies";

    items.forEach((item) => {
      const btn = document.createElement("button");
      btn.className = "smk-chat-chip";
      btn.textContent = item.label;
      btn.onclick = () => sendMessage(item.value || item.label);
      wrap.appendChild(btn);
    });

    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function renderSlots(slots) {
    if (!Array.isArray(slots) || !slots.length) return;

    const wrap = document.createElement("div");
    wrap.className = "smk-chat-slots";

    slots.forEach((slot) => {
      const btn = document.createElement("button");
      btn.className = "smk-chat-slot";
      btn.textContent = slot.label || `${slot.date} ${slot.time}`;
      btn.onclick = () => sendMessage(slot.value || slot.label || `${slot.date} ${slot.time}`);
      wrap.appendChild(btn);
    });

    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  async function sendMessage(text) {
    const message = (text || inputEl.value).trim();
    if (!message || isSending) return;

    clearInteractiveBlocks();
    addMessage("user", message);
    inputEl.value = "";
    isSending = true;
    addTyping();

    try {
      const response = await fetch(config.apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          session_id: sessionId,
          source: "website_widget",
        }),
      });

      const rawText = await response.text();
      let data = null;

      try {
        data = rawText ? JSON.parse(rawText) : null;
      } catch (parseError) {
        console.error("SMK widget: response is not valid JSON", {
          status: response.status,
          rawText,
        });
      }

      removeTyping();

      if (!response.ok) {
        console.error("SMK widget backend error:", {
          status: response.status,
          statusText: response.statusText,
          body: rawText,
        });

        const backendMessage =
          data?.reply ||
          data?.detail ||
          "Сервис временно недоступен. Попробуйте еще раз чуть позже.";

        addMessage("assistant", backendMessage);
        return;
      }

      addMessage("assistant", data?.reply || "Извините, не удалось получить ответ.");

      if (Array.isArray(data?.quick_replies)) {
        renderQuickReplies(data.quick_replies);
      }

      if (Array.isArray(data?.slots)) {
        renderSlots(data.slots);
      }
    } catch (error) {
      removeTyping();
      addMessage(
        "assistant",
        "Не удалось связаться с сервером. Проверьте соединение или попробуйте еще раз."
      );
      console.error("SMK widget network error:", error);
    } finally {
      isSending = false;
    }
  }

  function initChat() {
    if (initialized) return;
    initialized = true;
    addMessage("assistant", config.welcomeMessage);
    renderQuickReplies([
      { label: "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430", value: "\u0418\u043d\u0442\u0435\u0440\u0435\u0441\u0443\u0435\u0442 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 ECU" },
      { label: "\u0417\u0430\u043c\u0435\u0440", value: "\u0418\u043d\u0442\u0435\u0440\u0435\u0441\u0443\u0435\u0442 \u0437\u0430\u043c\u0435\u0440 \u043d\u0430 \u0434\u0438\u043d\u043e\u0441\u0442\u0435\u043d\u0434\u0435" },
      { label: "\u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u044f", value: "\u041d\u0443\u0436\u043d\u0430 \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u044f" },
    ]);
  }

  launcher.addEventListener("click", () => {
    isOpen = !isOpen;
    widget.style.display = isOpen ? "flex" : "none";
    if (isOpen) {
      initChat();
      inputEl.focus();
    }
  });

  sendBtn.addEventListener("click", () => sendMessage());

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  });
})()