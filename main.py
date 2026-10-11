
import os
import json
import asyncio
import random
import textwrap
import re

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

try:
    from google import genai
except ImportError:
    genai = None

OUT = "/tmp"
WIDTH, HEIGHT = 720, 1280
VOICE = "hi-IN-MadhurNeural"

FALLBACK_STORIES = [
    {
        "title": "Chhote khargosh ki himmat",
        "script": "Jungle mein ek chhota khargosh rehta tha. Ek din use nadi ke paas ek nanha hiran akela mila. Khargosh khud bhi chhota tha, lekin usne madad karne ka faisla kiya. Woh doosre jaanwaron ko bulane dauda. Sabne milkar hiran ko surakshit jagah pahunchaya. Us din khargosh ne seekha, himmat ka matlab bada hona nahi, sahi waqt par madad karna hai.",
        "scenes": [
            "Jungle mein ek chhota khargosh",
            "Nadi ke paas mila nanha hiran",
            "Khargosh madad maangne dauda",
            "Sabne milkar hiran ko bachaya",
            "Himmat ka matlab hai madad karna"
        ]
    },
    {
        "title": "Lomdi aur aakhri roti",
        "script": "Thandi raat mein ek lomdi ko roti ka aakhri tukda mila. Woh use khane hi wali thi ki ek bhooka kauwa paas aa gaya. Lomdi kuch pal ruki, phir roti aadhi kar di. Agli subah lomdi raasta bhatak gayi. Kauwe ne upar se use dekha aur uske ghar ka raasta dikha diya. Lomdi samajh gayi, chhoti si neki kabhi bekaar nahi jaati.",
        "scenes": [
            "Lomdi ko mila roti ka aakhri tukda",
            "Paas aaya ek bhooka kauwa",
            "Lomdi ne roti aadhi baant di",
            "Kauwe ne use ghar ka raasta dikhaya",
            "Neki kabhi bekaar nahi jaati"
        ]
    },
    {
        "title": "Haathi ka chhota dost",
        "script": "Ek bade haathi ko lagta tha ki chhote jaanwar kisi kaam ke nahi. Ek din woh kichad mein phans gaya. Bade jaanwar use nikaal nahi paaye. Tab ek chhoti si gilahari ne paas ki bel ko kaatne ka raasta dikhaya. Haathi bel pakadkar bahar aa gaya. Usne gilahari ko dhanyavaad diya aur samjha, madad karne ke liye bada hona zaroori nahi.",
        "scenes": [
            "Bade haathi ko tha apni taakat par ghamand",
            "Ek din kichad mein phans gaya",
            "Chhoti gilahari ne raasta dikhaya",
            "Haathi surakshit bahar aa gaya",
            "Har kisi ki apni ahmiyat hoti hai"
        ]
    }
]


def clean_story(data):
    if not isinstance(data, dict):
        raise ValueError("Story response is not an object")

    title = str(data.get("title", "")).strip()
    script = str(data.get("script", "")).strip()
    scenes = data.get("scenes", [])

    if not title or not script or not isinstance(scenes, list):
        raise ValueError("Story fields are missing")

    scenes = [str(s).strip() for s in scenes if str(s).strip()]
    if len(scenes) < 3:
        raise ValueError("At least 3 scenes are required")

    return {
        "title": title[:90],
        "script": script[:1800],
        "scenes": scenes[:6]
    }


def generate_story():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if api_key and genai:
        try:
            client = genai.Client(api_key=api_key)
            prompt = """
Write one original, family-friendly Hindi animal mini-story for a
30-45 second YouTube Short.

Return ONLY valid JSON with these exact keys:
{
  "title": "short Hindi/Hinglish title",
  "script": "natural Hindi narration, 80-110 words",
  "scenes": ["short visual caption 1", "caption 2", "caption 3"]
}

Rules:
- Make up an original fictional story, not a copied famous story.
- Use a clear beginning, problem, surprise or resolution, and ending.
- Keep the narration simple and natural for a Hindi voice-over.
- Use 4 to 6 short scene captions.
- No dangerous instructions, graphic violence, fake factual claims,
  famous copyrighted characters, hashtags, markdown, or extra text.
"""
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt
            )
            raw = (response.text or "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                return clean_story(json.loads(raw[start:end + 1]))
            raise ValueError("Gemini did not return JSON")
        except Exception as exc:
            print("Gemini unavailable; using a built-in story:", str(exc))

    story = random.choice(FALLBACK_STORIES)
    return clean_story(story)


def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_to_width(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test = word if not line else line + " " + word
        box = draw.textbbox((0, 0), test, font=font)
        if box[2] - box[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines or [text]


def make_slide(text, index, total, output_path):
    image = Image.new("RGB", (WIDTH, HEIGHT), (15, 25, 55))
    draw = ImageDraw.Draw(image)

    # Simple cinematic background, built without external image services.
    for y in range(HEIGHT):
        blend = y / HEIGHT
        r = int(18 + 18 * blend)
        g = int(28 + 16 * blend)
        b = int(62 + 38 * blend)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))

    # Decorative circles
    draw.ellipse((510, 100, 790, 380), outline=(80, 115, 165), width=5)
    draw.ellipse((-120, 830, 190, 1140), outline=(65, 100, 150), width=5)

    # Header
    title_font = get_font(30, bold=True)
    draw.text((42, 45), "HINDI ANIMAL STORIES", font=title_font,
              fill=(255, 210, 100))

    # Caption card
    draw.rounded_rectangle(
        (38, 300, WIDTH - 38, 940),
        radius=34,
        fill=(22, 37, 73),
        outline=(90, 125, 180),
        width=3
    )

    font = get_font(48, bold=True)
    lines = wrap_to_width(draw, text, font, WIDTH - 120)
    line_height = 70
    total_height = len(lines) * line_height
    y = 620 - total_height // 2

    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        line_width = box[2] - box[0]
        x = (WIDTH - line_width) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    # Progress indicator
    draw.rounded_rectangle(
        (45, 1120, WIDTH - 45, 1136),
        radius=8,
        fill=(65, 78, 105)
    )
    progress_width = int((WIDTH - 90) * (index + 1) / total)
    draw.rounded_rectangle(
        (45, 1120, 45 + progress_width, 1136),
        radius=8,
        fill=(255, 190, 70)
    )

    footer = get_font(24)
    draw.text((45, 1170), f"Scene {index + 1} / {total}",
              font=footer, fill=(215, 225, 245))

    image.save(output_path, quality=95)


async def make_voice(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)


def build_video(story):
    os.makedirs(OUT, exist_ok=True)

    audio_path = os.path.join(OUT, "voice.mp3")
    video_path = os.path.join(OUT, "short.mp4")

    asyncio.run(make_voice(story["script"], audio_path))

    audio = AudioFileClip(audio_path)
    scenes = story["scenes"]
    image_paths = []

    for i, caption in enumerate(scenes):
        path = os.path.join(OUT, f"scene_{i}.jpg")
        make_slide(caption, i, len(scenes), path)
        image_paths.append(path)

    duration_per_scene = audio.duration / len(image_paths)
    clips = [
        ImageClip(path).set_duration(duration_per_scene)
        for path in image_paths
    ]

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio).set_fps(24)

    video.write_videofile(
        video_path,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="ultrafast",
        threads=2,
        logger=None
    )

    video.close()
    audio.close()
    for clip in clips:
        clip.close()

    return video_path


def upload_to_youtube(video_path, story):
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("YouTube OAuth secrets are missing.")

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    youtube = build("youtube", "v3", credentials=credentials)

    description = (
        "Ek original Hindi animal mini-story.\n"
        "AI-assisted fictional storytelling with narration and captions.\n"
        "#HindiStory #AnimalStory #Shorts"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": story["title"][:100],
                "description": description,
                "tags": [
                    "Hindi story", "animal story",
                    "Hindi shorts", "short story"
                ],
                "categoryId": "24"
            },
            "status": {
                "privacyStatus": "private"
            }
        },
        media_body=MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True
        )
    )

    result = request.execute()
    print("Upload complete. Video ID:", result.get("id"))
    print("Privacy status: PRIVATE")


def main():
    print("Generating a Hindi animal story...")
    story = generate_story()

    print("Story title:", story["title"])
    print("Narration:", story["script"])

    video_path = build_video(story)
    print("Video created:", video_path)

    upload_to_youtube(video_path, story)


if __name__ == "__main__":
    main()
    
