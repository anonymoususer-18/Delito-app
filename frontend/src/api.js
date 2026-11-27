const API_URL = import.meta.env.VITE_API_URL || "";

async function ensureToken() {
  let token = localStorage.getItem("delito_token");
  if (!token) {
    const response = await fetch(`${API_URL}/api/v1/auth/demo-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "DELITO Customer" }),
    });
    const data = await response.json();
    token = data.access_token;
    localStorage.setItem("delito_token", token);
  }
  return token;
}

export async function api(path, options = {}) {
  const token = await ensureToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`DELITO request failed (${response.status})`);
  }
  return response.json();
}
