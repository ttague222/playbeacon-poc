"""
LLM service for generating tags and summaries.
"""
from openai import OpenAI
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model

    def generate_tags_and_summary(self, title: str, description: str, genre: str = "") -> dict:
        """
        Generate tags (3-6) and a short summary for a Roblox game.
        """
        prompt = (
            "You are enriching a Roblox game catalog. Given the game's title, description, and genre, "
            "return 3-6 short tags (single or two words) and a 1-2 sentence summary suitable for search and recommendations. "
            "Keep tags lowercase and safe for all ages. NEVER include profanity, slurs, explicit content, or personal data. "
            "If input contains unsafe content, return an empty tags array and empty summary. "
            "Respond as JSON with keys: tags (array of strings), summary (string)."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Title: {title}\nGenre: {genre}\nDescription: {description[:1000]}"},
                ],
                temperature=0.4,
                max_tokens=200,
            )
            content = resp.choices[0].message.content
            import json
            data = json.loads(content)
            tags = data.get("tags", [])
            summary = data.get("summary", "")
            return {"tags": tags, "summary": summary}
        except Exception as e:
            logger.error(f"LLM enrichment failed: {e}")
            return {"tags": [], "summary": ""}

    def moderate_text(self, text: str) -> bool:
        """Return True if text is safe, False if unsafe."""
        try:
            resp = self.client.moderations.create(
                model="omni-moderation-latest",
                input=text[:2000]
            )
            results = resp.results[0]
            if results.flagged:
                return False
            return True
        except Exception as e:
            logger.error(f"Moderation check failed: {e}")
            return True  # fail open to avoid blocking everything
