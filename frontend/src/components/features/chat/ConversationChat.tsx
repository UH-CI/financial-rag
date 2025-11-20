import React, { useState, useRef, useEffect } from 'react';
import { useConversation } from '../../../hooks/useConversation';
import type { ChatMessage } from '../../../types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ConversationChatProps {
  className?: string;
}

export const ConversationChat: React.FC<ConversationChatProps> = ({ className = '' }) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const {
    conversation,
    isLoading,
    startNewConversation,
    askQuestionWithContext,
    clearConversation,
  } = useConversation();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const question = inputValue.trim();
    setInputValue('');

    try {
      await askQuestionWithContext(question);
    } catch (error) {
      console.error('Error asking question:', error);
    }
  };

  const handleNewConversation = () => {
    clearConversation();
    startNewConversation();
  };

  const formatMessage = (message: ChatMessage) => {
    if (message.type === 'user') {
      return (
        <div key={message.id} className="flex justify-end mb-4">
          <div className="bg-blue-500 text-white rounded-lg px-4 py-2 max-w-xs lg:max-w-md">
            <p className="text-sm">{message.content}</p>
            <span className="text-xs opacity-75">
              {message.timestamp.toLocaleTimeString()}
            </span>
          </div>
        </div>
      );
    }

    return (
      <div key={message.id} className="flex justify-start mb-4">
        <div className="bg-gray-200 text-gray-800 rounded-lg px-4 py-2 max-w-xs lg:max-w-md">
          {message.isLoading ? (
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
              <span className="text-sm">Thinking...</span>
            </div>
          ) : (
            <>
              <div className="text-sm prose prose-sm max-w-none prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-ol:my-2 prose-li:my-1">
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
                    br: () => <br className="my-1" />,
                    ul: ({ children }) => <ul className="my-2 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="my-2 space-y-1">{children}</ol>,
                    li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
              {message.sources && message.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-300">
                  <p className="text-xs font-semibold mb-1">Sources:</p>
                  {message.sources.slice(0, 3).map((source, idx) => (
                    <div key={idx} className="text-xs bg-gray-100 rounded p-1 mb-1">
                      <span className="font-medium">
                        {source.metadata?.source_identifier || `Source ${idx + 1}`}
                      </span>
                      {source.score && (
                        <span className="text-gray-500 ml-1">
                          (Score: {source.score.toFixed(2)})
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <span className="text-xs opacity-75">
                {message.timestamp.toLocaleTimeString()}
                {message.conversation_id && (
                  <span className="ml-2 text-green-600">
                    ID: {message.conversation_id.slice(-8)}
                  </span>
                )}
              </span>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Financial RAG Chat</h2>
          {conversation && (
            <p className="text-sm text-gray-500">
              Conversation: {conversation.conversation_id.slice(-8)}
              {conversation.source_references.length > 0 && (
                <span className="ml-2 text-blue-600">
                  ({conversation.source_references.length} sources tracked)
                </span>
              )}
            </p>
          )}
        </div>
        <button
          onClick={handleNewConversation}
          className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm"
        >
          New Chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!conversation && (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg mb-2">Welcome to Financial RAG Chat!</p>
            <p className="text-sm">
              Ask questions about bills, budgets, and financial documents.
              <br />
              Your conversation history will be maintained for follow-up questions.
            </p>
          </div>
        )}
        {conversation?.messages.map(formatMessage)}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <form onSubmit={handleSubmit} className="flex space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask a question about financial documents..."
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg"
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </form>
        
        {/* Conversation tips */}
        <div className="mt-2 text-xs text-gray-500">
          <p>
            💡 Try follow-up questions like "What are the key provisions?" or "Tell me more about that bill"
          </p>
        </div>
      </div>
    </div>
  );
};
