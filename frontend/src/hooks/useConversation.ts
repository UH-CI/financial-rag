import { useState, useCallback, useRef } from 'react';
import type { ConversationState, ChatMessage, QuestionResponse } from '../types';
import { askQuestion } from '../services/api';

/**
 * Custom hook for managing conversation state and history
 */
export const useConversation = () => {
  const [conversation, setConversation] = useState<ConversationState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const conversationIdRef = useRef<string | null>(null);

  /**
   * Generate a new conversation ID
   */
  const generateConversationId = useCallback(() => {
    return `frontend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  /**
   * Start a new conversation
   */
  const startNewConversation = useCallback(() => {
    const newConversationId = generateConversationId();
    conversationIdRef.current = newConversationId;
    
    const newConversation: ConversationState = {
      conversation_id: newConversationId,
      messages: [],
      source_references: [],
      created_at: new Date(),
      last_updated: new Date(),
    };
    
    setConversation(newConversation);
    return newConversationId;
  }, [generateConversationId]);

  /**
   * Add a message to the conversation
   */
  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      conversation_id: conversationIdRef.current || undefined,
    };

    setConversation(prev => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...prev.messages, newMessage],
        last_updated: new Date(),
      };
    });

    return newMessage;
  }, []);

  /**
   * Update the last message in the conversation
   */
  const updateLastMessage = useCallback((updates: Partial<ChatMessage>) => {
    setConversation(prev => {
      if (!prev || prev.messages.length === 0) return prev;
      
      const messages = [...prev.messages];
      const lastIndex = messages.length - 1;
      messages[lastIndex] = { ...messages[lastIndex], ...updates };
      
      return {
        ...prev,
        messages,
        last_updated: new Date(),
      };
    });
  }, []);

  /**
   * Ask a question with conversation context
   */
  const askQuestionWithContext = useCallback(async (question: string): Promise<QuestionResponse> => {
    if (!conversation) {
      startNewConversation();
    }

    setIsLoading(true);

    try {
      // Add user message
      addMessage({
        type: 'user',
        content: question,
      });

      // Add loading message for assistant response
      addMessage({
        type: 'assistant',
        content: '',
        isLoading: true,
      });

      // Make API call with conversation context
      const response = await askQuestion(
        question,
        conversationIdRef.current || undefined,
        conversation?.source_references
      );

      // Update the loading message with the response
      updateLastMessage({
        content: response.answer,
        sources: response.sources,
        isLoading: false,
        conversation_id: response.conversation_id,
      });

      // Update conversation ID if it changed
      if (response.conversation_id && response.conversation_id !== conversationIdRef.current) {
        conversationIdRef.current = response.conversation_id;
        setConversation(prev => prev ? {
          ...prev,
          conversation_id: response.conversation_id!,
        } : null);
      }

      // Update source references for future queries
      if (response.sources && response.sources.length > 0) {
        setConversation(prev => {
          if (!prev) return null;
          
          const newSourceRefs = response.sources.map(source => ({
            source_identifier: source.metadata?.source_identifier || 'unknown',
            content_preview: source.content.substring(0, 200),
            timestamp: new Date().getTime(),
            query: question,
          }));

          return {
            ...prev,
            source_references: [...prev.source_references, ...newSourceRefs].slice(-10), // Keep last 10
          };
        });
      }

      return response;
    } catch (error) {
      // Update the loading message with error
      updateLastMessage({
        content: 'Sorry, I encountered an error while processing your question. Please try again.',
        isLoading: false,
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [conversation, startNewConversation, addMessage, updateLastMessage]);

  /**
   * Clear the current conversation
   */
  const clearConversation = useCallback(() => {
    setConversation(null);
    conversationIdRef.current = null;
  }, []);

  /**
   * Load a conversation from storage (if implementing persistence)
   */
  const loadConversation = useCallback((conversationData: ConversationState) => {
    setConversation(conversationData);
    conversationIdRef.current = conversationData.conversation_id;
  }, []);

  return {
    conversation,
    isLoading,
    startNewConversation,
    askQuestionWithContext,
    clearConversation,
    loadConversation,
    addMessage,
    updateLastMessage,
  };
};
