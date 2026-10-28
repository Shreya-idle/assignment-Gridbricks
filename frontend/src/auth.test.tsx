import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  signInAnonymously: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: () => ({ auth: mocks }),
}));

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("VITE_SUPABASE_URL", "https://project.supabase.co");
  vi.stubEnv("VITE_SUPABASE_PUBLISHABLE_KEY", "publishable-key");
  mocks.getSession.mockResolvedValue({ data: { session: null }, error: null });
  mocks.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } });
  mocks.signInAnonymously.mockResolvedValue({ error: null });
  mocks.signOut.mockResolvedValue({ error: null });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllEnvs(); });

describe("AuthProvider", () => {
  it("restores an existing permanent session", async () => {
    mocks.getSession.mockResolvedValue({ data: { session: { access_token: "token", user: { email: "analyst@example.com", is_anonymous: false } } }, error: null });
    const { AuthProvider, useAuth } = await import("./auth");
    function State() { const auth = useAuth(); return <span>{auth.status}:{auth.session?.user.email}</span>; }
    render(<AuthProvider><State /></AuthProvider>);
    expect(await screen.findByText("authenticated:analyst@example.com")).toBeInTheDocument();
  });

  it("creates an anonymous Supabase session on guest action", async () => {
    const { AuthProvider, useAuth } = await import("./auth");
    function GuestButton() { const auth = useAuth(); return <button onClick={() => void auth.continueAsGuest()}>Guest</button>; }
    render(<AuthProvider><GuestButton /></AuthProvider>);
    await waitFor(() => expect(mocks.getSession).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: "Guest" }));
    expect(mocks.signInAnonymously).toHaveBeenCalledOnce();
  });

  it("delegates logout to Supabase", async () => {
    const { AuthProvider, useAuth } = await import("./auth");
    function LogoutButton() { const auth = useAuth(); return <button onClick={() => void auth.signOut()}>Logout</button>; }
    render(<AuthProvider><LogoutButton /></AuthProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Logout" }));
    expect(mocks.signOut).toHaveBeenCalledOnce();
  });
});
