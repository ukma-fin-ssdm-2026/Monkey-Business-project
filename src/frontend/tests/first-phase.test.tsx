/** Codex: behavior tests for full card forms and session lifecycle. */
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { api, setAuthToken, SESSION_EXPIRED_EVENT } from "../src/api/client";
import { AuthProvider, useAuth } from "../src/context/AuthContext";
import { ProtectedRoute } from "../src/components/ProtectedRoute";
import { NewCardForm } from "../src/components/NewCardForm";
import { CardModal } from "../src/components/CardModal";

const user = { id: "owner", email: "owner@example.com", role: "candidate" as const, is_active: true };
const card = {
  id: "card", board_id: "board", stage_id: "stage", company: "Acme", position: "Engineer",
  vacancy_url: "https://example.com/job", requirements_text: "Python", deadline: "2026-12-10T10:00:00Z",
  notifications_enabled: true, status: "active" as const, position_index: 0,
  created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z",
};

function token(expires = Date.now() + 86400000) {
  return `${btoa('{}')}.${btoa(JSON.stringify({ exp: Math.floor(expires / 1000), sub: user.id }))}.signature`;
}

function storeSession(value = token()) {
  localStorage.setItem("tib.token", value);
  localStorage.setItem("tib.user", JSON.stringify(user));
}

beforeEach(() => { localStorage.clear(); setAuthToken(null); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); setAuthToken(null); });

describe("complete card lifecycle", () => {
  it("submits all initial fields together and preserves input after a failed save", async () => {
    const submit = vi.fn().mockRejectedValueOnce(new Error("Спробуйте ще раз")).mockResolvedValueOnce(undefined);
    render(<NewCardForm onSubmit={submit} onCancel={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Компанія"), { target: { value: "Acme" } });
    fireEvent.change(screen.getByLabelText("Посада"), { target: { value: "Engineer" } });
    fireEvent.change(screen.getByLabelText("Посилання на вакансію"), { target: { value: "https://example.com/job" } });
    fireEvent.change(screen.getByLabelText("Вимоги вакансії"), { target: { value: "Python" } });
    fireEvent.change(screen.getByLabelText("Дедлайн"), { target: { value: "2026-12-10T12:30" } });
    fireEvent.change(screen.getByLabelText("Посилання на завдання 1"), { target: { value: "https://example.com/task" } });
    fireEvent.click(screen.getByText("Ще посилання"));
    fireEvent.change(screen.getByLabelText("Посилання на завдання 2"), { target: { value: "https://example.com/repo" } });
    fireEvent.change(screen.getByLabelText("Нотатка"), { target: { value: "Feedback" } });
    fireEvent.click(screen.getByRole("button", { name: "Додати", exact: true }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Спробуйте ще раз");
    expect((screen.getByLabelText("Компанія") as HTMLInputElement).value).toBe("Acme");
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      company: "Acme", position: "Engineer", vacancy_url: "https://example.com/job", requirements_text: "Python",
      deadline: new Date("2026-12-10T12:30").toISOString(),
      links: ["https://example.com/task", "https://example.com/repo"], notes: [{ content: "Feedback", source: "candidate" }],
    }));
    fireEvent.click(screen.getByRole("button", { name: "Додати", exact: true }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
  });

  it("clears optional fields, edits notes and links, and shows the author without mentor membership", async () => {
    const link = { id: "link", card_id: card.id, url: "https://example.com/task", created_at: card.created_at };
    const note = { id: "note", card_id: card.id, content: "Initial", source: "candidate" as const, created_at: card.created_at, updated_at: card.updated_at };
    vi.spyOn(api, "listLinks").mockResolvedValue([link]);
    vi.spyOn(api, "listNotes").mockResolvedValue([note]);
    vi.spyOn(api, "listMentors").mockResolvedValue([]);
    vi.spyOn(api, "listComments").mockResolvedValue([{ id: "comment", card_id: card.id, author_id: "mentor", author_name: "mentor@example.com", author_role: "mentor", content: "Feedback", created_at: card.created_at }]);
    vi.spyOn(api, "updateCard").mockResolvedValue({ ...card, vacancy_url: null, requirements_text: null, deadline: null });
    vi.spyOn(api, "updateLink").mockResolvedValue({ ...link, url: "https://example.com/new" });
    vi.spyOn(api, "updateNote").mockResolvedValue({ ...note, content: "Updated" });
    render(<AuthProvider><CardModal card={card} boardId="board" canWrite onClose={vi.fn()} onUpdated={vi.fn()} onDeleted={vi.fn()} /></AuthProvider>);
    expect(await screen.findByText("mentor@example.com (ментор)")).toBeTruthy();
    for (const label of ["Посилання на вакансію", "Вимоги вакансії", "Дедлайн"]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value: "" } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Зберегти", exact: true }));
    await waitFor(() => expect(api.updateCard).toHaveBeenCalledWith("board", "card", { vacancy_url: null, requirements_text: null, deadline: null }));
    fireEvent.click(screen.getByText("Редагувати посилання"));
    fireEvent.change(screen.getByLabelText("Новий URL"), { target: { value: "https://example.com/new" } });
    fireEvent.click(screen.getByText("Зберегти посилання"));
    expect(await screen.findByRole("link", { name: "https://example.com/new" })).toBeTruthy();
    fireEvent.click(screen.getByText("Редагувати нотатку"));
    fireEvent.change(screen.getByLabelText("Текст нотатки"), { target: { value: "Updated" } });
    fireEvent.click(screen.getByText("Зберегти нотатку"));
    expect(await screen.findByText("Updated")).toBeTruthy();
    expect(api.updateNote).toHaveBeenCalledWith("board", "card", "note", { content: "Updated" });
  });
});

function SessionView() {
  const { user: currentUser, logout, applySession } = useAuth();
  return <><p>{currentUser?.email ?? "No session"}</p><button onClick={logout}>Logout</button>
    <button onClick={() => applySession({ access_token: token(), user })}>Login locally</button></>;
}

function renderSession() {
  return render(<MemoryRouter initialEntries={["/board"]}><AuthProvider><Routes>
    <Route element={<ProtectedRoute />}><Route path="/board" element={<SessionView />} /></Route>
    <Route path="/login" element={<p>Login page</p>} />
  </Routes></AuthProvider></MemoryRouter>);
}

describe("session lifecycle", () => {
  it("logs out, removes cached credentials and redirects away from the board", async () => {
    storeSession(); renderSession();
    await screen.findByText(user.email);
    fireEvent.click(screen.getByText("Logout"));
    expect(await screen.findByText("Login page")).toBeTruthy();
    expect(localStorage.getItem("tib.token")).toBeNull();
    expect(localStorage.getItem("tib.user")).toBeNull();
  });

  it.each(["expired", "malformed"])('rejects a %s restored session', async (kind) => {
    storeSession(kind === "expired" ? token(Date.now() - 1000) : "broken-token");
    renderSession();
    expect(await screen.findByText("Login page")).toBeTruthy();
    expect(localStorage.getItem("tib.token")).toBeNull();
  });

  it("expires the open board after 24 hours without waiting for an API request", async () => {
    vi.useFakeTimers(); storeSession(); renderSession();
    expect(screen.getByText(user.email)).toBeTruthy();
    await act(async () => { vi.advanceTimersByTime(86400000); });
    expect(screen.getByText("Login page")).toBeTruthy();
  });

  it("clears the session on an authenticated 401 even if the response is not JSON", async () => {
    storeSession(); renderSession();
    await screen.findByText(user.email);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("Unauthorized", { status: 401 }));
    await act(async () => { await expect(api.listMyBoards()).rejects.toThrow(); });
    expect(screen.getByText("Login page")).toBeTruthy();
    expect(localStorage.getItem("tib.token")).toBeNull();
  });

  it("does not invalidate a new session when an old request later returns 401", async () => {
    let resolve!: (response: Response) => void;
    setAuthToken("old-token");
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((done) => { resolve = done; }));
    const request = expect(api.listMyBoards()).rejects.toThrow();
    setAuthToken("new-token"); resolve(new Response("Unauthorized", { status: 401 }));
    await request;
    expect(expired).not.toHaveBeenCalled();
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });
});
