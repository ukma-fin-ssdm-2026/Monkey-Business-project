/**
 * Інструмент: Claude
 * Застосування: Єдина точка звернення фронтенду до API — обгортка над
 * fetch з усіма ендпоінтами з routers/*.py, auth.py, і розбором
 * ErrorResponse (schemas.py/errors.py) в типізований ApiError.
 * Верифікація: Кожен виклик звірено зі сигнатурою відповідного роутера
 * (метод, шлях, тіло, статус 204 для DELETE); e2e не ганяно (бекенд не
 * піднімався в цій сесії), перевірено типами (tsc) і продакшн-білдом.
 */

import type {
  AcceptInvitationRequest,
  AcceptInvitationResponse,
  BoardMentorOut,
  CardCreate,
  CardLinkCreate,
  CardLinkOut,
  CardListResponse,
  CardMove,
  CardNoteCreate,
  CardNoteOut,
  CardNoteUpdate,
  CardOut,
  CardUpdate,
  CommentCreate,
  CommentOut,
  ErrorResponse,
  InviteMentorRequest,
  LoginRequest,
  RegisterRequest,
  StageCreate,
  StageOut,
  StageUpdate,
  TokenResponse,
} from "./types";

// У dev-режимі Vite проксіює /v1 та /health на бекенд (vite.config.ts),
// тож відносний шлях працює без CORS. У проді достатньо віддавати
// фронтенд через той самий origin/reverse-proxy, що й API, або
// задати VITE_API_BASE_URL на білд-час — бекенд при цьому не змінюється.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;
  details: { field: string; message: string; provided_value: string | null }[];

  constructor(status: number, body: ErrorResponse) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.status = status;
    this.requestId = body.error.request_id;
    this.details = body.error.details ?? [];
  }
}

export function formatApiError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.details && err.details.length > 0) {
      const detailsMsg = err.details.map((d) => d.message).join(", ");
      return `${err.message}: ${detailsMsg}`;
    }
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
}

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(
      "Немає з'єднання з API. Перевірте, що бекенд запущено (docker compose up -d --build) і доступний.",
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    if (data && data.error) {
      throw new ApiError(res.status, data as ErrorResponse);
    }
    throw new Error(`Запит не вдався: HTTP ${res.status}`);
  }

  return data as T;
}

export const api = {
  // --- auth ---
  register: (payload: RegisterRequest) =>
    request<TokenResponse>("POST", "/v1/auth/register", payload),
  login: (payload: LoginRequest) =>
    request<TokenResponse>("POST", "/v1/auth/login", payload),

  // --- stages ---
  listStages: (boardId: string) =>
    request<StageOut[]>("GET", `/v1/boards/${boardId}/stages`),
  createStage: (boardId: string, payload: StageCreate) =>
    request<StageOut>("POST", `/v1/boards/${boardId}/stages`, payload),
  updateStage: (boardId: string, stageId: string, payload: StageUpdate) =>
    request<StageOut>(
      "PATCH",
      `/v1/boards/${boardId}/stages/${stageId}`,
      payload,
    ),
  deleteStage: (boardId: string, stageId: string) =>
    request<void>("DELETE", `/v1/boards/${boardId}/stages/${stageId}`),

  // --- cards ---
  listCards: (boardId: string, limit = 100, offset = 0) =>
    request<CardListResponse>(
      "GET",
      `/v1/boards/${boardId}/cards?limit=${limit}&offset=${offset}`,
    ),
  createCard: (boardId: string, payload: CardCreate) =>
    request<CardOut>("POST", `/v1/boards/${boardId}/cards`, payload),
  getCard: (boardId: string, cardId: string) =>
    request<CardOut>("GET", `/v1/boards/${boardId}/cards/${cardId}`),
  updateCard: (boardId: string, cardId: string, payload: CardUpdate) =>
    request<CardOut>(
      "PATCH",
      `/v1/boards/${boardId}/cards/${cardId}`,
      payload,
    ),
  deleteCard: (boardId: string, cardId: string) =>
    request<void>("DELETE", `/v1/boards/${boardId}/cards/${cardId}`),
  moveCard: (boardId: string, cardId: string, payload: CardMove) =>
    request<CardOut>(
      "POST",
      `/v1/boards/${boardId}/cards/${cardId}/move`,
      payload,
    ),

  // --- card links ---
  listLinks: (boardId: string, cardId: string) =>
    request<CardLinkOut[]>(
      "GET",
      `/v1/boards/${boardId}/cards/${cardId}/links`,
    ),
  createLink: (boardId: string, cardId: string, payload: CardLinkCreate) =>
    request<CardLinkOut>(
      "POST",
      `/v1/boards/${boardId}/cards/${cardId}/links`,
      payload,
    ),
  deleteLink: (boardId: string, cardId: string, linkId: string) =>
    request<void>(
      "DELETE",
      `/v1/boards/${boardId}/cards/${cardId}/links/${linkId}`,
    ),

  // --- card notes ---
  listNotes: (boardId: string, cardId: string) =>
    request<CardNoteOut[]>(
      "GET",
      `/v1/boards/${boardId}/cards/${cardId}/notes`,
    ),
  createNote: (boardId: string, cardId: string, payload: CardNoteCreate) =>
    request<CardNoteOut>(
      "POST",
      `/v1/boards/${boardId}/cards/${cardId}/notes`,
      payload,
    ),
  updateNote: (
    boardId: string,
    cardId: string,
    noteId: string,
    payload: CardNoteUpdate,
  ) =>
    request<CardNoteOut>(
      "PATCH",
      `/v1/boards/${boardId}/cards/${cardId}/notes/${noteId}`,
      payload,
    ),
  deleteNote: (boardId: string, cardId: string, noteId: string) =>
    request<void>(
      "DELETE",
      `/v1/boards/${boardId}/cards/${cardId}/notes/${noteId}`,
    ),

  // --- comments ---
  listComments: (boardId: string, cardId: string) =>
    request<CommentOut[]>(
      "GET",
      `/v1/boards/${boardId}/cards/${cardId}/comments`,
    ),
  createComment: (boardId: string, cardId: string, payload: CommentCreate) =>
    request<CommentOut>(
      "POST",
      `/v1/boards/${boardId}/cards/${cardId}/comments`,
      payload,
    ),
  deleteComment: (boardId: string, cardId: string, commentId: string) =>
    request<void>(
      "DELETE",
      `/v1/boards/${boardId}/cards/${cardId}/comments/${commentId}`,
    ),

  // --- mentors ---
  listMentors: (boardId: string) =>
    request<BoardMentorOut[]>("GET", `/v1/boards/${boardId}/mentors`),
  inviteMentor: (boardId: string, payload: InviteMentorRequest) =>
    request<BoardMentorOut>("POST", `/v1/boards/${boardId}/mentors`, payload),
  revokeMentor: (boardId: string, mentorId: string) =>
    request<void>("DELETE", `/v1/boards/${boardId}/mentors/${mentorId}`),

  // --- invitations ---
  getInvitation: (token: string) =>
    request<BoardMentorOut>("GET", `/v1/invitations/${token}`),
  acceptInvitation: (token: string, payload?: AcceptInvitationRequest) =>
    request<AcceptInvitationResponse>(
      "POST",
      `/v1/invitations/${token}/accept`,
      payload,
    ),
};
