/**
 * Інструмент: Claude
 * Застосування: Контекст автентифікації — токен і профіль користувача з
 * /v1/auth/login|register (JWT Bearer, TTL 24 год., auth.py), плюс
 * локальне зберігання обраного board_id.
 * Верифікація: Перевірено вручну логіку відновлення сесії з localStorage
 * та типи компіляцією; реальний вхід у запущений бекенд не тестувався
 * в цій сесії.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setAuthToken } from "../api/client";
import type { LoginRequest, RegisterRequest, UserOut } from "../api/types";

const TOKEN_KEY = "tib.token";
const USER_KEY = "tib.user";
// Останню відкриту дошку (зі списку GET /v1/boards на /board/setup)
// запам'ятовуємо в браузері окремо для кожного користувача.
const BOARD_KEY_PREFIX = "tib.board.";

interface AuthContextValue {
  user: UserOut | null;
  token: string | null;
  boardId: string | null;
  isReady: boolean;
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => void;
  setBoardId: (boardId: string) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [boardId, setBoardIdState] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);
    if (storedToken && storedUser) {
      const parsedUser = JSON.parse(storedUser) as UserOut;
      setAuthToken(storedToken);
      setToken(storedToken);
      setUser(parsedUser);
      const storedBoard = localStorage.getItem(BOARD_KEY_PREFIX + parsedUser.id);
      if (storedBoard) setBoardIdState(storedBoard);
    }
    setIsReady(true);
  }, []);

  const applySession = useCallback((data: { access_token: string; user: UserOut }) => {
    setAuthToken(data.access_token);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    const storedBoard = localStorage.getItem(BOARD_KEY_PREFIX + data.user.id);
    setBoardIdState(storedBoard);
  }, []);

  const login = useCallback(
    async (payload: LoginRequest) => {
      const data = await api.login(payload);
      applySession(data);
    },
    [applySession],
  );

  const register = useCallback(
    async (payload: RegisterRequest) => {
      const data = await api.register(payload);
      applySession(data);
    },
    [applySession],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setAuthToken(null);
    setToken(null);
    setUser(null);
    setBoardIdState(null);
  }, []);

  const setBoardId = useCallback(
    (id: string) => {
      if (!user) return;
      localStorage.setItem(BOARD_KEY_PREFIX + user.id, id);
      setBoardIdState(id);
    },
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, boardId, isReady, login, register, logout, setBoardId }),
    [user, token, boardId, isReady, login, register, logout, setBoardId],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth має використовуватись всередині AuthProvider");
  return ctx;
}
