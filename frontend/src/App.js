import React, { useState, useRef, useEffect } from 'react';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function generateSessionId() {
  return 's-' + Math.random().toString(36).substring(2, 10);
}

function App() {
  const [sessionId] = useState(() => generateSessionId());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = async (textToSend) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setLoading(true);

    try {
      const body = { session_id: sessionId, message: text };
      if (systemPrompt.trim()) {
        body.system_prompt = systemPrompt.trim();
      }

      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(() => ({ detail: `HTTP error ${res.status}` }));

      if (!res.ok) {
        let errorDetail = 'An error occurred';
        if (typeof data.detail === 'string') {
          errorDetail = data.detail;
        } else if (Array.isArray(data.detail)) {
          errorDetail = data.detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
        } else if (data.detail) {
          errorDetail = JSON.stringify(data.detail);
        }
        setMessages((prev) => [
          ...prev,
          { role: 'error', content: errorDetail },
        ]);
        return;
      }

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.reply, metadata: data.metadata },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'error', content: err.message || 'Network connection failed. Please retry.' },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="terminal-container">
      {/* Top Console Bar */}
      <header className="console-header">
        <div className="header-left">
          <div className="app-badge">CLAUDE-STYLE CORE</div>
          <h1 className="console-title">LLM Gateway Terminal</h1>
          <span className="console-desc">LiteLLM Proxy • Automated Failover • SQLite Persistence</span>
        </div>
        <div className="header-right">
          <span className="session-tag">SESSION: {sessionId}</span>
        </div>
      </header>

      {/* System Prompt Control */}
      <div className="system-config-bar">
        <span className="config-label">SYSTEM PROMPT:</span>
        <input
          id="system-prompt-field"
          data-testid="system-prompt-input"
          type="text"
          className="system-config-input"
          placeholder="Optional instruction to override model persona or format..."
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
      </div>

      {/* Stream Window */}
      <main className="console-stream">
        {messages.length === 0 ? (
          <div className="empty-console">
            <div className="empty-title">CONSOLE READY</div>
            <p className="empty-subtitle">
              Awaiting instructions. Multi-turn conversation context is automatically synchronized to SQLite.
            </p>
            <div className="cli-hint">
              <span>Example command:</span>
              <code>Explain the difference between SQLite WAL mode and LiteLLM response caching.</code>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`stream-item ${msg.role}`}>
              {msg.role === 'user' && (
                <div className="user-message-box">
                  <div className="role-tag user-tag">USER</div>
                  <div className="user-text">{msg.content}</div>
                </div>
              )}

              {msg.role === 'assistant' && (
                <div className="assistant-message-box" data-testid="assistant-message">
                  <div className="role-tag assistant-tag">ASSISTANT</div>
                  <div className="assistant-body">
                    <div className="reply-text">{msg.content}</div>
                    {msg.metadata && (
                      <div className="metadata-bar">
                        <span
                          data-testid="meta-source"
                          className={`meta-pill ${
                            msg.metadata.resolution_source === 'LLM_CACHE' ? 'pill-cache' : 'pill-live'
                          }`}
                        >
                          {msg.metadata.resolution_source}
                        </span>
                        <span className="meta-pill">
                          MODEL: <strong data-testid="meta-model">{msg.metadata.model}</strong>
                        </span>
                        <span className="meta-pill">
                          LATENCY: <strong data-testid="meta-latency">{msg.metadata.latency_ms} ms</strong>
                        </span>
                        <span className="meta-pill">
                          IN: <strong data-testid="meta-input-tokens">{msg.metadata.input_tokens}</strong>
                        </span>
                        <span className="meta-pill">
                          OUT: <strong data-testid="meta-output-tokens">{msg.metadata.output_tokens}</strong>
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {msg.role === 'error' && (
                <div className="error-message-box">
                  <div className="role-tag error-tag">SYSTEM ERROR</div>
                  <div className="error-text">{msg.content}</div>
                </div>
              )}
            </div>
          ))
        )}

        {loading && (
          <div className="stream-item assistant">
            <div className="assistant-message-box loading-box">
              <div className="role-tag assistant-tag">ASSISTANT</div>
              <div className="loading-state">
                <span className="blink-cursor">&gt;</span> Generating completion...
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      {/* Terminal Input Dock */}
      <footer className="console-dock">
        <div className="dock-wrapper">
          <div className="prompt-prefix">&gt;</div>
          <textarea
            ref={inputRef}
            data-testid="chat-input"
            className="dock-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Send message... (Enter to dispatch, Shift+Enter for newline)"
            rows={1}
            disabled={loading}
          />
          <button
            type="button"
            data-testid="send-button"
            className="dock-send-btn"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
          >
            EXECUTE
          </button>
        </div>
      </footer>
    </div>
  );
}

export default App;
