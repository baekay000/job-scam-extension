import requests
import json
import csv
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report
import matplotlib.pyplot as plt

# input testing file name here
filename = "archive/new_set.csv"
total = 0
correct = 0

true_labels = []
predicted_labels = []

with open("results.csv", "w", newline='', encoding='utf-8') as outfile:
    writer = csv.writer(outfile)
    writer.writerow(["Index", "True Label", "Predicted Label", "Reasoning", "Full Output"])

    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for i, row in enumerate(reader):
            if i >= 20:  # limit for testing
                break

            classification = int(row[-1].strip())
            row_text = " ".join(row[:-1]).strip()

            prompt = f"""
                You are a strict classifier. 
                Classify the following job posting as REAL, FAKE, or UNKNOWN.

                Rules:
                - First, explain your reasoning briefly under "Reasoning:".
                - Then, on a new line, write "Final Answer: " followed by exactly one of these words — REAL, FAKE, or UNKNOWN.

                Job posting:
                {row_text}
                """

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "mistral:7b", "prompt": prompt}
            )

            output = ""
            for line in response.iter_lines():
                if line:
                    output += json.loads(line.decode())["response"]

            output = output.lower()
            # Try to extract after "final answer:"
            if "final answer:" in output:
                final_answer = output.split("final answer:")[-1].strip()
            else:
                final_answer = output.strip()

            predicted_label = (
                0 if "real" in final_answer else
                1 if "fake" in final_answer else
                2
            )

            if predicted_label == classification:
                correct += 1
            total += 1

            reasoning = output.split("final answer:")[0].strip() if "final answer:" in output else ""
            writer.writerow([i, classification, predicted_label, reasoning, output])

            true_labels.append(classification)
            predicted_labels.append(predicted_label)

            print(f"[{i}] True: {classification}, Predicted: {predicted_label}")

# Show accuracy
accuracy = correct / total if total > 0 else 0
print(f"\nAccuracy: {accuracy:.2%}")

# --- Confusion Matrix and Metrics ---
labels = [0, 1, 2]
cm = confusion_matrix(true_labels, predicted_labels, labels=labels)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["REAL", "FAKE", "UNKNOWN"])
disp.plot(cmap="Blues")
plt.title("Job Posting Classifier Confusion Matrix")
plt.show()

print("\nClassification Report:")
print(classification_report(true_labels, predicted_labels, target_names=["REAL", "FAKE", "UNKNOWN"]))