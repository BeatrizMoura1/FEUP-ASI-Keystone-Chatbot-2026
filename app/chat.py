import json
import logging
import re

from app.config import NO_ANSWER_TEXT
from app.documents import get_allowed_documents
from app.llm import generate

logger = logging.getLogger("knowledge_finder")

SYSTEM_PROMPT = f"""You are Keystone, the internal knowledge assistant for employees of an engineering consultancy.
Rules:
1. Answer ONLY using the documents provided below. Do not use outside knowledge.
2. Cite the document name for every claim, e.g. "(Source: <document name>)".
3. If the answer is not in the documents, reply exactly "{NO_ANSWER_TEXT}" with an empty sources list.
4. Return ONLY a JSON object of the form {{"answer": "...", "sources": ["<document name>", ...]}}.
   "sources" must list the exact names of the documents you used.
5. The CONVERSATION SO FAR section (if present) is only there to understand follow-up questions, for example
   what "it" or "that project" refers to. It is NOT a source: every fact in your answer must come from the
   documents and be cited, even if an earlier answer already mentioned it."""

MAX_HISTORY_MESSAGE_CHARS = 1500


def build_user_prompt(documents: list[dict], question: str, conversation_history: list[dict]) -> str:
    """Put the full text of every allowed document, the recent conversation and the question into one prompt.

    Parameters
    ----------
    documents : list of dict
        Documents the user is allowed to see.
    question : str
        The user's question.
    conversation_history : list of dict
        Earlier messages of this chat as [{"role", "content"}], oldest first (may be empty).

    Returns
    -------
    str
        The user-turn prompt.
    """
    document_blocks = [
        f'<document name="{document["name"]}">\n{document["content"]}\n</document>' for document in documents
    ]
    prompt_text = "DOCUMENTS:\n\n" + "\n\n".join(document_blocks)
    if conversation_history:
        history_lines = [
            f'{"User" if message["role"] == "user" else "Assistant"}: {message["content"][:MAX_HISTORY_MESSAGE_CHARS]}'
            for message in conversation_history
        ]
        prompt_text += "\n\nCONVERSATION SO FAR (context only, not a source):\n" + "\n".join(history_lines)
    return prompt_text + f"\n\nQUESTION: {question}"


def parse_llm_reply(raw_reply: str, allowed_document_names: set[str]) -> dict:
    """Parse the model's JSON reply safely, falling back to plain text if it is malformed.

    Sources are kept only if they name a document the user is allowed to see.

    Parameters
    ----------
    raw_reply : str
        Raw model output.
    allowed_document_names : set of str
        Names of the documents that were in the prompt.

    Returns
    -------
    dict
        {"answer": str, "sources": list of str}.
    """
    parsed_reply = None
    for candidate_text in (raw_reply, *re.findall(r"\{.*\}", raw_reply, re.DOTALL)):
        try:
            parsed_reply = json.loads(candidate_text)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(parsed_reply, dict) or "answer" not in parsed_reply:
        logger.warning("LLM reply was not valid JSON, showing raw text instead.")
        return {"answer": raw_reply.strip() or NO_ANSWER_TEXT, "sources": []}

    answer_text = str(parsed_reply.get("answer", "")).strip() or NO_ANSWER_TEXT
    raw_sources = parsed_reply.get("sources") or []
    if not isinstance(raw_sources, list):
        raw_sources = [raw_sources]
    cited_sources = [str(source) for source in raw_sources if str(source) in allowed_document_names]
    if answer_text.rstrip(".").lower() == NO_ANSWER_TEXT.rstrip(".").lower():
        return {"answer": NO_ANSWER_TEXT, "sources": []}
    return {"answer": answer_text, "sources": list(dict.fromkeys(cited_sources))}


def answer_question(user: dict, question: str, conversation_history: list[dict] | None = None) -> dict:
    """Answer a question using only the documents this user may access.

    Parameters
    ----------
    user : dict
        The logged-in user.
    question : str
        The user's question.
    conversation_history : list of dict, optional
        Earlier messages of this chat as [{"role", "content"}], already filtered to what the user may see.

    Returns
    -------
    dict
        {"answer": str, "sources": list of {"id", "name"}, "context_document_ids": list of int}.
        "context_document_ids" lists every document that was in the prompt.

    Raises
    ------
    RateLimitError, LLMError
        Propagated from the LLM call.
    """
    allowed_documents = get_allowed_documents(user)
    if not allowed_documents:
        return {"answer": NO_ANSWER_TEXT, "sources": [], "context_document_ids": []}
    conversation_history = conversation_history or []
    logger.info(
        "User '%s' asked a question over %d documents with %d history messages.",
        user["username"], len(allowed_documents), len(conversation_history),
    )
    raw_reply = generate(SYSTEM_PROMPT, build_user_prompt(allowed_documents, question, conversation_history))
    document_ids_by_name = {document["name"]: document["id"] for document in allowed_documents}
    parsed_reply = parse_llm_reply(raw_reply, set(document_ids_by_name))
    parsed_reply["sources"] = [
        {"id": document_ids_by_name[source_name], "name": source_name} for source_name in parsed_reply["sources"]
    ]
    parsed_reply["context_document_ids"] = list(document_ids_by_name.values())
    return parsed_reply
