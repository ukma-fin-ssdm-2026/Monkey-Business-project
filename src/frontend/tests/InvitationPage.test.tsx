/**
 * ## Використання ШІ
 * - **Інструмент:** Codex.
 * - **Застосування:** створення 12 характеризаційних тестів сторінки запрошення.
 * - **Верифікація:** автор переглянув сценарії та перевірив результати до/після.
 */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, setAuthToken } from "../src/api/client";
import { InvitationPage } from "../src/pages/InvitationPage";

const state = vi.hoisted(() => ({
  token: "invitation-token" as string | undefined,
  authToken: null as string | null,
  navigate: vi.fn(),
  setBoardId: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ token: state.token }),
  useNavigate: () => state.navigate,
}));
vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ token: state.authToken, setBoardId: state.setBoardId }),
}));
vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return {
    ...actual,
    api: { getInvitation: vi.fn(), acceptInvitation: vi.fn() },
    setAuthToken: vi.fn(),
  };
});

const invitation = {
  id: "invitation-id", board_id: "board-id", mentor_id: "mentor-id",
  email: "mentor@example.com", status: "pending" as const,
  invite_token: "invitation-token", invited_at: "2026-10-01", accepted_at: null,
};

function apiError(message: string) {
  return new ApiError(404, {
    error: { code: "NOT_FOUND", message, details: [], request_id: "request-id", documentation: null },
  });
}

async function openForm() {
  const view = render(<InvitationPage />);
  await screen.findByRole("button", { name: "Прийняти запрошення" });
  return view;
}

function submit() {
  fireEvent.submit(screen.getByRole("button", { name: "Прийняти запрошення" }).closest("form")!);
}

beforeEach(() => {
  state.token = "invitation-token";
  state.authToken = null;
  localStorage.clear();
  vi.mocked(api.getInvitation).mockReset().mockResolvedValue(invitation);
  vi.mocked(api.acceptInvitation).mockReset();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("InvitationPage: behavior before refactoring", () => {
  it("shows the existing loading screen while the request is pending", () => {
    vi.mocked(api.getInvitation).mockReturnValue(new Promise(() => {}));
    const { container } = render(<InvitationPage />);
    expect(container.querySelector(".auth-screen > .auth-card .auth-subtitle")?.textContent)
      .toBe("Перевірка запрошення...");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("rejects a missing token without requesting the API and offers login", () => {
    state.token = undefined;
    const { container } = render(<InvitationPage />);
    expect(container.querySelector(".auth-screen > .auth-card .form-error")?.textContent)
      .toBe("Токен запрошення відсутній у посиланні");
    expect(api.getInvitation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Перейти до входу" }));
    expect(state.navigate).toHaveBeenCalledWith("/login");
  });

  it.each([
    [apiError("Посилання відкликано"), "Посилання відкликано"],
    [new Error("internal detail"), "Запрошення не знайдено або термін його дії минув"],
  ])("keeps the load error message for %s", async (error, message) => {
    vi.mocked(api.getInvitation).mockRejectedValue(error);
    render(<InvitationPage />);
    expect(await screen.findByText(message)).toBeTruthy();
    expect(screen.getByRole("heading").textContent).toBe("Запрошення не знайдено");
  });

  it("shows email, board and the current pending label even for an accepted invitation", async () => {
    vi.mocked(api.getInvitation).mockResolvedValue({ ...invitation, status: "accepted" });
    await openForm();
    expect(screen.getByText("mentor@example.com")).toBeTruthy();
    expect(screen.getByText("board-id")).toBeTruthy();
    expect(screen.getByText("Очікує підтвердження")).toBeTruthy();
    expect(screen.getByLabelText("Пароль").getAttribute("minlength")).toBe("8");
    expect(api.getInvitation).toHaveBeenCalledWith("invitation-token");
  });

  it("keeps the empty password guard when submission bypasses browser validation", async () => {
    await openForm();
    submit();
    expect(screen.getByText("Введіть пароль для активації облікового запису")).toBeTruthy();
    expect(api.acceptInvitation).not.toHaveBeenCalled();
  });

  it("rejects mismatched passwords without calling accept", async () => {
    await openForm();
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "example-pass" } });
    fireEvent.change(screen.getByLabelText("Підтвердіть пароль"), { target: { value: "different-pass" } });
    submit();
    expect(screen.getByText("Паролі не співпадають")).toBeTruthy();
    expect(api.acceptInvitation).not.toHaveBeenCalled();
  });

  it.each([
    [apiError("Запрошення вже використано"), "Запрошення вже використано"],
    [new Error("internal detail"), "Не вдалося прийняти запрошення"],
  ])("keeps acceptance errors and re-enables the form for %s", async (error, message) => {
    state.authToken = "existing-session";
    vi.mocked(api.acceptInvitation).mockRejectedValue(error);
    await openForm();
    submit();
    expect(await screen.findByText(message)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Прийняти запрошення" }) as HTMLButtonElement).disabled).toBe(false);
    expect(state.navigate).not.toHaveBeenCalled();
  });

  it("disables submit while acceptance is pending", async () => {
    state.authToken = "existing-session";
    vi.mocked(api.acceptInvitation).mockReturnValue(new Promise(() => {}));
    await openForm();
    submit();
    expect((screen.getByRole("button", { name: "Прийняття..." }) as HTMLButtonElement).disabled).toBe(true);
    expect(api.acceptInvitation).toHaveBeenCalledTimes(1);
  });

  it("accepts a signed-in mentor without a password and navigates after two seconds", async () => {
    state.authToken = "existing-session";
    vi.mocked(api.acceptInvitation).mockResolvedValue({ message: "Accepted", board_id: "board-id", status: "accepted", access_token: null });
    const { container } = await openForm();
    expect(screen.queryByLabelText("Пароль")).toBeNull();
    vi.useFakeTimers();
    await act(async () => submit());
    expect(api.acceptInvitation).toHaveBeenCalledWith("invitation-token", undefined);
    expect(state.setBoardId).toHaveBeenCalledWith("board-id");
    expect(setAuthToken).not.toHaveBeenCalled();
    expect(container.querySelector(".auth-screen > .auth-card h1")?.textContent)
      .toBe("🎉 Запрошення прийнято!");
    act(() => vi.advanceTimersByTime(1999));
    expect(state.navigate).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(state.navigate).toHaveBeenCalledWith("/board");
  });

  it("stores a new session and board, removes cached user, and leaves context unchanged", async () => {
    vi.mocked(api.acceptInvitation).mockResolvedValue({ message: "Accepted", board_id: "board-id", status: "accepted", access_token: "new-session" });
    localStorage.setItem("tib.user", "cached-user");
    await openForm();
    for (const label of ["Пароль", "Підтвердіть пароль"]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value: "example-pass" } });
    }
    vi.useFakeTimers();
    await act(async () => submit());
    expect(api.acceptInvitation).toHaveBeenCalledWith("invitation-token", { password: "example-pass" });
    expect(setAuthToken).toHaveBeenCalledWith("new-session");
    expect(localStorage.getItem("tib.token")).toBe("new-session");
    expect(localStorage.getItem("tib.board.mentor-id")).toBe("board-id");
    expect(localStorage.getItem("tib.user")).toBeNull();
    expect(state.setBoardId).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(2000));
    expect(state.navigate).toHaveBeenCalledWith("/board");
  });
});
