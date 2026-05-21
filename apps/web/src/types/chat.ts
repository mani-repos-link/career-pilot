export type Session = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
};

export type Message = {
  id: string;
  sessionId: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  provider?: string;
  model?: string;
  parentMessageId?: string | null;
  activeResponseId?: string | null;
  createdAt: string;
};
