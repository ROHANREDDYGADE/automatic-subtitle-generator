from flask import Flask, request, render_template, send_file
import whisper
import os
import sys
import ffmpeg
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

# Create necessary folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Load Whisper model
model = whisper.load_model("base")

@app.route("/")
def index():
    return '''
    <!doctype html>
    <title>Video to Subtitles</title>
    <h1>Upload a Video</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="video" accept="video/*">
        <button type="submit">Upload</button>
    </form>
    '''

@app.route("/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return "No file uploaded", 400

    video_file = request.files["video"]
    if video_file.filename == "":
        return "No selected file", 400

    # Save video file
    filename = secure_filename(video_file.filename)
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    video_file.save(video_path)

    # Extract audio from video using ffmpeg-python
    audio_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(filename)[0]}.mp3")
    try:
        ffmpeg.input(video_path).output(audio_path, q='0', map='a').run(overwrite_output=True)
    except ffmpeg.Error as e:
        print(f"Error extracting audio: {e}")
        return "Error extracting audio", 500

    # Transcribe audio using Whisper
    print("\nStarting transcription...\n", flush=True)
    result = model.transcribe(audio_path, task="translate", verbose=False)

    # Monitor progress
    total_duration = result["segments"][-1]["end"]
    for i, segment in enumerate(result["segments"]):
        progress = (segment["end"] / total_duration) * 100
        sys.stdout.write(f"\rProgress: {progress:.2f}% - Segment {i + 1}/{len(result['segments'])}")
        sys.stdout.flush()

    # Save subtitles to .srt file
    print("\n\nSaving subtitles...", flush=True)
    srt_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(filename)[0]}.srt")
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        for segment in result["segments"]:
            start = segment["start"]
            end = segment["end"]
            text = segment["text"]

            srt_file.write(f"{segment['id'] + 1}\n")
            srt_file.write(f"{format_time(start)} --> {format_time(end)}\n")
            srt_file.write(f"{text}\n\n")

    print("Transcription completed successfully.", flush=True)
    return send_file(srt_path, as_attachment=True)

def format_time(seconds):
    """Convert seconds to SRT time format."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"

if __name__ == "__main__":
    app.run(debug=True)
