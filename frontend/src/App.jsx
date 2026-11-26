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
  const [otp, setOtp] = useState("");
  const [otpStep, setOtpStep] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (resendCountdown <= 0) return;

    const timer = setTimeout(() => {
      setResendCountdown((current) => Math.max(0, current - 1));
    }, 1000);

    return () => clearTimeout(timer);
  }, [resendCountdown]);

  async function handleLogin(e) {
    e.preventDefault();

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      setOtpStep(true);
      setOtp("");
      setResendCountdown(60);
      setSuccess("A verification code has been sent to your email.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault();

    if (!/^\d{6}$/.test(otp)) {
      setError("Please enter the 6-digit verification code.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/login/verify", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          otp,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "OTP verification failed.");
      }

      navigate("/chat");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResendOtp() {
    if (resendCountdown > 0 || busy) return;

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/otp/resend", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          purpose: "login",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not resend the verification code.");
      }

      setOtp("");
      setResendCountdown(60);
      setSuccess("A new verification code has been sent.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function changeEmail() {
    setOtpStep(false);
    setOtp("");
    setError("");
    setSuccess("");
    setResendCountdown(0);
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/hai-logo.png" alt="HAi logo" />
        </div>

        <div className="auth-heading">
          <h1>{otpStep ? "Verify your email" : "Welcome back"}</h1>
          <p>
            {otpStep
              ? `Enter the 6-digit code sent to ${email}.`
              : "Sign in to continue to your AI workspace."}
          </p>
        </div>

        {!otpStep ? (
          <form onSubmit={handleLogin} className="auth-form">
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
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
                required
              />
            </label>

            {error && <div className="auth-error">{error}</div>}

            <button className="auth-submit" disabled={busy}>
              {busy ? "Signing in..." : "Continue"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="auth-form">
            <label>
              Verification code
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={otp}
                onChange={(e) =>
                  setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                placeholder="Enter 6-digit code"
                maxLength={6}
                required
              />
            </label>

            {error && <div className="auth-error">{error}</div>}
            {success && <div className="auth-success">{success}</div>}

            <button className="auth-submit" disabled={busy || otp.length !== 6}>
              {busy ? "Verifying..." : "Verify and sign in"}
            </button>

            <div className="auth-links">
              <button
                type="button"
                onClick={handleResendOtp}
                disabled={busy || resendCountdown > 0}
              >
                {resendCountdown > 0
                  ? `Resend code in ${resendCountdown}s`
                  : "Resend verification code"}
              </button>
              <button type="button" onClick={changeEmail} disabled={busy}>
                Use a different email
              </button>
            </div>
          </form>
        )}

        {!otpStep && (
          <>
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
          </>
        )}
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
  const [otp, setOtp] = useState("");
  const [otpStep, setOtpStep] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (resendCountdown <= 0) return;

    const timer = setTimeout(() => {
      setResendCountdown((current) => Math.max(0, current - 1));
    }, 1000);

    return () => clearTimeout(timer);
  }, [resendCountdown]);

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
          name: name.trim(),
          email: email.trim(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not create account.");
      }

      setOtpStep(true);
      setOtp("");
      setResendCountdown(60);
      setSuccess("A verification code has been sent to your email.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault();

    if (!/^\d{6}$/.test(otp)) {
      setError("Please enter the 6-digit verification code.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/signup/verify", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          otp,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Email verification failed.");
      }

      setSuccess("Your email is verified and your account has been created. Redirecting to sign in...");

      setTimeout(() => {
        navigate("/login");
      }, 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResendOtp() {
    if (resendCountdown > 0 || busy) return;

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/otp/resend", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          purpose: "signup",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not resend the verification code.");
      }

      setOtp("");
      setResendCountdown(60);
      setSuccess("A new verification code has been sent.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function changeDetails() {
    setOtpStep(false);
    setOtp("");
    setError("");
    setSuccess("");
    setResendCountdown(0);
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/hai-logo.png" alt="HAi logo" />
        </div>

        <div className="auth-heading">
          <h1>{otpStep ? "Verify your email" : "Create your account"}</h1>
          <p>
            {otpStep
              ? `Enter the 6-digit code sent to ${email}.`
              : "Start using your private AI workspace."}
          </p>
        </div>

        {!otpStep ? (
          <form onSubmit={handleSignup} className="auth-form">
            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
                required
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
                required
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
                required
              />
            </label>

            {error && <div className="auth-error">{error}</div>}

            <button className="auth-submit" disabled={busy}>
              {busy ? "Sending verification code..." : "Continue"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="auth-form">
            <label>
              Verification code
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={otp}
                onChange={(e) =>
                  setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                placeholder="Enter 6-digit code"
                maxLength={6}
                required
              />
            </label>

            {error && <div className="auth-error">{error}</div>}
            {success && <div className="auth-success">{success}</div>}

            <button className="auth-submit" disabled={busy || otp.length !== 6}>
              {busy ? "Verifying..." : "Verify email and create account"}
            </button>

            <div className="auth-links">
              <button
                type="button"
                onClick={handleResendOtp}
                disabled={busy || resendCountdown > 0}
              >
                {resendCountdown > 0
                  ? `Resend code in ${resendCountdown}s`
                  : "Resend verification code"}
              </button>
              <button type="button" onClick={changeDetails} disabled={busy}>
                Change account details
              </button>
            </div>
          </form>
        )}

        {!otpStep && (
          <p className="auth-footer">
            Already have an account?{" "}
            <Link to="/login">Sign in</Link>
          </p>
        )}
      </div>
    </div>
  );
}

/* =========================
   FORGOT PASSWORD PLACEHOLDER
========================= */

function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otpStep, setOtpStep] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setTimeout(() => {
      setResendCountdown((current) => Math.max(0, current - 1));
    }, 1000);
    return () => clearTimeout(timer);
  }, [resendCountdown]);

  async function handleRequestReset(e) {
    e.preventDefault();
    if (!email.trim()) {
      setError("Please enter your registered email address.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not request a password reset.");
      }
      setOtpStep(true);
      setOtp("");
      setResendCountdown(60);
      setSuccess(data.message || "If a matching account exists, a reset code will be sent.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResetPassword(e) {
    e.preventDefault();

    if (!/^\d{6}$/.test(otp)) {
      setError("Please enter the 6-digit verification code.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          otp,
          new_password: newPassword,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not reset your password.");
      }
      setSuccess("Password reset successfully. Redirecting to sign in...");
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResendOtp() {
    if (busy || resendCountdown > 0) return;

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/otp/resend", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), purpose: "password_reset" }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not resend the reset code. Please start again.");
      }
      setOtp("");
      setResendCountdown(60);
      setSuccess("A new password-reset code has been sent.");
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
          <h1>{otpStep ? "Reset your password" : "Forgot password?"}</h1>
          <p>
            {otpStep
              ? `Enter the 6-digit code sent to ${email} and choose a new password.`
              : "Enter your registered email address. We will send you a password-reset code."}
          </p>
        </div>

        {!otpStep ? (
          <form onSubmit={handleRequestReset} className="auth-form">
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </label>
            {error && <div className="auth-error">{error}</div>}
            {success && <div className="auth-success">{success}</div>}
            <button className="auth-submit" disabled={busy}>
              {busy ? "Sending code..." : "Send reset code"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleResetPassword} className="auth-form">
            <label>
              Verification code
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="Enter 6-digit code"
                maxLength={6}
                required
              />
            </label>
            <label>
              New password
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                required
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your new password"
                autoComplete="new-password"
                required
              />
            </label>
            {error && <div className="auth-error">{error}</div>}
            {success && <div className="auth-success">{success}</div>}
            <button className="auth-submit" disabled={busy || otp.length !== 6}>
              {busy ? "Resetting password..." : "Reset password"}
            </button>
            <div className="auth-links">
              <button type="button" onClick={handleResendOtp} disabled={busy || resendCountdown > 0}>
                {resendCountdown > 0 ? `Resend code in ${resendCountdown}s` : "Resend reset code"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setOtpStep(false);
                  setOtp("");
                  setNewPassword("");
                  setConfirmPassword("");
                  setError("");
                  setSuccess("");
                  setResendCountdown(0);
                }}
                disabled={busy}
              >
                Use a different email
              </button>
            </div>
          </form>
        )}

        <Link to="/login" className="back-login">
          ← Back to login
        </Link>
      </div>
    </div>
  );
}


/* =========================
   USER PROFILE PAGE
========================= */

function Profile() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/auth/me", { credentials: "include" })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not load your profile.");
        return data.user;
      })
      .then((user) => {
        if (!active) return;
        setName(user.name || "");
        setEmail(user.email || "");
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleSave(e) {
    e.preventDefault();
    if (name.trim().length < 2) {
      setError("Name must be at least 2 characters.");
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch("/api/auth/profile", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update your profile.");
      setName(data.user.name);
      setSuccess(data.message || "Profile updated successfully.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } finally {
      navigate("/login");
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/hai-logo.png" alt="HAi logo" />
        </div>
        <div className="auth-heading">
          <h1>Your profile</h1>
          <p>View and update your Huda AI account details.</p>
        </div>

        {busy ? (
          <div className="auth-loading">Loading profile...</div>
        ) : (
          <form onSubmit={handleSave} className="auth-form">
            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                required
              />
            </label>
            <label>
              Email
              <input type="email" value={email} readOnly />
            </label>
            {error && <div className="auth-error">{error}</div>}
            {success && <div className="auth-success">{success}</div>}
            <button className="auth-submit" disabled={saving}>
              {saving ? "Saving..." : "Save changes"}
            </button>
          </form>
        )}
        {error && busy && <div className="auth-error">{error}</div>}
        <Link to="/chat" className="back-login">
          ← Back to chat
        </Link>
        <button type="button" className="auth-links" onClick={handleLogout}>
          Log out
        </button>
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
    let active = true;

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
        if (active) setStatus("authenticated");
      })
      .catch(() => {
        if (active) setStatus("unauthenticated");
      });

    return () => {
      active = false;
    };
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
  const chatInitializationStarted = useRef(false);
  const [initializationAttempt, setInitializationAttempt] = useState(0);

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
  // Avoid duplicate initialization requests, including React Strict Mode's
  // development-only effect replay.
  if (chatInitializationStarted.current) return;
  chatInitializationStarted.current = true;

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
      // Allow the user to retry initialization after a network or API failure.
      chatInitializationStarted.current = false;
      setError(err.message);
    }
  }

  initializeChat();
}, [initializationAttempt]);

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

    // Check for an active conversation before clearing the user's message.
    if (!conversationId) {
      setError("Please create a new chat first.");
      return;
    }

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

        <Link to="/profile" className="logout-button">
          Profile
        </Link>

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
          {!conversationId && error && (
            <button
              type="button"
              className="auth-submit"
              onClick={() => setInitializationAttempt((attempt) => attempt + 1)}
              disabled={busy}
            >
              Retry loading chat
            </button>
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
        path="/profile"
        element={
          <ProtectedRoute>
            <Profile />
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
