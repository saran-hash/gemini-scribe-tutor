import os
import tempfile
import shutil
import subprocess
import traceback

from youtube_transcript_api import YouTubeTranscriptApi


def diag_video(vid: str):
    print(f"Diagnosing video id: {vid}")
    try:
        segs = YouTubeTranscriptApi.get_transcript(vid, languages=["en"])
        print(f"YouTubeTranscriptApi.get_transcript: {len(segs)} segments")
    except Exception as e:
        print("YouTubeTranscriptApi.get_transcript failed:")
        traceback.print_exc()
        try:
            tlist = YouTubeTranscriptApi.list_transcripts(vid)
            print("list_transcripts ok; available transcripts:")
            for t in tlist:
                try:
                    print(" -", t.language, "(generated=" , t.is_generated, ")")
                except Exception:
                    print(" - (could not inspect transcript object)")
        except Exception:
            print("list_transcripts also failed:")
            traceback.print_exc()

    # Try yt-dlp fallback if available
    if shutil.which("yt-dlp"):
        tmpdir = tempfile.mkdtemp(prefix=f"yt_{vid}_")
        out_template = os.path.join(tmpdir, "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang",
            "en",
            "--sub-format",
            "vtt",
            "-o",
            out_template,
            f"https://www.youtube.com/watch?v={vid}",
        ]
        print("Running yt-dlp to fetch auto-subtitles (if any):", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        print("yt-dlp returncode:", proc.returncode)
        print("yt-dlp stdout (truncated):\n", proc.stdout[:1000])
        print("yt-dlp stderr (truncated):\n", proc.stderr[:1000])
        print("Files written:")
        try:
            for fname in os.listdir(tmpdir):
                print(" -", fname)
        except Exception:
            print(" - (could not list tmpdir)")
        shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        print("yt-dlp not found in PATH; install yt-dlp and ffmpeg for a local fallback.")


if __name__ == "__main__":
    # Example video id from your error
    diag_video("aircAruvnKk")
