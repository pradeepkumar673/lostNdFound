// src/lib/api.ts
import axios, { AxiosError } from 'axios';
import type { Item, ItemFilters, PaginatedResponse, Match, ChatRoom, Message, Notification, Stats, User, Claim, AIAnalysis } from '@/types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// Request interceptor: attach JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('clf_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401
api.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('clf_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ─── Auth ────────────────────────────────────────────────────
export const authApi = {
  login: (data: { email: string; password: string }) =>
    api.post<{ token: string; user: User }>('/auth/login', data).then((r) => r.data),
  register: (data: { email: string; password: string; roll_number: string; name: string; department: string }) =>
    api.post<{ token: string; user: User }>('/auth/register', data).then((r) => r.data),
  me: () => api.get<User>('/auth/me').then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
  updateProfile: (data: FormData) =>
    api.patch<User>('/auth/profile', data, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data),
};

// ─── Items ────────────────────────────────────────────────────
export const itemsApi = {
  list: (filters: ItemFilters = {}) =>
    api.get<PaginatedResponse<Item>>('/items', { params: filters }).then((r) => r.data),
  get: (id: string) => api.get<Item>(`/items/${id}`).then((r) => r.data),
  create: (data: FormData) =>
    api.post<Item>('/items', data, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data),
  update: (id: string, data: Partial<Item>) => api.patch<Item>(`/items/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/items/${id}`).then((r) => r.data),
  analyze: (formData: FormData) =>
    api.post<AIAnalysis>('/items/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data),
  searchByImage: (formData: FormData) =>
    api.post<Item[]>('/items/search-by-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data),
  markResolved: (id: string) => api.patch<Item>(`/items/${id}/resolve`).then((r) => r.data),
  getMatches: (id: string) => api.get<Match[]>(`/items/${id}/matches`).then((r) => r.data),
  claimItem: (id: string, message: string) =>
    api.post<Claim>(`/items/${id}/claim`, { message }).then((r) => r.data),
  myItems: () => api.get<Item[]>('/items/my').then((r) => r.data),
};

// ─── Matches ────────────────────────────────────────────────────
export const matchesApi = {
  list: () => api.get<Match[]>('/matches').then((r) => r.data),
  get: (id: string) => api.get<Match>(`/matches/${id}`).then((r) => r.data),
  confirm: (id: string) => api.patch<Match>(`/matches/${id}/confirm`).then((r) => r.data),
  reject: (id: string) => api.patch<Match>(`/matches/${id}/reject`).then((r) => r.data),
};

// ─── Chat ────────────────────────────────────────────────────
export const chatApi = {
  rooms: () => api.get<ChatRoom[]>('/chat/rooms').then((r) => r.data),
  room: (id: string) => api.get<ChatRoom>(`/chat/rooms/${id}`).then((r) => r.data),
  messages: (roomId: string, page = 1) =>
    api.get<PaginatedResponse<Message>>(`/chat/rooms/${roomId}/messages`, { params: { page } }).then((r) => r.data),
  sendMessage: (roomId: string, content: string) =>
    api.post<Message>(`/chat/rooms/${roomId}/messages`, { content }).then((r) => r.data),
  createRoom: (itemId: string, participantId: string) =>
    api.post<ChatRoom>('/chat/rooms', { item_id: itemId, participant_id: participantId }).then((r) => r.data),
  markRead: (roomId: string) => api.patch(`/chat/rooms/${roomId}/read`).then((r) => r.data),
};

// ─── Notifications ────────────────────────────────────────────────────
export const notificationsApi = {
  list: (page = 1) =>
    api.get<PaginatedResponse<Notification>>('/notifications', { params: { page } }).then((r) => r.data),
  markRead: (id: string) => api.patch(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () => api.patch('/notifications/read-all').then((r) => r.data),
  unreadCount: () => api.get<{ count: number }>('/notifications/unread-count').then((r) => r.data),
};

// ─── Stats ────────────────────────────────────────────────────
export const statsApi = {
  global: () => api.get<Stats>('/stats').then((r) => r.data),
  heatmap: () => api.get<Array<{ lat: number; lng: number; weight: number; type: string }>>('/stats/heatmap').then((r) => r.data),
};
