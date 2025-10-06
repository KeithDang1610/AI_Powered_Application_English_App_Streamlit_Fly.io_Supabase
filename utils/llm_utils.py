import os, random, re
from typing import List, Tuple
import google.generativeai as genai
import json
from dotenv import load_dotenv, dotenv_values

# # Build absolute path to .env
# dotenv_path = os.path.join(os.getcwd(), ".env")

# # Load .env into a dictionary
# config = dotenv_values(dotenv_path)

class GeminiWrapper:
    def __init__(self, api_key, model_name ="gemini-2.5-flash-lite"):
        genai.configure(api_key=api_key)
        self.model_name = model_name

    def generate(self, prompt, generation_config):
        model = genai.GenerativeModel(self.model_name, generation_config=generation_config)
        response= model.generate_content(prompt)
        return response

config_for_passage = {
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 50,
}

config_for_chunk = {
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 50,
}

#Get the API key
# api_key = config.get("GOOGLE_API_KEY")

api_key = os.environ.get("GOOGLE_API_KEY")

gemini = GeminiWrapper(api_key)


def get_random_words_from_db(conn, user_id: int, n: int) -> List[str]:
    """Fetch n random words from vocab.db where learned=0."""
    cursor = conn.cursor()
    cursor.execute("SELECT word FROM words w LEFT JOIN user_vocab uv ON w.id = uv.word_id AND uv.user_id =%s WHERE uv.word_id IS NULL",(user_id,))
    words = [row[0] for row in cursor.fetchall()]
    conn.close()
    if not words:
        return []
    return random.sample(words, min(n, len(words)))

def create_fill_in_blank(passage: str, target_words: List[str], blanks: int = 3) -> Tuple[str, List[str]]:
    """Replace target words in passage with blanks."""
    candidates = []

    if target_words:
        # Use provided target words
        for w in set(target_words):
            pattern = re.compile(r"\b" + re.escape(w) + r"\b", flags=re.IGNORECASE)
            for m in pattern.finditer(passage):
                candidates.append((m.start(), m.end(), passage[m.start():m.end()], w))
    else:
        # Fallback — choose random words from passage itself
        words = re.findall(r"\b\w{4,}\b", passage)
        sampled = random.sample(words, min(blanks, len(words)))
        for w in sampled:
            pattern = re.compile(r"\b" + re.escape(w) + r"\b", flags=re.IGNORECASE)
            for m in pattern.finditer(passage):
                candidates.append((m.start(), m.end(), passage[m.start():m.end()], w))

    if not candidates:
        return passage, []

    # Pick non-overlapping blanks
    chosen, occupied = [], [False] * len(passage)
    for start, end, found, canonical in sorted(candidates, key=lambda x: x[0]):
        if len(chosen) >= blanks:
            break
        if any(occupied[start:end]):
            continue
        chosen.append((start, end, found, canonical))
        for i in range(start, end):
            occupied[i] = True

    # Replace chosen words with blanks
    masked_chars, answers = list(passage), []
    for start, end, found, canonical in reversed(chosen):
        masked_chars[start:end] = list("____")
        answers.append(found)
    answers.reverse()

    return ''.join(masked_chars), answers

def generate_passage_with_blanks(conn,user_id: int,words: List[str] = None, length: int = 200, blanks: int = 3, level: str = "B1 (Easy)") -> Tuple[str, List[str]]:
    """
    Generate a long educational passage and create blanks.
    If words are None or empty, fetch random words from vocab.db
    that are not learned.
    """
    if not words:
        # Fetch words from database
        words = get_random_words_from_db(conn, user_id, blanks)


    if words:
        prompt = (
            f"Write a short educational passage in English, about {length} words. "
            f"Target level: {level}. "
            f"Always include these target words naturally: {', '.join(words)}. "
            f"Even if some target words are more or less common than the target level, "
            f"keep the overall passage difficulty consistent with {level}. "
            f"Make the passage cohesive, clear, and one short paragraph."
        )
    # else:
    #     prompt = (
    #         f"Write a {length}-word educational passage in clear English. "
    #         "Make it cohesive and natural, one short paragraph."
    #     )

    resp = gemini.generate(prompt, config_for_passage)
    passage = resp.text.strip()

    # Create blanks (fallback to random words in passage if needed)
    passage_with_blanks, answers = create_fill_in_blank(passage, words, blanks=blanks)
    return passage_with_blanks, answers

def correct_sentence_with_llm(sentence: str, max_tokens: int = 200) -> dict:
    """
    Correct an English sentence using Gemini LLM.
    Returns a dict with:
    {
      'original': original sentence,
      'corrected': corrected sentence,
      'explanation': explanation of changes
    }
    Fallback: minimal correction (capitalize + punctuation) if LLM unavailable.
    """
    if not isinstance(sentence, str):
        raise ValueError("sentence must be a string")

    prompt = (
        "You are an English tutor. Correct the user's sentence for grammar, "
        "spelling, and natural phrasing. Return a JSON object ONLY with keys "
        "'original', 'corrected', and 'explanation'. 'explanation' should be a "
        "concise (1-3 sentences) explanation of the main changes.\n\n"
        f"User sentence:\n{sentence}"
    )

    try:
        resp = gemini.generate(prompt, config_for_passage)
        text = resp.text.strip()

        # Try parsing as JSON
        try:
            data = json.loads(text)
            return {
                'original': data.get('original', sentence),
                'corrected': data.get('corrected', data.get('correction', sentence)),
                'explanation': data.get('explanation', '')
            }
        except Exception:
            # Fallback: if not valid JSON, take first line as correction
            lines = text.splitlines()
            corrected = lines[0].strip() if lines else sentence
            explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            return {'original': sentence, 'corrected': corrected, 'explanation': explanation}

    except Exception as e:
        # If Gemini call fails -> fallback correction
        corrected = sentence.strip()
        if corrected and corrected[0].islower():
            corrected = corrected[0].upper() + corrected[1:]
        if corrected and corrected[-1] not in '.!%s':
            corrected = corrected + '.'
        explanation = f"Fallback: capitalized first letter and ensured punctuation. Error: {repr(e)}"
        return {'original': sentence, 'corrected': corrected, 'explanation': explanation}
   

def generate_passage_with_chunks(topic="daily life", length=150):
    """
    Generate a passage and highlight common English chunks with ** **.
    """
    prompt = (
        # f"Write a short natural and common passage of about {length} words about {topic}. "
        # f"Highlight common English chunks (multi-word expressions, collocations, idioms) in **bold**."
        "You are a writing assistant that generates short, natural, and coherent English passages commonly used by native speakers. "
        f"Length: about {length} words. "
        f"Topic: {topic}. "
        "Style: natural, common, everyday English that feels authentic. "
        "Highlight common English chunks (multi-word expressions, collocations, idioms) by putting them in bold. "
        "The passage should read smoothly, without sounding artificial or overly formal."
    )

    resp = gemini.generate(prompt, config_for_chunk)

    text = resp.text.strip()

    # Extract chunks inside ** **
    # chunks = re.findall(r"\*\*(.*%s)\*\*", text)
    chunks = re.findall(r"\*\*(.*?)\*\*", text)
    return text, chunks

def save_chunks_for_user(conn, user_id:int, topic, chunks):
    """
    Save extracted chunks for a user into the database.
    """
    cursor = conn.cursor()
    data = [(user_id, chunk, topic) for chunk in chunks]
    cursor.executemany(
        "INSERT INTO chunks (user_id, chunk, topic) VALUES (%s,%s,%s)",
        data
    )
    conn.commit() 
