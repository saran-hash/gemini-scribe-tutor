import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Settings as SettingsIcon } from 'lucide-react';
import { toast } from 'sonner';

export default function Settings() {
  const [backendUrl, setBackendUrl] = useState('http://localhost:5000');

  useEffect(() => {
    const stored = localStorage.getItem('backend_url');
    if (stored) {
      setBackendUrl(stored);
    }
  }, []);

  const handleSave = () => {
    localStorage.setItem('backend_url', backendUrl);
    toast.success('Settings saved successfully');
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
        <p className="text-muted-foreground">Configure your backend connection</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SettingsIcon className="h-5 w-5" />
            Backend Configuration
          </CardTitle>
          <CardDescription>Set the URL for your Flask + Ollama backend</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="backend-url">Backend URL</Label>
            <Input
              id="backend-url"
              type="url"
              placeholder="http://localhost:5000"
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
              className="mt-2"
            />
            <p className="text-sm text-muted-foreground mt-2">
              The base URL where your Flask backend is running (e.g., http://localhost:5000)
            </p>
          </div>
          <Button onClick={handleSave}>Save Settings</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API Endpoints</CardTitle>
          <CardDescription>Expected backend endpoints</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <code className="bg-muted px-2 py-1 rounded">POST /api/ingest</code>
              <span className="text-muted-foreground">Process and store learning materials</span>
            </div>
            <div className="flex items-center gap-2">
              <code className="bg-muted px-2 py-1 rounded">POST /api/ask</code>
              <span className="text-muted-foreground">Ask questions and get RAG-powered answers</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
