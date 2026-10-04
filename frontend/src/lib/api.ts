import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api";

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach token on every request
client.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  // Let browser set multipart boundary automatically for FormData
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

// Handle 401 responses
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  // --- Auth ---
  login: async (username: string, password: string) => {
    // Backend uses OAuth2PasswordRequestForm (form-encoded)
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);
    const { data } = await client.post("/auth/login", formData, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return data;
  },
  register: async (payload: { username: string; email: string; password: string; display_name?: string }) => {
    const { data } = await client.post("/auth/register", payload);
    return data;
  },
  getMe: async () => {
    const { data } = await client.get("/auth/me");
    return data;
  },
  getLLMSettings: async () => {
    const { data } = await client.get("/auth/llm-settings");
    return data;
  },
  updateLLMSettings: async (settings: Record<string, unknown>) => {
    const { data } = await client.put("/auth/llm-settings", settings);
    return data;
  },
  deleteLLMSettings: async () => {
    const { data } = await client.delete("/auth/llm-settings");
    return data;
  },

  // --- Projects ---
  listProjects: async () => {
    const { data } = await client.get("/projects/");
    return data;
  },
  getProject: async (projectId: string) => {
    const { data } = await client.get(`/projects/${projectId}`);
    return data;
  },
  createProject: async (payload: Record<string, unknown>) => {
    const { data } = await client.post("/projects/", payload);
    return data;
  },
  updateProject: async (projectId: string, payload: Record<string, unknown>) => {
    const { data } = await client.put(`/projects/${projectId}`, payload);
    return data;
  },
  deleteProject: async (projectId: string) => {
    const { data } = await client.delete(`/projects/${projectId}`);
    return data;
  },
  resetWritingPreferences: async (projectId: string) => {
    const { data } = await client.delete(`/projects/${projectId}/writing-preferences`);
    return data;
  },
  generateArcPlan: async (projectId: string) => {
    const { data } = await client.post(`/projects/${projectId}/arc-plan/generate`);
    return data;
  },

  // --- Chapters ---
  listChapters: async (projectId: string) => {
    const { data } = await client.get(`/projects/${projectId}/chapters`);
    return data;
  },
  getChapter: async (projectId: string, chapterId: string) => {
    const { data } = await client.get(`/projects/${projectId}/chapters/${chapterId}`);
    return data;
  },
  createChapter: async (projectId: string, payload: Record<string, unknown>) => {
    const { data } = await client.post(`/projects/${projectId}/chapters`, payload);
    return data;
  },
  updateChapter: async (projectId: string, chapterId: string, payload: Record<string, unknown>) => {
    const { data } = await client.put(`/projects/${projectId}/chapters/${chapterId}`, payload);
    return data;
  },
  deleteChapter: async (projectId: string, chapterId: string) => {
    const { data } = await client.delete(`/projects/${projectId}/chapters/${chapterId}`);
    return data;
  },
  generateChapter: async (projectId: string, chapterId: string) => {
    const { data } = await client.post(`/projects/${projectId}/chapters/${chapterId}/generate`);
    return data;
  },
  finalizeChapter: async (projectId: string, chapterId: string) => {
    const { data } = await client.post(`/projects/${projectId}/chapters/${chapterId}/finalize`);
    return data;
  },
  convertChapterScript: async (projectId: string, chapterId: string, target: "simplified" | "traditional") => {
    const { data } = await client.post(`/projects/${projectId}/chapters/${chapterId}/convert-script`, { target });
    return data;
  },

  // --- Styles ---
  listStyles: async () => {
    const { data } = await client.get("/styles/");
    return data;
  },
  getStyle: async (styleId: string) => {
    const { data } = await client.get(`/styles/${styleId}`);
    return data;
  },
  createStyle: async (payload: Record<string, unknown>) => {
    const { data } = await client.post("/styles/", payload);
    return data;
  },
  updateStyle: async (styleId: string, payload: Record<string, unknown>) => {
    const { data } = await client.put(`/styles/${styleId}`, payload);
    return data;
  },
  deleteStyle: async (styleId: string) => {
    const { data } = await client.delete(`/styles/${styleId}`);
    return data;
  },
  uploadStyleFiles: async (styleId: string, files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const { data } = await client.post(`/styles/${styleId}/upload-files`, formData);
    return data;
  },
  analyzeStyle: async (styleId: string) => {
    const { data } = await client.post(`/styles/${styleId}/analyze`);
    return data;
  },

  // --- Export ---
  exportProject: async (projectId: string, format: "epub" | "docx") => {
    const response = await client.get(`/projects/${projectId}/export/${format}`, {
      responseType: "blob",
    });
    return response;
  },
};
