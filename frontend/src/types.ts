// --- Vertical ---

export interface VerticalSeason {
  id: number;
  vertical_id: number;
  season_window: string;
  focus: string;
  hook: string | null;
  example_post: string | null;
  created_at: string;
  updated_at: string;
}

export interface Vertical {
  id: number;
  name: string;
  trigger_type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  seasons: VerticalSeason[];
}

export interface VerticalCreate {
  name: string;
  trigger_type: string;
  is_active: boolean;
}

export interface VerticalUpdate {
  name?: string;
  trigger_type?: string;
  is_active?: boolean;
}

// --- Collected Data ---

export interface CollectedDataItem {
  id: number;
  source: string;
  source_id: string | null;
  content_type: string;
  title: string;
  body: string | null;
  url: string | null;
  file_urls: string[] | null;
  tags: string[] | null;
  platform_metadata: Record<string, unknown> | null;
  published_at: string | null;
  reach_score: number;
  is_trending: boolean;
  is_all_time_favourite: boolean;
}

export interface ChannelData {
  trending: CollectedDataItem[];
  all_time_favourite: CollectedDataItem[];
}

export interface HashtagItem {
  name: string;
  posts_count: number;
}

export interface VerticalCollectedData {
  vertical_id: number;
  channels: Record<string, ChannelData>;
  news: CollectedDataItem[];
  meta_ads: CollectedDataItem[];
  hashtags: HashtagItem[];
}
