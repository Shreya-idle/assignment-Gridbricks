import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { createClient } from "@supabase/supabase-js";

interface Session { access_token: string; user: { email?: string; is_anonymous?: boolean } }
interface AuthClient {
  auth: {
    getSession(): Promise<{ data: { session: Session | null }; error: Error | null }>;
    onAuthStateChange(callback: (event: string, session: Session | null) => void): { data: { subscription: { unsubscribe(): void } } };
    signInWithPassword(credentials: { email: string; password: string }): Promise<{ error: Error | null }>;
    signUp(credentials: { email: string; password: string }): Promise<{ data: { session: Session | null }; error: Error | null }>;
    signInAnonymously(): Promise<{ error: Error | null }>;
    signOut(): Promise<{ error: Error | null }>;
  };
}

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
const supabase: AuthClient | null = supabaseUrl && supabaseKey
  ? createClient(supabaseUrl, supabaseKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } }) as AuthClient
  : null;

type AuthStatus = "loading" | "signed_out" | "authenticated";
interface AuthContextValue {
  configured: boolean;
  status: AuthStatus;
  session: Session | null;
  isGuest: boolean;
  accessToken: string | null;
  signIn(email: string, password: string): Promise<void>;
  signUp(email: string, password: string): Promise<boolean>;
  continueAsGuest(): Promise<void>;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>(supabase ? "loading" : "signed_out");

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      setSession(error ? null : data.session);
      setStatus(error || !data.session ? "signed_out" : "authenticated");
    });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setStatus(nextSession ? "authenticated" : "signed_out");
    });
    return () => { active = false; data.subscription.unsubscribe(); };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error("Supabase authentication is not configured.");
    if ((await supabase.auth.getSession()).data.session?.user.is_anonymous) await supabase.auth.signOut();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }, []);
  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error("Supabase authentication is not configured.");
    if ((await supabase.auth.getSession()).data.session?.user.is_anonymous) await supabase.auth.signOut();
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
    return !data.session;
  }, []);
  const continueAsGuest = useCallback(async () => {
    if (!supabase) throw new Error("Supabase authentication is not configured.");
    const current = (await supabase.auth.getSession()).data.session;
    if (current) return;
    const { error } = await supabase.auth.signInAnonymously();
    if (error) throw error;
  }, []);
  const signOut = useCallback(async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    configured: Boolean(supabase), status, session,
    isGuest: session?.user.is_anonymous === true,
    accessToken: session?.access_token ?? null,
    signIn, signUp, continueAsGuest, signOut,
  }), [status, session, signIn, signUp, continueAsGuest, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
