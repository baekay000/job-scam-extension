document.getElementById("checkBtn").addEventListener("click", async () => {
    const jobText = document.getElementById("jobText").value;
    const resultEl = document.getElementById("result");

    if (!jobText) {
        resultEl.textContent = "Please enter job posting text.";
        return;
    }

    try {
        const response = await fetch("http://127.0.0.1:5000/check_job", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: jobText })
        });
        const data = await response.json();
        resultEl.textContent = data.output || data.error;
    } catch (err) {
        resultEl.textContent = "Error connecting to Python server:\n" + err;
    }
});
