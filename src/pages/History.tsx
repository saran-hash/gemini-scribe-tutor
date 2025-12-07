import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Trash2, MessageSquare } from 'lucide-react';
import { useConversationHistory } from '@/hooks/useConversationHistory';
import { format } from 'date-fns';

export default function History() {
  const { conversations, deleteConversation } = useConversationHistory();

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Conversation History</h1>
        <p className="text-muted-foreground">Review your past conversations with NoteMind AI</p>
      </div>

      {conversations.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <MessageSquare className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-muted-foreground">No conversations yet. Start asking questions!</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {conversations.map((conv) => (
            <Card key={conv.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-lg">{conv.title}</CardTitle>
                    <CardDescription>{format(conv.createdAt, 'PPpp')}</CardDescription>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => deleteConversation(conv.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {conv.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`p-3 rounded-md ${
                        msg.role === 'user' ? 'bg-accent text-accent-foreground' : 'bg-muted'
                      }`}
                    >
                      <p className="text-sm font-semibold mb-1">{msg.role === 'user' ? 'You' : 'Tutor'}</p>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
