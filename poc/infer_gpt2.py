from transformers import (
    PreTrainedTokenizerFast,
    GPT2LMHeadModel,
    GPT2TokenizerFast,
    GPT2Tokenizer,
)


def load_model(model_path):
    model = GPT2LMHeadModel.from_pretrained(model_path)
    return model


def load_tokenizer(tokenizer_path):
    tokenizer = GPT2Tokenizer.from_pretrained(tokenizer_path)
    return tokenizer


def generate_text(model_path, sequence, max_length):

    model = load_model(model_path)
    tokenizer = load_tokenizer(model_path)
    ids = tokenizer.encode(f"{sequence}", return_tensors="pt")
    final_outputs = model.generate(
        ids,
        do_sample=True,
        max_length=max_length,
        pad_token_id=model.config.eos_token_id,
        top_k=50,
        top_p=0.95,
    )
    print(tokenizer.decode(final_outputs[0], skip_special_tokens=True))


model1_path = "models/fticp-small"
sequence1 = "What is differentation of self?"
max_len = 500
text = generate_text(model1_path, sequence1, max_len)
print(f">>>{text}<<<")
