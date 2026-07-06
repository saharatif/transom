import re

# Matches "1/8 inch", "1/32 of an inch", "1/4-inch", "0.125 inch", "1 inch".
# The Texas warranty doc's performance standards are almost entirely
# fraction-of-an-inch tolerances (drywall cracks, stucco cracks, crowning,
# bows/depressions, etc.), so this narrow pattern covers the cases that
# actually matter for this document rather than attempting general-purpose
# unit parsing.
_FRACTION_INCH = re.compile(
    r"(\d+)\s*/\s*(\d+)\s*(?:of an?\s*)?inch(?:es)?", re.IGNORECASE)
_DECIMAL_INCH = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|\s)?inch(?:es)?", re.IGNORECASE)


def extract_inch_measurements(text: str) -> list[float]:
    """Return every inch measurement found in text, as decimal inches.
    E.g. "a 1/8 inch crack" -> [0.125]. Order of appearance is preserved;
    duplicates are kept since a repeated number can be meaningful (e.g.
    the same threshold restated).
    """
    values = []
    consumed_spans = []

    for m in _FRACTION_INCH.finditer(text):
        # Mark the span consumed even for a malformed zero-denominator
        # fraction — otherwise the decimal pass below would parse the "0"
        # out of "1/0 inch" as a spurious 0.0-inch measurement.
        consumed_spans.append((m.start(), m.end()))
        numerator, denominator = int(m.group(1)), int(m.group(2))
        if denominator == 0:
            continue
        values.append((m.start(), numerator / denominator))

    for m in _DECIMAL_INCH.finditer(text):
        # Skip matches that overlap a fraction already captured above
        # (e.g. don't also parse the "8" out of "1/8 inch" as "8 inches").
        if any(m.start() < end and m.end() > start for start, end in consumed_spans):
            continue
        values.append((m.start(), float(m.group(1))))

    values.sort(key=lambda pair: pair[0])
    return [v for _, v in values]


# Words that carry no defect-identifying meaning for keyword matching —
# question words like "covered"/"warranty" appear everywhere, and unit
# words are already handled by the measurement extraction itself.
_KEYWORD_STOPWORDS = {
    "covered", "cover", "coverage", "warranty", "inch", "inches",
    "under", "does", "this", "that", "with", "have", "there", "what",
    "when", "where", "which", "should", "would", "could", "about",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+|\n(?=\()")


def _question_keywords(question: str) -> list[str]:
    """Subject nouns of the question — lowercase words of 4+ letters that
    aren't generic coverage/unit words. For "Is a 1/8 inch crack in the
    drywall covered?" this is ["crack", "drywall"].
    """
    words = re.findall(r"[a-zA-Z]{4,}", question.lower())
    return [w for w in words if w not in _KEYWORD_STOPWORDS]


def _sentences_matching(text: str, keywords: list[str], require_all: bool):
    """Sentences of text that mention the keywords (prefix match, so
    "crack" also matches "cracks"/"cracking")."""
    matched = []
    for sentence in _SENTENCE_SPLIT.split(text):
        lowered = sentence.lower()
        hits = [kw for kw in keywords
                if re.search(rf"\b{re.escape(kw)}", lowered)]
        if (require_all and len(hits) == len(keywords)) or (not require_all and hits):
            matched.append(sentence)
    return matched


def _agreed_threshold(texts: list[str]):
    """The single distinct inch value across texts, or None if zero or
    several different values were found."""
    values = []
    for t in texts:
        values.extend(extract_inch_measurements(t))
    distinct = {round(v, 6) for v in values}
    return distinct.pop() if len(distinct) == 1 else None


def compare_measurement_to_sources(question: str, source_text: str):
    """Deterministically compare a measurement in the question (e.g. "a
    1/8 inch crack") against threshold measurement(s) stated in the
    retrieved source text (e.g. "shall not exceed 1/32 of an inch").

    Returns None if the comparison isn't unambiguous (no measurement in
    the question, or no threshold in the sources, or multiple thresholds
    that don't agree) — in that case the LLM falls back to its own
    judgment with no computed fact to anchor on, same as before this fix.

    Why this exists: "does 1/8 inch exceed 1/32 inch" is a plain numeric
    comparison. Leaving it to the LLM's free-form reasoning was found to
    be inconsistent across otherwise-identical runs (BUGS.md #20) — same
    correct source clause retrieved, different yes/no conclusion. Doing
    the arithmetic in code removes that source of variance; the LLM is
    then only asked to apply a fixed coverage rule to an already-settled
    fact, not to also silently do the measurement comparison itself.
    """
    question_values = extract_inch_measurements(question)
    if len(question_values) != 1:
        return None

    # Retrieved warranty context routinely mixes thresholds from several
    # performance standards (a stucco crack limit next to the drywall
    # crack limit next to ceiling-bow tolerances), so a whole-text "all
    # values must agree" check almost never fires on real retrievals.
    # Instead, narrow deterministically to the sentences about the
    # question's subject, loosening one step at a time and stopping at the
    # first level where exactly one threshold value emerges:
    #   1. sentences mentioning ALL the question's subject nouns
    #      (e.g. both "crack" and "drywall" -> § 7(c) only);
    #   2. sentences mentioning ANY subject noun;
    #   3. the full source text (original behavior).
    # If every level is ambiguous, return None and let the LLM reason
    # unaided, same as before.
    keywords = _question_keywords(question)
    threshold = None
    if keywords:
        threshold = _agreed_threshold(
            _sentences_matching(source_text, keywords, require_all=True))
        if threshold is None:
            threshold = _agreed_threshold(
                _sentences_matching(source_text, keywords, require_all=False))
    if threshold is None:
        threshold = _agreed_threshold([source_text])
    if threshold is None:
        return None

    measured = question_values[0]
    return {
        "measured_inches": measured,
        "threshold_inches": threshold,
        "exceeds_threshold": measured > threshold,
    }
