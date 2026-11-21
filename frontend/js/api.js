const VeriToneAPI = {
  async runAnalysis(formData) {
    const res = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Analysis request failed.");
    }
    return data;
  },

  async fetchHistory() {
    const res = await fetch("/api/analyses");
    if (!res.ok) throw new Error("Failed to fetch history.");
    return res.json();
  },

  async fetchAnalysisById(id) {
    const res = await fetch(`/api/analyses/${id}`);
    if (!res.ok) throw new Error("Failed to load analysis record.");
    return res.json();
  },

  async deleteAnalysisById(id) {
    const res = await fetch(`/api/analyses/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete analysis record.");
    return res.json();
  },
};