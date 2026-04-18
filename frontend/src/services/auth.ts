const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

function normalizeAuthApiBase(url: string): string {
  const base = url.trim().replace(/\/+$/, "");
  if (base.endsWith("/api/v1")) {
    return base;
  }
  return `${base}/api/v1`;
}

export const API_URL = normalizeAuthApiBase(rawApiUrl);

export const login = async (username: string, password: string) => {
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);

  const response = await fetch(`${API_URL}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString(),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Login failed");
  }

  return response.json();
};

export const register = async (
  username: string,
  password: string,
  email: string,
) => {
  const response = await fetch(`${API_URL}/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password, email }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Registration failed");
  }

  return response.json();
};
