#!/usr/bin/env python3
# summary_generator.py
from typing import List, Dict, Optional
import os

DEFAULT_MODEL = "t5-small"  # reliable small model (fast)
HF_MODEL = os.getenv("SUMMARY_MODEL", DEFAULT_MODEL)
HF_TOKEN = (
    os.getenv("HF_TOKEN")
    or os.getenv("HUGGINGFACE_HUB_TOKEN")
    or os.getenv("HUGGINGFACEHUB_API_TOKEN")
)

# Decoding knobs (upper bounds; we’ll also compute dynamic limits per input)
MAX_LEN = int(os.getenv("SUMMARY_MAX_LEN", "140"))
MIN_LEN = int(os.getenv("SUMMARY_MIN_LEN", "60"))
NUM_BEAMS = int(os.getenv("SUMMARY_NUM_BEAMS", "4"))
NO_REPEAT_NGRAM = int(os.getenv("SUMMARY_NO_REPEAT_NGRAM", "3"))
DO_SAMPLE = os.getenv("SUMMARY_SAMPLING", "0").lower() in ("1","true","yes")
TOP_P = float(os.getenv("SUMMARY_TOP_P", "0.9"))
TEMPERATURE = float(os.getenv("SUMMARY_TEMPERATURE", "0.8"))

_PIPELINE = None
_LAST_ERR: Optional[str] = None

def _is_t5_family(name: str) -> bool:
    return "t5" in name.lower()

def _pipeline_with_auth(token: Optional[str]):
    """Create a summarization pipeline. No local_files_only to avoid generate() kwargs leak."""
    from transformers import pipeline
    try:
        return pipeline(
            task="summarization",
            model=HF_MODEL,
            tokenizer=HF_MODEL,
            token=token,                  # transformers >= 4.41
            trust_remote_code=False,
        )
    except TypeError:
        # older transformers
        return pipeline(
            task="summarization",
            model=HF_MODEL,
            tokenizer=HF_MODEL,
            use_auth_token=token,
            trust_remote_code=False,
        )

def _load_pipeline():
    """Try cache first implicitly; then token; then anonymous."""
    global _PIPELINE, _LAST_ERR
    if _PIPELINE is not None:
        return _PIPELINE

    # 1) Try anonymous (uses cache if present, else downloads)
    try:
        _PIPELINE = _pipeline_with_auth(token=None)
        print(f"[summary_generator] Loaded (cache/anon): {HF_MODEL}")
        _LAST_ERR = None
        return _PIPELINE
    except Exception as e:
        _PIPELINE = None
        _LAST_ERR = f"Anonymous load failed: {e}"

    # 2) Try with token if provided
    if HF_TOKEN:
        try:
            _PIPELINE = _pipeline_with_auth(token=HF_TOKEN)
            print(f"[summary_generator] Loaded with token: {HF_MODEL}")
            _LAST_ERR = None
            return _PIPELINE
        except Exception as e:
            _PIPELINE = None
            _LAST_ERR = f"Token load failed: {e}"
            print(f"[summary_generator] Token load failed; reason: {e}")

    print(f"[summary_generator] Could not load model. Using fallback. Reason: {_LAST_ERR}")
    return None

def _build_source_text(customer_name: str, product_list: List[Dict], total_amount: float) -> str:
    lines = [
        f"Customer: {customer_name}.",
        f"Total quoted amount: ${total_amount:,.2f}.",
        "Items:"
    ]
    for i, p in enumerate(product_list, 1):
        name = p.get("name") or "Item"
        cat  = p.get("category") or "General"
        qty  = p.get("quantity") or 1
        w, h = p.get("width_ft"), p.get("height_ft")
        try:
            dims = f"{float(w):.2f}ft x {float(h):.2f}ft" if (w is not None and h is not None) else "N/A"
        except Exception:
            dims = "N/A"
        lines.append(f"- {i}. {name} ({cat}), Qty: {qty}, Size: {dims}")
    lines.append(
        "Scope includes supply and installation to Reliant Windows standards, "
        "final site measurements prior to fabrication, and warranty-backed workmanship."
    )
    return " ".join(lines)

def _dynamic_lengths(text: str) -> tuple[int, int]:
    """
    Choose min/max lengths based on input size to avoid warnings
    and keep summaries concise.
    """
    wc = max(1, len(text.split()))
    dyn_max = min(MAX_LEN, max(48, int(wc * 0.8)))   # cap at 80% of input words
    dyn_min = min(MIN_LEN, max(24, int(wc * 0.4)))   # ~40% of input words
    # Ensure dyn_min < dyn_max
    if dyn_min >= dyn_max:
        dyn_min = max(16, dyn_max - 8)
    return dyn_min, dyn_max

def _summarize(text: str) -> str:
    nlp = _load_pipeline()
    if not nlp:
        raise RuntimeError(f"Transformers pipeline unavailable: {_LAST_ERR or 'unknown'}")

    if _is_t5_family(HF_MODEL):
        text = "summarize: " + text

    dyn_min, dyn_max = _dynamic_lengths(text)
    args = dict(
        max_length=dyn_max,
        min_length=dyn_min,
        no_repeat_ngram_size=NO_REPEAT_NGRAM,
        truncation=True
    )
    if DO_SAMPLE:
        args.update(dict(do_sample=True, top_p=TOP_P, temperature=TEMPERATURE, num_return_sequences=1))
    else:
        args.update(dict(num_beams=NUM_BEAMS))

    out = nlp(text, **args)
    return out[0]["summary_text"].strip()

def _fallback_summary(customer_name: str, product_list: List[dict], total_amount: float) -> str:
    seen, names = set(), []
    for p in product_list:
        n = p.get("name") or "product"
        if n not in seen:
            names.append(n); seen.add(n)
    name_str = ", ".join(names[:6]) + ("..." if len(names) > 6 else "") if names else "the specified products"
    return (
        f"This quotation for {customer_name} covers supply and installation of "
        f"{len(product_list)} item type(s) ({name_str}) with a total value of "
        f"${total_amount:,.2f}. The scope includes site verification, fabrication to "
        f"final measurements, and installation aligned with Reliant Windows standards."
    )

def generate_quote_summary(customer_name: str, product_list: List[dict], total_amount: float) -> str:
    src = _build_source_text(customer_name, product_list, total_amount)
    try:
        s = _summarize(src)
        print(f"[summary_generator] Used model: {HF_MODEL} | sampling={DO_SAMPLE}")
        return s
    except Exception as e:
        print(f"[summary_generator] Falling back to template. Reason: {e}")
        return _fallback_summary(customer_name, product_list, total_amount)
