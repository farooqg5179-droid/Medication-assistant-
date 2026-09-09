import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(BASE_DIR, "knowledge_base", "medications.json")

def tokens(text):
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))

def load_knowledge_base():
    with open(KB_PATH, "r", encoding="utf-8") as file:
        return json.load(file)

def retrieve_context(query, top_k=3):
    records = load_knowledge_base()
    query_tokens = tokens(query)
    results = []

    for medicine in records:
        searchable = " ".join([
            medicine.get("medicine_name", ""),
            medicine.get("generic_name", ""),
            medicine.get("common_uses", ""),
            medicine.get("common_side_effects", ""),
            medicine.get("serious_warnings", "")
        ])

        score = len(query_tokens.intersection(tokens(searchable)))

        if score > 0:
            results.append((score, medicine))

    results.sort(key=lambda item: item[0], reverse=True)

    selected = [item for score, item in results[:top_k]]

    if not selected:
        return "No matching information was found in the verified medication knowledge base."

    context = []

    for medicine in selected:
        context.append(
            f"Medicine: {medicine['medicine_name']}\n"
            f"Generic name: {medicine['generic_name']}\n"
            f"Common uses: {medicine['common_uses']}\n"
            f"Common side effects: {medicine['common_side_effects']}\n"
            f"Serious warnings: {medicine['serious_warnings']}\n"
            f"Source: {medicine['source']}"
        )

    return "\n\n---\n\n".join(context)
