// --- Types ---

export interface Chapter {
  id: string;
  project_id: string;
  chapter_number: number;
  title: string | null;
  status: string;
  direction: string | null;
  draft_content: string | null;
  final_content: string | null;
  logic_review: Record<string, unknown> | null;
  style_review: Record<string, unknown> | null;
  extraction_result: Record<string, unknown> | null;
  next_chapter_suggestion: ForeseerResult | null;
  revision_count: number;
  tokens_used: number;
  generation_cost: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  owner_id: string;
  title: string;
  description: string | null;
  genre: string | null;
  created_at: string;
  updated_at: string;
  outline: string | null;
  character_cards: CharacterCard[] | Record<string, unknown> | null;
  world_settings: Record<string, unknown> | null;
  active_style_id: string | null;
  writing_preferences: WritingPreferences | string | null;
  style_controls: Record<string, number> | null;
  arc_plan: ArcPlan | null;
}

export interface ArcPlanAct {
  name: string;
  chapter_range: string;
  goal: string;
}

export interface ArcPlanMilestone {
  id: string;
  title: string;
  description?: string;
  target_chapter?: number;
  act?: number;
  status: "pending" | "achieved" | string;
  achieved_chapter?: number | null;
}

export interface ArcPlanCharacterArc {
  name: string;
  want?: string;
  need?: string;
  transformation?: string;
}

export interface ArcPlanSubplot {
  name: string;
  summary?: string;
  status?: string;
}

export interface ArcPlan {
  theme?: string;
  central_conflict?: string;
  total_chapters?: number;
  acts?: ArcPlanAct[];
  milestones?: ArcPlanMilestone[];
  character_arcs?: ArcPlanCharacterArc[];
  subplots?: ArcPlanSubplot[];
  updated_at_chapter?: number;
}

export interface StyleProfile {
  id: string;
  owner_id: string;
  name: string;
  author_name: string | null;
  description: string | null;
  source_books: { name: string }[] | null;
  total_chunks: number;
  style_features: Record<string, unknown> | null;
}

export interface ForeseerBranch {
  title: string;
  summary: string;
  tension: string;
  new_characters: string[];
  suggested_direction: string;
}

export interface ForeseerResult {
  overall_assessment?: string;
  branches?: ForeseerBranch[];
  foreshadowing_callbacks?: {
    hook: string;
    callback_suggestion: string;
    urgency: string;
  }[];
}

export interface CharacterCard {
  name?: string;
  identity?: string;
  abilities?: string;
  relationships?: string;
  description?: string;
  [key: string]: unknown;
}

export interface WritingPreferences {
  [key: string]: unknown;
}
