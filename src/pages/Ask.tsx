import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Mic, MicOff, Send, Volume2, VolumeX, Loader2, BookOpen, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { askQuestion, deleteMaterial, type Citation } from '@/lib/api';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useTextToSpeech } from '@/hooks/useTextToSpeech';
import { useConversationHistory } from '@/hooks/useConversationHistory';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export default function Ask() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [selectedCitations, setSelectedCitations] = useState<Citation[]>([]);

  const { isListening, transcript, isSupported: voiceSupported, startListening, stopListening, resetTranscript } = useVoiceInput();
  const { speak, stop, isSpeaking, isSupported: ttsSupported } = useTextToSpeech();
  const { conversations, setCurrentConversation, addConversation, addMessage, getCurrentConversation, addMessageToCurrent, currentConversationId, deleteConversation } = useConversationHistory();

  // allow user to select multiple conversations/materials to use for answers
  const [selectedConversationIds, setSelectedConversationIds] = useState<string[]>([]);
  const handleSelectConversation = (ev: React.ChangeEvent<HTMLSelectElement>) => {
    const opts = Array.from(ev.target.selectedOptions).map((o) => o.value);
    setSelectedConversationIds(opts);
    // set primary/current conversation to the first selected for message persistence
    setCurrentConversation(opts.length > 0 ? opts[0] : null);
  };

  const handleDeleteCurrent = async () => {
    if (!currentConversationId) return;
    const confirm = window.confirm('Delete this material and its conversation? This cannot be undone.');
    if (!confirm) return;
    try {
      await deleteMaterial(currentConversationId);
    } catch (err: any) {
      // still attempt to remove locally even if backend fails
      toast.error(err?.message || 'Failed to delete material on server');
    }
    // remove locally
    deleteConversation(currentConversationId);
    setCurrentConversation(null);
    setSelectedConversationIds([]);
    toast.success('Material deleted');
  };

  // sync local messages with current conversation stored in hook/localStorage
  useEffect(() => {
    const cur = getCurrentConversation();
    if (cur) setMessages(cur.messages as Message[]);
    else setMessages([]);
  }, [currentConversationId]);

  // initialize selectedConversationIds from currentConversationId when available
  useEffect(() => {
    if (currentConversationId) setSelectedConversationIds([currentConversationId]);
  }, [currentConversationId]);

  const handleVoiceToggle = () => {
    if (isListening) {
      stopListening();
      setQuestion(transcript);
    } else {
      resetTranscript();
      startListening();
    }
  };

  const handleAsk = async () => {
    const q = isListening ? transcript : question;
    if (!q.trim()) {
      toast.error('Please enter a question');
      return;
    }

    if (isListening) {
      stopListening();
    }

    setIsAsking(true);
    const userMessage: Message = { role: 'user', content: q };
    // persist user message to current conversation
    const convId = addMessageToCurrent(userMessage);
    // update local state optimistically
    setMessages((prev) => [...prev, userMessage]);
    setQuestion('');
    resetTranscript();

    try {
      const response = await askQuestion(q, selectedConversationIds.length > 0 ? selectedConversationIds : undefined);
      const assistantMessage: Message = {
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
      };
      // persist assistant message
      addMessageToCurrent(assistantMessage);
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: any) {
      toast.error(error.message || 'Failed to get answer');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  const handleSpeak = (text: string) => {
    if (isSpeaking) {
      stop();
    } else {
      speak(text);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-end">
        <label className="mr-2 text-sm text-muted-foreground">Active Material:</label>
        <div className="flex items-center gap-2">
          <select value={currentConversationId || ''} onChange={handleSelectConversation} className="border rounded p-1">
            <option value="">(global)</option>
            {conversations.map((c) => (
              <option value={c.id} key={c.id}>{c.title}</option>
            ))}
          </select>
          {currentConversationId && (
            <Button variant="ghost" size="icon" onClick={handleDeleteCurrent} title="Delete material">
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          )}
        </div>
      </div>
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Ask Your Tutor</h1>
        <p className="text-muted-foreground">Ask questions about your uploaded materials</p>
      </div>

      <div className="space-y-4 mb-6 max-h-[500px] overflow-y-auto">
        {messages.map((msg, idx) => (
          <Card key={idx} className={msg.role === 'user' ? 'ml-12 bg-accent' : 'mr-12'}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm whitespace-pre-wrap flex-1">{msg.content}</p>
                {msg.role === 'assistant' && (
                  <div className="flex gap-2">
                    {ttsSupported && (
                      <Button variant="ghost" size="icon" onClick={() => handleSpeak(msg.content)}>
                        {isSpeaking ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                      </Button>
                    )}
                    {msg.citations && msg.citations.length > 0 && (
                      <Sheet>
                        <SheetTrigger asChild>
                          <Button variant="ghost" size="icon" onClick={() => setSelectedCitations(msg.citations || [])}>
                            <BookOpen className="h-4 w-4" />
                          </Button>
                        </SheetTrigger>
                        <SheetContent>
                          <SheetHeader>
                            <SheetTitle>Sources</SheetTitle>
                            <SheetDescription>Citations for this answer</SheetDescription>
                          </SheetHeader>
                          <div className="mt-4 space-y-4">
                            {selectedCitations.map((citation, i) => (
                              <Card key={i}>
                                <CardContent className="p-4">
                                  <p className="font-semibold text-sm mb-2">
                                    {citation.title} (Chunk {citation.chunkIndex})
                                  </p>
                                  <p className="text-sm text-muted-foreground">{citation.content}</p>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </SheetContent>
                      </Sheet>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="space-y-4">
            <Textarea
              placeholder={isListening ? 'Listening...' : 'Type your question here...'}
              value={isListening ? transcript : question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isListening || isAsking}
              className="min-h-[100px]"
            />
            <div className="flex gap-2">
              {voiceSupported && (
                <Button variant="outline" onClick={handleVoiceToggle} disabled={isAsking}>
                  {isListening ? <MicOff className="mr-2 h-4 w-4" /> : <Mic className="mr-2 h-4 w-4" />}
                  {isListening ? 'Stop Recording' : 'Start Recording'}
                </Button>
              )}
              <Button onClick={handleAsk} disabled={isAsking || (!question && !transcript)} className="flex-1">
                {isAsking ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Thinking...
                  </>
                ) : (
                  <>
                    <Send className="mr-2 h-4 w-4" />
                    Ask Question
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
