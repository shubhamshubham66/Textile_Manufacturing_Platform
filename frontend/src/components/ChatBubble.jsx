// Floating AI chat bubble shown on the landing page and inside the app.
// The real widget lives in the chatbot track (components/chatbot/ChatWidget.jsx);
// it talks only to our backend POST /api/chatbot/message, never to Dify.
// Pages can open it with: window.dispatchEvent(new Event("etm:open-chat"))
export { default } from "./chatbot/ChatWidget.jsx";
