/**
 * Cerberus Frontend - Global TypeScript Types
 * Aligned with backend domain entities
 */

// ============================================================================
// User Types
// ============================================================================

export type UserRole = "superadmin" | "admin" | "user";

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
  profile: UserProfile | null;
}

export interface UserProfile {
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  country: string | null;
  website: string | null;
  github: string | null;
  twitter: string | null;
}

export interface UserStats {
  total_solves: number;
  total_points: number;
  rank: number;
  streak_days: number;
  last_solve_at: string | null;
}

// ============================================================================
// Challenge Types
// ============================================================================

export type ChallengeCategory =
  | "web"
  | "crypto"
  | "pwn"
  | "reverse"
  | "forensics"
  | "misc"
  | "osint"
  | "blockchain"
  | "steganography";

export type ChallengeDifficulty = "easy" | "medium" | "hard" | "extreme";

export type ChallengeStatus = "draft" | "published" | "archived";

export interface Challenge {
  id: string;
  title: string;
  description: string;
  category: ChallengeCategory;
  difficulty: ChallengeDifficulty;
  points: number;
  status: ChallengeStatus;
  author_id: string;
  author: User | null;
  attachments: Attachment[];
  hints: Hint[];
  tags: string[];
  solve_count: number;
  is_solved: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChallengeDetail extends Challenge {
  dependencies: string[];
  mcq_questions: MCQQuestion[];
}

export interface Attachment {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  download_url: string;
}

// ============================================================================
// Hint Types
// ============================================================================

export interface Hint {
  id: string;
  challenge_id: string;
  content: string;
  cost: number;
  order: number;
  is_unlocked: boolean;
  unlocked_at: string | null;
}

// ============================================================================
// MCQ Types
// ============================================================================

export interface MCQQuestion {
  id: string;
  challenge_id: string;
  question: string;
  options: MCQOption[];
  points: number;
  is_answered: boolean;
  is_correct: boolean | null;
}

export interface MCQOption {
  id: string;
  text: string;
  order: number;
}

export interface MCQAnswer {
  question_id: string;
  selected_option_id: string;
}

export interface MCQResult {
  question_id: string;
  correct: boolean;
  points_awarded: number;
  correct_option_id: string;
}

// ============================================================================
// Submission Types
// ============================================================================

export type SubmissionStatus = "pending" | "correct" | "incorrect" | "rate_limited";

export interface Submission {
  id: string;
  challenge_id: string;
  user_id: string;
  flag: string;
  status: SubmissionStatus;
  points_awarded: number;
  attempt_number: number;
  submitted_at: string;
}

export interface SubmissionResponse {
  correct: boolean;
  message: string;
  points_awarded: number;
  solve_position: number | null;
}

// ============================================================================
// Leaderboard Types
// ============================================================================

export interface LeaderboardEntry {
  rank: number;
  user: User;
  total_points: number;
  total_solves: number;
  last_solve_at: string;
  is_current_user: boolean;
}

export interface TeamLeaderboardEntry {
  rank: number;
  team_name: string;
  total_points: number;
  total_solves: number;
  member_count: number;
}

// ============================================================================
// API Types
// ============================================================================

export interface ApiResponse<T> {
  data: T;
  message: string | null;
  status: "success" | "error";
}

export interface ApiError {
  detail: string;
  code: string;
  field: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ApiRequestConfig {
  params?: Record<string, string | number | boolean | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

// ============================================================================
// Auth Types
// ============================================================================

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// ============================================================================
// Theme Types
// ============================================================================

export type ThemeMode = "light" | "dark" | "system";

export interface ThemeConfig {
  mode: ThemeMode;
  safetyOrange: string;
  fontSize: "small" | "medium" | "large";
  reducedMotion: boolean;
  highContrast: boolean;
}

// ============================================================================
// UI Types
// ============================================================================

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface ModalState {
  isOpen: boolean;
  title: string;
  content: unknown;
  onClose?: () => void;
}

export interface FilterState {
  category: ChallengeCategory | null;
  difficulty: ChallengeDifficulty | null;
  status: "all" | "solved" | "unsolved" | "locked";
  search: string;
  sortBy: "points" | "difficulty" | "name" | "solves";
  sortOrder: "asc" | "desc";
}

// ============================================================================
// WebSocket Types
// ============================================================================

export type WebSocketEventType =
  | "solve"
  | "leaderboard_update"
  | "challenge_unlock"
  | "notification"
  | "user_join"
  | "user_leave";

export interface WebSocketMessage {
  type: WebSocketEventType;
  payload: unknown;
  timestamp: string;
}

export interface SolveEvent {
  user_id: string;
  username: string;
  challenge_id: string;
  challenge_title: string;
  points: number;
  solve_position: number;
}

// ============================================================================
// Terminal Types
// ============================================================================

export interface TerminalLine {
  id: string;
  content: string;
  type: "input" | "output" | "error" | "success" | "info";
  timestamp: string;
}

// ============================================================================
// Editor Types
// ============================================================================

export type EditorLanguage =
  | "python"
  | "javascript"
  | "typescript"
  | "c"
  | "cpp"
  | "java"
  | "go"
  | "rust"
  | "bash"
  | "powershell"
  | "sql"
  | "json"
  | "yaml"
  | "markdown";

export interface CodeSubmission {
  language: EditorLanguage;
  code: string;
  challenge_id: string;
}

// ============================================================================
// Admin Types
// ============================================================================

export interface AdminStats {
  total_users: number;
  total_challenges: number;
  total_solves: number;
  active_users_today: number;
  submissions_today: number;
  system_health: SystemHealth;
}

export interface SystemHealth {
  database: "healthy" | "degraded" | "down";
  redis: "healthy" | "degraded" | "down";
  storage: "healthy" | "degraded" | "down";
  last_checked: string;
}

export interface UserManagementFilters {
  role: UserRole | null;
  is_active: boolean | null;
  search: string;
}

// ============================================================================
// Form Types
// ============================================================================

export interface FormFieldError {
  message: string;
  type: string;
}

export type FormErrors<T> = Partial<Record<keyof T, FormFieldError>>;

// ============================================================================
// Analytics Types
// ============================================================================

export interface ChallengeAnalytics {
  challenge_id: string;
  title: string;
  solve_attempts: number;
  solve_count: number;
  solve_rate: number;
  average_solve_time_minutes: number;
  hint_unlock_rate: number;
}

export interface UserActivity {
  date: string;
  submissions: number;
  solves: number;
  points_earned: number;
}

// ============================================================================
// PWA Types
// ============================================================================

export interface PWAConfig {
  enabled: boolean;
  theme_color: string;
  background_color: string;
  display: "standalone" | "fullscreen" | "minimal-ui" | "browser";
  orientation: "portrait" | "landscape" | "any";
}

// ============================================================================
// Security Types
// ============================================================================

export interface SecurityConfig {
  csp_nonce: string;
  request_signing_enabled: boolean;
  debugger_detection_enabled: boolean;
  flag_encryption_enabled: boolean;
}

export interface EncryptedFlag {
  ciphertext: string;
  iv: string;
  tag: string;
}