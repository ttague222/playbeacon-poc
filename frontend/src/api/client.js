import axios from 'axios';
import { auth } from '../firebase';

// Local development API
const API_BASE_URL = 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(async (config) => {
  const currentUser = auth.currentUser;
  if (currentUser) {
    const token = await currentUser.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// API methods
export const api = {
  // Get game queue for a user (personalized recommendations)
  getQueue: async (limit = 10) => {
    const response = await apiClient.post('/queue', {
      limit: limit,
    });
    return response.data;
  },

  // Submit feedback
  submitFeedback: async (universeId, feedback) => {
    const response = await apiClient.post('/feedback', {
      universe_id: universeId,
      feedback: feedback, // 1 = like, 0 = skip, -1 = dislike
    });
    return response.data;
  },

  // Get all games
  getGames: async (limit = 50, offset = 0) => {
    const response = await apiClient.get(`/games?limit=${limit}&offset=${offset}`);
    return { games: response.data };
  },

  // Get specific game
  getGame: async (universeId) => {
    const response = await apiClient.get(`/games/${universeId}`);
    return response.data;
  },

  // Crawl games (admin function)
  crawlGames: async (keywords, limitPerKeyword = 50) => {
    const response = await apiClient.post('/crawl', {
      keywords: keywords,
      limit_per_keyword: limitPerKeyword,
    });
    return response.data;
  },

  // Generate embeddings (admin function)
  generateEmbeddings: async () => {
    const response = await apiClient.post('/generate-embeddings');
    return response.data;
  },

  // Get stats (admin function)
  getStats: async () => {
    const statsResponse = await apiClient.get('/pinecone/stats');
    const healthResponse = await apiClient.get('/health');

    return {
      ...statsResponse.data,
      ...healthResponse.data
    };
  },

  // Get health check
  getHealth: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },

  // Get admin status
  getAdminStatus: async () => {
    const response = await apiClient.get('/admin/status');
    return response.data;
  },

  // Reset user profile/feedback
  resetProfile: async () => {
    const response = await apiClient.post('/user/reset-profile');
    return response.data;
  },

  // Crawler APIs
  crawlerStatus: async () => {
    const response = await apiClient.get('/crawler/status');
    return response.data;
  },

  crawlerEmbedMissing: async (limit = 50) => {
    const response = await apiClient.post(`/crawler/embed-missing?limit=${limit}`);
    return response.data;
  },

  crawlerEnqueue: async (universeIds = [], source = 'manual', priority = 5) => {
    const response = await apiClient.post('/crawler/enqueue', {
      universe_ids: universeIds,
      source,
      priority,
    });
    return response.data;
  },

  crawlerProcessBatch: async (limit = 10) => {
    const response = await apiClient.post(`/crawler/process-batch?limit=${limit}`);
    return response.data;
  },

  crawlerEnqueueKeywords: async (keywords = [], limitPerKeyword = 20, priority = 5) => {
    const response = await apiClient.post('/crawler/enqueue-keywords', {
      keywords,
      limit_per_keyword: limitPerKeyword,
      priority,
    });
    return response.data;
  },

  crawlerEnqueueSorts: async (sorts = [], limit = 50, priority = 6) => {
    const response = await apiClient.post('/crawler/enqueue-sorts', {
      sorts,
      limit,
      priority,
    });
    return response.data;
  },

  crawlerEnqueueGraph: async (universeIds = [], priority = 6) => {
    const response = await apiClient.post('/crawler/enqueue-graph', {
      universe_ids: universeIds,
      priority,
    });
    return response.data;
  },

  crawlerFixThumbnails: async (limit = 50) => {
    const response = await apiClient.post('/crawler/fix-thumbnails', {
      limit,
    });
    return response.data;
  },

  crawlerRunFull: async () => {
    const response = await apiClient.post('/crawler/run-full');
    return response.data;
  },

  crawlerRegenEmbeddings: async (limit = 200) => {
    const response = await apiClient.post('/crawler/regenerate-embeddings', { limit });
    return response.data;
  },

  crawlerToggleSchedule: async (payload) => {
    const response = await apiClient.post('/crawler/schedule-toggle', payload);
    return response.data;
  },

  // Roblox Import Methods
  // Resolve Roblox username to user data
  resolveRobloxUsername: async (username) => {
    const response = await apiClient.get(`/roblox/resolve?username=${encodeURIComponent(username)}`);
    return response.data;
  },

  // Get Roblox import data (favorites, badges, groups)
  getRobloxImportData: async (userId) => {
    const response = await apiClient.get(`/roblox/import-data?userId=${userId}`);
    return response.data;
  },

  // Import selected Roblox games
  importRobloxGames: async (robloxUserId, robloxUsername, selectedGames) => {
    const response = await apiClient.post('/roblox/import-selected', {
      robloxUserId,
      robloxUsername,
      selectedGames,
    });
    return response.data;
  },

  // Skip Roblox import
  skipRobloxImport: async () => {
    const response = await apiClient.post('/user/skip-roblox-import');
    return response.data;
  },
};

export default apiClient;
