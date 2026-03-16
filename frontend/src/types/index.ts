// src/types/index.ts

export interface User {
  id: string;
  roll_number: string;
  email: string;
  name: string;
  department: string;
  avatar_url?: string;
  points: number;
  badges: Badge[];
  created_at: string;
}

export interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  earned_at: string;
}

export type ItemType = 'lost' | 'found';
export type ItemStatus = 'active' | 'claimed' | 'resolved';

export interface Item {
  id: string;
  type: ItemType;
  status: ItemStatus;
  title: string;
  description: string;
  category: string;
  location: string;
  campus_zone: string;
  lat?: number;
  lng?: number;
  images: string[];
  color?: string;
  brand?: string;
  tags: string[];
  features: string[];
  ocr_text?: string;
  ai_analysis?: AIAnalysis;
  owner: User;
  created_at: string;
  updated_at: string;
  match_count: number;
  view_count: number;
}

export interface AIAnalysis {
  suggested_title: string;
  suggested_description: string;
  category: string;
  category_confidence: number;
  brand?: string;
  color?: string;
  features: string[];
  tags: string[];
  ocr_text?: string;
  gemini_summary: string;
}

export interface Match {
  id: string;
  lost_item: Item;
  found_item: Item;
  similarity_score: number;
  match_reasons: string[];
  status: 'pending' | 'confirmed' | 'rejected';
  created_at: string;
}

export interface Claim {
  id: string;
  item: Item;
  claimant: User;
  message: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export interface Message {
  id: string;
  room_id: string;
  sender: User;
  content: string;
  type: 'text' | 'image' | 'system';
  read_by: string[];
  created_at: string;
}

export interface ChatRoom {
  id: string;
  participants: User[];
  item: Item;
  last_message?: Message;
  unread_count: number;
  created_at: string;
}

export interface Notification {
  id: string;
  type: 'match_found' | 'claim_received' | 'claim_approved' | 'item_resolved' | 'message' | 'badge_earned';
  title: string;
  body: string;
  data?: Record<string, string>;
  read: boolean;
  created_at: string;
}

export interface Stats {
  total_items: number;
  lost_items: number;
  found_items: number;
  resolved_items: number;
  active_matches: number;
  items_found_today: number;
  matches_today: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
}

export interface ItemFilters {
  type?: ItemType;
  category?: string;
  status?: ItemStatus;
  location?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  per_page?: number;
}

export const CATEGORIES = [
  { id: 'electronics', label: 'Electronics', icon: '💻', color: 'blue' },
  { id: 'clothing', label: 'Clothing', icon: '👕', color: 'purple' },
  { id: 'accessories', label: 'Accessories', icon: '⌚', color: 'yellow' },
  { id: 'books', label: 'Books', icon: '📚', color: 'amber' },
  { id: 'bags', label: 'Bags', icon: '🎒', color: 'orange' },
  { id: 'documents', label: 'Documents', icon: '📄', color: 'gray' },
  { id: 'keys', label: 'Keys', icon: '🔑', color: 'yellow' },
  { id: 'sports', label: 'Sports', icon: '⚽', color: 'green' },
  { id: 'jewelry', label: 'Jewelry', icon: '💍', color: 'pink' },
  { id: 'other', label: 'Other', icon: '📦', color: 'gray' },
] as const;

export const CAMPUS_ZONES = [
  'Main Building',
  'Library',
  'Cafeteria',
  'Sports Complex',
  'Hostel Block A',
  'Hostel Block B',
  'Labs Wing',
  'Auditorium',
  'Admin Block',
  'Parking Lot',
  'Ground',
  'Workshop',
] as const;
