import sys
import sys
import re
import fitz  # PyMuPDF

FILE_PATH = sys.argv[1]


def continuous_text(file_path):
    doc = fitz.open(file_path)
    full_text = []
    previous_line = ""

    for page in doc:
        # Extract text with layout preservation
        text = page.get_text("text")

        # Remove page number if it's at the end (like "363" or "364")
        text = re.sub(r"\n\d+\s*$", "", text)

        # Handle hyphenated words across page breaks
        if previous_line.endswith("-"):
            previous_line = previous_line[:-1]  # Remove the hyphen
            full_text[-1] = previous_line  # Update last line
            # Join with first word of new page
            if text:
                first_word = text.split()[0] if text.split() else ""
                remaining_text = (
                    " ".join(text.split()[1:]) if len(text.split()) > 1 else ""
                )
                full_text[-1] += first_word
                text = remaining_text

        # Add current page text
        if text:
            lines = text.split("\n")
            # Join with previous content if not a new paragraph
            if full_text and not (
                full_text[-1].endswith((".", "!", "?"))
                or lines[0].startswith((" ", "\t"))
            ):
                full_text[-1] += " " + lines[0]
                full_text.extend(lines[1:])
            else:
                full_text.extend(lines)

            # Store last line for potential hyphen handling
            if lines:
                previous_line = lines[-1]

    # Join all lines and clean up
    continuous_text = " ".join(full_text)
    # Remove any remaining page references like [24] or [25]
    continuous_text = re.sub(r"\[\d+\]", "", continuous_text)
    # Clean up multiple spaces
    continuous_text = " ".join(continuous_text.split())
    return continuous_text


def clean_extracted_text(file_path):
    doc = fitz.open(file_path)
    full_text = []
    previous_line = ""

    for page in doc:
        # Extract text with layout preservation
        text = page.get_text("text")

        # Remove page number if it's at the end (like "363" or "364")
        text = re.sub(r"\n\d+\s*$", "", text)

        # Handle hyphenated words across page breaks
        if previous_line.endswith("-"):
            previous_line = previous_line[:-1]  # Remove the hyphen
            full_text[-1] = previous_line  # Update last line
            # Join with first word of new page
            if text:
                first_word = text.split()[0] if text.split() else ""
                remaining_text = (
                    " ".join(text.split()[1:]) if len(text.split()) > 1 else ""
                )
                full_text[-1] += first_word
                text = remaining_text

        # Add current page text
        if text:
            lines = text.split("\n")
            # Join with previous content if not a new paragraph
            if full_text and not (
                full_text[-1].endswith((".", "!", "?"))
                or lines[0].startswith((" ", "\t"))
            ):
                full_text[-1] += " " + lines[0]
                full_text.extend(lines[1:])
            else:
                full_text.extend(lines)

            # Store last line for potential hyphen handling
            if lines:
                previous_line = lines[-1]

    # Join all lines and clean up
    continuous_text = " ".join(full_text)
    # Remove any remaining page references like [24] or [25]
    continuous_text = re.sub(r"\[\d+\]", "", continuous_text)
    # Clean up multiple spaces
    continuous_text = " ".join(continuous_text.split())
    return continuous_text


print(f"Converting {FILE_PATH} to markdown")


continuous_text = continuous_text(FILE_PATH)
print(continuous_text)
