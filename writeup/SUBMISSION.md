# Lexsi submission form: answers to paste

Form: https://hackathon.lexsi.ai/submission/ (due Nov 15, 11:59 PM AoE = **Nov 16, 12:59 PM Lagos**)

**Email:** the email you registered with (you fill this in).

**Title:** Pocket: Tiny Aya stays safe in English when you shrink it. In Hausa and Swahili it doesn't.

**Track:** Track 2 (AI Red Teaming, Safety and Alignment)

**Problem statements:**
- 2b.7 Safety-aware compression
- 2b.5 Locating where safety lives
- 2a.4 Multilingual and code-mixed safety
- 2a.2 Adversarial and safety evaluation sets

**Repos (kits) used:** CuratorKIT, AuditKIT, SafeTune

**Model used:** CohereLabs/tiny-aya-global (official GGUF f16 / q4_k_m, plus our q3_k_m / q2_k / imatrix builds) and CohereLabs/tiny-aya-earth (official q4_k_m)

**HF model collection:** https://huggingface.co/collections/MOREN808/pocket-tiny-aya-gguf-builds-models-6af9e58d7256661d47abf08d

**HF dataset collection:** https://huggingface.co/collections/MOREN808/pocket-tiny-aya-safety-under-quantization-data-6af9e58cb73d57d870ee726d

**Write-up / article:** [HF article link, if posted with PRO]. Otherwise the same article on HF: https://moren808-pocket.static.hf.space/article.html (also on GitHub: https://github.com/neromtoobad/pocket/blob/main/writeup/ARTICLE.md)

**GitHub repo:** https://github.com/neromtoobad/pocket

**Demo:** https://huggingface.co/spaces/MOREN808/pocket

## Abstract (under 500 words)

Tiny Aya is a 3.35B multilingual model from Cohere Labs, built to run on-device in 70+ languages. Its safety was measured at full precision; quantization was measured only for generation quality. We asked whether its refusals survive the trip to a phone, in every language.

We built a 1,198-prompt set with CuratorKIT: 120 harmful prompts (MultiJail) and 120 harmless look-alikes (XSTest) in English, Swahili, Yorùbá, Hausa and Igbo, with a back-translation quality gate. We ran Tiny Aya Global as GGUF at 16, 4, 3 and 2 bits and Tiny Aya Earth at 4 bits in llama.cpp, and scored every answer with Granite Guardian on an English back-translation, a lexical refusal detector, and AuditKIT's multilingual refusal metric, which we extended to Yorùbá, Hausa and Igbo. Belebele checks reading comprehension. Every change is paired against 16-bit on the same prompts with 95% bootstrap intervals.

Findings. (1) The official 4-bit file holds: no language moves beyond noise. (2) At 3-bit (1.8 GB), English refusal is unchanged (74% → 75%) but Swahili refusal falls 17 points, Yorùbá 11 and Hausa 8; attack success rises 10 points in Swahili and 12 in Hausa, while reading comprehension barely moves. The model stays fluent and complies more. (3) At 2-bit, refusals almost vanish outside English (Yorùbá 2%, Hausa 20%) while English still refuses 75%; this model is also partly broken. An English-only safety check would pass every one of these files.

We also report a measurement trap: our first table showed the 4-bit Hausa model losing 17 points of safety, but NLLB translates the standard Hausa refusal as "I can't help it," which the judge flags. 19 of 20 such rows were this sentence. Short pure refusals are now counted safe, and both raw and corrected rates are published.

Repair attempt: an importance matrix built from Tiny Aya's own safety conversations vs one from generic text, at the same 3-bit size. Neither restores refusal (Swahili attack success still +9 to +10 points), though both bring Swahili reading comprehension back from 50% to 57–58%. Safety and capability come apart under compression, so capability checks can't certify a quantized model. The fix that works is cheap: the official 4-bit file costs 0.34 GB more and keeps full-size safety. SafeTune's refusal directions show the full-precision model recognises harm in every language, at the same middle layers (best layer 20 of 36; harmful-vs-harmless AUROC 0.91 to 0.99, cosine to English 0.70 to 0.85), so the gap is in refusing, not in recognising.

All prompts, 8,386 judged answers, GGUFs, imatrix files and code are public, with a Space to browse every answer.
