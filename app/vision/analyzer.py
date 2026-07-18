from openai import OpenAI
import base64
import json
from pathlib import Path

client = OpenAI()


def encode_image(path: Path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def analyze_image(image_path: Path):

    image = encode_image(image_path)

    response = client.responses.create(
        model="gpt-4.1",
        input=[
            {
                "role": "system",
                "content": """
You are one of the best luxury real estate marketing directors in America.

Evaluate the photograph.

Return ONLY valid JSON.

{
"room_type":"",
"marketing_score":0,
"luxury_score":0,
"would_use":true,
"reason":""
}
"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type":"input_image",
                        "image_url":f"data:image/jpeg;base64,{image}"
                    }
                ]
            }
        ]
    )

    return response.output_text