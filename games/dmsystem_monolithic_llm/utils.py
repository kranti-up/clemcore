
import json


def cleanupanswer(prompt_answer: str) -> str:
    """Clean up the answer from the LLM DM."""
    if "```json" in prompt_answer:
        prompt_answer = prompt_answer.replace("```json", "").replace("```", "")
        try:
            prompt_answer = json.loads(prompt_answer)
        except Exception as e:
            pass
        return prompt_answer

    return prompt_answer