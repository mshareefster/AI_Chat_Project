import { useEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Link,
  useNavigate,
} from "react-router-dom";

const FALLBACK_MODELS = [
  "claude-sonnet-5",
  "claude-opus-5",
  "claude-haiku-4-5-20251001",
  "gpt-5.6-sol",
  "gpt-6-astra",
  "gpt-6-luna",
  "gpt-6-sol",
  "deepseek/deepseek-V3.2",
  "deepseek/deepseek-v4-pro",
  "google/gemini-3.5-flash",
  "google/gemini-3.1-pro-preview",
  "minimax/minimax-m3",
  "moonshot/kimi-k3",
  "qwen/qwen3.7-plus",
  "xai/grok-4.7",
  "zai/glm-5.3-flash",
];

/* =========================
   LOGIN PAGE
========================= */

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin(e) {
    e.preventDefault();

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      navigate("/chat");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/hai-logo.png" alt="HAi logo" />
        </div>

        <div className="auth-heading">
          <h1>Welcome back</h1>
          <p>Sign in to continue to your AI workspace.</p>
        </div>

        <form onSubmit={handleLogin} className="auth-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <button className="auth-submit" disabled={busy}>
            {busy ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="auth-links">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>

        <div className="auth-divider">
          <span>OR</span>
        </div>

        <button
          type="button"
          className="google-button"
          onClick={() => setError("Google Sign-In will be added next.")}
        >
          <span className="google-icon">G</span>
          Continue with Google
        </button>

        <p className="auth-footer">
          Don't have an account?{" "}
          <Link to="/signup">Create account</Link>
        </p>
      </div>
    </div>
  );
}

/* =========================
   SIGN UP PAGE
========================= */

function Signup() {
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleSignup(e) {
    e.preventDefault();

    if (!name.trim() || !email.trim() || !password) {
      setError("Please fill in all fields.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/signup", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          email,
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not create account.");
      }

      setSuccess("Account created successfully. Redirecting to login...");

      setTimeout(() => {
        navigate("/login");
      }, 1200);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/hai-logo.png" alt="HAi logo" />
        </div>

        <div className="auth-heading">
          <h1>Create your account</h1>
          <p>Start using your private AI workspace.</p>
        </div>

        <form onSubmit={handleSignup} className="auth-form">
          <label>
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              autoComplete="name"
            />
          </label>

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          {success && <div className="auth-success">{success}</div>}

          <button className="auth-submit" disabled={busy}>
            {busy ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

/* =========================
   FORGOT PASSWORD PLACEHOLDER
========================= */

function ForgotPassword() {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/hai-logo.png" alt="HAi logo" />
        </div>

        <div className="auth-heading">
          <h1>Forgot password?</h1>
          <p>
            Password reset will be available after we configure the reset
            email system.
          </p>
        </div>

        <Link to="/login" className="back-login">
          ← Back to login
        </Link>
      </div>
    </div>
  );
}

/* =========================
   PROTECTED ROUTE
========================= */

function ProtectedRoute({ children }) {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    fetch("/api/auth/me", {
      credentials: "include",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Not authenticated");
        }

        return response.json();
      })
      .then(() => {
        setStatus("authenticated");
      })
      .catch(() => {
        setStatus("unauthenticated");
      });
  }, []);

  if (status === "checking") {
    return (
      <div className="auth-loading">
        <div className="loading-logo">✦</div>
        <p>Checking your session...</p>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return children;
}

/* =========================
   CHAT PAGE
========================= */

function Chat() {
  const navigate = useNavigate();

  const [models, setModels] = useState(FALLBACK_MODELS);
  const [selected, setSelected] = useState("claude-sonnet-5");
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [renamingId, setRenamingId] = useState(null);
  const [renameTitle, setRenameTitle] = useState("");	
  const [input, setInput] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  async function loadConversations() {
  try {
    const response = await fetch("/api/conversations", {
      credentials: "include",
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Could not load conversations."
      );
    }

    setConversations(data.conversations || []);
  } catch (err) {
    setError(err.message);
  }
}	


async function renameConversation(id) {
  const title = renameTitle.trim();

  if (!title) {
    setError("Conversation title cannot be empty.");
    return;
  }

  try {
    const response = await fetch(`/api/conversations/${id}`, {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Could not rename conversation.");
    }

    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === id
          ? { ...conversation, title }
          : conversation
      )
    );

    setRenamingId(null);
    setRenameTitle("");
    setError("");
  } catch (err) {
    setError(err.message);
  }
}


async function deleteConversation(id) {
  const confirmed = window.confirm(
    "Are you sure you want to delete this conversation? This cannot be undone."
  );

  if (!confirmed) return;

  try {
    const response = await fetch(`/api/conversations/${id}`, {
      method: "DELETE",
      credentials: "include",
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Could not delete conversation."
      );
    }

    const remaining = conversations.filter(
      (conversation) => conversation.id !== id
    );

    setConversations(remaining);
    setError("");

    if (conversationId === id) {
      if (remaining.length > 0) {
        await loadConversation(remaining[0].id);
      } else {
        setConversationId(null);
        setMessages([]);
        setInput("");
        setFiles([]);
      }
    }
  } catch (err) {
    setError(err.message);
  }
}


  async function loadConversation(id) {
  try {
    const response = await fetch(
      `/api/conversations/${id}`,
      {
        credentials: "include",
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Could not load conversation."
      );
    }

    const conversation = data.conversation;

    setConversationId(conversation.id);
    setSelected(conversation.model || selected);
    setMessages(conversation.messages || []);
    setInput("");
    setFiles([]);
    setError("");
  } catch (err) {
    setError(err.message);
  }
}

  useEffect(() => {
    fetch("/api/models", {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.models?.length) {
          setModels(data.models);

          if (!data.models.includes(selected)) {
            setSelected(data.models[0]);
          }
        }
      })
      .catch(() => {});
  }, []);

useEffect(() => {
  loadConversations();
}, []);

useEffect(() => {
  async function initializeChat() {
    try {
      const response = await fetch("/api/conversations", {
        credentials: "include",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not load conversations."
        );
      }

      const existingConversations = data.conversations || [];

      setConversations(existingConversations);

      if (existingConversations.length > 0) {
        const latestConversation = existingConversations[0];

        setConversationId(latestConversation.id);
        setSelected(
          latestConversation.model || selected
        );
      } else {
        const createResponse = await fetch(
          "/api/conversations",
          {
            method: "POST",
            credentials: "include",
          }
        );

        const createData = await createResponse.json();

        if (!createResponse.ok) {
          throw new Error(
            createData.detail ||
              "Could not create a conversation."
          );
        }

        setConversationId(createData.conversation.id);
        setSelected(
          createData.conversation.model || selected
        );

        setConversations([
          createData.conversation
        ]);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  initializeChat();
}, []);

  async function logout() {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } finally {
      navigate("/login");
    }
  }

  async function newChat() {
  setMessages([]);
  setInput("");
  setFiles([]);
  setError("");

  try {
    const response = await fetch("/api/conversations", {
      method: "POST",
      credentials: "include",
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Could not create a new chat.");
    }

    setConversationId(data.conversation.id);
    setSelected(data.conversation.model || selected);
  } catch (err) {
    setError(err.message);
  }
}

  function addFiles(list) {
    const accepted = Array.from(list).slice(0, 5);
    setFiles((prev) => [...prev, ...accepted].slice(0, 5));
  }

  function pasteImage(e) {
    const items = Array.from(e.clipboardData?.items || []);
    const imageItem = items.find((item) =>
      item.type.startsWith("image/")
    );

    if (imageItem) {
      e.preventDefault();

      const file = imageItem.getAsFile();

      if (file) {
        const named = new File(
          [file],
          `screenshot-${Date.now()}.png`,
          { type: file.type }
        );

        addFiles([named]);
      }
    }
  }

  async function send() {
    if (busy || (!input.trim() && files.length === 0)) return;

    const userText = input.trim();
    const selectedFiles = [...files];

    const nextUser = {
      role: "user",
      content: userText || `[${selectedFiles.length} attachment(s)]`,
      attachments: selectedFiles.map((f) => f.name),
    };

    setMessages((prev) => [...prev, nextUser]);
    setInput("");
    setFiles([]);
    setBusy(true);
    setError("");
if (!conversationId) {
  setError("Please create a new chat first.");
  setBusy(false);
  return;
}

const form = new FormData();

form.append("conversationId", conversationId);
form.append("model", selected);
form.append("message", userText);

    selectedFiles.forEach((file) => {
      form.append("files", file);
    });

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        credentials: "include",
        body: form,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Request failed");
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.content || "(No response)",
        },
      ]);
  
	await loadConversations();

    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);

      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="chat-layout">
      <aside className="sidebar">
        <button className="new-chat" onClick={newChat}>
          ＋ New chat
        </button>

	<div className="side-title">CHAT HISTORY</div>

	
<div className="conversation-list">
  {conversations.map((conversation) => (
    <div
      key={conversation.id}
      className="conversation-entry"
    >
      {renamingId === conversation.id ? (
        <div className="rename-form">
          <input
            type="text"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                renameConversation(conversation.id);
              }

              if (e.key === "Escape") {
                setRenamingId(null);
                setRenameTitle("");
              }
            }}
            autoFocus
            maxLength={100}
            aria-label="Conversation title"
          />

          <button
            type="button"
            onClick={() => renameConversation(conversation.id)}
          >
            Save
          </button>

          <button
            type="button"
            onClick={() => {
              setRenamingId(null);
              setRenameTitle("");
            }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="conversation-row">
          <button
            type="button"
            className={`conversation-item ${
              conversation.id === conversationId ? "active" : ""
            }`}
            onClick={() => loadConversation(conversation.id)}
            title={conversation.title}
          >
            {conversation.title}
          </button>

          <button
            type="button"
            className="conversation-rename"
            title="Rename conversation"
            aria-label={`Rename ${conversation.title}`}
            onClick={() => {
              setRenamingId(conversation.id);
              setRenameTitle(conversation.title);
              setError("");
            }}
          >
            ✎
          </button>
	      <button
  type="button"
  className="conversation-delete"
  title="Delete conversation"
  aria-label={`Delete ${conversation.title}`}
  onClick={() => deleteConversation(conversation.id)}
>
  🗑
</button>
        </div>
      )}
    </div>
  ))}
</div>

 

        <div className="side-title">Selected model</div>

        <div className="selected-model">
          {selected}
        </div>

        <select
          className="model-select"
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
          }}
        >
          {models.map((model) => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </select>

        <button
          className="logout-button"
          onClick={logout}
        >
          Log out
        </button>

        <div className="side-bottom">
          Huda AI · Private API gateway
        </div>
      </aside>

      <main className="chat-main">
        <header className="chat-header">
          <button
            className="mobile-back"
            onClick={() => navigate("/")}
          >
            ←
          </button>

          <div>
            <strong>{selected}</strong>
            <span>AI Assistant</span>
          </div>

          <button
            className="header-new"
            onClick={newChat}
          >
            New chat
          </button>
        </header>

        <section className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <div className="empty-logo">✦</div>

              <h2>How can I help you?</h2>

              <p>
                Ask a question, upload a document, or paste a screenshot.
              </p>

              <div className="quick-actions">
                <button
                  onClick={() =>
                    setInput("Explain this code in simple English")
                  }
                >
                  Explain code
                </button>

                <button
                  onClick={() =>
                    setInput("Analyze the attached file")
                  }
                >
                  Analyze file
                </button>

                <button
                  onClick={() =>
                    setInput("Help me debug this screenshot")
                  }
                >
                  Debug screenshot
                </button>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              className={`message-row ${m.role}`}
              key={i}
            >
              <div className="avatar">
                {m.role === "user" ? "You" : "✦"}
              </div>

              <div className="message-bubble">
                <div className="message-text">
                  {m.content}
                </div>

                {m.attachments?.length > 0 && (
                  <div className="attachments">
                    {m.attachments.map((name) => (
                      <span key={name}>
                        📎 {name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="message-row assistant">
              <div className="avatar">✦</div>

              <div className="message-bubble typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
        </section>

        <div className="composer-wrap">
          {error && (
            <div className="error">
              {error}
            </div>
          )}

          {files.length > 0 && (
            <div className="file-preview">
              {files.map((f, i) => (
                <div className="file-chip" key={i}>
                  <span>📎 {f.name}</span>

                  <button
                    onClick={() =>
                      setFiles((prev) =>
                        prev.filter((_, x) => x !== i)
                      )
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="composer">
            <input
              ref={inputRef}
              type="file"
              id="file-input"
              multiple
              hidden
              onChange={(e) =>
                addFiles(e.target.files)
              }
            />

            <button
              className="attach"
              onClick={() =>
                document
                  .getElementById("file-input")
                  .click()
              }
              title="Attach files"
            >
              ＋
            </button>

            <textarea
              value={input}
              onChange={(e) =>
                setInput(e.target.value)
              }
              onKeyDown={onKeyDown}
              onPaste={pasteImage}
              placeholder="Message Huda AI..."
              rows="1"
            />

            <button
              className="send"
              disabled={
                busy ||
                (!input.trim() && files.length === 0)
              }
              onClick={send}
            >
              ↑
            </button>
          </div>

          <div className="composer-note">
            Enter to send · Shift+Enter for a new line ·
            Paste screenshots directly
          </div>
        </div>
      </main>
    </div>
  );
}

/* =========================
   ROUTER
========================= */

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />

      <Route path="/login" element={<Login />} />

      <Route path="/signup" element={<Signup />} />

      <Route
        path="/forgot-password"
        element={<ForgotPassword />}
      />

      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <Chat />
          </ProtectedRoute>
        }
      />

      <Route
        path="*"
        element={<Navigate to="/login" replace />}
      />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
