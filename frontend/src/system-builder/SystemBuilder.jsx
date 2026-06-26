import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, BarChart3, Clock, DollarSign, FileText, Goal, Image, Menu, Send, TrendingUp, X } from 'lucide-react';
import './SystemBuilder.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function SystemBuilder({ onBack }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [understanding, setUnderstanding] = useState(null);
  const [latestQuestion, setLatestQuestion] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [diagramXml, setDiagramXml] = useState(null);
  const [docsMarkdown, setDocsMarkdown] = useState(null);
  const [roi, setRoi] = useState(null);
  const [diagramOpen, setDiagramOpen] = useState(false);
  const [diagramLoading, setDiagramLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const bottomRef = useRef(null);
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
      const res = await fetch(`${API_BASE_URL}/system-builder/history`);
      if (res.ok) {
        const data = await res.json();
        setHistory(Array.isArray(data) ? data : []);
      }
    } catch {
      setHistory([]);
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
        diagramXmlRef.current = msg.xml;
        setDiagramXml(msg.xml);
      }
    }

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  async function sendMessage(event) {
    event?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/system-builder/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
        }),
      });
      if (!res.ok) throw new Error('Request failed');
      const data = await res.json();

      setSessionId(data.session_id);
      setUnderstanding(data.understanding);
      setIsComplete(data.is_complete);
      setDiagramXml(data.diagram_xml);
      setDocsMarkdown(data.docs_markdown);
      setRoi(data.roi);
      diagramXmlRef.current = data.diagram_xml;
      loadHistory();

      const assistantMsg = {
        role: 'assistant',
        content: data.latest_question || 'System design is complete!',
        isComplete: data.is_complete,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setLatestQuestion(data.latest_question);
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  }

  function openDiagram() {
    if (diagramXml) {
      diagramXmlRef.current = diagramXml;
      setDiagramLoading(true);
      setDiagramOpen(true);
    }
  }

  function renderUnderstanding() {
    if (!understanding) return null;
    return (
      <div className="sb-understanding">
        <h4>System Understanding</h4>
        <p><strong>Goal:</strong> {understanding.goal || '-'}</p>
        {understanding.description && <p><strong>Description:</strong> {understanding.description}</p>}

        {understanding.users?.length > 0 && (
          <>
            <h5>Users ({understanding.users.length})</h5>
            <ul>{understanding.users.map((u, i) => <li key={i}>{u.name} — {u.description}</li>)}</ul>
          </>
        )}

        {understanding.entities?.length > 0 && (
          <>
            <h5>Entities ({understanding.entities.length})</h5>
            <ul>{understanding.entities.map((e, i) => (
              <li key={i}>
                <strong>{e.name}</strong>
                {e.attributes?.length > 0 && <span className="sb-attrs"> ({e.attributes.map(a => a.name).join(', ')})</span>}
              </li>
            ))}</ul>
          </>
        )}

        {understanding.workflows?.length > 0 && (
          <>
            <h5>Workflows ({understanding.workflows.length})</h5>
            <ul>{understanding.workflows.map((w, i) => (
              <li key={i}><strong>{w.name}</strong> — {w.steps?.length || 0} steps</li>
            ))}</ul>
          </>
        )}

        {understanding.development_cost != null && (
          <p><strong>Development Cost:</strong> ${Number(understanding.development_cost).toLocaleString()}</p>
        )}
        {understanding.expected_monthly_return != null && (
          <p><strong>Expected Monthly Return:</strong> ${Number(understanding.expected_monthly_return).toLocaleString()}/mo</p>
        )}
      </div>
    );
  }

  function formatMoney(val) {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(val || 0);
  }

  async function restoreSession(sid) {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE_URL}/system-builder/session/${sid}`);
      if (!res.ok) return;
      const data = await res.json();
      setSessionId(sid);
      setUnderstanding(data.understanding);
      setIsComplete(data.is_complete);
      setDiagramXml(data.diagram_xml);
      setDocsMarkdown(data.docs_markdown);
      setRoi(data.roi);
      diagramXmlRef.current = data.diagram_xml;
      setLatestQuestion(data.latest_question);
      setMessages(data.messages || []);
      setHistoryOpen(false);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="sb-app">
      {historyOpen && (
        <div className="sb-history-overlay" onClick={() => setHistoryOpen(false)}>
          <aside className="sb-history-panel" onClick={(e) => e.stopPropagation()}>
            <div className="sb-history-topbar">
              <button
                className="sb-history-new"
                onClick={() => {
                  setSessionId(null);
                  setMessages([]);
                  setUnderstanding(null);
                  setIsComplete(false);
                  setDiagramXml(null);
                  setDocsMarkdown(null);
                  setRoi(null);
                  setLatestQuestion('');
                  setHistoryOpen(false);
                }}
              >
                <Goal size={17} /> New session
              </button>
              <div className="sb-history-sep" />
              <button className="sb-history-close" onClick={() => setHistoryOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="sb-history-list">
              {history.length === 0 && <p className="sb-history-empty">.</p>}
              {history.map((item) => (
                <button
                  key={item.session_id}
                  className={`sb-history-item${item.session_id === sessionId ? ' sb-history-active' : ''}`}
                  onClick={() => restoreSession(item.session_id)}
                >
                  <Clock size={15} />
                  <div className="sb-history-text">
                    <span>{item.goal || item.first_message || 'Untitled'}</span>
                    {item.is_complete && <span className="sb-history-badge">complete</span>}
                  </div>
                </button>
              ))}
            </div>
          </aside>
        </div>
      )}

      {diagramOpen && (
        <div className="sb-diagram-overlay" onClick={() => { setDiagramOpen(false); setDiagramLoading(false); }}>
          <div className="sb-diagram-modal" onClick={(e) => e.stopPropagation()}>
            <div className="sb-diagram-header">
              <span>System Diagram — {understanding?.goal || 'Design'}</span>
              <button className="sb-diagram-close" onClick={() => { setDiagramOpen(false); setDiagramLoading(false); }}>
                <X size={18} />
              </button>
            </div>
            {diagramLoading && <div className="sb-diagram-loader">Loading editor...</div>}
            <iframe
              ref={diagramFrameRef}
              className="sb-diagram-frame"
              src="https://embed.diagrams.net/?embed=1&ui=dark&save=1&proto=json"
              title="System Diagram"
              allowFullScreen
            />
          </div>
        </div>
      )}

      <header className="sb-topbar">
        <button className="sb-hamburger" onClick={() => setHistoryOpen(true)}>
          <Menu size={20} />
        </button>
        <div className="sb-title">System Builder</div>
        {isComplete && diagramXml && (
          <button className="sb-diagram-btn" onClick={openDiagram}>
            <Image size={16} /> View Diagram
          </button>
        )}
        <button className="sb-back-btn" onClick={onBack}>
          <ArrowLeft size={18} />
        </button>
      </header>

      <section className="sb-chat">
        {messages.length === 0 && (
          <div className="sb-welcome">
            <h2>System Builder</h2>
            <p>Describe the system you want to build. I'll ask questions, draw diagrams, calculate the ROI, and generate documentation.</p>
            <p className="sb-hint">Example: "I need a clinic management system. Development cost is 50,000 and expected monthly return is 15,000."</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`sb-msg ${msg.role}`}>
            <div className="sb-bubble">
              <p>{msg.content}</p>
            </div>
          </div>
        ))}

        {isComplete && roi && roi.is_profitable && (
          <div className="sb-roi-card">
            <div className="sb-roi-header">
              <BarChart3 size={18} /> ROI Analysis
            </div>
            <div className="sb-roi-grid">
              <div className="sb-roi-item">
                <DollarSign size={14} />
                <span className="sb-roi-label">Development Cost</span>
                <span className="sb-roi-value">${formatMoney(roi.development_cost)}</span>
              </div>
              <div className="sb-roi-item">
                <TrendingUp size={14} />
                <span className="sb-roi-label">Monthly Return</span>
                <span className="sb-roi-value">${formatMoney(roi.expected_monthly_return)}/mo</span>
              </div>
              <div className="sb-roi-item sb-roi-highlight">
                <BarChart3 size={14} />
                <span className="sb-roi-label">ROI Timeline</span>
                <span className="sb-roi-value">{roi.duration_display}</span>
              </div>
            </div>
          </div>
        )}

        {isComplete && diagramXml && (
          <div className="sb-complete-actions">
            <button className="sb-action-btn" onClick={openDiagram}>
              <Image size={16} /> Open Diagram Editor
            </button>
            {docsMarkdown && (
              <button className="sb-action-btn" onClick={() => {
                const blob = new Blob([docsMarkdown], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${understanding?.goal || 'system'}.md`;
                a.click();
                URL.revokeObjectURL(url);
              }}>
                <FileText size={16} /> Download Docs
              </button>
            )}
          </div>
        )}

        {loading && <div className="sb-typing">Thinking...</div>}
        {isComplete && renderUnderstanding()}
        <div ref={bottomRef} />
      </section>

      <form className="sb-composer" onSubmit={sendMessage}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) sendMessage(e); }}
          placeholder={latestQuestion || "Describe your system..."}
          rows={1}
        />
        <button className="sb-send" type="submit" disabled={loading || !input.trim()}>
          <Send size={19} />
        </button>
      </form>
    </div>
  );
}
