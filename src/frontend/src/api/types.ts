/**
 * Інструмент: Claude
 * Застосування: TypeScript-типи фронтенду, побудовані 1:1 зі
 * src/api/schemas.py (жодного поля понад те, що реально повертає/приймає
 * бекенд).
 * Верифікація: Звірено вручну поле за полем з усіма Pydantic-схемами
 * schemas.py; коректність підтверджено компіляцією (`tsc -b`) та
 * продакшн-білдом (`vite build`) без помилок типів.
 */

export type UserRole = "candidate" | "mentor" | "admin";

export interface BoardOut {
  id: string;
  owner_id: string;
  access: "owner" | "mentor";
  created_at: string;
}

export interface UserOut {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserOut;
}

export interface RegisterRequest {
  email: string;
  password: string;
  // Бекенд дозволяє реєстрацію лише з роллю candidate (auth.py:register),
  // інша роль -> 403 Forbidden, тож фронтенд її не пропонує.
  role: "candidate";
}

export interface LoginRequest {
  email: string;
  password: string;
}

export type CardStatus = "active" | "rejected" | "offer_accepted";

export interface CardOut {
  id: string;
  board_id: string;
  stage_id: string;
  company: string;
  position: string;
  vacancy_url: string | null;
  requirements_text: string | null;
  deadline: string | null;
  notifications_enabled: boolean;
  status: CardStatus;
  position_index: number;
  created_at: string;
  updated_at: string;
}

export interface CardCreate {
  company: string;
  position: string;
  vacancy_url?: string | null;
  requirements_text?: string | null;
  deadline?: string | null;
  notifications_enabled?: boolean;
  stage_id: string;
}

export interface CardUpdate {
  company?: string;
  position?: string;
  vacancy_url?: string | null;
  requirements_text?: string | null;
  deadline?: string | null;
  notifications_enabled?: boolean;
  status?: CardStatus;
}

export interface CardMove {
  stage_id: string;
  position_index: number;
}

export interface PaginationMeta {
  limit: number;
  offset: number;
  total: number;
}

export interface CardListResponse {
  items: CardOut[];
  pagination: PaginationMeta;
}

export interface StageOut {
  id: string;
  board_id: string;
  name: string;
  order_index: number;
  created_at: string;
}

export interface StageCreate {
  name: string;
  order_index?: number | null;
}

export interface StageUpdate {
  name?: string;
  order_index?: number;
}

export interface CardLinkOut {
  id: string;
  card_id: string;
  url: string;
  created_at: string;
}

export interface CardLinkCreate {
  url: string;
}

export type NoteSource = "candidate" | "recruiter" | "ai";

export interface CardNoteOut {
  id: string;
  card_id: string;
  content: string;
  source: NoteSource;
  created_at: string;
  updated_at: string;
}

export interface CardNoteCreate {
  content: string;
  source?: NoteSource;
}

export interface CardNoteUpdate {
  content: string;
}

export interface ErrorDetail {
  field: string;
  message: string;
  provided_value: string | null;
}

export interface ErrorBody {
  code: string;
  message: string;
  details: ErrorDetail[];
  request_id: string;
  documentation: string | null;
}

export interface ErrorResponse {
  error: ErrorBody;
}

// --- mentors / invitations ---

export type MentorStatus = "pending" | "accepted" | "revoked";

export interface BoardMentorOut {
  id: string;
  board_id: string;
  mentor_id: string | null;
  email: string;
  status: MentorStatus;
  invite_token: string;
  invited_at: string;
  accepted_at: string | null;
}

export interface InviteMentorRequest {
  email: string;
}

export interface AcceptInvitationRequest {
  password?: string;
}

export interface AcceptInvitationResponse {
  message: string;
  board_id: string;
  status: MentorStatus;
  access_token: string | null;
}

// --- comments ---

export interface CommentCreate {
  content: string;
}

export interface CommentOut {
  id: string;
  card_id: string;
  author_id: string;
  content: string;
  created_at: string;
}

