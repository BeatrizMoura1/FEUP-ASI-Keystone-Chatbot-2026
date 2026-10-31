const threadScroll = document.getElementById("thread-scroll");
const thread = document.getElementById("thread");
const welcome = document.getElementById("welcome");
const askForm = document.getElementById("ask-form");
const questionInput = document.getElementById("question-input");
const askButton = document.getElementById("ask-button");
const drawer = document.getElementById("drawer");
const sidebar = document.getElementById("sidebar");
const historyBox = document.getElementById("history");
const NO_ANSWER_TEXT = "No answer found.";
const CONVERSATION_HASH_PREFIX = "#chat-";

let isWaitingForAnswer = false;
let currentConversationId = null;
// Bumped every time the visible chat changes, so a late answer is not drawn into the wrong chat.
let viewVersion = 0;

const SUGGESTIONS_FOR_EVERYONE = [
  { question: "Can I work remotely from another country for a few weeks?", topic: "HR · Hybrid work" },
  { question: "What PPE do I need for a visit to a tunnel site?", topic: "Health & Safety" },
  { question: "Who has to sign off a calculation before it is issued to the client?", topic: "Quality · Deliverable review" },
  { question: "What actions came out of the last Linha Verde design review?", topic: "Project A · Linha Verde" },
];
const SUGGESTIONS_FOR_ADMINS = [
  SUGGESTIONS_FOR_EVERYONE[0],
  SUGGESTIONS_FOR_EVERYONE[3],
  { question: "When is the Costa Norte tender due, and what are our win themes?", topic: "Project B · Offshore wind bid" },
  { question: "What should I do if I lose my laptop?", topic: "IT Security" },
];

const ICONS = {
  document: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h5"/></svg>',
  thumbUp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z"/><path d="M7 10l4-7a2 2 0 0 1 3 2l-1 5h6a2 2 0 0 1 2 2.3l-1.4 7A2 2 0 0 1 17.6 21H7"/></svg>',
  thumbDown: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1z"/><path d="M17 14l-4 7a2 2 0 0 1-3-2l1-5H5a2 2 0 0 1-2-2.3l1.4-7A2 2 0 0 1 6.4 3H17"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6"/></svg>',
};

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function scrollToBottom() {
  threadScroll.scrollTop = threadScroll.scrollHeight;
}

/* ---------- Messages ---------- */

function clearThread() {
  thread.querySelectorAll(".row").forEach((row) => row.remove());
  welcome.hidden = false;
  drawer.classList.remove("open");
}

function addUserMessage(question) {
  welcome.hidden = true;
  const row = createElement("div", "row user");
  row.appendChild(createElement("div", "bubble", question));
  thread.appendChild(row);
  scrollToBottom();
}

function addBotRow() {
  welcome.hidden = true;
  const row = createElement("div", "row bot");
  const avatar = createElement("img", "logo");
  avatar.src = "/static/logo.svg";
  avatar.alt = "";
  const body = createElement("div", "bot-body");
  row.append(avatar, body);
  thread.appendChild(row);
  scrollToBottom();
  return { row, body };
}

function addTypingIndicator() {
  const { row, body } = addBotRow();
  const typing = createElement("div", "typing");
  typing.setAttribute("aria-label", "Searching documents");
  typing.innerHTML = "<span></span><span></span><span></span>";
  body.appendChild(typing);
  return row;
}

async function openDocument(documentId) {
  const response = await fetch(`/api/documents/${documentId}`);
  const projectBadge = document.getElementById("drawer-project");
  if (!response.ok) {
    document.getElementById("drawer-name").textContent = "Document unavailable";
    projectBadge.hidden = true;
    document.getElementById("drawer-content").textContent =
      "This document was deleted or you no longer have access to it.";
    drawer.classList.add("open");
    return;
  }
  const documentData = await response.json();
  document.getElementById("drawer-name").textContent = documentData.name;
  projectBadge.hidden = false;
  projectBadge.textContent = documentData.project === "GENERAL" ? "General" : `Project ${documentData.project}`;
  projectBadge.className = `badge project-${documentData.project}`;
  document.getElementById("drawer-content").textContent = documentData.content;
  drawer.classList.add("open");
}

function addRatingButtons(body, messageId, savedRating) {
  const actions = createElement("div", "actions");
  const feedbackNote = createElement("span", "feedback-note");
  const ratingButtons = [];
  for (const [iconSvg, label, isPositive] of [[ICONS.thumbUp, "Helpful", true], [ICONS.thumbDown, "Not helpful", false]]) {
    const ratingButton = createElement("button", "icon-button");
    ratingButton.type = "button";
    ratingButton.innerHTML = iconSvg;
    ratingButton.title = label;
    ratingButton.setAttribute("aria-label", label);
    ratingButton.classList.toggle("selected", savedRating === isPositive);
    ratingButton.onclick = async () => {
      const response = await fetch("/api/ratings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: messageId, is_positive: isPositive }),
      });
      if (!response.ok) { feedbackNote.textContent = "Could not save feedback"; return; }
      ratingButtons.forEach((button) => button.classList.toggle("selected", button === ratingButton));
      feedbackNote.textContent = "Thanks for your feedback";
    };
    ratingButtons.push(ratingButton);
    actions.appendChild(ratingButton);
  }
  actions.appendChild(feedbackNote);
  body.appendChild(actions);
}

function showAnswer(answerMessage) {
  const { body } = addBotRow();
  if (answerMessage.is_hidden) {
    const hiddenNotice = createElement("div", "answer hidden-answer");
    hiddenNotice.innerHTML = ICONS.lock;
    hiddenNotice.appendChild(createElement("span", "", answerMessage.content));
    body.appendChild(hiddenNotice);
    return;
  }
  const isNoAnswer = answerMessage.content.trim() === NO_ANSWER_TEXT;
  body.appendChild(createElement("div", isNoAnswer ? "answer no-answer" : "answer", answerMessage.content));
  if (answerMessage.sources.length) {
    const sources = createElement("div", "sources");
    for (const source of answerMessage.sources) {
      const sourceChip = createElement("button", "source-chip");
      sourceChip.type = "button";
      sourceChip.title = `Open ${source.name}`;
      sourceChip.innerHTML = ICONS.document;
      sourceChip.appendChild(createElement("span", "", source.name));
      sourceChip.onclick = () => openDocument(source.id);
      sources.appendChild(sourceChip);
    }
    body.appendChild(sources);
  }
  addRatingButtons(body, answerMessage.id, answerMessage.rating);
  scrollToBottom();
}

function showError(question, errorText) {
  const { row, body } = addBotRow();
  const errorCard = createElement("div", "error-card");
  errorCard.appendChild(createElement("span", "error-text", errorText));
  const retryButton = createElement("button", "danger-button", "Retry");
  retryButton.type = "button";
  retryButton.onclick = () => { row.remove(); ask(question, false); };
  errorCard.appendChild(retryButton);
  body.appendChild(errorCard);
  scrollToBottom();
}

/* ---------- Chat history ---------- */

function historyGroupLabel(updatedAt) {
  const updatedDate = new Date(updatedAt);
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const millisecondsPerDay = 86400000;
  if (updatedDate >= startOfToday) return "Today";
  if (updatedDate >= startOfToday - millisecondsPerDay) return "Yesterday";
  if (updatedDate >= startOfToday - 7 * millisecondsPerDay) return "Previous 7 days";
  return "Older";
}

async function loadHistory() {
  const response = await fetch("/api/conversations");
  if (!response.ok) return;
  const conversations = await response.json();
  historyBox.innerHTML = "";
  if (!conversations.length) {
    historyBox.appendChild(createElement("p", "history-empty", "Your chats will appear here."));
    return;
  }
  let previousGroupLabel = null;
  for (const conversation of conversations) {
    const groupLabel = historyGroupLabel(conversation.updated_at);
    if (groupLabel !== previousGroupLabel) {
      historyBox.appendChild(createElement("h4", "history-group", groupLabel));
      previousGroupLabel = groupLabel;
    }
    const historyItem = createElement("div", "history-item");
    historyItem.dataset.conversationId = conversation.id;
    historyItem.classList.toggle("active", conversation.id === currentConversationId);
    const openButton = createElement("button", "history-title", conversation.title);
    openButton.type = "button";
    openButton.title = conversation.title;
    openButton.onclick = () => openConversation(conversation.id);
    const deleteButton = createElement("button", "history-delete");
    deleteButton.type = "button";
    deleteButton.title = "Delete chat";
    deleteButton.setAttribute("aria-label", `Delete chat "${conversation.title}"`);
    deleteButton.innerHTML = ICONS.trash;
    deleteButton.onclick = () => deleteConversation(conversation.id, conversation.title);
    historyItem.append(openButton, deleteButton);
    historyBox.appendChild(historyItem);
  }
}

function markActiveConversation() {
  historyBox.querySelectorAll(".history-item").forEach((historyItem) => {
    historyItem.classList.toggle("active", Number(historyItem.dataset.conversationId) === currentConversationId);
  });
}

function setConversationInUrl(conversationId) {
  const newHash = conversationId === null ? "" : `${CONVERSATION_HASH_PREFIX}${conversationId}`;
  history.replaceState(null, "", `${location.pathname}${newHash}`);
}

function startNewChat() {
  viewVersion += 1;
  currentConversationId = null;
  setConversationInUrl(null);
  clearThread();
  markActiveConversation();
  closeSidebar();
  questionInput.focus();
}

async function openConversation(conversationId) {
  viewVersion += 1;
  const versionAtOpen = viewVersion;
  currentConversationId = conversationId;
  setConversationInUrl(conversationId);
  clearThread();
  welcome.hidden = true;
  markActiveConversation();
  closeSidebar();
  const response = await fetch(`/api/conversations/${conversationId}`);
  if (versionAtOpen !== viewVersion) return;
  if (!response.ok) { startNewChat(); return; }
  const conversation = await response.json();
  for (const message of conversation.messages) {
    if (message.role === "user") addUserMessage(message.content);
    else showAnswer(message);
  }
}

async function deleteConversation(conversationId, conversationTitle) {
  if (!confirm(`Delete the chat "${conversationTitle}"? This cannot be undone.`)) return;
  const response = await fetch(`/api/conversations/${conversationId}`, { method: "DELETE" });
  if (response.ok && conversationId === currentConversationId) startNewChat();
  loadHistory();
}

/* ---------- Asking ---------- */

function updateSendButton() {
  askButton.disabled = isWaitingForAnswer || !questionInput.value.trim();
}

function resizeInput() {
  questionInput.style.height = "auto";
  questionInput.style.height = `${questionInput.scrollHeight}px`;
}

async function ask(question, showQuestion = true) {
  const versionAtSend = viewVersion;
  if (showQuestion) addUserMessage(question);
  const typingRow = addTypingIndicator();
  isWaitingForAnswer = true;
  updateSendButton();
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, conversation_id: currentConversationId }),
    });
    if (response.status === 401) { window.location.href = "/login"; return; }
    const responseData = await response.json();
    typingRow.remove();
    if (versionAtSend !== viewVersion) { loadHistory(); return; }
    if (!response.ok) {
      showError(question, responseData.error || responseData.detail || "Request failed.");
      return;
    }
    if (currentConversationId === null) {
      currentConversationId = responseData.conversation_id;
      setConversationInUrl(currentConversationId);
    }
    showAnswer({ id: responseData.message_id, content: responseData.answer, sources: responseData.sources, rating: null });
    loadHistory();
  } catch (networkError) {
    typingRow.remove();
    if (versionAtSend === viewVersion) showError(question, `Could not reach the server: ${networkError}`);
  } finally {
    isWaitingForAnswer = false;
    updateSendButton();
  }
}

askForm.onsubmit = (submitEvent) => {
  submitEvent.preventDefault();
  const question = questionInput.value.trim();
  if (!question || isWaitingForAnswer) return;
  questionInput.value = "";
  resizeInput();
  ask(question);
};

questionInput.addEventListener("input", () => { resizeInput(); updateSendButton(); });
questionInput.addEventListener("keydown", (keyEvent) => {
  if (keyEvent.key === "Enter" && !keyEvent.shiftKey && !keyEvent.isComposing) {
    keyEvent.preventDefault();
    askForm.requestSubmit();
  }
});

/* ---------- Layout: drawer and mobile sidebar ---------- */

function closeSidebar() {
  sidebar.classList.remove("open");
}

document.getElementById("close-drawer").onclick = () => drawer.classList.remove("open");
document.getElementById("new-chat-button").onclick = startNewChat;
document.getElementById("menu-button").onclick = () => sidebar.classList.toggle("open");
document.getElementById("sidebar-backdrop").onclick = closeSidebar;
document.addEventListener("keydown", (keyEvent) => {
  if (keyEvent.key === "Escape") { drawer.classList.remove("open"); closeSidebar(); }
});

/* ---------- Start-up ---------- */

function showSuggestions(suggestions) {
  const suggestionsBox = document.getElementById("suggestions");
  suggestionsBox.innerHTML = "";
  for (const suggestion of suggestions) {
    const suggestionCard = createElement("button", "suggestion");
    suggestionCard.type = "button";
    suggestionCard.append(
      createElement("span", "suggestion-question", suggestion.question),
      createElement("span", "suggestion-topic", suggestion.topic),
    );
    suggestionCard.onclick = () => { if (!isWaitingForAnswer) ask(suggestion.question); };
    suggestionsBox.appendChild(suggestionCard);
  }
}

async function loadCurrentUser() {
  const response = await fetch("/api/me");
  if (!response.ok) { window.location.href = "/login"; return; }
  const currentUser = await response.json();
  document.getElementById("user-avatar").textContent = currentUser.username.charAt(0);
  document.getElementById("user-name").textContent = currentUser.username;
  document.getElementById("user-role").textContent = `· ${currentUser.role}`;
  document.getElementById("user-chip").hidden = false;
  document.getElementById("admin-link").hidden = currentUser.role !== "admin";
  document.getElementById("logout-button").hidden = false;
  document.getElementById("welcome-title").textContent = `Hi ${currentUser.username}, I'm Keystone`;
  showSuggestions(currentUser.role === "admin" ? SUGGESTIONS_FOR_ADMINS : SUGGESTIONS_FOR_EVERYONE);
}

document.getElementById("logout-button").onclick = async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
};

async function startUp() {
  await loadCurrentUser();
  const conversationIdInUrl = Number(location.hash.replace(CONVERSATION_HASH_PREFIX, ""));
  if (location.hash.startsWith(CONVERSATION_HASH_PREFIX) && conversationIdInUrl) {
    openConversation(conversationIdInUrl);
  }
  await loadHistory();
  questionInput.focus();
}

startUp();
