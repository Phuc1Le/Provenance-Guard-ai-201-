import re
import statistics


def analyze_stylometrics(text: str) -> dict:
    sentences = _split_sentences(text)
    words = text.split()
    total_words = len(words)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    scores = {}

    # 1. Sentence length variation — always computed when >= 2 sentences
    sentence_lengths = [len(s.split()) for s in sentences if s.split()]
    if len(sentence_lengths) >= 2:
        std_dev = statistics.stdev(sentence_lengths)
        # Low std_dev → AI (1.0), high std_dev → human (0.0)
        # Essays have structured variation; ceiling 12 (was 15 for casual text)
        scores["sentence_length_variation"] = max(0.0, 1.0 - std_dev / 12.0)

    # 2. Type-token ratio — only if >= 200 words (matches guardrail minimum)
    if total_words >= 200:
        unique_words = len(set(w.lower() for w in words))
        ttr = unique_words / total_words
        # Low TTR → AI (1.0), high TTR → human (0.0)
        # Essays repeat topic words; realistic genre range is [0.40, 0.70]
        scores["type_token_ratio"] = max(0.0, min(1.0, (0.70 - ttr) / 0.30))

    # 3. Paragraph length variation — only if >= 4 paragraphs
    # Intro + body paragraphs + conclusion; 3 is trivially met by any essay
    if len(paragraphs) >= 3:
        para_lengths = [len(p.split()) for p in paragraphs]
        variance = statistics.variance(para_lengths)
        # Low variance → AI (1.0), high variance → human (0.0)
        # Essays mix short intros with long body paragraphs; ceiling 500
        scores["paragraph_length_variation"] = max(0.0, 1.0 - variance / 500.0)

    # 4. Longest sentence length — always computed when sentences exist
    if sentence_lengths:
        longest = max(sentence_lengths)
        # <15 words → AI (1.0), >30 words → human (0.0), linear between
        # AI-generated prose rarely exceeds 30 words per sentence
        scores["longest_sentence"] = max(0.0, min(1.0, (30 - longest) / 15.0))

    if not scores:
        return {"score": 0.5, "features": {}}

    combined = sum(scores.values()) / len(scores)

    return {
        "score": round(combined, 4),
        "features": {k: round(v, 4) for k, v in scores.items()},
    }


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


if __name__ == "__main__":
    # All samples are 200+ words with 4+ paragraphs to exercise every feature.
    samples = [
        (
            "human essay",
            "The summer I turned sixteen, my grandmother taught me to bake bread."
            " Not the kind that comes from a machine, measured to the gram — the old-fashioned,"
            " feel-it-in-your-hands kind, where you know the dough is ready because it springs back"
            " under your knuckles with a quiet confidence I have never been able to fully describe."
            " She said recipes were suggestions. I think she meant that wisdom is mostly untransferable."
            "\n\n"
            "What strikes me now, decades later, is not the bread itself but the silence we worked in."
            " She was not a warm woman in the conventional sense — she did not dispense hugs or"
            " compliments, did not believe in coddling."
            " But she would stand beside you at the counter for three hours without needing to fill"
            " the space with talk, and that presence communicated something I have spent years trying"
            " to articulate and still failing every time."
            " Some forms of love resist language."
            "\n\n"
            "I have thought about this every time I have tried to teach something I genuinely know."
            " The problem is always the same."
            " You can name every ingredient, walk through every step, demonstrate the technique twice over."
            " But the part that actually matters — the judgment call, the calibrated touch,"
            " the moment when you decide it is enough — that does not transfer through instruction."
            " It lives in the hands."
            "\n\n"
            "My grandmother died in February of a year I kept misremembering afterward."
            " The last loaf she ever baked was one she did not live to eat."
            " I finished it alone at her kitchen table, still warm from the oven, in complete silence."
            " It was perfect."
        ),
        (
            "AI essay",
            "Climate change represents one of the most significant challenges facing modern society."
            " Rising global temperatures have disrupted ecosystems and altered weather patterns across"
            " many regions of the world."
            " Scientists have documented consistent increases in atmospheric greenhouse gas concentrations"
            " since the beginning of the industrial revolution."
            " These changes carry profound implications for food security, water availability, and human health."
            "\n\n"
            "Furthermore, the economic costs associated with climate change are becoming increasingly"
            " difficult to ignore."
            " Agricultural sectors are experiencing declining yields due to irregular rainfall and"
            " prolonged drought conditions."
            " Infrastructure in coastal regions faces mounting risks from sea level rise and intensified"
            " storm events."
            " It is important to note that the burden of these impacts falls disproportionately on"
            " developing nations."
            "\n\n"
            "In addition, the policy landscape surrounding climate action remains deeply contested"
            " among governments and institutions."
            " Policymakers must balance the immediate economic costs of transitioning away from fossil"
            " fuels with the long-term benefits of a stable climate system."
            " International agreements represent significant steps forward, but enforcement mechanisms"
            " remain limited in scope and effectiveness."
            " Effective solutions will require unprecedented cooperation across national boundaries."
            "\n\n"
            "In conclusion, addressing climate change requires systemic transformation rather than"
            " incremental adjustments to current practices."
            " Renewable energy technologies have advanced considerably and now offer economically"
            " competitive alternatives to traditional fossil fuels."
            " However, the pace of adoption must accelerate significantly to meet established targets."
            " Collective action, guided by scientific evidence and driven by political will, remains"
            " the only viable path forward."
        ),
        (
            "mixed",
            "The relationship between technology and human creativity has never been straightforward."
            " From the printing press to the camera, each major innovation prompted anxious debates"
            " about what it meant for authentic human expression — debates that, in retrospect,"
            " seem to have missed the point almost entirely."
            " We adapted."
            " The technology became a medium rather than a replacement, and new forms of creativity"
            " emerged that would have been impossible without it."
            "\n\n"
            "Artificial intelligence complicates this pattern in ways that are worth examining carefully."
            " Earlier technologies extended human capability without simulating it."
            " A camera captures light; it does not see."
            " But a language model does something that superficially resembles writing, and this"
            " resemblance — however imperfect — unsettles assumptions about authorship, intention,"
            " and originality that most people had never consciously examined before."
            "\n\n"
            "What gets lost in arguments about authenticity is a more practical question: does the"
            " work function?"
            " Does the essay illuminate something?"
            " Does the code run?"
            " Outcomes are not the whole story, but they are part of it."
            " And the honest answer is that AI-assisted work sometimes functions quite well,"
            " which is uncomfortable for frameworks built on the premise that process determines value."
            "\n\n"
            "None of this settles the deeper question of what we owe each other in acts of communication."
            " Disclosure matters."
            " Context matters."
            " The difference between a student submitting AI-generated work as their own and a"
            " professional using AI to accelerate a draft is real and significant."
            " But the technology itself is not the problem."
            " It rarely is."
        ),
    ]

    for label, text in samples:
        result = analyze_stylometrics(text)
        word_count = len(text.split())
        para_count = len([p for p in text.split("\n\n") if p.strip()])
        print(f"\n[{label}]  ({word_count} words, {para_count} paragraphs)")
        print(f"  score : {result['score']}")
        for feat, val in result["features"].items():
            print(f"  {feat:<30} {val}")
