
import os
import asyncio
import random
import textwrap

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

OUT = "/tmp"
FACTS = [
    {
        "title": "Gecko ki kamaal ki pakad",
        "script": "Kya aap jaante hain? Gecko chipkali apne pairon ki khaas banawat ki madad se deewar aur chhat par chal sakti hai. Iske pairon par bahut chhote structures hote hain jo satah ke saath kamzor molecular attraction banate hain.",
        "scenes": [
            "Gecko ki kamaal ki pakad",
            "Pairon par hote hain microscopic structures",
            "Isi se deewar aur chhat par chal paati hai!"
        ]
    },
    {
        "title": "Space mein awaaz kyun nahi?",
        "script": "Space mein aam taur par awaaz safar nahi kar sakti, kyunki awaaz ko failne ke liye hawa ya koi doosra medium chahiye. Space ka zyada hissa vacuum hai. Isliye wahan dhamake bhi film jaise sunai nahi dete.",
        "scenes": [
            "Space mein awaaz kyun nahi?",
            "Awaaz ko medium chahiye",
            "Space ka zyada hissa vacuum hai!"
        ]
    },
    {
        "title": "Octopus ke teen dil",
        "script": "Kya aap jaante hain? Octopus ke teen dil hote hain. Do dil khoon ko gills tak bhejte hain, jabki teesra dil baaki body mein khoon pump karta hai. Samundar ka ye jeev waqai anokha hai.",
        "scenes": [
            "Octopus ke teen dil!",
            "Do dil gills tak khoon bhejte hain",
            "Teesra dil body mein khoon pump karta hai"
        ]
    }
]

def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def make_slide(text, index):
    image = Image.new("RGB", (720, 1280), (13, 25, 50))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((35, 250, 685, 1030), radius=40,
                           fill=(24, 49, 85), outline=(70, 150, 220), width=4)
    draw.text((60, 100), "HINDI SCIENCE", font=get_font(34), fill=(255, 210, 70))
    draw.text((60, 1140), f"FACT {index + 1}", font=get_font(30), fill="white")
    font = get_font(52)
    lines = textwrap.wrap(text, width=20)
    y = 440 - len(lines) * 35
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((720 - (box[2] - box[0])) / 2, y),
                  line, font=font, fill="white")
        y += 85
    path = f"{OUT}/slide_{index}.png"
    image.save(path)
    return path

def main():
    client_id = os.environ["YOUTUBE_CLIENT_ID"]
    client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
    refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    fact = random.choice(FACTS)
    voice_file = f"{OUT}/voice.mp3"

    async def make_voice():
        talk = edge_tts.Communicate(
            fact["script"], voice="hi-IN-MadhurNeural", rate="+0%"
        )
        await talk.save(voice_file)

    asyncio.run(make_voice())

    audio = AudioFileClip(voice_file)
    duration = audio.duration
    scene_duration = duration / len(fact["scenes"])
    clips = []
    for i, scene in enumerate(fact["scenes"]):
        path = make_slide(scene, i)
        clips.append(ImageClip(path).set_duration(scene_duration))

    video = concatenate_videoclips(clips, method="compose").set_audio(audio)
    video = video.resize(height=1280)
    video.write_videofile(
        f"{OUT}/short.mp4", fps=24, codec="libx264",
        audio_codec="aac", preset="ultrafast", logger=None
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": fact["title"] + " #Shorts",
                "description": fact["script"] + "\n#HindiFacts #Science #Shorts",
                "categoryId": "28"
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=MediaFileUpload(
            f"{OUT}/short.mp4", mimetype="video/mp4",
            resumable=True
        )
    )
    result = request.execute()
    print("UPLOAD SUCCESSFUL:", result["id"])
    video.close()
    audio.close()

if __name__ == "__main__":
    main()
  
