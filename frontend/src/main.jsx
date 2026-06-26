import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CheckCircle, Clock, Goal, Image, List, Menu, Send, Wallet, X, Puzzle } from 'lucide-react';
import SystemBuilder from './system-builder/SystemBuilder.jsx';
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
  const [mode, setMode] = useState('chat');
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Tell me your financial goal. I will ask about income, expenses, and more step by step.',
    },
  ]);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pendingYesNo, setPendingYesNo] = useState(null);
  const [diagramXml, setDiagramXml] = useState(null);
  const [diagramOpen, setDiagramOpen] = useState(false);
  const [diagramLoading, setDiagramLoading] = useState(false);
  const bottomRef = useRef(null);
  const abortRef = useRef(null);
  const diagramFrameRef = useRef(null);
  const diagramXmlRef = useRef(null);

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

  function cancelRequest() {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
  }

  async function showDiagram(data, calculation) {
    try {
      setDiagramLoading(true);
      const res = await fetch(`${API_BASE_URL}/diagram`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data, calculation }),
      });
      if (!res.ok) { setDiagramLoading(false); return; }
      const { xml } = await res.json();
      diagramXmlRef.current = xml;
      setDiagramXml(xml);
      setDiagramOpen(true);
    } catch {
      setDiagramLoading(false);
    }
  }

  async function handleDiagramSave(xml) {
    try {
      const res = await fetch(`${API_BASE_URL}/diagram/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, user_id: userId, xml }),
      });
      if (res.ok) {
        diagramXmlRef.current = xml;
        setDiagramXml(xml);
      }
    } catch {
      // silently fail
    }
  }

  useEffect(() => {
    const allowedOrigins = [
      'https://embed.diagrams.net',
      'https://app.diagrams.net',
      'https://www.draw.io',
      'https://draw.io',
    ];

    function handleMessage(event) {
      if (!allowedOrigins.some((o) => event.origin.startsWith(o))) return;

      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }

      if (msg.event === 'init') {
        const xml = diagramXmlRef.current;
        if (xml && event.source) {
          event.source.postMessage(JSON.stringify({ action: 'load', xml }), event.origin);
        }
      }
      if (msg.event === 'load') {
        setDiagramLoading(false);
      }
      if (msg.event === 'save') {
        handleDiagramSave(msg.xml);
      }
    }

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  async function sendChat(text) {
    const optimisticUser = { id: crypto.randomUUID(), role: 'user', content: text };
    setMessages((current) => [...current, optimisticUser]);
    setInput('');
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, user_id: userId, conversation_id: conversationId }),
        signal: controller.signal,
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

      if (payload.assistant_message) {
        const assistantMsg = {
          ...payload.assistant_message,
          id: crypto.randomUUID(),
        };
        if (payload.is_complete) {
          if (payload.extracted_data) assistantMsg.extracted_data = payload.extracted_data;
          if (payload.calculation) assistantMsg.calculation = payload.calculation;
        }
        setMessages((current) => [...current, assistantMsg]);
      }

      if (payload.is_complete) {
        setPendingYesNo(null);
        loadHistory();
      } else if (payload.question_type === 'yesno') {
        setPendingYesNo(payload);
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
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
      abortRef.current = null;
    }
  }

  async function handleYesNo(isYes) {
    if (!pendingYesNo) return;
    if (isYes) {
      setInput('');
      setPendingYesNo({ ...pendingYesNo, waitingValue: true });
    } else {
      setPendingYesNo(null);
      await sendChat('No');
    }
  }

  async function handleYesValue() {
    if (!pendingYesNo || !input.trim()) return;
    const val = input.trim();
    setPendingYesNo(null);
    await sendChat(`Yes, ${val}`);
  }

  async function submitMessage() {
    const text = input.trim();
    if (!text || loading) return;
    if (pendingYesNo?.waitingValue) {
      await handleYesValue();
      return;
    }
    setPendingYesNo(null);
    await sendChat(text);
  }

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

  if (mode === 'system-builder') {
    return <SystemBuilder onBack={() => setMode('chat')} />;
  }

  return (
    <div className="app">
      {historyOpen && (
        <div className="historyOverlay" onClick={() => setHistoryOpen(false)}>
          <aside className="historyPanel" onClick={(e) => e.stopPropagation()}>
            <div className="historyTopBar">
              <button
                className="newChat"
                onClick={() => {
                  setConversationId(null);
                  setMessages([{ id: 'welcome-new', role: 'assistant', content: 'Start a new financial goal analysis whenever you are ready.' }]);
                  setHistoryOpen(false);
                  setPendingYesNo(null);
                }}
              >
                <Goal size={17} /> New goal
              </button>
              <div className="historyTopSep" />
              <button className="historyCloseBtn" onClick={() => setHistoryOpen(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <div className="historyList">
              {groupedHistory.length === 0 && <p className="empty">.</p>}
              {groupedHistory.map((group) => (
                <button
                  key={group.id}
                  className="historyItem"
                  onClick={() => {
                    const rebuilt = group.items
                      .flatMap((item) => [item.user_message, item.assistant_message])
                      .filter(Boolean);
                    setConversationId(group.id);
                    if (rebuilt.length) setMessages(rebuilt);
                    setHistoryOpen(false);
                  }}
                >
                  <Clock size={15} />
                  <span>{group.items[0]?.user_message?.content || ''}</span>
                </button>
              ))}
            </div>
          </aside>
        </div>
      )}
      {diagramOpen && (
        <div className="diagramOverlay" onClick={() => { setDiagramOpen(false); setDiagramLoading(false); }}>
          <div className="diagramModal" onClick={(e) => e.stopPropagation()}>
            <div className="diagramHeader">
              <span>Financial Roadmap</span>
              <button className="diagramCloseBtn" onClick={() => { setDiagramOpen(false); setDiagramLoading(false); }} aria-label="Close diagram">
                <X size={18} />
              </button>
            </div>
            {diagramLoading && <div className="diagramLoader">Loading editor...</div>}
            <iframe
              ref={diagramFrameRef}
              className="diagramFrame"
              src="https://embed.diagrams.net/?embed=1&ui=dark&save=1&proto=json"
              title="Financial Roadmap"
              allowFullScreen
            />
          </div>
        </div>
      )}
      <main className="main">
        <header className="topbar">
          <button className="hamburger" onClick={() => setHistoryOpen(true)} aria-label="Open history">
            <Menu size={20} />
          </button>
          <div className="statusPill">
            <Wallet size={16} />
            Smart financial analysis
          </div>
          <button className="modeToggle" onClick={() => setMode('system-builder')} title="System Builder">
            <Puzzle size={17} />
          </button>
        </header>

        <section className="chatStream">
          {messages.map((message) => (
            <Message key={message.id} message={message} onShowDiagram={showDiagram} />
          ))}
          {pendingYesNo && !pendingYesNo.waitingValue && (
            <div className="yesnoButtons">
              <button className="yesnoBtn yesnoYes" onClick={() => handleYesNo(true)} disabled={loading}>
                <CheckCircle size={16} /> Yes
              </button>
              <button className="yesnoBtn yesnoNo" onClick={() => handleYesNo(false)} disabled={loading}>
                <X size={16} /> No
              </button>
            </div>
          )}
          {loading && <div className="typing">Processing... <button className="cancelBtn" onClick={cancelRequest}>Cancel</button></div>}
          <div ref={bottomRef} />
        </section>

        <form className="composer" onSubmit={(e) => { e.preventDefault(); submitMessage(); }}>
          {pendingYesNo && pendingYesNo.waitingValue ? (
            <div className="yesValueInput">
              <span className="yesValueLabel">Enter the amount:</span>
              <div className="yesValueRow">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleYesValue();
                    }
                  }}
                  placeholder="e.g. 4200"
                  autoFocus
                />
                <button className="sendButton" type="button" onClick={handleYesValue} disabled={!input.trim()}>
                  <Send size={19} />
                </button>
              </div>
            </div>
          ) : (
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  submitMessage();
                }
              }}
              placeholder="Example: I want to buy a 40000 car. I earn 6500 monthly, spend 4200, have 8000 saved, and make 500 extra."
              rows={1}
            />
          )}
          {!pendingYesNo?.waitingValue && (
            <button className="sendButton" type="submit" disabled={loading || !input.trim()} aria-label="Send message">
              <Send size={19} />
            </button>
          )}
        </form>
      </main>
    </div>
  );
}

function Message({ message, onShowDiagram }) {
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
            <Metric label="Debts" value={data.current_debts} />
            {data.current_debts ? <Metric label="Net Savings" value={(data.current_savings || 0) - data.current_debts} /> : null}
            <Metric label="Extra" value={data.extra_income} />
          </div>
        )}
        {calculation && (
          <div className="resultPanel">
            <strong>{calculation.duration_display}</strong>
            <span>Net monthly savings: {formatMoney(calculation.net_monthly_savings)}</span>
            <span>Remaining: {formatMoney(calculation.remaining)}</span>
            <button className="diagramBtn" onClick={() => onShowDiagram && onShowDiagram(data, calculation)}>
              <Image size={15} /> View Financial Plan
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

function Metric({ label, value }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{formatMoney(value)}</strong>
    </div>
  );
}

function formatMoney(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value || 0);
}

createRoot(document.getElementById('root')).render(<App />);
