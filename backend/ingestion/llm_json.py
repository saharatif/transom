import json


def parse_llm_json(raw: str) -> dict | list:
    """Parse a JSON object/array out of an LLM text response.

    Extraction prompts ask for "ONLY JSON", but models still sometimes wrap
    the payload in a ```json fence or add a preamble/afterword sentence.
    A bare json.loads on the raw text fails on any of those with an error
    that doesn't say what the model actually returned. This finds the first
    balanced {...} or [...] in the text and parses just that, raising a
    ValueError that includes a snippet of the offending output so ingestion
    failures are diagnosable from the API error alone.
    """
    if not raw or not raw.strip():
        raise ValueError("LLM returned an empty response")

    text = raw.strip()

    # Fast path: the whole response is already valid JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first { or [ and its balanced closing partner, ignoring
    # brackets inside JSON strings.
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1),
                default=-1)
    if start == -1:
        raise ValueError(f"No JSON found in LLM response: {text[:200]!r}")

    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Malformed JSON in LLM response ({e}): "
                            f"{text[start:start + 200]!r}") from e

    raise ValueError(f"Unbalanced JSON in LLM response: {text[start:start + 200]!r}")
