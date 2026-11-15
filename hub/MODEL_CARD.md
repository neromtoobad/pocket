---
license: cc-by-nc-4.0
license_link: https://cohere.com/cohere-labs-cc-by-nc-license
base_model: CohereLabs/tiny-aya-global
base_model_relation: quantized
language:
- en
- sw
- yo
- ha
- ig
tags:
- gguf
- llama.cpp
- quantization
- safety
- tiny-aya
- imatrix
pipeline_tag: text-generation
---

# Tiny Aya Global: Pocket GGUF builds

Research builds of [CohereLabs/tiny-aya-global](https://huggingface.co/CohereLabs/tiny-aya-global) used in **Pocket**, a study of whether Tiny Aya's safety survives GGUF quantization in English, Swahili, Yorùbá, Hausa and Igbo (Lexsi AI Safety & Alignment Hackathon).

> **These are evaluation artifacts, not recommended deployments.** The uniform 3-bit and 2-bit files refuse harmful requests much less often outside English than Cohere's official files. For use, prefer Cohere's official GGUFs, or the safety-protected builds below once their results are in.

## Files

| File | Size | What it is | Refuses harmful prompts (en / sw / yo / ha / ig) |
|---|---|---|---|
| `tiny-aya-global-q3_k_m.gguf` | 1.8 GB | uniform q3_k_m from the official f16, no imatrix | 75 / 40 / 18 / 43 / 52 % |
| `tiny-aya-global-q2_k.gguf` | 1.5 GB | uniform q2_k from the official f16, no imatrix | 75 / 29 / 2 / 20 / 21 % |
| `imatrix-generic.gguf` | 7 MB | importance matrix from generic text (Belebele passages not in the test) | — |
| `imatrix-safety.gguf` | 7 MB | importance matrix from Tiny Aya's own f16 answers to 600 held-out harmful and harmless prompts in 5 languages | — |
{{EXTRA_ROWS}}

For reference, the official f16 file refuses 74 / 56 / 29 / 51 / 48 % and the official q4_k_m 73 / 59 / 32 / 56 / 56 %. Full results with judge scores and intervals: [MOREN808/pocket-safety-evals](https://huggingface.co/datasets/MOREN808/pocket-safety-evals). Browse every answer: [Pocket Space](https://huggingface.co/spaces/MOREN808/pocket).

## How they were made

llama.cpp b12403, from Cohere's official `tiny-aya-global-f16.gguf`:

```bash
llama-imatrix -m tiny-aya-global-f16.gguf -f calib_safety.txt -o imatrix-safety.gguf -ngl 99 -c 512 --chunks 400
llama-quantize tiny-aya-global-f16.gguf tiny-aya-global-q3_k_m.gguf q3_k_m
llama-quantize --imatrix imatrix-safety.gguf tiny-aya-global-f16.gguf tiny-aya-global-q3_k_m-imat-safety.gguf q3_k_m
# protected: safety-sensitive layer groups (from a crush-one-group sweep) kept at q6_k
llama-quantize --imatrix imatrix-safety.gguf --tensor-type "blk\.(…)\..*=q6_k" tiny-aya-global-f16.gguf out.gguf q3_k_m
```

Run with the model's own chat template (`llama-server --jinja`), which includes Cohere's default safety preamble.

## License

Same as the base model: CC-BY-NC 4.0, and use must follow the [Cohere Labs Acceptable Use Policy](https://docs.cohere.com/docs/c4ai-acceptable-use-policy).
