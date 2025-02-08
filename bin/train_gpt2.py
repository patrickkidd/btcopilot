import pandas as pd
import numpy as np
import re
from PyPDF2 import PdfReader
import os
import docx


# Functions to read different file types
def read_pdf(file_path):
    with open(file_path, "rb") as file:
        pdf_reader = PdfReader(file)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            text += pdf_reader.pages[page_num].extract_text()
    return text


def read_word(file_path):
    doc = docx.Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text


def read_txt(file_path):
    with open(file_path, "r") as file:
        text = file.read()
    return text


def read_documents_from_directory(directory):
    combined_text = ""
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if filename.endswith(".pdf"):
            combined_text += read_pdf(file_path)
        elif filename.endswith(".docx"):
            combined_text += read_word(file_path)
        elif filename.endswith(".txt"):
            combined_text += read_txt(file_path)
    return combined_text


# # Read documents from the directory
# # train_directory = '/content/drive/MyDrive/ColabNotebooks/data/chatbot_docs/training_data/full_text'
# train_directory = (
#     "/content/drive/MyDrive/ColabNotebooks/data/chatbot_docs/training_data/q_and_a"
# )
# with open(
#     "/Users/patrick/Documents/2\ -\ Work/2\ -\ Alaska\ Family\ Systems/2\ -\ Family\ Diagram\ App/Copilot/FTiCP.txt"
# ) as f:
#     text_data = f.read()
# text_data = re.sub(r"\n+", "\n", text_data).strip()  # Remove excess newline characters


from transformers import TextDataset, DataCollatorForLanguageModeling
from transformers import GPT2Tokenizer, GPT2LMHeadModel
from transformers import Trainer, TrainingArguments


def load_dataset(file_path, tokenizer, block_size=128):
    dataset = TextDataset(
        tokenizer=tokenizer,
        file_path=file_path,
        block_size=block_size,
    )
    return dataset


def load_data_collator(tokenizer, mlm=False):
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=mlm,
    )
    return data_collator


def train(
    train_file_path,
    model_name,
    output_dir,
    overwrite_output_dir,
    per_device_train_batch_size,
    num_train_epochs,
    save_steps,
):
    tokenizer = GPT2Tokenizer.from_pretrained(model_name)
    train_dataset = load_dataset(train_file_path, tokenizer)
    data_collator = load_data_collator(tokenizer)

    tokenizer.save_pretrained(output_dir)

    model = GPT2LMHeadModel.from_pretrained(model_name)

    model.save_pretrained(output_dir)

    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=overwrite_output_dir,
        per_device_train_batch_size=per_device_train_batch_size,
        num_train_epochs=num_train_epochs,
        save_total_limit=3,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=data_collator,
        train_dataset=train_dataset,
    )

    trainer.train()
    trainer.save_model()


import tempfile


# train_file_path = "/content/drive/MyDrive/ColabNotebooks/data/chatbot_docs/combined_text/full_text/train.txt"
TRAIN_FILE_PATH = "Sources/FTiCP.txt"

temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
with open(TRAIN_FILE_PATH, "r") as f:
    sdata = f.read()
    cleaned = re.sub(r"\n+", "\n", sdata).strip()  # Remove excess newline characters
    temp_file.write(cleaned)
temp_file.close()


model_name = "gpt2"
# output_dir = '/content/drive/MyDrive/ColabNotebooks/models/chat_models/custom_full_text'
output_dir = "/Users/patrick/Documents/2 - Work/2 - Alaska Family Systems/2 - Family Diagram App/Copilot/output-multi"
overwrite_output_dir = False
per_device_train_batch_size = 8
num_train_epochs = 50.0
save_steps = 50000


# Train
train(
    train_file_path=temp_file.name,
    model_name=model_name,
    output_dir=output_dir,
    overwrite_output_dir=overwrite_output_dir,
    per_device_train_batch_size=per_device_train_batch_size,
    num_train_epochs=num_train_epochs,
    save_steps=save_steps,
)
