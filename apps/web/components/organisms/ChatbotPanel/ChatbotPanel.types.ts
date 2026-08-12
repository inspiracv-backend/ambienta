import type { ChatbotQA } from '@/mocks/chatbot';

export interface ChatbotPanelProps {
  qaBase: ChatbotQA[];
  privileged?: boolean;
  examplePrompts: string[];
}
