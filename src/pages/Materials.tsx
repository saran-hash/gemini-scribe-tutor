import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, Link as LinkIcon, Loader2, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { ingestMaterials, type IngestItem } from '@/lib/api';
import { useConversationHistory } from '@/hooks/useConversationHistory';

export default function Materials() {
  const [files, setFiles] = useState<File[]>([]);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const { addConversation } = useConversationHistory();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result as string;
        resolve(base64.split(',')[1]);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleProcess = async () => {
    if (files.length === 0 && !youtubeUrl) {
      toast.error('Please add at least one file or YouTube URL');
      return;
    }

    setIsProcessing(true);
    try {
      // create a conversation before ingest so backend can tag chunks with it
      const title = 'Materials: ' + (files.length > 0 ? files.map((f) => f.name).join(', ') : youtubeUrl);
      const convId = addConversation(title);
      const items: IngestItem[] = [];

      for (const file of files) {
        if (file.type === 'application/pdf') {
          const base64 = await fileToBase64(file);
          items.push({
            type: 'pdf',
            name: file.name,
            dataBase64: base64,
          });
        } else if (file.type === 'text/plain') {
          const text = await file.text();
          items.push({
            type: 'text',
            name: file.name,
            text,
          });
        }
      }

      if (youtubeUrl) {
        items.push({
          type: 'youtube',
          name: youtubeUrl,
          url: youtubeUrl,
        });
      }

      await ingestMaterials({ items, conversationId: convId });
      toast.success('Materials processed successfully!');
      // conversation already created and set as current by addConversation
      setFiles([]);
      setYoutubeUrl('');
    } catch (error: any) {
      toast.error(error.message || 'Failed to process materials');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Upload Learning Materials</h1>
        <p className="text-muted-foreground">Add PDFs, text files, or YouTube videos to build your knowledge base</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Upload Files
          </CardTitle>
          <CardDescription>Select PDF or text files to upload</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <Label htmlFor="file-upload">Files (PDF, TXT)</Label>
              <Input
                id="file-upload"
                type="file"
                accept=".pdf,.txt"
                multiple
                onChange={handleFileChange}
                className="mt-2"
              />
            </div>
            {files.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Selected files:</p>
                {files.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <FileText className="h-4 w-4" />
                    {file.name}
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LinkIcon className="h-5 w-5" />
            YouTube Video
          </CardTitle>
          <CardDescription>Paste a YouTube video URL to extract transcript</CardDescription>
        </CardHeader>
        <CardContent>
          <div>
            <Label htmlFor="youtube-url">YouTube URL</Label>
            <Input
              id="youtube-url"
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              className="mt-2"
            />
          </div>
        </CardContent>
      </Card>

      <Button
        onClick={handleProcess}
        disabled={isProcessing || (files.length === 0 && !youtubeUrl)}
        size="lg"
        className="w-full"
      >
        {isProcessing ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Processing Materials...
          </>
        ) : (
          'Process Materials'
        )}
      </Button>
    </div>
  );
}
