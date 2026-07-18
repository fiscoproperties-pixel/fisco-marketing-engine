from pathlib import Path
import os

from dotenv import load_dotenv
from openai import OpenAI

# Load the .env file
dotenv_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=dotenv_path, override=True)

# Read the API key
key = os.getenv("OPENAI_API_KEY")

if not key:
    raise RuntimeError("OPENAI_API_KEY was not loaded.")

# Create the OpenAI client using the key we loaded
client = OpenAI(api_key=key)

response = client.responses.create(
    model="gpt-4.1-mini",
    input="Say exactly: Fisco AI is connected!"
)

print(response.output_text)