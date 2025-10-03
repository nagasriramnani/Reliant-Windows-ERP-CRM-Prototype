#!/usr/bin/env python3
# preload_models.py
"""
Pre-downloads a summarization model with your Hugging Face token
so the app loads instantly from local cache afterwards.
"""
import os
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_NAME = os.getenv("SUMMARY_MODEL", "t5-small")
HF_TOKEN = (
    os.getenv("HF_TOKEN")
    or os.getenv("HUGGINGFACE_HUB_TOKEN")
    or os.getenv("HUGGINGFACEHUB_API_TOKEN")
)

def _from_pretrained_with_token(cls, model, **extra):
    try:
        return cls.from_pretrained(model, token=HF_TOKEN, **extra)
    except TypeError:
        return cls.from_pretrained(model, use_auth_token=HF_TOKEN, **extra)

print(f"Preloading model: {MODEL_NAME}")
if not HF_TOKEN:
    print("NOTE: No HF token in env; using CLI login cache if available…")

tok = _from_pretrained_with_token(AutoTokenizer, MODEL_NAME)
mdl = _from_pretrained_with_token(AutoModelForSeq2SeqLM, MODEL_NAME)

# Warm a tiny forward pass so weights are ready in cache
inputs = tok("Warmup sample for caching.", return_tensors="pt", truncation=True)
_ = mdl.generate(**inputs, max_length=32)

print("✅ Preload complete. Model & tokenizer are cached locally.")
