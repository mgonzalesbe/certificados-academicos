const msgEl = document.getElementById("msg-global");

function setupPasswordToggle(inputId, btnId) {
  const input = document.getElementById(inputId);
  const btn = document.getElementById(btnId);
  if (!input || !btn) return;
  btn.addEventListener("click", () => {
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.textContent = showing ? "👁" : "🙈";
    btn.setAttribute(
      "aria-label",
      showing ? "Mostrar contraseña" : "Ocultar contraseña",
    );
  });
}

setupPasswordToggle("login-pass", "toggle-login-pass");
setupPasswordToggle("reg-pass", "toggle-reg-pass");

function showMsg(text, ok) {
  msgEl.textContent = text;
  msgEl.classList.remove(
    "hidden",
    "bg-red-100",
    "text-red-800",
    "bg-emerald-100",
    "text-emerald-800",
  );
  msgEl.classList.add(
    ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800",
  );
}

document.getElementById("tab-login").addEventListener("click", () => {
  document.getElementById("form-login").classList.remove("hidden");
  document.getElementById("form-register").classList.add("hidden");
  document
    .getElementById("tab-login")
    .classList.add("bg-white", "shadow-sm", "text-blue-800");
  document.getElementById("tab-login").classList.remove("text-gray-600");
  document
    .getElementById("tab-register")
    .classList.remove("bg-white", "shadow-sm", "text-blue-800");
  document.getElementById("tab-register").classList.add("text-gray-600");
});

document.getElementById("tab-register").addEventListener("click", () => {
  document.getElementById("form-register").classList.remove("hidden");
  document.getElementById("form-login").classList.add("hidden");
  document
    .getElementById("tab-register")
    .classList.add("bg-white", "shadow-sm", "text-blue-800");
  document.getElementById("tab-register").classList.remove("text-gray-600");
  document
    .getElementById("tab-login")
    .classList.remove("bg-white", "shadow-sm", "text-blue-800");
  document.getElementById("tab-login").classList.add("text-gray-600");
});

document.getElementById("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  msgEl.classList.add("hidden");
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({
      username: document.getElementById("login-user").value.trim(),
      password: document.getElementById("login-pass").value,
    }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    showMsg(data.error || "Error al iniciar sesión", false);
    return;
  }
  if (data.user?.role === "admin") {
    window.location.href = "/app/admin";
  } else {
    window.location.href = "/app/alumno";
  }
});

document
  .getElementById("form-register")
  .addEventListener("submit", async (e) => {
    e.preventDefault();
    msgEl.classList.add("hidden");
    const username = document.getElementById("reg-user").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-pass").value;
    const r = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        username: username,
        documento_identidad: document.getElementById("reg-doc").value.trim(),
        nombres: document.getElementById("reg-nombres").value.trim(),
        apellidos: document.getElementById("reg-apellidos").value.trim(),
        email: email,
        password: password,
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      showMsg(data.error || "No se pudo registrar", false);
      return;
    }
    // Auto-login after successful registration
    const loginR = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        username: email, // Use email for login
        password: password,
      }),
    });
    const loginData = await loginR.json().catch(() => ({}));
    if (!loginR.ok) {
      showMsg(
        "Cuenta creada, pero error al iniciar sesión automáticamente. Inicie sesión manualmente.",
        false,
      );
      document.getElementById("tab-login").click();
      return;
    }
    if (loginData.user?.role === "admin") {
      window.location.href = "/app/admin";
    } else {
      window.location.href = "/app/alumno";
    }
  });
