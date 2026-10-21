import { createSseParser } from "./sse";

export type Role = "tutor" | "student";

export interface Me {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  status: string;
  is_admin: boolean;
}

export type AccountStatus = "invited" | "active" | "account_locked";

export interface UserView {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  status: AccountStatus;
  is_admin: boolean;
  tutor_email: string | null;
  created_at: string;
}

export interface NewUser {
  email: string;
  display_name: string;
  role: Role;
  tutor_email?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export type Author = "student" | "tutor" | "ai";

export interface ChatMessage {
  role: "user" | "assistant";
  author: Author;
  author_name: string;
  content: string;
  at: string;
  /** The lesson question it's about, by number. */
  question?: string | null;
}

export interface ConversationVersion {
  updated_at: string;
}

export interface SendResult {
  title: string;
  /** Whether Prof AI replied: in a lesson chat, not for a tutor's message without @AI or a
   * student's message to their tutor only. */
  ai: boolean;
}

export interface QuestionOverview {
  number: string;
  text: string;
}

export interface LessonOverview {
  title: string;
  topics: string[];
  support?: SupportLevel;
  worked_examples?: WorkedExample[];
  /** What a student sees of each question: never its answer. */
  questions?: QuestionOverview[];
}

export interface QuestionProgress {
  number: string;
  status: "not_started" | "working" | "correct";
  attempts: number;
  help_messages: number;
}

export interface ConversationDetail extends ConversationSummary {
  lesson: LessonOverview | null;
  messages: ChatMessage[];
  progress?: QuestionProgress[];
}

export interface CheckOutcome {
  correct: boolean;
  feedback: string;
  progress: QuestionProgress[];
}

export interface LessonSource {
  filename: string;
  pages: number[];
}

export type SupportLevel = "step_by_step" | "balanced" | "stretch";

export interface WorkedExample {
  title: string;
  text: string;
}

export interface Question {
  number: string;
  text: string;
  /** Tutor-only: checks the student's answer, never shown to them. */
  answer: string | null;
}

export interface Worksheet {
  title: string;
  topics: string[];
  worked_examples: WorkedExample[];
  questions: Question[];
}

export interface LessonDraft {
  title: string;
  topics: string[];
  notes: string;
  support: SupportLevel | null;
  /** Checklist ids (DESCRIBE_CHECKLIST) the description didn't answer. */
  unanswered: string[];
}

export interface Lesson {
  title: string;
  topics: string[];
  notes: string;
  material: string;
  sources: LessonSource[];
  /** The server defaults to balanced. */
  support?: SupportLevel;
  worked_examples?: WorkedExample[];
  questions?: Question[];
}

export interface StudentChat {
  id: string;
  title: string;
  topics: string[];
  has_material: boolean;
  support: SupportLevel | null;
  /** null: the default model. */
  model: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface StudentChats {
  chats: StudentChat[];
  max_chats: number;
  max_lesson_tokens: number;
}

export interface ExtractedPage {
  number: number;
  text: string;
  tokens: number;
}

export interface ExtractedPdf {
  pages: ExtractedPage[];
  max_lesson_tokens: number;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface ApiOptions {
  fetchFn?: typeof fetch;
  redirectToSignIn?: () => void;
}

export const UNAVAILABLE = "Prof AI is unavailable right now. Try again later.";

export function signInUrl(returnTo: string): string {
  return `/.auth/login/aad?post_login_redirect_uri=${encodeURIComponent(returnTo)}`;
}

function redirectBrowserToSignIn(): void {
  const { pathname, search } = window.location;
  window.location.assign(signInUrl(pathname + search));
}

async function errorDetail(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

async function request(path: string, init: RequestInit, options: ApiOptions): Promise<Response> {
  const fetchFn = options.fetchFn ?? fetch;
  const redirectToSignIn = options.redirectToSignIn ?? redirectBrowserToSignIn;
  let response: Response;
  try {
    // Easy Auth answers an expired session with 401 for XHR, or with a cross-origin redirect
    // to sign-in that fetch can't follow; "manual" turns the latter into an opaque response.
    response = await fetchFn(path, {
      ...init,
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
        ...init.headers,
      },
      redirect: "manual",
    });
  } catch {
    throw new ApiError(0, UNAVAILABLE);
  }
  if (response.status === 401 || response.type === "opaqueredirect") {
    redirectToSignIn();
    throw new ApiError(401, "Signing you in…");
  }
  if (!response.ok) {
    const detail = response.status >= 500 ? undefined : await errorDetail(response);
    throw new ApiError(response.status, detail ?? UNAVAILABLE);
  }
  return response;
}

export async function getJson<T>(path: string, options: ApiOptions = {}): Promise<T> {
  return (await (await request(path, {}, options)).json()) as T;
}

async function sendJson<T>(
  method: "POST" | "PUT" | "PATCH",
  path: string,
  body: unknown,
  options: ApiOptions = {},
): Promise<T> {
  const response = await request(
    path,
    { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    options,
  );
  return (await response.json()) as T;
}

export function getMe(options?: ApiOptions): Promise<Me> {
  return getJson<Me>("/api/me", options);
}

export function listConversations(options?: ApiOptions): Promise<ConversationSummary[]> {
  return getJson<ConversationSummary[]>("/api/chat/conversations", options);
}

export function startConversation(options?: ApiOptions): Promise<ConversationSummary> {
  return sendJson<ConversationSummary>("POST", "/api/chat/conversations", {}, options);
}

export function getConversation(id: string, options?: ApiOptions): Promise<ConversationDetail> {
  return getJson<ConversationDetail>(`/api/chat/conversations/${encodeURIComponent(id)}`, options);
}

export interface TeachingStyle {
  content: string;
  system_prompt: string;
  max_bytes: number;
}

export function getTeachingStyle(options?: ApiOptions): Promise<TeachingStyle> {
  return getJson<TeachingStyle>("/api/teaching-style", options);
}

export function saveTeachingStyle(content: string, options?: ApiOptions): Promise<TeachingStyle> {
  return sendJson<TeachingStyle>("PUT", "/api/teaching-style", { content }, options);
}

export function listUsers(options?: ApiOptions): Promise<UserView[]> {
  return getJson<UserView[]>("/api/users", options);
}

export function inviteUser(user: NewUser, options?: ApiOptions): Promise<UserView> {
  return sendJson<UserView>("POST", "/api/users", user, options);
}

function userPath(id: string, action = ""): string {
  return `/api/users/${encodeURIComponent(id)}${action}`;
}

export function lockUser(id: string, reason: string, options?: ApiOptions): Promise<UserView> {
  return sendJson<UserView>("POST", userPath(id, "/lock"), { reason }, options);
}

export function unlockUser(id: string, options?: ApiOptions): Promise<UserView> {
  return sendJson<UserView>("POST", userPath(id, "/unlock"), {}, options);
}

export async function deleteUser(id: string, options: ApiOptions = {}): Promise<void> {
  await request(userPath(id), { method: "DELETE" }, options);
}

function studentChatsPath(studentId: string, chatId = ""): string {
  const base = `/api/students/${encodeURIComponent(studentId)}/chats`;
  return chatId ? `${base}/${encodeURIComponent(chatId)}` : base;
}

export function listStudentChats(studentId: string, options?: ApiOptions): Promise<StudentChats> {
  return getJson<StudentChats>(studentChatsPath(studentId), options);
}

export function createStudentChat(
  studentId: string,
  lesson: Lesson,
  licenceConfirmed: boolean,
  options?: ApiOptions,
  model?: string,
): Promise<StudentChat> {
  return sendJson<StudentChat>(
    "POST",
    studentChatsPath(studentId),
    { lesson, licence_confirmed: licenceConfirmed, ...(model ? { model } : {}) },
    options,
  );
}

export function changeStudentChatModel(
  studentId: string,
  chatId: string,
  model: string,
  options?: ApiOptions,
): Promise<StudentChat> {
  return sendJson<StudentChat>("PATCH", studentChatsPath(studentId, chatId), { model }, options);
}

export interface ModelOption {
  id: string;
  label: string;
  provider: "foundry" | "ollama";
  approved_for_student_conversations: boolean;
  context_window: number;
  input_usd_per_m: number;
  cached_input_usd_per_m: number;
  output_usd_per_m: number;
  typical_message_usd: number;
  notes: string;
}

export interface ModelList {
  models: ModelOption[];
  default: string;
  /** The tutor's model for their own test chats; null means the default. */
  preferred: string | null;
}

export function listModels(options?: ApiOptions): Promise<ModelList> {
  return getJson<ModelList>("/api/models", options);
}

export function setPreferredModel(model: string | null, options?: ApiOptions): Promise<ModelList> {
  return sendJson<ModelList>("PUT", "/api/models/preferred", { model }, options);
}

export function changeStudentChatSupport(
  studentId: string,
  chatId: string,
  support: SupportLevel,
  options?: ApiOptions,
): Promise<StudentChat> {
  return sendJson<StudentChat>("PATCH", studentChatsPath(studentId, chatId), { support }, options);
}

export async function deleteStudentChat(
  studentId: string,
  chatId: string,
  options: ApiOptions = {},
): Promise<void> {
  await request(studentChatsPath(studentId, chatId), { method: "DELETE" }, options);
}

export function extractPdf(
  filename: string,
  pdfBase64: string,
  options?: ApiOptions,
): Promise<ExtractedPdf> {
  return sendJson<ExtractedPdf>(
    "POST",
    "/api/lessons/extract",
    { filename, pdf_base64: pdfBase64 },
    options,
  );
}

/** Draft questions and worked examples from worksheet text, for the tutor to review. */
export function extractWorksheet(text: string, options?: ApiOptions): Promise<Worksheet> {
  return sendJson<Worksheet>("POST", "/api/lessons/worksheet", { text }, options);
}

export function draftLesson(description: string, options?: ApiOptions): Promise<LessonDraft> {
  return sendJson<LessonDraft>("POST", "/api/lessons/describe", { description }, options);
}

export interface ReplyHandlers {
  onDelta: (text: string) => void;
}

/** Streams Prof AI's reply, if the message asked for one; resolves once the turn is saved. */
async function postMessage(
  path: string,
  content: string,
  handlers: ReplyHandlers,
  options: ApiOptions,
  extra: { to_tutor?: true; question?: string } = {},
): Promise<SendResult> {
  const response = await request(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ content, ...extra }),
    },
    options,
  );
  let result: SendResult | undefined;
  let failure: string | undefined;
  const parser = createSseParser((event, data) => {
    if (event === "delta" && typeof data.text === "string") handlers.onDelta(data.text);
    else if (event === "done") {
      result = {
        title: typeof data.title === "string" ? data.title : "",
        ai: data.ai !== false,
      };
    } else if (event === "error") failure = typeof data.message === "string" ? data.message : "";
  });
  if (!response.body) throw new ApiError(0, UNAVAILABLE);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(value);
  }
  if (failure !== undefined) throw new ApiError(502, failure || UNAVAILABLE);
  if (result === undefined) throw new ApiError(0, UNAVAILABLE);
  return result;
}

function conversationPath(id: string, action = ""): string {
  return `/api/chat/conversations/${encodeURIComponent(id)}${action}`;
}

function messageExtras(toTutor: boolean, question?: string) {
  return { ...(toTutor ? { to_tutor: true as const } : {}), ...(question ? { question } : {}) };
}

/** toTutor: in a lesson chat, the student's message is for their tutor only. question: the
 * lesson question it's about. */
export function sendMessage(
  conversationId: string,
  content: string,
  handlers: ReplyHandlers,
  options: ApiOptions = {},
  toTutor = false,
  question?: string,
): Promise<SendResult> {
  const path = conversationPath(conversationId, "/messages");
  return postMessage(path, content, handlers, options, messageExtras(toTutor, question));
}

/** Check the student's answer to one question of their lesson. */
export function checkAnswer(
  conversationId: string,
  question: string,
  answer: string,
  options?: ApiOptions,
): Promise<CheckOutcome> {
  return sendJson<CheckOutcome>(
    "POST",
    conversationPath(conversationId, "/check"),
    { question, answer },
    options,
  );
}

export function getConversationVersion(
  id: string,
  options?: ApiOptions,
): Promise<ConversationVersion> {
  return getJson<ConversationVersion>(conversationPath(id, "/version"), options);
}

export function getStudentChat(
  studentId: string,
  chatId: string,
  options?: ApiOptions,
): Promise<ConversationDetail> {
  return getJson<ConversationDetail>(studentChatsPath(studentId, chatId), options);
}

export function getStudentChatVersion(
  studentId: string,
  chatId: string,
  options?: ApiOptions,
): Promise<ConversationVersion> {
  return getJson<ConversationVersion>(`${studentChatsPath(studentId, chatId)}/version`, options);
}

export function sendStudentChatMessage(
  studentId: string,
  chatId: string,
  content: string,
  handlers: ReplyHandlers,
  options: ApiOptions = {},
  question?: string,
): Promise<SendResult> {
  const path = `${studentChatsPath(studentId, chatId)}/messages`;
  return postMessage(path, content, handlers, options, messageExtras(false, question));
}
