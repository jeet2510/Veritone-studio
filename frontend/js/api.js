const VeriToneAPI = {
  async request(url, options = {}) {
    const response = await fetch(url, { credentials: "same-origin", ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  },

  session() { return this.request("/api/auth/me"); },
  login(credentials) {
    return this.request("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(credentials) });
  },
  register(credentials) {
    return this.request("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(credentials) });
  },
  logout() { return this.request("/api/auth/logout", { method: "POST" }); },
  runAnalysis(formData) {
    return this.request("/api/analyze", { method: "POST", body: formData });
  },
  fetchHistory() { return this.request("/api/analyses"); },
  fetchAnalysisById(id) { return this.request(`/api/analyses/${id}`); },
  deleteAnalysisById(id) { return this.request(`/api/analyses/${id}`, { method: "DELETE" }); },
  adminOverview() { return this.request("/api/admin/overview"); },
  adminUsers() { return this.request("/api/admin/users"); },
  adminUpdateUser(id, changes) {
    return this.request(`/api/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) });
  },
  adminAnalyses() { return this.request("/api/admin/analyses"); },
  adminAnalysis(id) { return this.request(`/api/admin/analyses/${id}`); },
};