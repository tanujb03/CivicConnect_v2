"""CI helper: a tiny random-weight BERT + a WordPiece tokenizer trained on the given texts, saved like a Hugging Face model directory (no download, no GPU)."""
from pathlib import Path


def build_tiny_encoder(out: Path, texts: list[str], vocab_size: int = 600) -> Path:
    from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, processors, trainers
    from transformers import BertConfig, BertModel, PreTrainedTokenizerFast
    tok = Tokenizer(models.WordPiece(unk_token="[UNK]"))
    tok.normalizer = normalizers.BertNormalizer(lowercase=True)
    tok.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    specials = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    tok.train_from_iterator(texts, trainers.WordPieceTrainer(vocab_size=vocab_size, special_tokens=specials))
    tok.post_processor = processors.TemplateProcessing(single="[CLS] $A [SEP]", special_tokens=[("[CLS]", tok.token_to_id("[CLS]")), ("[SEP]", tok.token_to_id("[SEP]"))])
    fast = PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="[UNK]", pad_token="[PAD]", cls_token="[CLS]", sep_token="[SEP]", mask_token="[MASK]")
    out.mkdir(parents=True, exist_ok=True)
    fast.save_pretrained(out)
    cfg = BertConfig(vocab_size=tok.get_vocab_size(), hidden_size=48, num_hidden_layers=2, num_attention_heads=2, intermediate_size=96, max_position_embeddings=160,
                     pad_token_id=tok.token_to_id("[PAD]"))
    BertModel(cfg).save_pretrained(out)
    return out
