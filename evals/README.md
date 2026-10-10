# Evaluation protocol

Run `python -m evals.run --limit 5` from the repository root. This uses configured Gemini/Tavily credentials and incurs provider usage. `--offline` only tests the result format and citation checker with clearly labelled fixtures; it is not evidence of answer quality.

The single-pass baseline and agent workflow receive identical retrieved evidence for each question. Retrieval is frozen inside the workflow, including retries, so this measures the incremental reasoning/validation cost and quality—not the benefit of additional search. Shared search latency is reported separately. Run an additional unfrozen experiment before claiming the retry search policy improves answers.

The JSON output contains answers, excerpts, citation ID validity, latency, model calls, tokens, and estimated model cost when environment rates are supplied. Citation validity measures whether an ID exists, not whether the source entails a claim. Search charges are excluded. Set `INPUT_USD_PER_MILLION` and `OUTPUT_USD_PER_MILLION` to your actual model's current rates; unset cost is null, never zero.

Review answers blind to strategy. Score factual accuracy, question coverage, and source support from 0 (unusable) to 4 (fully meets the rubric). Check claims against the linked documents; snippets alone may omit context. Record disagreements and source dates. Report sample size, median/p95 latency, average tokens and costs, quality means, and limitations. Five cases are a portfolio demonstration, not a statistically convincing benchmark. No quality superiority is claimed by the repository without reviewed results.
