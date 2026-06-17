import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Clock, Goal, Menu, Send, Sparkles, Wallet, X } from 'lucide-react';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const USER_ID_KEY = 'financial-chat-user-id';

function getUserId() {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

function App() {
  const [userId] = useState(getUserId);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Tell me your financial goal, income, expenses, savings, and any extra income. I will extract the numbers and calculate the timeline.',
    },
  ]);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function loadHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/history?user_id=${encodeURIComponent(userId)}`);
      if (response.ok) {
        const data = await response.json();
        setHistory(Array.isArray(data) ? data : []);
      }
    } catch {
      setHistory([]);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const optimisticUser = { id: crypto.randomUUID(), role: 'user', content: text };
    setMessages((current) => [...current, optimisticUser]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, user_id: userId, conversation_id: conversationId }),
      });
      const textBody = await response.text();
      let payload;
      try {
        payload = JSON.parse(textBody);
      } catch {
        throw new Error(`Server returned ${response.status} (${textBody.slice(0, 80)})`);
      }
      if (!response.ok) throw new Error(payload.detail || 'Request failed');
      setConversationId(payload.conversation_id);
      setMessages((current) => [...current, payload.assistant_message]);
      loadHistory();
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `I could not complete the analysis: ${error.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // ✅ التعديل هنا فقط
  const groupedHistory = useMemo(() => {
    const map = new Map();

    for (const item of history) {
      if (!item || !item.conversation_id) continue;

      const key = item.conversation_id;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }

    return [...map.entries()]
      .map(([id, items]) => ({ id, items }))
      .sort((a, b) => {
        const aTime = a.items.at(-1)?.assistant_message?.created_at || '';
        const bTime = b.items.at(-1)?.assistant_message?.created_at || '';
        return bTime.localeCompare(aTime);
      });
  }, [history]);

  return (
    <div className="app">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebarHeader">
          <div className="brandMark"><Sparkles size={18} /></div>
          <div>
            <h1>Financial Chat Assistant</h1>
            <span>Goal timeline history</span>
          </div>
          <button className="iconButton mobileOnly" onClick={() => setSidebarOpen(false)} aria-label="Close history">
            <X size={18} />
          </button>
        </div>
        <button
          className="newChat"
          onClick={() => {
            setConversationId(null);
            setMessages([{ id: 'welcome-new', role: 'assistant', content: 'Start a new financial goal analysis whenever you are ready.' }]);
            setSidebarOpen(false);
          }}
        >
          <Goal size={17} /> New goal
        </button>
        <div className="historyList">
          {groupedHistory.length === 0 && <p className="empty">No saved conversations yet.</p>}
          {groupedHistory.map((group) => (
            <button
              key={group.id}
              className="historyItem"
              onClick={() => {
                const rebuilt = group.items
                  .flatMap((item) => [item.user_message, item.assistant_message])
                  .filter(Boolean);

                setConversationId(group.id);

                // ✅ التعديل هنا فقط
                if (rebuilt.length) {
                  setMessages(rebuilt);
                }

                setSidebarOpen(false);
              }}
            >
              <Clock size={15} />
              <span>{group.items[0]?.user_message?.content || 'Saved analysis'}</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="iconButton mobileOnly" onClick={() => setSidebarOpen(true)} aria-label="Open history">
            <Menu size={20} />
          </button>
          <div className="statusPill"><Wallet size={16} /> Smart financial analysis</div>
        </header>

        <section className="chatStream">
          {messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
          {loading && <div className="typing">Analyzing numbers and calculating timeline...</div>}
          <div ref={bottomRef} />
        </section>

        <form className="composer" onSubmit={sendMessage}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) sendMessage(event);
            }}
            placeholder="Example: I want to buy a 40000 car. I earn 6500 monthly, spend 4200, have 8000 saved, and make 500 extra."
            rows={1}
          />
          <button className="sendButton" type="submit" disabled={loading || !input.trim()} aria-label="Send message">
            <Send size={19} />
          </button>
        </form>
      </main>
    </div>
  );
}

function Message({ message }) {
  const calculation = message.calculation;
  const data = message.extracted_data;
  return (
    <article className={`message ${message.role}`}>
      <div className="bubble">
        <p>{message.content}</p>
        {data && (
          <div className="analysisGrid">
            <Metric label="Goal" value={data.goal_price} />
            <Metric label="Income" value={data.monthly_income} />
            <Metric label="Expenses" value={data.monthly_expenses} />
            <Metric label="Savings" value={data.current_savings} />
            <Metric label="Extra" value={data.extra_income} />
          </div>
        )}
        {calculation && (
          <div className="resultPanel">
            <strong>{calculation.duration_display}</strong>
            <span>Net monthly savings: {formatMoney(calculation.net_monthly_savings)}</span>
            <span>Remaining: {formatMoney(calculation.remaining)}</span>
          </div>
        )}
      </div>
    </article>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value === null || value === undefined ? '0' : formatMoney(value)}</strong>
    </div>
  );
}

function formatMoney(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value || 0);
}

createRoot(document.getElementById('root')).render(<App />);